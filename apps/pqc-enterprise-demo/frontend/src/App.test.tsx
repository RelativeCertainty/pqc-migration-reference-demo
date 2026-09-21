import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { api } from './api';
import { testAnalysis } from './analysis-test-fixture';
import type { Dashboard, ReportMetadata, Session } from './contracts';

const analyst: Session = { authenticated: true, role: 'analyst', synthetic: true, csrfToken: 'synthetic-test-csrf' };
const dashboard: Dashboard = {
  baseline: { baselineId: 'synthetic-baseline-test', inputSha256: 'a'.repeat(64), asOf: '2026-09-01T00:00:00Z', tenantId: 'synthetic-test', synthetic: true, assetCount: 17, acceptanceStatus: 'unaccepted', sourceSystemWriteAuthority: false },
  counts: { assets: 17, observations: 20, dependencies: 12, cryptographicUses: 29, sourceFamilies: 2, estateAreas: 2, limitations: 4, conflictedAssets: 1, staleAssets: 2, contextOnlyAssets: 3, reports: 0 },
  families: [{ id: 'cmdb', name: 'Context repository', areaRef: 'area-01', assetCount: 9, observationCount: 10, status: 'synthetic_only' }, { id: 'ssh', name: 'Machine access', areaRef: 'area-04', assetCount: 8, observationCount: 10, status: 'synthetic_only' }],
  triageLanes: [], limitations: [], boundary: 'Synthetic test only',
};
const report: ReportMetadata = { id: 'report-test', phase: 'phase1', title: 'Synthetic current-state report', baselineId: dashboard.baseline.baselineId, inputSha256: dashboard.baseline.inputSha256, createdAt: '2026-09-05T12:00:00Z', contentSha256: 'b'.repeat(64), synthetic: true, acceptanceStatus: 'unaccepted', workerRunId: 'run-test' };

let session = analyst;
let reports: ReportMetadata[] = [];
const fetchMock = vi.fn(async (input: RequestInfo | URL, options?: RequestInit) => {
  const path = String(input);
  let body: unknown;
  if (path === '/api/session') body = session;
  else if (path === '/api/dashboard') body = dashboard;
  else if (path.startsWith('/api/analysis?')) body = testAnalysis;
  else if (path === '/api/actions') body = [];
  else if (path === '/api/sources') body = dashboard.families;
  else if (path.startsWith('/api/assets?')) body = { items: [], total: 0, page: 1, pageSize: 20 };
  else if (path === '/api/reports' && options?.method === 'POST') { reports = [report]; body = report; }
  else if (path === '/api/reports') body = reports;
  else if (path === '/api/reports/report-test') body = { metadata: report, content: { title: report.title, inventory: [], limitations: [] } };
  else if (path === '/api/runs') body = [];
  else throw new Error(`Unexpected test API route: ${path}`);
  return new Response(JSON.stringify(body), { status: options?.method === 'POST' ? 201 : 200, headers: { 'Content-Type': 'application/json' } });
});

