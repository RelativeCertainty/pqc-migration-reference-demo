<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Teachable design patterns

## Domain-Driven Design

Use bounded contexts for inventory, policy, migration, evidence, and program
governance. Domain language names business decisions and evidence states,
rather than vendor payload fields.

## Onion architecture

Keep policy and evidence semantics at the center. Application use cases
orchestrate domain behavior. Ports express required capabilities. Adapters
contain filesystem, vendor, protocol, reporting, and UI details.

## Ports and Adapters

A port is an owned contract, not a vendor-shaped interface. Replaceable
adapters permit a repository scanner, PKI source, TLS observer, SSH collector,
or project-system projection without changing the domain.

## Anti-Corruption Layer

Translate source-native records into canonical observations while preserving
source reference, collection time, confidence, classification, and conflict.
Do not let vendor terminology become the enterprise domain model.

## Specification

Represent indicator rules, policy eligibility, risk factors, gate criteria,
and exceptions as versioned, explainable specifications. A matched scanner
specification creates candidate evidence, not a vulnerability judgment.

## Strategy

Select prioritization, rollout, compatibility, hybrid-operation, and rollback
strategies through explicit policy profiles. Record which strategy and version
produced a decision.

## Evidence envelope

A consequential slice carries request, authority, decision, execution,
result, independent readback, timestamp, and accountable owner. Each field has
its own provenance; a later stage cannot manufacture an earlier one.

## Independent readback

Verification uses a path independent of the change command whenever practical:
negotiated TLS inspection after configuration, SSH handshake observation after
policy update, or deployed dependency resolution after an approved merge.

## Projection

YAML is the project backlog source of truth. Issues, boards, dashboards, and
the static demo are replaceable projections and must not become competing
execution authorities.
