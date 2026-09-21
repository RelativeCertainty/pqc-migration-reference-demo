from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from scripts.schema_registry import build_registry
from workers.pqc.migration_models import (
    AmbiguousWrite,
    JiraSimulator,
    MigrationModelError,
    RevisionConflict,
    ServiceNowSimulator,
    WorkItemCoordinator,
    canonical_digest,
    validate_cryptographic_use,
    validate_migration_case,
    validate_ticket_binding,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-09-05T12:00:00Z"
TENANT = "synthetic-enterprise"
PROVIDERS = (ServiceNowSimulator, JiraSimulator)


def crypto_use(pattern: str = "tls") -> dict:
    signature = pattern == "software"
    return {
        "contract_version": "pba.contract/CryptographicUse.v1",
        "synthetic": True,
        "tenant_id": TENANT,
        "crypto_use_id": f"use-{pattern}-1",
        "asset_ref": f"asset-{pattern}-1",
        "context": {
            "business_service_ref": "service-1",
            "application_ref": "application-1",
            "workload_ref": "workload-1",
            "deployment_ref": "deployment-1",
            "environment": "lab",
            "owner_ref": "owner-1",
            "criticality": "high",
        },
        "purpose": "digital_signature" if signature else "key_establishment",
        "protocol_role": "application_signature"
        if signature
        else f"{pattern}_key_exchange",
        "algorithm": {"name": "ML-DSA-65" if signature else "X25519", "parameters": {}},
        "implementation": {"name": "OpenSSL", "version": "3.5.4"},
        "protected_information": {
            "information_ref": "information-1",
            "confidentiality_until": None,
            "trust_until": None,
        },
        "evidence": [
            {
                "basis": "observed",
                "source_instance_ref": "source-1",
                "observation_ref": "observation-1",
                "custody_ref": "evidence-1",
                "observed_at": NOW,
            }
        ],
        "relying_party_refs": ["client-1"],
        "limitations": [],
    }


def migration_case(pattern: str = "tls", phase: int = 3) -> dict:
    plan = {
        "plan_id": f"plan-{pattern}-1",
        "revision": 1,
        "scope": {"asset_refs": [f"asset-{pattern}-1"], "environment": "lab"},
        "action_refs": [f"action-{pattern}-1"],
        "prerequisite_refs": ["prereq-1"],
        "acceptance_criteria_refs": ["criteria-1"],
        "recovery_strategy": "rollback",
        "recovery_ref": "recovery-1",
    }
    return {
        "contract_version": "pba.contract/PQCMigrationCase.v1",
        "synthetic": True,
        "tenant_id": TENANT,
        "case_id": f"case-{pattern}-1",
        "work_item_id": f"work-{pattern}-1",
        "phase": phase,
        "pattern": pattern,
        "state": "proposed",
        "revision": 1,
        "plan": plan,
        "plan_sha256": canonical_digest(plan),
    }


def approval_fixture(case: dict) -> dict:
    plan = case["plan"]
    return {
        "synthetic": True,
        "assurance_profile": "synthetic_fixture",
        "approval_ref": "approval-1",
        "tenant_id": case["tenant_id"],
        "work_item_id": case["work_item_id"],
        "plan_sha256": case["plan_sha256"],
        "scope_sha256": canonical_digest(plan["scope"]),
        "action_refs": list(plan["action_refs"]),
        "asset_refs": list(plan["scope"]["asset_refs"]),
        "decision": "approved",
        "issued_at": "2026-09-05T11:00:00Z",
        "expires_at": "2026-09-05T13:00:00Z",
        "revoked": False,
        "principal_ref": "synthetic-reviewer-1",
    }


def verification_fixture(case: dict, outcome: str = "passed") -> dict:
    plan = case["plan"]
    return {
        "synthetic": True,
        "assurance_profile": "synthetic_fixture",
        "tenant_id": case["tenant_id"],
        "work_item_id": case["work_item_id"],
        "attempt_ref": "attempt-1",
        "plan_sha256": case["plan_sha256"],
        "scope_sha256": canonical_digest(plan["scope"]),
        "action_refs": list(plan["action_refs"]),
        "asset_refs": list(plan["scope"]["asset_refs"]),
        "criteria_refs": list(plan["acceptance_criteria_refs"]),
        "verifier_ref": "synthetic-verifier-1",
        "evidence_refs": ["evidence-result-1"],
        "verified_at": "2026-09-05T12:01:00Z",
        "outcome": outcome,
    }


def prerequisite_fixture(case: dict) -> dict:
    return {
        "synthetic": True,
        "assurance_profile": "synthetic_fixture",
        "tenant_id": case["tenant_id"],
        "work_item_id": case["work_item_id"],
        "prerequisite_ref": "prereq-1",
        "plan_sha256": case["plan_sha256"],
        "scope_sha256": canonical_digest(case["plan"]["scope"]),
        "evidence_ref": "evidence-prerequisite-1",
        "checker_ref": "synthetic-checker-1",
        "checked_at": "2026-09-05T11:00:00Z",
        "expires_at": "2026-09-05T13:00:00Z",
        "outcome": "passed",
    }


def setup_case(provider_factory=ServiceNowSimulator, *, pattern="tls", phase=3):
    case = migration_case(pattern, phase)
    coordinator = WorkItemCoordinator(TENANT)
    coordinator.create_case(case)
    provider = provider_factory()
    coordinator.project_ticket(
        case["work_item_id"], provider, event_id="event-create-1"
    )
    provider.set_approval_fixture(approval_fixture(case))
    coordinator.record_prerequisite_fixture(
        case["work_item_id"], prerequisite_fixture(case)
    )
    return case, coordinator, provider


def admit(case, coordinator, provider, *, now=NOW, executor_ref="synthetic-executor-1"):
    return coordinator.admit_simulated_attempt(
        case["work_item_id"],
        provider,
        approval_ref="approval-1",
        attempt_ref="attempt-1",
        executor_ref=executor_ref,
        expected_revision=case["revision"],
        now=now,
    )


@pytest.mark.parametrize("pattern", ["tls", "ssh", "software"])
def test_shared_models_cover_all_three_patterns(pattern):
    use = crypto_use(pattern)
    case = migration_case(pattern)
    assert validate_cryptographic_use(use) == use
    assert validate_migration_case(case) == case
    assert "pqc_ready" not in use
    cloned = validate_cryptographic_use(use)
    cloned["context"]["application_ref"] = "changed-application"
    assert use["context"]["application_ref"] == "application-1"


@pytest.mark.parametrize(
    "basis", ["vendor_reported", "configured", "observed", "independently_verified"]
)
def test_evidence_basis_is_explicit_and_never_promoted(basis):
    use = crypto_use()
    use["evidence"][0]["basis"] = basis
    assert validate_cryptographic_use(use)["evidence"][0]["basis"] == basis


def test_schema_and_validation_do_not_allow_undefined_fields_or_private_keys():
    use = crypto_use()
    use["private_key"] = "synthetic-never-secret"
    with pytest.raises(MigrationModelError) as error:
        validate_cryptographic_use(use)
    assert "synthetic-never-secret" not in str(error.value)
    assert "private_key" not in str(error.value)
    del use["private_key"]
    use["evidence"][0]["raw_payload"] = "synthetic-value"
    with pytest.raises(MigrationModelError):
        validate_cryptographic_use(use)


def test_missing_evidence_requires_recorded_limitation():
    use = crypto_use()
    use["evidence"] = []
    with pytest.raises(
        MigrationModelError, match="PQC_MISSING_EVIDENCE_LIMITATION_REQUIRED"
    ):
        validate_cryptographic_use(use)
    use["limitations"] = ["missing_evidence"]
    assert validate_cryptographic_use(use)["evidence"] == []


@pytest.mark.parametrize(
    "bad_time",
    [
        "yesterday",
        "2026-19-05T00:00:00Z",
        "2026-09-05T00:00:00",
        "2026-09-05T00:00:00+03:00",
    ],
)
def test_malformed_or_non_utc_observation_rejected(bad_time):
    use = crypto_use()
    use["evidence"][0]["observed_at"] = bad_time
    with pytest.raises(MigrationModelError):
        validate_cryptographic_use(use)


def test_duplicate_observation_and_wrong_purpose_rejected():
    use = crypto_use()
    use["evidence"].append({**use["evidence"][0], "basis": "independently_verified"})
    with pytest.raises(MigrationModelError, match="PQC_DUPLICATE_OBSERVATION"):
        validate_cryptographic_use(use)
    use = crypto_use()
    use["purpose"] = "digital_signature"
    with pytest.raises(MigrationModelError, match="PQC_PURPOSE_ROLE_MISMATCH"):
        validate_cryptographic_use(use)


def test_plan_digest_bound_to_exact_content():
    case = migration_case()
    case["plan"]["scope"]["asset_refs"].append("unapproved-asset")
    with pytest.raises(MigrationModelError, match="PQC_PLAN_DIGEST_MISMATCH"):
        validate_migration_case(case)
    assert canonical_digest({"b": 2, "a": 1}) == canonical_digest({"a": 1, "b": 2})
    for value in (float("nan"), float("inf"), {"unsupported"}):
        with pytest.raises(MigrationModelError):
            canonical_digest(value)


@pytest.mark.parametrize("phase", [1, 2])
@pytest.mark.parametrize("provider_factory", PROVIDERS)
def test_assessment_phase_can_project_but_cannot_execute(phase, provider_factory):
    case, coordinator, provider = setup_case(provider_factory, phase=phase)
    with pytest.raises(MigrationModelError, match="PQC_ASSESSMENT_PHASE_READ_ONLY"):
        admit(case, coordinator, provider)
    case["state"] = "executing"
    with pytest.raises(MigrationModelError):
        validate_migration_case(case)


@pytest.mark.parametrize("pattern", ["tls", "ssh", "software"])
@pytest.mark.parametrize("provider_factory", PROVIDERS)
def test_same_canonical_journey_for_two_simulated_providers(pattern, provider_factory):
    case, coordinator, provider = setup_case(provider_factory, pattern=pattern)
    admission = admit(case, coordinator, provider)
    assert admission["simulation_only"] is True
    assert admission["live_execution_authorized"] is False
    receipt = verification_fixture(case)
    result = coordinator.record_simulated_verification(
        case["work_item_id"], receipt, expected_revision=2
    )
    assert result["migration_state"] == "resolved"
    assert result["live_execution_authorized"] is False
    assert coordinator.get_case(case["work_item_id"])["revision"] == 3
    binding = coordinator.project_ticket(
        case["work_item_id"], provider, event_id="event-close-1"
    )
    # Updating our projection preserves the provider-owned workflow status;
    # a real native status transition is a separately authorized operation.
    assert binding["provider_status"] == provider.status_mapping["open"]
    assert binding["work_item_id"] == case["work_item_id"]
    assert binding["provider_record_ref"].startswith("synthetic-")


@pytest.mark.parametrize("provider_factory", PROVIDERS)
def test_closed_external_ticket_never_authorizes_or_resolves_migration(
    provider_factory,
):
    case, coordinator, provider = setup_case(provider_factory)
    binding = provider.simulate_status_change(
        TENANT, case["work_item_id"], provider.status_mapping["closed"]
    )
    result = coordinator.receive_ticket_event(
        case["work_item_id"], provider, event_id="event-status-1", binding=binding
    )
    assert result == {
        "simulation_only": True,
        "duplicate": False,
        "migration_state": "proposed",
        "live_execution_authorized": False,
        "cryptographic_closure_inferred": False,
    }
    assert coordinator.get_case(case["work_item_id"])["state"] == "proposed"
    result = coordinator.receive_ticket_event(
        case["work_item_id"], provider, event_id="event-status-1", binding=binding
    )
    assert result["duplicate"] is True
    changed = copy.deepcopy(binding)
    changed["provider_revision_ref"] = "revision:200"
    changed["binding_sha256"] = canonical_digest(
        {k: v for k, v in changed.items() if k != "binding_sha256"}
    )
    with pytest.raises(MigrationModelError, match="PQC_IDEMPOTENCY_CONFLICT"):
        coordinator.receive_ticket_event(
            case["work_item_id"], provider, event_id="event-status-1", binding=changed
        )


@pytest.mark.parametrize("provider_factory", PROVIDERS)
def test_duplicate_projection_and_changed_request_conflict(provider_factory):
    provider = provider_factory()
    case = migration_case()
    first = provider.put_projection(case, event_id="event-1")
    assert provider.put_projection(case, event_id="event-1") == first
    changed = copy.deepcopy(case)
    changed["revision"] = 2
    with pytest.raises(MigrationModelError, match="PQC_IDEMPOTENCY_CONFLICT"):
        provider.put_projection(changed, event_id="event-1")
    assert len(provider._records) == 1


@pytest.mark.parametrize("provider_factory", PROVIDERS)
def test_coordinator_replays_identical_delivery_without_reissuing_a_write(
    provider_factory,
):
    case = migration_case()
    coordinator = WorkItemCoordinator(TENANT)
    coordinator.create_case(case)
    provider = provider_factory()
    first = coordinator.project_ticket(
        case["work_item_id"], provider, event_id="event-create-1"
    )
    assert (
        coordinator.project_ticket(
            case["work_item_id"], provider, event_id="event-create-1"
        )
        == first
    )
    assert len(provider._deliveries) == 1
    changed = copy.deepcopy(case["plan"])
    changed["revision"] += 1
    coordinator.revise_plan(case["work_item_id"], changed, expected_revision=1)
    with pytest.raises(MigrationModelError, match="PQC_IDEMPOTENCY_CONFLICT"):
        coordinator.project_ticket(
            case["work_item_id"], provider, event_id="event-create-1"
        )


@pytest.mark.parametrize("provider_factory", PROVIDERS)
def test_timeout_after_write_requires_readback_not_blind_retry(provider_factory):
    case = migration_case()
    coordinator = WorkItemCoordinator(TENANT)
    coordinator.create_case(case)
    provider = provider_factory()
    result = coordinator.project_ticket(
        case["work_item_id"],
        provider,
        event_id="event-create-1",
        timeout_after_write=True,
    )
    assert result["sync_state"] == "reconciliation_pending"
    with pytest.raises(AmbiguousWrite):
        coordinator.project_ticket(
            case["work_item_id"], provider, event_id="event-retry-2"
        )
    provider.set_approval_fixture(approval_fixture(case))
    with pytest.raises(AmbiguousWrite):
        admit(case, coordinator, provider)
    readback = coordinator.reconcile_ticket(case["work_item_id"], provider)
    assert readback["canonical_revision"] == 1
    assert (
        coordinator.project_ticket(
            case["work_item_id"], provider, event_id="event-create-1"
        )
        == readback
    )
    assert len(provider._records) == 1
    coordinator.record_prerequisite_fixture(
        case["work_item_id"], prerequisite_fixture(case)
    )
    assert admit(case, coordinator, provider)["simulation_only"] is True


@pytest.mark.parametrize("provider_factory", PROVIDERS)
def test_revision_conflicts_do_not_overwrite_provider_record(provider_factory):
    case, coordinator, provider = setup_case(provider_factory)
    changed = provider.simulate_status_change(
        TENANT, case["work_item_id"], provider.status_mapping["in_progress"]
    )
    plan = copy.deepcopy(case["plan"])
    plan["revision"] = 2
    updated = coordinator.revise_plan(case["work_item_id"], plan, expected_revision=1)
    with pytest.raises(RevisionConflict):
        coordinator.project_ticket(
            case["work_item_id"], provider, event_id="event-update-1"
        )
    record = provider.read_projection(TENANT, case["work_item_id"])
    assert record["binding"] == changed
    assert updated["plan_sha256"] != case["plan_sha256"]
    with pytest.raises(RevisionConflict):
        coordinator.reconcile_ticket(case["work_item_id"], provider)
    with pytest.raises(RevisionConflict):
        coordinator.resolve_projection_conflict(
            case["work_item_id"],
            provider,
            expected_revision=2,
            expected_provider_revision="revision:1",
        )
    result = coordinator.resolve_projection_conflict(
        case["work_item_id"],
        provider,
        expected_revision=2,
        expected_provider_revision=changed["provider_revision_ref"],
    )
    assert result["provider_status_preserved"] is True
    with pytest.raises(AmbiguousWrite):
        coordinator.project_ticket(
            case["work_item_id"], provider, event_id="event-update-1"
        )
    binding = coordinator.project_ticket(
        case["work_item_id"], provider, event_id="event-update-2"
    )
    assert binding["provider_status"] == changed["provider_status"]
    assert binding["canonical_revision"] == 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("revoked", True),
        ("decision", "rejected"),
        ("expires_at", "2026-09-05T12:00:00Z"),
        ("issued_at", "2026-09-05T12:01:00Z"),
        ("plan_sha256", "a" * 64),
        ("scope_sha256", "b" * 64),
        ("action_refs", ["wrong-action"]),
        ("asset_refs", ["wrong-asset"]),
        ("work_item_id", "wrong-work"),
    ],
)
def test_approval_binding_drift_revocation_and_expiry_rejected(field, value):
    case = migration_case()
    coordinator = WorkItemCoordinator(TENANT)
    coordinator.create_case(case)
    provider = ServiceNowSimulator()
    coordinator.project_ticket(
        case["work_item_id"], provider, event_id="event-create-1"
    )
    approval = approval_fixture(case)
    approval[field] = value
    provider.set_approval_fixture(approval)
    with pytest.raises(MigrationModelError):
        admit(case, coordinator, provider)
    assert coordinator.get_case(case["work_item_id"])["state"] == "proposed"


