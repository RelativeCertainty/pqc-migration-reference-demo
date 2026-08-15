import postureSource from "../components/PostureDashboard.tsx?raw";
import { SOURCE_ONLY_DEPLOYMENT_EVIDENCE } from "./deploymentEvidence.v1";

describe("fail-closed source-only evidence", () => {
  const descriptor = SOURCE_ONLY_DEPLOYMENT_EVIDENCE;

  it("records source and test evidence without asserting a deployment", () => {
    expect(descriptor).toMatchObject({
      schemaVersion: "pqc.deployment-evidence.v1",
      descriptorVersion: "1.3.0",
      deploymentState: "source_only_not_deployed",
      evidenceRecord: {
        kind: "source_repository_and_automated_tests",
        reference: "tracked source and test suite",
        currentRuntimeInference: "prohibited",
      },
      approvedLabelEligible: false,
      failClosed: true,
      runtimePromotion: "prohibited",
      target: {
        hostname: "pqc-demo.example.invalid",
        worker: "pqc-reference-demo",
      },
      promotionGate: {
        requiredChange: "reviewed_deployment_evidence_change",
        deploymentEvidenceRequired: true,
        exactHostValidationRequired: true,
        runtimeValidationRequired: true,
        freshEvidenceRequiredAfterChange: true,
      },
    });
  });

  it("keeps source, deployment, transport, KEX, signature, module, and external evidence separate", () => {
    const layers = Object.fromEntries(descriptor.layers.map((layer) => [layer.id, layer]));

    expect(layers["source-contract"].state).toBe("Development evidence");
    expect(layers["package-config"].state).toBe("Development evidence");
    expect(layers.deployment.state).toBe("Not deployed");
    expect(layers.deployment.boundary).toContain("example.invalid");
    expect(layers["hostname-pq-capability"].state).toBe("Not validated");
    expect(layers["request-transport"].state).toBe("Environment dependent");
    expect(layers["exact-session-kex"].state).toBe("Not observable");
    expect(layers["visitor-edge-signatures"].state).toBe("Not deployed");
    expect(layers["module-validation"].state).toBe("Not validated");
    expect(layers["external-validation"].state).toBe("Not validated");
    expect(new Set(descriptor.layers.map((layer) => layer.id)).size).toBe(descriptor.layers.length);
  });

  it("renders the source-only boundary and evidence layers in the posture UI", () => {
    expect(postureSource).toContain("Fail-closed source descriptor");
    expect(postureSource).toContain("Runtime metadata cannot promote this source descriptor");
    expect(postureSource).toContain("Source descriptor versus current runtime");
    expect(postureSource).toContain("Evidence layers stay separate");
    expect(postureSource).toContain("source-only portfolio snapshot");
    expect(postureSource).toContain("No customer or production outcome");
  });
});
