// Tab-scoped recorder for the supported browser connection. No standalone
// browser, debugger endpoint, desktop capture, application API or DOM injection.
// Import in the browser tool's Node session, then pass an already-owned Tab.
import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

export const CAPTURE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../artifacts/pqc-enterprise-demo') + path.sep;
const ROOT = CAPTURE_ROOT;
const MAX_BYTES = 512 * 1024 * 1024;
const CAPTURE_SETTINGS = Object.freeze({ format: 'jpeg', quality: 75, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1 });
const PUMP_INTERVAL_MS = 250;
const numericDiagnostic = value => typeof value === 'number' && Number.isFinite(value) ? value : null;
const failureMessage = error => (typeof error?.message === 'string' ? error.message : String(error)).slice(0, 4000);
export function frameTime(metadata, startedAt, receivedAt) {
  // Page.ScreencastFrameMetadata.timestamp is seconds since the Unix epoch.
  // Delivery/ACK time is NOT frame time: one readEvents call can drain a backlog.
  const value = metadata?.timestamp;
  if (typeof value !== 'number' || !Number.isFinite(value)) throw Error('browser_frame_timestamp_required');
  const ms = value * 1000;
  // The first screencast image may be an already-painted surface whose swap
  // predates startScreencast. Display it from capture start without inventing
  // footage before recording began; future or nonpositive times are invalid.
  if (ms <= 0 || ms > receivedAt + 1000) throw Error('browser_frame_timestamp_out_of_range');
  return Math.max(startedAt, ms);
}
async function assertPrivateDirectory(directory) {
  for (let candidate = directory; candidate !== path.dirname(candidate); candidate = path.dirname(candidate)) {
    try { if ((await fs.lstat(candidate)).isSymbolicLink()) throw Error('capture_symlink_not_allowed'); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
}
export class PqcVideoRecorder {
  constructor(tab, directory) {
    const resolved = path.resolve(directory);
    if (!resolved.startsWith(ROOT) || resolved === ROOT.slice(0, -1)) throw Error('isolated_video_directory_required');
    this.tab = tab; this.directory = resolved; this.frames = []; this.markers = [];
    this.running = false; this.cursor = 0; this.startedAt = null; this.bytes = 0;
    this.pumping = null; this.timer = null; this.stopping = false; this.failure = null;
    this.callbackFailure = null; this.checkpointFailure = null;
    this.transportDiagnostics = { readCount: 0, acknowledgedFrames: 0, reorderedBatches: 0, recentBatches: [] };
    this.checkpointSequence = 0; this.active = false;
  }
  async start(title) {
    if (this.running || this.startedAt) throw Error('capture_already_started');
    if (typeof title !== 'string' || !title.trim() || title.length > 160) throw Error('bounded_capture_title_required');
    const origin = new URL(await this.tab.url());
    if (origin.hostname !== '127.0.0.1' || origin.protocol !== 'http:') throw Error('loopback_synthetic_tab_required');
    this.origin = origin.origin;
    await assertPrivateDirectory(this.directory);
    await fs.mkdir(this.directory, { recursive: true, mode: 0o700 });
    if ((await fs.readdir(this.directory)).length) throw Error('empty_capture_directory_required');
    this.cdp = await this.tab.capabilities.get('cdp');
    let events = await this.cdp.readEvents({ methods: ['Page.screencastFrame'], limit: 100 });
    let discardedPages = 0;
    while (events.hasMore) {
      if (++discardedPages > 100) throw Error('old_capture_backlog_limit');
      events = await this.cdp.readEvents({ afterSequence: events.cursor, methods: ['Page.screencastFrame'], limit: 100 });
    }
    this.cursor = events.cursor; this.startedAt = Date.now(); this.title = title;
    // Capture every changed compositor frame: sampling sparse form interactions
    // can omit the only visible change. JPEG compression and nonblocking reads
    // reduce traffic without dropping those low-motion interactions.
    await this.cdp.send('Page.startScreencast', { ...CAPTURE_SETTINGS });
    this.running = true;
    return { title, started: true };
  }
  async during(work) {
    // The supported browser connection is scoped to an active tool call.
    // Never leave a timer making browser requests after that call returns.
    if (!this.running || this.active || typeof work !== 'function') throw Error('active_capture_callback_required');
    this.active = true; this.schedulePump();
    let result, callbackError, callbackFailed = false, captureError;
    try { result = await work(); }
    catch (error) {
      callbackFailed = true; callbackError = error;
      // Preserve the browser-action blocker independently of frame transport
      // failure. Store bounded message text only, not stacks or arbitrary data.
      this.callbackFailure = failureMessage(error);
    }
    this.active = false; clearTimeout(this.timer);
    try {
      if (this.pumping) await this.pumping;
      if (this.failure) throw Error(this.failure);
      if (!callbackFailed) { await this.pump(); await this.checkpoint(); }
    } catch (error) {
      captureError = error; this.failure ||= failureMessage(error);
    }
    if (callbackFailed || captureError || this.failure) {
      // The assembler already rejects every nonempty failure. An action error
      // therefore cannot leave an apparently valid, completed partial capture.
      this.failure ||= 'capture_browser_action_failed';
      try { await this.stop(); }
      catch (error) { captureError ||= error; }
      if (callbackFailed) throw callbackError;
      throw captureError || Error(this.failure);
    }
    return result;
  }
  schedulePump() {
    if (!this.running || this.stopping || !this.active) return;
    this.timer = setTimeout(async () => {
      try { await this.pump(); }
      catch (error) {
        this.failure ||= failureMessage(error); this.running = false;
        try { await this.cdp.send('Page.stopScreencast'); } catch { /* Preserve original failure. */ }
        try { await this.checkpoint(); } catch { this.checkpointFailure = 'capture_checkpoint_failed'; }
        return;
      }
      this.schedulePump();
    }, PUMP_INTERVAL_MS);
  }
  async pump() {
    if (this.failure) throw Error(this.failure);
    if (!this.running) return { frames: this.frames.length };
    if (this.pumping) return this.pumping;
    this.pumping = this.drain();
    try { return await this.pumping; } finally { this.pumping = null; }
  }
  async drain() {
    if (new URL(await this.tab.url()).origin !== this.origin) throw Error('capture_left_approved_loopback_origin');
    if (Date.now() - this.startedAt > 45 * 60 * 1000) throw Error('capture_duration_limit');
    let pages = 0;
    do {
      const requestedAtMs = Date.now();
      // Never long-poll the shared browser connection while a UI command may
      // need it. The next active-call timer handles an empty batch.
      const batch = await this.cdp.readEvents({ afterSequence: this.cursor, methods: ['Page.screencastFrame'], limit: 100, timeoutMs: 0 });
      if (!Array.isArray(batch.events) || batch.events.length > 100) throw Error('capture_event_batch_limit');
      const diagnostic = {
        requestedAtMs, readDurationMs: Date.now() - requestedAtMs,
        afterSequence: numericDiagnostic(this.cursor), cursor: numericDiagnostic(batch.cursor),
        eventCount: batch.events.length, hasMore: batch.hasMore === true, truncated: batch.truncated === true,
        firstSequence: numericDiagnostic(batch.events[0]?.sequence),
        lastSequence: numericDiagnostic(batch.events.at(-1)?.sequence),
        savedFramesBefore: this.frames.length, acknowledgedFrames: 0, ackDurationMs: 0,
        reordered: false,
      };
      this.transportDiagnostics.readCount++;
      this.transportDiagnostics.recentBatches.push(diagnostic);
      if (this.transportDiagnostics.recentBatches.length > 24) this.transportDiagnostics.recentBatches.shift();
      if (batch.truncated) throw Error('capture_events_truncated');
      const batchReceivedAtMs = Date.now();
      // Chrome's actual recorded revision submits JPEG encoding work to the
      // thread pool and emits each completed result; completion/event order is
      // not necessarily frame creation order. See SendScreencastFrame and
      // ScreencastFrameEncoded in the exact Chromium source:
      // https://raw.githubusercontent.com/chromium/chromium/8f5d36bc16f57115aeeff34baf4ad6aa964d509c/content/browser/devtools/protocol/page_handler.cc
      // Reorder only this complete, bounded batch by ORIGINAL source times.
      // A frame crossing the prior committed batch watermark still fails.
      const arrivals = batch.events.map((event, batchArrivalIndex) => ({ event, batchArrivalIndex }))
        .filter(({ event }) => event.params?.data)
        .map(item => ({ ...item, capturedAtMs: frameTime(item.event.params.metadata, this.startedAt, batchReceivedAtMs) }));
      const ordered = [...arrivals].sort((left, right) =>
        left.event.params.metadata.timestamp - right.event.params.metadata.timestamp || left.batchArrivalIndex - right.batchArrivalIndex);
      diagnostic.reordered = ordered.some((item, index) => item.batchArrivalIndex !== arrivals[index].batchArrivalIndex);
      if (diagnostic.reordered) {
        this.transportDiagnostics.reorderedBatches++;
        diagnostic.arrivalOrder = arrivals.map(({ event, batchArrivalIndex }) => ({
          eventSequence: numericDiagnostic(event.sequence), batchArrivalIndex, sourceTimestampSeconds: event.params.metadata.timestamp,
        }));
        diagnostic.presentationOrder = ordered.map(({ batchArrivalIndex }) => batchArrivalIndex);
      }
      // Equal effective timestamps cannot order two distinct captured images
      // or assign both positive display durations without inventing time.
      // Retain the diagnostic but fail closed; do not drop/deduplicate either.
      const previousBatchTime = this.frames.at(-1)?.capturedAtMs;
      if (ordered.some((item, index) => item.capturedAtMs === (index ? ordered[index - 1].capturedAtMs : previousBatchTime))) {
        this.transportDiagnostics.ambiguousTimestamp = { batchCursor: numericDiagnostic(batch.cursor), eventCount: ordered.length };
        throw Error('capture_frame_timestamp_ambiguous');
      }
      for (const { event, batchArrivalIndex, capturedAtMs } of ordered) {
        if (this.frames.length >= 90000) throw Error('capture_frame_limit');
        const bytes = Buffer.from(event.params.data, 'base64');
        if (bytes.length < 4 || bytes.length > 4 * 1024 * 1024 || bytes[0] !== 0xff || bytes[1] !== 0xd8) throw Error('capture_jpeg_frame_required');
        if (this.bytes + bytes.length > MAX_BYTES) throw Error('capture_storage_limit');
        const receivedAtMs = Date.now();
        if (this.frames.length && capturedAtMs < this.frames.at(-1).capturedAtMs) {
          // Retain only numeric transport facts for the first rejected frame.
          // A timestamp preceding the previous complete batch cannot be
          // repaired by this bounded buffer. Never change it or resort history.
          const previous = this.frames.at(-1);
          this.transportDiagnostics.frameOrderFailure = {
            eventSequence: numericDiagnostic(event.sequence),
            previousSequence: numericDiagnostic(previous.eventSequence),
            sourceTimestampSeconds: numericDiagnostic(event.params.metadata?.timestamp),
            capturedAtMs, previousCapturedAtMs: previous.capturedAtMs,
            backwardsByMs: previous.capturedAtMs - capturedAtMs,
            receivedAtMs, savedFrames: this.frames.length,
            afterSequence: numericDiagnostic(this.cursor), cursor: numericDiagnostic(batch.cursor),
          };
          throw Error('capture_frame_order_invalid');
        }
        const file = `${String(this.frames.length).padStart(6, '0')}.jpg`;
        await fs.writeFile(path.join(this.directory, file), bytes, { flag: 'wx', mode: 0o600 });
        this.bytes += bytes.length;
        this.frames.push({ file, capturedAtMs, receivedAtMs, batchReceivedAtMs, batchArrivalIndex, batchCursor: numericDiagnostic(batch.cursor), eventSequence: numericDiagnostic(event.sequence), timestampSource: 'browser_frame_metadata', sha256: createHash('sha256').update(bytes).digest('hex'), metadata: event.params.metadata });
        const ackStartedAt = Date.now();
        await this.cdp.send('Page.screencastFrameAck', { sessionId: event.params.sessionId });
        diagnostic.ackDurationMs += Date.now() - ackStartedAt;
        diagnostic.acknowledgedFrames++;
        this.transportDiagnostics.acknowledgedFrames++;
      }
      this.cursor = batch.cursor;
      if (!batch.hasMore) break;
      if (pages === 9) throw Error('capture_backlog_limit');
    } while (++pages < 10);
    return { frames: this.frames.length };
  }
  async mark({ chapter, task, why, next, effect, outcome = '', compressed = false, minimumDwellSeconds = 8, emphasis, targetDurationSeconds }) {
    if (!this.running) throw Error('capture_not_started');
    const atMs = Date.now();
    for (const value of [chapter, task, why, next, effect, outcome]) if (typeof value !== 'string' || value.length > 1000) throw Error('bounded_annotation_text_required');
    if (!Number.isFinite(minimumDwellSeconds) || minimumDwellSeconds < 8 || minimumDwellSeconds > 120) throw Error('bounded_reading_dwell_required');
    if (emphasis !== undefined && emphasis !== 'report') throw Error('known_annotation_emphasis_required');
    if (targetDurationSeconds !== undefined && (!compressed || !Number.isFinite(targetDurationSeconds) || targetDurationSeconds < 8 || targetDurationSeconds > 2700)) throw Error('bounded_explicit_compression_required');
    await this.pump();
    // Human-readable annotation only. It cannot call or mutate the application.
    const oneLine = value => value.replace(/\s+/g, ' ').trim();
    this.markers.push({ atMs, chapter: oneLine(chapter), task: oneLine(task), why: oneLine(why), next: oneLine(next), effect: oneLine(effect), outcome: oneLine(outcome), compressed: compressed === true, minimumDwellSeconds, ...(emphasis ? {emphasis} : {}), ...(targetDurationSeconds !== undefined ? {targetDurationSeconds} : {}) });
    await this.checkpoint();
    return { marker: this.markers.length, frames: this.frames.length };
  }
  async checkpoint() {
    // A timer failure and foreground stop can overlap. Serialize publication so
    // an earlier incomplete checkpoint can never replace the terminal record.
    this.checkpointChain = (this.checkpointChain || Promise.resolve()).catch(() => {}).then(() => this.writeCheckpoint());
    return this.checkpointChain;
  }
  async writeCheckpoint() {
    const temporary = path.join(this.directory, `capture-${++this.checkpointSequence}.tmp`);
    await fs.writeFile(temporary, JSON.stringify({
      schemaVersion: 'pqc.browser-capture.v1', synthetic: true, source: 'actual_tab_screencast',
      title: this.title, startedAtMs: this.startedAt, endedAtMs: this.endedAt || null,
      frames: this.frames, markers: this.markers, bytes: this.bytes, failure: this.failure,
      callbackFailure: this.callbackFailure, checkpointFailure: this.checkpointFailure,
      captureSettings: CAPTURE_SETTINGS, pumpIntervalMs: PUMP_INTERVAL_MS,
      transportDiagnostics: this.transportDiagnostics,
      boundary: 'Scenario role decisions only; not owner validation or enterprise acceptance.'
    }, null, 2), { mode: 0o600, flag: 'wx' });
    await fs.rename(temporary, path.join(this.directory, 'capture.json'));
  }
  async stop() {
    this.stopping = true; clearTimeout(this.timer);
    try {
      if (this.running) { await this.pump(); await this.cdp.send('Page.stopScreencast'); await this.pump(); }
    } catch (error) { this.failure ||= failureMessage(error); }
    finally {
      try { if (this.cdp) await this.cdp.send('Page.stopScreencast'); } catch { this.failure ||= 'capture_stop_unconfirmed'; }
      this.running = false; this.endedAt = Date.now();
    }
    if (!this.frames.length) this.failure ||= 'capture_no_frames';
    await this.checkpoint();
    if (this.failure) throw Error(this.failure);
    return { frames: this.frames.length, markers: this.markers.length, seconds: (this.endedAt - this.startedAt) / 1000 };
  }
}
