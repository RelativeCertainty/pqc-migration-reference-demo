<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# PQC Assessment Map Room Build Plan v1

## Document status

- Status: proposed implementation plan
- Intended audience: product owner, assessment lead, application engineers,
  source-integration engineers, project-control operators, and reviewers
- Public boundary: employer-neutral; synthetic examples only
- Current evidence level: design informed by existing synthetic and
  contract-tested repository behavior
- Authority boundary: read-only assessment; no production remediation,
  approval, ticket mutation, certificate action, key action, configuration
  change, or deployment action
- Machine-readable task manifest:
  `planning/assessment-map-room-build-plan.v1.yaml`

## Outcome

Build a presentation-ready and operationally useful **PQC Assessment Map
Room** that explains and tracks three separate questions:

1. Is the assessment program moving?
2. How much of the authorized cryptographic estate can be supported by
   evidence?
3. Which report conclusions are ready for review, and which remain limited?

The Map Room is a read-only projection. Enterprise source systems remain
authoritative for source-native facts. The program-control authority owns
actions, dependencies, RFIs, decisions, and gates. Accepted reports remain
immutable snapshots. The application does not become a competing source of
truth.

## Baseline audit

The repository already provides substantial synthetic and contract-tested
building blocks, but it does not yet contain an integrated Map Room:

- The browser has twelve hash-routed sections and a ten-step Interview Mode;
  it has no separate Phase 1 Briefing Mode.
- The application displays six informal source categories and five
  illustrative migration patterns. These are not the complete ten-domain,
  22-pattern, and 27-source ontology.
- The current dashboard derives values from hard-coded synthetic systems. It
  does not consume `DashboardProjection.v1`.
- The validated two-region Phase 1 fixture is not rendered by the browser, so
  its actual source-to-observation-to-asset-to-dependency lineage is not yet
  visible.
- The read-only Program Operations runtime is not connected to the browser.
- Program progress, estate-mapping progress, and report readiness do not yet
  have one composed projection model.
- The detailed biweekly report and smaller runtime report snapshot do not yet
  have a canonical mapping.
- The standalone export currently omits `contract-packs/`, and the public
  privacy scan does not yet cover YAML files.

Release 0 must stabilize these boundaries before new presentation behavior is
called reproducible from a clean checkout.

## Product thesis

The application is the map room, not the territory:

```text
enterprise source
  -> source profile and approved access route
  -> evidence observation
  -> canonical asset
  -> dependency and business context
  -> finding or evidence limitation
  -> Phase 1 current-state report
  -> Phase 2 risk and business-impact analysis
```

The experience must let a non-technical stakeholder understand this sequence
without first learning the complete program vocabulary. Technical detail must
remain available through progressive disclosure.

## Non-negotiable distinctions

### Program progress

Program progress answers whether actions, access requests, RFIs, decisions,
Jira work, deliverables, and gates are moving. It never proves estate coverage.

### Estate-mapping progress

Estate-mapping progress answers which sources have been admitted, what they
observed, which assets and dependencies can be correlated, and what remains
unknown. It never proves project acceptance.

### Report readiness

Report readiness answers which required statements are supported by adequate
evidence and review. It never converts an unanswered question into a negative
finding or treats an unknown population as zero.

These three axes must be stored and rendered separately. A combined percentage
is prohibited.

## Audience-facing ontology

The interface introduces these concepts in order:

1. **Estate domain** — a major part of the enterprise in which cryptography may
   be used or governed.
2. **Migration pattern** — a repeatable way a cryptographic use may eventually
   be assessed, changed, and verified.
3. **Source system** — an enterprise platform, repository, service, or approved
   export that may provide authoritative facts.
4. **Source profile** — what the source covers, who operates it, how it may be
   accessed, and which limitations apply.
5. **Observation** — a dated, provenance-bearing fact from one source.
6. **Canonical asset** — a reviewable enterprise object assembled from one or
   more observations without discarding the source references.
7. **Dependency** — an evidence-backed relationship between two assets or
   between an asset and its enterprise context.
8. **Evidence limitation** — a known restriction on scope, access, freshness,
   correlation, authority, or interpretation.
9. **Finding** — a reviewable conclusion supported by observations and bounded
   by disclosed limitations.
10. **Report readiness** — whether the evidence required for a report section
    is available, reviewed, and adequate for its intended claim.

