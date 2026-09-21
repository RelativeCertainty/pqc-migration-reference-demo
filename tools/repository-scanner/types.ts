// SPDX-License-Identifier: MIT

export type EvidenceIssueType =
  | "tls-protocol"
  | "algorithm-key-strength"
  | "certificate-trust"
  | "implementation-configuration"
  | "source-code-crypto-use"
  | "cryptographic-dependency"
  | "vendor-control";

export interface EvidenceObservationV1 {
  schemaVersion: "pqc.evidence-observation.v1";
  observationId: string;
  feedId: "sast";
  adapter: { name: string; version: string };
  source: { recordRef: string; collectedAt: string | null };
  subject: {
    candidateKey: string;
    assetHint: string | null;
    estateClass: "source-code";
  };
  classification: { issueType: EvidenceIssueType };
  finding: { fact: string };
  provenance: {
    assessment: "probable" | "assumption";
    confidence: "low" | "illustrative";
    sourceLocator: string;
  };
  safety: {
    synthetic: boolean;
    containsSecret: false;
    rawPayloadRetained: false;
  };
}

export interface ScanDiagnostic {
  code: string;
  severity: "information" | "warning";
  relativePath: string | null;
  message: string;
}

export interface RepositoryScanResultV1 {
  schemaVersion: "pqc.repository-scan-result.v1";
  scanner: {
    name: "pqc-reference-repository-scanner";
    version: string;
    rulesetVersion: string;
  };
  target: { label: string; digest: string };
  collectedAt: string;
  summary: {
    visitedFiles: number;
    inspectedFiles: number;
    skippedFiles: number;
    observationCount: number;
    warningCount: number;
  };
  observations: EvidenceObservationV1[];
  diagnostics: ScanDiagnostic[];
  limitations: string[];
}

export interface CandidateObservation {
  ruleId: string;
  issueType: EvidenceIssueType;
  relativePath: string;
  line: number;
  fact: string;
}

export interface InspectedFile {
  relativePath: string;
  content: string;
  digest: string;
}

export interface RepositorySnapshot {
  files: InspectedFile[];
  diagnostics: ScanDiagnostic[];
  visitedFiles: number;
  skippedFiles: number;
  digestMaterial: string;
}

export interface ScanRequest {
  root: string;
  label: string;
  excludes: string[];
  synthetic: boolean;
  collectedAt?: string;
}

export interface ClockPort {
  now(): Date;
}

export interface HashingPort {
  sha256(value: string | Uint8Array): string;
}

export interface RulesetPort {
  readonly version: string;
  evaluate(file: InspectedFile): CandidateObservation[];
}

export interface RepositoryReaderPort {
  read(root: string, excludes: string[]): Promise<RepositorySnapshot>;
}

export interface ReportWriterPort {
  write(outputDirectory: string, result: RepositoryScanResultV1): Promise<void>;
}

export class InputBoundaryError extends Error {
  readonly name = "InputBoundaryError";
}

export class OutputBoundaryError extends Error {
  readonly name = "OutputBoundaryError";
}

export class ContractError extends Error {
  readonly name = "ContractError";
}
