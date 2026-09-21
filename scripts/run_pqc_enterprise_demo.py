#!/usr/bin/env python3
"""Run only the isolated synthetic C#/React app with enforced resource limits.

This is development launch tooling, not installation or production activation.
No dependencies are downloaded. Stop the foreground command with Ctrl+C.
"""
from __future__ import annotations

import argparse
import fcntl
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/pqc-enterprise-demo"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18473)
    parser.add_argument("--database-limit-mib", type=int, choices=(128, 256, 512), default=128,
        help="Explicit bounded synthetic SQLite capacity; default 128 MiB. Existing history is never pruned.")
    parser.add_argument("--release-dir", type=Path, help="Explicit immutable build under the isolated demo artifacts directory")
    parser.add_argument("--synthetic-bundle-registry", type=Path,
        help="Explicit bounded synthetic reference-bundle registry; never an enterprise trust store")
    args = parser.parse_args()
    fixture = args.fixture.absolute()
    data = args.data_dir.absolute()
    dll = APP / "bin/Release/net10.0/PqcEnterpriseDemo.dll"
    web = APP / "wwwroot"
    try:
        if args.release_dir is not None:
            release = args.release_dir.absolute()
            if not release.is_relative_to(ROOT / "artifacts/pqc-enterprise-demo") or any(p.is_symlink() for p in (release, *release.parents)):
                raise ValueError("release_must_be_in_isolated_pqc_demo_artifacts")
            release = release.resolve(strict=True)
            if not release.is_relative_to(ROOT / "artifacts/pqc-enterprise-demo"):
                raise ValueError("release_must_be_in_isolated_pqc_demo_artifacts")
            dll, web = release / "PqcEnterpriseDemo.dll", release / "wwwroot"
        if not dll.is_file() or not (web / "index.html").is_file() or not (web / "asset-manifest.sha256").is_file():
            raise ValueError("build_csharp_and_react_first")
        if not fixture.is_file() or any(p.is_symlink() for p in (fixture, *fixture.parents, data, *data.parents)):
            raise ValueError("explicit_nonsymlink_fixture_and_data_required")
        data = data.resolve()
        if not data.is_relative_to(ROOT / "artifacts/pqc-enterprise-demo"):
            raise ValueError("data_must_be_in_isolated_pqc_demo_artifacts")
        if not 1024 <= args.port <= 65535 or args.port == 5432:
            raise ValueError("invalid_demo_port")
        if not shutil.which("systemd-run") or not shutil.which("dotnet"):
            raise ValueError("dotnet_and_user_cgroup_support_required")
        memory = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
        if int(memory["MemAvailable"].split()[0]) < 3 * 1024 * 1024:
            raise ValueError("less_than_3GiB_available_refusing_start")
        if shutil.disk_usage(ROOT).free < 2 * 1024**3:
            raise ValueError("less_than_2GiB_disk_free_refusing_start")
        registry = None
        if args.synthetic_bundle_registry is not None:
            registry = args.synthetic_bundle_registry.absolute()
            if (not registry.is_file() or any(p.is_symlink() for p in (registry, *registry.parents))
                    or not registry.resolve().is_relative_to(ROOT / "artifacts/pqc-enterprise-demo")
                    or not 2 <= registry.stat().st_size <= 256 * 1024):
                raise ValueError("bounded_isolated_synthetic_bundle_registry_required")
        os.umask(0o077)
        data.mkdir(mode=0o700, parents=True, exist_ok=True)
        if data.stat().st_mode & 0o077:
            raise ValueError("owner_only_data_directory_required")
        # One launcher across this isolated app, not a lock on production.
        lock_path = ROOT / "artifacts/pqc-enterprise-demo/launcher.lock"
        if lock_path.is_symlink():
            raise ValueError("invalid_launcher_lock")
        with lock_path.open("a") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            unit = "pqc-enterprise-demo-" + uuid.uuid4().hex[:12]
            command = ["systemd-run", "--user", "--scope", "--quiet", "--unit", unit,
                "--property=MemoryMax=1G", "--property=MemorySwapMax=0", "--property=CPUQuota=100%",
                "--property=TasksMax=128", "--property=RuntimeMaxSec=7200", "--",
                "dotnet", str(dll), "--data-dir", str(data), "--fixture", str(fixture),
                "--web-root", str(web), "--port", str(args.port)]
            print(f"Synthetic C#/React demo: http://127.0.0.1:{args.port}/", flush=True)
            print("Host-only access. Fixed synthetic assessment personas; no enterprise SSO. Ctrl+C stops only this app.", flush=True)
            environment = {**os.environ, "DOTNET_PROCESSOR_COUNT": "1", "DOTNET_CLI_TELEMETRY_OPTOUT": "1"}
            environment["PQC_DEMO_DATABASE_MAX_MIB"] = str(args.database_limit_mib)
            # Do not accidentally inherit an unrelated rehearsal's trust list.
            environment.pop("PQC_SYNTHETIC_BUNDLE_REGISTRY_FILE", None)
            if registry is not None:
                environment["PQC_SYNTHETIC_BUNDLE_REGISTRY_FILE"] = str(registry.resolve())
            return subprocess.call(command, env=environment)
    except (OSError, ValueError) as error:
        # Stable local validation messages only; never echo process environments.
        print(str(error) if isinstance(error, ValueError) else "demo_launch_failed", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
