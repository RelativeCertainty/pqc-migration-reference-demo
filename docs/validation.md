<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Validation and release gates

## Reproducible command

```bash
npm ci
python3 -m pip install -r requirements-validation.txt
npm run check
```

The check lane covers linting, TypeScript contracts, browser and scanner unit
tests, canonical collection-contract validation, 12 Program Operations
behavior tests, the Program Operations MCP self-test, the static build, and
public-export inspection.

## Required test families

- Contract: validate `RepositoryScanResultV1` and every `EvidenceObservationV1`.
- Canonical collection contract: validate seven JSON Schema 2020-12 contracts,
  seven positive fixtures, seven deliberately invalid fixtures, safe-field
  boundaries, and cross-record collection references.
- Workflow kernel: validate seven versioned workflow contracts and prove
  transactional workflow/outbox and collection/cursor commits, tenant-bound
  references, inbox deduplication, restart and lease recovery, bounded retries,
  permanent-failure quarantine, and unknown-outcome reconciliation.
- Rules: algorithm, dependency, protocol, certificate, PQC, and false-positive fixtures.
- Boundaries: symlinks, traversal, denied directories, binaries, key formats, size, unreadable files, and existing output.
- Privacy: no absolute paths, excerpts, key material, private markers, identifiers, or infrastructure names.
- Determinism: fixed input, ruleset, and timestamp yield byte-identical reports.
- Fusion: scanner observations remain compatible with canonical reconciliation.
- UI: evidence labels, synthetic scanner proof, keyboard use, responsive layout, and bounded claims.
- Export: exact allowlist, new history, and rejection of office files, environments, credentials, and unreviewed output.
- Pages: base-path assets, hash routes, no runtime APIs, CSP, robots posture, and least privilege.
- Program Operations contracts: validate all versioned records and the aggregate synthetic fixture.
- Program Operations behavior: fixed 12-tool MCP allowlist, deterministic projections, recursive redaction, sanitized errors, read-only HTTP methods, and non-persistent draft preparation.
- Program Operations effect boundary: no communication dispatch, Jira or calendar mutation, approval recording, arbitrary SQL, arbitrary file access, or provider proxying.
- Enterprise completion: treat the fixture runtime as synthetic evidence until identity, authorization, relational authority, recovery, deployment, and approved adapters are independently validated.

## Release gates

- **RG1 Source boundary:** review the exact standalone file inventory.
- **RG2 Claims:** connect every public claim to synthetic or contract-tested evidence.
- **RG3 Security:** exclude secrets, personal data, private history, client material, and unsafe runtime access.
- **RG4 Licensing:** confirm MIT/CC BY 4.0 boundaries and dependency notices.
- **RG5 Product:** reproduce scanner, demo, method, backlog, and presenter narrative.
- **RG6 Owner publication:** approve the exact public payload before remote creation or push.

Publication is treated as irreversible because prior clones cannot be recalled.
A tag is created only after checks, licensing/provenance review, and RG6.
