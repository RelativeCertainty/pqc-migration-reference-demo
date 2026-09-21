// SPDX-License-Identifier: MIT

import {
  ContractError,
  type EvidenceObservationV1,
  type RepositoryScanResultV1,
} from "./types.ts";

const issueTypes = new Set([
  "tls-protocol",
  "algorithm-key-strength",
  "certificate-trust",
  "implementation-configuration",
  "source-code-crypto-use",
  "cryptographic-dependency",
  "vendor-control",
]);

export function assertEvidenceObservationV1(value: EvidenceObservationV1): void {
  if (
    value.schemaVersion !== "pqc.evidence-observation.v1" ||
    value.feedId !== "sast" ||
    value.subject.estateClass !== "source-code" ||
    !issueTypes.has(value.classification.issueType) ||
    value.safety.containsSecret !== false ||
    value.safety.rawPayloadRetained !== false ||
    value.finding.fact.includes("\n") ||
    value.provenance.sourceLocator.startsWith("/")
  ) {
    throw new ContractError("evidence observation contract rejected");
  }
  if (
    value.safety.synthetic &&
    (
      value.source.collectedAt !== null ||
      value.provenance.assessment !== "assumption" ||
      value.provenance.confidence !== "illustrative"
    )
  ) {
    throw new ContractError("synthetic evidence contract rejected");
  }
}

export function assertRepositoryScanResultV1(value: RepositoryScanResultV1): void {
  if (
    value.schemaVersion !== "pqc.repository-scan-result.v1" ||
    value.scanner.name !== "pqc-reference-repository-scanner" ||
    !/^sha256:[a-f0-9]{64}$/u.test(value.target.digest) ||
    !/^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$/u.test(value.target.label) ||
    value.summary.inspectedFiles !== value.summary.visitedFiles - value.summary.skippedFiles ||
    value.summary.observationCount !== value.observations.length ||
    value.summary.warningCount !== value.diagnostics.filter((item) => item.severity === "warning").length
  ) {
    throw new ContractError("repository scan-result contract rejected");
  }
  for (const observation of value.observations) assertEvidenceObservationV1(observation);
  for (const diagnostic of value.diagnostics) {
    if (
      diagnostic.relativePath?.startsWith("/") ||
      diagnostic.relativePath?.split("/").includes("..") ||
      diagnostic.message.includes("\n")
    ) {
      throw new ContractError("repository diagnostic contract rejected");
    }
  }
}
