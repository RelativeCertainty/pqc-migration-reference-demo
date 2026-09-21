"""Legacy capabilities are served by the same C# authority, never a second runtime."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from urllib.request import Request

import pytest
from jsonschema import Draft202012Validator
from tests.test_pqc_enterprise_demo_http import Client, Server, fixture_input

ROOT = Path(__file__).resolve().parents[1]
DLL = os.environ.get("PQC_ENTERPRISE_DEMO_DLL")
pytestmark = pytest.mark.skipif(not DLL, reason="explicit built C# DLL required")


@pytest.fixture
def unified(tmp_path, fixture_input):
    server = Server(tmp_path, fixture_input)
    index = b"<!doctype html><title>One synthetic application</title>"
    (server.web / "index.html").write_bytes(index)
    (server.web / "asset-manifest.sha256").write_text(hashlib.sha256(index).hexdigest() + "  index.html\n")
    try:
        yield server.start()
    finally:
        server.stop()


def test_posture_is_authenticated_versioned_and_no_forged_crypto(unified):
    anonymous = Client(unified.origin)
    assert anonymous.request("/api/posture")[0] == 401
    client = anonymous.login()
    status, posture, headers = client.request("/api/posture", headers={"Forwarded": "proto=https", "X-Forwarded-Proto": "https", "X-TLS-Cipher": "fictional"})
    assert status == 200
    Draft202012Validator(json.loads((ROOT / "contracts/posture.v3.schema.json").read_text())).validate(posture)
    assert posture["request_transport"]["tls_cipher"] == {"state": "unavailable", "value": None}
    assert posture["request_transport"]["http_protocol"]["value"] == "HTTP/1.1"
    assert posture["data_posture"]["storage"] == "isolated_sqlite"
    assert not posture["approved_deployment_label"]["eligible"]
    assert headers["Cache-Control"] == "no-store"
    assert client.request("/api/posture", method="POST", body={})[0] == 405
    response = client.opener.open(Request(unified.origin + "/api/posture", method="HEAD"))
    assert response.status == 200 and response.read() == b""


def test_one_host_static_health_and_sensitive_paths(unified):
    client = Client(unified.origin)
    for path in ("/healthz", "/readyz", "/health/live", "/health/ready"):
        assert client.request(path)[0] == 200
    status, page, headers = client.request("/")
    assert status == 200 and "One synthetic application" in page
    assert len(headers["X-PQC-UI-Manifest"]) == 64
    (unified.web / "index.html").write_text("changed after startup")
    assert client.request("/")[1] == page
    for path in ("/_headers", "/asset-manifest.sha256", "/assets/app.js.map", "/.git/config", "/assets/missing", "/%2e%2e/config"):
        assert client.request(path)[0] == 404
    assert client.request("/", method="POST", body={})[0] == 405
    assert client.request("/", headers={"Sec-Fetch-Site": "cross-site"})[0] == 403


def test_capacity_uses_the_existing_session_and_csrf(unified):
    client = Client(unified.origin)
    assert client.request("/api/capacity/catalog")[0] == 401
    client.login()
    assert client.request("/api/capacity/catalog")[0] == 200
    assert client.request("/api/capacity/calculate", method="POST", body={}, headers={"X-PQC-CSRF": "wrong"})[0] == 403
    status, result, _ = client.request("/api/capacity/calculate", method="POST", body={})
    assert status == 200 and result["deployable"] is False
    assert Client(unified.origin).login("contributor").request("/api/capacity/catalog")[0] == 403


def test_tampered_ui_manifest_refuses_start(tmp_path, fixture_input):
    server = Server(tmp_path, fixture_input)
    (server.web / "index.html").write_text("tampered")
    (server.web / "asset-manifest.sha256").write_text("0" * 64 + "  index.html\n")
    try:
        with pytest.raises(AssertionError, match="exited before readiness"):
            server.start()
    finally:
        server.stop()


def test_version_is_the_csharp_application():
    value = json.loads(subprocess.check_output(["dotnet", DLL, "--version"], text=True))
    assert value["application"] == "one-csharp-react-host"
    assert value["profile"] == "synthetic-only"
