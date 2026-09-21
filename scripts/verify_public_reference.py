#!/usr/bin/env python3
"""Metadata-only publication guard: no matched source values are printed."""
import os
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    paths = [p for p in paths if p and (ROOT / p).is_file()]
    forbidden = {"node_modules", "bin", "obj", "project", "handoff", "case_workspace", "private-runtime", "private-backup", "fixture-custody"}
    patterns = {
        "private-key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "credential-token": re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}|AKIA[0-9A-Z]{16})"),
        "private-user-path": re.compile(rb"/home/" + rb"owner/|Documents/" + rb"Employment/"),
    }
    markers = []
    if marker_path := os.environ.get("PQC_PRIVATE_MARKERS_FILE"):
        source = Path(marker_path).resolve(strict=True)
        if source.is_relative_to(ROOT):
            print("Private marker file must remain outside this checkout.")
            return 2
        markers = [line.lower() for line in source.read_bytes().splitlines() if line.strip()]
    failures = []
    for relative in paths:
        path = ROOT / relative
        if forbidden.intersection(path.relative_to(ROOT).parts) or path.suffix.lower() in {".db", ".sqlite", ".pfx", ".p12", ".key", ".log", ".bundle"}:
            failures.append((relative, "excluded-path"))
        if path.is_symlink():
            failures.append((relative, "symlink-not-public-source"))
            continue
        data = path.read_bytes()
        if path.suffix.lower() in {".xlsx", ".docx", ".pptx"}:
            with zipfile.ZipFile(path) as archive:
                if sum(info.file_size for info in archive.infolist()) > 16 * 1024 * 1024:
                    failures.append((relative, "office-size-limit"))
                    continue
                data = b"\n".join(archive.read(info) for info in archive.infolist() if info.filename.endswith((".xml", ".rels")))
        for label, pattern in patterns.items():
            if pattern.search(data):
                failures.append((relative, label))
        if any(marker in data.lower() for marker in markers):
            failures.append((relative, "private-marker"))
    if sum(p.endswith(".csproj") for p in paths) != 1 or any(p.endswith(".go") or p.startswith("worker/") for p in paths):
        failures.append(("application-topology", "must-have-one-csharp-host-no-legacy-server"))
    for relative, label in failures:
        print(f"BLOCKED {relative}: {label}")
    print(f"Public boundary: {len(paths)} files; {len(failures)} findings. Matched values withheld.")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
