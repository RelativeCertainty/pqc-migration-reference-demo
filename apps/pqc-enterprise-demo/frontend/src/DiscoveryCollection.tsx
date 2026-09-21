import { useEffect, useId, useRef, useState } from 'react';
import { api, ApiError, dateLabel } from './api';
import type { Session } from './contracts';
import type { DiscoveryCollectionCatalog, DiscoveryCollectionForm, DiscoveryCollectionPackage } from './discovery-contracts';

type Pending = { path: string; headers: Record<string, string>; body: string; kind: 'create' | 'export' };
type Props = {
  assessmentId: string; sourceRevision: number; session: Session; disabled: boolean;
  onChanged: () => void | Promise<void>; onBusyChange: (busy: boolean) => void;
  onNavigate: (page: string, params?: Record<string, string>) => void;
};

// A download may never send the reader to another origin or assessment. File identity is server-owned.
function localDownload(value: string, base: string): string | undefined {
  return value.startsWith(`${base}/`) && !/[\\\s%?#]/.test(value) && !value.split('/').some(part => part === '.' || part === '..') ? value : undefined;
}

function DownloadLink({ value, base, label }: { value: string; base: string; label: string }) {
  const href = localDownload(value, base);
  return href ? <a className="button secondary" href={href} download>{label}</a> : <span className="d-help">Download unavailable: reload the saved collection.</span>;
}

function FormReference({ form }: { form: DiscoveryCollectionForm }) {
  return <details className="d-collection-class"><summary><strong>{form.familyName}</strong><span>5 questions</span></summary>
    <p className="d-help">Recognition examples, not confirmed enterprise selections. Include multiple products or deployments in one response; an unlisted product, referral or unknown is useful.</p>
    <p className="d-collection-examples">{form.examples.map(example => example.name).join('; ')}</p>
    <ol className="d-collection-questions">{form.questions.map(question => <li key={question.id}><span className="d-q-id">{question.id}</span><p>{question.prompt}</p><details><summary>Optional help</summary><p>{question.usefulResponse}</p><p>{question.whyItMatters}</p></details></li>)}</ol>
  </details>;
}

function PackageDownloads({ item, base }: { item: DiscoveryCollectionPackage; base: string }) {
  return <section className="d-collection-package" aria-label={`Excel package prepared ${dateLabel(item.createdAt)}`}>
    <p><strong>Prepared {dateLabel(item.createdAt)}</strong> · Saved export snapshot</p>
    <h4>Download individual editable Excel forms</h4>
    <p className="d-help">Each link downloads a physical .xlsx copy. Use individual files when your approved delivery route does not permit ZIP archives.</p>
    <ul className="d-collection-files">{item.forms.map(form => <li key={form.requestId}><DownloadLink value={form.downloadUrl} base={base} label={form.filename} /></li>)}</ul>
    <div className="d-actions"><DownloadLink value={item.indexUrl} base={base} label="Download consolidated questions and guide (Excel)" /></div>
    <p className="d-help">The guide is a reading and navigation copy, not an answer-import form. Return each individual Excel form through its matching web request. An import updates a draft; review and submit separately.</p>
    <details><summary>Optional archive for permitted delivery routes</summary><DownloadLink value={item.zipUrl} base={base} label="Download all 27 Excel forms + consolidated guide (ZIP)" /><p className="d-help">ZIP is optional. Do not use it where the recipient's organization blocks archives.</p></details>
  </section>;
}

export function DiscoveryCollection({ assessmentId, sourceRevision, session, disabled, onChanged, onBusyChange, onNavigate }: Props) {
  const headingId = useId(); const recipientId = useId();
  const base = `/api/assessments/${encodeURIComponent(assessmentId)}/discovery`;
  const [catalog, setCatalog] = useState<DiscoveryCollectionCatalog>(); const [loading, setLoading] = useState(true);
  const [error, setError] = useState(''); const [notice, setNotice] = useState(''); const [revisionConflict, setRevisionConflict] = useState(false);
  const [recipient, setRecipient] = useState(''); const [confirm, setConfirm] = useState(false); const [busy, setBusy] = useState(false); const [reload, setReload] = useState(0);
  const pending = useRef<Pending | null>(null); const acting = useRef(false);
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setError('');
    api<DiscoveryCollectionCatalog>(`${base}/catalog`, { signal: controller.signal }).then(value => {
      if (controller.signal.aborted) return;
      setCatalog(value); setRevisionConflict(false);
    }).catch(reason => { if (!controller.signal.aborted) setError(reason instanceof ApiError ? reason.message : 'The consolidated collection could not be loaded. Existing responses are unchanged.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [base, sourceRevision, reload]);
  const blocked = busy || !!pending.current || revisionConflict;
  useEffect(() => { onBusyChange(blocked); return () => onBusyChange(false); }, [blocked, onBusyChange]);
  async function execute(action: Pending, retry = false) {
    if (acting.current || disabled || !catalog?.canPrepare || !session.csrfToken || revisionConflict || !retry && pending.current) return;
    acting.current = true; pending.current = action; setBusy(true); setError(''); setNotice('');
    try {
      const value = await api<DiscoveryCollectionCatalog>(action.path, { method: 'POST', headers: action.headers, body: action.body });
      pending.current = null; setCatalog(value); setConfirm(false);
      setNotice(action.kind === 'create' ? 'The collection is saved. Its 27 requests are drafts; no email or response was sent. Prepare the Excel collection below, or open an individual web form.' : 'The complete Excel package is prepared. Download links below return this saved snapshot; preparation does not confirm a download or submit answers.');
      await onChanged();
    } catch (reason) {
      if (reason instanceof ApiError && reason.status < 500) pending.current = null;
      if (reason instanceof ApiError && reason.status === 409) { setRevisionConflict(true); setError('The assessment changed or this collection already exists. Reload the saved collection and review it before taking another action. No existing response was overwritten.'); }
      else setError(reason instanceof ApiError ? reason.message : 'Delivery was interrupted. Retry the original operation to reconcile its outcome without creating duplicate requests or files.');
    } finally { acting.current = false; setBusy(false); }
  }
  function command(kind: Pending['kind'], path: string, fields: Record<string, unknown> = {}) {
    if (!catalog || disabled || blocked || !session.csrfToken) return;
    void execute({ kind, path, headers: { 'Content-Type': 'application/json', 'X-PQC-CSRF': session.csrfToken, 'Idempotency-Key': crypto.randomUUID() }, body: JSON.stringify({ expectedRevision: catalog.revision, ...fields }) });
  }
  const locked = disabled || blocked || loading;
  const managementLocked = locked || !session.csrfToken;
  const existingForRecipient = catalog?.collections.some(item => item.assignedTo === recipient);
  const recipientLabel = (id: string) => catalog?.recipients.find(item => item.id === id)?.label || id.replace('synthetic-demo:', '').replaceAll('-', ' ');
  const forms = catalog?.domains.flatMap(domain => domain.forms) || [];
  return <section className="d-panel d-collection" aria-labelledby={headingId}>
    <p className="eyebrow">THE COMPLETE SHORT-DISCOVERY COLLECTION</p>
    <h2 id={headingId}>All 27 software-class forms, together</h2>
    <p>Read the consolidated questions, open a class-specific web form, or prepare the same collection for Excel. These are the new short forms, not the detailed specialist questionnaires.</p>
    {loading && <p role="status">Loading the saved collection…</p>}
    {error && <div className="d-error" role="alert"><p>{error}</p>{pending.current ? <button className="button secondary" disabled={busy || disabled} onClick={() => void execute(pending.current!, true)}>Retry original collection operation</button> : <button className="button secondary" disabled={busy || disabled} onClick={() => { setConfirm(false); setReload(value => value + 1); }}>Reload saved collection</button>}</div>}
    {notice && <p role="status" className="d-collection-notice">{notice}</p>}
    {catalog && <>
      <div className="d-collection-counts" aria-label="Collection contents"><span><strong>{catalog.domainCount}</strong>PQC discovery domains</span><span><strong>{catalog.formCount}</strong>software-class forms</span><span><strong>{catalog.questionsPerForm}</strong>core questions per form</span></div>
      <p className="d-help">Version {catalog.templateVersion}. {catalog.boundary}</p>
      <section className="d-collection-common"><h3>The five questions, in one place</h3><ol>{forms[0]?.questions.map(question => <li key={question.id}><strong>{question.id}</strong> {question.prompt}</li>)}</ol><p className="d-help">The same five questions are reused for each software class, with relevant examples. Having 27 available forms is not a requirement that one person answer them all. The coordinator selects what is relevant; a partial response, referral or explicit unknown is useful.</p></section>
      <details className="d-collection-browser"><summary>Browse all 27 forms by PQC discovery domain</summary>{catalog.domains.map(domain => <section className="d-collection-domain" key={domain.id}><h3>{domain.name}</h3>{domain.forms.map(form => <FormReference key={form.familyId} form={form} />)}</section>)}</details>
      {disabled && <p className="d-help">Collection preparation is paused while another operation is pending or this page has unsaved edits. Save or discard those edits first.</p>}
      {catalog.canPrepare && <section className="d-collection-create"><h3>Prepare a new web-form collection</h3><p>Create one separately tracked draft for every software class. Existing requests and answers stay unchanged. This does not send an email, submit a response, or make a source ready.</p>{!session.csrfToken && <p className="d-help">Sign in again to prepare collections. The saved catalog remains available to read.</p>}<label className="d-field" htmlFor={recipientId}><span>Collection recipient</span><select id={recipientId} value={recipient} disabled={managementLocked || confirm} onChange={event => { setRecipient(event.target.value); setConfirm(false); }}><option value="">Choose the intended recipient</option>{catalog.recipients.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
        {existingForRecipient ? <p className="d-help">A collection already exists for this recipient. Use its web forms and saved exports below; do not create duplicate assignments.</p> : confirm ? <div className="d-collection-confirm"><h4>Confirm 27 new draft requests</h4><p>Recipient: <strong>{recipientLabel(recipient)}</strong>. Assessment: <strong>{catalog.assessmentName}</strong>. One draft per software class; no previous answer will be copied or changed.</p><div className="d-actions"><button className="button primary" disabled={managementLocked || !recipient} onClick={() => command('create', `${base}/collections`, { assignedTo: recipient })}>Create the 27 draft web forms</button><button className="button secondary" disabled={locked} onClick={() => setConfirm(false)}>Cancel creation</button></div></div> : <button className="button secondary" disabled={managementLocked || !recipient} onClick={() => setConfirm(true)}>Review collection creation</button>}
      </section>}
      <section className="d-collection-saved"><h3>Your saved collections</h3>{catalog.collections.length === 0 && <p>No collection is available to your signed-in identity yet. {catalog.canPrepare ? 'Choose a recipient above to prepare one.' : 'Ask the coordinator for your collection or use an existing assignment link.'}</p>}{catalog.collections.map(collection => <article className="d-collection-record" key={collection.id}>
        <h4>{recipientLabel(collection.assignedTo)} · {collection.requests.length} class forms</h4><p className="d-help">Created {dateLabel(collection.createdAt)}. {collection.requests.filter(item => item.status === 'submitted').length} responses submitted; this is response tracking, not assessment completeness.</p>
        <details className="d-collection-web"><summary>Open individual web forms and response status</summary><ul>{collection.requests.map(request => <li key={request.requestId}><div><strong>{forms.find(item => item.familyId === request.familyId)?.familyName || request.familyId}</strong><p className="d-help">{request.status === 'submitted' ? 'Response submitted. No further response is required now.' : 'Draft. A useful answer, referral or unknown can be submitted.'}</p></div><button className="button secondary" disabled={locked} onClick={() => onNavigate('discovery-request', { assessment: assessmentId, request: request.requestId })}>{request.status === 'submitted' ? 'Read submitted response' : 'Open or resume form'}</button></li>)}</ul></details>
        {catalog.canPrepare && <div className="d-collection-export"><button className="button primary" disabled={managementLocked || collection.packages.length >= 3} onClick={() => command('export', `${base}/collections/${encodeURIComponent(collection.id)}/exports`)}>Prepare complete Excel collection</button><p className="d-help">Creates one ZIP with a consolidated reading guide and 27 individually returnable .xlsx forms. It snapshots saved answers only and does not change their status. Up to three retained packages per collection.</p>{collection.packages.length >= 3 && <p className="d-help">The three-package limit has been reached. Existing download links remain available.</p>}</div>}
        {collection.packages.length === 0 ? <p className="d-help">No Excel package has been prepared yet. {catalog.canPrepare ? 'Use the preparation button above.' : 'The coordinator prepares the collection; your existing web forms remain available.'}</p> : [...collection.packages].reverse().map(item => <PackageDownloads key={item.id} item={item} base={base} />)}
      </article>)}</section>
    </>}
  </section>;
}
