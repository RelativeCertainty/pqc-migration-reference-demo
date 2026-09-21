from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, Mapping, Protocol


class OAuthAuthorizerError(RuntimeError):
    """A deliberately metadata-free OAuth authorization failure."""


class SecretRefResolver(Protocol):
    """Resolve a tenant-bound SecretRef without exposing it to the caller."""

    def __call__(self, ref: Mapping[str, object], *, tenant_id: str) -> str: ...


@dataclass(frozen=True)
class _CachedBearer:
    value: str
    refresh_at: float


class ServiceNowOAuthClientCredentialsAuthorizer:
    """Apply a short-lived ServiceNow OAuth bearer token at send time.

    The client ID and client secret are resolved only while refreshing the
    in-memory token. They are never returned, serialized, logged, or attached to
    the scoped API request. The injected opener owns TLS trust and any proxy
    configuration. This authorizer is intentionally restricted to one HTTPS
    ServiceNow origin and the ``x_pba_pqc`` scoped API.
    """

    def __init__(
        self,
        *,
        base_url: str,
        tenant_id: str,
        client_id_ref: Mapping[str, object],
        client_secret_ref: Mapping[str, object],
        secret_resolver: SecretRefResolver,
        opener: urllib.request.OpenerDirector,
        timeout_seconds: float = 10.0,
        max_token_response_bytes: int = 32_768,
        refresh_skew_seconds: int = 60,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        parsed = urllib.parse.urlsplit(str(base_url))
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("ServiceNow OAuth base URL must be an HTTPS origin")
        if not isinstance(tenant_id, str) or not tenant_id:
            raise ValueError("ServiceNow OAuth tenant binding is required")
        if not callable(secret_resolver) or not hasattr(opener, "open"):
            raise ValueError("ServiceNow OAuth dependencies are required")
        if not 0.1 <= timeout_seconds <= 60:
            raise ValueError("invalid ServiceNow OAuth timeout")
        if not 1_024 <= max_token_response_bytes <= 131_072:
            raise ValueError("invalid ServiceNow OAuth response limit")
        if not 5 <= refresh_skew_seconds <= 300:
            raise ValueError("invalid ServiceNow OAuth refresh skew")
        self._origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        self._tenant_id = tenant_id
        self._client_id_ref = self._validate_secret_ref(client_id_ref)
        self._client_secret_ref = self._validate_secret_ref(client_secret_ref)
        self._secret_resolver = secret_resolver
        self._opener = opener
        self._timeout_seconds = timeout_seconds
        self._max_token_response_bytes = max_token_response_bytes
        self._refresh_skew_seconds = refresh_skew_seconds
        self._monotonic = monotonic
        self._cached: _CachedBearer | None = None
        self._lock = threading.Lock()

    def authorize(self, request: urllib.request.Request) -> None:
        self._validate_scoped_request(request)
        try:
            token = self._current_token()
            request.add_unredirected_header("Authorization", f"Bearer {token}")
        except OAuthAuthorizerError:
            raise
        except Exception:
            raise OAuthAuthorizerError(
                "ServiceNow OAuth authorization unavailable"
            ) from None

    def _current_token(self) -> str:
        now = self._monotonic()
        cached = self._cached
        if cached is not None and now < cached.refresh_at:
            return cached.value
        with self._lock:
            now = self._monotonic()
            cached = self._cached
            if cached is not None and now < cached.refresh_at:
                return cached.value
            refreshed = self._refresh(now)
            self._cached = refreshed
            return refreshed.value

    def _refresh(self, now: float) -> _CachedBearer:
        try:
            client_id = self._secret_resolver(
                self._client_id_ref, tenant_id=self._tenant_id
            )
            client_secret = self._secret_resolver(
                self._client_secret_ref, tenant_id=self._tenant_id
            )
            if not self._valid_secret_value(client_id) or not self._valid_secret_value(
                client_secret
            ):
                raise ValueError("invalid resolved credential")
            body = urllib.parse.urlencode(
                {
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                }
            ).encode("ascii")
            token_request = urllib.request.Request(
                f"{self._origin}/oauth_token.do",
                data=body,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                method="POST",
            )
            with self._opener.open(
                token_request, timeout=self._timeout_seconds
            ) as response:
                raw = response.read(self._max_token_response_bytes + 1)
            if not isinstance(raw, bytes) or len(raw) > self._max_token_response_bytes:
                raise ValueError("invalid OAuth response")
            value = json.loads(raw.decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("invalid OAuth response")
            access_token = value.get("access_token")
            token_type = value.get("token_type")
            expires_in = value.get("expires_in")
            if (
                not self._valid_bearer(access_token)
                or not isinstance(token_type, str)
                or token_type.casefold() != "bearer"
                or not isinstance(expires_in, int)
                or isinstance(expires_in, bool)
                or not 60 <= expires_in <= 86_400
            ):
                raise ValueError("invalid OAuth response")
            refresh_at = now + max(1, expires_in - self._refresh_skew_seconds)
            return _CachedBearer(value=access_token, refresh_at=refresh_at)
        except Exception:
            self._cached = None
            raise OAuthAuthorizerError(
                "ServiceNow OAuth authorization unavailable"
            ) from None

    def _validate_scoped_request(self, request: urllib.request.Request) -> None:
        parsed = urllib.parse.urlsplit(request.full_url)
        request_origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        if (
            request_origin != self._origin
            or not parsed.path.startswith("/api/x_pba_pqc/v1/")
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise OAuthAuthorizerError("ServiceNow OAuth authorization unavailable")

    @staticmethod
    def _validate_secret_ref(value: Mapping[str, object]) -> dict[str, object]:
        if not isinstance(value, Mapping):
            raise ValueError("ServiceNow OAuth SecretRef is required")
        ref = dict(value)
        if (
            set(ref) - {"name", "provider", "vaultPath", "vaultKey", "description"}
            or ref.get("provider") != "vault"
            or not isinstance(ref.get("name"), str)
            or not isinstance(ref.get("vaultPath"), str)
            or not isinstance(ref.get("vaultKey"), str)
        ):
            raise ValueError("ServiceNow OAuth SecretRef is invalid")
        return ref

    @staticmethod
    def _valid_secret_value(value: object) -> bool:
        return (
            isinstance(value, str)
            and 1 <= len(value) <= 8_192
            and all(0x20 <= ord(character) <= 0x7E for character in value)
        )

    @classmethod
    def _valid_bearer(cls, value: object) -> bool:
        return (
            cls._valid_secret_value(value)
            and isinstance(value, str)
            and 20 <= len(value) <= 8_192
            and not any(character.isspace() for character in value)
        )
