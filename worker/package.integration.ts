import { createTestHarness } from "wrangler";
import { readdir } from "node:fs/promises";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

const server = createTestHarness({
  workers: [{ configPath: "./wrangler.jsonc" }],
});

beforeAll(async () => {
  await server.listen();
});

afterAll(async () => {
  await server.close();
});

describe("packaged Worker and Static Assets", () => {
  it("serves the posture API through the packaged Worker", async () => {
    const response = await server.fetch("https://pqc-demo.example.invalid/api/posture");
    const payload = (await response.json()) as {
      schema_version: string;
      hostname: string;
      approved_deployment_label: { eligible: boolean };
    };

    expect(response.status).toBe(200);
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(payload.schema_version).toBe("pqc-posture.v2");
    expect(payload.hostname).toBe("pqc-demo.example.invalid");
    expect(payload.approved_deployment_label.eligible).toBe(false);
  });

  it("serves the built application and SPA fallbacks through the assets binding", async () => {
    for (const path of ["/", "/interview"]) {
      const response = await server.fetch(path);
      const body = await response.text();

      expect(response.status).toBe(200);
      expect(response.headers.get("Content-Type")).toContain("text/html");
      expect(response.headers.get("X-Frame-Options")).toBe("DENY");
      expect(body).toContain('<div id="root"></div>');
    }
  });

  it("serves fingerprinted assets with one immutable browser cache policy", async () => {
    const assetNames = await readdir(new URL("../dist/assets/", import.meta.url));
    expect(assetNames.length).toBeGreaterThan(0);

    for (const assetName of assetNames) {
      const response = await server.fetch(`/assets/${assetName}`);

      expect(response.status).toBe(200);
      expect(response.headers.get("Cache-Control")).toBe(
        "public, max-age=31536000, immutable",
      );
    }
  });

  it("keeps packaged API routes read-only", async () => {
    const response = await server.fetch("/api/posture", { method: "POST" });

    expect(response.status).toBe(405);
    expect(response.headers.get("Allow")).toBe("GET, HEAD");
  });

  it("returns a bounded 404 instead of the SPA for missing fingerprinted assets", async () => {
    const response = await server.fetch("/assets/missing.js");

    expect(response.status).toBe(404);
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    await expect(response.json()).resolves.toMatchObject({ error: "not_found" });
  });
});
