"""Offline safety tests. Live protocol proofs are an explicit separate command."""
import json
import stat

import pytest

from tools.pqc_reference import crypto_labs, lab_guard, signature_app


def test_memory_health_and_thresholds(tmp_path):
    (tmp_path / "pressure").mkdir()
    (tmp_path / "meminfo").write_text("MemAvailable: 7340032 kB\n")
    (tmp_path / "pressure/memory").write_text("some avg10=0.00 avg60=0.00 total=1\nfull avg10=0.00 avg60=0.00 total=1\n")
    health = lab_guard.memory_health(tmp_path)
    lab_guard.check_launch(health)
    assert health["available_bytes"] == 7 * lab_guard.GIB
    with pytest.raises(lab_guard.LabBlocked, match="insufficient_memory"):
        lab_guard.check_launch(dict(health, available_bytes=6 * lab_guard.GIB - 1))
    with pytest.raises(lab_guard.LabBlocked, match="memory_pressure"):
        lab_guard.check_launch(dict(health, full_avg10=1))


def _cgroup_fixture(tmp_path):
    unit = "pqc-ref-" + "a" * 32 + ".service"
    proc = tmp_path / "proc"
    (proc / "self").mkdir(parents=True)
    (proc / "self/cgroup").write_text("0::/user.slice/" + unit + "\n")
    root = tmp_path / "cgroup"
    group = root / "user.slice" / unit
    group.mkdir(parents=True)
    for name, value in {"memory.max": 512 * lab_guard.MIB, "memory.swap.max": 0, "pids.max": 64, "cpu.max": "100000 100000"}.items():
        (group / name).write_text(str(value))
    return unit, proc, root, group


def test_verified_actual_cgroup_limits(tmp_path):
    unit, proc, root, _ = _cgroup_fixture(tmp_path)
    result = lab_guard.verify_cgroup(unit, 512 * lab_guard.MIB, proc_root=proc, cgroup_root=root)
    assert result["memory_swap_max_bytes"] == 0
    assert result["tasks_max"] == 64


@pytest.mark.parametrize("name,value", [("memory.max", "max"), ("memory.max", str(lab_guard.GIB)), ("memory.swap.max", "1"), ("pids.max", "65"), ("cpu.max", "max 100000"), ("cpu.max", "200000 100000")])
def test_unenforced_limits_fail_closed(tmp_path, name, value):
    unit, proc, root, group = _cgroup_fixture(tmp_path)
    (group / name).write_text(value)
    with pytest.raises(lab_guard.LabBlocked):
        lab_guard.verify_cgroup(unit, 512 * lab_guard.MIB, proc_root=proc, cgroup_root=root)


def test_direct_unguarded_execution_rejected(tmp_path):
    unit, proc, root, _ = _cgroup_fixture(tmp_path)
    (proc / "self/cgroup").write_text("0::/user.slice/existing-production.service\n")
    with pytest.raises(lab_guard.LabBlocked, match="not_in_owned"):
        lab_guard.verify_cgroup(unit, 512 * lab_guard.MIB, proc_root=proc, cgroup_root=root)


def test_private_directory_and_symlink_rejection(tmp_path):
    directory = lab_guard.private_directory(tmp_path / "runtime")
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    link = tmp_path / "alias"
    link.symlink_to(directory)
    with pytest.raises(lab_guard.LabBlocked, match="unsafe_directory"):
        lab_guard.private_directory(link)


def test_global_single_lab_lock(tmp_path):
    with lab_guard.exclusive_lab(tmp_path):
        with pytest.raises(lab_guard.LabBlocked, match="another_reference_lab"):
            with lab_guard.exclusive_lab(tmp_path):
                pytest.fail("second lab must not be admitted")