def test_latest_readback_revocation_is_not_cached_and_cannot_be_reversed():
    case, coordinator, provider = setup_case()
    approval = provider.read_approval(TENANT, "approval-1")
    approval["revoked"] = True
    provider.set_approval_fixture(approval)
    with pytest.raises(MigrationModelError, match="PQC_APPROVAL_NOT_CURRENT"):
        admit(case, coordinator, provider)
    approval["revoked"] = False
    with pytest.raises(RevisionConflict):
        provider.set_approval_fixture(approval)


def test_changed_plan_invalidates_old_approval_and_plan_is_immutable_during_attempt():
    case, coordinator, provider = setup_case()
    plan = copy.deepcopy(case["plan"])
    plan["revision"] += 1
    plan["scope"]["asset_refs"].append("another-asset")
    changed = coordinator.revise_plan(case["work_item_id"], plan, expected_revision=1)
    coordinator.project_ticket(case["work_item_id"], provider, event_id="event-plan-2")
    with pytest.raises(MigrationModelError, match="PQC_APPROVAL_BINDING_MISMATCH"):
        admit(changed, coordinator, provider)
    approval = approval_fixture(changed)
    approval["approval_ref"] = "approval-2"
    provider.set_approval_fixture(approval)
    coordinator.record_prerequisite_fixture(
        changed["work_item_id"], prerequisite_fixture(changed)
    )
    coordinator.admit_simulated_attempt(
        case["work_item_id"],
        provider,
        approval_ref="approval-2",
        attempt_ref="attempt-1",
        executor_ref="synthetic-executor-1",
        expected_revision=2,
        now=NOW,
    )
    with pytest.raises(MigrationModelError, match="PQC_ACTIVE_PLAN_IMMUTABLE"):
        coordinator.revise_plan(case["work_item_id"], plan, expected_revision=3)


