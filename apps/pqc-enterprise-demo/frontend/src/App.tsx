import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { AnalysisWorkspace } from './AnalysisWorkspace';
import { AssessmentWorkspace } from './AssessmentWorkspace';
import { IntakeWorkspace } from './IntakeWorkspace';
import { QuestionnaireWorkspace } from './QuestionnaireWorkspace';
import { DiscoveryWorkspace } from './DiscoveryWorkspace';
import { AssessmentWork } from './AssessmentWork';
import { NarrativeReport } from './NarrativeReport';
import { ReferenceWorkspace } from './ReferenceWorkspace';
import { CapacityWorkspace } from './CapacityWorkspace';
import { ThemeControl, useDocumentTheme, useWorkspaceTheme } from './theme';
import { api, assessmentApiPath, selectedAssessmentId, dateLabel, humanize, readable } from './api';
import type { Asset, AssetDetail, AssetPage, Family, RecordData, Report, ReportMetadata, Role, Run, Session } from './contracts';

type Page = 'assessment-work' | 'discovery-request' | 'discovery' | 'questionnaire' | 'questionnaires' | 'intake' | 'assessments' | 'overview' | 'assets' | 'sources' | 'reports' | 'runs' | 'lookahead' | 'actions' | 'reference' | 'capacity';
const pages: { id: Page; label: string; icon: string }[] = [
  { id: 'assessment-work', label: 'Assessment work', icon: 'route' },
  { id: 'discovery', label: 'Discovery & mobilization', icon: 'route' },
  { id: 'questionnaires', label: 'Specialist questionnaires', icon: 'file' },
  { id: 'intake', label: 'Historical routing & intake', icon: 'layers' },
  { id: 'assessments', label: 'Guided assessment', icon: 'route' },
  { id: 'overview', label: 'Estate overview', icon: 'grid' },
  { id: 'assets', label: 'Asset explorer', icon: 'search' },
  { id: 'sources', label: 'Source coverage', icon: 'layers' },
  { id: 'actions', label: 'Findings & decisions', icon: 'route' },
  { id: 'reports', label: 'Reporting workspace', icon: 'file' },
  { id: 'runs', label: 'Run ledger', icon: 'history' },
  { id: 'lookahead', label: 'Migration lookahead', icon: 'route' },
  { id: 'reference', label: 'Reference explanations', icon: 'layers' },
  { id: 'capacity', label: 'Capacity planning', icon: 'grid' },
];
function hashPage(): Page {
  const candidate = window.location.hash.replace(/^#\/?/, '').split('?')[0];
  return ['questionnaire', 'discovery-request'].includes(candidate) || pages.some(page => page.id === candidate) ? candidate as Page : 'assessment-work';
}

const areas: Record<string, string> = {
  'area-01': 'Enterprise context', 'area-02': 'PKI & trust', 'area-03': 'Encrypted traffic',
  'area-04': 'Machine access', 'area-05': 'Software delivery', 'area-06': 'Cloud, keys & identity',
  'area-07': 'Protected data', 'area-08': 'Distributed endpoints',
  'area-09': 'Specialized cryptography', 'area-10': 'Governance & assurance',
};

function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const paths: Record<string, ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></>,
    layers: <><path d="m3 7 9-4 9 4-9 4-9-4Zm0 5 9 4 9-4M3 17l9 4 9-4" /></>,
    file: <><path d="M14 3H5v18h14V8l-5-5ZM14 3v5h5M8 12h8M8 16h6" /></>,
    history: <><path d="M4 7a9 9 0 1 1-1 8M4 3v5h5M12 7v6l4 2" /></>,
    route: <><circle cx="5" cy="5" r="2" /><circle cx="19" cy="19" r="2" /><path d="M7 5h9a4 4 0 0 1 0 8H8a3 3 0 0 0 0 6h9" /></>,
    arrow: <path d="M4 12h15m-5-5 5 5-5 5" />,
    close: <path d="m6 6 12 12M6 18 18 6" />,
    lock: <><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3" /></>,
    check: <path d="m5 12 4 4L19 6" />,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.file}</svg>;
}

function useLoad<T>(path: string, revision = 0) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(''); setData(undefined);
    api<T>(path, { signal: controller.signal }).then(value => {
      if (!controller.signal.aborted) setData(value);
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'The request could not be completed.');
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [path, retry, revision]);
  return { data, error, loading, reload: () => setRetry(value => value + 1) };
}

function LoadState({ loading, error, reload }: { loading: boolean; error: string; reload: () => void }) {
  if (error) return <div className="notice error" role="alert"><span>{error}</span><button className="button secondary" onClick={reload}>Try again</button></div>;
  if (loading) return <div className="loading" role="status"><span className="spinner" />Loading from the application…</div>;
  return null;
}

function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: string }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

function AssetStatus({ status }: { status: string }) {
  const statuses: Record<string, [string, string]> = {
    conflict: ['Conflicting evidence', 'attention'], stale: ['Stale evidence', 'attention'],
    context_only: ['Context only', 'neutral'], evidence_present: ['Evidence present', 'teal'],
  };
  const [label, tone] = statuses[status] || [humanize(status), 'neutral'];
  return <Badge tone={tone}>{label}</Badge>;
}

