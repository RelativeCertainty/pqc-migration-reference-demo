from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from typing import Callable, Mapping
from urllib.parse import quote, urlencode, urlsplit

from jsonschema import ValidationError

from ..errors import classify_http_failure
from ..models import RetryClass
from ..ports import IdempotencyStatus, PortResult, SafeProviderReceipt
from .contracts import ContractConfigurationError, ScopedContractRegistry, ScopedRoute
from .transport import (
    AuthenticatedHTTPTransport,
    HTTPRequest,
    HTTPResponse,
    ResponseBodyTooLarge,
    TransportTimeout,
    TransportUnavailable,
)


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TRACEPARENT = re.compile(
    r"^00-(?!0{32})[0-9a-f]{32}-(?!0{16})[0-9a-f]{16}-[0-9a-f]{2}$"
)
_FORBIDDEN_QUERY_KEYS = frozenset(
    {
        "encoded_query",
        "sysparm_query",
        "sysparm_encoded_query",
        "table",
        "table_name",
    }
)
_FORBIDDEN_WRITE_TARGETS = frozenset(
    {
        "oauth_entity",
        "sys_properties",
        "sys_user",
        "sys_user_has_role",
        "sysapproval_approver",
    }
)
_SAFE_IDEMPOTENCY_DISPOSITIONS = {
    "created": IdempotencyStatus.CREATED,
    "inserted": IdempotencyStatus.CREATED,
    "already_recorded": IdempotencyStatus.REPLAYED,
    "reconciled": IdempotencyStatus.RECONCILED,
    "unchanged": IdempotencyStatus.RECONCILED,
    "updated": IdempotencyStatus.RECONCILED,
}
_MUTATION_IDEMPOTENCY_FIELDS = {
    "cis.reconcile": "idempotency_key_sha256",
    "crypto_assets.reconcile": "idempotency_key_sha256",
    "changes.ensure": "idempotency_key_sha256",
    "change_tasks.transition": "transition_sha256",
    "verifications.append": "verification_record_sha256",
    "changes.close": "closure_request_sha256",
}


@dataclass(frozen=True)
class RequestContext:
    tenant_id: str
    request_id: str
    correlation_ref: str
    requested_at: str
    traceparent: str
    idempotency_key_sha256: str | None = None


