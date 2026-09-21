# PQC Assessment and Migration Reference
One C# backend, one React application, one maintained repository.

This is the maintained public source for the original reference demo and the assessment workspace. The C# host replaces the former Go and Worker servers; it serves the React build, owns durable synthetic assessment state, and exposes the original posture and health capabilities. There is no second capacity app or separate reference-demo service.

## Start here
Read the [maintainer and Copilot guide](docs/MAINTAINER_GUIDE.readable.html), then the [capability migration record](docs/UNIFIED_APPLICATION.readable.html). Coding agents must follow [AGENTS.md](AGENTS.md).

Included in the same authenticated application:

- Assessment work: receipt, reviewed identity relationships, supporting records, conclusions and report consequences.
- Five-question discovery forms, full specialist questionnaires, Excel exchange, software recognition examples and multiple products/deployments.
- Scope, roles, independent gate decisions, exact Phase 1 selection, Phase 2 business context and immutable reports.
- Asset search, estate graph, coverage, findings, standards, run history and migration lookahead.
- Original reference inventory, evidence fusion, prioritization, architecture, migration patterns, scenarios, decisions, assurance posture and guided explanations.
- Formula-based capacity planning, scenario comparison, sensitivity analysis and downloadable review packages. These estimates are assumptions, not benchmarks; Terraform output does not provision infrastructure.

## Prepare and run
Prerequisites: .NET SDK 10.0.400, Node 22.12+, Python 3.11+. The bounded local launcher currently requires Linux user-systemd/cgroup support. Do not install a second backend or expose the Vite development server as the product.

Dependency acquisition is explicit:
```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-handoff.txt
npm --prefix apps/pqc-enterprise-demo/frontend ci
dotnet restore apps/pqc-enterprise-demo/PqcEnterpriseDemo.csproj --locked-mode --disable-parallel
npm run build
.venv/bin/python scripts/start_reference.py
```

Open http://127.0.0.1:18479/ on the same host. Keep that foreground command running; Ctrl+C stops only this instance. It creates owner-only synthetic state under ignored artifacts, checks resource headroom, and enforces one CPU, 1 GiB RAM, no additional swap and a two-hour runtime limit. Restart the same command to resume the same state. Never delete it to solve a migration error.

The login lists fixed fictional demo personas. Its intentionally public demonstration password is `synthetic-demo-only`; it is not an enterprise credential. Use Assessment lead for coordination, Technical review lead for independent record review, and the designated sponsor/risk/business roles at their respective gates. Choosing a demo persona is simulation, not identity proof.

The original reference screens are now **Reference explanations** in the shared navigation. The calculator is **Capacity planning**. Supporting explanations do not overwrite assessment facts or authorize migration.

## Validate committed source
After reviewing and committing changes, run the sequential suite once:
```sh
.venv/bin/python scripts/validate_reference.py
```
It records the exact commit and per-check results under ignored `artifacts/reference-validation/`. It runs the publication boundary, C# build, React build/typecheck, Python domain/API suites, React tests and recorder tests. Optional historical/browser-dependent proofs are explicitly skipped when their prerequisites are unavailable. Tests do not establish owner acceptance.

## Public/private boundary
Only employer-neutral code, contracts, explanatory material and synthetic fixtures belong here. No employer contacts, project reports, SOWs, real returned forms, state databases, credentials, recordings or private Git history belong in this repository.

The blank operational fixtures are neutral reference reissues, with new content hashes and an inert example.invalid return address. They are not historical distributed enterprise forms and must not be mistaken for a live return channel.

The baseline mapping contains 27 questionnaire profiles and 27 runtime families with an explicit many-to-many crosswalk, not numerical identity. A separate versioned extension adds virtualization as the 28th software class without relabeling historical forms.

## Boundaries
This is a synthetic development application, not a deployed enterprise product. Enterprise SSO, approved HTTPS, SQL Server, live source qualification, production backup/restore and security review remain qualification work. SQLite persistence and fixed personas are deliberately demo-only. No live ticket submission or Phase 3/4 migration execution is enabled.

Python modules are offline fixture producers, normalizers and validation/reference tools, not an alternative runtime backend. Illustrative TypeScript calculations are reference models, not authoritative Phase 2 assessments.

The preserved public history contains the retired implementation for traceability. No private source history was merged.

## Licensing
See [LICENSE](LICENSE), [NOTICE](NOTICE), [LICENSE-DOCS](LICENSE-DOCS) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Public visibility is not permission to ignore the applicable source and third-party licenses.
