import type { CryptoIssueType } from "../domain/model";
import type { EvidenceObservationV1 } from "../domain/evidenceFusion";
import type {
  AdapterDiagnostic,
  EvidenceBatchAdapter,
  EvidenceImportContext,
  EvidenceImportRunV1,
} from "../ports/evidenceIngestion";
import {
  asArray,
  asRecord,
  assertImportContext,
  boundedText,
  canonicalAssetKey,
  EvidenceAdapterError,
  isRecord,
  stableSafeId,
  validTimestamp,
} from "./adapterSupport";

const CRYPTO_SIGNAL = /\b(?:aes|cipher|crypto(?:graphy|graphic)?|decrypt(?:ion)?|dsa|ecb|ecdsa|encrypt(?:ion)?|elliptic|hardcoded[ -]?key|hmac|key(?:pair|size|length|generation|store|management)?|md5|pem|private[ -]?key|public[ -]?key|rsa|sha-?1|signature|signing|ssl|tls|truststore|x\.?509)\b/iu;
const DEPENDENCY_SIGNAL = /\b(?:dependency|library|package|provider|sdk|version)\b/iu;
const CONFIGURATION_SIGNAL = /\b(?:cbc|cipher|ecb|hardcoded|iv|mode|padding|random|seed|tls|ssl|trust|verification)\b/iu;
const MAX_RUNS = 50;
const MAX_RESULTS = 5_000;

const ISSUE_TYPE_FACTS: Readonly<Record<CryptoIssueType, string>> = {
  "source-code-crypto-use": "source-code cryptographic use",
  "implementation-configuration": "cryptographic implementation or configuration",
  "cryptographic-dependency": "cryptographic dependency",
  "algorithm-key-strength": "cryptographic algorithm or key strength",
  "certificate-trust": "certificate or trust relationship",
  "tls-protocol": "TLS protocol use",
  "vendor-control": "vendor-controlled cryptographic dependency",
};

function ruleText(run: Record<string, unknown>, ruleId: string): string {
  const tool = isRecord(run.tool) ? run.tool : {};
  const driver = isRecord(tool.driver) ? tool.driver : {};
  const rules = asArray(driver.rules);
  const rule = rules.find((candidate) => isRecord(candidate) && candidate.id === ruleId);
  if (!isRecord(rule)) return "";
  const shortDescription = isRecord(rule.shortDescription) ? rule.shortDescription.text : "";
  const fullDescription = isRecord(rule.fullDescription) ? rule.fullDescription.text : "";
  const properties = isRecord(rule.properties) ? rule.properties : {};
  const tags = asArray(properties.tags).filter((item): item is string => typeof item === "string").join(" ");
  return [shortDescription, fullDescription, tags].filter((item): item is string => typeof item === "string").join(" ");
}

function resultMessage(result: Record<string, unknown>): string {
  const message = isRecord(result.message) ? result.message.text : "";
  return boundedText(message, "Snyk Code reported a crypto-relevant source finding.", 280);
}

function issueTypeFor(text: string): CryptoIssueType {
  if (DEPENDENCY_SIGNAL.test(text)) return "cryptographic-dependency";
  if (CONFIGURATION_SIGNAL.test(text)) return "implementation-configuration";
  return "source-code-crypto-use";
}

function runTimestamp(run: Record<string, unknown>, fallback: string | null): string | null {
  for (const invocation of asArray(run.invocations)) {
    if (!isRecord(invocation)) continue;
    const timestamp = validTimestamp(invocation.endTimeUtc) ?? validTimestamp(invocation.startTimeUtc);
    if (timestamp) return timestamp;
  }
  return fallback;
}

function toolName(run: Record<string, unknown>): string {
  const tool = isRecord(run.tool) ? run.tool : {};
  const driver = isRecord(tool.driver) ? tool.driver : {};
  return boundedText(driver.name, "unknown-sarif-tool", 80);
}

function severityFor(value: unknown): "ERROR" | "WARNING" | "NOTE" | "UNSPECIFIED" {
  if (value === "error") return "ERROR";
  if (value === "warning") return "WARNING";
  if (value === "note") return "NOTE";
  return "UNSPECIFIED";
}

