#!/usr/bin/env python3
"""Prepare bounded synthetic input for the C# application; never a runtime backend.

The source generator and normalizers are the existing tested reference dialects.
This tool imports no external file or credentials and starts no service. C# owns
the application database, queries, report assembly, snapshots and request ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.pqc_reference.assessment_store import (  # noqa: E402
    SyntheticAssessmentStore, canonical, write_new,
)
from tools.pqc_reference.report_pack import build_report_pack  # noqa: E402
from tools.pqc_reference.synthetic_estate import generate_estate  # noqa: E402


def prepare(output: Path, *, seed: int = 7, applications: int = 36, as_of: str | None = None) -> dict:
    """Create a new directory, preserving previous inputs, custody and proofs."""
    output = output.absolute()
    if any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError("symlink_output_denied")
    estate = generate_estate(seed, applications, source_scope="all")
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    store = SyntheticAssessmentStore(output / "fixture-custody", create=True)
    try:
        for page in estate["pages"]:
            store.ingest_page(tenant=estate["tenant_id"], **page)
        baseline = store.freeze_baseline(estate["tenant_id"], as_of=as_of or estate["as_of"])
        # Reuse the pure normalizer/illustrative assessment implementation as
        # a fixture producer, not as a live API or an application report store.
        pack = build_report_pack(
            baseline, store.report(estate["tenant_id"], baseline["baseline_id"], 1),
            store.report(estate["tenant_id"], baseline["baseline_id"], 2), estate,
        )
    finally:
        store.close()
    fixture = {
        "schemaVersion": "pqc.enterprise.synthetic-input.v1",
        "synthetic": True,
        "tenantId": estate["tenant_id"],
        "asOf": baseline["as_of"],
        "freshnessDays": baseline["freshness_days"],
        "sourceBinding": {
            "normalizer": "workers.pqc.assessment_sources.normalize_page",
            "illustrativeAssessment": "tools.pqc_reference.report_pack",
            "assessmentStatus": "illustrative_not_enterprise_approved",
            "sourceBaselineId": baseline["baseline_id"],
            "sourceEstateSha256": estate["content_sha256"],
            "sourceScope": "all",
            "seed": seed,
        },
        "inventory": pack["inventory"],
        "dependencies": pack["dependencies"],
        "sourceProfiles": pack["source_profiles"],
        "estateAreas": pack["estate_areas"],
        "observations": pack["evidence_appendix"]["observations"],
        "riskReviews": pack["risk_review_register"],
        "contextReviews": pack["context_review_register"],
        "limitations": pack["limitations"],
        "migrationCandidates": pack["migration_candidates"],
        "method": pack["method"],
        "sourcePageReceipts": pack["evidence_appendix"]["source_page_receipts"],
        "custodyReferences": pack["evidence_appendix"]["custody_artifacts"],
    }
    content = canonical(fixture)
    if len(content) > 16 * 1024 * 1024:
        raise ValueError("fixture_limit_exceeded")
    write_new(output / "synthetic-input.json", content)
    evidence = {
        "schemaVersion": "pqc.enterprise.fixture-proof.v1", "synthetic": True,
        "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content),
        "sourceFamilies": len(fixture["sourceProfiles"]),
        "estateAreas": len(fixture["estateAreas"]),
        "subjects": len(fixture["inventory"]),
        "observations": len(fixture["observations"]),
        "cryptographicUses": len(fixture["riskReviews"]),
        "providerConnections": 0, "qualifiedCommercialAdapters": 0,
        "enterpriseCoveragePercent": None,
    }
    write_new(output / "fixture-proof.json", canonical(evidence))
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--applications", type=int, default=36)
    args = parser.parse_args()
    try:
        proof = prepare(args.output_dir, seed=args.seed, applications=args.applications)
    except (ValueError, OSError):
        print("synthetic_fixture_preparation_failed", file=sys.stderr)
        return 1
    print(json.dumps(proof, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
