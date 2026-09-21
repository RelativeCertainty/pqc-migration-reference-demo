from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path

import pytest

from tools.pqc_reference.assessment_store import (
    ReferenceError,
    SyntheticAssessmentStore,
    canonical,
    report_markdown,
)


FIXTURES = Path(__file__).resolve().parents[1] / "integrations/pqc/reference_assessment"
TENANT = "synthetic-enterprise"
WHEN = "2026-09-05T00:00:00Z"


def page(kind):
    return json.loads((FIXTURES / f"{kind}.page.json").read_text())


def ingest(store, kind="cmdb", **overrides):
    arguments = dict(
        tenant=TENANT,
        source=f"synthetic-{kind}",
        page_id="page-1",
        kind=kind,
        payload=page(kind),
        observed_at=WHEN,
    )
    arguments.update(overrides)
    return store.ingest_page(**arguments)


@pytest.fixture
def store(tmp_path):
    result = SyntheticAssessmentStore(tmp_path / "reference", create=True)
    yield result
    result.close()


def test_real_normalization_custody_and_frozen_reports(store):
    for kind in ("cmdb", "pki", "tls"):
        assert ingest(store, kind)["result"] == "committed"
    baseline = store.freeze_baseline(TENANT, as_of=WHEN)
    assert baseline["counts"]["source_instances"] == 3
    assert baseline["counts"]["subjects"] >= 3
    assert baseline["counts"]["dependencies"] >= 2
    assert baseline["counts"]["enterprise_coverage_percent"] is None
    assert baseline["limitations"] == [
        {"code": "enterprise_coverage_denominator_unavailable"}
    ]
    assert baseline["human_acceptance"] == "not_requested"
    for phase in (1, 2):
        report = store.report(TENANT, baseline["baseline_id"], phase)
        assert store.report(TENANT, baseline["baseline_id"], phase) == report
        assert report["source_system_write_authority"] is False
        assert report["human_acceptance"] == "not_requested"
        assert "synthetic reference" in report_markdown(report)
    for encrypted in store.custody.iterdir():
        assert b"schema_version" not in encrypted.read_bytes()
        assert encrypted.stat().st_mode & 0o077 == 0
    for row in store.db.execute("SELECT * FROM pages"):
        assert store.read_artifact(TENANT, row["artifact_ref"], row["payload_digest"])[
            "synthetic"
        ]


@pytest.mark.parametrize("operation", ["freeze", "report", "replay"])
def test_empty_page_custody_is_required(store, operation):
    empty = page("cmdb")
    empty["records"] = []
    ingest(store, payload=empty)
    baseline = store.freeze_baseline(TENANT, as_of=WHEN)
    assert baseline["sources"][0]["artifact_ref"]
    artifact = next(store.custody.iterdir())
    artifact.unlink()  # Exact test-owned disposable fixture; no production data.
    with pytest.raises(ReferenceError):
        if operation == "freeze":
            store.freeze_baseline(TENANT, as_of=WHEN)
        elif operation == "report":
            store.report(TENANT, baseline["baseline_id"], 1)
        else:
            ingest(store, payload=empty)


@pytest.mark.parametrize(
    "fields",
    [
        {"protocol": "unknown"},
        {"key_exchange_group": None},
        {"key_exchange_group": "unknown"},
    ],
)
def test_unknown_protocol_or_group_never_claims_negotiation(store, fields):
    payload = page("tls")
    payload["records"][0].update(fields)
    ingest(store, "tls", payload=payload)
    baseline = store.freeze_baseline(TENANT, as_of=WHEN)
    report = store.report(TENANT, baseline["baseline_id"], 2)
    assert report["risk_candidates"][0]["negotiation_observed"] is False


def test_concurrent_identical_intake_is_one_commit_and_one_replay(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    directory = tmp_path / "concurrent-store"
    initialized = SyntheticAssessmentStore(directory, create=True)
    initialized.close()
    barrier = Barrier(2)

    def submit():
        connection = SyntheticAssessmentStore(directory)
        try:
            barrier.wait(timeout=5)
            return ingest(connection)["result"]
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: submit(), range(2)))
    assert sorted(results) == ["committed", "idempotent_replay"]
    verify = SyntheticAssessmentStore(directory)
    try:
        for table in ("pages", "observations", "events", "outbox", "cursors"):
            assert verify.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 1
        assert len(list(verify.custody.iterdir())) == 1
    finally:
        verify.close()


