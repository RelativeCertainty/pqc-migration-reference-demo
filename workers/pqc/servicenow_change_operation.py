from __future__ import annotations

import hashlib
import json
import os
import ssl
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

import workers.sdk as worker_sdk
from worker_runtime.grants import Grant

from .models import RetryClass
from .ports import PortResult
from .servicenow import (
    RequestContext,
    ServiceNowClient,
    ServiceNowOAuthClientCredentialsAuthorizer,
    NoRedirectHandler,
    UrllibAuthenticatedTransport,
)
from .servicenow.contracts import ContractConfigurationError, ScopedContractRegistry


WORKER_NAME = "pqc_servicenow_change_operation"
REQUIRED_CAPABILITY = "pqc.ticket.reconcile"
MAX_NORMALIZED_RESPONSE_BYTES = 65_536
_SHA256 = __import__("re").compile(r"^[0-9a-f]{64}$")
_ROOT = Path(__file__).resolve().parents[2]
_OPERATION_SCHEMA = _ROOT / "schemas" / "PQCWorkerOperation.v1.schema.json"
_ACTION_BINDING_SCHEMA = _ROOT / "schemas" / "PQCActionBinding.v1.schema.json"
_CONSUMPTION_SCHEMA = _ROOT / "schemas" / "PQCPermitConsumptionReceipt.v1.schema.json"
_COMMON_SCHEMA = _ROOT / "schemas" / "common.ProductionAlignment.v1.schema.json"
_CLIENT_ID_REF = {
    "name": "servicenow_oauth_client_id",
    "provider": "vault",
    "vaultPath": "secret/data/pba/internal/pqc/servicenow",
    "vaultKey": "client_id",
}
_CLIENT_SECRET_REF = {
    "name": "servicenow_oauth_client_secret",
    "provider": "vault",
    "vaultPath": "secret/data/pba/internal/pqc/servicenow",
    "vaultKey": "client_secret",
}
_ENV_SECRET_NAMES = {
    "servicenow_oauth_client_id": (
        "PBA_SECRET_PQC_SERVICENOW_CHANGE_OPERATION_SERVICENOW_OAUTH_CLIENT_ID"
    ),
    "servicenow_oauth_client_secret": (
        "PBA_SECRET_PQC_SERVICENOW_CHANGE_OPERATION_SERVICENOW_OAUTH_CLIENT_SECRET"
    ),
}
_OPERATION_AUTHORITY = {
    "changes.ensure": ("pqc.ticket.change.propose", "preauthorized_reversible"),
    "changes.read": ("pqc.ticket.reconcile.read", "read_only"),
    "change_tasks.transition": ("pqc.ticket.change.write", "approval_bound"),
    "approvals.read": ("pqc.ticket.reconcile.read", "read_only"),
    "verifications.append": ("pqc.ticket.change.write", "approval_bound"),
    "changes.close": ("pqc.ticket.change.close", "approval_bound"),
}
_MUTATIONS = {
    "changes.ensure",
    "change_tasks.transition",
    "verifications.append",
    "changes.close",
}
_REQUEST_IDEMPOTENCY_FIELDS = {
    "changes.ensure": "idempotency_key_sha256",
    "change_tasks.transition": "transition_sha256",
    "verifications.append": "verification_record_sha256",
    "changes.close": "closure_request_sha256",
}


class _ClientFactory(Protocol):
    def __call__(self, *, tenant_id: str) -> ServiceNowClient: ...


class ServiceNowWorkerError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__("ServiceNow operation failed safely")
        self.code = code


