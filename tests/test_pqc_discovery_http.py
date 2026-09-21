"""Five-question discovery behavior in an explicitly built, isolated demo only."""
from __future__ import annotations

import json
import os
import sqlite3
from uuid import uuid4

import pytest

from tests.test_pqc_enterprise_demo_http import Client, Server, Workspace, fixture_input

pytestmark = pytest.mark.skipif(not os.environ.get("PQC_ENTERPRISE_DEMO_DLL"), reason="explicit built candidate DLL required")


@pytest.fixture
def discovery_server(tmp_path, fixture_input):
    server = Server(tmp_path, fixture_input)
    try:
        yield server.start()
    finally:
        server.stop()


class DiscoveryFlow:
    def __init__(self, server):
        self.ws = Workspace(Client(server.origin).login(), "fresh")
        self.route = self.ws.route + "/discovery"

    def actor(self, role="analyst"):
        return self.ws.actor(role)

    def view(self, role="analyst"):
        response = self.actor(role).request(self.route)
        assert response[0] == 200, response[1]
        return response[1]

    def command(self, operation, target=None, fields=None, role="analyst", expected=200, revision=None, key=None):
        response = self.actor(role).request(self.route + "/commands", method="POST",
            body={"operation": operation, "targetId": target, "fields": fields or {},
                "expectedRevision": self.ws.refresh()["revision"] if revision is None else revision},
            headers={"Idempotency-Key": key or uuid4().hex})
        assert response[0] == expected, (operation, response[0], response[1])
        return response[1]

    def create(self, recipient="contributor", family="traffic-termination"):
        created = self.command("discovery_create", fields={"title": "Synthetic first contact",
            "familyId": family, "assignedTo": "synthetic-demo:" + recipient})
        return created["requests"][-1]["id"]

    def detail(self, request, role="analyst"):
        response = self.actor(role).request(self.route + "/" + request)
        assert response[0] == 200, response[1]
        return response[1]


def test_five_actual_questions_allow_useful_partial_without_full_dossier(discovery_server):
    flow = DiscoveryFlow(discovery_server)
    request = flow.create()
    detail = flow.detail(request, "contributor")
    form = detail["request"]
    assert form["templateVersion"] == "pqc.discovery.v2"
    assert [q["id"] for q in form["questions"]] == [f"DQ-{i:02d}" for i in range(1, 6)]
    assert len(form["answers"]) == 5
    assert form["examples"] == next(f["examples"] for f in flow.view()["families"] if f["id"] == "traffic-termination")
    assert form["questions"][-1]["prompt"] == "Are there any access restrictions, information-sharing considerations, or known gaps we should understand?"
    assert "do not need to establish policy or resolve the issue yourself" in form["questions"][-1]["usefulResponse"]
    assert "requesting evidence" not in json.dumps(form["questions"])
    guidance = detail["guidance"]
    assert set(guidance) == {"introduction", "handlingNotice", "reviewNotice", "submissionReceipt", "legacyNotice"}
    assert "Product names, document references, referrals and not sure" in guidance["introduction"]
    assert "do not need to create documents or demonstrate compliance" in guidance["handlingNotice"]
    assert "Do not submit credentials or sensitive files" in guidance["handlingNotice"]
    assert "agreed separately with the appropriate owner" in guidance["handlingNotice"]
    assert "submitting does not authorize access or complete the assessment" in guidance["reviewNotice"]
    assert guidance["legacyNotice"] == ""
    assert not detail["validation"]["canSubmit"]
    flow.command("discovery_submit", request, role="contributor", expected=409)
    saved = flow.command("discovery_save", request, {"answers": {"DQ-02": {"status": "referral", "text": "Synthetic platform team"}}}, "contributor")
    assert saved["validation"]["canSubmit"]
    assert sum(a["status"] == "unanswered" for a in saved["request"]["answers"].values()) == 4
    assert saved["request"]["productRefs"] == []
    submitted = flow.command("discovery_submit", request, role="contributor")
    assert submitted["request"]["status"] == "submitted" and not submitted["canEdit"]
    assert submitted["request"]["answers"]["DQ-02"]["recordedBy"] == "synthetic-demo:contributor"
    assert submitted["request"]["submission"]["contentSha256"]
    assert submitted["guidance"] == guidance
    assert submitted["request"]["receipt"] == guidance["submissionReceipt"]
    flow.command("discovery_save", request, {"answers": {}}, "contributor", expected=409)
    state = flow.ws.refresh()
    assert state["questionnaires"]["assignments"] == [] and state["intake"]["requests"] == []
    assert not state["documents"] and all(g["state"] == "not_submitted" for g in state["gates"])


