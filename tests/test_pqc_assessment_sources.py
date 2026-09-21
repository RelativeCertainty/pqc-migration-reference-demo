from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from workers.pqc.assessment_sources import (
    SourceContractError,
    normalize_page,
    qualified_ref,
    validate_catalog,
)


ROOT = Path(__file__).resolve().parents[1] / "integrations/pqc/reference_assessment"
NOW = "2026-09-05T10:00:00Z"


def page(kind: str) -> dict:
    return json.loads((ROOT / f"{kind}.page.json").read_text())


def normalize(kind: str, payload: dict | None = None, tenant: str = "synthetic-tenant") -> list[dict]:
    return normalize_page(kind, page(kind) if payload is None else payload,
                          tenant_id=tenant, source_instance_id=f"synthetic-{kind}", observed_at=NOW)


def catalog() -> dict:
    return json.loads((ROOT / "catalog.v1.json").read_text())


def test_catalog_counts_and_priority_patterns() -> None:
    assert validate_catalog() == {
        "estate_areas": 10, "source_families": 27, "migration_archetypes": 22,
        "priority_pattern_refs": ["tls-hybrid-key-exchange", "ssh-hybrid-key-exchange", "application-library-migration"],
    }
    value = catalog()
    assert all(row["execution_authorized"] is False for row in value["migration_archetypes"])
    assert all(row["product_profile"]["product"] is None for row in value["source_families"])
    assert all("not selections" in row["discovery_question"] for row in value["source_families"])


@pytest.mark.parametrize("mutation", [
    lambda data: data["estate_areas"].pop(),
    lambda data: data["source_families"][0].update(id=data["source_families"][1]["id"]),
    lambda data: data["source_families"][0].update(area_ref="missing-area"),
    lambda data: data["migration_archetypes"][0]["source_family_refs"].append("missing-family"),
    lambda data: data["source_families"][0]["pattern_refs"].append("missing-pattern"),
    lambda data: data["source_families"][0]["pattern_refs"].pop(),
    lambda data: data["priority_patterns"][0].update(pattern_ref="missing-pattern"),
    lambda data: data["priority_patterns"][0].update(pattern_ref="certificate-signature-migration"),
    lambda data: data["priority_patterns"][0].update(pattern_ref="ssh-hybrid-key-exchange"),
    lambda data: data["qualification_ladder"].reverse(),
    lambda data: data["source_families"][0]["product_profile"].update(authentication="assumed-admin"),
    lambda data: data["migration_archetypes"][0].update(execution_authorized=True),
])
def test_catalog_rejects_drift_and_unsupported_claims(mutation) -> None:
    value = catalog()
    mutation(value)
    with pytest.raises(SourceContractError):
        validate_catalog(value)


def test_raw_pages_link_to_same_application_and_certificate() -> None:
    application = normalize("cmdb")[0]
    certificate = normalize("pki")[0]
    endpoint = normalize("tls")[0]
    assert certificate["facts"]["application_ref"] == application["subject_ref"]
    assert endpoint["facts"]["application_ref"] == application["subject_ref"]
    assert endpoint["facts"]["certificate_ref"] == certificate["subject_ref"]
    assert certificate["facts"]["signature_algorithm"] == "sha256WithRSAEncryption"
    assert endpoint["facts"]["key_exchange_group"] == "X25519"
    assert application["facts"]["criticality"] == "high"
    assert application["facts"]["confidentiality_until"] == "2041-09-05"
    for row in (application, certificate, endpoint):
        assert set(row) == {"subject_ref", "fact_type", "assertion_kind", "facts"}
        assert row["assertion_kind"] == "observed"


def test_actual_raw_values_drive_output_and_conflicts_remain_visible() -> None:
    payload = page("tls")
    baseline = normalize("tls", payload)[0]
    payload["records"].append(copy.deepcopy(payload["records"][0]))
    payload["records"][1]["key_exchange_group"] = "X25519MLKEM768"
    payload["records"][1]["evidence_basis"] = "configured"
    result = normalize("tls", payload)
    assert result[0] == baseline
    assert result[0]["subject_ref"] == result[1]["subject_ref"]
    assert result[0]["facts"] != result[1]["facts"]
    assert result[1]["facts"]["key_exchange_group"] == "X25519MLKEM768"
    assert result[1]["assertion_kind"] == "configured"


