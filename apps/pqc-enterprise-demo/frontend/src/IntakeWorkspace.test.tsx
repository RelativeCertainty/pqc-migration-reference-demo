import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { IntakeWorkspace } from './IntakeWorkspace';
import App from './App';
import type { IntakeView } from './intake-contracts';
import type { Session } from './contracts';

const assessmentId = 'assessment-' + 'b'.repeat(32);
const base = `/api/assessments/${assessmentId}/intake`;
const session: Session = { authenticated: true, role: 'contributor', synthetic: true, csrfToken: 'synthetic-intake-csrf' };
function fixture(): IntakeView {
  return {
    assessmentId, assessmentName: 'Portal intake candidate', revision: 2, role: 'contributor', synthetic: true, eligibleFamilyIds: ['traffic-termination'],
    requests: [{ id: 'request-a', title: 'Find the portal evidence routes', familyId: 'traffic-termination', assignedTo: 'synthetic-demo:contributor', status: 'draft', whyItMatters: 'Distinguish the two portal deployments so their evidence cannot be mixed.', examples: ['F5 BIG-IP', 'NGINX'], systemIds: ['east', 'west', 'cmdb'], answers: {}, assertedBy: '', recordedBy: '', determination: '', limitation: '' }],
    systems: [{ id: 'east', requestId: 'request-a', label: 'Portal East', product: 'NGINX', environment: 'Synthetic east', systemRole: 'subject', aboutSystemId: '' }, { id: 'west', requestId: 'request-a', label: 'Portal West', product: 'NGINX', environment: 'Synthetic west', systemRole: 'subject', aboutSystemId: '' }, { id: 'cmdb', requestId: 'request-a', label: 'Context registry', product: 'Example CMDB', environment: 'Synthetic', systemRole: 'source', aboutSystemId: 'east' }],
    questions: [{ id: 'owner', label: 'Who owns this system?', whyItMatters: 'The coordinator needs an accountable route.', usefulResponse: 'Name a function or say that the owner remains unknown.' }, { id: 'limitation', label: 'What remains unknown?', whyItMatters: 'The report must preserve gaps.', usefulResponse: 'Describe the missing evidence and its consequence.' }],
    receipt: null, evidence: [], pendingEvidence: [], canCoordinate: false, canReview: false, canAdmit: false,
    reportPreview: { summary: 'Two deployments are identified; technical behavior remains unestablished.', conclusions: ['Two independently identified portal instances.'], limitations: ['No technical evidence admitted.'], nextDecisions: ['Identify an authorized evidence route.'] }, boundary: 'Synthetic local development only.',
  };
}
let view: IntakeView; let writes: { path: string; options: RequestInit }[]; let fail: '' | 'ambiguous' | 'conflict';
const navigate = vi.fn((page: string, params?: Record<string, string>) => { window.location.hash = `${page}?${new URLSearchParams(params)}`; });
const fetchMock = vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
  const path = String(input);
  if (options.method === 'POST') {
    writes.push({ path, options });
    if (fail === 'ambiguous') { fail = ''; throw new TypeError('Connection interrupted'); }
    if (fail === 'conflict') { fail = ''; return Response.json({ error: { code: 'assessment_revision_changed' } }, { status: 409 }); }
    if (path.includes('/imports/')) return Response.json({ previewId: 'preview-a', revision: view.revision, changes: [{ key: 'east/owner', baseline: 'Original owner', current: 'Web correction', returned: 'Offline correction', state: 'conflict' }] });
    if (path.includes('/exports/')) return Response.json({ exportId: 'export-a', downloadUrl: `${base}/exports/export-a/download`, revision: view.revision });
    const command = JSON.parse(String(options.body));
    // Match the C# closed wire envelope: nullable does not mean omittable.
    if (JSON.stringify(Object.keys(command).sort()) !== JSON.stringify(['expectedRevision', 'fields', 'operation', 'targetId'])) return Response.json({ error: 'body_fields_invalid' }, { status: 400 });
    view.revision++;
    if (command.operation === 'intake_save_response') { view.requests[0].answers = command.fields.answers; view.requests[0].assertedBy = command.fields.assertedBy; view.requests[0].recordedBy = 'synthetic-demo:contributor'; }
    if (command.operation === 'intake_submit_response') view.requests[0].status = 'returned';
    if (command.operation === 'intake_review_response') { view.requests[0].status = command.fields.determination === 'qualified' ? 'closed_with_limitation' : 'clarification_needed'; view.requests[0].determination = command.fields.determination; view.requests[0].limitation = command.fields.limitation; }
    view.receipt = { effect: command.operation === 'intake_submit_response' ? 'Response handed to the coordinator; the evidence gap remains.' : 'Saved partial response—not technical verification.', nextResponsible: 'Assessment coordinator', nextAction: 'Review the source route and retain the missing-evidence limitation.' };
    return Response.json(view);
  }
  if (path === '/api/session') return Response.json(session);
  if (path === '/api/assessments') return Response.json([{ id: assessmentId, name: view.assessmentName, revision: view.revision, mode: 'fresh', synthetic: true, stage: 2 }]);
  if (path === '/api/assessments/catalog') return Response.json({ sourceFamilies: [{ familyId: 'traffic-termination', name: 'Traffic termination' }, { familyId: 'ssh', name: 'Excluded machine access family' }] });
  if (path === base) return Response.json(view);
  throw new Error(`Unexpected fixture API route: ${path}`);
});
beforeEach(() => {
  view = fixture(); writes = []; fail = ''; navigate.mockClear(); fetchMock.mockClear();
  history.replaceState(null, '', `#intake?assessment=${assessmentId}`);
  vi.stubGlobal('fetch', fetchMock); vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined);
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
async function open(currentSession = session) { render(<IntakeWorkspace session={currentSession} onNavigate={navigate} />); await screen.findByRole('heading', { name: 'Find the portal evidence routes' }); }
async function partialAnswer() {
  fireEvent.click(screen.getByText('Specific answers for Portal East'));
  fireEvent.change(screen.getByLabelText(/Who owns this system\? — Portal East/), { target: { value: 'I do not know; ask the synthetic portal team.' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save partial response' }));
}
describe('discovery and evidence intake slice', () => {
  it('explains purpose, distinguishes deployments from evidence sources and shows the report consequence', async () => {
    await open();
    expect(screen.getByText('Find the right source')).toBeInTheDocument();
    expect(screen.getByText('Known systems or a useful referral')).toBeInTheDocument();
    expect(screen.getByText(/Help us locate existing information:/)).toHaveTextContent('Any later collection or system access must be agreed separately with the appropriate owner.');
    expect(screen.getByText('Distinguish the two portal deployments so their evidence cannot be mixed.')).toBeInTheDocument();
    expect(screen.getByText('F5 BIG-IP · NGINX')).toBeInTheDocument();
    expect(screen.getAllByText('System being assessed')).toHaveLength(2);
    expect(screen.getByText('Evidence source')).toBeInTheDocument();
    expect(screen.getByText(/Provides evidence about/)).toHaveTextContent('Portal East');
    const report = screen.getByRole('region', { name: 'Draft report consequence' });
    expect(report).toHaveTextContent('Two deployments are identified; technical behavior remains unestablished.');
    expect(report).toHaveTextContent('No technical evidence admitted.');
    expect(report).toHaveTextContent('Live draft · not an accepted deliverable');
    expect(report).toHaveTextContent('Next decisions and information needed');
    expect(screen.getByText('1 visible requests · not a coverage denominator')).toBeInTheDocument();
  });
  it('saves a partial unknown response and requires a separate checked handoff', async () => {
    await open(); await partialAnswer();
    expect(await screen.findByRole('heading', { name: 'Saved partial response—not technical verification.' })).toBeInTheDocument();
    expect(JSON.parse(String(writes[0].options.body))).toMatchObject({ operation: 'intake_save_response', targetId: 'request-a', expectedRevision: 2, fields: { assertedBy: 'synthetic-demo:contributor', answers: { 'east/owner': 'I do not know; ask the synthetic portal team.' } } });
    fireEvent.click(screen.getByRole('button', { name: 'Check response before handoff' }));
    expect(screen.getByRole('region', { name: 'Check your response before handoff' })).toHaveTextContent('This does not grant access, verify technical facts or accept a deliverable.');
    expect(writes).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'Confirm handoff to coordinator' }));
    expect(await screen.findByRole('heading', { name: 'Response handed to the coordinator; the evidence gap remains.' })).toBeInTheDocument();
    expect(writes).toHaveLength(2);
    expect(screen.getByText(/Next responsible:/).parentElement).toHaveTextContent('Assessment coordinator');
  });
  it('retains the first edit through parent updates and still synchronizes changed server readback', async () => {
    await open();
    const answer = screen.getByLabelText(/Who owns this system\? — Whole request/);
    fireEvent.change(answer, { target: { value: '  A useful first referral  ' } });
    await screen.findByText('Your web answers have unsaved edits.');
    expect(answer).toHaveValue('  A useful first referral  ');
    // Deliberately model a server-normalized response: local retention must not
    // disable later synchronization of a genuinely changed saved snapshot.
    vi.stubGlobal('fetch', async (input: RequestInfo | URL, options: RequestInit = {}) => {
      const response = await fetchMock(input, options);
      if (options.method !== 'POST' || !String(input).endsWith('/commands')) return response;
      const readback = await response.json() as IntakeView;
      readback.requests[0].answers['request-a/owner'] = 'A useful first referral';
      return Response.json(readback);
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save partial response' }));
    await screen.findByRole('heading', { name: 'Saved partial response—not technical verification.' });
    expect(JSON.parse(String(writes[0].options.body)).fields.answers).toEqual({ 'request-a/owner': '  A useful first referral  ' });
    expect(screen.getByLabelText(/Who owns this system\? — Whole request/)).toHaveValue('A useful first referral');
    expect(screen.queryByText('Your web answers have unsaved edits.')).not.toBeInTheDocument();
  });
  it('retains one request identity after ambiguous delivery', async () => {
    fail = 'ambiguous'; await open(); await partialAnswer();
    fireEvent.click(await screen.findByRole('button', { name: 'Retry original operation' }));
    await waitFor(() => expect(writes).toHaveLength(2));
    expect(writes[0].options.body).toBe(writes[1].options.body);
    expect(writes[0].options.headers).toEqual(writes[1].options.headers);
  });
  it('preserves entered answers after a revision conflict without allowing a blind retry', async () => {
    fail = 'conflict'; await open(); await partialAnswer();
    expect(await screen.findByRole('alert')).toHaveTextContent('no competing edit was overwritten');
    expect(screen.getByLabelText(/Who owns this system\? — Portal East/)).toHaveValue('I do not know; ask the synthetic portal team.');
    expect(screen.getByRole('button', { name: 'Save partial response' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Discard local draft and load saved revision' })).toBeEnabled();
    expect(writes).toHaveLength(1);
  });
  it('exports a server-linked copy and demands an explicit competing-edit choice before import commit', async () => {
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Prepare Excel questionnaire' }));
    expect(await screen.findByRole('link', { name: 'Download prepared Excel file' })).toHaveAttribute('href', `${base}/exports/export-a/download`);
    const file = new File(['synthetic fixture bytes'], 'returned.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    fireEvent.change(screen.getByLabelText('Preview a returned questionnaire (.xlsx)'), { target: { files: [file] } });
    const preview = await screen.findByRole('region', { name: 'Returned Excel change preview' });
    expect(preview).toHaveTextContent('No answers have changed yet.');
    expect(within(preview).getByRole('button', { name: 'Apply reviewed changes only' })).toBeDisabled();
    fireEvent.change(within(preview).getByRole('combobox'), { target: { value: 'current' } });
    fireEvent.click(within(preview).getByRole('button', { name: 'Apply reviewed changes only' }));
    await waitFor(() => expect(writes).toHaveLength(3));
    expect(JSON.parse(String(writes[2].options.body))).toMatchObject({ operation: 'intake_commit_import', fields: { previewId: 'preview-a', choices: { 'east/owner': 'current' } } });
    expect(writes[1].options.body).toBe(file);
  });
  it('creates an additional deployment without requiring product or environment guesses', async () => {
    await open();
    fireEvent.click(screen.getByText('Add a deployment or evidence source'));
    fireEvent.change(screen.getByLabelText('System or deployment name'), { target: { value: 'Portal North' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add this separate system record' }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(JSON.parse(String(writes[0].options.body))).toMatchObject({ operation: 'intake_add_system', fields: { label: 'Portal North', product: '', environment: '', systemRole: 'subject', aboutSystemId: '' } });
  });
  it('accepts a useful whole-request unknown without requiring any deployment or attribution impersonation', async () => {
    view.systems = []; view.requests[0].systemIds = []; await open();
    fireEvent.change(screen.getByLabelText(/Who owns this system\? — Whole request/), { target: { value: 'I do not know; please route to the platform function.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save partial response' }));
    await screen.findByRole('heading', { name: 'Saved partial response—not technical verification.' });
    expect(JSON.parse(String(writes[0].options.body))).toMatchObject({ fields: { answers: { 'request-a/owner': 'I do not know; please route to the platform function.' }, assertedBy: 'synthetic-demo:contributor' } });
    expect(screen.queryByLabelText('Person or function supplying these answers')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Check response before handoff' })).toBeEnabled();
  });
  it('shows the blocked admission reason and no executable admission when assessment gates are pending', async () => {
    view.canCoordinate = true;
    view.pendingEvidence = [{ id: 'batch-a', requestId: 'request-a', systemId: 'east', sourceSystemId: 'cmdb', count: 1, contentSha256: 'a'.repeat(64) }];
    await open();
    expect(screen.getByRole('button', { name: 'Check batch before admission' })).toBeDisabled();
    expect(screen.getByText('Evidence admission is waiting on the assessment boundary and source-access gates.')).toBeInTheDocument();
    expect(writes).toHaveLength(0);
  });
  it('describes the limited metadata check before admitting an operator-provided reference fixture', async () => {
    view.canCoordinate = true; view.canAdmit = true;
    view.pendingEvidence = [{ id: 'batch-a', requestId: 'request-a', systemId: 'east', sourceSystemId: 'cmdb', count: 1, contentSha256: 'a'.repeat(64) }];
    await open();
    expect(screen.getByText(/This view shows the subject, source, observation count and file reference only/)).toHaveTextContent('not the observation values or reported evidence basis');
    expect(screen.getByText(/Inspect the operator-provided synthetic fixture before admitting it/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Check batch before admission' }));
    const check = screen.getByRole('region', { name: 'Check evidence admission' });
    expect(check).toHaveTextContent('Confirm the metadata shown here and your review of the operator-provided fixture.');
    expect(check).toHaveTextContent('does not establish that their technical content was independently verified');
    expect(check).not.toHaveTextContent('reported basis above');
    expect(writes).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: 'Admit this synthetic reference batch' }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(JSON.parse(String(writes[0].options.body))).toMatchObject({ operation: 'intake_admit_evidence', targetId: 'request-a', fields: { batchId: 'batch-a' } });
  });
  it('replaces the pending-handoff prompt with the recorded limitation and next function after factual review', async () => {
    view.canReview = true; view.role = 'technical-reviewer'; view.requests[0].status = 'returned';
    await open({ ...session, role: 'reviewer' });
    fireEvent.change(screen.getByLabelText('Response determination'), { target: { value: 'qualified' } });
    fireEvent.change(screen.getByLabelText('Limitation, consequence and next responsible function'), { target: { value: 'Reported ownership only. Synthetic platform function must establish the evidence route.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Check determination before recording' }));
    expect(writes).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: 'Record this response determination' }));
    expect(await screen.findByText(/Factual review is recorded with a limitation/)).toHaveTextContent('The coordinator follows up with the responsible function named in that determination.');
    expect(screen.getByText(/Factual review is recorded with a limitation/)).toHaveTextContent('not proof that the underlying gap is resolved or the assessment is complete');
    expect(screen.queryByText('A saved response must be handed off before factual review.')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Check determination before recording' })).toBeDisabled();
    expect(view.requests[0].status).toBe('closed_with_limitation');
    expect(writes).toHaveLength(1);
  });
  it('keeps a qualified readback distinct from a response waiting for its initial handoff', async () => {
    view.canReview = true; view.requests[0].status = 'qualified'; view.requests[0].determination = 'qualified';
    await open({ ...session, role: 'reviewer' });
    expect(screen.getByText(/Factual review is recorded with a limitation/)).toBeInTheDocument();
    expect(screen.queryByText('A saved response must be handed off before factual review.')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Check determination before recording' })).toBeDisabled();
    expect(writes).toHaveLength(0);
  });
  it('explains the contributor-to-reviewer loop when clarification is requested', async () => {
    view.canReview = true; view.requests[0].status = 'clarification_needed'; view.requests[0].determination = 'needs_clarification';
    await open({ ...session, role: 'reviewer' });
    expect(screen.getByText(/Clarification was requested/)).toHaveTextContent('The assigned contributor supplies an updated response, then hands it off again for factual review.');
    expect(screen.queryByText('A saved response must be handed off before factual review.')).not.toBeInTheDocument();
    expect(screen.queryByText(/Factual review is recorded with a limitation/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Check determination before recording' })).toBeDisabled();
    expect(writes).toHaveLength(0);
  });
  it('offers only server-eligible families inside the current assessment boundary', async () => {
    view.canCoordinate = true; await open();
    fireEvent.click(screen.getByText('Create a focused source request'));
    const families = screen.getByRole('combobox', { name: 'Source family' });
    await waitFor(() => expect(within(families).getAllByRole('option')).toHaveLength(2));
    expect(within(families).getByRole('option', { name: 'Traffic termination' })).toBeInTheDocument();
    expect(within(families).queryByRole('option', { name: 'Excluded machine access family' })).not.toBeInTheDocument();
  });
  it('sends the complete C# create-command envelope including explicit null targetId', async () => {
    view.canCoordinate = true; await open();
    fireEvent.click(screen.getByText('Create a focused source request'));
    fireEvent.change(screen.getByLabelText('Request title'), { target: { value: 'Find synthetic portal evidence' } });
    const family = screen.getByRole('combobox', { name: 'Source family' });
    await waitFor(() => expect(within(family).getByRole('option', { name: 'Traffic termination' })).toBeInTheDocument());
    fireEvent.change(family, { target: { value: 'traffic-termination' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create request—not send an email' }));
    await waitFor(() => expect(writes).toHaveLength(1));
    const body = JSON.parse(String(writes[0].options.body));
    expect(Object.keys(body).sort()).toEqual(['expectedRevision', 'fields', 'operation', 'targetId']);
    expect(body).toEqual({ operation: 'intake_create_request', targetId: null, expectedRevision: 2, fields: { title: 'Find synthetic portal evidence', familyId: 'traffic-termination', assignedTo: 'synthetic-demo:contributor' } });
    expect(await screen.findByRole('heading', { name: 'Saved partial response—not technical verification.' })).toBeInTheDocument();
  });
  it('requires save or explicit discard before Excel, system creation or request switching can omit unsaved answers', async () => {
    view.requests.push({ ...view.requests[0], id: 'request-b', title: 'A second focused request', systemIds: [] });
    await open(); fireEvent.click(screen.getByText('Add a deployment or evidence source'));
    fireEvent.change(screen.getByLabelText(/Who owns this system\? — Whole request/), { target: { value: 'An unsaved synthetic response' } });
    expect(screen.getByText('Your web answers have unsaved edits.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Prepare Excel questionnaire' })).toBeDisabled();
    expect(screen.getByLabelText('Preview a returned questionnaire (.xlsx)')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Add this separate system record' })).toBeDisabled();
    expect(screen.getByRole('button', { name: /A second focused request/ })).toBeDisabled();
    expect(screen.getByRole('combobox', { name: 'Assessment workspace' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Save partial response' })).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: 'Discard unsaved web edits' }));
    expect(screen.getByLabelText(/Who owns this system\? — Whole request/)).toHaveValue('');
    expect(screen.getByRole('button', { name: 'Prepare Excel questionnaire' })).toBeEnabled();
    expect(screen.getByRole('button', { name: /A second focused request/ })).toBeEnabled();
    expect(writes).toHaveLength(0);
  });
  it('preserves the save-or-discard guard across global navigation and warns on page unload', async () => {
    render(<App />); await screen.findByRole('heading', { name: 'Find the portal evidence routes' });
    fireEvent.change(screen.getByLabelText(/Who owns this system\? — Whole request/), { target: { value: 'Unsaved routing answer' } });
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeDisabled();
    for (const button of within(screen.getByRole('navigation', { name: 'Main navigation' })).getAllByRole('button')) expect(button).toBeDisabled();
    const unload = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(unload);
    expect(unload.defaultPrevented).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Discard unsaved web edits' }));
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeEnabled();
  });
  it('links the coordinator to governed Phase 1 report preparation rather than generating a report from the preview', async () => {
    view.canCoordinate = true; await open();
    fireEvent.click(screen.getByRole('button', { name: 'Open Phase 1 report preparation →' }));
    expect(navigate).toHaveBeenLastCalledWith('assessments', { assessment: assessmentId, stage: '4', from: 'intake' });
    expect(screen.getByText(/opening it does not bypass them/)).toBeInTheDocument();
    expect(writes).toHaveLength(0);
  });
  it('explains an unassigned assessment URL and lets a contributor clear it without a retry loop', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, options?: RequestInit) => {
      if (String(input) === base) return Response.json({ error: 'assessment_forbidden' }, { status: 403 });
      if (String(input) === '/api/assessments') return Response.json([]);
      return fetchMock(input, options);
    }));
    render(<IntakeWorkspace session={session} onNavigate={navigate} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('not available to your signed-in persona');
    expect(screen.queryByRole('button', { name: 'Reload requests' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Clear this link and choose my assignments' }));
    expect(await screen.findByRole('heading', { name: 'Start with an assigned request' })).toBeInTheDocument();
    expect(navigate).toHaveBeenLastCalledWith('intake', { assessment: '', request: '' });
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(writes).toHaveLength(0);
  });
  it('keeps excluded request history visible but disables every intake write surface', async () => {
    view.eligibleFamilyIds = []; await open();
    expect(screen.getByText('This request is outside the current assessment boundary.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save partial response' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Check response before handoff' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Prepare Excel questionnaire' })).toBeDisabled();
    expect(screen.getByLabelText('Preview a returned questionnaire (.xlsx)')).toBeDisabled();
    expect(screen.getByText('Two deployments are identified; technical behavior remains unestablished.')).toBeInTheDocument();
    expect(writes).toHaveLength(0);
  });
  it('rejects an oversized workbook before transmitting it to the application', async () => {
    await open();
    const file = new File([new Uint8Array(1024 * 1024 + 1)], 'too-large.xlsx');
    fireEvent.change(screen.getByLabelText('Preview a returned questionnaire (.xlsx)'), { target: { files: [file] } });
    expect(await screen.findByRole('alert')).toHaveTextContent('no larger than 1 MiB');
    expect(writes).toHaveLength(0);
  });
  it('preserves an explicit historical intake bookmark without fetching legacy assessment or graph data', async () => {
    history.replaceState(null, '', `#intake?assessment=${assessmentId}`);
    render(<App />);
    await screen.findByRole('heading', { name: 'Find the portal evidence routes' });
    expect(within(screen.getByRole('navigation', { name: 'Main navigation' })).getAllByRole('button').map(button => button.textContent)).toEqual(['My discovery requests', 'Specialist questionnaires']);
    expect(screen.queryByRole('button', { name: 'Estate overview' })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.every(([path]) => ['/api/session', '/api/assessments', base].includes(String(path)))).toBe(true);
  });
});
