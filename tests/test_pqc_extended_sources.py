"""Independent expected mappings and adversarial tests for offline family models."""

from __future__ import annotations

import copy
import json
import socket

import pytest

from tools.pqc_reference.extended_estate import generate_extended_pages
from workers.pqc.assessment_sources import SourceContractError, qualified_ref
from workers.pqc.extended_sources import extended_family_profiles, extended_page_digest, normalize_extended_page


TENANT = "synthetic-enterprise"
AT = "2026-09-05T10:00:00Z"
# Hand-specified expectations, not obtained from the model or normalizer. These
# independently describe one source field, one relationship and first-use role.
EXPECTED = {
    "application-portfolio": ("lifecycle_stage", "active", "service_ref", "cmdb", "service-001", "business-service", None),
    "certificate-authorities": ("authority_role", "issuing_authority", "custody_ref", "hsm", "hsm-001", "record", "certificate_issuer"),
    "hsm": ("custody_mode", "non_exportable", "consumer_ref", "software-signing", "software-signing-001", "record", "key_custodian"),
    "api-and-mesh": ("workload_identity_mode", "mutual_tls", "certificate_ref", "pki", "cert-001", "record", "transport_key_exchange"),
    "network-telemetry": ("capture_mode", "handshake_metadata_only", "endpoint_ref", "tls", "endpoint-001", "record", "transport_key_exchange"),
    "ssh": ("hostname", "ssh-001.example", "credential_ref", "secrets", "secrets-001", "record", "transport_key_exchange"),
    "vpn": ("tunnel_protocol", "IKEv2", "certificate_ref", "pki", "cert-001", "record", "transport_key_exchange"),
    "source-build": ("revision", "synthetic-rev-001", "dependency_ref", "dependency-analysis", "dependency-analysis-001", "record", "application_signer"),
    "dependency-analysis": ("package_name", "synthetic-crypto-library", "build_ref", "source-build", "source-build-001", "record", "application_signer"),
    "software-signing": ("signature_format", "CMS", "custody_ref", "hsm", "hsm-001", "record", "code_signer"),
    "cloud-inventory": ("resource_class", "managed_runtime", "key_service_ref", "kms", "kms-001", "record", None),
    "kms": ("custody_mode", "service_managed_non_exportable", "data_ref", "data-governance", "data-governance-001", "record", "key_wrapper"),
    "secrets": ("credential_class", "ssh_certificate", "issuer_ref", "iam", "iam-001", "record", "credential_issuer"),
    "iam": ("token_format", "JWT", "custody_ref", "kms", "kms-001", "record", "token_issuer"),
    "databases": ("encryption_scope", "database_at_rest", "data_ref", "data-governance", "data-governance-001", "record", "data_encryptor"),
    "storage-backup": ("storage_class", "backup_archive", "key_service_ref", "kms", "kms-001", "record", "data_encryptor"),
    "data-governance": ("information_class", "synthetic_long_lived_records", "policy_ref", "policy-exceptions", "policy-exceptions-001", "record", None),
    "communications": ("communication_class", "dns", "authority_ref", "certificate-authorities", "certificate-authorities-001", "record", "dnssec_signer"),
    "endpoints": ("device_class", "workstation", "artifact_ref", "software-signing", "software-signing-001", "record", "firmware_verifier"),
    "embedded-ot": ("update_mechanism", "signed_offline_update", "vendor_ref", "vendor-assurance", "vendor-assurance-001", "record", "firmware_verifier"),
    "specialized-transactions": ("transaction_class", "synthetic_payment_message", "policy_ref", "policy-exceptions", "policy-exceptions-001", "record", "application_signer"),
    "mainframe": ("service_name", "synthetic-crypto-service-01", "custody_ref", "hsm", "hsm-001", "record", "key_custodian"),
    "policy-exceptions": ("policy_revision", "synthetic-policy-rev-01", "vendor_ref", "vendor-assurance", "vendor-assurance-001", "record", None),
    "vendor-assurance": ("product_label", "Synthetic Product A", "runtime_ref", "cloud-inventory", "cloud-inventory-001", "record", None),
}


@pytest.fixture(scope="module")
def pages():
    return {page["kind"]: page for page in generate_extended_pages()}


def normalize(page, *, tenant=TENANT, source=None, observed_at=AT):
    return normalize_extended_page(page["kind"], page["payload"], tenant_id=tenant,
                                   source_instance_id=source or page["source"], observed_at=observed_at)


def reseal(page):
    page["payload"]["content_sha256"] = extended_page_digest(page["payload"])
    return page


