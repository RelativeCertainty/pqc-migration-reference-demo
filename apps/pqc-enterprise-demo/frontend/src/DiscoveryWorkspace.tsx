import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { api, ApiError, dateLabel, humanize, selectedAssessmentId } from './api';
import { useApi } from './use-api';
import { DiscoveryCollection } from './DiscoveryCollection';
import type { Session } from './contracts';
import type { AssessmentSummary } from './assessment-contracts';
import type { DiscoveryAnswer, DiscoveryAnswerStatus, DiscoveryCommand, DiscoveryDetail, DiscoveryExport, DiscoveryImport, DiscoveryInvestigation, DiscoveryList, DiscoveryProduct, DiscoveryRecognition, DiscoveryRecognitionExample, DiscoveryRecognitionFamily, DiscoveryRequest, DiscoveryStandard } from './discovery-contracts';
import './discovery.css';

type Navigate = (page: string, params?: Record<string, string>) => void;
type Send = (operation: string, targetId: string | null, fields: Record<string, unknown>) => Promise<boolean>;
type View = DiscoveryList | DiscoveryDetail;
type Pending = { path: string; headers: Record<string, string>; body: BodyInit; success?: (value: unknown) => void };
const detailView = (value: View): value is DiscoveryDetail => 'request' in value;
const requestInUrl = () => new URLSearchParams(window.location.hash.split('?')[1]).get('request') || '';
const states: { value: DiscoveryAnswerStatus; label: string }[] = [
  { value: 'unanswered', label: 'Not answered yet' }, { value: 'answered', label: 'I can provide information' },
  { value: 'unknown', label: 'I do not know' }, { value: 'not_my_team', label: 'Not my team' },
  { value: 'referral', label: 'Try another team or contact' }, { value: 'not_applicable', label: 'Not applicable, as far as I know' },
];
const statusLabel = (value: string) => states.find(item => item.value === value)?.label || humanize(value);
const answerFor = (value?: Partial<DiscoveryAnswer>): DiscoveryAnswer => ({ status: 'unanswered', text: '', reference: '', ...value });
const writableAnswer = (value?: Partial<DiscoveryAnswer>) => { const item = answerFor(value); return { status: item.status, text: item.text, reference: item.reference }; };
const writableProduct = (value: DiscoveryProduct) => ({ id: value.id, label: value.label.trim() || value.product.trim(), product: value.product, environment: value.environment });
const lines = (value: string) => value.split('\n').map(item => item.trim()).filter(Boolean);
const principalLabel = (value: string) => humanize(value.replace('synthetic-demo:', ''));

