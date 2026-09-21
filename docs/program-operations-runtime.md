<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Program Operations: historical design and contract proposal

Status: retained design reference, not an installed HTTP/MCP runtime in this
application. Its named tools/program-operations entrypoints are not part of
this reconciliation. The language-neutral contracts and synthetic fixture are
preserved for future integration into the C# authority. Do not start or build
a parallel Python application from the historical instructions below.

## Purpose

A large PQC assessment has two kinds of work happening at once. The technical
team is discovering and validating the cryptographic estate. The program team
is also tracking what must happen, who must act, what evidence exists, and
which decision is due next. If those records live only in conversations, the
assessment becomes difficult to steer and difficult to defend.

This reference implementation gives those program records a stable,
machine-readable shape. A fresh checkout can run the synthetic API and MCP
server immediately. An enterprise team can then replace the fixture with
approved identity, database, backlog, calendar, document, and reporting
adapters without changing the domain contracts.

## The operating picture

```text
Approved program plan and enterprise commitments
  -> cycle objective
  -> weekly priorities
  -> daily outcomes and work windows
  -> work record and evidence references
  -> actions, dependencies, RFIs, and decisions
  -> gate assessment and accepted deliverable
```

A record identifier is always paired with a plain-language name. A request for
information is an enterprise dependency, not merely an email to a person. It
may be satisfied through approved API access, repository access, an export,
documentation, technical clarification, or bounded validation.

## Authority model

- Enterprise source systems remain authoritative for their own source facts.
- The admitted relational program store will own operational program state.
- The approved backlog will own Epic and Story execution state.
- Finalized reports are immutable, digest-bound snapshots.
- The accountable human owns communication, decisions, and acceptance.
- The API, MCP interface, dashboards, and workbooks are projections over those
  authorities; they do not silently create a second source of truth.

The checked-in fixture is intentionally different: it is synthetic test input,
not a durable enterprise authority.

## Daily record model

`ProjectDay.v1` bounds the day to three intended outcomes and one primary
artifact. It links to stories, actions, dependencies, RFIs, and gates. Work
windows provide planning capacity; actual sessions and time entries remain
separate so planned time is never mistaken for completed work.

`DailyLogEntry.v1` is append-oriented. `WorkSession.v1` describes what was
actually done. `TimeEntry.v1` records accurate elapsed minutes but explicitly
does not decide contractual billability. `DailyStatusSnapshot.v1` creates a
digest-bound close position. A correction creates a superseding record rather
than rewriting a finalized record.

`StakeholderUpdate.v1` separates completed facts from planned work. It allows
at most three asks, each with an accountable role, required date, and delivery
consequence. The reference runtime always returns `dispatchAllowed: false`.

## Safe runtime boundary

The HTTP server binds to loopback and implements GET routes only. Unsupported
methods return `405`. The MCP server accepts narrow JSON-RPC tool calls over
standard input and standard output. Every output passes through recursive
redaction; errors do not include stack traces, file paths, payload excerpts, or
credentials.

The reference runtime cannot:

- Send email or chat messages.
- Change calendars.
- Create or modify backlog records.
- Record stakeholder approval or decisions.
- Execute arbitrary commands or SQL.
- Read arbitrary local files.
- Proxy a source-system API.
- Expose raw evidence or source payloads.

## From reference runtime to enterprise service

### 1. Admit the model

Review the JSON Schemas, record meanings, authority boundaries, classification,
retention, correction, and acceptance semantics. Assign the owning functions.
Record differences as versioned contract changes instead of local exceptions.

### 2. Build the relational authority

Create versioned migrations for programs, days, append-only log entries, work
sessions, time entries, actions, dependencies, RFIs, decisions, gates, report
snapshots, evidence references, external bindings, and change history. Enforce
program and classification boundaries at the database and application layers.

Finalization and supersession need optimistic concurrency and auditable state
transitions. A report correction must preserve the prior digest and reference
the record it supersedes.

### 3. Bind enterprise identity and policy

Replace loopback trust with approved browser and service identities. Apply
deny-by-default authorization by program, role, data class, environment, and
operation. Keep secrets in the approved secret service and pass opaque secret
references to adapters. Do not record tokens, passwords, private keys, prompts,
or unrestricted source records in logs or telemetry.

### 4. Add read-only enterprise adapters

Implement the protocols in `tools/program-operations/adapters.py`:

- Program record store.
- Work-availability import that omits personal event titles.
- Backlog execution-state import.
- Allowlisted external-reference resolution.

Add source-specific adapters behind separate evidence-harvest ports. Program
Operations tracks their dependencies and results but must not become a generic
provider proxy.

### 5. Add durable operations

Add deployment manifests, migrations, readiness checks, safe telemetry,
resource limits, backup and restore procedures, failover tests, rollback, and
retention controls. Generate human workbooks and formal reports from the same
record authority.

### 6. Prove the boundary

Test authentication, authorization, concurrency, idempotency, supersession,
audience filtering, redaction, duplicate imports, stale external references,
backup restoration, and recovery. Test that API and MCP clients cannot send,
approve, mutate the backlog, or expose restricted fields.

Only source-backed, independently verified evidence can advance an integration
beyond synthetic or contract-tested status.

## Repository map

- `contracts/program-operations/`: language-neutral JSON Schemas.
- `fixtures/program-operations/`: independently authored synthetic program.
- `tools/program-operations/openapi.v1.yaml`: read-only API contract.
- `tools/program-operations/server.py`: HTTP and stdio MCP entrypoint.
- `tools/program-operations/runtime.py`: query, draft, redaction, and safe-error logic.
- `tools/program-operations/adapters.py`: enterprise adapter interfaces.
- `tools/program-operations/config/`: disabled-by-default binding example.
- `tools/program-operations/tests/`: deterministic contract and runtime tests.

## Evidence statement

The implementation demonstrates executable behavior against synthetic input.
It does not establish an enterprise deployment, an authorized source
connection, complete estate coverage, accepted findings, or a completed PQC
migration.
