"""Shared-state capacity stays bounded without disabling the legacy intake path."""
from __future__ import annotations

from io import BytesIO
import os
import sqlite3
from uuid import uuid4
from zipfile import ZIP_STORED, ZipFile

import pytest

from tests.test_pqc_discovery_evidence import DiscoveryJourney, discovery_evidence_server, fixture_input
from tests.test_pqc_intake_http import raw_request

pytestmark = pytest.mark.skipif(
    not os.environ.get("PQC_ENTERPRISE_DEMO_DLL"), reason="explicit isolated C# build required"
)


def legacy(d, operation, target=None, fields=None):
    status, result, _ = d.ws.client.request(d.ws.route + "/intake/commands", method="POST",
        body={"operation": operation, "targetId": target, "fields": fields or {},
              "expectedRevision": d.view()["revision"]}, headers={"Idempotency-Key": uuid4().hex})
    assert status == 200, (operation, status, result)
    return result


def legacy_request(d, title="Existing synthetic legacy request"):
    result = legacy(d, "intake_create_request", fields={"title": title,
        "familyId": "traffic-termination", "assignedTo": "synthetic-demo:contributor"})
    return result["requests"][-1]["id"]


def legacy_save(d, request):
    result = legacy(d, "intake_save_response", request,
        {"answers": {request + "/owner": "Synthetic platform function; source ownership is unverified."},
         "assertedBy": "Synthetic coordinator"})
    row = next(r for r in result["requests"] if r["id"] == request)
    assert row["answers"][request + "/owner"].startswith("Synthetic platform function")


def test_system_ceiling_counts_new_identities_and_keeps_legacy_writable(discovery_evidence_server):
    d = DiscoveryJourney(discovery_evidence_server).prepare()
    d.gates()
    request = legacy_request(d)
    d.resume_after_restart(discovery_evidence_server)
    # One evidence source plus 79 endpoints reaches the existing shared cap.
    d.stage(d.products[0], count=32)
    d.stage(d.products[1], count=32)
    d.command("discovery_add_product", d.investigation,
        {"label": "Synthetic portal north", "product": "Reference TLS configuration", "environment": "north"})
    third = d.view()["investigations"][0]["productRefs"][-1]
    d.stage(third, count=15)
    state = d.ws.refresh()
    assert len(state["intake"]["systems"]) == 80
    assert len(state["intake"]["batches"]) == 79

    # An additional capture for an existing endpoint must still fit: it adds
    # provenance, not another system. It remains staged, never auto-admitted.
    d.stage(d.products[0], basis="observed")
    assert len(d.ws.refresh()["intake"]["systems"]) == 80
    d.command("discovery_add_product", d.investigation,
        {"label": "Synthetic portal south", "product": "Reference TLS configuration", "environment": "south"})
    fourth = d.view()["investigations"][0]["productRefs"][-1]
    before = d.ws.refresh()
    result = d.stage(fourth, expected=409)
    assert result["error"]["code"] == "discovery_evidence_capacity_limit"
    after = d.ws.refresh()
    assert after["revision"] == before["revision"]
    assert after["intake"] == before["intake"]
    assert after["discovery"] == before["discovery"]
    legacy_save(d, request)


def test_hidden_evidence_route_respects_shared_request_ceiling(discovery_evidence_server):
    d = DiscoveryJourney(discovery_evidence_server).prepare()
    d.gates()
    d.resume_after_restart(discovery_evidence_server)
    requests = [legacy_request(d, f"Synthetic legacy request {index}") for index in range(19)]
    d.stage(d.products[0])
    assert len(d.ws.refresh()["intake"]["requests"]) == 20
    d.resume_after_restart(discovery_evidence_server)
    d.command("discovery_create_investigation", d.request,
        {"purpose": "Second synthetic evidence route", "assignedTo": "synthetic-demo:analyst", "productRefIds": []})
    d.investigation = d.view()["investigations"][-1]["id"]
    d.command("discovery_add_product", d.investigation,
        {"label": "Synthetic separate product", "product": "Reference TLS configuration", "environment": "test"})
    product = d.view()["investigations"][-1]["productRefs"][0]
    before = d.ws.refresh()
    result = d.stage(product, expected=409)
    assert result["error"]["code"] == "discovery_evidence_capacity_limit"
    after = d.ws.refresh()
    assert after["revision"] == before["revision"]
    assert after["intake"] == before["intake"]
    assert after["discovery"] == before["discovery"]
    legacy_save(d, requests[0])


def custody_sized_workbook(payload):
    """Keep five unchanged small answers; valid inert XML tests custody size.

    Stored ZIP members avoid a compression-bomb fixture. The input stays below
    the unchanged 1 MiB XLSX limit and includes no new part or executable data.
    """
    output = BytesIO()
    with ZipFile(BytesIO(payload)) as source, ZipFile(output, "w", compression=ZIP_STORED) as target:
        for name in source.namelist():
            body = source.read(name)
            if name == "xl/styles.xml":
                body += b"\n<!-- Synthetic bounded custody-size fixture: " + b"x" * 750_000 + b" -->"
            target.writestr(name, body)
    result = output.getvalue()
    assert 750_000 < len(result) < 1_048_576
    return result


def test_legacy_save_after_valid_shared_excel_state_exceeds_old_two_mib_limit(discovery_evidence_server):
    d = DiscoveryJourney(discovery_evidence_server)
    request = legacy_request(d)
    d.command("discovery_create", fields={"title": "Five-question synthetic custody proof",
        "familyId": "traffic-termination", "assignedTo": "synthetic-demo:contributor"})
    discovery_request = d.view()["requests"][0]["id"]
    contributor = d.ws.actor("contributor")
    status, exported, _ = contributor.request(d.route + "/exports/" + discovery_request,
        method="POST", body={"expectedRevision": d.view()["revision"]},
        headers={"Idempotency-Key": uuid4().hex})
    assert status == 200, exported
    status, payload, _ = raw_request(contributor, exported["downloadUrl"])
    assert status == 200
    payload = custody_sized_workbook(payload)
    for _ in range(3):
        status, preview, _ = raw_request(contributor,
            d.route + "/imports/" + discovery_request + "?expectedRevision=" + str(d.view()["revision"]),
            method="POST", data=payload,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Idempotency-Key": uuid4().hex})
        assert status == 200, preview
        assert all(change["state"] == "unchanged" for change in preview["import"]["changes"])
    # Read only the byte count from this test-owned database, never a payload.
    database_path = discovery_evidence_server.data / "enterprise-demo.sqlite3"
    with sqlite3.connect(database_path.as_uri() + "?mode=ro", uri=True) as database:
        row = database.execute("SELECT length(CAST(snapshot_json AS BLOB)) FROM assessment_versions WHERE assessment_id=? ORDER BY revision DESC LIMIT 1",
            (d.ws.state["id"],)).fetchone()
    assert 2_097_152 < row[0] < 8_388_608
    legacy_save(d, request)
    final = d.ws.refresh()
    assert final["discovery"]["requests"][0]["status"] == "draft"
    assert not final["intake"]["batches"]
    assert all(gate["state"] == "not_submitted" for gate in final["gates"])
