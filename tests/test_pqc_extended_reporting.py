"""All-family synthetic assessment: provenance, purpose and authority boundaries."""

from __future__ import annotations

import copy

import pytest

from tools.pqc_reference.assessment_store import (
    SyntheticAssessmentStore,
    digest,
    record_dependencies,
)
from tools.pqc_reference.report_pack import (
    ReportProjectionError,
    _extended_posture,
    build_report_pack,
    render_report_markdown,
)
from tools.pqc_reference.synthetic_estate import generate_estate


def snapshots(tmp_path, *, exclude=(), as_of=None, applications=12, estate=None):
    estate = estate or generate_estate(
        application_count=applications, source_scope="all"
    )
    store = SyntheticAssessmentStore(tmp_path / "reference", create=True)
    try:
        for page in estate["pages"]:
            if page["kind"] not in exclude:
                store.ingest_page(tenant=estate["tenant_id"], **page)
        baseline = store.freeze_baseline(
            estate["tenant_id"], as_of=as_of or estate["as_of"]
        )
        p1 = store.report(estate["tenant_id"], baseline["baseline_id"], 1)
        p2 = store.report(estate["tenant_id"], baseline["baseline_id"], 2)
    finally:
        store.close()
    return baseline, p1, p2, estate


def rehash(value, key):
    value[key] = digest({name: item for name, item in value.items() if name != key})


def test_all_27_modeled_families_feed_both_reports_without_vendor_qualification(
    tmp_path,
):
    baseline, p1, p2, estate = snapshots(tmp_path, applications=36)
    pack = build_report_pack(baseline, p1, p2, estate)
    assert pack["metrics"]["unique_subjects"] == 252
    assert (
        len(pack["source_profiles"])
        == pack["metrics"]["profiles_with_imported_pages"]
        == 27
    )
    assert len(pack["estate_areas"]) == 10
    assert all(
        profile["unique_subject_count"] > 0 for profile in pack["source_profiles"]
    )
    assert all(
        profile["product_binding_status"] == "unconfirmed"
        for profile in pack["source_profiles"]
    )
    assert pack["method"]["version"] == "1.1.0"
    assert pack["metrics"]["enterprise_coverage_percent"] is None
    extended = [
        row for row in baseline["observations"] if "cryptographic_uses" in row["facts"]
    ]
    covered = {
        ref
        for row in pack["risk_review_register"] + pack["context_review_register"]
        for ref in row["observation_refs"]
    }
    assert all(row["observation_id"] in covered for row in extended)
    for phase in (1, 2):
        rendered = render_report_markdown(pack, phase)
        assert "three implemented dialects" not in rendered
        assert "27 employer-neutral reference dialects" in rendered
        assert "No human acceptance" in rendered or "No human acceptance," in rendered
        assert all(area["name"] in rendered for area in pack["estate_areas"])


def test_normalized_relationships_and_protected_data_links_have_exact_provenance(
    tmp_path,
):
    inputs = snapshots(tmp_path)
    baseline = inputs[0]
    expected = [
        edge for row in baseline["observations"] for edge in record_dependencies(row)
    ]
    assert baseline["dependencies"] == expected
    pack = build_report_pack(*inputs)
    assert pack["metrics"]["dependency_observation_links"] == len(expected)
    assert pack["metrics"]["unique_dependency_edges"] == len(
        {(row["from_ref"], row["relationship"], row["to_ref"]) for row in expected}
    )
    observed = {row["observation_id"]: row for row in baseline["observations"]}
    assert any(
        row["relationship"] not in {"application_ref", "certificate_ref"}
        for row in expected
    )
    for use in pack["risk_review_register"]:
        for evidence in use["evidence"]:
            row = observed[evidence["observation_ref"]]
            assert row["evidence_sha256"] == evidence["custody_sha256"]
            assert row["subject_ref"] == use["subject_ref"]


