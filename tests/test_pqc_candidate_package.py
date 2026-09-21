"""Local artifact verification only; no application, browser or owner decisions."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("pqc_candidate_verify", Path(__file__).parents[1] / "scripts/verify_pqc_candidate_package.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


@pytest.fixture
def package(tmp_path, monkeypatch):
    monkeypatch.setattr(verify, "ROOT", tmp_path)
    root = tmp_path / "candidate"
    root.mkdir()
    (root / "inputs").mkdir()
    cases, files = [], []
    for index in range(27):
        name = f"form-{index}.xlsx"
        raw = b"unit-test placeholder; never presented as a real workbook"
        (root / "inputs" / name).write_bytes(raw)
        cases.append({"familyId": f"family-{index}", "questionnaireId": f"q-{index}",
                      "domainId": f"domain-{index % 10}", "formPath": name})
        files.append({"path": "inputs/" + name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    (root / "inputs/scenario.json").write_text(json.dumps({"cases": cases}))
    (root / "proof.json").write_text(json.dumps({"assessmentId": "synthetic-test", "reportIds": ["p1", "p2"],
        "buildIdentity": {"dllSha256": "test-build"}}))
    (root / "restore-verification.json").write_text(json.dumps({"status": "passed", "assessmentId": "synthetic-test",
        "buildSha256": "test-build", "reports": [{"exactByteMatch": True}, {"exactByteMatch": True}]}))
    (root / "candidate-manifest.json").write_text(json.dumps({"files": files, "apiProof": "proof.json", "phase1": {"reportId": "p1"}}))
    (root / "index.html").write_text("<a href='inputs/form-0.xlsx'>Example</a><a href='http://127.0.0.1:18477/'>App</a>")
    return root


def test_candidate_verifier_checks_cardinality_custody_and_links(package):
    result = verify.verify(package)
    assert result["status"] == "passed"
    assert result["primaryForms"] == 27 and result["domains"] == 10
    assert result["ownerOutcome"] is None


def test_changed_artifact_is_not_a_verified_candidate(package):
    (package / "inputs/form-0.xlsx").write_bytes(b"changed")
    with pytest.raises(ValueError, match="digest_mismatch"):
        verify.verify(package)


def test_missing_index_link_is_rejected(package):
    (package / "index.html").write_text("<a href='missing.xlsx'>Form</a>")
    with pytest.raises(ValueError, match="missing_or_unsafe_index_link"):
        verify.verify(package)


def test_different_restore_build_cannot_prove_the_candidate(package):
    restored = json.loads((package / "restore-verification.json").read_text())
    restored["buildSha256"] = "other-build"
    (package / "restore-verification.json").write_text(json.dumps(restored))
    with pytest.raises(ValueError, match="restore_proof_mismatch"):
        verify.verify(package)


def test_duplicate_family_cannot_hide_a_missing_questionnaire(package):
    scenario = json.loads((package / "inputs/scenario.json").read_text())
    scenario["cases"][26]["familyId"] = "family-0"
    (package / "inputs/scenario.json").write_text(json.dumps(scenario))
    with pytest.raises(ValueError, match="catalog_cardinality_mismatch"):
        verify.verify(package)
