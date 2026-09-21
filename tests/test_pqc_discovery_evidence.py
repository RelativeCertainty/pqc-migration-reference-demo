"""Five-question contribution -> staff investigation -> actual map/report proof.
Only isolated synthetic state and simulated identities, never owner verdicts.
"""
from __future__ import annotations
import copy
import json
import os
from urllib.parse import urlencode
from uuid import uuid4
import pytest
from tests.test_pqc_enterprise_demo_http import Client, Server, Workspace, decision_fields, fixture_input, scope_fields
from tests.test_pqc_enterprise_demo_http import unreported_business_context
from tests.test_pqc_intake_http import TLS, raw_request

pytestmark = pytest.mark.skipif(not os.environ.get("PQC_ENTERPRISE_DEMO_DLL"), reason="explicit isolated C# build required")

class DiscoveryJourney:
    def __init__(self, server, name="Isolated HTTP proof"):
        self.ws = Workspace(Client(server.origin).login(), "fresh", name=name)
        self.route = self.ws.route + "/discovery"
        scope = scope_fields(self.ws)
        scope.update(includedFamilyIds=["traffic-termination"], depthByFamily={"traffic-termination": "inventory"},
            excludedReasons={s["familyId"]: "Outside this bounded synthetic discovery proof." for s in self.ws.state["sources"] if s["familyId"] != "traffic-termination"})
        self.ws.command("update_scope", fields=scope)

    def view(self):
        status, data, _ = self.ws.client.request(self.route)
        assert status == 200, data
        return data

    def command(self, operation, target=None, fields=None, role="analyst", expected=200):
        status, result, _ = self.ws.actor(role).request(self.route + "/commands", method="POST",
            body={"operation": operation, "targetId": target, "fields": fields or {}, "expectedRevision": self.view()["revision"]},
            headers={"Idempotency-Key": uuid4().hex})
        assert status == expected, (operation, status, result)
        return result

    def prepare(self):
        self.command("discovery_create", fields={"title": "Which team can help with encrypted traffic?", "familyId": "traffic-termination", "assignedTo": "synthetic-demo:contributor"})
        self.request = self.view()["requests"][-1]["id"]
        self.command("discovery_save", self.request, {"answers": {
            "DQ-02": {"status": "referral", "text": "Synthetic network platform team can help."},
            "DQ-05": {"status": "unknown", "text": "I do not know which policy applies."}}}, "contributor")
        result = self.command("discovery_submit", self.request, role="contributor")
        assert result["request"]["status"] == "submitted"
        assert len(result["request"]["questions"]) == 5
        self.submission = copy.deepcopy(result["request"]["submission"])
        self.command("discovery_create_investigation", self.request, {"purpose": "Establish bounded TLS facts for two synthetic deployments.", "assignedTo": "synthetic-demo:analyst", "productRefIds": []})
        self.investigation = self.view()["investigations"][-1]["id"]
        for environment in ("east", "west"):
            self.command("discovery_add_product", self.investigation, {"label": f"Synthetic portal {environment}", "product": "Reference TLS configuration", "environment": environment})
        self.products = self.view()["investigations"][-1]["productRefs"]
        self.command("discovery_update_investigation", self.investigation, {"status": "researching", "researchSummary": "Closed synthetic reference format only; not an F5 API proof.",
            "proposedMethod": "Compare separate key-exchange and certificate-signature observations.", "documentationRefs": ["https://docs.openssl.org/3.5/man3/SSL_CTX_set1_curves/"],
            "limitation": "Business relationships, information lifetime, installed-product qualification and independent behavior remain unknown."})
        self.command("discovery_update_standard", "crypto-agility", {"observedPractice": "The respondent does not know the applicable policy; this is not evidence that no policy exists.",
            "existingRequirementStatus": "not_identified", "existingRequirementRefs": [], "authorityStatus": "proposed_owner", "proposedAuthority": "Synthetic enterprise security policy function",
            "conflictReviewStatus": "unassessed", "conflictNote": "Confirm existing requirements before considering adoption."})
        return self

    def gates(self):
        self.ws.gate("PQC-G00")
        self.ws.command("source_response", "traffic-termination", {"state": "route_confirmed", "systemOfRecord": "Controlled synthetic TLS pages", "product": "Reference format, not vendor API",
            "ownerFunction": "Synthetic network platform function", "accessRoute": "Synthetic fixture only, no live access", "note": "The simulated sponsor and information-owner authorize only the declared synthetic test boundary.",
            "dueAt": "2026-09-22", "assertedBy": "Synthetic coordinator"})
        self.ws.gate("PQC-P1-G01")

    def stage(self, product, *, hybrid=False, count=1, basis="configured", role="analyst", expected=200):
        payload=json.loads(TLS)
        payload["records"][0]["evidence_basis"]=basis
        payload["records"][0]["key_exchange_group"]="X25519MLKEM768" if hybrid else "X25519"
        for index in range(1,count):
            row=copy.deepcopy(payload["records"][0]);row.update(id=f"endpoint-{index+1}",hostname=f"portal{index+1}.example")
            payload["records"].append(row)
        query=urlencode({"expectedRevision": self.view()["revision"], "productRefId": product["id"], "sourceLabel": "Synthetic controlled export"})
        status,result,_=raw_request(self.ws.actor(role),f"{self.route}/investigations/{self.investigation}/evidence?{query}",method="POST",data=json.dumps(payload).encode(),content_type="application/json",headers={"Idempotency-Key":uuid4().hex})
        assert status==expected,(status,result)
        return result

    def admit_all(self):
        for index,product in enumerate(self.products):
            result=self.stage(product,hybrid=index==1)
            bundle=result["investigation"]["evidenceReviews"][-1]
            self.command("discovery_review_evidence",self.investigation,{"batchId":bundle["batchId"],"determination":"qualified","rationale":"Synthetic configured record; source namespace and separate crypto roles checked. No independent runtime verification."},"reviewer")
            self.command("discovery_admit_evidence",self.investigation,{"batchId":bundle["batchId"]})

    def resume_after_restart(self,server):
        # Deliberate durable checkpoint keeps this machine-speed test inside
        # the unchanged interactive action limiter, and proves session expiry.
        server.stop();server.start()
        self.ws.client=Client(server.origin).login()
        self.ws.clients={"analyst":self.ws.client}
        self.ws.refresh()

