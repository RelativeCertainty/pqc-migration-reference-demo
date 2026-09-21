"""Actual bounded source parser -> projection -> report contract checks.

Runs only against an explicitly supplied prebuilt candidate and newly generated
synthetic state. It never invokes vendor APIs or qualifies real products.
"""
from __future__ import annotations

import copy
import json
import os
from urllib.parse import urlencode
from uuid import uuid4

import pytest

from tests.test_pqc_enterprise_demo_http import fixture_input, scope_fields
from tests.test_pqc_intake_http import raw_request
from tests.test_pqc_workspace_http import Work, FIXTURES, work_server
from tests.test_pqc_assessment_report_contract import assert_report_content, assert_safe_report_html

pytestmark=pytest.mark.skipif(not os.environ.get("PQC_ENTERPRISE_DEMO_DLL"),reason="explicit built candidate required; no implicit build")


def stage_bytes(work,product_id,data):
    query=urlencode({"productId":product_id,"expectedRevision":work.ws.refresh()["revision"]})
    return raw_request(work.ws.client,work.ws.route+"/work/"+work.request+"/evidence?"+query,
        method="POST",data=data,content_type="application/json",headers={"Idempotency-Key":uuid4().hex})


def test_closed_source_schema_refuses_false_family_time_basis_and_shape(work_server):
    work=Work(work_server)
    source=json.loads((FIXTURES/"tls-configured.json").read_text())
    invalid=[]
    for field,value in (("synthetic",False),("familyId","cmdb"),("kind","ssh"),("collectedAt","2026-09-14"),("collectedAt","2026-09-14T12:00:00"),("collectedAt","2026-09-12T12:00:00Z")):
        changed=copy.deepcopy(source);changed[field]=value;invalid.append(json.dumps(changed).encode())
    for field,value in (("sourceUpdatedAt","not a date"),("sourceUpdatedAt","2026-02-30T12:00:00Z"),("sourceUpdatedAt","2026-09-15T12:00:00Z"),("basis","enterprise_verified"),("hostname","example.com")):
        changed=copy.deepcopy(source);changed["records"][0][field]=value;invalid.append(json.dumps(changed).encode())
    changed=copy.deepcopy(source);changed["undeclared"]=True;invalid.append(json.dumps(changed).encode())
    changed=copy.deepcopy(source);changed["records"].append(copy.deepcopy(changed["records"][0]));invalid.append(json.dumps(changed).encode())
    invalid.append(json.dumps(source).replace('"synthetic": true','"synthetic": true, "synthetic": true',1).encode())
    before=work.ws.refresh()["revision"]
    for index,data in enumerate(invalid):
        if index==8:work.checkpoint()
        status,result,_=stage_bytes(work,"not-used-invalid-source-is-rejected-first",data)
        assert status==400,result
        assert "workspace_synthetic_source_invalid" in json.dumps(result)
        assert work.ws.refresh()["revision"]==before
    assert work.case()["technicalRecords"]==[]


def reviewed_admission(work,product,filename,determination="supports_claim",payload=None):
    if payload is None:result=work.stage(product,filename)
    else:
        status,result,_=stage_bytes(work,product["id"],json.dumps(payload).encode())
        assert status==200,result
    bundle=result["case"]["technicalRecords"][-1]
    decisions=[{"observationId":row["id"],"determination":determination,"rationale":"Retain synthetic source basis and reference identities; no enterprise verification."} for row in bundle["observations"]]
    work.command("workspace_review_evidence",bundle["id"],{"determination":"qualified","rationale":"Bounded synthetic source fields reviewed.","recordDecisions":decisions},role="reviewer")
    work.command("workspace_admit_evidence",bundle["id"])
    work.checkpoint()
    return bundle


