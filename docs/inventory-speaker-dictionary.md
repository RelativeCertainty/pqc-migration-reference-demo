# Page 04 Inventory — Speaker Dictionary

Use this only as a lookup during rehearsal or questions. The read-aloud script
defines the essential terms at first use, and Page 04 displays the same short
definitions beside the table.

All records and feed observations in this demo are synthetic.

## The three questions Page 04 answers

1. **What are we talking about?** The asset, application, business service, and
   cryptography in use.
2. **Who can change it, and why?** The change-control class identifies who can
   act; the concern type identifies what needs attention.
3. **How much should we trust the combined record?** Evidence-match status,
   source references, freshness, confidence, and review reasons explain that.

## Evidence-matching terms

**Seed asset**
One distinct system from the initial inventory. This demo has ten synthetic
seed assets.

**Seed observation**
One issue classification expanded from a seed asset. A single seed asset may
have several crypto concerns, so ten assets become 36 seed observations. That
does not mean the source inventory had 36 rows.

**Enrichment observation**
One source-scoped modeled finding or context record from ExtraHop,
vulnerability management, PKI, SAST, or CMDB. It retains its own source
identity rather than being overwritten by another feed.

**Candidate key**
The normalized join value used to propose that observations describe the same
asset. A candidate key creates a reviewable grouping; it is not proof that the
grouping is correct.

**Canonical record**
The reviewable combined record produced by deterministic rules after grouping
and exact deduplication. “Canonical” means the shape is standardized. It does
not mean the record is automatically authoritative, complete, or approved.

**Correlated**
The initial inventory and at least one enrichment feed point to the same
candidate, and the retained observations do not disagree on the governed
identity fields. Correlated does not mean complete or correct.

**Unmatched**
One side of the join is missing. Either a seed asset has no enrichment
observation, or an enrichment observation points to a candidate that is absent
from the seed inventory. It is unmatched to the seed/enrichment join—not
“unmatched to reality,” and not proof that the asset does not exist.

**Conflict**
Observations grouped under the same candidate key disagree on a governed field.
In this v1 demo those fields are display name and change-control class. The
system exposes the disagreement and does not choose a winner. Conflict does not
mean every source is wrong.

**Exact duplicate**
The same feed and native source record submitted identical content more than
once. The duplicate is counted for transparency but is not retained twice as
independent evidence.

**Evidence reference**
A bounded pointer to one retained source observation: observation identifier,
feed, and assessment. It supplies traceability without copying a raw source
payload into the combined record.

**Review queue**
Candidate records that still need a person because of a conflict, missing
counterpart, unknown freshness, unresolved field, or low-confidence assumption.
Queue membership is not an incident or a failure; it is a visible decision
obligation.

**Source-reconciliation queue**
A separate quarantine for two or more different submissions that claim the
same feed-native identity. All disputed variants are excluded from the
canonical record until reviewed.

**Freshness unknown**
No retained observation contains a real runtime collection timestamp. The
synthetic fixtures intentionally produce this state. It means “not observed,”
not “recent” and not “expired.”

## Summary metrics

**Seed systems**
Distinct fictional systems supplied by the initial inventory: 10.

**Seed issue observations**
One synthetic observation per issue category assigned to a seed system: 36.
These are expanded classifications, not 36 original inventory rows.

**Enrichment submissions**
Normalized synthetic observations submitted by the five modeled enrichment
adapters before duplicate handling: 12. “Submission” does not mean a raw source
payload was stored.

**Retained enrichment**
Synthetic non-seed observation references retained after exact duplicate
handling: 11.

**Exact replay submissions**
Identical content resubmitted by the same feed under the same native source
identity: 1. Cross-feed corroboration is not treated as a duplicate.

**Candidates for review**
Combined candidate records that require a person: 11. Every current candidate
requires review because the fixture observations are illustrative assumptions
without runtime collection timestamps; the number does not mean 11 reviews
were completed.

## Filters

**Illustrative environment** filters the fictional deployment context.

**Illustrative migration stage** filters the fixture-authored program stage;
no workflow is executing.

**Illustrative priority** filters a fixture-authored sequencing label; it is
not calculated by Page 05.

**System owner** filters the fictional technical owner and is distinct from
the change-route role and evidence-review owner.

**Change-control class** filters who controls the implementation path:
first-party source code, an off-the-shelf product, or a third-party/SaaS
provider.

## Table columns

**Seed system / application — Fictional seed identity**
The synthetic asset name, application name, and stable demo identifier.

**Change route / concern — Who changes it / why it matters**
The change-control class routes work to a source-code team, an OTS/COTS product
owner, or a third-party/SaaS owner. Concern labels identify the crypto issue,
such as TLS, certificate trust, source-code crypto use, or vendor readiness.

**Seed-to-enrichment match — How synthetic feeds relate to the seed**
The precise matched, seed-only, enrichment-only, or identity/classification
conflict status; number of retained synthetic observation references; and
number of exact replay submissions ignored.

**Declared crypto use — Fixture algorithm / protocol / purpose**
The fixture-authored algorithm, protocol, and business or technical purpose for
which the seed record says cryptography is used. It was not runtime-observed.

**Illustrative business context — Fixture service / owner / exposure**
The fictional business service, system owner, environment, and exposure.

**Illustrative planning readiness — No implemented readiness rubric**
The fixture-authored readiness state, crypto-agility rating, dependency count,
and management model. No readiness rubric or dependency graph produced it.

**Illustrative priority — Fixture-authored urgency**
The synthetic sequencing label: Urgent, High, Moderate, or Low. It is separate
from Page 05's interactive model and is not an automated risk decision.

**Migration stage / pattern — Proposed, not executed**
The fixture-authored lifecycle status and proposed migration approach. It does
not prove that work was performed or validated.

**Seed + fusion details — Authority / gaps / review**
Opens four visibly separated groups: synthetic seed assertions, the derived
fusion result, the seed evidence envelope, and known proof gaps.

## Worked examples in this fixture

**Conflict — Internal Java Payment Service / Ledger Relay**
Several observations use the same candidate key. The initial inventory calls it
an internally controlled source-code system, while one modeled SAST observation
uses a different display name and classifies it as OTS/COTS. The UI therefore
shows Conflict and names `displayName` and `estateClass` as the fields that
disagree. It does not silently pick the SAST or seed value as universally true.

**Unmatched — orphan-service-77**
A modeled CMDB observation supplies a candidate key that is absent from the ten
seed assets. It is unmatched to the initial inventory. A person must determine
whether it is a legitimate new asset, a bad identifier, or a relationship that
needs a different join.

**Exact duplicate — modeled vulnerability observation**
One modeled vulnerability-manager record is submitted twice with identical
content and the same native reference. The page reports one exact duplicate and
retains only one evidence reference for that submission.

## Safe one-sentence explanation

> This page keeps the initial inventory and every modeled source observation
> distinct, proposes matches through governed keys, removes only exact
> duplicates, and sends missing or disagreeing evidence to a person instead of
> silently manufacturing a source of truth.
