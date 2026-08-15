# Evidence-Fusion Ports and Adapters

Status: implemented reference slice with deterministic synthetic adapters; no
client feed is connected

Evidence classification: development evidence; no customer records, source
payloads, credentials, keys, certificate bodies, or production observations

## Decision

Use ports and adapters so the canonical cryptographic inventory never depends
on ExtraHop, vulnerability-manager, PKI, SAST, CMDB, or initial-inventory field
names.

```text
initial inventory ───────────┐
ExtraHop Internet TLS ───────┤
vulnerability management ────┤  inbound adapters
PKI certificate inventory ───┼──────────────────────┐
SAST ────────────────────────┤                      │
CMDB ────────────────────────┘                      v
                                      EvidenceObservation.v1
                                                 │
                            normalize -> deduplicate -> correlate
                                                 │
                              preserve disagreement and provenance
                                                 │
                                                 v
                                      CanonicalCryptoRecord.v1
                                                 │
                        ┌────────────────────────┼─────────────────────┐
                        v                        v                     v
                 inventory view           review queue       workflow/metrics
                    adapter                  port                 ports
```

The reported initial inventory is modeled as a first-class inbound source. The
demo does not possess that inventory; deterministic synthetic records exercise
the same port without representing client data.

## Inbound port

[`evidence-observation.v1.schema.json`](../contracts/evidence-observation.v1.schema.json)
is the closed Draft 2020-12 contract emitted by every adapter. It separates:

- `feedId`: where the evidence came from;
- `issueType`: what cryptographic issue the observation represents; and
- `estateClass`: who controls the relevant change.

Supported feed identities are:

- the bounded initial-inventory seed;
- ExtraHop Internet TLS/certificate observations;
- vulnerability-management SSL-plugin and cryptographic findings;
- PKI certificate inventory;
- SAST cryptographic-use findings; and
- a bounded CMDB-derived identity/correlation hint.

The v1 observation port is intentionally finding-shaped: one issue type plus a
bounded fact and correlation hints. It can demonstrate a CMDB-derived identity
hint, but it does **not** yet normalize typed owner, service, lifecycle, or
relationship fields. A production successor should introduce a versioned
`observationKind` and closed conditional payloads for findings, asset/ownership
context, certificate or connection observations, and code-use observations,
with explicit classification and retention. The demo must not describe v1 as a
complete CMDB business-context model.

Supported issue types distinguish TLS/protocol, algorithm or key strength,
certificate/trust, implementation/configuration, source-code cryptographic use,
cryptographic dependency, and vendor-control gaps.

Supported change-control contexts distinguish first-party source code,
OTS/COTS software, and third-party/SaaS dependencies. These are deliberately
orthogonal axes: a vulnerability-manager feed can describe a source-code,
OTS/COTS, or third-party/SaaS issue, and one OTS/COTS product can have several
issue types.

## Inbound adapters

An adapter has one responsibility: validate a bounded feed-specific input and
emit `pqc.evidence-observation.v1`. It may not decide migration priority, merge
canonical records, or silently upgrade evidence quality.

Every emitted observation retains:

- adapter name and semantic version;
- native record reference without a raw payload;
- collection time, or explicit absence for synthetic fixtures;
- candidate correlation key and optional asset hint;
- feed, issue, and estate classifications;
- a bounded fact;
- assessment, confidence, and source locator; and
- safety assertions that secrets and raw payloads were not retained.

Production adapters would require their own authentication, authorization,
classification, retention, rate/cost, pagination, cursor, replay, and
observability reviews. No production credential or connector is part of this
reference slice.

A production ingestion adapter would need an independently reviewed runtime
contract for identity, authorization, retries, idempotency, scheduling,
observability, retention, and accountable approval. This reference UI and its
TypeScript fixtures are not an execution authority, scheduler, connector
runtime, or production catalog.

## Domain core

The evidence-fusion core is deterministic and feed-neutral.

Normalization:

- canonicalizes bounded candidate identifiers;
- maps feed-specific enumerations before the observation enters the core;
- never treats missing evidence as a negative finding; and
- never changes the observation's provenance assessment.

Deduplication:

- groups replays only by the same `feedId` plus native `source.recordRef`, then
  counts a duplicate only when the complete closed observation is identical;
- does not collapse cross-feed corroboration into a duplicate; and
- reports duplicate counts rather than silently discarding their existence;
- rejects an observation ID reused for different canonical content; and
- when one feed/native identity has divergent content, excludes every variant
  from canonical evidence and places every bounded observation reference in a
  separate result-level source-reconciliation queue. The queue carries an
  opaque source-identity reference, ordinal, exact-duplicate submission count,
  changed fields, and an explicit `trustedCanonicalContribution=false`; raw
  native locators and disputed candidate keys are not projected.

Correlation:

- groups observations by governed candidate keys;
- retains every trusted contributing observation reference while keeping every
  disputed source identity outside canonical records;
- distinguishes `correlated`, `conflict`, and `unmatched` outcomes;
- lets the governed seed supply display and estate values while still exposing
  disagreements; without a seed, disputed display or estate fields remain
  `null` rather than taking the first feed's value;
- is invariant to input ordering and never applies last-write-wins; and
- sends conflicts, unmatched observations, unknown freshness, and low-confidence
  results to review.

The reference algorithm demonstrates mechanics, not production entity
resolution. Real correlation keys, thresholds, override authority, and
false-match controls require the client's data and accountable review.

## Outbound port

[`canonical-crypto-record.v1.schema.json`](../contracts/canonical-crypto-record.v1.schema.json)
is the nested trusted-record boundary inside the versioned parent result. It
carries:

- a stable record and canonical-asset key;
- display name and estate class, or explicit `null` when unseeded contributors
  disagree;
- one or more issue types;
- structured contributing observation references;
- correlation status, exact-duplicate count, and conflict fields;
- observed or explicitly unknown freshness; and
- a required-review decision with reasons; and
- an evidence-composition state (`synthetic_only`, `mixed`, or
  `non_synthetic`) so one real observation cannot hide fixture contribution.

`Canonical` means one governed normalized contract. It does not mean a record
is complete, correct, authoritative, or ready for automatic remediation.

[`evidence-fusion-result.v1.schema.json`](../contracts/evidence-fusion-result.v1.schema.json)
is the stable, closed parent output port for views, review queues, workflow,
and metrics. It carries canonical records plus the separate
`sourceReconciliationQueue`. That queue is not a canonical record
and cannot contribute an issue, estate, display name, freshness value,
assessment, or evidence reference until accountable reconciliation produces a
new, unambiguous source observation. The runtime validator additionally
enforces parent-child identity equivalence, contiguous ordinals, unique
result-local queue identities, and disjoint canonical and disputed evidence.

## Outbound adapters

The domain output can be projected without changing the core:

- inventory/search read model;
- reconciliation and conflict-review queue;
- ITSM or workflow request candidate;
- coverage, match, conflict, freshness, ownership, and closure metrics; and
- evidence export for an accountable review packet.

No outbound adapter may authorize a production change or mark a migration
complete. Closure still requires installed validation or rediscovery evidence
and the accountable owner's decision.

## Contract evolution

- Schema names include a major version.
- The recursively closed v1 shapes freeze when this release publishes them.
  Any emitted field, enum, validation, meaning, privacy, or authority change
  requires a new contract version and an explicit adapter migration; adding an
  optional producer field is not backward compatible with an older closed v1
  consumer.
- Unknown properties fail validation.
- Unknown feed, issue, or estate classes fail validation rather than falling
  into an unreviewed “other” bucket.
- Synthetic observations cannot claim runtime collection or verified evidence.
- Raw payload and secret retention are prohibited by this interface contract.

## Pilot measurement

A useful first pilot is deliberately bounded. Seed a small cohort from the
existing inventory, connect the most valuable evidence feeds, and measure:

- source-record acceptance and rejection counts;
- exact-duplicate rate;
- correlation and unmatched rates;
- conflict rate by field and feed pair;
- freshness-known and stale rates;
- owner/estate classification coverage;
- review-queue aging and resolution; and
- findings that reach validated closure.

Those measures show whether the evidence loop improves decisions. They do not
prove complete enterprise cryptographic coverage or PQC readiness.
