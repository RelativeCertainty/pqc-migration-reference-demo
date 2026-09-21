<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Eighteen-week, two-phase PQC assessment project plan

This employer-neutral reference plan organizes a post-quantum cryptography
assessment into an 18-week engagement. Phase 1 establishes a defensible
current-state baseline during Weeks 1-8. Phase 2 evaluates technical and
business risk during Weeks 9-18. Engagement governance, reporting, and
stakeholder alignment operate across both phases.

The plan is a public template, not evidence that any organization has completed
the work. Relative weeks are planning windows rather than calendar commitments.
The versioned YAML backlog is authoritative; this document is a human-readable
projection of its epic and story structure.

## Delivery model and boundaries

- Phase 1, Weeks 1-8: confirm scope and method, establish safe source access,
  validate existing artifacts, discover the authorized estate, normalize and
  correlate observations, map dependencies, validate exposure and gaps, and
  issue the Current-State Assessment Report.
- Phase 2, Weeks 9-18: confirm the risk method, analyze technical exposure and
  decryption scenarios, evaluate libraries and vendor lifecycle, determine
  business and operational impact, prioritize risks and candidates, and issue
  the PQC Risk Register.
- Cross-phase, Weeks 1-18: maintain decision authority, schedule control,
  stakeholder alignment, RAID records, formal two-week reporting, findings
  reviews, and deliverable acceptance coordination.
- Assessment work does not authorize remediation, provider actions,
  configuration changes, deployment, revocation, ticket execution, procurement,
  certification, or acceptance of residual risk.
- Evidence retains source, freshness, confidence, and handling limits. Unknown,
  unmatched, stale, inferred, conflicting, and unavailable evidence remains
  visible rather than being promoted to fact.
- Private keys, secrets, credentials, customer captures, unrestricted raw
  payloads, and private engagement facts are outside this public plan.

## PQC-E00 — Engagement Governance, Reporting, and Stakeholder Alignment

Target window: Weeks 1-18, across both phases.

Purpose: Maintain decision authority, schedule control, stakeholder alignment,
reporting, RAID management, and deliverable acceptance across both assessment
phases.

Included:

- Governance, role, forum, escalation, and decision-authority definition.
- Risks, assumptions, issues, dependencies, decisions, actions, and scope-change control.
- Formal two-week reporting and phase review coordination.

Boundary: Excludes effectful remediation, system changes, and acceptance
decisions made without designated human authority. Planning outputs do not
authorize external effects; named human owners retain acceptance and exception
authority.

Completion: Governance records, formal reporting cycles, phase reviews, and
acceptance activities are complete or formally dispositioned.

High-level stories:

1. PQC-E00-S01 — Establish engagement governance, roles, forums, and escalation.
2. PQC-E00-S02 — Maintain RAID, decisions, dependencies, actions, and scope changes.
3. PQC-E00-S03 — Deliver biweekly status reporting, findings reviews, and acceptance coordination.

## Phase 1 — PQC Current-State Assessment

Phase 1 runs during Weeks 1-8. Its outcome is a validated, evidence-linked view
of the authorized cryptographic estate, its dependencies, material exposure
conditions, measured coverage, and known limitations. It produces the PQC
Current-State Assessment Report and a controlled Phase 2 input package.

### PQC-P1-E01 — Confirm Scope, Assessment Method, and Standards

Target window: Weeks 1-2.

Purpose: Define what will be assessed, how evidence will be evaluated, and what
constitutes a defensible Phase 1 result.

Included:

- Scope and exclusion definition.
- Assessment taxonomy and method.
- Standards and evidence-quality criteria.

Boundary: Excludes remediation design or execution, final Phase 2 risk scoring,
and unsupported claims of complete estate coverage. Planning outputs do not
authorize external effects.

Completion: Stakeholders can identify what is in scope, what is excluded, which
evidence is required, and how Phase 1 results will be evaluated.

High-level stories:

1. PQC-P1-E01-S01 — Confirm scope, exclusions, authority, and success criteria.
2. PQC-P1-E01-S02 — Establish the assessment method, taxonomy, and standards register.
3. PQC-P1-E01-S03 — Approve evidence-quality, coverage, confidence, and completion rules.

### PQC-P1-E02 — Establish Source Access and Evidence-Handling Controls

Target window: Weeks 1-3.

Purpose: Establish safe, approved, read-only access to assessment sources
without beginning uncontrolled collection.

Included:

- Authoritative source and owner register.
- Approved access and handling requirements.
- Source readiness and contingency assessment.

Boundary: Excludes remediation design or execution, final Phase 2 risk scoring,
and unsupported claims of complete estate coverage. No source is accessed
without authority, and protected evidence does not enter the public repository.

