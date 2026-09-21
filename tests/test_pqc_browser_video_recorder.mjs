// Unit tests only: the fake CDP frames are never exported as demonstration video.
import assert from 'node:assert/strict';
import { test, before } from 'node:test';
import fs from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { PqcVideoRecorder, frameTime, CAPTURE_ROOT } from '../scripts/pqc_browser_video_recorder.mjs';

before(async () => { await fs.mkdir(CAPTURE_ROOT, {recursive:true, mode:0o700}); });

test('preserves frame creation time rather than batched delivery time', () => {
  const start = 1800000000000;
  assert.equal(frameTime({ timestamp: (start + 100) / 1000 }, start, start + 700), start + 100);
  assert.throws(() => frameTime({}, start, start + 700), /timestamp_required/);
  assert.throws(() => frameTime({ timestamp: Infinity }, start, start + 700), /timestamp_required/);
  assert.equal(frameTime({ timestamp: (start - 5000) / 1000 }, start, start + 700), start);
  assert.throws(() => frameTime({ timestamp: 0 }, start, start + 700), /out_of_range/);
});

test('refuses output outside the isolated artifact collection', () => {
  assert.throws(() => new PqcVideoRecorder({}, '/tmp/pqc-recording'), /isolated_video_directory_required/);
});

test('drains frames only inside an active browser call and preserves reading budgets', async () => {
  const root = CAPTURE_ROOT;
  const directory = await fs.mkdtemp(`${root}recorder-unit-test-`);
  let reads = 0, acknowledgements = 0, recorder, captureSettings;
  const readRequests = [];
  const cdp = {
    readEvents: async options => {
      readRequests.push(options);
      reads++;
      const events = reads === 2 ? Array.from({ length: 8 }, (_, i) => ({ params: { data: Buffer.from([0xff, 0xd8, i, 0xff, 0xd9]).toString('base64'), sessionId: i, metadata: { timestamp: (recorder.startedAt + i) / 1000 } } })) : [];
      return { events, cursor: reads, hasMore: false, truncated: false };
    },
    send: async (method, params) => {
      if (method === 'Page.screencastFrameAck') acknowledgements++;
      if (method === 'Page.startScreencast') captureSettings = params;
    },
  };
  const tab = { url: async () => 'http://127.0.0.1:18477/#assessment-work', capabilities: { get: async () => cdp } };
  try {
    recorder = new PqcVideoRecorder(tab, directory);
    await recorder.start('Mock recorder unit test — not video evidence');
    const beforeIdle = reads;
    await new Promise(resolve => setTimeout(resolve, 80));
    assert.equal(reads, beforeIdle, 'No browser requests may outlive an active call');
    await recorder.during(async () => {
      const cue = { chapter: 'Unit test', task: 'Read', why: 'Verify', next: 'Reviewer', effect: 'None' };
      await assert.rejects(recorder.mark({ ...cue, minimumDwellSeconds: 2 }), /bounded_reading_dwell_required/);
      await assert.rejects(recorder.mark({ ...cue, emphasis: 'unknown' }), /known_annotation_emphasis_required/);
      await assert.rejects(recorder.mark({ ...cue, targetDurationSeconds: 20 }), /bounded_explicit_compression_required/);
      await recorder.mark({ chapter: 'Unit test', task: 'Read', why: 'Verify', next: 'Reviewer', effect: 'None', minimumDwellSeconds: 30, emphasis: 'report' });
      await new Promise(resolve => setTimeout(resolve, 150));
    });
    const afterActive = reads;
    await new Promise(resolve => setTimeout(resolve, 80));
    assert.equal(reads, afterActive, 'No background requests after callback returns');
    assert.equal(acknowledgements, 8);
    assert.equal(recorder.frames.length, 8);
    assert.ok(recorder.frames.every(frame => frame.sha256.length === 64));
    const stopped = await recorder.stop();
    assert.equal(stopped.frames, 8);
    const saved = JSON.parse(await fs.readFile(`${directory}/capture.json`, 'utf8'));
    assert.equal(saved.failure, null);
    assert.deepEqual(captureSettings, { format: 'jpeg', quality: 75, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1 });
    assert.deepEqual(saved.captureSettings, captureSettings);
    assert.equal(saved.pumpIntervalMs, 250);
    assert.ok(readRequests.slice(1).every(request => request.timeoutMs === 0), 'All capture reads are nonblocking');
    assert.equal(saved.transportDiagnostics.acknowledgedFrames, 8);
    assert.ok(saved.endedAtMs >= saved.frames.at(-1).capturedAtMs);
    assert.ok(saved.frames[0].receivedAtMs > saved.frames[0].capturedAtMs);
    assert.equal(saved.markers[0].minimumDwellSeconds, 30);
    assert.equal(saved.markers[0].emphasis, 'report');
  } finally {
    if (recorder?.running) await recorder.stop();
    // This exact private directory was created by this test above.
    await fs.rm(directory, { recursive: true });
  }
});