@pytest.mark.parametrize("status", ["unknown", "not_my_team", "not_applicable"])
def test_explicit_unknown_or_non_owner_does_not_require_invented_commitments(discovery_server, status):
    flow = DiscoveryFlow(discovery_server)
    request = flow.create()
    saved = flow.command("discovery_save", request, {"answers": {"DQ-01": {"status": status}}}, "contributor")
    assert saved["validation"]["canSubmit"]
    answer = saved["request"]["answers"]["DQ-01"]
    assert answer["reference"] == "" and "nextDate" not in answer and "nextOwner" not in answer
    assert flow.command("discovery_submit", request, role="contributor")["request"]["status"] == "submitted"


def test_assignment_privacy_current_authority_and_idempotency(discovery_server):
    flow = DiscoveryFlow(discovery_server)
    assert flow.actor("contributor").request(flow.route)[0] == 403
    assert flow.actor("contributor").request("/api/assessments")[1] == []
    first = flow.create()
    second = flow.create("contributor-two")
    assert [r["id"] for r in flow.view("contributor")["requests"]] == [first]
    assert flow.view("contributor")["standards"] == [] and flow.view("contributor")["investigations"] == []
    assert flow.actor("contributor").request(flow.route + "/" + second)[0] == 403
    assert flow.actor("contributor").request(flow.ws.route)[0] == 403
    flow.command("discovery_save", second, {"answers": {}}, "contributor", expected=403)
    flow.command("discovery_create", fields={"title": "Denied", "familyId": "traffic-termination", "assignedTo": "synthetic-demo:contributor"}, role="contributor", expected=403)
    revision = flow.ws.refresh()["revision"]
    key = uuid4().hex
    fields = {"answers": {"DQ-05": {"status": "answered", "text": "None known"}}}
    saved = flow.command("discovery_save", first, fields, "contributor", revision=revision, key=key)
    assert flow.command("discovery_save", first, fields, "contributor", revision=revision, key=key) == saved
    flow.command("discovery_save", first, {"answers": {"DQ-05": {"text": "Different"}}}, "contributor", revision=revision, key=key, expected=409)
    flow.command("discovery_save", first, fields, "contributor", revision=revision, expected=409)
    payload = {"operation": "discovery_save", "targetId": first, "fields": fields, "expectedRevision": revision}
    for headers in ({"Origin": "https://untrusted.example"}, {"X-PQC-CSRF": "invalid"}):
        assert flow.actor("contributor").request(flow.route + "/commands", method="POST", body=payload,
            headers={"Idempotency-Key": key, **headers})[0] == 403


def test_staff_investigation_can_add_multiple_deployments_after_unknown(discovery_server):
    flow = DiscoveryFlow(discovery_server)
    request = flow.create()
    flow.command("discovery_save", request, {"answers": {"DQ-01": {"status": "unknown"}}}, "contributor")
    submitted = flow.command("discovery_submit", request, role="contributor")["request"]
    created = flow.command("discovery_create_investigation", request,
        {"purpose": "Investigate source shapes using public documentation", "assignedTo": "synthetic-demo:reviewer", "productRefIds": []})
    investigation = created["investigations"][-1]["id"]
    for _ in range(2):
        updated = flow.command("discovery_add_product", investigation,
            {"label": "Synthetic same-named deployment", "product": "Synthetic TLS platform", "environment": "synthetic"})
    products = updated["investigations"][-1]["productRefs"]
    assert len(products) == 2 and products[0]["id"] != products[1]["id"]
    assert all(p["recordedBy"] == "synthetic-demo:analyst" for p in products)
    researched = flow.command("discovery_update_investigation", investigation,
        {"status": "ready_for_review", "researchSummary": "Public documentation only; not verified against a product instance.",
            "proposedMethod": "Build bounded synthetic fixtures before access qualification", "documentationRefs": ["https://example.invalid/synthetic-reference"], "limitation": "No source connection"}, "reviewer")
    row = researched["investigations"][-1]
    assert row["status"] == "ready_for_review" and row["evidenceReviews"] == [] and row["intakeRequestId"] is None
    assert flow.detail(request)["request"] == submitted
    assert flow.ws.refresh()["intake"]["batches"] == []
    flow.command("discovery_update_investigation", investigation, {"status": "verified"}, "reviewer", expected=400)
    flow.command("discovery_add_product", investigation, {"label": "Denied", "product": "", "environment": ""}, "reviewer", expected=403)
    flow.command("discovery_update_investigation", investigation, {"status": "researching"}, "contributor", expected=403)


