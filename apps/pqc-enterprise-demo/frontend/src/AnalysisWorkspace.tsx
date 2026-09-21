import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { api, ApiError, dateLabel, humanize, selectedAssessmentId } from './api';
import type { Session } from './contracts';
import type { ActionRecord, Analysis, AnalysisFilter, Distribution, FilterState, Finding } from './analysis-contracts';
import { useApi } from './use-api';

const filterDefinitions: { id: AnalysisFilter; key: keyof Analysis['filterOptions']; label: string }[] = [
  { id: 'service', key: 'services', label: 'Business service' },
  { id: 'owner', key: 'owners', label: 'Accountable owner' },
  { id: 'environment', key: 'environments', label: 'Environment' },
  { id: 'technology', key: 'technologies', label: 'Technology' },
  { id: 'family', key: 'families', label: 'Source family' },
];
const priorityLabels: Record<string, string> = { resolve_evidence: 'Resolve evidence', prioritize_review: 'Prioritize review', planned_review: 'Planned review', context_only: 'Context only' };
export const priorityLabel = (id: string) => priorityLabels[id] || humanize(id);

function filtersFromHash(): FilterState {
  const params = new URLSearchParams(window.location.hash.split('?')[1]);
  return Object.fromEntries(filterDefinitions.map(({ id }) => [id, params.get(id) || ''])) as FilterState;
}

