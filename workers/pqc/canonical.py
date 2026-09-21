from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Mapping

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from .contract_pack import ContractPack, ContractPackError
from .errors import PQCAdapterError
from .models import (
    EvidenceStatus,
    NormalizedObservation,
    RetryClass,
    Sensitivity,
)
from .safety import detect_sensitivity, normalize_timestamp


_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_ROOT = _ROOT / "schemas"
_TEST_CONFORMANCE_PATH = _ROOT / "tests" / "test_pqc_adapters.py"
_TENANT = re.compile(r"^[a-z][a-z0-9-]{1,62}[a-z0-9]$")
_REASON = re.compile(r"^[a-z][a-z0-9_.-]{1,127}$")
_DIGEST_REF = re.compile(r"^urn:pba:pqc:[a-z][a-z0-9._-]{1,47}:sha256:[0-9a-f]{64}$")

_PACK_PROFILES: Mapping[str, Mapping[str, str]] = {
    "snyk-code-sarif-2.1.0": {
        "adapter_id": "snyk-code-sarif-2.1.0",
        "vendor": "Snyk",
        "product": "Snyk Code CLI",
        "api_version": "SARIF 2.1.0",
        "provider_code": "snyk",
        "product_code": "snyk_code_cli",
        "canonical_api_version": "sarif-2.1.0",
    },
    "venafi-certificate-manager-saas-v1": {
        "adapter_id": "venafi-certificate-manager-saas-v1",
        "vendor": "CyberArk Venafi",
        "product": "Certificate Manager SaaS",
        "api_version": "outagedetection/v1",
        "provider_code": "cyberark_venafi",
        "product_code": "certificate_manager_saas",
        "canonical_api_version": "outagedetection/v1",
    },
    "venafi-ngts-outagedetection-v1": {
        "adapter_id": "venafi-ngts-outagedetection-v1",
        "vendor": "Palo Alto Networks Venafi",
        "product": "Next-Gen Trust Security",
        "api_version": "outagedetection/v1",
        "provider_code": "palo_alto_networks_venafi",
        "product_code": "next_gen_trust_security",
        "canonical_api_version": "outagedetection/v1",
    },
}

CONTRACT_NOT_ADMITTED_CODE = "PQC_ADAPTER_CONTRACT_NOT_ADMITTED"


class CanonicalProjectionError(ValueError):
    def __init__(self, code: str = "PQC_CANONICAL_PROJECTION_INVALID") -> None:
        super().__init__("PQC canonical projection failed validation")
        self.code = code


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _immutable_ref(
    *, identity: str, revision: str, digest: str, schema_id: str, schema_version: str
) -> dict[str, str]:
    return {
        "id": identity,
        "revision_id": revision,
        "content_sha256": digest,
        "schema_id": schema_id,
        "schema_version": schema_version,
    }


def _schema_validator(schema_name: str) -> Draft202012Validator:
    resources: list[tuple[str, Resource[object]]] = []
    for path in (
        _SCHEMA_ROOT / "common.ProductionAlignment.v1.schema.json",
        _SCHEMA_ROOT / schema_name,
    ):
        value = json.loads(path.read_text(encoding="utf-8"))
        resource = Resource.from_contents(value, default_specification=DRAFT202012)
        resources.append((value["$id"], resource))
    registry = Registry().with_resources(resources)
    target = json.loads((_SCHEMA_ROOT / schema_name).read_text(encoding="utf-8"))
    return Draft202012Validator(
        target, registry=registry, format_checker=FormatChecker()
    )


def _validate(schema_name: str, value: Mapping[str, object]) -> None:
    error = next(_schema_validator(schema_name).iter_errors(value), None)
    if error is not None:
        raise CanonicalProjectionError() from None