@pytest.mark.parametrize(
    "field,value",
    [
        ("plan_sha256", "a" * 64),
        ("scope_sha256", "b" * 64),
        ("action_refs", ["wrong-action"]),
        ("asset_refs", ["wrong-asset"]),
        ("criteria_refs", ["wrong-criteria"]),
        ("work_item_id", "wrong-work"),
        ("attempt_ref", "wrong-attempt"),
        ("tenant_id", "other-tenant"),
        ("evidence_refs", []),
        ("verifier_ref", "synthetic-executor-1"),
        ("verified_at", "2026-09-05T11:59:59Z"),
    ],
)
def test_independent_verification_exact_binding_is_required(field, value):
    case, coordinator, provider = setup_case()
    admit(case, coordinator, provider)
    receipt = verification_fixture(case)
    receipt[field] = value
    with pytest.raises(MigrationModelError):
        coordinator.record_simulated_verification(
            case["work_item_id"], receipt, expected_revision=2
        )
    assert coordinator.get_case(case["work_item_id"])["state"] == "executing"


def test_no_verification_without_attempt_or_double_closure():
    case, coordinator, provider = setup_case()
    with pytest.raises(MigrationModelError, match="PQC_VERIFICATION_STATE_INVALID"):
        coordinator.record_simulated_verification(
            case["work_item_id"], verification_fixture(case), expected_revision=1
        )
    admit(case, coordinator, provider)
    coordinator.record_simulated_verification(
        case["work_item_id"], verification_fixture(case), expected_revision=2
    )
    with pytest.raises(MigrationModelError, match="PQC_VERIFICATION_STATE_INVALID"):
        coordinator.record_simulated_verification(
            case["work_item_id"], verification_fixture(case), expected_revision=3
        )


