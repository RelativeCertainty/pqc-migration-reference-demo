import { useEffect, useState } from 'react';
import { api, humanize } from './api';
import type { Session } from './contracts';
import './CapacityWorkspace.css';

type Scenario = { name: string; profileId?: string; availability: string; historyMode: string; platform: string; parameters: Record<string, number> };
type Parameter = { key: string; label: string; group: string; unit: string; defaultValue: number; min: number; max: number; integer: boolean; description: string; basis: string };
type Result = { inputHash: string; scenario: Scenario; totals: Record<string, number>; storage: Record<string, number>;
  allocations: { tier: string; instances: number; cpuPerInstance: number; memoryGiBPerInstance: number; localDiskGiBPerInstance: number; survivingCores: number; requiredCores: number }[];
  equations: { id: string; label: string; formula: string; substitution: string; value: number; unit: string; basis: string }[];
  warnings: {code: string; message: string}[]; blockers: {code: string; message: string}[]; assumptions: string[];
  cost: {isAvailable: boolean; totalMonthly: number | null; currency: string; basis: string}; deployable: false; performanceVerified: false };
type Catalog = { definitions: Parameter[]; presets: Scenario[] };
const initial: Scenario = {name: 'Planning scenario', availability: 'ha', historyMode: 'changed', platform: 'unselected', parameters: {}};
const number = (value: number) => new Intl.NumberFormat('en-US', {maximumFractionDigits: 2}).format(value);

