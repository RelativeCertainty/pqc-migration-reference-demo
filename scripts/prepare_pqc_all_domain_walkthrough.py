#!/usr/bin/env python3
"""API rehearsal of all-domain synthetic records; NOT browser/video evidence.

Uses a newly created isolated state, authenticates the declared simulated roles,
stages and independently reviews each registered source bundle, and exercises
all seven gates including final Phase 2 disposition. Does not precomplete an
operator's existing assessment or record a founder-owner observation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlencode
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.build_pqc_enterprise_demo_fixture import prepare
from scripts.build_pqc_all_domain_walkthrough import workspace_purpose
from tests.test_pqc_enterprise_demo_http import Client, Server, Workspace, decision_fields, scope_fields
from tests.test_pqc_intake_http import raw_request
from tests.test_pqc_assessment_report_contract import assert_report_content, assert_safe_report_html

MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def write_json(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2)
        handle.write("\n")


def run(output: Path, inputs: Path, dll: Path):
    os.umask(0o077)
    output = output.absolute(); inputs = inputs.absolute()
    if not output.is_relative_to(ROOT / "artifacts/pqc-enterprise-demo") or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError("isolated_output_required")
    if output.exists():
        raise ValueError("fresh_output_required")
    scenario = json.loads((inputs / "scenario.json").read_text())
    assert scenario["synthetic"] and len(scenario["cases"]) == 27
    output.mkdir(mode=0o700, parents=True)
    prepare(output / "input", applications=12, as_of=scenario["asOf"])
    os.environ["PQC_SYNTHETIC_BUNDLE_REGISTRY_FILE"] = str(inputs / "bundle-registry.json")
    server = Server(output, output / "input/synthetic-input.json", dll=dll)
    reports = output / "reports"; reports.mkdir(mode=0o700)
    actions = []; cases = {}
    try:
        server.start()
        ws = Workspace(Client(server.origin).login(), "response_to_report_example", "Northstar Services · complete fictional assessment · API rehearsal")
        included = [case["familyId"] for case in scenario["cases"]]
        scope = scope_fields(ws)
        scope.update(objective="Develop a defensible fictional current-state assessment and actionable Phase 2 report across ten discovery domains.",
            cycleGoal="Review one selected source-class cohort per family; retain conflicts, stale information and blocked ingress explicitly.",
            handling="Synthetic Northstar Services fixtures only; no sensitive uploads, external sources, tickets, enterprise decisions or migration authority.",
            includedFamilyIds=included, depthByFamily={f: "inventory" for f in included}, excludedReasons={})
        ws.command("update_scope", fields=scope)

        def checkpoint(label):
            actions.append(dict(checkpoint=label, revision=ws.refresh()["revision"]))
            server.stop(); server.start()
            ws.client = Client(server.origin).login(); ws.clients = {"analyst": ws.client}; ws.refresh()
            print(json.dumps({"checkpoint": label, "revision": ws.state["revision"]}), flush=True)

        def command(operation, request, fields=None, role="analyst"):
            ws.refresh()
            status, result, _ = ws.actor(role).request(ws.route + "/work/commands", method="POST",
                body=ws.payload(operation, request, fields), headers={"Idempotency-Key": uuid4().hex})
            assert status == 200, (operation, status, result)
            return result

        def case_view(request):
            status, result, _ = ws.client.request(ws.route + "/work/" + request)
            assert status == 200, result
            return result

        def receive(request, path):
            query = urlencode({"requestId": request, "expectedRevision": ws.refresh()["revision"], "filename": path.name})
            status, result, _ = raw_request(ws.client, ws.route + "/receipts?" + query, method="POST", data=path.read_bytes(), content_type=MIME,
                headers={"Idempotency-Key": uuid4().hex})
            assert status == 200, result
            return result

        for index, item in enumerate(scenario["cases"]):
            ws.refresh()
            status, created, _ = ws.client.request(ws.route + "/discovery/commands", method="POST",
                body=ws.payload("discovery_create", fields={"title": "Review synthetic " + item["name"], "familyId": item["familyId"], "assignedTo": "synthetic-demo:contributor"}),
                headers={"Idempotency-Key": uuid4().hex})
            assert status == 200, created
            request = created["requests"][-1]["id"]
            result = receive(request, inputs / item["formPath"])
            receipt = result["receipt"]
            command("receipt_apply", receipt["id"], {"choices": {}, "note": "Scenario-generated receipt, unverified respondent attribution; no technical approval."})
            canonical = {}; products = {}
            def reconcile(products_to_link):
                for product in products_to_link:
                    label = product["deployment"]
                    result = command("reconcile_product", request, {"productId": product["id"], "decision": "same_system" if label in canonical else "distinct",
                        "canonicalId": canonical.get(label, ""), "label": label, "applicationService": product["applicationService"], "team": product["team"],
                        "rationale": "Scenario-generated explicit identity review. Source records and reported assertions remain distinct; duplicate references are retained."})
                    identity = next(i for i in result["case"]["identityDecisions"] if i["productId"] == product["id"])
                    canonical[label] = identity["canonicalId"]
                    products.setdefault(label, product)
            reconcile(receipt["products"])
            if item["familyId"] == "traffic-termination":
                duplicate = receive(request, inputs / "forms/area-03/traffic-termination-synthetic-duplicate.xlsx")
                assert duplicate["duplicate"] is True and duplicate["receipt"]["id"] == receipt["id"]
                revised = receive(request, inputs / "forms/area-03/traffic-termination-synthetic-revised.xlsx")["receipt"]
                assert any(c["state"] == "conflict" for c in revised["comparison"])
                command("receipt_apply", revised["id"], {"choices": {c["questionId"]: "current" for c in revised["comparison"]},
                    "note": "Keep current testimony pending clarification; the revised response and competing values stay visible."})
                reconcile(revised["products"])
            cases[item["familyId"]] = dict(requestId=request, products=products)
            if index % 3 == 2:
                checkpoint("received and reconciled " + str(index + 1) + " families")

        ws.gate("PQC-G00")
        for index, item in enumerate(scenario["cases"]):
            ws.command("source_response", item["familyId"], dict(state="route_confirmed", systemOfRecord="Registered closed synthetic " + item["name"],
                product="Recognition examples only; no installed-product or API qualification", ownerFunction=item["analysis"]["responsibleFunction"],
                accessRoute="Owner-controlled fictional files; no enterprise or provider connection", note=item["limitation"], dueAt="2026-09-22", assertedBy="Scenario-generated source coordinator"))
            if index % 8 == 7:
                checkpoint("source route register " + str(index + 1))
        ws.gate("PQC-P1-G01"); checkpoint("governance and source gate qualified")
        bundle_count = 0
        for index, item in enumerate(scenario["cases"]):
            request = cases[item["familyId"]]["requestId"]
            for source in item["bundles"]:
                product = cases[item["familyId"]]["products"][source["deployment"]]
                query = urlencode({"productId": product["id"], "expectedRevision": ws.refresh()["revision"]})
                status, staged, _ = raw_request(ws.client, ws.route + "/work/" + request + "/evidence?" + query, method="POST",
                    data=(inputs / source["path"]).read_bytes(), content_type="application/json", headers={"Idempotency-Key": uuid4().hex})
                assert status == 200, (item["familyId"], status, staged)
                bundle = next(b for b in staged["case"]["technicalRecords"] if b["status"] == "staged")
                command("workspace_review_evidence", bundle["id"], dict(determination="qualified", rationale="Independent simulated reviewer examined raw-source provenance, dates and normalized fields; not enterprise verification.",
                    recordDecisions=[dict(observationId=o["id"], determination=source["technicalDetermination"], rationale="Retain configured-versus-observed contradiction and temporal scope." if source["technicalDetermination"] == "conflict" else "Supports supplied fields and their stated evidence basis only; no complete population, product qualification or approved business lifetime.") for o in bundle["observations"]]), "reviewer")
                command("workspace_admit_evidence", bundle["id"])
                bundle_count += 1
            view = case_view(request)
            observations = [o for b in view["technicalRecords"] if b["status"] == "admitted" for o in b["observations"]]
            contradicting = [o["id"] for o in observations if o["technicalDetermination"] == "conflict" and o["basis"] == "observed"]
            fields = dict(productId="", cryptographicPurpose=workspace_purpose(item["technicalBasis"]["uses"]),
                phase1Conclusion=item["phase1Conclusion"], limitation=item["limitation"], nextDecision=item["analysis"]["nextDecision"], responsibleFunction=item["analysis"]["responsibleFunction"],
                phase2Consequence=item["analysis"]["businessImpact"], lifetime=item["analysis"]["lifetime"], confidence="limited",
                supportingObservationIds=[o["id"] for o in observations if o["id"] not in contradicting], contradictingObservationIds=contradicting)
            ws.refresh()
            status, preview, _ = ws.client.request(ws.route + "/report-impact/preview", method="POST", body=ws.payload("record_consequence", request, fields))
            assert status == 200, preview
            command("record_consequence", request, {**fields, "previewFingerprint": preview["previewFingerprint"]})
            ws.command("submit_package", item["familyId"], {"conclusion": item["phase1Conclusion"], "qualification": item["limitation"]})
            ws.command("review_package", item["familyId"], decision_fields(), "reviewer")
            if index % 2 == 1:
                checkpoint("reviewed admitted and interpreted " + str(index + 1) + " families")
        ws.gate("PQC-P1-G02")
        p1 = ws.report("phase1")
        assert_report_content(p1["content"], phase="phase1")
        ws.gate("PQC-P1-G03", report=p1["metadata"]["id"])
        checkpoint("Phase 1 exact report qualified")
        ws.command("set_method", fields=dict(name="Fictional use-level scenario analysis v1", description="Separate technical evidence, attributed business consequences, uncertainty and migration readiness; report all ten domains without claiming a complete enterprise population.",
            confidenceRules="Qualified when evidence is limited, stale, contradictory or incomplete; missing records never imply low exposure.", prioritizationRules="Prioritize assessment review for long-lived information, critical trust/dependencies or consequential unknowns; otherwise plan review. No numerical risk scale, loss forecast or quantum arrival date."), role="risk-lead")
        ws.gate("PQC-P2-G01")
        for index, item in enumerate(scenario["cases"]):
            ws.command("submit_analysis", item["familyId"], item["analysis"], "risk-lead")
            ws.command("review_analysis", item["familyId"], {**decision_fields(), "rationale": "Simulated business reviewer evaluated the attributed fictional statement, confidentiality/trust lifetime and distinct recommendation; no enterprise risk acceptance."}, "business-reviewer")
            if index % 6 == 5:
                checkpoint("business review " + str(index + 1) + " source classes")
        ws.gate("PQC-P2-G02")
        p2 = ws.report("phase2", p1["metadata"]["id"], "risk-lead")
        assert_report_content(p2["content"], phase="phase2")
        assert len({row["areaId"] for row in p2["content"]["scenarioRows"]}) == 10
        assert len(p2["content"]["scenarioRows"]) == 27
        assert all(row["businessStatementBy"] and row["businessStatementDate"] == "2026-09-16" for row in p2["content"]["scenarioRows"])
        ws.gate("PQC-P2-G03", report=p2["metadata"]["id"])
        assert all(g["state"] == "qualified" for g in ws.refresh()["gates"])
        assert all(e["origin"] == "scenario_generated" for e in ws.state["events"])
        for name, report in (("Phase_1_Current_State", p1), ("Phase_2_Risk_and_Recommendations", p2)):
            status, html, _ = ws.client.request(ws.route + "/reports/" + report["metadata"]["id"] + "/download?format=html")
            assert status == 200; assert_safe_report_html(html)
            (reports / (name + ".html")).write_text(html)
            write_json(reports / (name + ".json"), report)
        result = dict(schemaVersion="pqc.complete-walkthrough.api-proof.v1", status="passed", evidenceType="api_rehearsal_not_browser_or_video", synthetic=True,
            assessmentId=ws.state["id"], reportIds=[p1["metadata"]["id"], p2["metadata"]["id"]], selectedPhase1=p2["content"]["manifest"]["selectedPhase1"],
            cases=cases, domains=10, primaryFormsReceived=27, registeredBundlesReviewed=bundle_count, allSevenGates="qualified_simulated_only", duplicateReturnDetected=True,
            competingEditPreserved=True, actions=actions, ownerObservation=None, enterpriseAcceptance=False, externalConnections=0)
        result["buildIdentity"] = {"dllSha256":hashlib.sha256(dll.read_bytes()).hexdigest(),
            "scenarioSha256":hashlib.sha256((inputs/"scenario.json").read_bytes()).hexdigest(),
            "fixtureSha256":hashlib.sha256((output/"input/synthetic-input.json").read_bytes()).hexdigest(),
            "reports":[dict(name=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in sorted(reports.iterdir())]}
        result["purposeCategories"] = [dict(familyId=item["familyId"],sourcePurposes=item["cryptographicPurpose"],workspaceCategory=workspace_purpose(item["technicalBasis"]["uses"])) for item in scenario["cases"]]
        result["purposeCategoryLimit"] = "Each case has one coarse workspace category derived from the primary source use. Generic signing/custody operations without a compatible category remain context; all individual cryptographic purposes remain in source facts and report scenarios. The example does not create a separate conclusion for every use."
        write_json(output / "worked-example.json", result)
        checkpoint("final deliverable gates qualified and immutable reports read back")
        fresh = Workspace(Client(server.origin).login(), "response_to_report_example", "Northstar Services · your fresh synthetic walkthrough")
        fresh.command("update_scope", fields=scope)
        fresh.refresh()
        status, created, _ = fresh.client.request(fresh.route+"/discovery/commands", method="POST",
            body=fresh.payload("discovery_create",fields={"title":"Receive the synthetic traffic-termination form","familyId":"traffic-termination","assignedTo":"synthetic-demo:contributor"}),
            headers={"Idempotency-Key":uuid4().hex})
        assert status==200,created
        fresh_request=created["requests"][-1]["id"]
        fresh.refresh()
        assert all(g["state"]=="not_submitted" for g in fresh.state["gates"])
        write_json(output/"fresh-walkthrough.json",dict(assessmentId=fresh.state["id"],requestId=fresh_request,synthetic=True,
            gateDecisionsRecorded=False, technicalEvidenceAdmitted=False, responseReceived=False, expectedAction="Record the synthetic traffic-termination operational return; all approvals and technical review are still outstanding."))
        print(json.dumps({"status": "passed", "assessmentId": ws.state["id"], "reports": 2, "families": 27, "domains": 10, "bundles": bundle_count}))
        return result
    finally:
        server.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--dll", type=Path, required=True)
    args = parser.parse_args()
    run(args.output, args.inputs, args.dll)