function normalizeResult(
  run: Record<string, unknown>,
  result: Record<string, unknown>,
  context: EvidenceImportContext,
  ordinal: number,
): EvidenceObservationV1 | null {
  const ruleId = boundedText(result.ruleId, `result-${ordinal}`, 120);
  const message = resultMessage(result);
  const rule = ruleText(run, ruleId);
  const searchable = `${ruleId} ${rule} ${message}`;
  if (!CRYPTO_SIGNAL.test(searchable)) return null;

  const candidateKey = canonicalAssetKey(context.assetKey);
  const sourceIdentity = `${candidateKey}\u0000${ordinal}`;
  const recordRef = stableSafeId("snyk-code", sourceIdentity);
  const severity = severityFor(result.level);
  const synthetic = context.synthetic;
  const issueType = issueTypeFor(searchable);

  return {
    schemaVersion: "pqc.evidence-observation.v1",
    observationId: stableSafeId("obs:sast:snyk", sourceIdentity),
    feedId: "sast",
    adapter: { name: "snyk-code-sarif-adapter", version: "1.0.0" },
    source: { recordRef, collectedAt: synthetic ? null : runTimestamp(run, context.collectedAt) },
    subject: {
      candidateKey,
      assetHint: synthetic ? boundedText(context.assetName, "Synthetic source repository", 160) : null,
      estateClass: context.estateClass,
    },
    classification: { issueType },
    finding: {
      fact: `Snyk Code reported a ${ISSUE_TYPE_FACTS[issueType]} finding at ${severity} severity; the native message, rule identifier, and source location were withheld from export.`,
    },
    provenance: {
      assessment: synthetic ? "assumption" : "unresolved",
      confidence: synthetic ? "illustrative" : "low",
      sourceLocator: `local-import:snyk-code-sarif:${recordRef}`,
    },
    safety: { synthetic, containsSecret: false, rawPayloadRetained: false },
  };
}

export const SnykCodeSarifAdapter: EvidenceBatchAdapter = {
  id: "snyk-code-sarif",
  name: "snyk-code-sarif-adapter",
  version: "1.0.0",
  feedId: "sast",
  adapt(payload: unknown, context: EvidenceImportContext): EvidenceImportRunV1 {
    assertImportContext(context);
    const root = asRecord(payload, "Snyk Code import must be a SARIF JSON object.");
    if (root.version !== "2.1.0") {
      throw new EvidenceAdapterError("Snyk Code import must use SARIF 2.1.0.");
    }
    const runs = asArray(root.runs);
    if (runs.length === 0 || runs.length > MAX_RUNS) {
      throw new EvidenceAdapterError(`Snyk Code import must contain 1–${MAX_RUNS} SARIF runs.`);
    }

    const observations: EvidenceObservationV1[] = [];
    const diagnostics: AdapterDiagnostic[] = [];
    let skippedCount = 0;
    let resultCount = 0;

    for (const [runIndex, nativeRun] of runs.entries()) {
      const run = asRecord(nativeRun, `Snyk Code SARIF run ${runIndex + 1} is invalid.`);
      const name = toolName(run);
      if (!/snyk/iu.test(name)) {
        throw new EvidenceAdapterError(`Snyk Code SARIF run ${runIndex + 1} does not identify a Snyk producer.`);
      }
      for (const nativeResult of asArray(run.results)) {
        resultCount += 1;
        if (resultCount > MAX_RESULTS) {
          throw new EvidenceAdapterError(`Snyk Code import exceeds the ${MAX_RESULTS}-result safety limit.`);
        }
        if (!isRecord(nativeResult)) {
          skippedCount += 1;
          diagnostics.push({ level: "warning", code: "invalid-result", message: "A non-object SARIF result was skipped.", sourceRef: null });
          continue;
        }
        const observation = normalizeResult(run, nativeResult, context, resultCount);
        if (observation) observations.push(observation);
        else skippedCount += 1;
      }
    }

    if (observations.length === 0) {
      diagnostics.push({
        level: "information",
        code: "no-crypto-signal",
        message: "The import was valid, but no crypto-relevant Snyk Code findings matched the bounded classifier.",
        sourceRef: null,
      });
    }

    return {
      schemaVersion: "pqc.evidence-import-run.v1",
      adapterId: "snyk-code-sarif",
      adapterName: "snyk-code-sarif-adapter",
      adapterVersion: "1.0.0",
      feedId: "sast",
      sourceName: context.synthetic ? "synthetic-snyk-code-sarif" : "local-snyk-code-sarif",
      acceptedCount: observations.length,
      skippedCount,
      observations,
      diagnostics,
      safety: { synthetic: context.synthetic, containsSecret: false, rawPayloadRetained: false },
    };
  },
};