export function CapacityWorkspace({ session }: {session: Session}) {
  const [catalog, setCatalog] = useState<Catalog>();
  const [scenario, setScenario] = useState<Scenario>(initial);
  const [result, setResult] = useState<Result>();
  const [comparison, setComparison] = useState<Result[]>([]);
  const [sensitivity, setSensitivity] = useState<{label: string; result?: Result; error?: string}[]>([]);
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false); const [notice, setNotice] = useState('');
  useEffect(() => { const controller = new AbortController(); api<Catalog>('/api/capacity/catalog', {signal: controller.signal}).then(setCatalog).catch(() => {if (!controller.signal.aborted) setError('The capacity catalog could not be loaded. Reopen this page to retry.');}); return () => controller.abort(); }, []);
  function update(value: Scenario) { setScenario(value); setResult(undefined); setComparison([]); setSensitivity([]); setNotice('Inputs changed. Calculate to see current estimates.'); }
  async function run(operation: 'calculate' | 'compare' | 'sensitivity') {
    setBusy(true); setError(''); setNotice('');
    try {
      const response = await api<Result & {results: Result[]; cases: typeof sensitivity}>(`/api/capacity/${operation}`, {method: 'POST', headers: {'X-PQC-CSRF': session.csrfToken || ''}, body: JSON.stringify(operation === 'compare' ? {scenarios: catalog?.presets} : scenario)});
      if (operation === 'calculate') setResult(response);
      if (operation === 'compare') setComparison(response.results);
      if (operation === 'sensitivity') setSensitivity(response.cases);
      setNotice('Calculation complete. These are assumption-based estimates, not measured capacity or infrastructure authorization.');
    } catch { setError('Calculation was not accepted. Check all input ranges and your session; no plan was saved or infrastructure changed.'); }
    finally { setBusy(false); }
  }
  async function download() {
    if (!result) return;
    setBusy(true); setError('');
    try {
      const response = await fetch('/api/capacity/package', {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json', 'X-PQC-CSRF':session.csrfToken || ''}, body:JSON.stringify(result.scenario)});
      if (!response.ok) throw Error('download_failed');
      const url = URL.createObjectURL(await response.blob()); const link = document.createElement('a'); link.href=url; link.download='pqc-capacity-review-package.zip'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 60000);
      setNotice('Review package prepared. Browser delivery may be policy-restricted; its Terraform preview does not provision resources.');
    } catch {setError('The package could not be downloaded. No infrastructure action occurred.');} finally {setBusy(false);}
  }
  return <section className="capacity-workspace">
    <header className="page-header"><div><p className="eyebrow">Planning, not provisioning</p><h1>Capacity planning</h1><p>Choose a tier, inspect assumptions, and trace CPU, memory and disk estimates to the equations. No benchmark, deployment or migration execution is implied.</p></div></header>
    {error && <p className="notice error" role="alert">{error}</p>}{notice && <p className="notice" role="status">{notice}</p>}
    {!catalog ? <p role="status">Loading planning assumptions…</p> : <>
      <div className="reference-tabs">{catalog.presets.map(preset => <button className="button secondary" key={preset.profileId} disabled={busy} onClick={() => update(preset)}>Use {preset.profileId} tier</button>)}</div>
      <label>Scenario name<input maxLength={120} value={scenario.name} disabled={busy} onChange={e => update({...scenario,name:e.target.value})} /></label>
      <div className="capacity-controls">
        <label>Availability<select value={scenario.availability} disabled={busy} onChange={e=>update({...scenario,availability:e.target.value})}><option value="ha">High availability</option><option value="single">Single instance</option></select></label>
        <label>Observation history<select value={scenario.historyMode} disabled={busy} onChange={e=>update({...scenario,historyMode:e.target.value})}><option value="changed">Changed records and collection lineage</option><option value="full">Full snapshots</option></select></label>
        <label>Platform<select value={scenario.platform} disabled={busy} onChange={e=>update({...scenario,platform:e.target.value})}><option value="unselected">Not selected</option><option value="managed-vm">Managed virtual machines</option><option value="cloud-foundry">Cloud Foundry</option></select></label>
      </div>
      {[...new Set(catalog.definitions.map(d=>d.group))].map(group=><details key={group}><summary>{humanize(group)} assumptions</summary><div className="capacity-controls">{catalog.definitions.filter(d=>d.group===group).map(d=><label key={d.key}>{d.label} ({d.unit})<input type="number" min={d.min} max={d.max} step={d.integer ? 1 : 'any'} value={scenario.parameters[d.key] ?? d.defaultValue} disabled={busy} onChange={e=>update({...scenario,parameters:{...scenario.parameters,[d.key]:Number(e.target.value)}})} /><small>{d.description} Basis: {d.basis}.</small></label>)}</div></details>)}
      <div className="reference-tabs"><button className="button primary" disabled={busy} onClick={()=>void run('calculate')}>Calculate scenario</button><button className="button secondary" disabled={busy} onClick={()=>void run('compare')}>Compare three tiers</button><button className="button secondary" disabled={busy} onClick={()=>void run('sensitivity')}>Show CPU-cost sensitivity</button></div>
    </>}
    {result && <section aria-label="Capacity calculation result"><h2>{result.scenario.name}</h2><p>Input identity: <code>{result.inputHash}</code></p>
      <div className="capacity-controls">{Object.entries(result.totals).map(([key,value])=><article className="panel" key={key}><h3>{humanize(key)}</h3><strong>{number(value)}</strong></article>)}</div>
      <h3>Physical allocation and failure headroom</h3><div className="table-scroll"><table><thead><tr><th>Tier</th><th>Instances</th><th>CPU each</th><th>GiB RAM each</th><th>GiB disk each</th><th>Required / surviving cores</th></tr></thead><tbody>{result.allocations.map(a=><tr key={a.tier}><td>{a.tier}</td><td>{a.instances}</td><td>{a.cpuPerInstance}</td><td>{a.memoryGiBPerInstance}</td><td>{a.localDiskGiBPerInstance}</td><td>{number(a.requiredCores)} / {number(a.survivingCores)}</td></tr>)}</tbody></table></div>
      <h3>Warnings and unresolved decisions</h3>{[...result.blockers,...result.warnings].map((w,i)=><p className="notice" key={`${w.code}-${i}`}>{w.message}</p>)}
      <h3>Why these estimates?</h3>{result.equations.map(e=><details key={e.id}><summary>{e.label}: {number(e.value)} {e.unit}</summary><p><code>{e.formula}</code></p><p>{e.substitution}</p><p>Basis: {e.basis}</p></details>)}
      <h3>Storage quantities</h3><dl>{Object.entries(result.storage).map(([key,value])=><div key={key}><dt>{humanize(key)}</dt><dd>{number(value)}</dd></div>)}</dl>
      <p>{result.cost.isAvailable ? `Estimated monthly cost: ${result.cost.currency} ${number(result.cost.totalMonthly || 0)}` : 'Cost is unknown until approved prices are supplied.'} {result.cost.basis}</p>
      <ul>{result.assumptions.map(a=><li key={a}>{a}</li>)}</ul><button className="button secondary" disabled={busy} onClick={()=>void download()}>Download review package</button>
    </section>}
    {comparison.length > 0 && <section><h2>Tier comparison</h2>{comparison.map(r=><p key={r.inputHash}>{r.scenario.profileId}: {number(r.totals.cpu)} CPU, {number(r.totals.memoryGiB)} GiB RAM. {r.blockers.length} blockers remain.</p>)}</section>}
    {sensitivity.length > 0 && <section><h2>CPU-cost sensitivity</h2><p>This is not a confidence interval.</p>{sensitivity.map(c=><p key={c.label}>{c.label}: {c.result ? `${number(c.result.totals.cpu)} total CPU` : 'Outside parameter bounds'}</p>)}</section>}
  </section>;
}