def test_one_class_keeps_multiple_products_and_deployments_through_submission_and_investigation(discovery_server):
    flow = DiscoveryFlow(discovery_server)
    request = flow.create(family="traffic-termination")
    rows = [
        {"id": "", "label": "Synthetic proxy A / nonproduction", "product": "Synthetic proxy A", "environment": "nonproduction"},
        {"id": "", "label": "Synthetic proxy A / production", "product": "Synthetic proxy A", "environment": "production"},
        {"id": "", "label": "Synthetic proxy B / production", "product": "Synthetic proxy B", "environment": "production"},
    ]
    saved = flow.command("discovery_save", request, {"productRefs": rows}, "contributor")
    products = saved["request"]["productRefs"]
    first_revision = saved["revision"]
    assert saved["validation"]["canSubmit"]
    assert saved["request"]["familyId"] == "traffic-termination"
    assert len({product["id"] for product in products}) == 3
    assert [product["product"] for product in products] == [row["product"] for row in rows]
    assert all(product["recordedBy"] == "synthetic-demo:contributor" and product["recordedAt"] for product in products)
    assert len(saved["request"]["questions"]) == 5
    assert all(answer["status"] == "unanswered" for answer in saved["request"]["answers"].values())

    # Reorder the entries and correct one deployment without merging products
    # with the same name or replacing their stable server-held identities.
    reordered = [{key: product[key] for key in ("id", "label", "product", "environment")}
        for product in (products[2], products[1], products[0])]
    reordered[2]["label"] = "Synthetic proxy A / test"
    reordered[2]["environment"] = "test"
    corrected = flow.command("discovery_save", request, {"productRefs": reordered}, "contributor")
    assert [product["id"] for product in corrected["request"]["productRefs"]] == [row["id"] for row in reordered]
    assert corrected["request"]["productRefs"][:2] == [products[2], products[1]]
    assert flow.detail(request, "contributor")["request"] == corrected["request"]

    submitted = flow.command("discovery_submit", request, role="contributor")
    submitted_request = submitted["request"]
    assert submitted_request["status"] == "submitted" and not submitted["canEdit"]
    assert submitted_request["productRefs"] == corrected["request"]["productRefs"]
    assert submitted_request["submission"]["contentSha256"]
    flow.command("discovery_save", request, {"productRefs": []}, "contributor", expected=409)

    discovery_server.stop()
    discovery_server.start()
    flow.actor().login()
    flow.actor("contributor").login("contributor")
    assert flow.detail(request, "contributor")["request"] == submitted_request
    selected_ids = [product["id"] for product in submitted_request["productRefs"]]
    investigated = flow.command("discovery_create_investigation", request,
        {"purpose": "Research the distinct synthetic products and deployment contexts", "assignedTo": "synthetic-demo:reviewer",
            "productRefIds": selected_ids})["investigations"][-1]
    assert investigated["familyId"] == "traffic-termination"
    assert investigated["productRefIds"] == selected_ids
    assert investigated["productRefs"] == submitted_request["productRefs"]
    assert investigated["evidenceReviews"] == [] and investigated["intakeRequestId"] is None
    assert flow.detail(request, "contributor")["request"] == submitted_request
    state = flow.ws.refresh()
    assert state["intake"]["batches"] == [] and state["documents"] == []
    assert all(gate["state"] == "not_submitted" for gate in state["gates"])

    # Corrections and submission append history; they do not overwrite the
    # original response snapshot or manufacture verified technical evidence.
    with sqlite3.connect(discovery_server.data / "enterprise-demo.sqlite3") as database:
        historical = database.execute("SELECT snapshot_json FROM assessment_versions WHERE assessment_id=? AND revision=?",
            (state["id"], first_revision)).fetchone()
        assert historical is not None
        historical_request = next(item for item in json.loads(historical[0])["discovery"]["requests"] if item["id"] == request)
        assert historical_request["status"] == "draft"
        assert historical_request["productRefs"] == products