function AssetBadges({ asset }: { asset: Asset }) {
  return <span className="asset-badges"><AssetStatus status={asset.status} />{asset.isStale && asset.status !== 'stale' && <Badge tone="attention">Also stale</Badge>}{asset.isContextOnly && asset.status !== 'context_only' && <Badge>Context only</Badge>}</span>;
}

function PageHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <header className="page-header"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="page-description">{description}</p></div>{action}</header>;
}

function Login({ onLogin }: { onLogin: (session: Session) => void }) {
  const [role, setRole] = useState<Role>(() => ['questionnaire', 'discovery-request'].includes(hashPage()) ? 'contributor' : 'analyst');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try { onLogin(await api<Session>('/api/session', { method: 'POST', body: JSON.stringify({ role, password }) })); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Sign-in could not be completed.'); }
    finally { setBusy(false); }
  }
  return <main className="login-layout">
    <section className="login-story"><Brand /><div><p className="eyebrow">THE ENTERPRISE MAP</p><h1>From evidence.<br />To understanding.<br /><span>To a migration plan.</span></h1><p>Investigate one connected estate, follow the evidence, and build Phase 1 and Phase 2 reports from the same durable baseline.</p></div><div className="login-chain"><span>Discover</span><Icon name="arrow" /><span>Assess</span><Icon name="arrow" /><span>Plan</span></div></section>
    <section className="login-access"><form onSubmit={submit} className="login-card"><Badge tone="attention">ISOLATED SYNTHETIC DEMO</Badge><h2>Open the workspace</h2><p>This is a local development identity—not enterprise SSO. No live enterprise sources or migration controls are connected.</p><fieldset><legend>Demo role</legend><div className="role-options">{(['analyst', 'viewer'] as Role[]).map(value => <label key={value} className={role === value ? 'role-option selected' : 'role-option'}><input type="radio" name="role" value={value} checked={role === value} onChange={() => setRole(value)} /><strong>{humanize(value)}</strong><span>{value === 'analyst' ? 'Lead a guided assessment' : 'Read existing assessments and reports'}</span></label>)}</div></fieldset>
      <label className="field-label" htmlFor="review-persona">Or sign in as a contributing / reviewing persona</label><select id="review-persona" value={['analyst', 'viewer'].includes(role) ? '' : role} onChange={event => setRole(event.target.value as Role || 'analyst')}><option value="">Use selected role above</option><option value="contributor">Source contributor 1</option><option value="contributor-two">Source contributor 2</option><option value="reviewer">Technical reviewer</option><option value="sponsor">Assessment sponsor</option><option value="information-owner">Information owner</option><option value="risk-lead">Risk lead</option><option value="business-reviewer">Business reviewer</option></select>
      <p className="field-help">Signing in as <strong>{humanize(role)}</strong>. The server determines this persona’s permitted actions.</p><label className="field-label" htmlFor="demo-password">Synthetic demo password</label><input id="demo-password" type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} required /><p className="field-help">Use <code>synthetic-demo-only</code>. Never enter an enterprise password here.</p>{error && <p className="notice error" role="alert">{error}</p>}<button className="button primary login-submit" disabled={busy}>{busy ? 'Opening workspace…' : 'Open workspace'}<Icon name="arrow" /></button><div className="login-boundary"><Icon name="lock" size={17} /><span>Loopback access · synthetic tenant · no source-system writes</span></div></form></section>
  </main>;
}

function Brand() {
  return <div className="brand"><span className="brand-symbol"><Icon name="layers" size={25} /></span><span>PQC<span className="brand-subtitle">ENTERPRISE</span></span></div>;
}

