# PQC Assessment Map Room Presenter and Operator Guide

## Document status

- Status: Release 0 presentation protocol
- Intended audience: presenter, backup presenter, and meeting facilitator
- Public boundary: employer-neutral; synthetic examples only
- Route: `#briefing`
- Intended duration: six minutes
- Authority boundary: read-only explanation and projection; no external system
  action
- Demonstration source:
  `fixtures/synthetic-phase1/two-region/phase1-flow.v1.json`

## Purpose

Use the Map Room to keep a stakeholder conversation centered on six questions:

1. Mission — why an evidence-backed map is needed.
2. Estate — what kinds of enterprise territory must be represented.
3. Method — how source facts become assets, relationships, and report content.
4. Position — how program movement, estate evidence, and report readiness differ.
5. Demonstration — what the current synthetic evidence flow actually proves.
6. Action — which role must take which action by what date, and why it matters.

The application is the map room, not the territory. Enterprise source systems
remain authoritative for source-native facts. The application presents a
bounded view of evidence, resulting assets and dependencies, limitations, and
readiness.

## Presenter promise

Keep these statements true throughout the briefing:

- Every displayed record is synthetic.
- The demonstration uses only the checked-in two-region Phase 1 fixture.
- A source count is not an asset count.
- An observation count is not a risk count.
- Source readiness is not estate coverage.
- Report readiness is not report acceptance.
- An unknown denominator is reported as not measurable, never as zero.
- The demonstration does not claim a live connection, organization-wide
  completeness, product selection, deployed control, or accepted result.
- Decisions and commitments are captured in the authorized project-control
  process, not in the presentation application.

## Exact opening

Say this before advancing from Mission:

> The simplest way to understand this project is as enterprise map making. We
> know the kinds of territory that must be represented, but the map is only
> trustworthy when authoritative systems provide the measurements. Today I
> will show what we are mapping, how source information becomes an
> evidence-backed asset and dependency model, what the current demonstration
> proves, and which actions will move the assessment forward.

## Six-minute sequence

### 1. Mission — 0:00 to 0:45

Primary message:

> Phase 1 builds the evidence-backed current-state map. Phase 2 uses an
> accepted Phase 1 baseline to evaluate exposure, business impact, migration
> constraints, and priorities.

Operator action:

- Open `#briefing` before screen sharing.
- Select step 1, **Mission**, or press `Home`.
- Deliver the exact opening.
- Point to the two outputs: current-state assessment and risk priorities.

This screen should prove:

- The audience can state why the map is being built.
- The two assessment phases have distinct purposes.
- Later analysis depends on an evidence-backed current-state baseline.

This screen does not prove:

- That an enterprise inventory has been collected.
- That Phase 1 is complete or accepted.
- That any particular technology or delivery platform has been selected.

### 2. Estate — 0:45 to 1:35

Primary message:

> The enterprise cryptographic estate is broader than certificates or one
> application stack. The reference map recognizes ten domains so that material
> areas are not silently omitted.

Operator action:

- Advance to **Estate**.
- Describe the ten domains as map layers; do not read every example.
- Explain that the current fixture samples five source types and is not the
  complete estate model.

The ten map layers are:

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

This screen should prove:

- The assessment has a coherent enterprise scope model.
- A domain is an area to investigate, not a claim that evidence is available.
- Initial source work is a deliberate starting slice rather than the complete
  source landscape.

This screen does not prove:

- That all ten domains are in an authorized scope.
- That a source exists or is accessible for every domain.
- That the displayed domain structure measures enterprise coverage.

### 3. Method — 1:35 to 2:25

Primary message:

```text
source profile and authorized access
  -> dated evidence observation
  -> canonical asset
  -> evidence-backed dependency and context
  -> finding or disclosed limitation
  -> Phase 1 report
  -> Phase 2 analysis after baseline acceptance
```

Operator action:

- Advance to **Method**.
- Trace the flow from left to right once.
- Define an observation as a dated fact that retains its source reference.
- Define a canonical asset as a reviewable object assembled without discarding
  the observations that support it.
- State the exact transition:

> The workbook defines what must be learned. The application demonstrates what
> admitted answers become.

This screen should prove:

- The method preserves traceability from source to report.
- Several observations may contribute to one asset or dependency.
- Missing, conflicting, or uncorrelated evidence remains visible as a
  limitation or review item.

This screen does not prove:

- That every question requires a person-to-person survey.
- That one source is automatically authoritative for every fact.
- That correlation confidence is a probability of truth.

### 4. Position — 2:25 to 3:10

Primary message:

> Program progress, estate-mapping progress, and report readiness answer three
> different questions. They must never be collapsed into one completion
> percentage.

Operator action:

- Advance to **Position**.
- Name the three axes and the question each answers.
- Point to the scope, denominator, as-of time, and qualification attached to
  any displayed measure.
- If the screen says **not measurable**, leave it that way; do not estimate.

The three axes are:

- Program progress: are actions, dependencies, questions, decisions, and gates
  moving?
- Estate-mapping progress: which admitted sources produced observations, and
  which assets and dependencies can be supported?
- Report readiness: which required report statements have adequate evidence
  and review?

This screen should prove:

- The model can represent the three states independently.
- Measurements are bounded by a disclosed numerator, denominator, scope, and
  as-of time.
- An evidence limitation can block a report claim without erasing work already
  completed.

This screen does not prove:

- The current state of any organization or live program.
- Organization-wide estate coverage.
- Acceptance of a report or gate.

### 5. Demonstration — 3:10 to 5:00

Before interacting with the fixture, say the exact demonstration boundary:

> What you are about to see is a synthetic example, not enterprise inventory.
> Its purpose is to demonstrate how records from several enterprise sources
> become reviewable assets, dependencies, evidence limitations, dashboards,
> and ultimately report content.

Operator action:

- Advance to **Demonstration**.
- Confirm the persistent **Synthetic reference** label is visible.
- Show only the checked-in two-region fixture.
- Trace one relationship from a source observation to an asset, then from that
  asset to one dependency.
- Show the informational limitation before leaving the screen.
- Do not open source code, a terminal, raw logs, unrelated fixtures, or
  future-state views while sharing the screen.

The fixture contains:

- Scope: two fictional regions and the authorized synthetic asset type
  **TLS deployment**.
- Source contract packs: five.
- Source pages: ten.
- Normalized observations: ten.
- Canonical assets: eight.
- Evidence-backed dependencies: eight.
- Disclosed evidence limitations: one informational limitation concerning
  unvalidated ownership.
- Coverage denominator: a fixture-defined population of authorized synthetic
  TLS deployments; it is not an enterprise denominator.

The five source types are:

- Application and service context.
- Certificate lifecycle.
- TLS traffic management.
- Source repositories.
- Software analysis.

This screen should prove:

- Contract-shaped source pages can become provenance-bearing observations.
- Observations can be correlated into assets without losing their references.
- Evidence-backed relationships can connect TLS deployments, an application,
  certificate metadata, repositories, and software components.
- A dashboard or report view can be rebuilt from the same retained fixture.
- Limitations can remain visible beside otherwise successful processing.

This screen does not prove:

- A live API, repository, or enterprise-system connection.
- The existence, configuration, ownership, or posture of any real asset.
- Comprehensive discovery, organization-wide coverage, or production scale.
- A vulnerability, risk rating, migration recommendation, or accepted report.
- That the five demonstrated source types are the entire source landscape.

### 6. Action — 5:00 to 6:00

Primary message:

> The meeting succeeds when each blocking dependency has a responsible role,
> a concrete next action, a required date, and a stated consequence.

Operator action:

- Advance to **Action** or press `End`.
- Read back only the highest-priority open actions.
- For every action, confirm all five displayed fields: responsible role,
  action, required date, consequence, and status.
- Correct ambiguity aloud before leaving the item.
- Record confirmed commitments after the demonstration in the authorized
  project-control process.

This screen should prove:

- The conversation can end in explicit, reviewable next actions.
- An unanswered information need can be connected to a delivery consequence.
- The projection carries enough context to route an action without requiring
  the recipient to decode an identifier elsewhere.

This screen does not prove:

- That the application assigned work or recorded acceptance.
- That a displayed candidate role has accepted ownership.
- That a proposed date is an approved commitment until it is confirmed and
  recorded by the authorized process.

## Exact close

Say this while the Action screen remains visible:

> We do not need this group to answer hundreds of technical questions today.
> We need the group to help identify the smallest responsible functions,
> access routes, and next actions that will allow the evidence to be collected
> systematically. If every blocking dependency leaves this meeting with an
> owner, action, and date, the project moves from map planning into actual
> surveying.

Before leaving the screen, perform one final readback:

```text
Action:
Owner or responsible role:
Required date:
Delivery consequence if unresolved:
Status:
```

Do not end on the demonstration. End on the action, owner, date, and
consequence.

## Keyboard and visible controls

The `#briefing` route supports:

- `ArrowRight`, `ArrowDown`, or `PageDown`: next step.
- `ArrowLeft`, `ArrowUp`, or `PageUp`: previous step.
- `Home`: Mission, the first step.
- `End`: Action, the final step.
- `Escape`: exit Briefing Mode and return to Overview.
- `Tab` and `Shift+Tab`: move between visible interactive controls.
- `Enter` or `Space`: activate the focused control.

Visible controls provide the same route through **Previous**, **Next**, six
numbered step buttons, and **Exit briefing**.