@pytest.mark.parametrize("kind", ["cmdb", "pki", "tls"])
def test_exact_duplicates_replay_deterministically_without_loss(kind: str) -> None:
    payload = page(kind)
    payload["records"] *= 2
    unchanged = copy.deepcopy(payload)
    result = normalize(kind, payload)
    assert len(result) == 2 and result[0] == result[1]
    assert normalize(kind, payload) == result
    assert payload == unchanged
    assert normalize(kind, {**payload, "records": []}) == []


def test_missing_evidence_is_not_invented() -> None:
    payload = page("tls")
    payload["records"][0].update(application_source=None, application_id=None,
                                 certificate_source=None, certificate_id=None, key_exchange_group=None)
    result = normalize("tls", payload)[0]
    assert result["facts"]["application_ref"] is None
    assert result["facts"]["certificate_ref"] is None
    assert result["facts"]["key_exchange_group"] is None


def test_namespace_is_explicit_not_inferred_from_names() -> None:
    payload = page("pki")
    payload["records"][0]["application_source"] = "another-cmdb"
    result = normalize("pki", payload)[0]
    assert result["facts"]["application_ref"] != normalize("cmdb")[0]["subject_ref"]
    assert result["facts"]["application_ref"] == qualified_ref("synthetic-tenant", "another-cmdb", "app-001")


def test_identity_is_tenant_source_and_type_qualified() -> None:
    ref = qualified_ref("tenant", "source", "id")
    assert ref != qualified_ref("other", "source", "id")
    assert ref != qualified_ref("tenant", "other", "id")
    assert ref != qualified_ref("tenant", "source", "id", namespace="owner")
    assert qualified_ref("a:b", "c", "d") != qualified_ref("a", "b:c", "d")
    first, second = normalize("tls"), normalize("tls", tenant="other-tenant")
    assert first[0]["subject_ref"] != second[0]["subject_ref"]
    assert first[0]["facts"]["application_ref"] != second[0]["facts"]["application_ref"]


@pytest.mark.parametrize("mutation", [
    lambda data: data.update(synthetic=False),
    lambda data: data.update(schema_version="pba.pqc.reference-source-page.v2"),
    lambda data: data.update(provider_url="https://must-not-connect.invalid"),
    lambda data: data["records"][0].update(secret_value="synthetic-forbidden-value"),
    lambda data: data["records"][0].update(evidence_basis="independently_verified"),
    lambda data: data["records"][0].update(port=True),
    lambda data: data["records"][0].update(port=0),
    lambda data: data["records"][0].update(hostname="not-a-fixture.com"),
    lambda data: data["records"][0].update(key_exchange_group="X25519\n"),
    lambda data: data["records"][0].update(application_source=None),
    lambda data: data["records"][0].pop("key_exchange_group"),
    lambda data: data.update(records=data["records"] * 1001),
])
def test_closed_pages_fail_without_payload_echo(mutation) -> None:
    payload = page("tls")
    mutation(payload)
    with pytest.raises(SourceContractError) as failure:
        normalize("tls", payload)
    assert str(failure.value) in {"invalid_source_page", "incomplete_source_relation"}
    assert "synthetic-forbidden-value" not in str(failure.value)
    assert "must-not-connect" not in str(failure.value)


@pytest.mark.parametrize("overrides", [
    {"kind": "scanner"}, {"kind": []}, {"tenant_id": "https://invalid.example"}, {"source_instance_id": ""},
    {"observed_at": "2026-09-05"}, {"observed_at": "2026-99-05T00:00:00Z"},
])
def test_invalid_context_is_rejected(overrides: dict) -> None:
    args = dict(kind="tls", payload=page("tls"), tenant_id="tenant", source_instance_id="source", observed_at=NOW)
    args.update(overrides)
    with pytest.raises(SourceContractError):
        normalize_page(**args)


def test_kind_mismatch_and_invalid_dates_are_rejected() -> None:
    with pytest.raises(SourceContractError, match="source_kind_mismatch"):
        normalize_page("tls", page("cmdb"), tenant_id="tenant", source_instance_id="source", observed_at=NOW)
    payload = page("pki")
    payload["records"][0]["valid_until"] = "not-a-date"
    with pytest.raises(SourceContractError, match="invalid_source_page"):
        normalize("pki", payload)