def _contract_validators() -> tuple[
    Draft202012Validator, Draft202012Validator, Draft202012Validator
]:
    common = json.loads(_COMMON_SCHEMA.read_text(encoding="utf-8"))
    operation = json.loads(_OPERATION_SCHEMA.read_text(encoding="utf-8"))
    action_binding = json.loads(_ACTION_BINDING_SCHEMA.read_text(encoding="utf-8"))
    consumption = json.loads(_CONSUMPTION_SCHEMA.read_text(encoding="utf-8"))
    registry = Registry().with_resources(
        [
            (
                common["$id"],
                Resource.from_contents(common, default_specification=DRAFT202012),
            ),
            (
                operation["$id"],
                Resource.from_contents(operation, default_specification=DRAFT202012),
            ),
            (
                action_binding["$id"],
                Resource.from_contents(
                    action_binding, default_specification=DRAFT202012
                ),
            ),
            (
                consumption["$id"],
                Resource.from_contents(consumption, default_specification=DRAFT202012),
            ),
        ]
    )
    return (
        Draft202012Validator(
            operation, registry=registry, format_checker=FormatChecker()
        ),
        Draft202012Validator(
            action_binding, registry=registry, format_checker=FormatChecker()
        ),
        Draft202012Validator(
            consumption, registry=registry, format_checker=FormatChecker()
        ),
    )


_VALIDATOR, _ACTION_BINDING_VALIDATOR, _CONSUMPTION_VALIDATOR = _contract_validators()
_SCOPED_CONTRACTS = ScopedContractRegistry()


def _sha256(value: object) -> str:
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _nul_sha256(values: list[str]) -> str:
    return hashlib.sha256("\0".join(values).encode("utf-8")).hexdigest()


def _action_binding_sha256(value: Mapping[str, object]) -> str:
    return _nul_sha256(
        [
            str(value.get("contract_version", "")),
            str(value.get("tenant_id", "")),
            str(value.get("permit_id", "")),
            str(value.get("plan_id", "")),
            str(value.get("plan_revision", "")),
            str(value.get("plan_sha256", "")),
            str(value.get("asset_set_sha256", "")),
            str(value.get("cmdb_snapshot_sha256", "")),
            str(value.get("target_state_sha256", "")),
            str(value.get("action_code", "")),
            str(value.get("effect_class", "")),
            str(value.get("provider_integration_id", "")),
            str(value.get("provider_profile_revision", "")),
            str(value.get("destination_ref", "")),
            str(value.get("idempotency_key_sha256", "")),
            str(value.get("request_fields_sha256", "")),
            str(value.get("approval_revision", "")),
            str(value.get("preauthorization_revision", "")),
            str(value.get("executor_subject_ref", "")),
        ]
    )


def _consumption_sha256(value: Mapping[str, object]) -> str:
    return _nul_sha256(
        [
            str(value.get("contract_version", "")),
            str(value.get("tenant_id", "")),
            str(value.get("worker_run_id", "")),
            str(value.get("permit_id", "")),
            str(value.get("action_binding_sha256", "")),
            str(value.get("consumed_by_subject_ref", "")),
            str(value.get("authority_revision", "")),
            str(value.get("ledger_revision", "")),
            str(value.get("maximum_provider_write_calls", "")),
            str(value.get("consumed_at", "")),
        ]
    )


def _parse_utc(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID") from None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID")
    return parsed.astimezone(timezone.utc)


def _validate_request_fields_projection(
    *,
    operation_document: Mapping[str, object],
    provider_operation: str,
    request_fields: Mapping[str, object],
    request_id: object,
    correlation_ref: object,
    requested_at: object,
) -> None:
    expected_sha256 = operation_document.get("request_fields_sha256")
    if (
        not isinstance(expected_sha256, str)
        or _SHA256.fullmatch(expected_sha256) is None
        or _sha256(request_fields) != expected_sha256
    ):
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID")
    try:
        route = _SCOPED_CONTRACTS.route(provider_operation)
        payload = dict(request_fields)
        payload["header"] = {
            "contract_version": "pba.pqc.servicenow-api.v1",
            "request_id": request_id,
            "tenant_id": operation_document.get("tenant_id"),
            "correlation_ref": correlation_ref,
            "requested_at": requested_at,
            "contains_raw_payload": False,
        }
        route.request_validator.validate(payload)
    except (ContractConfigurationError, ValidationError, TypeError, ValueError):
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID") from None


