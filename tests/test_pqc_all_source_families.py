"""All-family composition proofs: synthetic files only, no product connections."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.prove_pqc_enterprise_reference import build_reference, source_manifest
from tools.pqc_reference.synthetic_estate import estate_digest, generate_estate
from workers.pqc.assessment_sources import SourceContractError, normalize_page


def test_core_cohort_remains_the_default_and_all_scope_is_explicit():
    core = generate_estate()
    assert core == generate_estate(source_scope="core")
    assert core["expectations"]["unique_subjects"] == 180
    assert core["expectations"]["reference_dialect_families"] == 3
    assert core["expectations"]["unconnected_source_families"] == 24
    assert core["generator"]["source_scope"] == "core"


@pytest.mark.parametrize("seed,applications", [(0, 12), (7, 36), (2**32 - 1, 60)])
def test_every_family_has_bounded_deterministic_raw_model_input(seed, applications):
    estate = generate_estate(seed, applications, source_scope="all")
    assert estate == generate_estate(seed, applications, source_scope="all")
    assert estate["content_sha256"] == estate_digest(estate)
    assert len(estate["source_profiles"]) == 27
    assert len({p["area_ref"] for p in estate["source_profiles"]}) == 10
    assert estate["expectations"]["reference_dialect_families"] == 27
    assert estate["expectations"]["unique_subjects"] == applications * 5 + 72
    assert estate["expectations"]["normalized_observations"] == applications * 5 + 73
    assert estate["expectations"]["unconnected_source_families"] == 0
    assert estate["expectations"]["qualified_product_adapters"] == 0
    assert estate["expectations"]["enterprise_connections"] == 0
    assert estate["expectations"]["enterprise_coverage_percent"] is None
    assert len(estate["pages"]) <= 50
    extra = [p for p in estate["pages"] if p["kind"] not in {"cmdb", "pki", "tls"}]
    assert len(extra) == len({p["kind"] for p in extra}) == 24
    for page in extra:
        assert len(page["payload"]["records"]) == 3
        assert len(json.dumps(page["payload"]).encode()) < 256 * 1024
        result = normalize_page(
            page["kind"], page["payload"], tenant_id=estate["tenant_id"],
            source_instance_id=page["source"], observed_at=page["observed_at"],
        )
        assert len(result) == 3
        assert {row["fact_type"] for row in result} == {page["kind"].replace("-", "_")}
    assert all(p["synthetic_record_count"] > 0 for p in estate["source_profiles"])
    assert all(p["product_binding_status"] == "unconfirmed" for p in estate["source_profiles"])


def test_extended_page_tampering_cannot_enter_through_shared_normalizer():
    estate = generate_estate(source_scope="all")
    page = next(p for p in estate["pages"] if p["kind"] == "ssh")
    altered = copy.deepcopy(page["payload"])
    altered["records"][0]["unexpected_secret"] = "SYNTHETIC-REJECTED"
    with pytest.raises(SourceContractError):
        normalize_page(
            "ssh", altered, tenant_id=estate["tenant_id"],
            source_instance_id=page["source"], observed_at=page["observed_at"],
        )


@pytest.mark.parametrize("scope", ["", "enterprise", "ALL", None, False])
def test_invalid_scope_fails_before_output_creation(tmp_path, scope):
    output = tmp_path / "must-not-exist"
    with pytest.raises(ValueError, match="invalid_synthetic_source_scope"):
        build_reference(output, source_scope=scope)
    assert not output.exists()


def test_all_models_flow_through_durable_reports_without_provider_authority(tmp_path):
    output = tmp_path / "all-families"
    proof = build_reference(output, source_scope="all")
    assert proof["result"] == "pass"
    assert proof["modeled_source_families"] == 27
    assert proof["source_scope"] == "all"
    assert proof["counts"]["subjects"] == 252
    assert proof["counts"]["observations"] == 253
    assert proof["counts"]["source_instances"] == 27
    assert proof["checks"]["durable_restart"]
    assert proof["checks"]["backup_restore"]
    assert proof["crypto_scope"] == "not_requested_not_proven"
    assert proof["authority"] == {
        "source_system_writes": False, "enterprise_deployment": False,
        "owner_verdict": None, "enterprise_risk_method_approved": False,
        "live_provider_qualification": False,
    }
    coverage = json.loads((output / "reports/source-model-coverage.json").read_text())
    assert coverage["populated_model_count"] == 27
    assert len(coverage["populated_family_ids"]) == 27
    assert coverage["qualified_product_adapters"] == coverage["enterprise_connections"] == 0
    assert not coverage["execution_authorized"]
    brief = (output / "operator-brief.md").read_text()
    assert "All 27 source families" in brief
    assert "zero enterprise connections" in brief
    for path, expected in proof["artifact_hashes"].items():
        assert hashlib.sha256((output / path).read_bytes()).hexdigest() == expected
    snapshot = json.loads((output / "reports/baseline.json").read_text())
    assert snapshot["human_acceptance"] == "not_requested"
    assert len(snapshot["sources"]) == 40
    second = tmp_path / "repeat"
    second_proof = build_reference(second, source_scope="all")
    assert second_proof["baseline_id"] == proof["baseline_id"]
    assert second_proof["report_ids"] == proof["report_ids"]
    assert (second / "reports/report-pack.json").read_bytes() == (output / "reports/report-pack.json").read_bytes()


def test_new_source_models_and_tests_are_bound_to_proof():
    manifest = source_manifest()
    for name in (
        "workers/pqc/extended_sources.py",
        "tools/pqc_reference/extended_estate.py",
        "integrations/pqc/reference_assessment/extended-families.v1.json",
        "tests/test_pqc_all_source_families.py",
    ):
        assert name in manifest
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == manifest[name]
