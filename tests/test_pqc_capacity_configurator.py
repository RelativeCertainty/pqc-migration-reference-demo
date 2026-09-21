"""Isolated loopback/CLI proofs for the capacity planner, not enterprise qualification."""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.error
import urllib.request
import zipfile

import pytest
from tests.test_pqc_enterprise_demo_http import Client, Server, fixture_input

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/pqc-enterprise-demo"
DLL = APP / "bin/Release/net10.0/PqcEnterpriseDemo.dll"


@pytest.fixture(scope="module")
def service(tmp_path_factory, fixture_input):
    assert DLL.is_file(), "Build the unified C# application first; tests never acquire dependencies."
    server = Server(tmp_path_factory.mktemp("capacity-module"), fixture_input, dll=str(DLL))
    (server.web / "index.html").write_text("<!doctype html><html><title>Synthetic module test</title></html>")
    try:
        server.start()
        yield Client(server.origin).login()
    finally:
        server.stop()


def request(base, path, data=None, headers=None):
    body = None if data is None else (data if isinstance(data, bytes) else json.dumps(data).encode())
    path = path.replace("/api/", "/api/capacity/", 1)
    req = urllib.request.Request(base.origin + path, data=body,
        headers={"Content-Type": "application/json", "Origin": base.origin, "X-PQC-CSRF": base.csrf, **(headers or {})})
    try:
        with base.opener.open(req, timeout=10) as response:
            return response.status, response.read(), response.headers
    except urllib.error.HTTPError as error:
        return error.code, error.read(), error.headers


def calculate(base, data):
    code, payload, _ = request(base, "/api/calculate", data)
    assert code == 200, payload
    return json.loads(payload)


def test_enterprise_independent_arithmetic(service):
    result = calculate(service, {})
    assert result["rates"]["burstRequestsPerSecond"] == 150
    assert result["rates"]["burstObservationsPerSecond"] == pytest.approx(10_000_000 / 28800 * 3)
    assert result["demands"]["apiRequiredCores"] == pytest.approx(150 * .02 * 1.3 / .65)
    assert result["demands"]["workerRequiredCores"] == pytest.approx((10_000_000 / 28800 * 3 * .003 + 3) * 1.3 / .65)
    assert result["demands"]["sqlRequiredCores"] == pytest.approx((150 * .008 + 10_000_000 / 28800 * 3 * .004 + 3) * 1.3 / .7)
    assert result["totals"]["cpu"] == 70
    assert result["totals"]["memoryGiB"] == 404
    logical = (1_000_000*2048 + 4_000_000*2048 + 8_000_000*256 + 89_000_000*1024 + 3_960_000_000*32)/1024**3 + 5
    assert result["storage"]["sqlProvisionGiBPerCopy"] == pytest.approx(logical*2*1.3/.7)
    assert result["storage"]["sqlAllocatedGiBPerCopy"] == 1024
    assert result["storage"]["retainedObservationVersions"] == 89_000_000
    assert result["storage"]["retainedLineageMemberships"] == 3_960_000_000
    assert not result["deployable"] and not result["performanceVerified"]
    assert result["cost"]["totalMonthly"] is None
    assert "active-exceeds-named" in {w["code"] for w in result["warnings"]}


def test_catalog_compare_and_surviving_allocations(service):
    code, payload, _ = request(service, "/api/catalog")
    assert code == 200
    catalog = json.loads(payload)
    assert len(catalog["presets"]) == 3
    definitions = catalog["definitions"]
    assert len({d["key"] for d in definitions}) == len(definitions)
    code, payload, _ = request(service, "/api/compare", {"scenarios": catalog["presets"]})
    assert code == 200
    results = json.loads(payload)["results"]
    assert [r["scenario"]["profileId"] for r in results] == ["mvp", "growth", "enterprise"]
    assert results[0]["scenario"]["availability"] == "single"
    for result in results:
        for allocation in result["allocations"]:
            if allocation["tier"] != "witness":
                assert allocation["survivingCores"] >= allocation["requiredCores"]
        sql = next(a for a in result["allocations"] if a["tier"] == "sql")
        assert sql["survivingCores"] == sql["cpuPerInstance"]
    assert request(service, "/api/compare", {"scenarios": [{}]*7})[0] == 400
    assert request(service, "/api/compare", {"scenarios": [None]})[0] == 400