def _validate_effect_authority(
    *,
    operation_document: Mapping[str, object],
    request_fields: Mapping[str, object],
    authority: Mapping[str, object],
    requested_at: object,
) -> None:
    if set(authority) != {"kind", "action_binding", "permit_consumption"}:
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID")
    if authority.get("kind") != "permit_consumption":
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID")
    action_binding = authority.get("action_binding")
    consumption = authority.get("permit_consumption")
    if not isinstance(action_binding, dict) or not isinstance(consumption, dict):
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID")
    try:
        _ACTION_BINDING_VALIDATOR.validate(action_binding)
        _CONSUMPTION_VALIDATOR.validate(consumption)
    except ValidationError:
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID") from None

    profile_ref = operation_document.get("provider_profile_ref")
    plan_ref = operation_document.get("plan_ref")
    if not isinstance(profile_ref, Mapping) or not isinstance(plan_ref, Mapping):
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID")
    exact_operation_binding = {
        "tenant_id": operation_document.get("tenant_id"),
        "plan_id": plan_ref.get("plan_id"),
        "plan_revision": plan_ref.get("revision_id"),
        "plan_sha256": plan_ref.get("plan_sha256"),
        "target_state_sha256": operation_document.get("target_state_sha256"),
        "action_code": operation_document.get("action_code"),
        "effect_class": operation_document.get("effect_class"),
        "provider_integration_id": profile_ref.get("id"),
        "provider_profile_revision": profile_ref.get("revision_id"),
        "destination_ref": operation_document.get("destination_ref"),
        "idempotency_key_sha256": operation_document.get("idempotency_key_sha256"),
        "request_fields_sha256": operation_document.get("request_fields_sha256"),
        "executor_subject_ref": operation_document.get("actor_principal_ref"),
    }
    if any(
        action_binding.get(field) != expected
        for field, expected in exact_operation_binding.items()
    ):
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID")

    for request_field, action_field in {
        "plan_ref": "plan_id",
        "plan_revision_ref": "plan_revision",
        "plan_sha256": "plan_sha256",
        "asset_set_sha256": "asset_set_sha256",
        "cmdb_snapshot_sha256": "cmdb_snapshot_sha256",
        "target_state_sha256": "target_state_sha256",
        "permit_ref": "permit_id",
    }.items():
        if request_field in request_fields and request_fields.get(
            request_field
        ) != action_binding.get(action_field):
            raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID")

    effect = operation_document.get("effect_class")
    if effect == "preauthorized_reversible":
        if action_binding.get("approval_revision") != "" or not action_binding.get(
            "preauthorization_revision"
        ):
            raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID")
    elif effect == "approval_bound":
        if action_binding.get("preauthorization_revision") != "" or action_binding.get(
            "approval_revision"
        ) != operation_document.get("approval_revision_ref"):
            raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID")
    else:
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID")

    action_sha256 = _action_binding_sha256(action_binding)
    authority_revision = (
        action_binding.get("preauthorization_revision")
        if effect == "preauthorized_reversible"
        else action_binding.get("approval_revision")
    )
    exact_consumption_binding = {
        "tenant_id": action_binding.get("tenant_id"),
        "worker_run_id": operation_document.get("worker_run_id"),
        "permit_id": action_binding.get("permit_id"),
        "action_binding_sha256": action_sha256,
        "consumed_by_subject_ref": operation_document.get("actor_principal_ref"),
        "authority_revision": authority_revision,
    }
    if any(
        consumption.get(field) != expected
        for field, expected in exact_consumption_binding.items()
    ):
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID")
    consumption_sha256 = _consumption_sha256(consumption)
    if (
        consumption.get("canonical_sha256") != consumption_sha256
        or consumption.get("consumption_ref") != f"sha256:{consumption_sha256}"
    ):
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID")
    consumed_at = _parse_utc(consumption.get("consumed_at"))
    evaluated_at = _parse_utc(requested_at)
    if consumed_at < evaluated_at - timedelta(minutes=17) or consumed_at > (
        evaluated_at + timedelta(seconds=30)
    ):
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID")


