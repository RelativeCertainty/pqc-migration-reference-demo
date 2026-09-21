from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping, TypeAlias


JSONScalar: TypeAlias = str | int | float | bool | None


class RetryClass(StrEnum):
    NONE = "none"
    RATE_LIMITED = "rate_limited"
    TRANSIENT = "transient"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    INVALID_REQUEST = "invalid_request"
    SCHEMA_DRIFT = "schema_drift"
    CONFLICT = "conflict"
    AMBIGUOUS_OUTCOME = "ambiguous_outcome"
    NOT_SUPPORTED = "not_supported"


class Sensitivity(StrEnum):
    NONE = "none"
    CONFIDENTIAL_METADATA = "confidential_metadata"
    AUTH_SECRET = "auth_secret"


class EvidenceStatus(StrEnum):
    DOCUMENTED = "documented"
    CONTRACT_TESTED = "contract_tested"
    LIVE_READBACK = "live_readback"
    CLOSED_LOOP = "closed_loop"


class DiagnosticLevel(StrEnum):
    INFORMATION = "information"
    WARNING = "warning"


@dataclass(frozen=True)
class ImportTimestamps:
    """Four distinct times; callers must never collapse them into one value."""

    collected_at: str | None
    package_generated_at: str
    imported_at: str


@dataclass(frozen=True)
class ImportContext:
    tenant_id: str
    source_name: str
    asset_key: str
    asset_name: str
    estate_class: str
    timestamps: ImportTimestamps
    synthetic: bool
    page_number: int = 0
    page_size: int = 100
    max_pages: int = 2_000


@dataclass(frozen=True)
class AdapterDiagnostic:
    """Metadata-only diagnostic. Detail text is deliberately not accepted."""

    level: DiagnosticLevel
    code: str

    def to_dict(self) -> dict[str, str]:
        return {"level": self.level.value, "code": self.code}


@dataclass(frozen=True)
class NormalizedObservation:
    observation_id: str
    provider: str
    product: str
    dialect: str
    asset_type: str
    asset_ref: str
    source_record_ref: str
    observed_at: str | None
    collected_at: str | None
    package_generated_at: str
    imported_at: str
    attributes: Mapping[str, JSONScalar]
    sensitivity: Sensitivity
    synthetic: bool
    evidence_status: EvidenceStatus

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "pba.pqc.crypto-observation.v2",
            "observation_id": self.observation_id,
            "provider": self.provider,
            "product": self.product,
            "dialect": self.dialect,
            "asset_type": self.asset_type,
            "asset_ref": self.asset_ref,
            "source_record_ref": self.source_record_ref,
            "observed_at": self.observed_at,
            "collected_at": self.collected_at,
            "package_generated_at": self.package_generated_at,
            "imported_at": self.imported_at,
            "attributes": dict(self.attributes),
            "sensitivity": self.sensitivity.value,
            "synthetic": self.synthetic,
            "evidence_status": self.evidence_status.value,
        }


@dataclass(frozen=True)
class ProviderPage:
    adapter_id: str
    contract_pack_id: str
    source_ref: str
    observations: tuple[NormalizedObservation, ...]
    total_records: int
    accepted_records: int
    skipped_records: int
    duplicate_records: int
    page_number: int
    next_cursor: str | None
    sensitivity: Sensitivity
    diagnostics: tuple[AdapterDiagnostic, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "pba.pqc.provider-page.v1",
            "adapter_id": self.adapter_id,
            "contract_pack_id": self.contract_pack_id,
            "source_ref": self.source_ref,
            "observations": [item.to_dict() for item in self.observations],
            "total_records": self.total_records,
            "accepted_records": self.accepted_records,
            "skipped_records": self.skipped_records,
            "duplicate_records": self.duplicate_records,
            "page_number": self.page_number,
            "next_cursor": self.next_cursor,
            "sensitivity": self.sensitivity.value,
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }
