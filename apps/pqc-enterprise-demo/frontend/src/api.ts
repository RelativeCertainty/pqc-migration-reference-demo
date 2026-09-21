const assessmentErrors: Record<string, string> = {
  demo_database_capacity_exceeded: 'The isolated demonstration database has reached its configured capacity or available storage is full. This operation was not recorded. Existing history was preserved. Ask the operator to review storage, then retry the identical operation.',
  workspace_field_invalid: 'Check the required fields and their allowed length. No change was recorded.',
  workspace_fields_invalid: 'The work form does not match the server contract. Preserve your entries and reload the case.',
  workspace_receipt_review_required: 'Review and record the offline response before using its reported products in this step.',
  workspace_receipt_conflict_unresolved: 'Choose which answer to retain for each competing received answer.',
  workspace_receipt_already_applied: 'This received version was already recorded. Reload its receipt instead of applying it again.',
  workspace_receipt_choice_invalid: 'Choose the current or returned answer for each question shown in the comparison.',
  workspace_canonical_identity_unknown: 'First record a distinct system identity, then select that reviewed identity for a duplicate reference.',
  workspace_product_scope_invalid: 'Choose a product from an applied receipt in this exact assessment request.',
  workspace_response_required: 'Record the reviewed offline response or obtain a useful web submission before staging technical records.',
  workspace_source_not_in_scope: 'This software class is outside the assessment boundary. Review its scope before further evidence work.',
  workspace_supporting_evidence_required: 'Supported confidence needs admitted technical records. Use limited or unknown confidence and preserve the limitation.',
  workspace_no_evidence_limitation_required: 'Explain the missing-evidence limitation before previewing a conclusion without admitted records.',
  workspace_preview_stale: 'The evidence or interpretation changed. Preview the current report consequence again before recording it.',
  workspace_independent_review_required: 'A designated technical reviewer different from the stager must review these records.',
  workspace_evidence_reviewed: 'This exact bundle already has a recorded determination. Preserve it and use a corrected capture for new review.',
  workspace_review_required: 'Independent technical qualification is required before the assessment lead can admit this bundle.',
  workspace_evidence_duplicate: 'This capture is already recorded for the selected deployment. Read its existing review instead of staging it again.',
  workspace_useful_response_required: 'Retain one useful answer, referral, unknown or reported product before recording this response.',
  workspace_evidence_capacity_limit: 'The bounded candidate has reached its evidence capacity. No existing records were removed.',
  workspace_custody_capacity_limit: 'The private artifact allowance is full. The operator must review capacity; no evidence was silently deleted.',
  intake_text_limit: 'Keep each answer to 512 characters or fewer. Use a concise explanation and an approved evidence reference; do not include credentials.',
  intake_useful_response_required: 'Identify one system or save a useful answer, unknown or referral before handing this response to the coordinator.',
  intake_attribution_invalid: 'Direct contributor responses use your signed-in identity. Record another function as a referral rather than attributing its answer to yourself.',
  intake_independent_review_required: 'This response needs a submitted handoff and an independent technical reviewer before its determination can be recorded.',
  intake_preview_stale: 'The response changed after this preview. Reload the saved revision and preview the returned workbook again before choosing changes.',
  intake_export_stale: 'The request assignment or template changed after export. Prepare a current workbook; preserve any offline answers for explicit review.',
  intake_export_binding_invalid: 'This workbook does not match the selected assessment, request or original server export. Choose its correct request or obtain a fresh export.',
  intake_question_scope_invalid: 'One or more answer identifiers do not belong to this request. Use the current generated questionnaire without changing its reference columns.',
  intake_conflict_resolution_required: 'Choose which answer to keep for every competing edit before applying the reviewed import.',
  intake_upload_limit: 'The returned questionnaire exceeds the permitted upload limit. Use the generated questionnaire without extra attachments or sheets.',
  intake_reference_evidence_invalid: 'This file is not the qualified synthetic TLS source-page format. Use the operator-provided reference fixture; arbitrary vendor exports are not supported.',
  intake_format_not_qualified_for_family: 'Raw evidence intake for this family is not qualified in this slice. Save the source route and evidence limitation instead.',
  intake_subject_binding_invalid: 'Choose an assessed deployment in this same request. An evidence source is not automatically the system it describes.',
  intake_source_binding_invalid: 'Choose a separate source or dual-role record in this same request to identify where the observation came from.',
  intake_duplicate_evidence: 'This evidence batch is already recorded for the selected binding. Review the staged or admitted record instead of importing it again.',
  intake_capacity_limit: 'This isolated candidate has reached its bounded request or system capacity. Ask the operator to review capacity; existing records were not removed.',
  intake_snapshot_capacity_limit: 'The isolated assessment has reached its storage allowance. No existing evidence was silently removed; ask the operator to review capacity.',
  intake_request_not_found: 'This request is unavailable in the selected assessment. Choose a visible assigned request from the list.',
  intake_request_out_of_scope: 'This request is outside the current assessment boundary. Its history remains available, but the assessment lead must review the scope before work resumes.',
  assessment_revision_changed: 'Another participant changed this assessment. Review the updated record before resubmitting.',
  assessment_scope_required: 'First record the assessment objective, scope and handling route in stage 1.',
  assessment_scope_depth_or_exclusion_required: 'Each included source needs an expected depth. Each excluded source needs a reason. Return to stage 1 and review the coverage boundary.',
  assessment_scope_family_invalid: 'Include at least one recognized source family in the assessment boundary.',
  assessment_required_field: 'Complete the required fields marked on this form before submitting.',
  assessment_date_invalid: 'Supply a valid follow-up or review date in the marked date field.',
  assessment_fields_invalid: 'This form no longer matches the server contract. Keep your answers and refresh the application before retrying.',
  assessment_text_invalid: 'Use ordinary text within the field limit of 2,048 characters; control characters are not permitted.',
  assessment_forbidden: 'This task belongs to another assessment responsibility. Check the named reviewer or contributor, then use the corresponding signed-in demonstration persona.',
  confirmed_route_details_required: 'A confirmed route needs the system of record, actual product, responsible function and approved read-only route. Otherwise choose “I do not know yet” and describe what remains missing.',
  approved_sample_route_required: 'Confirm this source route and obtain governance and source-readiness decisions before admitting its fixed synthetic sample.',
  assessment_source_not_in_scope: 'This source is outside the current assessment boundary. Return to stage 1 if the scope needs changing.',
  assessment_package_not_in_scope: 'This package is outside the current assessment boundary. Choose an in-scope package.',
  no_evidence_qualification_required: 'No evidence has been admitted. Record the missing-evidence limitation and its consequence; do not claim a technical conclusion.',
  evidence_limitations_require_qualification: 'This package has missing or limited evidence. Request changes or explicitly qualify the limitation instead of accepting an unsupported conclusion.',
  qualification_required: 'Describe the limitation, consequence and follow-up responsibility before recording qualified acceptance.',
  independent_package_reviewer_required: 'The package submitter cannot supply its independent technical review. Ask the designated reviewer to assess it.',
  independent_analysis_reviewer_required: 'The analysis submitter cannot supply its independent business review. Ask the designated reviewer to assess it.',
  package_submission_required: 'Submit the evidence package before recording its technical review.',
  analysis_submission_required: 'Submit the authored analysis before recording its business review.',
  selected_phase1_handoff_required: 'Choose the exact Phase 1 report accepted or qualified at the Phase 1 delivery gate. A newer report is not substituted automatically.',
  phase1_inputs_require_review: 'The Phase 1 evidence or review basis changed. Re-review the current input and its exact report before proceeding to Phase 2.',
  assessment_report_not_found: 'The selected report does not belong to this assessment. Choose a report from its recorded history.',
  assessment_gate_prerequisites: 'This gate still has unmet requirements. Review the “Still required” items in its checklist; other preparation can continue.',
  gate_requirements_not_met: 'This gate still has unmet requirements. Review the “Still required” items in its checklist.',
  gate_requirements_outstanding: 'This gate still has unmet requirements. Review the “Still required” items in its checklist. Selecting a report is not approval.',
  assessment_prerequisite_gate_required: 'A preceding review gate has not been accepted or qualified. Review the earlier stage’s named reviewers and requirements; other preparation can continue.',
  current_gate_submission_required: 'The gate must have a current submitted revision. Changed inputs need resubmission and re-review.',
  rejected_submission_requires_revision: 'This submission was rejected. Address its recorded reasons and revise the inputs before requesting review again.',
  gate_already_submitted: 'This gate is already submitted or decided. Read its recorded decisions instead of creating a duplicate submission.',
  gate_role_already_decided: 'Your review function already decided this exact submission. The immutable decision remains visible in gate history.',
  supported_analysis_requires_unqualified_evidence: 'Supported confidence requires reviewed, unqualified evidence. Use limited or unknown confidence and explain the evidence gap.',
  analysis_limitations_require_qualification: 'The analysis has missing evidence or limited confidence. Explicitly qualify its limitations or request changes.',
  assessment_context_required: 'Choose a guided assessment before making changes. Legacy investigation tools are read-only.',
  gate_submission_required: 'Submit this exact gate revision for review before recording a decision.',
  gate_inputs_changed: 'This gate’s input changed after submission. Submit the refreshed revision for review; previous decisions remain historical.',
  gate_report_inputs_changed: 'The selected report no longer matches current inputs. Generate and select a current report, then resubmit its delivery gate.',
  idempotency_request_changed: 'An earlier request used this request identity with different content. Reconcile the recorded result before creating a new action.',
};
export class ApiError extends Error {
  constructor(public status: number, public code?: string) {
    super(code && assessmentErrors[code] ? assessmentErrors[code] : status === 401 ? 'Your session has ended. Sign in again to continue.'
      : status === 403 ? 'This action is not available to your role, or the session needs refreshing.'
      : status === 404 ? 'This record is not available in the current baseline.'
      : status === 409 ? 'This request conflicts with an existing operation. Refresh the run history before retrying.'
      : status === 429 ? 'Too many requests. Wait a moment, then try again.'
      : 'The application could not complete this request. Try again or contact the operator.');
  }
}

