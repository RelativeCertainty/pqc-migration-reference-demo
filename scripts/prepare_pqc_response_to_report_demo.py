#!/usr/bin/env python3
"""Prepare a bounded synthetic response-to-report candidate through its public API.

Build/acquisition are separate. Refuses existing state and writes only under the
isolated demo artifact root. Uses simulated personas, never owner outcomes.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlencode
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.build_pqc_enterprise_demo_fixture import prepare
from tests.test_pqc_enterprise_demo_http import Client, Server, Workspace, decision_fields, scope_fields
from tests.test_pqc_intake_http import raw_request

FAMILIES = ["traffic-termination", "cmdb", "certificate-lifecycle"]
FILES = ROOT / "tests/fixtures/pqc-operational-return-v1/synthetic-scenario"
MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def prepare_demo(output: Path, dll: Path):
    os.umask(0o077)
    output = output.absolute()
    if not output.is_relative_to(ROOT / "artifacts/pqc-enterprise-demo") or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError("isolated_output_required")
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    if (output / "app-state").exists():
        raise ValueError("fresh_state_required")
    prepare(output / "input", applications=12)
    fixture = output / "input/synthetic-input.json"
    server = Server(output, fixture, dll=dll)
    reports = output / "reports"
    reports.mkdir(mode=0o700)
    try:
        server.start()
        ws = Workspace(Client(server.origin).login(), "response_to_report_example", name="Worked example · returned forms to qualified reports")
        scope = scope_fields(ws)
        scope.update(objective="Explain what the synthetic portal cohort records support, what conflicts and what remains unknown.",
            includedFamilyIds=FAMILIES, depthByFamily={f: "inventory" for f in FAMILIES},
            excludedReasons={s["familyId"]: "Outside this selected synthetic cohort, not an enterprise exclusion." for s in ws.state["sources"] if s["familyId"] not in FAMILIES})
        ws.command("update_scope", fields=scope)

        def discovery(operation, target=None, fields=None):
            ws.refresh()
            status, result, _ = ws.client.request(ws.route + "/discovery/commands", method="POST",
                body=ws.payload(operation, target, fields), headers={"Idempotency-Key": uuid4().hex})
            assert status == 200, (operation, status, result)
            return result

        discovery("discovery_create", fields={"title": "Review the synthetic traffic-termination return", "familyId": "traffic-termination", "assignedTo": "synthetic-demo:contributor"})
        request = ws.client.request(ws.route + "/discovery")[1]["requests"][-1]["id"]

        def case():
            status, result, _ = ws.client.request(ws.route + "/work/" + request)
            assert status == 200, result
            return result

        def command(operation, target, fields=None, role="analyst"):
            ws.refresh()
            status, result, _ = ws.actor(role).request(ws.route + "/work/commands", method="POST",
                body=ws.payload(operation, target, fields), headers={"Idempotency-Key": uuid4().hex})
            assert status == 200, (operation, status, result)
            return result

        def receive(path):
            ws.refresh()
            query = urlencode({"requestId": request, "expectedRevision": ws.state["revision"], "filename": path.name})
            status, result, _ = raw_request(ws.client, ws.route + "/receipts?" + query, method="POST", data=path.read_bytes(), content_type=MIME, headers={"Idempotency-Key": uuid4().hex})
            assert status == 200, result
            return result

        returns = sorted(FILES.glob("*.xlsx"))
        original = next(p for p in returns if "initial" in p.name)
        revised = next(p for p in returns if "revised" in p.name)
        first = receive(original)
        duplicate = receive(original)
        assert duplicate["duplicate"] is True
        command("receipt_apply", first["receipt"]["id"], {"choices": {}, "note": "Scenario-generated coordinator receipt. No authenticated respondent signature or technical acceptance."})
        canonical = {}

        def reconcile_all():
            for receipt in case()["receipts"]:
                if receipt["status"] != "applied":
                    continue
                existing = {i["productId"] for i in case()["identityDecisions"]}
                for product in receipt["products"]:
                    if product["id"] in existing:
                        continue
                    label = product["deployment"]
                    # Fixture aliases are scenario facts explicitly reviewed by this command.
                    normalized = "gateway-east" if "east" in label.lower() else "gateway-west" if "west" in label.lower() else "partner-edge"
                    fields = {"productId": product["id"], "decision": "same_system" if normalized in canonical else "distinct",
                        "canonicalId": canonical.get(normalized, ""), "label": normalized, "applicationService": "Synthetic portal application / portal service",
                        "team": product.get("owner", "Synthetic network platform function"),
                        "rationale": "Scenario-generated identity review of deployment, environment and application context. Alias rows link to the reviewed deployment without deleting the original assertion."}
                    result = command("reconcile_product", request, fields)
                    selected = next(i for i in result["case"]["identityDecisions"] if i["productId"] == product["id"])
                    canonical[normalized] = selected["canonicalId"]

        reconcile_all()
        second = receive(revised)
        assert any(c["state"] == "conflict" for c in second["receipt"]["comparison"])
        command("receipt_apply", second["receipt"]["id"], {"choices": {c["questionId"]: "current" for c in second["receipt"]["comparison"] if c["state"] == "conflict"},
            "note": "Keep the first reported routing position pending clarification of the revised return. Both workbook versions remain retained."})
        reconcile_all()
        ws.gate("PQC-G00")
        for family in FAMILIES:
            ws.command("source_response", family, {"state": "route_confirmed", "systemOfRecord": "Closed synthetic context, certificate and TLS fixtures", "product": "Example products only; no installed-product validation",
                "ownerFunction": "Synthetic source and network platform function", "accessRoute": "Owned synthetic files; no enterprise access", "note": "The partner-edge deployment has no supporting-information route. Other records are a bounded modeled cohort.",
                "dueAt": "2026-09-22", "assertedBy": "Scenario-generated source coordinator"})
        ws.gate("PQC-P1-G01")
        # Restart at the durable checkpoint, retaining the interactive action limit.
        server.stop(); server.start(); ws.client = Client(server.origin).login(); ws.clients = {"analyst": ws.client}; ws.refresh()
        products = case()["receipts"][0]["products"]
        selected_products = [next(p for p in products if "east" in p["deployment"].lower()), next(p for p in products if "west" in p["deployment"].lower())]
        for index, product in enumerate(selected_products):
            for filename in ("context.json", "certificate.json", "tls-configured.json", "tls-observed.json"):
                if index == 1 and filename == "tls-configured.json":
                    continue
                payload = json.loads((FILES / filename).read_text())
                if index == 1:
                    for row in payload["records"]:
                        if "hostname" in row: row["hostname"] = "portal-west.example"
                        if "deployment" in row: row["deployment"] = "gateway-west"
                        if "keyExchange" in row: row["keyExchange"] = "X25519"
                ws.refresh()
                query = urlencode({"productId": product["id"], "expectedRevision": ws.state["revision"]})
                status, staged, _ = raw_request(ws.client, ws.route + "/work/" + request + "/evidence?" + query, method="POST",
                    data=json.dumps(payload).encode(), content_type="application/json", headers={"Idempotency-Key": uuid4().hex})
                assert status == 200, staged
                bundle = next(b for b in staged["case"]["technicalRecords"] if b["status"] == "staged")
                is_conflict = index == 0 and filename.startswith("tls")
                command("workspace_review_evidence", bundle["bundleId"], {"determination": "qualified",
                    "rationale": "Independent simulated reviewer examined each source field. Configured hybrid exchange and modeled classical observation conflict; qualification retains the discrepancy, not a favorable selection.",
                    "recordDecisions": [{"observationId": o["id"], "determination": "conflict" if is_conflict else "supports_claim",
                        "rationale": "Preserve configured-versus-observed conflict." if is_conflict else "Supports only the supplied source fields and evidence basis; not enterprise behavior, ownership confirmation or lifetime."} for o in bundle["observations"]]}, "reviewer")
                command("workspace_admit_evidence", bundle["bundleId"])
        server.stop(); server.start(); ws.client = Client(server.origin).login(); ws.clients = {"analyst": ws.client}; ws.refresh()
        current = case()
        observations = [o for b in current["technicalRecords"] if b["status"] == "admitted" for o in b["observations"]]
        fields = {"phase1Conclusion": "Two of three reported deployments were examined in this synthetic cohort. Gateway-east has configured hybrid key exchange but a conflicting modeled classical observation. Gateway-west records classical exchange. Classical authentication remains separate in both deployments.",
            "limitation": "Partner-edge is reported but unexamined because its supporting-information route is blocked. The enterprise population, complete client cohort, independent runtime verification and information lifetime remain unknown. No absence of policy is inferred.",
            "nextDecision": "Network platform function: reconcile east configuration and observation scope. Partner service function: establish a permitted source route. Business review function: establish confidentiality/trust lifetimes and service consequences.",
            "responsibleFunction": "Synthetic network platform, partner service and business review functions", "phase2Consequence": "If these uses protect long-lived information or essential authentication, residual classical dependencies warrant investigation before migration prioritization. No loss estimate or quantum-arrival prediction is established.",
            "lifetime": "Unknown; requires attributed input and review by the information owner.", "confidence": "limited",
            "cryptographicPurpose": "key_establishment", "productId": "",
            "supportingObservationIds": [o["id"] for o in observations if o["basis"] != "observed"], "contradictingObservationIds": [o["id"] for o in observations if o["basis"] == "observed"]}
        ws.refresh()
        status, preview, _ = ws.client.request(ws.route + "/report-impact/preview", method="POST", body=ws.payload("record_consequence", request, fields))
        assert status == 200, preview
        command("record_consequence", request, {**fields, "previewFingerprint": preview["previewFingerprint"]})
        for index, product in enumerate(selected_products):
            records = [o for o in observations if o["canonicalId"] == canonical["gateway-east" if index == 0 else "gateway-west"]]
            per_use = {**fields, "productId": product["id"],
                "phase1Conclusion": "Gateway-east: configured hybrid key establishment conflicts with the modeled classical observation; classical authentication is a separate recorded dependency." if index == 0 else "Gateway-west: modeled source records describe classical key establishment and classical authentication; neither migration readiness nor whole-application exposure is established.",
                "supportingObservationIds": [o["id"] for o in records if index != 0 or o["basis"] != "observed"],
                "contradictingObservationIds": [o["id"] for o in records if index == 0 and o["basis"] == "observed"]}
            ws.refresh()
            status, material_preview, _ = ws.client.request(ws.route + "/report-impact/preview", method="POST", body=ws.payload("record_consequence", request, per_use))
            assert status == 200, material_preview
            command("record_consequence", request, {**per_use, "previewFingerprint": material_preview["previewFingerprint"]})
        for family in FAMILIES:
            ws.command("submit_package", family, {"conclusion": fields["phase1Conclusion"] if family == "traffic-termination" else "Synthetic source records provide bounded application context or certificate metadata for the two examined deployments; no enterprise completeness is established.", "qualification": fields["limitation"]})
            ws.command("review_package", family, decision_fields(), "reviewer")
        ws.gate("PQC-P1-G02")
        p1 = ws.report("phase1")
        ws.gate("PQC-P1-G03", report=p1["metadata"]["id"])
        server.stop(); server.start(); ws.client = Client(server.origin).login(); ws.clients = {"analyst": ws.client}; ws.refresh()
        ws.command("set_method", fields={"name": "Synthetic evidence-qualified scenario analysis", "description": "Separate exposure, business consequence, evidence confidence and migration readiness.", "confidenceRules": "Preserve unknowns and conflicts; no numeric enterprise score.", "prioritizationRules": "Resolve consequential knowledge gaps before migration design."}, role="risk-lead")
        ws.gate("PQC-P2-G01")
        for family in FAMILIES:
            ws.command("submit_analysis", family, {"scenario": fields["phase2Consequence"], "businessImpact": "Potential service and protected-information consequences remain conditional. Business reviewers acknowledge missing lifetime input; they do not invent it.", "recommendation": fields["nextDecision"], "priority": "planned_review", "rationale": "Resolve conflicts and missing business context. Ticket status and configured algorithms do not prove migration success.", "confidence": "limited"}, "risk-lead")
            ws.command("review_analysis", family, decision_fields(), "business-reviewer")
        ws.gate("PQC-P2-G02")
        p2 = ws.report("phase2", p1["metadata"]["id"], "risk-lead")
        for name, report in (("Phase_1_Current_State", p1), ("Phase_2_Risk_and_Recommendations", p2)):
            report_id = report["metadata"]["id"]
            status, html, _ = ws.client.request(ws.route + "/reports/" + report_id + "/download?format=html")
            assert status == 200
            (reports / (name + ".html")).write_text(html)
            write_json(reports / (name + ".json"), report)
        write_json(output / "worked-example.json", {"assessmentId": ws.state["id"], "requestId": request, "reportIds": [p1["metadata"]["id"], p2["metadata"]["id"]], "scenarioGenerated": True,
            "duplicateDetected": True, "originalReturn": original.name, "revisedReturn": revised.name, "preview": preview, "boundary": "Synthetic simulated decisions only; no owner product observation or enterprise acceptance."})
        fresh = Workspace(Client(server.origin).login(), "fresh", name="Your fresh walkthrough · operational form receipt")
        fresh_scope = scope_fields(fresh)
        fresh_scope.update(includedFamilyIds=FAMILIES, depthByFamily={f: "inventory" for f in FAMILIES}, excludedReasons={s["familyId"]: "Outside the walkthrough cohort." for s in fresh.state["sources"] if s["familyId"] not in FAMILIES})
        fresh.command("update_scope", fields=fresh_scope)
        status, created, _ = fresh.client.request(fresh.route + "/discovery/commands", method="POST", body=fresh.payload("discovery_create", fields={"title": "Receive and review the synthetic traffic-termination form", "familyId": "traffic-termination", "assignedTo": "synthetic-demo:contributor"}), headers={"Idempotency-Key": uuid4().hex})
        assert status == 200, created
        fresh_request = fresh.client.request(fresh.route + "/discovery")[1]["requests"][-1]["id"]
        write_json(output / "fresh-walkthrough.json", {"assessmentId": fresh.state["id"], "requestId": fresh_request, "scenarioGenerated": False, "expectedAction": "Record an operational-form receipt; no prior response or technical admission."})
        print(json.dumps({"output": str(output), "workedAssessment": ws.state["id"], "freshAssessment": fresh.state["id"], "reportCount": 2}))
    finally:
        server.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dll", type=Path, required=True)
    args = parser.parse_args()
    prepare_demo(args.output, args.dll)
