"""Registered reference normalizers -> independent review -> C# projections.

Isolated ephemeral loopback HTTP only, using an explicitly supplied built DLL.
No live provider, enterprise input, or owner acceptance is accessed or inferred.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

import pytest

from tests.test_pqc_enterprise_demo_http import Server, fixture_input, scope_fields
from tests.test_pqc_intake_http import raw_request
from tests.test_pqc_workspace_http import Work, FIXTURES, MIME
from tests.test_pqc_workspace_projection import stage_bytes
from tools.pqc_reference.synthetic_estate import generate_estate, KIND_TO_FAMILY
from workers.pqc.assessment_sources import normalize_page
from workers.pqc.extended_sources import extended_page_digest
from scripts.build_pqc_response_to_report_fixtures import edit as edit_workbook, workbook as read_workbook

pytestmark = pytest.mark.skipif(not os.environ.get("PQC_ENTERPRISE_DEMO_DLL"), reason="explicit built candidate required")
NORMALIZER = "workers.pqc.assessment_sources.normalize_page.v1"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def bundles():
    estate = generate_estate(application_count=12, source_scope="all")
    result = {}
    for page in estate["pages"]:
        family = KIND_TO_FAMILY.get(page["kind"], page["kind"])
        if family in result:
            continue
        raw = copy.deepcopy(page["payload"])
        raw["records"] = raw["records"][:1]
        if "content_sha256" in raw:
            raw["content_sha256"] = extended_page_digest(raw)
        records = normalize_page(page["kind"], raw, tenant_id=estate["tenant_id"],
                                 source_instance_id=page["source"], observed_at=page["observed_at"])
        result[family] = {
            "schemaVersion": "pqc.workspace.registered-source-bundle.v1", "synthetic": True,
            "tenantId": estate["tenant_id"], "familyId": family, "sourceInstanceId": page["source"],
            "sourceLabel": "Synthetic registered test source", "observedAt": page["observed_at"],
            "collectedAt": "2026-09-16T12:00:00Z", "normalizerVersion": NORMALIZER,
            "rawSourceSha256": hashlib.sha256(canonical(raw)).hexdigest(), "rawSource": raw, "records": records,
        }
    assert len(result) == 27
    return result


def register(path, data):
    entries = []
    for source in data.values():
        entries.append({"sha256": hashlib.sha256(canonical(source)).hexdigest(), "familyId": source["familyId"],
                        "sourceInstanceId": source["sourceInstanceId"], "normalizerVersion": NORMALIZER,
                        "rawSourceSha256": source["rawSourceSha256"]})
    path.write_bytes(canonical({"schemaVersion": "pqc.workspace.synthetic-bundle-registry.v1", "synthetic": True, "entries": entries}))
    path.chmod(0o600)


@pytest.fixture
def registered_server(tmp_path, fixture_input, monkeypatch):
    sources = bundles()
    registry = tmp_path / "registry.json"
    register(registry, sources)
    monkeypatch.setenv("PQC_SYNTHETIC_BUNDLE_REGISTRY_FILE", str(registry))
    fixture = json.loads(fixture_input.read_text())
    fixture["asOf"] = "2026-09-16T12:00:00Z"
    current_fixture = tmp_path / "input.json"
    current_fixture.write_bytes(canonical(fixture))
    current_fixture.chmod(0o600)
    server = Server(tmp_path, current_fixture)
    try:
        yield server.start(), sources, registry
    finally:
        server.stop()


def permit(work, families):
    scope = scope_fields(work.ws)
    scope.update(includedFamilyIds=families, depthByFamily={f: "inventory" for f in families},
                 excludedReasons={s["familyId"]: "Outside this reference test" for s in work.ws.state["sources"] if s["familyId"] not in families})
    work.ws.command("update_scope", fields=scope)
    work.ws.gate("PQC-G00")
    for index, family in enumerate(families):
        work.ws.command("source_response", family, {"state": "unknown", "systemOfRecord": "Registered synthetic source fixture",
            "product": "Not vendor-qualified", "ownerFunction": "Synthetic reference coordinator", "accessRoute": "Synthetic files only",
            "note": "Population and enterprise access remain unknown; no operational collection is authorized.",
            "dueAt": "2026-09-22", "assertedBy": "Synthetic fixture coordinator"})
        if index % 8 == 7:
            work.checkpoint()
    work.ws.gate("PQC-P1-G01")
    work.checkpoint()


def test_all_27_registered_families_require_record_review_and_project_sources(registered_server):
    server, sources, _ = registered_server
    work = Work(server)
    receipt = work.receive()["receipt"]
    work.apply(receipt)
    product = receipt["products"][0]
    work.identify(product)
    permit(work, list(sources))
    for index, (family, source) in enumerate(sources.items()):
        status, response, _ = stage_bytes(work, product["id"], canonical(source))
        assert status == 200, (family, response)
        bundle = response["case"]["technicalRecords"][-1]
        assert bundle["status"] == "staged"
        record = bundle["observations"][0]
        assert record["normalizerVersion"] == NORMALIZER
        assert record["facts"] == source["records"][0]["facts"]
        assert record["sourceRawSha256"] == source["rawSourceSha256"]
        assert work.ws.client.request(work.ws.route + "/analysis")[1]["summary"]["observations"] == index
        if index == 0:
            work.command("workspace_admit_evidence", bundle["id"], expected=409)
            work.command("workspace_review_evidence", bundle["id"], {"determination": "qualified", "rationale": "No self-review", "recordDecisions": []}, expected=403)
            work.command("workspace_review_evidence", bundle["id"], {"determination": "qualified", "rationale": "Every record must be examined", "recordDecisions": []}, role="reviewer", expected=409)
        work.command("workspace_review_evidence", bundle["id"], {"determination": "qualified", "rationale": "Source assumptions retained",
            "recordDecisions": [{"observationId": record["id"], "determination": "supports_claim", "rationale": "Only the registered synthetic source assertion, not independent verification."}]}, role="reviewer")
        work.command("workspace_admit_evidence", bundle["id"])
        work.checkpoint()
    analysis = work.ws.client.request(work.ws.route + "/analysis")[1]
    assert analysis["summary"]["observations"] == 27
    assert analysis["summary"]["assets"] == 27
    assert {f for row in analysis["assets"] for f in row["familyIds"]} == set(sources)
    assert len([row for row in analysis["coverage"] if row["present"] > 0]) == 10
    assert any(row["kind"] == "cryptographic_use" for row in analysis["graph"]["nodes"])
    endpoint = next(a for a in analysis["assets"] if "traffic-termination" in a["familyIds"])
    endpoint_detail = work.ws.client.request(work.ws.route + "/assets/" + endpoint["id"])[1]
    assert len(endpoint_detail["dependencies"]) >= 2
    assert {use["purpose"] for use in endpoint_detail["cryptographicUses"]} == {"key_establishment", "authentication"}
    assert all(use["independently_verified"] is False for use in endpoint_detail["cryptographicUses"])
    assert endpoint_detail["observations"][0]["facts"]["application_ref"].startswith("wsubject-")
    policy = next(a for a in analysis["assets"] if "policy-exceptions" in a["familyIds"])
    detail = work.ws.client.request(work.ws.route + "/assets/" + policy["id"])[1]
    assert detail["cryptographicUses"] == []
    assert "reported_policy_not_authorization" in {r["code"] for r in detail["limitations"]}
    assert detail["observations"][0]["facts"]["independently_verified"] is False
    report = work.ws.report("phase1")
    html = work.ws.client.request(work.ws.route + "/reports/" + report["metadata"]["id"] + "/download?format=html")[1]
    assert "purpose: key_establishment" in html
    assert "relationship: belongs_to_application" in html
    assert "cryptographic uses:</strong> Not established" not in html
    assert "relationships:</strong> Not established" not in html
    assert "reported system/source bindings have admitted supporting records" in html
    assert "not independently examined target deployments" in html


def test_source_platform_is_not_labeled_as_described_application_technology(registered_server):
    server, sources, _ = registered_server
    work = Work(server)
    # Keep the published questionnaire definition unchanged. This returned
    # source row intentionally names an inventory platform whose records
    # describe another system; the two names must not become one technology.
    original = (FIXTURES / "traffic-initial.xlsx").read_bytes()
    original_cells, worksheet_paths, _ = read_workbook(original)
    assert "Products & deployments" in worksheet_paths
    assert original_cells["Products & deployments"]["A4"] == "F5 BIG-IP"
    assert original_cells["Products & deployments"]["B4"] == "gateway-east"
    # The validated template helper resolves workbook relationships and shared
    # strings; hard-coded sheet numbers / text replacement can silently do nothing.
    amended = edit_workbook(original, {"Products & deployments": {"A4": "ServiceNow CMDB", "B4": "cmdb-selected"}})
    amended_cells, _, _ = read_workbook(amended)
    assert amended_cells["Products & deployments"]["A4"] == "ServiceNow CMDB"
    assert amended_cells["Products & deployments"]["B4"] == "cmdb-selected"
    assert amended_cells["Products & deployments"]["A5"] == original_cells["Products & deployments"]["A5"]
    query = urlencode({"requestId": work.request, "expectedRevision": work.ws.refresh()["revision"], "filename": "synthetic-source-platform.xlsx"})
    status, result, _ = raw_request(work.ws.client, work.ws.route + "/receipts?" + query, method="POST", data=amended,
        content_type=MIME, headers={"Idempotency-Key": uuid4().hex})
    assert status == 200, result
    receipt = result["receipt"]
    work.apply(receipt)
    edited_rows = [row for row in receipt["products"] if row["provenance"] == "Products & deployments!A4:H4"]
    assert len(edited_rows) == 1
    product = edited_rows[0]
    assert product["product"] == "ServiceNow CMDB"
    assert product["deployment"] == "cmdb-selected"
    identity = work.identify(product)
    permit(work, ["traffic-termination", "cmdb"])
    status, response, _ = stage_bytes(work, product["id"], canonical(sources["cmdb"]))
    assert status == 200, response
    bundle = response["case"]["technicalRecords"][-1]
    observation = bundle["observations"][0]
    work.command("workspace_review_evidence", bundle["id"], {"determination": "qualified", "rationale": "Source platform and described application are distinct.",
        "recordDecisions": [{"observationId": observation["id"], "determination": "supports_claim", "rationale": "Only the supplied application-context fields."}]}, role="reviewer")
    work.command("workspace_admit_evidence", bundle["id"])
    analysis = work.ws.client.request(work.ws.route + "/analysis")[1]
    asset = next(row for row in analysis["assets"] if "cmdb" in row["familyIds"])
    detail = work.ws.client.request(work.ws.route + "/assets/" + asset["id"])[1]
    fact = detail["observations"][0]["facts"]
    assert fact["source_product_label"] == "ServiceNow CMDB"
    assert "product_label" not in fact
    assert "ServiceNow" not in asset["technology"]
    assert asset["id"] == observation["systemId"] != identity["canonicalId"]
    assert detail["observations"][0]["source_instance_id"] != asset["id"]
    assert fact["name"] == sources["cmdb"]["records"][0]["facts"]["name"]
    report = work.ws.report("phase1")
    population = report["content"]["workspace"]["populationStatement"]
    assert report["content"]["manifest"]["workspaceTemplateVersion"] == "pqc.response-to-report.html.v4"
    assert population.startswith("1 of 1 reported system/source bindings")
    assert "not independently examined target deployments" in population


def test_unregistered_tampered_or_wrong_scope_bundles_do_not_mutate(registered_server):
    server, sources, registry = registered_server
    work = Work(server)
    receipt = work.receive()["receipt"]
    work.apply(receipt)
    product = receipt["products"][0]
    work.identify(product)
    permit(work, ["traffic-termination"])
    before = work.ws.refresh()["revision"]
    status, result, _ = stage_bytes(work, product["id"], canonical(sources["ssh"]))
    assert status == 409 and "workspace_source_not_in_scope" in json.dumps(result)
    altered = copy.deepcopy(sources["traffic-termination"])
    altered["records"][0]["facts"]["key_exchange_group"] = "X25519MLKEM768"
    status, result, _ = stage_bytes(work, product["id"], canonical(altered))
    assert status == 400 and "workspace_synthetic_bundle_not_registered" in json.dumps(result)
    assert work.ws.refresh()["revision"] == before
    assert not work.case()["technicalRecords"]

    # Even an exact registered entry cannot override the closed dialect and raw
    # identity checks. A registry is not permission for arbitrary conclusions.
    altered = copy.deepcopy(sources["traffic-termination"])
    altered["records"][0]["assertion_kind"] = "independent_verification"
    register(registry, {"invalid": altered})
    status, result, _ = stage_bytes(work, product["id"], canonical(altered))
    assert status == 400 and "workspace_synthetic_source_invalid" in json.dumps(result)
    assert work.ws.refresh()["revision"] == before
    invalid_cases = []
    for field, value in (("rawSourceSha256", "0" * 64), ("observedAt", "2026-09-17T12:00:00Z"), ("tenantId", "synthetic-unrelated")):
        altered = copy.deepcopy(sources["traffic-termination"])
        altered[field] = value
        invalid_cases.append(altered)
    altered = copy.deepcopy(sources["traffic-termination"])
    altered["records"][0]["approved"] = True
    invalid_cases.append(altered)
    for altered in invalid_cases:
        register(registry, {"invalid": altered})
        status, result, _ = stage_bytes(work, product["id"], canonical(altered))
        assert status == 400 and "workspace_synthetic_source_invalid" in json.dumps(result)
        assert work.ws.refresh()["revision"] == before


def test_registry_is_explicit_and_cross_assessment_product_is_rejected(registered_server, monkeypatch):
    server, sources, registry = registered_server
    work = Work(server)
    receipt = work.receive()["receipt"]
    work.apply(receipt)
    product = receipt["products"][0]
    permit(work, ["traffic-termination"])
    other = Work(server)
    other_receipt = other.receive()["receipt"]
    other.apply(other_receipt)
    status, result, _ = stage_bytes(work, other_receipt["products"][0]["id"], canonical(sources["traffic-termination"]))
    assert status == 400, result
    assert not work.case()["technicalRecords"]
    monkeypatch.delenv("PQC_SYNTHETIC_BUNDLE_REGISTRY_FILE")
    work.checkpoint()
    status, result, _ = stage_bytes(work, product["id"], canonical(sources["traffic-termination"]))
    assert status == 400 and "workspace_synthetic_registry_required" in json.dumps(result)
    assert not work.case()["technicalRecords"]
