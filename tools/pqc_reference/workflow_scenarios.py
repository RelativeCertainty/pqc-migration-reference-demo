"""Executable design scenarios, NOT records of owner approval or enterprise work."""

from workers.pqc.migration_models import (
    JiraSimulator,
    ServiceNowSimulator,
    WorkItemCoordinator,
    canonical_digest,
    validate_cryptographic_use,
    validate_migration_case,
)

TENANT = "synthetic-enterprise"
NOW = "2026-09-05T12:00:00Z"


def pattern_models(pattern: str) -> tuple[dict, dict]:
    if pattern not in {"tls", "ssh", "software"}:
        raise ValueError("unknown_reference_pattern")
    signature = pattern == "software"
    use = {
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
        "implementation": {
            "name": "OpenSSL" if pattern != "ssh" else "OpenSSH",
            "version": "synthetic-model",
        },
        "protected_information": {
            "information_ref": "information-1",
            "confidentiality_until": None,
            "trust_until": None,
        },
        "evidence": [],
        "relying_party_refs": ["client-1"],
        "limitations": ["missing_evidence"],
    }
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
    case = {
        "contract_version": "pba.contract/PQCMigrationCase.v1",
        "synthetic": True,
        "tenant_id": TENANT,
        "case_id": f"case-{pattern}-1",
        "work_item_id": f"work-{pattern}-1",
        "phase": 3,
        "pattern": pattern,
        "state": "proposed",
        "revision": 1,
        "plan": plan,
        "plan_sha256": canonical_digest(plan),
    }
    return validate_cryptographic_use(use), validate_migration_case(case)


def simulate_pattern(pattern: str, provider_name: str) -> dict:
    if provider_name not in {"servicenow", "jira_cloud"}:
        raise ValueError("unknown_reference_provider")
    use, case = pattern_models(pattern)
    provider = (
        ServiceNowSimulator() if provider_name == "servicenow" else JiraSimulator()
    )
    coordinator = WorkItemCoordinator(TENANT)
    coordinator.create_case(case)
    work = case["work_item_id"]
    coordinator.project_ticket(work, provider, event_id="create-1")
    native_closed = provider.simulate_status_change(
        TENANT, work, provider.status_mapping["closed"]
    )
    coordinator.receive_ticket_event(
        work, provider, event_id="external-close-1", binding=native_closed
    )
    before = coordinator.get_case(work)["state"]
    if before != "proposed":
        raise AssertionError("external_ticket_must_not_advance_case")
    plan = case["plan"]
    common = {
        "synthetic": True,
        "assurance_profile": "synthetic_fixture",
        "tenant_id": TENANT,
        "work_item_id": work,
        "plan_sha256": case["plan_sha256"],
        "scope_sha256": canonical_digest(plan["scope"]),
    }
    provider.set_approval_fixture(
        {
            **common,
            "approval_ref": "approval-1",
            "action_refs": plan["action_refs"],
            "asset_refs": plan["scope"]["asset_refs"],
            "decision": "approved",
            "issued_at": "2026-09-05T11:00:00Z",
            "expires_at": "2026-09-05T13:00:00Z",
            "revoked": False,
            "principal_ref": "synthetic-reviewer-1",
        }
    )
    coordinator.record_prerequisite_fixture(
        work,
        {
            **common,
            "prerequisite_ref": "prereq-1",
            "evidence_ref": "synthetic-prerequisite-fixture-1",
            "checker_ref": "synthetic-checker-1",
            "checked_at": "2026-09-05T11:00:00Z",
            "expires_at": "2026-09-05T13:00:00Z",
            "outcome": "passed",
        },
    )
    admission = coordinator.admit_simulated_attempt(
        work,
        provider,
        approval_ref="approval-1",
        attempt_ref="attempt-1",
        executor_ref="synthetic-executor-1",
        expected_revision=1,
        now=NOW,
    )
    verification = coordinator.record_simulated_verification(
        work,
        {
            **common,
            "attempt_ref": "attempt-1",
            "action_refs": plan["action_refs"],
            "asset_refs": plan["scope"]["asset_refs"],
            "criteria_refs": plan["acceptance_criteria_refs"],
            "verifier_ref": "synthetic-verifier-1",
            "evidence_refs": ["synthetic-verification-fixture-1"],
            "verified_at": "2026-09-05T12:01:00Z",
            "outcome": "passed",
        },
        expected_revision=2,
    )
    if (
        admission["live_execution_authorized"]
        or verification["live_execution_authorized"]
    ):
        raise AssertionError("simulation_must_not_authorize_live_execution")
    return {
        "pattern": pattern,
        "provider": provider_name,
        "result": "pass",
        "simulation_only": True,
        "real_owner_approval": False,
        "live_execution_authorized": False,
        "source_observation": False,
        "crypto_use_design_example": use,
        "case_design_example": case,
        "state_after_external_close": before,
        "state_after_fixture_verification": verification["migration_state"],
        "plan_sha256": case["plan_sha256"],
        "admission": admission,
        "verification": verification,
    }


def run_workflow_scenarios() -> dict:
    return {
        "type": "pqc.reference.workflow-simulation.v1",
        "synthetic": True,
        "scope": "Six in-memory design scenarios, not native-provider API or live execution proof.",
        "scenarios": [
            simulate_pattern(pattern, provider)
            for pattern in ("tls", "ssh", "software")
            for provider in ("servicenow", "jira_cloud")
        ],
    }