class ServiceNowClient:
    """Strict HTTP adapter for the PBA-authored ``x_pba_pqc`` scoped app.

    Authentication is intentionally absent from this API.  The injected
    transport must authenticate at send time, normally by resolving a SecretRef.
    """

    def __init__(
        self,
        *,
        base_url: str,
        tenant_id: str,
        transport: AuthenticatedHTTPTransport,
        registry: ScopedContractRegistry | None = None,
        timeout_seconds: float = 15.0,
        max_read_attempts: int = 3,
        max_request_bytes: int = 524_288,
        max_response_bytes: int = 1_048_576,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._base_url = self._validate_base_url(base_url)
        if not isinstance(tenant_id, str) or not re.fullmatch(
            r"[a-z][a-z0-9-]{1,62}[a-z0-9]", tenant_id
        ):
            raise ValueError("invalid ServiceNow tenant binding")
        if not hasattr(transport, "send"):
            raise ValueError("authenticated HTTP transport is required")
        if not 0.1 <= timeout_seconds <= 120:
            raise ValueError("invalid ServiceNow request timeout")
        if not 1 <= max_read_attempts <= 5:
            raise ValueError("invalid ServiceNow read retry limit")
        if not 1_024 <= max_request_bytes <= 1_048_576:
            raise ValueError("invalid ServiceNow request limit")
        if not 1_024 <= max_response_bytes <= 4_194_304:
            raise ValueError("invalid ServiceNow response limit")
        self._tenant_id = tenant_id
        self._transport = transport
        self._registry = registry or ScopedContractRegistry()
        self._timeout_seconds = timeout_seconds
        self._max_read_attempts = max_read_attempts
        self._max_request_bytes = max_request_bytes
        self._max_response_bytes = max_response_bytes
        self._sleeper = sleeper

    def capability_probe(
        self, context: RequestContext
    ) -> PortResult[Mapping[str, object]]:
        return self._call("capabilities.read", context, {})

    def reconcile_cis(
        self, context: RequestContext, request: Mapping[str, object]
    ) -> PortResult[Mapping[str, object]]:
        return self._call("cis.reconcile", context, request)

    def read_ci(
        self, context: RequestContext, ci_ref: str
    ) -> PortResult[Mapping[str, object]]:
        return self._call("cis.read", context, {"ci_ref": ci_ref})

    def list_crypto_assets(
        self,
        context: RequestContext,
        *,
        page_size: int,
        asset_type_filters: tuple[str, ...] = (),
        cursor_sha256: str | None = None,
    ) -> PortResult[Mapping[str, object]]:
        request: dict[str, object] = {
            "page_size": page_size,
            "asset_type_filters": list(asset_type_filters),
        }
        if cursor_sha256 is not None:
            request["cursor_sha256"] = cursor_sha256
        return self._call("crypto_assets.list", context, request)

    def reconcile_crypto_assets(
        self, context: RequestContext, request: Mapping[str, object]
    ) -> PortResult[Mapping[str, object]]:
        return self._call("crypto_assets.reconcile", context, request)

    def ensure_change(
        self, context: RequestContext, request: Mapping[str, object]
    ) -> PortResult[Mapping[str, object]]:
        return self._call("changes.ensure", context, request)

    def read_change(
        self, context: RequestContext, change_ref: str
    ) -> PortResult[Mapping[str, object]]:
        return self._call("changes.read", context, {"change_ref": change_ref})

    def transition_change_task(
        self,
        context: RequestContext,
        task_ref: str,
        request: Mapping[str, object],
    ) -> PortResult[Mapping[str, object]]:
        return self._call(
            "change_tasks.transition", context, {**request, "task_ref": task_ref}
        )

    def read_approval_snapshot(
        self, context: RequestContext, approval_ref: str
    ) -> PortResult[Mapping[str, object]]:
        return self._call("approvals.read", context, {"approval_ref": approval_ref})

    def append_verification(
        self, context: RequestContext, request: Mapping[str, object]
    ) -> PortResult[Mapping[str, object]]:
        return self._call("verifications.append", context, request)

    def close_change(
        self,
        context: RequestContext,
        change_ref: str,
        request: Mapping[str, object],
    ) -> PortResult[Mapping[str, object]]:
        return self._call(
            "changes.close", context, {**request, "change_ref": change_ref}
        )

    def read_events(
        self,
        context: RequestContext,
        *,
        limit: int,
        cursor_sha256: str | None = None,
    ) -> PortResult[Mapping[str, object]]:
        request: dict[str, object] = {"limit": limit}
        if cursor_sha256 is not None:
            request["cursor_sha256"] = cursor_sha256
        return self._call("events.read", context, request)

    def _call(
        self,
        operation_id: str,
        context: RequestContext,
        request_fields: Mapping[str, object],
    ) -> PortResult[Mapping[str, object]]:
        try:
            route = self._registry.route(operation_id)
            payload = self._prepare_payload(route, context, request_fields)
            body = (
                json.dumps(
                    payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
                ).encode("ascii")
                if route.mutation
                else b""
            )
            if len(body) > self._max_request_bytes:
                return self._failure(
                    operation_id,
                    "PQC_SERVICENOW_REQUEST_LIMIT_EXCEEDED",
                    RetryClass.INVALID_REQUEST,
                    provider_call_performed=False,
                )
            path = self._path(route, payload)
            headers = {
                "Accept": "application/json",
                "X-PBA-Correlation-Ref": context.correlation_ref,
                "X-PBA-Request-ID": context.request_id,
                "X-PBA-Tenant-ID": self._tenant_id,
                "Traceparent": context.traceparent,
            }
            if route.mutation:
                headers["Content-Type"] = "application/json"
                headers["X-PBA-Idempotency-Key-SHA256"] = str(
                    context.idempotency_key_sha256
                )
            prepared = HTTPRequest(
                operation_id=operation_id,
                method=route.method,
                url=f"{self._base_url}{path}",
                headers=headers,
                body=body,
                timeout_seconds=self._timeout_seconds,
                mutation=route.mutation,
            )
            return self._send(route, context, prepared)
        except (ContractConfigurationError, ValidationError, TypeError, ValueError):
            return self._failure(
                operation_id,
                "PQC_SERVICENOW_INVALID_REQUEST",
                RetryClass.INVALID_REQUEST,
                provider_call_performed=False,
            )

    def _prepare_payload(
        self,
        route: ScopedRoute,
        context: RequestContext,
        request_fields: Mapping[str, object],
    ) -> dict[str, object]:
        if context.tenant_id != self._tenant_id:
            raise ValueError("tenant binding mismatch")
        if (
            not isinstance(context.traceparent, str)
            or _TRACEPARENT.fullmatch(context.traceparent) is None
        ):
            raise ValueError("valid W3C traceparent is required")
        if not isinstance(request_fields, Mapping) or "header" in request_fields:
            raise ValueError("caller may not supply the contract header")
        if route.mutation:
            key = context.idempotency_key_sha256
            if not isinstance(key, str) or _SHA256.fullmatch(key) is None:
                raise ValueError("mutation idempotency binding is required")
        elif context.idempotency_key_sha256 is not None:
            raise ValueError("read calls cannot carry mutation idempotency")

        self._reject_unsafe_fields(request_fields, mutation=route.mutation)
        payload: dict[str, object] = dict(request_fields)
        payload["header"] = {
            "contract_version": "pba.pqc.servicenow-api.v1",
            "request_id": context.request_id,
            "tenant_id": self._tenant_id,
            "correlation_ref": context.correlation_ref,
            "requested_at": context.requested_at,
            "contains_raw_payload": False,
        }
        if route.mutation:
            idempotency_field = _MUTATION_IDEMPOTENCY_FIELDS.get(route.operation_id)
            if idempotency_field is None:
                raise ValueError("mutation has no admitted idempotency binding")
            if payload.get(idempotency_field) != context.idempotency_key_sha256:
                raise ValueError("request idempotency binding mismatch")
        route.request_validator.validate(payload)
        return payload

    def _send(
        self, route: ScopedRoute, context: RequestContext, request: HTTPRequest
    ) -> PortResult[Mapping[str, object]]:
        for attempt in range(self._max_read_attempts if not route.mutation else 1):
            try:
                response = self._transport.send(request)
            except ResponseBodyTooLarge:
                if route.mutation:
                    return self._ambiguous_write(route.operation_id)
                return self._failure(
                    route.operation_id,
                    "PQC_SERVICENOW_RESPONSE_LIMIT_EXCEEDED",
                    RetryClass.SCHEMA_DRIFT,
                )
            except (TransportTimeout, TransportUnavailable):
                if route.mutation:
                    return self._ambiguous_write(route.operation_id)
                if attempt + 1 < self._max_read_attempts:
                    self._sleeper(self._backoff_seconds(attempt))
                    continue
                return self._failure(
                    route.operation_id,
                    "PQC_SERVICENOW_TRANSIENT",
                    RetryClass.TRANSIENT,
                )

            if not 200 <= response.status_code < 300:
                failure = classify_http_failure(
                    response.status_code, self._header(response, "retry-after")
                )
                if route.mutation and failure.retry_class in {
                    RetryClass.RATE_LIMITED,
                    RetryClass.TRANSIENT,
                    RetryClass.CONFLICT,
                }:
                    return self._ambiguous_write(route.operation_id)
                if (
                    not route.mutation
                    and failure.retryable
                    and attempt + 1 < self._max_read_attempts
                ):
                    delay = failure.retry_after_seconds
                    self._sleeper(
                        float(
                            min(
                                delay
                                if delay is not None
                                else self._backoff_seconds(attempt),
                                60,
                            )
                        )
                    )
                    continue
                return self._failure(
                    route.operation_id, failure.code, failure.retry_class
                )

            return self._validated_success(route, context, response)
        return self._failure(
            route.operation_id,
            "PQC_SERVICENOW_TRANSIENT",
            RetryClass.TRANSIENT,
        )

    def _validated_success(
        self, route: ScopedRoute, context: RequestContext, response: HTTPResponse
    ) -> PortResult[Mapping[str, object]]:
        if len(response.body) > self._max_response_bytes:
            if route.mutation:
                return self._ambiguous_write(route.operation_id)
            return self._failure(
                route.operation_id,
                "PQC_SERVICENOW_RESPONSE_LIMIT_EXCEEDED",
                RetryClass.SCHEMA_DRIFT,
            )
        try:
            value = json.loads(response.body.decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("response must be an object")
            route.response_validator.validate(value)
            header = value["header"]
            if not isinstance(header, dict):
                raise ValueError("response header missing")
            if (
                header.get("tenant_id") != self._tenant_id
                or header.get("request_id") != context.request_id
                or header.get("correlation_ref") != context.correlation_ref
                or header.get("contains_raw_payload") is not False
            ):
                raise ValueError("response binding mismatch")
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError):
            if route.mutation:
                return self._ambiguous_write(route.operation_id)
            return self._failure(
                route.operation_id,
                "PQC_SERVICENOW_SCHEMA_DRIFT",
                RetryClass.SCHEMA_DRIFT,
            )

        if header["outcome"] == "partial":
            if route.mutation:
                return self._ambiguous_write(route.operation_id)
            return self._failure(
                route.operation_id,
                "PQC_SERVICENOW_PARTIAL_RESPONSE",
                RetryClass.SCHEMA_DRIFT,
                response=value,
            )

        if header["outcome"] != "ok":
            return self._failure(
                route.operation_id,
                "PQC_SERVICENOW_PROVIDER_REJECTED",
                RetryClass.INVALID_REQUEST,
                response=value,
            )

        if route.mutation and value.get("disposition") == "rejected":
            return self._failure(
                route.operation_id,
                "PQC_SERVICENOW_PROVIDER_REJECTED",
                RetryClass.INVALID_REQUEST,
                response=value,
            )

        if route.operation_id == "changes.close" and (
            value.get("guard_decision") != "allow" or value.get("state") != "closed"
        ):
            return self._failure(
                route.operation_id,
                "PQC_SERVICENOW_CLOSURE_GUARD_DENIED",
                RetryClass.INVALID_REQUEST,
                response=value,
            )

        return PortResult(
            ok=True,
            value=value,
            receipt=self._receipt(
                route.operation_id,
                value,
                retry_class=RetryClass.NONE,
                idempotency_status=self._idempotency_status(route, value),
            ),
        )

    def _path(self, route: ScopedRoute, payload: Mapping[str, object]) -> str:
        path = route.path_template
        substitutions = {
            "{ci_ref}": payload.get("ci_ref"),
            "{change_ref}": payload.get("change_ref"),
            "{approval_ref}": payload.get("approval_ref"),
            "{task_ref}": payload.get("task_ref"),
        }
        for marker, value in substitutions.items():
            if marker in path:
                if not isinstance(value, str):
                    raise ValueError("route reference is missing")
                path = path.replace(marker, quote(value, safe=""))
        if "{" in path or "}" in path or "?" in path:
            raise ValueError("route template was not resolved")
        if not path.startswith("/api/x_pba_pqc/v1/"):
            raise ValueError("route escaped the scoped-app allowlist")
        if route.query_parameters:
            query_items: list[tuple[str, str]] = []
            for field in route.query_parameters:
                value = payload.get(field)
                if value is None:
                    continue
                if isinstance(value, list):
                    query_items.extend((field, str(item)) for item in value)
                elif isinstance(value, (str, int)) and not isinstance(value, bool):
                    query_items.append((field, str(value)))
                else:
                    raise ValueError("declared query parameter has invalid type")
            if query_items:
                path = f"{path}?{urlencode(query_items, doseq=True, safe='')}"
        return path

    def _failure(
        self,
        operation_id: str,
        error_code: str,
        retry_class: RetryClass,
        *,
        response: Mapping[str, object] | None = None,
        provider_call_performed: bool = True,
    ) -> PortResult[Mapping[str, object]]:
        receipt_material: Mapping[str, object] = response or {
            "operation_id": operation_id,
            "error_code": error_code,
            "retry_class": retry_class.value,
        }
        return PortResult(
            ok=False,
            value=None,
            receipt=SafeProviderReceipt(
                provider_record_ref=None,
                provider_revision_token=None,
                idempotency_status=IdempotencyStatus.NOT_APPLICABLE,
                retry_class=retry_class,
                receipt_digest=self._digest(receipt_material),
                provider_call_performed=provider_call_performed,
            ),
            error_code=error_code,
        )

    def _ambiguous_write(self, operation_id: str) -> PortResult[Mapping[str, object]]:
        return PortResult(
            ok=False,
            value=None,
            receipt=SafeProviderReceipt(
                provider_record_ref=None,
                provider_revision_token=None,
                idempotency_status=IdempotencyStatus.UNKNOWN,
                retry_class=RetryClass.AMBIGUOUS_OUTCOME,
                receipt_digest=self._digest(
                    {
                        "operation_id": operation_id,
                        "outcome": "unknown",
                        "required_action": "readback_reconciliation",
                    }
                ),
                provider_call_performed=True,
            ),
            error_code="PQC_SERVICENOW_WRITE_RECONCILIATION_REQUIRED",
        )

    def _receipt(
        self,
        operation_id: str,
        response: Mapping[str, object],
        *,
        retry_class: RetryClass,
        idempotency_status: IdempotencyStatus,
    ) -> SafeProviderReceipt:
        provider_ref = self._first_string(
            response,
            (
                "provider_record_ref",
                "change_ref",
                "approval_ref",
                "seed_batch_ref",
            ),
        )
        revision = self._first_string(
            response,
            ("provider_revision_ref", "next_cursor_sha256"),
        )
        if operation_id == "cis.read" and isinstance(response.get("ci"), dict):
            ci = response["ci"]
            provider_ref = self._first_string(ci, ("ci_ref",))
            revision = self._first_string(ci, ("provider_revision_ref",))
        return SafeProviderReceipt(
            provider_record_ref=provider_ref,
            provider_revision_token=revision,
            idempotency_status=idempotency_status,
            retry_class=retry_class,
            receipt_digest=self._digest(response),
            provider_call_performed=True,
        )

    @staticmethod
    def _idempotency_status(
        route: ScopedRoute, response: Mapping[str, object]
    ) -> IdempotencyStatus:
        if not route.mutation:
            return IdempotencyStatus.NOT_APPLICABLE
        disposition = response.get("disposition")
        if isinstance(disposition, str):
            return _SAFE_IDEMPOTENCY_DISPOSITIONS.get(
                disposition, IdempotencyStatus.UNKNOWN
            )
        results = response.get("results")
        if isinstance(results, list):
            dispositions = {
                item.get("disposition") for item in results if isinstance(item, dict)
            }
            if "inserted" in dispositions:
                return IdempotencyStatus.CREATED
            if dispositions <= {"updated", "unchanged"}:
                return IdempotencyStatus.RECONCILED
        return IdempotencyStatus.UNKNOWN

    @staticmethod
    def _reject_unsafe_fields(value: object, *, mutation: bool) -> None:
        stack = [value]
        visited = 0
        while stack:
            current = stack.pop()
            visited += 1
            if visited > 10_000:
                raise ValueError("request exceeded structural limit")
            if isinstance(current, Mapping):
                for raw_key, child in current.items():
                    normalized_key = str(raw_key).strip().lower()
                    if normalized_key in _FORBIDDEN_QUERY_KEYS:
                        raise ValueError("encoded query or arbitrary table rejected")
                    if mutation and normalized_key in _FORBIDDEN_WRITE_TARGETS:
                        raise ValueError("restricted platform target rejected")
                    stack.append(child)
            elif isinstance(current, (list, tuple)):
                stack.extend(current)
            elif mutation and isinstance(current, str):
                if current.strip().lower() in _FORBIDDEN_WRITE_TARGETS:
                    raise ValueError("restricted platform target rejected")

    @staticmethod
    def _header(response: HTTPResponse, name: str) -> str | None:
        target = name.lower()
        for raw_name, value in response.headers.items():
            if raw_name.lower() == target:
                return value[:256]
        return None

    @staticmethod
    def _backoff_seconds(attempt: int) -> float:
        return float(min(2**attempt, 8))

    @staticmethod
    def _digest(value: Mapping[str, object]) -> str:
        canonical = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def _first_string(value: Mapping[str, object], keys: tuple[str, ...]) -> str | None:
        for key in keys:
            candidate = value.get(key)
            if isinstance(candidate, str):
                return candidate
        return None

    @staticmethod
    def _validate_base_url(value: str) -> str:
        if not isinstance(value, str) or len(value) > 512:
            raise ValueError("invalid ServiceNow base URL")
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError("ServiceNow base URL must be an HTTPS origin")
        return f"https://{parsed.netloc}"
