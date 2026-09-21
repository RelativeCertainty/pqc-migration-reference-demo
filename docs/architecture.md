<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Reference architecture

## Independent delivery boundary

The project is an employer-neutral, self-contained reference implementation.
It requires Node.js and static hosting only. Private automation systems may
adapt to the public contracts, but they are not dependencies or execution
authorities.

## Onion layers

1. **Domain:** evidence observations, canonical inventory concepts, risk context, migration decisions, gates, and evidence status.
2. **Application:** use cases such as `ScanRepository`, normalize observations, prioritize a cohort, propose a change, and verify a result.
3. **Ports:** filesystem, clock, hashing, ruleset, observation, report, source-feed, change-proposal, readback, and measurement boundaries.
4. **Adapters:** local read-only filesystem, scanner rules, JSON/Markdown reports, static UI projections, and future authorized enterprise integrations.

Dependencies point inward. The domain does not import a scanner, cloud SDK,
vendor model, UI framework, workflow engine, or private platform.

## Scanner slice

```text
Authorized directory
  -> ReadOnlyFilesystemPort
  -> evidence Specifications
  -> ScanRepository
  -> EvidenceObservationV1
  -> RepositoryScanResultV1
  -> create-only JSON and Markdown adapters
```

The filesystem adapter refuses symbolic links and traversal, skips denied
directories and file types, and never emits absolute paths or source excerpts.
Specifications identify candidates, not vulnerabilities.

## Change authority

Discovery and recommendations can be automated. Material changes require
explicit authorization. A proposal is not execution evidence, execution is not
readback, and readback is not a measured outcome.

## Future adapters

TLS, PKI, SSH, KMS/HSM, VPN, API, and signing adapters must translate
provider-native information through anti-corruption boundaries. Each adapter
must preserve source authority, provenance, classification, retention,
idempotency, rollback, and independent verification.
