import type {
  SyntheticEvidenceArtifact,
  SyntheticEvidenceRecord,
  SyntheticSystemId,
} from "./model";

const SYNTHETIC_SYSTEM_IDS = [
  "syn-api-edge-01",
  "syn-pay-java-02",
  "syn-vpn-03",
  "syn-ca-04",
  "syn-k8s-05",
  "syn-sign-06",
  "syn-sftp-07",
  "syn-ssh-08",
  "syn-mobile-09",
  "syn-archive-10",
] as const satisfies readonly SyntheticSystemId[];

function createSyntheticRecord(systemId: SyntheticSystemId): SyntheticEvidenceRecord {
  return {
    evidenceId: `synthetic-discovery:${systemId}:v1`,
    systemId,
    stageRef: "pqc-lifecycle-stage:2",
    provenance: {
      kind: "synthetic_fixture",
      sourceLocator: "src/domain/data.ts",
      synthetic: true,
    },
    confidence: {
      level: "illustrative",
      rationale: "The record demonstrates the contract only; it does not describe an observed organization or system.",
    },
    observation: {
      kind: "synthetic_fixture_declaration",
      observedAt: null,
      declaredOn: "2026-08-13",
      runtimeObserved: false,
    },
    evidence: {
      state: "assumption",
      owner: "PQC reference demo maintainer",
      reviewDate: "2026-09-13",
    },
    test: {
      result: "not_executed_in_artifact",
      locator: "src/domain/data.test.ts",
      scope: "The referenced development test checks schema, stage binding, record count, and synthetic boundaries; run evidence is separate.",
    },
    residualGaps: [
      "No environment source was queried.",
      "No installed runtime or cryptographic behavior was observed.",
      "No accountable environment owner validated this record.",
    ],
  };
}

export const SYNTHETIC_EVIDENCE_ARTIFACT = {
  schemaVersion: "pqc.synthetic-evidence.v1",
  artifactId: "pqc-reference-demo-discovery-inventory",
  artifactVersion: "1.0.0",
  synthetic: true,
  declaredOn: "2026-08-13",
  stage: {
    ref: "pqc-lifecycle-stage:2",
    ordinal: 2,
    label: "Discovery & Inventory",
  },
  records: SYNTHETIC_SYSTEM_IDS.map(createSyntheticRecord),
} satisfies SyntheticEvidenceArtifact;

export function syntheticEvidenceFor(systemId: SyntheticSystemId): SyntheticEvidenceRecord {
  const record = SYNTHETIC_EVIDENCE_ARTIFACT.records.find((candidate) => candidate.systemId === systemId);
  if (!record) throw new Error(`Missing synthetic evidence contract for ${systemId}`);
  return record;
}
