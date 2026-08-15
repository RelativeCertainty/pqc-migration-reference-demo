import type { CryptoIssueType, SoftwareEstateClass } from "./model";
import type {
  CanonicalCryptoRecordV1,
  EvidenceFeedId,
  EvidenceFusionResultV1,
  EvidenceObservationV1,
  SourceReconciliationItemV1,
} from "./evidenceFusion";

const FEED_IDS = new Set<EvidenceFeedId>([
  "initial-inventory",
  "extrahop-internet-tls",
  "vulnerability-manager",
  "pki-inventory",
  "sast",
  "cmdb",
]);
const FEED_ORDER: readonly EvidenceFeedId[] = [
  "initial-inventory",
  "extrahop-internet-tls",
  "vulnerability-manager",
  "pki-inventory",
  "sast",
  "cmdb",
];
const ESTATE_CLASSES = new Set<SoftwareEstateClass>(["source-code", "ots-cots", "third-party-saas"]);
const ISSUE_TYPES = new Set<CryptoIssueType>([
  "tls-protocol",
  "algorithm-key-strength",
  "certificate-trust",
  "implementation-configuration",
  "source-code-crypto-use",
  "cryptographic-dependency",
  "vendor-control",
]);
const ASSESSMENTS = new Set(["verified", "partially-verified", "probable", "assumption", "unresolved"]);
const CONFIDENCE_LEVELS = new Set(["high", "moderate", "low", "illustrative"]);
const SAFE_IDENTIFIER = /^[a-z0-9][a-z0-9._:-]{2,127}$/u;
const SAFE_RECORD_ID = /^record:(?=.*\S)[^\r\n\t]+$/u;
const SAFE_SOURCE_IDENTITY = /^source-identity:local:[0-9]{4}$/u;
const SAFE_CONFLICT_FIELD = /^[a-z][a-zA-Z0-9]*$/u;
const NO_CONTROL_LINES = /^[^\r\n\t]+$/u;
const CANONICAL_TIMESTAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z$/u;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasExactKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  return actual.length === expected.length && actual.every((key, index) => key === expected[index]);
}

function isBoundedText(value: unknown, maxLength: number): value is string {
  return typeof value === "string" && value.trim().length > 0 && value.length <= maxLength && NO_CONTROL_LINES.test(value);
}

function isCanonicalTimestamp(value: unknown): value is string {
  if (typeof value !== "string" || value.length > 30 || !CANONICAL_TIMESTAMP.test(value)) return false;
  const parsed = new Date(value);
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().slice(0, 19) === value.slice(0, 19);
}

export function assertEvidenceObservationContract(value: unknown): asserts value is EvidenceObservationV1 {
  if (!isRecord(value) || !hasExactKeys(value, ["schemaVersion", "observationId", "feedId", "adapter", "source", "subject", "classification", "finding", "provenance", "safety"])) {
    throw new Error("Evidence observation rejected: invalid root contract");
  }
  const { adapter, source, subject, classification, finding, provenance, safety: safetyValue } = value;
  if (value.schemaVersion !== "pqc.evidence-observation.v1" || typeof value.observationId !== "string" || !SAFE_IDENTIFIER.test(value.observationId) || !FEED_IDS.has(value.feedId as EvidenceFeedId)) {
    throw new Error("Evidence observation rejected: invalid identity fields");
  }
  if (!isRecord(adapter) || !hasExactKeys(adapter, ["name", "version"]) || typeof adapter.name !== "string" || !SAFE_IDENTIFIER.test(adapter.name) || typeof adapter.version !== "string" || adapter.version.length > 32 || !/^[0-9]+\.[0-9]+\.[0-9]+$/u.test(adapter.version)) {
    throw new Error("Evidence observation rejected: invalid adapter metadata");
  }
  if (!isRecord(source) || !hasExactKeys(source, ["recordRef", "collectedAt"]) || !isBoundedText(source.recordRef, 256) || (source.collectedAt !== null && !isCanonicalTimestamp(source.collectedAt))) {
    throw new Error("Evidence observation rejected: invalid source metadata");
  }
  if (!isRecord(subject) || !hasExactKeys(subject, ["candidateKey", "assetHint", "estateClass"]) || !isBoundedText(subject.candidateKey, 160) || (subject.assetHint !== null && !isBoundedText(subject.assetHint, 160)) || !ESTATE_CLASSES.has(subject.estateClass as SoftwareEstateClass)) {
    throw new Error("Evidence observation rejected: invalid subject fields");
  }
  if (!isRecord(classification) || !hasExactKeys(classification, ["issueType"]) || !ISSUE_TYPES.has(classification.issueType as CryptoIssueType)) {
    throw new Error("Evidence observation rejected: invalid issue classification");
  }
  if (!isRecord(finding) || !hasExactKeys(finding, ["fact"]) || !isBoundedText(finding.fact, 500)) {
    throw new Error("Evidence observation rejected: invalid finding");
  }
  if (!isRecord(provenance) || !hasExactKeys(provenance, ["assessment", "confidence", "sourceLocator"]) || !ASSESSMENTS.has(provenance.assessment as string) || !CONFIDENCE_LEVELS.has(provenance.confidence as string) || !isBoundedText(provenance.sourceLocator, 300)) {
    throw new Error("Evidence observation rejected: invalid provenance");
  }
  if (!isRecord(safetyValue) || !hasExactKeys(safetyValue, ["synthetic", "containsSecret", "rawPayloadRetained"]) || typeof safetyValue.synthetic !== "boolean" || safetyValue.containsSecret !== false || safetyValue.rawPayloadRetained !== false) {
    throw new Error("Evidence observation rejected: unsafe payload contract");
  }
  if (safetyValue.synthetic && (source.collectedAt !== null || !["assumption", "unresolved"].includes(provenance.assessment as string) || provenance.confidence !== "illustrative")) {
    throw new Error("Evidence observation rejected: synthetic evidence boundary violated");
  }
}

