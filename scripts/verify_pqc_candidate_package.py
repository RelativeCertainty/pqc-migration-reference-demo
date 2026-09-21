#!/usr/bin/env python3
"""Read-only custody and local-link checks; not browser or owner acceptance."""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1] / "artifacts/pqc-enterprise-demo"


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href", "")
            parsed = urlsplit(href)
            if not parsed.scheme and not parsed.netloc and parsed.path:
                self.paths.append(unquote(parsed.path))


def verify(package: Path) -> dict:
    package = package.absolute()
    if not package.is_relative_to(ROOT) or any(p.is_symlink() for p in (package, *package.parents)):
        raise ValueError("isolated_nonsymlink_candidate_required")
    manifest = json.loads((package / "candidate-manifest.json").read_text())
    checked = set()
    for record in manifest["files"]:
        relative = Path(record["path"])
        file = package / relative
        if relative.is_absolute() or ".." in relative.parts or record["path"] in checked:
            raise ValueError("invalid_or_duplicate_manifest_path")
        if any(p.is_symlink() for p in (file, *file.parents)):
            raise ValueError("manifest_symlink")
        with file.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if file.stat().st_size != record["bytes"] or actual != record["sha256"]:
            raise ValueError("manifest_byte_or_digest_mismatch")
        checked.add(record["path"])
    scenario = json.loads((package / "inputs/scenario.json").read_text())
    cases = scenario["cases"]
    if (len(cases) != 27 or len({c["familyId"] for c in cases}) != 27
            or len({c["questionnaireId"] for c in cases}) != 27
            or len({c["domainId"] for c in cases}) != 10):
        raise ValueError("catalog_cardinality_mismatch")
    if any("inputs/" + case["formPath"] not in checked for case in cases):
        raise ValueError("unsealed_primary_form")
    links = Links()
    links.feed((package / "index.html").read_text())
    for relative in links.paths:
        target = package / relative
        if ".." in Path(relative).parts or not target.is_file():
            raise ValueError("missing_or_unsafe_index_link")
    proof = json.loads((package / manifest["apiProof"]).read_text())
    if proof["reportIds"][0] != manifest["phase1"]["reportId"]:
        raise ValueError("phase1_reference_mismatch")
    restore = json.loads((package / "restore-verification.json").read_text())
    if (restore["status"] != "passed" or restore["assessmentId"] != proof["assessmentId"]
            or restore["buildSha256"] != proof["buildIdentity"]["dllSha256"]
            or not all(r["exactByteMatch"] for r in restore["reports"])):
        raise ValueError("restore_proof_mismatch")
    return {"status": "passed", "evidenceType": "local_file_checks_not_browser_acceptance",
            "hashedFiles": len(checked), "localIndexLinks": len(links.paths),
            "primaryForms": 27, "domains": 10, "ownerOutcome": None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    print(json.dumps(verify(parser.parse_args().package)))