function Assets({ initialStatus = '' }: { initialStatus?: string }) {
  const [query, setQuery] = useState('');
  const [debounced, setDebounced] = useState('');
  const [family, setFamily] = useState('');
  const [status, setStatus] = useState(initialStatus);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string>();
  const sources = useLoad<Family[]>('/api/sources');
  useEffect(() => { const timer = setTimeout(() => { setDebounced(query.trim()); setPage(1); }, 250); return () => clearTimeout(timer); }, [query]);
  const parameters = new URLSearchParams({ q: debounced, family, status, page: String(page), pageSize: '20' });
  const load = useLoad<AssetPage>(`/api/assets?${parameters}`);
  return <>
    <PageHeader eyebrow="INVESTIGATION" title="Asset explorer" description="Search the shared inventory, inspect cryptographic uses, and follow evidence and dependencies." />
    <section className="panel asset-panel"><div className="filter-grid"><label className="search-field"><span>Search assets</span><span className="input-icon"><Icon name="search" /><input type="search" placeholder="Name, identifier or source evidence…" value={query} maxLength={200} onChange={event => setQuery(event.target.value)} /></span></label><label><span>Source family</span><select value={family} onChange={event => { setFamily(event.target.value); setPage(1); }}><option value="">All source families</option>{sources.data?.map(source => <option key={source.id} value={source.id}>{source.name}</option>)}</select></label><label><span>Evidence status</span><select value={status} onChange={event => { setStatus(event.target.value); setPage(1); }}><option value="">All evidence states</option><option value="conflict">Conflicting evidence</option><option value="stale">Stale evidence</option><option value="context_only">Context only</option><option value="evidence_present">Evidence present</option></select></label></div>
      {sources.error && <p className="notice error" role="alert">Source filters are unavailable. <button className="text-button" onClick={sources.reload}>Reload filters</button></p>}
      <LoadState {...load} />
      {load.data && <><div className="result-summary" aria-live="polite"><strong>{load.data.total.toLocaleString()} assets</strong><span>Evidence presence is not verified migration readiness.</span></div>{load.data.items.length ? <div className="table-scroll"><table><thead><tr><th scope="col">Asset</th><th scope="col">Source family</th><th scope="col">Evidence status</th><th scope="col" className="numeric">Observations</th><th scope="col" className="numeric">Uses</th></tr></thead><tbody>{load.data.items.map(asset => <tr key={asset.id}><td><button className="asset-link" onClick={() => setSelected(asset.id)}>{asset.displayName}<Icon name="arrow" size={16} /></button><span className="record-id" title={asset.id}>{asset.id}</span></td><td>{asset.familyIds.map(id => sources.data?.find(source => source.id === id)?.name || humanize(id)).join(', ')}</td><td><AssetBadges asset={asset} /></td><td className="numeric">{asset.observationCount}</td><td className="numeric">{asset.cryptographicUseCount}</td></tr>)}</tbody></table></div> : <Empty title="No matching assets" detail="Try a different search term or clear the filters. Missing records are not silently substituted with examples." />}
      <div className="pagination"><span>Page {load.data.page} of {Math.max(1, Math.ceil(load.data.total / load.data.pageSize))}</span><div><button className="button secondary" disabled={page <= 1} onClick={() => setPage(value => value - 1)}>Previous</button><button className="button secondary" disabled={page * load.data.pageSize >= load.data.total} onClick={() => setPage(value => value + 1)}>Next</button></div></div></>}
    </section>{selected && <AssetDrawer id={selected} onClose={() => setSelected(undefined)} onSelect={setSelected} />}
  </>;
}

function RecordFields({ value, exclude = [] }: { value: RecordData; exclude?: string[] }) {
  return <dl className="record-fields">{Object.entries(value).filter(([key]) => !exclude.includes(key)).map(([key, item]) => <div key={key}><dt>{humanize(key)}</dt><dd>{readable(item)}</dd></div>)}</dl>;
}

function AssetDrawer({ id, onClose, onSelect }: { id: string; onClose: () => void; onSelect: (id: string) => void }) {
  const load = useLoad<AssetDetail>(`/api/assets/${encodeURIComponent(id)}`);
  const dialog = useRef<HTMLDialogElement>(null);
  const [tab, setTab] = useState('summary');
  useEffect(() => {
    const prior = document.activeElement as HTMLElement | null;
    dialog.current?.showModal();
    return () => { prior?.focus(); };
  }, []);
  useEffect(() => { setTab('summary'); }, [id]);
  const data = load.data;
  const tabs = [{ id: 'summary', label: 'Overview' }, { id: 'uses', label: 'Crypto uses', count: data?.cryptographicUses.length }, { id: 'evidence', label: 'Evidence', count: data?.observations.length }, { id: 'dependencies', label: 'Dependencies', count: data?.dependencies.length }];
  return <dialog ref={dialog} className="asset-dialog" onCancel={onClose} aria-labelledby="asset-title"><div className="drawer-header"><div><p className="eyebrow">ASSET INVESTIGATION</p><h2 id="asset-title">{data?.asset.displayName || 'Loading asset…'}</h2></div><button className="icon-button" onClick={onClose} aria-label="Close asset details"><Icon name="close" /></button></div><div className="drawer-body"><LoadState {...load} />{data && <><div className="drawer-meta"><AssetBadges asset={data.asset} /><Badge>Synthetic record</Badge><span>{data.asset.observationCount} observations</span></div><div className="detail-tabs" role="group" aria-label="Asset detail sections">{tabs.map(item => <button key={item.id} className={tab === item.id ? 'active' : ''} aria-pressed={tab === item.id} onClick={() => setTab(item.id)}>{item.label}{item.count !== undefined && <span>{item.count}</span>}</button>)}</div>
      {tab === 'summary' && <><h3>Normalized asset</h3><RecordFields value={data.asset.asset} /><h3>Recorded limitations</h3>{data.limitations.length ? data.limitations.map((item, index) => <div className="record-card" key={index}><RecordFields value={item} /></div>) : <p className="muted">No asset-specific limitation records. This does not establish enterprise completeness.</p>}<div className="quiet-note"><strong>Evidence baseline</strong><p className="mono">{data.baseline.baselineId}</p><p>As of {dateLabel(data.baseline.asOf)} · unaccepted synthetic baseline.</p></div></>}
      {tab === 'uses' && <><h3>Cryptography by purpose and role</h3><p className="muted">Key exchange, authentication, signing and data encryption are distinct uses—not one readiness flag.</p><RecordList rows={data.cryptographicUses} empty="No cryptographic use has been established for this asset." /></>}
      {tab === 'evidence' && <><h3>Source observations & custody references</h3><p className="muted">Configured, observed and vendor-reported facts retain their own basis. Synthetic observations are not enterprise verification.</p><RecordList rows={data.observations} empty="No source observations are available." /></>}
      {tab === 'dependencies' && <><h3>Business & technical dependencies</h3><p className="muted">Unresolved relationships remain limitations; follow linked subjects when present in the baseline.</p>{data.dependencies.length ? data.dependencies.map((item, index) => <div className="record-card" key={index}><RecordFields value={item} /><div className="dependency-actions">{[item.from_ref, ...(item.target_present === false ? [] : [item.to_ref]), item.source_ref, ...(item.target_present === false ? [] : [item.target_ref])].filter((value, position, all): value is string => typeof value === 'string' && value !== id && all.indexOf(value) === position).map(ref => <button key={ref} className="text-button" onClick={() => onSelect(ref)}>Inspect linked asset<Icon name="arrow" size={16} /></button>)}</div>{item.target_present === false && <p className="field-help">Target is not present in the baseline. This dependency remains unresolved.</p>}</div>) : <Empty title="No dependency links" detail="No relationships were returned for this subject." />}</>}
    </>}</div><div className="drawer-footer"><Icon name="lock" size={16} />Read-only investigation · no migration action</div></dialog>;
}

