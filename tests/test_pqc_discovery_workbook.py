"""Five-question C# web/Excel equivalence and safely staged offline responses.

Explicit built DLL, isolated synthetic state, no install or external actions.
LibreOffice open/save qualification is opt-in and is not native Excel proof.
"""
from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import json
import shutil
import sqlite3
import subprocess
from uuid import uuid4
from urllib.error import HTTPError
from urllib.request import Request
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from tests.test_pqc_enterprise_demo_http import Client, Server, Workspace, fixture_input
from tests.test_pqc_intake_http import raw_request
from tests.test_pqc_intake_workbook import xml, package, parts

DLL = os.environ.get("PQC_ENTERPRISE_DEMO_DLL")
pytestmark = pytest.mark.skipif(not DLL, reason="explicit candidate DLL required; no implicit build")
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
FIELDS = ["status", "text", "reference", "assertedBy"]


@pytest.fixture
def discovery_app(tmp_path, fixture_input):
    app = Server(tmp_path, fixture_input)
    try:
        yield app.start()
    finally:
        app.stop()


class Discovery:
    def __init__(self, app):
        self.ws = Workspace(Client(app.origin).login(), "fresh")
        self.route = self.ws.route + "/discovery"

    def actor(self, role="analyst"):
        return self.ws.actor(role)

    def revision(self):
        return self.ws.refresh()["revision"]

    def command(self, operation, target=None, fields=None, role="analyst", expected=200):
        result = self.actor(role).request(self.route + "/commands", method="POST",
            body={"operation": operation, "targetId": target, "fields": fields or {}, "expectedRevision": self.revision()},
            headers={"Idempotency-Key": uuid4().hex})
        assert result[0] == expected, (operation, result[1])
        return result[1]

    def create(self, recipient="contributor"):
        self.command("discovery_create", fields={"title": "Synthetic first-contact discovery", "familyId": "traffic-termination", "assignedTo": "synthetic-demo:" + recipient})
        rows = self.ws.refresh()["discovery"]["requests"]
        return rows[-1]["id"]

    def detail(self, request, role="analyst"):
        response = self.actor(role).request(self.route + "/" + request)
        assert response[0] == 200, response[1]
        return response[1]

    def export(self, request):
        response = self.actor("contributor").request(self.route + "/exports/" + request, method="POST",
            body={"expectedRevision": self.revision()}, headers={"Idempotency-Key": uuid4().hex})
        assert response[0] == 200, response[1]
        downloaded = raw_request(self.actor("contributor"), response[1]["downloadUrl"])
        assert downloaded[0] == 200
        return response[1], downloaded[1]

    def preview(self, request, payload, role="contributor", expected=200):
        result = raw_request(self.actor(role), self.route + "/imports/" + request + "?expectedRevision=" + str(self.revision()),
            data=payload, method="POST", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Idempotency-Key": uuid4().hex})
        assert result[0] == expected, result[1]
        return result[1]

    def commit(self, staged, choices=None, role="contributor", expected=200, key=None, revision=None):
        result = self.actor(role).request(self.route + "/imports/" + staged["import"]["id"] + "/commit", method="POST",
            body={"expectedRevision": self.revision() if revision is None else revision, "choices": choices or {}}, headers={"Idempotency-Key": key or uuid4().hex})
        assert result[0] == expected, result[1]
        return result[1]


def unpack(payload):
    with ZipFile(BytesIO(payload)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def cells(payload):
    return {c.attrib["r"]: "".join(c.itertext()) for c in ET.fromstring(payload).findall(f".//{{{NS}}}sheetData/{{{NS}}}row/{{{NS}}}c")}


def edit(payload, changes):
    entries = unpack(payload)
    root = ET.fromstring(entries["xl/worksheets/sheet1.xml"])
    for row in root.findall(f".//{{{NS}}}row"):
        values = {cell.attrib["r"][0]: cell for cell in row.findall(f"{{{NS}}}c")}
        qid = "".join(values.get("A", ET.Element("blank")).itertext())
        for field, value in changes.get(qid, {}).items():
            cell = values[chr(ord("C") + FIELDS.index(field))]
            for child in list(cell):
                cell.remove(child)
            cell.set("t", "inlineStr")
            ET.SubElement(ET.SubElement(cell, f"{{{NS}}}is"), f"{{{NS}}}t").text = value
    entries["xl/worksheets/sheet1.xml"] = xml(root)
    return package(entries)


def parse(payload, mode="--discovery-workbook-parser"):
    result = subprocess.run(["dotnet", DLL, mode], input=payload, capture_output=True, timeout=20, env={**os.environ, "DOTNET_PROCESSOR_COUNT": "1"})
    return result.returncode, json.loads(result.stdout) if result.returncode == 0 else result.stderr.decode()


def test_export_is_exact_five_question_gui_analog_not_a_hidden_full_form(discovery_app):
    form = Discovery(discovery_app)
    request = form.create()
    exported, payload = form.export(request)
    detail = form.detail(request)
    entries = unpack(payload)
    responses, guide = cells(entries["xl/worksheets/sheet1.xml"]), cells(entries["xl/worksheets/sheet2.xml"])
    assert len(detail["request"]["questions"]) == 5
    for index, question in enumerate(detail["request"]["questions"]):
        assert responses[f"A{index + 7}"] == question["id"]
        assert responses[f"B{index + 7}"] == question["prompt"]
        assert guide[f"B{index + 10}"] == question["whyItMatters"]
        assert guide[f"C{index + 10}"] == "\n".join(question["examples"])
        assert guide[f"D{index + 10}"] == question["usefulResponse"]
    assert not any(key.startswith("A") and int(key[1:]) > 11 for key in responses)
    assert detail["guidance"]["introduction"] in responses["A2"]
    assert detail["guidance"]["handlingNotice"] == responses["A3"]
    assert detail["guidance"]["reviewNotice"] in responses["A5"]
    assert "deadlines are not required" in responses["A4"]
    assert "requesting evidence" not in responses["B11"]
    parsed, result = parse(payload)
    assert parsed == 0 and result["exportId"] == exported["exportId"]
    assert set(result["answers"]) == {f"DQ-{i:02d}" for i in range(1, 6)}
    assert all(set(json.loads(value)["fields"]) == set(FIELDS) for value in result["answers"].values())
    assert parse(payload, "--intake-workbook-parser")[0] == 2
    assert parse(payload, "--questionnaire-workbook-parser")[0] == 2
    assert parse(package(parts()))[0] == 2


def test_native_download_uses_only_session_cookie_and_preserves_snapshot(discovery_app):
    """An ordinary anchor cannot add the API client's Origin/CSRF headers.

    Prove the real attachment path with browser-shaped request headers; do not
    substitute a public URL, bypass authorization, or infer browser acceptance.
    """
    form = Discovery(discovery_app)
    request = form.create()
    exported, original = form.export(request)
    revision = form.revision()
    contributor = form.actor("contributor")
    native_request = Request(contributor.origin + exported["downloadUrl"], headers={
        "Accept": "*/*", "Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "navigate",
    })
    with contributor.opener.open(native_request, timeout=20) as response:
        assert response.status == 200
        assert response.headers["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        disposition = response.headers["Content-Disposition"]
        assert disposition.startswith("attachment;")
        assert "synthetic-five-question-discovery.xlsx" in disposition
        assert int(response.headers["Content-Length"]) == len(original)
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["Cache-Control"] == "no-store"
        assert "sandbox" not in response.headers["Content-Security-Policy"]
        assert response.read() == original
    assert form.revision() == revision
    assert form.detail(request)["request"]["status"] == "draft"
    for client, expected in ((Client(discovery_app.origin), 401),
                             (form.actor("contributor-two"), 403)):
        with pytest.raises(HTTPError) as error:
            client.opener.open(Request(client.origin + exported["downloadUrl"]), timeout=20)
        assert error.value.code == expected
        assert not error.value.headers.get("Content-Disposition")


def test_recognition_covers_all_runtime_families_and_is_not_assessment_evidence(discovery_app, fixture_input):
    form = Discovery(discovery_app)
    request = form.create()
    before = form.detail(request)
    recognition = before["recognition"]
    domains = recognition["domains"]
    assert [d["id"] for d in domains] == [f"area-{i:02d}" for i in range(1, 11)]
    families = [f for d in domains for f in d["families"]]
    expected = {p["family_id"] for p in json.loads(fixture_input.read_text())["sourceProfiles"]}
    assert len(families) == 27 and {f["id"] for f in families} == expected
    assert recognition["domain"]["id"] == "area-03"
    assert recognition["catalogVersion"] == "pqc.software-recognition.v1"
    assert len(recognition["catalogSha256"]) == 64
    assert "not a complete market inventory" in recognition["boundary"]
    for family in families:
        assert len(family["examples"]) >= 6
        assert len({e["name"].casefold() for e in family["examples"]}) == len(family["examples"])
        for example in family["examples"]:
            assert example["url"].startswith("https://")
            assert example["kind"] in {"COTS", "SaaS", "Open source", "Hardware/platform"}
    after = form.detail(request)
    assert after["revision"] == before["revision"]
    assert after["request"] == before["request"]
    assert len(after["request"]["questions"]) == 5


def test_domain_examples_on_first_sheet_and_complete_reference_in_same_export(discovery_app):
    form = Discovery(discovery_app)
    request = form.create()
    _, payload = form.export(request)
    recognition = form.detail(request)["recognition"]
    entries = unpack(payload)
    first = cells(entries["xl/worksheets/sheet1.xml"])
    guide = cells(entries["xl/worksheets/sheet2.xml"])
    reference = cells(entries["xl/worksheets/sheet3.xml"])
    assert guide["B1"] == "pqc.discovery.return.v2"
    assert recognition["domain"]["name"] in first["A2"]
    for family in recognition["domain"]["families"]:
        for example in family["examples"]:
            assert example["name"] in first["A2"]
    assert "Examples only, not confirmed enterprise products" in first["A2"]
    assert recognition["boundary"] == reference["A2"]
    assert recognition["catalogSha256"] in reference["A3"]
    rows = [(d["name"], f["name"], e) for d in recognition["domains"] for f in d["families"] for e in f["examples"]]
    for index, (domain, family, example) in enumerate(rows, 5):
        assert reference[f"A{index}"] == domain
        assert reference[f"B{index}"] == family
        assert reference[f"C{index}"] == example["name"]
        assert reference[f"D{index}"] == example["kind"]
        assert reference[f"E{index}"] == example["url"]
    original = parse(payload)
    assert original[0] == 0
    root = ET.fromstring(entries["xl/worksheets/sheet3.xml"])
    root.find(f".//{{{NS}}}c[@r='C5']/{{{NS}}}is/{{{NS}}}t").text = "Unverified edited recognition note"
    entries["xl/worksheets/sheet3.xml"] = xml(root)
    assert parse(package(entries)) == original, "Recognition text must never become an answer or enterprise fact"
    ET.SubElement(root.find(f".//{{{NS}}}c[@r='C5']"), f"{{{NS}}}f").text = "1+1"
    entries["xl/worksheets/sheet3.xml"] = xml(root)
    assert parse(package(entries))[0] == 2, "Reference sheets retain the no-formula boundary"


@pytest.mark.skipif(not os.environ.get("PQC_RECOGNITION_PREVIOUS_DLL"), reason="explicit previous release for genuine old-export qualification")
def test_pre_recognition_export_and_user_history_survive_upgrade(tmp_path, fixture_input):
    app = Server(tmp_path, fixture_input, dll=os.environ["PQC_RECOGNITION_PREVIOUS_DLL"])
    try:
        app.start()
        form = Discovery(app)
        request = form.create()
        form.command("discovery_save", request, {"answers": {"DQ-02": {"status": "referral", "text": "Synthetic prior referral"}}}, "contributor")
        export, old_bytes = form.export(request)
        old_detail = form.detail(request)
        assert cells(unpack(old_bytes)["xl/worksheets/sheet2.xml"])["B1"] == "pqc.discovery.return.v1"
        app.stop()
        app.dll = DLL
        app.start()
        form.actor().login()
        form.actor("contributor").login("contributor")
        current = form.detail(request)
        assert current["request"] == old_detail["request"]
        assert current["revision"] == old_detail["revision"]
        assert current["recognition"]["domain"]["id"] == "area-03"
        assert raw_request(form.actor("contributor"), export["downloadUrl"])[1] == old_bytes
        assert parse(old_bytes)[0] == 0
        imported = form.commit(form.preview(request, edit(old_bytes, {"DQ-03": {"reference": "synthetic-reference:prior-form"}})))
        assert imported["request"]["answers"]["DQ-02"] == old_detail["request"]["answers"]["DQ-02"]
        assert imported["request"]["answers"]["DQ-03"]["reference"] == "synthetic-reference:prior-form"
        assert imported["request"]["questions"] == old_detail["request"]["questions"]
        assert imported["request"]["status"] == "draft"
    finally:
        app.stop()


@pytest.mark.skipif(not os.environ.get("PQC_DISCOVERY_LEGACY_DLL"), reason="explicit preserved v1 DLL required for cross-release proof")
def test_v1_history_exports_and_return_survive_v2_guidance_upgrade(tmp_path, fixture_input):
    """Create history through the actual v1 API; upgrade only the isolated app.

    No test-only production endpoint or database-history rewrite is introduced.
    """
    app = Server(tmp_path, fixture_input, dll=os.environ["PQC_DISCOVERY_LEGACY_DLL"])
    try:
        app.start()
        form = Discovery(app)
        request = form.create()
        saved = form.command("discovery_save", request, {"answers": {
            "DQ-02": {"status": "referral", "text": "Synthetic original team referral"}}}, "contributor")
        assert saved["request"]["templateVersion"] == "pqc.discovery.v1"
        assert "before requesting evidence" in saved["request"]["questions"][-1]["prompt"]
        exported, original_bytes = form.export(request)
        submitted = form.command("discovery_submit", request, role="contributor")
        prior_request = submitted["request"]
        with sqlite3.connect(app.data / "enterprise-demo.sqlite3") as database:
            prior_history = database.execute(
                "SELECT revision,snapshot_sha256,snapshot_json FROM assessment_versions WHERE assessment_id=? ORDER BY revision",
                (form.ws.state["id"],)).fetchall()

        app.stop()
        app.dll = DLL
        app.start()
        form.actor().login()
        form.actor("contributor").login("contributor")
        upgraded = form.detail(request, "contributor")
        assert upgraded["request"] == prior_request
        assert upgraded["guidance"]["legacyNotice"].startswith("This saved form retains its original questions.")
        assert "you do not need to produce documents" in upgraded["guidance"]["legacyNotice"]
        assert "No further response is required now" in upgraded["guidance"]["submissionReceipt"]
        assert raw_request(form.actor("contributor"), exported["downloadUrl"])[1] == original_bytes

        reopened = form.command("discovery_reopen", request, {"reason": "Synthetic referral correction"})
        assert reopened["request"]["questions"] == prior_request["questions"]
        assert reopened["request"]["templateSha256"] == prior_request["templateSha256"]
        assert reopened["request"]["history"][-1]["previousSubmissionSha256"] == prior_request["submission"]["contentSha256"]
        returned = edit(original_bytes, {"DQ-03": {"reference": "synthetic-reference:existing-inventory"}})
        imported = form.commit(form.preview(request, returned))
        assert imported["request"]["templateVersion"] == "pqc.discovery.v1"
        assert imported["request"]["answers"]["DQ-02"] == prior_request["answers"]["DQ-02"]
        assert imported["request"]["answers"]["DQ-03"]["reference"] == "synthetic-reference:existing-inventory"
        _, refreshed_bytes = form.export(request)
        sheets = unpack(refreshed_bytes)
        responses = cells(sheets["xl/worksheets/sheet1.xml"])
        guide = cells(sheets["xl/worksheets/sheet2.xml"])
        assert imported["guidance"]["handlingNotice"] == responses["A3"]
        assert imported["guidance"]["legacyNotice"] in guide["A8"]
        assert responses["B11"] == prior_request["questions"][-1]["prompt"]
        assert parse(refreshed_bytes)[0] == 0
        assert form.detail(form.create())["request"]["templateVersion"] == "pqc.discovery.v2"
        assert raw_request(form.actor("contributor"), exported["downloadUrl"])[1] == original_bytes
        with sqlite3.connect(app.data / "enterprise-demo.sqlite3") as database:
            preserved_history = database.execute(
                "SELECT revision,snapshot_sha256,snapshot_json FROM assessment_versions WHERE assessment_id=? AND revision<=? ORDER BY revision",
                (form.ws.state["id"], submitted["revision"])).fetchall()
        assert preserved_history == prior_history
    finally:
        app.stop()


@pytest.mark.parametrize("status", ["unknown", "not_my_team", "referral"])
def test_partial_offline_contribution_can_submit_without_hidden_requirements(discovery_app, status):
    form = Discovery(discovery_app)
    request = form.create()
    _, payload = form.export(request)
    returned = edit(payload, {"DQ-02": {"status": status, "text": "Synthetic routing response", "assertedBy": "synthetic-demo:sponsor"}})
    staged = form.preview(request, returned)
    assert "originalBase64" not in staged["import"]
    assert form.detail(request)["request"]["answers"]["DQ-02"]["status"] == "unanswered"
    applied = form.commit(staged)
    answer = applied["request"]["answers"]["DQ-02"]
    assert applied["request"]["status"] == "draft" and applied["request"]["submission"] is None
    assert applied["validation"]["canSubmit"]
    assert answer["recordedBy"] == "synthetic-demo:contributor"
    assert answer["assertedBy"] == "Unverified workbook attribution: synthetic-demo:sponsor"
    assert all(value["status"] == "unanswered" for qid, value in applied["request"]["answers"].items() if qid != "DQ-02")
    submitted = form.command("discovery_submit", request, role="contributor")
    assert submitted["request"]["status"] == "submitted"
    state = form.ws.refresh()
    assert all(gate["state"] == "not_submitted" for gate in state["gates"])
    assert not state["discovery"]["investigations"]
    assert all(standard["status"] == "draft" for standard in state["discovery"]["standards"])
    assert state["questionnaires"]["assignments"] == [] and state["intake"]["requests"] == []


def test_three_way_merge_is_question_atomic_and_unchanged_return_cannot_restore_stale_values(discovery_app):
    form = Discovery(discovery_app)
    request = form.create()
    form.command("discovery_save", request, {"answers": {"DQ-01": {"text": "Export baseline"}}}, "contributor")
    _, payload = form.export(request)
    form.command("discovery_save", request, {"answers": {"DQ-01": {"text": "Current text", "status": "unknown"}}}, "contributor")
    unchanged = form.preview(request, payload)
    assert next(c for c in unchanged["import"]["changes"] if c["questionId"] == "DQ-01")["state"] == "unchanged"
    assert form.commit(unchanged, {"DQ-01": "returned"})["request"]["answers"]["DQ-01"]["text"] == "Current text"
    staged = form.preview(request, edit(payload, {"DQ-01": {"text": "Offline text", "status": "answered"}}))
    assert next(c for c in staged["import"]["changes"] if c["questionId"] == "DQ-01")["state"] == "conflict"
    form.commit(staged, expected=400)
    accepted = form.commit(staged, {"DQ-01": "current"})
    assert accepted["request"]["answers"]["DQ-01"]["status"] == "unknown"
    assert accepted["request"]["answers"]["DQ-01"]["text"] == "Current text"


def test_new_web_edit_invalidates_preview_and_import_commit_replay_is_exact(discovery_app):
    form = Discovery(discovery_app)
    request = form.create()
    _, payload = form.export(request)
    staged = form.preview(request, edit(payload, {"DQ-01": {"text": "Offline statement"}}))
    form.command("discovery_save", request, {"answers": {"DQ-03": {"reference": "synthetic-reference:list"}}}, "contributor")
    form.commit(staged, expected=409)
    refreshed = form.preview(request, edit(payload, {"DQ-01": {"text": "Offline statement"}}))
    key, revision = uuid4().hex, form.revision()
    first = form.commit(refreshed, key=key, revision=revision)
    assert form.commit(refreshed, key=key, revision=revision) == first
    form.commit(refreshed, {"DQ-01": "current"}, key=key, revision=revision, expected=409)


def test_scope_and_write_authorization_precede_workbook_parsing(discovery_app):
    form = Discovery(discovery_app)
    first = form.create()
    second = form.create()
    exported, payload = form.export(first)
    form.preview(second, payload, expected=400)
    for role in ("contributor-two", "reviewer", "sponsor"):
        form.preview(first, b"not a workbook", role=role, expected=403)
    assert raw_request(form.actor("contributor-two"), exported["downloadUrl"])[0] == 403


@pytest.mark.parametrize("fault", ["formula", "conditional_formula", "validation_formula", "numeric", "duplicate", "macro", "external_link", "manifest", "definition"])
def test_closed_profile_and_exact_definitions_reject_unsafe_or_misleading_returns(discovery_app, fault):
    form = Discovery(discovery_app)
    request = form.create()
    _, payload = form.export(request)
    entries = unpack(payload)
    root = ET.fromstring(entries["xl/worksheets/sheet1.xml"])
    if fault in {"formula", "numeric"}:
        cell = root.find(f".//{{{NS}}}c[@r='D7']")
        for child in list(cell):
            cell.remove(child)
        cell.attrib.pop("t", None)
        if fault == "formula":
            ET.SubElement(cell, f"{{{NS}}}f").text = "1+1"
        ET.SubElement(cell, f"{{{NS}}}v").text = "2"
    elif fault == "duplicate":
        root.find(f".//{{{NS}}}c[@r='A8']/{{{NS}}}is/{{{NS}}}t").text = "DQ-01"
    elif fault == "conditional_formula":
        conditional = ET.Element(f"{{{NS}}}conditionalFormatting", sqref="D7")
        rule = ET.SubElement(conditional, f"{{{NS}}}cfRule", type="expression", priority="1")
        ET.SubElement(rule, f"{{{NS}}}formula").text = "1=1"
        root.insert(list(root).index(root.find(f"{{{NS}}}pageMargins")), conditional)
    elif fault == "validation_formula":
        validations = ET.Element(f"{{{NS}}}dataValidations", count="1")
        validation = ET.SubElement(validations, f"{{{NS}}}dataValidation", type="custom", sqref="D7")
        ET.SubElement(validation, f"{{{NS}}}formula1").text = "1=1"
        root.insert(list(root).index(root.find(f"{{{NS}}}pageMargins")), validations)
    elif fault == "macro":
        entries["xl/vbaProject.bin"] = b"synthetic invalid part"
    elif fault == "external_link":
        entries["xl/externalLinks/externalLink1.xml"] = b"<externalLink/>"
    elif fault == "definition":
        root.find(f".//{{{NS}}}c[@r='B7']/{{{NS}}}is/{{{NS}}}t").text = "Unapproved different question"
    elif fault == "manifest":
        guide = ET.fromstring(entries["xl/worksheets/sheet2.xml"])
        guide.find(f".//{{{NS}}}c[@r='B4']/{{{NS}}}is/{{{NS}}}t").text = "discovery-other-request"
        entries["xl/worksheets/sheet2.xml"] = xml(guide)
    entries["xl/worksheets/sheet1.xml"] = xml(root)
    returned = package(entries)
    if fault in {"manifest", "definition"}:
        result = form.preview(request, returned, expected=400)
        assert result["error"]["code"] == "discovery_workbook_definition_changed"
    else:
        code, error = parse(returned)
        assert code == 2
        if fault in {"conditional_formula", "validation_formula"}:
            assert error == "workbook_formula_not_allowed"


def test_literal_leading_zeros_and_formula_looking_text_survive_without_execution(discovery_app):
    form = Discovery(discovery_app)
    request = form.create()
    _, payload = form.export(request)
    staged = form.preview(request, edit(payload, {"DQ-01": {"text": "001234", "reference": "=literal-reference"}}))
    answer = form.commit(staged)["request"]["answers"]["DQ-01"]
    assert answer["text"] == "001234" and answer["reference"] == "=literal-reference"


@pytest.mark.skipif(os.environ.get("PQC_INTAKE_LIBREOFFICE_PROOF") != "1", reason="explicit installed LibreOffice qualification opt-in")
def test_libreoffice_open_save_preserves_five_question_form(discovery_app, tmp_path):
    office = shutil.which("libreoffice")
    assert office, "installed LibreOffice required; no implicit installation"
    form = Discovery(discovery_app)
    request = form.create()
    form.command("discovery_save", request, {"answers": {"DQ-01": {"text": "001234 synthetic", "reference": "=literal"}}}, "contributor")
    _, payload = form.export(request)
    source = tmp_path / "synthetic-discovery.xlsx"
    source.write_bytes(payload)
    output, profile = tmp_path / "converted", tmp_path / "office-profile"
    output.mkdir(mode=0o700)
    profile.mkdir(mode=0o700)
    run = subprocess.run([office, "-env:UserInstallation=" + profile.as_uri(), "--headless", "--convert-to", "xlsx", "--outdir", str(output), str(source)], capture_output=True, timeout=45)
    assert run.returncode == 0, "LibreOffice conversion failed (no payload output logged)"
    result = output / source.name
    assert result.is_file()
    original_code, original = parse(payload)
    saved_code, saved = parse(result.read_bytes())
    assert original_code == 0 and saved_code == 0, saved
    assert original == saved
    staged = form.preview(request, result.read_bytes())
    assert all(change["state"] == "unchanged" for change in staged["import"]["changes"])
