# Discovery and Evidence Intake — first-slice operator guide

8 September 2026. Private development guide. Synthetic information only.

## Start here

Open [Discovery and Evidence Intake](http://127.0.0.1:18475/#intake) on this Linux host.
This candidate is separate from the older applications on ports 18473 and 18474.
It does not replace their application files or state.

The purpose is to answer a practical question: **Which systems and functions can
supply the information for this assessment, what have they told us, and what can
the report responsibly conclude?**

The first slice connects these actions:

```text
Create a focused request with software examples
→ identify separate deployments and evidence sources
→ save a useful, possibly partial, response in the web form or Excel
→ hand the response to the coordinator and technical reviewer
→ preserve unknowns and explain their report consequence
→ separately admit qualified synthetic technical observations when gates permit
```

A response is not a verified inventory. A returned questionnaire is not a closed
assessment. A reviewed limitation is not evidence that cryptographic exposure is
low. Each screen explains what changed and who acts next.

## Review the worked example

The Chrome engineering walkthrough created
[Synthetic intake usability walkthrough — engineering test](http://127.0.0.1:18475/#intake?assessment=assessment-c676e1be26cf4af58ffccdf38239d0dc).
It contains two separately identified NGINX deployments, seven saved routing
answers, a contributor handoff and a synthetic factual review with limitations.
The west deployment's ownership and evidence route remain unknown. No technical
observations or formal gate approvals were added to this example.

As **Analyst**, open that assessment and read the report consequence below the
request. The displayed ownership, product and evidence-location responses are
attributed statements, not normalized facts or approved access routes. To inspect
editing safeguards, change an answer without saving: navigation and Excel
operations pause. **Discard unsaved web edits** restores the saved answer without
altering its review. Saving a changed response instead returns it to review.

**Open Phase 1 report preparation →** opens stage 4 of the same assessment.
The example intentionally lacks the objective and handling basis needed to
generate a report. A generation attempt explains the missing stage-1 input;
formal deliverable acceptance also remains blocked. **Return to Discovery &
intake →** returns to the source request journey. This is an engineering example
for your review, not your recorded acceptance or an enterprise deliverable.

## First walkthrough: two deployments and one useful unknown

1. On the login screen, leave **Analyst** selected. Use the published synthetic
   demo password `synthetic-demo-only` and select **Open workspace**. Never enter
   a real enterprise password or customer data here.
2. In **Discovery / intake**, choose an assessment. If there are none, follow the
   link to **Guided assessment**, enter a clearly synthetic name and select
   **Start assessment →**. Use **Return to Discovery & intake →** to continue
   the request journey. A new assessment has no accepted gates or admitted
   evidence.
3. Expand **Create a focused source request**. Name it “Synthetic portal
   deployments and evidence routes.” Choose the traffic-termination software
   family and **Source contributor 1**. Select **Create request—not send an
   email**. Only families inside the current assessment boundary are offered.
4. Read the request's purpose and software-recognition examples. These examples
   help identify the software class; they do not assert a the example enterprise product choice.
5. Sign out, choose **Source contributor 1** in the login selector and sign in
   with the same demonstration password. Open **My requests** and choose the
   assigned assessment. Contributor 2 cannot read or change this request.
6. Expand **Add a deployment or evidence source**. Add “Synthetic portal east”
   as a system being assessed, product “NGINX,” environment “test-east.” Add
   “Synthetic portal west” separately, with the same product and “test-west.”
   Optional product and environment details may remain unknown. Matching product
   names never merge the two system identities.
7. Under **Share what you know**, record a shared responsible function, such as
   “Synthetic application services.” State where an existing configuration export
   might be held. Open the specific answers for the west deployment; enter
   “I do not know” for its owner and refer it to “Synthetic regional platform
   function.” Record the missing route as a limitation.
8. Select **Save partial response**. The receipt says this is a draft. The report
   consequence separates the reported owner from the absence of technical
   observations. Nothing has been emailed, collected from a vendor or approved.
9. Select **Check response before handoff**, inspect the saved-response summary,
   then **Confirm handoff to coordinator**. The status now says the response is
   with the coordinator/reviewer. It does not say every question was answered.
10. Sign out and sign in as **Technical reviewer**. Reopen the same assessment and
    request. In **Factual review and next handoff**, choose **Usable with a
    recorded limitation**, or return it for clarification. Explain what the
    response supports, what remains unknown and the next responsible function.
    Check the determination, then record it. This synthetic demonstration action
    is not an owner product-validation verdict or enterprise acceptance.
11. Read **What this intake contributes to the report**. It presents conclusions,
    limits and next decisions. Both deployments remain distinct. Ownership is
    attributed testimony. The west-source gap remains visible rather than
    becoming an invented fact or a completion percentage.

Use **Sign out** when switching roles. Tabs in the same browser share a session;
opening another tab does not create an independent identity. Older bookmarked
links that are not assigned to a contributor now explain the access problem and
offer a return to that contributor's assignments.

## Excel is another entry surface, not an approval channel

1. As the assigned contributor or assessment lead, save the web answers first.
   Unsaved web answers pause Excel export/import, adding systems and the app's
   workspace/navigation controls. Choose **Save partial response** or
   **Discard unsaved web edits** explicitly; there is no silent autosave.
2. Select **Prepare Excel questionnaire**, then **Download prepared Excel file**.
   The app retains the exact export, question identities and answer baseline.
   Preparing or downloading it does not send an email.
3. Keep the generated layout. Enter literal text in the response column; do not
   add formulas, macros, sheets or approval instructions. This slice accepts only
   its generated questionnaire format, not the old RFI spreadsheets.
4. Choose the returned `.xlsx` under **Preview a returned questionnaire**. The
   maximum compressed upload is 1 MiB. Preview does not change any answers.
5. Review the original exported answer, current web answer and returned answer.
   Resolve competing edits explicitly. Blank returned cells preserve the current
   answer. Import review offers an explicit clear for changed or conflicting rows;
   unchanged rows are hidden. To erase an answer preserved by a blank return,
   clear that answer in the web form and save it deliberately. An unchanged old
   answer cannot overwrite a newer web answer.
6. Select **Apply reviewed changes only**. This saves a draft, not a submitted or
   approved response. Check and hand off when ready. Imported authorship remains
   unverified; the signed-in importer and intended recipient are kept distinct.

If the request changes while a preview is open, reload and preview the file
again. If its family leaves scope, historical responses and existing exports
remain readable, but new edits, exports, imports, review and admission stop until
the assessment lead explicitly restores the relevant scope.

The OpenXML structural tests and the LibreOffice open/save/re-import roundtrip
passed. Literal text, leading zeros and stable question identities were preserved.
These checks do not establish Microsoft Excel desktop qualification. Do not use a spreadsheet's
“approved” text as an authenticated decision.

Do not manually replace the URL or use browser history to switch requests while
editing. Those browser actions are not covered by the in-app navigation guard.
Reload/close produces a browser unsaved-work warning where supported.

## Technical evidence and actual report inputs

The first admitted raw format is the bounded synthetic TLS reference page at
`integrations/pqc/reference_assessment/tls.page.json`. It is not an F5, NGINX,
ServiceNow or other vendor-export adapter.

1. Add an **Evidence source**, such as “Synthetic configuration observer,” and
   link it to the particular assessed deployment. An evidence-producing system
   is not automatically the system about which its records speak.
2. In the evidence section, select the subject deployment and evidence source,
   and stage the reference JSON. Staging records custody and source attribution;
   it does not add admitted assets or claim permission to collect enterprise data.
   The staged card displays identities, count and file reference—not individual
   observation values or their evidence basis. Inspect the operator-provided
   synthetic fixture itself before considering admission; this screen is not a
   full technical-content review surface.
3. Admission remains blocked until the existing G00 and P1-G01 requirements and
   their designated decisions are satisfied for this assessment. Follow the
   **Guided assessment** gate screens to review the exact outstanding requirements.
   Intake responses do not silently satisfy the separate access register or
   authorize source access. The assessment lead owns that register and admission.
4. Once eligible, the assessment lead may admit the synthetic batch. The admitted
   observations then appear in assessment-scoped asset search/detail and report
   inputs. Staged-only records do not.
5. Inspect key establishment and certificate authentication separately. A supplied
   `X25519MLKEM768` value does not turn a classical certificate signature into a
   post-quantum signature. The source's stated evidence basis is retained, but this
   import does not independently exercise the endpoint.
6. As the assessment lead, select **Open Phase 1 report preparation →** below
   the intake preview. This opens Guided assessment, stage 4, where the report
   controls show their unmet prerequisites. Use the guided assessment's report
   generation and review controls for an immutable Phase 1 or Phase 2 document.
   New documents include the intake conclusions, limitations and selected
   evidence in their frozen inputs. New
   answers cannot rewrite an older report. Phase 2 still selects an explicit
   accepted-or-qualified Phase 1 package; this preview does not grant reliance.

The current TLS format has no observation timestamp, and its application and
certificate references are not independently resolved by this new intake slice.
Those limitations remain explicit. Admission does not automatically create a
reviewed risk scenario, migration recommendation or verified completion.

## What is implemented, and what is deliberately next

Implemented in this development candidate:

- C#-owned transactional requests, distinct systems, attribution, review,
  server-bound Excel reconciliation, receipts and report input history.
- Two isolated synthetic contributor assignments plus lead/reviewer roles.
- All ten estate areas and 27 runtime source families remain represented.
- An explicit crosswalk for the different 27-entry questionnaire catalog,
  including partial and unresolved mappings. Numbers and names are not used as
  an automatic identity match.
- A shared first-routing questionnaire with product-recognition examples.
- One raw synthetic TLS intake format, distinct source/subject identities,
  gated admission and connected asset/report readback.

Not yet implemented or claimed:

- All legacy form layouts, all product-specific questions or all raw vendor
  import formats. The crosswalk is a reviewed engineering artifact, not a live
  legacy import service. Two runtime families remain explicitly unmapped.
- Full multi-source identity reconciliation or a qualified commercial adapter.
- An automatic transfer of every intake answer into every legacy gate field.
- Enterprise authentication, SQL Server persistence, arbitrary confidential
  uploads, public response links, email delivery, ticket submission or migration.
- Production readiness, completed WCAG AA verification, independent owner
  acceptance or native Microsoft Office compatibility certification.

The first slice is bounded to 20 requests and 80 systems per assessment, at most
8 systems per request, 25 exports, 25 import previews and 20 evidence batches.
Answers are at most 512 characters. A TLS batch is at most 32 KiB / 32 records.
The snapshot limit is 2 MiB; SQLite has a page-count ceiling. Limits stop writes
rather than deleting old immutable history. There is no automatic retention or
archival policy for these snapshots yet.

## Candidate operation and recovery

The candidate has its own fresh synthetic fixture, release and SQLite state:

`artifacts/pqc-enterprise-demo/intake-review-20260908-Rq8mET/`

To restart it after its two-hour runtime expires, from the repository root:

```bash
.venv/security-ci/bin/python scripts/run_pqc_enterprise_demo.py \
  --release-dir artifacts/pqc-enterprise-demo/intake-review-20260908-Rq8mET/release-v4 \
  --fixture artifacts/pqc-enterprise-demo/intake-review-20260908-Rq8mET/input/synthetic-input.json \
  --data-dir artifacts/pqc-enterprise-demo/intake-review-20260908-Rq8mET/state \
  --port 18475
```

Keep the foreground terminal open. Ctrl+C stops only that launch. If another
demo holds the launcher lock or the port, do not kill it; coordinate the review
slot. The launcher requires at least 3 GiB available memory and 2 GiB free disk.

The application is capped at one CPU / 1 GiB RAM / no additional swap. A single
workbook parser is a separate, temporary unit capped at one CPU / 512 MiB RAM /
no additional swap, with no network and a 30-second deadline. Combined app/parser
ceilings are therefore 1.5 GiB and two CPU equivalents during parsing, not 1 GiB
total. Failed cleanup closes the parser lane until application restart rather
than admitting overlapping parser work. The parser is a bounded managed reader,
not a generally qualified hostile-file sandbox with a minimal filesystem view.

State and input paths are owner-only. There is no enterprise encryption/key
management or public HTTPS deployment in this candidate. Do not share its SQLite
files, fixture custody directories or loopback URL as an enterprise service.

Rollback means returning to an older application together with its own preserved
state. Never point an older build at this candidate database to simulate rollback.
The isolated HTTP tests exercise exact report/export preservation through restart
and backup/restore. They do not test restoration of an owner production database.

## Owner review requested, not recorded

Affected behaviors are R2 for the questionnaire-to-report workflow and R3 for
assignment authorization, workbook reconciliation/admission boundaries and
contributor restriction of legacy routes. These require targeted owner validation
before an affected production activation or readiness claim.

Please judge the practical outcome: can you tell why this request exists, provide
a partial answer, identify who acts next, and see what the report may or may not
conclude? Record an issue if returning a questionnaire looks like completion of
the assessment. Automated persona interactions and tests do not record your
`works`, `issue_found` or `blocked` outcome.

The resumed Chrome walkthrough inspected the landing screen and created a fresh
synthetic assessment. It found a real request-creation defect: the frontend
omitted a required nullable command field. Release v3 sends that field explicitly
for both intake and assessment commands. It also adds unsaved-answer safeguards,
a return-to-intake route, clearer review responsibilities and a report-preparation
link. Ten focused HTTP tests, frontend typechecking and all 58 frontend tests
passed. An earlier transient failure in an untouched graph test passed on focused
and full reruns without changing that test.

After the extension panel was dismissed, the release-v3 Chrome walkthrough
created the request, entered two separate deployments, saved a partial response,
handed it off and recorded a synthetic reviewer limitation. It verified disabled
navigation/Excel controls during unsaved edits, explicit discard without a state
revision change, the Phase 1 preparation link, the missing-objective explanation
and the return link. No formal gate approval, technical-evidence admission or
accepted report was generated in that fresh example.

The walkthrough also found two wording defects: free-text unknowns looked like
established owners/routes, and a completed review still displayed a pending-handoff
prompt. Release v4 corrects both and makes the staged-file metadata-only review
limitation explicit. Its backend build passed with no warnings/errors; 39 combined
intake/existing application HTTP tests and all 62 frontend tests passed, as did
typechecking and Worker architecture conformance. The candidate was backed up to
`pre-v4-backup` and restarted with its same synthetic state. No earlier release or
backup was overwritten.

Chrome was blocked by an open extension panel during sign-in to v4, so final-copy
browser readback remains pending. The successful end-to-end interaction above was
on v3; automated v4 checks are not being substituted for that last readback.
Desktop screenshots of the form and report preview showed no obvious border
collisions or overlapping controls. Full responsive, keyboard and
assistive-technology testing remains outstanding. No automated persona interaction
or engineering check is your acceptance.
