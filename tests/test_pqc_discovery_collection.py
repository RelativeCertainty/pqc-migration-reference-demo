"""One consolidated question collection and 27 assignment-bound Excel forms.

Exercise the actual C# HTTP authority against isolated synthetic SQLite state.
An explicit candidate DLL is required: no implicit builds, installs, public
requests, production data, email delivery, or owner-acceptance claims.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from base64 import b64encode
from hashlib import sha256
from io import BytesIO
import json
import os
import sqlite3
from uuid import uuid4
from urllib.request import Request
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from tests.test_pqc_enterprise_demo_http import Client, Server, fixture_input
from tests.test_pqc_discovery_workbook import Discovery, cells, edit, parse, unpack
from tests.test_pqc_intake_http import raw_request

DLL = os.environ.get("PQC_ENTERPRISE_DEMO_DLL")
pytestmark = pytest.mark.skipif(not DLL, reason="explicit candidate DLL required; no implicit build")
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
QUESTION_IDS = [f"DQ-{i:02d}" for i in range(1, 6)]
EXCEL_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
def collection_app(tmp_path, fixture_input):
    app = Server(tmp_path, fixture_input)
    try:
        yield app.start()
    finally:
        app.stop()


class Collection(Discovery):
    def catalog(self, role="analyst", expected=200):
        response = self.actor(role).request(self.route + "/catalog")
        assert response[0] == expected, response[1]
        return response[1]

    def prepare(self, recipient="contributor", *, role="analyst", expected=200,
                revision=None, key=None, extra=None):
        body = {"expectedRevision": self.revision() if revision is None else revision,
                "assignedTo": "synthetic-demo:" + recipient, **(extra or {})}
        response = self.actor(role).request(self.route + "/collections", method="POST",
            body=body, headers={"Idempotency-Key": key or uuid4().hex})
        assert response[0] == expected, response[1]
        return response[1]

    def package(self, collection_id, *, role="analyst", expected=200,
                revision=None, key=None, extra=None):
        response = self.actor(role).request(self.route + "/collections/" + collection_id + "/exports",
            method="POST", body={"expectedRevision": self.revision() if revision is None else revision,
                                  **(extra or {})},
            headers={"Idempotency-Key": key or uuid4().hex})
        assert response[0] == expected, response[1]
        return response[1]

    def prepared(self, recipient="contributor"):
        catalog = self.prepare(recipient)
        return next(c for c in catalog["collections"] if c["assignedTo"] == "synthetic-demo:" + recipient)

    def exported(self, collection_id):
        catalog = self.package(collection_id)
        return next(c for c in catalog["collections"] if c["id"] == collection_id)["packages"][-1]

    def download(self, path, *, role="contributor", expected=200):
        response = raw_request(self.actor(role), path)
        assert response[0] == expected, response[1] if expected != 200 else "download failed"
        return response


def package_collection(catalog, collection_id):
    return next(c for c in catalog["collections"] if c["id"] == collection_id)


def assert_workbook_only_text(payload):
    entries = unpack(payload)
    assert not any("vbaProject" in name or "externalLinks" in name for name in entries)
    for name, value in entries.items():
        if name.endswith(".rels"):
            assert all(r.attrib.get("TargetMode") != "External" for r in ET.fromstring(value))
        if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"):
            root = ET.fromstring(value)
            assert not root.findall(f".//{{{NS}}}f")
            assert not root.findall(f".//{{{NS}}}formula")
            assert not root.findall(f".//{{{NS}}}formula1")
            assert not root.findall(f".//{{{NS}}}formula2")


def test_catalog_has_ten_domains_twenty_seven_five_question_forms_without_creating_work(collection_app, fixture_input):
    form = Collection(collection_app)
    before = form.ws.refresh()
    catalog = form.catalog()
    assert catalog["canPrepare"] and catalog["collections"] == []
    assert [d["id"] for d in catalog["domains"]] == [f"area-{i:02d}" for i in range(1, 11)]
    forms = [f for domain in catalog["domains"] for f in domain["forms"]]
    expected = {p["family_id"] for p in json.loads(fixture_input.read_text())["sourceProfiles"]}
    assert len(forms) == 27 and {f["familyId"] for f in forms} == expected
    assert all([q["id"] for q in f["questions"]] == QUESTION_IDS for f in forms)
    assert len({tuple(q["prompt"] for q in f["questions"]) for f in forms}) == 1
    assert form.ws.refresh() == before, "Browsing the catalog must not assign or submit 27 tasks"
    assert raw_request(Client(collection_app.origin), form.route + "/catalog")[0] == 401


def test_complete_archive_matches_all_assigned_forms_exact_questions_and_242_examples(collection_app):
    form = Collection(collection_app)
    collection = form.prepared()
    assert len(collection["requests"]) == 27
    assert len({r["requestId"] for r in collection["requests"]}) == 27
    assert len({r["familyId"] for r in collection["requests"]}) == 27
    package = form.exported(collection["id"])
    assert len(package["forms"]) == 27
    archive_bytes = form.download(package["zipUrl"])[1]
    index_bytes = form.download(package["indexUrl"])[1]
    with ZipFile(BytesIO(archive_bytes)) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert len(names) == len(set(names)) == 28
        assert set(names) == {"00_Consolidated_Questions.xlsx", *(f["filename"] for f in package["forms"])}
        assert all(not name.startswith("/") and ".." not in name.split("/") for name in names)
        assert archive.read("00_Consolidated_Questions.xlsx") == index_bytes
        details = {}
        for entry in package["forms"]:
            individual = archive.read(entry["filename"])
            assert sha256(individual).hexdigest() == entry["sha256"]
            assert form.download(entry["downloadUrl"])[1] == individual
            detail = form.detail(entry["requestId"], "contributor")
            details[entry["familyId"]] = detail
            assert detail["request"]["familyId"] == entry["familyId"]
            assert entry["filename"] == f'{detail["recognition"]["domain"]["id"]}/{entry["familyId"]}.xlsx'
            worksheet = unpack(individual)
            answers = cells(worksheet["xl/worksheets/sheet1.xml"])
            guide = cells(worksheet["xl/worksheets/sheet2.xml"])
            assert guide["B3"] == form.ws.state["id"]
            assert guide["B4"] == entry["requestId"]
            assert guide["B5"] == detail["request"]["templateVersion"]
            assert guide["B6"] == detail["request"]["templateSha256"]
            for row, question in enumerate(detail["request"]["questions"], 7):
                assert answers[f"A{row}"] == question["id"]
                assert answers[f"B{row}"] == question["prompt"]
                assert guide[f"B{row + 3}"] == question["whyItMatters"]
                assert guide[f"C{row + 3}"] == "\n".join(question["examples"])
                assert guide[f"D{row + 3}"] == question["usefulResponse"]
            assert [answers[f"A{row}"] for row in range(7, 12)] == QUESTION_IDS
            assert not any(cell.startswith("A") and int(cell[1:]) > 11 for cell in answers)
            for family in detail["recognition"]["domain"]["families"]:
                assert all(example["name"] in answers["A2"] for example in family["examples"])
            parsed, content = parse(individual)
            assert parsed == 0, content
            assert content["exportId"] == guide["B2"]
            assert set(content["answers"]) == set(QUESTION_IDS)
            assert_workbook_only_text(individual)
    assert set(details) == {r["familyId"] for r in collection["requests"]}
    catalog = form.catalog()
    for domain in catalog["domains"]:
        for catalog_form in domain["forms"]:
            assert catalog_form["questions"] == details[catalog_form["familyId"]]["request"]["questions"]
    assert_workbook_only_text(index_bytes)
    index = unpack(index_bytes)
    sheets = ET.fromstring(index["xl/workbook.xml"]).findall(f"{{{NS}}}sheets/{{{NS}}}sheet")
    assert [sheet.attrib["name"] for sheet in sheets] == ["Start here", "All questions", "Software examples"]
    directory = cells(index["xl/worksheets/sheet1.xml"])
    questions = cells(index["xl/worksheets/sheet2.xml"])
    examples = cells(index["xl/worksheets/sheet3.xml"])
    assert "REFERENCE ONLY" in directory["A4"]
    assert "do not return this overview" in directory["A4"]
    assert "27 software classes" in directory["A2"]
    assert "five core questions" in directory["A2"]
    assert "not 135 different questions" in directory["A2"]
    recognition = next(iter(details.values()))["recognition"]
    flattened = [(domain, family) for domain in recognition["domains"] for family in domain["families"]]
    exported = {entry["familyId"]: entry for entry in package["forms"]}
    qrow = 5
    for index_row, (domain, family) in enumerate(flattened, 9):
        request = details[family["id"]]["request"]
        entry = exported[family["id"]]
        assert directory[f"A{index_row}"] == domain["name"]
        assert directory[f"B{index_row}"] == request["familyName"]
        assert directory[f"C{index_row}"] == entry["filename"]
        assert directory[f"D{index_row}"] == "draft"
        assert directory[f"E{index_row}"] == request["id"]
        assert entry["sha256"] in directory[f"F{index_row}"]
        for question in request["questions"]:
            assert questions[f"A{qrow}"] == domain["name"]
            assert questions[f"B{qrow}"] == request["familyName"]
            assert questions[f"C{qrow}"] == question["id"]
            assert questions[f"D{qrow}"] == question["prompt"]
            assert questions[f"E{qrow}"] == question["usefulResponse"]
            assert questions[f"F{qrow}"] == question["whyItMatters"]
            assert questions[f"G{qrow}"] == "; ".join(question["examples"])
            qrow += 1
    assert qrow == 140
    assert not any(key.startswith("A") and int(key[1:]) >= qrow for key in questions)
    reference_rows = [(domain, family, example) for domain, family in flattened for example in family["examples"]]
    assert len(reference_rows) == 242
    assert examples["A2"] == recognition["boundary"]
    assert recognition["catalogSha256"] in examples["A3"]
    for row, (domain, family, example) in enumerate(reference_rows, 5):
        assert examples[f"A{row}"] == domain["name"]
        assert examples[f"B{row}"] == family["name"]
        assert examples[f"C{row}"] == example["name"]
        assert examples[f"D{row}"] == example["kind"]
        assert examples[f"E{row}"] == example["url"]
    for parser in ("--discovery-workbook-parser", "--intake-workbook-parser", "--questionnaire-workbook-parser"):
        assert parse(index_bytes, parser)[0] == 2, "Consolidated overview is not an answer-return profile"


def test_prepare_is_one_atomic_revision_with_no_reuse_or_submission_of_prior_work(collection_app):
    form = Collection(collection_app)
    old_request = form.create()
    form.command("discovery_save", old_request, {"answers": {
        "DQ-02": {"status": "referral", "text": "Synthetic existing referral"}}}, "contributor")
    old_export, old_bytes = form.export(old_request)
    old_detail = form.detail(old_request)["request"]
    prior = form.ws.refresh()
    catalog = form.prepare()
    assert catalog["revision"] == prior["revision"] + 1
    state = form.ws.refresh()
    requests = state["discovery"]["requests"]
    assert len(requests) == 28
    assert form.detail(old_request)["request"] == old_detail
    assert form.download(old_export["downloadUrl"])[1] == old_bytes
    new = [r for r in requests if r["id"] != old_request]
    assert len({r["id"] for r in new}) == 27
    assert len({r["familyId"] for r in new}) == 27
    assert all(r["assignedTo"] == "synthetic-demo:contributor" for r in new)
    for request in new:
        assert request["status"] == "draft" and request["submission"] is None
        assert request["history"] == [] and request["productRefs"] == []
        assert [q["id"] for q in request["questions"]] == QUESTION_IDS
        assert set(request["answers"]) == set(QUESTION_IDS)
        assert all(answer["status"] == "unanswered" for answer in request["answers"].values())
    assert state["gates"] == prior["gates"]
    assert state["discovery"]["standards"] == prior["discovery"]["standards"]
    assert state["discovery"]["investigations"] == prior["discovery"]["investigations"]
    assert state["questionnaires"] == prior["questionnaires"]
    assert state["intake"] == prior["intake"]
    assert len(catalog["collections"]) == 1


def test_prepare_replay_and_duplicate_recipient_do_not_create_a_second_27_requests(collection_app):
    form = Collection(collection_app)
    key, revision = uuid4().hex, form.revision()
    first = form.prepare(key=key, revision=revision)
    assert form.prepare(key=key, revision=revision) == first
    form.prepare("contributor-two", key=key, revision=revision, expected=409)
    form.prepare(expected=409)
    assert len(form.ws.refresh()["discovery"]["requests"]) == 27
    assert len(form.catalog()["collections"]) == 1
    assert form.revision() == revision + 1


def test_stale_and_concurrent_collection_commands_cannot_leave_partial_requests(collection_app):
    form = Collection(collection_app)
    stale = form.revision()
    form.create()
    before = form.ws.refresh()
    form.prepare(revision=stale, expected=409)
    assert form.ws.refresh() == before
    second = Client(collection_app.origin).login()
    revision = form.revision()
    body = {"expectedRevision": revision, "assignedTo": "synthetic-demo:contributor"}
    def create(client):
        return client.request(form.route + "/collections", method="POST", body=body,
                              headers={"Idempotency-Key": uuid4().hex})[0]
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(create, [form.actor(), second])) == [200, 409]
    assert len(form.ws.refresh()["discovery"]["requests"]) == 28
    assert form.revision() == revision + 1


def test_collection_commands_are_closed_and_only_the_assessment_lead_can_prepare(collection_app):
    form = Collection(collection_app)
    before = form.ws.refresh()
    for role in ("contributor", "contributor-two", "reviewer", "sponsor", "viewer"):
        form.prepare(role=role, expected=403)
    form.prepare(extra={"principalId": "synthetic-demo:analyst"}, expected=400)
    form.prepare("not-a-recipient", expected=400)
    body = {"expectedRevision": form.revision(), "assignedTo": "synthetic-demo:contributor"}
    for actor, headers, expected in ((Client(collection_app.origin), {"Idempotency-Key": uuid4().hex}, 401),
            (form.actor(), {"Idempotency-Key": uuid4().hex, "X-PQC-CSRF": "wrong"}, 403)):
        assert actor.request(form.route + "/collections", method="POST", body=body, headers=headers)[0] == expected
    assert form.ws.refresh() == before
    created = form.prepared()
    for role in ("contributor", "contributor-two", "reviewer", "sponsor", "viewer"):
        form.package(created["id"], role=role, expected=403)
    form.package(created["id"], extra={"assignedTo": "synthetic-demo:contributor-two"}, expected=400)
    assert package_collection(form.catalog(), created["id"])["packages"] == []


def test_collection_list_and_all_downloads_remain_private_to_recipient_and_assessment(collection_app):
    form = Collection(collection_app)
    legacy_request = form.create()
    legacy_export, legacy_bytes = form.export(legacy_request)
    first = form.prepared()
    exported = form.exported(first["id"])
    second = form.prepared("contributor-two")
    assert {c["id"] for c in form.catalog()["collections"]} == {first["id"], second["id"]}
    for role, wanted, excluded in (("contributor", first, second), ("contributor-two", second, first)):
        view = form.catalog(role)
        assert not view["canPrepare"]
        assert [c["id"] for c in view["collections"]] == [wanted["id"]]
        assert excluded["id"] not in json.dumps(view)
    other = Collection(collection_app)
    for path in [exported["zipUrl"], exported["indexUrl"], exported["forms"][0]["downloadUrl"]]:
        form.download(path)
        form.download(path, role="contributor-two", expected=403)
        for role in ("reviewer", "sponsor", "viewer"):
            form.download(path, role=role, expected=403)
        assert raw_request(Client(collection_app.origin), path)[0] == 401
        transplanted = path.replace(form.ws.route, other.ws.route, 1)
        response = raw_request(other.actor(), transplanted)
        assert response[0] in (400, 403, 404)
        assert not response[2].get("Content-Disposition")
    assert all(c["id"] not in json.dumps(other.catalog()) for c in (first, second))
    # New private package bindings must not rewrite the prior individual-export
    # access model or silently invalidate already distributed legacy copies.
    for role in ("reviewer", "sponsor", "viewer"):
        assert form.download(legacy_export["downloadUrl"], role=role)[1] == legacy_bytes


def test_individual_from_collection_has_real_three_way_return_and_does_not_auto_submit(collection_app):
    form = Collection(collection_app)
    collection = form.prepared()
    package = form.exported(collection["id"])
    entry = next(f for f in package["forms"] if f["familyId"] == "traffic-termination")
    original = form.download(entry["downloadUrl"])[1]
    request = entry["requestId"]
    form.command("discovery_save", request, {"answers": {
        "DQ-02": {"status": "referral", "text": "Synthetic current team"}}}, "contributor")
    returned = edit(original, {"DQ-02": {"status": "referral", "text": "Synthetic offline team"}})
    staged = form.preview(request, returned)
    assert next(c for c in staged["import"]["changes"] if c["questionId"] == "DQ-02")["state"] == "conflict"
    assert form.detail(request)["request"]["answers"]["DQ-02"]["text"] == "Synthetic current team"
    form.commit(staged, expected=400)
    result = form.commit(staged, {"DQ-02": "returned"})
    assert result["request"]["answers"]["DQ-02"]["text"] == "Synthetic offline team"
    assert result["request"]["answers"]["DQ-02"]["recordedBy"] == "synthetic-demo:contributor"
    assert result["request"]["status"] == "draft" and result["request"]["submission"] is None
    assert result["validation"]["canSubmit"]
    assert form.download(entry["downloadUrl"])[1] == original
    index_bytes = form.download(package["indexUrl"])[1]
    form.preview(request, index_bytes, expected=400)
    assert all(g["state"] == "not_submitted" for g in form.ws.refresh()["gates"])


def test_private_package_bytes_cannot_leak_through_assessment_read_command_or_replay(collection_app):
    form = Collection(collection_app)
    collection = form.prepared()
    package = form.exported(collection["id"])
    entry = package["forms"][0]
    original = form.download(entry["downloadUrl"])[1]
    form.preview(entry["requestId"], edit(original, {"DQ-01": {"status": "unknown"}}))
    protected = [b64encode(form.download(path)[1]).decode() for path in
        (package["zipUrl"], package["indexUrl"], entry["downloadUrl"])]

    def check_projection(view):
        assert view["discovery"]["collections"] == []
        assert view["discovery"]["exchange"]["exports"] == []
        assert view["discovery"]["exchange"]["imports"] == []
        encoded = json.dumps(view)
        assert not any(value in encoded for value in protected)
        assert package["id"] not in encoded
        # Assessment reviewers retain their ordinary question/response access;
        # this boundary protects the new distributable packages, not all facts.
        assert len(view["discovery"]["requests"]) == 27

    for role in ("reviewer", "sponsor", "viewer", "risk-lead"):
        status, view, _ = form.actor(role).request(form.ws.route)
        assert status == 200
        check_projection(view)
    risk = form.actor("risk-lead")
    body = {"operation": "set_method", "targetId": None, "expectedRevision": form.revision(), "fields": {
        "name": "Synthetic draft method", "description": "Future review basis only; not accepted reliance.",
        "confidenceRules": "Qualify unsupported conclusions.", "prioritizationRules": "No invented enterprise scores."}}
    headers = {"Idempotency-Key": uuid4().hex}
    first = risk.request(form.ws.route + "/commands", method="POST", body=body, headers=headers)
    assert first[0] == 200, first[1]
    check_projection(first[1])
    replay = risk.request(form.ws.route + "/commands", method="POST", body=body, headers=headers)
    assert replay[0] == 200 and replay[1] == first[1]
    check_projection(replay[1])
    assert form.download(entry["downloadUrl"])[1] == original
    assert len(form.catalog()["collections"]) == 1


def test_package_replay_after_edit_returns_original_manifest_and_immutable_bytes(collection_app):
    form = Collection(collection_app)
    collection = form.prepared()
    key, revision = uuid4().hex, form.revision()
    first = form.package(collection["id"], key=key, revision=revision)
    package = package_collection(first, collection["id"])["packages"][-1]
    zip_bytes = form.download(package["zipUrl"])[1]
    index_bytes = form.download(package["indexUrl"])[1]
    entry = package["forms"][0]
    form.command("discovery_save", entry["requestId"], {"answers": {
        "DQ-01": {"status": "unknown"}}}, "contributor")
    replay = form.package(collection["id"], key=key, revision=revision)
    assert replay == first
    assert form.download(package["zipUrl"])[1] == zip_bytes
    assert form.download(package["indexUrl"])[1] == index_bytes
    form.package(collection["id"], key=key, revision=form.revision(), expected=409)
    assert len(package_collection(form.catalog(), collection["id"])["packages"]) == 1


def test_package_limit_and_stale_command_fail_without_partial_exports(collection_app):
    form = Collection(collection_app)
    collection = form.prepared()
    stale = form.revision()
    first = form.exported(collection["id"])
    before = form.ws.refresh()
    form.package(collection["id"], revision=stale, expected=409)
    assert form.ws.refresh() == before
    form.exported(collection["id"])
    form.exported(collection["id"])
    before = form.ws.refresh()
    form.package(collection["id"], expected=409)
    assert form.ws.refresh() == before
    assert len(package_collection(form.catalog(), collection["id"])["packages"]) == 3
    assert form.download(first["zipUrl"])[0] == 200


def test_collection_export_preserves_submitted_response_as_read_only_archive(collection_app):
    form = Collection(collection_app)
    collection = form.prepared()
    original = form.exported(collection["id"])
    original_bytes = form.download(original["zipUrl"])[1]
    request = collection["requests"][-1]["requestId"]
    form.command("discovery_save", request, {"answers": {"DQ-01": {"status": "unknown"}}}, "contributor")
    submitted = form.command("discovery_submit", request, role="contributor")
    archived = form.exported(collection["id"])
    assert form.detail(request)["request"] == submitted["request"]
    assert len(package_collection(form.catalog(), collection["id"])["packages"]) == 2
    entry = next(e for e in archived["forms"] if e["requestId"] == request)
    workbook = form.download(entry["downloadUrl"])[1]
    assert cells(unpack(workbook)["xl/worksheets/sheet1.xml"])["C7"] == "unknown"
    assert parse(workbook)[0] == 0
    form.preview(request, edit(workbook, {"DQ-01": {"status": "answered", "text": "Unadmitted return"}}), expected=403)
    assert form.detail(request)["request"] == submitted["request"]
    assert form.download(original["zipUrl"])[1] == original_bytes


def test_one_member_export_capacity_rejects_whole_package_without_partial_state(collection_app):
    form = Collection(collection_app)
    collection = form.prepared()
    original = form.exported(collection["id"])
    original_bytes = form.download(original["zipUrl"])[1]
    # The final member already has one collection export. Exhaust its remaining
    # three individual slots, then require the next 27-member command to fail
    # without persisting even its earlier otherwise-eligible members.
    request = collection["requests"][-1]["requestId"]
    individual = [form.export(request) for _ in range(3)]
    before = form.ws.refresh()
    form.package(collection["id"], expected=409)
    assert form.ws.refresh() == before
    assert len(package_collection(form.catalog(), collection["id"])["packages"]) == 1
    assert form.download(original["zipUrl"])[1] == original_bytes
    for exported, workbook in individual:
        assert form.download(exported["downloadUrl"])[1] == workbook


def test_native_index_and_archive_downloads_are_authenticated_no_store_attachments(collection_app):
    form = Collection(collection_app)
    collection = form.prepared()
    package = form.exported(collection["id"])
    revision = form.revision()
    contributor = form.actor("contributor")
    for path, mime in ((package["zipUrl"], "application/zip"), (package["indexUrl"], EXCEL_TYPE)):
        expected = form.download(path)[1]
        # Native anchors send no application CSRF or Origin header on this GET.
        with contributor.opener.open(Request(contributor.origin + path, headers={"Accept": "*/*",
                "Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "navigate"}), timeout=30) as response:
            assert response.status == 200
            assert response.headers["Content-Type"] == mime
            assert response.headers["Content-Disposition"].startswith("attachment;")
            assert response.headers["Cache-Control"] == "no-store"
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            assert "sandbox" not in response.headers["Content-Security-Policy"]
            assert int(response.headers["Content-Length"]) == len(expected)
            assert response.read() == expected
    assert form.revision() == revision


def test_collection_and_package_bytes_survive_restart_with_exact_assessment_history(collection_app):
    form = Collection(collection_app)
    collection = form.prepared()
    package = form.exported(collection["id"])
    catalog = form.catalog()
    byte_snapshots = {path: form.download(path)[1] for path in (package["zipUrl"], package["indexUrl"],
        package["forms"][0]["downloadUrl"])}
    with sqlite3.connect(collection_app.data / "enterprise-demo.sqlite3") as database:
        history = database.execute("SELECT revision,snapshot_sha256,snapshot_json FROM assessment_versions "
            "WHERE assessment_id=? ORDER BY revision", (form.ws.state["id"],)).fetchall()
    collection_app.stop()
    collection_app.start()
    form.actor().login()
    form.actor("contributor").login("contributor")
    assert form.catalog() == catalog
    for path, original in byte_snapshots.items():
        assert form.download(path)[1] == original
    with sqlite3.connect(collection_app.data / "enterprise-demo.sqlite3") as database:
        assert database.execute("SELECT revision,snapshot_sha256,snapshot_json FROM assessment_versions "
            "WHERE assessment_id=? ORDER BY revision", (form.ws.state["id"],)).fetchall() == history


@pytest.mark.skipif(not os.environ.get("PQC_COLLECTION_PREVIOUS_DLL"),
                   reason="explicit pre-collection release required for real history-upgrade proof")
def test_previous_export_and_user_answers_survive_collection_upgrade(tmp_path, fixture_input):
    app = Server(tmp_path, fixture_input, dll=os.environ["PQC_COLLECTION_PREVIOUS_DLL"])
    try:
        app.start()
        form = Collection(app)
        request = form.create()
        form.command("discovery_save", request, {"answers": {
            "DQ-02": {"status": "referral", "text": "Synthetic pre-collection referral"}}}, "contributor")
        original_export, original_bytes = form.export(request)
        old_detail = form.detail(request)
        with sqlite3.connect(app.data / "enterprise-demo.sqlite3") as database:
            history = database.execute("SELECT revision,snapshot_sha256,snapshot_json FROM assessment_versions "
                "WHERE assessment_id=? ORDER BY revision", (form.ws.state["id"],)).fetchall()
        app.stop()
        app.dll = DLL
        app.start()
        form.actor().login()
        form.actor("contributor").login("contributor")
        assert form.detail(request) == old_detail
        assert form.download(original_export["downloadUrl"])[1] == original_bytes
        form.prepared()
        assert form.detail(request)["request"] == old_detail["request"]
        assert len(form.ws.refresh()["discovery"]["requests"]) == 28
        assert form.download(original_export["downloadUrl"])[1] == original_bytes
        staged = form.preview(request, edit(original_bytes, {"DQ-03": {"reference": "synthetic-reference:prior-list"}}))
        result = form.commit(staged)
        assert result["request"]["answers"]["DQ-02"] == old_detail["request"]["answers"]["DQ-02"]
        assert result["request"]["answers"]["DQ-03"]["reference"] == "synthetic-reference:prior-list"
        assert result["request"]["status"] == "draft"
        with sqlite3.connect(app.data / "enterprise-demo.sqlite3") as database:
            assert database.execute("SELECT revision,snapshot_sha256,snapshot_json FROM assessment_versions "
                "WHERE assessment_id=? AND revision<=? ORDER BY revision",
                (form.ws.state["id"], old_detail["revision"])).fetchall() == history
    finally:
        app.stop()
