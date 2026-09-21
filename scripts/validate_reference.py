#!/usr/bin/env python3
"""One sequential post-commit validation run. Development evidence, not enterprise activation."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/pqc-enterprise-demo"


def main():
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip():
        print("Commit the reviewed source before running post-commit validation.")
        return 2
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = ROOT / "artifacts/reference-validation" / f"{revision[:12]}-{stamp}"
    output.mkdir(parents=True, mode=0o700)
    env = dict(os.environ, DOTNET_PROCESSOR_COUNT="1", DOTNET_CLI_TELEMETRY_OPTOUT="1")
    for key in ("PQC_SYNTHETIC_BUNDLE_REGISTRY_FILE", "PQC_BROWSER_PROOF_FILE", "PBA_OBSERVABILITY_URL"):
        env.pop(key, None)
    env["PQC_QUESTIONNAIRE_CATALOG_FILE"] = str(APP / "ReferenceData/questionnaire-catalog.json")
    env["PQC_ENTERPRISE_DEMO_DLL"] = str(APP / "bin/Release/net10.0/PqcEnterpriseDemo.dll")
    steps = [
        ("public-boundary", [sys.executable, "scripts/verify_public_reference.py"]),
        ("csharp", ["dotnet", "build", str(APP / "PqcEnterpriseDemo.csproj"), "--no-restore", "-c", "Release", "-m:1"]),
        ("react-build", ["npm", "--prefix", str(APP / "frontend"), "run", "build"]),
        ("python", [sys.executable, "-m", "pytest", "tests", "scripts/test_pqc_bom.py", "-q", "-ra", "--tb=short"]),
        ("react-tests", ["npm", "--prefix", str(APP / "frontend"), "test"]),
        ("recorder", ["node", "--test", "tests/test_pqc_browser_video_recorder.mjs"]),
    ]
    results = []
    for name, command in steps:
        print(f"Running {name}", flush=True)
        with (output / f"{name}.log").open("w") as log:
            try:
                code = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=1800).returncode
            except subprocess.TimeoutExpired:
                code = 124
        results.append({"check": name, "exitCode": code})
        print(f"{name}: {'PASS' if code == 0 else 'FAIL'}", flush=True)
    (output / "results.json").write_text(json.dumps({"revision": revision, "scope": "synthetic development; no owner acceptance", "results": results}, indent=2) + "\n")
    print(f"Evidence: {output.relative_to(ROOT)}")
    return int(any(result["exitCode"] for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