@pytest.mark.parametrize(
    "strategy,expected_state",
    [("rollback", "rolled_back"), ("forward_remediation", "blocked")],
)
def test_failed_verification_and_recovery_never_claim_migration_success(
    strategy, expected_state
):
    case = migration_case()
    case["plan"]["recovery_strategy"] = strategy
    case["plan_sha256"] = canonical_digest(case["plan"])
    coordinator = WorkItemCoordinator(TENANT)
    coordinator.create_case(case)
    provider = ServiceNowSimulator()
    coordinator.project_ticket(
        case["work_item_id"], provider, event_id="event-create-1"
    )
    provider.set_approval_fixture(approval_fixture(case))
    coordinator.record_prerequisite_fixture(
        case["work_item_id"], prerequisite_fixture(case)
    )
    admit(case, coordinator, provider)
    result = coordinator.record_simulated_verification(
        case["work_item_id"], verification_fixture(case, "failed"), expected_revision=2
    )
    assert result["migration_state"] == "failed"
    result = coordinator.record_simulated_recovery(
        case["work_item_id"],
        recovery_ref="recovery-1",
        recovery_evidence_ref="evidence-recovery-1",
        expected_revision=3,
    )
    assert result["migration_state"] == expected_state
    assert result["migration_success"] is False


def test_outages_and_unbound_approval_route_fail_closed():
    case, coordinator, provider = setup_case()
    provider.available = False
    with pytest.raises(MigrationModelError, match="PQC_PROVIDER_UNAVAILABLE"):
        admit(case, coordinator, provider)
    alternate = ServiceNowSimulator("unbound-profile")
    alternate.set_approval_fixture(approval_fixture(case))
    with pytest.raises(MigrationModelError, match="PQC_APPROVAL_ROUTE_UNBOUND"):
        admit(case, coordinator, alternate)


