import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AnalysisWorkspace } from './AnalysisWorkspace';
import { NarrativeReport } from './NarrativeReport';
import { testAnalysis, testFinding } from './analysis-test-fixture';
import type { ActionRecord, Narrative } from './analysis-contracts';
import type { Report, Session } from './contracts';

const analyst: Session = { authenticated: true, role: 'analyst', csrfToken: 'synthetic-csrf', synthetic: true };
let actions: ActionRecord[] = [];
let failWrites = false;
const fetchMock = vi.fn(async (input: RequestInfo | URL, options?: RequestInit) => {
  const path = String(input);
  if (path.startsWith('/api/analysis?')) return Response.json(testAnalysis);
  if (path === '/api/actions') return Response.json(actions);
  if (path === '/api/actions/finding-test' && options?.method === 'POST') {
    if (failWrites) return Response.json({ error: { code: 'revision_conflict' } }, { status: 409 });
    const body = JSON.parse(String(options.body));
    const record: ActionRecord = { id: 'action-test', findingId: 'finding-test', operation: body.operation, disposition: body.disposition, note: body.note, revision: 1, createdAt: '2026-09-05T12:00:00Z', actor: 'synthetic-analyst', evidenceRequestDraft: body.operation === 'prepare_evidence_request' ? 'Please identify an existing inventory, report, document reference or team. A referral or not sure is useful.' : null, status: 'needs_evidence', synthetic: true, externalDelivery: false, executionAuthorized: false };
    actions = [record]; return Response.json(record, { status: 201 });
  }
  throw new Error(`Unexpected synthetic test route ${path}`);
});