function Field({ label, value, change, multiline = false, disabled = false, help, maxLength = 4096 }: { label: string; value: string; change: (value: string) => void; multiline?: boolean; disabled?: boolean; help?: string; maxLength?: number }) {
  const id = useId();
  return <div className="d-field"><label htmlFor={id}>{label}</label>{multiline ? <textarea id={id} value={value} onChange={event => change(event.target.value)} disabled={disabled} maxLength={maxLength} aria-describedby={help ? `${id}-help` : undefined} /> : <input id={id} value={value} onChange={event => change(event.target.value)} disabled={disabled} maxLength={maxLength} aria-describedby={help ? `${id}-help` : undefined} />}{help && <p className="d-help" id={`${id}-help`}>{help}</p>}</div>;
}
function Select({ label, value, change, options, disabled = false }: { label: string; value: string; change: (value: string) => void; options: { value: string; label: string }[]; disabled?: boolean }) {
  const id = useId(); return <div className="d-field"><label htmlFor={id}>{label}</label><select id={id} value={value} onChange={event => change(event.target.value)} disabled={disabled}>{options.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select></div>;
}
function Examples({ values }: { values: string[] }) { return values.length ? <div className="d-examples"><p><strong>Examples of this software class:</strong> {values.slice(0, 3).join('; ')}. These are recognition examples, not confirmed enterprise selections.</p>{values.length > 3 && <details><summary>More examples</summary><p>{values.slice(3).join('; ')}</p></details>}</div> : null; }

function recognitionSource(value: string): string | undefined {
  if (!/^https:\/\//i.test(value) || /[\s\\]/.test(value)) return undefined;
  try { const url = new URL(value); return url.protocol === 'https:' && url.hostname && !url.username && !url.password ? url.href : undefined; }
  catch { return undefined; }
}

function RecognitionExamples({ examples }: { examples: DiscoveryRecognitionExample[] }) {
  return <ul className="d-recognition-examples">{examples.map((example, index) => {
    const source = recognitionSource(example.url);
    return <li key={`${example.name}-${index}`}>
      <div className="d-recognition-product">{source ? <a href={source} target="_blank" rel="noopener noreferrer" title={`Product source: ${example.name}`}>{example.name}</a> : <span>{example.name}</span>}<span className="d-recognition-kind">{example.kind}</span></div>
      {example.note && <p>{example.note}</p>}
    </li>;
  })}</ul>;
}

function RecognitionFamily({ family }: { family: DiscoveryRecognitionFamily }) {
  return <section className="d-recognition-family" aria-label={`${family.name} recognition examples`}><h3>{family.name}</h3><RecognitionExamples examples={family.examples} /></section>;
}

function RecognitionReference({ recognition, family }: { recognition: DiscoveryRecognition; family: DiscoveryRecognitionFamily }) {
  const headingId = useId();
  const siblings = recognition.domain.families.filter(item => item.id !== family.id);
  return <section className="d-recognition" aria-labelledby={headingId}>
    <h2 id={headingId}>Products you may recognize</h2>
    <p className="d-recognition-intro">COTS, OTS and enterprise SaaS examples for <strong>{family.name}</strong>. Product names link to their sources.</p>
    <p className="d-recognition-boundary">{recognition.boundary}</p>
    <RecognitionExamples examples={family.examples} />
    {siblings.length > 0 && <details className="d-recognition-browse"><summary>Explore other software classes in {recognition.domain.name}</summary>{siblings.map(item => <RecognitionFamily key={item.id} family={item} />)}</details>}
    <details className="d-recognition-browse"><summary>Browse all {recognition.domains.length} PQC discovery domains</summary>
      <p className="d-help">Explore the reference without changing your assigned software class or response. Add products you know are used in the answer below.</p>
      {recognition.domains.map(domain => <details className="d-recognition-domain" key={domain.id}><summary>{domain.name} <span>· {domain.families.length} software {domain.families.length === 1 ? 'class' : 'classes'}</span></summary>{domain.families.map(item => <RecognitionFamily key={item.id} family={item} />)}</details>)}
    </details>
    <details className="d-recognition-browse d-recognition-provenance"><summary>About this recognition reference</summary><p>Reference version {recognition.catalogVersion} · Reviewed {recognition.reviewedAt}. This catalog is maintained separately from the questions and examples saved with your request.</p><p>Catalog SHA-256: <code>{recognition.catalogSha256}</code></p></details>
  </section>;
}

export function DiscoveryWorkspace({ session, mode, onNavigate, onDirtyChange }: { session: Session; mode: 'respondent' | 'list'; onNavigate: Navigate; onDirtyChange?: (dirty: boolean) => void }) {
  const [assessmentId, setAssessmentId] = useState(selectedAssessmentId); const [requestId, setRequestId] = useState(requestInUrl);
  const [view, setView] = useState<View>(); const [loading, setLoading] = useState(false); const [error, setError] = useState('');
  const [accessError, setAccessError] = useState(false); const [busy, setBusy] = useState(false); const [conflict, setConflict] = useState(false);
  const [collectionBusy, setCollectionBusy] = useState(false);
  const [collectionListStale, setCollectionListStale] = useState(false);
  const [dirty, setDirty] = useState(false); const [refresh, setRefresh] = useState(0); const [epoch, setEpoch] = useState(0);
  const [exported, setExported] = useState<DiscoveryExport>(); const [preview, setPreview] = useState<DiscoveryImport>();
  const pending = useRef<Pending | null>(null); const acting = useRef(false);
  const base = `/api/assessments/${encodeURIComponent(assessmentId)}/discovery`;
  useEffect(() => { const update = () => { setAssessmentId(selectedAssessmentId()); setRequestId(requestInUrl()); }; window.addEventListener('hashchange', update); return () => window.removeEventListener('hashchange', update); }, []);
  useEffect(() => { onDirtyChange?.(dirty); return () => onDirtyChange?.(false); }, [dirty, onDirtyChange]);
  useEffect(() => { if (!dirty) return; const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; }; window.addEventListener('beforeunload', warn); return () => window.removeEventListener('beforeunload', warn); }, [dirty]);
  useEffect(() => {
    setView(undefined); setError(''); setAccessError(false); setConflict(false); setCollectionListStale(false); pending.current = null; setExported(undefined); setPreview(undefined);
    if (!assessmentId || mode === 'respondent' && !requestId) { setLoading(false); return; }
    const controller = new AbortController(); setLoading(true);
    api<View>(mode === 'respondent' ? `${base}/${encodeURIComponent(requestId)}` : base, { signal: controller.signal }).then(value => { if (!controller.signal.aborted) setView(value); }).catch(reason => {
      if (controller.signal.aborted) return;
      if (reason instanceof ApiError && [403, 404].includes(reason.status)) { setAccessError(true); setError('This request is not available to your signed-in identity. Use your own assignment link or ask the coordinator to check the recipient.'); }
      else setError('The saved discovery request could not be loaded. No response has been changed.');
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); }); return () => controller.abort();
  }, [assessmentId, requestId, base, mode, refresh]);
  function headers(contentType = 'application/json') { return { 'X-PQC-CSRF': session.csrfToken || '', 'Idempotency-Key': crypto.randomUUID(), 'Content-Type': contentType }; }
  async function execute(action: Pending, retry = false): Promise<boolean> {
    if (acting.current || conflict || !retry && pending.current) return false;
    acting.current = true; pending.current = action; setBusy(true); setError('');
    try {
      const result = await api<View>(action.path, { method: 'POST', headers: action.headers, body: action.body }); pending.current = null;
      if (action.success) action.success(result);
      else { setExported(undefined); setPreview(undefined); if (mode === 'list' && detailView(result)) setRefresh(value => value + 1); else setView(result); }
      return true;
    } catch (reason) {
      if (reason instanceof ApiError && reason.status < 500) pending.current = null;
      if (reason instanceof ApiError && reason.status === 409) { setConflict(true); setError('The saved revision or action eligibility changed. Your visible edits are preserved. Copy anything needed before loading saved data; nothing has been overwritten.'); }
      else setError(reason instanceof ApiError ? reason.message : 'Delivery was interrupted. Retry the same operation to resolve its outcome without sending a duplicate.');
      return false;
    } finally { acting.current = false; setBusy(false); }
  }
  const send: Send = async (operation, targetId, fields) => {
    if (!view || !session.csrfToken) return false;
    const body: DiscoveryCommand = { operation, targetId: targetId ?? null, fields, expectedRevision: view.revision };
    return execute({ path: `${base}/commands`, headers: headers(), body: JSON.stringify(body) });
  };
  async function prepareExcel() {
    if (!view || !detailView(view) || dirty) return;
    await execute({ path: `${base}/exports/${encodeURIComponent(view.request.id)}`, headers: headers(), body: JSON.stringify({ expectedRevision: view.revision }), success: value => { const result = value as DiscoveryExport; setExported(result); setView(current => current && { ...current, revision: result.revision }); } });
  }
  async function importExcel(file?: File) {
    if (!file || !view || !detailView(view) || dirty) return;
    if (!file.name.toLowerCase().endsWith('.xlsx') || file.size > 1024 * 1024) { setError('Choose the generated discovery .xlsx file, no larger than 1 MiB. No file has been sent.'); return; }
    await execute({ path: `${base}/imports/${encodeURIComponent(view.request.id)}?expectedRevision=${view.revision}`, headers: headers('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'), body: file, success: value => { const result = value as DiscoveryImport; setPreview(result); setView(current => current && { ...current, revision: result.revision }); } });
  }
  async function commitExcel(choices: Record<string, 'current' | 'returned'>) {
    if (!view || !preview || dirty) return;
    await execute({ path: `${base}/imports/${encodeURIComponent(preview.import.id)}/commit`, headers: headers(), body: JSON.stringify({ expectedRevision: view.revision, choices }) });
  }
  async function stageEvidence(investigationId: string, productRefId: string, sourceLabel: string, file: File) {
    if (!view || dirty) return false;
    if (file.size > 32768 || !file.name.toLowerCase().endsWith('.json')) { setError('Choose a controlled synthetic TLS JSON fixture, maximum 32 KiB. No file has been sent.'); return false; }
    const query = new URLSearchParams({ expectedRevision: String(view.revision), productRefId, sourceLabel });
    return execute({ path: `${base}/investigations/${encodeURIComponent(investigationId)}/evidence?${query}`, headers: headers('application/json'), body: file });
  }
  async function refreshCollectionList() {
    setBusy(true); setError('');
    try {
      const value = await api<DiscoveryList>(base);
      setView(current => current && !detailView(current) && current.assessmentId === value.assessmentId ? value : current);
      setCollectionListStale(false);
    } catch {
      setCollectionListStale(true);
      setError('The collection is saved, but the request list could not be refreshed. Reload the request list before editing another response; do not repeat the collection command.');
    } finally { setBusy(false); }
  }
  const locked = busy || conflict || !!pending.current || collectionBusy || collectionListStale;
  return <div className="discovery-workspace">
    <header className={`d-heading${view && detailView(view) ? ' d-heading-request' : ''}`}>
      <p className="eyebrow">{mode === 'respondent' ? 'FIVE-QUESTION DISCOVERY REQUEST' : 'DISCOVERY & MOBILIZATION'}</p>
      <h1>{view && detailView(view) ? view.request.title : mode === 'respondent' ? 'Your discovery request' : 'Find the right sources'}</h1>
      {view && detailView(view) && view.recognition && <section className="d-discovery-domain" aria-labelledby="discovery-domain"><p>PQC discovery domain</p><h2 id="discovery-domain">{view.recognition.domain.name}</h2></section>}
      {view && detailView(view) && <section className="d-software-class" aria-labelledby="discovery-software-class">
        <p>Software class</p><h2 id="discovery-software-class">{view.request.familyName}</h2>
      </section>}
      {!(view && detailView(view) && view.request.status === 'submitted') && <p>{view && detailView(view) ? view.guidance.introduction : 'Help identify relevant products, teams and existing information. A brief answer, referral or “not sure” is useful.'}</p>}
      {view && detailView(view) && <p className="d-handling-notice">{view.guidance.handlingNotice}</p>}
    </header>
    <p className="d-boundary">Synthetic development information only. Do not enter credentials, private keys or customer data.</p>
    {mode === 'list' && <AssessmentChoice selected={assessmentId} disabled={locked || dirty} canCreate={session.role === 'analyst'} choose={id => onNavigate('discovery', { assessment: id, request: '' })} create={() => onNavigate('assessments', { assessment: '', from: 'discovery' })} />}
    {mode === 'respondent' && (!assessmentId || !requestId) && <section className="d-panel"><h2>Open your request link</h2><p>The coordinator provides an exact assignment link. You do not need to configure the assessment.</p><button className="button secondary" onClick={() => onNavigate('discovery', { request: '' })}>Find my requests</button></section>}
    {loading && <p role="status">Loading the saved request…</p>}
    {error && <section className="d-error" role="alert"><p>{error}</p>{pending.current && <button className="button secondary" disabled={busy} onClick={() => void execute(pending.current!, true)}>Retry original operation</button>}{collectionListStale && <button className="button secondary" disabled={busy} onClick={() => void refreshCollectionList()}>Reload request list</button>}{conflict && <button className="button secondary" onClick={() => { setDirty(false); setEpoch(value => value + 1); setRefresh(value => value + 1); }}>Discard local edits and load saved revision</button>}{accessError && <button className="button secondary" onClick={() => onNavigate('discovery', { assessment: '', request: '' })}>Choose my own request</button>}{!view && !accessError && !loading && <button className="button secondary" onClick={() => setRefresh(value => value + 1)}>Reload requests</button>}</section>}
    {exported && <p className="d-help" role="status">The Excel copy is prepared, but this does not confirm a download. If Chrome says “Blocked by your organization,” ask your browser administrator to review the restriction. You can continue using this web form; do not disable browser protections.</p>}
    {view && detailView(view) && <ResponseForm key={`${view.request.id}-${epoch}`} detail={view} locked={locked} send={send} onDirtyChange={setDirty} offline={<details className="d-offline"><summary>Use the same five questions in Excel</summary><p>Save web edits first. Returned files update a draft; review and submit it separately.</p><button className="button secondary" disabled={locked || dirty || !view.canEdit} onClick={() => void prepareExcel()}>Prepare Excel form</button>{exported && !dirty && exported.downloadUrl.startsWith(`${base}/exports/`) && <a className="button secondary" href={exported.downloadUrl} download>Download prepared form</a>}<label className="d-field">Preview returned discovery form (.xlsx, maximum 1 MiB)<input type="file" accept=".xlsx" disabled={locked || dirty || !view.canEdit} onChange={event => { void importExcel(event.target.files?.[0]); event.target.value = ''; }} /></label><p className="d-help">Use the generated format. Blank Excel cells retain the export value; use the web form to clear an answer explicitly.</p>{dirty && <p>Excel is paused until web edits are saved or discarded.</p>}{preview && <ImportPreview key={preview.import.id} value={preview} disabled={locked || dirty || !view.canEdit} commit={commitExcel} />}</details>} />}
    {view && !detailView(view) && view.collectionAvailable && <DiscoveryCollection key={view.assessmentId} assessmentId={view.assessmentId} sourceRevision={view.revision} session={session} disabled={busy || conflict || !!pending.current || dirty || collectionListStale} onChanged={refreshCollectionList} onBusyChange={setCollectionBusy} onNavigate={onNavigate} />}
    {view && !detailView(view) && <StaffWorkspace key={`${view.assessmentId}-${epoch}`} view={view} session={session} locked={locked} dirty={dirty} onDirtyChange={setDirty} send={send} onNavigate={onNavigate} stageEvidence={stageEvidence} />}
  </div>;
}