def test_metadata_is_exclusive_create(tmp_path):
    target = tmp_path / "proof.json"
    lab_guard.write_metadata(target, {"result": "blocked"})
    with pytest.raises(FileExistsError):
        lab_guard.write_metadata(target, {"result": "pass"})
    assert json.loads(target.read_text())["result"] == "blocked"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_blocked_launch_never_starts_service(monkeypatch, tmp_path):
    monkeypatch.setattr(lab_guard, "memory_health", lambda: {"available_bytes": 0, "some_avg10": 0, "full_avg10": 0})
    monkeypatch.setattr(lab_guard.subprocess, "run", lambda *a, **k: pytest.fail("must not launch"))
    with pytest.raises(lab_guard.LabBlocked, match="insufficient_memory"):
        lab_guard.run_guarded("tls", tmp_path)


def test_run_labs_reports_blocks_without_claiming_pass(monkeypatch, tmp_path):
    def blocked():
        raise lab_guard.LabBlocked("disk_backed_runtime_required")
    monkeypatch.setattr(crypto_labs, "lab_root", blocked)
    proofs = crypto_labs.run_labs(tmp_path / "proofs")
    assert len(proofs) == 3
    for proof in proofs:
        assert proof["result"] == "blocked"
        assert proof["checks"] == []
        assert proof["enterprise_migration_authorized"] is False
        assert (tmp_path / "proofs" / (proof["track"] + ".proof.json")).is_file()


def test_unknown_or_duplicate_tracks_rejected(tmp_path):
    for tracks in ((), ("production",), ("tls", "tls")):
        with pytest.raises(ValueError):
            crypto_labs.run_labs(tmp_path / "proofs", tracks)


def test_tls_negotiated_group_parser():
    assert crypto_labs.tls_group("Peer Temp Key: X25519, 253 bits\n") == "X25519"
    assert crypto_labs.tls_group("Negotiated TLS1.3 group: X25519MLKEM768\n") == "X25519MLKEM768"
    assert crypto_labs.tls_group("Supported groups: X25519MLKEM768") is None


def test_tls_success_requires_negotiation_trust_and_application():
    from subprocess import CompletedProcess
    text = "Verification: OK\nNegotiated TLS1.3 group: X25519MLKEM768\nHTTP/1.0 200 ok\n"
    assert crypto_labs._tls_success(CompletedProcess([], 0, text), "X25519MLKEM768")
    assert not crypto_labs._tls_success(CompletedProcess([], 0, text.replace("Verification: OK", "")), "X25519MLKEM768")
    assert not crypto_labs._tls_success(CompletedProcess([], 0, text), "X25519")


def test_ssh_configuration_isolated_and_passwordless(tmp_path):
    text = crypto_labs._ssh_config(tmp_path, 31001, "mlkem768x25519-sha256").read_text()
    assert "ListenAddress 127.0.0.1" in text
    assert "PasswordAuthentication no" in text
    assert "PermitUserRC no" in text
    assert "DisableForwarding yes" in text
    assert "ForceCommand internal-sftp -R" in text
    assert str(tmp_path / "host") in text
    assert "/etc/ssh/sshd_config" not in text
    assert ".ssh/authorized_keys" not in text


def test_ssh_success_cannot_be_faked_by_debug_command_echo():
    from subprocess import CompletedProcess
    result = CompletedProcess([], 0, "Authenticated to loopback\nkex: algorithm: mlkem768x25519-sha256\nSending command: PQC_REFERENCE_SSH_OK\n")
    assert not crypto_labs._ssh_success(result, "mlkem768x25519-sha256")
    result.readback_verified = True
    assert crypto_labs._ssh_success(result, "mlkem768x25519-sha256")


def test_ssh_system_startup_script_blocks_without_reading_or_starting(monkeypatch, tmp_path):
    monkeypatch.setattr(crypto_labs.os, "getuid", lambda: 1000)
    monkeypatch.setattr(crypto_labs.os.path, "lexists", lambda path: path == "/etc/ssh/sshrc")
    monkeypatch.setattr(crypto_labs, "_must", lambda *a: pytest.fail("must not start crypto"))
    with pytest.raises(lab_guard.LabBlocked, match="system_ssh_startup_script_present"):
        crypto_labs.prove_ssh(tmp_path, crypto_labs._base("ssh"))