def test_native_references_start_as_limits_then_link_only_admitted_same_deployment_sources(work_server):
    work=Work(work_server,"response_to_report_example")
    included=["cmdb","certificate-lifecycle","traffic-termination"]
    scope=scope_fields(work.ws)
    scope.update(includedFamilyIds=included,depthByFamily={family:"inventory" for family in included},
        excludedReasons={s["familyId"]:"Outside the synthetic dependency cohort" for s in work.ws.state["sources"] if s["familyId"] not in included})
    work.ws.command("update_scope",fields=scope)
    receipt=work.receive()["receipt"];work.apply(receipt)
    product=receipt["products"][0];work.identify(product)
    work.ws.gate("PQC-G00")
    for family in ("cmdb","certificate-lifecycle"):
        work.ws.command("source_response",family,{"state":"unknown","systemOfRecord":"Closed synthetic reference fixtures","product":"Recognition example only",
            "ownerFunction":"Synthetic source coordination","accessRoute":"Synthetic files only; no enterprise route",
            "note":"Source population and enterprise access remain unestablished; bounded synthetic records may be examined in this test. Review date is a synthetic test fixture, not an enterprise commitment.","dueAt":"2026-09-22","assertedBy":"Synthetic test coordinator"})
    work.ws.gate("PQC-P1-G01");work.checkpoint()
    reviewed_admission(work,product,"tls-configured.json")
    analysis=work.ws.client.request(work.ws.route+"/analysis")[1]
    assert analysis["summary"]["assets"]==1
    endpoint=analysis["assets"][0]
    detail=work.ws.client.request(work.ws.route+"/assets/"+endpoint["id"])[1]
    fact=detail["observations"][0]["facts"]
    assert fact["native_application_id"]=="portal-app-001"
    assert fact["native_certificate_id"]=="portal-cert-001"
    assert fact["application_ref_status"]=="unresolved_reference"
    assert "application_ref" not in fact and "certificate_ref" not in fact
    assert "missing_relationship" in {row["code"] for row in detail["limitations"]}
    assert detail["dependencies"]==[]

    context=json.loads((FIXTURES/"context.json").read_text())
    # A vendor-native source identifier reused by another source class must
    # not make CMDB and TLS observations share coverage membership.
    context["sourceInstanceId"]="synthetic-tls-config"
    context["records"][0]["name"]="Synthetic portal <script>not executable</script>"
    reviewed_admission(work,product,"context.json",payload=context)
    reviewed_admission(work,product,"certificate.json")
    analysis=work.ws.client.request(work.ws.route+"/analysis")[1]
    assert analysis["summary"]["assets"]==3
    assert analysis["summary"]["observations"]==3
    assert analysis["summary"]["cryptographicUses"]==3
    assert sorted(a["familyIds"] for a in analysis["assets"])==[["certificate-lifecycle"],["cmdb"],["traffic-termination"]]
    endpoint=next(a for a in analysis["assets"] if "traffic-termination" in a["familyIds"])
    assert endpoint["ownerIds"]==["Synthetic application team"]
    assert endpoint["serviceIds"]==["portal-service-001"]
    detail=work.ws.client.request(work.ws.route+"/assets/"+endpoint["id"])[1]
    fact=detail["observations"][0]["facts"]
    assert fact["application_ref_status"]=="resolved_within_reviewed_deployment"
    assert fact["certificate_ref_status"]=="resolved_within_reviewed_deployment"
    assert len(detail["dependencies"])==2
    assert "missing_relationship" not in {row["code"] for row in detail["limitations"]}
    assert {u["purpose"] for u in detail["cryptographicUses"]}=={"key_establishment","authentication"}
    assert all(u["independently_verified"] is False for u in detail["cryptographicUses"])

    reviewed_admission(work,product,"tls-observed.json","conflict")
    analysis=work.ws.client.request(work.ws.route+"/analysis")[1]
    finding=next(f for f in analysis["findings"] if f["subjectId"]==endpoint["id"])
    assert finding["exposure"]=="conflicting_cryptographic_evidence"
    assert finding["readiness"]=="evidence_prerequisites_missing"
    assert "conflicting_observations" in finding["limitationCodes"]
    report=work.ws.report("phase1")
    assert_report_content(report["content"],phase="phase1")
    assert report["content"]["summary"]["subjects"]==3
    assert report["content"]["summary"]["observations"]==4
    assert report["content"]["workspace"]["enterpriseCoveragePercent"] is None
    assert "1 of 1 reported" in report["content"]["workspace"]["populationStatement"]
    assert len(report["content"]["manifest"]["workspaceEvidenceRefs"])==4
    html=work.ws.client.request(work.ws.route+"/reports/"+report["metadata"]["id"]+"/download?format=html")[1]
    assert_safe_report_html(html)
    assert "&lt;script&gt;not executable&lt;/script&gt;" in html
    assert "X25519MLKEM768" in html and "ecdsa-with-SHA256" in html
    assert "Missing documentation is not proof that no policy exists" in html
    assert "no the example enterprise estate facts" in html
    assert "No new reviewed conclusion has been recorded" in html
