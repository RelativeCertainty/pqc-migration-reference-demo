import { humanize } from './api';

type Row = Record<string, unknown>;
const object = (value: unknown): Row => value && typeof value === 'object' && !Array.isArray(value) ? value as Row : {};
const rows = (value: unknown): Row[] => Array.isArray(value) ? value.map(object) : [];
const text = (value: unknown) => typeof value === 'string' ? value : typeof value === 'number' ? String(value) : '';
const domains = ['Enterprise context', 'PKI and trust', 'Encrypted traffic', 'Machine access', 'Software delivery', 'Cloud, keys and identity', 'Protected data', 'Distributed endpoints', 'Specialized and regulated cryptography', 'Governance and assurance'];
const fields = (row: Row, definitions: [string, string][]) => <dl>{definitions.map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{text(row[key]) || 'Not established; retain this limitation.'}</dd></div>)}</dl>;

/** Reading projection of frozen C# report inputs; no new conclusions or decisions. */
export function WorkspaceReportSection({ content }: { content: Record<string, unknown> }) {
  const workspace = object(content.workspace);
  if (workspace.hasActivity !== true) return null;
  const coverage = rows(content.coverageRows);
  const receipts = rows(workspace.receipts);
  const conclusions = rows(workspace.consequences);
  const scenarios = rows(content.scenarioRows);
  const phase2 = content.phase === 'phase2';
  const areaIds = [...new Set(coverage.map(r => text(r.areaId)))].sort();
  return <section className="report-narrative-section" id="report-workspace">
    <p className="eyebrow">REVIEWED RESPONSE → REPORT</p><h2>Discovery-domain positions</h2>
    <p>{text(workspace.populationStatement)}</p><p>{text(workspace.populationBasis)} Receipt, technical review, evidence admission and report acceptance are separate achievements.</p>
    <nav className="report-contents" aria-label="Discovery-domain report contents">{areaIds.map(area => <a key={area} href={`#workspace-${area}`} onClick={event => { event.preventDefault(); document.getElementById(`workspace-${area}`)?.scrollIntoView({ block: 'start' }); }}>{domains[Number(area.slice(-2)) - 1] || humanize(area)}</a>)}</nav>
    {areaIds.map(area => <section className="report-narrative-section" id={`workspace-${area}`} key={area}><h2>{domains[Number(area.slice(-2)) - 1] || humanize(area)}</h2>
      {coverage.filter(r => r.areaId === area).map(source => {
        const family = text(source.familyId);
        const requests = new Set(receipts.filter(r => r.familyId === family).map(r => text(r.requestId)));
        const selected = conclusions.filter(c => requests.has(text(c.requestId)));
        return <article className="record-card" key={family}><h3>{text(source.name)}</h3><p>{text(source.observations)} admitted record(s) · {humanize(text(source.achievedDepth))}. Not an enterprise coverage percentage.</p>
          {!phase2 && selected.map((c, i) => <section key={text(c.id) || i}>{fields(c, [['phase1Conclusion', 'Current-state conclusion'], ['cryptographicPurpose', 'Cryptographic purpose'], ['confidence', 'Evidence adequacy'], ['limitation', 'Qualification / limitation'], ['responsibleFunction', 'Responsible function'], ['nextDecision', 'Next decision']])}</section>)}
          {!phase2 && selected.length === 0 && <p>No workspace conclusion is recorded for this source class. Do not infer low exposure or completeness.</p>}
          {phase2 && scenarios.filter(r => r.familyId === family).map((r, i) => <section key={i}>{fields(r, [['scenario', 'Conditional scenario'], ['businessImpact', 'Business consequence'], ['protectedInformation', 'Protected information'], ['protectedInformationLifetime', 'Confidentiality / trust lifetime'], ['businessStatementBy', 'Attributed business statement'], ['businessStatementDate', 'Statement date'], ['compatibilityConstraints', 'Compatibility constraints'], ['vendorConstraints', 'Vendor constraints'], ['operationalConstraints', 'Operational constraints'], ['recommendation', 'Recommendation'], ['priority', 'Assessment attention'], ['confidence', 'Evidence confidence'], ['confidenceBasis', 'Priority rationale'], ['owner', 'Responsible function'], ['nextDecision', 'Next decision'], ['scenarioState', 'Business review disposition'], ['businessReviewedBy', 'Business reviewer'], ['analysisQualification', 'Retained review qualification']])}</section>)}
        </article>;
      })}
    </section>)}
    <p>These are frozen report inputs. Later source updates or review decisions do not rewrite this snapshot. Neither report acceptance nor ticket completion authorizes migration.</p>
  </section>;
}
