"""Deterministic offline raw observations for all 24 extended reference families."""

from __future__ import annotations

import copy
import hashlib
from typing import Any

from workers.pqc.extended_sources import PAGE_VERSION, extended_family_profiles, extended_page_digest, normalize_extended_page


TENANT_ID = "synthetic-enterprise"
OBSERVED_AT = "2026-09-05T10:00:00Z"


def _native_relation(family: str, namespace: str, index: int, cohort: int) -> str:
    prefix = "service" if namespace == "business-service" else {
        "cmdb": "app", "certificate-lifecycle": "cert", "traffic-termination": "endpoint"
    }.get(family, family)
    serial = index
    if namespace == "business-service":
        serial = (cohort - 1) % 8 + 1
    elif family == "cmdb":
        serial = cohort
    elif family in {"certificate-lifecycle", "traffic-termination"}:
        serial = (cohort - 1) * 2 + 1
    return f"{prefix}-{serial:03d}"


def generate_extended_pages(seed: int = 7, application_count: int = 36) -> list[dict[str, Any]]:
    """Return 24 bounded pages, 72 unique subjects, without I/O or credentials.

Each family has two attributable reference cases and one missing-context case.
Capability-only, explicitly unknown algorithms and independently based uses are
declared in the machine dossiers. ``complete`` means this synthetic three-row
collection only, never complete product, tenant, area or enterprise inventory.
"""
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("invalid_synthetic_seed")
    if type(application_count) is not int or not 12 <= application_count <= 60:
        raise ValueError("synthetic_application_count_must_be_12_to_60")
    pages = []
    for kind, profile in extended_family_profiles().items():
        source = f"synthetic-{kind}"
        records = []
        for offset in range(3):
            index = offset + 1
            # All family-001 examples share app-001, building a fully joinable
            # cohort. The second cohort varies reproducibly by seed; absent
            # application context on the third record remains explicit.
            # The core deliberately gives app-003 orphan/missing certificate
            # and TLS attribution. Keep that explicit core scenario separate
            # from the joinable second extended-family cohort.
            candidates = [number for number in range(2, application_count + 1) if number != 3]
            cohort = 1 if index == 1 else candidates[int.from_bytes(hashlib.sha256(f"{seed}:cohort".encode("ascii")).digest()[:4], "big") % len(candidates)]
            row = {"id": f"{kind}-{index:03d}", "name": f"Synthetic {kind.replace('-', ' ')} record {index:03d}",
                   "evidence_basis": ("observed", "configured", "vendor_reported")[offset],
                   "application_id": None if index == 3 else f"app-{cohort:03d}"}
            for field, descriptor in profile["fields"].items():
                row[field] = copy.deepcopy(descriptor["samples"][offset])
            for field, relation in profile["relations"].items():
                row[field] = None if index == 3 else _native_relation(relation["target_family"], relation["namespace"], index, cohort)
            for use in profile["uses"]:
                for suffix, samples in use["samples"].items():
                    row[use["prefix"] + "_" + suffix] = samples[offset]
            records.append(row)
        payload = {"schema_version": PAGE_VERSION, "synthetic": True, "kind": kind,
                   "tenant_id": TENANT_ID, "source_instance_id": source, "records": records,
                   "next_cursor": None}
        payload["content_sha256"] = extended_page_digest(payload)
        normalize_extended_page(kind, payload, tenant_id=TENANT_ID, source_instance_id=source, observed_at=OBSERVED_AT)
        pages.append({"source": source, "page_id": "page-001", "kind": kind, "payload": payload,
                      "observed_at": OBSERVED_AT, "complete": True, "expected_cursor": None})
    return pages
