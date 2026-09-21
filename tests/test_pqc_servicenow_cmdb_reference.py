"""Offline native-shaped fixture proof; no ServiceNow or HTTP dependencies."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from workers.pqc.servicenow_cmdb_reference import (
    FakeTableTransport,
    ServiceNowReferenceError,
    collect_reference_fixture_pages,
    map_result_to_reference_page,
    normalize_servicenow_page,
    prove_servicenow_cmdb_reference,
    reference_profile,
    request_parameters,
)


FIXTURE = Path(__file__).resolve().parents[1] / "integrations/pqc/reference_assessment/servicenow-table.synthetic.json"


def responses():
    return json.loads(FIXTURE.read_text())["responses"]


def payload():
    return responses()[0]["body"]


def test_native_result_values_actually_drive_canonical_records():
    raw = payload()
    unchanged = copy.deepcopy(raw)
    result = normalize_servicenow_page(raw)
    assert len(result) == 2
    assert result[0]["facts"]["name"] == raw["result"][0]["name"]
    assert result[0]["facts"]["criticality"] == "unknown"
    assert result[0]["facts"]["business_service_ref"] is None
    assert result[0]["facts"]["confidentiality_until"] is None
    assert result[0]["facts"]["owner_ref"] is not None
    assert result[0]["assertion_kind"] == "observed"
    assert raw == unchanged
    raw["result"][0]["owned_by"] = "20000000000000000000000000000001"
    changed = normalize_servicenow_page(raw)
    assert result[0]["subject_ref"] == changed[0]["subject_ref"]
    assert result[0]["facts"]["owner_ref"] != changed[0]["facts"]["owner_ref"]


def test_reference_object_and_raw_sysid_string_map_identically():
    first, second = payload(), payload()
    second["result"][0]["owned_by"] = {"value": first["result"][0]["owned_by"]}
    assert normalize_servicenow_page(first) == normalize_servicenow_page(second)


@pytest.mark.parametrize("owner", [None, "", {"value": ""}])
def test_absent_owner_is_unknown_not_invented(owner):
    raw = payload()
    raw["result"][0]["owned_by"] = owner
    assert normalize_servicenow_page(raw)[0]["facts"]["owner_ref"] is None
    raw["result"][0].pop("owned_by")
    assert normalize_servicenow_page(raw)[0]["facts"]["owner_ref"] is None


@pytest.mark.parametrize("owner", [
    "Synthetic Owner Name", {"display_value": "Synthetic Owner"},
    {"value": "10000000000000000000000000000001", "display_value": "Synthetic Owner"},
    {"value": "10000000000000000000000000000001", "link": "https://do-not-follow.invalid"},
    {"value": "not-a-sys-id"}, 123,
])
def test_ambiguous_display_values_and_reference_links_fail_closed(owner):
    raw = payload()
    raw["result"][0]["owned_by"] = owner
    with pytest.raises(ServiceNowReferenceError) as failure:
        normalize_servicenow_page(raw)
    assert "Synthetic Owner" not in str(failure.value)
    assert "do-not-follow" not in str(failure.value)


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(result={}),
    lambda value: value.update(unrequested_field="not-echoed"),
    lambda value: value["result"][0].update(secret_field="not-echoed"),
    lambda value: value["result"][0].update(sys_id="not-hex"),
    lambda value: value["result"][0].update(sys_id={"value": "00000000000000000000000000000001"}),
    lambda value: value["result"][0].update(name="non-synthetic-customer"),
    lambda value: value["result"][0].update(name="Synthetic Trailing newline\n"),
    lambda value: value.update(result=value["result"] * 51),
])
def test_unknown_fields_identifiers_and_payload_budgets(mutation):
    raw = payload()
    mutation(raw)
    with pytest.raises(ServiceNowReferenceError) as failure:
        map_result_to_reference_page(raw)
    assert "not-echoed" not in str(failure.value)


def test_requests_are_read_only_allowlisted_and_do_not_expand_domains():
    parameters = request_parameters(2, 2)
    assert parameters == {
        "sysparm_display_value": "false", "sysparm_exclude_reference_link": "true",
        "sysparm_fields": "sys_id,name,owned_by", "sysparm_limit": "2", "sysparm_offset": "2",
        "sysparm_query": "ORDERBYsys_id", "sysparm_query_no_domain": "false",
        "sysparm_suppress_pagination_header": "false",
    }
    profile = reference_profile()
    assert profile["product_binding"]["instance"] is None
    assert profile["write_operations"] == []
    profile["request_contract"]["sysparm_display_value"] = "all"
    with pytest.raises(ServiceNowReferenceError, match="unqualified_mapping_profile"):
        request_parameters(0, 2, profile)


def test_bounded_pagination_duplicates_and_conflicts_remain_explicit():
    transport = FakeTableTransport(responses())
    result = collect_reference_fixture_pages(transport)
    assert result["state"] == "fixture_complete"
    assert result["counts"] == {"pages": 2, "raw_records": 4, "normalized_records": 3,
                                "subjects": 2, "duplicate_records": 1, "conflicting_subjects": 1}
    assert [request["parameters"]["sysparm_offset"] for request in transport.requests] == ["0", "2"]
    assert all(request["method"] == "GET" for request in transport.requests)
    assert result["live_provider_connected"] is False
    assert result["enterprise_collection_complete"] is False
    assert result["source_system_write_authority"] is False


def test_short_or_acl_filtered_empty_page_does_not_end_collection():
    fixture = responses()
    fixture[0]["body"]["result"] = []
    result = collect_reference_fixture_pages(FakeTableTransport(fixture))
    assert result["counts"]["pages"] == 2
    assert result["counts"]["raw_records"] == 2
    assert result["enterprise_collection_complete"] is False


@pytest.mark.parametrize("status,reason", [(401, "authentication_required"), (403, "access_denied"),
                                          (429, "rate_limited"), (503, "provider_unavailable")])
def test_error_response_is_sanitized_without_automatic_retry(status, reason):
    failed = {"status_code": status, "body": {"error": "must-not-echo-sensitive-payload"}, "headers": {}}
    for prefix in ([], [responses()[0]]):
        transport = FakeTableTransport(prefix + [failed])
        result = collect_reference_fixture_pages(transport)
        assert result["state"] == ("partial" if prefix else "blocked")
        assert result["reason"] == reason
        assert len(transport.requests) == len(prefix) + 1
        assert "must-not-echo" not in json.dumps(result)


def test_timeout_and_page_budget_do_not_claim_complete_collection():
    timeout = collect_reference_fixture_pages(FakeTableTransport([responses()[0], {"timeout": True}]))
    assert timeout["state"] == "partial" and timeout["reason"] == "transport_timeout"
    limited = collect_reference_fixture_pages(FakeTableTransport(responses()), max_pages=1)
    assert limited["state"] == "partial" and limited["reason"] == "page_budget_exhausted"
    assert limited["fixture_pages_exhausted"] is False


@pytest.mark.parametrize("link", [
    '<https://real-instance.example/api/now/table/cmdb_ci_appl?sysparm_offset=2&sysparm_limit=2>; rel="next"',
    '<https://synthetic-instance.invalid/api/now/table/cmdb_ci_appl?sysparm_offset=0&sysparm_limit=2>; rel="next"',
    '<https://synthetic-instance.invalid/api/now/table/sys_user?sysparm_offset=2&sysparm_limit=2>; rel="next"',
    '<https://synthetic-instance.invalid/api/now/table/cmdb_ci_appl?sysparm_offset=2&sysparm_limit=2&sysparm_query_no_domain=true>; rel="next"',
])
def test_unqualified_next_links_are_never_followed(link):
    fixture = responses()
    fixture[0]["headers"]["Link"] = link
    transport = FakeTableTransport(fixture)
    result = collect_reference_fixture_pages(transport)
    assert result["state"] == "blocked"
    assert len(transport.requests) == 1
    assert result["counts"]["pages"] == 0


def test_only_finite_fake_transport_is_accepted():
    class NativeTransport:
        def get(self, *args):
            pytest.fail("no native transport operation allowed")
    with pytest.raises(ServiceNowReferenceError, match="fake_transport_required"):
        collect_reference_fixture_pages(NativeTransport())
    for args in ((-1, 2), (0, 0), (0, 101), (True, 2)):
        with pytest.raises(ServiceNowReferenceError):
            request_parameters(*args)


def test_proof_callable_is_metadata_only_repeatable_and_explicit():
    proof = prove_servicenow_cmdb_reference()
    assert proof == prove_servicenow_cmdb_reference()
    assert proof["result"] == "pass"
    assert proof["proof_level"] == "documentation_shaped_fixture_contract"
    assert proof["counts"]["normalized_records"] == 3
    assert len(proof["normalized_records_sha256"]) == 64
    assert "Synthetic Records Application" not in json.dumps(proof)
    assert "10000000000000000000000000000001" not in json.dumps(proof)
    assert proof["enterprise_collection_complete"] is False


def test_tenant_source_namespace_and_profile_version_are_not_silent_defaults():
    base = normalize_servicenow_page(payload())
    other = normalize_servicenow_page(payload(), tenant_id="synthetic-other")
    assert base[0]["subject_ref"] != other[0]["subject_ref"]
    assert base[0]["facts"]["owner_ref"] != other[0]["facts"]["owner_ref"]
    with pytest.raises(ServiceNowReferenceError, match="synthetic_context_required"):
        normalize_servicenow_page(payload(), tenant_id="production")
    profile = reference_profile()
    profile["schema_version"] = "pba.pqc.servicenow-cmdb-mapping.v2"
    with pytest.raises(ServiceNowReferenceError, match="unqualified_mapping_profile"):
        normalize_servicenow_page(payload(), profile=profile)
