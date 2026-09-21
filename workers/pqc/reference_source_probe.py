"""Disabled molecular Worker candidate over three fixed synthetic source pages.

No caller-supplied path, provider URL, payload, credential, database or effect.
The controller owns any later persistence; this Worker returns only counts/hashes.
"""

from __future__ import annotations

import json
from typing import Any

from worker_runtime.grants import Grant
from workers import sdk as worker_sdk
from workers.pqc.assessment_sources import ROOT, normalize_page
from workers.pqc.safety import sha256_hex


WORKER_NAME = "pqc_reference_source_probe"
CAPABILITY = "pqc.contract_fixture.probe"
FIELDS = {"fixture_kind", "tenant_id", "observed_at", "synthetic"}


def validate_input(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError("invalid_reference_probe_input")
    if value["synthetic"] is not True or value["fixture_kind"] not in {
        "cmdb",
        "pki",
        "tls",
    }:
        raise ValueError("invalid_reference_probe_input")
    if not isinstance(value["tenant_id"], str) or not isinstance(
        value["observed_at"], str
    ):
        raise ValueError("invalid_reference_probe_input")


def project_fixture(kind: str, tenant_id: str, observed_at: str) -> dict[str, Any]:
    """Pure fixed-fixture projection, also callable by offline conformance tests."""
    validate_input(
        dict(
            fixture_kind=kind,
            tenant_id=tenant_id,
            observed_at=observed_at,
            synthetic=True,
        )
    )
    fixture_bytes = (ROOT / f"{kind}.page.json").read_bytes()
    records = normalize_page(
        kind,
        json.loads(fixture_bytes),
        tenant_id=tenant_id,
        source_instance_id=f"synthetic-{kind}",
        observed_at=observed_at,
    )
    canonical = json.dumps(
        records, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return {
        "worker": WORKER_NAME,
        "fixture_kind": kind,
        "record_count": len(records),
        "fixture_sha256": sha256_hex(fixture_bytes),
        "observations_sha256": sha256_hex(canonical),
        "synthetic": True,
        "external_effects": False,
        "evidence_status": "contract_tested",
    }


def run_reference_source_probe(
    value: Any, *, grant: Grant | None = None
) -> dict[str, Any]:
    if (
        grant is None
        or CAPABILITY not in grant.capabilities
        or not isinstance(value, dict)
        or grant.audit.get("tenant_id") != value.get("tenant_id")
    ):
        return {
            "success": False,
            "retryable": False,
            "status": "failed",
            "output": {},
            "error": {
                "code": "PQC_REFERENCE_PROBE_DENIED",
                "message": "reference probe denied",
            },
        }
    try:
        validate_input(value)
        output = project_fixture(
            value["fixture_kind"], value["tenant_id"], value["observed_at"]
        )
        return {
            "success": True,
            "retryable": False,
            "status": "completed",
            "output": output,
        }
    except Exception:
        return {
            "success": False,
            "retryable": False,
            "status": "failed",
            "output": {},
            "error": {
                "code": "PQC_REFERENCE_PROBE_INVALID",
                "message": "reference fixture validation failed",
            },
        }


def main() -> None:
    worker_sdk.run_worker(
        run_reference_source_probe, validate=validate_input, timeout_seconds=30
    )


if __name__ == "__main__":
    main()
