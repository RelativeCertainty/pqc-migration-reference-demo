import type { EvidenceState } from "./model";

export type DeploymentEvidenceLayerId =
  | "source-contract"
  | "package-config"
  | "deployment"
  | "hostname-pq-capability"
  | "request-transport"
  | "exact-session-kex"
  | "visitor-edge-signatures"
  | "module-validation"
  | "external-validation";

export interface DeploymentEvidenceLayer {
  readonly id: DeploymentEvidenceLayerId;
  readonly label: string;
  readonly state: EvidenceState;
  readonly claim: string;
  readonly boundary: string;
  readonly locator: string;
}

export interface DeploymentEvidenceDescriptor {
  readonly schemaVersion: "pqc.deployment-evidence.v1";
  readonly descriptorVersion: "1.3.0";
  readonly target: {
    readonly hostname: "pqc-demo.example.invalid";
    readonly worker: "pqc-reference-demo";
  };
  readonly deploymentState: "source_only_not_deployed";
  readonly evidenceRecord: {
    readonly kind: "source_repository_and_automated_tests";
    readonly reference: "tracked source and test suite";
    readonly currentRuntimeInference: "prohibited";
  };
  readonly approvedLabelEligible: false;
  readonly failClosed: true;
  readonly runtimePromotion: "prohibited";
  readonly promotionGate: {
    readonly requiredChange: "reviewed_deployment_evidence_change";
    readonly deploymentEvidenceRequired: true;
    readonly exactHostValidationRequired: true;
    readonly runtimeValidationRequired: true;
    readonly freshEvidenceRequiredAfterChange: true;
  };
  readonly layers: readonly DeploymentEvidenceLayer[];
}

export const SOURCE_ONLY_DEPLOYMENT_EVIDENCE = {
  schemaVersion: "pqc.deployment-evidence.v1",
  descriptorVersion: "1.3.0",
  target: {
    hostname: "pqc-demo.example.invalid",
    worker: "pqc-reference-demo",
  },
  deploymentState: "source_only_not_deployed",
  evidenceRecord: {
    kind: "source_repository_and_automated_tests",
    reference: "tracked source and test suite",
    currentRuntimeInference: "prohibited",
  },
  approvedLabelEligible: false,
  failClosed: true,
  runtimePromotion: "prohibited",
  promotionGate: {
    requiredChange: "reviewed_deployment_evidence_change",
    deploymentEvidenceRequired: true,
    exactHostValidationRequired: true,
    runtimeValidationRequired: true,
    freshEvidenceRequiredAfterChange: true,
  },
  layers: [
    {
      id: "source-contract",
      label: "Source + synthetic contract",
      state: "Development evidence",
      claim: "Typed source defines synthetic inventory, evidence, and claim boundaries.",
      boundary: "Source inspection does not establish deployed behavior, a real inventory, or a user outcome.",
      locator: "src/domain/syntheticEvidence.v1.ts",
    },
    {
      id: "package-config",
      label: "Tracked package configuration",
      state: "Development evidence",
      claim: "Tracked configuration defines intended Worker and portable-package behavior.",
      boundary: "Configuration and package tests do not prove that an artifact is installed, reachable, or operating in production.",
      locator: "wrangler.jsonc + portable source + automated tests",
    },
    {
      id: "deployment",
      label: "Deployment",
      state: "Not deployed",
      claim: "This public portfolio snapshot asserts no deployed service or provider resource.",
      boundary: "The reserved example.invalid hostname is a placeholder, not DNS, routing, identity, certificate, or provider evidence.",
      locator: "source-only portfolio boundary",
    },
    {
      id: "hostname-pq-capability",
      label: "Hostname PQ capability",
      state: "Not validated",
      claim: "No deployed hostname has been tested for hybrid X25519MLKEM768 capability.",
      boundary: "A source tree, TLS version, or certificate description cannot establish a server handshake or visitor session.",
      locator: "external exact-host evidence required",
    },
    {
      id: "request-transport",
      label: "Current request transport",
      state: "Environment dependent",
      claim: "TLS version, TLS cipher, and HTTP protocol may be observable when the Worker adapter is actually executed.",
      boundary: "Request metadata does not establish deployment identity, hostname capability, or the negotiated key exchange.",
      locator: "GET /api/posture",
    },
    {
      id: "exact-session-kex",
      label: "Exact browser-session KEX",
      state: "Not observable",
      claim: "No exact-session key-exchange claim is made.",
      boundary: "The application request-metadata contract exposes no exact negotiated KEX field.",
      locator: "GET /api/posture evidence boundary",
    },
    {
      id: "visitor-edge-signatures",
      label: "Visitor-edge PQ signatures",
      state: "Not deployed",
      claim: "This package does not deploy or claim post-quantum visitor-edge signatures.",
      boundary: "Digital signatures remain separate from hybrid key agreement.",
      locator: "source claim boundary",
    },
    {
      id: "module-validation",
      label: "Algorithm + module evidence",
      state: "Not validated",
      claim: "Final algorithm standards are displayed separately from implementation and module validation.",
      boundary: "No FIPS 140 module certificate, build identity, or installed-runtime validation is asserted.",
      locator: "docs/nist-traceability.md",
    },
    {
      id: "external-validation",
      label: "External validation",
      state: "Not validated",
      claim: "No customer, production, assessor, or measured user outcome is represented.",
      boundary: "Synthetic fixtures and automated tests cannot be promoted into external acceptance or operational evidence.",
      locator: "source-only portfolio boundary",
    },
  ],
} satisfies DeploymentEvidenceDescriptor;
