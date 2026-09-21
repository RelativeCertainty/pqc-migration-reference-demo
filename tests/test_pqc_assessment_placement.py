"""Local C# declaration does not admit a remote/mixed lane or activate a runner."""
from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_csharp_assessment_manifest_is_disabled_and_local_metadata_only():
    manifest = yaml.safe_load((ROOT / "manifests/workers/pqc_enterprise_assessment.worker.yaml").read_text())
    spec = manifest["spec"]
    schema = json.loads((ROOT / "schemas/ExecutionPlacementContract.v1.schema.json").read_text())
    Draft202012Validator(schema).validate(spec["placement"])
    assert manifest["metadata"]["labels"]["pba.io/activation-state"] == "disabled"
    assert manifest["metadata"]["labels"]["pba.io/default-enabled"] == "false"
    assert spec["runtime"] == "dotnet"
    assert spec["placement"]["database"]["access_mode"] == "none"
    assert spec["placement"]["commit"]["worker_authoritative_write_allowed"] is False
    assert spec["placement"]["artifact_io"]["input_mode"] == "inline_metadata"
    assert set(spec["io"]["inputSchema"]["properties"]) == {"assessmentId", "operation", "request_sha256", "expectedRevision", "synthetic"}


@pytest.mark.parametrize("mode", ["remote_allowed", "remote_preferred", "remote_required", "local_preferred"])
def test_csharp_declaration_cannot_enable_remote_fallback(mode):
    spec = yaml.safe_load((ROOT / "manifests/workers/pqc_enterprise_assessment.worker.yaml").read_text())["spec"]
    placement = deepcopy(spec["placement"])
    schema = json.loads((ROOT / "schemas/ExecutionPlacementContract.v1.schema.json").read_text())
    placement["mode"] = mode
    assert list(Draft202012Validator(schema).iter_errors(placement))
    placement["mode"] = "local_required"
    placement["eligible_lanes"] = ["dotnet", "python"]
    assert list(Draft202012Validator(schema).iter_errors(placement))
