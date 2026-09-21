from __future__ import annotations

import concurrent.futures
import hashlib
import inspect
import json
import os
import sys
import time
import uuid
from contextlib import nullcontext, suppress
from contextvars import ContextVar, copy_context
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple
from urllib.parse import urlparse

from worker_runtime.grants import Grant, get_current_grant, set_current_grant

from observability_ingress_client import emit_metadata_ingress
from observability_metadata import MetadataIngressError, make_metadata_ingress, trace_from_traceparent

try:  # Optional dependency; defaults to noop tracer when missing.
    from opentelemetry import trace
    from opentelemetry.propagate import get_global_textmap, set_global_textmap  # type: ignore
    from opentelemetry.sdk.resources import Resource  # type: ignore
    from opentelemetry.sdk.trace import TracerProvider  # type: ignore
    from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore
    from opentelemetry.trace import (  # type: ignore
        NonRecordingSpan,
        SpanContext,
        Status,
        StatusCode,
        TraceFlags,
        TraceState,
        set_span_in_context,
    )
except Exception:  # pragma: no cover
    trace = None
    set_span_in_context = None  # type: ignore
    TracerProvider = None  # type: ignore
    BatchSpanProcessor = None  # type: ignore
    Status = None  # type: ignore
    StatusCode = None  # type: ignore
    TraceFlags = None  # type: ignore
    TraceState = None  # type: ignore
    NonRecordingSpan = None  # type: ignore
    SpanContext = None  # type: ignore
    def get_global_textmap() -> None:  # type: ignore
        return None

    def set_global_textmap(_propagator: Any) -> None:  # type: ignore
        return None

if trace is not None:
    try:
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator  # type: ignore
    except Exception:  # pragma: no cover
        try:
            from opentelemetry.propagators.tracecontext import TraceContextTextMapPropagator  # type: ignore
        except Exception:  # pragma: no cover
            TraceContextTextMapPropagator = None  # type: ignore
else:
    TraceContextTextMapPropagator = None  # type: ignore

try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as OTLPGrpcExporter  # type: ignore
except Exception:  # pragma: no cover
    OTLPGrpcExporter = None  # type: ignore

try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as OTLPHttpExporter  # type: ignore
except Exception:  # pragma: no cover
    OTLPHttpExporter = None  # type: ignore

try:
    from opentelemetry.sdk.trace.export import OTLPSpanExporter as OTLPLegacyExporter  # type: ignore
except Exception:  # pragma: no cover
    OTLPLegacyExporter = None  # type: ignore

DEFAULT_TIMEOUT_SECONDS = float(os.getenv("PBA_WORKER_TIMEOUT_SECONDS", "15"))
SAFE_VALIDATION_CODE = "VALIDATION_ERROR"
SAFE_EXCEPTION_CODE = "WORKER_EXCEPTION"
SAFE_TIMEOUT_CODE = "TIMEOUT"
SAFE_DENIED_CODE = "WORKER_DENIED"
BREAK_GLASS_WARNING_CODE = "BREAK_GLASS_USED"
UNKNOWN_FIELD = "unknown"
DEFAULT_GOVERNANCE_DIR = "/tmp/pba-governance"
REGISTERED_MODEL_ACTIVITY_WORKERS = {
    "llm_prompt_wasmedge",
    "intake_draft_compose",
    "communication_response_compose",
    "job_finder_semantic_local",
    "job_finder_semantic_codex",
    "job_finder_resume_draft_local",
}
REGISTERED_MODEL_TRANSPORT_MODES = {
    "prompt_file",
    "stdin",
    "argv",
    "coordination_lock",
    "codex_cli_ephemeral",
    "unknown",
}

MODEL_ACTIVITY_PROFILES = {
    "llamaedge.wasmedge": {
        "model_asset_ref": "model.wasmedge.local_llm_runtime",
        "vendor_ref": "vendor.wasmedge",
        "component": "wasmedge",
        "capability_ref": "capability.llm.local.complete",
        "transport_mode": "unknown",
        "safe_transport": False,
    },
    "openai.codex_cli": {
        "model_asset_ref": "model.openai.gpt_5_6_sol_codex_agent",
        "vendor_ref": "vendor.openai",
        "component": "codex_agent",
        "capability_ref": "capability.llm.codex.agent.propose",
        "transport_mode": "codex_cli_ephemeral",
        "safe_transport": True,
    },
}
JOB_FINDER_MODEL_ACTIVITY_PROVIDERS = {
    "job_finder_semantic_local": "llamaedge.wasmedge",
    "job_finder_semantic_codex": "openai.codex_cli",
    "job_finder_resume_draft_local": "llamaedge.wasmedge",
}


def is_dev_env() -> bool:
    return os.getenv("PBA_ENV", "").lower() in {"dev", "local"}


def _is_break_glass_allowed(invocation: Dict[str, Any], *, dev_env: bool) -> bool:
    if not dev_env:
        return False
    if os.getenv("PBA_BREAK_GLASS", "0") != "1":
        return False
    configured_token = os.getenv("PBA_BREAK_GLASS_TOKEN", "")
    if not configured_token:
        return False
    invocation_token = invocation.get("break_glass_token")
    if not isinstance(invocation_token, str) or not invocation_token:
        return False
    return invocation_token == configured_token


def _synthesize_break_glass_grant(worker_name: str, trace_id: str) -> Grant:
    # Example (dev-only): PBA_ENV=dev PBA_BREAK_GLASS=1 PBA_BREAK_GLASS_TOKEN=token python -m workers.<module>
    return Grant(
        capabilities={"break_glass.allow"},
        limits={"cpu_ms": 30000, "mem_mb": 256, "wall_ms": 60000},
        io={"network": [], "fs": {"ro": [], "rw": []}},
        llm={"mode": "none", "model": "none", "max_tokens": 0},
        audit={
            "decision_id": f"break-glass:{worker_name}:{trace_id}",
            "policy_revision": "break_glass.dev",
        },
    )

_traceparent_ctx: ContextVar[Optional[str]] = ContextVar("traceparent", default=None)
_trace_ctx: ContextVar[Dict[str, Any]] = ContextVar("trace_ctx", default={})
_governance_target_ctx: ContextVar[Tuple[str, str]] = ContextVar(
    "governance_target", default=("", "")
)
_tracer_initialized: ContextVar[bool] = ContextVar("tracer_initialized", default=False)
_TRACER_EXPORTER_KEY: Optional[str] = None


