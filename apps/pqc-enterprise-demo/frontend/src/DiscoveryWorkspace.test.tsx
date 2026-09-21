import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { DiscoveryWorkspace } from './DiscoveryWorkspace';
import { DiscoveryReportSection } from './DiscoveryReportSection';
import type { Session } from './contracts';
import type { DiscoveryDetail, DiscoveryList, DiscoveryRecognition } from './discovery-contracts';

const assessmentId = `assessment-${'c'.repeat(32)}`;
const base = `/api/assessments/${assessmentId}/discovery`;
const requestId = 'discovery-one';
const deepLink = `#discovery-request?assessment=${assessmentId}&request=${requestId}`;
const actor: Session = { authenticated: true, role: 'contributor', synthetic: true, csrfToken: 'synthetic-discovery-csrf' };
const firstPrompt = 'Which products or services in this software class do you know are used?';
const lastPrompt = 'Are there any access restrictions, information-sharing considerations, or known gaps we should understand?';
const legacyPrompt = 'Are there known restrictions or gaps we should account for before requesting evidence?';
const guidance = {
  introduction: 'Help us identify the software used for this function, the teams familiar with it, and any existing information we should start with. Product names, document references, referrals and not sure are useful answers.',
  handlingNotice: 'You do not need to create documents or demonstrate compliance. Do not submit credentials or sensitive files. Any later collection or system access will be agreed separately with the appropriate owner.',
  reviewNotice: 'A partial answer, referral or explicit unknown is enough to submit. The assessment team owns follow-up; submitting does not authorize access or complete the assessment.',
  submissionReceipt: 'Your response has been received. The assessment team will review it and coordinate any follow-up. No further response is required now.',
  legacyNotice: '',
};
const legacyNotice = 'This saved form retains its original questions. References to evidence mean existing information that may help the assessment; you do not need to produce documents, establish policy or authorize access.';
let detail: DiscoveryDetail; let list: DiscoveryList; let session: Session;
let posts: { path: string; options: RequestInit }[]; let failure: '' | 'ambiguous' | 'conflict' | 'access';
const navigate = vi.fn((page: string, params: Record<string, string> = {}) => { window.location.hash = `${page}?${new URLSearchParams(params)}`; });
const fetchMock = vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
  const path = String(input);
  if (path === '/api/session') { if (options.method === 'POST') { posts.push({ path, options }); session = { ...actor, role: JSON.parse(String(options.body)).role }; } return Response.json(session); }
  if (path === '/api/assessments') return Response.json([{ id: assessmentId, name: detail.assessmentName }]);
  if (options.method === 'POST') {
    posts.push({ path, options });
    if (failure === 'ambiguous') { failure = ''; throw new TypeError('Interrupted delivery'); }
    if (failure === 'conflict') { failure = ''; return Response.json({ error: 'assessment_revision_changed' }, { status: 409 }); }
    if (path === `${base}/exports/${requestId}`) return Response.json({ exportId: 'export-one', downloadUrl: `${base}/exports/export-one/download`, revision: ++detail.revision });
    if (path.startsWith(`${base}/imports/${requestId}?`)) return Response.json({ revision: ++detail.revision, import: { id: 'import-one', changes: [{ questionId: 'DQ-01', baseline: { status: 'answered', text: 'At export', reference: '' }, current: { status: 'answered', text: 'Saved web answer', reference: '' }, returned: { status: 'referral', text: 'Offline platform team', reference: 'synthetic:team' }, state: 'conflict' }] } });
    if (path === `${base}/imports/import-one/commit`) { detail.request.answers['DQ-01'] = { status: 'referral', text: 'Offline platform team', reference: 'synthetic:team', assertedBy: 'unverified:offline' }; detail.revision++; return Response.json(detail); }
    const body = JSON.parse(String(options.body));
    if (JSON.stringify(Object.keys(body).sort()) !== JSON.stringify(['expectedRevision', 'fields', 'operation', 'targetId'])) return Response.json({ error: 'body_fields_invalid' }, { status: 400 });
    detail.revision++; list.revision = detail.revision;
    if (body.operation === 'discovery_create') { list.requests.push({ ...detail.request, id: 'discovery-two', title: body.fields.title }); return Response.json(list); }
    if (body.operation === 'discovery_save') { Object.assign(detail.request.answers, body.fields.answers || {}); if (body.fields.productRefs) detail.request.productRefs = body.fields.productRefs.map((item: Record<string, string>, index: number) => ({ ...item, id: item.id || `product-${index}` })); detail.validation = { canSubmit: true, issues: [] }; }
    if (body.operation === 'discovery_submit') { detail.request.status = 'submitted'; detail.canEdit = false; detail.request.receipt = 'The assessment coordinator reviews this routing response next.'; }
    if (body.operation === 'discovery_update_standard') { Object.assign(list.standards[0], body.fields, { revision: list.revision }); return Response.json(list); }
    if (body.operation === 'discovery_add_product') { list.investigations[0].productRefs = [{ ...body.fields, id: 'identified-east' }]; return Response.json(list); }
    if (body.operation === 'discovery_update_investigation') { Object.assign(list.investigations[0], body.fields); return Response.json(list); }
    return Response.json(detail);
  }
  if (path === base) return Response.json(list);
  if (path === `${base}/${requestId}`) return failure === 'access' ? Response.json({ error: 'assessment_forbidden' }, { status: 403 }) : Response.json(detail);
  throw new Error(`Unexpected test route: ${path}`);
});
beforeEach(() => {
  session = actor; posts = []; failure = ''; navigate.mockClear(); fetchMock.mockClear();
  detail = { assessmentId, assessmentName: 'Synthetic routing assessment', revision: 1, canEdit: true, canCoordinate: false, guidance: { ...guidance }, validation: { canSubmit: false, issues: ['Provide one useful answer, referral or explicit unknown before submitting.'] }, boundary: 'Synthetic only', request: { id: requestId, title: 'Identify encrypted traffic sources', familyId: 'traffic-termination', familyName: 'TLS termination', templateVersion: 'pqc.discovery.v2', questions: [firstPrompt, 'Which team or contact should we speak with?', 'Is there an existing inventory, configuration report or other reference we can start from?', 'Which application, business service or environment does your answer concern, if known?', lastPrompt].map((prompt, index) => ({ id: `DQ-0${index + 1}`, prompt, whyItMatters: 'Find the right route without inventing enterprise conclusions.', usefulResponse: index === 4 ? 'Share what you know. None known or not sure is sufficient; you do not need to establish policy or resolve the issue yourself.' : 'A product name, referral or explicit unknown is useful.', examples: index === 0 ? ['F5 BIG-IP', 'NGINX', 'HAProxy'] : [] })), examples: ['F5 BIG-IP', 'NGINX', 'HAProxy'], assignedTo: 'synthetic-demo:contributor', status: 'draft', answers: {}, productRefs: [], submission: null, receipt: null } };
  list = { assessmentId, assessmentName: detail.assessmentName, revision: 1, canCoordinate: true, canResearch: true, canStageEvidence: false, canAdmitEvidence: false, canReviewEvidence: false, families: [{ id: 'traffic-termination', name: 'TLS termination', examples: detail.request.examples }], investigators: [{ id: 'synthetic-demo:reviewer', label: 'Technical reviewer' }], requests: [structuredClone(detail.request)], standards: [{ id: 'assessment-evidence', title: 'Assessment and evidence proposal', version: 'v1', status: 'draft', purpose: 'Prepare the assessment basis.', proposalText: 'PROPOSED — NOT ADOPTED\nDistinguish observed facts and testimony.', existingRequirementStatus: 'unassessed', existingRequirementRefs: [], authorityStatus: 'unassigned', proposedAuthority: '', conflictReviewStatus: 'unassessed', conflictNote: '' }], investigations: [{ id: 'investigation-one', requestId, familyId: 'traffic-termination', productRefIds: [], productRefs: [], assignedTo: 'synthetic-demo:reviewer', status: 'planned', purpose: 'Identify the termination interface', researchSummary: '', proposedMethod: '', documentationRefs: [], limitation: '', intakeRequestId: null, evidenceReviews: [] }], boundary: 'Synthetic only' };
  history.replaceState(null, '', deepLink); vi.stubGlobal('fetch', fetchMock); vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined);
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
async function open() { render(<DiscoveryWorkspace session={actor} mode="respondent" onNavigate={navigate} />); await screen.findByRole('heading', { name: firstPrompt }); }
function top(name: string) { return screen.getAllByRole('button', { name })[0]; }
async function openStaff() { history.replaceState(null, '', `#discovery?assessment=${assessmentId}`); render(<DiscoveryWorkspace session={{ ...actor, role: 'analyst' }} mode="list" onNavigate={navigate} />); await screen.findByRole('heading', { name: 'Requests and returned responses' }); }

function recognitionFixture(): DiscoveryRecognition {
  const domain = { id: 'traffic', name: 'Encrypted traffic and service delivery', families: [
    { id: 'traffic-termination', name: 'TLS termination', examples: Array.from({ length: 12 }, (_, index) => ({ name: `Synthetic traffic product ${index + 1}`, kind: ['COTS', 'SaaS', 'Open source', 'Hardware/platform'][index % 4], url: `https://example.com/traffic/${index + 1}`, ...(index === 0 ? { note: 'Synthetic fixture for product recognition.' } : {}) })) },
    { id: 'traffic-observation', name: 'Traffic observation', examples: [{ name: 'Synthetic traffic observer', kind: 'COTS', url: 'https://example.com/observer' }] },
  ] };
  const identity = { id: 'identity', name: 'Identity and trust', families: [{ id: 'identity-platforms', name: 'Identity platforms', examples: [{ name: 'Synthetic identity service', kind: 'SaaS', url: 'https://example.com/identity' }] }] };
  return { catalogVersion: 'pqc.recognition.v1', catalogSha256: 'a'.repeat(64), reviewedAt: '2026-09-10', familyId: 'traffic-termination', boundary: 'Recognition examples only; these do not confirm company product selections, deployment, or PQC support. COTS means commercial off-the-shelf; OTS means off-the-shelf; SaaS means software as a service.', domain, domains: [domain, identity, ...Array.from({ length: 8 }, (_, index) => ({ id: `domain-${index + 3}`, name: `Synthetic domain ${index + 3}`, families: [{ id: `family-${index + 3}`, name: `Synthetic software class ${index + 3}`, examples: [{ name: `Synthetic domain product ${index + 3}`, kind: 'COTS', url: `https://example.com/domain/${index + 3}` }] }] }))] };
}

function selectedRecognitionExamples() {
  const reference = screen.getByRole('region', { name: 'Products you may recognize' });
  return within(reference.querySelector<HTMLElement>(':scope > .d-recognition-examples')!);
}

describe('current discovery recognition reference', () => {
  beforeEach(() => { detail.recognition = recognitionFixture(); });

  it('shows the domain and every selected-family product before the first of five unchanged questions', async () => {
    const original = structuredClone(detail.request);
    await open();
    const domain = screen.getByRole('heading', { name: detail.recognition!.domain.name });
    const software = screen.getByRole('heading', { name: 'TLS termination', level: 2 });
    expect(domain.compareDocumentPosition(software) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const reference = screen.getByRole('region', { name: 'Products you may recognize' });
    expect(reference.compareDocumentPosition(screen.getByRole('heading', { name: firstPrompt })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(reference).getByText(detail.recognition!.boundary)).toBeVisible();
    for (const example of detail.recognition!.domain.families[0].examples) {
      const link = selectedRecognitionExamples().getByRole('link', { name: example.name });
      expect(link).toBeVisible(); expect(link).toHaveAttribute('href', example.url);
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    }
    expect(selectedRecognitionExamples().getAllByRole('link')).toHaveLength(12);
    expect(screen.getAllByRole('combobox', { name: /What can you tell us\? —/ })).toHaveLength(5);
    expect(screen.getByText('0 software / deployment entries')).toBeVisible();
    expect(detail.request).toEqual(original); expect(posts).toHaveLength(0);
  });

  it('expands sibling families and any of the ten domains without changing the request or marking it dirty', async () => {
    const original = structuredClone(detail.request); const dirtyChange = vi.fn();
    render(<DiscoveryWorkspace session={actor} mode="respondent" onNavigate={navigate} onDirtyChange={dirtyChange} />);
    await screen.findByRole('heading', { name: firstPrompt });
    const siblingsSummary = screen.getByText('Explore other software classes in Encrypted traffic and service delivery');
    const siblings = siblingsSummary.closest('details')!;
    expect(siblings).not.toHaveAttribute('open');
    expect(within(siblings).getByRole('link', { name: 'Synthetic traffic observer' })).not.toBeVisible();
    fireEvent.click(siblingsSummary);
    expect(within(siblings).getByRole('link', { name: 'Synthetic traffic observer' })).toBeVisible();
    const catalog = screen.getByText('Browse all 10 PQC discovery domains').closest('details')!;
    expect(catalog).not.toHaveAttribute('open');
    fireEvent.click(screen.getByText('Browse all 10 PQC discovery domains'));
    expect(catalog).toHaveAttribute('open');
    for (const domain of detail.recognition!.domains) expect(within(catalog).getByText(domain.name, { exact: false, selector: 'summary' })).toBeVisible();
    const identity = within(catalog).getByText('Identity and trust', { exact: false, selector: 'summary' });
    expect(within(catalog).getByRole('link', { name: 'Synthetic identity service' })).not.toBeVisible();
    fireEvent.click(identity);
    expect(screen.getByRole('link', { name: 'Synthetic identity service' })).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Identity platforms' })).toBeVisible();
    fireEvent.click(within(catalog).getByText('Synthetic domain 10', { exact: false, selector: 'summary' }));
    expect(screen.getByRole('link', { name: 'Synthetic domain product 10' })).toBeVisible();
    fireEvent.click(screen.getByText('Browse all 10 PQC discovery domains'));
    expect(screen.getByText('Draft · not submitted')).toBeVisible();
    expect(screen.queryByLabelText('Software / product name 1')).not.toBeInTheDocument();
    expect(dirtyChange).not.toHaveBeenCalledWith(true);
    expect(detail.request).toEqual(original); expect(posts).toHaveLength(0); expect(navigate).not.toHaveBeenCalled();
  });

  it('keeps unsaved answers and multiple explicit products while browsing and changing either theme', async () => {
    render(<App />); await screen.findByRole('heading', { name: firstPrompt });
    fireEvent.change(screen.getByLabelText('Your response to DQ-01'), { target: { value: 'Ask our platform team.' } });
    for (const index of [1, 2]) {
      fireEvent.click(screen.getByRole('button', { name: index === 1 ? 'Add software or deployment' : 'Add another software or deployment' }));
      fireEvent.change(screen.getByLabelText(`Software / product name ${index}`), { target: { value: `Explicit deployment ${index}` } });
    }
    fireEvent.click(screen.getByText('Browse all 10 PQC discovery domains'));
    fireEvent.click(screen.getByText('Identity and trust', { exact: false, selector: 'summary' }));
    for (const mode of ['light', 'dark']) {
      fireEvent.change(screen.getByRole('combobox', { name: 'Theme' }), { target: { value: mode } });
      expect(screen.getByRole('region', { name: 'Products you may recognize' }).closest('.app-theme')).toHaveAttribute('data-theme', mode);
      expect(selectedRecognitionExamples().getByRole('link', { name: 'Synthetic traffic product 12' })).toBeVisible();
      expect(screen.getByRole('link', { name: 'Synthetic identity service' })).toBeVisible();
      expect(screen.getByLabelText('Your response to DQ-01')).toHaveValue('Ask our platform team.');
      expect(screen.getByLabelText('Software / product name 1')).toHaveValue('Explicit deployment 1');
      expect(screen.getByLabelText('Software / product name 2')).toHaveValue('Explicit deployment 2');
      expect(screen.queryByLabelText('Software / product name 3')).not.toBeInTheDocument();
      expect(window.location.hash).toBe(deepLink);
    }
    expect(posts).toHaveLength(0); expect(detail.request.answers).toEqual({}); expect(detail.request.productRefs).toEqual([]);
  });

  it('renders invalid or non-HTTPS sources as readable names without clickable links', async () => {
    const invalidSources = ['javascript:alert(1)', 'http://example.com/product', 'https://', 'https://user:password@example.com/', 'https://example.com/\nproduct', 'https://example.com\\@other.example/'];
    detail.recognition!.domain.families[0].examples = invalidSources.map((url, index) => ({ name: `Unsafe source ${index + 1}`, kind: 'COTS', url }));
    await open();
    const reference = screen.getByRole('region', { name: 'Products you may recognize' });
    for (let index = 1; index <= invalidSources.length; index++) {
      expect(within(reference).getAllByText(`Unsafe source ${index}`)[0]).toBeVisible();
      expect(within(reference).queryByRole('link', { name: `Unsafe source ${index}` })).not.toBeInTheDocument();
    }
    expect(posts).toHaveLength(0);
  });

  it('keeps the catalog version separate from historical question examples and saved answers', async () => {
    detail.request.templateVersion = 'pqc.discovery.v1'; detail.request.questions[4].prompt = legacyPrompt;
    detail.request.answers['DQ-05'] = { status: 'unknown', text: 'Original saved answer', reference: '' };
    detail.guidance.legacyNotice = legacyNotice;
    const original = structuredClone(detail.request);
    await open();
    expect(selectedRecognitionExamples().getByRole('link', { name: 'Synthetic traffic product 12' })).toBeVisible();
    const examples = screen.getByText('Examples saved with this question').closest('details')!;
    expect(examples).not.toHaveAttribute('open');
    fireEvent.click(screen.getByText('Examples saved with this question'));
    expect(within(examples).getByText(/F5 BIG-IP; NGINX; HAProxy/)).toBeVisible();
    fireEvent.click(screen.getByText('About this recognition reference'));
    expect(screen.getByText(/Reference version pqc.recognition.v1/)).toBeVisible();
    expect(screen.getByText('a'.repeat(64))).toBeVisible();
    expect(screen.getByRole('heading', { name: legacyPrompt })).toBeVisible();
    expect(screen.getByLabelText('Your response to DQ-05')).toHaveValue('Original saved answer');
    expect(detail.request).toEqual(original); expect(posts).toHaveLength(0);
  });

  it.each([undefined, null])('retains the original examples when the current reference is %s', async recognition => {
    detail.recognition = recognition;
    await open();
    expect(screen.queryByRole('heading', { name: 'Products you may recognize' })).not.toBeInTheDocument();
    expect(screen.queryByText('PQC discovery domain')).not.toBeInTheDocument();
    expect(screen.getByText(/F5 BIG-IP; NGINX; HAProxy/)).toBeVisible();
    expect(screen.getAllByRole('combobox', { name: /What can you tell us\? —/ })).toHaveLength(5);
    expect(posts).toHaveLength(0);
  });
});

describe('short discovery request', () => {
  it('applies the app theme to the exact assignment without clearing unsaved responses or submitting', async () => {
    render(<App />);
    await screen.findByRole('heading', { name: firstPrompt });
    const route = window.location.hash;
    fireEvent.change(screen.getByLabelText('Your response to DQ-01'), { target: { value: 'Synthetic NGINX and F5 deployments' } });
    const picker = screen.getByRole('combobox', { name: 'Theme' });
    for (const mode of ['light', 'dark']) {
      fireEvent.change(picker, { target: { value: mode } });
      expect(picker.closest('.app-theme')).toHaveAttribute('data-theme', mode);
      expect(document.documentElement).toHaveAttribute('data-workspace-theme', mode);
      expect(screen.getByLabelText('Your response to DQ-01')).toHaveValue('Synthetic NGINX and F5 deployments');
      expect(screen.getByRole('button', { name: 'Sign out' })).toBeDisabled();
      expect(window.location.hash).toBe(route);
    }
    expect(posts).toHaveLength(0);
    expect(detail.request.answers).toEqual({});
  });
  it('shows exactly five source-defined questions without staff setup or mandatory deadlines', async () => {
    await open(); expect(screen.getAllByRole('combobox', { name: /What can you tell us\? —/ })).toHaveLength(5);
    expect(screen.getAllByRole('heading', { name: 'TLS termination', level: 2 })).toHaveLength(1);
    expect(screen.getByRole('heading', { name: 'TLS termination', level: 2 }).closest('.d-software-class')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Add software or deployment' })).toBeVisible();
    expect(screen.getByText(/F5 BIG-IP; NGINX; HAProxy/)).toBeInTheDocument(); expect(screen.queryByLabelText('Assessment')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /adopt|admit|create five/i })).not.toBeInTheDocument(); expect(screen.queryByLabelText(/date|deadline|attestation/i)).not.toBeInTheDocument();
  });
  it('keeps a native authenticated download and distinguishes preparation from browser completion', async () => {
    await open();
    fireEvent.click(screen.getByText('Use the same five questions in Excel'));
    fireEvent.click(screen.getByRole('button', { name: 'Prepare Excel form' }));
    const link = await screen.findByRole('link', { name: 'Download prepared form' });
    expect(link).toHaveAttribute('href', `${base}/exports/export-one/download`);
    expect(link).toHaveAttribute('download');
    expect(screen.getByText(/this does not confirm a download/)).toHaveTextContent('do not disable browser protections');
    expect(detail.request.status).toBe('draft');
    expect(posts).toHaveLength(1);
    expect(posts[0].path).toBe(`${base}/exports/${requestId}`);
  });
  it('explains source discovery without demanding documents, compliance proof or access', async () => {
    await open();
    expect(screen.getByText(guidance.introduction)).toBeVisible();
    expect(screen.getByText(guidance.handlingNotice)).toBeVisible();
    expect(screen.getByRole('heading', { name: lastPrompt })).toBeVisible();
    expect(screen.getByText(/None known or not sure is sufficient/)).toBeVisible();
    expect(screen.queryByRole('heading', { name: legacyPrompt })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('About this earlier request')).not.toBeInTheDocument();
    expect(screen.getByText(/Synthetic development information only/)).toBeVisible();
    fireEvent.click(top('Review and submit'));
    await screen.findByRole('heading', { name: 'Check your response before handing it over' });
    expect(screen.getByText(guidance.reviewNotice)).toBeVisible();
    expect(screen.queryByText(/evidence acceptance|no evidence route|source enablement/)).not.toBeInTheDocument();
  });
  it('clarifies an earlier form without rewriting its pinned question or existing answer', async () => {
    detail.request.templateVersion = 'pqc.discovery.v1';
    detail.request.questions[4].prompt = legacyPrompt;
    detail.request.answers['DQ-05'] = { status: 'unknown', text: 'Not sure about handling', reference: '', assertedBy: 'synthetic-demo:contributor' };
    detail.guidance.legacyNotice = legacyNotice;
    const original = structuredClone(detail.request);
    await open();
    expect(screen.getByLabelText('About this earlier request')).toHaveTextContent(legacyNotice);
    expect(screen.getByRole('heading', { name: legacyPrompt })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: lastPrompt })).not.toBeInTheDocument();
    fireEvent.click(top('Review and submit'));
    await screen.findByRole('heading', { name: 'Check your response before handing it over' });
    expect(screen.getByLabelText('About this earlier request')).toHaveTextContent(legacyNotice);
    expect(screen.getByRole('heading', { name: `DQ-05 · ${legacyPrompt}` })).toBeInTheDocument();
    expect(screen.getByText('Not sure about handling')).toBeInTheDocument();
    expect(posts).toHaveLength(0);
    expect(detail.request).toEqual(original);
  });
  it('uses current receipt guidance for a historical submission without changing its recorded receipt', async () => {
    detail.request.templateVersion = 'pqc.discovery.v1';
    detail.request.questions[4].prompt = legacyPrompt;
    detail.request.status = 'submitted'; detail.canEdit = false;
    detail.request.receipt = 'This is not evidence acceptance or assessment completion; no email was sent.';
    detail.guidance.legacyNotice = legacyNotice;
    const original = structuredClone(detail.request);
    render(<DiscoveryWorkspace session={actor} mode="respondent" onNavigate={navigate} />);
    await screen.findByRole('heading', { name: 'Thank you. No further response is required now.' });
    expect(screen.getByText(guidance.submissionReceipt)).toBeVisible();
    expect(screen.queryByText(original.receipt!)).not.toBeInTheDocument();
    expect(screen.getByLabelText('About this earlier request')).toHaveTextContent(legacyNotice);
    expect(screen.queryByRole('button', { name: 'Submit response to coordinator' })).not.toBeInTheDocument();
    expect(detail.request).toEqual(original);
    expect(posts).toHaveLength(0);
  });
  it('saves only changed answers with the strict nullable wire fieldset and server attribution', async () => {
    detail.request.answers['DQ-02'] = { status: 'referral', text: 'Imported team', reference: '', assertedBy: 'unverified:offline' };
    await open(); fireEvent.change(screen.getByLabelText('Your response to DQ-01'), { target: { value: 'NGINX, platform team' } }); fireEvent.click(top('Save draft'));
    await screen.findByText(/Draft saved. This has not yet/); const body = JSON.parse(String(posts[0].options.body));
    expect(Object.keys(body).sort()).toEqual(['expectedRevision', 'fields', 'operation', 'targetId']); expect(Object.keys(body.fields.answers)).toEqual(['DQ-01']);
    expect(body.fields.answers['DQ-01']).toEqual({ status: 'answered', text: 'NGINX, platform team', reference: '' }); expect(detail.request.answers['DQ-02'].assertedBy).toBe('unverified:offline');
  });
  it('collapses optional reference help but opens an existing reference without hiding the primary response', async () => {
    detail.request.answers['DQ-02'] = { status: 'referral', text: 'Ask the synthetic platform team', reference: 'synthetic:team-directory' };
    await open();
    const emptyReference = screen.getByLabelText('Existing reference for DQ-01 (optional)');
    const suppliedReference = screen.getByLabelText('Existing reference for DQ-02 (optional)');
    expect(emptyReference.closest('details')).not.toHaveAttribute('open');
    expect(emptyReference).not.toBeVisible();
    expect(suppliedReference.closest('details')).toHaveAttribute('open');
    expect(suppliedReference).toBeVisible();
    expect(screen.getByLabelText('Your response to DQ-01')).toBeVisible();
    expect(screen.getByLabelText('What can you tell us? — DQ-01')).toBeVisible();
    fireEvent.click(screen.getByText('Optional reference and why we ask · DQ-01'));
    expect(emptyReference).toBeVisible();
  });
  it('hands off a useful explicit unknown with the other four unanswered and no invented deployment', async () => {
    await open(); fireEvent.change(screen.getByLabelText('What can you tell us? — DQ-01'), { target: { value: 'unknown' } }); fireEvent.click(top('Save draft')); await screen.findByText(/Draft saved. This has not yet/);
    fireEvent.click(top('Review and submit')); await screen.findByRole('heading', { name: 'Check your response before handing it over' });
    expect(screen.getAllByRole('heading', { name: 'TLS termination', level: 2 })).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Submit response to coordinator' })).toBeEnabled(); fireEvent.click(screen.getByRole('button', { name: 'Submit response to coordinator' }));
    const receipt = await screen.findByRole('heading', { name: 'Thank you. No further response is required now.' }); expect(receipt).toHaveFocus(); expect(screen.getByText(guidance.submissionReceipt)).toBeInTheDocument();
    expect(screen.queryByText(/source enablement|evidence acceptance|no evidence route/)).not.toBeInTheDocument();
    expect(screen.getAllByRole('heading', { name: 'TLS termination', level: 2 })).toHaveLength(1);
    expect(detail.request.productRefs).toEqual([]); expect(Object.keys(detail.request.answers)).toEqual(['DQ-01']);
  });
  it('does not issue a write for an unchanged draft and blocks empty submission', async () => {
    await open(); fireEvent.click(top('Save draft')); await screen.findByText('Your visible response is already saved.'); expect(posts).toHaveLength(0);
    fireEvent.click(top('Review and submit')); await screen.findByRole('heading', { name: 'Check your response before handing it over' }); expect(screen.getByRole('button', { name: 'Submit response to coordinator' })).toBeDisabled();
  });
  it('saves the current partial answer before opening check-answers in one action', async () => {
    await open(); fireEvent.change(screen.getByLabelText('What can you tell us? — DQ-02'), { target: { value: 'not_my_team' } }); fireEvent.click(top('Review and submit'));
    const reviewHeading = await screen.findByRole('heading', { name: 'Check your response before handing it over' }); expect(reviewHeading).toHaveFocus(); expect(screen.getByRole('button', { name: 'Submit response to coordinator' })).toBeEnabled();
    expect(JSON.parse(String(posts[0].options.body)).operation).toBe('discovery_save');
  });
  it('preserves separate same-product deployments and guards Excel while dirty', async () => {
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Add software or deployment' })); fireEvent.change(screen.getByLabelText('Deployment / identifying name 1 (optional)'), { target: { value: 'East' } }); fireEvent.change(screen.getByLabelText('Software / product name 1'), { target: { value: 'NGINX' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add another software or deployment' })); fireEvent.change(screen.getByLabelText('Deployment / identifying name 2 (optional)'), { target: { value: 'West' } }); fireEvent.change(screen.getByLabelText('Software / product name 2'), { target: { value: 'NGINX' } });
    expect(screen.getByRole('button', { name: 'Prepare Excel form' })).toBeDisabled(); fireEvent.click(top('Save draft')); await screen.findByText(/Draft saved. This has not yet/); expect(detail.request.productRefs.map(item => item.id)).toEqual(['product-0', 'product-1']);
    expect(detail.request.productRefs.map(item => [item.product, item.label])).toEqual([['NGINX', 'East'], ['NGINX', 'West']]);
  });
  it('removes server provenance fields when editing an existing deployment', async () => {
    detail.request.productRefs = [{ id: 'old-product', label: 'East', product: 'NGINX', environment: 'test', ...{ recordedBy: 'synthetic-demo:analyst', recordedAt: '2026-09-09T00:00:00Z' } }];
    await open(); fireEvent.change(screen.getByLabelText('Environment 1 (optional)'), { target: { value: 'test-east' } }); fireEvent.click(top('Save draft')); await screen.findByText(/Draft saved. This has not yet/);
    expect(JSON.parse(String(posts[0].options.body)).fields.productRefs).toEqual([{ id: 'old-product', label: 'East', product: 'NGINX', environment: 'test-east' }]);
  });
  it('saves multiple software names without demanding deployment details or extra answers', async () => {
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Add software or deployment' }));
    fireEvent.change(screen.getByLabelText('Software / product name 1'), { target: { value: 'NGINX' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add another software or deployment' }));
    fireEvent.change(screen.getByLabelText('Software / product name 2'), { target: { value: 'HAProxy' } });
    fireEvent.click(top('Review and submit'));
    await screen.findByRole('heading', { name: 'Check your response before handing it over' });
    expect(JSON.parse(String(posts[0].options.body)).fields).toEqual({ productRefs: [
      { id: '', product: 'NGINX', label: 'NGINX', environment: '' },
      { id: '', product: 'HAProxy', label: 'HAProxy', environment: '' },
    ] });
    expect(detail.request.answers).toEqual({});
    expect(screen.getByRole('button', { name: 'Submit response to coordinator' })).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: 'Submit response to coordinator' }));
    await screen.findByRole('heading', { name: 'Thank you. No further response is required now.' });
    expect(detail.request.productRefs).toHaveLength(2);
    expect(screen.getAllByRole('heading', { name: 'TLS termination', level: 2 })).toHaveLength(1);
  });
  it('recovers from an empty optional entry without losing a useful referral', async () => {
    await open();
    fireEvent.change(screen.getByLabelText('Your response to DQ-02'), { target: { value: 'Ask the synthetic platform team' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add software or deployment' }));
    fireEvent.click(top('Review and submit'));
    expect(await screen.findByRole('alert')).toHaveTextContent('Enter a software or deployment name for entry 1');
    expect(posts).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: 'Remove entry 1' }));
    fireEvent.click(top('Review and submit'));
    await screen.findByRole('heading', { name: 'Check your response before handing it over' });
    expect(detail.request.productRefs).toHaveLength(0);
    expect(detail.request.answers['DQ-02'].text).toBe('Ask the synthetic platform team');
  });
  it('retains class context when a submitted request is opened directly', async () => {
    detail.request.status = 'submitted'; detail.canEdit = false;
    render(<DiscoveryWorkspace session={actor} mode="respondent" onNavigate={navigate} />);
    await screen.findByRole('heading', { name: 'Thank you. No further response is required now.' });
    expect(screen.getAllByRole('heading', { name: 'TLS termination', level: 2 })).toHaveLength(1);
    expect(screen.queryByRole('button', { name: 'Add software or deployment' })).not.toBeInTheDocument();
  });
  it('reconciles real string-valued Excel conflicts into a draft and synchronizes inputs', async () => {
    await open(); fireEvent.click(screen.getByText('Use the same five questions in Excel'));
    fireEvent.change(screen.getByLabelText('Preview returned discovery form (.xlsx, maximum 1 MiB)'), { target: { files: [new File(['synthetic'], 'return.xlsx')] } });
    await screen.findByRole('heading', { name: 'Review returned answers' }); expect(screen.getByRole('button', { name: 'Apply to draft' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Keep which answer for DQ-01?'), { target: { value: 'returned' } }); fireEvent.click(screen.getByRole('button', { name: 'Apply to draft' }));
    await waitFor(() => expect(screen.getByLabelText('Your response to DQ-01')).toHaveValue('Offline platform team')); expect(detail.request.status).toBe('draft'); expect(screen.queryByRole('heading', { name: /Thank you/ })).not.toBeInTheDocument();
  });
  it('retries the identical request identity after ambiguous delivery', async () => {
    await open(); fireEvent.change(screen.getByLabelText('Your response to DQ-01'), { target: { value: 'A useful referral' } }); failure = 'ambiguous'; fireEvent.click(top('Save draft'));
    fireEvent.click(await screen.findByRole('button', { name: 'Retry original operation' })); await screen.findByText('Draft · not submitted');
    await waitFor(() => expect(posts).toHaveLength(2)); expect(posts[1].options.body).toEqual(posts[0].options.body); expect(posts[1].options.headers).toEqual(posts[0].options.headers);
  });
  it('preserves direct login destination and protects browser hash navigation until explicit discard', async () => {
    session = { authenticated: false, synthetic: true, role: null, csrfToken: null }; render(<App />); await screen.findByRole('heading', { name: 'Open the workspace' });
    fireEvent.change(screen.getByLabelText('Synthetic demo password'), { target: { value: 'synthetic-demo-only' } }); fireEvent.click(screen.getByRole('button', { name: /Open workspace/ }));
    await screen.findByRole('heading', { name: firstPrompt }); expect(location.hash).toBe(deepLink); expect(screen.queryByRole('navigation', { name: 'Main navigation' })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Your response to DQ-01'), { target: { value: 'Keep this draft' } });
    await act(async () => { location.hash = 'discovery'; window.dispatchEvent(new HashChangeEvent('hashchange')); });
    await screen.findByText(/Navigation was paused/); expect(screen.getByLabelText('Your response to DQ-01')).toHaveValue('Keep this draft'); expect(location.hash).toBe(deepLink);
    fireEvent.click(screen.getByRole('button', { name: 'Discard unsaved edits' })); await waitFor(() => expect(screen.getByRole('button', { name: 'My requests' })).toBeEnabled());
  });
  it('explains unauthorized request links and offers own assignments', async () => {
    failure = 'access'; render(<DiscoveryWorkspace session={actor} mode="respondent" onNavigate={navigate} />);
    await screen.findByText(/not available to your signed-in identity/); fireEvent.click(screen.getByRole('button', { name: 'Choose my own request' })); expect(navigate).toHaveBeenCalledWith('discovery', { assessment: '', request: '' });
  });
});

describe('separate staff discovery work', () => {
  it('creates the five-question default with targetId:null', async () => {
    await openStaff(); fireEvent.change(screen.getByLabelText('Request title'), { target: { value: 'Find termination owners' } }); fireEvent.change(screen.getByLabelText('Software class / source family'), { target: { value: 'traffic-termination' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create five-question request' })); await screen.findByRole('heading', { name: 'Find termination owners' });
    expect(JSON.parse(String(posts[0].options.body))).toMatchObject({ operation: 'discovery_create', targetId: null, fields: { title: 'Find termination owners', familyId: 'traffic-termination' } });
  });
  it('keeps proposal review separate from adoption and records existing practice', async () => {
    await openStaff(); fireEvent.click(screen.getByRole('button', { name: 'Draft standards proposals' })); fireEvent.change(screen.getByLabelText('Draft proposal package'), { target: { value: 'assessment-evidence' } });
    expect(screen.getByText('DRAFT PROPOSAL · NOT ADOPTED')).toBeInTheDocument(); expect(screen.queryByRole('button', { name: /adopt|approve|execute/i })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Observed or reported current practice'), { target: { value: 'Reported documentation route; not exercised.' } }); fireEvent.click(screen.getByRole('button', { name: 'Save draft proposal and review notes' }));
    await waitFor(() => expect(posts).toHaveLength(1)); expect(JSON.parse(String(posts[0].options.body)).fields.observedPractice).toContain('not exercised');
  });
  it('lets staff identify a deployment after a partial response without reopening it', async () => {
    list.requests[0].status = 'submitted'; await openStaff(); fireEvent.click(screen.getByRole('button', { name: 'Engineering investigations' })); fireEvent.change(screen.getByLabelText('Investigation or returned request'), { target: { value: 'investigation-one' } });
    expect(screen.getByText(/Here, evidence means information supporting an assessment conclusion/)).toBeInTheDocument();
    fireEvent.click(screen.getByText('Add identified product/deployment')); fireEvent.change(screen.getByLabelText('Identified deployment label'), { target: { value: 'East termination' } }); fireEvent.change(screen.getByLabelText('Identified deployment product'), { target: { value: 'NGINX' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add identified deployment' })); await screen.findByText(/East termination · NGINX/);
    expect(JSON.parse(String(posts[0].options.body)).operation).toBe('discovery_add_product'); expect(list.requests[0].status).toBe('submitted');
    fireEvent.click(screen.getByText('Stage a controlled synthetic TLS fixture')); expect(screen.getByRole('button', { name: 'Stage for technical review' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Inspect admitted assets' })).toBeInTheDocument(); expect(screen.getByRole('button', { name: 'Read report history' })).toBeInTheDocument();
  });
  it('saves revised proposal wording as a draft while preserving existing review notes', async () => {
    list.standards[0].conflictNote = 'Review retention rules with the information owner.';
    await openStaff(); fireEvent.click(screen.getByRole('button', { name: 'Draft standards proposals' })); fireEvent.change(screen.getByLabelText('Draft proposal package'), { target: { value: 'assessment-evidence' } });
    const wording = screen.getByLabelText('Draft proposal wording'); expect(wording.closest('details')).not.toHaveAttribute('open');
    fireEvent.click(screen.getByText('Revise draft proposal')); expect(wording).toBeVisible(); expect(wording).toHaveAttribute('maxlength', '16384');
    fireEvent.change(wording, { target: { value: 'PROPOSED — NOT ADOPTED\nConfirm the evidence retention route before collection.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save draft proposal and review notes' }));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect(JSON.parse(String(posts[0].options.body))).toMatchObject({ operation: 'discovery_update_standard', targetId: 'assessment-evidence', fields: { proposalText: 'PROPOSED — NOT ADOPTED\nConfirm the evidence retention route before collection.', conflictNote: 'Review retention rules with the information owner.' } });
    expect(list.standards[0].status).toBe('draft'); expect(screen.queryByRole('button', { name: /adopt|approve|execute/i })).not.toBeInTheDocument();
  });
  it('does not append duplicate punctuation to reported practice in the report', () => {
    render(<DiscoveryReportSection content={{ discovery: { hasActivity: true, summary: 'Synthetic discovery context.', responses: [], investigations: [], standards: [{ ...list.standards[0], observedPractice: 'Reported route is not yet exercised.' }], limitations: [], nextDecision: 'Confirm the review route.' } }} onInspect={vi.fn()} />);
    const practice = screen.getByText(/^Recorded practice:/);
    expect(practice).toHaveTextContent('Recorded practice: Reported route is not yet exercised. Conflict review:');
    expect(practice.textContent).not.toContain('..');
  });
});