function AssessmentChoice({ selected, disabled, canCreate, choose, create }: { selected: string; disabled: boolean; canCreate: boolean; choose: (id: string) => void; create: () => void }) {
  const list = useApi<AssessmentSummary[]>('/api/assessments');
  return <section className="d-panel"><Select label="Assessment" value={selected} change={choose} disabled={disabled || list.loading} options={[{ value: '', label: 'Choose an assessment with your requests' }, ...(list.data || []).map(item => ({ value: item.id, label: item.name }))]} />{list.error && <p role="alert">{list.error} <button className="text-button" onClick={list.reload}>Reload choices</button></p>}{!selected && <p className="d-help">An empty list means no request is assigned to this identity. Respondents can open their exact request link directly.</p>}{canCreate && !selected && <button className="text-button" onClick={create} disabled={disabled}>Set up an assessment →</button>}</section>;
}

function ResponseForm({ detail, locked, send, onDirtyChange, offline }: { detail: DiscoveryDetail; locked: boolean; send: Send; onDirtyChange: (dirty: boolean) => void; offline: ReactNode }) {
  const request = detail.request;
  const recognitionFamily = detail.recognition?.domain.families.find(item => item.id === request.familyId);
  const saved = JSON.stringify({ answers: request.answers, products: request.productRefs });
  const synchronized = useRef(saved);
  const [answers, setAnswers] = useState(request.answers); const [products, setProducts] = useState(request.productRefs);
  const [review, setReview] = useState(false); const [notice, setNotice] = useState(''); const [productIssue, setProductIssue] = useState('');
  const reviewHeading = useRef<HTMLHeadingElement>(null); const completionHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    const heading = request.status === 'submitted' ? completionHeading.current : review ? reviewHeading.current : null;
    if (heading) { heading.focus({ preventScroll: true }); heading.scrollIntoView?.({ block: 'start' }); }
  }, [request.status, review]);
  useLayoutEffect(() => { if (synchronized.current === saved) return; synchronized.current = saved; setAnswers(request.answers); setProducts(request.productRefs); }, [saved, request.answers, request.productRefs]);
  const changedAnswers = Object.fromEntries(request.questions.filter(item => JSON.stringify(writableAnswer(answers[item.id])) !== JSON.stringify(writableAnswer(request.answers[item.id]))).map(item => [item.id, writableAnswer(answers[item.id])]));
  const changedProducts = JSON.stringify(products) !== JSON.stringify(request.productRefs);
  const dirty = Object.keys(changedAnswers).length > 0 || changedProducts;
  useEffect(() => { onDirtyChange(dirty); return () => onDirtyChange(false); }, [dirty, onDirtyChange]);
  const disabled = locked || !detail.canEdit;
  async function save() {
    const unnamed = products.findIndex(item => !item.product.trim() && !item.label.trim());
    if (unnamed >= 0) { setProductIssue(`Enter a software or deployment name for entry ${unnamed + 1}, or remove that empty entry. You can still submit a partial response without listing any products.`); return false; }
    setProductIssue('');
    if (!dirty) { setNotice('Your visible response is already saved.'); return true; }
    const ok = await send('discovery_save', request.id, { ...(Object.keys(changedAnswers).length ? { answers: changedAnswers } : {}), ...(changedProducts ? { productRefs: products.map(writableProduct) } : {}) });
    if (ok) setNotice('Draft saved. This has not yet been handed to the coordinator.'); return ok;
  }
  function update(id: string, patch: Partial<DiscoveryAnswer>) { setAnswers(current => ({ ...current, [id]: { ...answerFor(current[id]), ...patch } })); setNotice(''); }
  function updateProducts(next: DiscoveryProduct[]) { setProducts(next); setProductIssue(''); setNotice(''); }
  const addressed = request.questions.filter(item => answerFor(answers[item.id]).status !== 'unanswered').length;
  if (request.status === 'submitted') return <><section className="d-complete" role="status"><p className="eyebrow">RESPONSE SUBMITTED</p><h2 ref={completionHeading} tabIndex={-1}>Thank you. No further response is required now.</h2><p>{detail.guidance.submissionReceipt}</p>{request.submission && <p className="d-help">Submitted {dateLabel(request.submission.submittedAt)} by {principalLabel(request.submission.submittedBy)}.</p>}</section><LegacyGuidance notice={detail.guidance.legacyNotice} /><Readback request={request} answers={answers} products={products} /></>;
  return <div className="d-form"><div className="d-context"><span>Assigned to <strong>{principalLabel(request.assignedTo)}</strong></span><span className={`d-status ${dirty ? 'unsaved' : ''}`}>{dirty ? 'Unsaved changes' : 'Draft · not submitted'}</span><span>{request.questions.length} questions · {addressed} with a response state</span><span>{products.length} software / deployment entries</span></div>
    <div className="d-draft-actions"><button className="button primary" disabled={disabled} onClick={() => void save()}>Save draft</button><button className="button secondary" disabled={disabled} onClick={() => void (async () => { if (await save()) setReview(true); })()}>Review and submit</button>{dirty && <button className="text-button" disabled={locked} onClick={() => { setAnswers(request.answers); setProducts(request.productRefs); setProductIssue(''); setReview(false); setNotice('Local edits discarded. The saved response is unchanged.'); }}>Discard unsaved edits</button>}</div>
    {notice && <p role="status">{notice}</p>}{productIssue && <p className="d-error" role="alert">{productIssue}</p>}{!detail.canEdit && <p className="d-help">You can read this request. Only its assigned respondent or assessment lead can edit a draft.</p>}
    {review ? <section className="d-panel"><h2 ref={reviewHeading} tabIndex={-1}>Check your response before handing it over</h2><p>{detail.guidance.reviewNotice}</p><LegacyGuidance notice={detail.guidance.legacyNotice} /><Readback request={request} answers={answers} products={products} />{detail.validation.issues.length > 0 && <div className="d-error" role="alert"><h3>Before submission</h3><ul>{detail.validation.issues.map((item, index) => <li key={index}>{item}</li>)}</ul></div>}<div className="d-actions"><button className="button secondary" onClick={() => setReview(false)}>Return to editing</button><button className="button primary" disabled={disabled || dirty || !detail.validation.canSubmit} onClick={() => void send('discovery_submit', request.id, {})}>Submit response to coordinator</button></div></section> : <>
      <LegacyGuidance notice={detail.guidance.legacyNotice} />
      {detail.recognition && recognitionFamily && <RecognitionReference recognition={detail.recognition} family={recognitionFamily} />}
      {request.questions.map((question, index) => { const answer = answerFor(answers[question.id]); const examples = question.examples.length ? question.examples : index === 0 ? request.examples : []; return <section className="d-question" key={question.id} aria-labelledby={`discovery-${question.id}`}><span className="d-q-id">{question.id} · Question {index + 1} of {request.questions.length}</span><h2 id={`discovery-${question.id}`}>{question.prompt}</h2>{detail.recognition && recognitionFamily ? examples.length > 0 && <details><summary>Examples saved with this question</summary><Examples values={examples} /></details> : <Examples values={examples} />}
        {index === 0 && <ProductEntries products={products} disabled={disabled} change={updateProducts} />}
        <Select label={`What can you tell us? — ${question.id}`} value={answer.status} change={value => update(question.id, { status: value as DiscoveryAnswerStatus })} options={states} disabled={disabled} /><Field label={`Your response to ${question.id}`} value={answer.text} multiline disabled={disabled} change={text => update(question.id, { text, ...(answer.status === 'unanswered' && text.trim() ? { status: 'answered' as const } : {}) })} help={question.usefulResponse} /><details className="d-reference-help" open={Boolean(answer.reference.trim())}><summary>Optional reference and why we ask · {question.id}</summary><p>{question.whyItMatters}</p><Field label={`Existing reference for ${question.id} (optional)`} value={answer.reference} disabled={disabled} maxLength={1024} change={reference => update(question.id, { reference })} help="An existing document, inventory or team reference is enough. Do not include credentials or upload sensitive content." /></details></section>; })}
      {offline}
      <div className="d-actions"><button className="button primary" disabled={disabled} onClick={() => void save()}>Save draft</button><button className="button secondary" disabled={disabled} onClick={() => void (async () => { if (await save()) setReview(true); })()}>Review and submit</button></div>
    </>}
  </div>;
}

