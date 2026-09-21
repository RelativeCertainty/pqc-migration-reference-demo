#!/usr/bin/env python3
"""Produce an application export in isolated synthetic test state for visual review.

Does not create a workbook independently, contact production, or submit an owner outcome.
Requires an explicit built DLL and existing synthetic fixture. No downloads.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", required=True, type=Path)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    output = args.output_dir.absolute()
    if not output.is_relative_to(ROOT / "artifacts/pqc-enterprise-demo") or output.exists():
        parser.error("output must be a new directory within isolated PQC demo artifacts")
    if any(p.is_symlink() for p in [output, *output.parents]):
        parser.error("symlink output refused")
    if not args.dll.is_file() or not args.fixture.is_file():
        parser.error("explicit existing DLL and synthetic fixture required")
    fixture = json.loads(args.fixture.read_text())
    if fixture.get("synthetic") is not True:
        parser.error("synthetic fixture required")
    os.umask(0o077)
    output.mkdir(mode=0o700)
    os.environ["PQC_ENTERPRISE_DEMO_DLL"] = str(args.dll.resolve())
    from tests.test_pqc_discovery_workbook import Discovery, Server, parse, unpack
    with tempfile.TemporaryDirectory(prefix="pqc-recognition-qa-") as scratch:
        app = Server(Path(scratch), args.fixture.resolve(), dll=args.dll.resolve())
        try:
            app.start()
            form = Discovery(app)
            request = form.create()
            _, payload = form.export(request)
            code, _ = parse(payload)
            if code:
                raise RuntimeError("application-generated workbook failed its parser")
            (output / "synthetic-recognition-review.xlsx").write_bytes(payload)
            detail = form.detail(request)
            recognition = detail.get("recognition")
            metadata = {"synthetic": True, "ownerOutcome": "not_recorded", "workbookParser": "passed",
                "sheetCount": sum(n.startswith("xl/worksheets/sheet") and n.endswith(".xml") for n in unpack(payload)),
                "referenceVersion": recognition["catalogVersion"] if recognition else None,
                "domainCount": len(recognition["domains"]) if recognition else 0,
                "exampleCount": sum(len(f["examples"]) for d in recognition["domains"] for f in d["families"]) if recognition else 0}
            (output / "validation.json").write_text(json.dumps(metadata, indent=2)+"\n")
            print(json.dumps(metadata))
        finally:
            app.stop()


if __name__ == "__main__":
    main()
