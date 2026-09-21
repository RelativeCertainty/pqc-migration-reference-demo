"""Authenticated intake HTTP proofs using an explicitly built isolated candidate.

No implicit builds, downloads, production connections, enterprise credentials or
owner decisions. All inputs and persona interactions are synthetic test data.
"""
from __future__ import annotations

import copy
from io import BytesIO
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request
from uuid import uuid4
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from tests.test_pqc_enterprise_demo_http import Client, Server, Workspace, fixture_input, scope_fields


ROOT = Path(__file__).resolve().parents[1]
DLL = os.environ.get("PQC_ENTERPRISE_DEMO_DLL")
pytestmark = pytest.mark.skipif(not DLL, reason="explicit built C# DLL required; no implicit build/download")
TLS = (ROOT / "integrations/pqc/reference_assessment/tls.page.json").read_bytes()
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


@pytest.fixture
def intake_server(tmp_path, fixture_input):
    app = Server(tmp_path, fixture_input)
    try:
        yield app.start()
    finally:
        app.stop()


def raw_request(client, path, *, data=None, method="GET", content_type=None, headers=None):
    """Use the authenticated helper's cookie jar without decoding XLSX as text."""
    header = {"Origin": client.origin}
    if client.csrf:
        header["X-PQC-CSRF"] = client.csrf
    if content_type:
        header["Content-Type"] = content_type
    header.update(headers or {})
    request = Request(client.origin + path, data=data, headers=header, method=method)
    try:
        response = client.opener.open(request, timeout=45)
    except HTTPError as error:
        response = error
    content = response.read()
    parsed = json.loads(content) if "application/json" in response.headers.get("Content-Type", "") else content
    return response.status, parsed, response.headers


