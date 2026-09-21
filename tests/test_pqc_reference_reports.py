"""Source-derived report projections; all files/databases are disposable fixtures."""

from __future__ import annotations

import copy
import json

import pytest

from tools.pqc_reference.assessment_store import SyntheticAssessmentStore, digest
from tools.pqc_reference.report_pack import (
    METHOD,
    ReportProjectionError,
    build_report_pack,
    render_report_markdown,
)
from tools.pqc_reference.synthetic_estate import estate_digest, generate_estate
from workers.pqc.assessment_sources import qualified_ref


def snapshots(tmp_path, estate=None, *, included_kinds=None, as_of=None):
    estate = estate or generate_estate(application_count=12)
    store = SyntheticAssessmentStore(tmp_path / "reference", create=True)
    try:
        for page in estate["pages"]:
            if included_kinds is None or page["kind"] in included_kinds:
                store.ingest_page(tenant=estate["tenant_id"], **page)
        baseline = store.freeze_baseline(
            estate["tenant_id"], as_of=as_of or estate["as_of"]
        )
        phase1 = store.report(estate["tenant_id"], baseline["baseline_id"], 1)
        phase2 = store.report(estate["tenant_id"], baseline["baseline_id"], 2)
    finally:
        store.close()
    return baseline, phase1, phase2, estate


def rehash(value, key):
    value[key] = digest({name: item for name, item in value.items() if name != key})


def uses_for(pack, native_id):
    subject = qualified_ref(pack["tenant_id"], "synthetic-tls", native_id)
    return [
        row for row in pack["risk_review_register"] if row["subject_ref"] == subject
    ]


def test_default_estate_generates_full_reproducible_report_pair(tmp_path):
    inputs = snapshots(tmp_path, generate_estate())
    pack = build_report_pack(*inputs)
    assert pack == build_report_pack(*inputs)
    assert pack["content_sha256"] == digest(
        {key: value for key, value in pack.items() if key != "content_sha256"}
    )
    assert pack["metrics"]["unique_subjects"] == 180
    assert pack["metrics"]["source_observations"] == 181
    assert pack["metrics"]["subjects_by_type"] == {
        "application": 36,
        "certificate": 72,
        "tls_endpoint": 72,
    }
    assert pack["metrics"]["cryptographic_uses"] == 288
    assert len(pack["estate_areas"]) == 10
    assert len(pack["source_profiles"]) == 27
    assert pack["metrics"]["profiles_with_imported_pages"] == 3
    assert pack["metrics"]["enterprise_coverage_percent"] is None
    for phase in (1, 2):
        rendered = render_report_markdown(pack, phase)
        assert rendered == render_report_markdown(pack, phase)
        assert rendered.splitlines()[2] == "## Executive Summary"
        assert "No human acceptance" in rendered
        assert "## Decisions and open questions" in rendered
        assert "## Caveats and authority" in rendered
        assert "Phase 3" in rendered and "Phase 4" in rendered
        assert pack["source_binding"]["baseline_id"] in rendered
        assert "| ---" not in rendered
        assert len(rendered) > 12000


def test_duplicates_and_conflicts_never_inflate_unique_subjects_or_uses(tmp_path):
    inputs = snapshots(tmp_path)
    pack = build_report_pack(*inputs)
    baseline = inputs[0]
    assert pack["metrics"]["unique_subjects"] == len(
        {row["subject_ref"] for row in baseline["observations"]}
    )
    assert pack["metrics"]["source_observations"] > pack["metrics"]["unique_subjects"]
    assert (
        pack["metrics"]["unique_dependency_edges"]
        < pack["metrics"]["dependency_observation_links"]
    )
    conflicted = uses_for(pack, "endpoint-009")
    assert len(conflicted) == 2
    exchange = next(row for row in conflicted if row["role"] == "tls_key_exchange")
    assert exchange["algorithm_variants"] == ["X25519", "X25519MLKEM768"]
    assert exchange["algorithm_posture"] == "conflicted"
    assert exchange["triage_lane"] == "resolve_evidence_conflict_or_gap"
    assert exchange["negotiated_behavior_observed"] is False
    signature = next(
        row for row in conflicted if row["role"] == "tls_certificate_signature"
    )
    assert "conflicting_observations" not in signature["limitation_codes"]
    assert "other_fact_conflict_on_subject" in signature["limitation_codes"]


def test_configured_vendor_and_observed_hybrid_are_distinct_from_authentication(
    tmp_path,
):
    pack = build_report_pack(*snapshots(tmp_path))
    for native_id, basis in [
        ("endpoint-010", "configured"),
        ("endpoint-011", "observed"),
        ("endpoint-012", "vendor_reported"),
    ]:
        rows = uses_for(pack, native_id)
        exchange = next(row for row in rows if row["role"] == "tls_key_exchange")
        signature = next(
            row for row in rows if row["role"] == "tls_certificate_signature"
        )
        assert exchange["algorithm_posture"] == "hybrid_key_exchange_recorded"
        assert exchange["evidence_bases"] == [basis]
        assert exchange["negotiated_behavior_observed"] is (basis == "observed")
        assert signature["algorithm_posture"] == "classical_method_review_candidate"
        assert signature["negotiated_behavior_observed"] is False
        assert exchange["risk_rating"] is None
        assert "pqc_ready" not in exchange
    assert (
        "does not establish post-quantum certificate authentication"
        in render_report_markdown(pack, 2)
    )