def test_context_records_do_not_manufacture_uses_from_packages_or_capabilities(
    tmp_path,
):
    inputs = snapshots(tmp_path)
    pack = build_report_pack(*inputs)
    no_uses = {
        row["observation_id"]
        for row in inputs[0]["observations"]
        if row["facts"].get("cryptographic_uses") == []
    }
    assert no_uses
    use_refs = {
        ref for use in pack["risk_review_register"] for ref in use["observation_refs"]
    }
    assert not use_refs & no_uses
    context_refs = {
        ref
        for item in pack["context_review_register"]
        for ref in item["observation_refs"]
    }
    assert no_uses <= context_refs
    families = {item["source_family_id"] for item in pack["context_review_register"]}
    assert {
        "hsm",
        "kms",
        "policy-exceptions",
        "vendor-assurance",
        "data-governance",
    } <= families
    for entry in pack["context_review_register"]:
        assert entry["risk_rating"] is None
        assert entry["source_claim_is_approval"] is False
        assert entry["source_claim_is_verified_migration"] is False
        assert entry["residual_risk_accepted"] is False
        assert entry["execution_authorized"] is False
        if entry["source_family_id"] in {"policy-exceptions", "vendor-assurance"}:
            assert entry["statement_basis"] in {"source_reported", "vendor_reported"}
            assert entry["record_observation_does_not_verify_claim"] is True
    assert "Context and capability review register" in render_report_markdown(pack, 2)


@pytest.mark.parametrize(
    "algorithm,purpose,posture",
    [
        (
            "AES-256-GCM",
            "data_encryption",
            "symmetric_mechanism_separate_parameter_review",
        ),
        ("AES-256", "key_wrapping", "symmetric_mechanism_separate_parameter_review"),
        ("AES-256-KW", "key_wrapping", "symmetric_mechanism_separate_parameter_review"),
        (
            "AES-256-CBC",
            "data_encryption",
            "symmetric_mechanism_separate_parameter_review",
        ),
        (
            "SHA-256",
            "digital_signature",
            "hash_or_mac_mechanism_separate_parameter_review",
        ),
        ("RSA", "key_wrapping", "classical_method_review_candidate"),
        ("mlkem768x25519-sha256", "key_establishment", "hybrid_key_exchange_recorded"),
        ("ML-DSA-65", "digital_signature", "pqc_signature_mechanism_recorded"),
        (None, "key_establishment", "unknown"),
    ],
)
def test_algorithm_review_is_purpose_specific_not_global_pqc_ready(
    algorithm, purpose, posture
):
    assert _extended_posture([algorithm], purpose) == posture


def test_symmetric_uses_are_not_rsa_like_migration_candidates(tmp_path):
    pack = build_report_pack(*snapshots(tmp_path))
    symmetric = [
        row
        for row in pack["risk_review_register"]
        if row["algorithm_posture"] == "symmetric_mechanism_separate_parameter_review"
    ]
    assert symmetric
    candidate_refs = {row["use_ref"] for row in pack["migration_candidates"]}
    assert not {row["use_id"] for row in symmetric} & candidate_refs
    assert all(
        row["risk_rating"] is None and row["execution_authorized"] is False
        for row in symmetric
    )
    assert all("pqc_ready" not in row for row in pack["risk_review_register"])


def test_extended_use_basis_is_its_own_fact_not_the_container_basis(tmp_path):
    pack = build_report_pack(*snapshots(tmp_path))
    extended = [
        row for row in pack["risk_review_register"] if row.get("source_family_id")
    ]
    assert extended
    found_bases = {basis for row in extended for basis in row["evidence_bases"]}
    assert {"configured", "observed", "vendor_reported"} <= found_bases
    for row in extended:
        assert row["evidence_bases"] == sorted(
            {assertion["basis"] for assertion in row["source_use_assertions"]}
        )
        if "observed" not in row["evidence_bases"]:
            assert row["negotiated_behavior_observed"] is False
        if row["purpose"] != "key_establishment":
            assert row["negotiated_behavior_observed"] is False
        assert row["independent_migration_verification"] is False


