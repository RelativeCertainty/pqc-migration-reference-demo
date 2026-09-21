<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Synthetic source contract laboratory

This directory contains independently authored, product-neutral fixtures for
five source families used by the deterministic Phase 1 proof:

- application portfolio, business services, and configuration inventory;
- PKI and certificate lifecycle metadata;
- TLS termination and traffic-management configuration;
- source-code repository catalogs; and
- SAST, SCA, SBOM, and related software-analysis signals.

Each pack has a versioned manifest and two linked pages. Cursor values are
opaque synthetic references. Records use nonresolvable synthetic identifiers
and exclude credentials, personal data, key material, source excerpts,
certificate subjects and issuers, raw provider payloads, and vendor claims.

The packs prove only the public contract shape and deterministic pagination
behavior. They do not prove a live integration, a vendor edition, authorized
customer access, enterprise coverage, source accuracy, or production
readiness.

## Executable proof

From the repository root, run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate-synthetic-phase1-proof.py
```

The validator:

1. checks all five new JSON Schemas;
2. validates six metric definitions;
3. walks the five two-page cursor chains;
4. rejects duplicate source-record identities and unsafe fixture fields;
5. resolves source records into ten normalized observations, eight canonical
   assets, and eight dependencies across two synthetic regions; and
6. recomputes source readiness, authorized-scope coverage, evidence freshness,
   correlation confidence, evidence limitations, and projection lag before
   comparing them to the golden projection.

## Metric guardrails

`DashboardMetricDefinition.v1` separates the six questions instead of
compressing them into a posture score. In particular:

- Coverage requires a named authorized scope, an independently supplied
  denominator, an asset unit, and an as-of time. A missing or zero denominator
  is `unavailable`, never zero percent.
- Readiness describes planned source families that passed declared checks. It
  is not estate coverage.
- Freshness describes evidence age under a stated threshold. It is not source
  accuracy.
- Confidence describes the evidence basis for a correlation. It is not a
  statistical probability of truth.
- Limitations remain visible records. Their count is not a success score.
- Projection lag measures dashboard currency relative to represented committed
  state. It is not evidence age.

The golden dashboard fixture explicitly forbids claims of enterprise
completeness, risk conclusion, migration completion, production state, or
write authority.
