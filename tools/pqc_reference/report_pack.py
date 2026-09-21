"""Deterministic, source-bound synthetic Phase 1/2 report projections.

No collection, store mutation, acceptance, risk authority, or source-system
execution happens here. The caller persists the returned pack and renders its
Markdown through the approved office/HTML handoff path. The detailed JSON is
the complete drill-through companion; reader IDs are abbreviated only in prose.
"""

from __future__ import annotations

import copy
from collections import Counter, defaultdict
from datetime import date
from typing import Any

from workers.pqc.assessment_sources import normalize_page

from .assessment_store import digest, record_dependencies, timestamp


METHOD = {
    "id": "synthetic-evidence-first-triage",
    "version": "1.0.0",
    "status": "illustrative_not_enterprise_approved",
    "numerical_scoring": False,
    "risk_rating_assigned": False,
    "long_lived_information_threshold_days": 1825,
    "rules": [
        {
            "id": "TRIAGE-01",
            "rule": "Conflicting or missing cryptographic facts require evidence reconciliation; do not select a preferred variant.",
        },
        {
            "id": "TRIAGE-02",
            "rule": "Configured and vendor-reported values are not negotiated-behavior observations.",
        },
        {
            "id": "TRIAGE-03",
            "rule": "Stale observations and unresolved dependencies require current evidence before pattern design.",
        },
        {
            "id": "TRIAGE-04",
            "rule": "Business context is joined only through attributable application relationships. Confidentiality lifetime informs key establishment; it does not establish signature trust/validation lifetime, which remains unknown in this source dialect.",
        },
        {
            "id": "TRIAGE-05",
            "rule": "Listed classical mechanisms are candidates for migration-method review, not automatically rated risks or approved changes.",
        },
        {
            "id": "TRIAGE-06",
            "rule": "Hybrid TLS key exchange does not establish post-quantum certificate authentication.",
        },
        {
            "id": "TRIAGE-07",
            "rule": "A recorded post-quantum signature mechanism requires independent interoperability and trust-chain verification; it does not establish asset-wide readiness.",
        },
        {
            "id": "TRIAGE-08",
            "rule": "Migration feasibility, vendor support, human acceptance and execution authorization are independent and remain unassessed unless separately evidenced.",
        },
    ],
}

_KINDS = {"cmdb": "application", "pki": "certificate", "tls": "tls_endpoint"}
_FAMILIES = {
    "cmdb": "cmdb",
    "pki": "certificate-lifecycle",
    "tls": "traffic-termination",
}
_HYBRID = {"x25519mlkem768", "secp256r1mlkem768", "secp384r1mlkem1024"}
_CLASSICAL = {
    "x25519",
    "secp256r1",
    "secp384r1",
    "secp521r1",
    "prime256v1",
    "rsa",
    "rsa-sha256",
    "sha256withrsaencryption",
    "sha384withrsaencryption",
    "rsassa-pss",
    "rsa-pss",
    "rsa-pss-sha256",
    "ecdsa",
    "ec",
    "ecdsa-with-sha256",
    "ecdsa-with-sha384",
    "ed25519",
    "ed448",
    "rsa-oaep",
    "rs256",
    "es256",
    "rsasha256",
    "modp-2048",
}
_PQC_SIGNATURES = {
    "ml-dsa-44",
    "ml-dsa-65",
    "ml-dsa-87",
    "slh-dsa-sha2-128s",
    "slh-dsa-shake-128s",
}
_ALLOWED_BASES = {"observed", "configured", "vendor_reported"}
_SIGNATURE_PURPOSES = {
    "authentication",
    "digital_signature",
    "credential_authentication",
}
_CONFIDENTIALITY_PURPOSES = {"key_establishment", "data_encryption", "key_wrapping"}
_SYMMETRIC = {
    "aes",
    "aes-128",
    "aes-192",
    "aes-256",
    "aes-128-gcm",
    "aes-256-gcm",
    "aes-256-cbc",
    "aes-256-kw",
    "aes-256-xts",
    "chacha20-poly1305",
}
_HASHES = {
    "sha-256",
    "sha-384",
    "sha-512",
    "sha256",
    "sha384",
    "sha512",
    "hmac-sha256",
    "hmac-sha-256",
}
_SSH_HYBRID = {
    "mlkem768x25519-sha256",
    "sntrup761x25519-sha512",
    "sntrup761x25519-sha512@openssh.com",
}
_SSH_CLASSICAL = {
    "curve25519-sha256",
    "curve25519-sha256@libssh.org",
    "diffie-hellman-group14-sha256",
    "ecdh-sha2-nistp256",
    "ssh-rsa",
    "rsa-sha2-256",
    "rsa-sha2-512",
    "ssh-ed25519",
}


def _method_for(baseline):
    method = copy.deepcopy(METHOD)
    if any("cryptographic_uses" in row["facts"] for row in baseline["observations"]):
        method["version"] = "1.1.0"
        method["rules"] += [
            {
                "id": "TRIAGE-09",
                "rule": "Symmetric encryption, key wrapping and hashes require purpose/parameter review; they are not classified as quantum-vulnerable public-key mechanisms merely because they use cryptography.",
            },
            {
                "id": "TRIAGE-10",
                "rule": "Package, platform, policy and vendor capability metadata is contextual evidence, not proof of cryptographic use, accepted risk, human approval or completed migration.",
            },
            {
                "id": "TRIAGE-11",
                "rule": "An explicitly reported use retains its own basis, parameters, protected-data relationship and trust lifetime; a configured or vendor-reported use is not observed negotiation.",
            },
        ]
        method["references"] = [
            {
                "id": "nist-pqc-faq-aes",
                "title": "NIST PQC FAQs — symmetric-key migration discussion",
                "url": "https://csrc.nist.gov/projects/post-quantum-cryptography/faqs",
                "reviewed_on": "2026-09-05",
                "supports": "Symmetric-key and hash transition questions are distinct from replacing quantum-vulnerable public-key mechanisms; this illustrative classifier does not certify any implementation.",
            },
            {
                "id": "openssh-pqc",
                "title": "OpenSSH Post-Quantum Cryptography",
                "url": "https://www.openssh.org/pq.html",
                "reviewed_on": "2026-09-05",
                "supports": "Hybrid SSH key agreement and signature authentication are different protocol functions; source-reported support is not proof of negotiated behavior.",
            },
        ]
    return method


def _kind_catalog(estate):
    kinds, families = dict(_KINDS), dict(_FAMILIES)
    # The core fixture retains its previous three-dialect declaration. Extended
    # capability is admitted only by a matched, versioned extension profile.
    declared = [row for row in estate["source_profiles"] if row.get("fact_type")]
    if declared:
        from workers.pqc.extended_sources import extended_family_profiles

        supported = extended_family_profiles()
        for profile in declared:
            family = profile["family_id"]
            if family in supported:
                fact_type = supported[family]["fact_type"]
                if profile["fact_type"] != fact_type:
                    raise ReportProjectionError("profile_fact_type_mismatch")
                if profile.get("model_contract") != supported[family]:
                    raise ReportProjectionError("profile_model_contract_mismatch")
                kinds[family], families[family] = fact_type, family
    return kinds, families


_PHASE1_CHECKLIST = [
    (
        "assessment_boundary",
        "Confirm the applications, environments and source populations included and excluded.",
    ),
    (
        "source_authority",
        "Name accountable source owners and approve read-only access, collection and custody routes.",
    ),
    (
        "evidence_acceptance",
        "Agree admissible evidence, freshness and conflict-resolution rules.",
    ),
    (
        "coverage_limitations",
        "Review missing sources, unresolved links and the unavailable whole-estate denominator.",
    ),
    (
        "inventory_handoff",
        "Accept or explicitly qualify this exact inventory/dependency snapshot for Phase 2 input.",
    ),
    (
        "analysis_method",
        "Approve a versioned enterprise assessment method before enterprise risk ratings are published.",
    ),
]


class ReportProjectionError(ValueError):
    """A fixed error code only; never returns input bodies or evidence material."""


def _without(value: dict[str, Any], field: str) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != field}


def _sorted_unique(values: list[str]) -> list[str]:
    return sorted(set(values))


