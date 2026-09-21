import postureSource from "../components/PostureDashboard.tsx?raw";
import overviewSource from "../components/OverviewArchitecture.tsx?raw";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
// Test-only source inspection: do not expose backend source through Vite's asset server.
const backendSource = readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), "../../../../Api/ReferenceEndpoints.cs"), "utf8");
import {
  APPROVED_PQC_BASELINE,
  CLAIM_BOUNDARIES,
  PROHIBITED_BLANKET_CLAIMS,
} from "./claims";

describe("PQC claim boundaries", () => {
  it("preserves the exact source-only baseline paragraph", () => {
    expect(APPROVED_PQC_BASELINE).toBe(
      "PQC migration reference package. The source models migration evidence, synthetic inventory, and bounded posture reporting. It is not deployed and makes no claim about a public hostname, provider configuration, or negotiated post-quantum session.",
    );
  });

  it("keeps deployment, capability, session, signature, module, and provider evidence separate", () => {
    expect(CLAIM_BOUNDARIES).toEqual({
      deployment: "source_only_not_deployed",
      hostnameCapability: "no_deployed_hostname_no_observation",
      exactSessionKeyExchange: "not_observable",
      visitorEdgePostQuantumSignatures: "not_deployed",
      cryptographicModuleEvidence: "not_validated",
      identityAndProviderEvidence: "not_asserted",
      productEvidenceTier: "Development evidence",
    });
  });

  it("does not use prohibited blanket claims in the posture UI or C# host", () => {
    const implementation = `${postureSource}\n${backendSource}`.toLowerCase();
    for (const claim of PROHIBITED_BLANKET_CLAIMS) {
      expect(implementation).not.toContain(claim.toLowerCase());
    }
  });

  it("labels the portfolio snapshot as source-only and not deployed", () => {
    expect(postureSource).toContain("Source-only package; deployment claims withheld");
    expect(overviewSource).toContain("Source-only reference; not deployed");
    expect(postureSource).toContain("No deployed hostname");
    expect(postureSource).toContain("No identity policy or provider resource is asserted");
  });

  it("shows development controls without promoting them to runtime evidence", () => {
    for (const requiredText of [
      "pqc-demo.example.invalid (reserved placeholder)",
      "No DNS or provider resource asserted",
      "CSP · HSTS · no framing · no sniffing",
      "Synthetic · secret-free · source-reviewed",
      "No customer or production outcome",
    ]) {
      expect(postureSource).toContain(requiredText);
    }
  });
});
