"""Bounded actual operational-return -> factual review -> report HTTP proofs.

Explicit compiled DLL only; each test uses a fresh temporary SQLite database,
synthetic workbook fixtures and random loopback listener. No provider or owner
acceptance is contacted or inferred.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

import pytest

from tests.test_pqc_enterprise_demo_http import Client, Server, Workspace, fixture_input, scope_fields
from tests.test_pqc_intake_http import raw_request

pytestmark = pytest.mark.skipif(not os.environ.get("PQC_ENTERPRISE_DEMO_DLL"), reason="explicit built C# DLL required")
FIXTURES = Path(__file__).parent / "fixtures/pqc-operational-return-v1/synthetic-scenario"
MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
def work_server(tmp_path, fixture_input):
    server = Server(tmp_path, fixture_input)
    try:
        yield server.start()
    finally:
        server.stop()


class Work:
    def __init__(self, server, mode="fresh"):
        self.server = server
        self.ws = Workspace(Client(server.origin).login(), mode)
        scope = scope_fields(self.ws)
        scope.update(includedFamilyIds=["traffic-termination"], depthByFamily={"traffic-termination": "inventory"},
            excludedReasons={s["familyId"]: "Outside the selected synthetic traffic cohort" for s in self.ws.state["sources"] if s["familyId"] != "traffic-termination"})
        self.ws.command("update_scope", fields=scope)
        self.request = self.new_request()

    def new_request(self):
        self.ws.refresh()
        status, result, _ = self.ws.client.request(self.ws.route + "/discovery/commands", method="POST",
            body=self.ws.payload("discovery_create", fields={"title": "Synthetic traffic-source return", "familyId": "traffic-termination", "assignedTo": "synthetic-demo:contributor"}),
            headers={"Idempotency-Key": uuid4().hex})
        assert status == 200, result
        return result["requests"][-1]["id"]

    def case(self, request=None, role="analyst"):
        status, result, _ = self.ws.actor(role).request(self.ws.route + "/work/" + (request or self.request))
        assert status == 200, result
        return result

    def receive(self, filename="traffic-initial.xlsx", request=None, key=None, revision=None, expected=200):
        query = urlencode({"requestId": request or self.request, "expectedRevision": self.ws.refresh()["revision"] if revision is None else revision, "filename": filename})
        status, result, _ = raw_request(self.ws.client, self.ws.route + "/receipts?" + query, method="POST", data=(FIXTURES / filename).read_bytes(),
            content_type=MIME, headers={"Idempotency-Key": key or uuid4().hex})
        assert status == expected, result
        return result

    def command(self, operation, target=None, fields=None, role="analyst", expected=200, revision=None, key=None):
        self.ws.refresh()
        payload = self.ws.payload(operation, target or self.request, fields)
        if revision is not None:
            payload["expectedRevision"] = revision
        status, result, _ = self.ws.actor(role).request(self.ws.route + "/work/commands", method="POST", body=payload,
            headers={"Idempotency-Key": key or uuid4().hex})
        assert status == expected, (operation, status, result)
        return result

    def apply(self, receipt, choices=None):
        return self.command("receipt_apply", receipt["id"], {"choices": choices or {}, "note": "Coordinator records unverified attributed workbook input, not respondent or technical approval."})

    def identify(self, product, decision="distinct", canonical=""):
        result = self.command("reconcile_product", fields={"productId": product["id"], "decision": decision, "canonicalId": canonical,
            "label": product["deployment"] or product["product"], "applicationService": "Synthetic portal service", "team": "Reported platform team", "rationale": "Reviewed synthetic deployment identity; original rows remain unchanged."})
        return next(i for i in result["case"]["identityDecisions"] if i["productId"] == product["id"])

    def stage(self, product, filename="tls-configured.json", expected=200):
        query = urlencode({"productId": product["id"], "expectedRevision": self.ws.refresh()["revision"]})
        status, result, _ = raw_request(self.ws.client, self.ws.route + "/work/" + self.request + "/evidence?" + query,
            method="POST", data=(FIXTURES / filename).read_bytes(), content_type="application/json", headers={"Idempotency-Key": uuid4().hex})
        assert status == expected, result
        return result

    def preview(self, fields, expected=200):
        self.ws.refresh()
        status, result, _ = self.ws.client.request(self.ws.route + "/report-impact/preview", method="POST", body=self.ws.payload("record_consequence", self.request, fields))
        assert status == expected, result
        return result

    def checkpoint(self):
        """Exercise actual restart/resume, also keeping fixtures within rate limits."""
        self.server.stop()
        self.server.start()
        client = Client(self.server.origin).login()
        self.ws.client = client
        self.ws.clients = {"analyst": client}
        self.ws.refresh()


def conclusion(product="", **overrides):
    fields = {"productId": product, "cryptographicPurpose": "key_establishment", "phase1Conclusion": "The selected synthetic capture supports only the stated configuration basis.",
        "limitation": "Live enterprise access and independent negotiated-behavior verification remain absent.", "nextDecision": "Identify the authorized investigator for the selected deployment.",
        "responsibleFunction": "Platform owner", "phase2Consequence": "Long-lived information may require a compatibility investigation; business impact remains unconfirmed.",
        "lifetime": "Unknown; business reviewer input required", "confidence": "limited", "supportingObservationIds": [], "contradictingObservationIds": []}
    fields.update(overrides)
    return fields


def test_operational_receipt_replay_conflicts_attribution_and_assessment_isolation(work_server):
    work = Work(work_server)
    before = work.ws.refresh()["workspace"]["materialFingerprint"]
    revision = work.ws.state["revision"]
    received = work.receive(key="same-return-proof", revision=revision)
    assert work.receive(key="same-return-proof", revision=revision) == received
    assert work.ws.refresh()["workspace"]["materialFingerprint"] == before
    assert received["receipt"]["status"] == "staged"
    assert len(received["receipt"]["products"]) == 4
    assert work.case()["task"]["step"] == "returned"
    assert work.ws.actor("contributor").request(work.ws.route + "/work")[0] == 403
    work.receive("traffic-revised.xlsx", key="same-return-proof", revision=revision, expected=409)
    other_request = work.new_request()
    duplicate_revision=work.ws.refresh()["revision"]
    duplicate = work.receive("traffic-duplicate.xlsx", request=other_request,key="duplicate-outcome-proof",revision=duplicate_revision)
    assert duplicate["duplicate"] is True
    assert duplicate["existingRequestId"] == work.request
    assert work.receive("traffic-duplicate.xlsx",request=other_request,key="duplicate-outcome-proof",revision=duplicate_revision)==duplicate
    work.receive("traffic-revised.xlsx",request=other_request,key="duplicate-outcome-proof",revision=duplicate_revision,expected=409)
    assert work.ws.refresh()["workspace"]["materialFingerprint"]==before
    assert work.case(other_request)["receipts"] == []
    assert not any(e["operation"] == "receipt_receive" for e in work.case(other_request)["history"])
    work.apply(received["receipt"])
    case = work.case()
    assert case["request"]["status"] == "submitted"
    assert "unverified" in case["request"]["receipt"]
    assert case["request"]["answers"]["DQ-02"]["recordedBy"] == "synthetic-demo:analyst"
    assert case["request"]["answers"]["DQ-02"]["assertedBy"] != "synthetic-demo:analyst"
    assert work.ws.refresh()["sources"][next(i for i,s in enumerate(work.ws.state["sources"]) if s["familyId"] == "traffic-termination")]["state"] == "unknown"
    revised = work.receive("traffic-revised.xlsx")["receipt"]
    assert any(c["state"] == "conflict" for c in revised["comparison"])
    work.command("receipt_apply", revised["id"], {"choices": {}, "note": "Missing conflict choices"}, expected=409)
    choices = {c["questionId"]: "current" for c in revised["comparison"]}
    work.apply(revised, choices)
    assert len(work.case()["receipts"]) == 2
    second = Work(work_server)
    assert second.ws.client.request(second.ws.route + "/receipts/" + received["receipt"]["id"])[0] in (400, 404)
    second.command("reconcile_product", fields={"productId": received["receipt"]["products"][0]["id"], "decision": "distinct", "label": "Cross-assessment must fail", "rationale": "Not owned by this assessment"}, expected=400)


def test_reviewed_records_update_map_and_frozen_reports_without_false_completion(work_server):
    work = Work(work_server, "response_to_report_example")
    assert work.ws.state["mode"] == "fresh"
    assert work.case()["mode"] == "pqc.response-to-report.example.v1"
    receipt = work.receive()["receipt"]
    work.apply(receipt)
    product, west, blocked, alias = receipt["products"]
    canonical = work.identify(product)["canonicalId"]
    work.identify(west)
    work.identify(blocked, "unresolved")
    work.identify(alias, "same_system", canonical)
    assert not work.case()["canStageEvidence"]
    work.stage(product, expected=409)
    work.ws.gate("PQC-G00")
    work.ws.gate("PQC-P1-G01")
    assert work.case()["canStageEvidence"]
    work.checkpoint()
    for filename, determination in (("tls-configured.json", "supports_claim"), ("tls-observed.json", "conflict")):
        staged = work.stage(product, filename)["case"]["technicalRecords"][-1]
        bundle = staged["id"]
        assert work.case()["task"]["state"] == "waiting" and not work.case()["task"]["canAct"]
        assert work.case(role="reviewer")["task"]["state"] == "needs_action"
        assert work.ws.client.request(work.ws.route + "/analysis")[1]["summary"]["assets"] == (0 if filename == "tls-configured.json" else 1)
        route = work.ws.route + "/evidence/" + bundle + "/observations"
        records = work.ws.actor("reviewer").request(route + "?pageSize=1")[1]
        assert records["total"] == 1 and not records["hasMore"]
        assert "observations" not in records["bundle"]
        assert work.ws.client.request(route + "?pageSize=101")[0] == 400
        work.command("workspace_review_evidence", bundle, {"determination": "qualified", "rationale": "No individual decisions"}, role="reviewer", expected=409)
        decisions = [{"observationId": o["id"], "determination": determination, "rationale": "Configured and observed records can disagree; retain the actual source basis."} for o in records["observations"]]
        work.command("workspace_review_evidence", bundle, {"determination": "qualified", "rationale": "Closed synthetic fields reviewed, not live behavior verified.", "recordDecisions": decisions}, expected=403)
        work.command("workspace_review_evidence", bundle, {"determination": "qualified", "rationale": "Closed synthetic fields reviewed, not live behavior verified.", "recordDecisions": decisions}, role="reviewer")
        work.command("workspace_admit_evidence", bundle)
    work.checkpoint()
    analysis = work.ws.client.request(work.ws.route + "/analysis")[1]
    assert analysis["summary"]["assets"] == 1
    case = work.case()
    records = [o for b in case["technicalRecords"] for o in b["observations"]]
    assert {o["basis"] for o in records} == {"configured", "observed"}
    support = next(o["id"] for o in records if o["basis"] == "configured")
    contradiction = next(o["id"] for o in records if o["basis"] == "observed")
    fields = conclusion(product["id"], supportingObservationIds=[support], contradictingObservationIds=[contradiction], confidence="supported")
    prior = work.ws.refresh()["revision"]
    preview = work.preview(fields)
    assert work.ws.refresh()["revision"] == prior and work.case()["consequences"] == []
    assert len(preview["consequence"]["evidenceRevisionRefs"]) == 2
    work.identify(alias, "unresolved")
    work.command("record_consequence", fields={**fields, "previewFingerprint": preview["previewFingerprint"]}, expected=409)
    work.preview({**fields, "productId": west["id"]}, expected=400)
    work.preview({**fields, "supportingObservationIds": []}, expected=409)
    current = work.preview(fields)
    work.command("record_consequence", fields={**fields, "previewFingerprint": current["previewFingerprint"]})
    blocked_fields = conclusion(blocked["id"], cryptographicPurpose="unknown", confidence="unknown")
    blocked_preview = work.preview(blocked_fields)
    work.command("record_consequence", fields={**blocked_fields, "previewFingerprint": blocked_preview["previewFingerprint"]})
    assert len(work.case()["consequences"]) == 2
    assert work.case()["task"]["state"] == "waiting"
    assert "follow-up" in work.case()["task"]["task"]
    assert all(e["origin"] == "scenario_generated" for e in work.ws.refresh()["events"])
    report = work.ws.report("phase1")
    report_id = report["metadata"]["id"]
    route = work.ws.route + "/reports/" + report_id
    html = work.ws.client.request(route + "/download?format=html")[1]
    assert "Live enterprise access" in html and "X25519MLKEM768" in html
    assert len(report["content"]["workspace"]["consequences"]) == 2
    work.identify(alias, "same_system", canonical)
    assert work.ws.client.request(route)[1] == report
    assert work.ws.client.request(route + "/download?format=html")[1] == html
    work.checkpoint()
    assert work.ws.client.request(route)[1] == report
    assert work.ws.client.request(route + "/download?format=html")[1] == html
    # Correcting a reviewed identity must not silently relabel technical facts.
    # Hold only its dependent evidence/conclusion; keep unrelated records live.
    west_identity = next(i for i in work.case()["identityDecisions"] if i["productId"] == west["id"])
    work.identify(product, "same_system", west_identity["canonicalId"])
    changed = work.case()
    assert all(b["status"] == "identity_review_required" for b in changed["technicalRecords"])
    assert work.ws.client.request(work.ws.route + "/analysis")[1]["summary"]["assets"] == 0
    assert next(c for c in changed["consequences"] if c["productId"] == product["id"])["status"] == "needs_review"
    assert next(c for c in changed["consequences"] if c["productId"] == blocked["id"])["status"] == "recorded"
    assert work.ws.client.request(route + "/download?format=html")[1] == html
    for bundle in changed["technicalRecords"]:
        rows = [{"observationId": o["id"], "determination": o["technicalDetermination"], "rationale": "Independent review of changed deployment binding; source bytes remain unchanged."} for o in bundle["observations"]]
        work.command("workspace_review_evidence", bundle["id"], {"determination": "qualified", "rationale": "Independent binding review", "recordDecisions": rows}, role="reviewer")
        work.command("workspace_admit_evidence", bundle["id"])
    assert work.ws.client.request(work.ws.route + "/analysis")[1]["summary"]["assets"] == 1
    rebound = [o for b in work.case()["technicalRecords"] for o in b["observations"]]
    assert all(o["captureCanonicalId"] == canonical and o["canonicalId"] == west_identity["canonicalId"] for o in rebound)
    assert all(o["previousBindingRevision"] < o["revision"] for o in rebound)
    assert next(c for c in work.case()["consequences"] if c["productId"] == product["id"])["status"] == "needs_review"


def test_unreceived_or_unsupported_conclusion_cannot_claim_supported_technical_fact(work_server):
    work = Work(work_server)
    assert work.case()["task"]["state"] == "waiting"
    fields = conclusion(confidence="supported")
    work.preview(fields, expected=409)
    work.preview(conclusion(limitation=""), expected=400)
    work.preview(conclusion(supportingObservationIds=["unknown-observation"]), expected=400)
    work.command("record_consequence", fields={**conclusion(), "previewFingerprint": "0" * 64}, expected=409)
    assert work.case()["consequences"] == []
    assert work.ws.actor("contributor").request(work.ws.route + "/report-impact/preview", method="POST", body=work.ws.payload("record_consequence", work.request, conclusion()))[0] == 403
    assert work.ws.refresh()["documents"] == []


def test_cannot_establish_review_cannot_be_promoted_to_supported_conclusion(work_server):
    work = Work(work_server)
    receipt = work.receive()["receipt"]
    work.apply(receipt)
    product = receipt["products"][0]
    work.identify(product)
    work.ws.gate("PQC-G00")
    work.ws.gate("PQC-P1-G01")
    bundle = work.stage(product)["case"]["technicalRecords"][-1]
    observation = bundle["observations"][0]
    work.command("workspace_review_evidence", bundle["id"], {"determination": "qualified", "rationale": "Record retained to explain what is not established.",
        "recordDecisions": [{"observationId": observation["id"], "determination": "cannot_establish", "rationale": "This configuration does not establish the asserted live negotiated behavior."}]}, role="reviewer")
    work.command("workspace_admit_evidence", bundle["id"])
    assert work.case()["technicalRecords"][0]["observations"][0]["technicalDetermination"] == "cannot_establish"
    rejected = work.preview(conclusion(product["id"], supportingObservationIds=[observation["id"]], confidence="supported"), expected=409)
    assert "workspace_technical_determination_insufficient" in json.dumps(rejected)
    allowed = work.preview(conclusion(product["id"], supportingObservationIds=[observation["id"]], confidence="limited"))
    assert allowed["consequence"]["confidence"] == "limited"
    assert allowed["consequence"]["limitation"]
