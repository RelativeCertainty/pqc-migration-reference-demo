#!/usr/bin/env python3
"""Build a new, synthetic-only evidence/report proof directory. Never deploys."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# These repository imports follow the explicit CLI path bootstrap above.
from scripts.render_readable_document import render_document  # noqa: E402
from tools.pqc_reference.assessment_store import (  # noqa: E402
    ReferenceError,
    SyntheticAssessmentStore,
    canonical,
    digest,
    write_new,
)
from tools.pqc_reference.workflow_scenarios import run_workflow_scenarios  # noqa: E402
from workers.pqc.assessment_sources import validate_catalog  # noqa: E402
from workers.pqc.reference_source_probe import project_fixture  # noqa: E402

SOURCE_PATTERNS = (
    "tools/pqc_reference/*.py",
    "workers/pqc/assessment_sources.py",
    "workers/pqc/extended_sources.py",
    "workers/pqc/migration_models.py",
    "workers/pqc/reference_source_probe.py",
    "workers/pqc/servicenow_cmdb_reference.py",
    "integrations/pqc/reference_assessment/*.json",
    "schemas/CryptographicUse.v1.schema.json",
    "schemas/PQCMigrationCase.v1.schema.json",
    "schemas/PQCTicketBinding.v1.schema.json",
    "manifests/workers/pqc_reference_source_probe.worker.yaml",
    "manifests/pipelines/pqc_reference_source_probe.pipeline.yaml",
    "scripts/prove_pqc_enterprise_reference.py",
    "scripts/render_readable_document.py",
    "tests/test_pqc_reference*.py",
    "tests/test_pqc_synthetic_estate.py",
    "tests/test_pqc_migration_models.py",
    "tests/test_pqc_assessment_sources.py",
    "tests/test_pqc_servicenow_cmdb_reference.py",
    "tests/test_pqc_extended*.py",
    "tests/test_pqc_all_source*.py",
)

# Closed declared proof edges. Extra/missing checks require deliberate review.
CRYPTO_CHECKS = {
    "tls": {
        "classical_baseline_trust_hostname_response",
        "hybrid_negotiated_trust_hostname_response",
        "mixed_capability_client_selects_hybrid",
        "wrong_hostname_rejected",
        "untrusted_issuer_rejected",
        "forbidden_classical_fallback_rejected",
        "incompatible_protocol_rejected",
        "hybrid_service_survives_negative_checks",
        "classical_configuration_restored",
    },
    "ssh": {
        "no_system_ssh_startup_script_present",
        "classical_baseline_authenticated_readback",
        "hybrid_kex_authenticated_readback",
        "mixed_client_selects_hybrid",
        "wrong_host_identity_rejected",
        "unauthorized_synthetic_identity_rejected",
        "forbidden_classical_fallback_rejected",
        "access_preserved_after_negative_checks",
        "classical_configuration_restored",
    },
    "software": {
        "legacy_application_build_signs_document",
        "legacy_application_verifies_document",
        "pqc_application_build_signs_document",
        "pqc_application_verifies_document",
        "wrong_algorithm_key_cannot_be_labeled_pqc",
        "tampered_document_rejected",
        "wrong_signing_key_rejected",
        "pqc_policy_rejects_classical_artifact",
        "legacy_readback_requires_explicit_policy",
        "old_verifier_rejects_new_signature",
        "old_verifier_cannot_enable_new_algorithm_by_policy",
        "restored_legacy_build_reads_legacy_artifact",
        "restored_legacy_build_cannot_read_new_artifact",
        "pqc_verifier_restored_after_recovery_exercise",
    },
}


def source_manifest() -> dict:
    paths = sorted(
        {
            path
            for pattern in SOURCE_PATTERNS
            for path in ROOT.glob(pattern)
            if path.is_file()
        }
    )
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
    }


def load_crypto_proofs(
    directory: Path, *, freshly_executed: bool = False
) -> list[dict]:
    expected = {
        name: hashlib.sha256(
            (ROOT / "tools/pqc_reference" / name).read_bytes()
        ).hexdigest()
        for name in ("crypto_labs.py", "lab_guard.py", "signature_app.py")
    }
    proofs = []
    for track in ("tls", "ssh", "software"):
        path = directory / f"{track}.proof.json"
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
            raise ReferenceError("invalid_crypto_proof_file")
        proof = json.loads(path.read_bytes())
        if (
            proof.get("type") != "pqc.reference.crypto-proof.v1"
            or proof.get("track") != track
            or proof.get("synthetic") is not True
            or proof.get("enterprise_migration_authorized") is not False
            or (
                proof.get("source_hashes") != expected
                and not (
                    freshly_executed
                    and proof.get("result") in {"fail", "blocked"}
                    and "source_hashes" not in proof
                )
            )
        ):
            raise ReferenceError("crypto_proof_source_or_scope_mismatch")
        if proof.get("result") not in {"pass", "fail", "blocked"}:
            raise ReferenceError("invalid_crypto_result")
        if proof.get("result") == "pass":
            checks = proof.get("checks", [])
            if (
                len(checks) != len(CRYPTO_CHECKS[track])
                or {check.get("name") for check in checks} != CRYPTO_CHECKS[track]
                or any(check.get("result") != "pass" for check in checks)
            ):
                raise ReferenceError("invalid_crypto_check_result")
            limits = proof.get("resource_limits", {})
            if (
                limits.get("memory_swap_max_bytes") != 0
                or limits.get("cpu_quota") != 100000
                or limits.get("cpu_period") != 100000
                or limits.get("tasks_max") != 64
                or limits.get("runtime_max_seconds") != 300
                or limits.get("memory_max_bytes")
                != (1024 if track == "software" else 512) * 1024**2
            ):
                raise ReferenceError("invalid_crypto_resource_proof")
        proofs.append(proof)
    return proofs


def _json(path: Path, value: dict | list) -> None:
    write_new(path, canonical(value) + b"\n")


def _document(directory: Path, stem: str, content: str) -> None:
    source = directory / f"{stem}.md"
    write_new(source, content.encode("utf-8"))
    write_new(
        directory / f"{stem}.readable.html",
        render_document(source, classification="private").encode("utf-8"),
    )


def build_reference(
    output: Path,
    *,
    seed: int = 7,
    application_count: int = 36,
    source_scope: str = "core",
    crypto: bool = False,
    crypto_proof_dir: Path | None = None,
) -> dict:
    from tools.pqc_reference.synthetic_estate import generate_estate
    from tools.pqc_reference.report_pack import (
        build_report_pack,
        render_report_markdown,
    )
    from workers.pqc.servicenow_cmdb_reference import prove_servicenow_cmdb_reference

    if crypto and crypto_proof_dir is not None:
        raise ReferenceError("choose_one_crypto_mode")
    output = output.absolute()
    if any(path.is_symlink() for path in (output, *output.parents)):
        raise ReferenceError("symlink_output_denied")
    # Validate and generate the bounded fixture before creating any destination.
    estate = generate_estate(
        seed=seed, application_count=application_count, source_scope=source_scope
    )
    source_before = source_manifest()
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    reports_dir = output / "reports"
    reports_dir.mkdir(mode=0o700)
    store = SyntheticAssessmentStore(output / "private-runtime", create=True)
    tenant = estate["tenant_id"]
    try:
        results = [store.ingest_page(tenant=tenant, **page) for page in estate["pages"]]
        if any(result["result"] != "committed" for result in results):
            raise ReferenceError("initial_collection_not_committed")
        replay = store.ingest_page(tenant=tenant, **estate["pages"][0])
        if replay["result"] != "idempotent_replay":
            raise ReferenceError("replay_not_idempotent")
        baseline = store.freeze_baseline(tenant, as_of=estate["as_of"])
        phase1 = store.report(tenant, baseline["baseline_id"], 1)
        phase2 = store.report(tenant, baseline["baseline_id"], 2)
        store.backup(output / "private-backup")
    finally:
        store.close()
    for location in ("private-runtime", "private-backup"):
        restored = SyntheticAssessmentStore(output / location)
        try:
            if (
                restored.get_baseline(tenant, baseline["baseline_id"]) != baseline
                or restored.report(tenant, baseline["baseline_id"], 1) != phase1
                or restored.report(tenant, baseline["baseline_id"], 2) != phase2
            ):
                raise ReferenceError("restart_or_restore_mismatch")
        finally:
            restored.close()
    pack = build_report_pack(baseline, phase1, phase2, estate)
    if (
        baseline["counts"]["subjects"] != estate["expectations"]["unique_subjects"]
        or baseline["counts"]["observations"] != estate["expectations"]["normalized_observations"]
    ):
        raise ReferenceError("generated_estate_readback_mismatch")
    # Explicitly generated source fixtures are safe development input. This is
    # not an export path for arbitrary or enterprise raw custody material.
    _json(reports_dir / "synthetic-estate.json", estate)
    _json(reports_dir / "baseline.json", baseline)
    _json(reports_dir / "phase1.json", phase1)
    _json(reports_dir / "phase2.json", phase2)
    _json(reports_dir / "report-pack.json", pack)
    modeled_families = [
        row["family_id"] for row in estate["source_profiles"]
        if row["synthetic_record_count"] > 0
    ]
    if source_scope == "all" and len(set(modeled_families)) != 27:
        raise ReferenceError("all_family_model_coverage_incomplete")
    model_coverage = {
        "type": "pqc.reference.source-model-coverage.v1",
        "synthetic": True,
        "source_scope": source_scope,
        "source_family_count": len(estate["source_profiles"]),
        "populated_model_count": len(modeled_families),
        "populated_family_ids": sorted(modeled_families),
        "qualified_product_adapters": 0,
        "enterprise_connections": 0,
        "enterprise_coverage_percent": None,
        "source_profiles": estate["source_profiles"],
        "source_record_counts": estate["expectations"]["raw_record_counts"],
        "normalized_observation_counts": estate["expectations"]["normalized_observation_counts"],
        "baseline_id": baseline["baseline_id"],
        "execution_authorized": False,
    }
    _json(reports_dir / "source-model-coverage.json", model_coverage)
    for phase in (1, 2):
        _document(
            reports_dir, f"phase{phase}-report", render_report_markdown(pack, phase)
        )
    workflow = run_workflow_scenarios()
    _json(output / "workflow-simulations.json", workflow)
    probes = [
        project_fixture(kind, tenant, estate["as_of"])
        for kind in ("cmdb", "pki", "tls")
    ]
    _json(output / "fixed-fixture-projections.json", probes)
    native_candidate = prove_servicenow_cmdb_reference()
    if native_candidate["result"] != "pass":
        raise ReferenceError("native_fixture_candidate_failed")
    _json(output / "servicenow-native-fixture-proof.json", native_candidate)
    # Crypto proofs qualify selected local mechanisms, never a generated estate migration.
    crypto_proofs = []
    if crypto:
        from tools.pqc_reference.crypto_labs import run_labs

        run_labs(output / "crypto")
        crypto_proofs = load_crypto_proofs(output / "crypto", freshly_executed=True)
    elif crypto_proof_dir:
        crypto_proofs = load_crypto_proofs(crypto_proof_dir.absolute())
        (output / "crypto").mkdir(mode=0o700)
        for proof in crypto_proofs:
            _json(output / "crypto" / f"{proof['track']}.proof.json", proof)
    if source_manifest() != source_before:
        raise ReferenceError("source_changed_during_proof")
    _json(output / "source-manifest.json", source_before)
    status = (
        "pass"
        if all(proof["result"] == "pass" for proof in crypto_proofs)
        else "incomplete"
    )
    proof = {
        "type": "pqc.reference.milestone-proof.v1",
        "result": status,
        "synthetic": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Development evidence-to-report composition and workflow simulations; no deployed product.",
        "git_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "git_dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)
        ),
        "source_manifest_sha256": digest(source_before),
        "fixture_estate_sha256": digest(estate),
        "seed": seed,
        "application_count": application_count,
        "source_scope": source_scope,
        "modeled_source_families": len(modeled_families),
        "baseline_id": baseline["baseline_id"],
        "report_ids": [phase1["report_id"], phase2["report_id"]],
        "catalog": validate_catalog(),
        "counts": baseline["counts"],
        "checks": {
            "source_records_consumed": True,
            "custody_verified": True,
            "replay_identical": True,
            "durable_restart": True,
            "backup_restore": True,
            "workflow_simulations": len(workflow["scenarios"]),
            "native_servicenow_fixture_contract": True,
        },
        "crypto_scope": "requested local reference proofs"
        if crypto_proofs
        else "not_requested_not_proven",
        "crypto_origin": "fresh_local_run"
        if crypto
        else "reused_source_matched_proofs"
        if crypto_proof_dir
        else "not_requested",
        "crypto_results": [
            {"track": p["track"], "result": p["result"], "checks": len(p["checks"])}
            for p in crypto_proofs
        ],
        "authority": {
            "source_system_writes": False,
            "enterprise_deployment": False,
            "owner_verdict": None,
            "enterprise_risk_method_approved": False,
            "live_provider_qualification": False,
        },
        "risk_boundary": {
            "current_runtime_impact": "R0: isolated development artifacts only; candidate manifests disabled",
            "future_assessment_readiness": "R2: owner-observed review and recovery required",
            "future_execution_activation": "R3: separate authorization and owner observation required",
        },
    }
    _document(output, "operator-brief", operator_brief(proof))
    safe_artifacts = [
        path
        for path in output.rglob("*")
        if path.is_file()
        and path.relative_to(output).parts[0]
        not in {"private-runtime", "private-backup"}
    ]
    proof["artifact_hashes"] = {
        str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(safe_artifacts)
    }
    _json(output / "proof.json", proof)
    return proof


def operator_brief(proof: dict) -> str:
    counts = proof["counts"]
    crypto_detail = (
        "TLS/SSH hybrid key exchange does not establish post-quantum authentication. "
        "The software proof changes application behavior on one installed OpenSSL version; "
        "it does not prove a library upgrade."
        if proof.get("crypto_results")
        else "No protocol or application migration lab was run or incorporated in this reporting proof."
    )
    family_description = (
        "All 27 source families supply synthetic reference-model records. The 24 extended models include context, key custody, SSH, software, protected data, endpoints and assurance."
        if proof.get("source_scope") == "all"
        else "Three reference source dialects are normalized: application context, certificates, and TLS endpoints."
    )
    return f"""# PQC synthetic estate — operator brief

