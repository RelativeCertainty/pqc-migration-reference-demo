"""Versioned PQC catalog addition tests; no provider or enterprise access."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from workers.pqc.assessment_sources import (
    CURRENT_CATALOG_SELECTOR,
    HISTORICAL_CATALOG_SELECTOR,
    SourceContractError,
    load_catalog,
    normalize_page,
    validate_catalog,
    validate_current_catalog,
)


ROOT = Path(__file__).resolve().parents[1] / "integrations/pqc/reference_assessment"
VIRTUALIZATION_FAMILY = "virtualization-hypervisors"


def _json(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def _sha256(name: str) -> str:
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def test_historical_catalog_schema_and_crosswalk_bytes_remain_immutable() -> None:
    assert _sha256("catalog.v1.json") == "f73b7a93562ed7490f83fa8b8b68afe4e753b745641923740fc87bea72ff1cb4"
    assert _sha256("catalog.schema.json") == "1d9435f8ac22ea1f5c0f3a9970bf975ac9b56f4b15ee78248176a9483c48405a"
    assert _sha256("intake-crosswalk.v1.json") == "011c94796631860fcaef76c8311c45e2578e57afa7c07b774dd20305e2b94869"


def test_v2_expansion_conforms_to_its_closed_schema_and_pins_v1() -> None:
    expansion = _json("catalog-expansion.v2.json")
    schema = _json("catalog-expansion.v2.schema.json")
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(expansion, schema)
    assert expansion["base_catalog"] == {
        "path": "catalog.v1.json",
        "schema_version": "pba.pqc.reference-qualification-catalog.v1",
        "sha256": _sha256("catalog.v1.json"),
        "source_family_count": 27,
    }
    assert expansion["current_catalog"] == {
        "schema_version": "pba.pqc.reference-qualification-catalog.v2",
        "source_family_count": 28,
    }


def test_explicit_catalog_selectors_separate_current_from_historical_runtime() -> None:
    historical = load_catalog(HISTORICAL_CATALOG_SELECTOR)
    current = load_catalog(CURRENT_CATALOG_SELECTOR)
    historical_ids = [row["id"] for row in historical["source_families"]]
    current_ids = [row["id"] for row in current["source_families"]]

    assert len(historical_ids) == 27
    assert VIRTUALIZATION_FAMILY not in historical_ids
    assert len(current_ids) == 28
    assert VIRTUALIZATION_FAMILY in current_ids
    assert current["schema_version"] == "pba.pqc.reference-qualification-catalog.v2"
    assert validate_catalog()["source_families"] == 27
    assert validate_current_catalog()["source_families"] == 28

    current["source_families"].clear()
    assert len(load_catalog(CURRENT_CATALOG_SELECTOR)["source_families"]) == 28


def test_virtualization_family_is_area_06_recognition_only() -> None:
    current = load_catalog(CURRENT_CATALOG_SELECTOR)
    families = current["source_families"]
    family = next(row for row in families if row["id"] == VIRTUALIZATION_FAMILY)
    family_index = [row["id"] for row in families].index(VIRTUALIZATION_FAMILY)

    assert families[family_index - 1]["id"] == "iam"
    assert families[family_index + 1]["id"] == "databases"
    assert family["area_ref"] == "area-06"
    assert family["name"] == "Virtualization and hypervisor platforms"
    assert family["recognition_examples"] == [
        "VMware vSphere (ESXi and vCenter)",
        "Microsoft Hyper-V and System Center Virtual Machine Manager",
    ]
    assert "not selections or evidence of installation" in family["discovery_question"]
    assert family["evidence_targets"] == [
        "virtualization hosts and clusters",
        "virtual-machine placement and relationships",
        "platform versions and accountable owners",
        "management-plane certificate and authentication configuration",
        "VM encryption and key-provider dependencies",
        "backup, restore and recovery dependencies",
    ]
    assert family["product_profile"]["status"] == "unknown_requires_owner_and_vendor_confirmation"
    assert all(value is None for key, value in family["product_profile"].items() if key != "status")
    assert current["examples_status"] == "recognition_examples_not_installed_or_selected"


def test_current_lineage_has_no_legacy_match_adapter_or_execution_claim() -> None:
    current = load_catalog(CURRENT_CATALOG_SELECTOR)
    lineage = current["catalog_lineage"]
    assert lineage["historical_questionnaire_reference"] == "intake-crosswalk.v1.json"
    assert lineage["historical_questionnaire_profile_count"] == 27
    assert lineage["historical_dispatch_state"] == (
        "historical_questionnaires_and_distribution_unchanged"
    )
    assert lineage["additions"] == [
        {
            "family_id": VIRTUALIZATION_FAMILY,
            "legacy_questionnaire_match": "none",
            "legacy_profile_id": None,
            "adapter_qualification": "not_qualified",
            "execution_authorized": False,
        }
    ]
    crosswalk = _json("intake-crosswalk.v1.json")
    mapped = {
        item["family_id"]
        for profile in crosswalk["rfi_profiles"]
        for item in profile["mappings"]
    }
    unmapped = {item["family_id"] for item in crosswalk["unmapped_runtime_families"]}
    assert VIRTUALIZATION_FAMILY not in mapped | unmapped


def test_current_archetype_crosswalk_is_complete_but_never_authorizes_execution() -> None:
    current = load_catalog(CURRENT_CATALOG_SELECTOR)
    family = next(row for row in current["source_families"] if row["id"] == VIRTUALIZATION_FAMILY)
    actual = {
        row["id"]
        for row in current["migration_archetypes"]
        if VIRTUALIZATION_FAMILY in row["source_family_refs"]
    }
    assert actual == set(family["pattern_refs"])
    assert all(row["execution_authorized"] is False for row in current["migration_archetypes"])


def test_current_catalog_rejects_binding_claims_and_unknown_selectors() -> None:
    altered = copy.deepcopy(load_catalog(CURRENT_CATALOG_SELECTOR))
    family = next(row for row in altered["source_families"] if row["id"] == VIRTUALIZATION_FAMILY)
    family["product_profile"]["product"] = "unverified-product-claim"
    with pytest.raises(SourceContractError, match="invalid_current_qualification_catalog"):
        validate_current_catalog(altered)
    with pytest.raises(SourceContractError, match="unsupported_catalog_selector"):
        load_catalog("latest")


def test_virtualization_has_no_synthetic_dialect_or_adapter() -> None:
    with pytest.raises(SourceContractError, match="unsupported_source_kind"):
        normalize_page(
            VIRTUALIZATION_FAMILY,
            {},
            tenant_id="synthetic-tenant",
            source_instance_id="synthetic-virtualization-hypervisors",
            observed_at="2026-09-18T00:00:00Z",
        )