def _behavior(pack: ContractPack) -> dict[str, object]:
    manifest = pack.manifest
    auth_mode = str(manifest["authentication"]["mode"])
    if auth_mode == "oauth2_client_credentials":
        authentication_modes = ["oauth2_client_credentials"]
    elif auth_mode in {"api_key_header", "snyk_cli_file_export"}:
        authentication_modes = ["api_key"]
    else:
        raise CanonicalProjectionError()

    pagination = str(manifest["transport"]["pagination"])
    if pagination == "not_applicable":
        pagination_mode = "none"
    elif pagination == "zero_based_page_number_and_page_size":
        pagination_mode = "page"
    else:
        raise CanonicalProjectionError()

    rate_limit = str(manifest["transport"]["rate_limit"])
    rate_limit_mode = (
        "none_documented" if rate_limit == "not_applicable" else "retry_after"
    )
    return {
        "authentication_modes": authentication_modes,
        "pagination_mode": pagination_mode,
        "cursor_mode": "none",
        "rate_limit_mode": rate_limit_mode,
        "async_job_mode": "none",
        "webhook_mode": "none",
        "idempotency_mode": "native_key"
        if manifest["transport"]["idempotency"] == "content_sha256"
        else "none",
        "concurrency_mode": "none",
        "error_model": "operation_specific",
    }


def _project_contract_pack_manifest(
    pack: ContractPack, *, tenant_id: str
) -> dict[str, object]:
    """Project the admitted adapter-runtime pack into the canonical v1 contract.

    The historical adapter-runtime manifest remains an implementation detail. This
    function is the only admission bridge and validates the closed canonical
    contract before returning it.
    """

    if _TENANT.fullmatch(tenant_id) is None:
        raise CanonicalProjectionError()
    manifest = pack.manifest
    profile = _PACK_PROFILES.get(pack.pack_id)
    if profile is None:
        raise CanonicalProjectionError()
    for field in ("adapter_id", "vendor", "product", "api_version"):
        if str(manifest[field]) != profile[field]:
            raise CanonicalProjectionError()
    provider_code = profile["provider_code"]
    product_code = profile["product_code"]
    api_version = profile["canonical_api_version"]
    if (
        _REASON.fullmatch(provider_code) is None
        or _REASON.fullmatch(product_code) is None
    ):
        raise CanonicalProjectionError()

    artifacts: dict[str, str] = {}
    for item in manifest["artifacts"]:
        relative_path = str(item["path"])
        admitted_digest = str(item["sha256"])
        if _file_sha256(pack.artifact_path(relative_path)) != admitted_digest:
            raise CanonicalProjectionError()
        artifacts[relative_path] = admitted_digest
    runtime_digest = pack.content_digest
    revision = f"revision:sha256:{runtime_digest}"
    schema_id = "https://upm.pba.io/schemas/AdapterRuntimeContract.v1.schema.json"

    def artifact_ref(path: str, kind: str) -> dict[str, str]:
        try:
            digest = artifacts[path]
        except KeyError:
            raise CanonicalProjectionError() from None
        return _immutable_ref(
            identity=f"artifact:{pack.pack_id}:{kind}:{path}",
            revision=revision,
            digest=digest,
            schema_id=schema_id,
            schema_version="1.0.0",
        )

    sources = manifest["official_sources"]
    if not isinstance(sources, list) or not sources:
        raise CanonicalProjectionError()
    primary_source = sources[0]
    retrieved_at = f"{primary_source['retrieved_at']}T00:00:00Z"
    source_digest = _sha256(sources)
    terms_ref = _immutable_ref(
        identity=f"terms:{pack.pack_id}:interoperability-development",
        revision=revision,
        digest=_sha256(manifest["license"]),
        schema_id="https://upm.pba.io/schemas/ContractRightsAssessment.v1.schema.json",
        schema_version="1.0.0",
    )
    request_path = str(manifest["request_schema"])
    response_path = str(manifest["response_schema"])
    method = str(manifest["transport"]["method"])
    operation_method = "LOCAL_CALL" if method == "FILE" else method
    fixture_refs = [
        artifact_ref(str(path), "synthetic-fixture")
        for path in manifest["fixture_paths"]
    ]
    conformance_digest = _file_sha256(_TEST_CONFORMANCE_PATH)

    projected: dict[str, object] = {
        "contract_version": "pba.contract/ContractPackManifest.v1",
        "pack_id": pack.pack_id,
        "tenant_id": tenant_id,
        "revision_id": revision,
        "provider_code": provider_code,
        "product_code": product_code,
        "api_version": api_version,
        "pack_version": "1.0.0",
        "source": {
            "source_type": "official_documentation",
            "official_source_uri": primary_source["url"],
            "retrieved_at": retrieved_at,
            "source_sha256": source_digest,
            "provenance_quality": "verified",
        },
        "rights": {
            "use_status": "authorized",
            "redistribution_status": "private_only",
            "terms_ref": terms_ref,
        },
        "access_class": manifest["access_class"],
        "evidence_status": manifest["evidence_status"],
        "publication_status": "private_only",
        "admission_status": "accepted",
        "admission_reason_code": "contract_pack.runtime_projection_admitted",
        "behavior": _behavior(pack),
        "operations": [
            {
                "operation_id": "inventory.import"
                if operation_method == "LOCAL_CALL"
                else "inventory.search",
                "operation_class": "inventory_read",
                "method": operation_method,
                "request_schema_ref": artifact_ref(request_path, "request-schema"),
                "response_schema_ref": artifact_ref(response_path, "response-schema"),
                "mapping_contract_ref": _immutable_ref(
                    identity=f"mapping:{pack.adapter_id}:v1",
                    revision=revision,
                    digest=runtime_digest,
                    schema_id=schema_id,
                    schema_version="1.0.0",
                ),
                "side_effecting": False,
            }
        ],
        "fixture_refs": fixture_refs,
        "simulator_ref": artifact_ref(
            str(manifest["simulator_scenarios"]), "simulator-scenarios"
        ),
        "conformance_suite_ref": _immutable_ref(
            identity="test:pqc-adapter-conformance:v1",
            revision=f"revision:sha256:{conformance_digest}",
            digest=conformance_digest,
            schema_id="https://upm.pba.io/schemas/PQCAdapterConformanceSuite.v1.schema.json",
            schema_version="1.0.0",
        ),
        "classification": {
            "data_class": "internal",
            "data_sensitivity": ["operational"],
            "regulatory_scope": ["none"],
        },
        "canonical_content_sha256": "0" * 64,
    }
    unsigned = copy.deepcopy(projected)
    unsigned.pop("canonical_content_sha256")
    projected["canonical_content_sha256"] = _sha256(unsigned)
    _validate("ContractPackManifest.v1.schema.json", projected)
    return projected


