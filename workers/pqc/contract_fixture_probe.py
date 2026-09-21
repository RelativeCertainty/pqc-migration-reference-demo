from __future__ import annotations

import json
import sys
from typing import Any, Mapping

import workers.sdk as worker_sdk
from worker_runtime.grants import Grant

from .adapters import (
    SnykCodeSarifAdapter,
    VenafiCertificateManagerAdapter,
    VenafiNGTSAdapter,
)
from .canonical import (
    require_canonical_contract_pack,
    require_canonical_crypto_observation,
)
from .contract_pack import ContractPackError, ContractPackLoader
from .errors import PQCAdapterError
from .models import ImportContext, ImportTimestamps
from .safety import sha256_hex, stable_sha256_id


WORKER_NAME = "pqc_contract_fixture_probe"
REQUIRED_CAPABILITY = "pqc.contract_fixture.probe"
_DENIED_CODE = "PQC_CONTRACT_FIXTURE_PROBE_DENIED"
_ADAPTERS = {
    SnykCodeSarifAdapter.adapter_id: SnykCodeSarifAdapter,
    VenafiCertificateManagerAdapter.adapter_id: VenafiCertificateManagerAdapter,
    VenafiNGTSAdapter.adapter_id: VenafiNGTSAdapter,
}
_EXPECTED_INPUT_KEYS = {
    "contract_pack_id",
    "adapter_id",
    "fixture_ref",
    "tenant_id",
    "source_ref",
    "asset_ref",
    "estate_class",
    "collected_at",
    "package_generated_at",
    "imported_at",
    "page_number",
    "page_size",
    "synthetic",
}


def validate_input(config: Mapping[str, Any]) -> None:
    if not isinstance(config, dict) or set(config) != _EXPECTED_INPUT_KEYS:
        raise ValueError("invalid contract fixture probe input")
    for key in (
        "contract_pack_id",
        "adapter_id",
        "fixture_ref",
        "tenant_id",
        "source_ref",
        "asset_ref",
        "estate_class",
        "package_generated_at",
        "imported_at",
    ):
        value = config.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 256:
            raise ValueError("invalid contract fixture probe input")
    collected_at = config.get("collected_at")
    if collected_at is not None and (
        not isinstance(collected_at, str) or len(collected_at) > 40
    ):
        raise ValueError("invalid contract fixture probe input")
    for key in ("page_number", "page_size"):
        value = config.get(key)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("invalid contract fixture probe input")
    if config.get("synthetic") is not True:
        raise ValueError("contract fixture probe is synthetic-only")


def _context(config: Mapping[str, Any]) -> ImportContext:
    return ImportContext(
        tenant_id=str(config["tenant_id"]),
        source_name=str(config["source_ref"]),
        asset_key=str(config["asset_ref"]),
        asset_name="Synthetic contract fixture",
        estate_class=str(config["estate_class"]),
        timestamps=ImportTimestamps(
            collected_at=config["collected_at"]
            if isinstance(config["collected_at"], str)
            else None,
            package_generated_at=str(config["package_generated_at"]),
            imported_at=str(config["imported_at"]),
        ),
        synthetic=True,
        page_number=int(config["page_number"]),
        page_size=int(config["page_size"]),
    )


def _denied_result() -> dict[str, object]:
    return {
        "success": False,
        "retryable": False,
        "output": {"worker": WORKER_NAME, "external_effects": False},
        "error": {
            "code": _DENIED_CODE,
            "message": "contract fixture probe denied by capability policy",
            "details": {"retry_class": "authorization"},
        },
    }


def run_contract_fixture_probe(
    config: Mapping[str, Any], *, grant: Grant | None = None
) -> dict[str, object]:
    bound_tenant = grant.audit.get("tenant_id") if grant is not None else None
    if (
        grant is None
        or REQUIRED_CAPABILITY not in grant.capabilities
        or not isinstance(config, Mapping)
        or bound_tenant != config.get("tenant_id")
    ):
        return _denied_result()
    try:
        validate_input(config)
        loader = ContractPackLoader()
        pack = loader.load(str(config["contract_pack_id"]))
        canonical_pack = require_canonical_contract_pack(
            pack, tenant_id=str(config["tenant_id"])
        )
        adapter_id = str(config["adapter_id"])
        if pack.adapter_id != adapter_id or adapter_id not in _ADAPTERS:
            raise ContractPackError()
        fixture_ref = str(config["fixture_ref"])
        if fixture_ref not in pack.manifest["fixture_paths"]:
            raise ContractPackError()
        payload = pack.load_json_artifact(fixture_ref)
        page = _ADAPTERS[adapter_id](loader).adapt(payload, _context(config))
        source_event_ref = stable_sha256_id(
            "source-event",
            config["tenant_id"],
            pack.pack_id,
            config["source_ref"],
            config["collected_at"],
            fixture_ref,
        )
        integration_profile_ref = stable_sha256_id(
            "integration-profile",
            config["tenant_id"],
            adapter_id,
            canonical_pack["canonical_content_sha256"],
        )
        canonical_observations = [
            require_canonical_crypto_observation(
                item,
                tenant_id=str(config["tenant_id"]),
                source_event_ref=source_event_ref,
                integration_profile_ref=integration_profile_ref,
            )
            for item in page.observations
        ]
        observation_refs = sorted(
            str(item["canonical_content_sha256"]) for item in canonical_observations
        )
        observations_digest = sha256_hex(
            json.dumps(observation_refs, separators=(",", ":"), ensure_ascii=True)
        )
        output = {
            "worker": WORKER_NAME,
            "contract_pack_id": pack.pack_id,
            "contract_pack_digest": canonical_pack["canonical_content_sha256"],
            "adapter_id": adapter_id,
            "fixture_ref_digest": stable_sha256_id(
                "fixture", pack.pack_id, fixture_ref
            ),
            "observation_count": len(observation_refs),
            "observations_digest": observations_digest,
            "total_records": page.total_records,
            "accepted_records": page.accepted_records,
            "skipped_records": page.skipped_records,
            "duplicate_records": page.duplicate_records,
            "sensitivity": page.sensitivity.value,
            "diagnostic_codes": [item.code for item in page.diagnostics],
            "evidence_status": pack.evidence_status.value,
            "synthetic": True,
            "external_effects": False,
        }
        return {"success": True, "retryable": False, "output": output}
    except PQCAdapterError as exc:
        return {
            "success": False,
            "retryable": exc.retryable,
            "output": {"worker": WORKER_NAME, "external_effects": False},
            "error": exc.to_worker_error(),
        }
    except ContractPackError as exc:
        return {
            "success": False,
            "retryable": False,
            "output": {"worker": WORKER_NAME, "external_effects": False},
            "error": {
                "code": exc.code,
                "message": "contract pack failed validation",
                "details": {"retry_class": "invalid_request"},
            },
        }


def main() -> None:
    worker_sdk.sys = sys
    worker_sdk.run_worker(run_contract_fixture_probe, validate=validate_input)


if __name__ == "__main__":
    main()