def _validate_inputs(baseline, phase1, phase2, estate):
    try:
        for value in (baseline, phase1, phase2, estate):
            if not isinstance(value, dict) or value["synthetic"] is not True:
                raise ReportProjectionError("synthetic_report_inputs_required")
        tenant = baseline["tenant_id"]
        if not tenant.startswith("synthetic-") or any(
            value["tenant_id"] != tenant for value in (phase1, phase2, estate)
        ):
            raise ReportProjectionError("report_tenant_mismatch")
        if digest(_without(baseline, "baseline_id")) != baseline["baseline_id"]:
            raise ReportProjectionError("baseline_digest_mismatch")
        if digest(_without(estate, "content_sha256")) != estate["content_sha256"]:
            raise ReportProjectionError("estate_digest_mismatch")
        for phase, report in ((1, phase1), (2, phase2)):
            if (
                report["phase"] != phase
                or report["baseline_id"] != baseline["baseline_id"]
                or digest(_without(report, "report_id")) != report["report_id"]
                or report["human_acceptance"] != "not_requested"
                or report["source_system_write_authority"] is not False
                or report["production_risk_method_approved"] is not False
                or report["counts"] != baseline["counts"]
                or report["limitations"] != baseline["limitations"]
            ):
                raise ReportProjectionError("phase_report_binding_mismatch")
        if (
            phase1["inventory"] != baseline["observations"]
            or phase1["dependencies"] != baseline["dependencies"]
        ):
            raise ReportProjectionError("phase1_inventory_mismatch")
        if (
            baseline["human_acceptance"] != "not_requested"
            or baseline["counts"]["enterprise_coverage_percent"] is not None
        ):
            raise ReportProjectionError("unsupported_acceptance_or_coverage_claim")
        pages = {}
        for page in estate["pages"]:
            key = (page["source"], page["page_id"])
            if key in pages:
                raise ReportProjectionError("duplicate_estate_page_identity")
            pages[key] = page
        expected = {}
        for source in baseline["sources"]:
            key = (source["source"], source["page_id"])
            page = pages.get(key)
            if page is None or (
                source["payload_digest"] != digest(page["payload"])
                or source["kind"] != page["kind"]
                or source["observed_at"] != page["observed_at"]
                or bool(source["complete"]) != page["complete"]
                or timestamp(source["observed_at"]) > timestamp(baseline["as_of"])
            ):
                raise ReportProjectionError("source_page_binding_mismatch")
            normalized = normalize_page(
                page["kind"],
                page["payload"],
                tenant_id=tenant,
                source_instance_id=page["source"],
                observed_at=page["observed_at"],
            )
            for record in normalized:
                record_id = digest(
                    {
                        "tenant": tenant,
                        "source": page["source"],
                        "page": page["page_id"],
                        "record": digest(record),
                    }
                )
                expected[record_id] = {
                    **record,
                    "observation_id": record_id,
                    "source_instance_id": page["source"],
                    "observed_at": page["observed_at"],
                    "evidence_sha256": source["payload_digest"],
                    "evidence_ref": digest(
                        {"tenant": tenant, "sha256": source["payload_digest"]}
                    )
                    + ".aesgcm",
                }
        actual = {
            record["observation_id"]: record for record in baseline["observations"]
        }
        if len(actual) != len(baseline["observations"]) or actual != expected:
            raise ReportProjectionError("normalized_observation_provenance_mismatch")
        expected_risk_observations = {
            key
            for key, record in actual.items()
            if record["fact_type"] in {"certificate", "tls_endpoint"}
            or "cryptographic_uses" in record["facts"]
        }
        linked = set()
        for entry in phase2["risk_candidates"]:
            if (
                entry["risk_rating"] is not None
                or entry["residual_risk_accepted"] is not False
                or entry.get("execution_authorized", False) is not False
                or entry.get("source_claim_is_approval", False) is not False
            ):
                raise ReportProjectionError("unsupported_risk_authority")
            for ref in entry["observation_refs"]:
                if (
                    ref not in actual
                    or actual[ref]["subject_ref"] != entry["subject_ref"]
                ):
                    raise ReportProjectionError("phase2_evidence_reference_mismatch")
                linked.add(ref)
        if linked != expected_risk_observations:
            raise ReportProjectionError("phase2_observation_coverage_mismatch")
        if (
            baseline["counts"]["observations"] != len(actual)
            or baseline["counts"]["subjects"]
            != len({row["subject_ref"] for row in actual.values()})
            or baseline["counts"]["source_instances"]
            != len({page["source"] for page in baseline["sources"]})
        ):
            raise ReportProjectionError("baseline_count_mismatch")
        return pages
    except ReportProjectionError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ReportProjectionError("invalid_report_input") from None


def _subject_inventory(baseline):
    grouped = defaultdict(list)
    for record in baseline["observations"]:
        grouped[record["subject_ref"]].append(record)
    inventory = []
    for ref, records in sorted(grouped.items()):
        records.sort(key=lambda item: item["observation_id"])
        names = _sorted_unique(
            [
                str(record["facts"][key])
                for record in records
                for key in ("name", "common_name", "hostname")
                if record["facts"].get(key)
            ]
        )
        fact_types = _sorted_unique([record["fact_type"] for record in records])
        variants = {
            digest({"facts": row["facts"], "basis": row["assertion_kind"]})
            for row in records
        }
        inventory.append(
            {
                "subject_ref": ref,
                "fact_types": fact_types,
                "display_names": names,
                "observation_count": len(records),
                "variant_count": len(variants),
                "conflict_status": "requires_review"
                if len(variants) > 1
                else "no_conflict_in_snapshot",
                "observation_refs": [row["observation_id"] for row in records],
                "source_instance_refs": _sorted_unique(
                    [row["source_instance_id"] for row in records]
                ),
            }
        )
        if any("cryptographic_uses" in row["facts"] for row in records):
            inventory[-1]["source_metadata_variants"] = [
                {
                    "observation_ref": row["observation_id"],
                    "evidence_basis": row["assertion_kind"],
                    "metadata": {
                        key: copy.deepcopy(value)
                        for key, value in row["facts"].items()
                        if key
                        not in {
                            "native_id",
                            "name",
                            "application_ref",
                            "relationships",
                            "cryptographic_uses",
                        }
                    },
                    "explicit_cryptographic_uses": copy.deepcopy(
                        row["facts"].get("cryptographic_uses", [])
                    ),
                }
                for row in records
            ]
    return grouped, inventory


def _dependencies(baseline):
    grouped = defaultdict(set)
    subjects = {item["subject_ref"] for item in baseline["observations"]}
    by_observation = {item["observation_id"]: item for item in baseline["observations"]}
    expected = [
        edge for row in baseline["observations"] for edge in record_dependencies(row)
    ]
    if sorted(digest(edge) for edge in expected) != sorted(
        digest(edge) for edge in baseline["dependencies"]
    ) or baseline["counts"]["dependencies"] != len(expected):
        raise ReportProjectionError("dependency_provenance_mismatch")
    for edge in baseline["dependencies"]:
        source = by_observation.get(edge["observation_ref"])
        if (
            source is None
            or source["subject_ref"] != edge["from_ref"]
            or edge not in record_dependencies(source)
        ):
            raise ReportProjectionError("dependency_provenance_mismatch")
        grouped[(edge["from_ref"], edge["relationship"], edge["to_ref"])].add(
            edge["observation_ref"]
        )
    return [
        {
            "from_ref": key[0],
            "relationship": key[1],
            "to_ref": key[2],
            "observation_refs": sorted(refs),
            "target_present": key[2] in subjects,
        }
        for key, refs in sorted(grouped.items())
    ]