@pytest.fixture
def discovery_evidence_server(tmp_path,fixture_input):
    server=Server(tmp_path,fixture_input)
    try: yield server.start()
    finally: server.stop()

def test_short_partial_to_two_deployments_and_traceable_phase1_phase2(discovery_evidence_server):
    d=DiscoveryJourney(discovery_evidence_server).prepare()
    before=d.ws.report("phase1")
    assert before["content"]["summary"]["observations"]==0
    assert before["content"]["discovery"]["responses"][0]["submission"]==d.submission
    d.stage(d.products[0],expected=409)
    d.gates();d.admit_all()
    d.resume_after_restart(discovery_evidence_server)
    view=d.view()
    assert view["requests"][0]["submission"]==d.submission
    assert view["requests"][0]["productRefs"]==[]
    assert all(s["status"]=="draft" for s in view["standards"])
    analysis=d.ws.client.request(d.ws.route+"/analysis")[1]
    assert analysis["summary"]["assets"]==2
    assert analysis["summary"]["cryptographicUses"]==4
    assert {f["exposure"] for f in analysis["findings"]}=={"classical_public_key_recorded","mixed_classical_and_hybrid"}
    assert all(f["readiness"]=="evidence_prerequisites_missing" for f in analysis["findings"])
    d.ws.command("submit_package","traffic-termination",{"conclusion":"Two synthetic deployments record separate key-exchange and signature uses. West records hybrid exchange and classical authentication.","qualification":"Configured synthetic records only. Population, business consequence and independent behavior are unestablished."})
    d.ws.command("review_package","traffic-termination",decision_fields(),"reviewer")
    d.ws.gate("PQC-P1-G02")
    p1=d.ws.report("phase1")
    assert p1["content"]["summary"]["observations"]==2
    assert p1["content"]["summary"]["enterpriseCoveragePercent"] is None
    assert len(p1["content"]["findings"])==2
    assert len(p1["content"]["manifest"]["observationRefs"])==2
    html=d.ws.client.request(d.ws.route+"/reports/"+p1["metadata"]["id"]+"/download?format=html")[1]
    assert "Standards proposed for review" in html and "not adopted policy" in html
    assert "Asserted by" in html and "Synthetic portal west" in html
    d.ws.gate("PQC-P1-G03",report=p1["metadata"]["id"])
    d.ws.command("set_method",fields={"name":"Synthetic qualitative scenario review","description":"Interpret role-specific exposure without inventing business impact.","confidenceRules":"Unknowns require qualification.","prioritizationRules":"Investigation order is not a risk-acceptance or remediation decision."},role="risk-lead")
    d.ws.gate("PQC-P2-G01")
    d.ws.command("submit_analysis","traffic-termination",{"scenario":"Classical certificate authentication remains a separate trust dependency even where hybrid key exchange is configured.","businessImpact":"Business consequence and protected-information lifetime require business-owner review; neither has been supplied.","recommendation":"Resolve application dependencies and independently exercise compatibility before migration design.","priority":"planned_review","rationale":"Source-bound synthetic records, not verified enterprise behavior.","confidence":"limited",**unreported_business_context()},"risk-lead")
    recorded=next(p for p in d.ws.state["packages"] if p["familyId"]=="traffic-termination")["analysis"]
    assert all(recorded.get(key) is None for key in unreported_business_context())
    d.ws.command("review_analysis","traffic-termination",decision_fields(),"business-reviewer")
    d.ws.gate("PQC-P2-G02")
    p2=d.ws.report("phase2",p1["metadata"]["id"],"risk-lead")
    assert p2["content"]["manifest"]["selectedPhase1"]["reportId"]==p1["metadata"]["id"]
    assert len(p2["content"]["scenarioRows"][0]["observationRefs"])==2
    assert p2["content"]["scenarioRows"][0]["businessStatementBy"]=="No separate attributed business statement recorded"
    assert p2["content"]["scenarioRows"][0]["scenarioState"]=="qualified"
    assert d.ws.client.request(d.ws.route+"/reports/"+before["metadata"]["id"])[1]==before
    frozen=copy.deepcopy(p2)
    d.command("discovery_update_standard","crypto-agility",{"conflictNote":"A newly reported requirement still needs authority review."})
    assert d.ws.client.request(d.ws.route+"/reports/"+p2["metadata"]["id"])[1]==frozen
    assert d.ws.client.request(d.ws.route+"/reports/"+p1["metadata"]["id"])[1]==p1

