"""Documentation-shaped ServiceNow Table API candidate with a fake transport only.

This module has no HTTP client, URL-fetch function, credentials or write methods.
Its mapping is versioned and deliberately incomplete. A passing fixture proves
parsing/normalization behavior, not a ServiceNow instance or CMDB qualification.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from workers.pqc.assessment_sources import normalize_page


ROOT = Path(__file__).resolve().parents[2] / "integrations/pqc/reference_assessment"
PROFILE_FILE = ROOT / "servicenow-cmdb.mapping.v1.json"
FIXTURE_FILE = ROOT / "servicenow-table.synthetic.json"
PATH = "/api/now/table/cmdb_ci_appl"
MAX_PAGE_BYTES = 256 * 1024
MAX_PAGES = 8
SYS_ID = re.compile(r"[a-f0-9]{32}\Z")
NAME = re.compile(r"Synthetic [A-Za-z0-9 -]{1,100}\Z")


class ServiceNowReferenceError(ValueError):
    """A controlled reason code; never includes a response body or reference."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, TypeError):
        raise ServiceNowReferenceError("invalid_json_value") from None


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def reference_profile() -> dict[str, Any]:
    return json.loads(PROFILE_FILE.read_text(encoding="utf-8"))


def _validated_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    expected = reference_profile()
    if profile is not None and profile != expected:
        raise ServiceNowReferenceError("unqualified_mapping_profile")
    if (expected.get("schema_version") != "pba.pqc.servicenow-cmdb-mapping.v1"
            or expected.get("method") != "GET" or expected.get("table_candidate") != "cmdb_ci_appl"
            or expected.get("field_mapping") != {"id": "sys_id", "name": "name", "owner_id": "owned_by"}
            or expected.get("request_contract") != {
                "sysparm_display_value": "false", "sysparm_exclude_reference_link": "true",
                "sysparm_fields": "sys_id,name,owned_by", "sysparm_query": "ORDERBYsys_id",
                "sysparm_query_no_domain": "false"}
            or expected.get("product_binding") != {"product": "ServiceNow", "edition": None,
                "version": None, "instance": None, "minimum_permissions": None,
                "authentication": None, "dictionary_validated": False}
            or expected.get("write_operations") != [] or expected.get("live_connection_supported") is not False):
        raise ServiceNowReferenceError("unqualified_mapping_profile")
    return expected


def request_parameters(offset: int, page_size: int, profile: dict[str, Any] | None = None) -> dict[str, str]:
    """Construct an allowlisted GET query; an arbitrary encoded query is forbidden."""
    _validated_profile(profile)
    if type(offset) is not int or not 0 <= offset < MAX_PAGES * 100:
        raise ServiceNowReferenceError("invalid_offset")
    if type(page_size) is not int or not 1 <= page_size <= 100:
        raise ServiceNowReferenceError("invalid_page_size")
    return {"sysparm_display_value": "false", "sysparm_exclude_reference_link": "true",
            "sysparm_fields": "sys_id,name,owned_by", "sysparm_limit": str(page_size),
            "sysparm_offset": str(offset), "sysparm_query": "ORDERBYsys_id",
            "sysparm_query_no_domain": "false", "sysparm_suppress_pagination_header": "false"}


def _native_id(value: Any, *, nullable: bool = False) -> str | None:
    if isinstance(value, dict):
        # 'all' / display-value responses and unexpected linked refs fail closed.
        if set(value) != {"value"}:
            raise ServiceNowReferenceError("ambiguous_reference_shape")
        value = value["value"]
    if nullable and value in (None, ""):
        return None
    if not isinstance(value, str) or not SYS_ID.fullmatch(value):
        raise ServiceNowReferenceError("invalid_native_identifier")
    return value