function canonicalizeKey(value: string): string {
  return value.trim().toLowerCase().replaceAll(/\s+/gu, "-");
}

function exactSourceKey(observation: EvidenceObservationV1): string {
  return `${observation.feedId}\u0000${observation.source.recordRef}`;
}

function canonicalValue(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalValue).join(",")}]`;
  if (isRecord(value)) {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalValue(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function changedFields(retained: EvidenceObservationV1, replay: EvidenceObservationV1): string[] {
  return [
    "sourceRecord",
    ...(retained.observationId !== replay.observationId ? ["observationId"] : []),
    ...(retained.adapter.name !== replay.adapter.name ? ["adapterName"] : []),
    ...(retained.adapter.version !== replay.adapter.version ? ["adapterVersion"] : []),
    ...(canonicalizeKey(retained.subject.candidateKey) !== canonicalizeKey(replay.subject.candidateKey) ? ["candidateKey"] : []),
    ...(retained.subject.assetHint !== replay.subject.assetHint ? ["displayName"] : []),
    ...(retained.subject.estateClass !== replay.subject.estateClass ? ["estateClass"] : []),
    ...(retained.classification.issueType !== replay.classification.issueType ? ["issueType"] : []),
    ...(retained.finding.fact !== replay.finding.fact ? ["finding"] : []),
    ...(retained.source.collectedAt !== replay.source.collectedAt ? ["collectedAt"] : []),
    ...(retained.provenance.assessment !== replay.provenance.assessment ? ["assessment"] : []),
    ...(retained.provenance.confidence !== replay.provenance.confidence ? ["confidence"] : []),
    ...(retained.provenance.sourceLocator !== replay.provenance.sourceLocator ? ["sourceLocator"] : []),
    ...(retained.safety.synthetic !== replay.safety.synthetic ? ["synthetic"] : []),
  ].sort();
}

function sortedUnique(values: readonly string[]): string[] {
  return [...new Set(values)].sort();
}

function oneOrNull<T>(values: readonly T[]): T | null {
  const unique = [...new Set(values)];
  return unique.length === 1 ? unique[0] : null;
}

export function assertCanonicalCryptoRecordContract(value: unknown): asserts value is CanonicalCryptoRecordV1 {
  if (!isRecord(value) || !hasExactKeys(value, ["schemaVersion", "recordId", "canonicalAssetKey", "displayName", "estateClass", "issueTypes", "evidenceRefs", "correlation", "freshness", "review", "safety"])) {
    throw new Error("Canonical record rejected: invalid root contract");
  }
  if (value.schemaVersion !== "pqc.canonical-crypto-record.v1" || !isBoundedText(value.recordId, 167) || String(value.recordId).length < 8 || !SAFE_RECORD_ID.test(String(value.recordId)) || !isBoundedText(value.canonicalAssetKey, 160)) {
    throw new Error("Canonical record rejected: invalid identity fields");
  }
  if (value.displayName !== null && !isBoundedText(value.displayName, 160)) throw new Error("Canonical record rejected: invalid display name");
  if (value.estateClass !== null && !ESTATE_CLASSES.has(value.estateClass as SoftwareEstateClass)) throw new Error("Canonical record rejected: invalid estate class");
  if (!Array.isArray(value.issueTypes) || value.issueTypes.length < 1 || value.issueTypes.length > ISSUE_TYPES.size || new Set(value.issueTypes).size !== value.issueTypes.length || !value.issueTypes.every((item) => ISSUE_TYPES.has(item as CryptoIssueType))) {
    throw new Error("Canonical record rejected: invalid issue types");
  }
  if (!Array.isArray(value.evidenceRefs) || value.evidenceRefs.length < 1 || value.evidenceRefs.length > 100) throw new Error("Canonical record rejected: invalid evidence refs");
  const refValues = value.evidenceRefs.map(canonicalValue);
  if (new Set(refValues).size !== refValues.length || !value.evidenceRefs.every((item) => isRecord(item) && hasExactKeys(item, ["observationId", "feedId", "assessment"]) && typeof item.observationId === "string" && SAFE_IDENTIFIER.test(item.observationId) && FEED_IDS.has(item.feedId as EvidenceFeedId) && ASSESSMENTS.has(item.assessment as string))) {
    throw new Error("Canonical record rejected: invalid evidence refs");
  }
  if (!isRecord(value.correlation) || !hasExactKeys(value.correlation, ["status", "duplicateCount", "conflictFields"])) throw new Error("Canonical record rejected: invalid correlation");
  const correlation = value.correlation;
  if (!["correlated", "conflict", "unmatched"].includes(String(correlation.status)) || !Number.isInteger(correlation.duplicateCount) || Number(correlation.duplicateCount) < 0 || Number(correlation.duplicateCount) > 10000) throw new Error("Canonical record rejected: invalid correlation counts");
  if (!Array.isArray(correlation.conflictFields) || correlation.conflictFields.length > 50 || new Set(correlation.conflictFields).size !== correlation.conflictFields.length || !correlation.conflictFields.every((item) => typeof item === "string" && item.length <= 80 && SAFE_CONFLICT_FIELD.test(item))) throw new Error("Canonical record rejected: invalid conflict fields");
  if (correlation.status === "conflict" ? correlation.conflictFields.length < 1 : correlation.conflictFields.length !== 0) throw new Error("Canonical record rejected: status/conflict mismatch");
  if (value.displayName === null && (!isRecord(value.review) || value.review.required !== true)) throw new Error("Canonical record rejected: unresolved display name is not reviewable");
  if (value.estateClass === null && (!isRecord(value.review) || value.review.required !== true)) throw new Error("Canonical record rejected: unresolved estate class is not reviewable");
  if (value.displayName === null && correlation.status === "conflict" && !correlation.conflictFields.includes("displayName")) throw new Error("Canonical record rejected: display-name conflict is not declared");
  if (value.estateClass === null && correlation.status === "conflict" && !correlation.conflictFields.includes("estateClass")) throw new Error("Canonical record rejected: estate-class conflict is not declared");
  const feeds = new Set(value.evidenceRefs.map((item) => (item as Record<string, unknown>).feedId));
  if (correlation.status === "correlated" && (!feeds.has("initial-inventory") || feeds.size < 2)) throw new Error("Canonical record rejected: invalid correlation status");
  if (!isRecord(value.freshness) || !hasExactKeys(value.freshness, ["newestObservedAt", "stale"]) || (value.freshness.newestObservedAt !== null && !isCanonicalTimestamp(value.freshness.newestObservedAt)) || ![true, false, null].includes(value.freshness.stale as boolean | null)) throw new Error("Canonical record rejected: invalid freshness");
  if (!isRecord(value.review) || !hasExactKeys(value.review, ["required", "reasons"]) || typeof value.review.required !== "boolean" || !Array.isArray(value.review.reasons) || value.review.reasons.length > 20 || new Set(value.review.reasons).size !== value.review.reasons.length || !value.review.reasons.every((reason) => isBoundedText(reason, 200)) || ((correlation.status !== "correlated" || value.freshness.newestObservedAt === null || value.displayName === null || value.estateClass === null) && (!value.review.required || value.review.reasons.length < 1))) throw new Error("Canonical record rejected: invalid review");
  if (!isRecord(value.safety) || !hasExactKeys(value.safety, ["synthetic", "evidenceComposition", "containsSecret", "rawPayloadRetained"]) || typeof value.safety.synthetic !== "boolean" || !["synthetic_only", "mixed", "non_synthetic"].includes(String(value.safety.evidenceComposition)) || value.safety.synthetic !== (value.safety.evidenceComposition !== "non_synthetic") || value.safety.containsSecret !== false || value.safety.rawPayloadRetained !== false) throw new Error("Canonical record rejected: invalid safety");
}

function assertSourceReconciliationItem(value: unknown): asserts value is SourceReconciliationItemV1 {
  if (!isRecord(value) || !hasExactKeys(value, ["sourceIdentityRef", "feedId", "conflictFields", "variants", "review"]) || typeof value.sourceIdentityRef !== "string" || !SAFE_SOURCE_IDENTITY.test(value.sourceIdentityRef) || !FEED_IDS.has(value.feedId as EvidenceFeedId)) {
    throw new Error("Evidence reconciliation rejected: invalid identity fields");
  }
  if (!Array.isArray(value.conflictFields) || value.conflictFields.length < 1 || value.conflictFields.length > 50 || new Set(value.conflictFields).size !== value.conflictFields.length || !value.conflictFields.every((field) => typeof field === "string" && field.length <= 80 && SAFE_CONFLICT_FIELD.test(field))) {
    throw new Error("Evidence reconciliation rejected: invalid conflict fields");
  }
  if (!Array.isArray(value.variants) || value.variants.length < 2 || value.variants.length > 100) throw new Error("Evidence reconciliation rejected: invalid variants");
  if (!value.variants.every((variant, index) => isRecord(variant) && hasExactKeys(variant, ["replayOrdinal", "observationId", "feedId", "sourceIdentityRef", "conflictFields", "duplicateSubmissionCount", "trustedCanonicalContribution"]) && variant.replayOrdinal === index + 1 && typeof variant.observationId === "string" && SAFE_IDENTIFIER.test(variant.observationId) && variant.feedId === value.feedId && variant.sourceIdentityRef === value.sourceIdentityRef && Array.isArray(variant.conflictFields) && variant.conflictFields.length >= 1 && variant.conflictFields.length <= 50 && new Set(variant.conflictFields).size === variant.conflictFields.length && variant.conflictFields.every((field) => typeof field === "string" && field.length <= 80 && SAFE_CONFLICT_FIELD.test(field)) && Number.isInteger(variant.duplicateSubmissionCount) && Number(variant.duplicateSubmissionCount) >= 0 && Number(variant.duplicateSubmissionCount) <= 10000 && variant.trustedCanonicalContribution === false)) {
    throw new Error("Evidence reconciliation rejected: invalid variant");
  }
  if (!isRecord(value.review) || !hasExactKeys(value.review, ["required", "reasons"]) || value.review.required !== true || !Array.isArray(value.review.reasons) || value.review.reasons.length !== 1 || value.review.reasons[0] !== "Disputed source identity is excluded from canonical evidence") {
    throw new Error("Evidence reconciliation rejected: invalid review boundary");
  }
}

export function assertEvidenceFusionResultContract(value: unknown): asserts value is EvidenceFusionResultV1 {
  if (!isRecord(value) || !hasExactKeys(value, ["schemaVersion", "records", "sourceReconciliationQueue"]) || value.schemaVersion !== "pqc.evidence-fusion-result.v1" || !Array.isArray(value.records) || value.records.length > 100 || !Array.isArray(value.sourceReconciliationQueue) || value.sourceReconciliationQueue.length > 100) {
    throw new Error("Evidence fusion rejected: invalid result contract");
  }
  for (const record of value.records as unknown[]) assertCanonicalCryptoRecordContract(record);
  for (const item of value.sourceReconciliationQueue as unknown[]) assertSourceReconciliationItem(item);
  const typedResult = value as unknown as EvidenceFusionResultV1;
  if (new Set(typedResult.records.map((record) => record.recordId)).size !== typedResult.records.length || new Set(typedResult.sourceReconciliationQueue.map((item) => item.sourceIdentityRef)).size !== typedResult.sourceReconciliationQueue.length) {
    throw new Error("Evidence fusion rejected: duplicate result identity");
  }
  const canonicalObservationIds = new Set(typedResult.records.flatMap((record) => record.evidenceRefs.map((ref) => ref.observationId)));
  if (typedResult.sourceReconciliationQueue.some((item) => item.variants.some((variant) => canonicalObservationIds.has(variant.observationId)))) {
    throw new Error("Evidence fusion rejected: quarantined evidence entered a canonical record");
  }
}

export function fuseEvidenceObservations(
  observations: readonly EvidenceObservationV1[],
): EvidenceFusionResultV1 {
  const canonicalByObservationId = new Map<string, string>();
  for (const observation of observations) {
    assertEvidenceObservationContract(observation);
    const canonical = canonicalValue(observation);
    const prior = canonicalByObservationId.get(observation.observationId);
    if (prior !== undefined && prior !== canonical) throw new Error("Evidence observation rejected: observationId is not globally unique");
    canonicalByObservationId.set(observation.observationId, canonical);
  }

  const groupedBySource = new Map<string, EvidenceObservationV1[]>();
  for (const observation of observations) {
    const sourceKey = exactSourceKey(observation);
    groupedBySource.set(sourceKey, [...(groupedBySource.get(sourceKey) ?? []), observation]);
  }

  const retained: EvidenceObservationV1[] = [];
  const duplicateCounts = new Map<string, number>();
  const sourceReconciliationQueue: SourceReconciliationItemV1[] = [];

  for (const [, group] of [...groupedBySource.entries()].sort(([left], [right]) => left.localeCompare(right))) {
    const byCanonical = new Map<string, EvidenceObservationV1[]>();
    for (const observation of group) {
      const key = canonicalValue(observation);
      byCanonical.set(key, [...(byCanonical.get(key) ?? []), observation]);
    }
    const variants = [...byCanonical.entries()].sort(([left], [right]) => left.localeCompare(right));
    if (variants.length > 1) {
      const representatives = variants.map(([, items]) => [...items].sort((left, right) => left.observationId.localeCompare(right.observationId))[0]);
      const sourceIdentityRef = `source-identity:local:${String(sourceReconciliationQueue.length + 1).padStart(4, "0")}`;
      const conflictFields = sortedUnique(representatives.flatMap((left) => representatives.flatMap((right) => left === right ? [] : changedFields(left, right))));
      const item: SourceReconciliationItemV1 = {
        sourceIdentityRef,
        feedId: representatives[0].feedId,
        conflictFields,
        variants: representatives
          .sort((left, right) => left.observationId.localeCompare(right.observationId))
          .map((variant, index) => ({
            replayOrdinal: index + 1,
            observationId: variant.observationId,
            feedId: variant.feedId,
            sourceIdentityRef,
            conflictFields: sortedUnique(representatives.flatMap((other) => other === variant ? [] : changedFields(variant, other))),
            duplicateSubmissionCount: (byCanonical.get(canonicalValue(variant))?.length ?? 1) - 1,
            trustedCanonicalContribution: false,
          })),
        review: { required: true, reasons: ["Disputed source identity is excluded from canonical evidence"] },
      };
      assertSourceReconciliationItem(item);
      sourceReconciliationQueue.push(item);
      continue;
    }

    const retainedGroup = variants[0][1];
    const retainedObservation = [...retainedGroup].sort((left, right) => left.observationId.localeCompare(right.observationId))[0];
    retained.push(retainedObservation);
    const assetKey = canonicalizeKey(retainedObservation.subject.candidateKey);
    duplicateCounts.set(assetKey, (duplicateCounts.get(assetKey) ?? 0) + retainedGroup.length - 1);
  }

  const byAsset = new Map<string, EvidenceObservationV1[]>();
  for (const observation of retained) {
    const assetKey = canonicalizeKey(observation.subject.candidateKey);
    byAsset.set(assetKey, [...(byAsset.get(assetKey) ?? []), observation]);
  }

  const records = [...byAsset.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([assetKey, unsortedEvidence]) => {
    const evidence = [...unsortedEvidence].sort((left, right) => FEED_ORDER.indexOf(left.feedId) - FEED_ORDER.indexOf(right.feedId) || left.observationId.localeCompare(right.observationId));
    const seedEvidence = evidence.filter((item) => item.feedId === "initial-inventory");
    const enrichmentEvidence = evidence.filter((item) => item.feedId !== "initial-inventory");
    const authoritativeNames = sortedUnique(seedEvidence.flatMap((item) => item.subject.assetHint ? [item.subject.assetHint] : []));
    const contributorNames = sortedUnique(evidence.flatMap((item) => item.subject.assetHint ? [item.subject.assetHint] : []));
    const authoritativeEstates = sortedUnique(seedEvidence.map((item) => item.subject.estateClass));
    const contributorEstates = sortedUnique(evidence.map((item) => item.subject.estateClass));
    const displayName = seedEvidence.length ? oneOrNull(authoritativeNames) : oneOrNull(contributorNames);
    const estateClass = (seedEvidence.length ? oneOrNull(authoritativeEstates) : oneOrNull(contributorEstates)) as SoftwareEstateClass | null;
    const conflictFields = sortedUnique([
      ...(contributorNames.length > 1 ? ["displayName"] : []),
      ...(contributorEstates.length > 1 ? ["estateClass"] : []),
    ]);
    const hasSeed = seedEvidence.length > 0;
    const hasEnrichment = enrichmentEvidence.length > 0;
    const status = conflictFields.length ? "conflict" : hasSeed && hasEnrichment ? "correlated" : "unmatched";
    const observedTimes = evidence.flatMap((item) => item.source.collectedAt ? [item.source.collectedAt] : []).sort((left, right) => Date.parse(right) - Date.parse(left) || right.localeCompare(left));
    const newestObservedAt = observedTimes[0] ?? null;
    const syntheticCount = evidence.filter((item) => item.safety.synthetic).length;
    const nonSyntheticCount = evidence.filter((item) => !item.safety.synthetic).length;
    const evidenceComposition = syntheticCount > 0 && nonSyntheticCount > 0 ? "mixed" : syntheticCount > 0 ? "synthetic_only" : "non_synthetic";
    const reasons = sortedUnique([
      ...(!hasSeed ? ["Enrichment observation has no matching synthetic seed-inventory record"] : []),
      ...(hasSeed && !hasEnrichment ? ["Synthetic seed-inventory record has no modeled enrichment observation"] : []),
      ...(displayName === null ? ["Contributing observations do not establish one governed display name"] : []),
      ...(estateClass === null ? ["Contributing observations do not establish one governed estate class"] : []),
      ...(newestObservedAt === null ? ["No retained observation has a runtime collection timestamp; freshness is unknown"] : []),
      ...(evidence.some((item) => ["assumption", "unresolved"].includes(item.provenance.assessment)) ? ["One or more retained observations are assumptions or unresolved"] : []),
      ...(evidence.some((item) => ["low", "illustrative"].includes(item.provenance.confidence)) ? ["One or more retained observations have low or illustrative confidence"] : []),
    ]);

    const record: CanonicalCryptoRecordV1 = {
      schemaVersion: "pqc.canonical-crypto-record.v1",
      recordId: `record:${assetKey}`,
      canonicalAssetKey: assetKey,
      displayName,
      estateClass,
      issueTypes: sortedUnique(evidence.map((item) => item.classification.issueType)) as CryptoIssueType[],
      evidenceRefs: evidence.map((item) => ({ observationId: item.observationId, feedId: item.feedId, assessment: item.provenance.assessment })),
      correlation: { status, duplicateCount: duplicateCounts.get(assetKey) ?? 0, conflictFields },
      freshness: { newestObservedAt, stale: null },
      review: { required: reasons.length > 0 || status !== "correlated", reasons },
      safety: {
        synthetic: evidenceComposition !== "non_synthetic",
        evidenceComposition,
        containsSecret: false,
        rawPayloadRetained: false,
      },
    };
    assertCanonicalCryptoRecordContract(record);
    return record;
  });

  const result: EvidenceFusionResultV1 = {
    schemaVersion: "pqc.evidence-fusion-result.v1",
    records,
    sourceReconciliationQueue: sourceReconciliationQueue.sort((left, right) => left.sourceIdentityRef.localeCompare(right.sourceIdentityRef)),
  };
  assertEvidenceFusionResultContract(result);
  return result;
}
