import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { QuestionnaireWorkspace } from './QuestionnaireWorkspace';
import type { Session } from './contracts';
import type { QuestionnaireAnswer, QuestionnaireDetail, QuestionnaireList, QuestionnaireQuestion } from './questionnaire-contracts';

const assessmentId = 'assessment-' + 'c'.repeat(32);
const base = `/api/assessments/${assessmentId}/questionnaires`;
const assignmentId = 'questionnaire-a';
const deepLink = `#questionnaire?assessment=${assessmentId}&assignment=${assignmentId}`;
const actor: Session = { authenticated: true, role: 'contributor', synthetic: true, csrfToken: 'synthetic-questionnaire-csrf' };
const blank = (): QuestionnaireAnswer => ({ status: 'unanswered', text: '', evidenceRefs: [], rationale: '', nextOwner: '', nextDate: '', blocker: '', scheduleEffect: '', attestationOwner: '', attestationDate: '', attestationQualification: '' });
// C# exchange uses Dictionary<string,string>, unlike the normal array-valued answer DTO.
const workbookAnswer = (text: string) => ({ ...blank(), status: 'answered', text, evidenceRefs: 'synthetic-reference:one\nsynthetic-reference:two', assertedBy: 'Offline supplying function' });
const questionIds = [...Array.from({ length: 24 }, (_, index) => `CQ-${String(index + 1).padStart(2, '0')}`), 'SQ-01', 'SQ-02', 'SQ-03'];
const firstPrompt = 'What are the exact product or service name, instance or tenant name, environment, region, network zone, and business scope for every in-scope deployment of this system type?';
function questions(templateId = 'SRC-RFI-003'): QuestionnaireQuestion[] {
  return questionIds.map((sourceId, index) => ({ id: `${templateId}/${sourceId}`, sourceId, section: index < 3 ? 'Source identity and scope' : index < 24 ? 'Interface and evidence details' : 'TLS-specific questions', prompt: index === 0 ? firstPrompt : `Original synthetic question ${sourceId} for ${templateId}: identify the relevant source facts.`, whyItMatters: 'Preserve a source-backed assessment route.', responseType: sourceId === 'CQ-24' ? 'controlled_value' : sourceId === 'CQ-04' ? 'reference_list' : sourceId === 'CQ-02' ? 'long_text' : 'structured_profile', required: true, evidenceExpectation: 'An approved synthetic reference.', completionCriteria: 'An answer and supporting reference, or an explicit qualified gap.', allowedValues: sourceId === 'CQ-24' ? ['yes', 'yes_with_qualifications', 'no', 'pending'] : [] }));
}
function fixture(): QuestionnaireDetail {
  return { assessmentId, assessmentName: 'Synthetic TLS assessment', revision: 5, canEdit: true, canCoordinate: false, assignment: { id: assignmentId, title: 'Portal East source questionnaire', templateId: 'SRC-RFI-003', templateVersion: 'test-v1', deployment: { id: 'east', label: 'Synthetic portal east', product: 'NGINX', environment: 'test-east' }, assignedTo: 'synthetic-demo:contributor', status: 'draft', questionCount: 27, answeredCount: 0, template: { id: 'SRC-RFI-003', title: 'Identify the authoritative TLS and mutual-TLS termination configurations across load balancers, proxies, API gateways, ingress controllers, and application-delivery platforms', systemType: 'TLS termination and application delivery', examples: ['F5 BIG-IP', 'NGINX', 'HAProxy', 'Kong'], questions: questions() }, scheduleEffects: ['none', 'monitor', 'blocks_collection'], answers: {}, submission: null }, validation: { canSubmit: false, issues: [{ questionId: 'SRC-RFI-003/CQ-01', field: 'status', message: 'Provide an explicit response state.' }] }, receipt: null };
}
let detail: QuestionnaireDetail; let list: QuestionnaireList; let session: Session; let posts: { path: string; options: RequestInit }[]; let fail: '' | 'conflict' | 'ambiguous';
const navigate = vi.fn((page: string, params: Record<string, string> = {}) => { window.location.hash = `${page}?${new URLSearchParams(params)}`; });
const fetchMock = vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
  const path = String(input);
  if (path === '/api/session') {
    if (options.method === 'POST') { posts.push({ path, options }); const body = JSON.parse(String(options.body)); session = { ...actor, role: body.role }; }
    return Response.json(session);
  }
  if (path === '/api/assessments') return Response.json([{ id: assessmentId, name: detail.assessmentName, revision: detail.revision, stage: 1, mode: 'fresh', synthetic: true }]);
  if (options.method === 'POST') {
    posts.push({ path, options });
    if (fail === 'ambiguous') { fail = ''; throw new TypeError('Interrupted delivery'); }
    if (fail === 'conflict') { fail = ''; return Response.json({ error: 'assessment_revision_changed' }, { status: 409 }); }
    if (path === `${base}/exports/${assignmentId}`) return Response.json({ exportId: 'export-a', downloadUrl: `${base}/exports/export-a/download`, revision: ++detail.revision });
    if (path.startsWith(`${base}/imports/${assignmentId}?`)) return Response.json({ revision: ++detail.revision, import: { id: 'import-a', assignmentId, exportId: 'export-a', committed: false, changes: [{ questionId: 'SRC-RFI-003/CQ-01', baseline: workbookAnswer('Exported owner'), current: workbookAnswer('New web owner'), returned: workbookAnswer('Offline owner'), state: 'conflict' }] } });
    if (path === `${base}/imports/import-a/commit`) { detail.assignment.answers['SRC-RFI-003/CQ-01'] = { ...blank(), status: 'answered', text: 'Offline owner', assertedBy: 'unverified:offline-author', recordedBy: 'synthetic-demo:contributor' }; detail.receipt = 'Returned questionnaire saved as a draft.'; detail.revision++; return Response.json(detail); }
    const body = JSON.parse(String(options.body));
    if (JSON.stringify(Object.keys(body).sort()) !== JSON.stringify(['expectedRevision', 'fields', 'operation', 'targetId'])) return Response.json({ error: 'body_fields_invalid' }, { status: 400 });
    detail.revision++;
    if (body.operation === 'questionnaire_create') { list.revision++; list.assignments.push({ ...detail.assignment, id: 'questionnaire-b', title: body.fields.title, templateId: body.fields.templateId, deployment: { id: 'west', ...body.fields.deployment }, assignedTo: body.fields.assignedTo }); return Response.json(list); }
    if (body.operation === 'questionnaire_save') { Object.assign(detail.assignment.answers, body.fields.answers); detail.receipt = 'Draft saved. Submission and review remain separate.'; }
    if (body.operation === 'questionnaire_submit') { detail.assignment.status = 'submitted'; detail.canEdit = false; detail.assignment.submission = { submittedAt: '2026-09-08T12:00:00Z', submittedBy: 'synthetic-demo:contributor', unresolvedQuestionIds: [] }; detail.receipt = 'Your response has been received.'; }
    return Response.json(detail);
  }
  if (path === base) return Response.json(list);
  if (path === `${base}/${assignmentId}`) return Response.json(detail);
  throw new Error(`Unexpected fixture route: ${path}`);
});
beforeEach(() => {
  detail = fixture(); session = actor; posts = []; fail = ''; navigate.mockClear(); fetchMock.mockClear();
  list = { assessmentId, assessmentName: detail.assessmentName, revision: 5, canCoordinate: true, assignments: [detail.assignment], catalog: { available: true, catalogId: 'test-catalog', catalogVersion: 'test-v1', templates: Array.from({ length: 27 }, (_, index) => { const id = `SRC-RFI-${String(index + 1).padStart(3, '0')}`; return { ...detail.assignment.template, id, systemType: `Synthetic source class ${index + 1}`, questions: questions(id) }; }) } };
  history.replaceState(null, '', deepLink);
  vi.stubGlobal('fetch', fetchMock); vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined);
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
async function open() { render(<QuestionnaireWorkspace session={actor} mode="respondent" onNavigate={navigate} />); await screen.findByRole('heading', { name: 'Synthetic portal east' }); }
function topButton(name: string) { return screen.getAllByRole('button', { name })[0]; }

describe('complete assigned source questionnaire', () => {
  it('opens the exact deployment and renders every original question without coordinator screens', async () => {
    await open();
    expect(screen.getByRole('group', { name: new RegExp(firstPrompt.replace(/[?]/g, '\\?')) })).toBeInTheDocument();
    expect(screen.getAllByRole('combobox', { name: /Response state —/ })).toHaveLength(27);
    expect(screen.getByLabelText('Requested profile details — SQ-03')).toBeInTheDocument();
    expect(screen.getByText(/This is the original detailed specialist questionnaire/)).toHaveTextContent('Any collection or system access must be agreed separately with the appropriate owner.');
    expect(screen.getAllByLabelText(/Supporting information references —/)).toHaveLength(27);
    expect(screen.queryByLabelText(/Supporting evidence references/)).not.toBeInTheDocument();
    expect(screen.getAllByText('Original supporting-information requirement:')).toHaveLength(27);
    expect(screen.getAllByText(/An approved synthetic reference/)).toHaveLength(27);
    expect(screen.getByText('SRC-RFI-003 · 27 original questions')).toBeInTheDocument();
    expect(screen.getByText('About this questionnaire · scope, examples and original definition').closest('details')).not.toHaveAttribute('open');
    expect(screen.getByText('Jump to a section').closest('details')).not.toHaveAttribute('open');
    expect(screen.queryByLabelText('Assessment')).not.toBeInTheDocument();
    expect(screen.queryByText('Create questionnaire assignment')).not.toBeInTheDocument();
    expect(screen.queryByText('Stage a synthetic source observation')).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([`${base}/${assignmentId}`]);
  });
  it('saves only changed answers, allows an incomplete draft and omits server attribution', async () => {
    detail.assignment.answers['SRC-RFI-003/CQ-02'] = { ...blank(), status: 'answered', text: 'Existing attributed input', assertedBy: 'unverified:offline-author', recordedBy: 'another-importer' };
    await open();
    const input = screen.getByLabelText('Requested profile details — CQ-01');
    expect(input).toHaveAttribute('maxlength', '8192');
    fireEvent.change(input, { target: { value: 'Product: NGINX\nRegion: unknown' } });
    fireEvent.change(screen.getByLabelText('Supporting information references — CQ-01'), { target: { value: '  synthetic-catalog:portal-east  \n\n' } });
    expect(topButton('Review and submit')).toBeDisabled();
    fireEvent.click(topButton('Save draft'));
    await screen.findByText('Draft saved. Submission and review remain separate.');
    expect(posts).toHaveLength(1);
    const body = JSON.parse(String(posts[0].options.body));
    expect(Object.keys(body).sort()).toEqual(['expectedRevision', 'fields', 'operation', 'targetId']);
    expect(Object.keys(body.fields.answers)).toEqual(['SRC-RFI-003/CQ-01']);
    expect(body.fields.answers['SRC-RFI-003/CQ-01']).toMatchObject({ status: 'answered', text: 'Product: NGINX\nRegion: unknown', evidenceRefs: ['synthetic-catalog:portal-east'] });
    expect(body.fields.answers['SRC-RFI-003/CQ-01']).not.toHaveProperty('recordedBy');
    expect(body.fields.answers['SRC-RFI-003/CQ-01']).not.toHaveProperty('assertedBy');
    expect(detail.assignment.answers['SRC-RFI-003/CQ-02'].assertedBy).toBe('unverified:offline-author');
    expect(topButton('Review and submit')).toBeEnabled();
  });
  it('does not create an API write for an unchanged draft', async () => {
    await open(); fireEvent.click(topButton('Save draft'));
    expect(screen.getByText(/No answer changes to save/)).toBeInTheDocument();
    expect(posts).toHaveLength(0);
  });
  it('records an unknown as a partial draft and shows exact missing submission requirements', async () => {
    detail.validation.issues = [{ questionId: 'SRC-RFI-003/CQ-01', field: 'nextOwner', message: 'Name the next responsible function.' }, { questionId: 'SRC-RFI-003/CQ-01', field: 'nextDate', message: 'Provide an expected follow-up date.' }];
    await open();
    fireEvent.change(screen.getByLabelText('Response state — CQ-01'), { target: { value: 'unknown' } });
    fireEvent.change(screen.getByLabelText('Reason or qualification — CQ-01'), { target: { value: 'The original recipient does not have the source inventory.' } });
    expect(screen.getByLabelText('Next responsible person or function — CQ-01')).toHaveValue('');
    expect(within(screen.getByLabelText('Schedule effect — CQ-01')).getByRole('option', { name: 'Blocks collection' })).toHaveValue('blocks_collection');
    fireEvent.click(topButton('Save draft')); await screen.findByText('Draft saved. Submission and review remain separate.');
    fireEvent.click(topButton('Review and submit'));
    expect(screen.getByRole('region', { name: 'Questionnaire submission requirements' })).toHaveTextContent('Name the next responsible function.');
    expect(screen.getAllByRole('button', { name: 'Submit this questionnaire' }).every(button => (button as HTMLButtonElement).disabled)).toBe(true);
    expect(posts).toHaveLength(1);
  });
  it('renders the original controlled attestation choices without creating an approval action', async () => {
    await open();
    fireEvent.change(screen.getByLabelText('Select an allowed response — CQ-24'), { target: { value: 'yes_with_qualifications' } });
    expect(screen.getByLabelText('Response state — CQ-24')).toHaveValue('answered');
    expect(screen.getByLabelText('Attestation qualifications — CQ-24')).toBeInTheDocument();
    expect(screen.getByText(/A webform value is not an authenticated gate decision/)).toBeInTheDocument();
    expect(posts).toHaveLength(0);
  });
  it('submits only from a saved review and finishes with no further respondent work required', async () => {
    detail.validation = { canSubmit: true, issues: [] };
    for (const question of detail.assignment.template.questions) detail.assignment.answers[question.id] = { ...blank(), status: 'not_applicable', rationale: 'Synthetic bounded scope exclusion.' };
    await open(); fireEvent.click(topButton('Review and submit'));
    expect(posts).toHaveLength(0);
    expect(screen.getByRole('region', { name: 'Review saved questionnaire' })).toHaveTextContent('Read the answers below before submitting.');
    fireEvent.click(topButton('Submit this questionnaire'));
    expect(await screen.findByRole('heading', { name: 'Your questionnaire has been submitted.' })).toBeInTheDocument();
    expect(screen.getByText(/No further response is required from you now/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Save draft' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Submit this questionnaire' })).not.toBeInTheDocument();
    expect(JSON.parse(String(posts[0].options.body))).toMatchObject({ operation: 'questionnaire_submit', targetId: assignmentId, fields: {} });
  });
  it('keeps the exact authenticated questionnaire deep link through sign-in', async () => {
    session = { authenticated: false, role: null, csrfToken: null, synthetic: true };
    render(<App />); await screen.findByRole('heading', { name: 'Open the workspace' });
    expect(screen.getByLabelText('Or sign in as a contributing / reviewing persona')).toHaveValue('contributor');
    fireEvent.change(screen.getByLabelText('Synthetic demo password'), { target: { value: 'synthetic-demo-only' } });
    fireEvent.click(screen.getByRole('button', { name: 'Open workspace' }));
    expect(await screen.findByRole('heading', { name: 'Synthetic portal east' })).toBeInTheDocument();
    expect(window.location.hash).toBe(deepLink);
    expect(screen.queryByRole('navigation', { name: 'Main navigation' })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([path]) => path === '/api/assessments')).toBe(false);
  });
  it('preserves an unsaved form against hash navigation and allows a new destination after explicit discard', async () => {
    render(<App />); await screen.findByRole('heading', { name: 'Synthetic portal east' });
    fireEvent.change(screen.getByLabelText('Requested profile details — CQ-01'), { target: { value: 'Unsaved synthetic deployment' } });
    expect(screen.getByRole('button', { name: 'My questionnaires' })).toBeDisabled();
    await act(async () => { window.location.hash = '#questionnaires'; window.dispatchEvent(new HashChangeEvent('hashchange')); });
    expect(window.location.hash).toBe(deepLink);
    expect(screen.getByRole('alert')).toHaveTextContent('Navigation was paused');
    expect(screen.getByLabelText('Requested profile details — CQ-01')).toHaveValue('Unsaved synthetic deployment');
    fireEvent.click(screen.getByRole('button', { name: 'Discard unsaved questionnaire edits' }));
    fireEvent.click(screen.getByRole('button', { name: 'My questionnaires' }));
    await screen.findByRole('heading', { name: 'Source questionnaires' });
    expect(window.location.hash).toContain('#questionnaires');
    expect(posts).toHaveLength(0);
  });
  it('preserves an unsaved form against a popstate route change', async () => {
    render(<App />); await screen.findByRole('heading', { name: 'Synthetic portal east' });
    fireEvent.change(screen.getByLabelText('Requested profile details — CQ-01'), { target: { value: 'Keep this draft' } });
    await act(async () => { history.replaceState(null, '', '#questionnaires'); window.dispatchEvent(new PopStateEvent('popstate')); });
    expect(window.location.hash).toBe(deepLink);
    expect(screen.getByLabelText('Requested profile details — CQ-01')).toHaveValue('Keep this draft');
    expect(screen.getByRole('alert')).toHaveTextContent('Navigation was paused');
  });
  it('reuses the exact idempotent write after interrupted delivery and keeps edits after a conflict', async () => {
    await open();
    fireEvent.change(screen.getByLabelText('Requested profile details — CQ-01'), { target: { value: 'Synthetic east' } });
    expect(screen.getByLabelText('Requested profile details — CQ-01')).toHaveValue('Synthetic east');
    expect(screen.getByText('Your latest edits are not saved.')).toBeInTheDocument();
    fail = 'ambiguous'; fireEvent.click(topButton('Save draft'));
    fireEvent.click(await screen.findByRole('button', { name: 'Retry original operation' }));
    await screen.findByText('Draft saved. Submission and review remain separate.');
    expect(posts[0].options.body).toBe(posts[1].options.body); expect(posts[0].options.headers).toEqual(posts[1].options.headers);
    fireEvent.change(screen.getByLabelText('Requested profile details — CQ-01'), { target: { value: 'Preserved revision conflict answer' } });
    fail = 'conflict'; fireEvent.click(topButton('Save draft'));
    expect(await screen.findByRole('alert')).toHaveTextContent('no competing response was overwritten');
    expect(screen.getByLabelText('Requested profile details — CQ-01')).toHaveValue('Preserved revision conflict answer');
    expect(topButton('Save draft')).toBeDisabled();
  });
  it('exports the full assignment and explicitly reconciles competing returned answers as a draft', async () => {
    await open(); fireEvent.click(screen.getByText('Work offline in Excel'));
    fireEvent.click(screen.getByRole('button', { name: 'Prepare Excel questionnaire' }));
    expect(await screen.findByRole('link', { name: 'Download prepared questionnaire' })).toHaveAttribute('href', `${base}/exports/export-a/download`);
    const file = new File(['synthetic xlsx bytes'], 'returned.xlsx');
    fireEvent.change(screen.getByLabelText('Preview returned questionnaire (.xlsx, maximum 1 MiB)'), { target: { files: [file] } });
    const comparison = await screen.findByRole('region', { name: 'Returned questionnaire comparison' });
    expect(within(comparison).getByRole('button', { name: 'Apply reviewed answers as a draft' })).toBeDisabled();
    expect(comparison).toHaveTextContent('Offline owner');
    expect(comparison).toHaveTextContent('synthetic-reference:one');
    expect(comparison).toHaveTextContent('synthetic-reference:two');
    fireEvent.change(within(comparison).getByRole('combobox'), { target: { value: 'returned' } });
    fireEvent.click(within(comparison).getByRole('button', { name: 'Apply reviewed answers as a draft' }));
    await screen.findByText('Returned questionnaire saved as a draft.');
    expect(screen.getByLabelText('Requested profile details — CQ-01')).toHaveValue('Offline owner');
    expect(screen.queryByText('Your latest edits are not saved.')).not.toBeInTheDocument();
    expect(posts[1].options.body).toBe(file);
    expect(JSON.parse(String(posts[2].options.body))).toMatchObject({ choices: { 'SRC-RFI-003/CQ-01': 'returned' } });
    fireEvent.change(screen.getByLabelText('Your answer — CQ-02'), { target: { value: 'A separate new answer' } });
    fireEvent.click(topButton('Save draft')); await waitFor(() => expect(posts).toHaveLength(4));
    expect(Object.keys(JSON.parse(String(posts[3].options.body)).fields.answers)).toEqual(['SRC-RFI-003/CQ-02']);
    expect(detail.assignment.answers['SRC-RFI-003/CQ-01'].assertedBy).toBe('unverified:offline-author');
  });
  it('separates coordinator assignment creation and exposes all 27 original catalog templates', async () => {
    history.replaceState(null, '', `#questionnaires?assessment=${assessmentId}`);
    render(<QuestionnaireWorkspace session={{ ...actor, role: 'analyst' }} mode="list" onNavigate={navigate} />);
    fireEvent.click(await screen.findByText('Assign a complete questionnaire'));
    const templates = screen.getByLabelText('Original source questionnaire');
    expect(within(templates).getAllByRole('option')).toHaveLength(28);
    fireEvent.change(templates, { target: { value: 'SRC-RFI-003' } });
    fireEvent.change(screen.getByLabelText('Deployment or instance name'), { target: { value: 'Synthetic portal west' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create questionnaire assignment' }));
    expect(await screen.findByRole('heading', { name: 'Synthetic portal west' })).toBeInTheDocument();
    expect(JSON.parse(String(posts[0].options.body))).toMatchObject({ operation: 'questionnaire_create', targetId: null, fields: { templateId: 'SRC-RFI-003', deployment: { label: 'Synthetic portal west', product: '', environment: '' } } });
    expect(screen.queryByLabelText('Requested profile details — CQ-01')).not.toBeInTheDocument();
  });
  it('explains an unauthorized direct link without falling back to another person’s form', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Response.json({ error: 'assessment_forbidden' }, { status: 403 })));
    render(<QuestionnaireWorkspace session={actor} mode="respondent" onNavigate={navigate} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('not available to your signed-in identity');
    expect(screen.queryByLabelText('Requested profile details — CQ-01')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Choose my own assignment' })).toBeInTheDocument();
  });
});
