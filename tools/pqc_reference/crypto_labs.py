"""Explicit, release-excluded PQC loopback proof commands; never run on import.

Public references (checked 2026-09-05):
https://docs.openssl.org/3.5/man1/openssl-s_client/
https://docs.openssl.org/3.5/man1/openssl-pkeyutl/
https://www.openssh.org/pq.html
https://man.openbsd.org/sshd_config
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import os
from pathlib import Path
import pwd
import re
import socket
import subprocess
import sys
import time
import uuid
from typing import Iterator

from .lab_guard import (CLEAN_ENV, GIB, MIB, LabBlocked, exclusive_lab, lab_root,
                        private_directory, run_guarded, verify_cgroup, write_metadata)

TYPE = "pqc.reference.crypto-proof.v1"
TRACKS = ("tls", "ssh", "software")
LIMITATIONS = {
    "tls": ["Synthetic loopback OpenSSL client/server only; not enterprise load-balancer interoperability.",
            "Hybrid key establishment only; certificate authentication remains ECDSA.",
            "Classical restoration is a recovery exercise, not a quantum-safe target."],
    "ssh": ["Synthetic keys with the existing OS uid; no operating-system account is created or changed.",
            "Isolated loopback sshd only; host SSH service/configuration and normal access remain untouched.",
            "Read-only internal-sftp reads one synthetic artifact; no login shell or shell startup files run.",
            "Hybrid key exchange only; host/user signatures remain Ed25519."],
    "software": ["Owned synthetic signer/verifier application; no enterprise application or hosted pull request.",
                 "Algorithm/API migration on one installed OpenSSL version; NOT a dependency/library upgrade.",
                 "Legacy readback is explicit; it does not make legacy ECDSA signatures quantum-resistant."],
}


class ProofFailure(RuntimeError):
    pass


def _base(track: str) -> dict:
    return {"type": TYPE, "track": track, "result": "blocked", "synthetic": True,
            "proof_level": "isolated_reference", "enterprise_migration_authorized": False,
            "checks": [], "limitations": list(LIMITATIONS[track])}


def _check(proof: dict, name: str, passed: bool) -> None:
    proof["checks"].append({"name": name, "result": "pass" if passed else "fail"})
    if not passed:
        raise ProofFailure(name)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _command(command: list[str], work: Path, *, data: str | None = None, timeout: int = 15) -> subprocess.CompletedProcess:
    """Bound output to a private file and never put it in proof artifacts/errors."""
    output = work / "command-output"
    with output.open("w+b") as log:
        child = subprocess.run(command, input=data.encode() if data is not None else None,
                               stdin=subprocess.DEVNULL if data is None else None,
                               stdout=log, stderr=subprocess.STDOUT, timeout=timeout,
                               cwd=work, env=CLEAN_ENV, check=False)
        if log.tell() > 256 * 1024:
            raise ProofFailure("child_output_limit")
        log.seek(0)
        text = log.read(256 * 1024).decode("utf-8", errors="replace")
    return subprocess.CompletedProcess(command, child.returncode, text, "")


def _must(command: list[str], work: Path) -> None:
    if _command(command, work).returncode:
        raise ProofFailure("synthetic_setup_failed")


def _port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextlib.contextmanager
def _server(command: list[str], work: Path, port: int) -> Iterator[subprocess.Popen]:
    with (work / "server-output").open("w+b") as log:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   cwd=work, env=CLEAN_ENV)
        try:
            for _ in range(60):
                if process.poll() is not None:
                    raise ProofFailure("isolated_server_start_failed")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise ProofFailure("isolated_server_readiness_timeout")
            yield process
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)


def _versions(track: str, work: Path) -> dict:
    result = {"openssl": _command(["/usr/bin/openssl", "version"], work).stdout.strip()}
    if track == "ssh":
        result["openssh"] = _command(["/usr/bin/ssh", "-V"], work).stdout.strip()
    if track == "software":
        result["python"] = sys.version.split()[0]
    # Version command output is allowlisted, not arbitrary subprocess output.
    if not result["openssl"].startswith("OpenSSL ") or len(result["openssl"]) > 180:
        raise ProofFailure("tool_version_unrecognized")
    if "openssh" in result and (not result["openssh"].startswith("OpenSSH_") or len(result["openssh"]) > 180):
        raise ProofFailure("tool_version_unrecognized")
    return result


def _ca(work: Path, stem: str) -> None:
    _must(["/usr/bin/openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
           "-noenc", "-keyout", str(work / (stem + ".key")), "-out", str(work / (stem + ".crt")),
           "-days", "1", "-subj", "/CN=PQC Synthetic Reference CA", "-addext", "basicConstraints=critical,CA:TRUE",
           "-addext", "keyUsage=critical,keyCertSign,cRLSign"], work)


def _tls_identity(work: Path) -> None:
    _ca(work, "ca")
    _ca(work, "untrusted")
    _must(["/usr/bin/openssl", "req", "-new", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
           "-noenc", "-keyout", str(work / "leaf.key"), "-out", str(work / "leaf.csr"),
           "-subj", "/CN=pqc-lab.invalid"], work)
    (work / "leaf.ext").write_text("subjectAltName=DNS:pqc-lab.invalid\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=serverAuth\n")
    _must(["/usr/bin/openssl", "x509", "-req", "-in", str(work / "leaf.csr"), "-CA", str(work / "ca.crt"),
           "-CAkey", str(work / "ca.key"), "-set_serial", "1", "-days", "1", "-extfile", str(work / "leaf.ext"),
           "-out", str(work / "leaf.crt")], work)


def tls_group(output: str) -> str | None:
    match = re.search(r"(?:Negotiated TLS1\.3 group|Peer Temp Key|Server Temp Key):\s*([A-Za-z0-9_-]+)", output)
    return match.group(1) if match else None


def _tls_client(work: Path, port: int, groups: str, *, hostname: str = "pqc-lab.invalid", ca: str = "ca.crt", protocol: str = "-tls1_3") -> subprocess.CompletedProcess:
    return _command(["/usr/bin/openssl", "s_client", "-brief", "-ign_eof", "-connect", f"127.0.0.1:{port}",
                     "-servername", "pqc-lab.invalid", "-verify_hostname", hostname, "-verify_return_error",
                     "-CAfile", str(work / ca), "-no-CApath", "-no-CAstore", protocol, "-groups", groups], work,
                    data="GET / HTTP/1.0\r\nHost: pqc-lab.invalid\r\n\r\n")


def _tls_server(work: Path, port: int, groups: str) -> list[str]:
    return ["/usr/bin/openssl", "s_server", "-accept", f"127.0.0.1:{port}", "-tls1_3", "-groups", groups,
            "-cert", str(work / "leaf.crt"), "-key", str(work / "leaf.key"), "-www", "-quiet"]


def _tls_success(result: subprocess.CompletedProcess, group: str) -> bool:
    return (result.returncode == 0 and "Verification: OK" in result.stdout and "HTTP/1.0 200 ok" in result.stdout
            and (tls_group(result.stdout) or "").lower() == group.lower())


def prove_tls(work: Path, proof: dict) -> None:
    _tls_identity(work)
    port = _port()
    with _server(_tls_server(work, port, "X25519"), work, port):
        baseline = _tls_client(work, port, "X25519")
        _check(proof, "classical_baseline_trust_hostname_response", _tls_success(baseline, "X25519"))
    with _server(_tls_server(work, port, "X25519MLKEM768"), work, port):
        migrated = _tls_client(work, port, "X25519MLKEM768")
        _check(proof, "hybrid_negotiated_trust_hostname_response", _tls_success(migrated, "X25519MLKEM768"))
        mixed = _tls_client(work, port, "X25519MLKEM768:X25519")
        _check(proof, "mixed_capability_client_selects_hybrid", _tls_success(mixed, "X25519MLKEM768"))
        wrong_name = _tls_client(work, port, "X25519MLKEM768", hostname="wrong.invalid")
        _check(proof, "wrong_hostname_rejected", wrong_name.returncode != 0 and "hostname mismatch" in wrong_name.stdout)
        wrong_ca = _tls_client(work, port, "X25519MLKEM768", ca="untrusted.crt")
        _check(proof, "untrusted_issuer_rejected", wrong_ca.returncode != 0 and "certificate verify failed" in wrong_ca.stdout)
        classical = _tls_client(work, port, "X25519")
        _check(proof, "forbidden_classical_fallback_rejected", classical.returncode != 0 and "HTTP/1.0 200 ok" not in classical.stdout)
        incompatible = _tls_client(work, port, "X25519", protocol="-tls1_2")
        _check(proof, "incompatible_protocol_rejected", incompatible.returncode != 0 and "HTTP/1.0 200 ok" not in incompatible.stdout)
        _check(proof, "hybrid_service_survives_negative_checks", _tls_success(_tls_client(work, port, "X25519MLKEM768"), "X25519MLKEM768"))
    with _server(_tls_server(work, port, "X25519"), work, port):
        _check(proof, "classical_configuration_restored", _tls_success(_tls_client(work, port, "X25519"), "X25519"))
    proof["negotiated"] = {"baseline": "X25519", "target": "X25519MLKEM768", "certificate_signature": "ECDSA"}


def _ssh_config(work: Path, port: int, group: str) -> Path:
    username = pwd.getpwuid(os.getuid()).pw_name
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", username):
        raise LabBlocked("unsupported_os_username")
    path = work / "sshd.conf"
    path.write_text(f"""Port {port}
