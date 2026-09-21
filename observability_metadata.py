from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from scripts.schema_registry import build_registry


REPO_ROOT = Path(__file__).resolve().parent
INGRESS_SCHEMA_PATH = REPO_ROOT / "schemas" / "ObservabilityMetadataIngress.v1.schema.json"
SOURCE_PROFILES_PATH = REPO_ROOT / "data" / "observability" / "source_profiles.v1.yaml"
INGRESS_SCHEMA_VERSION = "pba.observability.metadata-ingress.v1"
ADAPTER_CONTRACT = "metadata_only_v1"

SOURCE_KINDS = {
    "journal_metadata",
    "loki_metadata",
    "stdout_structured",
    "otel_span",
    "model_runtime",
    "adapter_health",
}

REFERENCE_KEYS = (
    "artifact_refs",
    "observation_refs",
    "relationship_refs",
    "policy_refs",
    "capability_refs",
    "audit_refs",
    "lineage_refs",
)

REDACTION_CONTRACT: Dict[str, Any] = {
    "mode": ADAPTER_CONTRACT,
    "payload_included": False,
    "message_included": False,
    "content_included": False,
    "path_included": False,
    "exception_included": False,
}

_TRACEPARENT_PARTS = 4
_MAX_REFS_PER_KIND = 12
_SOURCE_REF_RE = re.compile(r"^source\.[a-z0-9][a-z0-9._-]{2,126}$")
_PROFILE_KEYS = {
    "source_ref",
    "source_kind",
    "classification_mode",
    "event_subtype_prefixes",
    "fixed_classification",
}


class MetadataIngressError(ValueError):
    """A safe, value-free validation error for metadata ingress records."""


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_copy(value: Any, *, error_message: str) -> Any:
    try:
        return json.loads(json.dumps(value))
    except (TypeError, ValueError, RecursionError):
        raise MetadataIngressError(error_message) from None


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = json.loads(INGRESS_SCHEMA_PATH.read_text(encoding="utf-8"))
    schema_source_kinds = set(schema.get("properties", {}).get("source_kind", {}).get("enum", []))
    if schema_source_kinds != SOURCE_KINDS:
        raise MetadataIngressError("metadata ingress source-kind definitions are inconsistent")
    return Draft202012Validator(
        schema,
        registry=build_registry(schema, INGRESS_SCHEMA_PATH),
        format_checker=FormatChecker(),
    )