function RecordList({ rows, empty }: { rows: RecordData[]; empty: string }) {
  return rows.length ? <div className="record-list">{rows.map((row, index) => <div className="record-card" key={index}><RecordFields value={row} /></div>)}</div> : <Empty title="Nothing recorded" detail={empty} />;
}

function Empty({ title, detail }: { title: string; detail: string }) {
  return <div className="empty-state"><Icon name="layers" size={30} /><h3>{title}</h3><p>{detail}</p></div>;
}

function Sources() {
  const load = useLoad<Family[]>('/api/sources');
  return <><PageHeader eyebrow="DISCOVERY PROGRAM" title="Source coverage" description="Ten investigation areas, with each source family explicitly represented. Modeled does not mean connected or qualified." /><LoadState {...load} />{load.data && <><div className="source-summary"><strong>{load.data.length} modeled source families</strong><span>All displayed source records are synthetic. Enterprise completeness is unknown.</span><Badge tone="attention">No live connector qualification</Badge></div><div className="source-areas">{Object.entries(areas).map(([id, name]) => <section className="panel source-area" key={id}><header><span className="area-index">{id.slice(-2)}</span><div><p className="eyebrow">ESTATE AREA</p><h2>{name}</h2></div></header><div className="source-family-list">{load.data!.filter(family => family.areaRef === id).map(family => <article className="source-family" key={family.id}><div className="source-family-title"><h3>{family.name}</h3><Badge>Synthetic only</Badge></div><p><strong>{family.assetCount}</strong> asset memberships<span>·</span><strong>{family.observationCount}</strong> observations</p>{family.profile && <details><summary>Source profile & qualification boundary</summary><RecordFields value={family.profile} /></details>}</article>)}</div></section>)}</div><p className="chart-caption">Asset memberships are per family and may overlap. Use the estate overview for the distinct asset total.</p></>}</>;
}

function Reports({ session, onInspect, onReview }: { session: Session; onInspect: (id: string) => void; onReview: (id: string) => void }) {
  const load = useLoad<ReportMetadata[]>('/api/reports');
  const [selected, setSelected] = useState<string | undefined>(() => new URLSearchParams(window.location.hash.split('?')[1]).get('report') || undefined);
  const assessmentId = selectedAssessmentId();
  function openStage(phase: number) { window.location.hash = `assessments?assessment=${encodeURIComponent(assessmentId)}&stage=${phase === 1 ? 4 : 7}`; }
  return <><PageHeader eyebrow="EVIDENCE → DELIVERABLES" title="Reporting workspace" description="Generate durable reports through the C# application. Inventory, analysis and downloads stay bound to one evidence baseline." /><div className="report-builders">{[
    { phase: 1, title: 'Current-state assessment', detail: 'Inventory, source evidence, dependencies, coverage and recorded limitations.', input: 'The shared evidence baseline', output: 'A reviewable Phase 1 input package' },
    { phase: 2, title: 'Risk & migration analysis', detail: 'Explainable per-use analysis, migration candidates, constraints and review decisions.', input: 'The same baseline and a versioned method', output: 'A reviewable Phase 2 assessment' },
  ].map(item => <section className="panel report-builder" key={item.phase}><Badge tone="teal">PHASE {item.phase}</Badge><h2>{item.title}</h2><p className="muted">{item.detail}</p><dl><div><dt>Built from</dt><dd>{item.input}</dd></div><div><dt>Produces</dt><dd>{item.output}</dd></div></dl><button className="button primary" disabled={!assessmentId} onClick={() => openStage(item.phase)}>Open Phase {item.phase} assessment step<Icon name="file" size={17} /></button><p className="field-help">{assessmentId ? `Draft generation and exact-report review are part of the guided assessment. Signed in as ${humanize(session.role || 'viewer')}.` : 'Legacy reports are read-only. Select or start an assessment to generate new reports with scope, evidence and review context.'}</p></section>)}</div>
    <div className="notice muted-notice"><Icon name="lock" /><span>Generated does not mean accepted. Synthetic assessment decisions are recorded separately at the exact-report gate. Neither a report nor a demonstration decision is enterprise acceptance or execution authorization.</span></div>
    <section className="panel"><div className="section-heading"><div><p className="eyebrow">IMMUTABLE OUTPUTS</p><h2>Report history</h2></div><button className="text-button" onClick={load.reload}>Refresh history</button></div><LoadState {...load} />{load.data && (load.data.length ? <div className="report-history">{load.data.map(report => <article className="report-history-item" key={report.id}><span className="report-icon"><Icon name="file" size={25} /></span><div className="report-history-info"><Badge>{report.phase === 'phase1' ? 'Phase 1' : 'Phase 2'}</Badge><h3>{report.title}</h3><p>{dateLabel(report.createdAt)} · Synthetic snapshot; gate decisions are recorded separately.</p><p className="record-id" title={report.baselineId}>Baseline {report.baselineId}</p></div><div className="report-actions"><button className="button secondary" onClick={() => setSelected(report.id)}>Preview report</button><a className="text-button" href={assessmentApiPath(`/api/reports/${encodeURIComponent(report.id)}/download?format=html`)} download>HTML</a><a className="text-button" href={assessmentApiPath(`/api/reports/${encodeURIComponent(report.id)}/download?format=json`)} download>JSON</a></div></article>)}</div> : <Empty title="Your first report starts here" detail="Open the corresponding guided assessment step to prepare a draft and review the remaining prerequisites." />)}</section>
    {selected && <ReportPreview id={selected} onClose={() => setSelected(undefined)} onInspect={onInspect} onReview={onReview} />}
  </>;
}