def test_all_ten_areas_are_present_but_only_three_families_have_source_evidence(
    tmp_path,
):
    pack = build_report_pack(*snapshots(tmp_path))
    covered = {
        row["family_id"]
        for row in pack["source_profiles"]
        if row["imported_page_count"]
    }
    assert covered == {"cmdb", "certificate-lifecycle", "traffic-termination"}
    pending = [
        row for row in pack["source_profiles"] if row["family_id"] not in covered
    ]
    assert len(pending) == 24
    assert all(
        row["collection_status"] == "no_collected_evidence"
        and row["unique_subject_count"] == 0
        for row in pending
    )
    assert all(
        row["product_binding_status"] == "unconfirmed"
        for row in pack["source_profiles"]
    )
    rendered = render_report_markdown(pack, 1)
    assert all(area["name"] in rendered for area in pack["estate_areas"])
    assert "Recognition examples only" in rendered
    assert "Reported application ref" in rendered
    assert all(
        area["name"] in render_report_markdown(pack, 2) for area in pack["estate_areas"]
    )


def test_missing_imports_do_not_get_replaced_by_generator_expectations(tmp_path):
    inputs = snapshots(tmp_path, included_kinds={"cmdb"})
    estate = inputs[3]
    estate["expectations"]["unique_subjects"] = 999999
    estate["content_sha256"] = estate_digest(estate)
    pack = build_report_pack(*inputs)
    assert pack["metrics"]["unique_subjects"] == 12
    assert pack["metrics"]["source_instances"] == 1
    assert pack["metrics"]["profiles_with_imported_pages"] == 1
    assert pack["risk_review_register"] == []
    assert pack["migration_candidates"] == []
    assert "No cryptographic observations" in render_report_markdown(pack, 2)


def test_empty_baseline_stays_empty_and_requires_evidence(tmp_path):
    pack = build_report_pack(*snapshots(tmp_path, included_kinds=set()))
    assert pack["metrics"]["unique_subjects"] == 0
    assert pack["metrics"]["source_observations"] == 0
    assert pack["risk_review_register"] == []
    assert all(
        row["collection_status"] == "no_collected_evidence"
        for row in pack["source_profiles"]
    )
    assert "No source observations" in render_report_markdown(pack, 1)
    assert "no_observations" in pack["limitation_counts"]


def test_business_context_is_joined_by_application_reference_not_assumed(tmp_path):
    inputs = snapshots(tmp_path)
    pack = build_report_pack(*inputs)
    applications = {
        row["subject_ref"]: row
        for row in inputs[0]["observations"]
        if row["fact_type"] == "application"
    }
    for use in pack["risk_review_register"]:
        context = use["business_context"]
        if (
            len(context["application_refs"]) == 1
            and context["application_refs"][0] in applications
        ):
            application = applications[context["application_refs"][0]]
            expected = application["facts"]["criticality"]
            assert context["criticality"] == (
                None if expected == "unknown" else expected
            )
            assert (
                context["confidentiality_until"]
                == application["facts"]["confidentiality_until"]
            )
            assert application["observation_id"] in context["observation_refs"]
        else:
            assert context["criticality"] is None
            assert context["status"] == "unresolved"


def test_changed_business_facts_change_review_focus_without_becoming_risk_scores(
    tmp_path,
):
    estate = generate_estate(application_count=12)
    for page in estate["pages"]:
        if page["kind"] == "cmdb":
            for row in page["payload"]["records"]:
                row["criticality"] = "critical"
                row["confidentiality_until"] = "2046-09-05"
    estate["content_sha256"] = estate_digest(estate)
    pack = build_report_pack(*snapshots(tmp_path, estate))
    contextual = [
        use
        for use in pack["risk_review_register"]
        if use["business_context"]["observation_refs"]
    ]
    assert contextual
    assert all(
        "source_reports_high_business_criticality" in use["business_review_focus"]
        for use in contextual
    )
    assert all(
        "source_reports_long_lived_information" in use["business_review_focus"]
        for use in contextual
        if use["role"] == "tls_key_exchange"
    )
    authentication_uses = [
        use for use in contextual if use["role"] != "tls_key_exchange"
    ]
    assert authentication_uses
    assert all(
        "source_reports_long_lived_information" not in use["business_review_focus"]
        for use in authentication_uses
    )
    assert all(
        use["confidentiality_days_remaining"] is None
        and use["signature_trust_until"] is None
        for use in authentication_uses
    )
    assert all(
        "signature_trust_lifetime_unknown" in use["limitation_codes"]
        for use in authentication_uses
    )
    assert all(
        use["triage_lane"] != "review_migration_pattern" for use in authentication_uses
    )
    assert all(
        use["risk_rating"] is None and use["execution_authorized"] is False
        for use in contextual
    )