## Enterprise map

The public reference recognizes ten estate domains:

1. Enterprise context and ownership.
2. Certificates, trust, and public-key infrastructure.
3. TLS termination and application traffic.
4. Network, remote access, and machine access.
5. Software, repositories, and delivery pipelines.
6. Cloud, keys, secrets, identity, and workloads.
7. Data, storage, backup, and long-lived information.
8. DNS, email, documents, endpoints, and devices.
9. Specialized regulated cryptography.
10. Detection, governance, vendors, and assurance.

Named commercial products may be shown only as recognition prompts. A product
example never asserts enterprise use, approval, ownership, availability, or
selection.

## Map data model

### Nodes

The extensible asset model must support, at minimum:

- Application and business-service context.
- Certificate and trust metadata.
- TLS deployment or termination point.
- Source repository.
- Software component or cryptographic library.
- Key, HSM, or KMS reference without key material.
- Trust store or trust anchor.
- Signing and verification workflow.
- VPN, SSH, or other network cryptographic endpoint.
- Encrypted database, data store, archive, or backup set.
- Identity issuer or token-signing relationship.
- Device, firmware, secure-boot, or attestation object.
- Vendor-controlled product and installed-version context.

### Edges

The extensible dependency model must support relationships such as:

- Serves an application.
- Uses a certificate.
- Trusts or is trusted by.
- Implements or is implemented by.
- Contains or depends on a software component.
- Signs or verifies an artifact or message.
- Encrypts or protects a data set.
- Uses a key-management reference.
- Operates in an environment, site, or region.
- Supports a business service.
- Is operated or owned by a responsible function.
- Is supplied or controlled by a vendor.

Every node and edge must retain one or more evidence references, correlation
status, confidence basis, and review state.

## State model

### Source readiness

Use explicit states rather than vague completion language:

```text
not_profiled
candidate_source_identified
routed_to_responsible_function
owner_accepted
access_requested
access_ready
capability_probe_passed
collection_admitted
unavailable
deferred
```

### Map maturity

The public demonstration provides four reproducible synthetic states:

1. `outline_established`
   - Estate domains and intended scope are visible.
   - Source routes are unresolved.
   - Coverage is unavailable.
   - Report sections are structurally prepared but unsupported.

2. `sources_routed`
   - Candidate sources and responsible functions are represented.
   - Access actions and target dates exist.
   - No source facts are treated as collected evidence.

3. `evidence_arriving`
   - Admitted observations create candidate assets.
   - Correlation creates dependencies and review queues.
   - Conflicts, unmatched observations, and limitations remain visible.
   - Some report sections are partially supported.

4. `phase1_assessment_ready`
   - Required in-scope sources have explicit dispositions.
   - Applicable denominators and limitations are recorded.
   - Material conflicts have been resolved or disclosed.
   - The Phase 1 report is ready for accountable review.
   - Phase 2 may begin only after the baseline is accepted.

The scenario selector must say **Illustrative scenario** and display a
persistent synthetic-data banner. It must not resemble a live progress switch.

### Report-section readiness

Use these states:

```text
not_started
structure_ready
evidence_partial
review_ready
accepted
blocked
not_applicable
```

Each section records required evidence classes, available evidence references,
material limitations, accountable reviewer role, and status rationale.

## Measurement rules

- A percentage may be displayed only when its numerator, denominator, scope,
  as-of time, and denominator source are available.
- An unknown denominator produces `not_measurable`, never zero.
- Source readiness measures enablement, not estate coverage.
- Observation count measures collected facts, not distinct assets or risks.
- Correlation confidence describes the matching basis, not probability of
  truth.
- Missing evidence becomes a limitation, not a clean result.
- Report readiness is evaluated by required claim and evidence class, not by
  the raw number of answered questions.
- Scenario metrics and actual program metrics cannot appear in the same visual
  without separate labels and sources.

## Experience architecture

### Briefing mode

Add a six-step, presentation-safe route that preserves the meeting frame:

1. Mission — why the map is being built.
2. Estate — the ten-domain landscape.
3. Method — sources become observations, assets, dependencies, and reports.
4. Position — program, evidence, and report state shown separately.
5. Demonstration — selected synthetic map state with drill-down.
6. Action — decisions, routes, owners, dates, and consequences.