def test_cleanup_reconciles_failed_stop_against_actual_state(monkeypatch):
    from subprocess import CompletedProcess
    calls = []
    def control(*args):
        calls.append(args)
        if args[0] == "stop":
            return CompletedProcess([], 1, "", "")
        return CompletedProcess([], 0, "LoadState=loaded\nActiveState=active\nControlGroup=\n", "")
    monkeypatch.setattr(lab_guard, "_control", control)
    with pytest.raises(lab_guard.LabBlocked, match="cleanup_unverified"):
        lab_guard._cleanup("pqc-ref-" + "a" * 32 + ".service")
    assert calls[0][0] == "stop"


def test_cleanup_accepts_already_collected_exact_unit(monkeypatch):
    from subprocess import CompletedProcess
    monkeypatch.setattr(lab_guard, "_control", lambda *args: CompletedProcess([], 4, "LoadState=not-found\n", ""))
    lab_guard._cleanup("pqc-ref-" + "a" * 32 + ".service")


def test_cleanup_rejects_unscoped_service_target(monkeypatch):
    monkeypatch.setattr(lab_guard, "_control", lambda *a: pytest.fail("must never target existing service"))
    with pytest.raises(lab_guard.LabBlocked, match="invalid_lab_cleanup_target"):
        lab_guard._cleanup("postgres.service")


def test_signature_input_binds_algorithm_version_and_document():
    first = signature_app.signing_input("legacy-v1", b"synthetic")
    second = signature_app.signing_input("pqc-v2", b"synthetic")
    assert first != second
    assert json.loads(second)["algorithm"] == "ML-DSA-65"
    assert second != signature_app.signing_input("pqc-v2", b"changed")


def test_public_key_algorithm_identifier_does_not_trust_envelope_label():
    algorithm = signature_app.KEY_ALGORITHMS["pqc-v2"]
    body = algorithm + bytes.fromhex("03020000")
    assert signature_app.key_algorithm_identifier(bytes([0x30, len(body)]) + body) == algorithm
    with pytest.raises(ValueError):
        signature_app.key_algorithm_identifier(b"not-der")


def test_legacy_application_rejects_policy_override_before_access(capsys):
    assert signature_app.main(["verify", "--document", "not-read", "--key", "not-read", "--envelope", "not-read",
                               "--version", "legacy-v1", "--policy", "legacy-readback"]) == 2
    assert capsys.readouterr().out == "rejected\n"


def test_signature_policy_rejects_legacy_before_crypto(monkeypatch, tmp_path):
    document = tmp_path / "document"
    document.write_bytes(b"synthetic")
    envelope = json.loads(signature_app.signing_input("legacy-v1", document.read_bytes()))
    envelope["signature"] = "AA=="
    path = tmp_path / "envelope.json"
    path.write_text(json.dumps(envelope))
    monkeypatch.setattr(signature_app, "_openssl", lambda *a: pytest.fail("policy should reject first"))
    assert not signature_app.verify(document, tmp_path / "unused", path, "pqc-only")


def test_signature_tampered_metadata_rejected_before_crypto(monkeypatch, tmp_path):
    document = tmp_path / "document"
    document.write_bytes(b"synthetic")
    envelope = json.loads(signature_app.signing_input("pqc-v2", document.read_bytes()))
    envelope.update(algorithm="ECDSA-P256-SHA256", signature="AA==")
    path = tmp_path / "envelope.json"
    path.write_text(json.dumps(envelope))
    monkeypatch.setattr(signature_app, "_openssl", lambda *a: pytest.fail("tamper must reject first"))
    assert not signature_app.verify(document, tmp_path / "unused", path, "pqc-only")


def test_environment_has_no_credential_or_agent_inheritance():
    assert lab_guard.CLEAN_ENV == {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}
    assert signature_app.ENV == lab_guard.CLEAN_ENV


def test_reference_limitations_do_not_claim_library_upgrade():
    proof = crypto_labs._base("software")
    assert any("NOT a dependency/library upgrade" in item for item in proof["limitations"])


def test_failure_record_never_contains_raw_child_output():
    proof = crypto_labs._base("tls")
    with pytest.raises(crypto_labs.ProofFailure, match="trust_check"):
        crypto_labs._check(proof, "trust_check", False)
    assert proof["checks"] == [{"name": "trust_check", "result": "fail"}]