def _coverage(baseline, estate, by_subject):
    kinds, families = _kind_catalog(estate)
    profiles = estate["source_profiles"]
    if len(profiles) != 27 or len({item["family_id"] for item in profiles}) != 27:
        raise ReportProjectionError("source_family_catalog_incomplete")
    by_kind = defaultdict(list)
    for page in baseline["sources"]:
        if page["kind"] not in kinds:
            raise ReportProjectionError("unsupported_collected_dialect")
        by_kind[page["kind"]].append(page)
    profile_rows = []
    for profile in sorted(
        profiles, key=lambda item: (item["area_ref"], item["family_id"])
    ):
        kind = next(
            (
                kind
                for kind, family in families.items()
                if family == profile["family_id"]
            ),
            None,
        )
        pages = by_kind.get(kind, []) if kind else []
        sources = {page["source"] for page in pages}
        if not sources.issubset(set(profile["source_instance_ids"])):
            raise ReportProjectionError("profile_source_binding_mismatch")
        refs = {
            ref
            for ref, records in by_subject.items()
            if any(row["source_instance_id"] in sources for row in records)
        }
        if kind is None and profile["normalization_support"] != "not_implemented":
            raise ReportProjectionError("unsupported_adapter_claim")
        profile_rows.append(
            {
                "family_id": profile["family_id"],
                "area_ref": profile["area_ref"],
                "name": profile["name"],
                "recognition_examples": list(profile["recognition_examples"]),
                "examples_status": "recognition_examples_not_installed_or_selected",
                "evidence_targets": list(profile["evidence_targets"]),
                "normalization_support": "reference_dialect_only"
                if kind
                else "not_implemented",
                "source_instance_refs": sorted(sources),
                "imported_page_count": len(pages),
                "unique_subject_count": len(refs),
                "collection_status": "synthetic_partial_collection"
                if any(not page["complete"] for page in pages)
                else "synthetic_pages_present"
                if pages
                else "no_collected_evidence",
                "enterprise_route_status": "owner_and_access_confirmation_required",
                "product_binding_status": "unconfirmed",
                "enterprise_coverage_percent": None,
            }
        )
    area_names = {
        "area-01": "Enterprise context",
        "area-02": "PKI and trust",
        "area-03": "Encrypted traffic",
        "area-04": "Machine access",
        "area-05": "Software delivery",
        "area-06": "Cloud, keys and identity",
        "area-07": "Protected data",
        "area-08": "Distributed endpoints",
        "area-09": "Specialized and regulated cryptography",
        "area-10": "Governance and assurance",
    }
    if {row["area_ref"] for row in profile_rows} != set(area_names):
        raise ReportProjectionError("estate_area_catalog_incomplete")
    areas = []
    for ref, name in area_names.items():
        rows = [row for row in profile_rows if row["area_ref"] == ref]
        areas.append(
            {
                "area_ref": ref,
                "name": name,
                "profile_count": len(rows),
                "profiles_with_synthetic_evidence": sum(
                    row["imported_page_count"] > 0 for row in rows
                ),
                "profile_refs": [row["family_id"] for row in rows],
                "collection_status": "bounded_synthetic_evidence_only"
                if any(row["imported_page_count"] for row in rows)
                else "no_collected_evidence",
                "enterprise_coverage_percent": None,
            }
        )
    return areas, profile_rows


def _context(records, subjects):
    refs = _sorted_unique(
        [
            row["facts"]["application_ref"]
            for row in records
            if row["facts"].get("application_ref")
        ]
    )
    contexts = [
        row
        for ref in refs
        for row in subjects.get(ref, [])
        if row["fact_type"] == "application"
    ]
    result = {
        "application_refs": refs,
        "observation_refs": sorted(row["observation_id"] for row in contexts),
        "criticality": None,
        "confidentiality_until": None,
        "owner_ref": None,
        "business_service_ref": None,
        "status": "unresolved",
        "conflicted_fields": [],
    }
    if len(refs) != 1 or not contexts:
        return result
    for field in (
        "criticality",
        "confidentiality_until",
        "owner_ref",
        "business_service_ref",
    ):
        values = {row["facts"].get(field) for row in contexts}
        if len(values) == 1:
            item = next(iter(values))
            result[field] = item if item != "unknown" else None
        else:
            result["conflicted_fields"].append(field)
    result["status"] = (
        "conflicted"
        if result["conflicted_fields"]
        else "complete_in_synthetic_snapshot"
        if all(
            result[field] is not None
            for field in (
                "criticality",
                "confidentiality_until",
                "owner_ref",
                "business_service_ref",
            )
        )
        else "partial"
    )
    return result


def _posture(algorithms, role):
    if len(algorithms) > 1:
        return "conflicted"
    if not algorithms or any(value is None for value in algorithms):
        return "unknown"
    algorithm = algorithms[0].casefold()
    if role == "tls_key_exchange" and algorithm in _HYBRID:
        return "hybrid_key_exchange_recorded"
    if (
        role
        in {
            "certificate_issuer_signature",
            "tls_certificate_signature",
            "certificate_public_key",
        }
        and algorithm in _PQC_SIGNATURES
    ):
        return "pqc_signature_mechanism_recorded"
    return (
        "classical_method_review_candidate"
        if algorithm in _CLASSICAL
        else "unclassified_mechanism"
    )


def _uses(baseline, subjects):
    limitations = defaultdict(set)
    for item in baseline["limitations"]:
        if item.get("subject_ref"):
            limitations[item["subject_ref"]].add(item["code"])
    uses = []
    now = timestamp(baseline["as_of"])
    for subject, records in sorted(subjects.items()):
        kinds = {row["fact_type"] for row in records}
        if len(kinds) != 1:
            raise ReportProjectionError("subject_type_conflict")
        kind = next(iter(kinds))
        roles = (
            (
                ("tls_key_exchange", "key_exchange_group"),
                ("tls_certificate_signature", "certificate_signature_algorithm"),
            )
            if kind == "tls_endpoint"
            else (
                ("certificate_issuer_signature", "signature_algorithm"),
                ("certificate_public_key", "public_key_algorithm"),
            )
            if kind == "certificate"
            else ()
        )
        context = _context(records, subjects)
        for role, field in roles:
            algorithms = sorted(
                {row["facts"].get(field) for row in records},
                key=lambda item: (item is None, item or ""),
            )
            posture = _posture(algorithms, role)
            bases = _sorted_unique([row["assertion_kind"] for row in records])
            if not set(bases).issubset(_ALLOWED_BASES):
                raise ReportProjectionError("unsupported_evidence_basis")
            codes = set(limitations[subject])
            if "conflicting_observations" in codes and len(algorithms) == 1:
                # A disagreement elsewhere in a source record must not invent a
                # disagreement in this specific cryptographic purpose.
                codes.remove("conflicting_observations")
                codes.add("other_fact_conflict_on_subject")
            if posture == "unknown":
                codes.add("cryptographic_parameters_unknown")
            if posture == "conflicted":
                codes.add("conflicting_observations")
            if context["status"] != "complete_in_synthetic_snapshot":
                codes.add("business_context_requires_review")
            if context["conflicted_fields"]:
                codes.add("conflicting_business_context")
            if role != "tls_key_exchange":
                codes.add("signature_trust_lifetime_unknown")
            stale = [
                row["observation_id"]
                for row in records
                if (now - timestamp(row["observed_at"])).days
                > baseline["freshness_days"]
            ]
            if stale:
                codes.add("stale_evidence")
            context_observations = [
                row
                for ref in context["application_refs"]
                for row in subjects.get(ref, [])
                if row["observation_id"] in context["observation_refs"]
            ]
            if any(
                (now - timestamp(row["observed_at"])).days > baseline["freshness_days"]
                for row in context_observations
            ):
                codes.add("stale_business_context")
            if "observed" not in bases:
                codes.add("behavior_not_observed")
            if {
                "conflicting_observations",
                "cryptographic_parameters_unknown",
                "conflicting_business_context",
            } & codes:
                lane, rule = "resolve_evidence_conflict_or_gap", "TRIAGE-01"
            elif {
                "stale_evidence",
                "stale_business_context",
                "unresolved_dependency",
                "missing_relationship",
            } & codes:
                lane, rule = "refresh_evidence_and_dependencies", "TRIAGE-03"
            elif "behavior_not_observed" in codes:
                lane, rule = "validate_configured_or_vendor_claim", "TRIAGE-02"
            elif (
                context["status"] != "complete_in_synthetic_snapshot"
                or "signature_trust_lifetime_unknown" in codes
            ):
                lane, rule = "complete_business_context", "TRIAGE-04"
            elif posture == "classical_method_review_candidate":
                lane, rule = "review_migration_pattern", "TRIAGE-05"
            elif posture == "hybrid_key_exchange_recorded":
                lane, rule = (
                    "verify_key_exchange_and_authentication_separately",
                    "TRIAGE-06",
                )
            elif posture == "pqc_signature_mechanism_recorded":
                lane, rule = "verify_signature_interoperability_and_trust", "TRIAGE-07"
            else:
                lane, rule = "specialist_algorithm_review", "TRIAGE-08"
            lifetime = context["confidentiality_until"]
            days = (
                (date.fromisoformat(lifetime) - now.date()).days
                if lifetime and role == "tls_key_exchange"
                else None
            )
            focus = []
            if context["criticality"] in {"critical", "high"}:
                focus.append("source_reports_high_business_criticality")
            if (
                days is not None
                and days >= METHOD["long_lived_information_threshold_days"]
            ):
                focus.append("source_reports_long_lived_information")
            uses.append(
                {
                    "use_id": digest(
                        {
                            "baseline": baseline["baseline_id"],
                            "subject": subject,
                            "role": role,
                        }
                    ),
                    "subject_ref": subject,
                    "role": role,
                    "purpose": "key_establishment"
                    if role == "tls_key_exchange"
                    else "authentication",
                    "algorithm_variants": algorithms,
                    "algorithm_posture": posture,
                    "evidence_bases": bases,
                    "negotiated_behavior_observed": role == "tls_key_exchange"
                    and "observed" in bases
                    and all(
                        row["facts"].get("protocol") in {"TLSv1.2", "TLSv1.3"}
                        for row in records
                    )
                    and posture not in {"unknown", "conflicted"},
                    "observation_refs": sorted(
                        row["observation_id"] for row in records
                    ),
                    "evidence": sorted(
                        [
                            {
                                "observation_ref": row["observation_id"],
                                "custody_ref": row["evidence_ref"],
                                "custody_sha256": row["evidence_sha256"],
                                "source_instance_ref": row["source_instance_id"],
                                "observed_at": row["observed_at"],
                            }
                            for row in records
                        ],
                        key=lambda item: item["observation_ref"],
                    ),
                    "business_context": copy.deepcopy(context),
                    "confidentiality_days_remaining": days,
                    "information_lifetime_basis": "application_confidentiality_context"
                    if role == "tls_key_exchange"
                    else "signature_trust_lifetime_unavailable",
                    "signature_trust_until": None,
                    "business_review_focus": focus,
                    "limitation_codes": sorted(codes),
                    "triage_lane": lane,
                    "method_rule_ref": rule,
                    "risk_rating": None,
                    "assessment_status": "human_review_required",
                    "migration_feasibility": "not_assessed",
                    "vendor_blocker_status": "not_assessed",
                    "residual_risk_accepted": False,
                    "execution_authorized": False,
                }
            )
    return uses