@pytest.mark.parametrize("bad", [
    {"parameters": {"assets": -1}}, {"parameters": {"assets": 1.5}},
    {"parameters": {"bogus": 1}}, {"parameters": None}, {"name": None},
    {"availability": "maybe"}, {"platform": None}, {"schemaVersion": "future"},
    {"unrecognized": True}, {"parameters": {"harvestHours": 25}},
    {"parameters": {"apiUtilization": 0}}, {"parameters": {"assets": "1000"}},
    {"name": "x"*121}, {"parameters": {"assets": float("nan")}},
])
def test_strict_validation(service, bad):
    assert request(service, "/api/calculate", bad)[0] == 400


def test_determinism_monotonicity_and_retention(service):
    baseline = calculate(service, {})
    one = calculate(service, {"parameters": {"assets": 2_000_000, "activeUsers": 250}})
    two = calculate(service, {"parameters": {"activeUsers": 250, "assets": 2_000_000}})
    assert one["inputHash"] == two["inputHash"] != baseline["inputHash"]
    assert one["storage"]["sqlProvisionGiBPerCopy"] > baseline["storage"]["sqlProvisionGiBPerCopy"]
    assert one["demands"]["workerRequiredCores"] > baseline["demands"]["workerRequiredCores"]
    full = calculate(service, {"historyMode": "full"})
    assert full["storage"]["retainedObservationVersions"] == 3_960_000_000
    assert full["storage"]["sqlProvisionGiBPerCopy"] / 1024 == pytest.approx(14.186, abs=.001)
    assert full["storage"]["retainedLineageMemberships"] == baseline["storage"]["retainedLineageMemberships"]
    short = calculate(service, {"parameters": {"observationDays": 90}})
    assert short["storage"]["sqlProvisionGiBPerCopy"] < baseline["storage"]["sqlProvisionGiBPerCopy"]
    large_memory = calculate(service, {"parameters": {"apiWorkingSetGiB": 40}})
    api = next(a for a in large_memory["allocations"] if a["tier"] == "api")
    assert api["memoryGiBPerInstance"] == 52


def test_sensitivity_source_limit_and_cost(service):
    code, payload, _ = request(service, "/api/sensitivity", {})
    assert code == 200
    results = [c["result"] for c in json.loads(payload)["cases"]]
    assert results[0]["demands"]["apiRequiredCores"]*4 == pytest.approx(results[2]["demands"]["apiRequiredCores"])
    limited = calculate(service, {"parameters": {"sourceIngressMaxRecordsPerSecond": 1}})
    assert "source-throughput-insufficient" in {n["code"] for n in limited["warnings"]}
    assert "source-throughput-insufficient" in {n["code"] for n in limited["blockers"]}
    priced = calculate(service, {"parameters": {"pricingProvided": 1, "vcpuMonthlyRate": 10, "ramGiBMonthlyRate": 1, "sqlCoreMonthlyRate": 5}})
    assert priced["cost"]["totalMonthly"] == 70*10 + 404 + 32*5
    assert priced["cost"]["basis"]


def test_http_boundary_and_no_execution(service):
    assert request(service, "/api/calculate", {}, {"Origin": "https://other.example"})[0] == 403
    assert request(service, "/api/catalog", headers={"Host": "evil.example"})[0] == 400
    assert request(service, "/api/calculate", {}, {"Sec-Fetch-Site": "cross-site"})[0] == 403
    assert request(service, "/api/calculate", b"{}", {"Content-Type": "text/plain"})[0] == 415
    assert request(service, "/api/calculate", b" "*65537 + b"{}")[0] == 413
    assert request(service, "/api/apply", {})[0] == 404
    assert request(service, "/api/deploy", {})[0] == 404
    code, html, headers = request(service, "/")
    assert code == 200 and b"<html" in html
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]