def _redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _redact(v) for k, v in obj.items() if not _is_sensitive_key(k)}
    if isinstance(obj, list):
        return [_redact(v) for v in obj]
    return obj


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in ["secret", "token", "password", "key"])


def _safe_string(value: Any) -> str:
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            return cleaned
    if value is None:
        return UNKNOWN_FIELD
    text = str(value).strip()
    return text if text else UNKNOWN_FIELD


def _sanitize_segment(value: Any, fallback: str) -> str:
    raw = _safe_string(value)
    if raw == UNKNOWN_FIELD:
        return fallback
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in raw).strip("_")
    return cleaned if cleaned else fallback


def _meta_block(invocation: Dict[str, Any]) -> Dict[str, Any]:
    meta = invocation.get("metadata")
    if isinstance(meta, dict):
        return meta
    fallback = invocation.get("meta")
    if isinstance(fallback, dict):
        return fallback
    return {}


def _resolve_evidence_path(invocation: Dict[str, Any]) -> str:
    meta = _meta_block(invocation)
    direct = meta.get("evidence_path")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    evidence_root = meta.get("evidence_root")
    if isinstance(evidence_root, str) and evidence_root.strip():
        tenant = _sanitize_segment(invocation.get("tenant"), "unknown-tenant")
        run_id = _sanitize_segment(invocation.get("pipeline_run_id"), "unknown-run")
        invocation_id = _sanitize_segment(invocation.get("id"), "unknown-invocation")
        return os.path.join(evidence_root.strip(), tenant, run_id, invocation_id)
    evidence_obj = meta.get("evidence") if isinstance(meta.get("evidence"), dict) else {}
    nested = evidence_obj.get("path") if isinstance(evidence_obj, dict) else None
    if isinstance(nested, str) and nested.strip():
        return nested.strip()
    return UNKNOWN_FIELD


def _grant_decision_fields(grant: Optional[Grant]) -> Tuple[str, str]:
    if grant is None or not isinstance(grant.audit, dict):
        return UNKNOWN_FIELD, UNKNOWN_FIELD
    decision_id = _safe_string(grant.audit.get("decision_id"))
    revision = _safe_string(grant.audit.get("policy_revision") or grant.audit.get("revision"))
    return decision_id, revision


def _primary_classification_value(value: Any) -> str:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or UNKNOWN_FIELD
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                return item.strip()
    return UNKNOWN_FIELD


def _classification_payload(invocation: Dict[str, Any]) -> Dict[str, Any]:
    classification = invocation.get("classification") if isinstance(invocation.get("classification"), dict) else {}
    return {
        "classification_data_class": _safe_string(classification.get("data_class")),
        "classification_data_sensitivity": _primary_classification_value(classification.get("data_sensitivity")),
        "classification_regulatory_scope": _primary_classification_value(classification.get("regulatory_scope")),
    }


def _emit_run_log(
    *,
    event: str,
    invocation: Dict[str, Any],
    grant: Optional[Grant],
    success: Optional[bool] = None,
    error_code: Optional[str] = None,
    span: Any = None,
) -> None:
    decision_id, revision = _grant_decision_fields(grant)
    payload: Dict[str, Any] = {
        "event": event,
        "lane": "python",
        "worker": _safe_string(invocation.get("worker")),
        "worker_version": _safe_string(invocation.get("worker_version")),
        "run_id": _safe_string(invocation.get("pipeline_run_id")),
        "invocation_id": _safe_string(invocation.get("id")),
        "decision_id": decision_id,
        "policy_revision": revision,
        "tenant": _safe_string(invocation.get("tenant")),
        "domain": _safe_string(invocation.get("domain")),
        "environment": _safe_string(invocation.get("environment") or os.getenv("PBA_ENV")),
        "trace_id": _trace_id_from_invocation(invocation, {}),
    }
    payload.update(_classification_payload(invocation))
    if success is not None:
        payload["success"] = bool(success)
    if error_code is not None:
        payload["error_code"] = _safe_string(error_code)
    print(json.dumps(payload, sort_keys=True), file=sys.stderr, flush=True)
    _emit_worker_metadata_ingress(
        event=event,
        invocation=invocation,
        grant=grant,
        success=success,
        error_code=error_code,
        span=span,
    )