def test_stale_evidence_and_unresolved_dependencies_prevent_design_lane(tmp_path):
    pack = build_report_pack(*snapshots(tmp_path, as_of="2027-09-05T12:00:00Z"))
    assert pack["metrics"]["stale_subjects"] == pack["metrics"]["unique_subjects"]
    assert all(
        use["triage_lane"] != "review_migration_pattern"
        for use in pack["risk_review_register"]
    )
    assert pack["metrics"]["unresolved_dependency_edges"] > 0
    assert all(
        item["candidate_state"] == "evidence_work_required"
        for item in pack["migration_candidates"]
    )


def test_every_register_entry_and_candidate_has_drillthrough_provenance(tmp_path):
    inputs = snapshots(tmp_path)
    pack = build_report_pack(*inputs)
    observations = {row["observation_id"]: row for row in inputs[0]["observations"]}
    uses = {row["use_id"]: row for row in pack["risk_review_register"]}
    for use in uses.values():
        assert use["observation_refs"]
        for evidence in use["evidence"]:
            original = observations[evidence["observation_ref"]]
            assert evidence["custody_ref"] == original["evidence_ref"]
            assert evidence["custody_sha256"] == original["evidence_sha256"]
            assert original["subject_ref"] == use["subject_ref"]
    for candidate in pack["migration_candidates"]:
        assert candidate["use_ref"] in uses
        assert (
            candidate["observation_refs"]
            == uses[candidate["use_ref"]]["observation_refs"]
        )
        assert candidate["vendor_support_status"] == "unknown"
        assert candidate["recovery_requirements"]
        assert candidate["live_execution_authorized"] is False


@pytest.mark.parametrize("which", ["baseline", "phase1", "phase2", "estate"])
def test_input_hash_tampering_is_rejected(tmp_path, which):
    inputs = list(snapshots(tmp_path))
    position = {"baseline": 0, "phase1": 1, "phase2": 2, "estate": 3}[which]
    inputs[position]["unreviewed_extension"] = "synthetic-test"
    with pytest.raises(ReportProjectionError):
        build_report_pack(*inputs)


def test_rehashed_fabricated_normalized_record_fails_raw_source_binding(tmp_path):
    baseline, phase1, phase2, estate = snapshots(tmp_path)
    baseline["observations"][0]["facts"]["native_id"] = "fabricated-id"
    rehash(baseline, "baseline_id")
    for report in (phase1, phase2):
        report["baseline_id"] = baseline["baseline_id"]
    phase1["inventory"] = copy.deepcopy(baseline["observations"])
    rehash(phase1, "report_id")
    rehash(phase2, "report_id")
    with pytest.raises(
        ReportProjectionError, match="normalized_observation_provenance_mismatch"
    ):
        build_report_pack(baseline, phase1, phase2, estate)


def test_rehashed_provider_adapter_claim_is_rejected(tmp_path):
    inputs = list(snapshots(tmp_path))
    estate = inputs[3]
    profile = next(
        item for item in estate["source_profiles"] if item["family_id"] == "ssh"
    )
    profile["normalization_support"] = "reference_dialect_only"
    estate["content_sha256"] = estate_digest(estate)
    with pytest.raises(ReportProjectionError, match="unsupported_adapter_claim"):
        build_report_pack(*inputs)


def test_reports_cannot_accept_work_assign_ratings_or_cross_tenants(tmp_path):
    inputs = list(snapshots(tmp_path))
    for mutation in ("acceptance", "rating", "tenant"):
        changed = copy.deepcopy(inputs)
        if mutation == "acceptance":
            changed[1]["human_acceptance"] = "accepted"
            rehash(changed[1], "report_id")
        elif mutation == "rating":
            changed[2]["risk_candidates"][0]["risk_rating"] = "high"
            rehash(changed[2], "report_id")
        else:
            changed[2]["tenant_id"] = "synthetic-other"
            rehash(changed[2], "report_id")
        with pytest.raises(ReportProjectionError):
            build_report_pack(*changed)


def test_report_pack_method_scenario_and_source_hashes_are_bound(tmp_path):
    inputs = snapshots(tmp_path)
    pack = build_report_pack(*inputs)
    assert pack["source_binding"]["method_sha256"] == digest(METHOD)
    assert pack["source_binding"]["scenario_catalog_sha256"] == digest(
        inputs[3]["scenario_catalog"]
    )
    assert pack["source_binding"]["source_profiles_sha256"] == digest(
        inputs[3]["source_profiles"]
    )
    modified = copy.deepcopy(pack)
    modified["method"]["status"] = "accepted"
    with pytest.raises(ReportProjectionError):
        render_report_markdown(modified, 2)
    assert METHOD["risk_rating_assigned"] is False
    assert METHOD["numerical_scoring"] is False


def test_report_inputs_are_not_mutated(tmp_path):
    inputs = snapshots(tmp_path)
    before = json.dumps(inputs, sort_keys=True)
    pack = build_report_pack(*inputs)
    render_report_markdown(pack, 1)
    render_report_markdown(pack, 2)
    assert json.dumps(inputs, sort_keys=True) == before
