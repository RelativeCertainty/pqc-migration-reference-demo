// SPDX-License-Identifier: MIT

import { createHash } from "node:crypto";

import { assertRepositoryScanResultV1 } from "./contracts.ts";
import { ReadOnlyFilesystemAdapter } from "./filesystem.ts";
import { DefaultRuleset } from "./rules.ts";
import {
  ContractError,
  type ClockPort,
  type HashingPort,
  type RepositoryReaderPort,
  type RepositoryScanResultV1,
  type RulesetPort,
  type ScanRequest,
} from "./types.ts";

const SCANNER_VERSION = "0.1.0";
const limitations = [
  "The scanner inspects allowlisted UTF-8 repository text only; runtime negotiation, deployed configuration, generated artifacts, and external services are outside coverage.",
  "Indicator matches identify candidate cryptographic use for human assessment; they are not vulnerability findings and do not establish inventory completeness.",
  "Relative filenames and line numbers are retained for authorized local review, while source excerpts, raw payloads, secret values, and absolute paths are omitted.",
];

class SystemClock implements ClockPort {
  now(): Date {
    return new Date();
  }
}

class Sha256Hasher implements HashingPort {
  sha256(value: string | Uint8Array): string {
    return createHash("sha256").update(value).digest("hex");
  }
}

export interface ScanRepositoryPorts {
  clock: ClockPort;
  hashing: HashingPort;
  reader: RepositoryReaderPort;
  ruleset: RulesetPort;
}

function canonicalTimestamp(input: string | undefined, clock: ClockPort): string {
  const date = input === undefined ? clock.now() : new Date(input);
  if (Number.isNaN(date.valueOf())) throw new ContractError("collected-at must be a UTC timestamp");
  const canonical = date.toISOString().replace(/\.\d{3}Z$/u, "Z");
  if (!canonical.endsWith("Z")) throw new ContractError("collected-at must be UTC");
  return canonical;
}

export class ScanRepository {
  private readonly ports: ScanRepositoryPorts;

  constructor(ports: ScanRepositoryPorts) {
    this.ports = ports;
  }

  async execute(request: ScanRequest): Promise<RepositoryScanResultV1> {
    if (!/^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$/u.test(request.label)) {
      throw new ContractError("label must contain 2-64 safe characters");
    }

    const collectedAt = canonicalTimestamp(request.collectedAt, this.ports.clock);
    const snapshot = await this.ports.reader.read(request.root, request.excludes);
    const candidates = snapshot.files
      .flatMap((file) => this.ports.ruleset.evaluate(file))
      .sort((left, right) =>
        left.relativePath.localeCompare(right.relativePath, "en") ||
        left.line - right.line ||
        left.ruleId.localeCompare(right.ruleId, "en")
      );

    const observations = candidates.map((candidate) => {
      const observationHash = this.ports.hashing.sha256(
        [
          request.label,
          candidate.relativePath,
          candidate.ruleId,
          String(candidate.line),
          this.ports.ruleset.version,
        ].join("\0"),
      );
      const assetHash = this.ports.hashing.sha256(candidate.relativePath);
      return {
        schemaVersion: "pqc.evidence-observation.v1" as const,
        observationId: `obs:${observationHash.slice(0, 24)}`,
        feedId: "sast" as const,
        adapter: { name: "repository-scanner", version: SCANNER_VERSION },
        source: {
          recordRef: `repository:${candidate.relativePath}`.slice(0, 256),
          collectedAt: request.synthetic ? null : collectedAt,
        },
        subject: {
          candidateKey: `source:${assetHash.slice(0, 32)}`,
          assetHint: candidate.relativePath.slice(0, 160),
          estateClass: "source-code" as const,
        },
        classification: { issueType: candidate.issueType },
        finding: { fact: candidate.fact },
        provenance: {
          assessment: request.synthetic ? "assumption" as const : "probable" as const,
          confidence: request.synthetic ? "illustrative" as const : "low" as const,
          sourceLocator: `repository:${candidate.relativePath}#L${candidate.line}`.slice(0, 300),
        },
        safety: {
          synthetic: request.synthetic,
          containsSecret: false as const,
          rawPayloadRetained: false as const,
        },
      };
    });

    const result: RepositoryScanResultV1 = {
      schemaVersion: "pqc.repository-scan-result.v1",
      scanner: {
        name: "pqc-reference-repository-scanner",
        version: SCANNER_VERSION,
        rulesetVersion: this.ports.ruleset.version,
      },
      target: {
        label: request.label,
        digest: `sha256:${this.ports.hashing.sha256(
          `${request.label}\0${this.ports.ruleset.version}\0${snapshot.digestMaterial}`,
        )}`,
      },
      collectedAt,
      summary: {
        visitedFiles: snapshot.visitedFiles,
        inspectedFiles: snapshot.files.length,
        skippedFiles: snapshot.skippedFiles,
        observationCount: observations.length,
        warningCount: snapshot.diagnostics.filter((item) => item.severity === "warning").length,
      },
      observations,
      diagnostics: snapshot.diagnostics,
      limitations,
    };

    assertRepositoryScanResultV1(result);
    return result;
  }
}

export function createScanRepository(): ScanRepository {
  return new ScanRepository({
    clock: new SystemClock(),
    hashing: new Sha256Hasher(),
    reader: new ReadOnlyFilesystemAdapter(),
    ruleset: new DefaultRuleset(),
  });
}