def _extended_posture(algorithms, purpose):
    if len(algorithms) > 1:
        return "conflicted"
    if not algorithms or algorithms[0] in (None, "", "unknown"):
        return "unknown"
    value = algorithms[0].casefold()
    if purpose == "key_establishment" and value in _HYBRID | _SSH_HYBRID:
        return "hybrid_key_exchange_recorded"
    if purpose in _SIGNATURE_PURPOSES and value in _PQC_SIGNATURES:
        return "pqc_signature_mechanism_recorded"
    if value in _SYMMETRIC:
        return "symmetric_mechanism_separate_parameter_review"
    if value in _HASHES:
        return "hash_or_mac_mechanism_separate_parameter_review"
    if value in _CLASSICAL | _SSH_CLASSICAL:
        return "classical_method_review_candidate"
    return "unclassified_mechanism"


def _evidence_rows(records):
    return sorted(
        [
            {
                "observation_ref": row["observation_id"],
                "custody_ref": row["evidence_ref"],
                "custody_sha256": row["evidence_sha256"],
                "source_instance_ref": row["source_instance_id"],
                "observed_at": row["observed_at"],
            }
            for row in records
        ],
        key=lambda row: row["observation_ref"],
    )


def _extended_uses(baseline, subjects):
    """Use only explicit normalized use records, never a capability/package list."""
    result = []
    now = timestamp(baseline["as_of"])
    for subject, records in sorted(subjects.items()):
        extended = [row for row in records if "cryptographic_uses" in row["facts"]]
        if not extended:
            continue
        context = _context(records, subjects)
        groups = defaultdict(list)
        for record in extended:
            for use in record["facts"]["cryptographic_uses"]:
                groups[(use["purpose"], use["role"])].append((record, use))
        for (purpose, role), assertions in sorted(
            groups.items(), key=lambda item: str(item[0])
        ):
            rows = list({row["observation_id"]: row for row, _ in assertions}.values())
            algorithms = sorted(
                {use["algorithm"] for _, use in assertions},
                key=lambda item: (item is None, item or ""),
            )
            bases = _sorted_unique([use["basis"] for _, use in assertions])
            if not set(bases).issubset(_ALLOWED_BASES):
                raise ReportProjectionError("unsupported_evidence_basis")
            posture = _extended_posture(algorithms, purpose)
            protected_refs = sorted(
                {use["protected_data_ref"] for _, use in assertions},
                key=lambda item: (item is None, item or ""),
            )
            protected_ref = protected_refs[0] if len(protected_refs) == 1 else None
            codes = {
                item["code"]
                for item in baseline["limitations"]
                if item.get("subject_ref") == subject
                and (not item.get("field") or item["field"] == role)
            }
            parameter_variants = {
                digest(use["parameters"]): use["parameters"] for _, use in assertions
            }
            if (
                "conflicting_observations" in codes
                and len(algorithms) == len(parameter_variants) == 1
            ):
                codes.remove("conflicting_observations")
                codes.add("other_fact_conflict_on_subject")
            if posture == "unknown":
                codes.add("cryptographic_parameters_unknown")
            if posture == "conflicted" or len(parameter_variants) > 1:
                codes.add("conflicting_observations")
            if len(protected_refs) > 1:
                codes.add("conflicting_protected_data_reference")
            if len(rows) != len(extended):
                codes.add("use_presence_conflict")
            if "observed" not in bases:
                codes.add("behavior_not_observed")
            if context["status"] != "complete_in_synthetic_snapshot":
                codes.add("business_context_requires_review")
            if context["conflicted_fields"]:
                codes.add("conflicting_business_context")
            if any(
                (now - timestamp(row["observed_at"])).days > baseline["freshness_days"]
                for row in rows
            ):
                codes.add("stale_evidence")
            context_rows = [
                row
                for ref in context["application_refs"]
                for row in subjects.get(ref, [])
            ]
            if any(
                (now - timestamp(row["observed_at"])).days > baseline["freshness_days"]
                for row in context_rows
            ):
                codes.add("stale_business_context")
            trust_dates = {use["trust_until"] for _, use in assertions}
            trust_until = next(iter(trust_dates)) if len(trust_dates) == 1 else None
            if len(trust_dates) > 1:
                codes.add("conflicting_trust_lifetime")
            if purpose in _SIGNATURE_PURPOSES and not trust_until:
                codes.add("signature_trust_lifetime_unknown")
            # Storage-retention dates are not substituted for confidentiality.
            protected_rows = [
                row for ref in protected_refs if ref for row in subjects.get(ref, [])
            ]
            protected_dates = {
                row["facts"].get("confidentiality_until") for row in protected_rows
            }
            lifetime = None
            lifetime_basis = "not_a_confidentiality_use"
            if purpose in _CONFIDENTIALITY_PURPOSES:
                if any(protected_refs):
                    lifetime_basis = "explicit_protected_data_confidentiality"
                    lifetime = (
                        next(iter(protected_dates))
                        if len(protected_dates) == len(protected_refs) == 1
                        else None
                    )
                    if not lifetime:
                        codes.add("protected_data_confidentiality_unknown")
                    if len(protected_dates) > 1:
                        codes.add("conflicting_protected_data_lifetime")
                    if any(
                        (now - timestamp(row["observed_at"])).days
                        > baseline["freshness_days"]
                        for row in protected_rows
                    ):
                        codes.add("stale_protected_data_context")
                else:
                    lifetime_basis = "application_confidentiality_context"
                    lifetime = context["confidentiality_until"]
                if not lifetime:
                    codes.add("confidentiality_lifetime_unknown")
            else:
                lifetime_basis = (
                    "explicit_signature_trust_lifetime"
                    if trust_until
                    else "signature_trust_lifetime_unavailable"
                )
            days = (
                (date.fromisoformat(lifetime) - now.date()).days if lifetime else None
            )
            protocol_versions = {
                use["parameters"].get("protocol_version") for _, use in assertions
            }
            conflict_codes = {
                "conflicting_observations",
                "cryptographic_parameters_unknown",
                "use_presence_conflict",
                "conflicting_business_context",
                "conflicting_trust_lifetime",
                "conflicting_protected_data_lifetime",
                "conflicting_protected_data_reference",
            }
            stale_codes = {
                "stale_evidence",
                "stale_business_context",
                "stale_protected_data_context",
                "unresolved_dependency",
                "missing_relationship",
            }
            if codes & conflict_codes:
                lane, rule = "resolve_evidence_conflict_or_gap", "TRIAGE-01"
            elif codes & stale_codes:
                lane, rule = "refresh_evidence_and_dependencies", "TRIAGE-03"
            elif "behavior_not_observed" in codes:
                lane, rule = "validate_configured_or_vendor_claim", "TRIAGE-02"
            elif context["status"] != "complete_in_synthetic_snapshot" or codes & {
                "signature_trust_lifetime_unknown",
                "confidentiality_lifetime_unknown",
            }:
                lane, rule = "complete_business_context", "TRIAGE-04"
            elif posture == "classical_method_review_candidate":
                lane, rule = "review_migration_pattern", "TRIAGE-05"
            elif posture == "hybrid_key_exchange_recorded":
                lane, rule = (
                    "verify_key_exchange_and_authentication_separately",
                    "TRIAGE-06",
                )
            elif posture == "pqc_signature_mechanism_recorded":
                lane, rule = "verify_signature_interoperability_and_trust", "TRIAGE-07"
            elif posture in {
                "symmetric_mechanism_separate_parameter_review",
                "hash_or_mac_mechanism_separate_parameter_review",
            }:
                lane, rule = (
                    "review_symmetric_or_hash_parameters_separately",
                    "TRIAGE-09",
                )
            else:
                lane, rule = "specialist_algorithm_review", "TRIAGE-08"
            focus = []
            if context["criticality"] in {"high", "critical"}:
                focus.append("source_reports_high_business_criticality")
            if (
                days is not None
                and days >= METHOD["long_lived_information_threshold_days"]
            ):
                focus.append("source_reports_long_lived_information")
            result.append(
                {
                    "use_id": digest(
                        {
                            "baseline": baseline["baseline_id"],
                            "subject": subject,
                            "purpose": purpose,
                            "role": role,
                        }
                    ),
                    "subject_ref": subject,
                    "role": role,
                    "purpose": purpose,
                    "source_family_id": rows[0]["fact_type"].replace("_", "-"),
                    "algorithm_variants": algorithms,
                    "algorithm_posture": posture,
                    "parameter_variants": [
                        parameter_variants[key] for key in sorted(parameter_variants)
                    ],
                    "evidence_bases": bases,
                    "source_use_assertions": [
                        {"observation_ref": row["observation_id"], **copy.deepcopy(use)}
                        for row, use in assertions
                    ],
                    "negotiated_behavior_observed": purpose == "key_establishment"
                    and role == "transport_key_exchange"
                    and "observed" in bases
                    and not codes & conflict_codes
                    and protocol_versions.issubset(
                        {"TLSv1.2", "TLSv1.3", "SSH-2.0", "SSH2", "SSHv2", "IKEv2"}
                    ),
                    "observation_refs": sorted(row["observation_id"] for row in rows),
                    "evidence": _evidence_rows(rows),
                    "business_context": copy.deepcopy(context),
                    "protected_data_ref": protected_ref,
                    "protected_data_reference_variants": protected_refs,
                    "protected_data_observation_refs": sorted(
                        row["observation_id"] for row in protected_rows
                    ),
                    "confidentiality_days_remaining": days,
                    "information_lifetime_basis": lifetime_basis,
                    "signature_trust_until": trust_until
                    if purpose in _SIGNATURE_PURPOSES
                    else None,
                    "business_review_focus": focus,
                    "limitation_codes": sorted(codes),
                    "triage_lane": lane,
                    "method_rule_ref": rule,
                    "risk_rating": None,
                    "assessment_status": "human_review_required",
                    "migration_feasibility": "not_assessed",
                    "vendor_blocker_status": "not_assessed",
                    "residual_risk_accepted": False,
                    "execution_authorized": False,
                    "independent_migration_verification": False,
                }
            )
    return sorted(result, key=lambda item: item["use_id"])