def test_approval_and_verification_fixtures_cannot_claim_human_owner_authority():
    case, coordinator, provider = setup_case()
    approval = approval_fixture(case)
    approval["assurance_profile"] = "authenticated_owner_session"
    with pytest.raises(MigrationModelError, match="PQC_SYNTHETIC_APPROVAL_ONLY"):
        provider.set_approval_fixture(approval)
    with pytest.raises(MigrationModelError, match="PQC_SEPARATION_OF_DUTIES_REQUIRED"):
        admit(case, coordinator, provider, executor_ref="synthetic-reviewer-1")
    admit(case, coordinator, provider)
    receipt = verification_fixture(case)
    receipt["assurance_profile"] = "authenticated_owner_session"
    with pytest.raises(MigrationModelError, match="PQC_SYNTHETIC_VERIFICATION_ONLY"):
        coordinator.record_simulated_verification(
            case["work_item_id"], receipt, expected_revision=2
        )


def test_simulation_rejects_non_synthetic_and_nonlab_records_and_cross_tenant_access():
    for change in ("non_synthetic", "production", "wrong_tenant", "resolved"):
        case = migration_case()
        if change == "non_synthetic":
            case["synthetic"] = False
        elif change == "production":
            case["plan"]["scope"]["environment"] = "production"
            case["plan_sha256"] = canonical_digest(case["plan"])
        elif change == "wrong_tenant":
            case["tenant_id"] = "other-tenant"
        else:
            case["state"] = "resolved"
        with pytest.raises(MigrationModelError):
            WorkItemCoordinator(TENANT).create_case(case)
    provider = ServiceNowSimulator()
    provider.put_projection(migration_case(), event_id="event-1")
    assert provider.read_projection("other-tenant", "work-tls-1") is None
    provider.set_approval_fixture(approval_fixture(migration_case()))
    assert provider.read_approval("other-tenant", "approval-1") is None