This is a real reporting pipeline operating on generated mock data. It is not a the example enterprise assessment,
an accepted Phase 1 delivery, an approved Phase 2 risk method, or a deployed migration product.

## Start here

1. Open the [Phase 1 Current-State Assessment](reports/phase1-report.readable.html).
2. Open the [Phase 2 Risk and Migration Review](reports/phase2-report.readable.html).
3. Review the coverage limitations and the source-linked detail, not only the executive summary.
4. Compare the model with the actual contractual deliverable template before accepting it for enterprise use.

No demo application, login, installation, or network connection is needed to read these files.
The [generated source dataset](reports/synthetic-estate.json) contains raw synthetic pages,
all source profiles and named test scenarios. It can be regenerated from the recorded seed.

## What generated this run

- Seed: {proof["seed"]}. Synthetic baseline: `{proof["baseline_id"]}`.
- {counts["subjects"]} distinct subjects from {counts["observations"]} observations.
- {counts["dependencies"]} evidence-linked relationship assertions; these are not unique asset counts.
- 10 estate areas and 27 source families in the qualification catalog.
- {family_description}
- See the [source-model coverage record](reports/source-model-coverage.json) for exact family models and counts.
- Populated model coverage is not live integration coverage: zero enterprise connections and zero qualified commercial-product adapters.
- Recognition examples are not enterprise product selections. Missing or unverified facts remain explicit limitations.
- Real enterprise completeness remains unknown. Seeded estate size is not an enterprise denominator.

