# Guided PQC Assessment Workspace — Operator Guide

For the newer intake candidate on port 18475, start with the
[Discovery and Evidence Intake operator guide](INTAKE_WORKSPACE_OPERATOR.readable.html).
Its contributor personas use assignment-scoped **My requests**. The contributor
instructions below describe the earlier guided candidate on port 18474 and do
not authorize access to legacy assessment commands in the intake build.

Date: 8 September 2026

Status: local synthetic development candidate. This guide describes the implemented workflow; it does not announce a running deployment, successful owner acceptance, or an enterprise-ready product. Use the final engineering handoff for the verified candidate address and outstanding checks.

## What the application is for

The assessment is the main workflow. The dashboard, asset explorer and reports support it.

The application helps an assessment lead establish a bounded question and scope, identify accountable source functions, obtain attributable evidence, review a current-state map, and turn that map into explainable Phase 2 conclusions and next decisions. It also records where organizational routes and evidence are missing.

An unknown is a useful assessment result when it has a stated consequence, accountable next step and review date. It is not evidence that exposure is low or that a team is unwilling to cooperate.

The sequence is:

```text
Define the assessment
→ establish source routes and evidence
→ review the current-state map
→ deliver an exact Phase 1 snapshot
→ establish the Phase 2 input and method
→ review consequences and recommendations
→ deliver an exact Phase 2 snapshot
```

You may look ahead at any stage. Looking ahead is not permission to bypass a prerequisite. The C# application evaluates permissions and gates; a screen being visible does not grant authority.

## Open the right candidate

1. Wait for the final handoff to confirm the candidate is running. The intended review address is `http://127.0.0.1:18474/#assessments`.
2. Open that address in a browser on this Linux host. `127.0.0.1` means the computer running the browser; this is not a company-wide or remotely accessible address.
3. Do not treat the existing application on port `18473` as this candidate. That service is to remain untouched during candidate review.
4. Choose the Analyst role and enter the published synthetic demonstration password, `synthetic-demo-only`. Never enter an enterprise password or actual company data.
5. Select **Open workspace**. Start from **Guided assessment**, not a legacy report or an old bookmarked action filter.

If the candidate is unavailable, stop and ask for its current status. Do not change host services, open firewall ports, bind the app publicly, or replace the existing application to make the demonstration work.

The local candidate uses synthetic identities and an isolated application database. It does not implement enterprise SSO, SQL Server persistence, live enterprise connectors or Phase 3/4 migration execution.

## Choose the right starting point

### First orientation: create a separate worked example

As Analyst, select **Create a separate worked example**.

Each example has its own assessment identifier, persisted answers and history. It uses three selected source profiles from three areas, with a bounded synthetic evidence cohort. The other 24 families remain outside that worked-example cohort. This is not a declaration that those families are absent from, or out of scope for, an actual enterprise.

The example's initial source responses and qualified decisions are scenario-generated. They are visible in **Participants and immutable workflow history**. They are not decisions made by you, an enterprise approver or the founder-owner.

The worked example prepares the first three stages and lets you continue with the Phase 1 draft. It does not pre-accept the Phase 1 or Phase 2 deliverables on your behalf.

### A real test of the guidance: start a fresh assessment

As Analyst, enter a synthetic assessment name and select **Start assessment →**.

A fresh assessment does not begin with approved gates or admitted evidence. Use it to test whether the questions, task guidance, source examples, blocked states and review process are understandable without a prepared scenario.

Creating another assessment never resets the earlier one. Use **All assessments** and reopen the appropriate identifier to resume existing work.

## The eight synthetic personas

Use **Sign out**, then choose the required persona at the login screen. Reopen the same assessment, using its saved address or the assessment list. The identifier in the address distinguishes it from other examples.

These roles demonstrate separate responsibilities; they are not employee assignments or enterprise identity proof.

- **Analyst / assessment lead:** creates an assessment; sets scope; records source responses; admits the fixed sample; submits current-state packages and Phase 1 gates; generates report drafts. Participates in the lead's assigned gate decisions.
- **Source contributor:** records source-route information and submits an evidence-package conclusion. Records who supplied information separately from the authenticated recorder.
- **Technical reviewer:** independently reviews current-state packages and the baseline-validation gate. A submitter cannot independently review their own package.
- **Assessment sponsor:** reviews the designated governance, scope, deliverable and method gates from the sponsor's role.
- **Information owner:** reviews governance and permitted information handling.
- **Risk lead:** supplies the versioned Phase 2 method, submits analysis and Phase 2 gates, and generates report drafts.
- **Business reviewer:** independently reviews the analysis and its business-consequence validation gate.
- **Viewer:** reads assessments and reports; cannot record workflow decisions or generate new records.

Multiple tabs in one browser normally share the same session. For a simple walkthrough, switch personas sequentially. Do not assume a tab retains its former role after another tab signs in differently.

## Stage 1 — Establish the assessment

Question: what are we assessing, and under whose authority?

As Analyst:

1. State the decision the assessment supports, permitted information handling, collection method, cycle goal and review date.
2. Choose the source families included in this bounded cycle. Supply a reason for each family not selected.
3. Set one of three depth profiles for each selected family:
   - Source routing: identify the product, owner and permitted evidence route.
   - Inventory: examine a bounded body of source evidence.
   - Dependency cohort: relate selected uses to their application, service, information and relying-party dependencies.
4. Save the scope. Read the displayed remaining requirements.
5. Submit governance gate `PQC-G00` for review.
6. As Information owner and then Sponsor, inspect the submitted revision and record the corresponding decisions.

A routing answer is not an inventory. A bounded inventory is not a comprehensive enterprise map. A reviewed dependency cohort is not assurance about unexamined environments.

These are planning profiles, not proof-of-completion switches. The candidate admits a fixed family-level synthetic sample. It does not yet provide a service/application/environment cohort selector or prove dependency-cohort completeness. Read planned depth and achieved depth separately; planned dependency-cohort work must remain marked unvalidated.

## Stage 2 — Establish sources and obtain evidence

Question: which systems and functions can supply the facts?

For each selected family, use the product-recognition examples to ask: “What is the authoritative system of record for this class of software here, and which function owns its evidence?” The examples are recognition aids, not approved enterprise product selections.

As Contributor or Analyst, record:

- The response: route identified, unknown, another team needed, or blocked.
- System of record and product context.
- Accountable owner function and permitted read-only evidence route.
- Who supplied the answer, distinct from the signed-in person recording it.
- A concise constraint or response note and next date.

As Analyst, submit scope/source gate `PQC-P1-G01`; the Assessment lead and Sponsor provide its required decisions. Once the displayed prerequisites and route requirements are met, use the sample-admission action to bring that family's bounded fixture evidence into this assessment.

Sample admission reads prepared synthetic records. It does not call a vendor, send an RFI, scan an endpoint, exercise an enterprise credential or establish permission to perform those actions.

Keep two indicators separate: a route can be recorded without usable evidence, and fixture evidence can exist without a live route ever having been exercised. A missing response does not establish unwillingness.

## Stage 3 — Validate the enterprise map

Question: which observations and conclusions can we rely upon?

1. Inspect the selected package and its supporting assets, uses, observations and limitations.
2. As Analyst or Contributor, write a bounded current-state conclusion. Say what the evidence supports and what it does not support.
3. If technical evidence is missing, state that limitation and its consequence instead of inventing a conclusion.
4. Submit the package for technical review.
5. As Technical reviewer, accept its stated position, qualify it with limitations, or request changes. Preserve the rationale and review date.
6. As Analyst, submit baseline gate `PQC-P1-G02`. Assessment lead and Technical reviewer provide the required gate decisions.

Source-reported capability, configured state, observed behavior and independently verified behavior are different evidence claims. For example, a product's support for a hybrid group does not prove that a particular application negotiated it.

## Stage 4 — Deliver Phase 1

Question: is this exact current-state report suitable for the next phase?

1. As Analyst, choose **Generate Phase 1 draft**.
2. Select **Read report →** and inspect the executive position, scope, source enablement, coverage limitations, current-state conclusions and next decisions.
3. Verify that the report contains only this assessment's admitted evidence. A fresh selection must not silently acquire the full fixture inventory.
4. In gate `PQC-P1-G03`, choose the **Exact report to submit for this gate**, then submit it.
5. Assessment lead and Sponsor review that exact report. Use a qualified decision when limitations must remain attached, and identify their consequence, follow-up owner and date.

Report generation and acceptance are separate actions. A report remains an immutable snapshot. Its current review/reliance status is projected from separate decisions; accepting it does not rewrite its original bytes or authorize a source-system change.

## Stage 5 — Establish the Phase 2 analysis basis

Question: which accepted input and method govern the analysis?

As Risk lead, record the method name, approach to business impact, confidence/uncertainty rules and prioritization rules. Read the Phase 1 input identified by the assessment, and confirm it is the intended exact snapshot with its qualifications.

Submit method/input gate `PQC-P2-G01`. Risk lead and Sponsor provide its required decisions. The method remains a synthetic demonstration method, not an enterprise-approved risk methodology.

Keep exposure, business consequence, evidence confidence, technical migration readiness and organizational enablement distinct. A missing source route does not make the cryptographic exposure smaller. An easily upgraded product is not already migrated.

## Stage 6 — Assess consequences and recommend action

Question: why does the observed condition matter, and what should happen next?

As Analyst or Risk lead, prepare each package's analysis:

1. State a conditional scenario, including the relevant cryptographic purpose and failure or threat event.
2. Describe the affected business service, information or operation and the consequence requiring confirmation.
3. Record a recommendation or next investigation, proposed review priority and evidence confidence.
4. Explain the rationale against the declared method. Carry forward the package's limitations.
5. Submit the analysis for Business reviewer disposition.
6. As Risk lead, submit analysis-validation gate `PQC-P2-G02`; Risk lead and Business reviewer provide the required decisions.

Where lifetime, exact-product support, relying-party compatibility or recovery is not established, say so. The report does not fabricate those missing facts or convert an algorithm name into an approved risk score.

## Stage 7 — Deliver Phase 2

Question: is this exact risk review justified and actionable?

