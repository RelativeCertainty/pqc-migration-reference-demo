#!/usr/bin/env python3
"""Start the one C#/React application with isolated synthetic state, never install dependencies."""
from pathlib import Path
import argparse
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18479)
    args = parser.parse_args()
    os.umask(0o077)
    base = ROOT / "artifacts/pqc-enterprise-demo/reference"
    fixture = base / "input/synthetic-input.json"
    if not fixture.exists():
        result = subprocess.run([sys.executable, str(ROOT / "scripts/build_pqc_enterprise_demo_fixture.py"),
                                 "--output-dir", str(base / "input"), "--applications", "36"], cwd=ROOT)
        if result.returncode:
            return result.returncode
    environment = dict(os.environ)
    environment["PQC_QUESTIONNAIRE_CATALOG_FILE"] = str(ROOT / "apps/pqc-enterprise-demo/ReferenceData/questionnaire-catalog.json")
    return subprocess.call([sys.executable, str(ROOT / "scripts/run_pqc_enterprise_demo.py"),
                            "--fixture", str(fixture), "--data-dir", str(base / "state"),
                            "--port", str(args.port)], cwd=ROOT, env=environment)


if __name__ == "__main__":
    raise SystemExit(main())