def test_signature_trust_lifetime_is_not_application_confidentiality(tmp_path):
    pack = build_report_pack(*snapshots(tmp_path))
    signatures = [
        row
        for row in pack["risk_review_register"]
        if row["purpose"] in {"digital_signature", "credential_authentication"}
    ]
    assert signatures
    for row in signatures:
        assert row["confidentiality_days_remaining"] is None
        assert (
            "source_reports_long_lived_information" not in row["business_review_focus"]
        )
        asserted = {item["trust_until"] for item in row["source_use_assertions"]}
        expected = next(iter(asserted)) if len(asserted) == 1 else None
        assert row["signature_trust_until"] == expected
        if not expected:
            assert "signature_trust_lifetime_unknown" in row["limitation_codes"]


def test_uncollected_extended_family_stays_a_gap_not_a_generated_expectation(tmp_path):
    inputs = snapshots(tmp_path, exclude={"ssh", "policy-exceptions"})
    pack = build_report_pack(*inputs)
    assert pack["metrics"]["profiles_with_imported_pages"] == 25
    profiles = {row["family_id"]: row for row in pack["source_profiles"]}
    for family in ("ssh", "policy-exceptions"):
        assert profiles[family]["collection_status"] == "no_collected_evidence"
        assert profiles[family]["unique_subject_count"] == 0
    assert not any(
        row.get("source_family_id") == "ssh" for row in pack["risk_review_register"]
    )


def test_reproducible_reports_and_immutable_prior_baseline(tmp_path):
    inputs = snapshots(tmp_path)
    before = copy.deepcopy(inputs)
    pack = build_report_pack(*inputs)
    assert pack == build_report_pack(*inputs)
    assert render_report_markdown(pack, 1) == render_report_markdown(pack, 1)
    assert render_report_markdown(pack, 2) == render_report_markdown(pack, 2)
    assert inputs == before
    store = SyntheticAssessmentStore(tmp_path / "reference")
    try:
        assert (
            store.get_baseline(inputs[0]["tenant_id"], inputs[0]["baseline_id"])
            == inputs[0]
        )
        store.backup(tmp_path / "backup")
    finally:
        store.close()
    restored = SyntheticAssessmentStore(tmp_path / "backup")
    try:
        assert (
            restored.report(inputs[0]["tenant_id"], inputs[0]["baseline_id"], 2)
            == inputs[2]
        )
    finally:
        restored.close()


def test_rehashed_fabricated_extension_fact_is_not_source_evidence(tmp_path):
    baseline, p1, p2, estate = snapshots(tmp_path)
    record = next(
        row for row in baseline["observations"] if "cryptographic_uses" in row["facts"]
    )
    record["facts"]["name"] = "fabricated-source-fact"
    rehash(baseline, "baseline_id")
    for report in (p1, p2):
        report["baseline_id"] = baseline["baseline_id"]
    p1["inventory"] = copy.deepcopy(baseline["observations"])
    rehash(p1, "report_id")
    rehash(p2, "report_id")
    with pytest.raises(
        ReportProjectionError, match="normalized_observation_provenance_mismatch"
    ):
        build_report_pack(baseline, p1, p2, estate)


@pytest.mark.parametrize("field", ["execution_authorized", "source_claim_is_approval"])
def test_rehashed_phase2_source_claim_cannot_grant_authority(tmp_path, field):
    baseline, p1, p2, estate = snapshots(tmp_path)
    entry = next(
        row for row in p2["risk_candidates"] if "source_claim_is_approval" in row
    )
    entry[field] = True
    rehash(p2, "report_id")
    with pytest.raises(ReportProjectionError, match="unsupported_risk_authority"):
        build_report_pack(baseline, p1, p2, estate)


