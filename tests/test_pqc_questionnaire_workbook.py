"""Full 27-question offline exchange; isolated candidate and synthetic responses only.

Requires explicitly built DLL and the versioned catalog path. No build, package
installation, external communication, live state, or Office-compatibility claim
is implicit. Optional LibreOffice proof uses a unique owner-only user profile.
"""
from __future__ import annotations

from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from tests.test_pqc_questionnaire_http import Forms, questionnaire_server, all_unresolved
from tests.test_pqc_enterprise_demo_http import fixture_input
from tests.test_pqc_intake_http import raw_request
from tests.test_pqc_intake_workbook import xml, package, parts

DLL = os.environ.get("PQC_ENTERPRISE_DEMO_DLL")
CATALOG = os.environ.get("PQC_QUESTIONNAIRE_CATALOG_FILE")
pytestmark = pytest.mark.skipif(not DLL or not CATALOG, reason="explicit built candidate and versioned catalog required")
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
FIELDS = ["status", "text", "evidenceRefs", "rationale", "nextOwner", "nextDate", "blocker", "scheduleEffect", "assertedBy", "attestationOwner", "attestationDate", "attestationQualification"]


def export(forms, assignment, role="contributor"):
    response = forms.actor(role).request(forms.route + "/exports/" + assignment, method="POST",
        body={"expectedRevision": forms.revision()}, headers={"Idempotency-Key": uuid4().hex})
    assert response[0] == 200, response[1]
    downloaded = raw_request(forms.actor(role), response[1]["downloadUrl"])
    assert downloaded[0] == 200
    return response[1], downloaded[1]


