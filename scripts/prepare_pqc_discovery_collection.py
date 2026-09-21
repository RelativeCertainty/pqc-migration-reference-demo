#!/usr/bin/env python3
"""Materialize the isolated app's saved 27-form collection, not a second workbook writer.

Explicit existing assessment; loopback candidate only; no enterprise identity,
source access, email, submission or owner-validation outcomes. All state changes
go through authenticated C# collection commands and their transactional journal.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import sys
from uuid import uuid4
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assessment-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--confirm-synthetic-collection", action="store_true")
    args = parser.parse_args()
    output = args.output_dir.absolute()
    if not args.confirm_synthetic_collection or not re.fullmatch(r"assessment-[a-f0-9]{32}", args.assessment_id):
        parser.error("explicit synthetic confirmation and an existing assessment identity required")
    if output.exists() or not output.is_relative_to(ROOT / "artifacts/pqc-enterprise-demo") or any(p.is_symlink() for p in (output, *output.parents)):
        parser.error("output must be a new nonsymlink directory within isolated PQC demo artifacts")
    from tests.test_pqc_enterprise_demo_http import Client
    from tests.test_pqc_intake_http import raw_request

    os.umask(0o077)
    client = Client("http://127.0.0.1:18475").login("analyst")
    route = "/api/assessments/" + args.assessment_id + "/discovery"
    status, catalog, _ = client.request(route + "/catalog")
    if status != 200 or catalog.get("formCount") != 27 or not catalog.get("canPrepare"):
        raise RuntimeError("expected isolated collection catalog unavailable")
    recipient = "synthetic-demo:contributor"
    collection = next((c for c in catalog["collections"] if c["assignedTo"] == recipient), None)
    if collection is None:
        status, catalog, _ = client.request(route + "/collections", method="POST",
            body={"expectedRevision": catalog["revision"], "assignedTo": recipient},
            headers={"Idempotency-Key": uuid4().hex})
        if status != 200:
            raise RuntimeError("collection command did not confirm success; inspect saved catalog before retrying")
        collection = next(c for c in catalog["collections"] if c["assignedTo"] == recipient)
    if not collection["packages"]:
        status, catalog, _ = client.request(route + "/collections/" + collection["id"] + "/exports",
            method="POST", body={"expectedRevision": catalog["revision"]},
            headers={"Idempotency-Key": uuid4().hex})
        if status != 200:
            raise RuntimeError("export command did not confirm success; inspect saved catalog before retrying")
        collection = next(c for c in catalog["collections"] if c["id"] == collection["id"])
    package = collection["packages"][-1]
    if not package["zipUrl"].startswith(route + "/collections/"):
        raise RuntimeError("unexpected download route")
    status, payload, _ = raw_request(client, package["zipUrl"])
    if status != 200:
        raise RuntimeError("saved collection download failed")
    expected = {"00_Consolidated_Questions.xlsx", *(entry["filename"] for entry in package["forms"])}
    with ZipFile(BytesIO(payload)) as archive:
        if len(package["forms"]) != 27 or len(archive.namelist()) != 28 or set(archive.namelist()) != expected or archive.testzip():
            raise RuntimeError("invalid collection archive")
        for entry in package["forms"]:
            if not re.fullmatch(r"area-\d{2}/[a-z0-9-]+\.xlsx", entry["filename"]):
                raise RuntimeError("invalid form path")
            if sha256(archive.read(entry["filename"])).hexdigest() != entry["sha256"]:
                raise RuntimeError("form checksum mismatch")
        output.mkdir(mode=0o700, parents=True)
        for name in sorted(expected):
            target = output / name
            target.parent.mkdir(mode=0o700, exist_ok=True)
            target.write_bytes(archive.read(name))
    (output / "PQC_Discovery_27_Forms_and_Consolidated_Questions.zip").write_bytes(payload)
    metadata = {"synthetic": True, "ownerOutcome": "not_recorded", "assessmentId": args.assessment_id,
        "collectionId": collection["id"], "packageId": package["id"], "assignedTo": recipient,
        "templateVersion": catalog["templateVersion"], "domainCount": 10, "formCount": 27,
        "questionsPerForm": 5, "xlsxCount": 28, "zipBytes": len(payload), "zipSha256": sha256(payload).hexdigest(),
        "forms": package["forms"], "zipUrl": package["zipUrl"], "indexUrl": package["indexUrl"],
        "appUrl": "http://127.0.0.1:18475/#discovery?assessment=" + args.assessment_id,
        "boundary": "Synthetic development forms only. Real enterprise responses require separately approved handling and intake."}
    (output / "collection-manifest.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: metadata[key] for key in ("assessmentId", "collectionId", "packageId", "formCount", "xlsxCount", "zipBytes", "appUrl")}))


if __name__ == "__main__":
    main()
