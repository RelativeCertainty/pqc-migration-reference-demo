<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Project planning

`backlog.v2.yaml` is the authoritative employer-neutral assessment backlog. It
defines the 18-week, two-phase engagement, 15 epics, 45 directly nested
stories, phase and engagement gates, evidence requirements, and Jira projection
metadata. Its six-item future-state appendix is outside the two-phase backlog,
requires future authorization, and has `jiraProjection: false`.
`project-backlog.v2.schema.json` defines the machine-readable contract.

## Authority and projections

- The YAML backlog is the planning source of truth.
- The [18-week plan](../docs/two-phase-assessment-project-plan.md),
  `current-wave.md`, status reports, Jira issues, and boards are projections.
- Planning IDs are stable reference identifiers, not Jira keys. Jira-assigned
  keys must not be written back as replacements for planning IDs.
- Scope, acceptance criteria, dependencies, evidence requirements, status, and
  phase decisions change in YAML first and are then propagated to projections.
- A projection mismatch is drift to reconcile, not authority to overwrite the
  YAML source.

## Evidence model

- Planning-source status records whether an input is verified, partially
  verified, probable, an assumption, or unresolved.
- Delivery-evidence status records whether required work evidence is planned,
  available, collected, validated, accepted, blocked, or unresolved.
- Framework proof levels describe the reference implementation only:
  `concept`, `synthetic`, `contract_tested`, `live_readback`, or `closed_loop`.
- A framework proof level does not prove that an assessment deliverable exists
  for a particular engagement. Delivery evidence and framework proof remain
  separate.
- Unknown, stale, unmatched, conflicting, inferred, and blocked evidence stays
  visible; projections must not silently promote it to verified fact.

## Jira boundary

Jira is a collaboration surface. The v2 backlog supplies the planning ID,
summary, parent relationship, labels, component, and fix-version intent for an
authorized projection. Creating or changing Jira issues is a separate external
action. Jira comments, workflow states, and keys do not supersede the YAML
backlog, and public template content must not imply that a live Jira projection
has occurred.

## Reporting contract

- `RC-BIWEEKLY` produces one formal report every two weeks; `RC-PHASE-REVIEW`
  governs findings and deliverable review at each phase boundary.
- `biweekly-status-report.v1.schema.json` defines the immutable report contract,
  and `biweekly-status-report.synthetic.yaml` is a public synthetic fixture.
- Every report pins the backlog schema and SHA-256 digest used for that period so
  later planning changes cannot silently rewrite its basis.
- An accepted report is not edited in place. A correction receives a new report
  ID and names the accepted report in `supersedesReportId`.
- Report status and delivery-evidence status are projections of supported state;
  they do not create scope, acceptance, or remediation authority.

## Privacy boundary

The public v2 backlog and its projections contain templates only. They must not
contain employer or customer identifiers, actual engagement dates, environment
or system names, findings, source locators, received documents, credentials,
raw evidence, or tenant captures. A private engagement plan may instantiate the
template in a separate protected location; it must never be copied wholesale
into this public repository.

## Legacy migration

`backlog.v1.yaml` and `project-backlog.v1.schema.json` are immutable legacy
references. They are not authoritative for new work. The complete disposition
record in [migrations/backlog.v1-to-v2.yaml](migrations/backlog.v1-to-v2.yaml)
maps every v1 epic, feature, and story to v2 work, a future appendix, deferral,
merge, or explicit exclusion. See [migrations/README.md](migrations/README.md)
for usage notes.

Authored planning content is CC BY 4.0. JSON Schemas are MIT-licensed.