export function AnalysisWorkspace({ session, onInspect, onReports, mode = 'overview', readOnly = false }: {
  session: Session; onInspect: (subjectId: string) => void; onReports: () => void; mode?: 'overview' | 'queue'; readOnly?: boolean;
}) {
  const [filters, setFilters] = useState(filtersFromHash);
  const [revision, setRevision] = useState(0);
  const [findingId, setFindingId] = useState<string>();
  const [priority, setPriority] = useState('');
  const [signal, setSignal] = useState<{ field: 'exposure' | 'readiness'; id: string }>();
  const [page, setPage] = useState(1);
  const analysis = useApi<Analysis>(`/api/analysis?${new URLSearchParams(filters)}`);
  const actionLoad = useApi<ActionRecord[]>('/api/actions', revision);
  useEffect(() => {
    const update = () => { setFilters(filtersFromHash()); setPage(1); };
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);
  useEffect(() => {
    const requested = new URLSearchParams(window.location.hash.split('?')[1]).get('finding');
    if (requested && analysis.data?.findings.some(finding => finding.id === requested)) setFindingId(requested);
  }, [analysis.data]);
  function setFilter(id: AnalysisFilter, value: string) {
    const next = { ...filters, [id]: value };
    setFilters(next); setPage(1);
    const params = new URLSearchParams(Object.entries(next).filter(([, item]) => item));
    if (selectedAssessmentId()) params.set('assessment', selectedAssessmentId());
    window.location.hash = `${mode === 'queue' ? 'actions' : 'overview'}${params.size ? `?${params}` : ''}`;
  }
  function resetFilters() {
    setFilters({ service: '', owner: '', environment: '', technology: '', family: '' });
    setPriority(''); setSignal(undefined); setPage(1); window.location.hash = (mode === 'queue' ? 'actions' : 'overview') + (selectedAssessmentId() ? '?assessment=' + encodeURIComponent(selectedAssessmentId()) : '');
  }
  const data = analysis.data;
  const findings = data?.findings.filter(finding => (!priority || finding.priority === priority) && (!signal || finding[signal.field] === signal.id)) || [];
  const pageSize = mode === 'overview' ? 3 : 8;
  function drillSignal(field: 'exposure' | 'readiness' | 'priority', id: string) {
    setPriority(field === 'priority' ? id : ''); setSignal(field === 'priority' ? undefined : { field, id }); setPage(1);
    document.getElementById('findings-title')?.scrollIntoView({ block: 'start' });
  }
  const selected = data?.findings.find(finding => finding.id === findingId);
  return <div className="analytical-workspace">
    <header className="analytical-header"><div><p className="eyebrow">{mode === 'queue' ? 'INVESTIGATE / REVIEW / DISPOSITION' : 'CRYPTOGRAPHIC ESTATE / OPERATING PICTURE'}</p><h1 tabIndex={-1}>{mode === 'queue' ? 'Turn findings into decisions.' : 'Evidence. Exposure. Next action.'}</h1><p>{mode === 'queue' ? 'Review the rationale, name the evidence needed, and preserve a local decision trail.' : 'Follow the relationships that matter, distinguish uncertainty from exposure, and direct the next investigation.'}</p></div><button className="button primary" onClick={onReports}>Open report workspace <span aria-hidden="true">↗</span></button></header>
    <section className="analysis-filters" aria-label="Analysis-wide filters"><div className="filter-scope"><span className="scope-light" /><strong>TEMPORARY INVESTIGATION FILTERS</strong><small>Every filter applies to the graph, distributions, coverage and findings.</small></div><div className="analysis-filter-fields">{filterDefinitions.map(({ id, key, label }) => <label key={id}><span>{label}</span><select value={filters[id]} onChange={event => setFilter(id, event.target.value)}><option value="">All {label.toLowerCase()}s</option>{data?.filterOptions[key].map(option => <option value={option.id} key={option.id}>{option.label}</option>)}</select></label>)}</div>
      <div className="assessment-filter-chips" aria-label="Active investigation filters">{filterDefinitions.filter(({ id }) => !!filters[id]).map(({ id, key, label }) => <button key={id} onClick={() => setFilter(id, '')} aria-label={`Remove ${label.toLowerCase()} filter`}>{label}: {data?.filterOptions[key].find(option => option.id === filters[id])?.label || filters[id]} <span aria-hidden="true">×</span></button>)}</div>
      <div className="filter-footer"><span>Temporary filters never change assessment scope or report inputs. No enterprise coverage claim.</span><button className="text-button" onClick={resetFilters}>Clear investigation filters</button></div></section>
    {analysis.loading && <div className="loading" role="status"><span className="spinner" />Building the evidence-backed operating picture…</div>}
    {analysis.error && <div className="notice error" role="alert">{analysis.error}<button className="button secondary" onClick={analysis.reload}>Retry analysis</button></div>}
    {data && <>
      {data.findings.length === 0 && <div className="notice muted-notice" role="status"><div><strong>{Object.values(filters).some(Boolean) ? 'No findings match these combined filters.' : 'No finding records are available in this assessment selection.'}</strong><p>{filters.owner && filters.family ? 'The accountable owner and source family filters apply together. This does not mean the selected family has no evidence or no risk.' : 'Empty results are not a conclusion that risk is absent. Review admitted evidence and the current filters.'}</p><div className="assessment-inline-actions">{filters.owner && <button className="button secondary" onClick={() => setFilter('owner', '')}>Clear owner filter</button>}{Object.values(filters).some(Boolean) && <button className="text-button" onClick={resetFilters}>Clear all investigation filters</button>}</div></div></div>}
      <div className="analysis-baseline"><span>BASELINE <code title={data.baseline.baselineId}>{data.baseline.baselineId.slice(0, 24)}…</code></span><span>AS OF {dateLabel(data.baseline.asOf)} UTC</span><span>METHOD {data.method.version} · {humanize(data.method.status)}</span><span className="badge attention">Synthetic / unaccepted</span></div>
      <div className="analysis-metrics">{[
        { label: 'Assets in scope', count: data.summary.assets, detail: `${data.summary.observations} source observations`, tone: 'aqua' },
        { label: 'Cryptographic uses', count: data.summary.cryptographicUses, detail: 'Purpose and role stay separate', tone: 'violet' },
        { label: 'Review findings', count: data.summary.findings, detail: 'Evidence-backed review candidates', tone: 'aqua' },
        { label: 'Decisions required', count: data.summary.decisionsRequired, detail: 'Named questions, not automatic approval', tone: 'amber' },
      ].map(metric => <article className={`analysis-metric tone-${metric.tone}`} key={metric.label}><p>{metric.label}</p><strong>{metric.count.toLocaleString()}</strong><span>{metric.detail}</span></article>)}</div>
      {mode === 'overview' && <>
        <div className="analysis-graph-row"><EstateGraph graph={data.graph} onInspect={onInspect} /><section className="analysis-panel operating-readout"><header className="block-heading"><div><p className="eyebrow">WHAT THIS COHORT NEEDS</p><h2>Direct the next move.</h2></div></header><ol>{data.decisions.slice(0, 2).map((decision, index) => <li key={decision.id}><span>{String(index + 1).padStart(2, '0')}</span><div><strong>{decision.title}</strong><p>{decision.action || decision.rationale}</p><small>Owner: {decision.owner || 'Not identified'}</small></div></li>)}</ol>{!data.decisions.length && <p className="muted">No decision records in this scope. This does not establish absence of risk.</p>}<div className="readout-boundary"><strong>Evidence quality controls reliance.</strong><p>{data.summary.staleAssets} stale assets · {data.summary.disputedAssets} disputed assets · {data.summary.contextOnlyAssets} context-only assets. Review groups can overlap.</p></div><EvidenceBlockers findings={data.findings} onReview={setFindingId} /></section></div>
        <div className="analysis-distributions"><DistributionPanel title="Exposure signals" eyebrow="WHAT THE EVIDENCE INDICATES" rows={data.summary.exposureCounts} tone="aqua" total={data.summary.findings} detail="Use-level exposure and uncertainty. Not an approved enterprise risk rating." onSelect={id => drillSignal('exposure', id)} /><DistributionPanel title="Change readiness" eyebrow="WHAT MAY CONSTRAIN CHANGE" rows={data.summary.readinessCounts} tone="violet" total={data.summary.findings} detail="Readiness is separate from exposure. Ease of change does not reduce current exposure." onSelect={id => drillSignal('readiness', id)} /><DistributionPanel title="Review priorities" eyebrow="WHERE TO SPEND ATTENTION" rows={data.summary.priorityCounts} tone="amber" total={data.summary.findings} detail={data.method.priorityMeaning} onSelect={id => drillSignal('priority', id)} /></div>
        <CoverageMatrix rows={data.coverage} assets={data.assets} onInspect={onInspect} />
      </>}
      <section className="analysis-panel findings-workbench" aria-labelledby="findings-title"><header className="block-heading"><div><p className="eyebrow">EVIDENCE → IMPLICATION → ACTION</p><h2 id="findings-title">{mode === 'queue' ? 'Finding & decision queue' : 'Priority investigations'}</h2></div><label className="finding-priority-filter"><span>Review lane</span><select value={priority} onChange={event => { setPriority(event.target.value); setPage(1); }}><option value="">All review lanes</option>{data.summary.priorityCounts.map(item => <option key={item.id} value={item.id}>{priorityLabel(item.id)}</option>)}</select></label></header><p className="section-explanation">A finding says what was observed, why it matters, and the next review action. Local dispositions are not risk acceptance or source-system change authorization.</p>{actionLoad.error && <p className="notice error" role="alert">Review-state readback is unavailable. Refresh before recording a disposition.<button className="text-button" onClick={actionLoad.reload}>Refresh review state</button></p>}{signal && <p className="finding-drilldown" role="status">Finding drilldown: {humanize(signal.field)} / {humanize(signal.id)} <button className="text-button" onClick={() => { setSignal(undefined); setPage(1); }}>Clear finding drilldown</button></p>}<div className="finding-list">{findings.slice((page - 1) * pageSize, page * pageSize).map(finding => <FindingCard key={finding.id} finding={finding} action={actionLoad.data?.find(action => action.findingId === finding.id)} onInspect={onInspect} onReview={() => setFindingId(finding.id)} />)}</div>{findings.length === 0 && <div className="empty-state"><h3>No findings in this selection</h3><p>Change the cohort or review lane to continue. Missing evidence is not automatically a clean result.</p></div>}<div className="pagination"><span>{findings.length} findings · page {page} of {Math.max(1, Math.ceil(findings.length / pageSize))}</span><div><button className="button secondary" disabled={page === 1} onClick={() => setPage(current => current - 1)}>Previous</button><button className="button secondary" disabled={page * pageSize >= findings.length} onClick={() => setPage(current => current + 1)}>Next</button></div></div></section>
      {mode === 'overview' && <div className="overview-queue-link"><p>Overview highlights three findings at a time. Findings support grouped assessment tasks; they are not a separate checklist of chores.</p><button className="button secondary" onClick={() => { const params = new URLSearchParams(Object.entries(filters).filter(([, item]) => item)); if (selectedAssessmentId()) params.set('assessment', selectedAssessmentId()); window.location.hash = `actions${params.size ? `?${params}` : ''}`; }}>Open the complete finding queue →</button></div>}<p className="analysis-boundary">{data.boundary}</p>
    </>}
    {selected && (readOnly ? <FindingReadDialog finding={selected} onInspect={onInspect} onClose={() => setFindingId(undefined)} /> : <FindingActionDialog finding={selected} impact={data?.businessImpacts.find(item => item.id === selected.impactId)} decision={data?.decisions.find(item => item.id === selected.decisionId)} session={session} current={actionLoad.data?.find(action => action.findingId === selected.id)} stateAvailable={!!actionLoad.data} onInspect={onInspect} onClose={() => { setFindingId(undefined); const params = new URLSearchParams(window.location.hash.split('?')[1]); if (params.has('finding')) { params.delete('finding'); history.replaceState(null, '', `#${mode === 'queue' ? 'actions' : 'overview'}${params.size ? `?${params}` : ''}`); } }} onSaved={() => setRevision(current => current + 1)} />)}
  </div>;
}

function EvidenceBlockers({ findings, onReview }: { findings: Finding[]; onReview: (id: string) => void }) {
  const groups = [
    { id: 'evidence_prerequisites_missing', label: 'Evidence prerequisites unresolved' },
    { id: 'independent_verification_required', label: 'Independent verification pending' },
    { id: 'product_qualification_required', label: 'Exact-product qualification pending' },
  ];
  const blockers = groups.map(group => ({ ...group, finding: findings.find(item => item.readiness === group.id) })).filter(group => !!group.finding);
  return <section className="evidence-blockers"><p className="eyebrow">CONSTRAINTS ON THE NEXT STEP</p><h3>Evidence & product blockers</h3>
    {blockers.length ? <ul>{blockers.map(group => <li key={group.id}><button className="text-button" onClick={() => onReview(group.finding!.id)}>{group.label} →</button><span>{group.finding!.subjectLabel}</span></li>)}</ul> : <p>No specific prerequisite group is recorded in this scope. This does not prove migration readiness.</p>}
    <small>Qualification pending is not a confirmed vendor blockage or product incompatibility. Investigate the source-linked constraint.</small>
  </section>;
}

function DistributionPanel({ title, eyebrow, rows, tone, total, detail, onSelect }: { title: string; eyebrow: string; rows: Distribution; tone: string; total: number; detail: string; onSelect?: (id: string) => void }) {
  const max = Math.max(1, ...rows.map(row => row.count));
  return <section className={`analysis-panel distribution-panel tone-${tone}`}><p className="eyebrow">{eyebrow}</p><h2>{title}</h2><div className="distribution-rows">{rows.map(row => <div className="distribution-row" key={row.id}><div>{onSelect ? <button onClick={() => onSelect(row.id)}>{priorityLabel(row.id)}</button> : <span>{priorityLabel(row.id)}</span>}<strong>{row.count}</strong></div><svg viewBox="0 0 100 5" preserveAspectRatio="none" aria-hidden="true"><rect width="100" height="5" className="distribution-track" /><rect width={row.count / max * 100} height="5" className="distribution-fill" /></svg></div>)}</div><p className="distribution-note">{total} findings in scope. {detail}</p></section>;
}

function CoverageMatrix({ rows, assets, onInspect }: { rows: Analysis['coverage']; assets: Analysis['assets']; onInspect: (id: string) => void }) {
  const [selection, setSelection] = useState<{ areaId: string; group: 'present' | 'missing' | 'stale' | 'disputed' }>();
  const [page, setPage] = useState(1);
  const labels = { present: 'Mapped subjects', missing: 'No use evidence', stale: 'Stale subjects', disputed: 'Disputed subjects' };
  const selectedRow = rows.find(row => row.areaId === selection?.areaId);
  const selectedAssets = selectedRow && selection ? assets.filter(asset => asset.areaRefs.includes(selectedRow.areaId) &&
    (selection.group === 'present' || selection.group === 'missing' && asset.isContextOnly ||
      selection.group === 'stale' && asset.isStale || selection.group === 'disputed' && asset.isDisputed)) : [];
  useEffect(() => { setSelection(undefined); setPage(1); }, [assets]);
  return <section className="analysis-panel coverage-panel">
    <header className="block-heading"><div><p className="eyebrow">TEN-AREA EVIDENCE MATRIX</p><h2>Coverage is not the same as completeness.</h2></div><span className="badge">Selected cohort</span></header>
    <p className="section-explanation">Select a subject count to investigate the underlying records. Mapped, no-use, stale and disputed values count selected subjects; groups can overlap. Missing families count catalog families without a subject in this scope—not confirmed enterprise gaps.</p>
    <div className="table-scroll"><table className="coverage-matrix"><thead><tr><th scope="col">Estate area</th><th scope="col">Source families</th><th scope="col">Mapped subjects</th><th scope="col">No use evidence</th><th scope="col">Stale</th><th scope="col">Disputed</th><th scope="col">Missing families</th></tr></thead><tbody>{rows.map(row => <tr key={row.areaId}>
      <th scope="row"><span>{row.areaId.replace('area-', '')}</span>{row.label}</th><td>{row.familyCount}</td>
      {(['present', 'missing', 'stale', 'disputed'] as const).map(group => <td key={group} title={group === 'missing' ? row.missingMeaning : row.denominator}><button className={'matrix-cell ' + (row[group] ? { present: 'present', missing: 'uncertain', stale: 'stale', disputed: 'disputed' }[group] : '')} aria-label={row.label + ': ' + labels[group] + ', ' + row[group]} aria-pressed={selection?.areaId === row.areaId && selection.group === group} onClick={() => { setSelection({ areaId: row.areaId, group }); setPage(1); }}>{row[group]}</button></td>)}
      <td>{row.missingFamilies ?? 'Not calculated'}</td>
    </tr>)}</tbody></table></div>
    {selectedRow && selection && <section className="coverage-drilldown" aria-label="Coverage subject drilldown">
      <header><div><p className="eyebrow">UNDERLYING SUBJECTS</p><h3>{selectedRow.label} / {labels[selection.group]}</h3></div><button className="text-button" onClick={() => setSelection(undefined)}>Close subject drilldown</button></header>
      <p>{selectedAssets.length} selected subjects. {selection.group === 'missing' ? selectedRow.missingMeaning : selectedRow.denominator}</p>
      <ul>{selectedAssets.slice((page - 1) * 6, page * 6).map(asset => <li key={asset.id}><button className="text-button" onClick={() => onInspect(asset.id)}>{asset.label} ↗</button><span>{humanize(asset.evidenceState)} · {asset.useIds.length} cryptographic uses</span></li>)}</ul>
      {!selectedAssets.length && <p>No subjects in this area and evidence group under the current five-filter scope.</p>}
      {selectedAssets.length > 6 && <div className="pagination"><span>Page {page} of {Math.ceil(selectedAssets.length / 6)}</span><div><button className="button secondary" disabled={page === 1} onClick={() => setPage(value => value - 1)}>Previous subjects</button><button className="button secondary" disabled={page * 6 >= selectedAssets.length} onClick={() => setPage(value => value + 1)}>Next subjects</button></div></div>}
    </section>}
  </section>;
}

export function FindingCard({ finding, action, onInspect, onReview }: { finding: Finding; action?: ActionRecord; onInspect: (id: string) => void; onReview: () => void }) {
  return <article className="finding-card"><div className="finding-topline"><span className={`priority-signal priority-${finding.priority}`}>{priorityLabel(finding.priority)}</span><span className="finding-evidence-state">{humanize(finding.evidenceState)} · {finding.observationRefs.length} evidence references</span>{action && <span className="badge teal">{humanize(action.status)} · r{action.revision}</span>}</div><h3>{finding.title}</h3><button className="finding-asset" onClick={() => onInspect(finding.subjectId)}>{finding.subjectLabel} <span aria-hidden="true">↗</span></button><div className="finding-explanation"><div><span>OBSERVATION</span><p>{finding.observation}</p></div><div><span>BUSINESS / TECHNICAL IMPLICATION</span><p>{finding.implication}</p></div><div><span>RECOMMENDED NEXT ACTION</span><p>{finding.recommendation}</p></div></div><div className="finding-bottomline"><div><span>Owner</span><strong>{finding.owner || 'Not identified'}</strong><span>Readiness</span><strong>{humanize(finding.readiness)}</strong></div><button className="button secondary" onClick={onReview}>View finding <span aria-hidden="true">→</span></button></div></article>;
}

function FindingReadDialog({ finding, onInspect, onClose }: { finding: Finding; onInspect: (id: string) => void; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { const prior = document.activeElement as HTMLElement | null; dialog.current?.showModal(); return () => prior?.focus(); }, []);
  const id = selectedAssessmentId();
  return <dialog className="report-dialog finding-dialog" ref={dialog} aria-labelledby="finding-reader-title" onCancel={onClose}><header className="drawer-header"><div><p className="eyebrow">SUPPORTING ASSESSMENT EVIDENCE</p><h2 id="finding-reader-title">{finding.title}</h2></div><button className="icon-button" aria-label="Close finding" onClick={onClose}>×</button></header><div className="drawer-body"><dl className="record-fields"><div><dt>What was observed</dt><dd>{finding.observation}</dd></div><div><dt>Why it matters</dt><dd>{finding.implication}</dd></div><div><dt>What needs to happen next</dt><dd>{finding.recommendation}</dd></div><div><dt>Evidence confidence</dt><dd>{humanize(finding.confidence)}</dd></div><div><dt>Limitations</dt><dd>{finding.limitationCodes.map(humanize).join(' · ') || 'No specific limitation attached; this is not enterprise verification.'}</dd></div></dl><button className="button secondary" onClick={() => onInspect(finding.subjectId)}>Inspect supporting source evidence</button><div className="notice muted-notice">Record conclusions, request missing information, and obtain review through the guided assessment package. A finding is not a separate approval task.</div><a className="button primary" href={`#assessments${id ? '?assessment=' + encodeURIComponent(id) + '&stage=3' : ''}`} onClick={onClose}>{id ? 'Return to assessment review package' : 'Choose an assessment'}</a></div></dialog>;
}

function EstateGraph({ graph, onInspect }: { graph: Analysis['graph']; onInspect: (id: string) => void }) {
  const [selection, setSelection] = useState<string>();
  const [zoom, setZoom] = useState(1);
  const viewport = useRef<HTMLDivElement>(null);
  const nodes = graph.nodes;
  const lanes = [
    { kind: 'business_service', label: 'Business service' }, { kind: 'application', label: 'Application' },
    { kind: 'asset', label: 'Asset / deployment' }, { kind: 'cryptographic_use', label: 'Cryptographic use' },
    { kind: 'external_reference', label: 'External reference' },
  ];
  const layout = useMemo(() => {
    const order = ['business_service', 'application', 'asset', 'cryptographic_use', 'external_reference'];
    const count = [0, 0, 0, 0, 0];
    const positions = new Map(nodes.map(node => {
      const index = order.indexOf(node.kind), lane = index < 0 ? 4 : index;
      return [node.id, { x: 20 + lane * 204, y: 68 + count[lane]++ * 88, lane }];
    }));
    return { positions, height: Math.max(320, 105 + Math.max(...count) * 88) };
  }, [nodes]);
  useEffect(() => { setSelection(undefined); }, [nodes]);
  const node = nodes.find(item => item.id === selection);
  const connections = graph.edges.filter(edge => edge.source === selection || edge.target === selection);
  const linked = new Set(connections.flatMap(edge => [edge.source, edge.target]));
  const kindTone = (kind: string) => kind.includes('use') ? 'use' : kind.includes('service') || kind.includes('application') ? 'context' : kind.includes('reference') ? 'reference' : 'asset';
  return <section className="analysis-panel estate-graph-panel">
    <header className="block-heading"><div><p className="eyebrow">CONNECTED CRYPTOGRAPHIC ESTATE</p><h2>Follow the dependency.</h2></div><span className="graph-live-marker"><i />API PROJECTION</span></header>
    <div className="graph-toolbar"><span>{graph.displayedNodes} of {graph.totalNodes} nodes{graph.truncated ? ' · bounded preview' : ''} · {graph.edges.length} displayed edges</span><div>
      <button aria-label="Zoom out graph" disabled={zoom <= .75} onClick={() => setZoom(value => Math.max(.75, value - .25))}>−</button><span>{Math.round(zoom * 100)}%</span><button aria-label="Zoom in graph" disabled={zoom >= 1.75} onClick={() => setZoom(value => Math.min(1.75, value + .25))}>+</button>
      <button aria-label="Pan graph left" onClick={() => viewport.current?.scrollBy({ left: -204, behavior: 'smooth' })}>←</button><button aria-label="Pan graph right" onClick={() => viewport.current?.scrollBy({ left: 204, behavior: 'smooth' })}>→</button>
      <button onClick={() => { setZoom(1); setSelection(undefined); viewport.current?.scrollTo({ left: 0, top: 0 }); }}>Reset</button>
    </div></div>
    <div className="graph-viewport" ref={viewport} tabIndex={0} aria-label="Scrollable dependency lanes">{nodes.length ? <svg className="estate-graph" style={{ width: 1050 * zoom, height: layout.height * zoom }} viewBox={'0 0 1050 ' + layout.height} role="group" aria-label="Interactive dependency graph. Tab to a node and press Enter to select it.">
      <defs><pattern id="graph-grid" width="22" height="22" patternUnits="userSpaceOnUse"><path d="M 22 0 L 0 0 0 22" fill="none" className="graph-gridline" /></pattern><marker id="graph-arrow" viewBox="0 0 7 7" refX="6" refY="3.5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 7 3.5 L 0 7 z" fill="#72bcbf" /></marker></defs>
      <rect width="1050" height={layout.height} fill="url(#graph-grid)" />
      {lanes.map((lane, index) => <g key={lane.kind} aria-hidden="true"><text x={20 + index * 204} y="28" className="graph-lane-title">{lane.label}</text><line x1={20 + index * 204} x2={194 + index * 204} y1="42" y2="42" className="graph-lane-rule" /></g>)}
      <g aria-hidden="true">{graph.edges.map(edge => {
        const from = layout.positions.get(edge.source), to = layout.positions.get(edge.target);
        if (!from || !to) return null;
        const forward = to.lane > from.lane, same = to.lane === from.lane;
        const x1 = from.x + (forward || same ? 174 : 0), y1 = from.y + 31;
        const x2 = to.x + (forward ? 0 : 174), y2 = to.y + 31;
        const bend = same ? x1 + 22 : (x1 + x2) / 2;
        return <path key={edge.id} markerEnd="url(#graph-arrow)" className={selection ? (edge.source === selection || edge.target === selection ? 'graph-edge highlighted' : 'graph-edge faded') : 'graph-edge'} d={'M ' + x1 + ' ' + y1 + ' C ' + bend + ' ' + y1 + ', ' + bend + ' ' + y2 + ', ' + x2 + ' ' + y2} />;
      })}</g>
      {nodes.map(item => {
        const position = layout.positions.get(item.id)!; const selected = selection === item.id;
        return <g role="button" tabIndex={0} key={item.id} aria-label={'Select ' + item.label + ', ' + humanize(item.kind)} aria-pressed={selected}
          className={'graph-node node-' + kindTone(item.kind) + (selected ? ' selected' : '') + (selection && !selected && !linked.has(item.id) ? ' dimmed' : '')}
          transform={'translate(' + position.x + ' ' + position.y + ')'} onClick={() => setSelection(item.id)}
          onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelection(item.id); } }}>
          <title>{item.label} · {humanize(item.kind)}</title><rect width="174" height="62" rx="5" />
          <circle cx="12" cy="16" r="3" /><text x="22" y="20" className="graph-node-kind">{humanize(item.kind)}</text>
          <text x="11" y="44" className="graph-node-label">{item.label.length > 24 ? item.label.slice(0, 23) + '…' : item.label}</text>
        </g>;
      })}
    </svg> : <div className="empty-state"><h3>No graph nodes in this scope</h3><p>Broaden the filters to inspect mapped relationships.</p></div>}</div>
    <div className="graph-legend"><span className="legend-context">Service / application</span><span className="legend-asset">Asset</span><span className="legend-use">Cryptographic use</span><span className="legend-reference">Reference / unresolved</span></div>
    <div className="graph-selection" aria-live="polite">{node ? <><div><strong>{node.label}</strong><span>{humanize(node.kind)} · {connections.length} displayed connections{!node.inScope ? ' · outside selected scope' : ''}</span></div>{node.subjectId && ['asset', 'application', 'cryptographic_use'].includes(node.kind) ? <button className="button secondary" onClick={() => onInspect(node.subjectId)}>Inspect source asset ↗</button> : <span className="badge attention">Reference only — no source asset record</span>}</> : <p>Select a node to highlight evidence-linked relationships and inspect the underlying record. Lanes identify system roles; scroll horizontally to follow each connection. Reference-only names remain explicitly unresolved.</p>}</div>
    <details className="assessment-graph-alternative"><summary>Read relationships as a list instead of a graph</summary><ul>{graph.edges.map(edge => <li key={edge.id}>{nodes.find(item => item.id === edge.source)?.label || edge.source} → {humanize(edge.relationship)} → {nodes.find(item => item.id === edge.target)?.label || edge.target}</li>)}</ul>{graph.edges.length === 0 && <p>No relationships are displayed under the current filters.</p>}</details>
    {node && connections.length > 0 && <details className="graph-relationships"><summary>Explain selected relationships</summary><ul>{connections.map(edge => <li key={edge.id}><strong>{humanize(edge.relationship)}</strong><span>{nodes.find(item => item.id === edge.source)?.label} → {nodes.find(item => item.id === edge.target)?.label}</span><small>{edge.observationRefs.length} evidence references</small></li>)}</ul></details>}
  </section>;
}