def _trusted_classification(invocation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    classification = invocation.get("classification")
    if not isinstance(classification, dict):
        return None
    required = ("data_class", "data_sensitivity", "regulatory_scope")
    if any(name not in classification for name in required) or "notes" in classification:
        return None
    return {name: classification[name] for name in required}


def _safe_ingress_identifier(value: Any, fallback: str, max_len: int = 120) -> str:
    if not isinstance(value, str):
        return fallback
    raw = value.strip()
    if not raw or not raw.isascii() or len(raw) > max_len or not raw[0].isalnum():
        return fallback
    if any(not (ch.isalnum() or ch in "._:/-") for ch in raw):
        return fallback
    return raw


def _bounded_ingress_counter(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if 0 <= value <= 1_000_000_000:
        return value
    return None


def _invocation_traceparent(invocation: Dict[str, Any]) -> Optional[str]:
    meta = _meta_block(invocation)
    meta_trace = meta.get("trace") if isinstance(meta.get("trace"), dict) else {}
    invocation_trace = invocation.get("trace") if isinstance(invocation.get("trace"), dict) else {}
    for candidate in (
        meta_trace.get("traceparent"),
        invocation_trace.get("traceparent"),
        get_traceparent(),
    ):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _emit_ingress_record(record: Dict[str, Any]) -> None:
    if os.getenv("PBA_OBSERVABILITY_METADATA_STDERR", "1") == "1":
        print(json.dumps(record, sort_keys=True, separators=(",", ":")), file=sys.stderr, flush=True)
    try:
        emit_metadata_ingress(record)
    except Exception:
        # Observability is never allowed to break the Worker result path. The
        # strict record has already been validated before this boundary.
        return


def _emit_worker_metadata_ingress(
    *,
    event: str,
    invocation: Dict[str, Any],
    grant: Optional[Grant],
    success: Optional[bool],
    error_code: Optional[str],
    span: Any = None,
) -> None:
    classification = _trusted_classification(invocation)
    if classification is None:
        return
    tenant = _safe_ingress_identifier(invocation.get("tenant"), "", 80)
    environment = _safe_ingress_identifier(invocation.get("environment") or os.getenv("PBA_ENV"), "", 48)
    domain = _safe_ingress_identifier(invocation.get("domain"), "", 80)
    worker = _safe_ingress_identifier(invocation.get("worker"), "", 120)
    worker_run_id = _safe_ingress_identifier(invocation.get("id"), "", 160)
    pipeline_run_id = _safe_ingress_identifier(invocation.get("pipeline_run_id"), "", 160)
    if not all((tenant, environment, domain, worker, worker_run_id, pipeline_run_id)):
        return

    phase = "started" if event.endswith(".start") else ("completed" if success is not False else "failed")
    verb = "START" if phase == "started" else ("COMPLETE" if phase == "completed" else "ERROR")
    severity = "error" if phase == "failed" else "info"
    upstream_event_id = f"worker.{worker_run_id}.{phase}"
    lifecycle_identity = f"{tenant}:{pipeline_run_id}:{worker_run_id}"
    parent_trace = trace_from_traceparent(_invocation_traceparent(invocation), identity=lifecycle_identity)
    with suppress(Exception):
        span_context = span.get_span_context() if span is not None else None
        if span_context and span_context.is_valid:
            parent_trace = {
                "trace_id": f"{int(span_context.trace_id):032x}",
                "span_id": f"{int(span_context.span_id):016x}",
                "synthetic": False,
            }
    span_digest = hashlib.sha256(
        f"{parent_trace['trace_id']}:{upstream_event_id}".encode("utf-8")
    ).hexdigest()
    trace_data = {
        "trace_id": parent_trace["trace_id"],
        "span_id": span_digest[:16],
        "parent_span_id": parent_trace["span_id"],
        "synthetic": True,
    }
    decision_id, _revision = _grant_decision_fields(grant)
    scope: Dict[str, Any] = {
        "tenant": tenant,
        "environment": environment,
        "domain": domain,
        "service": "pba.worker",
        "component": "python_sdk",
        "worker": worker,
        "pipeline_run_id": pipeline_run_id,
        "worker_run_id": worker_run_id,
    }
    pipeline = _safe_ingress_identifier(invocation.get("pipeline"), "", 120)
    step = _safe_ingress_identifier(invocation.get("step"), "", 120)
    if pipeline:
        scope["pipeline"] = pipeline
    if step:
        scope["step"] = step
    if decision_id != UNKNOWN_FIELD:
        scope["policy_decision_id"] = _safe_ingress_identifier(decision_id, "", 160)

    activity: Dict[str, Any] = {
        "event_type": "observe",
        "event_subtype": f"runtime.worker.{phase}",
        "kind": f"runtime.worker.{phase}",
        "verb": verb,
        "status": phase,
        "severity": severity,
    }
    if error_code:
        activity["error_code"] = _safe_ingress_identifier(error_code, "unknown", 120)
    try:
        record = make_metadata_ingress(
            source_kind="stdout_structured",
            source_ref="source.worker.python",
            upstream_event_id=upstream_event_id,
            observed_at=datetime.now(tz=timezone.utc).isoformat(),
            trace=trace_data,
            scope=scope,
            classification=classification,
            activity=activity,
            refs={"policy_refs": ["policy.pba.worker.execution"]},
        )
    except MetadataIngressError:
        return
    _emit_ingress_record(record)


def _emit_otel_span_metadata_ingress(
    *,
    invocation: Dict[str, Any],
    span: Any,
    success: bool,
    error_code: Optional[str],
    duration_ms: int,
) -> None:
    classification = _trusted_classification(invocation)
    if classification is None or span is None:
        return
    try:
        span_context = span.get_span_context()
        if not span_context or not span_context.is_valid:
            return
        trace_id = f"{int(span_context.trace_id):032x}"
        span_id = f"{int(span_context.span_id):016x}"
    except Exception:
        return

    tenant = _safe_ingress_identifier(invocation.get("tenant"), "", 80)
    environment = _safe_ingress_identifier(invocation.get("environment") or os.getenv("PBA_ENV"), "", 48)
    domain = _safe_ingress_identifier(invocation.get("domain"), "", 80)
    worker = _safe_ingress_identifier(invocation.get("worker"), "", 120)
    worker_run_id = _safe_ingress_identifier(invocation.get("id"), "", 160)
    pipeline_run_id = _safe_ingress_identifier(invocation.get("pipeline_run_id"), "", 160)
    if not all((tenant, environment, domain, worker, worker_run_id, pipeline_run_id)):
        return

    trace_data: Dict[str, Any] = {"trace_id": trace_id, "span_id": span_id, "synthetic": False}
    # Prefer the SDK span's actual parent. Fall back to an incoming
    # traceparent only when it belongs to the same trace; a synthesized or
    # cross-trace identifier must never be projected as an OTEL parent.
    parent_context = getattr(span, "parent", None)
    with suppress(Exception):
        if (
            parent_context
            and parent_context.is_valid
            and f"{int(parent_context.trace_id):032x}" == trace_id
            and f"{int(parent_context.span_id):016x}" != span_id
        ):
            trace_data["parent_span_id"] = f"{int(parent_context.span_id):016x}"
    if "parent_span_id" not in trace_data:
        parent = trace_from_traceparent(_invocation_traceparent(invocation), identity=worker_run_id)
        if not parent["synthetic"] and parent["trace_id"] == trace_id and parent["span_id"] != span_id:
            trace_data["parent_span_id"] = parent["span_id"]
    scope: Dict[str, Any] = {
        "tenant": tenant,
        "environment": environment,
        "domain": domain,
        "service": "pba.worker",
        "component": "python_otel",
        "worker": worker,
        "pipeline_run_id": pipeline_run_id,
        "worker_run_id": worker_run_id,
    }
    pipeline = _safe_ingress_identifier(invocation.get("pipeline"), "", 120)
    step = _safe_ingress_identifier(invocation.get("step"), "", 120)
    if pipeline:
        scope["pipeline"] = pipeline
    if step:
        scope["step"] = step
    activity: Dict[str, Any] = {
        "event_type": "observe",
        "event_subtype": "telemetry.span.completed",
        "kind": "telemetry.span.completed",
        "verb": "OBSERVE",
        "status": "completed" if success else "failed",
        "severity": "info" if success else "error",
        "duration_ms": max(0, min(int(duration_ms), 86400000)),
    }
    if error_code:
        activity["error_code"] = _safe_ingress_identifier(error_code, "unknown", 120)
    upstream_event_id = f"otel.{trace_id}.{span_id}"
    try:
        record = make_metadata_ingress(
            source_kind="otel_span",
            source_ref="source.runtime.python_otel",
            upstream_event_id=upstream_event_id,
            observed_at=datetime.now(tz=timezone.utc).isoformat(),
            trace=trace_data,
            scope=scope,
            classification=classification,
            activity=activity,
            refs={"policy_refs": ["policy.pba.observability.otel_projection"]},
        )
    except MetadataIngressError:
        return
    _emit_ingress_record(record)


def _emit_registered_model_activity(
    *,
    invocation: Dict[str, Any],
    output: Dict[str, Any],
    span: Any,
    success: bool,
    error_code: Optional[str],
    duration_ms: int,
) -> None:
    worker = _safe_ingress_identifier(invocation.get("worker"), "", 120)
    if worker not in REGISTERED_MODEL_ACTIVITY_WORKERS:
        return
    provider = "llamaedge.wasmedge"
    if worker in JOB_FINDER_MODEL_ACTIVITY_PROVIDERS:
        raw_provider = output.get("provider")
        provider = JOB_FINDER_MODEL_ACTIVITY_PROVIDERS[worker]
        if raw_provider != provider:
            return
    profile = MODEL_ACTIVITY_PROFILES[provider]
    classification = _trusted_classification(invocation)
    if classification is None:
        return
    tenant = _safe_ingress_identifier(invocation.get("tenant"), "", 80)
    environment = _safe_ingress_identifier(invocation.get("environment") or os.getenv("PBA_ENV"), "", 48)
    domain = _safe_ingress_identifier(invocation.get("domain"), "", 80)
    worker_run_id = _safe_ingress_identifier(invocation.get("id"), "", 160)
    pipeline_run_id = _safe_ingress_identifier(invocation.get("pipeline_run_id"), "", 160)
    if not all((tenant, environment, domain, worker_run_id, pipeline_run_id)):
        return

    parent = trace_from_traceparent(_invocation_traceparent(invocation), identity=worker_run_id)
    trace_data: Dict[str, Any] = {
        "trace_id": parent["trace_id"],
        "span_id": hashlib.sha256(f"model:{worker_run_id}".encode("utf-8")).hexdigest()[:16],
        "parent_span_id": parent["span_id"],
        "synthetic": True,
    }
    if span is not None:
        with suppress(Exception):
            span_context = span.get_span_context()
            if span_context and span_context.is_valid:
                trace_data["trace_id"] = f"{int(span_context.trace_id):032x}"
                trace_data["parent_span_id"] = f"{int(span_context.span_id):016x}"

    phase = "completed" if success else "failed"
    activity: Dict[str, Any] = {
        "event_type": "execute" if success else "audit",
        "event_subtype": f"model.inference.{phase}",
        "kind": f"model.inference.{phase}",
        "verb": "COMPLETE" if success else "ERROR",
        "status": phase,
        "severity": "info" if success else "error",
        "duration_ms": max(0, min(int(duration_ms), 86400000)),
    }
    if error_code:
        activity["error_code"] = _safe_ingress_identifier(error_code, "unknown", 120)
    inv_input = invocation.get("input") if isinstance(invocation.get("input"), dict) else {}
    max_tokens = inv_input.get("max_tokens")
    counters: Dict[str, int] = {}
    for counter_name in ("input_tokens", "output_tokens", "total_tokens"):
        counter_value = _bounded_ingress_counter(output.get(counter_name))
        if counter_value is not None:
            counters[counter_name] = counter_value
    if counters:
        activity["counters"] = counters

    transport_value = output.get("transport_mode")
    transport_mode = (
        transport_value.strip().lower()
        if isinstance(transport_value, str)
        else str(profile["transport_mode"])
    )
    if transport_mode not in REGISTERED_MODEL_TRANSPORT_MODES:
        transport_mode = "unknown"
    gpu_backend_value = output.get("gpu_backend")
    gpu_backend = gpu_backend_value.strip().lower() if isinstance(gpu_backend_value, str) else "unknown"
    if gpu_backend not in {"none", "cpu", "cuda", "rocm", "metal", "wasi_nn", "unknown"}:
        gpu_backend = "unknown"
    model: Dict[str, Any] = {
        "model_asset_ref": profile["model_asset_ref"],
        "vendor_ref": profile["vendor_ref"],
        "transport_mode": transport_mode,
        "safe_transport": (
            output.get("safe_transport") is True
            if "safe_transport" in output
            else bool(profile["safe_transport"])
        ),
        "gpu_backend": gpu_backend,
        "gpu_verified": output.get("gpu_verified") is True,
    }
    bounded_max_tokens = _bounded_ingress_counter(max_tokens)
    if bounded_max_tokens is not None and bounded_max_tokens > 0:
        model["max_tokens"] = bounded_max_tokens
    scope: Dict[str, Any] = {
        "tenant": tenant,
        "environment": environment,
        "domain": domain,
        "service": "pba.model_runtime",
        "component": profile["component"],
        "worker": worker,
        "pipeline_run_id": pipeline_run_id,
        "worker_run_id": worker_run_id,
        "model_invocation_id": worker_run_id,
    }
    upstream_event_id = f"model.{worker_run_id}.{phase}"
    try:
        record = make_metadata_ingress(
            source_kind="model_runtime",
            source_ref="source.model.governed_runtime",
            upstream_event_id=upstream_event_id,
            observed_at=datetime.now(tz=timezone.utc).isoformat(),
            trace=trace_data,
            scope=scope,
            classification=classification,
            activity=activity,
            model=model,
            refs={
                "policy_refs": ["policy.pba.model_runtime.metadata_projection"],
                "capability_refs": [profile["capability_ref"]],
            },
        )
    except MetadataIngressError:
        return
    _emit_ingress_record(record)


def _resolve_governance_target(invocation: Dict[str, Any]) -> Tuple[str, str, str]:
    evidence_path = _resolve_evidence_path(invocation)
    if evidence_path == UNKNOWN_FIELD:
        base_dir = os.getenv("PBA_GOVERNANCE_DIR", DEFAULT_GOVERNANCE_DIR).strip() or DEFAULT_GOVERNANCE_DIR
        tenant = _sanitize_segment(invocation.get("tenant"), "unknown-tenant")
        run_id = _sanitize_segment(invocation.get("pipeline_run_id"), "unknown-run")
        invocation_id = _sanitize_segment(invocation.get("id"), "unknown-invocation")
        evidence_path = os.path.join(base_dir, tenant, run_id, invocation_id)
    hashes_path = os.path.join(evidence_path, "hashes.json")
    governance_path = os.path.join(evidence_path, "governance.json")
    return governance_path, evidence_path, hashes_path


def _safe_sha256_file(path: str) -> str:
    try:
        hasher = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                hasher.update(chunk)
    except Exception:
        return UNKNOWN_FIELD
    return f"sha256:{hasher.hexdigest()}"


def _trace_id_from_invocation(invocation: Dict[str, Any], trace_info: Dict[str, Any]) -> str:
    trace_id = trace_info.get("trace_id") if isinstance(trace_info, dict) else None
    if isinstance(trace_id, str) and trace_id.strip():
        return trace_id.strip()
    trace_obj = invocation.get("trace") if isinstance(invocation.get("trace"), dict) else {}
    fallback = trace_obj.get("trace_id") if isinstance(trace_obj, dict) else None
    if isinstance(fallback, str) and fallback.strip():
        return fallback.strip()
    return UNKNOWN_FIELD


def _grant_profile(invocation: Dict[str, Any]) -> str:
    raw_grant = invocation.get("grant")
    if isinstance(raw_grant, dict):
        profile = raw_grant.get("profile")
        if isinstance(profile, str) and profile.strip():
            return profile.strip()
    return UNKNOWN_FIELD


def _grant_limit_value(grant: Optional[Grant], invocation: Dict[str, Any], field: str) -> Any:
    if grant is not None and isinstance(grant.limits, dict):
        value = grant.limits.get(field)
        if isinstance(value, (int, float)) and value >= 0:
            return int(value)
    raw_grant = invocation.get("grant")
    if isinstance(raw_grant, dict):
        limits = raw_grant.get("limits")
        if isinstance(limits, dict):
            value = limits.get(field)
            if isinstance(value, (int, float)) and value >= 0:
                return int(value)
    return UNKNOWN_FIELD


def _governance_error_code(result: Dict[str, Any]) -> str:
    if bool(result.get("success")):
        return "none"
    err_obj = result.get("error")
    if isinstance(err_obj, dict):
        code = err_obj.get("code")
        if isinstance(code, str) and code.strip():
            return code.strip()
    return UNKNOWN_FIELD


def _build_governance_record(
    invocation: Dict[str, Any],
    grant: Optional[Grant],
    result: Dict[str, Any],
    trace_info: Dict[str, Any],
    evidence_path: str,
    hashes_path: str,
) -> Dict[str, Any]:
    decision_id, revision = _grant_decision_fields(grant)
    record = {
        "tenant": _safe_string(invocation.get("tenant")),
        "domain": _safe_string(invocation.get("domain")),
        "environment": _safe_string(invocation.get("environment") or os.getenv("PBA_ENV")),
        "pipeline_run_id": _safe_string(invocation.get("pipeline_run_id")),
        "invocation_id": _safe_string(invocation.get("id")),
        "worker": {
            "name": _safe_string(invocation.get("worker")),
            "version": _safe_string(invocation.get("worker_version")),
        },
        "success": bool(result.get("success")),
        "error_code": _governance_error_code(result),
        "policy": {
            "decision_id": decision_id,
            "revision": revision,
        },
        "grant": {
            "profile": _grant_profile(invocation),
            "limits": {
                "wall_ms": _grant_limit_value(grant, invocation, "wall_ms"),
                "mem_mb": _grant_limit_value(grant, invocation, "mem_mb"),
            },
        },
        "integrity": {
            "verify_mode": UNKNOWN_FIELD,
            "verified": UNKNOWN_FIELD,
        },
        "http_fetch": {
            "allowed_count": 0,
            "denied_count": 0,
            "host_counts": {},
        },
        "evidence": {
            "path": evidence_path,
            "hashes_path": hashes_path,
            "hashes_json_sha256": _safe_sha256_file(hashes_path),
        },
        "trace_id": _trace_id_from_invocation(invocation, trace_info),
    }
    classification = invocation.get("classification") if isinstance(invocation.get("classification"), dict) else {}
    if classification:
        record["classification"] = {
            "data_class": _safe_string(classification.get("data_class")),
            "data_sensitivity": classification.get("data_sensitivity"),
            "regulatory_scope": classification.get("regulatory_scope"),
        }
    return record


def _emit_governance_log(
    *,
    invocation: Dict[str, Any],
    success: bool,
    governance_path: str,
    warning: Optional[str] = None,
) -> None:
    payload: Dict[str, Any] = {
        "event": "pba.worker.governance.write",
        "lane": "python",
        "worker": _safe_string(invocation.get("worker")),
        "run_id": _safe_string(invocation.get("pipeline_run_id")),
        "invocation_id": _safe_string(invocation.get("id")),
        "tenant": _safe_string(invocation.get("tenant")),
        "domain": _safe_string(invocation.get("domain")),
        "environment": _safe_string(invocation.get("environment") or os.getenv("PBA_ENV")),
        "success": bool(success),
    }
    if warning:
        payload["warning_code"] = "GOVERNANCE_WRITE_FAILED"
    print(json.dumps(payload, sort_keys=True), file=sys.stderr, flush=True)


def _write_governance_signal_pack(
    *,
    invocation: Dict[str, Any],
    grant: Optional[Grant],
    result: Dict[str, Any],
    trace_info: Dict[str, Any],
) -> None:
    governance_path, evidence_path, hashes_path = _resolve_governance_target(invocation)
    record = _build_governance_record(invocation, grant, result, trace_info, evidence_path, hashes_path)
    try:
        os.makedirs(os.path.dirname(governance_path), exist_ok=True)
        with open(governance_path, "w", encoding="utf-8") as fh:
            json.dump(record, fh, sort_keys=True, separators=(",", ":"))
            fh.write("\n")
        _emit_governance_log(invocation=invocation, success=True, governance_path=governance_path)
    except Exception:
        _emit_governance_log(
            invocation=invocation,
            success=False,
            governance_path=governance_path,
            warning="governance_write_failed",
        )


def _runtime_env_overrides(invocation: Dict[str, Any]) -> Dict[str, str]:
    governance_path, evidence_path, hashes_path = _resolve_governance_target(invocation)
    overrides: Dict[str, str] = {}
    environment = _safe_string(
        invocation.get("environment")
        or os.getenv("PBA_ENV")
        or os.getenv("PBA_ENVIRONMENT")
    )
    runtime_values = {
        "PBA_RUN_ID": _safe_string(invocation.get("id")),
        "PBA_PIPELINE_RUN_ID": _safe_string(invocation.get("pipeline_run_id")),
        "PBA_TENANT": _safe_string(invocation.get("tenant")),
        "PBA_ENVIRONMENT": environment,
        "PBA_ENV": environment,
        "PBA_DOMAIN": _safe_string(invocation.get("domain")),
        "PBA_EVIDENCE_PATH": evidence_path,
        "PBA_RUNTIME_GOVERNANCE_PATH": governance_path,
        "PBA_RUNTIME_HASHES_PATH": hashes_path,
    }
    raw_grant = invocation.get("grant")
    if isinstance(raw_grant, dict):
        profile = raw_grant.get("profile")
        if isinstance(profile, str) and profile.strip():
            runtime_values["PBA_GRANT_PROFILE"] = profile.strip()
    for key, value in runtime_values.items():
        if value == UNKNOWN_FIELD or not value:
            continue
        overrides[key] = value
    return overrides


def _parse_otlp_headers(val: Optional[str]) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if not val:
        return headers
    for part in val.split(","):
        if not part:
            continue
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k and v:
            headers[k] = v
    return headers


def _build_otlp_exporter(endpoint: str, headers: Dict[str, str]):
    parsed = urlparse(endpoint)
    use_http = parsed.scheme in {"http", "https"} and (parsed.path in {"", "/", "/v1/traces"})
    if use_http and OTLPHttpExporter is not None:
        target = endpoint.rstrip("/")
        if parsed.path in {"", "/"}:
            target = f"{target}/v1/traces"
        return OTLPHttpExporter(endpoint=target, headers=headers or None)

    if OTLPGrpcExporter is not None:
        kwargs: Dict[str, Any] = {"endpoint": endpoint}
        if headers:
            kwargs["headers"] = headers
        if endpoint.startswith("http://"):
            kwargs["insecure"] = True
        return OTLPGrpcExporter(**kwargs)

    if OTLPLegacyExporter is not None:
        kwargs = {"endpoint": endpoint}
        if headers:
            kwargs["headers"] = headers
        if endpoint.startswith("http://"):
            kwargs["insecure"] = True
        return OTLPLegacyExporter(**kwargs)

    raise RuntimeError("No OTLP trace exporter available")


def _parse_invocation(raw: str) -> Dict[str, Any]:
    try:
        data = json.loads(raw) if raw else {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_traceparent() -> Optional[str]:
    return _traceparent_ctx.get()


def get_trace_context() -> Dict[str, Any]:
    return _trace_ctx.get()


def get_governance_signal_pack_target() -> Tuple[str, str]:
    return _governance_target_ctx.get()


def get_grant() -> Optional[Grant]:
    return get_current_grant()


def _init_tracer_if_needed() -> None:
    global _TRACER_EXPORTER_KEY
    if trace is None or TracerProvider is None:
        return
    provider = trace.get_tracer_provider()
    otel_service_name = os.getenv("OTEL_SERVICE_NAME", "pba.worker")
    if not isinstance(provider, TracerProvider):
        provider = TracerProvider(resource=Resource.create({"service.name": otel_service_name}))
        trace.set_tracer_provider(provider)

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    otlp_headers = _parse_otlp_headers(os.getenv("OTEL_EXPORTER_OTLP_HEADERS"))
    if otlp_endpoint and BatchSpanProcessor:
        config_key = f"{otlp_endpoint}|{','.join(f'{k}={v}' for k, v in sorted(otlp_headers.items()))}"
        if _TRACER_EXPORTER_KEY == config_key:
            _tracer_initialized.set(True)
            return
        with suppress(Exception):
            exporter = _build_otlp_exporter(endpoint=otlp_endpoint, headers=otlp_headers)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            _TRACER_EXPORTER_KEY = config_key
    _tracer_initialized.set(True)


def _build_span_context(trace_id: Optional[str]) -> Optional[Any]:
    if not (trace and TraceContextTextMapPropagator and set_span_in_context):
        return None
    if not trace_id or not isinstance(trace_id, str):
        return None
    carrier = {"traceparent": f"00-{trace_id}-{uuid.uuid4().hex[:16]}-01"}
    try:
        propagator = TraceContextTextMapPropagator()
        return propagator.extract(carrier=carrier)
    except Exception:
        return None


def _traceparent_from_span(span: Any) -> Optional[str]:
    if not span or not TraceContextTextMapPropagator or not trace:
        return None
    carrier: Dict[str, str] = {}
    try:
        propagator = TraceContextTextMapPropagator()
        propagator.inject(carrier, context=set_span_in_context(span) if set_span_in_context else None)  # type: ignore[arg-type]
    except Exception:
        return None
    return carrier.get("traceparent")


def _normalize_handler_result(handler_result: Any) -> Tuple[bool, bool, Dict[str, Any], Optional[Dict[str, Any]], Optional[str]]:
    success = False
    retryable = False
    output: Dict[str, Any] = {}
    error_payload: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    if isinstance(handler_result, dict) and "success" in handler_result:
        success = bool(handler_result.get("success"))
        retryable = bool(handler_result.get("retryable"))
        output_val = handler_result.get("output")
        output = output_val if isinstance(output_val, dict) else {}
        err_val = handler_result.get("error")
        if isinstance(err_val, dict):
            error_payload = err_val
        msg_val = handler_result.get("message")
        if isinstance(msg_val, str):
            message = msg_val
        errors_list = handler_result.get("errors")
        if isinstance(errors_list, list) and errors_list and isinstance(errors_list[0], dict):
            if not error_payload:
                error_payload = errors_list[0]
    else:
        success = True
        output = handler_result if isinstance(handler_result, dict) else {}
    return success, retryable, output, error_payload, message


def _build_result(
    *,
    success: bool,
    retryable: bool,
    output: Dict[str, Any],
    error_payload: Optional[Dict[str, Any]],
    message: Optional[str],
    traceparent: Optional[str],
) -> Dict[str, Any]:
    safe_output = _redact(output or {})
    result: Dict[str, Any] = {
        "type": "pba.worker.result.v1",
        "success": bool(success),
        "status": "completed" if success else "failed",
        "retryable": bool(retryable),
        "output": safe_output if isinstance(safe_output, dict) else {},
        "errors": [],
    }
    if message:
        result["message"] = message
    if error_payload:
        safe_error = _redact(error_payload)
        result["error"] = safe_error
        result["errors"] = [safe_error]
    if traceparent:
        result.setdefault("trace", {})["traceparent"] = traceparent
        result["output"]["traceparent"] = traceparent
    return result


def _resolve_timeout(invocation: Dict[str, Any], override: Optional[float]) -> float:
    if override is not None:
        return float(override)
    meta = invocation.get("metadata") or invocation.get("meta") or {}
    lifecycle = invocation.get("lifecycle") or meta.get("lifecycle") or {}
    timeout_val: Optional[float] = None
    if isinstance(meta, dict):
        candidate = meta.get("timeout_seconds")
        if isinstance(candidate, (int, float)) and candidate > 0:
            timeout_val = float(candidate)
    if isinstance(lifecycle, dict):
        candidate = lifecycle.get("timeout_seconds") or lifecycle.get("timeout")
        if isinstance(candidate, (int, float)) and candidate > 0:
            timeout_val = float(candidate)
    env_val = os.getenv("PBA_WORKER_TIMEOUT_SECONDS")
    if env_val:
        try:
            env_timeout = float(env_val)
            if env_timeout > 0:
                timeout_val = env_timeout
        except ValueError:
            pass
    return timeout_val if timeout_val is not None else DEFAULT_TIMEOUT_SECONDS


def _invoke_handler(handler: Callable[..., Any], payload: Dict[str, Any], grant: Optional[Grant]) -> Any:
    previous_grant = get_current_grant()
    set_current_grant(grant)
    try:
        params = inspect.signature(handler).parameters
    except Exception:
        try:
            return handler(payload)
        finally:
            set_current_grant(previous_grant)

    try:
        grant_param = params.get("grant")
        if grant_param is not None and grant_param.kind in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            return handler(payload, grant=grant)
        return handler(payload)
    finally:
        set_current_grant(previous_grant)


def _execute_with_timeout(handler: Callable[..., Any], payload: Dict[str, Any], grant: Optional[Grant], timeout_seconds: float) -> Any:
    invocation_context = copy_context()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(invocation_context.run, _invoke_handler, handler, payload, grant)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            raise TimeoutError from exc


def run_worker(
    handler: Callable[..., Dict[str, Any]],
    *,
    validate: Optional[Callable[[Dict[str, Any]], None]] = None,
    timeout_seconds: Optional[float] = None,
) -> None:
    original_stdout = sys.stdout
    sys.stdout = sys.stderr
    previous_env: Dict[str, Optional[str]] = {}
    try:
        raw = sys.stdin.read()
        invocation = _parse_invocation(raw)
        inv_input = invocation.get("input") or {}
        meta_block = invocation.get("meta") if isinstance(invocation.get("meta"), dict) else {}
        trace_info = meta_block.get("trace") if isinstance(meta_block.get("trace"), dict) else None
        if not trace_info:
            trace_info = invocation.get("trace") if isinstance(invocation.get("trace"), dict) else {}
        traceparent = trace_info.get("traceparent") if isinstance(trace_info, dict) else None
        _traceparent_ctx.set(traceparent)
        _trace_ctx.set(trace_info if isinstance(trace_info, dict) else {})
        governance_path, evidence_path, _ = _resolve_governance_target(invocation)
        _governance_target_ctx.set((governance_path, evidence_path))
        grant = Grant.from_invocation(invocation)
        set_current_grant(grant)
        env_overrides = _runtime_env_overrides(invocation)
        for key, value in env_overrides.items():
            previous_env[key] = os.getenv(key)
            os.environ[key] = value
        dev_env = is_dev_env()
        bypass_missing_grant = os.getenv("PBA_REQUIRE_GRANT", "1") == "0" and dev_env
        require_grant = not bypass_missing_grant
        break_glass_warning: Optional[Dict[str, str]] = None
        if grant is None and require_grant:
            worker_name = str(invocation.get("worker") or "unknown")
            trace_id = str((trace_info or {}).get("trace_id") or invocation.get("pipeline_run_id") or "unknown")
            if _is_break_glass_allowed(invocation, dev_env=dev_env):
                grant = _synthesize_break_glass_grant(worker_name, trace_id)
                set_current_grant(grant)
                break_glass_warning = {
                    "code": BREAK_GLASS_WARNING_CODE,
                    "message": "dev/local break-glass bypass used for missing OPA grant",
                }
                print(f"BREAK_GLASS_USED worker={worker_name} trace_id={trace_id}", file=sys.stderr, flush=True)
            else:
                _emit_run_log(event="pba.worker.run.start", invocation=invocation, grant=grant)
                result = _build_result(
                    success=False,
                    retryable=False,
                    output={},
                    error_payload={"message": "worker denied: missing OPA grant", "code": SAFE_DENIED_CODE},
                    message="worker denied: missing OPA grant",
                    traceparent=traceparent,
                )
                _emit_run_log(
                    event="pba.worker.run.end",
                    invocation=invocation,
                    grant=grant,
                    success=False,
                    error_code=SAFE_DENIED_CODE,
                )
                _write_governance_signal_pack(
                    invocation=invocation,
                    grant=grant,
                    result=result,
                    trace_info=trace_info if isinstance(trace_info, dict) else {},
                )
                original_stdout.write(json.dumps(result) + "\n")
                original_stdout.flush()
                return

        if grant is None and not require_grant:
            set_current_grant(None)

        timeout_val = _resolve_timeout(invocation, timeout_seconds)

        try:
            if validate:
                validate(inv_input if isinstance(inv_input, dict) else {})
        except Exception:
            _emit_run_log(event="pba.worker.run.start", invocation=invocation, grant=grant)
            result = _build_result(
                success=False,
                retryable=False,
                output={},
                error_payload={"message": "validation failed", "code": SAFE_VALIDATION_CODE},
                message="validation failed",
                traceparent=traceparent,
            )
            _emit_run_log(
                event="pba.worker.run.end",
                invocation=invocation,
                grant=grant,
                success=False,
                error_code=SAFE_VALIDATION_CODE,
            )
            _write_governance_signal_pack(
                invocation=invocation,
                grant=grant,
                result=result,
                trace_info=trace_info if isinstance(trace_info, dict) else {},
            )
            original_stdout.write(json.dumps(result) + "\n")
            original_stdout.flush()
            return

        _init_tracer_if_needed()
        tracer = trace.get_tracer("pba.worker") if trace else None  # type: ignore
        propagator = TraceContextTextMapPropagator() if TraceContextTextMapPropagator else None
        ctx = None
        if propagator and traceparent:
            try:
                carrier = {"traceparent": traceparent}
                ctx = propagator.extract(carrier=carrier)
            except Exception:
                ctx = None
        if ctx is None and trace_info and trace_info.get("trace_id"):
            ctx = _build_span_context(str(trace_info.get("trace_id")))

        success = False
        retryable = False
        output_payload: Dict[str, Any] = {}
        error_payload: Optional[Dict[str, Any]] = None
        message: Optional[str] = None

        span_cm = tracer.start_as_current_span("worker.run", context=ctx) if tracer else nullcontext()
        started = time.time()
        with span_cm as span:
            if span and trace:
                attrs = {
                    "upm.tenant": invocation.get("tenant"),
                    "upm.run_id": invocation.get("pipeline_run_id"),
                    "upm.pipeline_run_id": invocation.get("pipeline_run_id"),
                    "upm.pipeline": invocation.get("pipeline"),
                    "upm.worker": invocation.get("worker"),
                    "upm.step": invocation.get("step"),
                    "upm.step_name": invocation.get("step"),
                    "upm.worker_run_id": invocation.get("id"),
                    "upm.domain": invocation.get("domain"),
                }
                meta = invocation.get("metadata") or {}
                attrs["upm.worker.attempt"] = meta.get("attempt", 1)
                classification = invocation.get("classification") if isinstance(invocation.get("classification"), dict) else {}
                if classification:
                    attrs["upm.classification.data_class"] = classification.get("data_class")
                    attrs["upm.classification.data_sensitivity"] = classification.get("data_sensitivity")
                    attrs["upm.classification.primary_sensitivity"] = _primary_classification_value(classification.get("data_sensitivity"))
                    attrs["upm.classification.regulatory_scope"] = classification.get("regulatory_scope")
                    attrs["upm.classification.primary_regulatory_scope"] = _primary_classification_value(classification.get("regulatory_scope"))
                for key, value in attrs.items():
                    if value is not None:
                        span.set_attribute(key, value)
            _emit_run_log(
                event="pba.worker.run.start",
                invocation=invocation,
                grant=grant,
                span=span,
            )
            try:
                handler_result = _execute_with_timeout(
                    handler,
                    inv_input if isinstance(inv_input, dict) else {},
                    grant,
                    timeout_val,
                )
                success, retryable, output_payload, error_payload, message = _normalize_handler_result(handler_result)
            except TimeoutError:
                success = False
                retryable = False
                error_payload = {"message": "timeout", "code": SAFE_TIMEOUT_CODE}
                message = "timeout"
                if span and trace and Status and StatusCode:
                    span.set_status(Status(StatusCode.ERROR, error_payload["message"]))  # type: ignore[arg-type]
            except Exception:  # pragma: no cover - exception path covered separately
                success = False
                retryable = False
                output_payload = {}
                error_payload = {"message": "worker exception", "code": SAFE_EXCEPTION_CODE}
                message = "worker exception"
                if span and trace and Status and StatusCode:
                    span.set_status(Status(StatusCode.ERROR, error_payload["message"]))  # type: ignore[arg-type]
            if span and trace:
                with suppress(Exception):
                    span.set_attribute("upm.worker.duration_ms", (time.time() - started) * 1000.0)  # type: ignore[arg-type]

        effective_traceparent = traceparent or _traceparent_from_span(span)
        result = _build_result(
            success=success,
            retryable=retryable,
            output=output_payload,
            error_payload=error_payload,
            message=message,
            traceparent=effective_traceparent,
        )
        if break_glass_warning is not None:
            result["warning"] = break_glass_warning
        error_code: Optional[str] = None
        if not success:
            err_obj = result.get("error")
            if isinstance(err_obj, dict):
                code = err_obj.get("code")
                if isinstance(code, str):
                    error_code = code
        _emit_registered_model_activity(
            invocation=invocation,
            output=output_payload,
            span=span,
            success=success,
            error_code=error_code,
            duration_ms=int((time.time() - started) * 1000.0),
        )
        _emit_otel_span_metadata_ingress(
            invocation=invocation,
            span=span,
            success=success,
            error_code=error_code,
            duration_ms=int((time.time() - started) * 1000.0),
        )
        _emit_run_log(
            event="pba.worker.run.end",
            invocation=invocation,
            grant=grant,
            success=success,
            error_code=error_code if error_code is not None else (None if success else UNKNOWN_FIELD),
            span=span,
        )
        _write_governance_signal_pack(
            invocation=invocation,
            grant=grant,
            result=result,
            trace_info=trace_info if isinstance(trace_info, dict) else {},
        )
        original_stdout.write(json.dumps(result) + "\n")
        original_stdout.flush()
    finally:
        sys.stdout = original_stdout
        for key, previous in previous_env.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous
        set_current_grant(None)