def test_jira_dialects_and_field_ownership_cannot_be_silently_rebound():
    cloud = JiraSimulator()
    datacenter = JiraSimulator(dialect="jira_data_center")
    assert cloud.provider != datacenter.provider
    assert cloud.profile_ref != datacenter.profile_ref
    binding = cloud.put_projection(migration_case(), event_id="event-1")
    binding["field_ownership"]["migration_state"] = "provider"
    binding["binding_sha256"] = canonical_digest(
        {k: v for k, v in binding.items() if k != "binding_sha256"}
    )
    with pytest.raises(MigrationModelError):
        validate_ticket_binding(binding)


def test_bindings_project_into_existing_work_item_v1_contract():
    binding = ServiceNowSimulator().put_projection(migration_case(), event_id="event-1")
    keys = {
        "integration_profile_ref",
        "record_kind",
        "provider_record_ref",
        "provider_revision_ref",
        "binding_sha256",
    }
    projected = {key: binding[key] for key in keys}
    schema_path = ROOT / "schemas" / "WorkItem.v1.schema.json"
    schema = json.loads(schema_path.read_text())
    binding_schema = {**schema, **schema["properties"]["ticket_bindings"]["items"]}
    validator = Draft202012Validator(
        binding_schema,
        registry=build_registry(schema, schema_path),
        format_checker=FormatChecker(),
    )
    assert validator.is_valid(projected)