ListenAddress 127.0.0.1
AddressFamily inet
HostKey {work / 'host'}
PidFile {work / 'sshd.pid'}
AuthorizedKeysFile {work / 'user.pub'}
AuthorizedKeysCommand none
AuthorizedPrincipalsFile none
TrustedUserCAKeys none
AllowUsers {username}
UsePAM no
PasswordAuthentication no
KbdInteractiveAuthentication no
HostbasedAuthentication no
GSSAPIAuthentication no
PubkeyAuthentication yes
AuthenticationMethods publickey
PermitRootLogin no
PermitEmptyPasswords no
PermitUserEnvironment no
PermitUserRC no
PermitTTY no
StrictModes yes
DisableForwarding yes
X11Forwarding no
PermitTunnel no
MaxSessions 1
MaxStartups 2
LoginGraceTime 10
KexAlgorithms {group}
Subsystem sftp internal-sftp
ForceCommand internal-sftp -R -d {work}
LogLevel VERBOSE
""")
    return path


def _ssh_client(work: Path, port: int, group: str, *, known_hosts: str = "known_hosts", identity: str = "user") -> subprocess.CompletedProcess:
    readback = work / ("readback-" + uuid.uuid4().hex)
    batch = work / "sftp.batch"
    batch.write_text(f'get "{work / "synthetic-artifact"}" "{readback}"\n')
    result = _command(["/usr/bin/sftp", "-F", str(work / "ssh.conf"), "-vv", "-P", str(port),
                       "-b", str(batch), "-o", "KexAlgorithms=" + group,
                       "-o", "UserKnownHostsFile=" + str(work / known_hosts),
                       "-i", str(work / identity), "127.0.0.1"], work)
    # Readback is independent of debug logs, which can echo commands/markers.
    result.readback_verified = readback.is_file() and readback.read_bytes() == b"PQC_REFERENCE_SSH_ARTIFACT\n"
    if readback.exists():
        readback.unlink()
    return result


def _ssh_success(result: subprocess.CompletedProcess, group: str) -> bool:
    return result.returncode == 0 and getattr(result, "readback_verified", False) and "kex: algorithm: " + group in result.stdout and "Authenticated to " in result.stdout


def prove_ssh(work: Path, proof: dict) -> None:
    if os.getuid() == 0:
        raise LabBlocked("ssh_reference_requires_unprivileged_user")
    # OpenSSH 10.0's session.c calls the system sshrc even for internal-sftp.
    # Inspect presence only, never contents, and refuse rather than execute it.
    if any(os.path.lexists(path) for path in ("/etc/ssh/sshrc", "/usr/local/etc/sshrc", "/usr/local/etc/ssh/sshrc")):
        raise LabBlocked("system_ssh_startup_script_present")
    _check(proof, "no_system_ssh_startup_script_present", True)
    for stem in ("host", "user", "wrong"):
        _must(["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "pqc-synthetic-reference", "-f", str(work / stem)], work)
    (work / "known_hosts").write_text("pqc-reference " + (work / "host.pub").read_text())
    (work / "wrong_hosts").write_text("pqc-reference " + (work / "wrong.pub").read_text())
    (work / "synthetic-artifact").write_bytes(b"PQC_REFERENCE_SSH_ARTIFACT\n")
    (work / "ssh.conf").write_text("""Host *
  BatchMode yes
  StrictHostKeyChecking yes
  GlobalKnownHostsFile /dev/null
  HostKeyAlias pqc-reference
  CheckHostIP no
  UpdateHostKeys no
  VerifyHostKeyDNS no
  IdentitiesOnly yes
  IdentityAgent none
  PasswordAuthentication no
  KbdInteractiveAuthentication no
  PreferredAuthentications publickey
  ConnectTimeout 5
  ConnectionAttempts 1
  RequestTTY no
  ClearAllForwardings yes
  ForwardAgent no
  ForwardX11 no
  ProxyCommand none
  ProxyJump none