beforeEach(() => {
  history.replaceState(null, '', '#overview'); actions = []; failWrites = false; fetchMock.mockClear();
  vi.stubGlobal('fetch', fetchMock);
  vi.spyOn(HTMLElement.prototype, 'scrollIntoView').mockImplementation(() => undefined);
  vi.spyOn(HTMLDialogElement.prototype, 'showModal').mockImplementation(function (this: HTMLDialogElement) { this.setAttribute('open', ''); });
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('analytical workspace', () => {
  it('explains an empty combined owner/family selection and clears only the owner while retaining assessment context', async () => {
    history.replaceState(null, '', '#actions?assessment=assessment-test&owner=owner-test&family=traffic');
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => String(input).includes('/analysis?') ? Response.json({ ...testAnalysis, findings: [] }) : Response.json([])));
    render(<AnalysisWorkspace mode="queue" readOnly session={analyst} onInspect={vi.fn()} onReports={vi.fn()} />);
    expect(await screen.findByText('No findings match these combined filters.')).toBeInTheDocument();
    expect(screen.getByText(/The accountable owner and source family filters apply together/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Clear owner filter' }));
    const params = new URLSearchParams(window.location.hash.split('?')[1]);
    expect(params.get('assessment')).toBe('assessment-test');
    expect(params.get('family')).toBe('traffic');
    expect(params.has('owner')).toBe(false);
  });

  it('keeps assessment investigation read-only and returns findings to the grouped workflow', async () => {
    history.replaceState(null, '', '#actions?assessment=assessment-test');
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => String(input).includes('/analysis?') ? Response.json(testAnalysis) : Response.json([])));
    render(<AnalysisWorkspace mode="queue" readOnly session={analyst} onInspect={vi.fn()} onReports={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: /View finding/ }));
    expect(screen.queryByRole('button', { name: /Save disposition/ })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Return to assessment/ })).toHaveAttribute('href', '#assessments?assessment=assessment-test&stage=3');
  });

  it('applies all five filters to one shared analysis API request', async () => {
    render(<AnalysisWorkspace session={analyst} onInspect={vi.fn()} onReports={vi.fn()} />);
    await screen.findByRole('heading', { name: 'Follow the dependency.' });
    for (const [label, value] of [['Business service', 'service-test'], ['Accountable owner', 'owner-test'], ['Environment', 'test'], ['Technology', 'TLS'], ['Source family', 'traffic']]) {
      fireEvent.change(screen.getByRole('combobox', { name: label }), { target: { value } });
      await screen.findByRole('heading', { name: 'Follow the dependency.' });
    }
    await waitFor(() => expect(fetchMock.mock.calls.some(([path]) => String(path).includes('service=service-test&owner=owner-test&environment=test&technology=TLS&family=traffic'))).toBe(true));
    expect(screen.getByText(/Every filter applies to the graph, distributions, coverage and findings/)).toBeInTheDocument();
    expect(window.location.hash).toContain('family=traffic');
  });

  it('selects real graph nodes with the keyboard and drills into the source subject', async () => {
    const inspect = vi.fn();
    render(<AnalysisWorkspace session={analyst} onInspect={inspect} onReports={vi.fn()} />);
    const node = await screen.findByRole('button', { name: 'Select TLS key exchange, Cryptographic use' });
    fireEvent.keyDown(node, { key: 'Enter' });
    expect(node).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'Inspect source asset ↗' }));
    expect(inspect).toHaveBeenCalledWith('asset-test');
    expect(screen.getByText(/2 of 2 nodes/)).toBeInTheDocument();
  });

  it('allows viewers to inspect a finding but not record actions or prepare a draft', async () => {
    render(<AnalysisWorkspace session={{ ...analyst, role: 'viewer' }} onInspect={vi.fn()} onReports={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: /View finding/ }));
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByRole('button', { name: 'Record local review' })).toBeDisabled();
    expect(within(dialog).getByRole('combobox', { name: 'Operation' })).toBeDisabled();
    expect(within(dialog).getByText(/Viewer access: actions are read-only/)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false);
  });

  it.each([['Exposure signals', 'Public key use'], ['Change readiness', 'Needs qualification'], ['Review priorities', 'Resolve evidence']])('drills %s into only matching findings', async (title, category) => {
    const extra = { ...testFinding, id: 'other-finding', title: 'An unrelated context finding', priority: 'context_only', exposure: 'unknown', readiness: 'not_assessed' };
    vi.stubGlobal('fetch', async (input: RequestInfo | URL, options?: RequestInit) => String(input).startsWith('/api/analysis?') ? Response.json({ ...testAnalysis, findings: [testFinding, extra] }) : fetchMock(input, options));
    render(<AnalysisWorkspace session={analyst} onInspect={vi.fn()} onReports={vi.fn()} />);
    const panel = (await screen.findByRole('heading', { name: title })).closest('section')!;
    expect(screen.getByRole('heading', { name: extra.title })).toBeInTheDocument();
    fireEvent.click(within(panel).getByRole('button', { name: category }));
    expect(screen.queryByRole('heading', { name: extra.title })).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: testFinding.title })).toBeInTheDocument();
  });

  it('drills coverage memberships into actual assets and preserves empty groups', async () => {
    const inspect = vi.fn();
    render(<AnalysisWorkspace session={analyst} onInspect={inspect} onReports={vi.fn()} />);
    for (const group of ['Mapped subjects', 'Disputed subjects']) {
      fireEvent.click(await screen.findByRole('button', { name: `Encrypted traffic: ${group}, 1` }));
      const drilldown = screen.getByRole('region', { name: 'Coverage subject drilldown' });
      expect(within(drilldown).getByText(/1 selected subjects/)).toBeInTheDocument();
      fireEvent.click(within(drilldown).getByRole('button', { name: 'Synthetic edge ↗' }));
      expect(inspect).toHaveBeenCalledWith('asset-test');
    }
    for (const group of ['No use evidence', 'Stale subjects']) {
      fireEvent.click(screen.getByRole('button', { name: `Encrypted traffic: ${group}, 0` }));
      expect(within(screen.getByRole('region', { name: 'Coverage subject drilldown' })).getByText(/No subjects in this area/)).toBeInTheDocument();
    }
  });

  it('places role-based graph lanes left to right and never opens reference-only nodes as assets', async () => {
    vi.stubGlobal('fetch', async (input: RequestInfo | URL, options?: RequestInit) => String(input).startsWith('/api/analysis?') ? Response.json({ ...testAnalysis, graph: { ...testAnalysis.graph, nodes: [...testAnalysis.graph.nodes, { id: 'service-ref', label: 'Service reference (name not supplied)', kind: 'business_service', subjectId: 'not-an-asset', inScope: true, areaRefs: ['area-03'] }] } }) : fetchMock(input, options));
    render(<AnalysisWorkspace session={analyst} onInspect={vi.fn()} onReports={vi.fn()} />);
    const asset = await screen.findByRole('button', { name: 'Select Synthetic edge, Asset' });
    const use = screen.getByRole('button', { name: 'Select TLS key exchange, Cryptographic use' });
    expect(asset).toHaveAttribute('transform', 'translate(428 68)');
    expect(use).toHaveAttribute('transform', 'translate(632 68)');
    fireEvent.click(screen.getByRole('button', { name: 'Select Service reference (name not supplied), Business service' }));
    expect(screen.queryByRole('button', { name: 'Inspect source asset ↗' })).not.toBeInTheDocument();
    expect(screen.getByText('Reference only — no source asset record')).toBeInTheDocument();
  });

  it('prepares an information-request draft without changing operation, revision, CSRF or idempotency binding', async () => {
    render(<AnalysisWorkspace session={analyst} onInspect={vi.fn()} onReports={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: /View finding/ }));
    fireEvent.change(screen.getByRole('combobox', { name: 'Operation' }), { target: { value: 'prepare_evidence_request' } });
    expect(screen.getByRole('option', { name: 'Prepare information request draft' })).toHaveValue('prepare_evidence_request');
    expect(screen.getByText(/This is not a request to demonstrate compliance/)).toHaveTextContent('The assessment team coordinates any later technical review separately.');
    expect(screen.getByRole('textbox', { name: /Review note/ })).toHaveAttribute('maxlength', '800');
    fireEvent.change(screen.getByRole('textbox', { name: /Review note/ }), { target: { value: 'Confirm the authoritative configuration source.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Prepare local draft — do not send' }));
    expect(await screen.findByText('Information request draft — not sent')).toBeInTheDocument();
    expect(screen.getByText('Please identify an existing inventory, report, document reference or team. A referral or not sure is useful.')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith('/api/actions/finding-test', expect.objectContaining({ method: 'POST', headers: expect.objectContaining({ 'X-PQC-CSRF': analyst.csrfToken, 'Idempotency-Key': expect.any(String) }), body: expect.stringContaining('"expectedRevision":0') }));
    expect(screen.queryByRole('button', { name: /^send/i })).not.toBeInTheDocument();
  });

  it('preserves stored draft wording and never rewrites history when the display label changes', async () => {
    const historicalDraft = 'DRAFT — NOT SENT\nSubject: Evidence request — historical original\nOriginal coordinator wording remains unchanged.';
    actions = [{ id: 'action-legacy', findingId: 'finding-test', operation: 'prepare_evidence_request', disposition: null, note: 'Historical note.', revision: 1, createdAt: '2026-09-05T12:00:00Z', actor: 'synthetic-analyst', evidenceRequestDraft: historicalDraft, status: 'needs_evidence', synthetic: true, externalDelivery: false, executionAuthorized: false }];
    render(<AnalysisWorkspace session={analyst} onInspect={vi.fn()} onReports={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: /View finding/ }));
    expect(screen.getByRole('heading', { name: 'Information request draft — not sent' })).toBeInTheDocument();
    expect(screen.getByText(/Subject: Evidence request — historical original/).textContent).toBe(historicalDraft);
    expect(fetchMock.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false);
  });

  it('preserves the operator note when concurrent state prevents a write', async () => {
    failWrites = true;
    render(<AnalysisWorkspace session={analyst} onInspect={vi.fn()} onReports={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: /View finding/ }));
    fireEvent.change(screen.getByRole('textbox', { name: /Review note/ }), { target: { value: 'Keep this review context.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Record local review' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Your note is preserved');
    expect(screen.getByRole('textbox', { name: /Review note/ })).toHaveValue('Keep this review context.');
  });

  it('links conditional business impact and accountable decision context without inventing vendor failure', async () => {
    const impact = { id: 'impact-test', subjectId: 'asset-test', title: 'Operational impact to validate', rationale: 'A relying application may depend on this endpoint; the dependency requires owner validation.', observationRefs: ['observation-test'], owner: 'owner-test', action: 'Confirm the relying service and continuity requirement.', readiness: 'product_qualification_required', evidenceState: 'disputed' };
    vi.stubGlobal('fetch', async (input: RequestInfo | URL, options?: RequestInit) => String(input).startsWith('/api/analysis?') ? Response.json({ ...testAnalysis, findings: [{ ...testFinding, readiness: 'product_qualification_required' }], businessImpacts: [impact] }) : fetchMock(input, options));
    render(<AnalysisWorkspace session={analyst} onInspect={vi.fn()} onReports={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Exact-product qualification pending →' }));
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByText(impact.rationale)).toBeInTheDocument();
    expect(within(dialog).getByText(/Confirm the relying service/)).toBeInTheDocument();
    expect(within(dialog).getByRole('heading', { name: 'Identify the source authority' })).toBeInTheDocument();
    expect(within(dialog).getByText('Conditional assessment context, not a quantified business loss.')).toBeInTheDocument();
    expect(within(dialog).getByText(/does not establish vendor blockage/)).toBeInTheDocument();
  });
});

describe('executive-first report reader', () => {
  it('presents conclusions and accountable actions before the collapsible technical appendix', () => {
    const narrative: Narrative = {
      executiveSummary: [{ title: 'Resolve disputed evidence before reliance', body: 'The mock cohort contains a source disagreement that constrains the assessment.' }],
      sections: [{ id: 'findings', title: 'Principal findings', summary: 'Prioritize source reconciliation.', paragraphs: ['The finding is supported by a retained source observation.'], findingIds: [testFinding.id] }],
      nextSteps: [{ title: 'Obtain source confirmation', owner: 'Synthetic platform owner', action: 'Provide dated readback evidence.', decisionRequired: 'Name the authoritative source.', consequence: 'The conclusion remains qualified.' }],
      questions: ['Who can confirm the configured exchange?'], caveats: ['No enterprise acceptance or source-system writes.'],
    };
    const report: Report = { metadata: { id: 'report-test', phase: 'phase2', title: 'Mock risk and migration review', baselineId: 'baseline-test', inputSha256: 'a'.repeat(64), createdAt: '2026-09-05T12:00:00Z', contentSha256: 'b'.repeat(64), synthetic: true, acceptanceStatus: 'unaccepted', workerRunId: 'run-test' }, content: { schemaVersion: 'pqc.enterprise.report.v2', narrative, analysis: testAnalysis } };
    const inspect = vi.fn(); const review = vi.fn();
    render(<NarrativeReport report={report} onInspect={inspect} onReview={review} />);
    expect(screen.getByRole('heading', { name: 'What matters. Why. What next.' })).toBeInTheDocument();
    expect(screen.getByText('Provide dated readback evidence.')).toBeInTheDocument();
    expect(screen.getByText('The conclusion remains qualified.')).toBeInTheDocument();
    const appendix = screen.getByText('Evidence appendix, method and immutable report provenance').closest('details');
    expect(appendix).not.toHaveAttribute('open');
    fireEvent.click(screen.getByRole('button', { name: 'Inspect Synthetic edge ↗' }));
    expect(inspect).toHaveBeenCalledWith('asset-test');
    fireEvent.click(screen.getByRole('button', { name: 'Open finding review →' }));
    expect(review).toHaveBeenCalledWith('finding-test');
  });
});
