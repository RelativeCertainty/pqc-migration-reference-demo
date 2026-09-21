"""Portable, classification-only intake crosswalk checks; no enterprise data access."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import jsonschema
import pytest


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "integrations/pqc/reference_assessment"
CROSSWALK = json.loads((BASE / "intake-crosswalk.v1.json").read_text())
SCHEMA = json.loads((BASE / "intake-crosswalk.v1.schema.json").read_text())
CATALOG = json.loads((BASE / "catalog.v1.json").read_text())


def profiles_by_id(crosswalk=CROSSWALK):
    return {profile["id"]: profile for profile in crosswalk["rfi_profiles"]}


def mappings_for(profile_id, crosswalk=CROSSWALK):
    return {
        item["family_id"]: item["relationship"]
        for item in profiles_by_id(crosswalk)[profile_id]["mappings"]
    }


def test_document_conforms_to_closed_versioned_schema():
    jsonschema.Draft202012Validator.check_schema(SCHEMA)
    jsonschema.validate(CROSSWALK, SCHEMA)
    assert CROSSWALK["crosswalk_id"] == "intake-rfi-runtime-20260908-v1"
    assert CROSSWALK["status"] == "development_classification_mapping_requires_review"


def test_all_27_original_profile_ids_are_preserved_without_private_file_dependency():
    profiles = CROSSWALK["rfi_profiles"]
    ids = [profile["id"] for profile in profiles]
    assert len(ids) == len(set(ids)) == 27
    assert set(ids) == {f"SRC-RFI-{number:03d}" for number in range(1, 28)}
    assert CROSSWALK["source_catalog"]["profile_count"] == len(ids)
    assert CROSSWALK["source_catalog"]["snapshot_scope"] == (
        "classification_ids_and_labels_only_no_answers_or_enterprise_instances"
    )


def test_all_runtime_families_have_explicit_mapping_or_unmapped_disposition():
    family_ids = {family["id"] for family in CATALOG["source_families"]}
    mapped = {
        item["family_id"]
        for profile in CROSSWALK["rfi_profiles"]
        for item in profile["mappings"]
    }
    unmapped = {item["family_id"] for item in CROSSWALK["unmapped_runtime_families"]}
    assert len(family_ids) == CROSSWALK["runtime_catalog"]["family_count"] == 27
    assert len({family["area_ref"] for family in CATALOG["source_families"]}) == 10
    assert mapped | unmapped == family_ids
    assert not mapped & unmapped
    assert len(unmapped) == len(CROSSWALK["unmapped_runtime_families"])
    for profile in CROSSWALK["rfi_profiles"]:
        links = profile["mappings"]
        assert len(links) == len({link["family_id"] for link in links})


def test_runtime_catalog_drift_requires_explicit_crosswalk_revision_review():
    assert CROSSWALK["runtime_catalog"]["schema_version"] == CATALOG["schema_version"]
    assert CROSSWALK["runtime_catalog"]["sha256"] == hashlib.sha256(
        (BASE / "catalog.v1.json").read_bytes()
    ).hexdigest()


def test_one_profile_to_multiple_families_is_explicit_not_ordinal():
    assert mappings_for("SRC-RFI-001") == {
        "cmdb": "partial", "application-portfolio": "partial"
    }
    assert mappings_for("SRC-RFI-002") == {
        "certificate-lifecycle": "partial", "certificate-authorities": "partial"
    }
    # Runtime's thirteenth item is software-signing, not the thirteenth RFI's HSM.
    assert CATALOG["source_families"][12]["id"] != "hsm"
    assert mappings_for("SRC-RFI-013") == {"hsm": "exact"}


def test_multiple_profiles_to_one_family_preserve_question_scope():
    assert mappings_for("SRC-RFI-007")["source-build"] == "partial"
    assert mappings_for("SRC-RFI-009")["source-build"] == "partial"
    assert mappings_for("SRC-RFI-019") == {"communications": "partial"}
    assert mappings_for("SRC-RFI-020") == {"communications": "partial"}
    assert profiles_by_id()["SRC-RFI-019"]["unresolved_aspects"]


def test_reordering_either_catalog_does_not_change_mappings():
    reordered = copy.deepcopy(CROSSWALK)
    reordered["rfi_profiles"].reverse()
    for profile_id in profiles_by_id():
        assert mappings_for(profile_id, reordered) == mappings_for(profile_id)
    family_ids = {family["id"] for family in reversed(CATALOG["source_families"])}
    assert family_ids == {family["id"] for family in CATALOG["source_families"]}


def test_real_taxonomy_gaps_remain_explicit_instead_of_forced_equivalence():
    gaps = {
        entry["family_id"]: entry
        for entry in CROSSWALK["unmapped_runtime_families"]
    }
    assert set(gaps) == {"mainframe", "policy-exceptions"}
    assert all(gap["relationship"] == "unmapped" for gap in gaps.values())
    assert all(gap["reason"] and gap["next_action"] for gap in gaps.values())
    network = profiles_by_id()["SRC-RFI-004"]
    assert {link["relationship"] for link in network["mappings"]} == {"overlap"}
    assert "network-telemetry" not in mappings_for("SRC-RFI-004")
    assert network["unresolved_aspects"]
    assert mappings_for("SRC-RFI-024") == {"specialized-transactions": "overlap"}
    assert profiles_by_id()["SRC-RFI-024"]["unresolved_aspects"]


def test_relationships_never_assert_adapter_or_evidence_equivalence():
    assert set(CROSSWALK["relationship_definitions"]) == {
        "exact", "partial", "overlap", "unmapped"
    }
    exact = CROSSWALK["relationship_definitions"]["exact"]
    assert "routing only" in exact and "never" in exact
    assert "adapter behavior" in exact and "authority" in exact
    rules = " ".join(CROSSWALK["rules"])
    assert "never by catalog order" in rules
    assert "No mapping creates a source instance" in rules
    assert "cannot silently remap historical answers" in rules
    assert "enterprise completeness" in rules


@pytest.mark.parametrize("extra", ["answers", "owners", "credentials", "approved_by"])
def test_schema_rejects_response_and_authority_fields(extra):
    altered = copy.deepcopy(CROSSWALK)
    altered["rfi_profiles"][0][extra] = "SYNTHETIC-REJECTED"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(altered, SCHEMA)


def test_snapshot_omits_employer_context_and_does_not_activate_any_capability():
    encoded = json.dumps(CROSSWALK)
    assert ("/home/" + "owner") not in encoded
    assert "the example enterprise" not in encoded
    assert "example-enterprise" not in encoded
    assert "@" not in encoded
    assert "https://" not in encoded
    assert "not an owner-approved enterprise taxonomy" in " ".join(CROSSWALK["limitations"])
