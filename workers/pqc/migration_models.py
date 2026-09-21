"""Closed PQC model validators and deliberately in-memory ticketing simulations.

This module performs no I/O other than reading fixed repository schemas. It is
not a Worker, credential provider, human-approval authority, or live executor.
Simulator admission always reports ``live_execution_authorized=False``. A real
integration must use the governed Worker/Pipeline and independently authenticated
approval/readback boundaries; these fixture authorities must never be promoted.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from jsonschema import Draft202012Validator, FormatChecker

from .models import Sensitivity
from .safety import detect_sensitivity


_SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,255}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_LIMIT = 1024
_OWNERSHIP = {
    "plan": "pqc",
    "scope": "pqc",
    "acceptance_criteria": "pqc",
    "migration_state": "pqc",
    "provider_status": "provider",
    "approval_record": "provider_readback",
}


class MigrationModelError(ValueError):
    """Stable code only: values and provider payloads are never echoed."""

    def __init__(self, code: str = "PQC_MODEL_INVALID") -> None:
        self.code = code
        super().__init__(code)


class RevisionConflict(MigrationModelError):
    def __init__(self) -> None:
        super().__init__("PQC_REVISION_CONFLICT")


class AmbiguousWrite(MigrationModelError):
    def __init__(self) -> None:
        super().__init__("PQC_RECONCILIATION_REQUIRED")


def canonical_digest(value: object) -> str:
    """SHA-256 of sorted, ASCII-escaped compact JSON; NOT an RFC8785 claim."""
    try:
        pending = [(value, 0)]
        nodes = 0
        while pending:
            item, depth = pending.pop()
            nodes += 1
            if nodes > 100_000 or depth > 24:
                raise MigrationModelError("PQC_CANONICAL_BOUNDS_EXCEEDED")
            if isinstance(item, dict):
                if not all(isinstance(key, str) for key in item):
                    raise MigrationModelError()
                pending.extend((child, depth + 1) for child in item.values())
            elif isinstance(item, list):
                pending.extend((child, depth + 1) for child in item)
            elif type(item) not in (str, int, float, bool, type(None)):
                raise MigrationModelError()
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, RecursionError):
        raise MigrationModelError() from None
    return hashlib.sha256(encoded).hexdigest()


@lru_cache(maxsize=3)
def _validator(name: str) -> Draft202012Validator:
    schema = json.loads((_SCHEMAS / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _validate(name: str, value: object) -> dict[str, Any]:
    try:
        if not isinstance(value, dict) or not _validator(name).is_valid(value):
            raise MigrationModelError()
        sensitivity = detect_sensitivity(value)
        if sensitivity.sensitivity == Sensitivity.AUTH_SECRET:
            raise MigrationModelError("PQC_SECRET_MATERIAL_REJECTED")
        return copy.deepcopy(value)
    except (RecursionError, TypeError):
        raise MigrationModelError() from None


def validate_cryptographic_use(value: dict[str, Any]) -> dict[str, Any]:
    result = _validate("CryptographicUse.v1.schema.json", value)
    for evidence in result["evidence"]:
        _time(evidence["observed_at"])
    for name in ("confidentiality_until", "trust_until"):
        if result["protected_information"][name] is not None:
            _time(result["protected_information"][name])
    role = result["protocol_role"]
    purpose = result["purpose"]
    if (
        role in {"tls_key_exchange", "ssh_key_exchange"}
        and purpose != "key_establishment"
    ):
        raise MigrationModelError("PQC_PURPOSE_ROLE_MISMATCH")
    if role in {
        "tls_certificate_signature",
        "ssh_host_signature",
        "ssh_user_signature",
    }:
        if purpose not in {"authentication", "digital_signature"}:
            raise MigrationModelError("PQC_PURPOSE_ROLE_MISMATCH")
    if (
        role in {"application_signature", "code_signature"}
        and purpose != "digital_signature"
    ):
        raise MigrationModelError("PQC_PURPOSE_ROLE_MISMATCH")
    if role == "data_at_rest" and purpose != "data_encryption":
        raise MigrationModelError("PQC_PURPOSE_ROLE_MISMATCH")
    if role == "key_wrap" and purpose != "key_wrapping":
        raise MigrationModelError("PQC_PURPOSE_ROLE_MISMATCH")
    if not result["evidence"] and "missing_evidence" not in result["limitations"]:
        raise MigrationModelError("PQC_MISSING_EVIDENCE_LIMITATION_REQUIRED")
    observations = [item["observation_ref"] for item in result["evidence"]]
    if len(observations) != len(set(observations)):
        raise MigrationModelError("PQC_DUPLICATE_OBSERVATION")
    return result


def validate_migration_case(value: dict[str, Any]) -> dict[str, Any]:
    result = _validate("PQCMigrationCase.v1.schema.json", value)
    if canonical_digest(result["plan"]) != result["plan_sha256"]:
        raise MigrationModelError("PQC_PLAN_DIGEST_MISMATCH")
    return result


def _binding_hash(value: dict[str, Any]) -> str:
    return canonical_digest(
        {key: item for key, item in value.items() if key != "binding_sha256"}
    )


def validate_ticket_binding(value: dict[str, Any]) -> dict[str, Any]:
    result = _validate("PQCTicketBinding.v1.schema.json", value)
    expected = (
        {"open": "new", "in_progress": "in_progress", "closed": "closed"}
        if result["provider"] == "servicenow"
        else {"open": "todo", "in_progress": "doing", "closed": "done"}
    )
    if (
        result["status_mapping"] != expected
        or result["provider_status"] not in expected.values()
    ):
        raise MigrationModelError("PQC_PROVIDER_DIALECT_MISMATCH")
    if result["binding_sha256"] != _binding_hash(result):
        raise MigrationModelError("PQC_BINDING_DIGEST_MISMATCH")
    return result


def _ref(value: object) -> str:
    if not isinstance(value, str) or not _REF.fullmatch(value):
        raise MigrationModelError()
    return value


def _time(value: object) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", value
    ):
        raise MigrationModelError("PQC_TIME_INVALID")
    try:
        result = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise MigrationModelError("PQC_TIME_INVALID") from None
    if result.tzinfo != timezone.utc:
        raise MigrationModelError("PQC_TIME_INVALID")
    return result


def _closed(value: object, required: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != required:
        raise MigrationModelError()
    return copy.deepcopy(value)


def _bounded_put(store: dict[Any, Any], key: Any, value: Any) -> None:
    if key not in store and len(store) >= _LIMIT:
        raise MigrationModelError("PQC_SIMULATOR_LIMIT")
    store[key] = value


def _require_synthetic(case: dict[str, Any]) -> None:
    if case["synthetic"] is not True or case["plan"]["scope"]["environment"] != "lab":
        raise MigrationModelError("PQC_SYNTHETIC_LAB_ONLY")


def _approval_fixture(value: object) -> dict[str, Any]:
    result = _closed(
        value,
        {
            "synthetic",
            "assurance_profile",
            "approval_ref",
            "tenant_id",
            "work_item_id",
            "plan_sha256",
            "scope_sha256",
            "action_refs",
            "asset_refs",
            "decision",
            "issued_at",
            "expires_at",
            "revoked",
            "principal_ref",
        },
    )
    if (
        result["synthetic"] is not True
        or result["assurance_profile"] != "synthetic_fixture"
    ):
        raise MigrationModelError("PQC_SYNTHETIC_APPROVAL_ONLY")
    if not isinstance(result["revoked"], bool) or result["decision"] not in (
        "approved",
        "rejected",
    ):
        raise MigrationModelError()
    for key in ("approval_ref", "tenant_id", "work_item_id", "principal_ref"):
        _ref(result[key])
    for key in ("plan_sha256", "scope_sha256"):
        if not isinstance(result[key], str) or not _SHA256.fullmatch(result[key]):
            raise MigrationModelError()
    for key in ("action_refs", "asset_refs"):
        items = result[key]
        if not isinstance(items, list) or not 1 <= len(items) <= 4096:
            raise MigrationModelError()
        for item in items:
            _ref(item)
        if len(items) != len(set(items)):
            raise MigrationModelError()
    if _time(result["issued_at"]) >= _time(result["expires_at"]):
        raise MigrationModelError("PQC_APPROVAL_INTERVAL_INVALID")
    return result


class TicketProjectionPort(Protocol):
    """Ticket work surface only. It has no execution or approval-write operation."""

    provider: str
    profile_ref: str

    def put_projection(
        self,
        case: dict[str, Any],
        *,
        event_id: str,
        expected_provider_revision: str | None = None,
        timeout_after_write: bool = False,
    ) -> dict[str, Any]: ...

    def read_projection(
        self, tenant_id: str, work_item_id: str
    ) -> dict[str, Any] | None: ...


class ApprovalReadbackPort(Protocol):
    """Separate read-only approval port; synthetic fixtures are not human decisions."""

    def read_approval(
        self, tenant_id: str, approval_ref: str
    ) -> dict[str, Any] | None: ...


class _TicketSimulator:
    """Bounded synthetic provider double; never accesses provider SDKs or networks."""

    provider = ""
    status_mapping: dict[str, str] = {}

    def __init__(self, profile_ref: str | None = None) -> None:
        self.profile_ref = _ref(profile_ref or f"synthetic-{self.provider}-profile")
        self._records: dict[tuple[str, str], dict[str, Any]] = {}
        self._deliveries: dict[tuple[str, str], tuple[str, dict[str, Any]]] = {}
        self._approvals: dict[tuple[str, str], dict[str, Any]] = {}
        self.available = True

    def _available(self) -> None:
        if not self.available:
            raise MigrationModelError("PQC_PROVIDER_UNAVAILABLE")

    def put_projection(
        self,
        case: dict[str, Any],
        *,
        event_id: str,
        expected_provider_revision: str | None = None,
        timeout_after_write: bool = False,
    ) -> dict[str, Any]:
        self._available()
        case = validate_migration_case(case)
        _require_synthetic(case)
        _ref(event_id)
        identity = (case["tenant_id"], case["work_item_id"])
        delivery_key = (case["tenant_id"], event_id)
        request_digest = canonical_digest(
            {"case": case, "expected_revision": expected_provider_revision}
        )
        previous = self._deliveries.get(delivery_key)
        if previous:
            if previous[0] != request_digest:
                raise MigrationModelError("PQC_IDEMPOTENCY_CONFLICT")
            return copy.deepcopy(previous[1])
        prior = self._records.get(identity)
        if prior:
            if expected_provider_revision != prior["binding"]["provider_revision_ref"]:
                raise RevisionConflict()
            if case["revision"] <= prior["binding"]["canonical_revision"]:
                raise RevisionConflict()
            revision = prior["provider_revision"] + 1
        else:
            if expected_provider_revision is not None:
                raise RevisionConflict()
            revision = 1
        if len(self._deliveries) >= _LIMIT or (
            prior is None and len(self._records) >= _LIMIT
        ):
            raise MigrationModelError("PQC_SIMULATOR_LIMIT")
        # Projection updates do not overwrite provider-owned workflow status.
        # Native transitions are a separate provider operation with their own
        # controls. The canonical migration revision remains PQC-owned.
        native = (
            prior["binding"]["provider_status"]
            if prior
            else self.status_mapping["open"]
        )
        binding = {
            "contract_version": "pba.contract/PQCTicketBinding.v1",
            "synthetic": True,
            "tenant_id": case["tenant_id"],
            "work_item_id": case["work_item_id"],
            "provider": self.provider,
            "integration_profile_ref": self.profile_ref,
            "record_kind": "ticket",
            "provider_record_ref": f"synthetic-{self.provider}-{canonical_digest(list(identity))[:24]}",
            "provider_revision_ref": f"revision:{revision}",
            "canonical_revision": case["revision"],
            "provider_status": native,
            "sync_state": "synchronized",
            "field_ownership": copy.deepcopy(_OWNERSHIP),
            "status_mapping": copy.deepcopy(self.status_mapping),
            "permission_refs": [
                "synthetic-ticket-read",
                "synthetic-ticket-write",
                "synthetic-approval-read",
            ],
        }
        binding["binding_sha256"] = _binding_hash(binding)
        binding = validate_ticket_binding(binding)
        self._records[identity] = {
            "binding": binding,
            "provider_revision": revision,
            "plan_sha256": case["plan_sha256"],
            "scope_sha256": canonical_digest(case["plan"]["scope"]),
        }
        self._deliveries[delivery_key] = (request_digest, copy.deepcopy(binding))
        if timeout_after_write:
            raise AmbiguousWrite()
        return copy.deepcopy(binding)

    def read_projection(
        self, tenant_id: str, work_item_id: str
    ) -> dict[str, Any] | None:
        self._available()
        record = self._records.get((_ref(tenant_id), _ref(work_item_id)))
        return copy.deepcopy(record) if record else None

    def simulate_status_change(
        self, tenant_id: str, work_item_id: str, status: str
    ) -> dict[str, Any]:
        self._available()
        if status not in self.status_mapping.values():
            raise MigrationModelError("PQC_PROVIDER_DIALECT_MISMATCH")
        identity = (_ref(tenant_id), _ref(work_item_id))
        record = self._records.get(identity)
        if record is None:
            raise MigrationModelError("PQC_TICKET_NOT_FOUND")
        record["provider_revision"] += 1
        binding = record["binding"]
        binding["provider_status"] = status
        binding["provider_revision_ref"] = f"revision:{record['provider_revision']}"
        binding["binding_sha256"] = _binding_hash(binding)
        return copy.deepcopy(binding)

    def set_approval_fixture(self, value: dict[str, Any]) -> None:
        """Test-fixture setter only; cannot record a real human owner verdict."""
        approved = _approval_fixture(value)
        key = (approved["tenant_id"], approved["approval_ref"])
        prior = self._approvals.get(key)
        if prior:
            # The only allowed update is monotonic revocation. Reapproval requires
            # a new native approval identity; it cannot resurrect a revoked record.
            expected = copy.deepcopy(prior)
            expected["revoked"] = True
            if approved != expected and approved != prior:
                raise RevisionConflict()
        _bounded_put(self._approvals, key, approved)

    def read_approval(self, tenant_id: str, approval_ref: str) -> dict[str, Any] | None:
        self._available()
        result = self._approvals.get((_ref(tenant_id), _ref(approval_ref)))
        return copy.deepcopy(result) if result else None


class ServiceNowSimulator(_TicketSimulator):
    provider = "servicenow"
    status_mapping = {"open": "new", "in_progress": "in_progress", "closed": "closed"}


class JiraSimulator(_TicketSimulator):
    provider = "jira_cloud"
    status_mapping = {"open": "todo", "in_progress": "doing", "closed": "done"}

    def __init__(
        self, profile_ref: str | None = None, *, dialect: str = "jira_cloud"
    ) -> None:
        if dialect not in {"jira_cloud", "jira_data_center"}:
            raise MigrationModelError("PQC_PROVIDER_DIALECT_MISMATCH")
        self.provider = dialect
        super().__init__(profile_ref)


def _simulator(provider: object) -> None:
    if type(provider) not in (ServiceNowSimulator, JiraSimulator):
        raise MigrationModelError("PQC_SIMULATOR_PROVIDER_ONLY")


class WorkItemCoordinator:
    """Pure synthetic model rehearsal, using WorkItem.v1 state vocabulary.

    Each instance is tenant-bound. There is no live dispatch method and no
    durable store: the enterprise controller owns those concerns separately.
    Caller-supplied case states cannot bootstrap executing/resolved records.
    """

    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = _ref(tenant_id)
        self._cases: dict[str, dict[str, Any]] = {}
        self._bindings: dict[tuple[str, str], dict[str, Any]] = {}
        self._pending: dict[tuple[str, str], bool] = {}
        self._attempts: dict[str, dict[str, Any]] = {}
        self._events: dict[tuple[str, str], str] = {}
        self._projection_requests: dict[tuple[str, str], dict[str, Any]] = {}
        self._prerequisites: dict[tuple[str, str, str], dict[str, Any]] = {}

    def create_case(self, case: dict[str, Any]) -> dict[str, Any]:
        case = validate_migration_case(case)
        _require_synthetic(case)
        if case["tenant_id"] != self.tenant_id:
            raise MigrationModelError("PQC_TENANT_MISMATCH")
        if case["state"] != "proposed" or case["revision"] != 1:
            raise MigrationModelError("PQC_INITIAL_STATE_INVALID")
        key = case["work_item_id"]
        if key in self._cases:
            if self._cases[key] == case:
                return copy.deepcopy(case)
            raise RevisionConflict()
        if any(
            existing["case_id"] == case["case_id"] for existing in self._cases.values()
        ):
            raise RevisionConflict()
        _bounded_put(self._cases, key, case)
        return copy.deepcopy(case)

    def get_case(self, work_item_id: str) -> dict[str, Any]:
        case = self._cases.get(_ref(work_item_id))
        if case is None:
            raise MigrationModelError("PQC_CASE_NOT_FOUND")
        return copy.deepcopy(case)

    def _case(self, work_item_id: str, expected_revision: int) -> dict[str, Any]:
        case = self.get_case(work_item_id)
        if type(expected_revision) is not int or case["revision"] != expected_revision:
            raise RevisionConflict()
        return case

    def revise_plan(
        self, work_item_id: str, plan: dict[str, Any], *, expected_revision: int
    ) -> dict[str, Any]:
        case = self._case(work_item_id, expected_revision)
        if case["state"] in {"executing", "verifying", "resolved"}:
            raise MigrationModelError("PQC_ACTIVE_PLAN_IMMUTABLE")
        if not isinstance(plan, dict) or plan.get("plan_id") != case["plan"]["plan_id"]:
            raise MigrationModelError("PQC_PLAN_ID_MISMATCH")
        if plan.get("revision") != case["plan"]["revision"] + 1:
            raise RevisionConflict()
        case["plan"] = copy.deepcopy(plan)
        case["plan_sha256"] = canonical_digest(plan)
        case["revision"] += 1
        case["state"] = "proposed"
        case = validate_migration_case(case)
        _require_synthetic(case)
        self._cases[work_item_id] = case
        return copy.deepcopy(case)

    def project_ticket(
        self,
        work_item_id: str,
        provider: _TicketSimulator,
        *,
        event_id: str,
        timeout_after_write: bool = False,
    ) -> dict[str, Any]:
        _simulator(provider)
        _ref(event_id)
        key = (work_item_id, provider.profile_ref)
        case = self.get_case(work_item_id)
        delivery_key = (provider.profile_ref, event_id)
        request = self._projection_requests.get(delivery_key)
        case_digest = canonical_digest(case)
        if request and request["case_sha256"] != case_digest:
            raise MigrationModelError("PQC_IDEMPOTENCY_CONFLICT")
        if self._pending.get(key) or (request and request["abandoned"]):
            raise AmbiguousWrite()
        if request and request["result"] is not None:
            return copy.deepcopy(request["result"])
        binding = self._bindings.get(key)
        if binding and binding["provider"] != provider.provider:
            raise MigrationModelError("PQC_PROVIDER_DIALECT_MISMATCH")
        expected = (
            request["expected_revision"]
            if request
            else binding["provider_revision_ref"]
            if binding
            else None
        )
        if request is None:
            request = {
                "case_sha256": case_digest,
                "work_item_id": work_item_id,
                "expected_revision": expected,
                "result": None,
                "abandoned": False,
            }
            _bounded_put(self._projection_requests, delivery_key, request)
        try:
            result = provider.put_projection(
                case,
                event_id=event_id,
                expected_provider_revision=expected,
                timeout_after_write=timeout_after_write,
            )
        except AmbiguousWrite:
            _bounded_put(self._pending, key, True)
            return {
                "simulation_only": True,
                "sync_state": "reconciliation_pending",
                "live_execution_authorized": False,
            }
        except RevisionConflict:
            _bounded_put(self._pending, key, True)
            raise
        _bounded_put(self._bindings, key, result)
        request["result"] = copy.deepcopy(result)
        return copy.deepcopy(result)

    def reconcile_ticket(
        self, work_item_id: str, provider: _TicketSimulator
    ) -> dict[str, Any]:
        _simulator(provider)
        case = self.get_case(work_item_id)
        record = provider.read_projection(self.tenant_id, work_item_id)
        if record is None:
            raise AmbiguousWrite()
        binding = validate_ticket_binding(record["binding"])
        if (
            binding["tenant_id"] != self.tenant_id
            or binding["work_item_id"] != work_item_id
            or binding["integration_profile_ref"] != provider.profile_ref
            or binding["provider"] != provider.provider
            or binding["canonical_revision"] != case["revision"]
            or record["plan_sha256"] != case["plan_sha256"]
            or record["scope_sha256"] != canonical_digest(case["plan"]["scope"])
        ):
            raise RevisionConflict()
        key = (work_item_id, provider.profile_ref)
        _bounded_put(self._bindings, key, binding)
        self._pending.pop(key, None)
        for (profile, _event), request in self._projection_requests.items():
            if (
                profile == provider.profile_ref
                and request["work_item_id"] == work_item_id
                and request["case_sha256"] == canonical_digest(case)
                and request["result"] is None
                and not request["abandoned"]
            ):
                request["result"] = copy.deepcopy(binding)
        return copy.deepcopy(binding)

    def resolve_projection_conflict(
        self,
        work_item_id: str,
        provider: _TicketSimulator,
        *,
        expected_revision: int,
        expected_provider_revision: str,
    ) -> dict[str, Any]:
        """Explicitly reconcile revisions before reapplying only PQC-owned fields.

        It records no approval and performs no provider write. The caller must
        use a new delivery identity to propose the newer canonical projection.
        """
        _simulator(provider)
        self._case(work_item_id, expected_revision)
        key = (work_item_id, provider.profile_ref)
        if not self._pending.get(key):
            raise MigrationModelError("PQC_RECONCILIATION_NOT_PENDING")
        record = provider.read_projection(self.tenant_id, work_item_id)
        if record is None:
            raise AmbiguousWrite()
        binding = validate_ticket_binding(record["binding"])
        if (
            binding["tenant_id"] != self.tenant_id
            or binding["work_item_id"] != work_item_id
            or binding["integration_profile_ref"] != provider.profile_ref
            or binding["provider"] != provider.provider
            or binding["provider_revision_ref"] != expected_provider_revision
            or binding["canonical_revision"] >= expected_revision
        ):
            raise RevisionConflict()
        _bounded_put(self._bindings, key, binding)
        self._pending.pop(key, None)
        for (profile, _event), request in self._projection_requests.items():
            if (
                profile == provider.profile_ref
                and request["work_item_id"] == work_item_id
                and request["result"] is None
            ):
                request["abandoned"] = True
        return {
            "simulation_only": True,
            "live_execution_authorized": False,
            "decision": "reapply_pqc_owned_projection",
            "provider_status_preserved": True,
        }

    def receive_ticket_event(
        self,
        work_item_id: str,
        provider: _TicketSimulator,
        *,
        event_id: str,
        binding: dict[str, Any],
    ) -> dict[str, Any]:
        """Events trigger provider readback. Their status is never workflow authority."""
        _simulator(provider)
        _ref(event_id)
        case = self.get_case(work_item_id)
        candidate = validate_ticket_binding(binding)
        if (
            candidate["tenant_id"] != self.tenant_id
            or candidate["work_item_id"] != work_item_id
        ):
            raise MigrationModelError("PQC_TENANT_OR_WORK_MISMATCH")
        event_key = (provider.profile_ref, event_id)
        digest = canonical_digest(candidate)
        prior = self._events.get(event_key)
        if prior and prior != digest:
            raise MigrationModelError("PQC_IDEMPOTENCY_CONFLICT")
        if not prior:
            readback = self.reconcile_ticket(work_item_id, provider)
            if readback != candidate:
                raise RevisionConflict()
            _bounded_put(self._events, event_key, digest)
        return {
            "simulation_only": True,
            "duplicate": prior is not None,
            "migration_state": case["state"],
            "live_execution_authorized": False,
            "cryptographic_closure_inferred": False,
        }

    def record_prerequisite_fixture(
        self, work_item_id: str, receipt: dict[str, Any]
    ) -> None:
        """Prepare immutable synthetic prerequisite readback, never real evidence."""
        case = self.get_case(work_item_id)
        receipt = _closed(
            receipt,
            {
                "synthetic",
                "assurance_profile",
                "tenant_id",
                "work_item_id",
                "prerequisite_ref",
                "plan_sha256",
                "scope_sha256",
                "evidence_ref",
                "checker_ref",
                "checked_at",
                "expires_at",
                "outcome",
            },
        )
        if (
            receipt["synthetic"] is not True
            or receipt["assurance_profile"] != "synthetic_fixture"
        ):
            raise MigrationModelError("PQC_SYNTHETIC_PREREQUISITE_ONLY")
        if (
            receipt["tenant_id"] != self.tenant_id
            or receipt["work_item_id"] != work_item_id
            or receipt["plan_sha256"] != case["plan_sha256"]
            or receipt["scope_sha256"] != canonical_digest(case["plan"]["scope"])
            or receipt["prerequisite_ref"] not in case["plan"]["prerequisite_refs"]
        ):
            raise MigrationModelError("PQC_PREREQUISITE_BINDING_MISMATCH")
        _ref(receipt["evidence_ref"])
        _ref(receipt["checker_ref"])
        if receipt["outcome"] not in ("passed", "failed") or _time(
            receipt["checked_at"]
        ) >= _time(receipt["expires_at"]):
            raise MigrationModelError("PQC_PREREQUISITE_INVALID")
        key = (work_item_id, case["plan_sha256"], receipt["prerequisite_ref"])
        prior = self._prerequisites.get(key)
        if prior and prior != receipt:
            raise RevisionConflict()
        _bounded_put(self._prerequisites, key, receipt)

    def admit_simulated_attempt(
        self,
        work_item_id: str,
        approval_provider: _TicketSimulator,
        *,
        approval_ref: str,
        attempt_ref: str,
        executor_ref: str,
        expected_revision: int,
        now: str,
    ) -> dict[str, Any]:
        _simulator(approval_provider)
        case = self._case(work_item_id, expected_revision)
        if case["phase"] < 3:
            raise MigrationModelError("PQC_ASSESSMENT_PHASE_READ_ONLY")
        if case["state"] not in {"proposed", "plan_ready", "awaiting_approval"}:
            raise MigrationModelError("PQC_EXECUTION_STATE_INVALID")
        if any(key[0] == work_item_id for key in self._pending):
            raise AmbiguousWrite()
        if (work_item_id, approval_provider.profile_ref) not in self._bindings:
            raise MigrationModelError("PQC_APPROVAL_ROUTE_UNBOUND")
        self.reconcile_ticket(work_item_id, approval_provider)
        approval = approval_provider.read_approval(self.tenant_id, approval_ref)
        if approval is None:
            raise MigrationModelError("PQC_APPROVAL_MISSING")
        approval = _approval_fixture(approval)
        plan = case["plan"]
        if (
            approval["tenant_id"] != self.tenant_id
            or approval["work_item_id"] != work_item_id
            or approval["approval_ref"] != approval_ref
            or approval["plan_sha256"] != case["plan_sha256"]
            or approval["scope_sha256"] != canonical_digest(plan["scope"])
            or set(approval["action_refs"]) != set(plan["action_refs"])
            or set(approval["asset_refs"]) != set(plan["scope"]["asset_refs"])
        ):
            raise MigrationModelError("PQC_APPROVAL_BINDING_MISMATCH")
        if approval["revoked"] or approval["decision"] != "approved":
            raise MigrationModelError("PQC_APPROVAL_NOT_CURRENT")
        if (
            not _time(approval["issued_at"])
            <= _time(now)
            < _time(approval["expires_at"])
        ):
            raise MigrationModelError("PQC_APPROVAL_NOT_CURRENT")
        for prerequisite_ref in plan["prerequisite_refs"]:
            receipt = self._prerequisites.get(
                (work_item_id, case["plan_sha256"], prerequisite_ref)
            )
            if (
                receipt is None
                or receipt["outcome"] != "passed"
                or not _time(receipt["checked_at"])
                <= _time(now)
                < _time(receipt["expires_at"])
            ):
                raise MigrationModelError("PQC_PREREQUISITE_NOT_CURRENT")
        _ref(attempt_ref)
        _ref(executor_ref)
        if approval["principal_ref"] == executor_ref:
            raise MigrationModelError("PQC_SEPARATION_OF_DUTIES_REQUIRED")
        if attempt_ref in self._attempts:
            raise MigrationModelError("PQC_ATTEMPT_ALREADY_EXISTS")
        attempt = {
            "simulation_only": True,
            "live_execution_authorized": False,
            "attempt_ref": attempt_ref,
            "executor_ref": executor_ref,
            "tenant_id": self.tenant_id,
            "work_item_id": work_item_id,
            "plan_sha256": case["plan_sha256"],
            "approval_ref": approval_ref,
            "scope_sha256": canonical_digest(plan["scope"]),
            "started_at": now,
            "state": "executing",
        }
        _bounded_put(self._attempts, attempt_ref, attempt)
        case["state"] = "executing"
        case["revision"] += 1
        self._cases[work_item_id] = case
        return copy.deepcopy(attempt)

    def record_simulated_verification(
        self,
        work_item_id: str,
        receipt: dict[str, Any],
        *,
        expected_revision: int,
    ) -> dict[str, Any]:
        case = self._case(work_item_id, expected_revision)
        if case["phase"] < 3 or case["state"] not in {"executing", "verifying"}:
            raise MigrationModelError("PQC_VERIFICATION_STATE_INVALID")
        receipt = _closed(
            receipt,
            {
                "synthetic",
                "assurance_profile",
                "tenant_id",
                "work_item_id",
                "attempt_ref",
                "plan_sha256",
                "scope_sha256",
                "action_refs",
                "asset_refs",
                "criteria_refs",
                "verifier_ref",
                "evidence_refs",
                "verified_at",
                "outcome",
            },
        )
        if (
            receipt["synthetic"] is not True
            or receipt["assurance_profile"] != "synthetic_fixture"
        ):
            raise MigrationModelError("PQC_SYNTHETIC_VERIFICATION_ONLY")
        attempt = self._attempts.get(_ref(receipt["attempt_ref"]))
        if not attempt or attempt["state"] != "executing":
            raise MigrationModelError("PQC_ATTEMPT_MISMATCH")
        plan = case["plan"]
        for key in ("action_refs", "asset_refs", "criteria_refs", "evidence_refs"):
            values = receipt[key]
            if not isinstance(values, list) or not 1 <= len(values) <= 4096:
                raise MigrationModelError()
            for item in values:
                _ref(item)
            if len(values) != len(set(values)):
                raise MigrationModelError()
        if (
            receipt["tenant_id"] != self.tenant_id
            or receipt["work_item_id"] != work_item_id
            or attempt["work_item_id"] != work_item_id
            or receipt["plan_sha256"] != case["plan_sha256"]
            or receipt["scope_sha256"] != canonical_digest(plan["scope"])
            or set(receipt["action_refs"]) != set(plan["action_refs"])
            or set(receipt["asset_refs"]) != set(plan["scope"]["asset_refs"])
            or set(receipt["criteria_refs"]) != set(plan["acceptance_criteria_refs"])
        ):
            raise MigrationModelError("PQC_VERIFICATION_BINDING_MISMATCH")
        if _ref(receipt["verifier_ref"]) == attempt["executor_ref"]:
            raise MigrationModelError("PQC_INDEPENDENT_VERIFIER_REQUIRED")
        if _time(receipt["verified_at"]) < _time(attempt["started_at"]):
            raise MigrationModelError("PQC_VERIFICATION_PREDATES_ATTEMPT")
        if receipt["outcome"] not in ("passed", "failed"):
            raise MigrationModelError()
        state = "resolved" if receipt["outcome"] == "passed" else "failed"
        attempt["state"] = state
        attempt["verification_sha256"] = canonical_digest(receipt)
        case["state"] = state
        case["revision"] += 1
        self._cases[work_item_id] = case
        return {
            "simulation_only": True,
            "live_execution_authorized": False,
            "migration_state": state,
            "verification_sha256": attempt["verification_sha256"],
        }

    def record_simulated_recovery(
        self,
        work_item_id: str,
        *,
        recovery_ref: str,
        recovery_evidence_ref: str,
        expected_revision: int,
    ) -> dict[str, Any]:
        case = self._case(work_item_id, expected_revision)
        if case["phase"] < 3 or case["state"] != "failed":
            raise MigrationModelError("PQC_RECOVERY_STATE_INVALID")
        if _ref(recovery_ref) != case["plan"]["recovery_ref"]:
            raise MigrationModelError("PQC_RECOVERY_BINDING_MISMATCH")
        _ref(recovery_evidence_ref)
        # Forward remediation is not a rollback and is never inferred complete.
        case["state"] = (
            "rolled_back"
            if case["plan"]["recovery_strategy"] == "rollback"
            else "blocked"
        )
        case["revision"] += 1
        self._cases[work_item_id] = case
        return {
            "simulation_only": True,
            "migration_state": case["state"],
            "recovery_evidence_ref": recovery_evidence_ref,
            "migration_success": False,
            "live_execution_authorized": False,
        }