Briefing mode uses large text, one main message per view, keyboard navigation,
stable deep links, and no controls that resemble production execution.

### Operator mode

Operator mode adds detail without changing authority:

- Source-readiness register.
- RFI and dependency drill-down.
- Capability-probe results.
- Evidence and provenance browser.
- Asset and dependency explorer.
- Conflict and unmatched-observation queues.
- Evidence-limitations register.
- Report-section readiness.
- Gate and decision position.

### Executive mode

Executive mode displays only:

- Scope and as-of date.
- Current phase and next gate.
- Program blockers requiring action.
- Source-readiness position.
- Measurable coverage with denominator disclosure.
- Material limitations.
- Report readiness.
- Decisions and accountable dates.

It excludes raw evidence, private notes, credentials, unrestricted source
payloads, and unapproved findings.

## Contract plan

Preserve existing version-one contracts unchanged. Add new versions or new
contracts where semantics expand.

### Reuse

- `ProviderIntegrationProfile.v1`
- `CapabilityProbe.v1`
- `CollectionRun.v1`
- `EvidenceObservation.v1`
- `CanonicalCryptoRecord.v1`
- `CryptoDependency.v1`
- `Phase1SyntheticFlow.v1`
- `DashboardProjection.v1`
- Program Operations action, dependency, RFI, decision, gate, and report
  contracts

### Add

- `PQCEstateOntology.v1` — the authoritative public taxonomy of ten estate
  domains, 22 migration patterns, 27 source-system types, recognition hints,
  and their many-to-many relationships.
- `AssessmentMapProjection.v1` — nodes, edges, evidence references, conflicts,
  limitations, and bounded measurements.
- `BriefingScenario.v1` — synthetic state, narrative sequence, and allowed
  projection references.
- `ReportReadinessProjection.v1` — report sections, evidence requirements,
  limitations, review state, and acceptance state.
- `ProgramPositionProjection.v1` — read-only action, dependency, decision, and
  gate summary for audience-filtered display.

The contracts remain language-neutral JSON Schema. OpenAPI describes external
HTTP projection access. Generated Protobuf/gRPC contracts may be used for
internal component seams when the selected runtime supports them. Transport
formats do not replace the canonical evidence schemas.

## Implementation releases

### Release 0 — presentation-safe walking skeleton

Purpose: support an immediate stakeholder briefing without claiming new
enterprise capability.

Work:

- Preserve the current dirty working baseline and make the required existing
  contracts, fixtures, and validators durable before the UI depends on them.
- Include `contract-packs/` in the standalone export and extend public privacy
  validation to YAML.
- Define the six-step briefing narrative as checked-in data.
- Reuse the existing Overview, Architecture, Inventory, Dashboard, Posture,
  and Questions surfaces through a curated route.
- Preserve the current Interview Mode and add a distinct Phase 1 Briefing Mode.
- Add an unmistakable synthetic-reference boundary at the start and during
  every scenario view.
- Use the existing two-region Phase 1 fixture as the only evidence-bearing
  demonstration.
- Add a final action view containing role, action, required date, consequence,
  and status fields.
- Prepare a static screenshot or PDF fallback for every demonstrated view.

Exit criteria:

- The six-step sequence completes in six minutes or less.
- No view claims live enterprise connectivity or enterprise-wide coverage.
- Every displayed number identifies its synthetic scope and denominator.
- The route works from a clean checkout.
- The standalone export contains the five public source contract packs.
- Public privacy validation covers the authored YAML sources.
- Keyboard navigation and 200-percent browser zoom remain usable.
- Existing repository validation remains green.

### Release 1 — contract-backed scenario playback

Purpose: demonstrate how the map changes as evidence matures.

Work:

- Add the four `BriefingScenario.v1` fixtures.
- Add the canonical ten-domain, 22-pattern, and 27-source ontology and validate
  every cross-reference.
- Generate every scenario from shared source profiles, observations, assets,
  dependencies, limitations, and report-section rules.
- Add a scenario selector with descriptive state names, not percentages.
- Show why each metric is available or unavailable.
- Add regression tests proving that an unavailable denominator cannot produce
  a coverage percentage.
- Add tests proving that scenario data cannot be labeled actual.

Exit criteria:

- All four scenarios validate against the same contracts.
- State transitions add evidence without silently deleting limitations.
- A later state cannot claim acceptance without the required review record.
- Scenario playback is deterministic.

