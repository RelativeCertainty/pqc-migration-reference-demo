"""The candidate Worker only projects repository-owned synthetic fixtures."""

import copy
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from worker_runtime.grants import Grant
from workers.pqc.reference_source_probe import (
    CAPABILITY,
    project_fixture,
    run_reference_source_probe,
)

ROOT = Path(__file__).resolve().parents[1]


def request():
    return {
        "fixture_kind": "cmdb",
        "tenant_id": "internal",
        "observed_at": "2026-09-05T12:00:00Z",
        "synthetic": True,
    }


def grant(tenant="internal", capabilities=None):
    return Grant(
        capabilities={CAPABILITY} if capabilities is None else capabilities,
        audit={"tenant_id": tenant},
    )


@pytest.mark.parametrize("kind", ["cmdb", "pki", "tls"])
def test_fixed_fixtures_match_closed_manifest_contract(kind):
    manifest = yaml.safe_load(
        (ROOT / "manifests/workers/pqc_reference_source_probe.worker.yaml").read_text()
    )
    value = dict(request(), fixture_kind=kind)
    Draft202012Validator(manifest["spec"]["io"]["inputSchema"]).validate(value)
    result = run_reference_source_probe(value, grant=grant())
    assert result["success"] is True
    assert result["status"] == "completed"
    assert result["output"] == project_fixture(kind, "internal", value["observed_at"])
    Draft202012Validator(manifest["spec"]["io"]["outputSchema"]).validate(
        result["output"]
    )
    assert result["output"]["external_effects"] is False
    assert result["output"]["record_count"] == 1
    assert "records.example" not in json.dumps(result)
    assert manifest["metadata"]["labels"]["pba.io/default-enabled"] == "false"


@pytest.mark.parametrize("authority", [None, grant("other"), grant(capabilities=set())])
def test_grant_and_tenant_required(authority):
    result = run_reference_source_probe(request(), grant=authority)
    assert result["success"] is False
    assert result["error"]["code"] == "PQC_REFERENCE_PROBE_DENIED"
    assert result["output"] == {}


@pytest.mark.parametrize(
    "mutation",
    [
        {"fixture_kind": "../../production"},
        {"fixture_kind": []},
        {"provider_url": "https://example.invalid"},
        {"synthetic": False},
        {"observed_at": "yesterday"},
        {"tenant_id": ""},
    ],
)
def test_closed_input_and_sanitized_errors(mutation):
    value = copy.deepcopy(request())
    value.update(mutation)
    result = run_reference_source_probe(value, grant=grant())
    assert not result["success"]
    assert result["output"] == {}
    assert "production" not in json.dumps(result)
    assert "example.invalid" not in json.dumps(result)
    assert result["retryable"] is False
