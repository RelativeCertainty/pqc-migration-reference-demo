#!/usr/bin/env python3
"""Render the public-product recognition catalog as a local human-readable reference.

No network access, enterprise records, product recommendation or publication.
"""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/pqc-enterprise-demo"


def main():
    domains = [domain for segment in ("1-5", "6-10") for domain in json.loads(
        (APP / f"ReferenceData/recognition-domains-{segment}.v1.json").read_text())["domains"]]
    count = sum(len(family["examples"]) for domain in domains for family in domain["families"])
    rows = ["# PQC Discovery Domains — software recognition reference", "",
        f"{count} examples across 10 discovery domains and 27 software classes. Reference version: pqc.software-recognition.v1. Reviewed: September 10, 2026.", "",
        "Use these names to recognize a software class and identify the right products or teams. They are not a complete market inventory, a confirmed enterprise stack, purchasing recommendations, PQC-readiness claims or qualified connectors. An unlisted product or a referral is equally useful. Several products and deployments may serve the same function.", "",
        "COTS means commercial off-the-shelf; OTS means off-the-shelf; SaaS means software as a service. Open-source and relevant hardware/platform examples are included. Offering labels are broad recognition categories, not exact licensing or deployment profiles. Follow the official product references; installed versions and permitted interfaces still require confirmation.", ""]
    for index, domain in enumerate(domains, 1):
        rows.extend([f"## {index}. {domain['name']}", ""])
        for family in domain["families"]:
            rows.extend([f"### {family['name']}", ""])
            for example in family["examples"]:
                note = (" — " + example["note"]) if example.get("note") else ""
                rows.append(f"- [{example['name']}]({example['url']}) ({example['kind']}){note}")
            rows.append("")
    source = APP / "SOFTWARE_RECOGNITION_REFERENCE.md"
    source.write_text("\n".join(rows), encoding="utf-8")
    return subprocess.call([sys.executable, str(ROOT / "scripts/render_readable_document.py"), str(source)])


if __name__ == "__main__":
    raise SystemExit(main())