def test_proposed_standards_do_not_assume_existing_policy_or_automatic_adoption(discovery_server):
    flow = DiscoveryFlow(discovery_server)
    standards = flow.view()["standards"]
    assert {s["id"] for s in standards} == {"assessment-evidence", "crypto-agility", "migration-assurance"}
    assert all(s["status"] == "draft" and s["existingRequirementStatus"] == "unassessed" for s in standards)
    assert all(len(s["proposalText"]) > 500 and s["publicationRefs"] for s in standards)
    assert any("Draft" in ref["status"] for s in standards for ref in s["publicationRefs"])
    changed = flow.command("discovery_update_standard", "assessment-evidence",
        {"existingRequirementStatus": "not_identified", "observedPractice": "Synthetic existing practice has not been established",
            "authorityStatus": "proposed_owner", "proposedAuthority": "Synthetic information governance function",
            "conflictReviewStatus": "unassessed", "conflictNote": "Reconcile existing controls before considering adoption."})
    standard = next(s for s in changed["standards"] if s["id"] == "assessment-evidence")
    assert standard["status"] == "draft" and standard["recordedBy"] == "synthetic-demo:analyst"
    assert standard["revision"] == changed["revision"] and standard["recordedAt"]
    flow.command("discovery_update_standard", "assessment-evidence", {"status": "adopted"}, expected=400)
    flow.command("discovery_update_standard", "assessment-evidence", {"authorityStatus": "approved"}, expected=400)
    flow.command("discovery_update_standard", "assessment-evidence", {"conflictNote": "Denied"}, "reviewer", expected=403)
    assert all(g["state"] == "not_submitted" for g in flow.ws.refresh()["gates"])


def test_attribution_reopen_history_and_restart_keep_prior_submission(discovery_server):
    flow = DiscoveryFlow(discovery_server)
    request = flow.create()
    recorded = flow.command("discovery_save", request, {"answers": {"DQ-02": {"status": "answered", "text": "Synthetic meeting referral", "assertedBy": "Synthetic meeting respondent"}}})
    prior = recorded["request"]["answers"]["DQ-02"]
    flow.command("discovery_save", request, {"answers": {
        "DQ-02": {k: v for k, v in prior.items() if k != "recordedBy"}, "DQ-05": {"status": "unknown"}}}, "contributor")
    assert flow.detail(request)["request"]["answers"]["DQ-02"] == prior
    flow.command("discovery_save", request, {"answers": {"DQ-01": {"recordedBy": "synthetic-demo:sponsor"}}}, "contributor", expected=400)
    flow.command("discovery_save", request, {"answers": {"DQ-01": {"assertedBy": "synthetic-demo:sponsor"}}}, "contributor", expected=400)
    submitted = flow.command("discovery_submit", request, role="contributor")
    reopened = flow.command("discovery_reopen", request, {"reason": "Synthetic source routing correction"})
    history = reopened["request"]["history"][0]
    assert history["previousSubmissionSha256"] == submitted["request"]["submission"]["contentSha256"]
    assert history["reason"] == "Synthetic source routing correction"
    assert history["actor"] == "synthetic-demo:analyst"
    before = flow.detail(request)
    discovery_server.stop(); discovery_server.start()
    flow.actor().login()
    assert flow.detail(request) == before
    with sqlite3.connect(discovery_server.data / "enterprise-demo.sqlite3") as database:
        row = database.execute("SELECT snapshot_json FROM assessment_versions WHERE assessment_id=? AND revision=?",
            (flow.ws.state["id"], submitted["revision"])).fetchone()
        assert submitted["request"]["submission"]["contentSha256"] in row[0]
        with pytest.raises(sqlite3.DatabaseError, match="immutable"):
            database.execute("DELETE FROM assessment_versions")