function LegacyGuidance({ notice }: { notice: string }) { return notice ? <aside className="d-panel d-legacy-guidance" aria-label="About this earlier request"><h3>About this earlier request</h3><p>{notice}</p></aside> : null; }

function ProductEntries({ products, disabled, change }: { products: DiscoveryProduct[]; disabled: boolean; change: (products: DiscoveryProduct[]) => void }) {
  function update(index: number, field: 'label' | 'product' | 'environment', value: string) { change(products.map((item, at) => at === index ? { ...item, [field]: value } : item)); }
  return <section className="d-product-list" aria-labelledby="discovery-products">
    <h3 id="discovery-products">Known software in this class <span>(optional)</span></h3>
    <p>Add each product separately. For another deployment of the same product, add another entry. A software name alone is enough.</p>
    {!products.length && <p className="d-help">No software listed yet. You may use the answer box instead, give a referral, or say you do not know.</p>}
    {products.map((product, index) => <fieldset className="d-product" key={product.id || `new-${index}`}>
      <legend>Software / deployment {index + 1}</legend>
      <Field label={`Software / product name ${index + 1}`} value={product.product} maxLength={256} disabled={disabled} change={value => update(index, 'product', value)} />
      <div className="d-product-fields">
        <Field label={`Deployment / identifying name ${index + 1} (optional)`} value={product.label} maxLength={256} disabled={disabled} change={value => update(index, 'label', value)} help="For example, a regional instance or team-managed installation." />
        <Field label={`Environment ${index + 1} (optional)`} value={product.environment} maxLength={256} disabled={disabled} change={value => update(index, 'environment', value)} />
      </div>
      <button className="text-button" disabled={disabled} onClick={() => change(products.filter((_, at) => at !== index))}>Remove entry {index + 1}</button>
    </fieldset>)}
    <button className="button secondary d-add-product" disabled={disabled || products.length >= 20} onClick={() => change([...products, { id: '', label: '', product: '', environment: '' }])}>{products.length ? 'Add another software or deployment' : 'Add software or deployment'}</button>
    <p className="d-help">Up to 20 entries in one response. No separate questionnaire is required for each product. Information already entered above does not need to be repeated below.</p>
  </section>;
}

