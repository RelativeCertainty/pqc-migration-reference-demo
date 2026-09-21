"""Deterministic fixture/model proofs, not browser or owner acceptance."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from scripts.build_pqc_all_domain_walkthrough import build, canonical, workspace_purpose, FIXTURES, NORMALIZER
from scripts.build_pqc_response_to_report_fixtures import workbook, NS
from workers.pqc.assessment_sources import normalize_page, SourceContractError


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    output = tmp_path_factory.mktemp("all-domain-inputs") / "generated"
    build(output)
    return output


def test_complete_inputs_preserve_catalog_questions_and_literal_operational_answers(generated):
    scenario = json.loads((generated / "scenario.json").read_text())
    definitions = json.loads((FIXTURES / "catalog.json").read_text())
    forms = {f["familyId"]: f for f in definitions["forms"]}
    assert len(scenario["cases"]) == 27
    assert len({c["domainId"] for c in scenario["cases"]}) == 10
    assert len(list(generated.glob("forms/*/*-synthetic-completed.xlsx"))) == 27
    for case in scenario["cases"]:
        data = (generated / case["formPath"]).read_bytes()
        spec = forms[case["familyId"]]
        cells, paths, parts = workbook(data)
        assert len(data) <= 1_048_576
        for sheet, readonly in spec["readonlyCells"].items():
            for address, value in readonly.items():
                assert cells[sheet].get(address) == value
        assert len(spec["questions"]) == 5
        assert [q["id"] for q in spec["questions"]] == [f"DQ-{n:02d}" for n in range(1, 6)]
        assert cells["Start here"][spec["respondentCells"]["respondent"]].startswith("Synthetic respondent")
        assert cells["Start here"][spec["respondentCells"]["scope"]].startswith("Synthetic practice only — DO NOT EMAIL")
        assert "SYNTHETIC TRAINING COPY" in cells["Version & return record"][spec["coordinatorCell"]]
        for path in paths.values():
            sheet = ET.fromstring(parts[path])
            for variant in ("odd", "even", "first"):
                header = sheet.find(f"{{{NS}}}headerFooter/{{{NS}}}{variant}Header").text
                footer = sheet.find(f"{{{NS}}}headerFooter/{{{NS}}}{variant}Footer").text
                assert "SYNTHETIC TRAINING COPY — DO NOT EMAIL" in header
                assert "DO NOT EMAIL" in footer
    traffic = generated / "forms/area-03/traffic-termination-synthetic-completed.xlsx"
    assert traffic.read_bytes() == (generated / "forms/area-03/traffic-termination-synthetic-duplicate.xlsx").read_bytes()
    assert traffic.read_bytes() != (generated / "forms/area-03/traffic-termination-synthetic-revised.xlsx").read_bytes()


def test_bundle_registry_is_byte_bound_to_actual_raw_normalizer_results(generated):
    registry = json.loads((generated / "bundle-registry.json").read_text())
    registry_rows = {r["sha256"]: r for r in registry["entries"]}
    assert len(registry_rows) == 29
    families = set()
    for path in generated.glob("bundles/*.json"):
        data = path.read_bytes(); bundle = json.loads(data)
        entry = registry_rows[hashlib.sha256(data).hexdigest()]
        assert bundle["rawSourceSha256"] == hashlib.sha256(canonical(bundle["rawSource"])).hexdigest()
        assert bundle["normalizerVersion"] == NORMALIZER
        assert entry["familyId"] == bundle["familyId"]
        assert bundle["records"] == normalize_page(bundle["rawSource"]["kind"], bundle["rawSource"],
            tenant_id=bundle["tenantId"], source_instance_id=bundle["sourceInstanceId"], observed_at=bundle["observedAt"])
        assert len(data) <= 32768 and 1 <= len(bundle["records"]) <= 32
        assert bundle["observedAt"] <= bundle["collectedAt"]
        assert "phase1Conclusion" not in bundle and "businessImpact" not in bundle
        families.add(bundle["familyId"])
    assert len(families) == 27
    changed = copy.deepcopy(bundle["rawSource"])
    changed["records"][0]["invented_field"] = "must fail"
    with pytest.raises(SourceContractError):
        normalize_page(changed["kind"], changed, tenant_id=bundle["tenantId"], source_instance_id=bundle["sourceInstanceId"], observed_at=bundle["observedAt"])


def test_business_context_is_attributed_distinct_and_not_execution_authority(generated):
    context = json.loads((generated / "business-context.json").read_text())
    rows = context["domains"]
    assert len(rows) == 10 and len({r["impact"] for r in rows}) == 10
    assert len({r["recommendation"] for r in rows}) == 10
    assert all(r["assertedBy"] and r["lifetime"] and r["statementDate"] == "2026-09-16" for r in rows)
    assert all(r["reviewStatus"] == "pending_simulated_business_review" for r in rows)
    scenario = json.loads((generated / "scenario.json").read_text())
    assert scenario["authority"]["ownerObservation"] is None
    assert scenario["authority"]["executionAuthorized"] is False
    assert scenario["expected"]["enterpriseCoveragePercent"] is None
    assert scenario["expected"]["qualifiedVendorAdapters"] == 0
    assert scenario["expected"]["blockedDeployments"] == 1
    assert all(case["analysis"]["assertedBy"] for case in scenario["cases"])
    crosswalk = json.loads((generated / "catalog-crosswalk.json").read_text())
    assert scenario["crosswalkId"] == crosswalk["crosswalk_id"]
    for case in scenario["cases"]:
        expected = [(r["id"], m["relationship"]) for r in crosswalk["rfi_profiles"] for m in r["mappings"] if m["family_id"] == case["familyId"]]
        assert [(r["questionnaireId"],r["relationship"]) for r in case["detailedQuestionnaireCrosswalk"]] == expected


def test_manifest_integrity_create_only_and_unknowns_not_erased(generated):
    scenario = json.loads((generated / "scenario.json").read_text())
    for entry in scenario["files"]:
        data = (generated / entry["name"]).read_bytes()
        assert len(data) == entry["bytes"] and hashlib.sha256(data).hexdigest() == entry["sha256"]
    with pytest.raises(ValueError, match="create_only"):
        build(generated)
    answers = json.loads((generated / "form-responses.json").read_text())["responses"]
    states = {q["status"] for response in answers for q in response["questions"]}
    assert {"Answered", "Referral", "Unknown", "Unanswered", "Blocked", "Disputed"} <= states
    traffic = next(r for r in answers if r["familyId"] == "traffic-termination")
    assert len(traffic["products"]) == 4 and len({p["deployment"] for p in traffic["products"]}) == 3
    assert next(p for p in traffic["products"] if p["deployment"] == "edge-third")["owner"] == "Unknown"


def test_each_family_technical_position_uses_only_its_own_source_facts(generated):
    scenario=json.loads((generated/"scenario.json").read_text())
    assert len({case["analysis"]["recommendation"] for case in scenario["cases"]}) == 27
    assert len({case["analysis"]["nextDecision"] for case in scenario["cases"]}) == 27
    for case in scenario["cases"]:
        selected=json.loads((generated/case["bundles"][0]["path"]).read_text())
        facts=selected["records"][0]["facts"]
        expected_purposes = list(dict.fromkeys(use["purpose"] for use in case["technicalBasis"]["uses"]))
        assert case["cryptographicPurpose"] == ("; ".join(expected_purposes) or "context")
        for item in case["technicalBasis"]["sourceFacts"]:
            assert facts[item["field"]]==item["value"]
        if case["familyId"]!="traffic-termination":
            assert "gateway-east" not in case["phase1Conclusion"].lower()
            assert "gateway-west" not in case["analysis"]["scenario"].lower()
            assert "edge-third" not in case["phase1Conclusion"].lower()
            assert "gateway-east" not in case["analysis"]["recommendation"].lower()
            assert "edge-third" not in case["analysis"]["recommendation"].lower()
        if case["familyId"] in {"databases","storage-backup"}:
            assert "does not establish quantum-vulnerable" in case["analysis"]["scenario"]
        if not case["technicalBasis"]["uses"]:
            assert "no cryptographic algorithm exposure" in case["analysis"]["scenario"]


def test_coarse_workspace_purpose_does_not_invent_signature_operations():
    assert workspace_purpose([]) == "context"
    assert workspace_purpose([{"purpose":"data_encryption"}]) == "data_protection"
    assert workspace_purpose([{"purpose":"key_wrapping"}]) == "data_protection"
    assert workspace_purpose([{"purpose":"digital_signature","role":"code_signer"}]) == "software_signing"
    assert workspace_purpose([{"purpose":"digital_signature","role":"token_issuer"}]) == "authentication"
    assert workspace_purpose([{"purpose":"digital_signature","role":"application_signer"}]) == "context"
