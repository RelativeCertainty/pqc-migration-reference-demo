from __future__ import annotations

import re
from typing import Any, Mapping

from ..canonical import require_canonical_contract_pack
from ..contract_pack import ContractPack, ContractPackError, ContractPackLoader
from ..errors import PQCAdapterError
from ..models import (
    AdapterDiagnostic,
    DiagnosticLevel,
    ImportContext,
    NormalizedObservation,
    ProviderPage,
    RetryClass,
    Sensitivity,
)
from ..safety import (
    detect_sensitivity,
    normalize_timestamp,
    stable_sha256_id,
)
from .base import (
    asset_scope_ref,
    encode_page_cursor,
    normalized_context_times,
    source_ref,
)


MAX_INSTANCES_PER_CERTIFICATE = 2_000
FORBIDDEN_GENERIC_ENVELOPES = {"items", "results", "certificateDetails"}
KNOWN_STATUSES = {"ACTIVE", "EXPIRED", "REVOKED", "RETIRED", "PENDING", "UNKNOWN"}
KNOWN_DEPLOYMENT_STATUSES = {"ACTIVE", "DEPLOYED", "SUPERSEDED", "UNKNOWN"}
KNOWN_PROTOCOLS = {"SSLV2", "SSLV3", "TLSV1", "TLSV1.1", "TLSV1.2", "TLSV1.3"}
KNOWN_ALGORITHM_LABELS = {
    "SHA1WITHRSAENCRYPTION": "sha1_with_rsa_encryption",
    "SHA224WITHRSAENCRYPTION": "sha224_with_rsa_encryption",
    "SHA256WITHRSAENCRYPTION": "sha256_with_rsa_encryption",
    "SHA384WITHRSAENCRYPTION": "sha384_with_rsa_encryption",
    "SHA512WITHRSAENCRYPTION": "sha512_with_rsa_encryption",
    "ECDSAWITHSHA256": "ecdsa_with_sha256",
    "ECDSAWITHSHA384": "ecdsa_with_sha384",
    "ECDSAWITHSHA512": "ecdsa_with_sha512",
    "ED25519": "ed25519",
    "ED448": "ed448",
    "MLDSA": "ml_dsa",
    "SLHDSA": "slh_dsa",
    "MD5": "md5",
    "SHA1": "sha1",
    "SHA224": "sha224",
    "SHA256": "sha256",
    "SHA384": "sha384",
    "SHA512": "sha512",
    "SHA3256": "sha3_256",
    "SHA3384": "sha3_384",
    "SHA3512": "sha3_512",
}


def _record(value: object) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise PQCAdapterError("PQC_ADAPTER_SCHEMA_DRIFT", RetryClass.SCHEMA_DRIFT)
    return value


def _nonempty_text(
    record: Mapping[str, Any], key: str, *, maximum: int = 2_048
) -> str | None:
    value = record.get(key)
    if isinstance(value, str) and value.strip():
        return value[:maximum]
    return None