## How to review the extended source models

In all-family mode, each additional family has three source-shaped records: attributable examples and an intentionally
incomplete case. Records pass through closed normalization rules; they are not pre-written report conclusions.
Inspect the retained source reference, typed metadata, application and technical relationships,
cryptographic purpose and role, assertion basis, and limitations together.
The small fixture cohort exercises model behavior; it is not a scale, performance, or exhaustive product-compatibility test.

Context-only records remain context. Package presence and hardware-supported algorithms do not establish
active cryptographic use. Configured or vendor-reported behavior is not independent verification.
Policy and vendor records do not grant approval. Phase 2 separates exposure review from migration readiness.

## Engineering evidence

Collection, encrypted raw-page custody, immutable baseline, repeatable report JSON, process restart,
backup/restore, and six provider-neutral workflow simulations completed.
Crypto scope: {proof["crypto_scope"]}. See [machine proof](proof.json) for exact requested scopes and results.
Crypto evidence origin: {proof["crypto_origin"]}. Reused proofs are not a new live run.
{crypto_detail}
Simulated ticket approvals and verification fixtures are never real owner records or execution permits.

## Safe handling

The `reports` folder and this brief contain synthetic review material. Nothing was uploaded or emailed.
Do not distribute `private-runtime` or `private-backup`: those contain the local development database,
encrypted source pages, and their synthetic custody key. This is not production key management.
The generated SQLite file contains synthetic normalized metadata in plaintext; only raw pages are encrypted.
Keep this entire run directory owner-only. Runs are create-only and never overwrite a prior report.
There is no automatic retention deletion; remove only an exact disposable run after review and confirmation.