def _context_reviews(baseline, subjects):
    """Make capability/governance evidence useful without manufacturing a use."""
    output = []
    for subject, records in sorted(subjects.items()):
        rows = [
            row
            for row in records
            if "cryptographic_uses" in row["facts"]
            and not row["facts"]["cryptographic_uses"]
        ]
        if not rows:
            continue
        kind = rows[0]["fact_type"]
        reason = {
            "policy_exceptions": "reported_policy_or_exception_requires_authority_review",
            "vendor_assurance": "reported_vendor_claim_requires_versioned_product_qualification",
            "data_governance": "information_lifetime_and_ownership_context_only",
            "dependency_analysis": "package_presence_does_not_establish_cryptographic_use",
            "hsm": "key_custody_capability_does_not_establish_consumer_use",
            "kms": "key_custody_capability_does_not_establish_consumer_use",
        }.get(kind, "context_or_capability_without_explicit_cryptographic_use")
        output.append(
            {
                "context_review_id": digest(
                    {
                        "baseline": baseline["baseline_id"],
                        "subject": subject,
                        "kind": "context_review",
                    }
                ),
                "subject_ref": subject,
                "source_family_id": kind.replace("_", "-"),
                "fact_type": kind,
                "rationale_code": reason,
                "statement_basis": "vendor_reported"
                if kind == "vendor_assurance"
                else "source_reported"
                if kind == "policy_exceptions"
                else "source_metadata_only",
                "record_observation_does_not_verify_claim": True,
                "method_rule_ref": "TRIAGE-10",
                "assessment_status": "context_review_required",
                "fact_variants": [copy.deepcopy(row["facts"]) for row in rows],
                "evidence_bases": _sorted_unique(
                    [row["assertion_kind"] for row in rows]
                ),
                "observation_refs": sorted(row["observation_id"] for row in rows),
                "evidence": _evidence_rows(rows),
                "business_context": _context(records, subjects),
                "limitation_codes": sorted(
                    {
                        item["code"]
                        for item in baseline["limitations"]
                        if item.get("subject_ref") == subject
                    }
                ),
                "risk_rating": None,
                "source_claim_is_approval": False,
                "source_claim_is_verified_migration": False,
                "residual_risk_accepted": False,
                "execution_authorized": False,
            }
        )
    return output


def _migration_candidates(uses, dependencies):
    output = []
    for use in uses:
        if use["algorithm_posture"] not in {
            "classical_method_review_candidate",
            "unknown",
            "conflicted",
            "unclassified_mechanism",
        }:
            continue
        role = use["role"]
        pattern = (
            "tls-hybrid-key-exchange"
            if role == "tls_key_exchange"
            else "certificate-signature-migration"
        )
        family = use.get("source_family_id")
        if family:
            purpose = use["purpose"]
            if purpose == "key_establishment":
                pattern = (
                    "ssh-hybrid-key-exchange"
                    if family == "ssh"
                    else "vpn-key-exchange"
                    if family == "vpn"
                    else "tls-hybrid-key-exchange"
                )
            elif purpose == "key_wrapping":
                pattern = "envelope-key-rewrap"
            elif purpose == "data_encryption":
                pattern = (
                    "archive-restoration"
                    if family == "storage-backup"
                    else "data-reencryption"
                )
            else:
                pattern = {
                    "code_signer": "code-signing",
                    "application_signer": "application-library-migration",
                    "firmware_verifier": "firmware-trust",
                    "token_issuer": "identity-token-signing",
                    "document_signer": "document-signature",
                    "credential_issuer": "workload-credential",
                    "dnssec_signer": "dnssec",
                    "email_signer": "message-protection",
                    "key_custodian": "key-service-consumer",
                }.get(
                    role,
                    "specialist-ceremony"
                    if family
                    in {"mainframe", "specialized-transactions", "embedded-ot"}
                    else "certificate-signature-migration",
                )
                if family in {"mainframe", "specialized-transactions"}:
                    pattern = "specialist-ceremony"
        output.append(
            {
                "candidate_id": digest({"use_id": use["use_id"], "pattern": pattern}),
                "use_ref": use["use_id"],
                "subject_ref": use["subject_ref"],
                "pattern_ref": pattern,
                "rationale": "Review this specific cryptographic use after its evidence and business dependencies are resolved.",
                "candidate_state": "design_review_candidate"
                if use["triage_lane"] == "review_migration_pattern"
                else "evidence_work_required",
                "blocking_limitation_codes": use["limitation_codes"],
                "observation_refs": use["observation_refs"],
                "dependency_refs": sorted(
                    {
                        edge["to_ref"]
                        for edge in dependencies
                        if edge["from_ref"] == use["subject_ref"]
                    }
                ),
                "prerequisites": [
                    "owner_confirmed_scope",
                    "current_read_only_observations",
                    "relying_party_compatibility",
                    "product_version_and_support",
                    "exact_plan_approval",
                ],
                "recovery_requirements": [
                    "previous_configuration_reference",
                    "access_preservation_test",
                    "bounded_canary",
                    "independent_readback",
                ],
                "recovery_strategy": "requires_design",
                "vendor_support_status": "unknown",
                "live_execution_authorized": False,
            }
        )
    return output