def validate_input(value: Mapping[str, Any]) -> None:
    if not isinstance(value, dict) or set(value) != {
        "operation_document",
        "provider_operation",
        "request_fields",
        "request_id",
        "correlation_ref",
        "requested_at",
        "authority",
    }:
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_INPUT_INVALID")
    operation_document = value.get("operation_document")
    request_fields = value.get("request_fields")
    authority = value.get("authority")
    provider_operation = value.get("provider_operation")
    if (
        not isinstance(operation_document, dict)
        or not isinstance(request_fields, dict)
        or "header" in request_fields
        or not isinstance(authority, dict)
        or not isinstance(provider_operation, str)
        or provider_operation not in _OPERATION_AUTHORITY
    ):
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_INPUT_INVALID")
    try:
        _VALIDATOR.validate(operation_document)
    except ValidationError:
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID") from None
    expected_action, expected_effect = _OPERATION_AUTHORITY[provider_operation]
    if (
        operation_document.get("capability_code") != REQUIRED_CAPABILITY
        or operation_document.get("action_code") != expected_action
        or operation_document.get("effect_class") != expected_effect
        or operation_document.get("contains_raw_provider_payload") is not False
    ):
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID")
    for key in ("request_id", "correlation_ref", "requested_at"):
        item = value.get(key)
        if not isinstance(item, str) or not 1 <= len(item) <= 256:
            raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_INPUT_INVALID")
    _validate_request_fields_projection(
        operation_document=operation_document,
        provider_operation=provider_operation,
        request_fields=request_fields,
        request_id=value.get("request_id"),
        correlation_ref=value.get("correlation_ref"),
        requested_at=value.get("requested_at"),
    )
    expected_authority_kind = {
        "read_only": "none",
        "preauthorized_reversible": "permit_consumption",
        "approval_bound": "permit_consumption",
    }[expected_effect]
    if authority.get("kind") != expected_authority_kind:
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID")
    if expected_authority_kind == "none":
        if set(authority) != {"kind"}:
            raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID")
    else:
        _validate_effect_authority(
            operation_document=operation_document,
            request_fields=request_fields,
            authority=authority,
            requested_at=value.get("requested_at"),
        )
    if provider_operation in _MUTATIONS:
        idempotency = operation_document.get("idempotency_key_sha256")
        request_field = _REQUEST_IDEMPOTENCY_FIELDS[provider_operation]
        if (
            _SHA256.fullmatch(str(idempotency)) is None
            or request_fields.get(request_field) != idempotency
        ):
            raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID")
    elif "idempotency_key_sha256" in operation_document:
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_AUTHORITY_INVALID")


def _require_grant(
    operation_document: Mapping[str, object],
    authority: Mapping[str, object],
    grant: Grant | None,
) -> None:
    if grant is None:
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_DENIED")
    try:
        grant.require(REQUIRED_CAPABILITY)
    except PermissionError:
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_DENIED") from None
    profile_ref = operation_document.get("provider_profile_ref")
    if not isinstance(profile_ref, Mapping):
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_DENIED")
    expected_audit = {
        "tenant_id": operation_document.get("tenant_id"),
        "worker_run_id": operation_document.get("worker_run_id"),
        "pqc_action_code": operation_document.get("action_code"),
        "operation_document_sha256": _sha256(operation_document),
        "provider_profile_sha256": profile_ref.get("content_sha256"),
        "destination_ref": operation_document.get("destination_ref"),
        "authority_kind": authority.get("kind"),
        "request_fields_sha256": operation_document.get("request_fields_sha256"),
    }
    if authority.get("kind") != "none":
        action_binding = authority.get("action_binding")
        consumption = authority.get("permit_consumption")
        if not isinstance(action_binding, Mapping) or not isinstance(
            consumption, Mapping
        ):
            raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_DENIED")
        expected_audit["authority_ref"] = consumption.get("consumption_ref")
        expected_audit["authority_sha256"] = consumption.get("canonical_sha256")
        expected_audit["authority_revision"] = consumption.get("authority_revision")
        expected_audit["action_binding_sha256"] = consumption.get(
            "action_binding_sha256"
        )
    if operation_document.get("idempotency_key_sha256") is not None:
        expected_audit["idempotency_key_sha256"] = operation_document.get(
            "idempotency_key_sha256"
        )
    if any(
        grant.audit.get(key) != expected for key, expected in expected_audit.items()
    ):
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_DENIED")


