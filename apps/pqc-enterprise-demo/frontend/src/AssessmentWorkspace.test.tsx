import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AssessmentWorkspace } from './AssessmentWorkspace';
import type { AssessmentCatalog, AssessmentDetail, AssessmentGate, AssessmentSource } from './assessment-contracts';
import type { Session } from './contracts';

const analyst: Session = { authenticated: true, role: 'analyst', synthetic: true, csrfToken: 'synthetic-workflow-csrf' };
const assessmentId = 'assessment-' + 'a'.repeat(32);
const source = (familyId: string, name: string): AssessmentSource => ({ id: familyId, familyId, name, areaId: 'area-01', examples: ['Example Platform'], state: 'unanswered', systemOfRecord: '', product: '', ownerFunction: '', accessRoute: '', note: '', dueAt: '', assertedBy: '', respondedBy: '', observationIds: [], subjectIds: [] });
const sources = [source('context', 'Context repository'), source('excluded', 'Excluded family')];
const gates: AssessmentGate[] = Array.from({ length: 7 }, (_, index) => ({ id: ['PQC-G00', 'PQC-P1-G01', 'PQC-P1-G02', 'PQC-P1-G03', 'PQC-P2-G01', 'PQC-P2-G02', 'PQC-P2-G03'][index], name: `Gate ${index + 1}`, stage: index + 1, requiredRoles: index === 0 ? ['sponsor', 'information-owner'] : ['assessment-lead', 'sponsor'], state: 'not_submitted', requirements: [{ label: 'Evidence requirement', satisfied: true }], decisions: [], submissionRevision: 0, fingerprint: 'f'.repeat(64), documentId: '' }));
const catalog: AssessmentCatalog = {
  personas: [{ principalId: 'synthetic-demo:analyst', role: 'assessment-lead', label: 'Assessment lead' }, { principalId: 'synthetic-demo:sponsor', role: 'sponsor', label: 'Engagement sponsor' }, { principalId: 'synthetic-demo:risk-lead', role: 'risk-lead', label: 'Risk lead' }],
  stages: Array.from({ length: 7 }, (_, index) => ({ id: index + 1, label: `Stage ${index + 1}`, question: `Question for stage ${index + 1}` })),
  sourceFamilies: sources, gates, operations: [], depthOptions: [{ id: 'routing', label: 'Route identification' }, { id: 'inventory', label: 'Bounded inventory' }, { id: 'dependency_cohort', label: 'Dependency cohort' }],
};
function freshDetail(): AssessmentDetail {
  return {
    id: assessmentId, name: 'Bounded synthetic assessment', mode: 'fresh', synthetic: true, revision: 7, stage: 1,
    scope: { objective: 'Map a bounded synthetic service', handling: 'Owner-only synthetic evidence', method: 'Versioned draft method', cycleGoal: 'Find the accountable source function', reviewDate: '2026-09-20', includedFamilyIds: ['context'], excludedReasons: { excluded: 'Outside this selected cohort' }, depthByFamily: { context: 'routing' } },
    assignments: catalog.personas, sources: structuredClone(sources), packages: sources.map(item => ({ id: item.id, familyId: item.familyId, label: item.name, state: 'ready', conclusion: '', qualification: '', submittedBy: '', reviewedBy: '', revision: 0, evidenceCount: 0, subjectCount: 0, observationIds: [], subjectIds: [], analysis: { scenario: '', businessImpact: '', recommendation: '', priority: 'planned_review', rationale: '', confidence: 'unknown', state: 'ready', submittedBy: '', reviewedBy: '' } })),
    gates: structuredClone(gates), documents: [], nextActions: [], events: [], questions: [],
    availableOperations: ['update_scope', 'source_response', 'admit_sample', 'submit_package', 'review_package', 'submit_gate', 'decide_gate', 'set_method', 'submit_analysis', 'review_analysis', 'generate_report'],
    method: { name: '', description: '', confidenceRules: '', prioritizationRules: '', status: 'draft', revision: 0 },
  };
}
let detail: AssessmentDetail;
let failMode: 'none' | 'ambiguous' | 'conflict' = 'none';
let writes: RequestInit[];
const navigate = vi.fn((page: string, params?: Record<string, string>) => { window.location.hash = `${page}?${new URLSearchParams(params)}`; });
const fetchMock = vi.fn(async (input: RequestInfo | URL, options?: RequestInit) => {
  const path = String(input);
  if (options?.method === 'POST') {
    writes.push(options);
    if (failMode === 'ambiguous') { failMode = 'none'; throw new TypeError('Connection interrupted'); }
    if (failMode === 'conflict') { failMode = 'none'; detail.revision++; return Response.json({ error: { code: 'assessment_revision_changed' } }, { status: 409 }); }
    if (path.endsWith('/commands')) detail.revision++;
    return Response.json(detail, { status: 201 });
  }
  if (path === '/api/assessments/catalog') return Response.json(catalog);
  if (path === '/api/assessments') return Response.json([detail]);
  if (path === `/api/assessments/${assessmentId}`) return Response.json(detail);
  throw new Error(`Unexpected fixture route: ${path}`);
});
beforeEach(() => {
  detail = freshDetail(); writes = []; failMode = 'none'; navigate.mockClear(); fetchMock.mockClear();
  history.replaceState(null, '', `#assessments?assessment=${assessmentId}&stage=2`);
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function stage(number: number) { history.replaceState(null, '', `#assessments?assessment=${assessmentId}&stage=${number}`); }
async function open(session = analyst) {
  render(<AssessmentWorkspace session={session} onNavigate={navigate} />);
  await screen.findByRole('heading', { name: 'Bounded synthetic assessment' });
}
async function answerSource() {
  fireEvent.change(await screen.findByLabelText('Person or function supplying this answer'), { target: { value: 'Synthetic source coordinator' } });
  fireEvent.change(screen.getByLabelText('What is known, missing, or blocked?'), { target: { value: 'Please help identify the responsible repository function.' } });
  fireEvent.change(screen.getByLabelText('Expected follow-up date'), { target: { value: '2026-09-20' } });
}

describe('guided assessment application', () => {
  it('creates a fresh server-owned assessment from the primary entry without implying approved gates', async () => {
    history.replaceState(null, '', '#assessments');
    render(<AssessmentWorkspace session={analyst} onNavigate={navigate} />);
    fireEvent.change(await screen.findByLabelText(/Assessment name/), { target: { value: 'Synthetic cohort test' } });
    fireEvent.click(screen.getByRole('button', { name: 'Start assessment →' }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(JSON.parse(String(writes[0].body))).toEqual({ name: 'Synthetic cohort test', mode: 'fresh' });
    expect(writes[0].headers).toMatchObject({ 'X-PQC-CSRF': analyst.csrfToken, 'Idempotency-Key': expect.any(String) });
    expect(navigate).toHaveBeenCalledWith('assessments', { assessment: assessmentId, stage: '1' });
  });

  it('exposes all seven stages but excludes out-of-scope sources from working tasks and counts', async () => {
    await open();
    expect(within(screen.getByRole('navigation', { name: 'Assessment stages' })).getAllByRole('button')).toHaveLength(7);
    expect(screen.queryByRole('button', { name: /Excluded family/ })).not.toBeInTheDocument();
    expect(screen.getAllByText('0 of 1')).toHaveLength(2);
    fireEvent.click(screen.getByRole('button', { name: 'Stage 7: Stage 7' }));
    expect(navigate).toHaveBeenLastCalledWith('assessments', { assessment: assessmentId, stage: '7' });
    expect(writes).toHaveLength(0);
  });

  it('preserves creation request identity after uncertain delivery, even if the draft name changes', async () => {
    history.replaceState(null, '', '#assessments'); failMode = 'ambiguous';
    render(<AssessmentWorkspace session={analyst} onNavigate={navigate} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Start assessment →' }));
    await screen.findByRole('button', { name: 'Retry original assessment creation' });
    fireEvent.change(screen.getByLabelText(/Assessment name/), { target: { value: 'Do not silently replace the uncertain request' } });
    fireEvent.click(screen.getByRole('button', { name: 'Retry original assessment creation' }));
    await waitFor(() => expect(writes).toHaveLength(2));
    expect(writes[0].body).toBe(writes[1].body);
    expect((writes[0].headers as Record<string, string>)['Idempotency-Key']).toBe((writes[1].headers as Record<string, string>)['Idempotency-Key']);
  });

  it('records a low-friction unknown response with attribution, not fabricated product answers', async () => {
    await open(); await answerSource();
    expect(screen.getByRole('heading', { name: 'Identify teams and information sources' })).toBeInTheDocument();
    expect(screen.getByText(/Why we ask: locate existing information/)).toHaveTextContent('saving this response does not grant access or verify cryptographic behavior.');
    fireEvent.click(screen.getByRole('button', { name: 'Save source response' }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(JSON.parse(String(writes[0].body))).toMatchObject({ operation: 'source_response', targetId: 'context', expectedRevision: 7, fields: { state: 'unknown', assertedBy: 'Synthetic source coordinator', systemOfRecord: '', product: '', ownerFunction: '', accessRoute: '', dueAt: '2026-09-20' } });
    expect(await screen.findByText(/Recorded: Source response/)).toBeInTheDocument();
  });

  it('keeps ambiguous command retries byte-identical and reuses the idempotency key', async () => {
    failMode = 'ambiguous'; await open(); await answerSource();
    fireEvent.click(screen.getByRole('button', { name: 'Save source response' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Retry identical request' }));
    await waitFor(() => expect(writes).toHaveLength(2));
    expect(writes[0].body).toBe(writes[1].body);
    expect((writes[0].headers as Record<string, string>)['Idempotency-Key']).toBe((writes[1].headers as Record<string, string>)['Idempotency-Key']);
  });

  it('refreshes a revision conflict without discarding the contributor’s entered answers', async () => {
    failMode = 'conflict'; await open(); await answerSource();
    fireEvent.click(screen.getByRole('button', { name: 'Save source response' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Another participant changed this assessment.');
    await waitFor(() => expect(screen.getByText('Revision 8')).toBeInTheDocument());
    expect(screen.getByLabelText('Person or function supplying this answer')).toHaveValue('Synthetic source coordinator');
    expect(screen.getByLabelText('What is known, missing, or blocked?')).toHaveValue('Please help identify the responsible repository function.');
  });

  it('sends only closed scope fields and synchronizes depth/exclusion maps when including a source', async () => {
    stage(1);
    Object.assign(detail.scope, { revision: 20 });
    await open();
    fireEvent.click(screen.getByRole('checkbox', { name: /Excluded family/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Save scope draft' }));
    await waitFor(() => expect(writes).toHaveLength(1));
    const { fields } = JSON.parse(String(writes[0].body));
    expect(fields).not.toHaveProperty('revision');
    expect(fields.depthByFamily).toEqual({ context: 'routing', excluded: 'routing' });
    expect(fields.excludedReasons).toEqual({});
    expect(Object.keys(fields)).toHaveLength(8);
    const command = JSON.parse(String(writes[0].body));
    expect(Object.keys(command).sort()).toEqual(['expectedRevision', 'fields', 'operation', 'targetId']);
    expect(command.targetId).toBeNull();
  });
  it('preserves intake entry context after creating an assessment and provides an explicit return route', async () => {
    history.replaceState(null, '', '#assessments?from=intake');
    render(<AssessmentWorkspace session={analyst} onNavigate={navigate} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Start assessment →' }));
    await waitFor(() => expect(navigate).toHaveBeenCalledWith('assessments', { assessment: assessmentId, stage: '1', from: 'intake' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Return to Discovery & intake →' }));
    expect(navigate).toHaveBeenLastCalledWith('intake', { assessment: assessmentId });
    expect(writes).toHaveLength(1);
  });

  it('removes a source’s depth when excluding it and retains an explicit reason', async () => {
    stage(1); await open();
    fireEvent.click(screen.getByRole('checkbox', { name: /Excluded family/ }));
    fireEvent.click(screen.getByRole('checkbox', { name: /Context repository/ }));
    fireEvent.change(screen.getByLabelText('Reason outside this assessment'), { target: { value: 'Separate cohort; review in the next cycle' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save scope draft' }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(JSON.parse(String(writes[0].body)).fields).toMatchObject({ includedFamilyIds: ['excluded'], depthByFamily: { excluded: 'routing' }, excludedReasons: { context: 'Separate cohort; review in the next cycle' } });
  });

  it('requires an explicit report selection and submits its exact identifier for G03 evaluation', async () => {
    stage(4); detail.gates[3].requirements[0].satisfied = false;
    detail.documents = [{ id: 'report-exact', phase: 'phase1', createdAt: '2026-09-08T12:00:00Z', contentSha256: 'd'.repeat(64), inputFingerprint: 'e'.repeat(64), status: 'draft' }];
    await open();
    expect(screen.getByRole('button', { name: 'Submit this gate for review' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Exact report to submit for this gate'), { target: { value: 'report-exact' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit this gate for review' }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(JSON.parse(String(writes[0].body))).toMatchObject({ operation: 'submit_gate', targetId: 'PQC-P1-G03', fields: { reportId: 'report-exact' } });
  });

  it('requires a chosen Phase 1 report for Phase 2 and never silently selects latest', async () => {
    stage(7); detail.documents = [{ id: 'accepted-phase1', phase: 'phase1', createdAt: '2026-09-08T12:00:00Z', contentSha256: 'd'.repeat(64), inputFingerprint: 'e'.repeat(64), status: 'accepted' }];
    detail.phase1InputReportId = 'accepted-phase1';
    await open({ ...analyst, role: 'risk-lead' });
    expect(screen.getByRole('button', { name: 'Generate Phase 2 draft' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Select the exact Phase 1 input report/), { target: { value: 'accepted-phase1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Generate Phase 2 draft' }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(JSON.parse(String(writes[0].body))).toMatchObject({ operation: 'generate_report', fields: { phase: 'phase2', phase1ReportId: 'accepted-phase1' } });
  });

  it('shows the exact handoff basis before Phase 2 method review without substituting a newer draft', async () => {
    stage(5); detail.phase1InputReportId = 'qualified-phase1';
    detail.documents = [
      { id: 'qualified-phase1', phase: 'phase1', createdAt: '2026-09-08T12:00:00Z', contentSha256: 'd'.repeat(64), inputFingerprint: 'e'.repeat(64), status: 'qualified' },
      { id: 'newer-draft', phase: 'phase1', createdAt: '2026-09-16T12:00:00Z', contentSha256: 'f'.repeat(64), inputFingerprint: 'a'.repeat(64), status: 'draft' },
    ];
    await open({ ...analyst, role: 'risk-lead' });
    expect(screen.getByRole('region', { name: 'Exact Phase 1 reliance basis' })).toHaveTextContent('qualified-phase1');
    expect(screen.getByRole('region', { name: 'Exact Phase 1 reliance basis' })).not.toHaveTextContent('newer-draft');
    fireEvent.click(screen.getByRole('button', { name: 'Read selected Phase 1 basis →' }));
    expect(navigate).toHaveBeenCalledWith('reports', { assessment: detail.id, report: 'qualified-phase1' });
    expect(writes).toHaveLength(0);
  });

  it('keeps attributed business context and constraints distinct when submitting Phase 2 analysis', async () => {
    stage(6); await open({ ...analyst, role: 'risk-lead' });
    for (const [label, value] of [
      ['Conditional risk scenario', 'Long-lived synthetic claims are protected by the examined legacy exchange.'],
      ['Business consequence and what needs confirmation', 'Disclosure would undermine the fictional claims service.'],
      ['Recommended treatment or next investigation', 'Qualify relying-party compatibility before a pilot.'],
      ['Rationale tied to the agreed method', 'Prioritize because information outlives the proposed migration window.'],
      ['Protected information and affected business service', 'Synthetic claims archive and customer portal'],
      ['Confidentiality or trust lifetime and basis', 'Seven years, per the fictional information owner.'],
      ['Business context asserted by', 'Fictional claims information owner'],
      ['Business statement date', '2026-09-16'],
      ['Compatibility and relying-party constraints', 'Two older clients need qualification.'],
      ['Vendor dependencies and commitments', 'No confirmed delivery commitment.'],
      ['Operational and change constraints', 'Use an isolated approved maintenance window.'],
      ['Responsible function for the recommendation', 'Fictional platform engineering'],
      ['Next decision and who must make it', 'Sponsor confirms the pilot cohort.'],
    ]) fireEvent.change(screen.getByLabelText(new RegExp(`^${label}`)), { target: { value } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit analysis for business review' }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(JSON.parse(String(writes[0].body))).toMatchObject({ operation: 'submit_analysis', fields: { protectedInformation: 'Synthetic claims archive and customer portal', lifetime: 'Seven years, per the fictional information owner.', assertedBy: 'Fictional claims information owner', statementDate: '2026-09-16', responsibleFunction: 'Fictional platform engineering', nextDecision: 'Sponsor confirms the pilot cohort.' } });
    expect(JSON.parse(String(writes[0].body)).fields).not.toHaveProperty('reviewedBy');
  });

  it('opens the exact report without dropping its assessment context', async () => {
    stage(7); detail.documents = [{ id: 'phase2-exact', phase: 'phase2', createdAt: '2026-09-16T12:00:00Z', contentSha256: 'd'.repeat(64), inputFingerprint: 'e'.repeat(64), status: 'draft' }];
    await open({ ...analyst, role: 'risk-lead' });
    fireEvent.click(screen.getByRole('button', { name: 'Read report →' }));
    expect(navigate).toHaveBeenCalledWith('reports', { assessment: detail.id, report: 'phase2-exact' });
    expect(writes).toHaveLength(0);
  });

  it('uses review-and-confirm before a designated persona records a gate decision', async () => {
    stage(1); detail.gates[0].state = 'submitted';
    await open({ ...analyst, role: 'sponsor' });
    expect(screen.getByLabelText('Decision requested for this exact revision')).toHaveValue('');
    fireEvent.change(screen.getByLabelText('Decision requested for this exact revision'), { target: { value: 'qualified' } });
    fireEvent.change(screen.getByLabelText('Evidence-based decision rationale'), { target: { value: 'Bounded synthetic evidence only.' } });
    fireEvent.change(screen.getByLabelText('Limitation, consequence and follow-up owner'), { target: { value: 'No live source evidence; assessment lead to follow up.' } });
    fireEvent.change(screen.getByLabelText('Follow-up review date'), { target: { value: '2026-09-20' } });
    fireEvent.click(screen.getByRole('button', { name: 'Check decision before recording' }));
    expect(screen.getByRole('region', { name: 'Check your decision' })).toHaveTextContent('it does not answer the technical question');
    expect(writes).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: 'Confirm and record this decision' }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(JSON.parse(String(writes[0].body))).toMatchObject({ operation: 'decide_gate', targetId: 'PQC-G00', fields: { decision: 'qualified' } });
  });

  it('maps the analyst persona to its assessment-lead review responsibility from the catalog', async () => {
    stage(2); detail.gates[1].state = 'submitted';
    await open();
    expect(screen.getByText('Assessment lead')).toBeInTheDocument();
    expect(screen.getByLabelText('Decision requested for this exact revision')).toBeEnabled();
  });
});