@pytest.mark.parametrize("kind", EXPECTED)
def test_independent_family_fields_relationships_and_use_roles(kind, pages):
    field, value, relation, target_source, native_id, namespace, role = EXPECTED[kind]
    row = normalize(pages[kind])[0]
    assert set(row) == {"subject_ref", "fact_type", "assertion_kind", "facts"}
    assert row["fact_type"] == kind.replace("-", "_")
    assert row["subject_ref"] == qualified_ref(TENANT, "synthetic-" + kind, kind + "-001")
    facts = row["facts"]
    assert facts[field] == value
    assert facts[relation] == qualified_ref(TENANT, "synthetic-" + target_source, native_id, namespace=namespace)
    assert facts["application_ref"] == qualified_ref(TENANT, "synthetic-cmdb", "app-001")
    assert facts[relation] in {link["target_ref"] for link in facts["relationships"]}
    if role is None:
        assert facts["cryptographic_uses"] == []
    else:
        assert facts["cryptographic_uses"][0]["role"] == role
    assert "reference_dialect_only" in facts["limitations"]
    assert "product_binding_unqualified" in facts["limitations"]


@pytest.mark.parametrize("kind", EXPECTED)
def test_each_family_consumes_changed_raw_field_without_pre_authored_output(kind, pages):
    field, original, *_ = EXPECTED[kind]
    page = copy.deepcopy(pages[kind])
    replacement = "ssh-changed.example" if field == "hostname" else "synthetic-changed"
    if field == "communication_class":
        replacement = "signed_email"
    page["payload"]["records"][0][field] = replacement
    updated = normalize(reseal(page))[0]
    baseline = normalize(pages[kind])[0]
    assert updated["facts"][field] == replacement != original
    assert updated["subject_ref"] == baseline["subject_ref"]
    assert updated != baseline


@pytest.mark.parametrize("kind", EXPECTED)
def test_missing_application_and_family_relations_remain_unknown(kind, pages):
    row = normalize(pages[kind])[2]
    assert row["facts"]["application_ref"] is None
    assert row["facts"]["relationships"] == []
    assert "missing_business_context" in row["facts"]["limitations"]
    assert "missing_relationship" in row["facts"]["limitations"]


def test_catalog_exact_complement_and_documented_authority_boundaries():
    profiles = extended_family_profiles()
    assert set(profiles) == set(EXPECTED)
    assert {profile["area_ref"] for profile in profiles.values()} == {f"area-{i:02d}" for i in range(1, 11)}
    for profile in profiles.values():
        assert profile["model_status"] == "synthetic_reference_dialects_not_vendor_wire_contracts"
        assert set(profile["product_binding"].values()) == {None}
        assert len(profile["qualification_gates"]) == 6
        for field in ("candidate_automation", "manual_boundary", "information_loss", "unsupported_capabilities", "recognition_examples"):
            assert profile[field]
        assert profile["examples_status"] == "recognition_examples_not_installed_or_selected"
    profiles["ssh"]["fields"].clear()
    assert extended_family_profiles()["ssh"]["fields"]


@pytest.mark.parametrize("seed,count", [(0, 12), (7, 36), (2**32 - 1, 60)])
def test_reproducible_bounded_pages_and_qualified_subjects(seed, count):
    pages = generate_extended_pages(seed, count)
    assert pages == generate_extended_pages(seed, count)
    assert len(pages) == 24
    rows = []
    for page in pages:
        assert len(page["payload"]["records"]) == 3
        assert len(json.dumps(page["payload"]).encode()) <= 256 * 1024
        assert page["complete"] is True and page["expected_cursor"] is None
        assert page["payload"]["next_cursor"] is None
        assert extended_page_digest(page["payload"]) == page["payload"]["content_sha256"]
        rows.extend(normalize(page))
    assert len(rows) == len({row["subject_ref"] for row in rows}) == 72


def test_seed_changes_only_deterministic_context_and_does_not_mutate_previous_call():
    first = generate_extended_pages(7, 36)
    original = copy.deepcopy(first)
    second = generate_extended_pages(8, 36)
    assert first != second
    second[0]["payload"]["records"][0]["name"] = "Synthetic changed"
    assert first == original == generate_extended_pages(7, 36)


@pytest.mark.parametrize("seed,count", [(True, 36), (-1, 36), (2**32, 36), (7, False), (7, 0), (7, 11), (7, 61), ("7", 36)])
def test_generator_rejects_unbounded_or_ambiguous_parameters(seed, count):
    with pytest.raises(ValueError):
        generate_extended_pages(seed, count)