def build_report_pack(baseline: dict, phase1: dict, phase2: dict, estate: dict) -> dict:
    """Build a pure immutable projection from source-validated stored snapshots."""
    _validate_inputs(baseline, phase1, phase2, estate)
    subjects, inventory = _subject_inventory(baseline)
    dependencies = _dependencies(baseline)
    areas, profiles = _coverage(baseline, estate, subjects)
    uses = _uses(baseline, subjects) + _extended_uses(baseline, subjects)
    context_reviews = _context_reviews(baseline, subjects)
    method = _method_for(baseline)
    candidates = _migration_candidates(uses, dependencies)
    as_of = timestamp(baseline["as_of"])
    records = baseline["observations"]
    stale = [
        row
        for row in records
        if (as_of - timestamp(row["observed_at"])).days > baseline["freshness_days"]
    ]
    kinds, _ = _kind_catalog(estate)
    by_type = {
        kind: sum(kind in item["fact_types"] for item in inventory)
        for kind in kinds.values()
    }
    custody = {}
    for record in records:
        key = record["evidence_ref"]
        if key not in custody:
            custody[key] = {
                "custody_ref": key,
                "custody_sha256": record["evidence_sha256"],
                "observation_refs": [],
            }
        custody[key]["observation_refs"].append(record["observation_id"])
    for item in custody.values():
        item["observation_refs"].sort()
    limitations = copy.deepcopy(baseline["limitations"])
    app_records = [row for row in records if row["fact_type"] == "application"]
    gaps = {}
    for field in (
        "owner_ref",
        "business_service_ref",
        "criticality",
        "confidentiality_until",
    ):
        gaps[field] = sorted(
            {
                row["subject_ref"]
                for row in app_records
                if row["facts"].get(field) in (None, "unknown")
            }
        )
    body = {
        "schema_version": "pba.pqc.reference-report-pack.v1",
        "synthetic": True,
        "tenant_id": baseline["tenant_id"],
        "as_of": baseline["as_of"],
        "source_binding": {
            "baseline_id": baseline["baseline_id"],
            "phase1_report_id": phase1["report_id"],
            "phase2_report_id": phase2["report_id"],
            "estate_content_sha256": estate["content_sha256"],
            "scenario_catalog_sha256": digest(estate["scenario_catalog"]),
            "source_profiles_sha256": digest(estate["source_profiles"]),
            "method_sha256": digest(method),
        },
        "authority": {
            "proof_level": "synthetic_development_projection",
            "human_acceptance": "not_requested",
            "enterprise_risk_method_approved": False,
            "source_system_write_authority": False,
            "migration_execution_authorized": False,
            "whole_estate_denominator_available": False,
        },
        "metrics": {
            "unique_subjects": len(inventory),
            "subjects_by_type": by_type,
            "source_observations": len(records),
            "source_instances": len({page["source"] for page in baseline["sources"]}),
            "imported_pages": len(baseline["sources"]),
            "custody_artifacts": len(custody),
            "unique_dependency_edges": len(dependencies),
            "dependency_observation_links": len(baseline["dependencies"]),
            "unresolved_dependency_edges": sum(
                not edge["target_present"] for edge in dependencies
            ),
            "conflicted_subjects": sum(
                row["conflict_status"] == "requires_review" for row in inventory
            ),
            "stale_subjects": len({row["subject_ref"] for row in stale}),
            "stale_observations": len(stale),
            "freshness_window_days": baseline["freshness_days"],
            "observation_basis_counts": dict(
                sorted(Counter(row["assertion_kind"] for row in records).items())
            ),
            "profiles_total": len(profiles),
            "profiles_with_imported_pages": sum(
                row["imported_page_count"] > 0 for row in profiles
            ),
            "areas_total": len(areas),
            "cryptographic_uses": len(uses),
            "context_only_review_subjects": len(context_reviews),
            "migration_candidates": len(candidates),
            "enterprise_coverage_percent": None,
        },
        "estate_areas": areas,
        "source_profiles": profiles,
        "inventory": inventory,
        "dependencies": dependencies,
        "limitations": limitations,
        "limitation_counts": dict(
            sorted(Counter(item["code"] for item in limitations).items())
        ),
        "business_context_gaps": gaps,
        "phase1_handoff_checklist": [
            {"id": key, "question": text, "human_disposition": "not_requested"}
            for key, text in _PHASE1_CHECKLIST
        ],
        "method": method,
        "risk_review_register": uses,
        "context_review_register": context_reviews,
        "triage_lane_counts": dict(
            sorted(Counter(use["triage_lane"] for use in uses).items())
        ),
        "migration_candidates": candidates,
        "lookahead": [
            {
                "phase": 3,
                "title": "Design and mediate bounded migration pilots",
                "status": "proposed_not_authorized",
                "work": [
                    "Resolve evidence gaps before selecting target cohorts.",
                    "Bind each plan to prerequisites, approvals, independent verification and recovery.",
                    "Project canonical work items to ticket providers without delegating execution authority.",
                ],
                "patterns": [
                    "tls-hybrid-key-exchange",
                    "ssh-hybrid-key-exchange",
                    "application-library-migration",
                ],
                "boundary": "Source-modeled TLS, SSH, signing, encryption and contextual records are synthetic investigation evidence only; independently executed protocol/application labs remain separate proofs, not discovered enterprise coverage."
                if context_reviews or any(use.get("source_family_id") for use in uses)
                else "The imported reference estate contains TLS observations only; SSH and application/library proofs are separate synthetic labs, not discovered enterprise coverage.",
            },
            {
                "phase": 4,
                "title": "Coordinate repeatable migration waves and assurance",
                "status": "proposed_not_authorized",
                "work": [
                    "Sequence dependent consumers and maintenance windows.",
                    "Rediscover configurations and verify that improvements persist.",
                    "Allow narrowly preauthorized operations only after product, policy and recovery qualification.",
                ],
                "boundary": "No live wave scheduler, provider write, enterprise deployment or policy preauthorization is established by this pack.",
            },
        ],
        "evidence_appendix": {
            "observations": copy.deepcopy(records),
            "custody_artifacts": [custody[key] for key in sorted(custody)],
            "source_page_receipts": copy.deepcopy(baseline["sources"]),
            "scenario_catalog": copy.deepcopy(estate["scenario_catalog"]),
        },
        "reproduction": {
            "renderer": "tools.pqc_reference.report_pack",
            "canonicalization": "sorted_ascii_compact_json",
            "timestamps": "source_snapshot_only_no_wall_clock",
            "risk_scoring": "omitted_unapproved_method",
            "comparison_basis": "single synthetic snapshot; no enterprise progress or trend claim",
            "visual_omission": "Exact counts and per-record lookup are provided; no invented trend or whole-estate percentage.",
        },
    }
    return {**body, "content_sha256": digest(body)}


def _pretty(value):
    return str(value).replace("_", " ")


def _short(value):
    return str(value).removeprefix("pqc-ref:")[:16]