def test_restart_and_backup_restore_preserve_report(tmp_path):
    original = tmp_path / "original"
    store = SyntheticAssessmentStore(original, create=True)
    for kind in ("cmdb", "pki", "tls"):
        ingest(store, kind)
    baseline = store.freeze_baseline(TENANT, as_of=WHEN)
    report = store.report(TENANT, baseline["baseline_id"], 2)
    store.backup(tmp_path / "backup")
    store.close()
    for root in (original, tmp_path / "backup"):
        reopened = SyntheticAssessmentStore(root)
        try:
            assert reopened.freeze_baseline(TENANT, as_of=WHEN) == baseline
            assert reopened.report(TENANT, baseline["baseline_id"], 2) == report
        finally:
            reopened.close()


def test_no_page_cursor_event_or_projection_survives_rollback(store):
    with pytest.raises(ReferenceError, match="injected_transaction_failure"):
        ingest(store, fail_before_cursor=True)
    for table in ("pages", "observations", "cursors", "events", "outbox"):
        assert store.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    assert ingest(store)["result"] == "committed"


def test_idempotent_page_and_changed_replay_fail(store):
    ingest(store)
    assert ingest(store)["result"] == "idempotent_replay"
    assert store.db.execute("SELECT count(*) FROM events").fetchone()[0] == 1
    with pytest.raises(ReferenceError, match="page_replay_conflict"):
        ingest(store, complete=False)
    with pytest.raises(ReferenceError, match="page_replay_conflict"):
        ingest(store, observed_at="2026-09-06T00:00:00Z")


def test_cursor_compare_and_swap_prevents_stale_collection(store):
    ingest(store)
    with pytest.raises(ReferenceError, match="cursor_revision_conflict"):
        ingest(store, page_id="page-2")
    assert (
        ingest(store, page_id="page-2", expected_cursor="page-1")["result"]
        == "committed"
    )


def test_partial_missing_and_stale_evidence_stays_visible(store):
    ingest(store, kind="tls", complete=False)
    baseline = store.freeze_baseline(TENANT, as_of="2026-11-05T00:00:00Z")
    codes = {item["code"] for item in baseline["limitations"]}
    assert {
        "missing_source",
        "partial_source_collection",
        "stale_evidence",
        "unresolved_dependency",
    } <= codes
    report = store.report(TENANT, baseline["baseline_id"], 2)
    assert report["limitations"] == baseline["limitations"]
    assert all(entry["risk_rating"] is None for entry in report["risk_candidates"])


def test_conflicts_are_not_silently_overwritten(store):
    ingest(store)
    changed = copy.deepcopy(page("cmdb"))
    current = changed["records"][0]["criticality"]
    changed["records"][0]["criticality"] = "low" if current != "low" else "high"
    ingest(store, page_id="page-2", expected_cursor="page-1", payload=changed)
    baseline = store.freeze_baseline(TENANT, as_of=WHEN)
    assert any(
        item["code"] == "conflicting_observations" for item in baseline["limitations"]
    )


def test_tenant_isolation_and_no_inferred_acceptance(store):
    ingest(store)
    baseline = store.freeze_baseline(TENANT, as_of=WHEN)
    with pytest.raises(ReferenceError, match="baseline_not_found"):
        store.report("synthetic-other", baseline["baseline_id"], 2)
    other = store.freeze_baseline("synthetic-other", as_of=WHEN)
    assert other["counts"]["observations"] == 0
    for tenant in ("internal", "production", "synthetic-../escape"):
        with pytest.raises(ReferenceError):
            store.freeze_baseline(tenant, as_of=WHEN)


def test_reference_rejects_real_source_unknown_fields_and_invalid_times(store):
    for value in (False, None):
        invalid = page("cmdb")
        invalid["synthetic"] = value
        with pytest.raises(ValueError):
            ingest(store, payload=invalid)
    invalid = page("cmdb")
    invalid["password"] = "synthetic-forbidden-field"
    with pytest.raises(ValueError):
        ingest(store, payload=invalid)
    with pytest.raises(ReferenceError, match="timezone_required"):
        ingest(store, observed_at="2026-09-05T00:00:00")
    with pytest.raises(ReferenceError, match="assessment_phase_required"):
        store.report(TENANT, "unused", 3)