function ReportPreview({ id, onClose, onInspect, onReview }: { id: string; onClose: () => void; onInspect: (id: string) => void; onReview: (id: string) => void }) {
  const load = useLoad<Report>(`/api/reports/${encodeURIComponent(id)}`);
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { const prior = document.activeElement as HTMLElement | null; ref.current?.showModal(); return () => prior?.focus(); }, []);
  const report = load.data;
  return <dialog ref={ref} className="report-dialog report-reader-dialog" aria-labelledby="report-title" onCancel={onClose}>
    <header className="drawer-header"><div><p className="eyebrow">PERSISTED REPORT / EXECUTIVE READER</p><h2 id="report-title">{report?.metadata.title || 'Loading report…'}</h2></div><button className="icon-button" aria-label="Close report preview" onClick={onClose}><Icon name="close" /></button></header>
    <div className="drawer-body"><LoadState {...load} />{report && (report.content.narrative ? <NarrativeReport report={report} onInspect={onInspect} onReview={onReview} /> : <>
      <div className="notice muted-notice"><strong>Legacy evidence export.</strong> This immutable v1 report predates the analytical reader. Its original content is preserved; generate a new report for the executive narrative and decision view.</div>
      <div className="drawer-meta"><Badge tone="attention">Synthetic · unaccepted</Badge><span>Created {dateLabel(report.metadata.createdAt)}</span></div>
      <details className="report-technical-appendix"><summary>Read original evidence sections and provenance</summary><RecordFields value={{ baseline: report.metadata.baselineId, content_sha256: report.metadata.contentSha256, worker_run: report.metadata.workerRunId }} />
      {Object.entries(report.content).filter(([key]) => !['title', 'phase', 'synthetic'].includes(key)).map(([key, value]) => <section className="preview-section" key={key}><h3>{humanize(key)}</h3>{Array.isArray(value) ? <><p>{value.length} records. First 5 shown; the download retains every record.</p>{value.slice(0, 5).map((item, index) => <div className="record-card" key={index}>{typeof item === 'object' && item ? <RecordFields value={item as RecordData} /> : <p>{readable(item)}</p>}</div>)}</> : typeof value === 'object' && value ? <RecordFields value={value as RecordData} /> : <p>{readable(value)}</p>}</section>)}</details>
    </>)}</div>
    <footer className="drawer-footer report-preview-actions"><a className="button primary" href={assessmentApiPath(`/api/reports/${encodeURIComponent(id)}/download?format=html`)} download>Download full HTML</a><a className="button secondary" href={assessmentApiPath(`/api/reports/${encodeURIComponent(id)}/download?format=json`)} download>Download JSON</a></footer>
  </dialog>;
}