class Intake:
    def __init__(self, server, mode="fresh"):
        # The existing worked example intentionally scopes only selected families;
        # never assume TLS is in that assessment or bypass its approval gates.
        self.ws = Workspace(Client(server.origin).login(), "fresh")
        self.client = self.ws.client
        self.route = self.ws.route + "/intake"
        if mode == "worked_example":
            scope = scope_fields(self.ws)
            scope.update(includedFamilyIds=["traffic-termination"],
                depthByFamily={"traffic-termination": "routing"},
                excludedReasons={source["familyId"]: "Outside this bounded synthetic TLS intake proof."
                    for source in self.ws.state["sources"] if source["familyId"] != "traffic-termination"})
            self.ws.command("update_scope", fields=scope)
            self.ws.gate("PQC-G00")
            self.ws.command("source_response", "traffic-termination", {"state": "route_confirmed",
                "systemOfRecord": "Synthetic configuration export", "product": "Synthetic reference TLS dialect",
                "ownerFunction": "Synthetic platform function", "accessRoute": "Owner-provided synthetic fixture only",
                "note": "Bounded test fixture route; no live source or enterprise authorization.",
                "dueAt": "2026-09-22", "assertedBy": "Synthetic assessment coordinator"})
            self.ws.gate("PQC-P1-G01")

    def actor(self, role):
        return self.ws.actor(role)

    def view(self, role="analyst"):
        status, view, _ = self.actor(role).request(self.route)
        assert status == 200, (status, view)
        return view

    def payload(self, operation, target=None, fields=None):
        return {"operation": operation, "targetId": target, "fields": fields or {},
            "expectedRevision": self.view()["revision"]}

    def command(self, operation, target=None, fields=None, role="analyst"):
        response = self.actor(role).request(self.route + "/commands", method="POST",
            body=self.payload(operation, target, fields), headers={"Idempotency-Key": uuid4().hex})
        assert response[0] == 200, (operation, response[0], response[1])
        return response[1]

    def create_request(self, title="Locate the portal deployments", assigned="contributor", family="traffic-termination"):
        before = {row["id"] for row in self.view()["requests"]}
        result = self.command("intake_create_request", fields={"title": title,
            "familyId": family, "assignedTo": "synthetic-demo:" + assigned})
        return next(row for row in result["requests"] if row["id"] not in before)["id"]

    def system(self, request_id, label, *, role="subject", about="", product="", environment="", actor="contributor"):
        before = {row["id"] for row in self.view()["systems"]}
        result = self.command("intake_add_system", request_id, {"label": label,
            "product": product, "environment": environment, "systemRole": role,
            "aboutSystemId": about}, actor)
        return next(row for row in result["systems"] if row["id"] not in before)["id"]

    def save(self, request_id, answers, *, actor="contributor", asserted_by=""):
        return self.command("intake_save_response", request_id,
            {"answers": answers, "assertedBy": asserted_by}, actor)

    def export(self, request_id, actor="contributor"):
        status, result, _ = self.actor(actor).request(self.route + "/exports/" + request_id,
            method="POST", body={"expectedRevision": self.view()["revision"]},
            headers={"Idempotency-Key": uuid4().hex})
        assert status == 200, (status, result)
        status, workbook, headers = raw_request(self.actor(actor), result["downloadUrl"])
        assert status == 200 and isinstance(workbook, bytes)
        assert "spreadsheetml.sheet" in headers["Content-Type"]
        return result, workbook

    def import_preview(self, request_id, workbook, actor="contributor"):
        route = self.route + "/imports/" + request_id + "?" + urlencode({"expectedRevision": self.view()["revision"]})
        return raw_request(self.actor(actor), route, method="POST", data=workbook,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Idempotency-Key": uuid4().hex})

    def stage(self, request_id, system_id, source_id, *, actor="contributor", data=TLS):
        route = self.route + "/evidence/" + request_id + "?" + urlencode({
            "systemId": system_id, "sourceSystemId": source_id,
            "expectedRevision": self.view()["revision"]})
        return raw_request(self.actor(actor), route, method="POST", data=data,
            content_type="application/json", headers={"Idempotency-Key": uuid4().hex})


def request_record(view, request_id):
    return next(row for row in view["requests"] if row["id"] == request_id)


def edited_workbook(workbook, replacements):
    """Edit only literal response cells in a server-generated synthetic workbook."""
    output = BytesIO()
    changed = set()
    with ZipFile(BytesIO(workbook)) as source, ZipFile(output, "w") as target:
        for info in source.infolist():
            contents = source.read(info.filename)
            if info.filename.startswith("xl/worksheets/"):
                root = ET.fromstring(contents)
                for row in root.findall(".//{" + NS + "}row"):
                    cells = list(row.findall("{" + NS + "}c"))
                    by_column = {cell.attrib["r"][0]: cell for cell in cells}
                    key = "".join(by_column.get("A", ET.Element("empty")).itertext())
                    if key not in replacements:
                        continue
                    cell = by_column.get("C")
                    if cell is None:
                        cell = ET.SubElement(row, "{" + NS + "}c", {"r": "C" + row.attrib["r"]})
                    cell.clear()
                    cell.set("r", "C" + row.attrib["r"])
                    cell.set("t", "inlineStr")
                    inline = ET.SubElement(cell, "{" + NS + "}is")
                    text = ET.SubElement(inline, "{" + NS + "}t")
                    text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                    text.text = replacements[key]
                    changed.add(key)
                contents = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            target.writestr(info, contents)
    assert changed == set(replacements)
    return output.getvalue()


def test_two_deployments_partial_response_handoff_and_report_consequence(intake_server):
    intake = Intake(intake_server)
    request_id = intake.create_request()
    initial = intake.view("contributor")
    request = request_record(initial, request_id)
    assert request["examples"] and request["whyItMatters"]
    assert initial["questions"]
    assert all(question["whyItMatters"] and question["usefulResponse"] for question in initial["questions"])
    assert "not sent" in initial["receipt"]["effect"]
    east = intake.system(request_id, "Synthetic portal east", product="NGINX", environment="test-east")
    west = intake.system(request_id, "Synthetic portal west", product="NGINX", environment="test-west")
    source = intake.system(request_id, "Synthetic configuration repository", role="source", about=east)
    assert len({east, west, source}) == 3
    saved = intake.save(request_id, {
        east + "/owner": "Synthetic application services",
        east + "/evidenceRoute": "Approved configuration export not yet requested",
        west + "/owner": "I do not know",
        west + "/referral": "Synthetic regional platform function",
        request_id + "/limitation": "West environment source route remains unconfirmed."})
    assert request_record(saved, request_id)["status"] == "responding"
    assert "Draft saved" in saved["receipt"]["effect"]
    assert saved["evidence"] == []
    returned = intake.command("intake_submit_response", request_id, role="contributor")
    assert request_record(returned, request_id)["status"] == "returned"
    assert returned["receipt"]["nextResponsible"] == "Assessment lead"
    assert returned["receipt"]["nextAction"] == request_id
    reviewed = intake.command("intake_review_response", request_id, {
        "determination": "qualified", "limitation": "Identity routing is usable; no technical behavior verified."}, "reviewer")
    record = request_record(reviewed, request_id)
    assert record["status"] == "closed_with_limitation"
    assert record["reviewedBy"] == "synthetic-demo:reviewer"
    preview = reviewed["reportPreview"]
    assert any("Synthetic portal east" in line and "Synthetic application services" in line for line in preview["conclusions"])
    assert any("Synthetic portal west" in line and "no technical observation admitted" in line for line in preview["limitations"])
    assert any("Synthetic regional platform function" in line for line in preview["nextDecisions"])
    assert "Enterprise population is unknown" in " ".join(preview["limitations"])
    assert all(gate["state"] == "not_submitted" for gate in intake.ws.refresh()["gates"])


def test_unknown_routing_answers_remain_quoted_responses_not_confirmed_facts(intake_server):
    intake = Intake(intake_server, "worked_example")
    request_id = intake.create_request("Synthetic partially known deployment")
    subject = intake.system(request_id, "Synthetic routing-only portal")
    source = intake.system(request_id, "Synthetic possible evidence store", role="source", about=subject)
    both = intake.system(request_id, "Synthetic combined-role system", role="both")
    unknown_owner = "I do not know"
    unknown_route = "Unknown — no route identified"
    unknown_referral = "Not my team; next function is unknown"
    intake.save(request_id, {subject + "/owner": unknown_owner,
        subject + "/evidenceRoute": unknown_route, subject + "/referral": unknown_referral})
    routing_request = intake.create_request("Synthetic referral without a system")
    intake.save(routing_request, {routing_request + "/owner": unknown_owner,
        routing_request + "/evidenceRoute": unknown_route, routing_request + "/referral": unknown_referral})
    preview = intake.view()["reportPreview"]
    assert preview["summary"].startswith("3 recorded systems and evidence sources;")
    conclusions = " ".join(preview["conclusions"])
    decisions = " ".join(preview["nextDecisions"])
    assert "Synthetic routing-only portal: system being assessed." in conclusions
    assert "Synthetic possible evidence store: system supplying evidence." in conclusions
    assert "Synthetic combined-role system: system being assessed and supplying evidence." in conclusions
    assert conclusions.count(f"Ownership response: “{unknown_owner}”.") == 2
    assert f"Evidence-location response: “{unknown_route}”." in decisions
    assert f"Referral response: “{unknown_referral}”." in decisions
    assert "Review the response and establish an evidence route; obtain authorization before collection." in decisions
    assert "The assessment lead must confirm the next responsible function." in decisions
    assert "owner I do not know" not in conclusions
    assert "reported responsible function I do not know" not in conclusions
    assert "confirm and authorize reported route Unknown" not in decisions
    assert "Next function: Not my team" not in decisions
    assert all(f": {token};" not in conclusions for token in ("subject", "source", "both"))
    recorded = request_record(intake.view(), request_id)
    assert recorded["answers"][subject + "/owner"] == unknown_owner
    assert recorded["answers"][subject + "/evidenceRoute"] == unknown_route
    assert recorded["determination"] == "awaiting_review"
    assert preview["evidence"] == []
    report = intake.ws.report("phase1")
    assert report["content"]["intake"]["conclusions"] == preview["conclusions"]
    report_route = intake.ws.route + "/reports/" + report["metadata"]["id"]
    intake.save(request_id, {subject + "/owner": "Synthetic suggested platform function"})
    assert intake.client.request(report_route)[1] == report
    assert "Synthetic suggested platform function" in " ".join(intake.view()["reportPreview"]["conclusions"])
    assert all(row["id"] != source for row in preview["evidence"])
    assert all(row["id"] != both for row in preview["evidence"])


def test_assigned_contributors_cannot_read_write_export_or_replay_other_requests(intake_server):
    intake = Intake(intake_server)
    assert intake.actor("contributor").request(intake.route)[0] == 403
    assert all(row["id"] != intake.ws.state["id"] for row in intake.actor("contributor").request("/api/assessments")[1])
    first = intake.create_request("Synthetic first assignment")
    second = intake.create_request("Synthetic second assignment", "contributor-two")
    intake.save(second, {second + "/owner": "SYNTHETIC-PRIVATE-SECOND-FUNCTION"}, actor="contributor-two")
    for role, expected, hidden in (("contributor", first, second), ("contributor-two", second, first)):
        view = intake.view(role)
        assert {row["id"] for row in view["requests"]} == {expected}
        assert hidden not in json.dumps(view)
        assert intake.actor(role).request(intake.ws.route)[0] == 403
        assert intake.actor(role).request(intake.ws.route + "/reports")[0] == 403
        assert intake.actor(role).request(intake.ws.route + "/runs")[0] == 403
    assert "SYNTHETIC-PRIVATE-SECOND-FUNCTION" not in json.dumps(intake.view("contributor"))
    payload = intake.payload("intake_save_response", second, {"answers": {second + "/owner": "Changed"}, "assertedBy": ""})
    assert intake.actor("contributor").request(intake.route + "/commands", method="POST", body=payload,
        headers={"Idempotency-Key": "cross-contributor-write-" + uuid4().hex})[0] == 403
    exported, workbook = intake.export(second, "contributor-two")
    assert raw_request(intake.actor("contributor"), exported["downloadUrl"])[0] == 403
    assert intake.import_preview(second, workbook, "contributor")[0] == 403
    assert intake.actor("contributor").request(intake.route + "/exports/" + second, method="POST",
        body={"expectedRevision": intake.view()["revision"]}, headers={"Idempotency-Key": uuid4().hex})[0] == 403
    # An invalid workbook would fail parsing as 400 if unauthorized bytes reached
    # the parser. Review/read access is not permission to import respondent files.
    for role in ("reviewer", "viewer"):
        assert intake.import_preview(second, b"SYNTHETIC-NOT-A-WORKBOOK", role)[0] == 403


def test_create_request_requires_explicit_null_target_in_browser_wire_contract(intake_server):
    intake = Intake(intake_server)
    fields = {"title": "Synthetic browser wire-contract regression", "familyId": "traffic-termination",
        "assignedTo": "synthetic-demo:contributor"}
    # JSON.stringify drops undefined values: omitting the declared target field
    # must remain invalid, not cause the server's closed contract to be relaxed.
    body = {"operation": "intake_create_request", "fields": fields,
        "expectedRevision": intake.view()["revision"]}
    status, error, _ = intake.client.request(intake.route + "/commands", method="POST", body=body,
        headers={"Idempotency-Key": uuid4().hex})
    assert status == 400 and error["error"]["code"] == "missing_request_field"
    assert intake.view()["requests"] == []
    status, result, _ = intake.client.request(intake.route + "/commands", method="POST",
        body={**body, "targetId": None}, headers={"Idempotency-Key": uuid4().hex})
    assert status == 200, result
    assert len(result["requests"]) == 1


def test_request_commands_are_closed_idempotent_and_recheck_revision(intake_server):
    intake = Intake(intake_server)
    request_id = intake.create_request()
    payload = intake.payload("intake_save_response", request_id, {
        "answers": {request_id + "/referral": "Not my team; synthetic platform function"}, "assertedBy": ""})
    headers = {"Idempotency-Key": uuid4().hex}
    actor = intake.actor("contributor")
    first = actor.request(intake.route + "/commands", method="POST", body=payload, headers=headers)
    assert first[0] == 200, first[1]
    assert actor.request(intake.route + "/commands", method="POST", body=payload, headers=headers)[1] == first[1]
    changed = copy.deepcopy(payload)
    changed["fields"]["answers"][request_id + "/referral"] = "Different synthetic function"
    assert actor.request(intake.route + "/commands", method="POST", body=changed, headers=headers)[0] == 409
    assert actor.request(intake.route + "/commands", method="POST", body=payload,
        headers={"Idempotency-Key": uuid4().hex})[0] == 409
    assert actor.request(intake.route + "/commands", method="POST", body=payload,
        headers={"Idempotency-Key": uuid4().hex, "X-PQC-CSRF": "invalid"})[0] == 403
    injected = {**intake.payload("intake_submit_response", request_id), "principalId": "synthetic-demo:analyst"}
    assert actor.request(intake.route + "/commands", method="POST", body=injected,
        headers={"Idempotency-Key": uuid4().hex})[0] == 400
    submitted = intake.command("intake_submit_response", request_id, role="contributor")
    assert request_record(submitted, request_id)["status"] == "returned"
    assert submitted["systems"] == []  # a useful referral needs no invented deployment
    assert submitted["evidence"] == []
    assert any("Not my team; synthetic platform function" in line for line in submitted["reportPreview"]["nextDecisions"])
    assert actor.request(intake.route + "/commands", method="POST",
        body=intake.payload("intake_review_response", request_id, {"determination": "qualified", "limitation": "Self review"}),
        headers={"Idempotency-Key": uuid4().hex})[0] == 403


def test_scope_command_requires_same_explicit_null_wire_contract(intake_server):
    intake = Intake(intake_server)
    body = {"operation": "update_scope", "fields": scope_fields(intake.ws),
        "expectedRevision": intake.view()["revision"]}
    status, error, _ = intake.client.request(intake.ws.route + "/commands", method="POST", body=body,
        headers={"Idempotency-Key": uuid4().hex})
    assert status == 400 and error["error"]["code"] == "missing_request_field"
    status, result, _ = intake.client.request(intake.ws.route + "/commands", method="POST",
        body={**body, "targetId": None}, headers={"Idempotency-Key": uuid4().hex})
    assert status == 200, result
    assert result["revision"] == body["expectedRevision"] + 1


def test_removed_family_keeps_history_but_blocks_writes_and_report_reliance(intake_server):
    intake = Intake(intake_server)
    request_id = intake.create_request()
    subject = intake.system(request_id, "Synthetic excluded portal")
    intake.save(request_id, {subject + "/owner": "Synthetic excluded function"})
    exported, workbook = intake.export(request_id)
    intake.ws.refresh()
    scope = scope_fields(intake.ws)
    included = [family for family in scope["includedFamilyIds"] if family != "traffic-termination"]
    scope.update(includedFamilyIds=included,
        depthByFamily={family: scope["depthByFamily"][family] for family in included},
        excludedReasons={"traffic-termination": "Excluded after initial synthetic routing; retain history only."})
    intake.ws.command("update_scope", fields=scope)
    view = intake.view("contributor")
    assert request_record(view, request_id)["answers"][subject + "/owner"] == "Synthetic excluded function"
    assert "Synthetic excluded portal" not in json.dumps(view["reportPreview"])
    assert "Synthetic excluded function" not in json.dumps(view["reportPreview"])
    assert raw_request(intake.actor("contributor"), exported["downloadUrl"])[1] == workbook
    assert intake.actor("contributor").request(intake.route + "/commands", method="POST",
        body=intake.payload("intake_save_response", request_id, {"answers": {subject + "/owner": "Changed"}, "assertedBy": ""}),
        headers={"Idempotency-Key": uuid4().hex})[0] == 409
    assert intake.import_preview(request_id, b"SYNTHETIC-NOT-A-WORKBOOK")[0] == 409
    assert intake.actor("contributor").request(intake.route + "/exports/" + request_id, method="POST",
        body={"expectedRevision": intake.view()["revision"]}, headers={"Idempotency-Key": uuid4().hex})[0] == 409


def test_workbook_roundtrip_conflict_blank_no_change_and_stale_preview(intake_server):
    intake = Intake(intake_server)
    request_id = intake.create_request()
    owner_key = request_id + "/owner"
    referral_key = request_id + "/referral"
    intake.save(request_id, {owner_key: "Synthetic baseline owner", referral_key: "Synthetic baseline referral"})
    export, workbook = intake.export(request_id)
    assert export["exportId"]
    with ZipFile(BytesIO(workbook)) as archive:
        assert archive.testzip() is None
        assert "xl/workbook.xml" in archive.namelist()
    returned = edited_workbook(workbook, {owner_key: "Synthetic offline owner", referral_key: ""})
    intake.save(request_id, {owner_key: "Synthetic web owner"})
    status, preview, _ = intake.import_preview(request_id, returned)
    assert status == 200, preview
    changes = {change["key"]: change for change in preview["changes"]}
    assert changes[owner_key]["state"] == "conflict"
    assert changes[owner_key]["baseline"] == "Synthetic baseline owner"
    assert changes[owner_key]["current"] == "Synthetic web owner"
    assert changes[owner_key]["returned"] == "Synthetic offline owner"
    assert changes[referral_key]["state"] == "unchanged"
    assert request_record(intake.view(), request_id)["answers"][owner_key] == "Synthetic web owner"
    unresolved = intake.actor("contributor").request(intake.route + "/commands", method="POST",
        body=intake.payload("intake_commit_import", request_id, {"previewId": preview["previewId"], "choices": {}}),
        headers={"Idempotency-Key": uuid4().hex})
    assert unresolved[0] == 400
    intake.save(request_id, {owner_key: "Synthetic later web owner"})
    assert intake.actor("contributor").request(intake.route + "/commands", method="POST",
        body=intake.payload("intake_commit_import", request_id, {"previewId": preview["previewId"], "choices": {owner_key: "returned"}}),
        headers={"Idempotency-Key": uuid4().hex})[0] == 409
    status, refreshed, _ = intake.import_preview(request_id, returned)
    assert status == 200, refreshed
    result = intake.command("intake_commit_import", request_id, {"previewId": refreshed["previewId"],
        "choices": {owner_key: "returned"}}, "contributor")
    answers = request_record(result, request_id)["answers"]
    assert answers[owner_key] == "Synthetic offline owner"
    assert answers[referral_key] == "Synthetic baseline referral"
    assert request_record(result, request_id)["status"] == "responding"
    assert "workbook text cannot approve" in result["receipt"]["effect"]
    # An unchanged answer from the original export must not erase a later web
    # edit, even if a caller explicitly selects the returned value for that row.
    intake.save(request_id, {referral_key: "Synthetic later referral"})
    status, unchanged, _ = intake.import_preview(request_id, workbook)
    assert status == 200, unchanged
    change = next(row for row in unchanged["changes"] if row["key"] == referral_key)
    assert change["state"] == "unchanged"
    result = intake.command("intake_commit_import", request_id, {"previewId": unchanged["previewId"],
        "choices": {referral_key: "returned"}}, "contributor")
    assert request_record(result, request_id)["answers"][referral_key] == "Synthetic later referral"


def test_tls_staging_is_not_admission_and_source_identity_is_not_subject(intake_server):
    intake = Intake(intake_server)
    request_id = intake.create_request()
    subject = intake.system(request_id, "Synthetic assessed portal")
    other_subject = intake.system(request_id, "Synthetic other portal")
    source = intake.system(request_id, "Synthetic observer", role="source", about=subject)
    assert intake.stage(request_id, subject, subject)[0] == 400
    assert intake.stage(request_id, source, source)[0] == 400
    assert intake.stage(request_id, other_subject, source)[0] == 400
    status, staged, _ = intake.stage(request_id, subject, source)
    assert status == 200, staged
    assert staged["evidence"] == []
    assert staged["reportPreview"]["evidence"] == []
    assets = intake.client.request(intake.ws.route + "/assets")[1]
    assert subject not in {asset["id"] for asset in assets["items"]}
    assert len(staged["pendingEvidence"]) == 1
    pending = staged["pendingEvidence"][0]
    assert pending["systemId"] == subject and pending["sourceSystemId"] == source
    assert not staged["canAdmit"]
    assert intake.client.request(intake.route + "/commands", method="POST",
        body=intake.payload("intake_admit_evidence", request_id, {"batchId": pending["id"]}),
        headers={"Idempotency-Key": uuid4().hex})[0] == 409
    assert intake.stage(request_id, subject, source)[0] == 409
    non_synthetic = json.loads(TLS)
    non_synthetic["synthetic"] = False
    assert intake.stage(request_id, subject, source, data=json.dumps(non_synthetic).encode())[0] == 400


def test_admitted_tls_reaches_report_input_with_independent_crypto_roles(intake_server):
    intake = Intake(intake_server, "worked_example")
    request_id = intake.create_request()
    subject = intake.system(request_id, "Synthetic hybrid portal")
    source = intake.system(request_id, "Synthetic bounded observer", role="source", about=subject)
    hybrid = json.loads(TLS)
    hybrid["records"][0]["key_exchange_group"] = "X25519MLKEM768"
    status, staged, _ = intake.stage(request_id, subject, source, data=json.dumps(hybrid).encode())
    assert status == 200, staged
    assert not staged["canAdmit"]  # the contributor can stage, never admit
    assert intake.view()["canAdmit"]  # the coordinator has both required gates
    assert intake.client.request(intake.ws.route + "/assets?" + urlencode({"q": "Synthetic hybrid portal"}))[1]["total"] == 0
    batch_id = staged["pendingEvidence"][0]["id"]
    result = intake.command("intake_admit_evidence", request_id, {"batchId": batch_id})
    observation = result["evidence"][0]
    assert observation["systemId"] == subject
    assert observation["sourceSystemId"] == source
    assert observation["keyExchange"] == "X25519MLKEM768"
    assert observation["authentication"] == "sha256WithRSAEncryption"
    assert observation["basis"] == "observed"
    assert result["reportPreview"]["evidence"] == result["evidence"]
    conclusions = " ".join(result["reportPreview"]["conclusions"])
    assert "key establishment X25519MLKEM768" in conclusions
    assert "certificate authentication sha256WithRSAEncryption" in conclusions
    assert "has not independently exercised" in conclusions
    assert not result["pendingEvidence"]
    status, assets, _ = intake.client.request(intake.ws.route + "/assets?" + urlencode({"q": "Synthetic hybrid portal"}))
    assert status == 200 and assets["total"] == 1
    assert assets["items"][0]["id"] == subject
    detail = intake.client.request(intake.ws.route + "/assets/" + subject)[1]
    assert observation["id"] in {row["observation_id"] for row in detail["observations"]}
    report = intake.ws.report("phase1")
    assert observation["id"] in {row["id"] for row in report["content"]["intake"]["evidence"]}
    assert subject in json.dumps(report["content"])


def test_reports_freeze_intake_input_and_survive_restart_backup_restore(tmp_path, fixture_input):
    server = Server(tmp_path, fixture_input)
    try:
        server.start()
        intake = Intake(server, "worked_example")
        request_id = intake.create_request()
        subject = intake.system(request_id, "Synthetic preserved portal")
        intake.save(request_id, {subject + "/owner": "Synthetic initial owner"})
        intake.command("intake_submit_response", request_id, role="contributor")
        intake.command("intake_review_response", request_id, {"determination": "qualified",
            "limitation": "Owner statement only; no cryptographic behavior inferred."}, "reviewer")
        exported, workbook = intake.export(request_id)
        preview = intake.view()["reportPreview"]
        report = intake.ws.report("phase1")
        assert report["content"]["intake"]["lineage"]["inputSha256"] == preview["lineage"]["inputSha256"]
        assert "Synthetic initial owner" in json.dumps(report["content"]["intake"])
        report_route = intake.ws.route + "/reports/" + report["metadata"]["id"]
        intake.save(request_id, {subject + "/owner": "Synthetic corrected owner"})
        assert intake.view()["reportPreview"]["lineage"]["inputSha256"] != preview["lineage"]["inputSha256"]
        assert intake.client.request(report_route)[1] == report
        frozen_state = intake.client.request(intake.ws.route)[1]
        server.stop()
        server.start()
        assert intake.client.request(report_route)[0] == 401
        intake.client.login()
        assert intake.client.request(report_route)[1] == report
        assert intake.client.request(intake.ws.route)[1] == frozen_state
        assert raw_request(intake.client, exported["downloadUrl"])[1] == workbook
        server.stop()
        backup = tmp_path / "intake-backup"
        completed = subprocess.run(["dotnet", str(Path(DLL).resolve()), "--data-dir", str(server.data),
            "--fixture", str(fixture_input), "--backup-dir", str(backup)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        assert completed.returncode == 0, "isolated intake backup failed"
        server.data = backup
        server.start()
        restored = Client(server.origin).login()
        assert restored.request(report_route)[1] == report
        assert restored.request(intake.ws.route)[1] == frozen_state
        assert raw_request(restored, exported["downloadUrl"])[1] == workbook
        server.stop()
        with sqlite3.connect(backup / "enterprise-demo.sqlite3") as database:
            assert database.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            with pytest.raises(sqlite3.DatabaseError, match="immutable"):
                database.execute("DELETE FROM assessment_versions")
    finally:
        server.stop()