def test_evidence_requires_independent_review_and_cannot_use_legacy_admission(discovery_evidence_server):
    d=DiscoveryJourney(discovery_evidence_server).prepare();d.gates()
    d.stage(d.products[0],role="contributor",expected=403)
    result=d.stage(d.products[0],count=2)
    i=result["investigation"];bundle=i["evidenceReviews"][-1]
    assert bundle["observationCount"]==2 and len(bundle["batchIds"])==2
    assert d.ws.client.request(d.ws.route+"/assets")[1]["total"]==0
    d.command("discovery_admit_evidence",d.investigation,{"batchId":bundle["batchId"]},expected=409)
    d.command("discovery_review_evidence",d.investigation,{"batchId":bundle["batchId"],"determination":"qualified","rationale":"Not an independent actor."},expected=403)
    status,_,_=d.ws.client.request(d.ws.route+"/intake/commands",method="POST",body={"operation":"intake_admit_evidence","targetId":i["intakeRequestId"],"fields":{"batchId":bundle["batchIds"][0]},"expectedRevision":d.view()["revision"]},headers={"Idempotency-Key":uuid4().hex})
    assert status==409
    d.command("discovery_review_evidence",d.investigation,{"batchId":bundle["batchId"],"determination":"qualified","rationale":"Native records remain distinct endpoints, not duplicate products."},"reviewer")
    d.command("discovery_admit_evidence",d.investigation,{"batchId":bundle["batchId"]})
    assets=d.ws.client.request(d.ws.route+"/assets")[1]
    assert assets["total"]==2 and len({a["id"] for a in assets["items"]})==2
    assert d.ws.actor("contributor").request(d.ws.route+"/reports")[0]==403
    d.stage(d.products[0],count=2,expected=409)

def test_blank_request_is_not_report_progress_and_proposal_only_work_is_rendered(discovery_evidence_server):
    d=DiscoveryJourney(discovery_evidence_server)
    before=d.ws.report("phase1")
    d.command("discovery_create",fields={"title":"Fresh assignment, not evidence","familyId":"traffic-termination","assignedTo":"synthetic-demo:contributor"})
    after=d.ws.report("phase1")
    assert before["metadata"]["inputFingerprint"]==after["metadata"]["inputFingerprint"]
    assert after["content"]["discovery"]["responses"]==[]
    d.command("discovery_update_standard","assessment-evidence",{"observedPractice":"No existing requirement has yet been identified; policy absence is not established.","conflictNote":"Proposal-only review: identify the appropriate company authority."})
    changed=d.ws.report("phase1")
    assert changed["metadata"]["inputFingerprint"]!=before["metadata"]["inputFingerprint"]
    html=d.ws.client.request(d.ws.route+"/reports/"+changed["metadata"]["id"]+"/download?format=html")[1]
    assert "Proposal-only review" in html and "NIST SP 800-30" in html
    assert "No existing requirement has yet been identified" in html
    assert changed["content"]["summary"]["observations"]==0