async function failedCaptureTest(run, mode = 'normal') {
  const root = CAPTURE_ROOT;
  const directory = await fs.mkdtemp(`${root}recorder-error-unit-test-`);
  let reads = 0, stops = 0, recorder, origin = 'http://127.0.0.1:18477/#assessment-work';
  let notifyStop;
  const stopped = new Promise(resolve => { notifyStop = resolve; });
  const cdp = {
    readEvents: async () => {
      reads++;
      const truncated = mode === 'truncated' && reads > 1;
      const crossBatch = mode === 'cross-batch-order' && (reads === 2 || reads === 3);
      const events = (reads === 2 || crossBatch) && !truncated ? Array.from({ length: crossBatch ? 1 : 8 }, (_, i) => ({ sequence: crossBatch ? 98 + reads : 100 + i, params: {
        data: Buffer.from([0xff, 0xd8, i, 0xff, 0xd9]).toString('base64'), sessionId: i,
        metadata: { timestamp: (recorder.startedAt + (crossBatch ? (reads === 2 ? 40 : 20) : i)) / 1000 },
      } })) : [];
      return { events, cursor: reads, hasMore: false, truncated };
    },
    send: async method => { if (method === 'Page.stopScreencast') { stops++; notifyStop(); } },
  };
  const tab = { url: async () => origin, capabilities: { get: async () => cdp } };
  try {
    recorder = new PqcVideoRecorder(tab, directory);
    await recorder.start('Mock recorder error test — never video evidence');
    await run({ recorder, stopped, leaveOrigin: () => { origin = 'https://example.invalid/'; } });
    const saved = JSON.parse(await fs.readFile(`${directory}/capture.json`, 'utf8'));
    assert.equal(recorder.running, false);
    assert.equal(recorder.active, false);
    assert.ok(stops > 0, 'Invalid capture must be explicitly stopped');
    assert.ok(saved.endedAtMs);
    assert.ok(saved.failure, 'Assembler rejection flag must remain nonempty even with valid frames');
    const afterStop = reads;
    await new Promise(resolve => setTimeout(resolve, 80));
    assert.equal(reads, afterStop, 'Invalid capture cannot keep making browser requests');
    return saved;
  } finally {
    if (recorder?.running) { try { await recorder.stop(); } catch { /* Expected invalid test capture. */ } }
    await fs.rm(directory, { recursive: true });
  }
}

test('callback failure is rethrown unchanged, separately recorded, and invalidates otherwise valid frames', async () => {
  const blocker = Error('Chrome extension UI is open; close it before continuing.');
  const saved = await failedCaptureTest(async ({ recorder }) => {
    await assert.rejects(recorder.during(async () => {
      await recorder.pump();
      throw blocker;
    }), error => error === blocker);
  });
  assert.equal(saved.frames.length, 8);
  assert.equal(saved.callbackFailure, blocker.message);
  assert.equal(saved.failure, 'capture_browser_action_failed');
});

