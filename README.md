# PQC Migration Reference Demo

An independent, synthetic reference implementation for planning an enterprise
post-quantum cryptography (PQC) migration. It demonstrates how cryptographic
inventory evidence can be normalized, correlated, prioritized, reviewed, and
carried through governed migration decisions without overstating what the
evidence proves.

This public repository is a **locally runnable reference implementation** and
provides development evidence only. It is not a live customer service,
production deployment, cryptographic implementation, completed migration, or
NIST/FIPS validation.

## What is included

- A React and TypeScript interface for a ten-system synthetic inventory,
  prioritization, evidence review, migration patterns, and assurance posture.
- Closed JSON Schema contracts for evidence observations, canonical inventory
  records, fusion results, and the bounded read-only posture API.
- Deterministic evidence-fusion logic that preserves provenance, conflicts,
  unmatched records, replay counts, and human-review requirements.
- A local slice that imports Snyk Code SARIF and modeled Venafi-shaped
  certificate-search JSON, normalizes both through categorical, redacted adapters,
  correlates them to inventory, proposes governed migration work, and exports
  a closed evidence package.
- A Cloudflare Worker adapter that serves static assets and a read-only
  `/api/posture` endpoint without application storage or request-payload echo.
- A standard-library-only Go server for portable, loopback-first execution.
- Synthetic SBOM/CBOM tooling and a scoped cryptographic inventory.
- NIST source-status and claim-boundary documentation.
- Unit, integration, packaging, parity, contract, and security-oriented tests.

## What this demonstrates

- Evidence boundaries that distinguish source inspection, runtime observation,
  exact-host capability, algorithm standards, and module validation.
- Ports-and-adapters design for combining heterogeneous security evidence
  without silently discarding disagreement or provenance.
- Fail-closed contracts, deterministic processing, bounded telemetry, and
  operator review before sensitive conclusions or actions.
- Portable delivery across a Worker-oriented runtime and an embedded Go
  executable while keeping their posture semantics aligned.

## What this does not claim

- No customer, employer, production, or private-environment data is included.
- No authenticated remote connector, public hostname, identity policy, DNS
  configuration, or cloud-provider deployment is asserted. The two working
  adapters accept user-selected files in browser memory only.
- No inventory completeness, migration completion, business outcome, or
  production adoption is asserted.
- No exact browser-session key exchange, hybrid-PQ endpoint capability,
  post-quantum visitor signature, CAVP certificate, CMVP certificate, or
  FIPS-validated runtime is asserted.
- The repository does not implement cryptographic algorithms; it models
  migration governance, evidence handling, and assurance boundaries.

## Run locally

Prerequisites:

- Node.js 22.12 or newer and npm 10
- Go 1.25 or newer (the module selects Go 1.26.6 for validation)
- Python 3.11 or newer for the BOM tests

```sh
npm ci
npm run check
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q scripts/test_pqc_bom.py
```

For local development:

```sh
npm run dev
```

Open the app, select **Run slice**, and use the included fixtures immediately.
To exercise a real local export without configuring credentials:

```sh
snyk code test --sarif-file-output=snyk-code.sarif.json
```

Import that SARIF file into the SAST port. A bounded JSON response shaped like
the modeled Venafi certificate-search fixture can be imported into the
PKI-inventory port. The browser normalizes the files locally; withholds native
messages, paths, file names, certificate identifiers, subjects, and issuers;
authorizes no change; and can export
`pqc-migration-evidence-package.v1.json` for review.

For the portable Go build:

```sh
npm run portable:build
./portable/bin/pqc-reference-demo
```

Native execution listens on `127.0.0.1:8080` by default. The checked-in
Worker configuration intentionally has no public route and disables
`workers.dev` and preview URLs. Publishing this source does not deploy it.

## Evidence and design notes

- [Evidence-fusion architecture](docs/evidence-fusion-architecture.md)
- [Runnable Snyk + Venafi migration slice](docs/runnable-migration-slice.md)
- [NIST traceability](docs/nist-traceability.md)
- [NIST source-status registry](docs/source-status-registry.md)
- [Inventory speaker dictionary](docs/inventory-speaker-dictionary.md)
- [Contract boundaries](contracts/README.md)
- [Portable runtime](portable/README.md)

The included data and examples are deterministic synthetic fixtures. Any
production use would require its own identity, authorization, data
classification, retention, connector, deployment, observability, recovery,
cost, and accountable-owner review.

Snyk and Venafi are trademarks of their respective owners. This independent
reference implementation is not affiliated with, sponsored by, or endorsed by
either vendor.

## License posture

This repository is publicly visible for portfolio and evaluation purposes but
is not offered under an open-source license. See [LICENSE](LICENSE) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Third-party dependencies
remain subject to their own licenses.
