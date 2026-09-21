<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Current rolling-wave projection

Projection metadata:

- Source schema: `pqc.project-backlog.v2`
- Source backlog: `planning/backlog.v2.yaml`
- Backlog SHA-256: `b1c444583042c49b06a18146ae893d310c4437d8b5525a98a7b562acb0c75f00`
- Iteration: `C01` (relative Weeks 1-2)
- Selection rule: include every and only initial-wave story whose authoritative backlog status is `ready`.

The YAML backlog remains authoritative. `ready` is a scheduling state, not
evidence that delivery has started or that a required artifact exists. Delivery
evidence for these stories remains `planned` until supported and advanced in the
backlog through the governed planning process.

## Ready initial-wave stories

### PQC-E00 — Engagement Governance, Reporting, and Stakeholder Alignment

- `PQC-E00-S01`, Weeks 1-2: Establish engagement governance, roles, forums, and escalation.
- `PQC-E00-S02`, Weeks 1-18: Maintain RAID, decisions, dependencies, actions, and scope changes.
- `PQC-E00-S03`, Weeks 1-18: Deliver biweekly status reporting, findings reviews, and acceptance coordination.

### PQC-P1-E01 — Confirm Scope, Assessment Method, and Standards

- `PQC-P1-E01-S01`, Week 1: Confirm scope, exclusions, authority, and success criteria.
- `PQC-P1-E01-S02`, Weeks 1-2: Establish the assessment method, taxonomy, and standards register.
- `PQC-P1-E01-S03`, Week 2: Approve evidence-quality, coverage, confidence, and completion rules.

### PQC-P1-E02 — Establish Source Access and Evidence-Handling Controls

- `PQC-P1-E02-S01`, Weeks 1-2: Establish the authoritative source and source-owner register.
- `PQC-P1-E02-S02`, Week 2: Confirm access, classification, retention, and handling requirements.

## Projection boundary

No `proposed`, `in_progress`, `blocked`, `done`, or `accepted` story is included.
Jira issues or boards may project this list after a separately authorized
external action, but they do not replace the YAML source or change story status.
