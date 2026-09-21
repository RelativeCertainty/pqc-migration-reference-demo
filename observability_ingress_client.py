from __future__ import annotations

import contextlib
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping, Optional

from observability_metadata import MetadataIngressError, validate_metadata_ingress


INGEST_PATH = "/v1/observability/ingest"
_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "host.containers.internal", "pba-observability-ingest"}
_CIRCUIT_SECONDS = 5.0
_circuit_lock = threading.Lock()
_circuit_open_until = 0.0


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        return None


def _configured_endpoint(explicit: Optional[str] = None) -> str:
    raw_value = explicit if explicit is not None else os.getenv("PBA_OBSERVABILITY_INGEST_URL")
    raw = str(raw_value or "").strip()
    if not raw:
        return ""
    parsed = urllib.parse.urlparse(raw)
    hostname = str(parsed.hostname or "").lower()
    try:
        port = parsed.port
    except ValueError:
        raise ValueError("observability ingress URL must be the registered loopback/internal HTTP endpoint") from None
    if (
        parsed.scheme != "http"
        or hostname not in _ALLOWED_HOSTS
        or port is None
        or not 1 <= port <= 65535
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path.rstrip("/") != INGEST_PATH
        or parsed.query
        or parsed.fragment
        or "?" in raw
        or "#" in raw
    ):
        raise ValueError("observability ingress URL must be the registered loopback/internal HTTP endpoint")
    return raw.rstrip("/")


def _configured_token(explicit: Optional[str] = None) -> str:
    if explicit is not None:
        return str(explicit)
    return str(os.getenv("PBA_OBSERVABILITY_INGEST_TOKEN") or "")


def _valid_token(token: str) -> bool:
    return (
        bool(token)
        and token == token.strip()
        and len(token) <= 4096
        and all(0x20 <= ord(char) <= 0x7E for char in token)
    )


def _circuit_is_open() -> bool:
    with _circuit_lock:
        return time.monotonic() < _circuit_open_until


def _set_circuit(*, unavailable: bool) -> None:
    global _circuit_open_until
    with _circuit_lock:
        _circuit_open_until = time.monotonic() + _CIRCUIT_SECONDS if unavailable else 0.0


def emit_metadata_ingress(
    record: Mapping[str, Any],
    *,
    endpoint: Optional[str] = None,
    token: Optional[str] = None,
    timeout: float = 0.2,
) -> str:
    """Send one validated metadata-only ingress record without redirects/proxies.

    Returns one controlled status: disabled, accepted, rejected, or unavailable.
    It never returns response bodies, URLs, tokens, or exception text.
    """

    try:
        validated = validate_metadata_ingress(record)
        target = _configured_endpoint(endpoint)
    except (MetadataIngressError, ValueError):
        return "rejected"
    if not target:
        return "disabled"
    internal_token = _configured_token(token)
    if not internal_token:
        return "disabled"
    if not _valid_token(internal_token):
        return "rejected"
    if _circuit_is_open():
        return "unavailable"

    try:
        body = json.dumps(validated, sort_keys=True, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            target,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "pba-observability-metadata-producer/1",
                "X-PBA-Internal-Token": internal_token,
            },
            method="POST",
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        with opener.open(request, timeout=max(0.05, min(float(timeout), 1.0))) as response:
            response.read(4096)
            if int(response.status) in {200, 201, 202}:
                _set_circuit(unavailable=False)
                return "accepted"
            return "rejected"
    except urllib.error.HTTPError as exc:
        with contextlib.suppress(Exception):
            exc.read(4096)
        if 400 <= int(exc.code) < 500:
            return "rejected"
        _set_circuit(unavailable=True)
        return "unavailable"
    except Exception:
        _set_circuit(unavailable=True)
        return "unavailable"