beforeEach(() => {
  window.localStorage.clear();
  history.replaceState(null, '', '#overview');
  session = analyst; reports = []; fetchMock.mockClear();
  vi.stubGlobal('fetch', fetchMock);
  vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined);
  vi.spyOn(HTMLDialogElement.prototype, 'showModal').mockImplementation(function (this: HTMLDialogElement) { this.setAttribute('open', ''); });
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('connected enterprise application', () => {
  it('applies the explicit appearance preference to the authenticated workspace only', async () => {
    window.localStorage.setItem('pqc.workspace.theme.v1', 'light');
    const view = render(<App />);
    const picker = await screen.findByRole('combobox', { name: 'Theme' });
    expect(picker.closest('.app-theme')).toHaveAttribute('data-theme', 'light');
    expect(document.documentElement).toHaveAttribute('data-workspace-theme', 'light');
    fireEvent.change(picker, { target: { value: 'dark' } });
    expect(picker.closest('.app-theme')).toHaveAttribute('data-theme', 'dark');
    expect(document.documentElement).toHaveAttribute('data-workspace-theme', 'dark');
    view.unmount();
    expect(document.documentElement).not.toHaveAttribute('data-workspace-theme');
    session = { authenticated: false, role: null, csrfToken: null, synthetic: true };
    render(<App />);
    expect(await screen.findByRole('heading', { name: 'Open the workspace' })).toBeInTheDocument();
    expect(screen.queryByRole('combobox', { name: 'Theme' })).not.toBeInTheDocument();
    expect(document.querySelector('.login-layout')?.closest('.app-theme')).toBeNull();
    expect(document.documentElement).not.toHaveAttribute('data-workspace-theme');
  });
  it('renders dashboard metrics returned by the API, not production or invented coverage', async () => {
    render(<App />);
    expect(await screen.findByRole('heading', { name: 'Evidence. Exposure. Next action.' })).toBeInTheDocument();
    expect(await screen.findByText('17')).toBeInTheDocument();
    expect(screen.getByText('29')).toBeInTheDocument();
    expect(screen.getByText(/Review priority is not an enterprise risk rating/)).toBeInTheDocument();
    expect(screen.getByText('SYNTHETIC DATA')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/analysis?'), expect.objectContaining({ credentials: 'same-origin' }));
  });

  it('starts a real API search and exposes a useful empty state', async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: 'Asset explorer' }));
    fireEvent.change(await screen.findByRole('searchbox'), { target: { value: 'an-owned-application' } });
    await waitFor(() => expect(fetchMock.mock.calls.some(([path]) => String(path).includes('q=an-owned-application'))).toBe(true));
    expect(await screen.findByRole('heading', { name: 'No matching assets' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
  });

  it('cancels obsolete search requests when the query changes', async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: 'Asset explorer' }));
    await screen.findByRole('heading', { name: 'No matching assets' });
    const firstCall = fetchMock.mock.calls.find(([path]) => String(path).startsWith('/api/assets?'));
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'changed-query' } });
    await waitFor(() => expect(firstCall?.[1]?.signal?.aborted).toBe(true));
  });

  it('keeps legacy report generation unavailable for a viewer', async () => {
    session = { ...analyst, role: 'viewer' };
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: 'Reporting workspace' }));
    expect(await screen.findByRole('button', { name: /Open Phase 1 assessment step/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Open Phase 2 assessment step/ })).toBeDisabled();
    expect(screen.getAllByText(/Legacy reports are read-only/)).toHaveLength(2);
    expect(fetchMock.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false);
  });

  it('does not permit analyst report-generation writes outside an assessment', async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: 'Reporting workspace' }));
    expect(await screen.findByRole('button', { name: /Open Phase 2 assessment step/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Open Phase 1 assessment step/ })).toBeDisabled();
    expect(fetchMock.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false);
  });

  it('retains legacy report readback and downloads without bypassing assessment gates', async () => {
    reports = [report];
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: 'Reporting workspace' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Preview report' }));
    expect(await screen.findByRole('heading', { name: report.title, level: 2 })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Download full HTML' })).toHaveAttribute('href', '/api/reports/report-test/download?format=html');
    expect(fetchMock.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false);
  });

  it('labels future migration controls as not enabled', async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: 'Migration lookahead' }));
    expect(await screen.findByText('A closed ticket is not a verified migration.')).toBeInTheDocument();
    expect(screen.getAllByText('Proposed · not enabled')).toHaveLength(2);
    expect(screen.queryByRole('button', { name: /execute migration/i })).not.toBeInTheDocument();
  });

  it('offers only synthetic demo identities when no session exists', async () => {
    session = { authenticated: false, role: null, csrfToken: null, synthetic: true };
    render(<App />);
    expect(await screen.findByRole('heading', { name: 'Open the workspace' })).toBeInTheDocument();
    expect(screen.getByText(/Never enter an enterprise password here/)).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Analyst/ })).toBeChecked();
  });

  it('keeps the addressable route when the keyboard skip link focuses the workspace', async () => {
    history.replaceState(null, '', '#reports');
    render(<App />);
    await screen.findByRole('button', { name: /Open Phase 1 assessment step/ });
    fireEvent.click(screen.getByRole('link', { name: 'Skip to content' }));
    expect(window.location.hash).toBe('#reports');
    expect(document.getElementById('main-content')).toHaveFocus();
  });

  it('labels local review runs separately from report generation', async () => {
    vi.stubGlobal('fetch', async (input: RequestInfo | URL, options?: RequestInit) => String(input) === '/api/runs' ? Response.json([{ id: 'review-run', phase: 'review', reportId: null, status: 'succeeded', actor: 'synthetic-analyst', createdAt: '2026-09-05T12:00:00Z', baselineId: 'baseline-test', manifestId: 'local-review-manifest', result: { actionId: 'review-action', artifactSha256: 'a'.repeat(64) } }]) : fetchMock(input, options));
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: 'Run ledger' }));
    expect(await screen.findByText('FINDING REVIEW')).toBeInTheDocument();
    expect(screen.getByText('Review result')).toBeInTheDocument();
    expect(screen.getByText('review-action')).toBeInTheDocument();
    expect(screen.queryByText('PHASE 2 REPORT')).not.toBeInTheDocument();
  });
});

describe('API safety', () => {
  it('never echoes backend error payloads', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{"error":"sensitive-server-detail"}', { status: 500 })));
    await expect(api('/api/assets')).rejects.toThrow('The application could not complete this request.');
  });
  it('rejects off-origin API paths before fetch', async () => {
    await expect(api('https://example.invalid/api/assets')).rejects.toThrow('Only same-origin');
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it('turns recognized bounded error codes into actionable copy without echoing server text', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Response.json({ error: { code: 'assessment_revision_changed', message: 'do not echo this detail' } }, { status: 409 })));
    await expect(api('/api/assessments/test')).rejects.toThrow('Another participant changed this assessment.');
  });
  it('ignores oversized or unrecognized error envelopes', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Response.json({ error: { code: 'assessment_revision_changed', message: 'x'.repeat(5000) } }, { status: 409 })));
    await expect(api('/api/assessments/test')).rejects.toThrow('This request conflicts with an existing operation.');
  });
});
