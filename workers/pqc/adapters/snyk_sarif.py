from __future__ import annotations

import re
from typing import Any, Mapping

from ..canonical import require_canonical_contract_pack
from ..contract_pack import ContractPackError, ContractPackLoader
from ..errors import PQCAdapterError
from ..models import (
    AdapterDiagnostic,
    DiagnosticLevel,
    ImportContext,
    NormalizedObservation,
    ProviderPage,
    RetryClass,
    Sensitivity,
)
from ..safety import (
    detect_sensitivity,
    normalize_timestamp,
    stable_sha256_id,
)
from .base import asset_scope_ref, normalized_context_times, source_ref


MAX_RUNS = 20
MAX_RESULTS = 5_000
MAX_RULES_PER_RUN = 5_000
_ACCEPTED_TOOL_NAMES = {"snyk", "snykcode"}
_CRYPTO_SIGNALS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("asymmetric_rsa", re.compile(r"\brsa\b", re.IGNORECASE)),
    (
        "asymmetric_ec",
        re.compile(r"\b(?:ecdsa|elliptic|curve25519|x25519)\b", re.IGNORECASE),
    ),
    ("asymmetric_dsa", re.compile(r"\bdsa\b", re.IGNORECASE)),
    (
        "symmetric_cipher",
        re.compile(r"\b(?:aes|des|3des|cipher|cbc|ecb|gcm)\b", re.IGNORECASE),
    ),
    (
        "hash",
        re.compile(
            r"\b(?:md5|sha-?1|sha-?2|sha-?256|sha-?384|sha-?512|hash)\b", re.IGNORECASE
        ),
    ),
    (
        "key_management",
        re.compile(
            r"\b(?:hardcoded[ -]?key|keystore|keypair|key generation|private key)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "transport_security",
        re.compile(r"\b(?:ssl|tls|x\.?509|truststore)\b", re.IGNORECASE),
    ),
    (
        "digital_signature",
        re.compile(r"\b(?:signature|signing|verify)\b", re.IGNORECASE),
    ),
)
_SEVERITIES = {"none", "note", "warning", "error"}
_SEMANTIC_VERSION = re.compile(
    r"\A\d{1,5}(?:\.\d{1,5}){1,3}\Z",
    re.ASCII,
)


def _record(value: object) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise PQCAdapterError("PQC_ADAPTER_SCHEMA_DRIFT", RetryClass.SCHEMA_DRIFT)
    return value


def _array(value: object) -> list[object]:
    if not isinstance(value, list):
        raise PQCAdapterError("PQC_ADAPTER_SCHEMA_DRIFT", RetryClass.SCHEMA_DRIFT)
    return value


def _text(value: object, *, maximum: int = 4_096) -> str:
    if not isinstance(value, str):
        return ""
    return value[:maximum]


def _tool_name(run: Mapping[str, Any]) -> tuple[str, Mapping[str, Any]]:
    tool = _record(run.get("tool"))
    driver = _record(tool.get("driver"))
    native_name = _text(driver.get("name"), maximum=80)
    normalized = re.sub(r"[\s_-]+", "", native_name).casefold()
    if normalized not in _ACCEPTED_TOOL_NAMES:
        raise PQCAdapterError(
            "PQC_ADAPTER_UNSUPPORTED_DIALECT", RetryClass.NOT_SUPPORTED
        )
    return native_name, driver