function Readback({ request, answers, products }: { request: DiscoveryRequest; answers: Record<string, DiscoveryAnswer>; products: DiscoveryProduct[] }) { return <div className="d-readback">{products.length > 0 && <section><h3>Known products and deployments</h3><ul>{products.map((item, index) => <li key={item.id || index}><strong>{item.product || item.label}</strong>{item.label && item.label !== item.product && <> — {item.label}</>}{item.environment && <> · {item.environment}</>}</li>)}</ul></section>}{request.questions.map(question => { const answer = answerFor(answers[question.id]); return <section key={question.id}><h3>{question.id} · {question.prompt}</h3><strong>{statusLabel(answer.status)}</strong><p>{answer.text || 'No additional text provided.'}</p>{answer.reference && <p>Existing reference: {answer.reference}</p>}{answer.assertedBy && <p className="d-help">Attributed to {principalLabel(answer.assertedBy)}; recorded by {principalLabel(answer.recordedBy || 'not recorded')}.</p>}</section>; })}</div>; }

function ImportPreview({ value, disabled, commit }: { value: DiscoveryImport; disabled: boolean; commit: (choices: Record<string, 'current' | 'returned'>) => Promise<void> }) {
  const [choices, setChoices] = useState<Record<string, 'current' | 'returned'>>({});
  const conflicts = value.import.changes.filter(item => item.state === 'conflict');
  return <section className="d-panel"><h3>Review returned answers</h3><p>Changes are a draft only. Resolve every competing edit before applying; no submission or approval is imported.</p>{value.import.changes.filter(item => item.state !== 'unchanged').map(item => <article className="d-compare" key={item.questionId}><h4>{item.questionId} · {item.state === 'conflict' ? 'Competing edit—choose a version' : 'Returned change'}</h4>{(['baseline', 'current', 'returned'] as const).map(version => <div key={version}><strong>{version === 'baseline' ? 'At export' : humanize(version)}</strong><p>{statusLabel(item[version].status)}: {item[version].text || 'No text'}</p>{item[version].reference && <p>Reference: {item[version].reference}</p>}</div>)}{item.state === 'conflict' && <Select label={`Keep which answer for ${item.questionId}?`} value={choices[item.questionId] || ''} change={choice => setChoices(current => ({ ...current, [item.questionId]: choice as 'current' | 'returned' }))} disabled={disabled} options={[{ value: '', label: 'Choose a version' }, { value: 'current', label: 'Keep saved web answer' }, { value: 'returned', label: 'Use returned Excel answer' }]} />}</article>)}{value.import.changes.every(item => item.state === 'unchanged') && <p>No changed answers were returned.</p>}<button className="button primary" disabled={disabled || conflicts.some(item => !choices[item.questionId])} onClick={() => void commit(choices)}>Apply to draft</button></section>;
}

function StaffWorkspace({ view, session, locked, dirty, onDirtyChange, send, onNavigate, stageEvidence }: { view: DiscoveryList; session: Session; locked: boolean; dirty: boolean; onDirtyChange: (dirty: boolean) => void; send: Send; onNavigate: Navigate; stageEvidence: (id: string, product: string, source: string, file: File) => Promise<boolean> }) {
  const [tab, setTab] = useState<'requests' | 'standards' | 'engineering'>('requests'); const [selected, setSelected] = useState('');
  const staff = view.canCoordinate || view.canResearch || view.canReviewEvidence || !session.role?.startsWith('contributor');
  return <>
    {staff && <div className="d-tabs" role="group" aria-label="Discovery work surfaces">{[{ id: 'requests', label: 'Discovery requests' }, { id: 'standards', label: 'Draft standards proposals' }, { id: 'engineering', label: 'Engineering investigations' }].map(item => <button key={item.id} className={tab === item.id ? 'active' : ''} aria-pressed={tab === item.id} disabled={dirty || locked} onClick={() => { setSelected(''); setTab(item.id as typeof tab); }}>{item.label}</button>)}</div>}
    {tab === 'requests' && <><section className="d-panel"><h2>{view.canCoordinate ? 'Requests and returned responses' : 'My discovery requests'}</h2><p className="d-help">Five questions to help identify products, teams and existing information. Brief answers, referrals and “not sure” are useful. The coordinator organizes any follow-up.</p>{view.requests.length === 0 && <p>No discovery requests are available here. {view.canCoordinate ? 'Create a request for the software class you want to identify.' : 'Ask the coordinator for your exact assignment link.'}</p>}{view.requests.map(request => <RequestCard key={request.id} request={request} view={view} locked={locked || dirty} send={send} open={() => onNavigate('discovery-request', { assessment: view.assessmentId, request: request.id })} investigate={() => { setSelected(request.id); setTab('engineering'); }} />)}</section>{view.canCoordinate && <CreateRequest view={view} locked={locked} send={send} onDirtyChange={onDirtyChange} />}</>}
    {tab === 'standards' && <><section className="d-panel"><h2>Propose a shared operating basis</h2><p>These three packages are drafts for review. Record existing requirements and reported practice before proposing an accountable function. Nothing here adopts policy or authorizes collection or migration.</p><Select label="Draft proposal package" value={selected} change={setSelected} disabled={dirty || locked} options={[{ value: '', label: 'Choose a proposal to review' }, ...view.standards.map(item => ({ value: item.id, label: item.title }))]} /></section>{view.standards.filter(item => item.id === selected).map(item => <StandardEditor key={`${item.id}-${item.revision || view.revision}`} item={item} locked={locked || !view.canCoordinate} send={send} onDirtyChange={onDirtyChange} />)}</>}
    {tab === 'engineering' && <><section className="d-panel"><h2>Turn a useful response into a bounded investigation</h2><p>Engineering identifies the product and approved interface, documents limitations, and prepares evidence for independent review. Research readiness is not technical acceptance.</p><p className="d-help">Here, evidence means information supporting an assessment conclusion, with its source, date, scope and limitations recorded. A discovery response identifies a starting point; it does not authorize collection or establish technical behavior.</p><Select label="Investigation or returned request" value={selected} change={setSelected} disabled={dirty || locked} options={[{ value: '', label: 'Choose an investigation or returned request' }, ...view.investigations.map(item => ({ value: item.id, label: `${item.purpose} · ${humanize(item.status)}` })), ...view.requests.filter(item => item.status === 'submitted').map(item => ({ value: item.id, label: `New investigation from: ${item.title}` }))]} />{!view.investigations.length && !view.requests.some(item => item.status === 'submitted') && <p>A useful submitted response—even “I do not know”—provides the handoff context for engineering.</p>}</section>
      {view.canCoordinate && view.requests.filter(item => item.id === selected && item.status === 'submitted').map(request => <CreateInvestigation key={request.id} request={request} view={view} locked={locked} send={send} onDirtyChange={onDirtyChange} />)}
      {view.investigations.filter(item => item.id === selected).map(item => <InvestigationEditor key={`${item.id}-${view.revision}`} item={item} view={view} session={session} locked={locked} send={send} onDirtyChange={onDirtyChange} onNavigate={onNavigate} stageEvidence={stageEvidence} />)}
      <div className="d-lineage"><strong>Where the work goes next</strong><p>Submitted discovery → engineer investigation → staged evidence → independent technical review → admitted assessment evidence → map and report inputs.</p><div className="d-actions"><button className="button secondary" disabled={dirty || locked} onClick={() => onNavigate('assets', { assessment: view.assessmentId })}>Inspect admitted assets</button><button className="button secondary" disabled={dirty || locked} onClick={() => onNavigate('reports', { assessment: view.assessmentId })}>Read report history</button><button className="text-button" disabled={dirty || locked} onClick={() => onNavigate('assessments', { assessment: view.assessmentId, stage: '4' })}>Phase 1 draft and handoff prerequisites →</button></div><p className="d-help">Only admitted technical evidence affects the technical map. Submitted responses remain attributed discovery context. Draft preparation does not bypass gate review.</p></div>
    </>}
  </>;
}

