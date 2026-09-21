#!/usr/bin/env python3
"""Create a local, explicitly source-checked operator guide; never operate the app.

The browser-proof status is kept explicit. This produces Markdown and its
readable HTML copy, not simulated screenshots or an assertion of user acceptance.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def build(package: Path, port: int):
    package = package.resolve(strict=True)
    if not package.is_relative_to(ROOT / "artifacts/pqc-enterprise-demo"):
        raise ValueError("isolated_candidate_required")
    os.umask(0o077)
    origin = f"http://127.0.0.1:{port}"
    guide = f"""# PQC assessment: operator field guide

All-domain synthetic development candidate · 16 September 2026

## Read this first

Your job is to turn supplied information into a defensible assessment: identify what was reported, examine what the records establish, retain disagreements and unknowns, and explain the resulting recommendations. Your job is not to make every status green.

Northstar Services and all named people, functions, business statements and source records in this package are fictional. Software names are recognition examples, not evidence of installations or qualified vendor connectors. A simulated gate decision is not enterprise acceptance or the founder-owner's product observation.

These instructions use the current interface's exact labels. The validation record alongside this guide separately states whether the browser walkthrough, video, report rendering and owner review were completed. Source inspection and API tests alone are not a filmed operator walkthrough.

## 1. Open the isolated candidate

1. Open the terminal startup command in `START_AND_RESUME.readable.html` in this package. Run that command and keep its terminal open. Do not start another candidate or remove a launcher lock.
2. On this same Linux host, open [{origin}/]({origin}/). This is host-only: 127.0.0.1 on somebody else's computer will not open your app.
3. At the existing login screen choose Analyst. Enter the displayed synthetic password `synthetic-demo-only`, then click **Open workspace**. Never use an enterprise password here.
4. Use the fresh-assessment link in the package index for your own rehearsal. Use the completed-example link only to inspect the API-rehearsed example. They have different assessment IDs and histories.
5. If you are starting from nothing, click **Guided assessment** in the left navigation, enter **Assessment name**, then click **Start assessment →**. Do not select **Create a separate worked example** if your goal is to practice every handoff yourself.

To change roles later: save or discard visible edits, click **Sign out** at the bottom of the left sidebar, and use **Or sign in as a contributing / reviewing persona** on the login screen. Its exact options include **Technical reviewer**, **Assessment sponsor**, **Information owner**, **Risk lead**, and **Business reviewer**. To return to the lead, select the **Analyst** radio option. Re-enter the synthetic password and click **Open workspace**, then reopen the same assessment link. Changing persona is a deliberate simulation of different people, not evidence of independent enterprise decisions.

The application runs with the existing one-CPU, 1-GiB, no-added-swap limit. If startup refuses headroom or a lock, stop here; do not stop another service to make room. The reports and forms remain readable offline.

## 2. Set the boundary and establish the source routes

1. In **Guided assessment**, click the **Establish the assessment** stage tile (01). Fill **Assessment objective**, **Current cycle goal**, **Evidence-handling route**, **Assessment method / agreed approach**, and **Next review date** using the fictional scenario. Choose the relevant source families and **Expected evidence depth**, then click **Save scope draft**. For the full all-domain exercise, all 27 families remain included; this is scenario scope, not enterprise coverage.
2. Under **Review gates for this stage**, read G00's unmet requirements. When eligible, the lead clicks **Submit this gate for review**.
3. Sign out. At login choose **Assessment sponsor**; sign in and return to this same assessment and stage. Under **Review this submitted gate**, set **Decision requested for this exact revision**. Supply **Evidence-based decision rationale**, **Limitation, consequence and follow-up owner** if qualified, and **Follow-up review date**. Click **Check decision before recording**, read the confirmation, then **Confirm and record this decision**.
4. Repeat that decision as the separate Information owner persona. One principal cannot substitute for both required roles. Every decision in this exercise is simulated.
5. Sign in as Analyst and click **Establish sources and obtain evidence** (02). Choose a family under **Identify teams and information sources**. Set **What can you establish now?**, then complete **Person or function supplying this answer**, **What is known, missing, or blocked?**, and **Expected follow-up date**. An identified route additionally needs **System of record or existing reference**, **Actual product / edition / version**, **Responsible function**, and **Approved read-only evidence route**. Use fictional references and dates only. Click **Save source response** and repeat for selected families. This coordinator register is distinct from the contributor's five short questions.
6. Submit P1-G01 once its displayed requirements are met. Record the lead and Sponsor decisions using the same check/confirm sequence. Do not click **Admit this source’s synthetic sample**: that is the older reference path and is not used in this walkthrough.

Result: the bounded handling and collection prerequisites are recorded. This has not verified any cryptography or approved a migration.

