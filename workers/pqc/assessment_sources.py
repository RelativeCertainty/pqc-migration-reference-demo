"""Offline, synthetic source-page normalization and adapter qualification catalog.

These reference dialects are deliberately NOT ServiceNow, Venafi or scanner APIs.
The caller owns collection/evidence metadata and immutable revision persistence.
No record is dropped or reconciled here: duplicates replay identically, conflicting
variants retain the same subject identity, and missing relations remain unknown.
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

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2] / "integrations/pqc/reference_assessment"
_IDENTIFIER = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}\Z")
_FACT_TYPES = {"cmdb": "application", "pki": "certificate", "tls": "tls_endpoint"}
_PRIORITY_PATTERNS = {"tls-hybrid-key-exchange", "ssh-hybrid-key-exchange", "application-library-migration"}
_FORMAT_CHECKER = FormatChecker()
HISTORICAL_CATALOG_SELECTOR = "historical-v1"
CURRENT_CATALOG_SELECTOR = "current"
_CATALOG_V1_VERSION = "pba.pqc.reference-qualification-catalog.v1"
_CATALOG_V2_VERSION = "pba.pqc.reference-qualification-catalog.v2"
_CATALOG_EXPANSION_VERSION = "pba.pqc.reference-qualification-catalog-expansion.v2"
_VIRTUALIZATION_FAMILY_ID = "virtualization-hypervisors"


@_FORMAT_CHECKER.checks("date-time")
def _valid_datetime(value: Any) -> bool:
    # jsonschema's date-time checker otherwise depends on an optional package.
    if not isinstance(value, str):
        return True
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", value):
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


@_FORMAT_CHECKER.checks("date")
def _valid_date(value: Any) -> bool:
    if not isinstance(value, str):
        return True
    try:
        return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)) and date.fromisoformat(value) is not None
    except ValueError:
        return False


class SourceContractError(ValueError):
    """Controlled metadata-only error; never contains source values."""


def _identifier(value: Any) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise SourceContractError("invalid_source_identifier")


def qualified_ref(
    tenant_id: str, source_instance_id: str, native_id: str, *, namespace: str = "record"
) -> str:
    """Stable identity; tenant and source namespace cannot collide by delimiters."""
    for value in (tenant_id, source_instance_id, native_id, namespace):
        _identifier(value)
    canonical = json.dumps([tenant_id, source_instance_id, namespace, native_id], separators=(",", ":"))
    return "pqc-ref:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@lru_cache(maxsize=4)
def _validator(name: str) -> Draft202012Validator:
    schema = json.loads((ROOT / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=_FORMAT_CHECKER)


@lru_cache(maxsize=1)
def _current_catalog_validator() -> Draft202012Validator:
    """Build the closed v2 validator from the immutable v1 schema plus lineage."""
    schema = json.loads((ROOT / "catalog.schema.json").read_text(encoding="utf-8"))
    schema["$id"] = "https://example.invalid/pqc/reference-qualification-catalog.v2.schema.json"
    schema["title"] = "PQC reference qualification catalog v2"
    schema["properties"]["schema_version"]["const"] = _CATALOG_V2_VERSION
    families = schema["properties"]["source_families"]
    families["minItems"] = 28
    families["maxItems"] = 28
    schema["required"].append("catalog_lineage")
    schema["properties"]["catalog_lineage"] = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "base_schema_version",
            "base_sha256",
            "expansion_schema_version",
            "historical_questionnaire_reference",
            "historical_questionnaire_profile_count",
            "historical_dispatch_state",
            "additions",
        ],
        "properties": {
            "base_schema_version": {"const": _CATALOG_V1_VERSION},
            "base_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            "expansion_schema_version": {"const": _CATALOG_EXPANSION_VERSION},
            "historical_questionnaire_reference": {"const": "intake-crosswalk.v1.json"},
            "historical_questionnaire_profile_count": {"const": 27},
            "historical_dispatch_state": {
                "const": "historical_questionnaires_and_distribution_unchanged"
            },
            "additions": {
                "const": [
                    {
                        "family_id": _VIRTUALIZATION_FAMILY_ID,
                        "legacy_questionnaire_match": "none",
                        "legacy_profile_id": None,
                        "adapter_qualification": "not_qualified",
                        "execution_authorized": False,
                    }
                ]
            },
        },
    }
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=_FORMAT_CHECKER)


def _relation(tenant_id: str, row: dict[str, Any], relation: str) -> str | None:
    native_id, source = row[f"{relation}_id"], row[f"{relation}_source"]
    if (native_id is None) != (source is None):
        raise SourceContractError("incomplete_source_relation")
    return None if native_id is None else qualified_ref(tenant_id, source, native_id)


def _has_control_characters(value: Any) -> bool:
    if isinstance(value, str):
        return any(ord(char) < 32 or ord(char) == 127 for char in value)
    if isinstance(value, dict):
        return any(_has_control_characters(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_control_characters(item) for item in value)
    return False


def normalize_page(
    kind: str,
    payload: dict[str, Any],
    *,
    tenant_id: str,
    source_instance_id: str,
    observed_at: str,
) -> list[dict[str, Any]]:
    """Normalize only the closed reference dialect; no I/O, scans or credentials.

    ``observed_at`` is checked but persisted by the caller, not silently inferred.
    A syntactic synthetic marker is not a production data-classification control.
    The worker intake must also enforce its fixture-only authority boundary.
    """
    _identifier(tenant_id)
    _identifier(source_instance_id)
    if not isinstance(kind, str):
        raise SourceContractError("unsupported_source_kind")
    if not isinstance(observed_at, str) or not _valid_datetime(observed_at):
        raise SourceContractError("invalid_observation_time")
    if kind not in _FACT_TYPES:
        # Lazy import keeps the shared identity helpers free of import cycles.
        # These are closed synthetic family dialects, not live vendor adapters.
        from workers.pqc.extended_sources import (
            extended_family_profiles,
            normalize_extended_page,
        )

        if kind not in extended_family_profiles():
            raise SourceContractError("unsupported_source_kind")
        return normalize_extended_page(
            kind, payload, tenant_id=tenant_id,
            source_instance_id=source_instance_id, observed_at=observed_at,
        )
    if not _validator("source-page.schema.json").is_valid(payload):
        raise SourceContractError("invalid_source_page")
    if _has_control_characters(payload):
        raise SourceContractError("invalid_source_page")
    if payload["kind"] != kind:
        raise SourceContractError("source_kind_mismatch")

    output = []
    for row in payload["records"]:
        facts: dict[str, Any] = {"native_id": row["id"]}
        if kind == "cmdb":
            facts.update(
                name=row["name"],
                business_service_ref=(qualified_ref(tenant_id, source_instance_id, row["business_service_id"], namespace="business-service")
                                      if row["business_service_id"] is not None else None),
                owner_ref=(qualified_ref(tenant_id, source_instance_id, row["owner_id"], namespace="owner")
                           if row["owner_id"] is not None else None),
                criticality=row["criticality"],
                environment=row["environment"],
                confidentiality_until=row["confidentiality_until"],
            )
        elif kind == "pki":
            facts.update(
                application_ref=_relation(tenant_id, row, "application"),
                common_name=row["common_name"],
                signature_algorithm=row["signature_algorithm"],
                public_key_algorithm=row["public_key_algorithm"],
                public_key_bits=row["public_key_bits"],
                valid_until=row["valid_until"],
            )
        else:
            facts.update(
                application_ref=_relation(tenant_id, row, "application"),
                certificate_ref=_relation(tenant_id, row, "certificate"),
                hostname=row["hostname"],
                port=row["port"],
                protocol=row["protocol"],
                key_exchange_group=row["key_exchange_group"],
                certificate_signature_algorithm=row["certificate_signature_algorithm"],
            )
        output.append({
            "subject_ref": qualified_ref(tenant_id, source_instance_id, row["id"]),
            "fact_type": _FACT_TYPES[kind],
            "assertion_kind": row["evidence_basis"],
            "facts": facts,
        })
    return output


def _validate_catalog_integrity(
    catalog: dict[str, Any], *, expected_family_count: int
) -> dict[str, Any]:
    """Check closed catalog referential integrity without network access."""
    areas = {item["id"] for item in catalog["estate_areas"]}
    families = {item["id"] for item in catalog["source_families"]}
    patterns = {item["id"] for item in catalog["migration_archetypes"]}
    if (len(areas), len(families), len(patterns)) != (10, expected_family_count, 22):
        raise SourceContractError("duplicate_catalog_identity")
    if {item["area_ref"] for item in catalog["source_families"]} != areas:
        raise SourceContractError("invalid_area_reference")
    referenced_families = set()
    for pattern in catalog["migration_archetypes"]:
        refs = set(pattern["source_family_refs"])
        if not refs.issubset(families):
            raise SourceContractError("invalid_source_family_reference")
        referenced_families.update(refs)
    if referenced_families != families:
        raise SourceContractError("unmapped_source_family")
    priority_refs = [item["pattern_ref"] for item in catalog["priority_patterns"]]
    if len(set(priority_refs)) != 3 or set(priority_refs) != _PRIORITY_PATTERNS:
        raise SourceContractError("invalid_priority_pattern_reference")
    for family in catalog["source_families"]:
        if not set(family["pattern_refs"]).issubset(patterns):
            raise SourceContractError("invalid_pattern_reference")
        actual = {item["id"] for item in catalog["migration_archetypes"] if family["id"] in item["source_family_refs"]}
        if set(family["pattern_refs"]) != actual:
            raise SourceContractError("inconsistent_catalog_crosswalk")
    return {"estate_areas": 10, "source_families": expected_family_count, "migration_archetypes": 22,
            "priority_pattern_refs": priority_refs}


def _read_historical_catalog() -> dict[str, Any]:
    path = ROOT / "catalog.v1.json"
    if path.is_symlink() or path.stat().st_size > 512 * 1024:
        raise SourceContractError("invalid_qualification_catalog")
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if not _validator("catalog.schema.json").is_valid(catalog):
        raise SourceContractError("invalid_qualification_catalog")
    _validate_catalog_integrity(catalog, expected_family_count=27)
    return catalog


def _read_catalog_expansion() -> dict[str, Any]:
    path = ROOT / "catalog-expansion.v2.json"
    if path.is_symlink() or path.stat().st_size > 128 * 1024:
        raise SourceContractError("invalid_qualification_catalog_expansion")
    expansion = json.loads(path.read_text(encoding="utf-8"))
    if not _validator("catalog-expansion.v2.schema.json").is_valid(expansion):
        raise SourceContractError("invalid_qualification_catalog_expansion")
    historical_bytes = (ROOT / expansion["base_catalog"]["path"]).read_bytes()
    if not hmac.compare_digest(
        hashlib.sha256(historical_bytes).hexdigest(), expansion["base_catalog"]["sha256"]
    ):
        raise SourceContractError("qualification_catalog_base_digest_mismatch")
    return expansion


@lru_cache(maxsize=1)
def _composed_current_catalog() -> dict[str, Any]:
    base = _read_historical_catalog()
    expansion = _read_catalog_expansion()
    addition = expansion["source_family_additions"][0]
    family = copy.deepcopy(addition["family"])
    if family["id"] in {row["id"] for row in base["source_families"]}:
        raise SourceContractError("duplicate_catalog_expansion_identity")

    insertion_index = max(
        index
        for index, row in enumerate(base["source_families"])
        if row["area_ref"] == family["area_ref"]
    ) + 1
    base["source_families"].insert(insertion_index, family)

    archetypes = {row["id"]: row for row in base["migration_archetypes"]}
    expansion_refs = set()
    for item in expansion["migration_archetype_ref_additions"]:
        archetype = archetypes.get(item["archetype_id"])
        if archetype is None:
            raise SourceContractError("invalid_catalog_expansion_pattern_reference")
        for family_ref in item["source_family_refs"]:
            if family_ref in archetype["source_family_refs"]:
                raise SourceContractError("duplicate_catalog_expansion_reference")
            archetype["source_family_refs"].append(family_ref)
            expansion_refs.add(item["archetype_id"])
    if expansion_refs != set(family["pattern_refs"]):
        raise SourceContractError("inconsistent_catalog_expansion_crosswalk")

    boundary = expansion["historical_questionnaire_boundary"]
    base["schema_version"] = expansion["current_catalog"]["schema_version"]
    base["catalog_lineage"] = {
        "base_schema_version": expansion["base_catalog"]["schema_version"],
        "base_sha256": expansion["base_catalog"]["sha256"],
        "expansion_schema_version": expansion["schema_version"],
        "historical_questionnaire_reference": boundary["crosswalk_path"],
        "historical_questionnaire_profile_count": boundary["profile_count"],
        "historical_dispatch_state": boundary["dispatch_state"],
        "additions": [
            {
                "family_id": family["id"],
                "legacy_questionnaire_match": addition["lineage"]["legacy_questionnaire_match"],
                "legacy_profile_id": addition["lineage"]["legacy_profile_id"],
                "adapter_qualification": addition["lineage"]["adapter_qualification"],
                "execution_authorized": addition["lineage"]["execution_authorized"],
            }
        ],
    }
    if not _current_catalog_validator().is_valid(base):
        raise SourceContractError("invalid_current_qualification_catalog")
    _validate_catalog_integrity(base, expected_family_count=28)
    return base


def load_catalog(selector: str) -> dict[str, Any]:
    """Load one explicit release; ``current`` composes v1 with the v2 overlay."""
    if selector == HISTORICAL_CATALOG_SELECTOR:
        return copy.deepcopy(_read_historical_catalog())
    if selector == CURRENT_CATALOG_SELECTOR:
        return copy.deepcopy(_composed_current_catalog())
    raise SourceContractError("unsupported_catalog_selector")


def validate_catalog(catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate the immutable v1 runtime catalog; retained for compatibility."""
    if catalog is None:
        catalog = _read_historical_catalog()
    if not _validator("catalog.schema.json").is_valid(catalog):
        raise SourceContractError("invalid_qualification_catalog")
    return _validate_catalog_integrity(catalog, expected_family_count=27)


def validate_current_catalog(catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate the exact composed 28-family catalog without changing runtime defaults."""
    expected = _composed_current_catalog()
    if catalog is None:
        catalog = expected
    if not _current_catalog_validator().is_valid(catalog):
        raise SourceContractError("invalid_current_qualification_catalog")
    if catalog != expected:
        raise SourceContractError("current_qualification_catalog_drift")
    return _validate_catalog_integrity(catalog, expected_family_count=28)
