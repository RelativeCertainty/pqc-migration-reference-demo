<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Twelve-week PQC consulting plan

> **Legacy plan:** This 12-week plan is retained for historical and migration
> lineage. It is superseded for current planning by the
> [18-week, two-phase PQC assessment project plan](two-phase-assessment-project-plan.md)
> and its [authoritative v2 YAML backlog](../planning/backlog.v2.yaml). Do not
> project new work from this document.

This employer-neutral template fixes epics and acceptance gates while allowing
authorized tooling, cohorts, schedules, and coverage targets to be calibrated
during Week 1.

## E1 - Program mobilization and governance, Weeks 1-2

- Charter: sponsor, outcomes, scope, exclusions, measures, decision rights, escalation, cadence.
- Governance: stakeholder map, RACI, RAID, decision log, evidence gates, architecture and risk forums.
- Standards: authoritative register separating final standards, drafts, sector guidance, and vendor claims.
- Interim policy: approved algorithms, hybrid treatment, exceptions, evidence, and crypto-agility.
- G1: sponsor and accountable security stakeholders accept governance and the first 90-day definition of done.

## E2 - Cryptographic assessment and inventory, Weeks 1-4

- Canonical contract: asset, service, owner, data lifetime, algorithm, protocol, key/certificate metadata, dependency, environment, exposure, vendor, confidence, source, and freshness without key material.
- Reconciliation: source authority, provenance, deduplication, conflict, staleness, and human review.
- Source mobilization: PKI, code, network, CMDB, cloud, vulnerability, KMS/HSM, and vendor sources.
- Pilot: select an authorized read-only cohort with classification and retention.
- Baseline: normalize observations and measure coverage, unmatched records, conflicts, duplicates, stale evidence, and unknown ownership.
- G2: measurable pilot baseline with explicit confidence and unknowns.

## E3 - Risk, dependencies, and roadmap, Weeks 2-5

- Context: business services, sensitive data, retention, exposure, criticality, change control, and vendors.
- Priority policy: harvest-now risk, vulnerable public-key use, data lifetime, exposure, criticality, readiness, agility, and controls.
- Waves: urgent, pilot-ready, vendor-blocked, unsupported, and exception cohorts.
- Horizons: 90-day, 12-month, 24-month, and 36-month exits with dependencies and capacity.
- G3: risk, architecture, and business owners accept the first wave and ordering rationale.

## E4 - Crypto-agile architecture and sourcing, Weeks 2-6

- Target: domain-owned policy, replaceable algorithm profiles, provider-neutral ports, anti-corruption adapters, evidence, and independent verification.
- Patterns: TLS, PKI, KMS/HSM, SSH, APIs, VPNs, signing, hybrid operation, rollback, and compatibility fallback.
- Sourcing: score tools and build options on coverage, authority, integration, evidence, support, cost, and lock-in.
- Decisions: name systems of record and the deliberately small custom-engineering surface.
- G4: architecture governance accepts pilot patterns and ownership boundaries.

## E5 - Vertical proof slices, Weeks 3-10

- Repository, Weeks 3-5: scan an authorized source cohort, reconcile dependencies, measure coverage, and generate proposals or approved pull requests while retaining human merge authority.
- TLS/PKI, Weeks 5-8: inventory endpoints, lab-test classical/hybrid/target profiles, pilot with rollback, then capture interoperability, performance, chain, and readback evidence.
- SSH, Weeks 7-10: inventory clients, servers, key exchange, administration, and fallback; pilot approved hybrid exchange where supported and independently verify negotiation and rollback.
- G5: close only with authorized change, readback, benchmark, and rollback evidence.

## E6 - Validation, compliance, and operations, Weeks 4-11

- Tests: functional, interoperability, performance, negative, failure injection, rollback, and regression.
- Evidence: versioned request, decision, execution, result, readback, timestamps, and accountable owner.
- Controls: tickets, approvals, exception expiry, idempotency, incident handling, rollback, and retention.
- Mapping: connect practices to applicable risk and audit controls without certification claims.
- Measures: coverage, ownership, staleness, high-risk backlog, vendor readiness, pilot/rollback success, and validated migration rate.
- G6: risk, audit, operations, and architecture accept the evidence model and procedures.

## E7 - Enablement and handoff, Weeks 7-12

- Training: executive, program, architecture, engineering, risk, and operations modules.
- Labs: repository, TLS, and SSH examples teach method and architecture.
- Ownership: inventory, policy, architecture, pilots, exceptions, evidence, vendors, and metrics.
- Transfer: backlog, patterns, playbooks, decisions, training, and next-wave roadmap.
- G7: named internal owners can assess, prioritize, and run the next authorized pilot without consultant dependence.
