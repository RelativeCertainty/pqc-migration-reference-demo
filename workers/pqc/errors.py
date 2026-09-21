from __future__ import annotations

from dataclasses import dataclass

from .models import RetryClass


SAFE_ERROR_MESSAGES = {
    "PQC_ADAPTER_INVALID_INPUT": "provider input failed validation",
    "PQC_ADAPTER_UNSUPPORTED_DIALECT": "provider dialect is not supported",
    "PQC_ADAPTER_SCHEMA_DRIFT": "provider response no longer matches the admitted contract",
    "PQC_ADAPTER_LIMIT_EXCEEDED": "provider input exceeded an admitted safety limit",
    "PQC_ADAPTER_RATE_LIMITED": "provider requested a bounded retry",
    "PQC_ADAPTER_TRANSIENT": "provider reported a temporary failure",
    "PQC_ADAPTER_AUTHENTICATION": "provider authentication failed",
    "PQC_ADAPTER_AUTHORIZATION": "provider authorization failed",
    "PQC_ADAPTER_CONFLICT": "provider reported a version or state conflict",
    "PQC_ADAPTER_CONTRACT_NOT_ADMITTED": "provider contract is not admitted for canonical processing",
    "PQC_CONTRACT_PACK_INVALID": "contract pack failed validation",
}


class PQCAdapterError(ValueError):
    def __init__(
        self,
        code: str,
        retry_class: RetryClass,
        *,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(
            SAFE_ERROR_MESSAGES.get(code, "provider adapter failed safely")
        )
        self.code = code
        self.retry_class = retry_class
        self.retry_after_seconds = retry_after_seconds

    @property
    def retryable(self) -> bool:
        return self.retry_class in {RetryClass.RATE_LIMITED, RetryClass.TRANSIENT}

    def to_worker_error(self) -> dict[str, object]:
        details: dict[str, object] = {"retry_class": self.retry_class.value}
        if self.retry_after_seconds is not None:
            details["retry_after_seconds"] = self.retry_after_seconds
        return {
            "code": self.code,
            "message": str(self),
            "details": details,
        }


@dataclass(frozen=True)
class HTTPFailure:
    code: str
    retry_class: RetryClass
    retry_after_seconds: int | None = None

    @property
    def retryable(self) -> bool:
        return self.retry_class in {RetryClass.RATE_LIMITED, RetryClass.TRANSIENT}


def classify_http_failure(
    status_code: int, retry_after: str | None = None
) -> HTTPFailure:
    bounded_retry_after: int | None = None
    if retry_after and retry_after.isascii() and retry_after.isdigit():
        candidate = int(retry_after)
        if 0 <= candidate <= 3_600:
            bounded_retry_after = candidate
    if status_code == 429:
        return HTTPFailure(
            "PQC_ADAPTER_RATE_LIMITED",
            RetryClass.RATE_LIMITED,
            bounded_retry_after,
        )
    if status_code in {408, 425, 500, 502, 503, 504}:
        return HTTPFailure("PQC_ADAPTER_TRANSIENT", RetryClass.TRANSIENT)
    if status_code == 401:
        return HTTPFailure("PQC_ADAPTER_AUTHENTICATION", RetryClass.AUTHENTICATION)
    if status_code == 403:
        return HTTPFailure("PQC_ADAPTER_AUTHORIZATION", RetryClass.AUTHORIZATION)
    if status_code in {409, 412}:
        return HTTPFailure("PQC_ADAPTER_CONFLICT", RetryClass.CONFLICT)
    return HTTPFailure("PQC_ADAPTER_INVALID_INPUT", RetryClass.INVALID_REQUEST)