def test_package_manifest_roundtrip_and_review_only(service, tmp_path):
    scenario = {"name": "=Reviewed, \"scenario\"", "platform": "cloud-foundry"}
    code, payload, headers = request(service, "/api/package", scenario)
    assert code == 200 and headers["Content-Type"] == "application/zip"
    assert "pqc-capacity-review-package.zip" in headers["Content-Disposition"]
    assert payload == request(service, "/api/package", scenario)[1]
    archive = zipfile.ZipFile(io.BytesIO(payload))
    manifest = json.loads(archive.read("manifest.json"))
    assert set(archive.namelist()) == {x["path"] for x in manifest["entries"]} | {"manifest.json"}
    for item in manifest["entries"]:
        raw = archive.read(item["path"])
        assert len(raw) == item["bytes"]
        assert hashlib.sha256(raw).hexdigest() == item["sha256"]
        assert not item["path"].startswith("/") and ".." not in item["path"]
    contract = json.loads(archive.read("deployment-contract.json"))
    assert contract["mode"] == "review_only" and not contract["enabled"]
    assert not contract["phase3ExecutionEnabled"] and not contract["phase4ExecutionEnabled"]
    result = json.loads(archive.read("result.json"))
    exported = json.loads(archive.read("scenario.json"))
    assert calculate(service, exported)["inputHash"] == result["inputHash"]
    assert list(csv.reader(io.StringIO(archive.read("estimates.csv").decode())))
    tfvars = json.loads(archive.read("terraform-review/capacity-profile.tfvars.json"))
    assert not tfvars["deployable"]
    variables = archive.read("terraform-review/variables.tf").decode()
    for name in tfvars:
        assert f'variable "{name}"' in variables
    for name in archive.namelist():
        if name.endswith(".tf"):
            content = archive.read(name).decode()
            assert 'resource "' not in content and 'provider "' not in content and 'provisioner "' not in content
    cf = archive.read("cloud-foundry-manifest.review.yaml").decode()
    assert "REVIEW" in cf
    assert "Candidate tier: sql" not in cf and "Candidate tier: witness" not in cf
    assert b"<svg" in archive.read("capacity-one-line.svg")
    rows = list(csv.reader(io.StringIO(archive.read("model-inputs.csv").decode())))
    assert len(rows) == len(exported["parameters"]) + 1
    script = tmp_path / "scenario.json"
    script.write_text(json.dumps(exported))
    cli = subprocess.run(["dotnet", str(DLL), "--capacity-evaluate", str(script)], capture_output=True, text=True, timeout=10, check=True)
    assert json.loads(cli.stdout)["inputHash"] == result["inputHash"]
    output = tmp_path / "review.zip"
    subprocess.run(["dotnet", str(DLL), "--capacity-package", str(script), str(output)], capture_output=True, timeout=10, check=True)
    assert output.read_bytes() == payload
    original = output.read_bytes()
    again = subprocess.run(["dotnet", str(DLL), "--capacity-package", str(script), str(output)], capture_output=True, timeout=10)
    assert again.returncode == 2 and output.read_bytes() == original


def test_export_refuses_silent_input_redaction(service):
    scenario = {"name": "/home/synthetic-review/example"}
    assert request(service, "/api/package", scenario)[0] == 400


def test_sensitivity_long_names_and_bounded_cases(service):
    status, payload, _ = request(service, "/api/sensitivity", {"name": "x"*120, "parameters": {"apiCpuMs": 10000}})
    assert status == 200
    cases = json.loads(payload)["cases"]
    assert cases[0].get("result") and cases[1].get("result")
    assert cases[2]["error"] == "outside_parameter_bounds"