Completion: Every planned source has an owner role, approved collection method,
access state, handling classification, and contingency for unavailable access.

High-level stories:

1. PQC-P1-E02-S01 — Establish the authoritative source and source-owner register.
2. PQC-P1-E02-S02 — Confirm access, classification, retention, and handling requirements.
3. PQC-P1-E02-S03 — Validate source readiness and document unavailable-access contingencies.

### PQC-P1-E03 — Validate Existing Inventories and Assessment Artifacts

Target window: Weeks 2-4.

Purpose: Determine which existing inventory, architecture, security, and vendor
artifacts can be trusted and reused before initiating new discovery.

Included:

- Existing-artifact register.
- Authority and quality evaluation.
- Reuse and conflict disposition.

Boundary: Excludes remediation, Phase 2 scoring, and unsupported completeness
claims. Existing records are not authoritative merely because they exist;
conflicts and provenance remain visible.

Completion: Existing artifacts are classified as usable, conditionally usable,
superseded, conflicting, or insufficient with a recorded rationale.

High-level stories:

1. PQC-P1-E03-S01 — Inventory existing assessment sources and artifacts.
2. PQC-P1-E03-S02 — Evaluate authority, completeness, freshness, conflicts, and ownership.
3. PQC-P1-E03-S03 — Disposition each artifact as usable, conditional, superseded, conflicting, or insufficient.

### PQC-P1-E04 — Discover the Authorized Cryptographic Estate

Target window: Weeks 2-5.

Purpose: Collect provenance-preserving observations from authorized sources
without claiming completeness or risk.

Included:

- Authorized discovery plan.
- Controlled observation collection.
- Collection failure and limitation ledger.

Boundary: Discovery is read-only and limited to approved sources. It excludes
remediation, final risk scoring, private key collection, and unsupported
completeness claims.

Completion: Authorized sources have been assessed or collected, observations
retain provenance, and failed or unavailable paths are explicitly recorded.

High-level stories:

1. PQC-P1-E04-S01 — Prepare the authorized discovery and collection plan.
2. PQC-P1-E04-S02 — Collect cryptographic observations across approved estate domains.
3. PQC-P1-E04-S03 — Record provenance, collection failures, unavailable sources, and limitations.

### PQC-P1-E05 — Normalize, Correlate, and Measure Inventory Coverage

Target window: Weeks 3-6.

Purpose: Convert disconnected source records into a traceable canonical estate
with visible conflicts and uncertainty.

Included:

- Canonical observation normalization.
- Evidence-preserving correlation.
- Coverage and data-quality measurement.

Boundary: Excludes remediation and final risk scoring. Correlation preserves
provenance and confidence, and coverage is not represented as completeness
without an authoritative denominator.

Completion: The inventory has stable planning identities, traceable evidence,
documented correlation confidence, and quantified coverage and unknowns.

High-level stories:

1. PQC-P1-E05-S01 — Normalize observations into the canonical cryptographic asset model.
2. PQC-P1-E05-S02 — Correlate assets, services, endpoints, CIs, owners, and dependencies.
3. PQC-P1-E05-S03 — Measure coverage, duplication, staleness, conflicts, confidence, and unknowns.

### PQC-P1-E06 — Map Business, Data, Regulatory, and Technical Dependencies

Target window: Weeks 4-7.

Purpose: Attach the enterprise context needed to understand where cryptographic
assets matter and to support later risk analysis.

Included:

- Business-service and ownership mapping.
- Data and obligation context.
- Regional, third-party, and technical dependency validation.

Boundary: Excludes remediation and final Phase 2 scoring. Missing context stays
explicit; technical observations do not silently establish business ownership,
criticality, obligation, or impact.

Completion: Material assets and findings can be traced to relevant services,
data, owners, dependencies, and obligations or are explicitly marked as missing
that context.

High-level stories:

1. PQC-P1-E06-S01 — Map assets to business services, owners, and critical processes.
2. PQC-P1-E06-S02 — Map data classifications, confidentiality lifetimes, and obligations.
3. PQC-P1-E06-S03 — Validate technical, regional, third-party, and service dependencies.

### PQC-P1-E07 — Identify Exposure, Legacy Implementations, and Evidence Gaps

Target window: Weeks 5-7.

Purpose: Form evidence-backed findings about technical exposure and assessment
limitations without prematurely assigning final risk.

Included:

- Cryptographic exposure findings.
- Legacy and configurability constraints.
- Evidence-gap and Phase 2 candidate record.

