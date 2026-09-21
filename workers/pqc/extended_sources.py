"""Closed offline models for 24 additional source families, not vendor adapters.

Source assertions are not canonical migration contracts or execution authority.
The page digest detects accidental/tampered content relative to its declared hash;
it is not a signature, source authentication or a classification control. The
caller must retain raw custody and authorize intake separately. No networking,
credentials or source mutation exists; only fixed repository model files are read.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import re
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from workers.pqc.assessment_sources import SourceContractError, qualified_ref


ROOT = Path(__file__).resolve().parents[2] / "integrations/pqc/reference_assessment"
PAGE_VERSION = "pba.pqc.extended-source-page.v1"
MODEL_VERSION = "pba.pqc.extended-family-models.v1"
MAX_RECORDS = 128
MAX_PAGE_BYTES = 256 * 1024
_CORE = {"cmdb", "certificate-lifecycle", "traffic-termination"}
_BASIS = ("observed", "configured", "vendor_reported")
_IDENTIFIER = r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}"
_TEXT = r"[A-Za-z0-9][A-Za-z0-9 ._:/+()-]{0,127}"
_TENANT = r"synthetic-[a-z0-9][a-z0-9-]{0,47}"
_SOURCE_ALIAS = {"cmdb": "cmdb", "certificate-lifecycle": "pki", "traffic-termination": "tls"}
_FIELD_TYPES = {"text", "identifier", "integer", "boolean", "date", "tokens", "hostname"}
_USE_SUFFIXES = ("present", "algorithm", "basis", "key_bits", "protocol_version", "trust_until")
_PURPOSES = {"key_establishment", "authentication", "digital_signature", "data_encryption", "key_wrapping"}
_ROLES = {"transport_key_exchange", "peer_authentication", "certificate_issuer", "code_signer", "token_issuer",
          "data_encryptor", "key_wrapper", "firmware_verifier", "document_signer", "key_custodian",
          "application_signer", "credential_issuer", "dnssec_signer", "email_signer"}


def _error(code: str) -> SourceContractError:
    return SourceContractError(code)


def _bounded_json(value: Any, *, depth: int = 0, budget: list[int] | None = None) -> None:
    """Reject nesting, exotic objects, unbounded strings/nodes before serialization."""
    if budget is None:
        budget = [0]
    budget[0] += 1
    if depth > 6 or budget[0] > 20000:
        raise _error("extended_page_budget_exceeded")
    if type(value) is int and not -(2**63) <= value < 2**63:
        raise _error("invalid_extended_source_value")
    if value is None or type(value) in (bool, int):
        return
    if isinstance(value, str):
        if len(value) > 256 or any(ord(c) < 32 or ord(c) > 126 for c in value):
            raise _error("invalid_extended_source_value")
        return
    if type(value) is list:
        if len(value) > MAX_RECORDS:
            raise _error("extended_page_budget_exceeded")
        for item in value:
            _bounded_json(item, depth=depth + 1, budget=budget)
        return
    if type(value) is dict:
        if len(value) > 64:
            raise _error("extended_page_budget_exceeded")
        for key, item in value.items():
            if type(key) is not str:
                raise _error("invalid_extended_source_value")
            _bounded_json(key, depth=depth + 1, budget=budget)
            _bounded_json(item, depth=depth + 1, budget=budget)
        return
    raise _error("invalid_extended_source_value")


def extended_page_digest(payload: dict[str, Any]) -> str:
    """Canonical content hash excluding only its own declared digest field."""
    if type(payload) is not dict:
        raise _error("invalid_extended_source_page")
    _bounded_json(payload)
    encoded = json.dumps({key: value for key, value in payload.items() if key != "content_sha256"},
                         sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
    if len(encoded) > MAX_PAGE_BYTES:
        raise _error("extended_page_budget_exceeded")
    return hashlib.sha256(encoded).hexdigest()


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


def _field_schema(field_type: str) -> dict[str, Any]:
    if field_type == "integer":
        return _nullable({"type": "integer", "minimum": 0, "maximum": 65536})
    if field_type == "boolean":
        return _nullable({"type": "boolean"})
    if field_type == "tokens":
        return _nullable({"type": "array", "maxItems": 16, "uniqueItems": True,
                          "items": {"type": "string", "pattern": f"^{_TEXT}$", "maxLength": 128}})
    pattern = {"text": _TEXT, "identifier": r"synthetic-[A-Za-z0-9][A-Za-z0-9_.:-]{0,117}", "date": r"\d{4}-\d{2}-\d{2}",
               "hostname": r"[a-z0-9][a-z0-9.-]{0,100}\.example"}[field_type]
    return _nullable({"type": "string", "pattern": f"^{pattern}$", "maxLength": 128})


def _use_field_schemas(prefix: str) -> dict[str, dict[str, Any]]:
    return {
        f"{prefix}_present": {"type": "boolean"},
        f"{prefix}_algorithm": _field_schema("text"),
        f"{prefix}_basis": {"enum": [*_BASIS, None]},
        f"{prefix}_key_bits": _nullable({"type": "integer", "minimum": 1, "maximum": 65536}),
        f"{prefix}_protocol_version": _field_schema("text"),
        f"{prefix}_trust_until": _field_schema("date"),
    }


def _relationship_schema(target_family: str, namespace: str) -> dict[str, Any]:
    prefix = "service" if namespace == "business-service" else {
        "cmdb": "app", "certificate-lifecycle": "cert", "traffic-termination": "endpoint"
    }.get(target_family, target_family)
    # Known or explicitly unresolved synthetic identities are permitted; arbitrary
    # native vendor IDs/URLs/cross-tenant/source provenance are not this dialect.
    return _nullable({"type": "string", "pattern": f"^{re.escape(prefix)}-(?:unmapped-)?[0-9]{{3}}$"})


@lru_cache(maxsize=1)
def _load_profiles() -> dict[str, dict[str, Any]]:
    path = ROOT / "extended-families.v1.json"
    if path.is_symlink() or path.stat().st_size > 256 * 1024:
        raise _error("invalid_extended_family_models")
    model = json.loads(path.read_text(encoding="utf-8"))
    required_model = {"schema_version", "model_status", "product_binding", "qualification_gates", "restrictions", "profiles"}
    if set(model) != required_model or model["schema_version"] != MODEL_VERSION:
        raise _error("invalid_extended_family_models")
    if model["model_status"] != "synthetic_reference_dialects_not_vendor_wire_contracts":
        raise _error("invalid_extended_family_models")
    if model["product_binding"] != {"product": None, "edition": None, "version": None, "instance": None}:
        raise _error("invalid_extended_family_models")
    catalog = json.loads((ROOT / "catalog.v1.json").read_text(encoding="utf-8"))
    families = {family["id"]: family for family in catalog["source_families"]}
    if type(model["profiles"]) is not dict or set(model["profiles"]) != set(families) - _CORE or len(model["profiles"]) != 24:
        raise _error("invalid_extended_family_models")
    expected = {"area_ref", "name", "fact_type", "fields", "relations", "uses", "candidate_automation",
                "manual_boundary", "information_loss", "unsupported_capabilities"}
    profiles = {}
    for kind, profile in model["profiles"].items():
        if set(profile) != expected or profile["area_ref"] != families[kind]["area_ref"] or profile["fact_type"] != kind.replace("-", "_"):
            raise _error("invalid_extended_family_models")
        fields = {}
        for field, spec in profile["fields"].items():
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", field) or not {"type", "samples"}.issubset(spec) or set(spec) - {"type", "samples", "choices"} or spec["type"] not in _FIELD_TYPES:
                raise _error("invalid_extended_family_models")
            if field in {"id", "name", "evidence_basis", "application_id"}:
                raise _error("invalid_extended_family_models")
            if type(spec["samples"]) is not list or len(spec["samples"]) != 3:
                raise _error("invalid_extended_family_models")
            fields[field] = _field_schema(spec["type"])
            if "choices" in spec:
                if type(spec["choices"]) is not list or not spec["choices"] or any(type(choice) is not str for choice in spec["choices"]):
                    raise _error("invalid_extended_family_models")
                fields[field] = {"enum": [*spec["choices"], None]}
            if any(not Draft202012Validator(fields[field]).is_valid(sample) for sample in spec["samples"]):
                raise _error("invalid_extended_family_models")
        for field, relation in profile["relations"].items():
            if set(relation) != {"relationship", "target_family", "namespace"} or relation["target_family"] not in families:
                raise _error("invalid_extended_family_models")
            if not field.endswith("_id") or relation["namespace"] not in {"record", "business-service"} or field in fields or field in {"id", "name", "evidence_basis", "application_id"}:
                raise _error("invalid_extended_family_models")
            fields[field] = _relationship_schema(relation["target_family"], relation["namespace"])
        for use in profile["uses"]:
            if set(use) != {"prefix", "purpose", "role", "protected_data_field", "samples"} or use["purpose"] not in _PURPOSES or use["role"] not in _ROLES:
                raise _error("invalid_extended_family_models")
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,40}", use["prefix"]) or set(use["samples"]) != set(_USE_SUFFIXES):
                raise _error("invalid_extended_family_models")
            if use["protected_data_field"] is not None and profile["relations"].get(use["protected_data_field"], {}).get("target_family") != "data-governance":
                raise _error("invalid_extended_family_models")
            for field, schema in _use_field_schemas(use["prefix"]).items():
                if field in fields:
                    raise _error("invalid_extended_family_models")
                fields[field] = schema
                samples = use["samples"][field[len(use["prefix"]) + 1:]]
                if type(samples) is not list or len(samples) != 3 or any(not Draft202012Validator(schema).is_valid(s) for s in samples):
                    raise _error("invalid_extended_family_models")
        for field in ("candidate_automation", "manual_boundary", "information_loss", "unsupported_capabilities"):
            if not profile[field] or any(type(item) is not str or not item for item in profile[field]):
                raise _error("invalid_extended_family_models")
        enriched = copy.deepcopy(profile)
        enriched.update(family_id=kind, model_status=model["model_status"], product_binding=copy.deepcopy(model["product_binding"]),
                        qualification_gates=list(model["qualification_gates"]), restrictions=list(model["restrictions"]),
                        recognition_examples=list(families[kind]["recognition_examples"]),
                        examples_status="recognition_examples_not_installed_or_selected", raw_field_schemas=fields,
                        source_instance_id=f"synthetic-{kind}", evidence_targets=list(families[kind]["evidence_targets"]))
        profiles[kind] = enriched
    return profiles


def extended_family_profiles() -> dict[str, dict[str, Any]]:
    """Return detached machine dossiers, including exact compiled raw-field schemas."""
    return copy.deepcopy(_load_profiles())


@lru_cache(maxsize=24)
def _page_validator(kind: str) -> Draft202012Validator:
    profile = _load_profiles()[kind]
    row_fields = {
        "id": {"type": "string", "pattern": f"^{re.escape(kind)}-[0-9]{{3}}$"},
        "name": {"type": "string", "pattern": r"^Synthetic [A-Za-z0-9 ._()-]{1,110}$"},
        "evidence_basis": {"enum": list(_BASIS)},
        "application_id": _relationship_schema("cmdb", "record"),
        **profile["raw_field_schemas"],
    }
    schema = {
        "type": "object", "additionalProperties": False,
        "required": ["schema_version", "synthetic", "kind", "tenant_id", "source_instance_id", "records", "next_cursor", "content_sha256"],
        "properties": {
            "schema_version": {"const": PAGE_VERSION}, "synthetic": {"const": True}, "kind": {"const": kind},
            "tenant_id": {"type": "string", "pattern": f"^{_TENANT}$"},
            "source_instance_id": {"const": f"synthetic-{kind}"},
            "records": {"type": "array", "maxItems": MAX_RECORDS,
                        "items": {"type": "object", "additionalProperties": False, "required": list(row_fields), "properties": row_fields}},
            "next_cursor": {"anyOf": [{"type": "null"}, {"type": "string", "pattern": r"^page-[0-9]{3}$"}]},
            "content_sha256": {"type": "string", "pattern": r"^[a-f0-9]{64}$"},
        },
    }
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _validate_values(row: dict[str, Any], profile: dict[str, Any]) -> None:
    # No source URL, credential material, content payload, PEM or arbitrary
    # custom metadata is admitted. Schema closure rejects secret-bearing keys.
    for value in row.values():
        values = value if isinstance(value, list) else [value]
        for item in values:
            if isinstance(item, str) and ("://" in item or "PRIVATE KEY" in item.upper()
                                          or re.search(r"(?:password|authorization|bearer|token)\s*[:=]", item, re.I)):
                raise _error("invalid_extended_source_value")
    date_fields = [field for field, spec in profile["fields"].items() if spec["type"] == "date"]
    date_fields += [use["prefix"] + "_trust_until" for use in profile["uses"]]
    for field in date_fields:
        if row[field] is not None:
            try:
                date.fromisoformat(row[field])
            except ValueError:
                raise _error("invalid_extended_source_date") from None
    for use in profile["uses"]:
        prefix = use["prefix"]
        if not row[prefix + "_present"]:
            if any(row[prefix + "_" + suffix] is not None for suffix in _USE_SUFFIXES if suffix != "present"):
                raise _error("absent_use_has_assertion")
        elif row[prefix + "_basis"] not in _BASIS:
            raise _error("cryptographic_use_basis_required")


def normalize_extended_page(kind: str, payload: dict[str, Any], *, tenant_id: str,
                            source_instance_id: str, observed_at: str) -> list[dict[str, Any]]:
    """Pure bounded normalization; known/unknown facts never become authorization."""
    if type(kind) is not str or kind not in _load_profiles():
        raise _error("unsupported_extended_source_kind")
    if type(tenant_id) is not str or not re.fullmatch(_TENANT, tenant_id) or source_instance_id != f"synthetic-{kind}":
        raise _error("invalid_extended_source_boundary")
    if type(observed_at) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", observed_at):
        raise _error("invalid_observation_time")
    try:
        datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError:
        raise _error("invalid_observation_time") from None
    digest = extended_page_digest(payload)
    if not _page_validator(kind).is_valid(payload):
        raise _error("invalid_extended_source_page")
    if payload["tenant_id"] != tenant_id or payload["source_instance_id"] != source_instance_id:
        raise _error("extended_source_boundary_mismatch")
    if not hmac.compare_digest(payload["content_sha256"], digest):
        raise _error("extended_source_digest_mismatch")
    profile = _load_profiles()[kind]
    output = []
    for row in payload["records"]:
        _validate_values(row, profile)
        application_ref = None if row["application_id"] is None else qualified_ref(tenant_id, "synthetic-cmdb", row["application_id"])
        facts = {"native_id": row["id"], "name": row["name"], "application_ref": application_ref}
        facts.update({field: copy.deepcopy(row[field]) for field in profile["fields"]})
        relationships = [] if application_ref is None else [{"relationship": "belongs_to_application", "target_ref": application_ref}]
        limitation_codes = {"reference_dialect_only", "product_binding_unqualified"}
        if application_ref is None:
            limitation_codes.add("missing_business_context")
        if any(row[field] is None for field in profile["fields"]):
            limitation_codes.add("source_metadata_unknown")
        for field, relation in profile["relations"].items():
            target = None if row[field] is None else qualified_ref(
                tenant_id, "synthetic-" + _SOURCE_ALIAS.get(relation["target_family"], relation["target_family"]),
                row[field], namespace=relation["namespace"])
            facts[field[:-3] + "_ref"] = target
            if target is None:
                limitation_codes.add("missing_relationship")
            else:
                relationships.append({"relationship": relation["relationship"], "target_ref": target})
        uses = []
        for use in profile["uses"]:
            prefix = use["prefix"]
            # Retain every declared raw use field so a review can trace the
            # summary to its source assertion without reconstructing a payload.
            facts.update({prefix + "_" + suffix: row[prefix + "_" + suffix] for suffix in _USE_SUFFIXES})
            if not row[prefix + "_present"]:
                continue
            algorithm, basis = row[prefix + "_algorithm"], row[prefix + "_basis"]
            data_field = use["protected_data_field"]
            uses.append({"purpose": use["purpose"], "role": use["role"], "algorithm": algorithm, "basis": basis,
                         "parameters": {"key_bits": row[prefix + "_key_bits"], "protocol_version": row[prefix + "_protocol_version"]},
                         "protected_data_ref": None if data_field is None else facts[data_field[:-3] + "_ref"],
                         "trust_until": row[prefix + "_trust_until"]})
            if algorithm is None:
                limitation_codes.add("cryptographic_parameters_unknown")
            if basis == "configured":
                limitation_codes.add("configured_cryptographic_use")
            if basis == "vendor_reported":
                limitation_codes.add("unverified_vendor_claim")
        if not uses and any(row.get(field) for field in ("supported_algorithms", "supported_mechanisms", "declared_capabilities")):
            limitation_codes.add("capability_not_use")
        if kind == "dependency-analysis" and not uses:
            limitation_codes.add("package_presence_not_use")
        if kind == "policy-exceptions":
            limitation_codes.add("reported_policy_not_authorization")
        if kind == "vendor-assurance":
            limitation_codes.add("vendor_claim_not_independently_verified")
        if kind == "data-governance" and row["confidentiality_until"] is None:
            limitation_codes.add("unknown_information_lifetime")
        facts.update(relationships=relationships, cryptographic_uses=uses, limitations=sorted(limitation_codes))
        output.append({"subject_ref": qualified_ref(tenant_id, source_instance_id, row["id"]),
                       "fact_type": profile["fact_type"], "assertion_kind": row["evidence_basis"], "facts": facts})
    return output