async function safeErrorCode(response: Response): Promise<string | undefined> {
  // Read only a bounded error envelope, and display only fixed local copy.
  const reader = response.body?.getReader();
  if (!reader) return undefined;
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 4096) { await reader.cancel(); return undefined; }
      chunks.push(value);
    }
    const bytes = new Uint8Array(size); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    const body = JSON.parse(new TextDecoder().decode(bytes)) as { error?: { code?: unknown } | string; code?: unknown };
    const code = typeof body.error === 'object' ? body.error?.code : typeof body.error === 'string' ? body.error : body.code;
    return typeof code === 'string' && Object.hasOwn(assessmentErrors, code) ? code : undefined;
  } catch { return undefined; } finally { reader.releaseLock(); }
}

export function selectedAssessmentId(): string {
  return new URLSearchParams(window.location.hash.split('?')[1]).get('assessment') || '';
}

/** Scope existing investigation tools without creating a second workflow authority. */
export function assessmentApiPath(path: string): string {
  const id = selectedAssessmentId();
  return id && /^\/api\/(dashboard|analysis|assets|sources|reports|runs|actions)(?:[/?]|$)/.test(path)
    ? `/api/assessments/${encodeURIComponent(id)}${path.slice(4)}` : path;
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  if (!path.startsWith('/api/')) throw new Error('Only same-origin application API paths are permitted.');
  path = assessmentApiPath(path);
  const response = await fetch(path, { ...options, credentials: 'same-origin', headers: {
    Accept: 'application/json', ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers,
  } });
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event('pqc-session-expired'));
    throw new ApiError(response.status, await safeErrorCode(response));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function readable(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Not recorded';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  if (Array.isArray(value)) return value.map(readable).join(', ');
  return Object.entries(value as Record<string, unknown>).map(([key, item]) => `${humanize(key)}: ${readable(item)}`).join(' · ');
}

export function humanize(value: string): string {
  const words = value.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/[_-]/g, ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function dateLabel(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC',
  }).format(date);
}