Boundary: Excludes remediation and final Phase 2 scoring. Findings distinguish
observed, inferred, and unknown facts and do not claim certification or
unsupported estate coverage.

Completion: Findings have evidence, affected scope, confidence, ownership state,
and an explanation of uncertainty without presenting Phase 2 risk conclusions.

High-level stories:

1. PQC-P1-E07-S01 — Identify relevant algorithm, protocol, key-length, and exposure conditions.
2. PQC-P1-E07-S02 — Identify legacy, unsupported, fixed, or non-configurable implementations.
3. PQC-P1-E07-S03 — Document evidence gaps, unknowns, and Phase 2 analysis candidates.

### PQC-P1-E08 — Produce and Review the Current-State Assessment Report

Target window: Weeks 6-8.

Purpose: Consolidate Phase 1 evidence into the accepted PQC Current-State
Assessment Report and a controlled Phase 2 input package.

Included:

- Executive and technical report drafting.
- Findings review and factual reconciliation.
- Final report and Phase 2 handoff.

Boundary: Report acceptance does not assert universal inventory completeness,
resolve risk, or authorize remediation. Limitations and unresolved evidence
remain part of the accepted record.

Completion: The Current-State Assessment Report is delivered, reviewed, revised
as appropriate, and accepted or dispositioned through governance.

High-level stories:

1. PQC-P1-E08-S01 — Draft the executive, technical, scope, method, inventory, and findings sections.
2. PQC-P1-E08-S02 — Conduct the Phase 1 findings-review session and reconcile factual feedback.
3. PQC-P1-E08-S03 — Issue the final report and approved Phase 2 input package.

## Phase 2 — PQC Risk and Business Impact Analysis

Phase 2 runs during Weeks 9-18. It evaluates the technical and business
significance of the accepted Phase 1 baseline and delivers an evidence-linked,
prioritized PQC Risk Register with decision-ready recommendations and an
exception record.

### PQC-P2-E01 — Confirm Risk Method and Phase 2 Readiness

Target window: Weeks 9-10.

Purpose: Confirm that Phase 1 evidence is fit for risk analysis and establish
transparent risk, confidence, prioritization, and exception rules.

Included:

- Phase 2 entry assessment.
- Risk-rating and confidence method.
- Exception and incomplete-evidence governance.

Boundary: Excludes production remediation, unauthorized risk or exception
acceptance, and claims that recommendations are approved implementation
commitments.

Completion: The risk method is accepted, required Phase 1 inputs are available,
and material evidence gaps have an agreed treatment.

High-level stories:

1. PQC-P2-E01-S01 — Validate the Phase 1 baseline and Phase 2 entry conditions.
2. PQC-P2-E01-S02 — Establish the risk dimensions, ratings, confidence, and prioritization method.
3. PQC-P2-E01-S03 — Establish exception, incomplete-evidence, and review governance.

### PQC-P2-E02 — Analyze Cryptographic Exposure and Decryption Scenarios

Target window: Weeks 10-13.

Purpose: Evaluate the technical significance of observed cryptographic
conditions, data lifetime, adversary opportunity, and migration constraints.

Included:

- Algorithm and protocol exposure analysis.
- Store-now/decrypt-later scenarios.
- Crypto-agility and concentration analysis.

Boundary: Excludes production remediation and unauthorized risk acceptance.
Scenario analysis is not a prediction of a quantum-computing date or a guarantee
of exploitability.

Completion: Each material exposure has a documented technical rationale,
affected scope, uncertainty, and relationship to future migration concerns.

High-level stories:

1. PQC-P2-E02-S01 — Analyze algorithm, protocol, key-strength, and configuration exposure.
2. PQC-P2-E02-S02 — Analyze data lifetime and store-now/decrypt-later scenarios.
3. PQC-P2-E02-S03 — Analyze crypto-agility, concentration, and migration constraints.

### PQC-P2-E03 — Analyze Library, Vulnerability, and Vendor-Lifecycle Risk

Target window: Weeks 10-14.

Purpose: Determine how software dependencies, vulnerability intelligence,
support status, and vendor roadmaps affect risk and migration feasibility.

Included:

- Library and module analysis.
- Vendor support and roadmap analysis.
- External dependency and blocker analysis.

Boundary: Excludes production remediation and unapproved implementation
commitments. Vendor statements retain source and date; absent evidence is not
proof of readiness and analysis is not a product endorsement.

Completion: Material library and vendor dependencies are reflected in risk
analysis with blockers, provenance, confidence, and external dependencies.

High-level stories:

1. PQC-P2-E03-S01 — Analyze cryptographic libraries, modules, versions, and vulnerability intelligence.
2. PQC-P2-E03-S02 — Analyze vendor support, end-of-life status, and published roadmaps.
3. PQC-P2-E03-S03 — Identify external dependencies, unsupported products, and vendor blockers.