def canonical_contract_pack_manifest(
    pack: ContractPack, *, tenant_id: str
) -> dict[str, object]:
    """Return a closed canonical pack contract or one sanitized projection error."""

    try:
        return _project_contract_pack_manifest(pack, tenant_id=tenant_id)
    except CanonicalProjectionError:
        raise
    except Exception:
        # The adapter boundary must never echo a malformed pack field or local path.
        raise CanonicalProjectionError() from None


def _project_crypto_observation(
    observation: NormalizedObservation,
    *,
    tenant_id: str,
    source_event_ref: str,
    integration_profile_ref: str,
) -> dict[str, object]:
    if (
        _TENANT.fullmatch(tenant_id) is None
        or not source_event_ref
        or not integration_profile_ref
        or observation.sensitivity == Sensitivity.AUTH_SECRET
        or _DIGEST_REF.fullmatch(observation.observation_id) is None
        or _DIGEST_REF.fullmatch(observation.asset_ref) is None
        or _DIGEST_REF.fullmatch(source_event_ref) is None
        or _DIGEST_REF.fullmatch(integration_profile_ref) is None
    ):
        raise CanonicalProjectionError()

    observed_at = normalize_timestamp(observation.observed_at)
    collected_at = normalize_timestamp(observation.collected_at)
    package_generated_at = normalize_timestamp(observation.package_generated_at)
    ingested_at = normalize_timestamp(observation.imported_at)
    if None in (observed_at, collected_at, package_generated_at, ingested_at):
        raise CanonicalProjectionError()

    facts = {
        "provider": observation.provider,
        "product": observation.product,
        "dialect": observation.dialect,
        "asset_type": observation.asset_type,
        "source_record_ref": observation.source_record_ref,
        "attributes": dict(observation.attributes),
        "sensitivity": observation.sensitivity.value,
        "synthetic": observation.synthetic,
        "package_generated_at": package_generated_at,
    }
    if detect_sensitivity(facts).sensitivity == Sensitivity.AUTH_SECRET:
        raise CanonicalProjectionError()
    if observation.sensitivity == Sensitivity.CONFIDENTIAL_METADATA:
        classification = {
            "data_class": "confidential",
            "data_sensitivity": ["operational"],
            "regulatory_scope": ["none"],
        }
    else:
        classification = {
            "data_class": "internal",
            "data_sensitivity": ["none"],
            "regulatory_scope": ["none"],
        }
    evidence_quality = (
        "verified"
        if observation.evidence_status
        in {EvidenceStatus.LIVE_READBACK, EvidenceStatus.CLOSED_LOOP}
        else "partially_verified"
    )
    projected: dict[str, object] = {
        "contract_version": "pba.contract/CryptoObservation.v2",
        "observation_id": observation.observation_id,
        "tenant_id": tenant_id,
        "source_event_ref": source_event_ref,
        "asset_ref": observation.asset_ref,
        "integration_profile_ref": integration_profile_ref,
        "observation_kind": "imported_evidence",
        "disposition": "present",
        "facts_sha256": _sha256(facts),
        "confidence": 1.0 if observation.synthetic else 0.8,
        "classification": classification,
        "evidence_visibility": "public_synthetic"
        if observation.synthetic
        else "private_tenant",
        "evidence_quality": evidence_quality,
        "integration_status": observation.evidence_status.value,
        "observed_at": observed_at,
        "collected_at": collected_at,
        "ingested_at": ingested_at,
        "contains_raw_payload": False,
        "canonical_content_sha256": "0" * 64,
    }
    unsigned = copy.deepcopy(projected)
    unsigned.pop("canonical_content_sha256")
    projected["canonical_content_sha256"] = _sha256(unsigned)
    _validate("CryptoObservation.v2.schema.json", projected)
    return projected