def test_stale_extended_sources_prevent_migration_design_admission(tmp_path):
    pack = build_report_pack(*snapshots(tmp_path, as_of="2028-09-05T12:00:00Z"))
    assert pack["metrics"]["stale_subjects"] == pack["metrics"]["unique_subjects"]
    assert all(
        row["triage_lane"] != "review_migration_pattern"
        for row in pack["risk_review_register"]
    )
    assert all(
        row["live_execution_authorized"] is False
        for row in pack["migration_candidates"]
    )


def test_extension_profile_contract_tampering_is_rejected(tmp_path):
    inputs = snapshots(tmp_path)
    profile = next(
        row for row in inputs[3]["source_profiles"] if row["family_id"] == "ssh"
    )
    profile["model_contract"]["unsupported_capabilities"] = []
    rehash(inputs[3], "content_sha256")
    with pytest.raises(ReportProjectionError, match="profile_model_contract_mismatch"):
        build_report_pack(*inputs)


def test_different_protected_data_refs_remain_one_conflicted_use(tmp_path):
    from workers.pqc.extended_sources import extended_page_digest

    estate = generate_estate(application_count=12, source_scope="all")
    page = next(row for row in estate["pages"] if row["kind"] == "databases")
    profile = next(
        row for row in estate["source_profiles"] if row["family_id"] == "databases"
    )["model_contract"]
    use_spec = next(row for row in profile["uses"] if row["protected_data_field"])
    duplicate = copy.deepcopy(page["payload"]["records"][0])
    duplicate[use_spec["protected_data_field"]] = "data-governance-002"
    page["payload"]["records"].append(duplicate)
    page["payload"]["content_sha256"] = extended_page_digest(page["payload"])
    rehash(estate, "content_sha256")
    inputs = snapshots(tmp_path, estate=estate)
    pack = build_report_pack(*inputs)
    subject = next(
        row["subject_ref"]
        for row in inputs[0]["observations"]
        if row["fact_type"] == "databases"
        and row["facts"]["native_id"] == duplicate["id"]
    )
    uses = [
        row
        for row in pack["risk_review_register"]
        if row["subject_ref"] == subject and row["role"] == use_spec["role"]
    ]
    assert len(uses) == 1
    use = uses[0]
    assert len(use["protected_data_reference_variants"]) == 2
    assert use["protected_data_ref"] is None
    assert use["confidentiality_days_remaining"] is None
    assert "conflicting_protected_data_reference" in use["limitation_codes"]
    assert use["triage_lane"] == "resolve_evidence_conflict_or_gap"
    assert use["negotiated_behavior_observed"] is False


def test_reported_policy_approval_and_vendor_validation_do_not_grant_authority(
    tmp_path,
):
    from workers.pqc.extended_sources import extended_page_digest

    estate = generate_estate(application_count=12, source_scope="all")
    for page in estate["pages"]:
        if page["kind"] == "policy-exceptions":
            page["payload"]["records"][0]["review_state"] = "approved"
        elif page["kind"] == "vendor-assurance":
            page["payload"]["records"][0]["independent_validation_state"] = "verified"
        else:
            continue
        page["payload"]["content_sha256"] = extended_page_digest(page["payload"])
    rehash(estate, "content_sha256")
    pack = build_report_pack(*snapshots(tmp_path, estate=estate))
    contexts = [
        row
        for row in pack["context_review_register"]
        if row["source_family_id"] in {"policy-exceptions", "vendor-assurance"}
    ]
    assert contexts
    retained = {
        variant.get("review_state")
        for row in contexts
        for variant in row["fact_variants"]
    }
    assert "approved" in retained
    assert any(
        variant.get("independent_validation_state") == "verified"
        for row in contexts
        for variant in row["fact_variants"]
    )
    for row in contexts:
        assert row["statement_basis"] in {"source_reported", "vendor_reported"}
        assert row["record_observation_does_not_verify_claim"] is True
        assert row["source_claim_is_approval"] is False
        assert row["source_claim_is_verified_migration"] is False
        assert row["execution_authorized"] is False