Operator cautions:

- Do not use the browser Back button to advance the sequence.
- If the browser is full-screen, the first `Escape` may exit full-screen before
  the application receives it. Use **Exit briefing** when the result is
  uncertain.
- Keep the pointer still unless a detail must be identified. Keyboard movement
  is less visually distracting.

## Preflight

### Before the meeting

- Validate the repository from a clean, reviewable state with `npm run check`.
- Confirm the synthetic proof separately with `npm run synthetic:test`.
- Start the local application with `npm run dev` and use the loopback address
  reported by the development server.
- Open the application directly at `#briefing`.
- Complete the full six-step path twice using only the keyboard.
- Complete the path once using only the visible controls.
- Set browser zoom to 200 percent and confirm that every primary message,
  synthetic label, metric qualification, and action field remains usable.
- Return to the preferred presentation zoom after the 200-percent check.
- Confirm the source digest and validation status shown for the fixture are
  current.
- Open the offline fallback in a separate local window and navigate it to
  Mission.
- Disconnect external networking briefly and confirm that the local briefing
  and fallback remain available.
- Close unrelated tabs and applications.
- Disable operating-system, browser, mail, chat, and calendar notifications.
- Share the application window, not the entire desktop.
- Confirm that no private notes, customer material, credentials, terminals, or
  notification previews can enter the shared view.
- Assign a facilitator to capture actions, owners, dates, and consequences
  outside the presentation application.

### Immediately before presenting

- Return to Mission with `Home`.
- Confirm the route says `#briefing`.
- Confirm the **Synthetic reference** boundary is visible.
- Confirm browser zoom and window size.
- Confirm the local application and fallback are both open.
- Start a six-minute timer that is not visible in the shared window.
- Deliver the exact opening before interacting with the screen.

## Two-hundred-percent zoom check

The 200-percent check is an acceptance test, not the required speaking zoom.
At 200 percent, verify:

- No text, badge, card, connector, control, or focus outline collides with
  another object.
- No primary message or qualification is truncated.
- The current step, step count, and synthetic boundary remain visible.
- The Previous, Next, numbered-step, and Exit controls remain reachable by
  keyboard.
- Focus order follows Mission through Action.
- Each action retains its role, action, date, consequence, and status.

If any of these fail, use the offline fallback and record the defect. Do not
hide a qualification or synthetic label to make the view fit.

## Offline fallback

Keep a local PDF or screenshot sequence with one captured view for each of the
six steps. Each capture must retain:

- Step name and primary message.
- Synthetic-reference boundary.
- Metric scope and denominator qualification where a number appears.
- Source-fixture identity or digest on the Demonstration view.
- Role, action, required date, consequence, and status on the Action view.

The fallback is a presentation copy, not new evidence. It must be regenerated
when the briefing fixture or rendered view changes.

## Thirty-second failure pivot

If the interactive route stalls, renders incorrectly, or becomes unavailable:

1. First 10 seconds: press no more than one safe navigation key or reload the
   local route once. Do not open developer tools.
2. By 20 seconds: switch to the already-open local fallback at the same step.
3. By 30 seconds: say, “The interactive view is unavailable, so I will continue
   with the captured synthetic walkthrough.” Resume the script immediately.

Do not troubleshoot code, networking, credentials, or presentation equipment
while the audience waits. If the fallback also fails, return to the static map
flow, state the demonstration boundary verbally, and proceed directly to
Action. Preserve the action-owner-date close even when the demonstration is
omitted.

## Rehearsal acceptance

The briefing is ready only when:

- Mission through Action completes in six minutes or less.
- The exact opening, transition, demonstration boundary, and close can be
  delivered without searching notes.
- A reviewer can explain the map, its inputs, and its report outputs afterward.
- The reviewer does not confuse program progress, estate-mapping progress, and
  report readiness.
- All displayed counts match the checked-in two-region fixture.
- Every displayed number carries its synthetic scope and denominator.
- Keyboard-only navigation works at normal zoom and 200-percent zoom.
- Every captured fallback view is current and locally available.
- No screen claims a live connection, enterprise completeness, technology
  selection, deployed control, or accepted result.
- The final screen preserves a specific action, responsible role, required
  date, consequence, and status.

## Evidence and non-claim record

After rehearsal, record:

```text
Source revision:
Fixture path:
Fixture digest:
Validation command and result:
Briefing duration:
Keyboard result:
200-percent zoom result:
Offline fallback result:
Reviewer:
Observed issues:
```

A successful rehearsal proves only that this public, synthetic walkthrough is
presentation-safe and reproducible for the recorded source revision. It does
not prove an enterprise deployment, live source access, comprehensive estate
coverage, report acceptance, or operational readiness.