test('truncated pump cannot mask the original browser callback blocker', async () => {
  const blocker = Error('The Chrome extension popup must be dismissed by the user.');
  const saved = await failedCaptureTest(async ({ recorder, stopped }) => {
    await assert.rejects(recorder.during(async () => {
      await stopped; // Let the active-call timer observe the truncated event batch.
      throw blocker;
    }), error => error === blocker);
  }, 'truncated');
  assert.equal(saved.failure, 'capture_events_truncated');
  assert.equal(saved.callbackFailure, blocker.message);
  const batch = saved.transportDiagnostics.recentBatches.at(-1);
  assert.equal(batch.truncated, true);
  assert.equal(batch.afterSequence, 1);
  assert.equal(batch.cursor, 2);
  assert.equal(batch.savedFramesBefore, 0);
  assert.equal(batch.acknowledgedFrames, 0);
});

test('final drain truncation after successful callback still stops and rejects the capture', async () => {
  const saved = await failedCaptureTest(async ({ recorder }) => {
    await assert.rejects(recorder.during(async () => 'action succeeded'), /capture_events_truncated/);
  }, 'truncated');
  assert.equal(saved.failure, 'capture_events_truncated');
  assert.equal(saved.callbackFailure, null);
});

test('origin safeguard still rejects and stops a capture after the callback changes origin', async () => {
  const saved = await failedCaptureTest(async ({ recorder, leaveOrigin }) => {
    await assert.rejects(recorder.during(async () => { leaveOrigin(); }), /capture_left_approved_loopback_origin/);
  });
  assert.equal(saved.failure, 'capture_left_approved_loopback_origin');
  assert.equal(saved.callbackFailure, null);
});

test('a frame preceding the prior completed batch remains rejected with timestamp diagnostics', async () => {
  const saved = await failedCaptureTest(async ({ recorder }) => {
    await assert.rejects(recorder.during(async () => {
      await recorder.pump();
      return 'UI action completed';
    }), /capture_frame_order_invalid/);
  }, 'cross-batch-order');
  assert.equal(saved.failure, 'capture_frame_order_invalid');
  assert.equal(saved.callbackFailure, null);
  assert.equal(saved.frames.length, 1, 'Rejected frame must not be recorded or reordered');
  assert.equal(saved.transportDiagnostics.acknowledgedFrames, 1);
  const failure = saved.transportDiagnostics.frameOrderFailure;
  assert.equal(failure.eventSequence, 101);
  assert.equal(failure.previousSequence, 100);
  assert.equal(failure.previousCapturedAtMs, saved.startedAtMs + 40);
  assert.equal(failure.capturedAtMs, saved.startedAtMs + 20);
  assert.equal(failure.backwardsByMs, 20);
  assert.equal(failure.savedFrames, 1);
  assert.ok(Object.values(failure).every(value => typeof value === 'number' && Number.isFinite(value)));
});

test('active polling is bounded and diagnostics omit event payloads', async () => {
  const root = CAPTURE_ROOT;
  const directory = await fs.mkdtemp(`${root}recorder-poll-unit-test-`);
  let reads = 0, recorder;
  const cdp = {
    readEvents: async () => ({ events: [], cursor: ++reads, hasMore: false, truncated: false, privatePayload: 'DO_NOT_LOG' }),
    send: async () => {},
  };
  const tab = { url: async () => 'http://127.0.0.1:18477/', capabilities: { get: async () => cdp } };
  try {
    recorder = new PqcVideoRecorder(tab, directory);
    await recorder.start('Mock transport diagnostics — never video evidence');
    await recorder.during(async () => {
      await new Promise(resolve => setTimeout(resolve, 100));
      assert.equal(reads, 1, 'The timer must not poll at the previous 50ms cadence');
      for (let index = 0; index < 30; index++) await recorder.pump();
    });
    await assert.rejects(recorder.stop(), /capture_no_frames/);
    const text = await fs.readFile(`${directory}/capture.json`, 'utf8');
    const saved = JSON.parse(text);
    assert.equal(saved.failure, 'capture_no_frames');
    assert.equal(saved.frames.length, 0);
    assert.ok(saved.endedAtMs);
    assert.equal(recorder.running, false);
    assert.equal(saved.transportDiagnostics.recentBatches.length, 24);
    assert.ok(saved.transportDiagnostics.readCount >= 30);
    assert.equal(text.includes('DO_NOT_LOG'), false);
    assert.ok(saved.transportDiagnostics.recentBatches.every(batch => batch.readDurationMs >= 0));
  } finally {
    if (recorder?.running) await recorder.stop();
    await fs.rm(directory, { recursive: true });
  }
});

