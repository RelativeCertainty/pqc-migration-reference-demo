import { humanize } from './api';

type DiscoveryReport = {
  hasActivity?: boolean;
  summary: string;
  responses: { id: string; title: string; answers: { questionId: string; prompt: string; answer: { status: string; text: string; reference: string; assertedBy: string; recordedBy: string } }[] }[];
  investigations: { id: string; purpose: string; assignedTo: string; status: string; researchSummary: string; limitation: string;
    evidence: { batchId: string; productLabel: string; sourceLabel: string; status: string; observationCount: number; reviewRationale: string; observationRefs: string[] }[] }[];
  standards: { id: string; title: string; status: string; proposalText: string; observedPractice: string; existingRequirementStatus: string; proposedAuthority: string; conflictReviewStatus: string; conflictNote: string;
    publicationRefs?: { title: string; url: string; status: string }[] }[];
  limitations: string[]; nextDecision: string;
};
type Finding = { id: string; subjectId: string; subjectLabel: string; title: string; observation: string; evidenceState: string; exposure: string; observationRefs: string[] };
const sentence = (value: string) => /[.!?]$/.test(value.trim()) ? value.trim() : `${value.trim()}.`;

export function DiscoveryReportSection({ content, onInspect }: { content: Record<string, unknown>; onInspect: (id: string) => void }) {
  const discovery = content.discovery as DiscoveryReport | undefined;
  if (!discovery || (!discovery.hasActivity && !discovery.responses.length && !discovery.investigations.length)) return null;
  const observationIds = new Set(discovery.investigations.flatMap(i => i.evidence.flatMap(e => e.observationRefs)));
  const findings = ((content.findings as Finding[] | undefined) || []).filter(f => f.observationRefs.some(id => observationIds.has(id)));
  const workspace = content.workspace as { hasActivity?: boolean; bundles?: { status: string }[] } | undefined;
  const workspaceAdmitted = workspace?.hasActivity && workspace.bundles?.some(b => b.status === 'admitted');
  return <section className="report-narrative-section" id="report-discovery">
    <p className="eyebrow">CONTRIBUTION → INVESTIGATION → REPORT</p>
    <h2>What discovery changed</h2><p>{discovery.summary}</p>
    <h3>Technical conclusions supported by admitted records</h3>
    {!findings.length && <p>{workspaceAdmitted ? 'Reviewed technical records admitted through Assessment work are presented in the discovery-domain positions above. This older discovery-investigation section has no separate technical findings; questionnaire answers remain attributed context.' : 'No technical findings are linked through this discovery-investigation path. Received answers alone support routing and limitations, not technical verification.'}</p>}
    {findings.map(f => <article className="record-card" key={f.id}><h4>{f.subjectLabel}</h4><p>{f.observation}</p>
      <p><strong>Assessment implication:</strong> {f.exposure === 'mixed_classical_and_hybrid' ? 'Hybrid key exchange and classical certificate signatures are separate uses. This is not an application-wide migration outcome.' : humanize(f.exposure)}</p>
      <p><strong>Next action:</strong> Confirm business context, relying parties and independent behavior before proposing migration. Product readiness and company-policy compliance are not established.</p>
      <button className="text-button" onClick={() => onInspect(f.subjectId)}>Inspect supporting records →</button></article>)}
    <h3>Engineering follow-through</h3>
    {discovery.investigations.map(i => <article className="record-card" key={i.id}><h4>{i.purpose}</h4><p>{humanize(i.status)} · {i.assignedTo}</p><p>{i.researchSummary || 'Research not yet recorded.'}</p>
      <p><strong>Limitation:</strong> {i.limitation || 'Technical scope and evidence limitations still require review.'}</p>
      <ul>{i.evidence.map(e => <li key={e.batchId}>{e.productLabel}: {humanize(e.status)} — {e.observationCount} observation(s). {e.status === 'admitted' ? 'Included in the map and report inputs.' : 'Not included in technical conclusions.'} {e.reviewRationale}</li>)}</ul></article>)}
    <details><summary>Submitted discovery contributions and attribution</summary>{discovery.responses.map(r => <article key={r.id}><h3>{r.title}</h3><dl>{r.answers.map(q => <div key={q.questionId}><dt>{q.prompt}</dt><dd>{humanize(q.answer.status)}{q.answer.text && ` — ${q.answer.text}`}<p>Reference: {q.answer.reference || 'Not supplied'}. Asserted by {q.answer.assertedBy || 'Not recorded'}; recorded by {q.answer.recordedBy || 'not recorded'}.</p></dd></div>)}</dl></article>)}</details>
    <h3>Standards proposed for company review</h3><p>These drafts support recommendations, not retrospective noncompliance findings. Missing documentation does not mean no policy exists.</p>
    {discovery.standards.map(s => <article className="record-card" key={s.id}><h4>{s.title} · Draft, not adopted</h4><p>Existing requirements: {humanize(s.existingRequirementStatus)}. Review authority: {s.proposedAuthority || 'To be identified'} (not adoption).</p><p>Recorded practice: {sentence(s.observedPractice || 'Not established')} Conflict review: {humanize(s.conflictReviewStatus)}. {s.conflictNote}</p>
      <details><summary>Read the proposed standard and references</summary><p style={{ whiteSpace: 'pre-line' }}>{s.proposalText}</p><ul>{s.publicationRefs?.map(r => <li key={r.url}><a href={r.url} target="_blank" rel="noreferrer">{r.title}</a> — {r.status}</li>)}</ul></details></article>)}
    <p><strong>Decision required:</strong> {discovery.nextDecision}</p>
  </section>;
}
