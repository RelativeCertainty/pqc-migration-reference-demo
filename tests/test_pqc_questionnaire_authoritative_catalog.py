"""Opt-in source-definition parity against a private compiled catalog.

Reads explicitly selected questionnaire definitions only. All assignments and
application data are synthetic, in a test-owned disposable SQLite store.
"""
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from tests.test_pqc_enterprise_demo_http import Client, Server, Workspace, fixture_input


pytestmark = pytest.mark.skipif(
    not os.environ.get("PQC_ENTERPRISE_DEMO_DLL") or not os.environ.get("PQC_AUTHORITATIVE_QUESTIONNAIRE_CATALOG"),
    reason="Explicit built DLL and compiled source-definition catalog required")


def test_every_template_reaches_assignment_without_abbreviation(tmp_path, fixture_input, monkeypatch):
    path = Path(os.environ["PQC_AUTHORITATIVE_QUESTIONNAIRE_CATALOG"])
    expected = json.loads(path.read_text())
    monkeypatch.setenv("PQC_QUESTIONNAIRE_CATALOG_FILE", str(path))
    server = Server(tmp_path, fixture_input)
    try:
        server.start()
        ws = Workspace(Client(server.origin).login(), "fresh")
        route = ws.route + "/questionnaires"
        status, catalog, _ = ws.client.request(route)
        assert status == 200
        assert len(catalog["catalog"]["templates"]) == 27
        revision = catalog["revision"]
        observed_bindings = set()
        for template in expected["templates"]:
            status, result, _ = ws.client.request(route + "/commands", method="POST",
                body={"operation": "questionnaire_create", "targetId": None, "expectedRevision": revision,
                    "fields": {"templateId": template["id"], "title": "Synthetic definition parity " + template["id"],
                        "assignedTo": "synthetic-demo:contributor", "deployment": {
                            "label": "Synthetic deployment " + template["id"], "product": "Synthetic product", "environment": "test"}}},
                headers={"Idempotency-Key": uuid4().hex})
            assert status == 200, (status, template["id"])
            revision = result["revision"]
            assignment_id = result["assignments"][-1]["id"]
            status, detail, _ = ws.client.request(route + "/" + assignment_id)
            assert status == 200
            assignment = detail["assignment"]
            assert assignment["template"] == template
            assert assignment["templateVersion"] == expected["catalogVersion"]
            assert assignment["operatingContract"] == expected["operatingContract"]
            assert len(assignment["answers"]) == 27
            assert all(a["status"] == "unanswered" for a in assignment["answers"].values())
            assert not detail["validation"]["canSubmit"]
            observed_bindings.update(q["id"] for q in assignment["template"]["questions"])
        assert len(observed_bindings) == 729
        assert len({a["deployment"]["id"] for a in result["assignments"]}) == 27
    finally:
        server.stop()