async function batchOrderingTest(offsets, run) {
  const root = CAPTURE_ROOT;
  const directory = await fs.mkdtemp(`${root}recorder-ordering-unit-test-`);
  let reads = 0, recorder;
  const acknowledged = [];
  const images = offsets.map((_, i) => Buffer.from([0xff, 0xd8, i, 0xff, 0xd9]));
  const cdp = {
    readEvents: async () => ({
      cursor: ++reads, hasMore: false, truncated: false,
      events: reads === 2 ? offsets.map((offset, index) => ({
        sequence: 100 + index,
        params: { data: images[index].toString('base64'), sessionId: index, metadata: { timestamp: (recorder.startedAt + offset) / 1000 } },
      })) : [],
    }),
    send: async (method, params) => { if (method === 'Page.screencastFrameAck') acknowledged.push(params.sessionId); },
  };
  const tab = { url: async () => 'http://127.0.0.1:18477/', capabilities: { get: async () => cdp } };
  try {
    recorder = new PqcVideoRecorder(tab, directory);
    await recorder.start('Mock batch ordering — never video evidence');
    await run({ recorder, directory, acknowledged, images });
  } finally {
    if (recorder?.running) { try { await recorder.stop(); } catch { /* Preserve the expected invalid test result. */ } }
    await fs.rm(directory, { recursive: true });
  }
}

test('complete batch is ordered by original source times while retaining arrival order, all frames and hashes', async () => {
  await batchOrderingTest([10, 30, 20], async ({ recorder, directory, acknowledged, images }) => {
    await recorder.during(async () => {
      await recorder.pump();
      await new Promise(resolve => setTimeout(resolve, 40));
    });
    await recorder.stop();
    const saved = JSON.parse(await fs.readFile(`${directory}/capture.json`, 'utf8'));
    assert.equal(saved.failure, null);
    assert.equal(saved.frames.length, 3);
    assert.deepEqual(acknowledged, [0, 2, 1]);
    assert.deepEqual(saved.frames.map(frame => frame.eventSequence), [100, 102, 101]);
    assert.deepEqual(saved.frames.map(frame => frame.batchArrivalIndex), [0, 2, 1]);
    assert.deepEqual(saved.frames.map(frame => frame.capturedAtMs), [10, 20, 30].map(offset => saved.startedAtMs + offset));
    for (const frame of saved.frames) {
      assert.equal(frame.metadata.timestamp, (saved.startedAtMs + [10, 30, 20][frame.batchArrivalIndex]) / 1000);
      const bytes = await fs.readFile(`${directory}/${frame.file}`);
      assert.deepEqual(bytes, images[frame.batchArrivalIndex]);
      assert.equal(frame.sha256, createHash('sha256').update(bytes).digest('hex'));
    }
    assert.equal(saved.transportDiagnostics.reorderedBatches, 1);
    const batch = saved.transportDiagnostics.recentBatches.find(item => item.reordered);
    assert.deepEqual(batch.arrivalOrder.map(item => item.eventSequence), [100, 101, 102]);
    assert.deepEqual(batch.presentationOrder, [0, 2, 1]);
  });
});

test('equal source timestamps fail without inventing times or discarding one of the images', async () => {
  await batchOrderingTest([10, 10], async ({ recorder, directory, acknowledged }) => {
    await assert.rejects(recorder.during(async () => 'UI action completed'), /capture_frame_timestamp_ambiguous/);
    const saved = JSON.parse(await fs.readFile(`${directory}/capture.json`, 'utf8'));
    assert.equal(saved.failure, 'capture_frame_timestamp_ambiguous');
    assert.equal(saved.frames.length, 0, 'Ambiguous batch is not silently deduplicated or partially admitted');
    assert.deepEqual(acknowledged, []);
    assert.equal(saved.transportDiagnostics.ambiguousTimestamp.eventCount, 2);
    assert.equal(recorder.running, false);
  });
});
