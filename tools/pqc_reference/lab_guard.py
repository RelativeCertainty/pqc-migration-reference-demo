"""Fail-closed resource isolation for disposable, owner-run PQC reference labs.

This is a release-excluded engineering harness, not a production execution
adapter. It neither changes existing services nor acquires dependencies.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid

GIB = 1024**3
MIB = 1024**2
LAUNCH_AVAILABLE = 6 * GIB
STOP_AVAILABLE = 4 * GIB
RUNTIME_SECONDS = 300
CLEAN_ENV = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}


class LabBlocked(RuntimeError):
    """The message is a controlled reason code, never child process output."""


def memory_health(proc_root: Path = Path("/proc")) -> dict:
    available = None
    for line in (proc_root / "meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            available = int(line.split()[1]) * 1024
    pressure = {}
    for line in (proc_root / "pressure/memory").read_text().splitlines():
        fields = line.split()
        pressure[fields[0]] = float(dict(f.split("=") for f in fields[1:])["avg10"])
    if available is None or not {"some", "full"} <= pressure.keys():
        raise LabBlocked("memory_health_unavailable")
    return {"available_bytes": available, "some_avg10": pressure["some"], "full_avg10": pressure["full"]}


def check_launch(health: dict) -> None:
    if health["available_bytes"] < LAUNCH_AVAILABLE:
        raise LabBlocked("insufficient_memory_headroom")
    if health["some_avg10"] >= 10 or health["full_avg10"] >= 1:
        raise LabBlocked("memory_pressure_at_launch")


def private_directory(path: Path) -> Path:
    """Create only a dedicated directory; never chmod an existing user tree."""
    path = path.absolute()
    if path.is_symlink():
        raise LabBlocked("unsafe_directory")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    metadata = path.stat()
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise LabBlocked("directory_not_owner_only")
    return path


def lab_root() -> Path:
    root = private_directory(Path.home() / ".cache" / "pqc-reference-labs")
    proc = subprocess.run(
        ["findmnt", "-n", "-o", "FSTYPE", "--target", str(root)],
        capture_output=True, text=True, timeout=5, env=CLEAN_ENV, check=False,
    )
    if proc.returncode or proc.stdout.strip() not in {"ext4", "btrfs", "xfs", "zfs", "ext3"}:
        raise LabBlocked("disk_backed_runtime_required")
    if shutil.disk_usage(root).free < GIB:
        raise LabBlocked("insufficient_disk_headroom")
    return root


@contextlib.contextmanager
def exclusive_lab(root: Path):
    fd = os.open(root / "active.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise LabBlocked("unsafe_lock_file")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LabBlocked("another_reference_lab_active") from exc
        yield
    finally:
        os.close(fd)


def write_metadata(path: Path, value: dict) -> None:
    """Exclusive-create prevents replacing unrelated artifacts or following links."""
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "w") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def verify_cgroup(unit: str, memory_limit: int, *, proc_root: Path = Path("/proc"), cgroup_root: Path = Path("/sys/fs/cgroup")) -> dict:
    if not re.fullmatch(r"pqc-ref-[a-f0-9]{32}\.service", unit):
        raise LabBlocked("invalid_lab_unit")
    own = [line[3:] for line in (proc_root / "self/cgroup").read_text().splitlines() if line.startswith("0::")]
    if len(own) != 1 or Path(own[0]).name != unit:
        raise LabBlocked("not_in_owned_lab_cgroup")
    group = cgroup_root / own[0].lstrip("/")
    try:
        memory = int((group / "memory.max").read_text().strip())
        swap = int((group / "memory.swap.max").read_text().strip())
        tasks = int((group / "pids.max").read_text().strip())
        quota, period = (int(item) for item in (group / "cpu.max").read_text().split())
    except (OSError, ValueError) as exc:
        raise LabBlocked("cgroup_limits_unavailable") from exc
    if memory != memory_limit or swap != 0 or tasks != 64 or not (0 < quota <= period):
        raise LabBlocked("cgroup_limits_not_enforced")
    return {"memory_max_bytes": memory, "memory_swap_max_bytes": swap, "tasks_max": tasks, "cpu_quota": quota, "cpu_period": period, "runtime_max_seconds": RUNTIME_SECONDS}


def _control(*args: str) -> subprocess.CompletedProcess:
    # Only the user bus routing variables cross this boundary, not manager secrets.
    env = dict(CLEAN_ENV)
    for name in ("XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"):
        if name in os.environ:
            env[name] = os.environ[name]
    return subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True, timeout=8, env=env, check=False)


def _properties(unit: str) -> dict:
    result = _control("show", unit, "--property=ActiveState,Result,RuntimeMaxUSec,KillMode,NoNewPrivileges")
    if result.returncode:
        raise LabBlocked("user_service_inspection_failed")
    return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)


def _cleanup(unit: str) -> None:
    """Reconcile ambiguous startup/stop results against the exact owned unit."""
    if not re.fullmatch(r"pqc-ref-[a-f0-9]{32}\.service", unit):
        raise LabBlocked("invalid_lab_cleanup_target")
    try:
        _control("stop", unit)
    except subprocess.TimeoutExpired:
        # Still the same disposable UUID unit, never a discovered production unit.
        _control("kill", "--kill-whom=all", "--signal=KILL", unit)
    inspection = _control("show", unit, "--property=LoadState,ActiveState,ControlGroup")
    properties = dict(line.split("=", 1) for line in inspection.stdout.splitlines() if "=" in line)
    if properties.get("LoadState") == "not-found":
        return
    if inspection.returncode or properties.get("ActiveState") not in {"inactive", "failed"}:
        raise LabBlocked("owned_lab_cleanup_unverified")
    cgroup = properties.get("ControlGroup", "")
    if cgroup:
        if Path(cgroup).name != unit:
            raise LabBlocked("owned_lab_cleanup_unverified")
        root = Path("/sys/fs/cgroup") / cgroup.lstrip("/")
        if any(path.read_text().strip() for path in root.rglob("cgroup.procs")):
            raise LabBlocked("owned_lab_processes_remain")
    _control("reset-failed", unit)


def run_guarded(track: str, root: Path) -> dict:
    """Run exactly one track, stopping only our exact transient unit on pressure."""
    if track not in {"tls", "ssh", "software"}:
        raise ValueError("unknown reference track")
    try:
        health = memory_health()
        check_launch(health)
    except (OSError, ValueError) as exc:
        raise LabBlocked("memory_health_unavailable") from exc
    for tool in ("systemd-run", "systemctl", "openssl") + (("ssh", "sshd", "sftp", "ssh-keygen") if track == "ssh" else ()):
        if shutil.which(tool, path=CLEAN_ENV["PATH"]) is None:
            raise LabBlocked("required_tool_not_installed")
    memory_limit = GIB if track == "software" else 512 * MIB
    unit = "pqc-ref-" + uuid.uuid4().hex + ".service"
    repo_root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="run-", dir=root) as temporary:
        workspace = Path(temporary)
        command = [
            "systemd-run", "--user", "--quiet", "--unit=" + unit,
            "--property=Type=exec", "--property=MemoryMax=" + str(memory_limit),
            "--property=MemorySwapMax=0", "--property=CPUQuota=100%", "--property=TasksMax=64",
            "--property=RuntimeMaxSec=300", "--property=UMask=0077", "--property=KillMode=control-group",
            "--property=NoNewPrivileges=yes", "--property=LimitFSIZE=4194304", "--property=LimitCORE=0",
            "--property=StandardOutput=null", "--property=StandardError=null",
            "--property=WorkingDirectory=" + str(repo_root),
            "/usr/bin/env", "-i", "PATH=/usr/bin:/bin", "LANG=C", "LC_ALL=C",
            sys.executable, "-m", "tools.pqc_reference.crypto_labs", "--execute", track, str(workspace), unit,
        ]
        # systemd-run itself needs the user's bus, but its child receives env -i.
        bus_env = dict(CLEAN_ENV)
        for name in ("XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"):
            if name in os.environ:
                bus_env[name] = os.environ[name]
        attempted = False
        try:
            attempted = True
            launched = subprocess.run(command, capture_output=True, text=True, timeout=10, env=bus_env, check=False)
            if launched.returncode:
                raise LabBlocked("resource_isolation_start_failed")
            deadline = time.monotonic() + RUNTIME_SECONDS + 5
            admission_deadline = time.monotonic() + 15
            admitted = False
            pressure_samples = 0
            while time.monotonic() < deadline:
                current = memory_health()
                pressure_samples = pressure_samples + 1 if (current["some_avg10"] >= 10 or current["full_avg10"] >= 1) else 0
                if current["available_bytes"] < STOP_AVAILABLE or pressure_samples >= 3:
                    raise LabBlocked("lab_stopped_for_host_pressure")
                properties = _properties(unit)
                if not admitted and (workspace / "limits.json").is_file():
                    if properties.get("RuntimeMaxUSec") != "5min" or properties.get("KillMode") != "control-group" or properties.get("NoNewPrivileges") != "yes":
                        raise LabBlocked("service_limits_not_enforced")
                    write_metadata(workspace / "admitted.json", {"admitted": True})
                    admitted = True
                if (workspace / "result.json").is_file():
                    proof = json.loads((workspace / "result.json").read_text())
                    proof["host_launch"] = health
                    return proof
                if properties.get("ActiveState") in {"failed", "inactive"}:
                    raise LabBlocked("isolated_child_stopped_without_proof")
                if not admitted and time.monotonic() > admission_deadline:
                    raise LabBlocked("isolation_admission_timeout")
                time.sleep(0.5)
            raise LabBlocked("lab_runtime_exceeded")
        finally:
            if attempted:
                # Exact UUID unit only; never stop/restart any existing service.
                _cleanup(unit)