function Runs() {
  const load = useLoad<Run[]>('/api/runs');
  return <><PageHeader eyebrow="DURABLE EXECUTION RECORD" title="Run ledger" description="Trace assessment commands and report generation to their bounded worker records, input baselines and persisted results." action={<button className="button secondary" onClick={load.reload}>Refresh runs</button>} /><div className="notice muted-notice"><Icon name="lock" /><span>Only synthetic assessment and report runs are exposed here. Ticket mediation and source-system execution are not enabled.</span></div><section className="panel"><LoadState {...load} />{load.data && (load.data.length ? <div className="run-list">{load.data.map(run => <article className="run-item" key={run.id}><div className="run-heading"><div><p className="eyebrow">{run.phase === 'review' ? 'FINDING REVIEW' : run.phase === 'phase1' ? 'PHASE 1 REPORT' : run.phase === 'phase2' ? 'PHASE 2 REPORT' : 'ASSESSMENT COMMAND'}</p><h2>{humanize(run.status)}</h2></div><Badge tone={run.status === 'completed' || run.status === 'succeeded' ? 'teal' : 'attention'}>{humanize(run.status)}</Badge></div><dl className="record-fields"><div><dt>Worker run</dt><dd className="mono">{run.id}</dd></div><div><dt>Manifest</dt><dd>{run.manifestId}</dd></div><div><dt>Initiated by</dt><dd>{run.actor}</dd></div><div><dt>Created</dt><dd>{dateLabel(run.createdAt)} · {run.createdAt}</dd></div><div><dt>Input baseline</dt><dd className="mono">{run.baselineId}</dd></div><div><dt>{run.phase === 'review' ? 'Review result' : run.phase === 'assessment' ? 'Assessment result' : 'Report result'}</dt><dd className="mono">{run.result?.actionId || run.result?.reportId || run.reportId || 'No committed result'}</dd></div><div><dt>Content SHA-256</dt><dd className="mono">{run.result?.artifactSha256 || run.result?.contentSha256 || 'Not recorded'}</dd></div></dl></article>)}</div> : <Empty title="No runs yet" detail="Save an assessment response or generate a draft report to create a bounded run and inspect its result here." />)}</section></>;
}

function Lookahead() {
  return <><PageHeader eyebrow="PRODUCT DIRECTION" title="From the map to migration." description="The assessment foundation supports a governed migration lifecycle. Future phases are proposed capabilities, not enabled controls." /><div className="roadmap-grid">{[
    { phase: '01', title: 'Establish the map', tag: 'Current demo surface', text: 'Source observations become inventory, cryptographic uses, dependencies and an evidence-backed assessment.', outcomes: ['Inspect assets and evidence', 'Make limitations explicit', 'Generate the current-state report'], gate: 'Accountable owners accept or qualify the baseline.' },
    { phase: '02', title: 'Explain the priorities', tag: 'Current demo surface', text: 'Analyze each cryptographic use against evidence, business context, constraints and a versioned method.', outcomes: ['Trace conclusions to source records', 'Separate exposure from readiness', 'Generate risk and migration analysis'], gate: 'Approve the assessment method and disposition exceptions.' },
    { phase: '03', title: 'Design & prove changes', tag: 'Proposed · not enabled', text: 'Model migration cases and immutable plans. Mediate authorized work through provider-neutral tickets.', outcomes: ['TLS, SSH and application patterns', 'Exact-plan approval readback', 'Isolated canaries and independent verification'], gate: 'Authorize each pilot scope, change and recovery plan.' },
    { phase: '04', title: 'Operate & assure', tag: 'Proposed · not enabled', text: 'Scale qualified patterns into bounded migration waves with continuing rediscovery and outcome verification.', outcomes: ['Dependency-aware rollout cohorts', 'Detect regression and evidence drift', 'Close cases only after verified outcomes'], gate: 'Qualify automation, operating controls and recovery.' },
  ].map(item => <section className="panel roadmap-card" key={item.phase}><span className="roadmap-number">{item.phase}</span><Badge tone={Number(item.phase) <= 2 ? 'teal' : 'neutral'}>{item.tag}</Badge><h2>{item.title}</h2><p>{item.text}</p><ul>{item.outcomes.map(outcome => <li key={outcome}>{outcome}</li>)}</ul><div className="roadmap-gate"><Icon name="lock" size={17} /><span>{item.gate}</span></div></section>)}</div><section className="evidence-journey lookahead-authority"><div><p className="eyebrow">OWN THE WORKFLOW. ADAPT THE WORK SURFACE.</p><h2>A closed ticket is not a verified migration.</h2><p>Migration cases, plan revisions and acceptance criteria belong to the application. ServiceNow, Jira or another provider can carry the work and authoritative human approvals through qualified bindings.</p></div><Badge tone="attention">No external writes enabled</Badge></section><p className="chart-caption">The demo does not certify compliance, confirm enterprise product selections, approve a production risk methodology or authorize remediation.</p></>;
}