def preview(forms, assignment, payload, role="contributor", expected=200):
    response = raw_request(forms.actor(role), forms.route + "/imports/" + assignment + "?expectedRevision=" + str(forms.revision()),
        data=payload, method="POST", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Idempotency-Key": uuid4().hex})
    assert response[0] == expected, (response[0], response[1])
    return response[1]


def commit(forms, value, choices=None, role="contributor", expected=200, revision=None, key=None):
    result = forms.actor(role).request(forms.route + "/imports/" + value["import"]["id"] + "/commit", method="POST",
        body={"expectedRevision": forms.revision() if revision is None else revision, "choices": choices or {}},
        headers={"Idempotency-Key": key or uuid4().hex})
    assert result[0] == expected, result[1]
    return result[1]


def unpack(payload):
    with ZipFile(BytesIO(payload)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def cells(content):
    root = ET.fromstring(content)
    return {cell.attrib["r"]: "".join(cell.itertext()) for cell in root.findall(f".//{{{NS}}}sheetData/{{{NS}}}row/{{{NS}}}c")}


def edit(payload, edits, part="xl/worksheets/sheet1.xml"):
    entries = unpack(payload)
    root = ET.fromstring(entries[part])
    for row in root.findall(f".//{{{NS}}}row"):
        rowcells = {cell.attrib["r"][0]: cell for cell in row.findall(f"{{{NS}}}c")}
        if "A" not in rowcells:
            continue
        qid = "".join(rowcells["A"].itertext())
        for field, value in edits.get(qid, {}).items():
            column = chr(ord("C") + FIELDS.index(field))
            cell = rowcells[column]
            for child in list(cell):
                cell.remove(child)
            cell.set("t", "inlineStr")
            ET.SubElement(ET.SubElement(cell, f"{{{NS}}}is"), f"{{{NS}}}t").text = value
    entries[part] = xml(root)
    return package(entries)


def parse(payload, legacy=False):
    result = subprocess.run(["dotnet", DLL, "--intake-workbook-parser" if legacy else "--questionnaire-workbook-parser"],
        input=payload, capture_output=True, timeout=20, env={**os.environ, "DOTNET_PROCESSOR_COUNT": "1"})
    return result.returncode, json.loads(result.stdout) if result.returncode == 0 else result.stderr.decode()


def test_full_export_exact_questions_definitions_and_literal_text(questionnaire_server):
    forms = Forms(questionnaire_server)
    assignment = forms.create()
    qid = "SRC-RFI-003/CQ-01"
    forms.command("questionnaire_save", assignment, {"answers": {qid: {"text": "=00123", "rationale": "+00001"}}}, "contributor")
    exported, payload = export(forms, assignment)
    entries = unpack(payload)
    response = cells(entries["xl/worksheets/sheet1.xml"])
    guide = cells(entries["xl/worksheets/sheet2.xml"])
    assigned = forms.detail(assignment)["assignment"]
    actual = assigned["template"]["questions"]
    assert len(actual) == 27
    for index, question in enumerate(actual, 7):
        assert response[f"A{index}"] == question["id"]
        assert response[f"B{index}"] == question["prompt"]
        assert guide[f"C{index}"] == question["responseType"]
        assert guide[f"F{index}"] == question["evidenceExpectation"]
        assert guide[f"G{index}"] == question["completionCriteria"]
        assert guide[f"E{index}"] == "\n".join(question["allowedValues"])
    pane = ET.fromstring(entries["xl/worksheets/sheet1.xml"]).find(f".//{{{NS}}}pane")
    assert pane.attrib["xSplit"] == "2" and pane.attrib["ySplit"] == "6"
    schedule_guide = guide["A5"]
    assert "Responses column J" in schedule_guide
    assert set(" | ".join(schedule_guide.splitlines()[1:-1]).split(" | ")) == set(assigned["scheduleEffects"])
    guide_row = ET.fromstring(entries["xl/worksheets/sheet2.xml"]).find(f".//{{{NS}}}row[@r='5']")
    assert float(guide_row.attrib["ht"]) >= 18 * len(schedule_guide.splitlines())
    code, decoded = parse(payload)
    assert code == 0
    assert decoded["exportId"] == exported["exportId"]
    answer = json.loads(decoded["answers"][qid])["fields"]
    assert answer["text"] == "=00123" and answer["rationale"] == "+00001"
    assert len(decoded["answers"]) == 27
    assert parse(payload, legacy=True)[0] == 2
    assert parse(package(parts()))[0] == 2


def test_partial_import_stages_then_applies_as_draft_with_unverified_attribution(questionnaire_server):
    forms = Forms(questionnaire_server)
    assignment = forms.create()
    _, payload = export(forms, assignment)
    qid = "SRC-RFI-003/CQ-01"
    returned = edit(payload, {qid: {"status": "answered", "text": "001234", "evidenceRefs": "synthetic-reference:owner-list", "assertedBy": "synthetic-demo:sponsor"}})
    staged = preview(forms, assignment, returned)
    assert "originalBase64" not in staged["import"]
    assert forms.detail(assignment)["assignment"]["answers"][qid]["status"] == "unanswered"
    result = commit(forms, staged)
    answer = result["assignment"]["answers"][qid]
    assert answer["text"] == "001234"
    assert answer["recordedBy"] == "synthetic-demo:contributor"
    assert answer["assertedBy"] == "Unverified workbook attribution: synthetic-demo:sponsor"
    assert result["assignment"]["status"] == "draft" and result["assignment"]["submission"] is None
    assert not result["validation"]["canSubmit"]
    assert all(gate["state"] == "not_submitted" for gate in forms.ws.refresh()["gates"])


def test_whole_question_conflict_does_not_mix_status_and_concurrent_text(questionnaire_server):
    forms = Forms(questionnaire_server)
    assignment = forms.create()
    _, payload = export(forms, assignment)
    qid = "SRC-RFI-003/CQ-01"
    forms.command("questionnaire_save", assignment, {"answers": {qid: {"text": "Current web statement", "status": "unknown"}}}, "contributor")
    staged = preview(forms, assignment, edit(payload, {qid: {"status": "answered", "text": "Returned offline statement"}}))
    change = next(change for change in staged["import"]["changes"] if change["questionId"] == qid)
    assert change["state"] == "conflict"
    commit(forms, staged, expected=400)
    accepted = commit(forms, staged, {qid: "current"})
    assert accepted["assignment"]["answers"][qid]["text"] == "Current web statement"
    assert accepted["assignment"]["answers"][qid]["status"] == "unknown"


def test_stale_unchanged_return_does_not_overwrite_current_even_if_chosen(questionnaire_server):
    forms = Forms(questionnaire_server)
    assignment = forms.create()
    qid = "SRC-RFI-003/CQ-01"
    forms.command("questionnaire_save", assignment, {"answers": {qid: {"text": "Export baseline"}}}, "contributor")
    _, payload = export(forms, assignment)
    forms.command("questionnaire_save", assignment, {"answers": {qid: {"text": "Current web statement"}}}, "contributor")
    staged = preview(forms, assignment, payload)
    assert all(change["state"] == "unchanged" for change in staged["import"]["changes"])
    result = commit(forms, staged, {qid: "returned"})
    assert result["assignment"]["answers"][qid]["text"] == "Current web statement"


def test_edit_after_preview_requires_fresh_preview_and_reassignment_revokes_exchange(questionnaire_server):
    forms = Forms(questionnaire_server)
    assignment = forms.create()
    exported, payload = export(forms, assignment)
    staged = preview(forms, assignment, edit(payload, {"SRC-RFI-003/CQ-01": {"text": "Returned statement"}}))
    forms.command("questionnaire_save", assignment, {"answers": {"SRC-RFI-003/CQ-02": {"text": "Concurrent unrelated answer"}}}, "contributor")
    commit(forms, staged, expected=409)
    forms.command("questionnaire_reassign", assignment, {"assignedTo": "synthetic-demo:contributor-two", "reason": "Synthetic route correction"})
    assert raw_request(forms.actor("contributor"), exported["downloadUrl"])[0] == 403
    preview(forms, assignment, payload, expected=403)
    preview(forms, assignment, payload, role="contributor-two", expected=409)
    commit(forms, staged, expected=403)


def test_wrong_assignment_and_changed_definition_rejected(questionnaire_server):
    forms = Forms(questionnaire_server)
    first, second = forms.create(), forms.create(label="Another synthetic deployment")
    _, payload = export(forms, first)
    preview(forms, second, payload, expected=400)
    entries = unpack(payload)
    root = ET.fromstring(entries["xl/worksheets/sheet1.xml"])
    cell = root.find(f".//{{{NS}}}c[@r='B7']/{{{NS}}}is/{{{NS}}}t")
    cell.text = "Different and unapproved question wording"
    entries["xl/worksheets/sheet1.xml"] = xml(root)
    result = preview(forms, first, package(entries), expected=400)
    assert result["error"]["code"] == "questionnaire_workbook_definition_changed"


def test_tampered_manifest_rejected_and_import_requires_current_write_authority(questionnaire_server):
    forms = Forms(questionnaire_server)
    assignment = forms.create()
    _, payload = export(forms, assignment)
    entries = unpack(payload)
    root = ET.fromstring(entries["xl/worksheets/sheet3.xml"])
    root.find(f".//{{{NS}}}c[@r='B5']/{{{NS}}}is/{{{NS}}}t").text = "SRC-RFI-027"
    entries["xl/worksheets/sheet3.xml"] = xml(root)
    result = preview(forms, assignment, package(entries), expected=400)
    assert result["error"]["code"] == "questionnaire_workbook_definition_changed"
    # Pre-parser authorization: even malformed bytes cannot consume the parser
    # lane for an unassigned contributor or a read-only assessment reviewer.
    for role in ("contributor-two", "reviewer", "sponsor"):
        preview(forms, assignment, b"not a workbook", role=role, expected=403)


def test_import_commit_replay_is_exact_and_does_not_duplicate_response_history(questionnaire_server):
    forms = Forms(questionnaire_server)
    assignment = forms.create()
    _, payload = export(forms, assignment)
    qid = "SRC-RFI-003/CQ-01"
    staged = preview(forms, assignment, edit(payload, {qid: {"text": "Synthetic offline return"}}))
    key, revision = uuid4().hex, forms.revision()
    first = commit(forms, staged, key=key, revision=revision)
    assert commit(forms, staged, key=key, revision=revision) == first
    commit(forms, staged, {qid: "current"}, key=key, revision=revision, expected=409)
    assert forms.detail(assignment)["revision"] == first["revision"]


def test_import_rejects_attribution_that_would_exceed_stored_field_limit(questionnaire_server):
    forms = Forms(questionnaire_server)
    assignment = forms.create()
    _, payload = export(forms, assignment)
    returned = edit(payload, {"SRC-RFI-003/CQ-01": {"text": "Synthetic answer", "assertedBy": "x" * 4096}})
    result = preview(forms, assignment, returned, expected=400)
    assert result["error"]["code"] == "questionnaire_answer_invalid"


@pytest.mark.parametrize("fault", ["formula", "external_link", "macro", "duplicate_question", "numeric_text", "unexpected_sheet"])
def test_closed_profile_rejects_active_or_ambiguous_content(questionnaire_server, fault):
    forms = Forms(questionnaire_server)
    assignment = forms.create()
    _, payload = export(forms, assignment)
    entries = unpack(payload)
    root = ET.fromstring(entries["xl/worksheets/sheet1.xml"])
    if fault in {"formula", "numeric_text"}:
        cell = root.find(f".//{{{NS}}}c[@r='D7']")
        for child in list(cell):
            cell.remove(child)
        cell.attrib.pop("t", None)
        if fault == "formula":
            ET.SubElement(cell, f"{{{NS}}}f").text = "1+1"
        ET.SubElement(cell, f"{{{NS}}}v").text = "2"
    elif fault == "duplicate_question":
        root.find(f".//{{{NS}}}c[@r='A8']/{{{NS}}}is/{{{NS}}}t").text = "SRC-RFI-003/CQ-01"
    elif fault == "external_link":
        entries["xl/externalLinks/externalLink1.xml"] = b"<externalLink/>"
    elif fault == "macro":
        entries["xl/vbaProject.bin"] = b"not executable"
    elif fault == "unexpected_sheet":
        entries["xl/worksheets/sheet4.xml"] = b"<worksheet/>"
    entries["xl/worksheets/sheet1.xml"] = xml(root)
    assert parse(package(entries))[0] == 2


def test_unresolved_import_can_submit_only_via_separate_authenticated_command(questionnaire_server):
    forms = Forms(questionnaire_server)
    assignment = forms.create()
    _, payload = export(forms, assignment)
    answers = all_unresolved(forms.detail(assignment))
    edits = {qid: {field: "\n".join(value) if isinstance(value, list) else value for field, value in answer.items()} for qid, answer in answers.items()}
    staged = preview(forms, assignment, edit(payload, edits))
    result = commit(forms, staged)
    assert result["validation"]["canSubmit"]
    assert result["assignment"]["status"] == "draft"
    submitted = forms.command("questionnaire_submit", assignment, role="contributor")
    assert submitted["assignment"]["status"] == "submitted"
    assert len(submitted["assignment"]["submission"]["unresolvedQuestionIds"]) == 27
    assert all(gate["state"] == "not_submitted" for gate in forms.ws.refresh()["gates"])


@pytest.mark.skipif(os.environ.get("PQC_INTAKE_LIBREOFFICE_PROOF") != "1", reason="explicit local LibreOffice qualification opt-in")
def test_libreoffice_full_questionnaire_open_save_reimports_without_profile_relaxation(questionnaire_server, tmp_path):
    executable = shutil.which("libreoffice")
    assert executable, "installed LibreOffice required; no implicit installation"
    forms = Forms(questionnaire_server)
    assignment = forms.create()
    qid = "SRC-RFI-003/CQ-01"
    forms.command("questionnaire_save", assignment, {"answers": {qid: {"text": "001234 synthetic value", "rationale": "=literal not formula"}}}, "contributor")
    exported, payload = export(forms, assignment)
    source = tmp_path / "synthetic-questionnaire.xlsx"
    source.write_bytes(payload)
    output = tmp_path / "roundtrip"
    output.mkdir(mode=0o700)
    profile = tmp_path / "office-profile"
    profile.mkdir(mode=0o700)
    conversion = subprocess.run([executable, "-env:UserInstallation=" + profile.as_uri(), "--headless", "--convert-to", "xlsx", "--outdir", str(output), str(source)], capture_output=True, timeout=45)
    assert conversion.returncode == 0, "LibreOffice conversion failed (no payload output logged)"
    converted = output / source.name
    assert converted.is_file()
    code, decoded = parse(converted.read_bytes())
    assert code == 0, decoded
    assert decoded["exportId"] == exported["exportId"]
    original_code, original = parse(payload)
    assert original_code == 0 and decoded["answers"] == original["answers"]
    staged = preview(forms, assignment, converted.read_bytes())
    assert all(change["state"] == "unchanged" for change in staged["import"]["changes"])
