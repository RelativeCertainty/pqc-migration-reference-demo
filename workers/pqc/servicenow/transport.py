from __future__ import annotations

import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol


_SAFE_RESPONSE_HEADERS = frozenset({"content-type", "etag", "retry-after"})


@dataclass(frozen=True)
class HTTPRequest:
    """Credential-free request prepared by the scoped-app client."""

    operation_id: str
    method: str
    url: str
    headers: Mapping[str, str]
    body: bytes
    timeout_seconds: float
    mutation: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))


@dataclass(frozen=True)
class HTTPResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))


class TransportTimeout(TimeoutError):
    """The adapter cannot know whether a submitted request reached ServiceNow."""


class TransportUnavailable(ConnectionError):
    """The authenticated HTTP transport was unavailable."""


class ResponseBodyTooLarge(ValueError):
    """The provider returned more bytes than the admitted response limit."""


class RequestAuthorizer(Protocol):
    """Apply authentication directly to a native request at send time.

    Implementations should resolve a SecretRef through the approved secret
    provider for each request.  The PBA client never receives the credential.
    """

    def authorize(self, request: urllib.request.Request) -> None: ...


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Expose redirect responses without automatically replaying requests."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # An external write or OAuth token POST must never be replayed to a
        # redirect target. The caller must reconcile or fail authorization.
        return None


class AuthenticatedHTTPTransport(Protocol):
    """HTTP transport whose implementation owns TLS and authentication."""

    def send(self, request: HTTPRequest) -> HTTPResponse: ...


class UrllibAuthenticatedTransport:
    """Bounded real HTTP transport with injected opener and authorizer.

    The opener is required so the operator, rather than this adapter, owns the
    TLS/mTLS, proxy, and trust configuration.  The authorizer is called only
    immediately before I/O.  Neither object is inspected or serialized here.
    """

    def __init__(
        self,
        *,
        opener: urllib.request.OpenerDirector,
        authorizer: RequestAuthorizer,
        max_response_bytes: int = 1_048_576,
    ) -> None:
        if not hasattr(opener, "open") or not hasattr(authorizer, "authorize"):
            raise ValueError("authenticated HTTP transport dependencies are required")
        if not 1_024 <= max_response_bytes <= 4_194_304:
            raise ValueError("invalid HTTP response limit")
        self._opener = opener
        self._authorizer = authorizer
        self._max_response_bytes = max_response_bytes

    def send(self, request: HTTPRequest) -> HTTPResponse:
        native_request = urllib.request.Request(
            request.url,
            data=request.body,
            headers=dict(request.headers),
            method=request.method,
        )
        try:
            self._authorizer.authorize(native_request)
        except Exception:
            # Authorizer exceptions may contain credential/provider details.
            raise TransportUnavailable("request authorization unavailable") from None

        try:
            with self._opener.open(
                native_request, timeout=request.timeout_seconds
            ) as response:
                body = self._read_bounded(response)
                return HTTPResponse(
                    status_code=int(response.status),
                    headers=self._safe_headers(response.headers),
                    body=body,
                )
        except urllib.error.HTTPError as exc:
            try:
                body = self._read_bounded(exc)
            except Exception:
                raise ResponseBodyTooLarge("provider response exceeded limit") from None
            return HTTPResponse(
                status_code=int(exc.code),
                headers=self._safe_headers(exc.headers),
                body=body,
            )
        except (TimeoutError, socket.timeout):
            raise TransportTimeout("provider request timed out") from None
        except (urllib.error.URLError, OSError):
            raise TransportUnavailable("provider transport unavailable") from None

    def _read_bounded(self, response: object) -> bytes:
        read = getattr(response, "read", None)
        if read is None:
            raise ResponseBodyTooLarge("provider response was unreadable")
        body = read(self._max_response_bytes + 1)
        if not isinstance(body, bytes) or len(body) > self._max_response_bytes:
            raise ResponseBodyTooLarge("provider response exceeded limit")
        return body

    @staticmethod
    def _safe_headers(headers: object) -> dict[str, str]:
        items = getattr(headers, "items", None)
        if items is None:
            return {}
        safe: dict[str, str] = {}
        for raw_name, raw_value in items():
            name = str(raw_name).lower()
            if name in _SAFE_RESPONSE_HEADERS:
                safe[name] = str(raw_value)[:256]
        return safe