function RequestCard({ request, view, locked, send, open, investigate }: { request: DiscoveryRequest; view: DiscoveryList; locked: boolean; send: Send; open: () => void; investigate: () => void }) {
  const [reason, setReason] = useState(''); const [copied, setCopied] = useState(false);
  const link = `${window.location.origin}${window.location.pathname}#discovery-request?${new URLSearchParams({ assessment: view.assessmentId, request: request.id })}`;
  return <article className="d-request-card"><span className="d-status">{request.status === 'submitted' ? 'Response submitted · coordinator acts next' : 'Draft · respondent can contribute'}</span><h3>{request.title}</h3><p>{request.familyName} · Assigned to {principalLabel(request.assignedTo)} · {request.questions.length} questions</p><div className="d-actions"><button className="button secondary" disabled={locked} onClick={open}>{request.status === 'submitted' ? 'Read submitted response' : 'Open five-question request'}</button>{view.canCoordinate && request.status === 'submitted' && <button className="button primary" disabled={locked} onClick={investigate}>Prepare engineering investigation</button>}</div>{view.canCoordinate && <><label className="d-link-field">Respondent link for {request.title}<input readOnly value={link} /></label><button className="text-button" disabled={locked} onClick={() => void navigator.clipboard?.writeText(link).then(() => setCopied(true)).catch(() => setCopied(false))}>{copied ? 'Link copied' : 'Copy request link'}</button><p className="d-help">Share through an approved channel. The application does not send messages; sign-in and assignment permission still apply.</p>{request.status === 'submitted' && <details><summary>Ask for a revised response</summary><Field label={`Reason to reopen ${request.title}`} value={reason} change={setReason} disabled={locked} /><button className="button secondary" disabled={locked || !reason.trim()} onClick={() => void send('discovery_reopen', request.id, { reason })}>Reopen response</button></details>}</>}</article>;
}
function Recipient({ value, change, disabled }: { value: string; change: (value: string) => void; disabled: boolean }) { return <Select label="Assigned respondent" value={value} change={change} disabled={disabled} options={[{ value: 'synthetic-demo:contributor', label: 'Source contributor 1' }, { value: 'synthetic-demo:contributor-two', label: 'Source contributor 2' }]} />; }
function CreateRequest({ view, locked, send, onDirtyChange }: { view: DiscoveryList; locked: boolean; send: Send; onDirtyChange: (value: boolean) => void }) {
  const [title, setTitle] = useState(''); const [familyId, setFamilyId] = useState(''); const [assignedTo, setAssignedTo] = useState('synthetic-demo:contributor');
  const dirty = !!title || !!familyId || assignedTo !== 'synthetic-demo:contributor';
  useEffect(() => { onDirtyChange(dirty); return () => onDirtyChange(false); }, [dirty, onDirtyChange]);
  return <section className="d-panel d-create"><h2>Assign a short discovery request</h2><p>Choose the software class—not a presumed product or deployment. The recipient can identify systems, refer you elsewhere or report an unknown.</p><Field label="Request title" value={title} change={setTitle} maxLength={256} disabled={locked} /><Select label="Software class / source family" value={familyId} change={setFamilyId} disabled={locked} options={[{ value: '', label: 'Choose the software class to identify' }, ...view.families.map(item => ({ value: item.id, label: item.name }))]} /><Examples values={view.families.find(item => item.id === familyId)?.examples || []} /><Recipient value={assignedTo} change={setAssignedTo} disabled={locked} /><div className="d-actions"><button className="button primary" disabled={locked || !title.trim() || !familyId} onClick={() => void (async () => { if (await send('discovery_create', null, { title, familyId, assignedTo })) { setTitle(''); setFamilyId(''); setAssignedTo('synthetic-demo:contributor'); } })()}>Create five-question request</button>{dirty && <button className="text-button" disabled={locked} onClick={() => { setTitle(''); setFamilyId(''); setAssignedTo('synthetic-demo:contributor'); }}>Discard request setup</button>}</div></section>;
}

