#!/usr/bin/env python3
"""Read back frozen reports from a fresh copy of a stopped synthetic state.

No workflow commands, production connections, browser automation or owner
outcomes. Execute this process inside the existing bounded user cgroup.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.test_pqc_enterprise_demo_http import Client, Server


def verify(package: Path, rehearsal: Path, release_name: str = "release"):
    package, rehearsal = package.absolute(), rehearsal.absolute()
    for path in [package, rehearsal]:
        if any(p.is_symlink() for p in [path, *path.parents]) or not path.is_relative_to(ROOT / "artifacts/pqc-enterprise-demo"):
            raise ValueError("isolated_candidate_required")
    if not rehearsal.is_relative_to(package):
        raise ValueError("candidate_rehearsal_required")
    proof = json.loads((rehearsal / "worked-example.json").read_text())
    fresh = json.loads((rehearsal / "fresh-walkthrough.json").read_text())
    assert proof["status"] == "passed"
    if Path(release_name).name != release_name or not release_name.startswith("release"):
        raise ValueError("explicit_release_name_required")
    dll = package / release_name / "PqcEnterpriseDemo.dll"
    dll_hash = hashlib.sha256(dll.read_bytes()).hexdigest()
    assert dll_hash == proof["buildIdentity"]["dllSha256"]
    root = package / "restore-readback"
    root.mkdir(mode=0o700)
    shutil.copytree(rehearsal / "app-state", root / "app-state")
    server = Server(root, rehearsal / "input/synthetic-input.json", dll=dll)
    original_registry = os.environ.get("PQC_SYNTHETIC_BUNDLE_REGISTRY_FILE")
    os.environ.pop("PQC_SYNTHETIC_BUNDLE_REGISTRY_FILE", None)
    matches = []
    try:
        server.start()
        client = Client(server.origin).login()
        route = "/api/assessments/" + proof["assessmentId"]
        code, state, _ = client.request(route)
        assert code == 200 and all(g["state"] == "qualified" for g in state["gates"])
        for report_id, stem in zip(proof["reportIds"], ["Phase_1_Current_State", "Phase_2_Risk_and_Recommendations"], strict=True):
            code, rendered, _ = client.request(route + "/reports/" + report_id + "/download?format=html")
            assert code == 200
            original = (rehearsal / "reports" / (stem + ".html")).read_bytes()
            assert rendered.encode() == original
            matches.append({"reportId": report_id, "htmlSha256": hashlib.sha256(original).hexdigest(), "exactByteMatch": True})
        code, untouched, _ = client.request("/api/assessments/" + fresh["assessmentId"])
        assert code == 200 and all(not g["decisions"] for g in untouched["gates"])
        result = {"schemaVersion": "pqc.candidate.restore-readback.v1", "status": "passed",
                  "synthetic": True, "buildSha256": dll_hash, "assessmentId": proof["assessmentId"],
                  "reports": matches, "freshGateDecisionsRemainEmpty": True,
                  "workflowWrites": 0, "ownerObservation": None, "evidenceType": "isolated_copy_and_api_readback"}
        (package / "restore-verification.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"status": "passed", "immutableReportsMatched": len(matches), "freshDecisionsEmpty": True}))
    finally:
        server.stop()
        if original_registry is not None:
            os.environ["PQC_SYNTHETIC_BUNDLE_REGISTRY_FILE"] = original_registry


if __name__ == "__main__":
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--rehearsal", type=Path, required=True)
    parser.add_argument("--release-name", default="release")
    args = parser.parse_args()
    verify(args.package, args.rehearsal, args.release_name)
