"""Actual HTTP checks of separate business input and Phase 1 lineage."""
from __future__ import annotations

import os
from uuid import uuid4

import pytest

from tests.test_pqc_enterprise_demo_http import decision_fields, fixture_input, unreported_business_context
from tests.test_pqc_workspace_http import Work, work_server, conclusion

pytestmark = pytest.mark.skipif(not os.environ.get("PQC_ENTERPRISE_DEMO_DLL"), reason="explicit prebuilt candidate required")


@pytest.mark.parametrize("invalid", ["legacy_shape", "forged_review", "unattributed_statement"])
def test_analysis_rejects_invalid_contract_without_recording_a_decision(work_server, invalid):
    work = Work(work_server, "response_to_report_example")
    fields = {"scenario": "Synthetic scoped scenario", "businessImpact": "Not yet established.",
        "recommendation": "Request business context", "priority": "planned_review",
        "rationale": "Missing business information remains a limitation.", "confidence": "limited",
        **unreported_business_context()}
    expected_code = "assessment_fields_invalid"
    if invalid == "legacy_shape":
        for key in unreported_business_context():
            fields.pop(key)
    elif invalid == "forged_review":
        fields["reviewedBy"] = "synthetic-demo:business-reviewer"
    else:
        fields["protectedInformation"] = "Synthetic correspondence"
        expected_code = "business_statement_attribution_required"
    before = work.ws.refresh()
    status, result, _ = work.ws.actor("risk-lead").request(work.ws.route + "/commands", method="POST",
        body=work.ws.payload("submit_analysis", "traffic-termination", fields),
        headers={"Idempotency-Key": uuid4().hex})
    assert status == 400 and result["error"]["code"] == expected_code
    after = work.ws.refresh()
    assert after["revision"] == before["revision"]
    assert after["packages"] == before["packages"]
    assert after["events"] == before["events"]


def test_business_only_consequence_revision_does_not_rewrite_phase1_handoff(work_server):
    work=Work(work_server,"response_to_report_example")
    receipt=work.receive()["receipt"]; work.apply(receipt)
    product=receipt["products"][0]; work.identify(product)
    work.ws.gate("PQC-G00"); work.ws.gate("PQC-P1-G01")
    fields=conclusion(product["id"])
    preview=work.preview(fields)
    work.command("record_consequence",fields={**fields,"previewFingerprint":preview["previewFingerprint"]})
    work.ws.command("submit_package","traffic-termination",{"conclusion":fields["phase1Conclusion"],"qualification":fields["limitation"]})
    work.ws.command("review_package","traffic-termination",decision_fields(),"reviewer")
    work.ws.gate("PQC-P1-G02")
    report=work.ws.report("phase1")
    work.ws.gate("PQC-P1-G03",report=report["metadata"]["id"])
    before=work.ws.refresh()["workspace"]
    changed={**fields,"phase2Consequence":"Attributed synthetic portal disruption consequence for review.","lifetime":"Seven years, attributed synthetic information-owner statement."}
    preview=work.preview(changed)
    work.command("record_consequence",fields={**changed,"previewFingerprint":preview["previewFingerprint"]})
    state=work.ws.refresh()
    assert state["workspace"]["materialFingerprint"]!=before["materialFingerprint"]
    assert state["workspace"]["phase1MaterialFingerprint"]==before["phase1MaterialFingerprint"]
    assert next(g for g in state["gates"] if g["id"]=="PQC-P1-G03")["state"]=="qualified"
    assert state["phase1InputReportId"]==report["metadata"]["id"]
    assert work.ws.client.request(work.ws.route+"/reports/"+report["metadata"]["id"])[1]==report
    work.checkpoint()
    phase1change={**changed,"phase1Conclusion":"Revised technical current-state conclusion changes the basis."}
    preview=work.preview(phase1change)
    work.command("record_consequence",fields={**phase1change,"previewFingerprint":preview["previewFingerprint"]})
    assert next(g for g in work.ws.refresh()["gates"] if g["id"]=="PQC-P1-G03")["state"]=="needs_review"


