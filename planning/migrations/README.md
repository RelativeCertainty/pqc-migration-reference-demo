# Backlog migrations

`backlog.v1-to-v2.yaml` is the complete, employer-neutral disposition record
for replacing the original 12-week reference backlog with the two-phase
assessment backlog.

The manifest preserves every v1 epic, feature, and story exactly once. A
`targetRef` is a stable planning identifier, not a Jira key. Items assigned to
`FUT-*` are optional appendices and do not enter committed work unless they are
separately approved. An `excluded` item has no target and records why it is
outside the assessment boundary.

The v1 source remains immutable. The migration manifest explains lineage; it
does not make the public reference backlog or an issue tracker authoritative
over the v2 planning source.