def map_result_to_reference_page(payload: dict[str, Any], profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Map actual raw field values, retaining duplicate and conflicting records.

    No fabricated application criticality, service association or information
    lifetime is substituted for fields that this profile has not qualified.
    The synthetic name constraint is an intentional reference-only restriction.
    """
    selected = _validated_profile(profile)
    if not isinstance(payload, dict) or set(payload) != {"result"}:
        raise ServiceNowReferenceError("invalid_table_response")
    rows = payload["result"]
    if not isinstance(rows, list) or len(rows) > 100 or len(_canonical(payload)) > MAX_PAGE_BYTES:
        raise ServiceNowReferenceError("table_page_budget_exceeded")
    mapping = selected["field_mapping"]
    records = []
    for row in rows:
        if not isinstance(row, dict) or not {"sys_id", "name"} <= set(row) or not set(row) <= {"sys_id", "name", "owned_by"}:
            raise ServiceNowReferenceError("unqualified_response_fields")
        if not isinstance(row[mapping["id"]], str):
            raise ServiceNowReferenceError("invalid_native_identifier")
        native_id = _native_id(row[mapping["id"]])
        name = row[mapping["name"]]
        if not isinstance(name, str) or not NAME.fullmatch(name):
            raise ServiceNowReferenceError("synthetic_name_required")
        records.append({
            "id": native_id, "name": name, "owner_id": _native_id(row.get(mapping["owner_id"]), nullable=True),
            "evidence_basis": "observed", "business_service_id": None, "criticality": "unknown",
            "environment": "synthetic_lab", "confidentiality_until": None,
        })
    return {"schema_version": "pba.pqc.reference-source-page.v1", "kind": "cmdb", "synthetic": True, "records": records}


def normalize_servicenow_page(payload: dict[str, Any], *, tenant_id: str = "synthetic-enterprise",
                             source_instance_id: str = "synthetic-servicenow-cmdb",
                             observed_at: str = "2026-09-05T12:00:00Z",
                             profile: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if (not isinstance(tenant_id, str) or not isinstance(source_instance_id, str)
            or not tenant_id.startswith("synthetic-") or not source_instance_id.startswith("synthetic-")):
        raise ServiceNowReferenceError("synthetic_context_required")
    return normalize_page("cmdb", map_result_to_reference_page(payload, profile), tenant_id=tenant_id,
                          source_instance_id=source_instance_id, observed_at=observed_at)


class FakeTableTransport:
    """A finite sequence of in-memory responses; no caller-provided I/O callback."""

    def __init__(self, responses: list[dict[str, Any]]):
        if not isinstance(responses, list) or not 1 <= len(responses) <= MAX_PAGES:
            raise ServiceNowReferenceError("invalid_fixture_sequence")
        self._responses = copy.deepcopy(responses)
        self.requests: list[dict[str, Any]] = []

    def get(self, path: str, parameters: dict[str, str]) -> dict[str, Any]:
        if path != PATH or parameters != request_parameters(int(parameters["sysparm_offset"]), int(parameters["sysparm_limit"])):
            raise ServiceNowReferenceError("unapproved_reference_request")
        self.requests.append({"method": "GET", "path": path, "parameters": copy.deepcopy(parameters)})
        if not self._responses:
            raise ServiceNowReferenceError("fixture_sequence_exhausted")
        value = self._responses.pop(0)
        if value == {"timeout": True}:
            raise ServiceNowReferenceError("transport_timeout")
        if not isinstance(value, dict) or set(value) != {"status_code", "body", "headers"}:
            raise ServiceNowReferenceError("invalid_fixture_response")
        return value


def _next_offset(headers: Any, offset: int, page_size: int) -> int | None:
    if not isinstance(headers, dict) or not set(headers) <= {"Link"}:
        raise ServiceNowReferenceError("unqualified_response_headers")
    value = headers.get("Link")
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 2048:
        raise ServiceNowReferenceError("invalid_pagination_link")
    # This reference fixture uses one next Link; URLs are parsed, never fetched.
    match = re.fullmatch(r'<([^<>]+)>;\s*rel="next"', value)
    if not match:
        raise ServiceNowReferenceError("invalid_pagination_link")
    parsed = urlsplit(match[1])
    if (parsed.scheme != "https" or parsed.netloc != "synthetic-instance.invalid"
            or parsed.path != PATH or parsed.fragment or parsed.username or parsed.password):
        raise ServiceNowReferenceError("unapproved_pagination_target")
    parameters = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
    if parameters != {"sysparm_offset": [str(offset + page_size)], "sysparm_limit": [str(page_size)]}:
        raise ServiceNowReferenceError("pagination_revision_conflict")
    return offset + page_size


def collect_reference_fixture_pages(transport: FakeTableTransport, *, page_size: int = 2,
                                    max_pages: int = MAX_PAGES,
                                    profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Exercise bounded offset pagination; never accept a native network transport.

    ServiceNow applies its limit before ACL filtering, so a short/empty result
    is not used as an end-of-collection signal. Only the checked fixture Link
    controls continuation; even end-of-fixture is not enterprise completeness.
    """
    if type(transport) is not FakeTableTransport:
        raise ServiceNowReferenceError("fake_transport_required")
    _validated_profile(profile)
    request_parameters(0, page_size, profile)
    if type(max_pages) is not int or not 1 <= max_pages <= MAX_PAGES:
        raise ServiceNowReferenceError("invalid_page_budget")
    records = []
    page_receipts = []
    offset, exhausted, reason = 0, False, None
    for _ in range(max_pages):
        try:
            response = transport.get(PATH, request_parameters(offset, page_size, profile))
            status = response["status_code"]
            if type(status) is not int or status != 200:
                raise ServiceNowReferenceError({401: "authentication_required", 403: "access_denied",
                                               429: "rate_limited", 408: "transport_timeout",
                                               500: "provider_unavailable", 503: "provider_unavailable"}.get(status, "unexpected_response_status"))
            normalized = normalize_servicenow_page(response["body"], profile=profile)
            if len(normalized) > page_size:
                raise ServiceNowReferenceError("provider_page_limit_exceeded")
            next_offset = _next_offset(response["headers"], offset, page_size)
            records.extend(normalized)
            page_receipts.append({"offset": offset, "record_count": len(normalized), "raw_response_sha256": _sha(response["body"])})
            if next_offset is None:
                exhausted = True
                break
            offset = next_offset
        except ServiceNowReferenceError as exc:
            reason = str(exc)
            break
        except (ValueError, TypeError, KeyError):
            reason = "invalid_fixture_response"
            break
    if not exhausted and reason is None:
        reason = "page_budget_exhausted"
    unique = {_sha(row): row for row in records}
    variants: dict[str, set[str]] = defaultdict(set)
    for sha, row in unique.items():
        variants[row["subject_ref"]].add(sha)
    return {
        "schema_version": "pba.pqc.servicenow-cmdb-fixture-collection.v1", "synthetic": True,
        "state": "fixture_complete" if exhausted else "partial" if page_receipts else "blocked",
        "reason": reason, "fixture_pages_exhausted": exhausted, "enterprise_collection_complete": False,
        "live_provider_connected": False, "source_system_write_authority": False,
        "profile_sha256": _sha(_validated_profile(profile)), "pages": page_receipts,
        "records": [unique[key] for key in sorted(unique)],
        "counts": {"pages": len(page_receipts), "raw_records": len(records), "normalized_records": len(unique),
                   "subjects": len(variants), "duplicate_records": len(records) - len(unique),
                   "conflicting_subjects": sum(len(values) > 1 for values in variants.values())},
        "limitations": ["instance_edition_version_and_dictionary_unqualified", "source_route_and_permissions_unconfirmed",
                        "offset_pagination_is_not_snapshot_isolation", "acl_filtered_results_are_not_enterprise_denominator",
                        "business_service_criticality_information_lifetime_unmapped", "owner_reference_is_not_owner_acceptance"],
    }


def prove_servicenow_cmdb_reference() -> dict[str, Any]:
    """Fixed synthetic input -> native field mapper -> canonical records proof.

    Returns metadata only, never native source rows, names, credentials or URLs
    supplied by a response. Artifact emission belongs to the caller.
    """
    fixture = json.loads(FIXTURE_FILE.read_text(encoding="utf-8"))
    if set(fixture) != {"schema_version", "synthetic", "responses"} or fixture["synthetic"] is not True or fixture["schema_version"] != "pba.pqc.servicenow-table-fixture.v1":
        raise ServiceNowReferenceError("invalid_native_fixture")
    result = collect_reference_fixture_pages(FakeTableTransport(fixture["responses"]), page_size=2)
    expected_counts = {"pages": 2, "raw_records": 4, "normalized_records": 3, "subjects": 2,
                       "duplicate_records": 1, "conflicting_subjects": 1}
    return {"type": "pqc.reference.servicenow-cmdb-proof.v1", "synthetic": True,
            "proof_level": "documentation_shaped_fixture_contract",
            "result": "pass" if result["state"] == "fixture_complete" and result["counts"] == expected_counts else "fail",
            "fixture_sha256": _sha(fixture), "mapping_profile_sha256": result["profile_sha256"],
            "normalized_records_sha256": _sha(result["records"]), "counts": result["counts"],
            "live_provider_connected": False, "source_system_write_authority": False,
            "enterprise_collection_complete": False, "limitations": result["limitations"]}
