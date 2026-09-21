# Security policy
Report vulnerabilities privately through this repository's GitHub security reporting. Never include credentials, customer records or private infrastructure information in public issues.

## Current boundary
One C# loopback host serves React and assessment APIs. It uses isolated SQLite, bounded workbook parsing, assessment-scoped authorization, expected revisions, idempotency, CSRF and immutable reporting. Fixed fictional personas simulate roles; they are not enterprise authentication.

Static assets are loaded into an immutable memory snapshot. Packaged builds contain a SHA-256 manifest which the host validates; the bounded launcher requires it. Tiny test fixtures may omit a manifest, but this is not a release integrity claim. Source maps, dot-paths, encoded traversal, manifest downloads and cross-site requests are denied. Proxy headers do not establish transport cryptography.

Do not use this application for real enterprise responses until identity, HTTPS, handling, retention, database custody, observability, authorization and recovery have been independently qualified. Never weaken those boundaries to make a demonstration work.

## Publication
Run scripts/verify_public_reference.py before committing/pushing. It reports file paths and rule names, never matched secrets. An optional externally held private-marker file can screen known organization identifiers without committing those identifiers. Also review fixture/archive contents and changed history manually: a scanner is not a complete confidentiality proof.

No deployment workflow, public hostname or production credential is configured. CI has contents-read permission only.
