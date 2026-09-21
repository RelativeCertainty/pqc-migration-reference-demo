"""Deterministic employer-neutral estate for Phase 1/2 report development.

The default core cohort preserves the CMDB, PKI and TLS reference dialects.
The explicit all-family scope also exercises 24 closed source-family models.
Neither scope proves installed products, enterprise coverage, commercial APIs,
approvals or migration authorizations.
Generation is bounded, offline and side-effect free; it creates no credentials.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from workers.pqc.assessment_sources import normalize_page, validate_catalog


SCHEMA_VERSION = "pba.pqc.synthetic-estate.v1"
AS_OF = "2026-09-05T12:00:00Z"
FRESH_AT = "2026-09-05T10:00:00Z"
STALE_AT = "2026-07-01T10:00:00Z"
TENANT_ID = "synthetic-enterprise"
PAGE_SIZE = 12
CATALOG_PATH = Path(__file__).resolve().parents[2] / "integrations/pqc/reference_assessment/catalog.v1.json"
KIND_TO_FAMILY = {"cmdb": "cmdb", "pki": "certificate-lifecycle", "tls": "traffic-termination"}
SERVICES = ("Records", "Identity", "Fulfillment", "Analytics", "Document Exchange", "Billing", "Internal Tools", "Archive")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def estate_digest(estate: dict[str, Any]) -> str:
    """Hash the complete snapshot except its self-referential digest field."""
    return hashlib.sha256(_canonical({key: value for key, value in estate.items() if key != "content_sha256"})).hexdigest()


def _choose(seed: int, label: str, choices: tuple) -> Any:
    # Hash-based selection does not depend on Python's random generator version
    # or on the order in which additional scenarios are later generated.
    value = hashlib.sha256(f"{seed}:{label}".encode("ascii")).digest()
    return choices[int.from_bytes(value[:8], "big") % len(choices)]


def _record(kind: str, native_id: str) -> dict[str, str]:
    return {"kind": kind, "source": f"synthetic-{kind}", "native_id": native_id}


def generate_estate(
    seed: int = 7, application_count: int = 36, *, source_scope: str = "core"
) -> dict[str, Any]:
    """Return raw pages, candidate source profiles and reproducible scenario facts.

    Default snapshot: 36 applications, 72 unique certificates and 72 unique TLS
    endpoints. One duplicate input and one conflicting endpoint revision are
    intentional. Core mode generates at most 26 pages and 302 raw rows for
    60 apps; all-family mode adds 24 pages and 72 raw rows.
    ``complete`` describes this synthetic collection receipt, never enterprise
    completeness. All source pages are valid inputs to ``normalize_page``.
    """
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("invalid_synthetic_seed")
    if type(application_count) is not int or not 12 <= application_count <= 60:
        raise ValueError("synthetic_application_count_must_be_12_to_60")
    if source_scope not in ("core", "all"):
        raise ValueError("invalid_synthetic_source_scope")
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    validate_catalog(catalog)
    records: dict[str, list[dict[str, Any]]] = {"cmdb": [], "pki": [], "tls": []}
    scenarios: list[dict[str, Any]] = []

    def scenario(identifier: str, description: str, refs: list[dict[str, str]], codes: list[str],
                 pages: list[dict[str, str]] | None = None) -> None:
        scenarios.append({"id": identifier, "description": description, "affected_records": refs,
                          "source_pages": pages or [], "expected_limitation_codes": codes})

    for index in range(1, application_count + 1):
        service_index = (index - 1) % len(SERVICES)
        app_id = f"app-{index:03d}"
        records["cmdb"].append({
            "id": app_id, "evidence_basis": "observed",
            "name": f"Synthetic {SERVICES[service_index]} Application {index:03d}",
            "business_service_id": f"service-{service_index + 1:03d}",
            "owner_id": f"team-{service_index + 1:03d}",
            "criticality": _choose(seed, app_id + ":criticality", ("critical", "high", "high", "medium", "low")),
            "environment": _choose(seed, app_id + ":environment", ("synthetic_lab", "synthetic_development")),
            "confidentiality_until": f"{_choose(seed, app_id + ':lifetime', (2027, 2029, 2033, 2041))}-09-05",
        })
        for slot in range(2):
            serial = (index - 1) * 2 + slot + 1
            cert_id, endpoint_id = f"cert-{serial:03d}", f"endpoint-{serial:03d}"
            hostname = f"app-{index:03d}-{'edge' if slot == 0 else 'internal'}.example"
            algorithm, signature, bits = _choose(seed, cert_id + ":key", (
                ("RSA", "sha256WithRSAEncryption", 2048),
                ("RSA", "sha384WithRSAEncryption", 3072),
                ("EC", "ecdsa-with-SHA256", 256),
                ("EC", "ecdsa-with-SHA384", 384),
            ))
            records["pki"].append({
                "id": cert_id, "evidence_basis": "observed", "application_id": app_id,
                "application_source": "synthetic-cmdb", "common_name": hostname,
                "signature_algorithm": signature, "public_key_algorithm": algorithm,
                "public_key_bits": bits, "valid_until": f"2027-{1 + serial % 12:02d}-15T00:00:00Z",
            })
            records["tls"].append({
                "id": endpoint_id, "evidence_basis": "observed", "application_id": app_id,
                "application_source": "synthetic-cmdb", "certificate_id": cert_id,
                "certificate_source": "synthetic-pki", "hostname": hostname,
                "port": 443 if slot == 0 else 8443,
                "protocol": _choose(seed, endpoint_id + ":protocol", ("TLSv1.3", "TLSv1.3", "TLSv1.2")),
                "key_exchange_group": _choose(seed, endpoint_id + ":group", ("X25519", "X25519", "secp256r1")),
                "certificate_signature_algorithm": signature,
            })

    # Fixed scenarios ensure meaningful report branches for every supported seed.
    for index in (0, 7):
        records["cmdb"][index]["owner_id"] = None
    scenario("missing-owners", "Two synthetic applications have no attributable owner route.",
             [_record("cmdb", records["cmdb"][index]["id"]) for index in (0, 7)], ["missing_business_context"])
    records["cmdb"][1]["business_service_id"] = None
    scenario("missing-service-context", "An application has no business-service association.",
             [_record("cmdb", "app-002")], ["missing_business_context"])
    records["cmdb"][2]["confidentiality_until"] = None
    scenario("unknown-information-lifetime", "Required confidentiality lifetime has not been established.",
             [_record("cmdb", "app-003")], ["missing_business_context"])
    records["cmdb"][3]["criticality"] = "unknown"
    scenario("unknown-criticality", "Business criticality remains unknown rather than being assigned a low rating.",
             [_record("cmdb", "app-004")], ["missing_business_context"])

    records["pki"][4]["application_id"] = "app-unmapped-001"
    records["tls"][4]["application_id"] = "app-unmapped-001"
    scenario("orphan-application", "Certificate and endpoint cite an application absent from the synthetic CMDB snapshot.",
             [_record("pki", "cert-005"), _record("tls", "endpoint-005")], ["unresolved_dependency"])
    for kind in ("pki", "tls"):
        records[kind][5].update(application_id=None, application_source=None)
    scenario("missing-application-links", "Absent source relationships remain unknown instead of being inferred from hostnames.",
             [_record("pki", "cert-006"), _record("tls", "endpoint-006")], ["missing_relationship"])
    records["tls"][6]["certificate_id"] = "cert-unmapped-001"
    scenario("orphan-certificate", "An endpoint references a certificate absent from the certificate snapshot.",
             [_record("tls", "endpoint-007")], ["unresolved_dependency"])
    records["tls"][7].update(certificate_id=None, certificate_source=None)
    scenario("missing-certificate-link", "An endpoint lacks an attributable certificate relationship.",
             [_record("tls", "endpoint-008")], ["missing_relationship"])

    records["tls"][8].update(protocol="TLSv1.3", key_exchange_group="X25519", evidence_basis="observed")
    for index, basis in ((9, "configured"), (10, "observed"), (11, "vendor_reported")):
        records["tls"][index].update(protocol="TLSv1.3", key_exchange_group="X25519MLKEM768", evidence_basis=basis)
        scenario(basis.replace("_", "-") + "-hybrid", "Synthetic hybrid key establishment is " + basis.replace("_", " ") + "; classical certificate authentication is a separate fact.",
                 [_record("tls", records["tls"][index]["id"])], [])
    records["pki"][12].update(signature_algorithm=None, public_key_algorithm=None, public_key_bits=None)
    records["tls"][12].update(key_exchange_group=None, certificate_signature_algorithm=None)
    scenario("unknown-cryptographic-parameters", "Two source records omit cryptographic parameters; no algorithm is invented.",
             [_record("pki", "cert-013"), _record("tls", "endpoint-013")], ["cryptographic_parameters_unknown"])
    scenario("classical-signatures-remain", "Hybrid TLS entries retain their separately observed classical certificate signatures.",
             [_record("pki", "cert-010"), _record("pki", "cert-011"), _record("pki", "cert-012")], [])

    pages: list[dict[str, Any]] = []
    last_cursor: dict[str, str | None] = {kind: None for kind in records}
    for kind, rows in records.items():
        for offset in range(0, len(rows), PAGE_SIZE):
            number = offset // PAGE_SIZE + 1
            page_id = f"page-{number:03d}"
            selected = copy.deepcopy(rows[offset:offset + PAGE_SIZE])
            duplicate = kind == "pki" and number == 1
            if duplicate:
                selected.append(copy.deepcopy(selected[0]))
            stale = (kind == "pki" and number == 1) or (kind == "tls" and number == 2)
            partial = kind in {"pki", "tls"} and offset + PAGE_SIZE >= len(rows)
            pages.append({
                "source": f"synthetic-{kind}", "page_id": page_id, "kind": kind,
                "payload": {"schema_version": "pba.pqc.reference-source-page.v1", "kind": kind,
                            "synthetic": True, "records": selected},
                "observed_at": STALE_AT if stale else FRESH_AT,
                "complete": not partial, "expected_cursor": last_cursor[kind],
            })
            last_cursor[kind] = page_id
            page_ref = [{"source": f"synthetic-{kind}", "page_id": page_id}]
            if stale:
                scenario(f"stale-{kind}-page", "A retained synthetic source page is older than the 30-day reference freshness window.",
                         [_record(kind, row["id"]) for row in rows[offset:offset + PAGE_SIZE]], ["stale_evidence"], page_ref)
            if partial:
                scenario(f"partial-{kind}-collection", "The collector explicitly reports an incomplete source collection; no whole-estate denominator is available.",
                         [], ["partial_source_collection"], page_ref)
            if duplicate:
                scenario("duplicate-raw-record", "An identical source record repeats within a page; custody retains the raw duplicate and normalization storage deduplicates it.",
                         [_record("pki", "cert-001")], [], page_ref)

    conflict = copy.deepcopy(records["tls"][8])
    conflict["key_exchange_group"] = "X25519MLKEM768"
    conflict["evidence_basis"] = "configured"
    conflict_page_id = f"page-{len(records['tls']) // PAGE_SIZE + bool(len(records['tls']) % PAGE_SIZE) + 1:03d}"
    pages.append({
        "source": "synthetic-tls", "page_id": conflict_page_id, "kind": "tls",
        "payload": {"schema_version": "pba.pqc.reference-source-page.v1", "kind": "tls", "synthetic": True, "records": [conflict]},
        "observed_at": "2026-09-05T11:00:00Z", "complete": False, "expected_cursor": last_cursor["tls"],
    })
    scenario("conflicting-configuration-and-observation", "One endpoint has observed classical negotiation and a separately configured hybrid claim; both revisions remain visible.",
             [_record("tls", "endpoint-009")], ["conflicting_observations"],
             [{"source": "synthetic-tls", "page_id": conflict_page_id}])

    kind_to_family = dict(KIND_TO_FAMILY)
    extended_profiles = {}
    if source_scope == "all":
        from tools.pqc_reference.extended_estate import generate_extended_pages
        from workers.pqc.extended_sources import extended_family_profiles

        extended_profiles = extended_family_profiles()
        extra_pages = generate_extended_pages(seed, application_count)
        pages.extend(extra_pages)
        kind_to_family.update({kind: kind for kind in extended_profiles})
        for page in extra_pages:
            scenario(
                f"extended-{page['kind']}-model",
                "Source-family reference records exercise explicit metadata, relationships and unknowns; not a vendor API qualification.",
                [], [], [{"source": page["source"], "page_id": page["page_id"]}],
            )

    raw_counts = Counter()
    normalized_counts = Counter()
    subject_ids: dict[str, set[str]] = defaultdict(set)
    assertion_counts = Counter()
    for page in pages:
        if len(_canonical(page["payload"])) > 256 * 1024:
            raise ValueError("synthetic_page_budget_exceeded")
        normalized = normalize_page(page["kind"], page["payload"], tenant_id=TENANT_ID,
                                    source_instance_id=page["source"], observed_at=page["observed_at"])
        unique = {_canonical(row): row for row in normalized}
        raw_counts[page["kind"]] += len(page["payload"]["records"])
        normalized_counts[page["kind"]] += len(unique)
        for row in unique.values():
            subject_ids[page["kind"]].add(row["subject_ref"])
            assertion_counts[row["assertion_kind"]] += 1
    if len(pages) > (50 if source_scope == "all" else 26):
        raise ValueError("synthetic_page_budget_exceeded")

    profiles = []
    family_to_kind = {family: kind for kind, family in kind_to_family.items()}
    for family in catalog["source_families"]:
        kind = family_to_kind.get(family["id"])
        profile = {
            "family_id": family["id"], "area_ref": family["area_ref"], "name": family["name"],
            "recognition_examples": family["recognition_examples"], "examples_status": catalog["examples_status"],
            "route_status": "synthetic_fixture_available" if kind else "candidate_source_route",
            "normalization_support": "reference_dialect_only" if kind else "not_implemented",
            "source_instance_ids": [f"synthetic-{kind}"] if kind else [],
            "evidence_targets": family["evidence_targets"],
            "synthetic_record_count": raw_counts[kind] if kind else 0,
            "product_binding_status": "unconfirmed",
        }
        if kind in extended_profiles:
            profile["model_contract"] = extended_profiles[kind]
            profile["fact_type"] = extended_profiles[kind]["fact_type"]
        profiles.append(profile)
    result = {
        "schema_version": SCHEMA_VERSION, "synthetic": True,
        "classification": "synthetic_public_safe", "tenant_id": TENANT_ID, "as_of": AS_OF,
        "generator": {"version": 2 if source_scope == "all" else 1,
                      "seed": seed, "application_count": application_count,
                      "source_scope": source_scope},
        "limitations": ["Not enterprise data or measured enterprise coverage.",
                        ("All 27 families contain synthetic model records; no commercial-product adapter is qualified."
                         if source_scope == "all" else "Only three employer-neutral reference dialects contain normalized observations."),
                        "Source profiles do not prove installed products, working commercial APIs or authorized source routes.",
                        "Configured, vendor-reported and observed facts are distinct; no owner approval is generated."],
        "pages": pages, "source_profiles": profiles, "scenario_catalog": scenarios,
        "expectations": {
            "page_count": len(pages), "raw_record_counts": dict(raw_counts),
            "normalized_observation_counts": dict(normalized_counts),
            "unique_subject_counts": {kind: len(refs) for kind, refs in subject_ids.items()},
            "unique_subjects": sum(len(refs) for refs in subject_ids.values()),
            "normalized_observations": sum(normalized_counts.values()),
            "duplicate_raw_records": sum(raw_counts.values()) - sum(normalized_counts.values()),
            "conflicting_subjects": 1, "assertion_basis_counts": dict(assertion_counts),
            "source_families": len(profiles), "estate_areas": len({item["area_ref"] for item in profiles}),
            "reference_dialect_families": len(kind_to_family), "unconnected_source_families": len(profiles) - len(kind_to_family),
            "qualified_product_adapters": 0, "enterprise_connections": 0,
            "enterprise_coverage_percent": None,
            "minimum_limitation_codes": sorted({code for item in scenarios for code in item["expected_limitation_codes"]}
                                               | {"enterprise_coverage_denominator_unavailable"}),
        },
    }
    result["content_sha256"] = estate_digest(result)
    return result