def _first_text(record: Mapping[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = _nonempty_text(record, key)
        if value is not None:
            return value
        native_list = record.get(key)
        if isinstance(native_list, list):
            for native_value in native_list[:100]:
                if isinstance(native_value, str) and native_value.strip():
                    return native_value[:2_048]
    return None


def _safe_int(value: object, *, maximum: int = 1_000_000) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= maximum:
        return value
    return None


def _algorithm(value: object) -> str:
    if not isinstance(value, str):
        return "unknown"
    normalized = re.sub(r"[^A-Z0-9]", "", value.upper())
    if normalized.startswith("RSA"):
        return "rsa"
    if normalized in {"EC", "ECC", "ECDSA", "ECDH"}:
        return "elliptic_curve"
    if normalized == "DSA":
        return "dsa"
    if normalized in {"MLDSA", "MLKEM", "SLHDSA"}:
        return normalized.lower()
    return "unknown"


def _normalized_status(value: object) -> str:
    if not isinstance(value, str):
        return "unknown"
    upper = value.upper()
    return upper.lower() if upper in KNOWN_STATUSES else "unknown"


def _normalized_algorithm_label(value: object) -> str:
    if not isinstance(value, str):
        return "unknown"
    normalized = re.sub(r"[^A-Z0-9]", "", value.upper())
    return KNOWN_ALGORITHM_LABELS.get(normalized, "unknown")


def _instance_summary(certificate: Mapping[str, Any]) -> tuple[int, str, str]:
    native_instances = certificate.get("instances", [])
    if native_instances is None:
        native_instances = []
    if not isinstance(native_instances, list):
        raise PQCAdapterError("PQC_ADAPTER_SCHEMA_DRIFT", RetryClass.SCHEMA_DRIFT)
    if len(native_instances) > MAX_INSTANCES_PER_CERTIFICATE:
        raise PQCAdapterError("PQC_ADAPTER_LIMIT_EXCEEDED", RetryClass.INVALID_REQUEST)
    protocols: set[str] = set()
    deployment_statuses: set[str] = set()
    for native_instance in native_instances:
        instance = _record(native_instance)
        native_protocols = instance.get("sslProtocols", [])
        if not isinstance(native_protocols, list) or len(native_protocols) > 32:
            raise PQCAdapterError("PQC_ADAPTER_SCHEMA_DRIFT", RetryClass.SCHEMA_DRIFT)
        for protocol in native_protocols:
            if isinstance(protocol, str):
                normalized = protocol.upper()
                if normalized in KNOWN_PROTOCOLS:
                    protocols.add(normalized.lower())
        status = instance.get("deploymentStatus")
        if isinstance(status, str) and status.upper() in KNOWN_DEPLOYMENT_STATUSES:
            deployment_statuses.add(status.lower())
    return (
        len(native_instances),
        ",".join(sorted(protocols)),
        ",".join(sorted(deployment_statuses)),
    )


class VenafiCertificateSearchAdapterBase:
    adapter_id: str
    pack_id: str
    provider: str
    product: str
    dialect: str

    def __init__(self, loader: ContractPackLoader | None = None) -> None:
        self.pack: ContractPack = (loader or ContractPackLoader()).load(self.pack_id)

    def adapt(self, payload: object, context: ImportContext) -> ProviderPage:
        tenant_id = context.tenant_id if isinstance(context, ImportContext) else ""
        require_canonical_contract_pack(self.pack, tenant_id=tenant_id)
        collected_at, package_generated_at, imported_at = normalized_context_times(
            context
        )
        root = _record(payload)
        if FORBIDDEN_GENERIC_ENVELOPES.intersection(root):
            raise PQCAdapterError(
                "PQC_ADAPTER_UNSUPPORTED_DIALECT", RetryClass.NOT_SUPPORTED
            )
        rows = root.get("certificates")
        count = root.get("count")
        if (
            not isinstance(rows, list)
            or not isinstance(count, int)
            or isinstance(count, bool)
        ):
            raise PQCAdapterError("PQC_ADAPTER_SCHEMA_DRIFT", RetryClass.SCHEMA_DRIFT)
        max_total = int(self.pack.manifest["limits"]["max_total_records"])
        max_page_size = int(self.pack.manifest["limits"]["max_page_size"])
        if count < len(rows) or count > max_total:
            raise PQCAdapterError(
                "PQC_ADAPTER_LIMIT_EXCEEDED", RetryClass.INVALID_REQUEST
            )
        if len(rows) > min(context.page_size, max_page_size):
            raise PQCAdapterError(
                "PQC_ADAPTER_LIMIT_EXCEEDED", RetryClass.INVALID_REQUEST
            )
        try:
            self.pack.validate_response(payload)
        except ContractPackError as exc:
            raise PQCAdapterError(
                "PQC_ADAPTER_SCHEMA_DRIFT", RetryClass.SCHEMA_DRIFT
            ) from exc

        sensitivity = detect_sensitivity(payload).sensitivity
        if sensitivity == Sensitivity.AUTH_SECRET:
            raise PQCAdapterError(
                "PQC_ADAPTER_AUTH_SECRET_INPUT", RetryClass.INVALID_REQUEST
            )
        observations: list[NormalizedObservation] = []
        diagnostics: list[AdapterDiagnostic] = []
        seen: set[str] = set()
        duplicates = 0
        scope_ref = asset_scope_ref(context)
        for native_certificate in rows:
            certificate = _record(native_certificate)
            if not certificate:
                raise PQCAdapterError(
                    "PQC_ADAPTER_SCHEMA_DRIFT", RetryClass.SCHEMA_DRIFT
                )
            certificate_id = _first_text(
                certificate, ("id", "managedCertificateId", "fingerprint")
            )
            if certificate_id is None:
                raise PQCAdapterError(
                    "PQC_ADAPTER_SCHEMA_DRIFT", RetryClass.SCHEMA_DRIFT
                )
            fingerprint = _nonempty_text(certificate, "fingerprint")
            subject = _first_text(certificate, ("subjectDN", "subjectCN"))
            issuer = _first_text(certificate, ("issuerDN", "issuerCN"))
            source_record_ref = stable_sha256_id(
                "venafi-certificate",
                scope_ref,
                self.dialect,
                certificate_id,
                fingerprint,
            )
            observation_id = stable_sha256_id(
                "observation", scope_ref, self.adapter_id, source_record_ref
            )
            if observation_id in seen:
                duplicates += 1
                continue
            seen.add(observation_id)
            instance_count, protocols, deployment_statuses = _instance_summary(
                certificate
            )
            key_strength = _safe_int(certificate.get("keyStrength"), maximum=1_000_000)
            observed_at = (
                normalize_timestamp(certificate.get("modificationDate")) or collected_at
            )
            validity_start = normalize_timestamp(certificate.get("validityStart"))
            validity_end = normalize_timestamp(certificate.get("validityEnd"))
            attributes = {
                "certificate_status": _normalized_status(
                    certificate.get("certificateStatus")
                ),
                "public_key_algorithm": _algorithm(certificate.get("encryptionType")),
                "key_strength_bits": key_strength,
                "signature_algorithm": _normalized_algorithm_label(
                    certificate.get("signatureAlgorithm")
                ),
                "signature_hash_algorithm": _normalized_algorithm_label(
                    certificate.get("signatureHashAlgorithm")
                ),
                "self_signed": certificate.get("selfSigned")
                if isinstance(certificate.get("selfSigned"), bool)
                else None,
                "validity_start": validity_start,
                "validity_end": validity_end,
                "managed": _nonempty_text(certificate, "managedCertificateId")
                is not None,
                "instance_count": instance_count,
                "tls_protocols": protocols,
                "deployment_statuses": deployment_statuses,
                "certificate_id_ref": stable_sha256_id(
                    "certificate-id", scope_ref, certificate_id
                ),
                "fingerprint_ref": stable_sha256_id(
                    "fingerprint", scope_ref, fingerprint
                )
                if fingerprint
                else None,
                "subject_ref": stable_sha256_id("subject", scope_ref, subject)
                if subject
                else None,
                "issuer_ref": stable_sha256_id("issuer", scope_ref, issuer)
                if issuer
                else None,
                "import_scope_ref": scope_ref,
            }
            observations.append(
                NormalizedObservation(
                    observation_id=observation_id,
                    provider=self.provider,
                    product=self.product,
                    dialect=self.dialect,
                    asset_type="certificate",
                    asset_ref=stable_sha256_id(
                        "asset-certificate",
                        scope_ref,
                        self.dialect,
                        certificate_id,
                        fingerprint,
                    ),
                    source_record_ref=source_record_ref,
                    observed_at=observed_at,
                    collected_at=collected_at,
                    package_generated_at=package_generated_at,
                    imported_at=imported_at,
                    attributes=attributes,
                    sensitivity=sensitivity,
                    synthetic=context.synthetic,
                    evidence_status=self.pack.evidence_status,
                )
            )

        if not rows:
            diagnostics.append(
                AdapterDiagnostic(DiagnosticLevel.INFORMATION, "empty_inventory_page")
            )
        if duplicates:
            diagnostics.append(
                AdapterDiagnostic(DiagnosticLevel.WARNING, "duplicate_record")
            )
        consumed = min(count, (context.page_number * context.page_size) + len(rows))
        next_page = context.page_number + 1
        next_cursor = None
        if consumed < count:
            if next_page >= min(
                context.max_pages, int(self.pack.manifest["limits"]["max_pages"])
            ):
                raise PQCAdapterError(
                    "PQC_ADAPTER_LIMIT_EXCEEDED", RetryClass.INVALID_REQUEST
                )
            next_cursor = encode_page_cursor(
                self.pack, self.adapter_id, source_ref(context), next_page
            )
        return ProviderPage(
            adapter_id=self.adapter_id,
            contract_pack_id=self.pack.pack_id,
            source_ref=source_ref(context),
            observations=tuple(observations),
            total_records=count,
            accepted_records=len(observations),
            skipped_records=0,
            duplicate_records=duplicates,
            page_number=context.page_number,
            next_cursor=next_cursor,
            sensitivity=sensitivity,
            diagnostics=tuple(diagnostics),
        )
