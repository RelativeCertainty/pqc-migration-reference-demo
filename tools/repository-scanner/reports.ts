// SPDX-License-Identifier: MIT

import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import {
  OutputBoundaryError,
  type ReportWriterPort,
  type RepositoryScanResultV1,
} from "./types.ts";

function markdown(result: RepositoryScanResultV1): string {
  const lines = [
    "# Repository Cryptography Assessment",
    "",
    "> Evidence status: " + (result.observations.every((item) => item.safety.synthetic) ? "synthetic" : "candidate"),
    "",
    "This report contains conservative indicators for human assessment. It is not a vulnerability report, compliance determination, or complete cryptographic inventory.",
    "",
    "## Target",
    "",
    `- Label: \`${result.target.label}\``,
    `- Digest: \`${result.target.digest}\``,
    `- Collected at: \`${result.collectedAt}\``,
    `- Scanner: \`${result.scanner.name} ${result.scanner.version}\``,
    `- Ruleset: \`${result.scanner.rulesetVersion}\``,
    "",
    "## Summary",
    "",
    `- Visited files: ${result.summary.visitedFiles}`,
    `- Inspected files: ${result.summary.inspectedFiles}`,
    `- Skipped files: ${result.summary.skippedFiles}`,
    `- Candidate observations: ${result.summary.observationCount}`,
    `- Warnings: ${result.summary.warningCount}`,
    "",
    "## Candidate observations",
    "",
  ];

  if (result.observations.length === 0) {
    lines.push("No indicators matched the current conservative ruleset. This does not establish absence of cryptographic use.", "");
  } else {
    for (const observation of result.observations) {
      lines.push(
        `### ${observation.classification.issueType}`,
        "",
        `- Location: \`${observation.provenance.sourceLocator}\``,
        `- Assessment: \`${observation.provenance.assessment}\``,
        `- Confidence: \`${observation.provenance.confidence}\``,
        `- Fact: ${observation.finding.fact}`,
        "",
      );
    }
  }

  lines.push("## Skipped-file diagnostics", "");
  if (result.diagnostics.length === 0) {
    lines.push("No skipped-file diagnostics were recorded.", "");
  } else {
    for (const diagnostic of result.diagnostics) {
      lines.push(
        `- **${diagnostic.severity} / ${diagnostic.code}:** ${diagnostic.relativePath === null ? "repository" : `\`${diagnostic.relativePath}\``} - ${diagnostic.message}`,
      );
    }
    lines.push("");
  }

  lines.push("## Coverage limitations", "");
  for (const limitation of result.limitations) lines.push(`- ${limitation}`);
  lines.push("");
  return lines.join("\n");
}

export class CreateOnlyReportAdapter implements ReportWriterPort {
  async write(outputDirectory: string, result: RepositoryScanResultV1): Promise<void> {
    try {
      await mkdir(outputDirectory, { recursive: false, mode: 0o700 });
      await writeFile(
        path.join(outputDirectory, "scan-result.json"),
        `${JSON.stringify(result, null, 2)}\n`,
        { encoding: "utf8", flag: "wx", mode: 0o600 },
      );
      await writeFile(
        path.join(outputDirectory, "assessment.md"),
        markdown(result),
        { encoding: "utf8", flag: "wx", mode: 0o600 },
      );
    } catch {
      throw new OutputBoundaryError("output directory must be new and create-only");
    }
  }
}