def test_frozen_baseline_does_not_change_with_new_collection(store):
    ingest(store)
    baseline = store.freeze_baseline(TENANT, as_of=WHEN)
    report = store.report(TENANT, baseline["baseline_id"], 1)
    ingest(store, "pki")
    assert store.get_baseline(TENANT, baseline["baseline_id"]) == baseline
    assert store.report(TENANT, baseline["baseline_id"], 1) == report
    assert (
        store.freeze_baseline(TENANT, as_of=WHEN)["baseline_id"]
        != baseline["baseline_id"]
    )


def test_artifact_tampering_blocks_new_baseline(store):
    ingest(store)
    target = next(store.custody.iterdir())
    target.write_bytes(b"tampered-synthetic-ciphertext")
    with pytest.raises(ReferenceError, match="artifact_verification_failed"):
        store.freeze_baseline(TENANT, as_of=WHEN)


def test_tampering_after_freeze_blocks_report_generation(store):
    ingest(store)
    baseline = store.freeze_baseline(TENANT, as_of=WHEN)
    next(store.custody.iterdir()).write_bytes(b"tampered")
    with pytest.raises(ReferenceError, match="artifact_verification_failed"):
        store.report(TENANT, baseline["baseline_id"], 2)


def test_missing_relations_and_algorithms_are_not_treated_as_complete(store):
    missing = page("tls")
    for field in (
        "application_id",
        "application_source",
        "certificate_id",
        "certificate_source",
        "key_exchange_group",
        "certificate_signature_algorithm",
    ):
        missing["records"][0][field] = None
    ingest(store, kind="tls", payload=missing)
    baseline = store.freeze_baseline(TENANT, as_of=WHEN)
    codes = {item["code"] for item in baseline["limitations"]}
    assert {"missing_relationship", "cryptographic_parameters_unknown"} <= codes


@pytest.mark.parametrize("basis", ["configured", "vendor_reported"])
def test_configured_support_does_not_prove_negotiation(store, basis):
    source = page("tls")
    source["records"][0]["key_exchange_group"] = "X25519MLKEM768"
    source["records"][0]["evidence_basis"] = basis
    ingest(store, kind="tls", payload=source)
    baseline = store.freeze_baseline(TENANT, as_of=WHEN)
    candidate = store.report(TENANT, baseline["baseline_id"], 2)["risk_candidates"][0]
    assert candidate["evidence_basis"] == basis
    assert candidate["negotiation_observed"] is False


def test_algorithm_substrings_do_not_establish_hybrid_capability(store):
    source = page("tls")
    source["records"][0]["key_exchange_group"] = "NotActuallyMLKEM"
    ingest(store, kind="tls", payload=source)
    baseline = store.freeze_baseline(TENANT, as_of=WHEN)
    candidate = store.report(TENANT, baseline["baseline_id"], 2)["risk_candidates"][0]
    assert candidate["rationale_code"] == "key_establishment_requires_method_review"


def test_immutable_ledgers_reject_updates(store):
    ingest(store)
    baseline = store.freeze_baseline(TENANT, as_of=WHEN)
    store.report(TENANT, baseline["baseline_id"], 1)
    for table in ("pages", "observations", "events", "outbox", "baselines", "reports"):
        with pytest.raises(sqlite3.IntegrityError, match="immutable_reference_record"):
            store.db.execute(f"DELETE FROM {table}")
        store.db.rollback()


def test_does_not_adopt_existing_database_or_follow_symlink(tmp_path):
    root = tmp_path / "existing"
    root.mkdir(mode=0o700)
    with pytest.raises(FileExistsError):
        SyntheticAssessmentStore(root, create=True)
    link = tmp_path / "link"
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(ReferenceError, match="invalid_reference_directory"):
        SyntheticAssessmentStore(link)


def test_report_serialization_is_stable(store):
    ingest(store)
    baseline = store.freeze_baseline(TENANT, as_of=WHEN)
    first = store.report(TENANT, baseline["baseline_id"], 2)
    assert canonical(first) == canonical(
        store.report(TENANT, baseline["baseline_id"], 2)
    )