def test_rich_business_analysis_requires_attribution_not_forged_review(work_server):
    work=Work(work_server,"response_to_report_example")
    fields=dict(scenario="Synthetic scoped scenario",businessImpact="Synthetic consequence",recommendation="Investigate the selected cohort",priority="planned_review",
        rationale="Recorded uncertainty and dependencies",confidence="limited",protectedInformation="Synthetic correspondence",lifetime="Seven years",
        compatibilityConstraints="Legacy verifier cohort",vendorConstraints="Exact version unqualified",operationalConstraints="Recovery prerequisites",
        responsibleFunction="Synthetic service owner",nextDecision="Confirm the business context")
    work.ws.refresh()
    def submit(value):
        return work.ws.actor("risk-lead").request(work.ws.route+"/commands",method="POST",body=work.ws.payload("submit_analysis","traffic-termination",value),headers={"Idempotency-Key":uuid4().hex})
    assert submit(fields)[0]==400
    fields.update(assertedBy="Synthetic information owner",statementDate="2026-09-16")
    assert submit({**fields,"reviewedBy":"synthetic-demo:business-reviewer"})[0]==400
    status,state,_=submit(fields)
    assert status==200,state
    analysis=next(p for p in state["packages"] if p["familyId"]=="traffic-termination")["analysis"]
    assert analysis["protectedInformation"]=="Synthetic correspondence"
    assert analysis["lifetime"]=="Seven years" and analysis["assertedBy"]=="Synthetic information owner"
    assert analysis["reviewedBy"]=="" and analysis["state"]=="submitted"
    assert analysis["submittedBy"]=="synthetic-demo:risk-lead"


def test_phase2_executive_uses_reviewed_business_consequences_not_phase1_counts(work_server):
    work = Work(work_server, "response_to_report_example")
    receipt = work.receive()["receipt"]
    work.apply(receipt)
    product = receipt["products"][0]
    work.identify(product)
    work.ws.gate("PQC-G00")
    work.ws.gate("PQC-P1-G01")
    fields = conclusion(product["id"], phase1Conclusion="Selected configuration requires corroboration.")
    preview = work.preview(fields)
    work.command("record_consequence", fields={**fields, "previewFingerprint": preview["previewFingerprint"]})
    work.ws.command("submit_package", "traffic-termination", {"conclusion": fields["phase1Conclusion"], "qualification": fields["limitation"]})
    work.ws.command("review_package", "traffic-termination", decision_fields(), "reviewer")
    work.ws.gate("PQC-P1-G02")
    phase1 = work.ws.report("phase1")
    work.ws.gate("PQC-P1-G03", report=phase1["metadata"]["id"])
    work.ws.command("set_method", fields={"name": "Bounded test method", "description": "Conditional consequences and supported decisions",
        "confidenceRules": "Retain material unknowns", "prioritizationRules": "Use recorded attention priority, not numerical risk scores"}, role="risk-lead")
    work.ws.gate("PQC-P2-G01")
    analysis = {"scenario": "Retained correspondence could outlive transport protection.", "businessImpact": "Synthetic portal disruption could prevent client correspondence.",
        "recommendation": "Reconcile the ingress configuration and observed client cohort.", "priority": "prioritize_review", "rationale": "Long-lived information and an unresolved peer dependency.",
        "confidence": "limited", "protectedInformation": "Fictional correspondence", "lifetime": "Seven years after creation",
        "assertedBy": "Synthetic information owner", "statementDate": "2026-09-16", "responsibleFunction": "Synthetic portal owner",
        "compatibilityConstraints": "The selected legacy client cohort needs independent compatibility review.",
        "vendorConstraints": "Exact product version and provider support remain unqualified.",
        "operationalConstraints": "A separate bounded verification and recovery plan is required.",
        "nextDecision": "Confirm the permitted compatibility investigation."}
    work.ws.command("submit_analysis", "traffic-termination", analysis, role="risk-lead")
    draft = work.ws.report("phase2", phase1["metadata"]["id"], role="risk-lead")
    draft_summary = " ".join(item["body"] for item in draft["content"]["narrative"]["executiveSummary"])
    assert "No designated business review" in draft_summary
    assert analysis["businessImpact"] not in draft_summary
    work.ws.command("review_analysis", "traffic-termination", decision_fields(), role="business-reviewer")
    # Continue from persisted state in a new process, as the longer HTTP suites
    # do between role-intensive batches; keep the application rate limit intact.
    work.checkpoint()
    work.ws.gate("PQC-P2-G02")
    phase2 = work.ws.report("phase2", phase1["metadata"]["id"], role="risk-lead")
    summary = " ".join(item["body"] for item in phase2["content"]["narrative"]["executiveSummary"])
    for field in ("businessImpact", "lifetime", "recommendation", "responsibleFunction", "nextDecision", "rationale"):
        assert analysis[field] in summary, field
    assert "Conditional business consequence" in summary
    assert "not numerical risk ratings" in summary
    assert "prioritize review: 1" in summary
    assert "opening highlights 1 of 1 reviewed domains" in summary
    html = work.ws.client.request(work.ws.route + "/reports/" + phase2["metadata"]["id"] + "/download?format=html")[1]
    executive = html.split('id="scope"')[0]
    assert analysis["businessImpact"] in executive and analysis["nextDecision"] in executive
    assert phase2["content"]["manifest"]["selectedPhase1"]["reportId"] == phase1["metadata"]["id"]
    assert work.ws.client.request(work.ws.route + "/reports/" + phase1["metadata"]["id"])[1] == phase1
