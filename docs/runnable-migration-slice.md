# Runnable Snyk + Venafi migration slice

## Outcome and boundary

North star: **bounded evidence import → normalized observations → canonical
correlation → human-reviewed migration proposal → durable evidence export**.

This slice closes the gap between a modeled architecture and a locally
executable result. It deliberately stops before credentialed collection,
ticket creation, infrastructure mutation, cryptographic migration, or claims
about deployed behavior.

The browser is the execution boundary. Selected files remain in browser
memory. The Cloudflare Worker and portable Go runtime continue to expose only
static assets and the read-only posture endpoint; neither receives evidence
files or stores migration state.

## Ports and adapters

```text
Snyk Code SARIF ──> SAST adapter ───────────────┐
                                                │ EvidenceObservation v1
Venafi search JSON ─> PKI-inventory adapter ───┤
                                                v
Synthetic inventory seed ───────────────> evidence-fusion core
                                                │
                                                v
                                  canonical records + review state
                                                │
                                                v
                                    migration-planning service
                                                │
                                                v
                                    evidence package JSON export
```

The inbound application port is `EvidenceBatchAdapter`; the orchestration
port is `RunMigrationSliceInputPort`. Vendor formats are confined to adapters.
The domain core accepts only `EvidenceObservationV1` and publishes only closed,
versioned contracts.

### Snyk Code adapter

- Input: SARIF 2.1.0 emitted by `snyk code test`.
- Bound: 50 SARIF runs and 5,000 results per import.
- Normalization: crypto-relevant findings become source-code use,
  implementation/configuration, or cryptographic-dependency observations.
- Exclusion: unrelated SAST findings are counted as skipped and do not enter
  canonical records.
- Redaction: native messages, rule identifiers, source paths, line numbers,
  tool strings, and file names are withheld from the exported package.
- Claim ceiling: an arbitrary local file remains unresolved, low-confidence
  evidence; no producer authentication or deployed-runtime assertion is made.

### Venafi certificate-search adapter

- Input: a modeled Venafi-shaped JSON object containing `certificates`,
  `certificateDetails`, `items`, or `results`.
- Bound: 30 certificate records per import; the application also enforces a
  combined 90-observation limit per correlation target.
- Normalization: each certificate becomes separate certificate/trust,
  public-key algorithm/key-strength, and relying-party dependency
  observations.
- Exclusion: private keys, certificate bodies, credentials, file names,
  certificate identifiers, subjects, issuers, and unrestricted algorithm
  strings are not copied to the result.
- Claim ceiling: an arbitrary local file remains unresolved, low-confidence
  evidence; its vendor provenance, completeness, and deployed behavior are
  unproved.

## Capability contract

| Field | Contract |
| --- | --- |
| Capability | Convert two bounded vendor-shaped evidence files into proposed PQC migration work. |
| Subject scope | One user-selected synthetic correlation target per import. |
| Inputs | Snyk Code SARIF 2.1.0 and bounded, modeled Venafi-shaped certificate-search JSON, with synthetic/non-synthetic provenance. |
| Outputs | Import-run records, canonical fusion result, proposed work items, and a deterministically identified evidence package. |
| Side effects | Browser-local artifact download only. No server, tenant, provider, or ticket-system write. |
| State | Work items are always `proposed`; review is always required; approval is always unrecorded. |
| Idempotency | Stable observation IDs and package ID are derived deterministically from normalized source identity and correlation scope. |
| Failure behavior | Invalid shape, timestamp, context, or safety limit fails closed; invalid child rows are skipped with bounded diagnostics where safe. |
| Acceptance | Both fixtures normalize, fuse to their selected inventory records, produce reviewable work, and export no native message, path, file name, certificate identifier, subject, issuer, raw payload, approval, or execution authority. |
| Recovery | Restore fixtures or reload the page. No external state exists to roll back. |

## Authority and data boundary

| Operation | Effect class | Authority | Evidence | Recovery |
| --- | --- | --- | --- | --- |
| Select a file | Read-only local | Browser user | Generic adapter source label only; local file name is withheld | Clear selection or reload |
| Normalize | Deterministic local | Adapter contract and bounds | Observation IDs, counts, diagnostics | Reject or restore fixture |
| Correlate | Deterministic local | Fusion contract | Provenance, conflicts, duplicates, review reasons | Rerun with corrected target |
| Propose work | Proposal-only | Planning rules | Evidence references, rationale, authority gates | Discard package |
| Export JSON | Local artifact write | Explicit user click | Closed evidence package | Delete downloaded file |
| Apply migration | External effect | Not implemented or authorized | None | Not applicable |

No model inference is used. Classification and planning are deterministic and
reviewable. No adapter response can approve itself, create a ticket, alter a
cryptographic configuration, or attest completion.

The application service additionally caps combined normalized evidence at 90
observations per correlation target. Larger inventories must be split into
separately reviewed runs instead of silently overrunning the canonical-record
contract or a modest local machine.

## Run locally

```sh
npm ci
npm run dev
```

Open the loopback URL printed by Vite, choose **Run slice**, and either retain
the bundled fixtures or select local files. The fixtures intentionally include
one unrelated Snyk finding so the skipped-record path is visible.

Generate a Snyk input with:

```sh
snyk code test --sarif-file-output=snyk-code.sarif.json
```

For Venafi, capture the JSON result from a certificate-search operation using
your separately governed access method, verify that it matches the modeled
fixture shape, then select the response file. Do not place API credentials in
an import file. Selecting a file does not authenticate it as vendor evidence.

Vendor contract references:

- [Snyk Code CLI `test` command](https://docs.snyk.io/developer-tools/snyk-cli/commands/code-test)
- [Venafi certificate search via API](https://docs.venafi.cloud/api/certificate-search-via-api/)
- [Venafi API search request components](https://docs.venafi.cloud/api/components-of-api-search/)

Venafi documents separate `certificatesearch`, `certificateinstancesearch`,
and `managedcertificatesearch` operations. The local adapter represents their
shared certificate-inventory category; a credentialed connector should keep
those endpoint-specific request/response transports behind this port and add
contract fixtures from the exact tenant/API revision used in rehearsal.

## Evidence and claim status

```yaml
capability_area: local-evidence-to-migration-proposal
implementation_state: source-implemented
evidence_tier: Development evidence
confidence: high for deterministic synthetic-fixture behavior; unresolved for arbitrary imported-file provenance
assessment: Two categorical, redacted import adapters execute through one domain core and produce a review-required, exportable proposal.
evidence_limit: Synthetic fixtures and local tests do not prove authenticated collection, vendor-format completeness, customer data fit, deployed-runtime truth, or migration execution.
known_gaps:
  - authenticated connector collection and secret-by-reference handling
  - tenant identity, retention, append-only persistence, and operator audit log
  - approved ticket/change adapter and independent completion verification
next_gate: Rehearse one non-production, credentialed read-only collection through a local server-side connector with redacted evidence and explicit cleanup.
```
