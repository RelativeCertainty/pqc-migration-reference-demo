# Maintainer and integration guide
## The application you are continuing
The maintained source is RelativeCertainty/pqc-migration-reference-demo. The sole host is apps/pqc-enterprise-demo/PqcEnterpriseDemo.csproj, with React at frontend/. C# replaces the former Go runtime and adds durable assessment behavior. Capacity planning and reference explanations are modules in that same application.

## Reproduce locally
Follow root README's explicit dependency and build commands. The launcher creates a reproducible all-family synthetic fixture and isolated owner-only SQLite state, serves the compiled frontend, and opens no external provider connections. Use the host-only URL it prints. Start/resume does not reset records. The default URL is http://127.0.0.1:18479/.

The launcher requires Linux systemd user scopes and refuses inadequate memory/disk or a held launcher lock. Do not evict another application or bypass that lock. A Windows/enterprise deployment adapter requires separate design and qualification, not removal of safeguards.

## Orientation
Assessment work is the primary coordinator/reviewer surface. An assessment contains requests, receipts, investigations, reviewed relationships, conclusions and reports. Its five case sections connect returned information, systems/sources, supporting information, report consequences and history.

Discovery is the five-question contributor path. Specialist questionnaires and historical routing remain available for their proper audiences. Estate overview, Assets and Source coverage help investigation; filters do not alter formal assessment scope. Reports and Guided assessment expose distinct report and gate responsibilities.

Reference explanations preserve the prior inventory, architecture, evidence fusion, prioritization, decision and posture demonstrations. Their calculations are illustrative. Capacity planning exposes deterministic estimates, equations, assumptions, tier comparisons, sensitivity and review packages. Neither module silently modifies the assessment or provisions infrastructure.

## Synthetic role walkthrough
1. Sign in using the fictional Assessment lead persona.
2. Create a new assessment or open a clearly labelled worked example. Never reuse enterprise returns.
3. Receive a neutral operational workbook under the selected assessment; inspect provenance, answers and product rows before recording receipt.
4. Compare duplicate/revised returns. Resolve competing edits explicitly; blanks do not erase reviewed information.
5. Review same/different/unresolved deployments, preserving original assertions.
6. Stage supported synthetic records. An independent technical-review persona records determinations; the lead separately admits evidence where allowed.
7. Preview specific finding, limitation and next-decision effects before committing conclusions.
8. Generate Phase 1 after its required gates. Simulated sponsor/lead decisions bind the exact report revision.
9. Select that exact accepted or qualified Phase 1 report for Phase 2. Supply attributed business consequence/lifetime information where known; leave meaningful unknowns explicit.
10. Have the risk/business roles review analysis, generate Phase 2, and exercise its deliverable gate. Downloaded report bytes retain the selected basis and limitations.

This describes an engineering rehearsal, not owner or enterprise acceptance. Existing scenario preparation scripts generate fixtures; they do not replace browser or real-user validation.

## Model and integration boundaries
Use IEnterpriseStore and the typed scoped APIs as the current application boundary. Existing concrete SQLite implementation is a reference adapter, not the required enterprise database. Do not transport it wholesale into a destination core that already has ports/adapters.

In the authorized destination environment, map principal and assignment lookup, command transactions, custody, normalization/query, identity review, report-impact evaluation, immutable report storage and work-queue projections into its existing interfaces. Keep C# invariants and carry contract tests. Port pure offline Python normalizers into the destination's selected adapter language when runtime collection is implemented; do not introduce a second web service just to reuse fixture code.

## Storage and recovery
The ignored artifact directory includes state and source fixture custody. Never commit it. Preserve application release, fixture/catalog versions, SQLite state and custody together before upgrading. The C# backup command operates only on explicitly selected isolated state:
dotnet apps/pqc-enterprise-demo/bin/Release/net10.0/PqcEnterpriseDemo.dll --data-dir ABSOLUTE_STATE --fixture ABSOLUTE_SYNTHETIC_INPUT --backup-dir ABSOLUTE_NEW_BACKUP
Do not run it against real or shared services. Restore into a new owner-only directory and validate with the matching release. Keep the prior pair recoverable. No database downgrade or history deletion is supported.

## Tests and evidence
Run scripts/validate_reference.py after committing. It runs checks sequentially and stores per-command logs plus the exact commit. The API suites launch isolated random-loopback servers and synthetic databases. Browser/historical release proofs require explicit artifacts and may skip; a skip is not a pass.
Any repair after a failing suite needs its affected checks repeated against the repair commit. Do not relabel the original failure.

## Publication and continuation
Run the metadata-only publication guard and manually inspect staged diffs, workbook XML and added history. Blank forms here are neutral reissues, not the originals sent to a customer. Keep private contacts, reports and customer-specific instructions outside this repository and its history.
Priorities are owner walkthrough, enterprise foundation qualification, one read-only cohort and measured capacity. Live migration, ticket writes and public deployment are not enabled by this source reconciliation.
