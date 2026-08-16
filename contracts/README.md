# Evidence-fusion contracts

These Draft 2020-12 JSON Schemas are the stable application boundary for the
reference evidence-fusion slice:

- `evidence-observation.v1.schema.json` is the inbound port. Feed-specific
  adapters translate the bounded initial-inventory seed plus ExtraHop,
  vulnerability-management, PKI, SAST, or CMDB payloads into this neutral
  observation. Feed-native objects do not enter the domain core.
- `canonical-crypto-record.v1.schema.json` is the nested trusted-record port.
  The domain publishes correlated records while retaining observation references,
  exact-duplicate counts, conflicts, freshness, evidence composition, and
  review requirements.
- `evidence-fusion-result.v1.schema.json` is the versioned result port. It
  carries canonical records plus a closed, bounded source-reconciliation queue.
  Each opaque source identity is a collision-free result-local ordinal, has at
  least two disputed variants, and requires review. None of those variants
  enters a canonical record, and native source locators never appear in the
  queue.
- `evidence-fusion-result.v1.example.json` is the synthetic cross-language
  conformance vector. Python validates it against Draft 2020-12, and the
  TypeScript core must emit equivalent structured content from the same
  bounded fixture.
- `evidence-import-run.v1.schema.json` is the output port for one bounded
  local adapter invocation. It carries normalized observations and redacted
  diagnostics, never the native Snyk or Venafi payload.
- `migration-work-item.v1.schema.json` is a proposal-only planning contract.
  Its closed state model requires human review and cannot represent approval
  or execution authority.
- `migration-evidence-package.v1.schema.json` composes adapter runs, the
  canonical fusion result, proposed work, and the explicit no-actuation
  assurance boundary into one deterministically identified export.

The contracts deliberately separate three concerns:

1. `feedId` identifies where an observation came from.
2. `issueType` identifies the cryptographic problem represented by the
   observation, including protocol, algorithm/key-strength, certificate/trust,
   implementation, source-code, dependency, and vendor-control findings.
3. `estateClass` identifies the change-control context: first-party source
   code, OTS/COTS software, or a third-party/SaaS dependency.

All three schemas are recursively closed. They exclude raw source payloads and
require `containsSecret=false` plus `rawPayloadRetained=false`. A real adapter
must store or reference protected source evidence under its own approved data
classification and retention controls; these interface records are not a safe
place to copy credentials, keys, full certificates, source code, scanner
payloads, or customer data.

The local-file adapters satisfy that contract by emitting fixed categorical
facts and opaque local record references. They do not export user file names,
SARIF messages, rule identifiers, source paths, certificate identifiers,
subjects, issuers, or unrestricted algorithm strings. Non-synthetic imports
remain `unresolved` with `low` confidence because selecting a file does not
authenticate its producer, integrity, recency, or completeness.

Closed-schema compatibility is exact: after v1 is published, adding even an
optional emitted field or enum value requires a new version and an explicit
adapter migration. Producers and consumers must never rely on unknown-property
tolerance.

The result contract validates every queue and variant field. JSON Schema cannot
express that a variant's `feedId` and `sourceIdentityRef` equal its parent queue
item, that queue identities are unique within a result, that replay ordinals are
contiguous, or that quarantined observation IDs are absent from canonical
records. Those cross-record invariants are enforced by the result-port runtime
validator before a result is returned.

The runnable lab includes deterministic synthetic fixtures plus local-file
import adapters for Snyk Code SARIF and Venafi certificate-search JSON. A file
selected in the browser is processed in memory and is not sent to an
application server. These adapters establish local interface behavior; they do
not establish an authenticated remote connector, production inventory,
complete coverage, or an authoritative client record.

`EvidenceObservation v1` is deliberately finding-shaped. Its CMDB example
provides only a bounded correlation hint; typed ownership, service,
relationship, lifecycle, certificate, connection, and code-use payloads are a
future versioned-contract concern, not an existing v1 capability.

The adjacent `posture.v2.schema.json` is a separate runtime-response contract.
It records request-transport observations only. It deliberately cannot assert
Cloudflare Access state, exact-host PQ capability, or deployment-label
eligibility. This public repository is source-only and includes no provider,
identity, DNS, or live-host evidence. `posture.v1.schema.json` is retained as a
historical predeployment contract and is not emitted by this source revision.