""")
    port = _port()
    def server(group):
        configuration = _ssh_config(work, port, group)
        return _server(["/usr/bin/sshd", "-D", "-e", "-f", str(configuration)], work, port)
    with server("curve25519-sha256"):
        _check(proof, "classical_baseline_authenticated_readback", _ssh_success(_ssh_client(work, port, "curve25519-sha256"), "curve25519-sha256"))
    with server("mlkem768x25519-sha256"):
        _check(proof, "hybrid_kex_authenticated_readback", _ssh_success(_ssh_client(work, port, "mlkem768x25519-sha256"), "mlkem768x25519-sha256"))
        _check(proof, "mixed_client_selects_hybrid", _ssh_success(_ssh_client(work, port, "mlkem768x25519-sha256,curve25519-sha256"), "mlkem768x25519-sha256"))
        wrong_host = _ssh_client(work, port, "mlkem768x25519-sha256", known_hosts="wrong_hosts")
        _check(proof, "wrong_host_identity_rejected", wrong_host.returncode != 0 and "Host key verification failed" in wrong_host.stdout)
        wrong_key = _ssh_client(work, port, "mlkem768x25519-sha256", identity="wrong")
        _check(proof, "unauthorized_synthetic_identity_rejected", wrong_key.returncode != 0 and "Permission denied" in wrong_key.stdout)
        classical = _ssh_client(work, port, "curve25519-sha256")
        _check(proof, "forbidden_classical_fallback_rejected", classical.returncode != 0 and "no matching key exchange method" in classical.stdout)
        _check(proof, "access_preserved_after_negative_checks", _ssh_success(_ssh_client(work, port, "mlkem768x25519-sha256"), "mlkem768x25519-sha256"))
    with server("curve25519-sha256"):
        _check(proof, "classical_configuration_restored", _ssh_success(_ssh_client(work, port, "curve25519-sha256"), "curve25519-sha256"))
    proof["negotiated"] = {"baseline": "curve25519-sha256", "target": "mlkem768x25519-sha256", "host_and_user_signatures": "Ed25519"}


def prove_software(work: Path, proof: dict) -> None:
    from . import signature_app
    import py_compile
    # Versioned owned application entrypoints are built and then actually run.
    # The OpenSSL runtime stays unchanged and is explicitly recorded as such.
    source = Path(signature_app.__file__).resolve()
    (work / "signature_app.py").write_bytes(source.read_bytes())
    builds = {}
    for version, policy in (("legacy-v1", "legacy-only"), ("pqc-v2", "pqc-only")):
        launcher = work / (version + ".py")
        launcher.write_text("import sys\nfrom signature_app import main\n"
                            + f"APP_VERSION = {version!r}\nDEFAULT_POLICY = {policy!r}\n"
                            + "args = sys.argv[1:]\n"
                            + "if '--policy' not in args: args += ['--policy', DEFAULT_POLICY]\n"
                            + "raise SystemExit(main(args + ['--version', APP_VERSION]))\n")
        built = work / (version + ".pyc")
        py_compile.compile(str(launcher), cfile=str(built), dfile=f"/pqc-reference/{version}.py", doraise=True,
                           invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH)
        builds[version] = {"entrypoint_sha256": _hash(launcher), "build_sha256": _hash(built), "shared_application_sha256": _hash(source)}
    proof["application_builds"] = builds
    proof["dependency_upgrade"] = False
    document = work / "document"
    document.write_bytes(b"Synthetic release artifact: reference document revision 1.\n")
    (work / "tampered").write_bytes(b"Synthetic altered document.\n")
    for stem, algorithm in (("legacy", "EC"), ("pqc", "ML-DSA-65"), ("wrong", "ML-DSA-65")):
        command = ["/usr/bin/openssl", "genpkey", "-algorithm", algorithm, "-out", str(work / (stem + ".key"))]
        if algorithm == "EC":
            command += ["-pkeyopt", "ec_paramgen_curve:prime256v1"]
        _must(command, work)
        _must(["/usr/bin/openssl", "pkey", "-in", str(work / (stem + ".key")), "-pubout", "-out", str(work / (stem + ".pub"))], work)
    def app(version, operation, *, key, envelope, doc="document", policy=None):
        command = [sys.executable, str(work / (version + ".pyc")), operation,
                   "--document", str(work / doc), "--key", str(work / key), "--envelope", str(work / envelope)]
        if policy:
            command += ["--policy", policy]
        return _command(command, work)
    _check(proof, "legacy_application_build_signs_document", app("legacy-v1", "sign", key="legacy.key", envelope="legacy.json").returncode == 0)
    _check(proof, "legacy_application_verifies_document", app("legacy-v1", "verify", key="legacy.pub", envelope="legacy.json").returncode == 0)
    _check(proof, "pqc_application_build_signs_document", app("pqc-v2", "sign", key="pqc.key", envelope="pqc.json").returncode == 0)
    _check(proof, "pqc_application_verifies_document", app("pqc-v2", "verify", key="pqc.pub", envelope="pqc.json").returncode == 0)
    _check(proof, "wrong_algorithm_key_cannot_be_labeled_pqc", app("pqc-v2", "sign", key="legacy.key", envelope="mislabeled.json").returncode == 2)
    _check(proof, "tampered_document_rejected", app("pqc-v2", "verify", key="pqc.pub", envelope="pqc.json", doc="tampered").returncode == 2)
    _check(proof, "wrong_signing_key_rejected", app("pqc-v2", "verify", key="wrong.pub", envelope="pqc.json").returncode == 2)
    _check(proof, "pqc_policy_rejects_classical_artifact", app("pqc-v2", "verify", key="legacy.pub", envelope="legacy.json").returncode == 2)
    _check(proof, "legacy_readback_requires_explicit_policy", app("pqc-v2", "verify", key="legacy.pub", envelope="legacy.json", policy="legacy-readback").returncode == 0)
    _check(proof, "old_verifier_rejects_new_signature", app("legacy-v1", "verify", key="pqc.pub", envelope="pqc.json").returncode == 2)
    _check(proof, "old_verifier_cannot_enable_new_algorithm_by_policy", app("legacy-v1", "verify", key="pqc.pub", envelope="pqc.json", policy="legacy-readback").returncode == 2)
    _check(proof, "restored_legacy_build_reads_legacy_artifact", app("legacy-v1", "verify", key="legacy.pub", envelope="legacy.json").returncode == 0)
    _check(proof, "restored_legacy_build_cannot_read_new_artifact", app("legacy-v1", "verify", key="pqc.pub", envelope="pqc.json").returncode == 2)
    _check(proof, "pqc_verifier_restored_after_recovery_exercise", app("pqc-v2", "verify", key="pqc.pub", envelope="pqc.json").returncode == 0)
    proof["migration"] = {"baseline": "ECDSA-P256-SHA256", "target": "ML-DSA-65", "rollback_limitation": "Keep the new verifier available for newly signed artifacts."}


def _execute(track: str, work: Path, unit: str) -> int:
    os.umask(0o077)
    proof = _base(track)
    started = time.monotonic()
    try:
        private_directory(work)
        proof["resource_limits"] = verify_cgroup(unit, GIB if track == "software" else 512 * MIB)
        write_metadata(work / "limits.json", proof["resource_limits"])
        deadline = time.monotonic() + 15
        while not (work / "admitted.json").is_file():
            if time.monotonic() > deadline:
                raise LabBlocked("parent_admission_missing")
            time.sleep(0.1)
        proof["versions"] = _versions(track, work)
        proof["source_hashes"] = {name: _hash(Path(__file__).with_name(name)) for name in ("crypto_labs.py", "lab_guard.py", "signature_app.py")}
        {"tls": prove_tls, "ssh": prove_ssh, "software": prove_software}[track](work, proof)
        proof["result"] = "pass"
    except LabBlocked as exc:
        proof["reason"] = str(exc)
    except ProofFailure as exc:
        proof["result"] = "fail"
        proof["reason"] = str(exc)
    except subprocess.TimeoutExpired:
        proof["result"] = "fail"
        proof["reason"] = "bounded_child_timeout"
    except Exception:
        # No exception text, raw subprocess output, keys or payloads leave the lab.
        proof["result"] = "fail"
        proof["reason"] = "isolated_reference_exception"
    proof["elapsed_seconds"] = round(time.monotonic() - started, 3)
    write_metadata(work / "result.json", proof)
    return 0 if proof["result"] == "pass" else 1


def run_labs(output_dir: Path, tracks: tuple[str, ...] = TRACKS) -> list[dict]:
    """Explicitly run sequential isolated labs, recording metadata-only results.

    An unavailable safety control yields blocked evidence; it never falls back
    to an unconstrained process, container, privileged command or network pull.
    """
    if not tracks or len(set(tracks)) != len(tracks) or any(track not in TRACKS for track in tracks):
        raise ValueError("select distinct known reference tracks")
    output = private_directory(output_dir)
    if any((output / (track + ".proof.json")).exists() for track in tracks):
        raise FileExistsError("proof output already exists; select a new run directory")
    proofs = []
    try:
        root = lab_root()
        with exclusive_lab(root):
            for track in tracks:
                try:
                    proof = run_guarded(track, root)
                except LabBlocked as exc:
                    proof = _base(track)
                    proof["reason"] = str(exc)
                except (OSError, ValueError, subprocess.TimeoutExpired):
                    proof = _base(track)
                    proof["reason"] = "safety_control_unavailable"
                proofs.append(proof)
    except LabBlocked as exc:
        proofs = [dict(_base(track), reason=str(exc)) for track in tracks]
    for proof in proofs:
        write_metadata(output / (proof["track"] + ".proof.json"), proof)
    return proofs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", choices=TRACKS)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("unit")
    arguments = parser.parse_args()
    if arguments.execute is None:
        parser.error("internal guarded entrypoint requires --execute")
    return _execute(arguments.execute, arguments.workspace, arguments.unit)


if __name__ == "__main__":
    raise SystemExit(main())