def canonical_crypto_observation(
    observation: NormalizedObservation,
    *,
    tenant_id: str,
    source_event_ref: str,
    integration_profile_ref: str,
) -> dict[str, object]:
    """Return metadata-only CryptoObservation.v2 or a sanitized projection error."""

    try:
        return _project_crypto_observation(
            observation,
            tenant_id=tenant_id,
            source_event_ref=source_event_ref,
            integration_profile_ref=integration_profile_ref,
        )
    except CanonicalProjectionError:
        raise
    except Exception:
        raise CanonicalProjectionError() from None


def _contract_not_admitted() -> PQCAdapterError:
    return PQCAdapterError(CONTRACT_NOT_ADMITTED_CODE, RetryClass.NOT_SUPPORTED)


def require_canonical_contract_pack(
    pack: ContractPack, *, tenant_id: str
) -> dict[str, object]:
    """Fail closed with one adapter-safe error when a pack is not admitted."""

    try:
        return canonical_contract_pack_manifest(pack, tenant_id=tenant_id)
    except (CanonicalProjectionError, ContractPackError):
        raise _contract_not_admitted() from None


def require_canonical_crypto_observation(
    observation: NormalizedObservation,
    *,
    tenant_id: str,
    source_event_ref: str,
    integration_profile_ref: str,
) -> dict[str, object]:
    """Fail closed with the same adapter-safe error at the canonical boundary."""

    try:
        return canonical_crypto_observation(
            observation,
            tenant_id=tenant_id,
            source_event_ref=source_event_ref,
            integration_profile_ref=integration_profile_ref,
        )
    except CanonicalProjectionError:
        raise _contract_not_admitted() from None