## 3. Receive one complete form, then the remaining returns

The package's `inputs/forms/` folders contain the actual completed five-question workbooks. There are 27 primary completed forms, plus a traffic duplicate and revised return. They use the operational email-return edition, not fabricated app-export bindings.

1. Open **Assessment work**, use **Assessment for this work** to choose the intended assessment, then click the relevant case's **Open this task** or **Read work and blocking reason**. The packaged fresh walkthrough already has one traffic-termination request; use that request first. To add the other 26 classes, click **Request catalog and individual Excel forms**, use **Assign a short discovery request**, complete **Request title**, **Software class / source family**, and **Assigned respondent**, then **Create five-question request** for each missing class. Do not create a full collection in that seeded assessment: it would create another traffic request. For a completely new assessment with no requests, instead use **Prepare a new web-form collection**, choose **Collection recipient**, click **Review collection creation**, check assessment and recipient, then **Create the 27 draft web forms**. Reuse an existing collection when present. Return using **Assessment work** in the sidebar.
2. Open **Returned information**. Confirm the displayed assessment, request and software class before choosing a file.
3. In **Completed operational questionnaire (.xlsx, maximum 1 MiB)** choose `traffic-termination-synthetic-completed.xlsx` from `inputs/forms/area-03/`. Tick **I confirm this return belongs to …** only after checking the displayed request and assessment, then click **Receive and preview information**.
4. Read the declared respondent/team and authenticated receiver separately. Expand **All returned answers, referrals and references**. Review every row under **Products and deployments supplied in this return**.
5. For each **Retain which answer for DQ-…?** control, deliberately choose the returned or current answer. Enter **Receipt review note**, then click **Record reviewed offline response**. A useful referral, unknown or partial answer is still a contribution.
6. Receive `traffic-termination-synthetic-duplicate.xlsx`. The application should report that the exact file was already received, with no second receipt or artifact.
7. Receive `traffic-termination-synthetic-revised.xlsx`, repeating the file selection and confirmation checkbox. Compare prior, current and returned values. Choose each **Retain which answer for DQ-…?**, enter a new **Receipt review note**, and click **Record reviewed offline response**. Do not choose the favorable value merely to remove a conflict; blank cells must not silently erase known information.
8. Use **Continue another source case** to process each of the other 26 primary files under its matching class. Do not infer the mapping from catalog position or filename alone; the imported definition identifiers are authoritative.

Result: attributed information is received and reviewed. It is not technical qualification, collection authorization or assessment acceptance.

## 4. Reconcile products and deployments

1. Open **Systems and sources**. In **Reported product or deployment**, select the original gateway-east row. Read its row number, reference, environment and notes—not just the F5 product name.
2. If the supplied context supports it, set **Identity determination** to **This is a distinct assessed system**. Enter **Reviewed system label** and **Identity rationale and evidence basis**. Add the reviewed service/team where known. Click **Record identity determination**.
3. Select the second gateway-east row, whose reference identifies the suspected duplicate. Choose **This refers to the same system as another record**, then select the original east identity in **Same system as**. Enter the label and rationale and record the determination.
4. If east is unavailable as a target, do not select west to get past the screen. Click **Discard identity edits**, establish the original east row first, then return to the duplicate. Unreviewed rows are displayed as unavailable targets with a reason.
5. Record gateway-west and edge-third separately. Keep genuinely uncertain relationships **Identity remains unresolved**. For revised-return rows, compare with the existing identities instead of creating another deployment automatically.

Result: original assertions remain intact, while reviewed relationships connect them. A later correction appends history and triggers targeted re-review; it does not rewrite old report bytes.

## 5. Examine the source records and preserve disagreements

1. As Analyst, open the case's **Technical records** section. Under **Stage a bounded source capture**, choose **Reviewed return deployment for this capture**, then select its matching JSON from `inputs/bundles/` using **Controlled synthetic source JSON (maximum 32 KiB)**. The source-to-deployment mapping is retained in `inputs/scenario.json`; do not associate a record with a deployment merely because its filename looks similar.
2. Click **Stage source capture for review**. The registered source file must be one of the exact prepared fixtures. This is not an arbitrary vendor-import facility or enterprise trust store. Do not use the separate historical **Stage controlled synthetic TLS records** subsection for this registered-bundle exercise.
3. Sign out, sign in as Technical reviewer, and reopen the same case. Select **Technical bundle to review or admit** when more than one bundle is present.
4. Read each source's native ID, observed and collected dates, evidence basis, nested facts and limitations. For every **Record determination for …**, state whether the record supports the claim, conflicts with other information, or cannot establish it. Complete every **Record rationale for …**.
5. Fill **Technical review rationale for …**. Click **Review qualified determination**, check the consequence, then **Confirm qualified determination**. Alternatively click **Request technical clarification**, then **Confirm clarification request** where the records cannot be qualified. An unchanged rejected capture cannot simply be admitted; a correction becomes a new linked capture.
6. Sign in as Analyst again, reopen **Technical records**, and select the exact qualified bundle in **Technical bundle to review or admit** if that selector is present. Click **Review lead admission**, then **Confirm admission to assessment inputs**. Do not skip this handoff or let the stager act as independent reviewer.
7. Repeat for the other registered bundles. Preserve the east configured-hybrid versus modeled-classical observation as a conflict. Preserve edge-third's blocked source route as an unexamined limitation; a qualified bundle does not erase either condition.