def test_ssh_exchange_and_classical_signature_are_distinct_and_use_basis_not_row_basis(pages):
    row = normalize(pages["ssh"])[1]
    assert row["assertion_kind"] == "configured"
    exchange, signature = row["facts"]["cryptographic_uses"]
    assert (exchange["purpose"], exchange["algorithm"], exchange["basis"]) == ("key_establishment", "mlkem768x25519-sha256", "configured")
    assert (signature["purpose"], signature["algorithm"], signature["basis"]) == ("digital_signature", "rsa-sha2-512", "observed")
    unknown = normalize(pages["ssh"])[2]["facts"]
    assert len(unknown["cryptographic_uses"]) == 1
    assert unknown["cryptographic_uses"][0]["algorithm"] is None
    assert "cryptographic_parameters_unknown" in unknown["limitations"]
    assert not any("ready" in key for key in row["facts"])


@pytest.mark.parametrize("kind", ["hsm", "kms", "mainframe", "dependency-analysis", "vendor-assurance"])
def test_capabilities_never_create_uses(kind, pages):
    index = 0 if kind == "vendor-assurance" else 2
    facts = normalize(pages[kind])[index]["facts"]
    assert facts["cryptographic_uses"] == []
    assert "capability_not_use" in facts["limitations"]
    if kind == "dependency-analysis":
        assert facts["package_version"] == "3.5.4"
        assert facts["declared_capabilities"] == ["ML-DSA-65", "ML-KEM-768"]
        assert "package_presence_not_use" in facts["limitations"]


def test_each_explicit_crypto_field_is_consumed_not_derived_from_version(pages):
    page = copy.deepcopy(pages["ssh"])
    raw = page["payload"]["records"][0]
    raw.update(key_exchange_algorithm="X25519", key_exchange_basis="vendor_reported", key_exchange_key_bits=256,
               key_exchange_protocol_version="synthetic-protocol", key_exchange_trust_until="2031-09-05")
    use = normalize(reseal(page))[0]["facts"]["cryptographic_uses"][0]
    assert use == {"purpose": "key_establishment", "role": "transport_key_exchange", "algorithm": "X25519", "basis": "vendor_reported",
                   "parameters": {"key_bits": 256, "protocol_version": "synthetic-protocol"}, "protected_data_ref": None,
                   "trust_until": "2031-09-05"}


def test_symmetric_use_and_confidentiality_trust_retention_are_separate(pages):
    database = normalize(pages["databases"])[0]["facts"]
    use = database["cryptographic_uses"][0]
    assert (use["purpose"], use["algorithm"], use["parameters"]["key_bits"]) == ("data_encryption", "AES-256-GCM", 256)
    assert use["protected_data_ref"] == qualified_ref(TENANT, "synthetic-data-governance", "data-governance-001")
    governance = normalize(pages["data-governance"])[0]["facts"]
    assert governance["confidentiality_until"] == "2041-09-05"
    assert governance["integrity_until"] == "2046-09-05"
    archive = normalize(pages["storage-backup"])[0]["facts"]
    assert archive["retention_until"] == "2041-09-05" and "confidentiality_until" not in archive
    assert use["trust_until"] is None


def test_dns_email_document_have_distinct_cases_and_unknown_stays_unknown(pages):
    facts = [row["facts"] for row in normalize(pages["communications"])]
    assert [row["communication_class"] for row in facts] == ["dns", "signed_email", "document_exchange"]
    assert [row["cryptographic_uses"][0]["role"] for row in facts] == ["dnssec_signer", "email_signer", "document_signer"]
    assert [row["cryptographic_uses"][0]["algorithm"] for row in facts] == ["RSASHA256", "ECDSA", None]
    assert all(len(row["cryptographic_uses"]) == 1 for row in facts)


def test_governance_and_vendor_states_are_not_authority_or_independent_verification(pages):
    policy = normalize(pages["policy-exceptions"])[0]["facts"]
    assert policy["review_state"] == "synthetic_proposed"
    assert "reported_policy_not_authorization" in policy["limitations"]
    vendor = normalize(pages["vendor-assurance"])[0]["facts"]
    assert vendor["independent_validation_state"] == "not_tested"
    assert "vendor_claim_not_independently_verified" in vendor["limitations"]
    assert vendor["cryptographic_uses"] == policy["cryptographic_uses"] == []