export default function App() {
  const { theme, changeTheme } = useWorkspaceTheme();
  const [session, setSession] = useState<Session>();
  useDocumentTheme(theme, session?.authenticated === true);
  const [sessionError, setSessionError] = useState('');
  const [page, setPage] = useState<Page>(hashPage);
  const [assessmentId, setAssessmentId] = useState(selectedAssessmentId);
  const [selectedAsset, setSelectedAsset] = useState<string>();
  const [intakeDirty, setIntakeDirty] = useState(false);
  const [navigationBlocked, setNavigationBlocked] = useState(false);
  const dirtyRef = useRef(false);
  const rememberedHash = useRef(window.location.hash);
  dirtyRef.current = intakeDirty;
  useEffect(() => {
    const update = (event: Event) => {
      if (dirtyRef.current && window.location.hash !== rememberedHash.current) {
        history.replaceState(null, '', window.location.pathname + window.location.search + rememberedHash.current);
        event.stopImmediatePropagation(); setNavigationBlocked(true); return;
      }
      rememberedHash.current = window.location.hash;
      setPage(hashPage()); setAssessmentId(selectedAssessmentId()); setSelectedAsset(undefined);
    };
    // Capture before child route listeners so an unsaved form cannot unmount first.
    window.addEventListener('hashchange', update, true); window.addEventListener('popstate', update, true);
    return () => { window.removeEventListener('hashchange', update, true); window.removeEventListener('popstate', update, true); };
  }, []);
  useEffect(() => { if (!intakeDirty) setNavigationBlocked(false); }, [intakeDirty]);
  useEffect(() => { document.getElementById('main-content')?.focus({ preventScroll: true }); }, [page]);
  const [assetFilter, setAssetFilter] = useState('');
  const [revision, setRevision] = useState(0);
  const [logoutBusy, setLogoutBusy] = useState(false);
  const contributorOnly = session?.role === 'contributor' || session?.role === 'contributor-two';
  useEffect(() => { if (contributorOnly && !['discovery', 'discovery-request', 'intake', 'questionnaire', 'questionnaires'].includes(page)) { setPage('discovery'); const query = new URLSearchParams(); if (assessmentId) query.set('assessment', assessmentId); window.location.hash = 'discovery' + (query.size ? '?' + query : ''); } }, [contributorOnly, page, assessmentId]);
  useEffect(() => {
    const controller = new AbortController();
    setSessionError('');
    api<Session>('/api/session', { signal: controller.signal }).then(setSession).catch(reason => {
      if (!controller.signal.aborted) setSessionError(reason instanceof Error ? reason.message : 'The application is unavailable.');
    });
    return () => controller.abort();
  }, [revision]);
  useEffect(() => {
    const expire = () => { setSession({ authenticated: false, role: null, csrfToken: null, synthetic: true }); };
    window.addEventListener('pqc-session-expired', expire);
    return () => window.removeEventListener('pqc-session-expired', expire);
  }, []);
  function navigate(target: Page, filter = '') {
    if (intakeDirty) return;
    const query = new URLSearchParams(target === 'overview' || target === 'actions' ? window.location.hash.split('?')[1] : undefined);
    if (assessmentId) query.set('assessment', assessmentId);
    query.delete('stage'); query.delete('report');
    setPage(target); setAssetFilter(filter); window.location.hash = target + (query.size ? '?' + query : ''); window.scrollTo({ top: 0 });
  }
  function guidedNavigate(target: string, params: Record<string, string> = {}) {
    if (intakeDirty || !['questionnaire', 'discovery-request'].includes(target) && !pages.some(item => item.id === target)) return;
    const query = new URLSearchParams();
    if (assessmentId) query.set('assessment', assessmentId);
    Object.entries(params).forEach(([key, value]) => { if (value) query.set(key, value); else query.delete(key); });
    setPage(target as Page); setAssessmentId(query.get('assessment') || ''); setSelectedAsset(undefined);
    window.location.hash = target + (query.size ? '?' + query : ''); window.scrollTo({ top: 0 });
  }
  function reviewFinding(id: string) { guidedNavigate('actions', { finding: id }); }
  async function logout() {
    setLogoutBusy(true);
    try { await api<void>('/api/logout', { method: 'POST', headers: { 'X-PQC-CSRF': session?.csrfToken || '' } }); setSession({ authenticated: false, role: null, csrfToken: null, synthetic: true }); }
    catch (reason) { setSessionError(reason instanceof Error ? reason.message : 'Sign-out could not be completed.'); }
    finally { setLogoutBusy(false); }
  }
  if (!session) return <main className="startup"><Brand /><LoadState loading={!sessionError} error={sessionError} reload={() => setRevision(value => value + 1)} /></main>;
  if (!session.authenticated) return <Login onLogin={value => { setSession(value); setPage(hashPage()); setSessionError(''); }} />;
  if (page === 'questionnaire' || page === 'discovery-request') return <div className={`${page === 'discovery-request' ? 'discovery-mode ' : ''}questionnaire-mode q-respondent-app app-theme`} data-theme={theme}><a href="#main-content" className="skip-link" onClick={event => { event.preventDefault(); document.getElementById('main-content')?.focus(); }}>Skip to questionnaire</a><header className="q-app-header"><Brand /><div><ThemeControl theme={theme} onChange={changeTheme} /><button className="q-header-link" disabled={intakeDirty} onClick={() => guidedNavigate(page === 'discovery-request' ? 'discovery' : 'questionnaires', { assignment: '', request: '' })}>{page === 'discovery-request' ? 'My requests' : 'My questionnaires'}</button><button className="q-header-link" disabled={logoutBusy || intakeDirty} onClick={() => void logout()}>{logoutBusy ? 'Signing out…' : 'Sign out'}</button></div></header><main id="main-content" tabIndex={-1} className="main-content" key={assessmentId || 'unassigned'}><>{navigationBlocked && <div className="q-error" role="alert">Navigation was paused to protect your unsaved response. Save or discard the edits, then choose the destination again.</div>}{page === 'discovery-request' ? <DiscoveryWorkspace session={session} mode="respondent" onNavigate={guidedNavigate} onDirtyChange={setIntakeDirty} /> : <QuestionnaireWorkspace session={session} mode="respondent" onNavigate={guidedNavigate} onDirtyChange={setIntakeDirty} />}</></main><footer className="app-footer"><span>Synthetic development questionnaire · no enterprise submission or source-system change</span></footer></div>;
  return <div className="app-layout app-theme" data-theme={theme}><a href="#main-content" className="skip-link" onClick={event => { event.preventDefault(); document.getElementById('main-content')?.focus(); }}>Skip to content</a>
    <aside className="sidebar"><Brand /><ThemeControl theme={theme} onChange={changeTheme} /><div className="workspace-label"><span className="status-dot" />SYNTHETIC WORKSPACE</div><nav aria-label="Main navigation">{pages.filter(item => contributorOnly ? ['discovery', 'questionnaires'].includes(item.id) : !['discovery', 'questionnaires', 'intake'].includes(item.id)).map(item => <button key={item.id} disabled={intakeDirty} className={page === item.id ? 'nav-item active' : 'nav-item'} aria-current={page === item.id ? 'page' : undefined} onClick={() => navigate(item.id)}><Icon name={item.icon} /><span>{contributorOnly ? (item.id === 'discovery' ? 'My discovery requests' : 'Specialist questionnaires') : item.label}</span></button>)}</nav>{!contributorOnly && <details className="nav-archive" open={['discovery', 'questionnaires', 'intake'].includes(page)}><summary>Reference &amp; history</summary>{pages.filter(item => ['discovery', 'questionnaires', 'intake'].includes(item.id)).map(item => <button key={item.id} className={page === item.id ? 'nav-item active' : 'nav-item'} disabled={intakeDirty} onClick={() => navigate(item.id)}><Icon name={item.icon} /><span>{item.id === 'discovery' ? 'Request catalog & forms' : item.label}</span></button>)}</details>}<div className="sidebar-bottom"><div className="architecture-label"><span>C# application authority</span><span>React guided experience</span></div><div className="user-card"><span className="avatar">{session.role?.slice(0, 1).toUpperCase()}</span><span><strong>Demo {session.role}</strong><span>Local synthetic identity</span></span></div><button className="sign-out" disabled={logoutBusy || intakeDirty} onClick={() => void logout()}>{logoutBusy ? 'Signing out…' : 'Sign out'}</button>{intakeDirty && <p className="intake-help">Save or discard the unsaved web answers before leaving.</p>}</div></aside>
    <div className="workspace"><div className="synthetic-banner"><span><strong>SYNTHETIC DATA</strong> Development demonstration—not the current enterprise estate.</span><span>Assessment only · no live integrations</span></div>
      <main id="main-content" tabIndex={-1} className="main-content" key={assessmentId || 'legacy'}>
        {sessionError && <p className="notice error" role="alert">{sessionError}</p>}
        {navigationBlocked && <div className="notice error" role="alert">Navigation was paused to protect your unsaved answers. Save or discard the edits, then choose the destination again.</div>}
        {page === 'intake' && <IntakeWorkspace session={session} onNavigate={guidedNavigate} onDirtyChange={setIntakeDirty} />}
        {page === 'discovery' && <DiscoveryWorkspace session={session} mode="list" onNavigate={guidedNavigate} onDirtyChange={setIntakeDirty} />}
        {page === 'assessment-work' && !contributorOnly && <AssessmentWork session={session} onNavigate={guidedNavigate} onDirtyChange={setIntakeDirty} />}
        {page === 'questionnaires' && <QuestionnaireWorkspace session={session} mode="list" onNavigate={guidedNavigate} onDirtyChange={setIntakeDirty} />}
        {!contributorOnly && <>
        {page !== 'assessment-work' && page !== 'discovery' && page !== 'intake' && page !== 'questionnaires' && page !== 'assessments' && page !== 'lookahead' && <div className="assessment-tool-context"><strong>{assessmentId ? 'Assessment-scoped investigation' : 'Legacy baseline · read-only investigation'}</strong><span>{assessmentId ? 'These tools show evidence admitted to the selected assessment. Temporary filters do not change its report scope.' : 'Choose an assessment to connect this investigation to tasks, report inputs and review gates.'}</span><button className="text-button" onClick={() => navigate('assessment-work')}>{assessmentId ? 'Return to assessment work →' : 'Choose an assessment →'}</button></div>}
        {page === 'assessments' && <AssessmentWorkspace session={session} onNavigate={guidedNavigate} />}
        {page === 'overview' && <AnalysisWorkspace session={session} readOnly onInspect={setSelectedAsset} onReports={() => navigate('reports')} />}
        {page === 'actions' && <AnalysisWorkspace mode="queue" session={session} readOnly onInspect={setSelectedAsset} onReports={() => navigate('reports')} />}
        {page === 'assets' && <Assets key={assetFilter} initialStatus={assetFilter} />}{page === 'sources' && <Sources />}
        {page === 'reports' && <Reports session={session} onInspect={setSelectedAsset} onReview={reviewFinding} />}
        {page === 'runs' && <Runs />}{page === 'lookahead' && <Lookahead />}
        {page === 'reference' && !contributorOnly && <ReferenceWorkspace />}
        {page === 'capacity' && !contributorOnly && <CapacityWorkspace session={session} />}
        {selectedAsset && <AssetDrawer id={selectedAsset} onClose={() => setSelectedAsset(undefined)} onSelect={setSelectedAsset} />}
        </>}
      </main><footer className="app-footer"><span>PQC Enterprise · Development evidence</span><span>Owner acceptance and enterprise activation remain separate gates.</span></footer>
    </div>
  </div>;
}
