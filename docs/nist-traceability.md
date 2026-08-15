# NIST traceability for the PQC migration reference demo

Status: implemented design reference with bounded public-boundary evidence

Evidence as of: 2026-08-13

Source scope: official NIST properties only (`nist.gov`, `csrc.nist.gov`, and NIST subdomains)

## Purpose and interpretation boundary

This document traces the demo's migration model to current NIST standards, guidance, project material, and validation programs. It does not assert that the demo is NIST certified, FIPS compliant, production ready, or a completed migration.

The six labels below mirror headings in the NIST NCCoE's supplementary PQC FAQ, which says it groups common questions into six phases. The FAQ is explicitly non-exhaustive and periodically updated. Turning those headings into an ordered lifecycle with required artifacts, gates, and demo behavior is a reference-demo synthesis. It is not a NIST-prescribed taxonomy, maturity model, or implementation method. See [SRC-NIST-001](https://pages.nist.gov/nccoe-migration-post-quantum-cryptography/FAQ/) (living supplementary material, last updated 2026-06-30; status checked and accessed 2026-08-13).

NIST CSF 2.0 is used as a governance overlay, not as another migration sequence. Its six Functions are concurrent and continuous cybersecurity outcomes, and the framework does not prescribe how outcomes must be achieved. The phase-to-Function associations in this document are therefore an illustrative demo mapping. See [SRC-NIST-003](https://csrc.nist.gov/pubs/cswp/29/the-nist-cybersecurity-framework-csf-20/final) (Final, 2024-02-26; accessed 2026-08-13) and [SRC-NIST-014](https://www.nist.gov/cyberframework/faqs) (living NIST FAQ; accessed 2026-08-13).

## Source authority rules

- A Final FIPS or Final NIST publication may support claims within its stated scope.
- A planning note or errata notice must travel with any implementation claim affected by it. Final status does not erase current errata.
- An Initial Public Draft or Initial Preliminary Draft may support exploration and planning language only. It must not be presented as a final requirement, settled deadline, or final NIST recommendation.
- A living project page or FAQ may describe current NIST project direction and terminology. It is not automatically a standard or normative control.
- A demo mapping, record schema, score, gate, or workflow must be labeled as a demo design choice unless NIST specifies it directly.
- Source status must be rechecked before publication, procurement, production activation, or an assurance claim. The authoritative status ledger is `source-status-registry.md`.

## Six-stage demo lifecycle

The stages are presented in a useful operating order, but discovery, risk reassessment, testing, and monitoring are expected to loop as evidence changes.

### 1. Awareness and Preparation

NIST basis:

- The NCCoE FAQ uses this phase heading and describes PQC preparation, terminology, crypto agility, standards, and policy resources. [SRC-NIST-001](https://pages.nist.gov/nccoe-migration-post-quantum-cryptography/FAQ/) (living; updated 2026-06-30; accessed 2026-08-13).
- The NCCoE project says migration requires understanding quantum-vulnerable public-key use in hardware, software, and services and developing prioritized roadmaps. [SRC-NIST-002](https://www.nccoe.nist.gov/applied-cryptography/migration-to-pqc) (active project, `Reviewing Comments`; accessed 2026-08-13).

Demo objective:

- Establish scope, accountable owners, protected business outcomes, risk assumptions, terminology, and evidence rules.
- Record which systems, data lifetimes, dependencies, and environments are in scope before scoring or recommending a change.
- Make crypto agility an architectural quality and operating capability from the outset.

Minimum evidence:

- Scope statement and exclusions.
- Named decision owner and technical owner.
- Business-critical services and data-protection horizons.
- Source snapshot with status dates.
- Assumptions, unknowns, and a review cadence.

Illustrative CSF 2.0 overlay: Govern is primary; Identify supports scope and context. This mapping is a demo interpretation, not an official NIST crosswalk.

Exit posture: prepared to inventory, not "quantum ready."

### 2. Discovery and Inventory

NIST basis:

- The NCCoE FAQ defines a cryptographic inventory as a descriptive record of cryptography used across systems, applications, services, devices, and data flows. It lists algorithms, protocols and services, key metadata without key material, certificates, dependent components, and protected data as possible inventory content. [SRC-NIST-001](https://pages.nist.gov/nccoe-migration-post-quantum-cryptography/FAQ/) (living; updated 2026-06-30; accessed 2026-08-13).
- The NCCoE project focuses one workstream on cryptographic discovery and the use of inventories for risk management and prioritization. [SRC-NIST-002](https://www.nccoe.nist.gov/applied-cryptography/migration-to-pqc) (active project; accessed 2026-08-13).
- SP 1800-38B describes discovery-tool demonstrations, but remains preliminary. [SRC-NIST-011](https://csrc.nist.gov/pubs/sp/1800/38/iprd-%281%29) (Initial Preliminary Draft, 2023-12-19; accessed 2026-08-13).

Demo objective:

- Normalize observed and declared cryptographic use into one canonical demo inventory.
- Preserve provenance, confidence, conflicts, and unknowns instead of collapsing them into unsupported certainty.
- Link cryptographic use to business services, protected data, dependencies, and replacement boundaries.

Minimum evidence:

- Reproducible discovery source or accountable declaration for each record.
- Observation time, scope, and environment.
- Algorithms, protocols, roles, implementation/provider details, and dependent assets when known.
- Explicit `unknown` or `conflicted` values where evidence is incomplete.
- No secret keys, private-key material, passwords, tokens, or unredacted sensitive payloads.

Illustrative CSF 2.0 overlay: Identify is primary; Govern sets inventory ownership, scope, and policy.

Exit posture: inventory coverage is measured and residual blind spots are named; completeness is not assumed.

### 3. Risk Assessment and Planning

NIST basis:

- The NCCoE FAQ says discovery and inventory reveal the extent, location, and use of current cryptography so an organization can understand what needs migration. [SRC-NIST-001](https://pages.nist.gov/nccoe-migration-post-quantum-cryptography/FAQ/) (living; updated 2026-06-30; accessed 2026-08-13).
- The NCCoE project connects cryptographic inventories with risk management, prioritization, and roadmaps. [SRC-NIST-002](https://www.nccoe.nist.gov/applied-cryptography/migration-to-pqc) (active project; accessed 2026-08-13).
- NIST IR 8547 describes an expected transition approach and proposed timelines, but it remains nonfinal. [SRC-NIST-009](https://csrc.nist.gov/pubs/ir/8547/ipd) (Initial Public Draft, 2024-11-12; comments closed; accessed 2026-08-13).

Demo objective:

- Prioritize records using business impact, data-protection horizon, exposure, cryptographic role, replaceability, vendor readiness, and evidence confidence.
- Produce a roadmap with decisions, dependencies, owners, target states, rollback needs, and explicitly accepted residual risk.
- Keep any numeric priority or risk score explainable and labeled as a demo method.

Minimum evidence:

- Rationale for quantum-vulnerability classification.
- Business criticality and protected-data lifetime.
- Dependency and support-lifecycle analysis.
- Migration option analysis, constraints, owner, and review date.
- Separate facts, draft planning inputs, assumptions, and unresolved questions.

Illustrative CSF 2.0 overlay: Govern and Identify are primary. Protect, Respond, and Recover inform target controls, contingency, and rollback planning.

Exit posture: an evidence-backed plan exists; draft NIST dates are not represented as final mandates.

### 4. Migration Execution

NIST basis:

- FIPS 203 specifies ML-KEM; FIPS 204 specifies ML-DSA; FIPS 205 specifies SLH-DSA. All three are Final. [SRC-NIST-005](https://csrc.nist.gov/pubs/fips/203/final), [SRC-NIST-006](https://csrc.nist.gov/pubs/fips/204/final), and [SRC-NIST-007](https://csrc.nist.gov/pubs/fips/205/final) (Final, 2024-08-13; accessed 2026-08-13).
- SP 800-227 gives final recommendations for secure KEM implementation and use. [SRC-NIST-008](https://csrc.nist.gov/pubs/sp/800/227/final) (Final, 2025-09-18; accessed 2026-08-13).
- FIPS 203 has a 2025-11-17 planning note and FIPS 204 has a 2026-07-31 planning note pointing to potential updates/errata. Their Final status remains, but implementations must evaluate the current errata.

Demo objective:

- Change only the approved, bounded cryptographic use and its dependencies.
- Preserve compatibility, observability, configuration provenance, and a tested rollback path.
- Record the exact algorithm, parameters, implementation, module, protocol integration, environment, and operational mode rather than using an undifferentiated `PQC enabled` flag.

Minimum evidence:

- Approved change scope tied to inventory record IDs.
- Target standard and current errata review.
- Implementation and configuration identity.
- Dependency and interoperability plan.
- Rollback criteria and accountable approver.
- No completion claim before testing and operational validation.

Illustrative CSF 2.0 overlay: Protect is primary; Govern controls authorization and exceptions; Recover supports reversibility.

Exit posture: a bounded implementation candidate exists, not a validated product or completed migration.

### 5. Migration Testing

NIST basis:

- The NCCoE interoperability workstream seeks compatibility findings in controlled, non-production environments. [SRC-NIST-002](https://www.nccoe.nist.gov/applied-cryptography/migration-to-pqc) (active project; accessed 2026-08-13).
- SP 1800-38C contains preliminary interoperability and performance results produced before December 2023 with draft PQC KEM standards. Those results are historical exploration, not current final-standard conformance evidence. [SRC-NIST-011](https://csrc.nist.gov/pubs/sp/1800/38/iprd-%281%29) (Initial Preliminary Draft; accessed 2026-08-13) and [SRC-NIST-001](https://pages.nist.gov/nccoe-migration-post-quantum-cryptography/FAQ/) (living; accessed 2026-08-13).
- CAVP tests approved algorithm implementations; it does not replace protocol, integration, performance, failure-mode, or operational testing. [SRC-NIST-012](https://csrc.nist.gov/Projects/cryptographic-algorithm-validation-program) (program page updated 2026-08-12; accessed 2026-08-13).

Demo objective:

- Test correctness, interoperability, performance, failure behavior, downgrade/negotiation behavior where applicable, observability, and rollback in the claimed environment.
- Keep test evidence bound to versions, configuration, scope, and time.
- Distinguish a local or synthetic test result from a NIST validation certificate.

Minimum evidence:

- Test plan and expected results.
- Exact implementation and environment identifiers.
- Positive, negative, regression, compatibility, and rollback results.
- Performance measurements with stated conditions.
- Failed, skipped, and out-of-scope cases retained.

Illustrative CSF 2.0 overlay: Protect and Detect are primary; Respond and Recover readiness are exercised; Govern controls acceptance criteria.

Exit posture: the bounded candidate passed stated tests, with residual gaps preserved. This does not establish CAVP or CMVP status.

### 6. Validation and Monitoring

NIST basis:

- CAVP validates approved cryptographic algorithm implementations and individual components. Algorithm validation is a prerequisite for cryptographic module validation, but is not itself module validation. [SRC-NIST-012](https://csrc.nist.gov/Projects/cryptographic-algorithm-validation-program) (updated 2026-08-12; accessed 2026-08-13).
- CMVP validates cryptographic modules against FIPS 140. Certificates are scoped to the module, version, operational environment, and approved mode described by the entry. CMVP does not assess supply-chain suitability, and an algorithm certificate alone does not make a product or module FIPS 140 validated. [SRC-NIST-013](https://csrc.nist.gov/Projects/cryptographic-module-validation-program/validated-modules) (updated 2026-08-07; accessed 2026-08-13).

Demo objective:

- Verify that every assurance statement names its scope and evidence class.
- Monitor inventory drift, implementation/configuration changes, certificate state, exceptions, control effectiveness, and source-status changes.
- Reopen discovery, risk, execution, or testing when evidence changes.

Minimum evidence:

- Exact CAVP or CMVP certificate reference when such validation is claimed.
- Match among certificate scope, module/version, operational environment, configuration, and approved mode.
- Current operational test evidence and monitoring time.
- Residual-risk owner, expiration/review date, and remediation trigger.
- Source revalidation for draft-to-final transitions and errata.

Illustrative CSF 2.0 overlay: Govern and Detect are primary; Respond and Recover apply when monitoring reveals a failure or unacceptable drift; Identify updates the inventory.

Exit posture: assurance is bounded to current evidence. `Validated` must never stand alone without its subject, scope, program, and date.

## Canonical cryptographic inventory contract

`Canonical` means the demo has one normalized record contract used across all six stages. It does not mean NIST publishes or requires this exact schema. NIST supplies the inventory purpose and representative content; the fields below add demo governance and traceability.

Each inventory record should carry:

1. Record identity and provenance

   - Stable `inventory_record_id`.
   - Observation or declaration time.
   - Discovery method and sanitized source locator.
   - Evidence state: `verified`, `partially_verified`, `probable`, `assumption`, or `unresolved`.
   - Observation kind: `observed`, `declared`, `inferred`, `unknown`, or `conflicted`.
   - Evidence owner and next review date.

2. Business and system context

   - Organization boundary, environment, service, system, application, component, device, and data flow.
   - Business and technical owners.
   - Criticality, exposure, data classification, retention, and confidentiality lifetime.
   - Upstream, downstream, vendor, and shared-service dependencies.

3. Cryptographic use

   - Security purpose and operation: key establishment, signature, encryption, authentication, integrity, certificate use, or another stated purpose.
   - Protocol or service, algorithm family, exact algorithm/parameter set when known, and negotiation context.
   - Library/provider/module and version; operational environment and approved mode when relevant.
   - Key and certificate metadata such as type, owner, algorithm, expiration, lifecycle state, and chain reference, but never key material.
   - Protected data and its relevant lifetime.

4. Risk and migration state

   - Quantum-vulnerability classification, rationale, and source.
   - Business impact, data-horizon exposure, dependency constraints, replaceability, and vendor readiness.
   - Priority and rationale; any score labeled as a demo calculation.
   - Target state, lifecycle stage, decision owner, exception, review date, and rollback boundary.

5. Testing, validation, and monitoring

   - Test scope, environment, result, evidence locator, and timestamp.
   - CAVP certificate identifier and exact implementation scope, if applicable.
   - CMVP certificate identifier, module/version, operational environment, status, and approved mode, if applicable.
   - Last observed configuration, drift state, monitoring result, and unresolved gaps.

Records from multiple discovery sources are not silently merged when they disagree. The canonical view retains source-specific observations and exposes the conflict for review.

## Crypto agility acceptance model

NIST defines crypto agility as the capabilities needed to replace and adapt cryptographic algorithms across protocols, applications, software, hardware, firmware, and infrastructures while preserving security and ongoing operations. See [SRC-NIST-004](https://csrc.nist.gov/pubs/cswp/39/upd1/considerations-for-achieving-crypto-agility/final) (Final update dated 2026-06-29; accessed 2026-08-13).

For this demo, evidence of crypto agility requires more than an algorithm selector. The record should show:

- Where algorithm choice and policy are controlled.
- Which protocol, API, data-format, hardware, certificate, and vendor dependencies constrain replacement.
- Whether implementation changes can be staged, observed, tested, rolled back, and audited.
- How compatibility and downgrade/failure behavior are handled.
- How inventories and policies are updated after a change.
- Which constraints or hard-coded dependencies remain.

This is a demo operationalization of the final NIST concept, not a NIST conformance test or score.

## Validation vocabulary

Use these statements precisely:

- `Tested in the demo` means only that the stated test ran in the stated environment and produced the recorded result.
- `CAVP validated` may be used only for the exact algorithm implementation represented by a current official validation entry. It does not mean the containing product or module is FIPS 140 validated.
- `CMVP validated` may be used only for the exact cryptographic module, version, operational environment, and mode represented by a current official certificate. It does not establish product-wide security, supply-chain suitability, protocol interoperability, secure deployment, or fitness for a business use.
- `Uses a NIST-standardized algorithm` describes algorithm selection. It does not establish implementation correctness, certificate status, module validation, protocol behavior, or migration completion.
- `PQC migration complete`, `NIST certified`, `NIST compliant`, `quantum proof`, and unqualified `quantum safe` are not supported by this reference demo.

## Residual gaps and watch items

- NIST IR 8547 remains an Initial Public Draft. Its proposed transition dates may change and cannot be presented as final requirements.
- CSWP 48 remains an Initial Public Draft. The demo's CSF overlay is interpretive; a future final mapping may require revision.
- SP 1800-38A/B/C remains Initial Preliminary Draft material. The NCCoE project says future updates will move into other draft white papers, tech notes, and informational reports.
- The six phase labels appear in a living, non-exhaustive NCCoE FAQ. The demo lifecycle and gates must be rechecked if that FAQ changes.
- FIPS 203 and FIPS 204 are Final but have active planning notes for potential updates. Current errata must be evaluated for every affected implementation claim.
- The demo's canonical inventory contract and priority method are design choices, not NIST-prescribed schemas or formulas.
- A standardized algorithm does not prove a particular implementation, protocol exchange, browser session, server, module, product, or production deployment.
- CAVP and CMVP entries can change status or become historical/revoked. Certificate state and exact scope must be checked at the time of any claim.
- This implemented reference demo contains local source, package, browser, and
  synthetic evidence, but no supported-route deployment, real inventory,
  production observation, owner acceptance, third-party validation, or
  certificate evidence.

## Review rule

Before any public, procurement, compliance, or production-readiness statement, recheck every cited source in `source-status-registry.md`, resolve or disclose relevant residual gaps, and use only wording permitted by `claims-register.md`.