## Regenerate this reporting scenario

From the repository root, choose an unused output-directory name and run:

```sh
.venv/security-ci/bin/python scripts/prove_pqc_enterprise_reference.py \\
  --output-dir artifacts/pqc-enterprise-reference/new-review \\
  --source-scope {proof.get("source_scope", "core")} --seed {proof["seed"]} --applications {proof.get("application_count", 36)}
```

This command uses installed dependencies and synthetic files only. It refuses an existing output directory,
does not start a server, and does not request cryptographic labs. Report contents are reproducible;
fresh custody encryption, timestamps and office/PDF serialization can produce different file hashes.

## What remains before live use

Owner-confirmed product/version profiles, authorized source access, approved evidence handling,
native API qualification, enterprise identity/persistence/custody, an approved assessment method,
real owner review, and contractual acceptance remain separate gates.
No migration actions or production services are enabled by this run.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="New private run directory; must not exist",
    )
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--applications", type=int, default=36)
    parser.add_argument(
        "--source-scope", choices=("core", "all"), default="core",
        help="Core three-family cohort or all 27 synthetic source-family models",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--crypto",
        action="store_true",
        help="Explicitly run the three bounded loopback labs, sequentially",
    )
    mode.add_argument(
        "--crypto-proof-dir",
        type=Path,
        help="Reuse sanitized local proofs only if exact source hashes still match",
    )
    args = parser.parse_args()
    try:
        proof = build_reference(
            args.output_dir,
            seed=args.seed,
            application_count=args.applications,
            source_scope=args.source_scope,
            crypto=args.crypto,
            crypto_proof_dir=args.crypto_proof_dir,
        )
    except Exception:
        print(
            "PQC reference build failed; no enterprise action was attempted. Inspect the local development tests.",
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {
                "result": proof["result"],
                "counts": proof["counts"],
                "crypto": proof["crypto_results"],
            },
            sort_keys=True,
        )
    )
    return 0 if proof["result"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