def _require_runtime_binding(operation_document: Mapping[str, object]) -> None:
    if (
        os.getenv("PBA_WORKER_NAME") != WORKER_NAME
        or os.getenv("PBA_TENANT") != operation_document.get("tenant_id")
        or os.getenv("PBA_RUN_ID") != operation_document.get("worker_run_id")
        or os.getenv("PBA_DOMAIN") != "pqc_migration"
    ):
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_ROUTE_MISMATCH")


class _EnvironmentSecretResolver:
    def __call__(self, ref: Mapping[str, object], *, tenant_id: str) -> str:
        if tenant_id != os.getenv("PBA_TENANT"):
            raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_SECRET_UNAVAILABLE")
        name = ref.get("name")
        env_name = _ENV_SECRET_NAMES.get(str(name))
        value = os.getenv(env_name or "")
        if not value:
            raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_SECRET_UNAVAILABLE")
        return value


def _runtime_client(*, tenant_id: str) -> ServiceNowClient:
    base_url = os.getenv("PBA_PQC_SERVICENOW_BASE_URL", "").strip()
    if not base_url:
        raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_RUNTIME_UNAVAILABLE")
    tls_context = ssl.create_default_context()
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=tls_context),
        NoRedirectHandler(),
    )
    authorizer = ServiceNowOAuthClientCredentialsAuthorizer(
        base_url=base_url,
        tenant_id=tenant_id,
        client_id_ref=_CLIENT_ID_REF,
        client_secret_ref=_CLIENT_SECRET_REF,
        secret_resolver=_EnvironmentSecretResolver(),
        opener=opener,
    )
    transport = UrllibAuthenticatedTransport(opener=opener, authorizer=authorizer)
    return ServiceNowClient(
        base_url=base_url,
        tenant_id=tenant_id,
        transport=transport,
    )


def _call(
    client: ServiceNowClient,
    provider_operation: str,
    context: RequestContext,
    request_fields: Mapping[str, object],
) -> PortResult[Mapping[str, object]]:
    if provider_operation == "changes.ensure":
        return client.ensure_change(context, request_fields)
    if provider_operation == "changes.read":
        return client.read_change(context, str(request_fields.get("change_ref", "")))
    if provider_operation == "change_tasks.transition":
        fields = dict(request_fields)
        task_ref = str(fields.pop("task_ref", ""))
        return client.transition_change_task(context, task_ref, fields)
    if provider_operation == "approvals.read":
        return client.read_approval_snapshot(
            context, str(request_fields.get("approval_ref", ""))
        )
    if provider_operation == "verifications.append":
        return client.append_verification(context, request_fields)
    if provider_operation == "changes.close":
        fields = dict(request_fields)
        change_ref = str(fields.pop("change_ref", ""))
        return client.close_change(context, change_ref, fields)
    raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_INPUT_INVALID")