@pytest.mark.parametrize("kind,field,value", [
    ("data-governance", "classification_state", "accepted"),
    ("specialized-transactions", "specialist_review_state", "authorized"),
])
def test_synthetic_state_cannot_claim_human_acceptance(kind, field, value, pages):
    page = copy.deepcopy(pages[kind])
    page["payload"]["records"][0][field] = value
    with pytest.raises(SourceContractError, match="invalid_extended_source_page"):
        normalize(reseal(page))


@pytest.mark.parametrize("kind,field,value,limitation", [
    ("policy-exceptions", "review_state", "approved", "reported_policy_not_authorization"),
    ("vendor-assurance", "independent_validation_state", "verified", "vendor_claim_not_independently_verified"),
])
def test_reported_approved_or_verified_states_are_preserved_without_authority(kind, field, value, limitation, pages):
    page = copy.deepcopy(pages[kind])
    page["payload"]["records"][0][field] = value
    facts = normalize(reseal(page))[0]["facts"]
    assert facts[field] == value
    assert limitation in facts["limitations"]
    assert facts["cryptographic_uses"] == []
    assert "execution_authorized" not in facts and "canonical_approval" not in facts
    page["payload"]["records"][0]["execution_authorized"] = True
    with pytest.raises(SourceContractError):
        normalize(reseal(page))


@pytest.mark.parametrize("seed,count", [(0, 12), (7, 36), (2**32 - 1, 60)])
def test_core_relation_targets_share_the_actual_application_cohort(seed, count):
    from tools.pqc_reference.synthetic_estate import generate_estate
    from workers.pqc.assessment_sources import normalize_page

    core = generate_estate(seed=seed, application_count=count)
    core_records = {}
    for page in core["pages"]:
        for row in normalize_page(page["kind"], page["payload"], tenant_id=TENANT,
                                  source_instance_id=page["source"], observed_at=page["observed_at"]):
            core_records[row["subject_ref"]] = row
    for page in generate_extended_pages(seed, count):
        for row in normalize(page)[:2]:
            facts = row["facts"]
            for relation in facts["relationships"]:
                target = core_records.get(relation["target_ref"])
                if target and target["fact_type"] in {"certificate", "tls_endpoint"}:
                    assert target["facts"]["application_ref"] == facts["application_ref"]
            if page["kind"] == "application-portfolio":
                application = core_records[facts["application_ref"]]
                assert facts["service_ref"] == application["facts"]["business_service_ref"]


def test_duplicates_and_conflicts_retain_identity_and_values_for_ledger(pages):
    page = copy.deepcopy(pages["ssh"])
    first = copy.deepcopy(page["payload"]["records"][0])
    altered = copy.deepcopy(first)
    altered["key_exchange_algorithm"] = "mlkem768x25519-sha256"
    page["payload"]["records"] = [first, copy.deepcopy(first), altered]
    rows = normalize(reseal(page))
    assert rows[0] == rows[1]
    assert rows[0] != rows[2]
    assert len({row["subject_ref"] for row in rows}) == 1


def test_tenant_separation_and_payload_boundary_binding(pages):
    page = copy.deepcopy(pages["ssh"])
    with pytest.raises(SourceContractError, match="boundary_mismatch"):
        normalize(page, tenant="synthetic-other")
    page["payload"]["tenant_id"] = "synthetic-other"
    changed = normalize(reseal(page), tenant="synthetic-other")[0]
    original = normalize(pages["ssh"])[0]
    assert changed["subject_ref"] != original["subject_ref"]
    assert changed["facts"]["application_ref"] != original["facts"]["application_ref"]
    assert changed["facts"]["credential_ref"] != original["facts"]["credential_ref"]
    with pytest.raises(SourceContractError, match="boundary"):
        normalize(page, source="synthetic-other-source")


def test_relation_changes_are_consumed_and_orphans_not_invented(pages):
    page = copy.deepcopy(pages["ssh"])
    page["payload"]["records"][0]["credential_id"] = "secrets-unmapped-009"
    facts = normalize(reseal(page))[0]["facts"]
    assert facts["credential_ref"] == qualified_ref(TENANT, "synthetic-secrets", "secrets-unmapped-009")
    assert facts["credential_ref"] in {link["target_ref"] for link in facts["relationships"]}