### PQC-P2-E04 — Evaluate Business-Service and Operational Impact

Target window: Weeks 11-15.

Purpose: Translate technical exposure into business, operational, regulatory,
customer, and reputational consequences.

Included:

- Business-service and critical-process impact.
- Data and obligation impact.
- Operational disruption and blast-radius impact.

Boundary: Excludes production remediation and unauthorized risk acceptance.
Technical observations do not establish business impact without supporting
evidence or validation by accountable owners.

Completion: Material technical risks have documented business-service impact,
affected stakeholders, consequence rationale, and unresolved context gaps.

High-level stories:

1. PQC-P2-E04-S01 — Evaluate business-service and critical-process impact.
2. PQC-P2-E04-S02 — Evaluate data, regulatory, contractual, customer, and reputational impact.
3. PQC-P2-E04-S03 — Evaluate operational disruption, regional blast radius, and recovery implications.

### PQC-P2-E05 — Prioritize Risks, Candidates, and Exceptions

Target window: Weeks 14-16.

Purpose: Produce a transparent order of attention and decision-ready cohorts
without creating remediation execution authority.

Included:

- Evidence-based risk prioritization.
- Candidate cohort formation.
- Exception and unresolved-decision record.

Boundary: Candidates are assessment outputs, not approved changes, procurement
choices, committed roadmaps, or execution instructions. Exceptions retain named
human decision authority.

Completion: Risks can be compared consistently, priority decisions are
justified, and exceptions or deferred items have an owner role and rationale.

High-level stories:

1. PQC-P2-E05-S01 — Prioritize risks using technical exposure, impact, confidence, and feasibility.
2. PQC-P2-E05-S02 — Group remediation and investigation candidates into decision-ready cohorts.
3. PQC-P2-E05-S03 — Document exceptions, deferrals, vendor dependencies, and unresolved decisions.

### PQC-P2-E06 — Produce and Review the PQC Risk Register

Target window: Weeks 16-18.

Purpose: Deliver the authoritative Phase 2 risk register, reconcile stakeholder
challenge, and obtain formal disposition.

Included:

- Evidence-linked risk-register assembly.
- Stakeholder challenge and correction.
- Final register and engagement handoff.

Boundary: The register does not claim that risk has been accepted, remediated,
or transferred without an explicit accountable decision. Implementation and
remediation remain separately authorized work.

Completion: The risk register has been delivered, reviewed, reconciled with
stakeholder feedback, and accepted or formally dispositioned.

High-level stories:

1. PQC-P2-E06-S01 — Assemble evidence-linked risk-register entries.
2. PQC-P2-E06-S02 — Conduct stakeholder review, challenge, and correction.
3. PQC-P2-E06-S03 — Issue the accepted register, recommendations, exceptions, and handoff package.

## Future-state appendix — outside the two-phase backlog

The v2 backlog preserves six possible follow-on capabilities without admitting
them into the 18-week assessment. The appendix is explicitly marked
`jiraProjection: false` and `futureAuthorizationRequired: true`. Its items are
not current epics or stories, do not carry delivery status, and must not be
scheduled, projected to Jira, or treated as authority for external effects.

1. FUT-01 — Standardized remediation work-item lifecycle. Translate prioritized findings into asset-type-specific work items only after remediation scope and ownership are approved.
2. FUT-02 — Immutable remediation planning and approval binding. Bind future changes to a versioned plan, asset state, approval record, window, rollback path, and one-use execution authority.
3. FUT-03 — Ticket and change lifecycle automation. Integrate governed work items with ticket, change, task, approval, evidence, and closure workflows through provider-neutral ports.
4. FUT-04 — Controlled execution and rollback adapters. Implement exact-plan, approval-bound, ledgered, reversible actions only for asset classes with safe provider behavior and readback.
5. FUT-05 — Independent verification, reharvest, and closure guard. Close future work only when independent readback and fresh inventory evidence match the approved target state.
6. FUT-06 — Optional migration roadmap and operating-model extension. Convert accepted risks and candidates into capacity-aware horizons, ownership, training, and operating practices under separate scope.

## Projection and change control

`planning/backlog.v2.yaml` remains the planning source of truth. Jira epics and
stories, status reports, rolling-wave views, and this document are projections.
Scope, acceptance, dependencies, status, evidence requirements, and phase
decisions change in YAML first and then propagate to projections. Planning IDs
are stable references rather than Jira keys. The legacy 12-week plan remains
available only for migration lineage and comparison.
