"""End-to-end offline development composition; no protocol labs or providers."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.prove_pqc_enterprise_reference import (
    CRYPTO_CHECKS,
    build_reference,
    load_crypto_proofs,
)
from tools.pqc_reference.assessment_store import ReferenceError


def test_generate_actual_reports_reopen_and_restore(tmp_path):
    output = tmp_path / "new-run"
    proof = build_reference(output, application_count=12)
    assert proof["result"] == "pass"
    assert proof["crypto_scope"] == "not_requested_not_proven"
    assert proof["crypto_origin"] == "not_requested"
    assert proof["crypto_results"] == []
    assert proof["counts"]["subjects"] == 60
    assert proof["checks"]["backup_restore"] is True
    assert proof["checks"]["durable_restart"] is True
    assert proof["authority"]["owner_verdict"] is None
    assert not proof["authority"]["source_system_writes"]
    assert not any(name.startswith("private-") for name in proof["artifact_hashes"])
    for relative, digest in proof["artifact_hashes"].items():
        file = output / relative
        assert file.stat().st_mode & 0o077 == 0
        assert hashlib.sha256(file.read_bytes()).hexdigest() == digest
    for phase in (1, 2):
        reader = (output / "reports" / f"phase{phase}-report.readable.html").read_text()
        assert '<html lang="en"' in reader
        assert "noindex,nofollow,noarchive" in reader
        assert "synthetic" in reader.lower()
    assert json.loads((output / "proof.json").read_bytes()) == proof
    prior = (output / "proof.json").read_bytes()
    with pytest.raises(FileExistsError):
        build_reference(output, application_count=12)
    assert (output / "proof.json").read_bytes() == prior


def test_invalid_generation_and_symlink_do_not_create_store(tmp_path):
    output = tmp_path / "invalid"
    with pytest.raises(ValueError):
        build_reference(output, application_count=100000)
    assert not output.exists()
    link = tmp_path / "link"
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ReferenceError, match="symlink"):
        build_reference(link / "invalid", application_count=12)
    assert not output.exists()


def test_crypto_import_requires_exact_sources_and_scope(tmp_path):
    source = Path(__file__).resolve().parents[1] / "tools/pqc_reference"
    hashes = {
        name: hashlib.sha256((source / name).read_bytes()).hexdigest()
        for name in ("crypto_labs.py", "lab_guard.py", "signature_app.py")
    }
    for track in ("tls", "ssh", "software"):
        proof = {
            "type": "pqc.reference.crypto-proof.v1",
            "track": track,
            "synthetic": True,
            "enterprise_migration_authorized": False,
            "source_hashes": hashes,
            "result": "pass",
            "checks": [
                {"name": name, "result": "pass"}
                for name in sorted(CRYPTO_CHECKS[track])
            ],
            "resource_limits": {
                "memory_swap_max_bytes": 0,
                "cpu_quota": 100000,
                "cpu_period": 100000,
                "tasks_max": 64,
                "runtime_max_seconds": 300,
                "memory_max_bytes": (1024 if track == "software" else 512) * 1024**2,
            },
        }
        (tmp_path / f"{track}.proof.json").write_text(json.dumps(proof))
    assert len(load_crypto_proofs(tmp_path)) == 3
    proof["source_hashes"] = dict(hashes, **{"crypto_labs.py": "0" * 64})
    (tmp_path / "software.proof.json").write_text(json.dumps(proof))
    with pytest.raises(ReferenceError, match="source_or_scope_mismatch"):
        load_crypto_proofs(tmp_path)


def test_crypto_import_rejects_empty_pass(tmp_path):
    source = Path(__file__).resolve().parents[1] / "tools/pqc_reference"
    hashes = {
        name: hashlib.sha256((source / name).read_bytes()).hexdigest()
        for name in ("crypto_labs.py", "lab_guard.py", "signature_app.py")
    }
    (tmp_path / "tls.proof.json").write_text(
        json.dumps(
            {
                "type": "pqc.reference.crypto-proof.v1",
                "track": "tls",
                "synthetic": True,
                "enterprise_migration_authorized": False,
                "source_hashes": hashes,
                "result": "pass",
                "checks": [],
            }
        )
    )
    with pytest.raises(ReferenceError, match="invalid_crypto_check_result"):
        load_crypto_proofs(tmp_path)


def test_fresh_safety_block_still_emits_incomplete_milestone(tmp_path, monkeypatch):
    from tools.pqc_reference import crypto_labs, lab_guard

    def insufficient_resources():
        raise lab_guard.LabBlocked("insufficient_memory")

    monkeypatch.setattr(crypto_labs, "lab_root", insufficient_resources)
    output = tmp_path / "blocked-run"
    proof = build_reference(output, application_count=12, crypto=True)
    assert proof["result"] == "incomplete"
    assert proof["crypto_origin"] == "fresh_local_run"
    assert len(proof["crypto_results"]) == 3
    assert all(
        row["result"] == "blocked" and row["checks"] == 0
        for row in proof["crypto_results"]
    )
    assert (output / "proof.json").exists()
    # A failure recorded by this invocation is not portable proof of an old source.
    with pytest.raises(ReferenceError, match="source_or_scope_mismatch"):
        load_crypto_proofs(output / "crypto")