def _inventory_lines(pack):
    lines = [
        "## Inventory and relationship appendix",
        "",
        "Each subject appears once below, even when repeated pages or conflicting observations exist. "
        "Identifiers are abbreviated here; the machine-readable report pack preserves every complete identity, observation and custody hash.",
        "",
    ]
    for item in pack["inventory"]:
        name = "; ".join(item["display_names"]) or "Unnamed synthetic subject"
        lines += [
            f"### {name}",
            "",
            f"- Subject: `{_short(item['subject_ref'])}`. Type: {', '.join(item['fact_types'])}.",
            f"- Observations: {item['observation_count']}; distinct variants: {item['variant_count']}; {_pretty(item['conflict_status'])}.",
            "- Observation references: "
            + ", ".join(f"`{_short(ref)}`" for ref in item["observation_refs"])
            + ".",
        ]
        edges = [
            edge
            for edge in pack["dependencies"]
            if edge["from_ref"] == item["subject_ref"]
        ]
        if edges:
            for edge in edges:
                lines.append(
                    f"- Reported {_pretty(edge['relationship'])}: `{_short(edge['to_ref'])}`; "
                    + (
                        "target present in snapshot."
                        if edge["target_present"]
                        else "target unresolved; no dependency facts inferred."
                    )
                )
        for variant in item.get("source_metadata_variants", []):
            lines.append(
                f"- Source metadata ({variant['evidence_basis']}): "
                + "; ".join(
                    f"{_pretty(key)} = {value}"
                    for key, value in sorted(variant["metadata"].items())
                )
                + "."
            )
            for use in variant["explicit_cryptographic_uses"]:
                lines.append(
                    f"- Explicit {_pretty(use['purpose'])} use, role {_pretty(use['role'])}: {use['algorithm'] or 'unknown'} ({use['basis']}); capability listings are not substituted for this assertion."
                )
            if not variant["explicit_cryptographic_uses"]:
                lines.append(
                    "- No explicit cryptographic use in this observation; the record contributes context or capability only."
                )
        lines.append("")
    if not pack["inventory"]:
        lines += [
            "No source observations were imported into this snapshot. No inventory is inferred from the source catalog.",
            "",
        ]
    return lines


def _risk_lines(pack):
    lines = [
        "## Cryptographic-use review register",
        "",
        "These are work-queue dispositions, not numerical risk scores or accepted enterprise risk ratings. "
        "Key establishment, signatures, credential authentication, data encryption and key wrapping remain separate uses; capability-only metadata is listed separately.",
        "",
    ]
    for use in pack["risk_review_register"]:
        algorithms = ", ".join(
            value or "unknown" for value in use["algorithm_variants"]
        )
        context = use["business_context"]
        lines += [
            f"### {_pretty(use['role'])}: {_short(use['subject_ref'])}",
            "",
            f"- Use: `{_short(use['use_id'])}`. Algorithm evidence: {algorithms}. Basis: {', '.join(use['evidence_bases'])}.",
            f"- Review lane: {_pretty(use['triage_lane'])} ({use['method_rule_ref']}). Evidence posture: {_pretty(use['algorithm_posture'])}.",
            f"- Application context: {_pretty(context['status'])}; criticality: {context['criticality'] or 'unknown'}; application confidentiality until: {context['confidentiality_until'] or 'unknown'}.",
            "- Relevant lifetime: "
            + (
                f"{_pretty(use['information_lifetime_basis'])} ({use['confidentiality_days_remaining']} days remaining)."
                if use["purpose"] in _CONFIDENTIALITY_PURPOSES
                and use["confidentiality_days_remaining"] is not None
                else "confidentiality lifetime unknown."
                if use["purpose"] in _CONFIDENTIALITY_PURPOSES
                else f"source-reported signature trust until {use['signature_trust_until']}; requires validation."
                if use.get("signature_trust_until")
                else "signature trust/validation lifetime unknown; application confidentiality is context only."
            ),
            "- Limitations: "
            + (
                ", ".join(_pretty(code) for code in use["limitation_codes"])
                or "No additional gaps recorded for this use; enterprise validation remains outstanding"
            )
            + ".",
            "- Observation references: "
            + ", ".join(f"`{_short(ref)}`" for ref in use["observation_refs"])
            + ".",
            "- Risk rating: not assigned. Feasibility and vendor blockers: not assessed. Human review required.",
            "",
        ]
    if not pack["risk_review_register"]:
        lines += [
            "No cryptographic observations support a use-level review register. Collect evidence first; absence is not a low-risk rating.",
            "",
        ]
    return lines


def _context_lines(pack):
    rows = pack.get("context_review_register", [])
    if not rows:
        return []
    lines = [
        "## Context and capability review register",
        "",
        "These source records contribute ownership, lifecycle, platform, key-custody, policy or vendor context. They do not establish an actual cryptographic use, accepted policy decision or verified migration.",
        "",
    ]
    for row in rows:
        lines += [
            f"### {_pretty(row['source_family_id'].replace('-', '_'))}: {_short(row['subject_ref'])}",
            "",
            f"- Review: {_pretty(row['rationale_code'])} ({row['method_rule_ref']}).",
            f"- Record observation basis: {', '.join(row['evidence_bases'])}. Statement basis: {_pretty(row['statement_basis'])}; observing a statement does not independently verify its truth. Review status: {_pretty(row['assessment_status'])}.",
            "- Observation references: "
            + ", ".join(f"`{_short(ref)}`" for ref in row["observation_refs"])
            + ".",
            "- Source-normalized facts: "
            + "; ".join(
                f"{_pretty(key)} = {value}"
                for variant in row["fact_variants"]
                for key, value in sorted(variant.items())
                if key
                not in {
                    "native_id",
                    "application_ref",
                    "relationships",
                    "cryptographic_uses",
                    "limitations",
                }
            )
            + ".",
            "- Limitations: "
            + (
                ", ".join(_pretty(code) for code in row["limitation_codes"])
                or "Enterprise source/product qualification remains outstanding"
            )
            + ".",
            "- No risk rating, approval, residual-risk acceptance or migration verification is inferred.",
            "",
        ]
    return lines