def test_canonical_digest_rejects_lossy_non_json_keys_and_deep_values():
    for value in ({1: "value"}, ("tuple",), {"tuple": (1, 2)}):
        with pytest.raises(MigrationModelError):
            canonical_digest(value)
    nested = {}
    for _ in range(30):
        nested = {"nested": nested}
    with pytest.raises(MigrationModelError):
        canonical_digest(nested)


def test_simulator_has_no_live_provider_injection_path():
    case = migration_case()
    coordinator = WorkItemCoordinator(TENANT)
    coordinator.create_case(case)

    class ExternalProvider:
        def put_projection(self, *args, **kwargs):
            pytest.fail("Live/provider method must not be dispatched")

    with pytest.raises(MigrationModelError, match="PQC_SIMULATOR_PROVIDER_ONLY"):
        coordinator.project_ticket(
            case["work_item_id"], ExternalProvider(), event_id="event-1"
        )


def test_stale_ticket_projection_prevents_admission_even_with_new_approval():
    case, coordinator, provider = setup_case()
    plan = copy.deepcopy(case["plan"])
    plan["revision"] += 1
    changed = coordinator.revise_plan(case["work_item_id"], plan, expected_revision=1)
    approval = approval_fixture(changed)
    approval["approval_ref"] = "approval-2"
    provider.set_approval_fixture(approval)
    with pytest.raises(RevisionConflict):
        coordinator.admit_simulated_attempt(
            case["work_item_id"],
            provider,
            approval_ref="approval-2",
            attempt_ref="attempt-1",
            executor_ref="synthetic-executor-1",
            expected_revision=2,
            now=NOW,
        )


@pytest.mark.parametrize(
    "change", ["missing", "failed", "expired", "future", "wrong_plan"]
)
def test_approval_does_not_override_missing_or_stale_prerequisites(change):
    case = migration_case()
    coordinator = WorkItemCoordinator(TENANT)
    coordinator.create_case(case)
    provider = ServiceNowSimulator()
    coordinator.project_ticket(case["work_item_id"], provider, event_id="event-1")
    provider.set_approval_fixture(approval_fixture(case))
    receipt = prerequisite_fixture(case)
    if change == "failed":
        receipt["outcome"] = "failed"
    elif change == "expired":
        receipt["expires_at"] = NOW
    elif change == "future":
        receipt["checked_at"] = "2026-09-05T12:00:01Z"
    elif change == "wrong_plan":
        receipt["plan_sha256"] = "a" * 64
        with pytest.raises(
            MigrationModelError, match="PQC_PREREQUISITE_BINDING_MISMATCH"
        ):
            coordinator.record_prerequisite_fixture(case["work_item_id"], receipt)
    if change not in {"missing", "wrong_plan"}:
        coordinator.record_prerequisite_fixture(case["work_item_id"], receipt)
    with pytest.raises(MigrationModelError, match="PQC_PREREQUISITE_NOT_CURRENT"):
        admit(case, coordinator, provider)