function StandardEditor({ item, locked, send, onDirtyChange }: { item: DiscoveryStandard; locked: boolean; send: Send; onDirtyChange: (value: boolean) => void }) {
  const initial = { proposalText: item.proposalText, existingRequirementStatus: item.existingRequirementStatus, existingRequirementRefs: item.existingRequirementRefs.join('\n'), observedPractice: item.observedPractice || '', authorityStatus: item.authorityStatus, proposedAuthority: item.proposedAuthority, conflictReviewStatus: item.conflictReviewStatus, conflictNote: item.conflictNote };
  const [draft, setDraft] = useState(initial); const dirty = JSON.stringify(draft) !== JSON.stringify(initial);
  useEffect(() => { onDirtyChange(dirty); return () => onDirtyChange(false); }, [dirty, onDirtyChange]);
  const update = (key: keyof typeof initial, value: string) => setDraft(current => ({ ...current, [key]: value }));
  return <section className="d-panel"><span className="d-status">DRAFT PROPOSAL · NOT ADOPTED</span><h2>{item.title}</h2><p>{item.purpose}</p><div className="d-standard-text">{item.proposalText}</div><details><summary>Revise draft proposal</summary><Field label="Draft proposal wording" value={draft.proposalText} change={value => update('proposalText', value)} multiline maxLength={16384} disabled={locked} help="Revise the proposed wording for review. Saving creates a draft revision; it does not adopt policy or authorize collection or migration." /></details>{item.publicationRefs?.length ? <details><summary>Publication references and status</summary>{item.publicationRefs.map(ref => <p key={ref.url}>{/^https:\/\//.test(ref.url) ? <a href={ref.url} target="_blank" rel="noreferrer">{ref.title}</a> : ref.title} — {ref.status}</p>)}</details> : null}<h3>Establish the current enterprise basis</h3><Select label="Existing requirement status" value={draft.existingRequirementStatus} change={value => update('existingRequirementStatus', value)} disabled={locked} options={['unassessed', 'reported_existing', 'not_identified', 'conflict_reported'].map(value => ({ value, label: humanize(value) }))} /><Field label="Existing requirement references (one per line)" value={draft.existingRequirementRefs} multiline disabled={locked} change={value => update('existingRequirementRefs', value)} /><Field label="Observed or reported current practice" value={draft.observedPractice} multiline disabled={locked} change={value => update('observedPractice', value)} help="Attribute reported practice; do not present a proposed standard as an existing enterprise requirement." /><Select label="Authority route status" value={draft.authorityStatus} change={value => update('authorityStatus', value)} disabled={locked} options={['unassigned', 'proposed_owner', 'review_requested'].map(value => ({ value, label: humanize(value) }))} /><Field label="Proposed accountable function" value={draft.proposedAuthority} change={value => update('proposedAuthority', value)} disabled={locked} /><Select label="Conflict review status" value={draft.conflictReviewStatus} change={value => update('conflictReviewStatus', value)} disabled={locked} options={['unassessed', 'no_conflict_reported', 'conflict_reported'].map(value => ({ value, label: humanize(value) }))} /><Field label="Conflicts or review questions" value={draft.conflictNote} change={value => update('conflictNote', value)} multiline disabled={locked} /><div className="d-actions"><button className="button primary" disabled={locked || !dirty} onClick={() => void send('discovery_update_standard', item.id, { ...draft, existingRequirementRefs: lines(draft.existingRequirementRefs) })}>Save draft proposal and review notes</button>{dirty && <button className="text-button" disabled={locked} onClick={() => setDraft(initial)}>Discard unsaved proposal and review notes</button>}</div><p className="d-standard-note">Next: the assessment lead routes the proposal to the appropriate policy or architecture function. Recording a proposed authority does not establish its approval.</p></section>;
}

function CreateInvestigation({ request, view, locked, send, onDirtyChange }: { request: DiscoveryRequest; view: DiscoveryList; locked: boolean; send: Send; onDirtyChange: (value: boolean) => void }) {
  const [purpose, setPurpose] = useState(''); const [assignedTo, setAssignedTo] = useState(''); const [products, setProducts] = useState<string[]>([]);
  const dirty = !!purpose || !!assignedTo || products.length > 0;
  useEffect(() => { onDirtyChange(dirty); return () => onDirtyChange(false); }, [dirty, onDirtyChange]);
  return <section className="d-panel"><h2>Investigation from: {request.title}</h2><details><summary>Read the submitted handoff</summary><Readback request={request} answers={request.answers} products={request.productRefs} /></details><Field label="Question this investigation must answer" value={purpose} change={setPurpose} multiline disabled={locked} help="For example: identify the termination product, edition and documented read-only interface for one bounded service cohort." /><Select label="Assigned investigator" value={assignedTo} change={setAssignedTo} disabled={locked} options={[{ value: '', label: 'Choose an investigator' }, ...(view.investigators || []).map(item => ({ value: item.id, label: item.label }))]} />{request.productRefs.length > 0 && <fieldset><legend>Known deployments to investigate (optional)</legend>{request.productRefs.map(item => <label className="d-options" key={item.id}><input type="checkbox" checked={products.includes(item.id)} disabled={locked} onChange={event => setProducts(current => event.target.checked ? [...current, item.id] : current.filter(id => id !== item.id))} />{item.label} · {item.product}</label>)}</fieldset>}<div className="d-actions"><button className="button primary" disabled={locked || !purpose.trim() || !assignedTo} onClick={() => void (async () => { if (await send('discovery_create_investigation', request.id, { purpose, assignedTo, productRefIds: products })) { setPurpose(''); setAssignedTo(''); setProducts([]); } })()}>Create bounded investigation</button>{dirty && <button className="text-button" disabled={locked} onClick={() => { setPurpose(''); setAssignedTo(''); setProducts([]); }}>Discard investigation setup</button>}</div><p className="d-help">Unknown product details can be established by engineering after this handoff. The respondent’s submitted answers remain unchanged.</p></section>;
}

function InvestigationEditor({ item, view, session, locked, send, onDirtyChange, onNavigate, stageEvidence }: { item: DiscoveryInvestigation; view: DiscoveryList; session: Session; locked: boolean; send: Send; onDirtyChange: (value: boolean) => void; onNavigate: Navigate; stageEvidence: (id: string, product: string, source: string, file: File) => Promise<boolean> }) {
  const initial = { status: item.status, researchSummary: item.researchSummary, proposedMethod: item.proposedMethod, documentationRefs: item.documentationRefs.join('\n'), limitation: item.limitation };
  const [draft, setDraft] = useState(initial); const [product, setProduct] = useState({ label: '', product: '', environment: '' });
  const dirtyResearch = JSON.stringify(draft) !== JSON.stringify(initial); const dirtyProduct = Object.values(product).some(Boolean); const dirty = dirtyResearch || dirtyProduct;
  useEffect(() => { onDirtyChange(dirty); return () => onDirtyChange(false); }, [dirty, onDirtyChange]);
  const canEditResearch = item.canEditResearch ?? (view.canCoordinate || view.canResearch && item.assignedTo === `synthetic-demo:${session.role}`);
  const update = (key: keyof typeof initial, value: string) => setDraft(current => ({ ...current, [key]: value }));
  const productRefs = item.productRefs || view.requests.find(request => request.id === item.requestId)?.productRefs.filter(ref => item.productRefIds.includes(ref.id)) || [];
  return <section className="d-panel"><h2>{item.purpose}</h2><p>Assigned investigator: <strong>{principalLabel(item.assignedTo)}</strong> · {humanize(item.status)} (research only)</p><Select label="Research status" value={draft.status} change={value => update('status', value)} disabled={locked || !canEditResearch} options={['planned', 'researching', 'ready_for_review', 'blocked'].map(value => ({ value, label: humanize(value) }))} />{([{ key: 'researchSummary', label: 'Product and interface research' }, { key: 'documentationRefs', label: 'Official documentation references (one per line)' }, { key: 'proposedMethod', label: 'Proposed bounded evidence method' }, { key: 'limitation', label: 'Unknowns, constraints and next decisions' }] as const).map(field => <Field key={field.key} label={field.label} value={draft[field.key]} change={value => update(field.key, value)} multiline disabled={locked || !canEditResearch} />)}<div className="d-actions"><button className="button primary" disabled={locked || !canEditResearch || !dirtyResearch || dirtyProduct} onClick={() => void send('discovery_update_investigation', item.id, { ...draft, documentationRefs: lines(draft.documentationRefs) })}>Save engineering research</button>{dirtyResearch && <button className="text-button" disabled={locked} onClick={() => setDraft(initial)}>Discard research edits</button>}</div>
    <h3>Identified products and deployments</h3>{productRefs.length ? productRefs.map(ref => <p key={ref.id}>{ref.label} · {ref.product} · {ref.environment || 'Environment unspecified'}</p>) : <p>No deployment identified yet. This does not invalidate the respondent’s useful handoff.</p>}
    {view.canCoordinate && <details><summary>Add identified product/deployment</summary><p>Engineering can identify a deployment without reopening the completed respondent task. This creates an investigation record, not a verified asset.</p>{(['label', 'product', 'environment'] as const).map(field => <Field key={field} label={`Identified deployment ${humanize(field).toLowerCase()}`} value={product[field]} change={value => setProduct(current => ({ ...current, [field]: value }))} disabled={locked} maxLength={256} />)}<button className="button secondary" disabled={locked || dirtyResearch || !product.label.trim() || !product.product.trim()} onClick={() => void send('discovery_add_product', item.id, product)}>Add identified deployment</button>{dirtyProduct && <button className="text-button" disabled={locked} onClick={() => setProduct({ label: '', product: '', environment: '' })}>Discard product details</button>}</details>}
    <EvidencePanel item={item} products={productRefs} view={view} locked={locked || dirty} send={send} stageEvidence={stageEvidence} onGates={() => onNavigate('assessments', { assessment: view.assessmentId, stage: '2' })} />
  </section>;
}

function EvidencePanel({ item, products, view, locked, send, stageEvidence, onGates }: { item: DiscoveryInvestigation; products: DiscoveryProduct[]; view: DiscoveryList; locked: boolean; send: Send; stageEvidence: (id: string, product: string, source: string, file: File) => Promise<boolean>; onGates: () => void }) {
  const [productId, setProductId] = useState(''); const [sourceLabel, setSourceLabel] = useState(''); const [file, setFile] = useState<File>();
  const [rationale, setRationale] = useState<Record<string, string>>({});
  const qualifiedFamily = item.familyId === 'traffic-termination';
  const permissions = { ...view, canStageEvidence: item.canStageEvidence ?? view.canStageEvidence, canReviewEvidence: item.canReviewEvidence ?? view.canReviewEvidence, canAdmitEvidence: item.canAdmitEvidence ?? view.canAdmitEvidence, evidenceBlockingReason: item.evidenceBlockingReason || view.evidenceBlockingReason };
  return <section className="d-evidence-review"><h3>Technical evidence and independent review</h3><p>Only the bounded synthetic TLS fixture profile is qualified in this increment. Research notes and returned answers do not become measured cryptography.</p>{!qualifiedFamily && <p className="d-standard-note">Technical evidence admission is not qualified for this source family. Continue documented research; do not substitute a TLS fixture from another family.</p>}
    {qualifiedFamily && <><p className="d-help">Stage → independent reviewer determination → lead admission. Staged records do not populate the map or reports.</p>{!permissions.canStageEvidence && view.canCoordinate && <p>{permissions.evidenceBlockingReason || 'Staging requires the assessment lead and the G00 / P1-G01 evidence boundaries.'} <button className="text-button" disabled={locked} onClick={onGates}>Review evidence-admission gates →</button></p>}{view.canCoordinate && <details><summary>Stage a controlled synthetic TLS fixture</summary><Select label="Evidence subject deployment" value={productId} change={setProductId} disabled={locked || !permissions.canStageEvidence} options={[{ value: '', label: 'Choose an identified deployment' }, ...products.map(ref => ({ value: ref.id, label: ref.label }))]} /><Field label="Source of the staged observation" value={sourceLabel} change={setSourceLabel} disabled={locked || !permissions.canStageEvidence} maxLength={256} help="Name the separate evidence source. The source is not automatically the application being described." /><label className="d-field">Controlled synthetic TLS JSON (maximum 32 KiB)<input type="file" accept=".json" disabled={locked || !permissions.canStageEvidence} onChange={event => setFile(event.target.files?.[0])} /></label><button className="button secondary" disabled={locked || !permissions.canStageEvidence || !productId || !sourceLabel.trim() || !file} onClick={() => file && void stageEvidence(item.id, productId, sourceLabel, file)}>Stage for technical review</button></details>}</>}
    {item.evidenceReviews.map(batch => <article key={batch.batchId}><span className="d-status">{humanize(batch.status)}</span><h4>{batch.productLabel} ← {batch.sourceLabel}</h4><p>{batch.observationCount} observations · staged by {principalLabel(batch.stagedBy)}</p><details><summary>Evidence identity and review basis</summary><p className="record-id">{batch.contentSha256}</p><p>This screen shows deployment/source identity, record count and digest—not full observation contents. The reviewer must separately examine the controlled operator-provided fixture and its limitations before recording a determination.</p></details>{batch.reviewRationale && <p>Reviewer determination: {batch.reviewRationale}</p>}{permissions.canReviewEvidence && qualifiedFamily && ['staged', 'needs_clarification'].includes(batch.status) && <><Field label={`Review rationale for ${batch.productLabel}`} value={rationale[batch.batchId] || ''} change={value => setRationale(current => ({ ...current, [batch.batchId]: value }))} multiline disabled={locked} /><div className="d-actions"><button className="button secondary" disabled={locked || !rationale[batch.batchId]?.trim()} onClick={() => void send('discovery_review_evidence', item.id, { batchId: batch.batchId, determination: 'qualified', rationale: rationale[batch.batchId] })}>Record qualified technical determination</button><button className="button secondary" disabled={locked || !rationale[batch.batchId]?.trim()} onClick={() => void send('discovery_review_evidence', item.id, { batchId: batch.batchId, determination: 'needs_clarification', rationale: rationale[batch.batchId] })}>Request clarification</button></div></>}{batch.status === 'qualified' && <><p>Next: assessment lead admits the reviewed scope if gate prerequisites remain valid.</p>{view.canCoordinate && <button className="button primary" disabled={locked || !permissions.canAdmitEvidence || !qualifiedFamily} onClick={() => void send('discovery_admit_evidence', item.id, { batchId: batch.batchId })}>Admit reviewed evidence to assessment</button>}</>}{batch.status === 'admitted' && <p>Included in the selected assessment’s technical evidence set. New report snapshots can use it; historical accepted reports are unchanged.</p>}</article>)}
  </section>;
}
