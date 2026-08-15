import worker from "./index";
import { API_SECURITY_HEADERS, buildPosturePayload } from "./posture";
import wranglerSource from "../wrangler.jsonc?raw";

const handle = worker.fetch;

function requestWithCf(path: string, method = "GET") {
  const request = new Request(`https://pqc-demo.example.invalid${path}`, { method });
  Object.defineProperty(request, "cf", {
    value: {
      tlsVersion: "TLSv1.3",
      tlsCipher: "AEAD-AES128-GCM-SHA256",
      httpProtocol: "HTTP/2",
    },
  });
  return request;
}

const env: CloudflareBindings = {
  ASSETS: {
    async fetch() {
      return new Response("<h1>asset</h1>", {
        headers: { "Content-Type": "text/html; charset=utf-8" },
      });
    },
    connect() {
      throw new Error("The unit-test asset binding does not support sockets.");
    },
  },
};

describe("posture Worker", () => {
  it("disables source-map upload and Workers Logs observability", () => {
    const config = JSON.parse(wranglerSource) as {
      upload_source_maps?: boolean;
      observability?: { enabled?: boolean };
    };

    expect(config.upload_source_maps).toBe(false);
    expect(config.observability?.enabled).toBe(false);
  });

  it("returns bounded request metadata without visitor identifiers", () => {
    const payload = buildPosturePayload(requestWithCf("/api/posture"));
    expect(payload.request_transport.tls_version.value).toBe("TLSv1.3");
    expect(payload.request_transport.tls_cipher.value).toBe("AEAD-AES128-GCM-SHA256");
    expect(payload.request_transport.exact_session_key_exchange.state).toBe("not_observable");
    expect(payload.schema_version).toBe("pqc-posture.v2");
    expect(payload.evidence_tier).toBe("request_transport_observation");
    expect(payload.hostname_capability.state).toBe("not_observable_by_handler");
    expect(payload.access_control.state).toBe("not_observable_by_handler");
    expect(payload.visitor_edge_post_quantum_signatures.state).toBe("not_deployed");
    expect(payload.approved_deployment_label.eligible).toBe(false);

    const serialized = JSON.stringify(payload).toLowerCase();
    for (const disallowedField of ["ip_address", "client_ip", "cookie", "email", "user_agent", "authorization"]) {
      expect(serialized).not.toContain(disallowedField);
    }
  });

  it("applies no-store and browser security headers to the API", async () => {
    const response = await handle(requestWithCf("/api/posture"), env);
    expect(response.status).toBe(200);
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(response.headers.get("Content-Type")).toContain("application/json");
    for (const [name, value] of Object.entries(API_SECURITY_HEADERS)) {
      expect(response.headers.get(name)).toBe(value);
    }
  });

  it("rejects mutations and unknown API routes", async () => {
    const postResponse = await handle(requestWithCf("/api/posture", "POST"), env);
    expect(postResponse.status).toBe(405);
    expect(postResponse.headers.get("Allow")).toBe("GET, HEAD");

    const missingResponse = await handle(requestWithCf("/api/unknown"), env);
    expect(missingResponse.status).toBe(404);
  });

  it("returns no body for HEAD and secures Worker-fetched assets", async () => {
    const headResponse = await handle(requestWithCf("/api/posture", "HEAD"), env);
    expect(headResponse.status).toBe(200);
    expect(await headResponse.text()).toBe("");

    const assetResponse = await handle(requestWithCf("/fallback"), env);
    expect(assetResponse.headers.get("X-Frame-Options")).toBe("DENY");
    expect(assetResponse.headers.get("Content-Type")).toContain("text/html");
  });

  it("does not turn a missing fingerprinted asset into an SPA fallback", async () => {
    const response = await handle(requestWithCf("/assets/missing.js"), env);

    expect(response.status).toBe(404);
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    await expect(response.json()).resolves.toMatchObject({ error: "not_found" });
  });
});