Result: only the specifically reviewed and admitted records become assessment inputs. Configuration is not negotiated behavior, vendor testimony is not independent verification, and hybrid key establishment does not make certificate authentication post-quantum.

## 6. Record an understandable report consequence

1. Open the case's **Assessment consequence** section. Select **Affected deployment for this conclusion** and **Cryptographic purpose being assessed**. Keep key establishment and authentication conclusions separate. If a conclusion is already present, use **Conclusion to review or revise** to choose it or **Start a separate conclusion**.
2. Under **Evidence supporting or contradicting this conclusion**, set each relevant **Use record … in this conclusion** to **Supporting evidence** or **Contradicting evidence / unresolved difference**. Leave unrelated records **Not relied upon**. Preserve contradictory references rather than hiding them.
3. Complete **Phase 1 conclusion supported by this case**, **Material limitation and what cannot be concluded**, **Next decision needed**, and **Next responsible function**. Choose **Evidence confidence for this conclusion**. Add **Conditional Phase 2 business consequence** and **Confidentiality or trust lifetime and its basis** only when attributed scenario material supports them. Keep confidence, exposure, impact and readiness separate.
4. Click **Preview exact report consequence**. Read **Phase 1 will explain**, **Phase 2 may rely on**, **Remaining limitations**, and **Next decision**.
5. If the text is supported, click **Record this reviewed consequence**. If inputs changed, refresh the preview; a stale preview cannot be committed.
6. Repeat across the ten domains. A context, governance or blocked-source contribution can legitimately be a recommendation or limitation rather than a manufactured cryptographic vulnerability.

Result: a versioned report contribution—not an accepted report. Raw workbook answers and hashes belong in its supporting records, not in place of conclusions.

## 7. Generate and review the Phase 1 handoff

1. Click **Continue technical package review**. For each package fill **What does the evidence establish?** and **Unresolved limitations and consequences**. Click **Submit package for technical review**.
2. As Technical reviewer, use **Technical reviewer disposition**, **Check decision before recording**, and **Confirm and record this decision** for each submitted package. Qualified acceptance keeps the limitations visible.
3. As Analyst, submit P1-G02 under **Review gates for this stage**. Record its lead and Technical reviewer decisions separately. In **Guided assessment**, click the **Deliver Phase 1** tile (04), or **Next: Deliver Phase 1** below the gate. The separate **Phase 1 report and handoff** shortcut is available from a case's Assessment consequence section.
4. As Analyst, click **Generate Phase 1 draft**, then **Read report →**. Check that the report describes reported, corroborated, disputed and unexamined information. The traffic cohort is two of three declared deployments examined—not an enterprise completeness percentage.
5. Close the reader with **Close report preview**, click **Guided assessment**, and select **Deliver Phase 1** (04). In **Exact report to submit for this gate**, choose the report ID you read. Click **Submit this gate for review** for P1-G03. Record the lead and Assessment sponsor decisions for these exact immutable bytes.

Result: a qualified or accepted synthetic Phase 1 basis. A newer draft cannot silently replace it, and the historical report is never rewritten by a later questionnaire.

## 8. Develop substantive Phase 2 analysis