### Release 2 — program-control projection

Purpose: let the application frame the live project conversation.

Work:

- Bind a read-only adapter to the Program Operations API or approved exported
  snapshot.
- Display current cycle, next gate, due actions, blocking dependencies, open
  RFIs, decisions required, and report snapshot status.
- Apply audience filtering before data reaches the browser.
- Keep actual program position visually separate from synthetic estate data.
- Add as-of time, source version, and digest to every program projection.
- Keep the public hosted reference fixture-backed. Authenticated live Program
  Operations access belongs only in a separately approved enterprise
  deployment profile.

Exit criteria:

- The browser cannot mutate program records.
- Private notes, time records, personal calendar details, and restricted
  evidence are absent.
- Every action includes its name, responsible role, required date,
  consequence, and source reference.
- Stale or unavailable program data is visibly identified.

### Release 3 — source-readiness and evidence map

Purpose: replace illustrative source progress with admitted read-only evidence.

Work:

- Implement source adapters one at a time behind the existing narrow ports.
- Require a source profile, access authority, classification, capability probe,
  and collection policy before admission.
- Normalize provider records into evidence observations.
- Correlate observations into canonical assets without losing provenance.
- Show conflicts and unmatched observations as review work.
- Add estate-domain and migration-pattern filters.
- Extend asset and dependency types only through versioned contracts and
  conformance fixtures.

Exit criteria:

- Each adapter passes pagination, retry, duplication, authorization failure,
  malformed-record, schema-drift, and cursor-recovery tests.
- A source outage cannot corrupt prior accepted evidence.
- Provider-native objects do not enter the domain model.
- No credential, secret, key material, unrestricted payload, or raw source code
  enters the dashboard or telemetry.

### Release 4 — report-readiness projection

Purpose: show exactly how evidence supports Phase 1 and enables Phase 2.

Work:

- Define evidence requirements for each Phase 1 report section.
- Define the mapping between the full biweekly report contract and the smaller
  runtime report snapshot.
- Bind assets, dependencies, findings, and limitations to report sections.
- Show unsupported, partially supported, review-ready, accepted, and blocked
  sections.
- Generate report preview content from the same authoritative references.
- Require an accepted Phase 1 baseline before enabling Phase 2 risk claims.
- Preserve corrections through superseding snapshots.

Exit criteria:

- Every report statement is traceable to evidence or explicitly labeled
  interpretation.
- Every limitation appears in the report preview and readiness explanation.
- Accepted snapshots cannot be overwritten.
- Phase 2 readiness fails closed when required Phase 1 evidence is missing.

### Release 5 — enterprise deployment profile

Purpose: bind the product-neutral core to an approved enterprise environment.

Work:

- Generate runtime, relational-store, identity, secret-service, telemetry,
  ingress, object-storage, analytics, and source-adapter bindings from an
  approved technology-selection profile.
- Keep deployment-specific code in adapters and configuration.
- Add backup, restore, failover, rollback, accessibility, load, security, and
  operator-runbook evidence.
- Retain a clean local synthetic path for deterministic development and
  demonstration.

Exit criteria:

- Selected bindings have internal evidence and authorized decision references.
- The deployment passes the same domain and adapter conformance suites as the
  reference implementation.
- Production-readiness and live-readback claims are made only after their own
  evidence gates pass.

## Component sequence

Build and prove the Map Room through declared edges:

```text
contract
  -> deterministic fixture
  -> domain projection
  -> component test
  -> adjacent-component seam
  -> presentation-safe slice
  -> read-only enterprise adapter
```

Recommended order:

1. Contracts and validation.
2. Scenario fixtures.
3. Pure projection functions.
4. Briefing navigation and views.
5. Program-position adapter.
6. Source-readiness adapter.
7. Evidence-map explorer.
8. Report-readiness generator.
9. Enterprise deployment adapters.

Do not begin with the complete deployment stack. Each phase must emit a
source-bound proof that states exactly what was demonstrated and what was not.

## Repository change map

Planned additions:

```text
contracts/pqc-estate-ontology.v1.schema.json
contracts/assessment-map-projection.v1.schema.json
contracts/briefing-scenario.v1.schema.json
contracts/report-readiness-projection.v1.schema.json
contracts/program-position-projection.v1.schema.json

fixtures/assessment-map/outline-established.v1.json
fixtures/assessment-map/sources-routed.v1.json
fixtures/assessment-map/evidence-arriving.v1.json
fixtures/assessment-map/phase1-assessment-ready.v1.json

src/domain/assessmentMap.ts
src/domain/reportReadiness.ts
src/domain/briefing.ts
src/components/BriefingMode.tsx
src/components/EstateMap.tsx
src/components/ProgramPosition.tsx
src/components/ReportReadiness.tsx

scripts/validate-assessment-map.py
docs/assessment-map-room.md
docs/assessment-map-room-presenter-guide.md
```

Existing files should be changed only after focused tests establish the
intended compatibility behavior. Generated build-info files are not authored
sources.

## Test plan

### Contract and domain tests

- Unique and resolvable domain, source, asset, dependency, evidence,
  limitation, report-section, action, decision, and gate identifiers.
- Every identifier appears with a plain-language name in human views.
- No dependency references a missing asset.
- Every asset and dependency retains evidence references.
- Duplicate observations do not create duplicate admitted effects.
- Conflicting sources remain visible and do not silently choose a winner.
- Unknown denominators suppress coverage percentages.
- Evidence limitations cannot be converted into success metrics.
- Report readiness cannot advance without required evidence and review.

### Presentation tests

- Every briefing step has one primary message.
- All audience-facing terms are introduced before specialist use.
- The complete briefing fits the intended duration.
- All text remains readable at presentation distance and 200-percent zoom.
- No clipping, collisions, unintended wrapping, or obscured connectors.
- Keyboard-only operation follows the intended sequence.
- The synthetic boundary remains visible in screenshots and full-screen mode.

### Security and authority tests

- Browser identities have no write-capable endpoint.
- Scenario fixtures contain no enterprise identifiers or customer data.
- Program projections exclude private notes and time details.
- Raw evidence, source code, payloads, credentials, secrets, private keys, and
  unrestricted error text cannot enter the view or telemetry.
- Future remediation controls remain absent or deny-by-default.

### Portability tests

- A clean checkout can validate contracts and run the synthetic briefing.
- Generated clients agree with canonical schemas.
- Internal transport substitution does not change domain values.
- Enterprise adapters pass the same conformance tests as reference adapters.
- Presentation and report projections rebuild deterministically from source
  records.

## Friday-safe operating protocol

Until Release 0 is complete, use the existing application manually in this
order:

```text
Overview
  -> Architecture
  -> Inventory
  -> Dashboard
  -> Questions
```

Before presenting:

- Run the repository checks.
- Rehearse the exact click path.
- Open the application locally as the primary path.
- Retain screenshots or a PDF as the offline fallback.
- Disable notifications and close unrelated applications and tabs.
- Confirm every visible state is labeled synthetic.
- Do not demonstrate future write, ticket, or remediation views as current
  assessment capability.

During the meeting:

- Begin with the map-making purpose.
- Explain the ontology before opening detailed records.
- State that the workbook defines what must be learned and the app shows what
  admitted answers become.
- Return from the demonstration to actions, owners, dates, and consequences.
- Capture decisions in the authoritative program-control process, not in the
  presentation application.

## Definition of done

The Map Room v1 is done only when:

- A non-technical stakeholder can explain the map, its inputs, and its outputs
  after the six-step briefing.
- Actual program state, synthetic scenario state, estate evidence state, and
  report readiness cannot be confused.
- Every metric carries its scope, denominator, as-of time, and qualification.
- Every displayed asset and dependency is traceable to retained evidence.
- Unknowns and limitations remain visible.
- The same source records generate the dashboard and report-readiness views.
- The reference path runs from a clean checkout.
- The enterprise path can be completed by implementing documented adapters
  rather than rewriting the domain core.
- No unauthorized external action or production mutation is possible.

## Immediate implementation queue

1. Approve the Map Room name, three-axis model, and four scenario names.
2. Add and validate the five new contracts.
3. Build the four deterministic scenario fixtures from the current synthetic
   Phase 1 flow.
4. Implement pure projection functions and negative tests.
5. Add the six-step Briefing Mode and presentation-safe navigation.
6. Rehearse and visually validate Release 0.
7. Bind the read-only Program Operations projection.
8. Add source-readiness and report-readiness views.
9. Admit enterprise source adapters one at a time after authorization.
