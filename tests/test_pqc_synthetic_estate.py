"""Synthetic estate/report scenarios; no listeners, providers or real inputs."""

from __future__ import annotations

import copy
import json
from collections import Counter, defaultdict

import pytest

from tools.pqc_reference.assessment_store import SyntheticAssessmentStore
from tools.pqc_reference.synthetic_estate import AS_OF, estate_digest, generate_estate
from workers.pqc.assessment_sources import normalize_page


def test_default_estate_is_complete_deterministic_and_explicitly_synthetic():
    estate = generate_estate()
    assert estate == generate_estate()
    assert estate["content_sha256"] == estate_digest(estate)
    assert estate["synthetic"] is True
    assert estate["tenant_id"] == "synthetic-enterprise"
    assert estate["as_of"] == AS_OF
    assert estate["expectations"]["unique_subject_counts"] == {"cmdb": 36, "pki": 72, "tls": 72}
    assert estate["expectations"]["normalized_observations"] == 181
    assert estate["expectations"]["raw_record_counts"] == {"cmdb": 36, "pki": 73, "tls": 73}
    assert estate["expectations"]["page_count"] == 16
    assert estate["expectations"]["duplicate_raw_records"] == 1
    assert estate["expectations"]["enterprise_coverage_percent"] is None
    assert len(estate["scenario_catalog"]) >= 18


def test_different_seed_changes_context_without_removing_scenarios():
    first, second = generate_estate(seed=7), generate_estate(seed=8)
    assert first["content_sha256"] != second["content_sha256"]
    assert first["pages"][0]["payload"] != second["pages"][0]["payload"]
    assert {row["id"] for row in first["scenario_catalog"]} == {row["id"] for row in second["scenario_catalog"]}
    altered = copy.deepcopy(first)
    altered["pages"][0]["payload"]["records"][0]["criticality"] = "unknown"
    assert estate_digest(altered) != first["content_sha256"]


@pytest.mark.parametrize("seed,count", [(0, 12), (7, 36), (2**32 - 1, 60), (9, 13)])
def test_all_raw_pages_are_valid_bounded_and_cursor_ordered(seed, count):
    estate = generate_estate(seed=seed, application_count=count)
    cursors = defaultdict(lambda: None)
    seen = set()
    subjects = defaultdict(set)
    for page in estate["pages"]:
        key = (page["source"], page["page_id"])
        assert key not in seen
        seen.add(key)
        assert page["expected_cursor"] == cursors[page["source"]]
        cursors[page["source"]] = page["page_id"]
        assert len(json.dumps(page["payload"]).encode()) < 256 * 1024
        rows = normalize_page(page["kind"], page["payload"], tenant_id=estate["tenant_id"],
                              source_instance_id=page["source"], observed_at=page["observed_at"])
        subjects[page["kind"]].update(row["subject_ref"] for row in rows)
    assert len(estate["pages"]) <= 26
    assert {kind: len(ids) for kind, ids in subjects.items()} == {"cmdb": count, "pki": count * 2, "tls": count * 2}
    assert any(page["expected_cursor"] is not None for page in estate["pages"])


def test_source_profiles_cover_ten_areas_without_claiming_other_adapters():
    estate = generate_estate()
    profiles = estate["source_profiles"]
    assert len(profiles) == len({item["family_id"] for item in profiles}) == 27
    assert len({item["area_ref"] for item in profiles}) == 10
    active = [item for item in profiles if item["normalization_support"] == "reference_dialect_only"]
    assert {item["family_id"] for item in active} == {"cmdb", "certificate-lifecycle", "traffic-termination"}
    pending = [item for item in profiles if item["normalization_support"] == "not_implemented"]
    assert len(pending) == 24
    assert all(item["synthetic_record_count"] == 0 and not item["source_instance_ids"] for item in pending)
    assert all(item["product_binding_status"] == "unconfirmed" for item in profiles)
    assert all(item["examples_status"] == "recognition_examples_not_installed_or_selected" for item in profiles)


def test_hybrid_basis_classical_authentication_and_unknowns_stay_separate():
    estate = generate_estate()
    records = [row for page in estate["pages"] if page["kind"] == "tls" for row in page["payload"]["records"]]
    lookup = {row["id"]: row for row in records}
    for native_id, basis in (("endpoint-010", "configured"), ("endpoint-011", "observed"), ("endpoint-012", "vendor_reported")):
        row = lookup[native_id]
        assert row["evidence_basis"] == basis
        assert row["key_exchange_group"] == "X25519MLKEM768"
        assert row["certificate_signature_algorithm"] in {"sha256WithRSAEncryption", "sha384WithRSAEncryption", "ecdsa-with-SHA256", "ecdsa-with-SHA384"}
    assert lookup["endpoint-013"]["key_exchange_group"] is None
    variants = [row for row in records if row["id"] == "endpoint-009"]
    assert len(variants) == 2
    assert {(row["evidence_basis"], row["key_exchange_group"]) for row in variants} == {
        ("observed", "X25519"), ("configured", "X25519MLKEM768")}


def test_estate_drives_durable_reports_and_every_declared_limitation(tmp_path):
    estate = generate_estate()
    store = SyntheticAssessmentStore(tmp_path / "estate", create=True)
    try:
        for page in estate["pages"]:
            assert store.ingest_page(tenant=estate["tenant_id"], **page)["result"] == "committed"
        baseline = store.freeze_baseline(estate["tenant_id"], as_of=estate["as_of"])
        assert baseline["counts"]["subjects"] == estate["expectations"]["unique_subjects"]
        assert baseline["counts"]["observations"] == estate["expectations"]["normalized_observations"]
        actual_codes = {item["code"] for item in baseline["limitations"]}
        assert set(estate["expectations"]["minimum_limitation_codes"]) <= actual_codes
        conflicts = [item for item in baseline["limitations"] if item["code"] == "conflicting_observations"]
        assert len(conflicts) == estate["expectations"]["conflicting_subjects"]
        assert Counter(row["assertion_kind"] for row in baseline["observations"]) == estate["expectations"]["assertion_basis_counts"]
        for phase in (1, 2):
            report = store.report(estate["tenant_id"], baseline["baseline_id"], phase)
            assert report["synthetic"] is True
            assert report["human_acceptance"] == "not_requested"
            assert report["source_system_write_authority"] is False
            assert report["counts"]["enterprise_coverage_percent"] is None
            assert report == store.report(estate["tenant_id"], baseline["baseline_id"], phase)
    finally:
        store.close()


@pytest.mark.parametrize("arguments", [
    {"seed": True}, {"seed": -1}, {"seed": 2**32}, {"seed": "7"},
    {"application_count": True}, {"application_count": 11}, {"application_count": 61},
    {"application_count": 12.5},
])
def test_invalid_sizes_and_seeds_are_rejected(arguments):
    with pytest.raises(ValueError):
        generate_estate(**arguments)