@lru_cache(maxsize=1)
def load_source_profiles() -> Dict[str, Dict[str, Any]]:
    try:
        raw = yaml.safe_load(SOURCE_PROFILES_PATH.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        raise MetadataIngressError("source profile catalog could not be loaded") from None
    if not isinstance(raw, dict) or set(raw) != {"apiVersion", "kind", "metadata", "spec"}:
        raise MetadataIngressError("source profile catalog is invalid")
    if raw.get("apiVersion") != "pba.observability/v1" or raw.get("kind") != "ObservabilitySourceProfileCatalog":
        raise MetadataIngressError("source profile catalog version is invalid")
    metadata = raw.get("metadata")
    if not isinstance(metadata, dict) or set(metadata) != {"name", "version"}:
        raise MetadataIngressError("source profile catalog metadata is invalid")
    spec = raw.get("spec") if isinstance(raw, dict) else {}
    if not isinstance(spec, dict) or set(spec) != {"adapter_contract", "profiles"}:
        raise MetadataIngressError("source profile catalog specification is invalid")
    if spec.get("adapter_contract") != ADAPTER_CONTRACT:
        raise MetadataIngressError("source profile catalog adapter contract is invalid")
    profiles = spec.get("profiles") if isinstance(spec, dict) else []
    result: Dict[str, Dict[str, Any]] = {}
    if not isinstance(profiles, list):
        raise MetadataIngressError("source profile catalog is invalid")
    for profile in profiles:
        if not isinstance(profile, dict):
            raise MetadataIngressError("source profile catalog contains an invalid profile")
        source_ref = str(profile.get("source_ref") or "").strip()
        if set(profile) - _PROFILE_KEYS or not _SOURCE_REF_RE.fullmatch(source_ref) or source_ref in result:
            raise MetadataIngressError("source profile catalog contains an invalid source reference")
        source_kind = profile.get("source_kind")
        if source_kind not in SOURCE_KINDS:
            raise MetadataIngressError("source profile catalog contains an invalid source kind")
        prefixes = profile.get("event_subtype_prefixes")
        if (
            not isinstance(prefixes, list)
            or not prefixes
            or len(prefixes) > 12
            or any(not isinstance(prefix, str) or not prefix.endswith(".") or len(prefix) > 120 for prefix in prefixes)
        ):
            raise MetadataIngressError("source profile catalog contains invalid event subtype prefixes")
        mode = profile.get("classification_mode")
        fixed = profile.get("fixed_classification")
        if mode == "required_from_producer":
            if fixed is not None:
                raise MetadataIngressError("producer-classified source profile cannot set a fixed classification")
        elif mode == "fixed_platform_operational":
            if fixed != {
                "data_class": "internal",
                "data_sensitivity": "operational",
                "regulatory_scope": "none",
            }:
                raise MetadataIngressError("fixed source profile classification is invalid")
        else:
            raise MetadataIngressError("source profile catalog classification mode is invalid")
        result[source_ref] = dict(profile)
    if {profile["source_kind"] for profile in result.values()} != SOURCE_KINDS:
        raise MetadataIngressError("source profile catalog does not cover every source kind")
    return result


def _validation_path(error: Any) -> str:
    parts = [str(item) for item in getattr(error, "absolute_path", [])]
    return ".".join(parts) if parts else "record"


def validate_metadata_ingress(record: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(record, Mapping):
        raise MetadataIngressError("metadata ingress record must be an object")
    copied = _json_copy(record, error_message="metadata ingress record is not JSON-compatible")
    errors = sorted(_validator().iter_errors(copied), key=lambda item: list(item.absolute_path))
    if errors:
        paths = sorted({_validation_path(error) for error in errors})
        raise MetadataIngressError("metadata ingress validation failed at: " + ", ".join(paths[:8]))
    try:
        observed_at = str(copied["observed_at"])
        parsed_observed_at = dt.datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise MetadataIngressError("metadata ingress validation failed at: observed_at") from None
    if "T" not in observed_at.upper() or parsed_observed_at.tzinfo is None:
        raise MetadataIngressError("metadata ingress validation failed at: observed_at")

    source_ref = copied["source_ref"]
    profile = load_source_profiles().get(source_ref)
    if profile is None:
        raise MetadataIngressError("metadata ingress source_ref is not registered")
    if copied["source_kind"] != profile.get("source_kind"):
        raise MetadataIngressError("metadata ingress source kind does not match its registered profile")

    subtype = str(copied["activity"]["event_subtype"])
    prefixes = [str(item) for item in profile.get("event_subtype_prefixes") or []]
    if not prefixes or not any(subtype.startswith(prefix) for prefix in prefixes):
        raise MetadataIngressError("metadata ingress event subtype is not allowed for its source profile")

    classification_mode = profile.get("classification_mode")
    if classification_mode == "fixed_platform_operational":
        fixed = profile.get("fixed_classification")
        if copied.get("classification") != fixed:
            raise MetadataIngressError("metadata ingress classification does not match its fixed source profile")
    elif classification_mode != "required_from_producer":
        raise MetadataIngressError("metadata ingress source profile classification mode is invalid")

    if copied["source_kind"] == "model_runtime":
        if not isinstance(copied.get("model"), dict):
            raise MetadataIngressError("model runtime ingress requires governed model metadata")
        if not copied.get("scope", {}).get("model_invocation_id"):
            raise MetadataIngressError("model runtime ingress requires model_invocation_id")
    elif "model" in copied:
        raise MetadataIngressError("model metadata is only allowed for model runtime ingress")

    return copied


def metadata_ingress_event_ref(record: Mapping[str, Any]) -> str:
    """Return the immutable source identity, excluding mutable event content.

    Any change to activity, trace, classification, or other metadata for the
    same registered upstream identity therefore reaches the fingerprint
    conflict path instead of silently creating a second canonical event.
    """
    identity = {
        "schema_version": record.get("schema_version"),
        "source_kind": record.get("source_kind"),
        "source_ref": record.get("source_ref"),
        "upstream_event_id": record.get("upstream_event_id"),
    }
    digest = _sha256_text(_canonical_json(identity))
    return f"event.adapter.v1.{record.get('source_kind')}.{digest}"


def metadata_ingress_fingerprint(record: Mapping[str, Any]) -> str:
    return _sha256_text(_canonical_json(record))


def _bounded_refs(required: Iterable[str], supplied: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in (*required, *supplied):
        if value not in result:
            result.append(value)
        if len(result) == _MAX_REFS_PER_KIND:
            break
    return result


def _default_refs(record: Mapping[str, Any]) -> Dict[str, list[str]]:
    source_kind = str(record["source_kind"])
    refs = record.get("refs") if isinstance(record.get("refs"), Mapping) else {}
    projected: Dict[str, list[str]] = {}
    for key in REFERENCE_KEYS:
        values = refs.get(key) if isinstance(refs, Mapping) else None
        projected[key] = _bounded_refs((), values if isinstance(values, list) else ())

    projected["policy_refs"] = _bounded_refs(
        (
            "policy.pba.observability.metadata_ingress",
            f"policy.pba.observability.source.{source_kind}",
        ),
        projected["policy_refs"],
    )
    projected["capability_refs"] = _bounded_refs(
        (f"capability.observability.source.{source_kind}.project",),
        projected["capability_refs"],
    )
    projected["lineage_refs"] = _bounded_refs(
        (f"event.source.{source_kind}",),
        projected["lineage_refs"],
    )
    return projected


def build_observability_event_from_metadata(record: Mapping[str, Any]) -> Dict[str, Any]:
    ingress = validate_metadata_ingress(record)
    scope = ingress["scope"]
    activity = ingress["activity"]
    trace = ingress["trace"]
    event_ref = metadata_ingress_event_ref(ingress)
    fingerprint = metadata_ingress_fingerprint(ingress)

    context: Dict[str, Any] = {
        "adapter_contract": ADAPTER_CONTRACT,
        "redaction": dict(REDACTION_CONTRACT),
        "source_kind": ingress["source_kind"],
        "source_ref": ingress["source_ref"],
        "upstream_event_id": ingress["upstream_event_id"],
        "normalized_sha256": fingerprint,
        "trace_synthetic": trace["synthetic"],
        "tenant": scope["tenant"],
        "environment": scope["environment"],
        "domain": scope["domain"],
        "service": scope["service"],
        "component": scope["component"],
        "status": activity["status"],
        "classification": ingress["classification"],
    }
    for key in (
        "pipeline",
        "worker",
        "step",
        "pipeline_run_id",
        "worker_run_id",
        "model_invocation_id",
        "policy_decision_id",
        "grant_sha256",
    ):
        if key in scope:
            context[key] = scope[key]
    for key in ("severity", "error_code", "duration_ms", "attempt", "counters"):
        if key in activity:
            context[key] = activity[key]
    if "source_position_sha256" in ingress:
        context["source_position_sha256"] = ingress["source_position_sha256"]
    if "model" in ingress:
        context["model"] = ingress["model"]

    entity: Dict[str, Any] = {
        "emitter_entity_id": "entity.system.observability_adapter",
        "principal_entity_id": "entity.system.observability_adapter",
        "tenant_entity_id": f"entity.tenant.{scope['tenant']}",
    }
    if scope.get("worker"):
        entity["worker_entity_id"] = f"entity.worker.{scope['worker']}"

    actor = {
        "system": "observability_adapter",
        "component": ingress["source_kind"],
    }
    semantics = {
        "domain": scope["domain"],
        "kind": activity["kind"],
        "verb": activity["verb"],
    }
    refs = _default_refs(ingress)
    event: Dict[str, Any] = {
        "event_ref": event_ref,
        "version": "v1",
        "trace": {
            "trace_id": trace["trace_id"],
            "span_id": trace["span_id"],
        },
        "timestamp": ingress["observed_at"],
        "actor": actor,
        "entity": entity,
        "event_type": activity["event_type"],
        "event_subtype": activity["event_subtype"],
        "semantics": semantics,
        "context": context,
        **refs,
    }
    if trace.get("parent_span_id"):
        event["trace"]["parent_span_id"] = trace["parent_span_id"]
    return event


def trace_from_traceparent(traceparent: Optional[str], *, identity: str) -> Dict[str, Any]:
    raw = str(traceparent or "").strip().lower()
    parts = raw.split("-")
    if (
        len(parts) == _TRACEPARENT_PARTS
        and parts[0] == "00"
        and len(parts[1]) == 32
        and len(parts[2]) == 16
        and len(parts[3]) == 2
        and all(ch in "0123456789abcdef" for ch in parts[0] + parts[1] + parts[2] + parts[3])
        and parts[1] != "0" * 32
        and parts[2] != "0" * 16
    ):
        return {"trace_id": parts[1], "span_id": parts[2], "synthetic": False}
    digest = _sha256_text(identity)
    return {"trace_id": digest[:32], "span_id": digest[32:48], "synthetic": True}


def make_metadata_ingress(
    *,
    source_kind: str,
    source_ref: str,
    upstream_event_id: str,
    observed_at: str,
    trace: Mapping[str, Any],
    scope: Mapping[str, Any],
    classification: Mapping[str, Any],
    activity: Mapping[str, Any],
    refs: Optional[Mapping[str, Iterable[str]]] = None,
    model: Optional[Mapping[str, Any]] = None,
    source_position_sha256: Optional[str] = None,
) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "schema_version": INGRESS_SCHEMA_VERSION,
        "source_kind": source_kind,
        "source_ref": source_ref,
        "upstream_event_id": upstream_event_id,
        "observed_at": observed_at,
        "trace": dict(trace),
        "scope": dict(scope),
        "classification": dict(classification),
        "activity": dict(activity),
        "redaction": dict(REDACTION_CONTRACT),
    }
    if refs:
        record["refs"] = {key: list(values) for key, values in refs.items() if values}
    if model:
        record["model"] = dict(model)
    if source_position_sha256:
        record["source_position_sha256"] = source_position_sha256
    return validate_metadata_ingress(record)
