import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AssessmentWork } from './AssessmentWork';
import type { Session } from './contracts';
import type { DiscoveryList } from './discovery-contracts';
import type { OperationalReceipt, WorkCase, WorkQueue } from './assessment-work-contracts';

const assessmentId = 'assessment-work-test'; const requestId = 'discovery-work-test';
const base = `/api/assessments/${assessmentId}`;
const actor: Session = { authenticated: true, role: 'analyst', synthetic: true, csrfToken: 'synthetic-work-csrf' };
let current: WorkCase; let queue: WorkQueue; let discovery: DiscoveryList;
let posts: { path: string; options: RequestInit }[];
let failure: '' | 'ambiguous' | 'conflict' | 'denied';
let duplicateRequest: string;
const dirty = vi.fn();
const navigate = vi.fn((page: string, params: Record<string, string> = {}) => { window.location.hash = `${page}?${new URLSearchParams(params)}`; });
const fetchMock = vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
  const path = String(input);
  if (options.method === 'POST') {
    posts.push({ path, options });
    if (failure === 'ambiguous') { failure = ''; throw new TypeError('Synthetic interrupted delivery'); }
    if (failure === 'conflict') { failure = ''; return Response.json({ error: 'assessment_revision_changed' }, { status: 409 }); }
    if (path.startsWith(`${base}/receipts?`) && duplicateRequest) return Response.json({ assessmentId, revision: current.revision, duplicate: true, existingRequestId: duplicateRequest });
    if (path === `${base}/report-impact/preview`) { const body = JSON.parse(String(options.body)); return Response.json({ revision: current.revision, previewFingerprint: 'f'.repeat(64), consequence: body.fields, phase1Text: body.fields.phase1Conclusion, phase2Text: body.fields.phase2Consequence, limitations: [body.fields.limitation], nextDecision: body.fields.nextDecision }); }
    current.revision++; queue.revision = current.revision;
    if (path.startsWith(`${base}/receipts?`)) current.receipts = [receiptFixture()];
    else if (path.endsWith('/commands')) {
      const body = JSON.parse(String(options.body));
      if (body.operation === 'receipt_apply') { current.receipts[0].status = 'applied'; current.request.status = 'submitted'; }
      if (body.operation === 'reconcile_product') current.identityDecisions.push({ id: 'identity-recorded', ...body.fields });
      if (body.operation === 'workspace_review_evidence') current.technicalRecords[0].status = body.fields.determination;
      if (body.operation === 'workspace_admit_evidence') current.technicalRecords[0].status = 'admitted';
      if (body.operation === 'record_consequence') current.consequence = { ...body.fields, id: 'consequence-recorded', status: 'recorded' };
    }
    return Response.json({ assessmentId, revision: current.revision, case: current, effect: 'Recorded in synthetic history.' });
  }
  if (path === '/api/assessments') return Response.json([{ id: assessmentId, name: 'Synthetic service assessment' }]);
  if (path === `${base}/work`) return Response.json(queue);
  if (path === `${base}/work/${requestId}`) return failure === 'denied' ? Response.json({ error: 'assessment_forbidden' }, { status: 403 }) : Response.json(current);
  if (path === `${base}/discovery`) return Response.json(discovery);
  throw new Error(`Unexpected fixture route: ${path}`);
});
function receiptFixture(): OperationalReceipt {
  return { id: 'receipt-1', status: 'staged', filename: 'PQC_Discovery_Questionnaire_TLS.xlsx', artifactSha256: 'a'.repeat(64), profile: 'pqc.discovery.email-return.v1', familyId: 'traffic-termination', receivedAt: '2026-09-14T10:00:00Z', receivedBy: 'synthetic-demo:analyst', respondent: 'Synthetic platform respondent', team: 'Synthetic platform team', responseDate: '2026-09-14', scope: 'Portal East and West only',
    answers: Array.from({ length: 5 }, (_, index) => ({ questionId: `DQ-0${index + 1}`, prompt: `Discovery question ${index + 1}`, status: index === 0 ? 'answered' : 'unknown', text: index === 0 ? 'Two distinct deployments, same product.' : 'Not sure', reference: '', attribution: 'Offline author — unverified', followUp: 'Synthetic platform team' })),
    products: [{ id: 'wproduct-east', product: 'Synthetic proxy', deployment: 'Portal East', environment: 'test', applicationService: 'Synthetic portal', team: 'Platform', dependencies: 'Synthetic service dependency', reference: 'synthetic:inventory', notes: 'Alias may exist' }, { id: 'wproduct-alias', product: 'Synthetic proxy', deployment: 'East alias', environment: 'test', applicationService: '', team: '', dependencies: '', reference: '', notes: 'Suspected duplicate' }],
    comparison: Array.from({ length: 5 }, (_, index) => ({ questionId: `DQ-0${index + 1}`, current: { status: 'answered', text: 'Previous reported version', reference: '' }, returned: { status: 'unknown', text: 'Not sure', reference: '' }, state: 'conflict' })),
  };
}
beforeEach(() => {
  posts = []; failure = ''; duplicateRequest = ''; dirty.mockClear(); navigate.mockClear(); fetchMock.mockClear();
  current = { assessmentId, assessmentName: 'Synthetic service assessment', revision: 7,
    request: { id: requestId, title: 'Identify portal termination', familyId: 'traffic-termination', familyName: 'TLS termination', templateVersion: 'pqc.discovery.v2', questions: Array.from({ length: 5 }, (_, index) => ({ id: `DQ-0${index + 1}`, prompt: `Discovery question ${index + 1}`, whyItMatters: 'Identify the useful route', usefulResponse: 'A referral or unknown is useful', examples: [] })), examples: [], assignedTo: 'synthetic-demo:contributor', status: 'submitted', answers: {}, productRefs: [], submission: null, receipt: null },
    investigations: [], receipts: [], identityDecisions: [], technicalRecords: [], consequence: null, history: [], documents: [], allowedActions: ['receipt_receive', 'receipt_apply', 'reconcile_product', 'record_consequence', 'workspace_stage_evidence'], boundary: 'Synthetic development only' };
  queue = { assessmentId, assessmentName: current.assessmentName, revision: 7, boundary: current.boundary, items: [{ requestId, title: current.request.title, familyId: current.request.familyId, familyName: current.request.familyName, state: 'needs_action', task: 'Review received questionnaire', why: 'An offline response needs an attributed handoff.', effect: 'Reviewed answers support source routing, not technical verification.', nextFunction: 'Assessment lead', canAct: true }] };
  discovery = { assessmentId, assessmentName: current.assessmentName, revision: 7, canCoordinate: true, families: [], requests: [current.request], standards: [], investigations: [], investigators: [{ id: 'synthetic-demo:reviewer', label: 'Technical reviewer' }], boundary: current.boundary };
  history.replaceState(null, '', `#assessment-work?assessment=${assessmentId}`); vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
async function open(step?: string) {
  if (step) history.replaceState(null, '', `#assessment-work?assessment=${assessmentId}&request=${requestId}&step=${step}`);
  render(<div className="app-theme" data-theme="dark"><AssessmentWork session={actor} onNavigate={navigate} onDirtyChange={dirty} /></div>);
  await screen.findByRole('heading', { name: step ? 'Review received questionnaire' : 'Identify portal termination' });
}
function fillConsequence() {
  for (const [label, value] of [['Phase 1 conclusion supported by this case', 'The synthetic inventory establishes two reported deployments.'], ['Material limitation and what cannot be concluded', 'Source collection remains blocked; technical use is unknown.'], ['Next decision needed', 'Name the authorized source route.'], ['Next responsible function', 'Synthetic information owner'], ['Conditional Phase 2 business consequence', 'Portal reliance requires business review.']]) fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

describe('one coordinator and reviewer assessment-work surface', () => {
  it('shows four work states, a purpose and the next responsible function, not completion metrics', async () => {
    await open();
    for (const label of ['Needs my action', 'In progress', 'Waiting', 'Recorded']) expect(screen.getByRole('button', { name: new RegExp(`^${label} \\(`) })).toBeVisible();
    expect(screen.getByText('An offline response needs an attributed handoff.')).toBeVisible();
    expect(screen.getByText('Assessment lead')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Open this task' }));
    await screen.findByRole('heading', { name: 'What was supplied' });
    expect(window.location.hash).toContain(`request=${requestId}`); expect(window.location.hash).toContain(`assessment=${assessmentId}`);
    expect(screen.getByText('What your action changes')).toBeVisible(); expect(posts).toHaveLength(0);
  });
  it('distinguishes an empty waiting lane from a completed assessment', async () => {
    await open(); fireEvent.click(screen.getByRole('button', { name: /^Waiting/ }));
    expect(await screen.findByRole('heading', { name: 'No work in waiting' })).toBeVisible();
    expect(screen.getByText(/This does not mean the assessment is complete/)).toBeVisible();
  });
  it('opens the server-selected actionable section instead of restarting every case at intake', async () => {
    queue.items[0].step = 'technical'; await open();
    fireEvent.click(screen.getByRole('button', { name: 'Open this task' }));
    expect(await screen.findByRole('heading', { name: 'Review the technical contents' })).toBeVisible();
    expect(window.location.hash).toContain('step=technical'); expect(posts).toHaveLength(0);
  });
  it('requires explicit assessment/request binding before receiving the individual physical workbook', async () => {
    await open('returned');
    const button = screen.getByRole('button', { name: 'Receive and preview information' });
    fireEvent.change(screen.getByLabelText(/Completed operational questionnaire/), { target: { files: [new File(['synthetic workbook bytes'], 'PQC_Discovery_Questionnaire_TLS.xlsx')] } });
    expect(button).toBeDisabled(); expect(posts).toHaveLength(0);
    fireEvent.click(screen.getByRole('checkbox', { name: /I confirm this return belongs/ }));
    fireEvent.click(button); await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0].path).toBe(`${base}/receipts?requestId=${requestId}&expectedRevision=7&filename=PQC_Discovery_Questionnaire_TLS.xlsx`);
    expect(posts[0].options.headers).toMatchObject({ 'X-PQC-CSRF': actor.csrfToken, 'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    expect(await screen.findByText('Synthetic platform respondent')).toBeVisible();
    expect(screen.getByText(/Workbook received for review/)).toBeVisible();
  });
  it('rejects ZIP and macro-enabled files without making a request', async () => {
    await open('returned');
    fireEvent.change(screen.getByLabelText(/Completed operational questionnaire/), { target: { files: [new File(['not accepted'], 'forms.zip')] } });
    expect(screen.getByRole('alert')).toHaveTextContent('ZIP and macro-enabled'); expect(posts).toHaveLength(0);
  });
  it('explains a duplicate’s original request without silently changing the current binding', async () => {
    duplicateRequest = 'discovery-original-binding'; await open('returned');
    fireEvent.change(screen.getByLabelText(/Completed operational questionnaire/), { target: { files: [new File(['same workbook'], 'returned.xlsx')] } });
    fireEvent.click(screen.getByRole('checkbox', { name: /I confirm this return belongs/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Receive and preview information' }));
    expect(await screen.findByRole('button', { name: 'Open the original receipt request' })).toBeVisible();
    expect(screen.getByText(/No duplicate response or source artifact was created/)).toBeVisible();
    expect(window.location.hash).toContain(`request=${requestId}`); expect(navigate).not.toHaveBeenCalled();
  });
  it('shows prior recorded, current and returned information plus product rows before an offline handoff', async () => {
    const prior = { ...receiptFixture(), id: 'receipt-prior', filename: 'earlier.xlsx', status: 'applied', receivedAt: '2026-09-13T10:00:00Z' };
    prior.answers[0].text = 'Earlier reported deployment claim';
    current.receipts = [prior, receiptFixture()]; await open('returned');
    expect(screen.getByText(/Earlier reported deployment claim/)).toBeVisible();
    expect(screen.getAllByRole('heading', { name: 'Prior recorded return' })).toHaveLength(5);
    expect(screen.getByRole('region', { name: 'Returned products and deployments' })).toHaveTextContent('Synthetic proxy — Portal East');
    expect(screen.getByText(/historical reported version, not a server export baseline/)).toBeVisible();
    expect(posts).toHaveLength(0);
  });
  it('identifies required answers and notes before disabling the handoff', async () => {
    current.receipts = [receiptFixture()]; await open('returned');
    expect(screen.getByLabelText('Receipt review note')).toHaveAttribute('aria-required', 'true');
    expect(screen.getByLabelText('Retain which answer for DQ-01?')).toHaveAttribute('aria-required', 'true');
    expect(screen.getByText(/^Still required:/)).toHaveTextContent('answer choice for DQ-01');
    expect(screen.getByText(/^Still required:/)).toHaveTextContent('receipt review note');
  });
  it('records explicit receipt choices without treating offline attribution as authenticated approval', async () => {
    current.receipts = [receiptFixture()]; await open('returned');
    const button = screen.getByRole('button', { name: 'Record reviewed offline response' });
    expect(button).toBeDisabled();
    for (let index = 1; index <= 5; index++) fireEvent.change(screen.getByLabelText(`Retain which answer for DQ-0${index}?`), { target: { value: index === 1 ? 'current' : 'returned' } });
    fireEvent.change(screen.getByLabelText('Receipt review note'), { target: { value: 'Preserve the competing product assertion and record the remaining unknowns.' } });
    fireEvent.click(button); await waitFor(() => expect(posts).toHaveLength(1));
    expect(JSON.parse(String(posts[0].options.body))).toMatchObject({ operation: 'receipt_apply', targetId: 'receipt-1', expectedRevision: 7, fields: { choices: { 'DQ-01': 'current', 'DQ-02': 'returned' } } });
    expect(await screen.findByText(/This receipt has already been applied/)).toBeVisible();
    expect(screen.getByText(/not an authenticated respondent signature/)).toBeVisible();
  });
  it('uses an existing canonical identity for a duplicate without deleting reported rows', async () => {
    current.receipts = [{ ...receiptFixture(), status: 'applied' }];
    current.identityDecisions = [{ id: 'identity-east', productId: 'wproduct-east', decision: 'distinct', canonicalId: 'wsystem-east', label: 'Reviewed Portal East', applicationService: 'Portal', team: 'Platform', rationale: 'Reviewed context record' }];
    await open('systems');
    fireEvent.change(screen.getByLabelText('Reported product or deployment'), { target: { value: 'wproduct-alias' } });
    fireEvent.change(screen.getByLabelText('Identity determination'), { target: { value: 'same_system' } });
    fireEvent.change(screen.getByLabelText('Same system as'), { target: { value: 'wsystem-east' } });
    fireEvent.change(screen.getByLabelText('Reviewed system label'), { target: { value: 'Portal East alias' } });
    fireEvent.change(screen.getByLabelText('Identity rationale and evidence basis'), { target: { value: 'The inventory identifies both names with one immutable native system ID.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Record identity determination' }));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect(JSON.parse(String(posts[0].options.body)).fields).toMatchObject({ productId: 'wproduct-alias', decision: 'same_system', canonicalId: 'wsystem-east' });
    expect(current.receipts[0].products).toHaveLength(2);
  });
  it('distinguishes identical deployment labels and explains the original-record prerequisite', async () => {
    const receipt = { ...receiptFixture(), status: 'applied' };
    receipt.products[1].deployment = receipt.products[0].deployment;
    receipt.products[1].reference = 'synthetic:second-reference-east';
    current.receipts = [receipt]; await open('systems');
    const options = within(screen.getByLabelText('Reported product or deployment')).getAllByRole('option');
    expect(options[0]).toHaveTextContent('reported row 1');
    expect(options[1]).toHaveTextContent('reported row 2');
    expect(options[1]).toHaveTextContent('synthetic:second-reference-east');
    expect(screen.getByRole('option', { name: 'This refers to the same system as another record' })).toBeDisabled();
    expect(screen.getByText(/First select the original reported row/)).toBeVisible();
    expect(posts).toHaveLength(0);
  });
  it('distinguishes eight assertions from two returned versions without changing their identities', async () => {
    const receipts = [1, 2].map(version => ({ ...receiptFixture(), id: `receipt-${version}`, status: 'applied', filename: `returned-v${version}.xlsx`, products: Array.from({ length: 4 }, (_, row) => ({ ...receiptFixture().products[0], id: `product-${version}-${row}`, product: 'F5 BIG-IP', deployment: 'gateway-east', environment: 'synthetic-test-east', provenance: `Products & deployments!A${row + 4}:I${row + 4}` })) }));
    current.receipts = receipts; await open('systems');
    const options = within(screen.getByLabelText('Reported product or deployment')).getAllByRole('option');
    expect(options).toHaveLength(8);
    expect(new Set(options.map(option => option.textContent)).size).toBe(8);
    expect(options[0]).toHaveTextContent('Return 1 · reported row 1');
    expect(options[4]).toHaveTextContent('Return 2 · reported row 1');
    expect(options[4]).toHaveTextContent('Products & deployments!A4:I4');
    fireEvent.change(screen.getByLabelText('Reported product or deployment'), { target: { value: 'product-2-0' } });
    expect(screen.getByText('Return 2 · returned-v2.xlsx')).toBeVisible();
    expect(posts).toHaveLength(0);
  });
  it('allows a reviewed same-name target and explains unresolved targets separately', async () => {
    const receipt = { ...receiptFixture(), status: 'applied' };
    receipt.products[1].deployment = receipt.products[0].deployment;
    receipt.products.push({ ...receipt.products[0], id: 'wproduct-unresolved', reference: 'synthetic:uncertain' });
    current.receipts = [receipt];
    current.identityDecisions = [{ id: 'identity-east', productId: 'wproduct-east', decision: 'distinct', canonicalId: 'wsystem-east', label: 'Reviewed Portal East', applicationService: '', team: '', rationale: 'Original inventory reference establishes the reviewed east identity.' }, { id: 'identity-unknown', productId: 'wproduct-unresolved', decision: 'unresolved', canonicalId: '', label: 'Uncertain east', applicationService: '', team: '', rationale: 'Native identifier missing.' }];
    await open('systems');
    fireEvent.change(screen.getByLabelText('Reported product or deployment'), { target: { value: 'wproduct-alias' } });
    fireEvent.change(screen.getByLabelText('Identity determination'), { target: { value: 'same_system' } });
    const targets = within(screen.getByLabelText('Same system as'));
    expect(targets.getByRole('option', { name: /Reviewed Portal East · reviewed identity/ })).toBeEnabled();
    expect(targets.getByRole('option', { name: /reviewed as unresolved; establish identity first/ })).toBeDisabled();
    expect(targets.queryByRole('option', { name: /reported row 2/ })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Same system as'), { target: { value: 'wsystem-east' } });
    expect(screen.getByLabelText('Reviewed match basis')).toHaveTextContent('Original inventory reference establishes the reviewed east identity.');
    expect(posts).toHaveLength(0);
  });
  it('renders normalized cryptographic uses and relationships without hiding structured records', async () => {
    current.technicalRecords = [{ bundleId: 'wbundle-registered', investigationId: '', productLabel: 'Synthetic key service', sourceLabel: 'Synthetic key inventory', kind: 'registered', status: 'staged', canReview: true, reviewRationale: '', observations: [{ id: 'obs-key', systemId: 'key-1', sourceSystemId: 'source-1', nativeId: 'key-native-1', basis: 'configuration', normalizerVersion: 'synthetic-normalizer.v1', supports: ['Key consumer metadata within the supplied fixture'], cannotEstablish: ['Runtime negotiation'], facts: { cryptographic_uses: [{ purpose: 'key_establishment', algorithm: 'RSA-2048', implementation: { library: 'Synthetic Crypto Library', version: '1.0' } }], relationships: [{ relation: 'protects', target: 'Synthetic claims archive' }] } }] }];
    await open('technical');
    expect(screen.getByText('RSA-2048')).toBeVisible();
    expect(screen.getByText('Synthetic Crypto Library')).toBeVisible();
    expect(screen.getByText('Synthetic claims archive')).toBeVisible();
    expect(screen.getByText('Runtime negotiation')).toBeVisible();
    expect(screen.queryByText(/Structured value requires/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Review qualified determination' })).toBeDisabled();
    expect(posts).toHaveLength(0);
  });
  it('connects a recorded case to phase handoffs without recording any decision', async () => {
    await open('consequence');
    fireEvent.click(screen.getByRole('button', { name: 'Phase 1 report and handoff' }));
    expect(navigate).toHaveBeenCalledWith('assessments', { assessment: assessmentId, stage: '4' });
    expect(posts).toHaveLength(0);
  });
  it('shows real technical fields and requires a per-record determination before qualification', async () => {
    current.technicalRecords = [{ bundleId: 'wbundle-1', investigationId: '', productLabel: 'Portal East', sourceLabel: 'Synthetic TLS capture', kind: 'tls', status: 'staged', canReview: true, canAdmit: false, reviewRationale: '', observations: [{ id: 'obs-1', systemId: 'subject-1', sourceSystemId: 'source-1', nativeId: 'endpoint-east', hostname: 'portal.invalid', keyExchange: 'X25519', authentication: 'RSA', basis: 'observed', collectedAt: '2026-09-14T10:00:00Z' }] }];
    await open('technical');
    expect(screen.getByText('X25519')).toBeVisible(); expect(screen.getByText('RSA')).toBeVisible();
    const review = screen.getByRole('button', { name: 'Review qualified determination' });
    fireEvent.change(screen.getByLabelText('Technical review rationale for Portal East'), { target: { value: 'The observed record conflicts with the hybrid configuration claim.' } });
    expect(review).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Record determination for endpoint-east'), { target: { value: 'conflict' } });
    fireEvent.change(screen.getByLabelText('Record rationale for endpoint-east'), { target: { value: 'Classical observed exchange differs from the reported hybrid setting; scope requires checking.' } });
    fireEvent.click(review); expect(posts).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: 'Confirm qualified determination' })); await waitFor(() => expect(posts).toHaveLength(1));
    expect(JSON.parse(String(posts[0].options.body))).toMatchObject({ operation: 'workspace_review_evidence', targetId: 'wbundle-1', fields: { determination: 'qualified', recordDecisions: [{ observationId: 'obs-1', determination: 'conflict' }] } });
  });
  it('keeps technical review unavailable when the server does not authorize this principal', async () => {
    current.technicalRecords = [{ bundleId: 'wbundle-1', investigationId: '', productLabel: 'Portal East', sourceLabel: 'Synthetic capture', status: 'staged', canReview: false, reviewRationale: '', observations: [{ id: 'obs-1', systemId: 'subject-1', sourceSystemId: 'source-1', nativeId: 'endpoint', basis: 'configured' }] }];
    await open('technical'); expect(screen.getByRole('button', { name: 'Review qualified determination' })).toBeDisabled();
    expect(screen.getByText(/different from the stager must supply this determination/)).toBeVisible(); expect(posts).toHaveLength(0);
  });
  it('exposes identity-change re-review as a real technical determination, not admitted evidence', async () => {
    current.technicalRecords = [{ bundleId: 'wbundle-rebind', investigationId: '', productLabel: 'Portal East', sourceLabel: 'Synthetic capture', status: 'identity_review_required', canReview: true, proposedCanonicalId: 'wsystem-corrected', identityChangeReason: 'The alias was associated with the wrong deployment.', reviewRationale: '', observations: [{ id: 'obs-prior', systemId: 'subject-prior', sourceSystemId: 'source-1', nativeId: 'endpoint-east', keyExchange: 'X25519', basis: 'observed' }] }];
    await open('technical');
    expect(screen.getByText('Identity correction requires new technical review and lead admission.')).toBeVisible();
    expect(screen.getByText('The alias was associated with the wrong deployment.')).toBeVisible();
    expect(screen.getByLabelText('Record determination for endpoint-east')).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Review qualified determination' })).toBeDisabled(); expect(posts).toHaveLength(0);
  });
  it('explains the exact staging prerequisite without attempting a denied upload', async () => {
    current.canStageEvidence = false; current.stageEvidenceBlockingReasons = ['Boundary and source/access-register gates must pass before technical information is staged.'];
    current.receipts = [{ ...receiptFixture(), status: 'applied' }]; await open('technical');
    expect(screen.getByRole('button', { name: 'Stage source capture for review' })).toBeDisabled();
    expect(screen.getByLabelText('Controlled synthetic source JSON (maximum 32 KiB)')).toBeDisabled();
    expect(screen.getByText(current.stageEvidenceBlockingReasons[0])).toBeVisible(); expect(posts).toHaveLength(0);
  });
  it('protects one bundle’s unsaved review from another bundle or a staging action', async () => {
    current.canStageEvidence = true;
    current.technicalRecords = ['East', 'West'].map(side => ({ bundleId: `wbundle-${side}`, investigationId: '', productLabel: `Portal ${side}`, sourceLabel: `Synthetic capture ${side}`, status: 'staged', canReview: true, canAdmit: false, reviewRationale: '', observations: [{ id: `obs-${side}`, systemId: `subject-${side}`, sourceSystemId: 'source-1', nativeId: `endpoint-${side}`, keyExchange: 'X25519', basis: 'observed' }] }));
    await open('technical');
    fireEvent.change(screen.getByLabelText('Technical review rationale for Portal East'), { target: { value: 'Preserve this partial technical review while checking the exact basis.' } });
    expect(screen.getByLabelText('Technical bundle to review or admit')).toBeDisabled();
    expect(screen.getByLabelText('Technical review rationale for Portal West')).toBeDisabled();
    expect(screen.getByLabelText('Controlled synthetic source JSON (maximum 32 KiB)')).toBeDisabled();
    expect(screen.getByLabelText('Technical review rationale for Portal East')).toHaveValue('Preserve this partial technical review while checking the exact basis.');
    expect(posts).toHaveLength(0);
  });
  it('previews exact report text without committing it, then binds the commit to its fingerprint', async () => {
    await open('consequence'); fillConsequence(); fireEvent.click(screen.getByRole('button', { name: 'Preview exact report consequence' }));
    const preview = await screen.findByRole('region', { name: 'Report consequence preview' });
    expect(within(preview).getByText('The synthetic inventory establishes two reported deployments.')).toBeVisible();
    expect(current.consequence).toBeNull(); expect(posts[0].path).toBe(`${base}/report-impact/preview`);
    fireEvent.click(within(preview).getByRole('button', { name: 'Record this reviewed consequence' }));
    await waitFor(() => expect(posts).toHaveLength(2));
    expect(JSON.parse(String(posts[1].options.body))).toMatchObject({ operation: 'record_consequence', expectedRevision: 7, fields: { previewFingerprint: 'f'.repeat(64), confidence: 'unknown' } });
  });
  it('invalidates the preview when wording changes and preserves the selected theme', async () => {
    await open('consequence'); fillConsequence(); fireEvent.click(screen.getByRole('button', { name: 'Preview exact report consequence' }));
    await screen.findByRole('region', { name: 'Report consequence preview' });
    fireEvent.change(screen.getByLabelText('Next decision needed'), { target: { value: 'Corrected decision for a different source scope.' } });
    expect(screen.queryByRole('region', { name: 'Report consequence preview' })).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Assessment work' }).closest('.app-theme')).toHaveAttribute('data-theme', 'dark');
    expect(screen.getByRole('button', { name: 'Systems and sources' })).toBeDisabled(); expect(dirty).toHaveBeenLastCalledWith(true);
  });
  it('binds the report consequence to a deployment, purpose and explicitly selected support and contradiction', async () => {
    current.receipts = [{ ...receiptFixture(), status: 'applied' }];
    current.technicalRecords = [{ bundleId: 'wbundle-admitted', investigationId: '', productId: 'wproduct-east', productLabel: 'Portal East', sourceLabel: 'Synthetic compatibility cohort', status: 'admitted', reviewRationale: 'Both facts retained with their distinct basis.', observations: [{ id: 'obs-configured', systemId: 'subject-1', sourceSystemId: 'source-1', nativeId: 'configured-east', keyExchange: 'X25519MLKEM768', basis: 'configured' }, { id: 'obs-observed', systemId: 'subject-1', sourceSystemId: 'source-1', nativeId: 'observed-east', keyExchange: 'X25519', basis: 'observed' }] }];
    await open('consequence'); fillConsequence();
    expect(screen.getByLabelText('Use record configured-east in this conclusion')).toHaveValue('');
    expect(screen.getByLabelText('Use record observed-east in this conclusion')).toHaveValue('');
    fireEvent.change(screen.getByLabelText('Affected deployment for this conclusion'), { target: { value: 'wproduct-east' } });
    fireEvent.change(screen.getByLabelText('Cryptographic purpose being assessed'), { target: { value: 'key_establishment' } });
    fireEvent.change(screen.getByLabelText('Use record configured-east in this conclusion'), { target: { value: 'supporting' } });
    fireEvent.change(screen.getByLabelText('Use record observed-east in this conclusion'), { target: { value: 'contradicting' } });
    fireEvent.click(screen.getByRole('button', { name: 'Preview exact report consequence' }));
    await screen.findByRole('region', { name: 'Report consequence preview' });
    expect(JSON.parse(String(posts[0].options.body)).fields).toMatchObject({ productId: 'wproduct-east', cryptographicPurpose: 'key_establishment', supportingObservationIds: ['obs-configured'], contradictingObservationIds: ['obs-observed'] });
    fireEvent.change(screen.getByLabelText('Affected deployment for this conclusion'), { target: { value: '' } });
    expect(screen.queryByRole('region', { name: 'Report consequence preview' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Use record configured-east in this conclusion')).toHaveValue('');
    expect(screen.getByLabelText('Use record observed-east in this conclusion')).toHaveValue('');
  });
  it('keeps separately scoped key establishment and authentication conclusions available for revision', async () => {
    current.receipts = [{ ...receiptFixture(), status: 'applied' }];
    const first = { id: 'consequence-kex', phase1Conclusion: 'Hybrid exchange was configured, not independently verified.', limitation: 'Configuration does not prove negotiation.', nextDecision: 'Authorize a bounded observation.', responsibleFunction: 'Synthetic owner', phase2Consequence: 'Business review needed.', lifetime: '', confidence: 'limited' as const, productId: 'wproduct-east', cryptographicPurpose: 'key_establishment' };
    const second = { ...first, id: 'consequence-auth', phase1Conclusion: 'Certificate authentication remains classical.', cryptographicPurpose: 'authentication' };
    current.consequences = [first, second]; current.consequence = second;
    await open('consequence');
    expect(screen.getByLabelText('Phase 1 conclusion supported by this case')).toHaveValue(second.phase1Conclusion);
    fireEvent.change(screen.getByLabelText('Conclusion to review or revise'), { target: { value: first.id } });
    expect(screen.getByLabelText('Phase 1 conclusion supported by this case')).toHaveValue(first.phase1Conclusion);
    expect(screen.getByLabelText('Cryptographic purpose being assessed')).toHaveValue('key_establishment');
    fireEvent.change(screen.getByLabelText('Conclusion to review or revise'), { target: { value: '' } });
    expect(screen.getByLabelText('Phase 1 conclusion supported by this case')).toHaveValue('');
    expect(screen.getByText(second.phase1Conclusion)).toBeVisible(); expect(posts).toHaveLength(0);
  });
  it('does not carry unavailable historical evidence into a new consequence preview silently', async () => {
    current.consequence = { id: 'consequence-needs-review', phase1Conclusion: 'A historical conclusion needs its corrected identity checked.', limitation: 'Association is disputed.', nextDecision: 'Review corrected association.', responsibleFunction: 'Technical reviewer', phase2Consequence: '', lifetime: '', confidence: 'limited', supportingObservationIds: ['old-not-admitted'], status: 'needs_review' };
    await open('consequence');
    expect(screen.getByText(/This conclusion needs re-review because a relevant input changed/)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Preview exact report consequence' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Remove references needing re-review' }));
    expect(screen.getByRole('button', { name: 'Preview exact report consequence' })).toBeEnabled();
    expect(screen.getByLabelText('Material limitation and what cannot be concluded')).toHaveValue('Association is disputed.'); expect(posts).toHaveLength(0);
  });
  it('retries ambiguous delivery with the identical body and idempotency identity', async () => {
    current.receipts = [receiptFixture()]; await open('returned');
    for (let index = 1; index <= 5; index++) fireEvent.change(screen.getByLabelText(`Retain which answer for DQ-0${index}?`), { target: { value: 'returned' } });
    fireEvent.change(screen.getByLabelText('Receipt review note'), { target: { value: 'Record reported unknowns without claiming technical evidence.' } });
    failure = 'ambiguous'; fireEvent.click(screen.getByRole('button', { name: 'Record reviewed offline response' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Retry identical operation' }));
    await waitFor(() => expect(posts).toHaveLength(2)); expect(posts[1].options.body).toBe(posts[0].options.body); expect(posts[1].options.headers).toEqual(posts[0].options.headers);
  });
  it('preserves consequence edits on a revision conflict instead of inventing a successful save', async () => {
    await open('consequence'); fillConsequence(); failure = 'conflict';
    fireEvent.click(screen.getByRole('button', { name: 'Preview exact report consequence' }));
    await screen.findByRole('button', { name: 'Discard local edits and reload saved case' });
    expect(screen.getByLabelText('Next decision needed')).toHaveValue('Name the authorized source route.');
    expect(screen.queryByRole('button', { name: 'Record this reviewed consequence' })).not.toBeInTheDocument(); expect(current.consequence).toBeNull();
  });
  it('does not expose another principal’s case on access denial', async () => {
    failure = 'denied'; history.replaceState(null, '', `#assessment-work?assessment=${assessmentId}&request=${requestId}`);
    render(<AssessmentWork session={actor} onNavigate={navigate} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('No case or queue result has been assumed');
    expect(screen.queryByRole('heading', { name: 'What was supplied' })).not.toBeInTheDocument(); expect(posts).toHaveLength(0);
  });
});
