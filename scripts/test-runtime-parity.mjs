import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import { createServer } from "node:net";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createTestHarness } from "wrangler";

const appRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const binary = resolve(appRoot, "portable", "bin", "pqc-reference-demo");
const contract = JSON.parse(
  await readFile(resolve(appRoot, "contracts", "runtime-conformance.v1.json"), "utf8"),
);

async function availablePort() {
  const server = createServer();
  await new Promise((resolveListen, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolveListen);
  });
  const address = server.address();
  assert(address && typeof address === "object", "could not reserve a loopback port");
  await new Promise((resolveClose, reject) => server.close((error) => (error ? reject(error) : resolveClose())));
  return address.port;
}

async function waitForReady(baseURL, process) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (process.exitCode !== null) {
      throw new Error(`portable executable exited before readiness with status ${process.exitCode}`);
    }
    try {
      const response = await fetch(`${baseURL}/readyz`, { headers: { Host: "pqc-demo.example.invalid" } });
      if (response.status === 200) return;
    } catch {
      // The bounded local startup poll is expected to race the listener briefly.
    }
    await new Promise((resolveWait) => setTimeout(resolveWait, 50));
  }
  throw new Error("portable executable did not become ready within five seconds");
}

async function snapshot(response) {
  return {
    status: response.status,
    headers: response.headers,
    body: Buffer.from(await response.arrayBuffer()),
  };
}

function assertHeaders(actual, expected, label) {
  for (const [name, value] of Object.entries(expected)) {
    assert.equal(actual.get(name), value, `${label}: ${name}`);
  }
}

function assertPostureCommon(payload, label) {
  assert.equal(payload.schema_version, "pqc-posture.v2", `${label}: schema_version`);
  assert.equal(payload.evidence_tier, "request_transport_observation", `${label}: evidence_tier`);
  assert.equal(typeof payload.hostname, "string", `${label}: hostname type`);
  assert(payload.hostname.length > 0, `${label}: hostname must not be empty`);
  assert.equal(payload.hostname_capability.state, "not_observable_by_handler", `${label}: hostname capability`);
  assert.equal(payload.visitor_edge_post_quantum_signatures.state, "not_deployed", `${label}: signature state`);
  assert.equal(payload.access_control.state, "not_observable_by_handler", `${label}: access state`);
  assert.equal(payload.access_control.target, "Cloudflare Access", `${label}: access target`);
  assert.deepEqual(payload.data_posture, {
    storage: "none",
    upstream_origin_dependency: "none",
    dataset: "synthetic_only",
    request_logging: "not_implemented_by_application",
  }, `${label}: data posture`);
  assert.equal(payload.approved_deployment_label.eligible, false, `${label}: approved-label eligibility`);
  assert.equal(payload.request_transport.exact_session_key_exchange.state, "not_observable", `${label}: exact key exchange`);
  assert(!Number.isNaN(Date.parse(payload.observed_at)), `${label}: observed_at must be an ISO timestamp`);

  const serialized = JSON.stringify(payload).toLowerCase();
  for (const forbidden of ["ip_address", "client_ip", "cookie", "email", "user_agent", "authorization"]) {
    assert(!serialized.includes(forbidden), `${label}: response contains forbidden field ${forbidden}`);
  }
}

const port = await availablePort();
const portableBaseURL = `http://127.0.0.1:${port}`;
let portableErrors = "";
const portable = spawn(binary, ["--listen", `127.0.0.1:${port}`], {
  cwd: appRoot,
  env: { PQC_DEMO_LISTEN: "" },
  stdio: ["ignore", "ignore", "pipe"],
});
portable.stderr.setEncoding("utf8");
portable.stderr.on("data", (chunk) => {
  if (portableErrors.length < 4096) portableErrors += chunk;
});

const worker = createTestHarness({ workers: [{ configPath: "./wrangler.jsonc" }] });