@pytest.mark.parametrize("field,value", [
    ("credential_id", "kms-001"), ("credential_id", "real-secret-native-id"),
    ("credential_id", {"tenant_id": "other", "id": "secrets-001"}),
    ("application_id", "https://private.invalid/record"), ("hostname", "real-host.invalid"),
    ("key_exchange_present", 1), ("key_exchange_key_bits", True), ("key_exchange_key_bits", -1),
    ("key_exchange_key_bits", 65537), ("key_exchange_basis", "independently_verified"),
    ("key_exchange_basis", None), ("evidence_basis", "accepted"), ("name", "Synthetic bad\nname"),
    ("name", "Synthetic password:do-not-echo"), ("key_exchange_algorithm", "bearer:do-not-echo"),
    ("key_exchange_algorithm", "-----BEGIN " + "PRIVATE KEY-----"),
    ("key_exchange_algorithm", "https://private.invalid/material"),
    ("key_exchange_trust_until", "2026-02-30"), ("key_exchange_trust_until", "tomorrow"),
    ("id", "ssh-001:other-tenant"),
])
def test_closed_types_relations_dates_and_sensitive_markers_rejected(field, value, pages):
    page = copy.deepcopy(pages["ssh"])
    page["payload"]["records"][0][field] = value
    with pytest.raises(SourceContractError) as error:
        normalize(reseal(page))
    assert "do-not-echo" not in str(error.value)
    assert "private.invalid" not in str(error.value)


@pytest.mark.parametrize("key", ["password", "token", "private_key", "custom_metadata", "payload", "source_instance_id", "tenant_id", "relationships", "cryptographic_uses"])
def test_unknown_record_fields_rejected_even_with_valid_content_hash(key, pages):
    page = copy.deepcopy(pages["ssh"])
    page["payload"]["records"][0][key] = "do-not-echo"
    with pytest.raises(SourceContractError) as error:
        normalize(reseal(page))
    assert "do-not-echo" not in str(error.value)


@pytest.mark.parametrize("field,value", [("schema_version", "unsupported-v2"), ("synthetic", False),
                                        ("kind", "vpn"), ("source_instance_id", "synthetic-vpn"),
                                        ("next_cursor", "https://private.invalid/next"), ("arbitrary", "unrecognized")])
def test_unknown_page_version_fields_and_sources_rejected(field, value, pages):
    page = copy.deepcopy(pages["ssh"])
    page["payload"][field] = value
    with pytest.raises(SourceContractError):
        normalize(reseal(page))


def test_missing_required_fields_and_tampering_rejected(pages):
    page = copy.deepcopy(pages["ssh"])
    page["payload"]["records"][0]["key_exchange_algorithm"] = "X25519"
    with pytest.raises(SourceContractError, match="digest_mismatch"):
        normalize(page)
    del page["payload"]["records"][0]["hostname"]
    with pytest.raises(SourceContractError, match="invalid_extended_source_page"):
        normalize(reseal(page))


def test_absent_use_cannot_hide_an_algorithm_or_basis(pages):
    page = copy.deepcopy(pages["hsm"])
    page["payload"]["records"][2]["recorded_operation_algorithm"] = "ML-DSA-65"
    with pytest.raises(SourceContractError, match="absent_use_has_assertion"):
        normalize(reseal(page))


def test_empty_page_is_valid_and_bounded_inputs_fail_closed(pages):
    page = copy.deepcopy(pages["ssh"])
    page["payload"]["records"] = []
    assert normalize(reseal(page)) == []
    page["payload"]["records"] = [copy.deepcopy(pages["ssh"]["payload"]["records"][0])] * 129
    with pytest.raises(SourceContractError, match="budget"):
        normalize(page)
    for value in ("x" * 257, 2**70, float("nan"), {"deep": {"deep": {"deep": {"deep": {"deep": {"deep": {"deep": {}}}}}}}}):
        page = copy.deepcopy(pages["ssh"])
        page["payload"]["records"][0]["hostname"] = value
        with pytest.raises(SourceContractError):
            normalize(page)


@pytest.mark.parametrize("timestamp", ["2026-02-30T10:00:00Z", "2026-09-05", "2026-09-05T10:00:00", "2026-09-05T10:00:00+00:00", None])
def test_observation_timestamp_requires_valid_utc(timestamp, pages):
    with pytest.raises(SourceContractError, match="invalid_observation_time"):
        normalize(pages["ssh"], observed_at=timestamp)


def test_no_network_during_generation_or_normalization(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("network_use_forbidden")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    assert len(generate_extended_pages()) == 24


@pytest.mark.parametrize("kind,field", [("kms", "key_reference"), ("secrets", "credential_reference")])
def test_custody_references_are_synthetic_metadata_not_untyped_secret_values(kind, field, pages):
    page = copy.deepcopy(pages[kind])
    page["payload"]["records"][0][field] = "opaque-real-credential-looking-value"
    with pytest.raises(SourceContractError):
        normalize(reseal(page))
