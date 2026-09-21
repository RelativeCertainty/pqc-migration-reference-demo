# Maintained application agent guide

## Non-negotiable architecture
This repository owns ONE application: C# is the application/backend authority and React is its frontend. Work inside apps/pqc-enterprise-demo. Do not revive portable Go, a Worker web server, a parallel Python API, a second React bootstrap or a separately hosted capacity app.

Preserve original reference capabilities and the assessment workflow together. Reference models remain explanatory; authoritative receipt, identity, technical review, gate and report behavior belongs in C#.

Read docs/MAINTAINER_GUIDE.md and docs/UNIFIED_APPLICATION.md before edits. README is the current run path. Other retained plans describe proposals/historical prototypes and cannot override this guide.

## Repository and publication safety
- Preserve unrelated dirty work, existing public history, licenses and attributions.
- Never import private repository history. Reconcile approved source files, not entire parent repositories.
- No employer names, contacts, SOWs, actual questionnaires/returns, presentations, state, logs, credentials or private recordings in public commits.
- Do not inspect an employer destination repository from this environment. Its local authorized Copilot performs integration there.
- Do not print secrets. Use metadata-only scanners; inspect archive structure and Office XML for publication safety.
- Never reset hard, force push, broadly clean, prune production data or bypass security checks.
- Existing host services are owner-operated, not disposable test dependencies. Use isolated synthetic state, loopback and bounded CPU/RAM.
- Do not send email, change tickets, enable production integrations or execute migrations under a code-edit request.

## Model invariants
- Source family, questionnaire profile, product, deployment and evidence source are different identities. Use the crosswalk, not number/name matching.
- Preserve all five initial discovery questions and optional detailed definitions. Partial answers, unknowns, referrals, blocked/disputed states are useful records, not failed respondents.
- Receipt is not answer application, evidence admission, technical verification, deliverable acceptance or execution authorization.
- Preserve attributed respondent assertions separately from authenticated importer/reviewer identity.
- Keep technical observations, business statements, standards proposals and adopted requirements separate.
- Separate exposure, impact, confidence and readiness; hybrid key exchange is not PQ authentication.
- Never silently merge deployments. Append reversible reviewed relationships, preserve source assertions and immutable history.
- Assessment context, server-derived principal, authorization, expected revision and idempotency apply to every command. Enforce again inside the transaction.
- Store events, outcomes and state atomically. Retry uncertain writes by reconciliation, not blind resubmission.
- Independent gate slots require distinct authorized principals. Simulated role switching is not real enterprise acceptance.
- Reports bind exact input revisions and bytes; Phase 2 explicitly selects its accepted/qualified Phase 1 package.
- An unknown denominator forbids enterprise coverage percentages. Filters never redefine accepted scope.
- Preserve v3 migration bytes/checksum and the ordered additive migration chain. Never rewrite applied migrations or retained reports.

## Implementation map
- Program.cs and Api/: HTTP adapters and one host.
- Core/: domain/application behavior, interfaces, command admission, report evaluation and durable ledger.
- Capacity/: pure bounded planning calculations, exposed inside the same host.
- frontend/src/: one React shell, assessment modules and shared theme.
- frontend/src/reference/: retained reference components and deterministic illustrative models.
- ReferenceData/ and Fixtures/: versioned neutral catalogs and synthetic definitions.
- contracts/, schemas/, manifests/: versioned contracts and simulated execution boundaries.
- workers/, tools/, scripts/: offline synthetic source normalization, preparation, validation and operator tooling. They must not become an alternate application authority.
- tests/: parser, domain, HTTP, custody, report, architecture, recovery and security regression tests.

## Ports/adapters integration in the destination environment
Do not replace the destination scaffold, root agent instructions, CI or startup files. Inventory its interfaces and conventions locally, then map these responsibilities into existing ports:
principal/assignment access; assessment command store; artifact custody/parser; evidence query; identity reconciliation; report-impact evaluation; report rendering/storage; work queue/case queries.
Keep business policies in C# core/application layers, database and HTTP behavior in adapters, and React bound to typed APIs. Bring compatibility tests with each vertical slice. Document explicit semantic differences. No bridge process to Go is acceptable as the completed migration.

## Development procedure
1. Read the scoped code, current contracts, migration chain and relevant tests.
2. State affected behavior and risk: R2 workflow/UI; R3 authorization/custody/migration. Owner observations remain owner-entered.
3. Implement the smallest coherent slice across C#, types, UI and tests.
4. Reuse repository fixtures. Never use real enterprise responses for development.
5. Acquire dependencies explicitly using pinned lockfiles. Tests never silently download them.
6. Update current docs and readable HTML. Do not make historical validation counts current claims.
7. Review publication boundaries before committing. Run the full sequential suite on committed source; preserve failures and skips.
8. Do not claim product/enterprise readiness from builds, screenshots, synthetic decisions or local tests.
9. Push only the explicitly authorized branch after validation, without rewriting history.

## Commands
Use README for setup. Build: npm run build.
Focused compile: npm run typecheck.
Post-commit suite: .venv/bin/python scripts/validate_reference.py.
Public guard: python3 scripts/verify_public_reference.py.
Launcher: .venv/bin/python scripts/start_reference.py.

## Continuation priorities
First verify the unified navigation and one complete response-to-report journey with the owner. Then qualify enterprise identity, approved HTTPS, SQL Server adapter, custody/retention and backup/restore before real responses. Qualify one owner-confirmed context source plus one certificate/TLS source with exact product/version/permission and completeness tests. Measure workloads before treating capacity coefficients as benchmarks.
Phase 3/4 execution remains future work. Provider tickets are bindings to canonical work, never the source of cryptographic verification.