function FindingActionDialog({ finding, impact, decision, session, current, stateAvailable, onInspect, onClose, onSaved }: {
  finding: Finding; impact?: Analysis['businessImpacts'][number]; decision?: Analysis['decisions'][number]; session: Session; current?: ActionRecord; stateAvailable: boolean;
  onInspect: (id: string) => void; onClose: () => void; onSaved: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [operation, setOperation] = useState('investigate');
  const [disposition, setDisposition] = useState('needs_evidence');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState<ActionRecord>();
  const pending = useRef<{ payload: string; key: string } | undefined>(undefined);
  const latest = saved || current;
  useEffect(() => { const prior = document.activeElement as HTMLElement | null; dialog.current?.showModal(); return () => prior?.focus(); }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (session.role !== 'analyst' || !session.csrfToken || busy || !stateAvailable) return;
    const payload = JSON.stringify({ operation, disposition: operation === 'record_disposition' ? disposition : null, note, expectedRevision: latest?.revision || 0 });
    if (pending.current && pending.current.payload !== payload) { setError('A prior result is uncertain. Refresh the review state before submitting changed content.'); return; }
    pending.current ||= { payload, key: crypto.randomUUID() };
    setBusy(true); setError('');
    try {
      const record = await api<ActionRecord>(`/api/actions/${encodeURIComponent(finding.id)}`, { method: 'POST', headers: { 'X-PQC-CSRF': session.csrfToken, 'Idempotency-Key': pending.current.key }, body: payload });
      pending.current = undefined; setSaved(record); setNote(''); onSaved();
    } catch (reason) {
      if (reason instanceof ApiError && reason.status < 500) pending.current = undefined;
      setError(reason instanceof ApiError && reason.status === 409 ? 'The finding was changed by another request. Your note is preserved. Close and refresh the queue before recording a new disposition.' : reason instanceof ApiError ? reason.message : 'The result is uncertain. Your note is preserved; retrying unchanged content uses the same request identity.');
    } finally { setBusy(false); }
  }
  return <dialog className="report-dialog finding-dialog" ref={dialog} aria-labelledby="finding-dialog-title" onCancel={onClose}><header className="drawer-header"><div><p className="eyebrow">LOCAL FINDING REVIEW</p><h2 id="finding-dialog-title">{finding.title}</h2></div><button className="icon-button" aria-label="Close finding review" onClick={onClose}>×</button></header><div className="drawer-body"><div className="finding-review-summary"><span className={`priority-signal priority-${finding.priority}`}>{priorityLabel(finding.priority)}</span><button className="text-button" onClick={() => onInspect(finding.subjectId)}>{finding.subjectLabel} ↗</button><h3>Why this is in the queue</h3><p>{finding.priorityRationale}</p><dl><div><dt>Observed</dt><dd>{finding.observation}</dd></div><div><dt>Implication</dt><dd>{finding.implication}</dd></div><div><dt>Next action</dt><dd>{finding.recommendation}</dd></div><div><dt>Accountable owner</dt><dd>{finding.owner || 'Not identified'}</dd></div></dl>{impact && <section className="finding-linked-context"><p className="eyebrow">BUSINESS IMPACT / TO VALIDATE</p><h3>{impact.title}</h3><p>{impact.rationale}</p><p><strong>Validation action:</strong> {impact.action}</p><small>Conditional assessment context, not a quantified business loss.</small></section>}{decision && <section className="finding-linked-context"><p className="eyebrow">LINKED ACCOUNTABLE DECISION</p><h3>{decision.title}</h3><p>{decision.rationale}</p><p><strong>Decision action:</strong> {decision.action}</p><small>Owner: {decision.owner || 'Not identified'} · proposed review, not authorization</small></section>}<details className="finding-linked-context"><summary>Evidence and product qualification constraints</summary><p>Readiness: {humanize(finding.readiness)}</p><p>{finding.limitationCodes.length ? finding.limitationCodes.map(humanize).join(' · ') : 'No specific limitation code attached; exact-product qualification is still a separate gate.'}</p><p>{finding.recommendation}</p><small>Missing qualification does not establish vendor blockage or confirmed incompatibility.</small></details></div><form className="finding-action-form" onSubmit={event => void submit(event)}><h3>Record the next step</h3><p className="muted">A local synthetic work aid. No ticket, email, approval or migration will be sent or executed.</p>{operation === 'prepare_evidence_request' && <p className="field-help">Ask for an existing inventory, report, document reference or team referral. This is not a request to demonstrate compliance, send sensitive files or grant access. The assessment team coordinates any later technical review separately.</p>}<label><span>Operation</span><select value={operation} onChange={event => setOperation(event.target.value)} disabled={busy || session.role !== 'analyst'}><option value="investigate">Start investigation</option><option value="review_finding">Record finding review</option><option value="prepare_evidence_request">Prepare information request draft</option><option value="record_disposition">Record disposition</option></select></label>{operation === 'record_disposition' && <label><span>Disposition</span><select value={disposition} onChange={event => setDisposition(event.target.value)} disabled={busy || session.role !== 'analyst'}><option value="needs_evidence">Needs evidence</option><option value="reviewed">Reviewed — not risk acceptance</option><option value="deferred">Deferred — not an approved exception</option></select></label>}<label><span>Review note — synthetic information only</span><textarea value={note} maxLength={800} rows={4} onChange={event => setNote(event.target.value)} disabled={busy || session.role !== 'analyst'} placeholder="What must be investigated, clarified or collected next?" /></label><p className="field-help">Revision {latest?.revision || 0} · Notes are preserved on errors. Never enter credentials or real enterprise data.</p>{session.role === 'viewer' && <p className="notice muted-notice">Viewer access: actions are read-only. An analyst is required to record a review or prepare a request.</p>}{!stateAvailable && <p className="notice error">Review state must be loaded before a new revision can be recorded.</p>}{error && <p className="notice error" role="alert">{error}</p>}<button className="button primary" disabled={busy || session.role !== 'analyst' || !stateAvailable}>{busy ? 'Recording…' : operation === 'prepare_evidence_request' ? 'Prepare local draft — do not send' : 'Record local review'}</button></form>{latest && <section className="saved-review"><p className="eyebrow">PERSISTED REVIEW STATE</p><h3>{humanize(latest.status)} · revision {latest.revision}</h3><p>{latest.note || 'No note recorded.'}</p><small>{latest.actor} · {dateLabel(latest.createdAt)} · external delivery: no</small>{latest.evidenceRequestDraft && <><h4>Information request draft — not sent</h4><pre>{latest.evidenceRequestDraft}</pre></>}</section>}</div><footer className="drawer-footer">Review does not equal approval · ticket closure does not equal verified migration</footer></dialog>;
}
