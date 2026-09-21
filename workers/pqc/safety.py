from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from .errors import PQCAdapterError
from .models import RetryClass, Sensitivity


SAFE_ID_PREFIX = re.compile(r"^[a-z][a-z0-9._-]{1,47}$")
SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+-]{0,159}$")
SAFE_ESTATE_CLASSES = {
    "source_code",
    "pki_trust",
    "protocol_endpoint",
    "workload_identity",
    "cryptographic_service",
}
_AUTH_SECRET_KEYS = {
    "apikey",
    "accesstoken",
    "authtoken",
    "clientsecret",
    "credential",
    "credentials",
    "keymaterial",
    "password",
    "privatekey",
    "secret",
    "secrets",
    "token",
}
_CONFIDENTIAL_METADATA_KEYS = {
    "artifactlocation",
    "certificateid",
    "companyid",
    "fingerprint",
    "hostname",
    "ipaddress",
    "issuerdn",
    "message",
    "path",
    "serialnumber",
    "snippet",
    "subjectcn",
    "subjectdn",
    "uri",
}
_PEM_MARKERS = (
    "-----BEGIN " + "PRIVATE KEY-----",  # defensive marker, no key material
    "-----BEGIN " + "RSA PRIVATE KEY-----",
    "-----BEGIN " + "EC PRIVATE KEY-----",
    "-----BEGIN " + "OPENSSH PRIVATE KEY-----",
)


@dataclass(frozen=True)
class SensitivityReport:
    sensitivity: Sensitivity
    reason_codes: tuple[str, ...]


def stable_sha256_id(prefix: str, *parts: object) -> str:
    if not SAFE_ID_PREFIX.fullmatch(prefix):
        raise ValueError("unsafe identifier prefix")
    digest = hashlib.sha256()
    digest.update(b"pba.pqc.id.v1\x00")
    digest.update(prefix.encode("ascii"))
    for part in parts:
        digest.update(b"\x00")
        if part is None:
            digest.update(b"<null>")
        elif isinstance(part, (str, int, float, bool)):
            digest.update(str(part).encode("utf-8", errors="replace"))
        else:
            canonical = json.dumps(
                part,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                default=str,
            )
            digest.update(canonical.encode("ascii"))
    return f"urn:pba:pqc:{prefix}:sha256:{digest.hexdigest()}"


def sha256_hex(value: str | bytes) -> str:
    raw = value.encode("utf-8", errors="replace") if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()


def safe_label(
    value: object, *, fallback: str = "unknown", max_length: int = 160
) -> str:
    if not isinstance(value, str):
        return fallback
    cleaned = " ".join(value.replace("\x00", " ").split()).strip()
    if not cleaned:
        return fallback
    candidate = cleaned[:max_length]
    if not SAFE_LABEL.fullmatch(candidate):
        return fallback
    return candidate


def normalize_timestamp(value: object) -> str | None:
    if not isinstance(value, str) or not value.isascii() or len(value) > 40:
        return None
    candidate = value.strip()
    if re.search(r"[+-]\d{4}$", candidate):
        candidate = f"{candidate[:-5]}{candidate[-5:-2]}:{candidate[-2:]}"
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    normalized = parsed.astimezone(timezone.utc)
    return normalized.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def require_timestamp(value: object) -> str:
    normalized = normalize_timestamp(value)
    if normalized is None:
        raise PQCAdapterError("PQC_ADAPTER_INVALID_INPUT", RetryClass.INVALID_REQUEST)
    return normalized


def validate_context(context: object) -> None:
    from .models import ImportContext

    if not isinstance(context, ImportContext):
        raise PQCAdapterError("PQC_ADAPTER_INVALID_INPUT", RetryClass.INVALID_REQUEST)
    if not context.tenant_id or len(context.tenant_id) > 128:
        raise PQCAdapterError("PQC_ADAPTER_INVALID_INPUT", RetryClass.INVALID_REQUEST)
    if not context.source_name or len(context.source_name) > 256:
        raise PQCAdapterError("PQC_ADAPTER_INVALID_INPUT", RetryClass.INVALID_REQUEST)
    if not context.asset_key or len(context.asset_key) > 256:
        raise PQCAdapterError("PQC_ADAPTER_INVALID_INPUT", RetryClass.INVALID_REQUEST)
    if not context.asset_name or len(context.asset_name) > 256:
        raise PQCAdapterError("PQC_ADAPTER_INVALID_INPUT", RetryClass.INVALID_REQUEST)
    if context.estate_class not in SAFE_ESTATE_CLASSES:
        raise PQCAdapterError("PQC_ADAPTER_INVALID_INPUT", RetryClass.INVALID_REQUEST)
    if context.page_number < 0 or not 1 <= context.page_size <= 500:
        raise PQCAdapterError("PQC_ADAPTER_LIMIT_EXCEEDED", RetryClass.INVALID_REQUEST)
    if not 1 <= context.max_pages <= 2_000 or context.page_number >= context.max_pages:
        raise PQCAdapterError("PQC_ADAPTER_LIMIT_EXCEEDED", RetryClass.INVALID_REQUEST)
    if context.timestamps.collected_at is not None:
        require_timestamp(context.timestamps.collected_at)
    require_timestamp(context.timestamps.package_generated_at)
    require_timestamp(context.timestamps.imported_at)


def detect_sensitivity(
    payload: object, *, max_nodes: int = 100_000
) -> SensitivityReport:
    reason_codes: set[str] = set()
    stack: list[tuple[object, int]] = [(payload, 0)]
    visited = 0
    while stack:
        value, depth = stack.pop()
        visited += 1
        if visited > max_nodes or depth > 24:
            reason_codes.add("payload_bounds_exceeded")
            break
        if isinstance(value, dict):
            for native_key, child in value.items():
                key = re.sub(r"[^a-z0-9]", "", str(native_key).lower())
                if key in _AUTH_SECRET_KEYS:
                    reason_codes.add("credential_field_present")
                elif key in _CONFIDENTIAL_METADATA_KEYS:
                    reason_codes.add("private_operational_metadata_present")
                stack.append((child, depth + 1))
        elif isinstance(value, (list, tuple)):
            stack.extend((child, depth + 1) for child in value)
        elif isinstance(value, str):
            upper = value.upper()
            if any(marker in upper for marker in _PEM_MARKERS):
                reason_codes.add("private_key_material_present")
    if reason_codes & {"credential_field_present", "private_key_material_present"}:
        sensitivity = Sensitivity.AUTH_SECRET
    elif reason_codes:
        sensitivity = Sensitivity.CONFIDENTIAL_METADATA
    else:
        sensitivity = Sensitivity.NONE
    return SensitivityReport(sensitivity, tuple(sorted(reason_codes)))


def highest_sensitivity(values: Iterable[Sensitivity]) -> Sensitivity:
    priority = {
        Sensitivity.NONE: 0,
        Sensitivity.CONFIDENTIAL_METADATA: 1,
        Sensitivity.AUTH_SECRET: 2,
    }
    return max(values, key=priority.__getitem__, default=Sensitivity.NONE)