def render_report_markdown(pack: dict, phase: int) -> str:
    """Render complete readable report copy; never writes files or accepts work."""
    if phase not in (1, 2):
        raise ReportProjectionError("assessment_phase_required")
    if (
        not isinstance(pack, dict)
        or pack.get("synthetic") is not True
        or digest(_without(pack, "content_sha256")) != pack.get("content_sha256")
    ):
        raise ReportProjectionError("report_pack_digest_mismatch")
    metrics = pack["metrics"]
    title = "Current-State Assessment" if phase == 1 else "PQC Risk Review Register"
    missing_profiles = (
        metrics["profiles_total"] - metrics["profiles_with_imported_pages"]
    )
    lines = [f"# {title} — Synthetic Development Draft", "", "## Executive Summary", ""]
    if phase == 1:
        lines += [
            f"- The stored snapshot contains {metrics['unique_subjects']} distinct subjects from {metrics['source_observations']} source observations, connected by {metrics['unique_dependency_edges']} distinct dependency edges. This demonstrates how attributable source records become an inventory—not a completed enterprise assessment.",
            f"- Imported evidence covers {metrics['profiles_with_imported_pages']} reference source families. {missing_profiles} of the {metrics['profiles_total']} cataloged families have no imported evidence. None is a qualified commercial-product adapter or an approved enterprise access route.",
            f"- {metrics['conflicted_subjects']} subjects have conflicting variants, {metrics['stale_subjects']} have stale observations, and {metrics['unresolved_dependency_edges']} dependency edges have no target in the snapshot. These remain explicit review work.",
            "- The next decision is to approve the real assessment boundary, evidence rules and source routes, then accept or qualify an exact inventory handoff. No human acceptance has been recorded.",
            "",
        ]
    else:
        lines += [
            f"- The inventory supports {metrics['cryptographic_uses']} separately modeled cryptographic uses and {metrics['migration_candidates']} evidence-linked migration-design candidates. These counts are derived from the frozen records, not from demo progress labels.",
            "- The review method is illustrative and versioned. It assigns no numerical score or enterprise risk rating; observed exposure, missing evidence, business significance and feasibility remain separate.",
            f"- {metrics['conflicted_subjects']} conflicted subjects and {missing_profiles} source families without imported evidence limit conclusions. A catalog entry is not evidence of a deployed product or its support for migration.",
            "- Use this draft to refine the evidence and assessment model. Phase 3 pilot approval, production integration and Phase 4 automation remain separate decisions.",
            "",
        ]
    lines += [
        "## What this snapshot measures",
        "",
        f"Snapshot time: {pack['as_of']}. Freshness window: {metrics['freshness_window_days']} days, as declared by this synthetic baseline.",
        "",
        f"- Applications: {metrics['subjects_by_type']['application']}; certificates: {metrics['subjects_by_type']['certificate']}; TLS endpoints: {metrics['subjects_by_type']['tls_endpoint']}.",
        f"- Source instances: {metrics['source_instances']}; imported pages: {metrics['imported_pages']}; custody artifacts: {metrics['custody_artifacts']}.",
        f"- Distinct dependency edges: {metrics['unique_dependency_edges']}; observation-to-edge links: {metrics['dependency_observation_links']}. Repeated observations do not inflate distinct edge or subject coverage.",
        "- Whole-estate completeness: unknown. No approved enterprise population or percentage is inferred from the generated records.",
        "",
        f"The snapshot imports {metrics['profiles_with_imported_pages']} employer-neutral reference dialects. Every record is synthetic; modeled family coverage does not represent qualified product APIs, enterprise access or accepted evidence.",
        "",
    ]
    extra_types = {
        kind: count
        for kind, count in metrics["subjects_by_type"].items()
        if kind not in _KINDS.values() and count
    }
    if extra_types:
        lines += ["Additional source-modeled subject types:", ""]
        lines.extend(
            f"- {_pretty(kind).capitalize()}: {count} distinct subjects."
            for kind, count in sorted(extra_types.items())
        )
        lines += [
            "",
            f"Context-only review subjects: {metrics['context_only_review_subjects']}. These remain outside the cryptographic-use denominator.",
            "",
        ]
    if phase == 1:
        lines += [
            "## The map is connected, but source gaps remain",
            "",
            "The following areas organize discovery. Evidence in one source family does not establish coverage for its neighboring families.",
            "",
        ]
        for area in pack["estate_areas"]:
            lines += [
                f"### {area['name']}",
                "",
                f"{area['profiles_with_synthetic_evidence']} of {area['profile_count']} listed families have imported synthetic pages. Enterprise completeness is unknown.",
                "",
            ]
            for profile in [
                item
                for item in pack["source_profiles"]
                if item["area_ref"] == area["area_ref"]
            ]:
                lines += [
                    f"- {profile['name']}: {_pretty(profile['collection_status'])}; {profile['unique_subject_count']} distinct subjects.",
                    f"  Recognition examples only: {', '.join(profile['recognition_examples'])}.",
                    f"  Evidence targets: {', '.join(profile['evidence_targets'])}.",
                ]
            lines.append("")
    else:
        lines += [
            "## Evidence quality determines the next action",
            "",
            "Each use receives one next-work lane. The ordering below is a review process, not a ranking of enterprise risk.",
            "",
        ]
        for lane, count in pack["triage_lane_counts"].items():
            lines.append(f"- {_pretty(lane).capitalize()}: {count} cryptographic uses.")
        lines += [
            "",
            f"Method: {pack['method']['id']}, version {pack['method']['version']}; illustrative, not enterprise approved.",
            "",
        ]
        lines.extend(
            f"- {rule['id']}: {rule['rule']}" for rule in pack["method"]["rules"]
        )
        for reference in pack["method"].get("references", []):
            lines += [
                "",
                f"{reference['supports']} [{reference['title']}]({reference['url']}) (reference checked {reference['reviewed_on']}).",
            ]
        lines += [
            "",
            "The five-year confidentiality review threshold is an illustrative work-queue trigger. It is not a regulatory deadline or a prediction of quantum capability.",
            "",
        ]
        lines += [
            "## Evidence coverage limits this risk review",
            "",
            "Only the imported reference families below provide observations for this report. The remaining families are discovery routes, not assessed populations.",
            "",
        ]
        for area in pack["estate_areas"]:
            lines.append(
                f"- {area['name']}: {area['profiles_with_synthetic_evidence']} of {area['profile_count']} cataloged families have synthetic pages; enterprise completeness is unknown."
            )
        lines.append("")
    lines += [
        "## Limitations need owners and source routes",
        "",
        "A limitation is a bounded statement about what this snapshot cannot support. It is not proof that the source system is unsafe or absent.",
        "",
    ]
    for code, count in pack["limitation_counts"].items():
        lines.append(
            f"- {_pretty(code).capitalize()}: {count} recorded limitation entries."
        )
    lines += ["", "Business-context gaps, counted by distinct application subject:", ""]
    for field, refs in pack["business_context_gaps"].items():
        lines.append(
            f"- {_pretty(field)}: {len(refs)} applications require clarification."
        )
    lines += [
        "",
        "Every enterprise source profile still needs its responsible function, exact product/version, approved read-only route and custody constraints confirmed. Recognition examples do not constitute product selection.",
        "",
    ]
    if phase == 1:
        lines += [
            "## Phase 1 handoff requires explicit human decisions",
            "",
            "The frozen inventory can be inspected and reproduced. It has not been accepted as an enterprise deliverable. Each checkpoint below is unrequested—not implicitly approved.",
            "",
        ]
        for index, item in enumerate(pack["phase1_handoff_checklist"], 1):
            lines.append(
                f"{index}. {item['question']} Human disposition: not requested."
            )
        lines += [
            "",
            "The Phase 2 report is tied to this exact baseline. New evidence creates a new snapshot; it does not silently rewrite an accepted historical report. Accepting an inventory would still not authorize remediation.",
            "",
        ]
    else:
        lines += [
            "## Migration candidates require design, not a one-click upgrade",
            "",
            "Candidates link one use to one migration pattern and its evidence. They remain blocked from live execution until product support, consumers, approvals and recovery are established.",
            "",
        ]
        counts = Counter(item["pattern_ref"] for item in pack["migration_candidates"])
        for pattern, count in sorted(counts.items()):
            lines.append(
                f"- {_pretty(pattern.replace('-', '_'))}: {count} use-level design candidates."
            )
        lines += [
            "",
            "For TLS, a successful hybrid key-exchange result does not establish post-quantum authentication. Certificate signatures and relying-party trust need their own evidence and transition plan.",
            "",
            "Each candidate needs owner-confirmed scope, current observations, client compatibility, exact product support and plan-bound approval. Recovery must define the previous state, access-preservation checks and independent readback; irreversible transitions need forward remediation rather than an invented rollback.",
            "",
            "Vendor statements, if imported, remain attributed source claims. Product support, blockers, roadmap commitments, license entitlement and regulatory acceptance require separate qualification; they do not become accepted facts automatically.",
            "",
        ]
    lines += ["## Look ahead: from evidence to controlled migration", ""]
    for item in pack["lookahead"]:
        lines += [
            f"### Phase {item['phase']}: {item['title']}",
            "",
            "Proposed only; not authorized.",
            "",
        ]
        lines.extend(f"- {text}" for text in item["work"])
        lines += ["", item["boundary"], ""]
    lines += [
        "## Decisions and open questions",
        "",
        "1. Which functions will confirm source-of-record boundaries, business owners and information lifetimes?",
        "2. Which exact product versions and read-only interfaces can be qualified with representative evidence?",
        "3. Who will approve evidence freshness, conflicting-source resolution and limitation acceptance?",
        "4. Which enterprise risk method and reviewers will replace the illustrative triage rules?",
        "5. Which bounded pilot cohort, consumer tests and recovery strategy should enter migration design?",
        "6. Which ticketing platform should host work and human approval records while the PQC application retains plan and verification authority?",
        "",
        "## Caveats and authority",
        "",
        "This is a source-derived synthetic development report, not a representation of the enterprise estate. No human acceptance, production risk rating, vendor qualification, source-system write or migration execution authority has been recorded.",
        "",
        "The supporting records prove this report's reproducible derivation and relationships. They do not establish an authenticated enterprise deployment or ongoing evidence collection. SSH and application/library migration proofs are separate lab tracks, not evidence inferred from TLS or certificate records.",
        "",
    ]
    lines += (
        _inventory_lines(pack)
        if phase == 1
        else _risk_lines(pack) + _context_lines(pack)
    )
    lines += [
        "## Evidence and reproduction references",
        "",
        "The machine-readable report pack is the complete appendix for source pages, observations, custody references, dependency links, candidate prerequisites and scenario definitions. Custody hashes identify retained synthetic source evidence; this projection does not independently re-open or decrypt those artifacts.",
        "",
        f"- Baseline SHA-256: `{pack['source_binding']['baseline_id']}`.",
        f"- Phase {phase} source report SHA-256: `{pack['source_binding'][f'phase{phase}_report_id']}`.",
        f"- Source estate SHA-256: `{pack['source_binding']['estate_content_sha256']}`.",
        f"- Scenario catalog SHA-256: `{pack['source_binding']['scenario_catalog_sha256']}`.",
        f"- Report-pack SHA-256: `{pack['content_sha256']}`.",
        "",
    ]
    return "\n".join(lines)
