"""Launcher registry isolation without starting a service or reading credentials."""
from pathlib import Path
import hashlib
import sys

import pytest

from scripts import run_pqc_enterprise_demo as launcher


def prepared(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    root = tmp_path / "artifacts/pqc-enterprise-demo"
    release = root / "release"
    (release / "wwwroot").mkdir(parents=True)
    (release / "PqcEnterpriseDemo.dll").write_bytes(b"test-only-not-executable")
    (release / "wwwroot/index.html").write_text("<title>Test fixture</title>")
    (release / "wwwroot/asset-manifest.sha256").write_text(
        hashlib.sha256((release / "wwwroot/index.html").read_bytes()).hexdigest() + "  index.html\n")
    fixture = root / "fixture.json"
    fixture.write_text("{}")
    data = root / "test-state"
    args = ["launcher", "--fixture", str(fixture), "--data-dir", str(data),
            "--release-dir", str(release), "--port", "18477"]
    monkeypatch.setattr(launcher.shutil, "which", lambda _: "/test/not-executed")
    calls = []
    monkeypatch.setattr(launcher.subprocess, "call", lambda command, env: calls.append((command, env)) or 0)
    return root, args, calls


def test_launcher_does_not_inherit_another_registry(monkeypatch, tmp_path):
    _, args, calls = prepared(monkeypatch, tmp_path)
    monkeypatch.setenv("PQC_SYNTHETIC_BUNDLE_REGISTRY_FILE", "/unrelated/test-registry.json")
    monkeypatch.setattr(sys, "argv", args)
    assert launcher.main() == 0
    command, environment = calls[0]
    assert "PQC_SYNTHETIC_BUNDLE_REGISTRY_FILE" not in environment
    assert "--property=MemorySwapMax=0" in command
    assert "--property=MemoryMax=1G" in command
    assert "--property=CPUQuota=100%" in command
    assert environment["PQC_DEMO_DATABASE_MAX_MIB"] == "128"


def test_launcher_refuses_a_release_without_a_ui_manifest(monkeypatch, tmp_path):
    root, args, calls = prepared(monkeypatch, tmp_path)
    (root / "release/wwwroot/asset-manifest.sha256").unlink()
    monkeypatch.setattr(sys, "argv", args)
    assert launcher.main() == 1
    assert calls == []


@pytest.mark.parametrize("limit", [128, 256, 512])
def test_launcher_sets_only_explicit_database_budget(monkeypatch, tmp_path, limit):
    _, args, calls = prepared(monkeypatch, tmp_path)
    monkeypatch.setenv("PQC_DEMO_DATABASE_MAX_MIB", "999999")
    monkeypatch.setattr(sys, "argv", args + ["--database-limit-mib", str(limit)])
    assert launcher.main() == 0
    assert calls[0][1]["PQC_DEMO_DATABASE_MAX_MIB"] == str(limit)


def test_launcher_default_budget_does_not_inherit_ambient_override(monkeypatch, tmp_path):
    _, args, calls = prepared(monkeypatch, tmp_path)
    monkeypatch.setenv("PQC_DEMO_DATABASE_MAX_MIB", "512")
    monkeypatch.setattr(sys, "argv", args)
    assert launcher.main() == 0
    assert calls[0][1]["PQC_DEMO_DATABASE_MAX_MIB"] == "128"


@pytest.mark.parametrize("invalid", ["0", "129", "1024", "unlimited"])
def test_launcher_rejects_unqualified_database_limits(monkeypatch, tmp_path, invalid):
    _, args, calls = prepared(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "argv", args + ["--database-limit-mib", invalid])
    with pytest.raises(SystemExit) as error:
        launcher.main()
    assert error.value.code == 2
    assert calls == []


def test_launcher_accepts_only_explicit_isolated_registry(monkeypatch, tmp_path):
    root, args, calls = prepared(monkeypatch, tmp_path)
    registry = root / "synthetic-registry.json"
    registry.write_text("{}")
    monkeypatch.setattr(sys, "argv", args + ["--synthetic-bundle-registry", str(registry)])
    assert launcher.main() == 0
    assert calls[0][1]["PQC_SYNTHETIC_BUNDLE_REGISTRY_FILE"] == str(registry)


def test_launcher_refuses_symlink_or_nonisolated_registry(monkeypatch, tmp_path):
    root, args, calls = prepared(monkeypatch, tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    link = root / "registry-link.json"
    link.symlink_to(outside)
    for invalid in [outside, link]:
        monkeypatch.setattr(sys, "argv", args + ["--synthetic-bundle-registry", str(invalid)])
        assert launcher.main() == 1
    assert calls == []
