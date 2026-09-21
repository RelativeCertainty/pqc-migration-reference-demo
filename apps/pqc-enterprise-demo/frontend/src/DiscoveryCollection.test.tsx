import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { DiscoveryCollection } from './DiscoveryCollection';
import { DiscoveryWorkspace } from './DiscoveryWorkspace';
import type { DiscoveryCollectionCatalog, DiscoveryCollectionRecord, DiscoveryQuestion } from './discovery-contracts';
import type { Session } from './contracts';

const assessmentId = `assessment-${'a'.repeat(32)}`;
const base = `/api/assessments/${assessmentId}/discovery`;
const actor: Session = { authenticated: true, synthetic: true, role: 'analyst', csrfToken: 'synthetic-csrf' };
const questions: DiscoveryQuestion[] = [
  'Which products or services in this software class do you know are used?',
  'Which team or contact should we speak with?',
  'Is there an existing inventory, configuration report or other reference we can start from?',
  'Which application, business service or environment does your answer concern, if known?',
  'Are there any access restrictions, information-sharing considerations, or known gaps we should understand?',
].map((prompt, index) => ({ id: `DQ-0${index + 1}`, prompt, whyItMatters: 'Identify useful information without making an unsupported technical conclusion.', usefulResponse: 'A partial response, referral or explicit unknown is useful.', examples: [] }));
let catalog: DiscoveryCollectionCatalog; let posts: { path: string; options: RequestInit }[];
let failure: '' | 'ambiguous' | 'conflict' | 'load' | 'list-readback'; let listReads: number;
const onChanged = vi.fn(); const onBusyChange = vi.fn(); const onNavigate = vi.fn();
function savedCollection(firstSubmitted = true): DiscoveryCollectionRecord {
  return { id: 'dcollection-one', assignedTo: 'synthetic-demo:contributor', createdAt: '2026-09-10T12:00:00Z', requests: catalog.domains.flatMap(domain => domain.forms).map((form, index) => ({ familyId: form.familyId, requestId: `discovery-${index + 1}`, status: firstSubmitted && index === 0 ? 'submitted' : 'draft' })), packages: [] };
}
function excelPackage(collection: DiscoveryCollectionRecord, index = 1) {
  return { id: `dpackage-${index}`, createdAt: '2026-09-10T12:30:00Z', zipUrl: `${base}/collections/${collection.id}/exports/dpackage-${index}/download`, indexUrl: `${base}/collections/${collection.id}/exports/dpackage-${index}/index`, forms: collection.requests.map((request, formIndex) => ({ familyId: request.familyId, requestId: request.requestId, filename: `source-class-${formIndex + 1}.xlsx`, downloadUrl: `${base}/exports/dexport-${formIndex + 1}/download`, sha256: 'b'.repeat(64) })) };
}
const fetchMock = vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
  const path = String(input);
  if (options.method === 'POST') {
    posts.push({ path, options });
    if (failure === 'ambiguous') { failure = ''; throw new TypeError('Interrupted delivery'); }
    if (failure === 'conflict') { failure = ''; return Response.json({ error: 'assessment_revision_changed' }, { status: 409 }); }
    if (path === `${base}/collections`) catalog.collections.push(savedCollection(false));
    else if (path === `${base}/collections/dcollection-one/exports`) catalog.collections[0].packages.push(excelPackage(catalog.collections[0]));
    else throw new Error(`Unexpected POST route: ${path}`);
    catalog.revision++; return Response.json(catalog);
  }
  if (path === `${base}/catalog`) return failure === 'load' ? Response.json({ error: 'unavailable' }, { status: 503 }) : Response.json(catalog);
  if (path === '/api/assessments') return Response.json([{ id: assessmentId, name: catalog.assessmentName }]);
  if (path === base) {
    listReads++;
    if (failure === 'list-readback' && listReads > 1) return Response.json({ error: 'unavailable' }, { status: 503 });
    return Response.json({ assessmentId, assessmentName: catalog.assessmentName, revision: catalog.revision, canCoordinate: true, collectionAvailable: true, requests: catalog.collections.flatMap(collection => collection.requests.map(request => ({ id: request.requestId, title: `Short form ${request.familyId}`, familyId: request.familyId, familyName: catalog.domains.flatMap(domain => domain.forms).find(form => form.familyId === request.familyId)!.familyName, templateVersion: catalog.templateVersion, questions, examples: [], assignedTo: collection.assignedTo, status: request.status, answers: {}, productRefs: [], submission: null, receipt: null }))), families: catalog.domains.flatMap(domain => domain.forms).map(form => ({ id: form.familyId, name: form.familyName, examples: form.examples.map(example => example.name) })), standards: [], investigations: [], boundary: catalog.boundary });
  }
  throw new Error(`Unexpected GET route: ${path}`);
});
beforeEach(() => {
  let family = 0;
  catalog = {
    assessmentId, assessmentName: 'Synthetic complete collection', revision: 8, canPrepare: true,
    templateVersion: 'pqc.discovery.v2', domainCount: 10, formCount: 27, questionsPerForm: 5,
    boundary: 'Synthetic discovery references only. Submission does not authorize access or establish technical readiness.',
    recipients: [{ id: 'synthetic-demo:contributor', label: 'Source contributor 1' }, { id: 'synthetic-demo:contributor-two', label: 'Source contributor 2' }],
    domains: Array.from({ length: 10 }, (_, domainIndex) => ({ id: `area-${domainIndex + 1}`, name: `PQC domain ${domainIndex + 1}`, forms: Array.from({ length: domainIndex < 7 ? 3 : 2 }, () => { const number = ++family; return { familyId: `family-${number}`, familyName: `Software class ${number}`, questions: structuredClone(questions), examples: [{ name: `Recognition product ${number}`, kind: 'COTS', url: `https://example.com/product-${number}` }] }; }) })),
    collections: [],
  };
  posts = []; failure = ''; listReads = 0; onChanged.mockClear(); onBusyChange.mockClear(); onNavigate.mockClear(); fetchMock.mockClear();
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
async function open(disabled = false, session = actor) {
  render(<DiscoveryCollection assessmentId={assessmentId} sourceRevision={catalog.revision} session={session} disabled={disabled} onChanged={onChanged} onBusyChange={onBusyChange} onNavigate={onNavigate} />);
  await screen.findByRole('heading', { name: 'The five questions, in one place' });
}
function selectRecipient() { fireEvent.change(screen.getByLabelText('Collection recipient'), { target: { value: 'synthetic-demo:contributor' } }); }
async function confirmCreate() {
  selectRecipient(); fireEvent.click(screen.getByRole('button', { name: 'Review collection creation' }));
  fireEvent.click(screen.getByRole('button', { name: 'Create the 27 draft web forms' }));
}

describe('consolidated short-discovery collection', () => {
  it('shows all five current questions, 10 domains and 27 complete class forms without creating requests', async () => {
    await open();
    const counts = screen.getByLabelText('Collection contents');
    for (const count of ['10', '27', '5']) expect(within(counts).getByText(count)).toBeVisible();
    const common = screen.getByRole('heading', { name: 'The five questions, in one place' }).closest('section')!;
    expect(within(common).getAllByRole('listitem')).toHaveLength(5);
    for (const question of questions) expect(within(common).getByText(question.prompt, { exact: false })).toBeVisible();
    fireEvent.click(screen.getByText('Browse all 27 forms by PQC discovery domain'));
    for (const domain of catalog.domains) expect(screen.getByRole('heading', { name: domain.name })).toBeVisible();
    for (const form of catalog.domains.flatMap(domain => domain.forms)) {
      const summary = screen.getByText(form.familyName).closest('summary')!;
      fireEvent.click(summary);
      const formView = summary.closest('details')!;
      expect(within(formView).getAllByRole('listitem')).toHaveLength(5);
      expect(within(formView).getByText(form.examples[0].name)).toBeVisible();
      for (const question of questions) expect(within(formView).getByText(question.prompt)).toBeVisible();
    }
    expect(posts).toHaveLength(0); expect(onChanged).not.toHaveBeenCalled();
  });

  it('requires recipient and consequence review before creating 27 separately tracked drafts', async () => {
    await open();
    expect(screen.getByRole('button', { name: 'Review collection creation' })).toBeDisabled();
    selectRecipient(); fireEvent.click(screen.getByRole('button', { name: 'Review collection creation' }));
    expect(screen.getByRole('heading', { name: 'Confirm 27 new draft requests' })).toBeVisible();
    expect(screen.getByText(/no previous answer will be copied or changed/)).toBeVisible();
    expect(posts).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: 'Create the 27 draft web forms' }));
    await screen.findByText(/The collection is saved/);
    expect(posts).toHaveLength(1); expect(posts[0].path).toBe(`${base}/collections`);
    expect(JSON.parse(String(posts[0].options.body))).toEqual({ expectedRevision: 8, assignedTo: 'synthetic-demo:contributor' });
    expect(posts[0].options.headers).toMatchObject({ 'X-PQC-CSRF': actor.csrfToken, 'Idempotency-Key': expect.any(String) });
    expect(catalog.collections[0].requests).toHaveLength(27); expect(onChanged).toHaveBeenCalledOnce();
    expect(screen.getByText(/A collection already exists for this recipient/)).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Create the 27 draft web forms' })).not.toBeInTheDocument();
  });

  it('retries ambiguous delivery with the same idempotency key, recipient and revision', async () => {
    await open(); failure = 'ambiguous'; await confirmCreate();
    await screen.findByText(/Delivery was interrupted/);
    expect(screen.getByRole('button', { name: 'Create the 27 draft web forms' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Retry original collection operation' }));
    await screen.findByText(/The collection is saved/);
    expect(posts).toHaveLength(2); expect(posts[1]).toEqual(posts[0]);
    expect(catalog.collections).toHaveLength(1); expect(catalog.collections[0].requests).toHaveLength(27);
    expect(onBusyChange).toHaveBeenCalledWith(true);
  });

  it('does not blindly retry a conflict and reloads the saved collection explicitly', async () => {
    await open(); failure = 'conflict'; await confirmCreate();
    await screen.findByText(/The assessment changed or this collection already exists/);
    expect(screen.queryByRole('button', { name: 'Retry original collection operation' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create the 27 draft web forms' })).toBeDisabled();
    catalog.collections.push(savedCollection()); catalog.revision++;
    fireEvent.click(screen.getByRole('button', { name: 'Reload saved collection' }));
    await screen.findByText(/A collection already exists for this recipient/);
    expect(posts).toHaveLength(1); expect(screen.queryByRole('button', { name: 'Create the 27 draft web forms' })).not.toBeInTheDocument();
  });

  it('prepares one immutable ZIP plus consolidated guide and all 27 individual Excel links', async () => {
    catalog.collections.push(savedCollection()); await open();
    fireEvent.click(screen.getByRole('button', { name: 'Prepare complete Excel collection' }));
    const zip = await screen.findByRole('link', { name: 'Download all 27 Excel forms + consolidated guide (ZIP)' });
    expect(zip).toHaveAttribute('href', `${base}/collections/dcollection-one/exports/dpackage-1/download`);
    expect(zip).toHaveAttribute('download');
    expect(screen.getByRole('link', { name: 'Download consolidated questions and guide (Excel)' })).toHaveAttribute('href', `${base}/collections/dcollection-one/exports/dpackage-1/index`);
    expect(screen.getByRole('heading', { name: 'Download individual editable Excel forms' })).toBeVisible();
    for (let number = 1; number <= 27; number++) expect(screen.getByRole('link', { name: `source-class-${number}.xlsx` })).toHaveAttribute('href', `${base}/exports/dexport-${number}/download`);
    expect(screen.getByText(/The guide is a reading and navigation copy, not an answer-import form/)).toBeVisible();
    expect(JSON.parse(String(posts[0].options.body))).toEqual({ expectedRevision: 8 });
    expect(posts[0].path).toBe(`${base}/collections/dcollection-one/exports`);
  });

  it('keeps contributor views read-only for collection management and opens exact assigned forms', async () => {
    catalog.canPrepare = false; catalog.collections.push(savedCollection());
    catalog.collections[0].packages.push(excelPackage(catalog.collections[0]));
    await open(false, { ...actor, role: 'contributor' });
    expect(screen.queryByLabelText('Collection recipient')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Prepare complete|Create the 27/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('Open individual web forms and response status'));
    expect(screen.getByText('Response submitted. No further response is required now.')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Read submitted response' }));
    expect(onNavigate).toHaveBeenCalledWith('discovery-request', { assessment: assessmentId, request: 'discovery-1' });
    expect(screen.getAllByRole('button', { name: 'Open or resume form' })).toHaveLength(26);
    expect(posts).toHaveLength(0);
  });

  it('pauses preparation when parent has unsaved changes without disabling read-only catalog exploration', async () => {
    catalog.collections.push(savedCollection()); await open(true);
    expect(screen.getByLabelText('Collection recipient')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Prepare complete Excel collection' })).toBeDisabled();
    fireEvent.click(screen.getByText('Browse all 27 forms by PQC discovery domain'));
    expect(screen.getByRole('heading', { name: 'PQC domain 10' })).toBeVisible();
    expect(posts).toHaveLength(0);
  });

  it('retains old exports at the package limit and rejects off-assessment or unsafe download URLs', async () => {
    const collection = savedCollection();
    collection.packages = [1, 2, 3].map(index => excelPackage(collection, index));
    collection.packages[0].zipUrl = 'https://example.com/export.zip';
    collection.packages[1].zipUrl = '/api/assessments/another/discovery/exports/file/download';
    collection.packages[2].zipUrl = `${base}/exports/%2e%2e/download`;
    catalog.collections = [collection]; await open();
    expect(screen.getByRole('button', { name: 'Prepare complete Excel collection' })).toBeDisabled();
    expect(screen.queryByRole('link', { name: 'Download all 27 Excel forms + consolidated guide (ZIP)' })).not.toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'Download consolidated questions and guide (Excel)' })).toHaveLength(3);
    expect(screen.getAllByText('Download unavailable: reload the saved collection.')).toHaveLength(3);
    expect(posts).toHaveLength(0);
  });

  it('distinguishes a load failure from an empty collection and recovers by read-only reload', async () => {
    failure = 'load';
    render(<DiscoveryCollection assessmentId={assessmentId} sourceRevision={8} session={actor} disabled={false} onChanged={onChanged} onBusyChange={onBusyChange} onNavigate={onNavigate} />);
    await screen.findByRole('alert');
    expect(screen.queryByText(/No collection is available/)).not.toBeInTheDocument();
    failure = ''; fireEvent.click(screen.getByRole('button', { name: 'Reload saved collection' }));
    await waitFor(() => expect(screen.getByText(/No collection is available to your signed-in identity yet/)).toBeVisible());
    expect(posts).toHaveLength(0);
  });

  it('preserves the successful receipt when the parent request list refreshes', async () => {
    history.replaceState(null, '', `#discovery?assessment=${assessmentId}`);
    render(<DiscoveryWorkspace session={actor} mode="list" onNavigate={onNavigate} />);
    await screen.findByRole('heading', { name: 'The five questions, in one place' });
    await confirmCreate();
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Open five-question request' })).toHaveLength(27));
    expect(screen.getByText(/The collection is saved/)).toBeVisible();
    expect(screen.getByText(/no email or response was sent/)).toBeVisible();
    expect(posts).toHaveLength(1);
  });

  it('retains receipt and recovers a failed parent readback without repeating the command', async () => {
    history.replaceState(null, '', `#discovery?assessment=${assessmentId}`);
    render(<DiscoveryWorkspace session={actor} mode="list" onNavigate={onNavigate} />);
    await screen.findByRole('heading', { name: 'The five questions, in one place' });
    failure = 'list-readback'; await confirmCreate();
    await screen.findByText(/The collection is saved, but the request list could not be refreshed/);
    expect(screen.getByText(/Its 27 requests are drafts/)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Prepare complete Excel collection' })).toBeDisabled();
    failure = ''; fireEvent.click(screen.getByRole('button', { name: 'Reload request list' }));
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Open five-question request' })).toHaveLength(27));
    expect(screen.getByText(/Its 27 requests are drafts/)).toBeVisible();
    expect(posts).toHaveLength(1);
  });

  it('does not offer preparation controls without a current CSRF session', async () => {
    catalog.collections.push(savedCollection()); await open(false, { ...actor, csrfToken: null });
    expect(screen.getByRole('button', { name: 'Prepare complete Excel collection' })).toBeDisabled();
    expect(screen.getByLabelText('Collection recipient')).toBeDisabled();
    expect(screen.getByText(/Sign in again to prepare collections/)).toBeVisible();
    expect(posts).toHaveLength(0);
  });
});
