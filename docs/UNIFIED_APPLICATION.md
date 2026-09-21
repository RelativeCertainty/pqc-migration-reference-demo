# One application: migration and capability record
## Decision
The C# implementation replaces the former Go application. React remains the sole frontend. The assessment workflow extends that product; it is not a separate demo.

## Original runtime capabilities
- Static SPA and typed assets: now C# StaticAssets, with safe paths, bounded immutable snapshots, optional verified manifest at the direct test-host boundary and mandatory manifest in the packaged launcher.
- UI integrity: frontend build generates asset-manifest.sha256; C# validates every listed hash and complete membership. Manifest and source maps are not downloadable.
- Health/readiness: /healthz and /readyz remain available, alongside /health/live and /health/ready. Readiness now checks loaded synthetic state rather than merely process availability.
- Posture: authenticated /api/posture uses versioned pqc-posture.v3. Storage is truthfully isolated_sqlite and access is synthetic_session_only; the former v2 stateless/no-auth contract remains historical, not the active response schema.
- Version: the C# executable accepts --version and reports assembly source identity/runtime. UI responses include the validated manifest hash when present.
- Security: loopback-only explicit host, no trusted forwarded-crypto claims, same-origin checks, CSRF, no-store, safe error codes, disabled request logging, CSP and sensitive-path rejection.
- Portability: source builds with .NET rather than Go. The supported bounded launcher is Linux-only today; there is no assertion of a qualified Windows installer or public HTTPS deployment.

## Preserved original frontend capabilities
All twelve original topic modules are retained: overview, architecture, TVM mapping, inventory, prioritization, workflow, scenarios, decisions, patterns, posture, dashboard and questions. Guided explanation controls remain inside the common shell. Evidence-fusion, risk and source-status logic and their tests move with those modules. Their illustrative outputs are not promoted to authoritative assessment conclusions.

The new operational application supplies discovery, specialist forms, Excel exchange, receipt/reconciliation, staged record review, assessment gates, business analysis, immutable reports, graph/search/coverage and work queues. Pure capacity calculations now run in the same C# host with same-session APIs and a React module; the standalone host is retired.

## Deliberate differences
The old Worker and Go routes were stateless/read-only. The integrated application has durable synthetic state and authenticated role-scoped commands. Consequently API posture schema, access semantics, readiness and CSP are explicitly different. HTTP loopback does not send misleading production HSTS or claim upstream TLS. No second runtime is kept as an authority for compatibility.

The inherited public Git history preserves old source. Current runtime configuration, CI and root run commands select C#/React only. Python fixtures, normalizers, BOM tools and schema examples are supporting development tools, not a Python production backend.

## Evidence and limits
This reconciliation is a development candidate. Exact executed checks are recorded by scripts/validate_reference.py against its commit. No source file, automated test, simulated decision or screenshot is owner acceptance or proof of live integration. Enterprise identity, SQL Server, HTTPS and migration execution still require their separate gates.
