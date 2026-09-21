<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# PQC assessment method

## 1. Establish authority

Define sponsor, in-scope estates, source owners, data classification,
retention, decision rights, escalation, and change authority before
collection. Read-only collection does not imply permission to publish or
modify.

## 2. Define the canonical inventory contract

Capture asset and service identity, accountable owner, environment, algorithm,
protocol, key/certificate metadata without key material, dependency, data
lifetime, external exposure, vendor, source, confidence, freshness, and
unresolved conflicts.

## 3. Mobilize sources

Classify each source as authoritative, corroborating, or discovery-only.
Candidate sources include source scanning, PKI, network observations, CMDB,
cloud inventory, vulnerability platforms, KMS/HSM metadata, and vendor
attestations.

## 4. Normalize and reconcile

Use source-specific anti-corruption adapters. Preserve provenance, deduplicate
without erasing disagreement, expose stale evidence, and route low-confidence
matches to human review.

## 5. Contextualize and prioritize

Score transparent factors rather than hiding judgment in a single opaque
number:

- Quantum-vulnerable public-key use and harvest-now exposure.
- Data confidentiality and authenticity lifetime.
- Business criticality and external exposure.
- Migration readiness and crypto-agility.
- Vendor and interoperability dependencies.
- Change complexity, rollback, and compensating controls.

## 6. Plan migration waves

Separate urgent cohorts, proof candidates, vendor-blocked assets, unsupported
technology, and approved exceptions. Give each wave measurable entry and exit
criteria across 90-day, 12-month, 24-month, and 36-month horizons.

## 7. Execute evidence-gated slices

Use repository, TLS/PKI, and SSH as the first reference slices. Close a slice
only at the evidence level actually demonstrated.

## 8. Report limitations

Report coverage denominator, unmatched records, stale evidence, source gaps,
unknown ownership, conflicts, false-positive risk, and untested runtime
behavior. Never infer completeness from tool execution.