def _rules(driver: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    native_rules = driver.get("rules", [])
    if not isinstance(native_rules, list) or len(native_rules) > MAX_RULES_PER_RUN:
        raise PQCAdapterError("PQC_ADAPTER_LIMIT_EXCEEDED", RetryClass.INVALID_REQUEST)
    indexed: dict[str, Mapping[str, Any]] = {}
    for value in native_rules:
        if not isinstance(value, dict):
            raise PQCAdapterError("PQC_ADAPTER_SCHEMA_DRIFT", RetryClass.SCHEMA_DRIFT)
        rule_id = _text(value.get("id"), maximum=256)
        if rule_id:
            indexed[rule_id] = value
    return indexed


def _rule_search_text(rule: Mapping[str, Any]) -> str:
    values: list[str] = []
    for key in ("shortDescription", "fullDescription"):
        nested = rule.get(key)
        if isinstance(nested, dict):
            values.append(_text(nested.get("text")))
    properties = rule.get("properties")
    if isinstance(properties, dict) and isinstance(properties.get("tags"), list):
        values.extend(_text(tag, maximum=160) for tag in properties["tags"][:50])
    return " ".join(values)


def _run_observed_at(run: Mapping[str, Any], fallback: str | None) -> str | None:
    invocations = run.get("invocations", [])
    if not isinstance(invocations, list):
        return fallback
    for value in invocations[:100]:
        if not isinstance(value, dict):
            continue
        observed = normalize_timestamp(value.get("endTimeUtc"))
        if observed is None:
            observed = normalize_timestamp(value.get("startTimeUtc"))
        if observed is not None:
            return observed
    return fallback


def _location(result: Mapping[str, Any]) -> tuple[str, int | None, int | None]:
    locations = result.get("locations", [])
    if not isinstance(locations, list) or len(locations) > 20:
        raise PQCAdapterError("PQC_ADAPTER_LIMIT_EXCEEDED", RetryClass.INVALID_REQUEST)
    if not locations or not isinstance(locations[0], dict):
        return "", None, None
    physical = locations[0].get("physicalLocation")
    if not isinstance(physical, dict):
        return "", None, None
    artifact = physical.get("artifactLocation")
    region = physical.get("region")
    uri = (
        _text(artifact.get("uri"), maximum=2_048) if isinstance(artifact, dict) else ""
    )
    if not isinstance(region, dict):
        return uri, None, None
    start_line = region.get("startLine")
    start_column = region.get("startColumn")
    safe_line = (
        start_line
        if isinstance(start_line, int)
        and not isinstance(start_line, bool)
        and start_line > 0
        else None
    )
    safe_column = (
        start_column
        if isinstance(start_column, int)
        and not isinstance(start_column, bool)
        and start_column > 0
        else None
    )
    return uri, safe_line, safe_column


def _signals(searchable: str) -> tuple[str, ...]:
    return tuple(
        name for name, pattern in _CRYPTO_SIGNALS if pattern.search(searchable)
    )


def _finding_kind(signals: tuple[str, ...]) -> str:
    if "key_management" in signals:
        return "source_code_key_management"
    if "transport_security" in signals:
        return "source_code_protocol_crypto"
    return "source_code_crypto_use"


def _tool_version(value: object) -> str:
    if not isinstance(value, str):
        return "unknown"
    candidate = value.strip()
    return candidate if _SEMANTIC_VERSION.fullmatch(candidate) else "unknown"


class SnykCodeSarifAdapter:
    adapter_id = "snyk-code-sarif-2.1.0"

    def __init__(self, loader: ContractPackLoader | None = None) -> None:
        self.pack = (loader or ContractPackLoader()).load("snyk-code-sarif-2.1.0")

    def adapt(self, payload: object, context: ImportContext) -> ProviderPage:
        tenant_id = context.tenant_id if isinstance(context, ImportContext) else ""
        require_canonical_contract_pack(self.pack, tenant_id=tenant_id)
        collected_at, package_generated_at, imported_at = normalized_context_times(
            context
        )
        root = _record(payload)
        if root.get("version") != "2.1.0":
            raise PQCAdapterError(
                "PQC_ADAPTER_UNSUPPORTED_DIALECT", RetryClass.NOT_SUPPORTED
            )
        runs = _array(root.get("runs"))
        if not 1 <= len(runs) <= MAX_RUNS:
            raise PQCAdapterError(
                "PQC_ADAPTER_LIMIT_EXCEEDED", RetryClass.INVALID_REQUEST
            )
        preflight_results = 0
        for native_run in runs:
            run = _record(native_run)
            native_results = _array(run.get("results", []))
            preflight_results += len(native_results)
            if preflight_results > MAX_RESULTS:
                raise PQCAdapterError(
                    "PQC_ADAPTER_LIMIT_EXCEEDED", RetryClass.INVALID_REQUEST
                )
        try:
            self.pack.validate_response(payload)
        except ContractPackError as exc:
            raise PQCAdapterError(
                "PQC_ADAPTER_SCHEMA_DRIFT", RetryClass.SCHEMA_DRIFT
            ) from exc

        sensitivity = detect_sensitivity(payload).sensitivity
        if sensitivity == Sensitivity.AUTH_SECRET:
            raise PQCAdapterError(
                "PQC_ADAPTER_AUTH_SECRET_INPUT", RetryClass.INVALID_REQUEST
            )
        scope_ref = asset_scope_ref(context)
        observations: list[NormalizedObservation] = []
        diagnostics: list[AdapterDiagnostic] = []
        seen: set[str] = set()
        result_count = 0
        skipped = 0
        duplicates = 0

        for native_run in runs:
            run = _record(native_run)
            _native_tool_name, driver = _tool_name(run)
            rules = _rules(driver)
            tool_version = _tool_version(
                driver.get("semanticVersion") or driver.get("version")
            )
            results = _array(run.get("results", []))
            result_count += len(results)
            if result_count > MAX_RESULTS:
                raise PQCAdapterError(
                    "PQC_ADAPTER_LIMIT_EXCEEDED", RetryClass.INVALID_REQUEST
                )
            observed_at = _run_observed_at(run, collected_at)

            for native_result in results:
                result = _record(native_result)
                rule_id = _text(result.get("ruleId"), maximum=256)
                if not rule_id:
                    raise PQCAdapterError(
                        "PQC_ADAPTER_SCHEMA_DRIFT", RetryClass.SCHEMA_DRIFT
                    )
                message = result.get("message")
                message_text = (
                    _text(message.get("text")) if isinstance(message, dict) else ""
                )
                searchable = " ".join(
                    (rule_id, _rule_search_text(rules.get(rule_id, {})), message_text)
                )
                signals = _signals(searchable)
                if not signals:
                    skipped += 1
                    continue
                uri, start_line, start_column = _location(result)
                source_identity = stable_sha256_id(
                    "snyk-finding",
                    scope_ref,
                    rule_id,
                    message_text,
                    uri,
                    start_line,
                    start_column,
                )
                observation_id = stable_sha256_id(
                    "observation", scope_ref, self.adapter_id, source_identity
                )
                if observation_id in seen:
                    duplicates += 1
                    continue
                seen.add(observation_id)
                severity = _text(result.get("level"), maximum=20).casefold()
                if severity not in _SEVERITIES:
                    severity = "unspecified"
                observations.append(
                    NormalizedObservation(
                        observation_id=observation_id,
                        provider="snyk",
                        product="snyk_code",
                        dialect="sarif_2_1_0",
                        asset_type="application_crypto_use",
                        asset_ref=scope_ref,
                        source_record_ref=source_identity,
                        observed_at=observed_at,
                        collected_at=collected_at,
                        package_generated_at=package_generated_at,
                        imported_at=imported_at,
                        attributes={
                            "finding_kind": _finding_kind(signals),
                            "severity": severity,
                            "rule_ref": stable_sha256_id("rule", scope_ref, rule_id),
                            "message_ref": stable_sha256_id(
                                "message", scope_ref, message_text
                            ),
                            "location_ref": stable_sha256_id(
                                "location", scope_ref, uri, start_line, start_column
                            ),
                            "crypto_signals": ",".join(signals),
                            "tool_family": "snyk_code",
                            "tool_version": tool_version,
                        },
                        sensitivity=sensitivity,
                        synthetic=context.synthetic,
                        evidence_status=self.pack.evidence_status,
                    )
                )

        if not observations:
            diagnostics.append(
                AdapterDiagnostic(DiagnosticLevel.INFORMATION, "no_crypto_signal")
            )
        if duplicates:
            diagnostics.append(
                AdapterDiagnostic(DiagnosticLevel.WARNING, "duplicate_record")
            )
        return ProviderPage(
            adapter_id=self.adapter_id,
            contract_pack_id=self.pack.pack_id,
            source_ref=source_ref(context),
            observations=tuple(observations),
            total_records=result_count,
            accepted_records=len(observations),
            skipped_records=skipped,
            duplicate_records=duplicates,
            page_number=0,
            next_cursor=None,
            sensitivity=sensitivity,
            diagnostics=tuple(diagnostics),
        )
