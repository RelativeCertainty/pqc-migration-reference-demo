"""Real HTTP checks against the built C# server and an isolated synthetic DB.

Set PQC_ENTERPRISE_DEMO_DLL to the built DLL. No build, download, production
service, real credential, or external provider is accessed by these tests.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import time
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
import yaml

from scripts.build_pqc_enterprise_demo_fixture import prepare

ROOT = Path(__file__).resolve().parents[1]
DLL = os.environ.get("PQC_ENTERPRISE_DEMO_DLL")
pytestmark = pytest.mark.skipif(not DLL, reason="explicit built C# DLL required; no implicit build/download")


@pytest.fixture
def analysis_server(tmp_path, fixture_input):
    app = Server(tmp_path, fixture_input)
    try:
        yield app.start()
    finally:
        app.stop()


def test_analysis_projection_reconciles_and_filters(analysis_server, fixture_input):
    client = Client(analysis_server.origin).login()
    status, analysis, _ = client.request("/api/analysis")
    assert status == 200
    assert len(analysis["coverage"]) == 10
    assert len(analysis["filterOptions"]["families"]) == 27
    assert len(analysis["assets"]) == client.request("/api/dashboard")[1]["counts"]["assets"]
    subjects = {row["id"] for row in analysis["assets"]}
    observations = set()
    source_uses = json.loads(fixture_input.read_text())["riskReviews"]
    for asset in analysis["assets"]:
        observations.update(asset["observationRefs"])
    assert analysis["findings"]
    assert len({row["id"] for row in analysis["findings"]}) == len(analysis["findings"])
    assert analysis["summary"]["findings"] == len(analysis["findings"])
    for distribution in ("exposureCounts", "readinessCounts", "priorityCounts"):
        assert sum(row["count"] for row in analysis["summary"][distribution]) == len(analysis["findings"])
    for coverage in analysis["coverage"]:
        members = [row for row in analysis["assets"] if coverage["areaId"] in row["areaRefs"]]
        assert coverage["present"] == len(members)
        assert coverage["missing"] == sum(row["isContextOnly"] for row in members)
        assert coverage["stale"] == sum(row["isStale"] for row in members)
        assert coverage["disputed"] == sum(row["isDisputed"] for row in members)
    for finding in analysis["findings"]:
        assert finding["subjectId"] in subjects
        assert finding["observation"] and finding["implication"] and finding["recommendation"]
        assert finding["priorityRationale"] and finding["readiness"]
        assert set(finding["observationRefs"]) <= observations
        for group, reference in (("riskScenarios", "riskScenarioId"), ("businessImpacts", "impactId"),
                ("recommendations", "recommendationId"), ("decisions", "decisionId")):
            linked = next(row for row in analysis[group] if row["id"] == finding[reference])
            assert linked["subjectId"] == finding["subjectId"]
            assert linked["observationRefs"] == finding["observationRefs"]
        # A classical signature on one use must not turn a separate hybrid
        # exchange into a classical long-lived confidentiality scenario.
        if "store-now/decrypt-later" in finding["implication"]:
            assert any(use["subject_ref"] == finding["subjectId"]
                and use["algorithm_posture"] == "classical_method_review_candidate"
                and use["purpose"] == "key_establishment"
                and (use.get("confidentiality_days_remaining") or 0) >= 1825
                for use in source_uses)
    nodes = {row["id"] for row in analysis["graph"]["nodes"]}
    assert any(row["kind"] == "cryptographic_use" for row in analysis["graph"]["nodes"])
    for edge in analysis["graph"]["edges"]:
        assert edge["source"] in nodes and edge["target"] in nodes
    for dimension, options, field in (
        ("service", "services", "serviceIds"), ("owner", "owners", "ownerIds"),
        ("environment", "environments", "environments"), ("technology", "technologies", "technologies"),
        ("family", "families", "familyIds"),
    ):
        option = next((row for row in analysis["filterOptions"][options] if row["id"] != "unknown"), None)
        if option is None:
            continue  # unavailable business context must not be manufactured
        filtered = client.request("/api/analysis?" + urlencode({dimension: option["id"]}))[1]
        assert filtered["assets"]
        assert all(option["id"] in row[field] for row in filtered["assets"])
        selected = {row["id"] for row in filtered["assets"]}
        assert all(row["subjectId"] in selected for row in filtered["findings"])
        original_ids = {row["id"] for row in analysis["findings"] if row["subjectId"] in selected}
        assert {row["id"] for row in filtered["findings"]} == original_ids
    assert not client.request("/api/analysis?family=does-not-exist")[1]["assets"]
    assert client.request("/api/analysis?service=" + "x" * 161)[0] == 400


def test_local_actions_are_atomic_idempotent_and_not_acceptance(analysis_server, tmp_path):
    """Legacy writers are retired; durable edits require an assessment identity."""
    client = Client(analysis_server.origin).login()
    finding = client.request("/api/analysis")[1]["findings"][0]
    body = {"operation": "prepare_evidence_request", "disposition": None, "note": "Synthetic clarification", "expectedRevision": 0}
    route = "/api/actions/" + quote(finding["id"])
    assert client.request(route, method="POST", body=body, headers={"Idempotency-Key": "retired-action-write"})[0] == 409
    assert client.request(route)[1] == []
    assessment = Workspace(client, mode="fresh")
    before = assessment.state
    scope = scope_fields(assessment)
    payload = assessment.payload("update_scope", fields=scope)
    headers = {"Idempotency-Key": "new-scoped-command"}
    first = client.request(assessment.route + "/commands", method="POST", body=payload, headers=headers)
    assert first[0] == 200, first[1]
    assert first[1]["revision"] == before["revision"] + 1
    assert client.request(assessment.route + "/commands", method="POST", body=payload, headers=headers)[1] == first[1]
    changed = {**payload, "fields": {**scope, "objective": "Changed command"}}
    assert client.request(assessment.route + "/commands", method="POST", body=changed, headers=headers)[0] == 409
    assert client.request(assessment.route + "/commands", method="POST", body=payload, headers={"Idempotency-Key": "stale-scoped-command"})[0] == 409
    assert client.request(assessment.route + "/analysis")[1]["summary"]["assets"] == 0
    assert all(g["state"] == "not_submitted" for g in first[1]["gates"])
    analysis_server.stop()
    analysis_server.start()
    client.login()
    assert client.request(assessment.route)[1]["scope"]["objective"] == scope["objective"]
    assert len(client.request(assessment.route + "/runs")[1]) >= 2


def test_action_permissions_validation_and_concurrent_edits(analysis_server):
    client = Client(analysis_server.origin).login()
    ws = Workspace(client, mode="fresh")
    viewer = Client(analysis_server.origin).login("viewer")
    body = ws.payload("submit_gate", "PQC-G00")
    headers = {"Idempotency-Key": "permission-gate-proof"}
    assert viewer.request(ws.route + "/commands", method="POST", body=body, headers=headers)[0] == 403
    assert client.request(ws.route + "/commands", method="POST", body=body, headers={**headers, "X-PQC-CSRF": "wrong"})[0] == 403
    assert client.request(ws.route + "/commands", method="POST", body=ws.payload("execute_migration"), headers=headers)[0] == 403
    assert client.request(ws.route + "/commands", method="POST", body={**body, "principalId": "synthetic-demo:sponsor"}, headers=headers)[0] == 400
    scope = {**scope_fields(ws), "objective": "One concurrent winner"}
    body = ws.payload("update_scope", fields=scope)
    second = Client(analysis_server.origin).login()
    def update(item):
        index, actor = item
        return actor.request(ws.route + "/commands", method="POST", body=body, headers={"Idempotency-Key": f"concurrent-scope-{index}"})[0]
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(update, enumerate([client, second]))) == [200, 409]
    assert client.request(ws.route)[1]["revision"] == ws.state["revision"] + 1


def test_narrative_reports_are_readable_and_freeze_review_context(analysis_server):
    from tests.test_pqc_assessment_report_contract import assert_report_content, assert_safe_report_html
    ws = Workspace(Client(analysis_server.origin).login())
    p1 = ws.report("phase1")
    assert_report_content(p1["content"], phase="phase1")
    assert_safe_report_html(ws.client.request(ws.route + "/reports/" + p1["metadata"]["id"] + "/download?format=html")[1])
    ws.gate("PQC-P1-G03", report=p1["metadata"]["id"])
    ws.command("set_method", fields={"name": "Bounded scenario method", "description": "Assess role, information lifetime and conditional consequence.",
        "confidenceRules": "Missing or conflicting evidence requires qualification.", "prioritizationRules": "Exposure and readiness remain distinct."}, role="risk-lead")
    ws.gate("PQC-P2-G01")
    for package in ws.state["packages"]:
        if package["familyId"] not in ws.state["scope"]["includedFamilyIds"]:
            continue
        ws.command("submit_analysis", package["familyId"], {"scenario": "If classical key establishment protects long-lived information, recorded traffic may need prioritized review.",
            "businessImpact": "Confidentiality consequence requires business-owner confirmation.", "recommendation": "Corroborate the protection role and lifetime before a migration plan.",
            "priority": "planned_review", "rationale": "Bounded sample and source limitations.", "confidence": "limited",
            **unreported_business_context()}, role="risk-lead")
        recorded = next(p for p in ws.state["packages"] if p["familyId"] == package["familyId"])["analysis"]
        assert all(recorded.get(key) is None for key in unreported_business_context())
        ws.command("review_analysis", package["familyId"], decision_fields(), role="business-reviewer")
    ws.gate("PQC-P2-G02")
    p2 = ws.report("phase2", p1["metadata"]["id"], role="risk-lead")
    assert_report_content(p2["content"], phase="phase2")
    assert p2["content"]["manifest"]["selectedPhase1"]["reportId"] == p1["metadata"]["id"]
    assert p2["content"]["manifest"]["selectedPhase1"]["contentSha256"] == p1["metadata"]["contentSha256"]
    assert p2["content"]["scenarioRows"]
    for row in p2["content"]["scenarioRows"]:
        assert row["businessStatementBy"] == "No separate attributed business statement recorded"
        assert row["businessStatementDate"] == "Not recorded"
        assert row["scenarioState"] == "qualified"
    ws.gate("PQC-P2-G03", report=p2["metadata"]["id"])
    assert all(g["state"] in ("accepted", "qualified") for g in ws.state["gates"])
    assert ws.client.request(ws.route + "/reports/" + p2["metadata"]["id"])[1] == p2
    assert ws.client.request("/api/reports")[1] == []


class Client:
    def __init__(self, origin):
        self.origin = origin
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))
        self.csrf = None

    def request(self, path, *, method="GET", body=None, headers=None):
        header = {"Origin": self.origin}
        if body is not None:
            header["Content-Type"] = "application/json"
        if self.csrf:
            header["X-PQC-CSRF"] = self.csrf
        header.update(headers or {})
        data = json.dumps(body).encode() if body is not None else None
        request = Request(self.origin + path, data=data, headers=header, method=method)
        try:
            response = self.opener.open(request, timeout=10)
        except HTTPError as error:
            response = error
        content = response.read()
        parsed = json.loads(content) if "application/json" in response.headers.get("Content-Type", "") else content.decode()
        return response.status, parsed, response.headers

    def login(self, role="analyst"):
        status, session, _ = self.request("/api/session", method="POST", body={"role": role, "password": "synthetic-demo-only"})
        assert status == 200
        self.csrf = session["csrfToken"]
        return self


class Server:
    def __init__(self, folder, fixture, data=None, dll=None):
        self.dll = dll or DLL
        self.data = data or folder / "app-state"
        self.data.mkdir(mode=0o700, exist_ok=True)
        self.fixture = fixture
        self.web = folder / "web"
        self.web.mkdir(exist_ok=True)
        with socket.socket() as port_socket:
            port_socket.bind(("127.0.0.1", 0))
            self.port = port_socket.getsockname()[1]
        self.origin = f"http://127.0.0.1:{self.port}"
        self.process = None

    def start(self):
        self.process = subprocess.Popen([
            "dotnet", str(Path(self.dll).resolve()), "--data-dir", str(self.data),
            "--fixture", str(self.fixture), "--web-root", str(self.web),
            "--port", str(self.port),
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={**os.environ, "DOTNET_CLI_TELEMETRY_OPTOUT": "1", "DOTNET_PROCESSOR_COUNT": "1"})
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise AssertionError("isolated C# server exited before readiness")
            try:
                if Client(self.origin).request("/health/ready")[0] == 200:
                    return self
            except OSError:
                pass
            time.sleep(0.05)
        self.stop()
        raise AssertionError("isolated C# server readiness timeout")

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)


def decision_fields(decision="qualified"):
    return {"decision": decision, "rationale": "Synthetic review within the bounded sample.",
        "qualification": "Unknown enterprise population; no production acceptance.", "reviewDate": "2026-09-22"}


def unreported_business_context():
    """Current command fields, explicitly blank rather than fabricated testimony."""
    return {"protectedInformation": "", "lifetime": "", "assertedBy": "", "statementDate": "",
        "compatibilityConstraints": "", "vendorConstraints": "", "operationalConstraints": "",
        "responsibleFunction": "", "nextDecision": ""}


def scope_fields(ws):
    scope = {**ws.state["scope"], "objective": "Bounded synthetic assessment",
        "handling": "Synthetic references only, no external access.", "method": "Examine, attribute and qualify.",
        "cycleGoal": "Answer selected assessment questions.", "reviewDate": "2026-09-22"}
    scope.pop("revision", None)
    return scope


class Workspace:
    """Drive only public, authenticated assessment commands against a test DB."""
    def __init__(self, client, mode="worked_example", name="Isolated HTTP proof"):
        from uuid import uuid4
        self.client = client
        self.clients = {"analyst": client}
        self.key = uuid4().hex
        status, state, _ = client.request("/api/assessments", method="POST",
            body={"name": name, "mode": mode}, headers={"Idempotency-Key": self.key})
        assert status == 201, state
        self.state = state
        self.route = "/api/assessments/" + state["id"]
        self.counter = 0

    def refresh(self):
        status, self.state, _ = self.client.request(self.route)
        assert status == 200
        return self.state

    def actor(self, role):
        if role not in self.clients:
            self.clients[role] = Client(self.client.origin).login(role)
        return self.clients[role]

    def payload(self, operation, target=None, fields=None):
        return {"operation": operation, "targetId": target, "expectedRevision": self.state["revision"], "fields": fields or {}}

    def command(self, operation, target=None, fields=None, role="analyst"):
        self.refresh()
        self.counter += 1
        status, result, _ = self.actor(role).request(self.route + "/commands", method="POST",
            body=self.payload(operation, target, fields), headers={"Idempotency-Key": self.key + f"-{self.counter}"})
        assert status == 200, (operation, target, status, result)
        self.state = result
        return result

    def report(self, phase, parent=None, role="analyst"):
        fields = {"phase": phase}
        if parent is not None:
            fields["phase1ReportId"] = parent
        self.command("generate_report", fields=fields, role=role)
        report_id = self.state["documents"][-1]["id"]
        status, result, _ = self.client.request(self.route + "/reports/" + report_id)
        assert status == 200
        return result

    def gate(self, gate_id, report=None):
        lead = "risk-lead" if "P2" in gate_id else "analyst"
        self.command("submit_gate", gate_id, {"reportId": report} if report else {}, role=lead)
        slots = next(g for g in self.state["gates"] if g["id"] == gate_id)["requiredRoles"]
        roles = {"assessment-lead": "analyst", "technical-reviewer": "reviewer"}
        for slot in slots:
            self.command("decide_gate", gate_id, decision_fields(), role=roles.get(slot, slot))
        assert next(g for g in self.state["gates"] if g["id"] == gate_id)["state"] == "qualified"


@pytest.fixture(scope="module")
def fixture_input(tmp_path_factory):
    folder = tmp_path_factory.mktemp("pqc-csharp-fixture")
    prepare(folder / "generated", applications=12)
    return folder / "generated/synthetic-input.json"


@pytest.fixture(scope="module")
def server(tmp_path_factory, fixture_input):
    folder = tmp_path_factory.mktemp("pqc-csharp-http")
    app = Server(folder, fixture_input)
    try:
        yield app.start()
    finally:
        app.stop()


def test_authentication_and_origin_boundaries(server):
    client = Client(server.origin)
    assert client.request("/api/dashboard")[0] == 401
    assert client.request("/api/reports")[0] == 401
    assert client.request("/api/assets")[0] == 401
    assert client.request("/api/session")[1]["authenticated"] is False
    assert client.request("/health/live", headers={"Host": "evil.example"})[0] == 400
    assert client.request("/api/session", method="POST", body={"role": "analyst", "password": "synthetic-demo-only"}, headers={"Origin": "https://evil.example"})[0] == 403
    assert client.request("/api/session", method="POST", body={"role": "analyst", "password": "incorrect"})[0] == 401
    status, _, headers = client.request("/health/ready")
    assert status == 200 and headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert "Access-Control-Allow-Origin" not in headers


def test_dashboard_and_assets_are_from_same_durable_input(server, fixture_input):
    fixture = json.loads(fixture_input.read_text())
    client = Client(server.origin).login()
    dashboard = client.request("/api/dashboard")[1]
    assert dashboard["counts"]["assets"] == len(fixture["inventory"])
    assert dashboard["counts"]["observations"] == len(fixture["observations"])
    assert dashboard["counts"]["cryptographicUses"] == len(fixture["riskReviews"])
    assert dashboard["counts"]["sourceFamilies"] == 27
    assert dashboard["counts"]["estateAreas"] == 10
    assert dashboard["baseline"]["acceptanceStatus"] == "unaccepted"
    first = client.request("/api/assets?pageSize=10")[1]
    assert first["total"] == dashboard["counts"]["assets"]
    second = client.request("/api/assets?page=2&pageSize=10")[1]
    assert not {x["id"] for x in first["items"]} & {x["id"] for x in second["items"]}
    asset = first["items"][0]
    detail = client.request("/api/assets/" + quote(asset["id"]))[1]
    assert detail["asset"]["id"] == asset["id"]
    assert len(detail["observations"]) == asset["observationCount"]
    assert all(row["subject_ref"] == asset["id"] for row in detail["observations"])
    assert client.request("/api/assets?q=" + quote(asset["displayName"]))[1]["total"] > 0
    assert client.request("/api/assets?q=no-such-synthetic-asset")[1]["total"] == 0
    assert client.request("/api/assets?family=ssh")[1]["total"] == 3
    assert client.request("/api/assets?status=conflict")[1]["total"] == 1
    for status, count in (("stale", "staleAssets"), ("context_only", "contextOnlyAssets"), ("conflict", "conflictedAssets")):
        assert client.request("/api/assets?status=" + status)[1]["total"] == dashboard["counts"][count]
    assert client.request("/api/assets?q=RSA")[1]["total"] > 0
    assert len(client.request("/api/sources")[1]) == 27


def test_mutation_is_role_and_csrf_scoped(server):
    viewer = Client(server.origin).login("viewer")
    assert viewer.request("/api/dashboard")[0] == 200
    assert viewer.request("/api/reports", method="POST", body={"phase": 1}, headers={"Idempotency-Key": "viewer-denied"})[0] == 403
    analyst = Client(server.origin).login()
    assert analyst.request("/api/reports", method="POST", body={"phase": 1}, headers={"Idempotency-Key": "csrf-denied", "X-PQC-CSRF": "incorrect"})[0] == 403
    assert analyst.request("/api/reports", method="POST", body={"phase": 3}, headers={"Idempotency-Key": "phase-denied"})[0] == 400
    assert analyst.request("/api/reports", method="POST", body={"phase": 1, "accepted": True}, headers={"Idempotency-Key": "extra-denied"})[0] == 400
    assert analyst.request("/api/reports", method="POST", body={"phase": 1})[0] == 400
    assert analyst.request("/api/migrate", method="POST", body={})[0] == 404
    assert analyst.request("/api/logout", method="POST")[0] == 200
    assert analyst.request("/api/dashboard")[0] == 401


def test_queries_are_bounded_and_injection_is_literal(server):
    client = Client(server.origin).login()
    for path in ("/api/assets?page=0", "/api/assets?pageSize=101", "/api/assets?q=" + "a" * 201):
        assert client.request(path)[0] == 400
    assert client.request("/api/assets?q=" + quote("' OR 1=1 --"))[1]["total"] == 0
    assert client.request("/api/assets/not-an-asset")[0] == 404


def test_report_creation_replay_conflict_and_download(server):
    client = Client(server.origin).login()
    assert client.request("/api/reports", method="POST", body={"phase": 1}, headers={"Idempotency-Key": "legacy-report-write"})[0] == 409
    ws = Workspace(client)
    body = ws.payload("generate_report", fields={"phase": "phase1"})
    first = client.request(ws.route + "/commands", method="POST", body=body, headers={"Idempotency-Key": "phase1-command-proof"})
    assert first[0] == 200, first[1]
    assert client.request(ws.route + "/commands", method="POST", body=body, headers={"Idempotency-Key": "phase1-command-proof"})[1] == first[1]
    ws.refresh()
    report_id = ws.state["documents"][-1]["id"]
    report = client.request(ws.route + "/reports/" + report_id)[1]
    assert report["metadata"]["synthetic"] is True
    assert client.request(ws.route + "/reports/" + report_id + "/download?format=json")[1] == report
    assert client.request(ws.route + "/reports/" + report_id + "/download?format=exe")[0] == 400
    assert client.request(ws.route + "/reports/not-a-report")[0] == 404
    html = client.request(ws.route + "/reports/" + report_id + "/download?format=html")
    assert html[0] == 200 and "Executive" in html[1]
    assert "style-src 'sha256-" in html[2]["Content-Security-Policy"]
    assert "unsafe-inline" not in html[2]["Content-Security-Policy"]
    classification = json.loads((ROOT / "schemas/common.Classification.schema.json").read_text())
    registry = Registry().with_resource("https://pba.io/schemas/common.Classification.schema.json", Resource.from_contents(classification))
    invocation_schema = json.loads((ROOT / "schemas/WorkerInvocation.schema.json").read_text())
    result_schema = json.loads((ROOT / "schemas/WorkerResult.schema.json").read_text())
    worker = yaml.safe_load((ROOT / "manifests/workers/pqc_enterprise_assessment.worker.yaml").read_text())["spec"]
    runs = client.request(ws.route + "/runs")[1]
    assert runs
    for run in runs:
        Draft202012Validator(invocation_schema, registry=registry).validate(run["workerInvocation"])
        Draft202012Validator(result_schema).validate(run["workerResult"])
        Draft202012Validator(worker["io"]["inputSchema"]).validate(run["workerInvocation"]["input"])
        Draft202012Validator(worker["io"]["outputSchema"]).validate(run["workerResult"]["output"])
        assert run["workerInvocation"]["meta"]["canonicalCatalogDispatch"] is False


def test_concurrent_duplicate_request_has_one_report(server):
    clients = [Client(server.origin).login(), Client(server.origin).login()]
    ws = Workspace(clients[0])
    body = ws.payload("generate_report", fields={"phase": "phase1"})
    def create(client):
        return client.request(ws.route + "/commands", method="POST", body=body, headers={"Idempotency-Key": "concurrent-report-proof"})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, clients))
    assert all(r[0] == 200 for r in results), results
    assert results[0][1] == results[1][1]
    assert len(clients[0].request(ws.route + "/reports")[1]) == 1


def test_restart_and_backup_restore_preserve_exact_report(tmp_path, fixture_input):
    server = Server(tmp_path, fixture_input)
    try:
        server.start()
        client = Client(server.origin).login()
        ws = Workspace(client)
        before = ws.report("phase1")
        report_route = ws.route + "/reports/" + before["metadata"]["id"]
        state_before = client.request(ws.route)[1]
        server.stop(); server.start()
        assert client.request(ws.route)[0] == 401
        client.login()
        assert client.request(report_route)[1] == before
        assert client.request(ws.route)[1] == state_before
        server.stop()
        backup = tmp_path / "backup"
        completed = subprocess.run(["dotnet", str(Path(DLL).resolve()), "--data-dir", str(server.data),
            "--fixture", str(fixture_input), "--backup-dir", str(backup)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        assert completed.returncode == 0, "isolated backup failed"
        server.data = backup; server.start()
        restored = Client(server.origin).login()
        assert restored.request(report_route)[1] == before
        assert restored.request(ws.route)[1] == state_before
        server.stop()
        with sqlite3.connect(backup / "enterprise-demo.sqlite3") as database:
            assert database.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert database.execute("PRAGMA user_version").fetchone()[0] == 4
            for table in ("assessment_documents", "assessment_versions", "assessment_commands", "assessment_events"):
                with pytest.raises(sqlite3.DatabaseError, match="immutable"):
                    database.execute(f"DELETE FROM {table}")
    finally:
        server.stop()


def assert_startup_refused(data, fixture, web):
    completed = subprocess.run(["dotnet", str(Path(DLL).resolve()), "--data-dir", str(data),
        "--fixture", str(fixture), "--web-root", str(web), "--port", "19473"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    assert completed.returncode != 0, "invalid fixture/store was not rejected before serving"
    # Host exposes only a stable startup code; not an exception, database path or records.
    combined = completed.stdout + completed.stderr
    assert b"System." not in combined and b"SELECT" not in combined
    assert str(data).encode() not in combined


def test_fresh_scope_has_no_admitted_facts_and_filters_cannot_change_scope(analysis_server):
    client = Client(analysis_server.origin).login()
    ws = Workspace(client, "fresh")
    catalog = client.request("/api/assessments/catalog")[1]
    assert len(catalog["stages"]) == 7
    assert len(catalog["sourceFamilies"]) == 27
    assert len({s["areaId"] for s in catalog["sourceFamilies"]}) == 10
    assert {d["id"] for d in catalog["depthOptions"]} == {"routing", "inventory", "dependency_cohort"}
    assert all(s["examples"] for s in catalog["sourceFamilies"])
    assert all(not s["observationIds"] for s in ws.state["sources"])
    before = client.request(ws.route)[1]
    analysis = client.request(ws.route + "/analysis?family=network-telemetry&owner=nonexistent")[1]
    assert analysis["summary"]["assets"] == analysis["summary"]["findings"] == 0
    assert analysis["baseline"]["populationStatus"] == "unknown"
    assert client.request(ws.route)[1] == before
    assert client.request(ws.route + "/assets")[1]["total"] == 0
    assert client.request(ws.route + "/reports")[1] == []
    assert client.request(ws.route + "/commands", method="POST", body=ws.payload("admit_sample", before["sources"][0]["familyId"]),
        headers={"Idempotency-Key": "deny-unapproved-admission"})[0] == 409


def test_attributed_route_and_no_evidence_qualification_do_not_establish_cryptography(analysis_server):
    ws = Workspace(Client(analysis_server.origin).login(), "fresh")
    family = ws.state["sources"][0]["familyId"]
    scope = scope_fields(ws)
    scope.update(includedFamilyIds=[family], depthByFamily={family: "routing"},
        excludedReasons={s["familyId"]: "Not part of this bounded routing proof." for s in ws.state["sources"] if s["familyId"] != family})
    ws.command("update_scope", fields=scope)
    ws.gate("PQC-G00")
    ws.command("source_response", family, {"state": "not_my_team", "systemOfRecord": "", "product": "", "ownerFunction": "",
        "accessRoute": "", "note": "Wrong recipient; no willingness conclusion.", "dueAt": "2026-09-22", "assertedBy": "Synthetic infrastructure respondent"})
    source = next(s for s in ws.state["sources"] if s["familyId"] == family)
    assert source["assertedBy"] == "Synthetic infrastructure respondent"
    assert source["respondedBy"] == "synthetic-demo:analyst"
    assert source["state"] == "not_my_team"
    ws.gate("PQC-P1-G01")
    ws.command("submit_package", family, {"conclusion": "The correct source route remains unidentified.", "qualification": "No technical evidence was admitted."})
    ws.refresh()
    result = ws.actor("reviewer").request(ws.route + "/commands", method="POST", body=ws.payload("review_package", family, decision_fields("accepted")),
        headers={"Idempotency-Key": "deny-false-evidence-completion"})
    assert result[0] == 400
    ws.command("review_package", family, decision_fields(), role="reviewer")
    questions = [q for q in ws.state["questions"] if q["familyId"] == family]
    assert len(questions) == 2
    assert all(q["state"] == "qualified" for q in questions)
    assert ws.state["metrics"]["questionAnswerability"]["supported"] == 0
    report = ws.report("phase1")
    assert report["content"]["summary"]["subjects"] == 0
    assert report["content"]["findings"] == []
    assert report["content"]["coverageRows"][0]["coveragePercent"] is None


def test_gate_slots_rejection_and_changed_inputs_preserve_history(analysis_server):
    ws = Workspace(Client(analysis_server.origin).login(), "fresh")
    ws.command("update_scope", fields=scope_fields(ws))
    ws.command("submit_gate", "PQC-G00")
    denied = ws.client.request(ws.route + "/commands", method="POST", body=ws.payload("decide_gate", "PQC-G00", decision_fields()),
        headers={"Idempotency-Key": "lead-cannot-impersonate-sponsor"})
    assert denied[0] == 403
    ws.command("decide_gate", "PQC-G00", decision_fields("rejected"), role="sponsor")
    assert ws.client.request(ws.route + "/commands", method="POST", body=ws.payload("submit_gate", "PQC-G00"), headers={"Idempotency-Key": "same-rejected-submission"})[0] == 409
    old = next(g for g in ws.state["gates"] if g["id"] == "PQC-G00")["decisions"][0]
    scope = {**scope_fields(ws), "handling": "Revised synthetic handling controls; no enterprise data."}
    ws.command("update_scope", fields=scope)
    ws.gate("PQC-G00")
    gate = next(g for g in ws.state["gates"] if g["id"] == "PQC-G00")
    assert old in gate["decisions"]
    assert len({d["principalId"] for d in gate["decisions"] if d["fingerprint"] == gate["fingerprint"]}) == 2
    assert ws.client.request(ws.route + "/commands", method="POST", body=ws.payload("decide_gate", "PQC-G00", decision_fields()),
        headers={"Idempotency-Key": "lead-cannot-fill-other-role"})[0] == 403


def test_assessments_share_only_source_material_not_workflow_or_reports(analysis_server):
    client = Client(analysis_server.origin).login()
    first = Workspace(client)
    second = Workspace(client, "fresh")
    original = client.request(second.route)[1]
    report = first.report("phase1")
    assert client.request(second.route + "/reports/" + report["metadata"]["id"])[0] == 404
    assert client.request(second.route + "/reports")[1] == []
    assert client.request(second.route + "/analysis")[1]["summary"]["assets"] == 0
    assert client.request(second.route)[1] == original
    assert all(e["origin"] == "scenario_generated" for e in first.state["events"] if e["operation"] != "generate_report")
    assert all(e["origin"] == "user_entered_synthetic" for e in second.state["events"])


def test_phase2_input_is_exact_and_changed_basis_blocks_reliance(analysis_server):
    ws = Workspace(Client(analysis_server.origin).login())
    first = ws.report("phase1")
    ws.gate("PQC-P1-G03", report=first["metadata"]["id"])
    newer = ws.report("phase1")
    assert newer["metadata"]["id"] != first["metadata"]["id"]
    phase2 = ws.report("phase2", first["metadata"]["id"], role="risk-lead")
    assert phase2["content"]["manifest"]["selectedPhase1"]["reportId"] == first["metadata"]["id"]
    denied = ws.actor("risk-lead").request(ws.route + "/commands", method="POST", body=ws.payload("generate_report", fields={"phase": "phase2", "phase1ReportId": newer["metadata"]["id"]}),
        headers={"Idempotency-Key": "never-select-latest-implicitly"})
    assert denied[0] == 409
    scope = {**scope_fields(ws), "objective": "Changed assessment purpose <script>alert(1)</script>"}
    ws.command("update_scope", fields=scope)
    denied = ws.actor("risk-lead").request(ws.route + "/commands", method="POST", body=ws.payload("generate_report", fields={"phase": "phase2", "phase1ReportId": first["metadata"]["id"]}),
        headers={"Idempotency-Key": "changed-basis-not-old-acceptance"})
    assert denied[0] == 409
    assert ws.client.request(ws.route + "/reports/" + first["metadata"]["id"])[1] == first
    new_report = ws.report("phase1")
    html = ws.client.request(ws.route + "/reports/" + new_report["metadata"]["id"] + "/download?format=html")[1]
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_legacy_v2_upgrade_preserves_old_report_and_annotation(tmp_path, fixture_input):
    old_dll = ROOT / "artifacts/pqc-enterprise-demo/analytical-release-20260905/PqcEnterpriseDemo.dll"
    if not old_dll.exists():
        pytest.skip("explicit historical synthetic binary unavailable; no download")
    old = Server(tmp_path, fixture_input, dll=old_dll)
    try:
        old.start()
        client = Client(old.origin).login()
        status, report, _ = client.request("/api/reports", method="POST", body={"phase": 1}, headers={"Idempotency-Key": "historical-p1-proof"})
        assert status in (200, 201)
        historical = client.request("/api/reports/" + report["id"])[1]
        finding = client.request("/api/analysis")[1]["findings"][0]
        response = client.request("/api/actions/" + finding["id"], method="POST", body={"operation": "investigate", "disposition": None,
            "note": "Historical synthetic annotation", "expectedRevision": 0}, headers={"Idempotency-Key": "historical-action-proof"})
        assert response[0] == 201
        old.stop()
        with sqlite3.connect(old.data / "enterprise-demo.sqlite3") as db:
            assert db.execute("PRAGMA user_version").fetchone()[0] == 2
        current = Server(tmp_path, fixture_input, data=old.data)
        try:
            current.start()
            newer = Client(current.origin).login()
            assert newer.request("/api/reports/" + report["id"])[1] == historical
            assert newer.request("/api/actions/" + finding["id"])[1] == [response[1]]
            assert newer.request("/api/assessments")[1] == []
            with sqlite3.connect(current.data / "enterprise-demo.sqlite3") as db:
                assert db.execute("PRAGMA user_version").fetchone()[0] == 4
                migrations = db.execute("SELECT version,source_sha256 FROM assessment_schema_migrations ORDER BY version").fetchall()
                assert [row[0] for row in migrations] == [3, 4]
                assert all(len(row[1]) == 64 for row in migrations)
        finally:
            current.stop()
    finally:
        old.stop()


@pytest.mark.parametrize("fault", ["legacy_trigger", "assessment_trigger", "changed_digest", "missing_table"])
def test_schema_tampering_is_rejected_without_healing(tmp_path, fixture_input, fault):
    app = Server(tmp_path, fixture_input)
    app.start(); app.stop()
    database = app.data / "enterprise-demo.sqlite3"
    with sqlite3.connect(database) as db:
        if fault == "legacy_trigger":
            db.execute("DROP TRIGGER immutable_records_UPDATE")
        elif fault == "assessment_trigger":
            db.execute("DROP TRIGGER immutable_assessment_versions_DELETE")
        elif fault == "changed_digest":
            sql = db.execute("SELECT sql FROM sqlite_master WHERE name='immutable_assessment_schema_migrations_UPDATE'").fetchone()[0]
            db.execute("DROP TRIGGER immutable_assessment_schema_migrations_UPDATE")
            db.execute("UPDATE assessment_schema_migrations SET source_sha256=?", ("0" * 64,))
            db.execute(sql)
        else:
            db.execute("DROP TABLE assessment_commands")
        db.commit()
        before = db.execute("SELECT type,name,sql FROM sqlite_master ORDER BY name").fetchall()
    assert_startup_refused(app.data, fixture_input, app.web)
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT type,name,sql FROM sqlite_master ORDER BY name").fetchall() == before
        assert db.execute("PRAGMA user_version").fetchone()[0] == 4


@pytest.mark.parametrize("fault", ["real_tenant", "authorized_use", "cross_subject", "missing_subject", "inaccessible_identifier"])
def test_invalid_fixture_cannot_be_served(tmp_path, fixture_input, fault):
    fixture = json.loads(fixture_input.read_text())
    if fault == "real_tenant":
        fixture["tenantId"] = "enterprise"
    elif fault == "authorized_use":
        fixture["riskReviews"][0]["execution_authorized"] = True
    elif fault == "missing_subject":
        del fixture["riskReviews"][0]["subject_ref"]
    elif fault == "inaccessible_identifier":
        fixture["inventory"][0]["subject_ref"] = "bad/id"
    else:
        use = fixture["riskReviews"][0]
        wrong = next(row for row in fixture["observations"] if row["subject_ref"] != use["subject_ref"])
        use["observation_refs"] = [wrong["observation_id"]]
    fixture_path = tmp_path / "invalid-input.json"
    fixture_path.write_text(json.dumps(fixture))
    data, web = tmp_path / "data", tmp_path / "web"
    data.mkdir(mode=0o700)
    web.mkdir()
    assert_startup_refused(data, fixture_path, web)


def test_persisted_record_tampering_cannot_keep_baseline_identity(tmp_path, fixture_input):
    app = Server(tmp_path, fixture_input)
    try:
        app.start()
    finally:
        app.stop()
    # Deliberately corrupt ONLY this test-owned synthetic DB to exercise readback.
    with sqlite3.connect(app.data / "enterprise-demo.sqlite3") as database:
        database.execute("DROP TRIGGER immutable_records_UPDATE")
        database.execute("UPDATE records SET payload_json='{}' WHERE kind='inventory' AND position=0")
    assert_startup_refused(app.data, fixture_input, app.web)


def test_existing_unowned_directory_and_symlink_refused(tmp_path, fixture_input):
    data, web = tmp_path / "unowned", tmp_path / "web"
    data.mkdir(mode=0o700)
    web.mkdir()
    marker = data / "unrelated-user-file"
    marker.write_text("preserve this unrelated test file")
    assert_startup_refused(data, fixture_input, web)
    assert marker.read_text() == "preserve this unrelated test file"
    assert not (data / "enterprise-demo.sqlite3").exists()
    target = tmp_path / "real-folder"
    target.mkdir()
    symlink = tmp_path / "linked"
    symlink.symlink_to(target, target_is_directory=True)
    assert_startup_refused(symlink, fixture_input, web)
    assert not list(target.iterdir())