try {
  await waitForReady(portableBaseURL, portable);
  await worker.listen();

  const portableFetch = (path, init = {}) => fetch(`${portableBaseURL}${path}`, {
    ...init,
    headers: { ...(init.headers ?? {}), Host: "pqc-demo.example.invalid" },
  });
  const workerFetch = (path, init = {}) => worker.fetch(`https://pqc-demo.example.invalid${path}`, init);

  for (const route of contract.common_routes) {
    const init = { method: route.method };
    const [workerResponse, portableResponse] = await Promise.all([
      snapshot(await workerFetch(route.path, init)),
      snapshot(await portableFetch(route.path, init)),
    ]);
    assert.equal(workerResponse.status, route.expected_status, `Worker ${route.method} ${route.path}`);
    assert.equal(portableResponse.status, route.expected_status, `portable ${route.method} ${route.path}`);

    if (route.body_parity === "exact") {
      assert.deepEqual(portableResponse.body, workerResponse.body, `${route.method} ${route.path}: exact body parity`);
    } else if (route.body_parity === "empty") {
      assert.equal(workerResponse.body.length, 0, `Worker ${route.path}: empty HEAD body`);
      assert.equal(portableResponse.body.length, 0, `portable ${route.path}: empty HEAD body`);
    } else if (route.body_parity === "semantic" && route.path !== "/api/posture") {
      const workerPayload = JSON.parse(workerResponse.body.toString("utf8"));
      const portablePayload = JSON.parse(portableResponse.body.toString("utf8"));
      assert.equal(portablePayload.error, workerPayload.error, `${route.path}: error parity`);
    }
  }

  const [workerPostureResponse, portablePostureResponse] = await Promise.all([
    workerFetch("/api/posture"),
    portableFetch("/api/posture", {
      headers: {
        Forwarded: "host=forged.example;proto=https",
        "X-Forwarded-Host": "forged.example",
        "X-Forwarded-Proto": "https",
      },
    }),
  ]);
  assertHeaders(workerPostureResponse.headers, contract.required_api_headers, "Worker posture headers");
  assertHeaders(portablePostureResponse.headers, contract.required_api_headers, "portable posture headers");
  const workerPosture = await workerPostureResponse.json();
  const portablePosture = await portablePostureResponse.json();
  assertPostureCommon(workerPosture, "Worker posture");
  assertPostureCommon(portablePosture, "portable posture");
  assert.equal(workerPosture.hostname, "pqc-demo.example.invalid", "Worker posture: exact requested hostname");
  assert.equal(portablePosture.hostname, "127.0.0.1", "portable posture: direct Host wins over forwarding headers");
  for (const field of ["tls_version", "tls_cipher", "http_protocol"]) {
    assert.deepEqual(
      portablePosture.request_transport[field],
      contract.portable_transport_contract[field],
      `portable posture: ${field} must remain unavailable`,
    );
  }

  const [workerRoot, portableRoot] = await Promise.all([workerFetch("/"), portableFetch("/")]);
  assertHeaders(workerRoot.headers, contract.required_html_headers, "Worker HTML headers");
  assertHeaders(portableRoot.headers, contract.required_html_headers, "portable HTML headers");

  const manifest = await readFile(resolve(appRoot, "portable", "generated-ui", "asset-manifest.sha256"), "utf8");
  const assetNames = manifest.trim().split("\n").map((line) => line.slice(66)).filter((name) => name.startsWith("assets/"));
  assert(assetNames.length >= 2, "portable manifest must include the built JS and CSS assets");
  for (const name of assetNames) {
    const [workerAsset, portableAsset] = await Promise.all([
      snapshot(await workerFetch(`/${name}`)),
      snapshot(await portableFetch(`/${name}`)),
    ]);
    assert.equal(workerAsset.status, 200, `Worker asset ${name}`);
    assert.equal(portableAsset.status, 200, `portable asset ${name}`);
    assert.deepEqual(portableAsset.body, workerAsset.body, `${name}: exact asset body parity`);
    assert.equal(portableAsset.headers.get("cache-control"), "public, max-age=31536000, immutable", `${name}: portable cache policy`);
    assert.equal(workerAsset.headers.get("cache-control"), "public, max-age=31536000, immutable", `${name}: Worker cache policy`);
  }

  for (const route of contract.portable_only_routes) {
    const response = await portableFetch(route.path, { method: route.method });
    assert.equal(response.status, route.expected_status, `portable ${route.method} ${route.path}`);
    assert.deepEqual(await response.json(), { status: "ok" }, `portable ${route.path}: fixed health response`);
  }

  process.stdout.write(`runtime parity passed for ${contract.common_routes.length} common routes and ${assetNames.length} exact built assets\n`);
} finally {
  await worker.close().catch(() => {});
  if (portable.exitCode === null) portable.kill("SIGTERM");
  await new Promise((resolveExit) => {
    if (portable.exitCode !== null) resolveExit();
    else portable.once("exit", resolveExit);
  });
  if (portable.exitCode && portable.exitCode !== 0) {
    process.stderr.write(portableErrors.slice(0, 4096));
  }
}