1. As Risk lead, explicitly select the intended Phase 1 input report. Do not substitute a newly generated report merely because it is newer.
2. Choose **Generate Phase 2 draft**.
3. Read each scenario, business impact, evidence-confidence basis, vendor/implementation uncertainty, recommendation, accountable function and next decision.
4. Submit the exact Phase 2 report to gate `PQC-P2-G03`.
5. Risk lead and Sponsor record its required decisions.

Phase 2 produces an assessment position and prioritized next work. It does not create an approved change, close an enterprise ticket, rotate a key, upgrade a workload or execute a migration. Phase 3/4 remains a future control-system direction.

## Read, save and print a report

1. From Stage 4 or Stage 7, choose **Read report →**. You can also use **Reporting workspace** and select the report in history.
2. Use the narrative preview to inspect the executive position and next actions. Raw identifiers and supporting records belong in traceability details, not the executive message.
3. Download the **HTML** reading copy. Open the saved file in a browser; it uses no remote assets or live connector.
4. For PDF, use the browser's **Print** command, select **Save as PDF**, and inspect landscape print preview before saving. Verify table headers, line wrapping, page breaks and the report identifier in the footer. Expand and separately retain traceability details if the complete technical appendix is needed; the default printed reading copy omits the collapsible appendix.
5. Retain the original HTML and report identifier with the PDF. JSON is available for engineering traceability; it is not the primary leadership reading copy.

No email or external distribution is performed by this workflow. Approval of an assessment position is not permission to send its contents elsewhere.

## When the app says “not yet”

- **No findings or no assets:** inspect the selected assessment, admitted source packages and active filters. Empty selections stay empty; the catalog is not substituted as evidence.
- **No immediate action assigned:** inspect the gate requirements and signed-in role. Another participant may have the next task. This message does not mean the assessment is complete.
- **Disabled review:** confirm the package or gate was submitted, that the signed-in role is required, and that independent review is permitted for this actor.
- **Needs re-review:** a relevant scope, source, package, method or report input changed. Review the current submission; do not overwrite historical decisions to make them appear current.
- **Save result uncertain:** use **Retry identical request**. Do not create a different request merely because the first response was lost.
- **Revision changed:** keep the entered answers, inspect the refreshed state and requirements, then resubmit intentionally. The server does not use blind last-write-wins.
- **Blocked source:** record the known constraint, owner/route next step and date. Use an explicit qualified assessment conclusion when appropriate; do not simulate live evidence to clear the blocker.

## Read the operating indicators correctly

- Question answerability counts supported, qualified and unanswered questions in this assessment's current question set. The starter set distinguishes source routing from evidence availability; it is not yet a complete registry of every material business, cryptographic-use, dependency and acceptance question.
- Source enablement distinguishes documented routes from admitted synthetic samples. No live route is exercised in this candidate. Counts are not enterprise coverage or employee performance ratings.
- Decision backlog counts unfilled required-role slots on current submitted gates and their elapsed calendar-day age. It does not count every unsubmitted prerequisite or imply an approved response-time target. Zero pending slots is not proof that the assessment is finished.

Package qualifications currently use reviewer-authored text and retained limitation codes. This increment does not yet provide a full structured issue/disposition and factual-review-comment task system. Reviewers must not describe a bulk qualified package as resolution of each material dispute; unresolved facts remain unresolved.

## Founder-owner review queue — no outcomes recorded here

This candidate needs targeted owner observations before the corresponding readiness or activation claim. These are proposed review scopes, not claims that the owner has accepted anything.

R2 — guided workflow and report usability:

- Start a fresh assessment and explain its next useful action without coaching.
- Recognize the difference between three worked-example families and the full 27-family catalog.
- Record a blocked route and trace its limitation into the Phase 1 report.
- Review an exact report and explain what the separate gate decision changes.
- Follow the Phase 1-to-Phase 2 handoff and identify the selected input and method.
- Read a Phase 2 scenario and identify its accountable next action and remaining uncertainty.
- Check desktop/narrow-screen use and the printable report reading copy.

R3 — authorization and consequential transition boundaries:

- Confirm a Viewer cannot write or record decisions.
- Confirm the wrong reviewer or a package submitter cannot masquerade as an independent reviewer.
- Confirm a changed input requires the appropriate re-review, preserving historical records.
- Confirm Phase 2 cannot silently bind an unrelated or merely newest Phase 1 report.
- Confirm synthetic persona decisions and scenario-generated history cannot be presented as founder-owner outcomes or enterprise approvals.

Only the founder-owner may record the targeted `works`, `issue_found` or `blocked` observations through the designated owner-validation process. Automation and this guide cannot infer, submit or rewrite those outcomes. Missing observations block the affected claim, not unrelated development.

## What remains beyond this candidate

Enterprise identity and access integration; SQL Server persistence and operating proof; qualified read-only product connectors; custody of real enterprise evidence; enterprise deployment and supported remote access; calibrated and approved assessment methods; migration-ticket mediation; live execution and independently verified closure all require their own implementation and authorization gates.

The local assessment workflow is a development proof path for those capabilities, not a claim that they already exist.