def run_servicenow_change_operation(
    config: Mapping[str, Any],
    *,
    grant: Grant | None = None,
    client_factory: _ClientFactory = _runtime_client,
    traceparent: str | None = None,
) -> dict[str, object]:
    try:
        validate_input(config)
        operation_document = config["operation_document"]
        authority = config["authority"]
        assert isinstance(operation_document, dict)
        assert isinstance(authority, dict)
        _require_grant(operation_document, authority, grant)
        _require_runtime_binding(operation_document)
        active_traceparent = traceparent or worker_sdk.get_traceparent()
        if not isinstance(active_traceparent, str):
            raise ServiceNowWorkerError("PQC_SERVICENOW_WORKER_TRACE_REQUIRED")
        idempotency = operation_document.get("idempotency_key_sha256")
        context = RequestContext(
            tenant_id=str(operation_document["tenant_id"]),
            request_id=str(config["request_id"]),
            correlation_ref=str(config["correlation_ref"]),
            requested_at=str(config["requested_at"]),
            traceparent=active_traceparent,
            idempotency_key_sha256=str(idempotency)
            if idempotency is not None
            else None,
        )
        client = client_factory(tenant_id=context.tenant_id)
        result = _call(
            client,
            str(config["provider_operation"]),
            context,
            config["request_fields"],
        )
        response = dict(result.value) if result.value is not None else None
        if response is not None:
            encoded = json.dumps(
                response, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode("ascii")
            if len(encoded) > MAX_NORMALIZED_RESPONSE_BYTES:
                raise ServiceNowWorkerError(
                    "PQC_SERVICENOW_WORKER_RESPONSE_LIMIT_EXCEEDED"
                )
        mutation = str(config["provider_operation"]) in _MUTATIONS
        reconciliation_required = (
            result.receipt.retry_class == RetryClass.AMBIGUOUS_OUTCOME
        )
        output: dict[str, object] = {
            "worker": WORKER_NAME,
            "provider_operation": config["provider_operation"],
            "action_code": operation_document["action_code"],
            "outcome": "succeeded"
            if result.ok
            else ("reconciliation_required" if reconciliation_required else "failed"),
            "normalized_response": response,
            "normalized_response_sha256": _sha256(response)
            if response is not None
            else None,
            "provider_record_ref": result.receipt.provider_record_ref,
            "provider_revision_ref": result.receipt.provider_revision_token,
            "idempotency_status": result.receipt.idempotency_status.value,
            "retry_class": result.receipt.retry_class.value,
            "receipt_sha256": result.receipt.receipt_digest,
            "provider_call_performed": result.receipt.provider_call_performed,
            "external_effects_performed": (
                mutation and result.receipt.provider_call_performed
            ),
            "reconciliation_required": reconciliation_required,
            "unvalidated_provider_values_included": False,
            "sensitive_values_included": False,
        }
        if result.ok:
            return {"success": True, "retryable": False, "output": output}
        return {
            "success": False,
            "retryable": result.receipt.retry_class
            in {RetryClass.RATE_LIMITED, RetryClass.TRANSIENT}
            and not mutation,
            "output": output,
            "error": {
                "code": result.error_code or "PQC_SERVICENOW_PROVIDER_FAILED",
                "message": "ServiceNow operation failed safely",
                "details": {
                    "retry_class": result.receipt.retry_class.value,
                    "reconciliation_required": reconciliation_required,
                },
            },
        }
    except ServiceNowWorkerError as exc:
        return {
            "success": False,
            "retryable": False,
            "output": {
                "worker": WORKER_NAME,
                "provider_call_performed": False,
                "external_effects_performed": False,
                "unvalidated_provider_values_included": False,
                "sensitive_values_included": False,
            },
            "error": {
                "code": exc.code,
                "message": "ServiceNow operation failed safely",
                "details": {"retry_class": "invalid_request"},
            },
        }
    except Exception:
        return {
            "success": False,
            "retryable": False,
            "output": {
                "worker": WORKER_NAME,
                "provider_call_performed": False,
                "external_effects_performed": False,
                "unvalidated_provider_values_included": False,
                "sensitive_values_included": False,
            },
            "error": {
                "code": "PQC_SERVICENOW_WORKER_INTERNAL_FAILURE",
                "message": "ServiceNow operation failed safely",
                "details": {"retry_class": "invalid_request"},
            },
        }


def main() -> None:
    worker_sdk.sys = sys
    worker_sdk.run_worker(run_servicenow_change_operation, validate=validate_input)


if __name__ == "__main__":
    main()