1. Sign in as **Risk lead**. Click **Guided assessment**, then **Establish the analysis basis** (05). Under **Exact Phase 1 basis for this method**, read the selected report identity and use **Read selected Phase 1 basis →** to inspect its qualifications. Close the reader and return to the same stage. If no basis is selected, complete P1-G03 first; do not choose a newer draft as a shortcut. The **Phase 2 method and reliance** shortcut also reaches this stage from a case's Assessment consequence section.
2. Fill **Method name**, **Method and business-impact approach**, **Confidence and uncertainty rules**, and **Prioritization rules**. Click **Save analysis method for review**. Submit P2-G01 and obtain Risk lead and Sponsor dispositions.
3. Click **Assess consequences and recommend action** (06). For each source package enter **Conditional risk scenario**, **Business consequence and what needs confirmation**, **Recommended treatment or next investigation**, and **Rationale tied to the agreed method**. The supplied `inputs/business-context.json` is fictional preparation material, not an automatically approved business statement.
4. Complete **Protected information and affected business service**, **Confidentiality or trust lifetime and basis**, **Business context asserted by**, and **Business statement date**. Enter the distinct compatibility, vendor and operational constraints, responsible function and next decision.
5. Choose **Proposed review priority** and **Evidence confidence** without inventing a numerical risk score. Click **Submit analysis for business review**.
6. Sign in as Business reviewer. Disposition every submitted analysis using the check/confirm sequence. Record any unresolved information lifetime or service consequence as a limitation, not a guessed fact.
7. Submit and disposition P2-G02 with the Risk lead and Business reviewer. Saving Phase 2 business context must not invalidate unchanged Phase 1 facts; changing actual scope, identity or evidence still requires targeted review.

Result: reviewed, attributed business analysis linked to the selected current-state basis. The priorities are demonstration attention categories, not enterprise-approved scoring or predictions about quantum-computer arrival.

## 9. Generate the final report and complete simulated review

1. As Risk lead, click **Guided assessment**, then **Deliver Phase 2** (07). In **Select the exact Phase 1 input report**, explicitly choose the reviewed handoff basis. Other snapshots are unavailable; the server repeats this check. Click **Generate Phase 2 draft**.
2. Click **Read report →**. Check executive decisions, all ten domain contributions, distinct risk scenarios, lifetimes, constraints, accountable next actions, exact Phase 1 basis and provenance appendix.
3. Close the reader using **Close report preview**, return through **Guided assessment** to **Deliver Phase 2** (07), and in **Exact report to submit for this gate** select the Phase 2 report just read. Click **Submit this gate for review** for P2-G03. Record both Risk lead and Assessment sponsor decisions with **Check decision before recording** followed by **Confirm and record this decision**, retaining explicit qualifications.
4. Click **Open assessment report history**, find the exact report, then **Preview report**. Use **Download full HTML** in the reader, or **HTML** beside its history entry. **Download JSON** is the technical supporting export, not the primary reading copy. The companion PDF contains the same frozen report content with its own file hash; it is not separately authored analysis.
5. Verify that the report ID and hash match the package's rehearsal or browser-recording identity. An API-rehearsed report must not be presented as the result of an unperformed filmed walkthrough.

Result: a completed synthetic document and simulated review history. It still does not authorize remediation, adopt a company standard or establish enterprise acceptance.

## If you get stuck

- An unavailable control should name the missing prerequisite or required role. Do not bypass it or use another deployment merely to continue.
- Save or discard visible edits before changing sections. **Discard identity edits**, **Discard consequence edits** and the corresponding receipt/review controls discard only unsaved changes.
- A conflict after another edit requires reload and review, not blind resubmission. **Retry identical operation** reconciles an interrupted request; it is not permission to create another outcome.
- A blocked source remains in the report. A received form, closed task or qualified record is not proof that the assessment is complete.
- A browser download restriction is a separate delivery issue. Do not disable security controls; use the individual local package files while the authorized browser path is investigated.

## Restart, backup and rollback

Stop only this candidate with Ctrl+C in its launcher terminal. After it exits, copy the entire synthetic state directory into a new mode-0700 backup directory, including SQLite sidecars if present. Record the paired release manifest and fixture hash. Never copy an arbitrary live database or point a candidate at owner-operated production state.

Restore a backup into a new private directory and launch the matching immutable release against that copy. Confirm assessment IDs and frozen report hashes before relying on it. Do not run an older application against a newer schema. The earlier application needs its own matching historical state for rollback.

Enterprise identity, approved HTTPS, SQL Server qualification, evidence handling/retention, measured capacity, live integrations and Phase 3/4 migration execution remain outside this increment. Only the owner records product-acceptance outcomes; automation supplies engineering evidence.
"""
    source = package / "Operator_guide.md"
    source.write_text(guide)
    subprocess.run([sys.executable, str(ROOT / "scripts/render_readable_document.py"), str(source)], check=True)
    (package / "operator-guide-status.json").write_text(json.dumps({
        "schemaVersion": "pqc.operator-guide-status.v1", "instructionBasis": "source_checked_control_labels",
        "browserWalkthroughVerified": False, "ownerAcceptance": "not_recorded",
        "docx": "pending_managed_runtime_or_user_approved_existing_toolchain",
        "preset": "compact_reference_guide", "header": "memo_masthead",
    }, indent=2) + "\n")
    print(source.with_suffix(".readable.html"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18477)
    options = parser.parse_args()
    build(options.package, options.port)
