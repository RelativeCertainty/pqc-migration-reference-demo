from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Generic, Mapping, Protocol, TypeVar

from .models import JSONScalar, ProviderPage, RetryClass


T = TypeVar("T")


class IdempotencyStatus(StrEnum):
    CREATED = "created"
    REPLAYED = "replayed"
    RECONCILED = "reconciled"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SafeProviderReceipt:
    provider_record_ref: str | None
    provider_revision_token: str | None
    idempotency_status: IdempotencyStatus
    retry_class: RetryClass
    receipt_digest: str
    provider_call_performed: bool


@dataclass(frozen=True)
class PortResult(Generic[T]):
    ok: bool
    value: T | None
    receipt: SafeProviderReceipt
    error_code: str | None = None


@dataclass(frozen=True)
class IntegrationProfileRef:
    profile_ref: str
    profile_revision: str


@dataclass(frozen=True)
class CapabilityProbe:
    capabilities: tuple[str, ...]
    unsupported_capabilities: tuple[str, ...]
    provider_release: str | None


@dataclass(frozen=True)
class HarvestRequest:
    profile: IntegrationProfileRef
    artifact_ref: str
    artifact_sha256: str
    cursor: str | None = None


@dataclass(frozen=True)
class EvidenceImportRequest:
    profile: IntegrationProfileRef
    artifact_ref: str
    artifact_sha256: str
    media_type: str


@dataclass(frozen=True)
class EnsureTicket:
    external_id: str
    work_item_ref: str
    title_code: str
    fields: Mapping[str, JSONScalar] = field(default_factory=dict)


@dataclass(frozen=True)
class EnsureChange:
    external_id: str
    plan_ref: str
    plan_digest: str
    change_type: str
    fields: Mapping[str, JSONScalar] = field(default_factory=dict)


@dataclass(frozen=True)
class EnsureTask:
    external_id: str
    change_ref: str
    wave: int
    fields: Mapping[str, JSONScalar] = field(default_factory=dict)


@dataclass(frozen=True)
class ReadSnapshot:
    provider_record_ref: str
    expected_revision_token: str | None = None


@dataclass(frozen=True)
class Transition:
    provider_record_ref: str
    expected_revision_token: str
    target_state: str


@dataclass(frozen=True)
class AttachEvidence:
    provider_record_ref: str
    artifact_ref: str
    artifact_sha256: str
    evidence_kind: str


@dataclass(frozen=True)
class Reconcile:
    provider_record_ref: str
    cursor: str | None = None


@dataclass(frozen=True)
class ExecutionRequest:
    plan_ref: str
    plan_digest: str
    permit_ref: str
    permit_digest: str


class CapabilityProbePort(Protocol):
    def probe(self, profile: IntegrationProfileRef) -> PortResult[CapabilityProbe]: ...


class InventoryHarvestPort(Protocol):
    def harvest(self, request: HarvestRequest) -> PortResult[ProviderPage]: ...


class EvidenceImportPort(Protocol):
    def import_evidence(
        self, request: EvidenceImportRequest
    ) -> PortResult[ProviderPage]: ...


class TicketingPort(Protocol):
    def ensure_ticket(
        self, command: EnsureTicket
    ) -> PortResult[Mapping[str, JSONScalar]]: ...


class ChangeManagementPort(Protocol):
    def ensure_change(
        self, command: EnsureChange
    ) -> PortResult[Mapping[str, JSONScalar]]: ...

    def ensure_task(
        self, command: EnsureTask
    ) -> PortResult[Mapping[str, JSONScalar]]: ...

    def transition(
        self, command: Transition
    ) -> PortResult[Mapping[str, JSONScalar]]: ...


class CMDBSnapshotPort(Protocol):
    def read_cmdb_snapshot(
        self, command: ReadSnapshot
    ) -> PortResult[Mapping[str, JSONScalar]]: ...


class ApprovalSnapshotPort(Protocol):
    def read_approval_snapshot(
        self, command: ReadSnapshot
    ) -> PortResult[Mapping[str, JSONScalar]]: ...


class EvidenceAttachmentPort(Protocol):
    def attach_evidence(
        self, command: AttachEvidence
    ) -> PortResult[Mapping[str, JSONScalar]]: ...


class RemediationPlanPort(Protocol):
    def resolve_plan(self, plan_ref: str) -> PortResult[Mapping[str, JSONScalar]]: ...


class ExecutionPort(Protocol):
    def execute(
        self, command: ExecutionRequest
    ) -> PortResult[Mapping[str, JSONScalar]]: ...


class RollbackPort(Protocol):
    def rollback(
        self, command: ExecutionRequest
    ) -> PortResult[Mapping[str, JSONScalar]]: ...


class VerificationPort(Protocol):
    def verify(
        self, command: ExecutionRequest
    ) -> PortResult[Mapping[str, JSONScalar]]: ...


class ProviderEventPort(Protocol):
    def reconcile(self, command: Reconcile) -> PortResult[Mapping[str, JSONScalar]]: ...
