<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Evidence-Gated Vertical Slice Method

## Purpose

The method turns a broad PQC migration into small, teachable slices that cross
discovery, domain decisions, authorized change, verification, and measurement.
It combines rolling-wave planning with stable program gates.

## Invariant flow

1. **Discover:** gather authorized observations without assuming completeness.
2. **Normalize:** map source-native records into versioned evidence contracts.
3. **Contextualize:** connect candidate cryptographic use to ownership, service, data lifetime, exposure, criticality, and dependencies.
4. **Decide:** apply transparent policy and prioritization specifications; retain the decision and approver.
5. **Change:** create a bounded, reversible, explicitly authorized change.
6. **Verify:** independently read back negotiated or deployed behavior.
7. **Measure:** compare outcomes, performance, failures, rollback, and residual risk.

A slice stops at the strongest evidence actually produced. Missing authority or
readback keeps the slice partial rather than converting an assumption into a
completion claim.

## Stage gates

- **G0 Boundary:** scope, authority, classification, retention, and exclusions are explicit.
- **G1 Contract:** inputs, canonical records, decisions, and outputs are versioned.
- **G2 Baseline:** coverage, conflicts, staleness, unknown ownership, and limitations are measured.
- **G3 Decision:** accountable owners approve priority and treatment.
- **G4 Change:** an authorized reversible change executes with traceable evidence.
- **G5 Readback:** an independent path verifies target behavior.
- **G6 Outcome:** benchmarks, rollback, residual risk, and next action are accepted.

## Rolling-wave rule

Epics and features remain stable. Stories are made implementation-ready two
weeks ahead. New evidence may reshape stories and sequencing, but it does not
silently rewrite accepted gates, historical observations, or decision records.
