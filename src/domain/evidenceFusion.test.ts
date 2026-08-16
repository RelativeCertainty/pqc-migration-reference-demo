import canonicalRecordSchema from "../../contracts/canonical-crypto-record.v1.schema.json";
import evidenceObservationSchema from "../../contracts/evidence-observation.v1.schema.json";
import fusionResultConformance from "../../contracts/evidence-fusion-result.v1.example.json";
import {
  adaptSyntheticFeedFixtures,
  CmdbAdapter,
  EVIDENCE_FUSION_FEEDS,
  EVIDENCE_FUSION_VIEW,
  ExtraHopAdapter,
  InitialInventoryAdapter,
  PkiInventoryAdapter,
  SastAdapter,
  VulnerabilityManagerAdapter,
  type EvidenceObservationV1,
} from "./evidenceFusion";
import {
  assertCanonicalCryptoRecordContract,
  assertEvidenceObservationContract,
  assertEvidenceFusionResultContract,
  fuseEvidenceObservations,
} from "./evidenceFusionCore";

const seedFixture = {
  rowRef: "seed-001",
  assetKey: "asset-001",
  assetName: "Synthetic Service",
  estateClass: "source-code" as const,
  issueType: "cryptographic-dependency" as const,
  assertion: "Synthetic initial inventory stand-in.",
};

const scannerFixture = {
  pluginRef: "scanner-001",
  assetKey: "asset-001",
  assetName: "Synthetic Service",
  estateClass: "source-code" as const,
  issueType: "algorithm-key-strength" as const,
  finding: "Synthetic non-TLS algorithm and key-strength finding.",
};

describe("evidence fusion ports and adapters", () => {
  it("exposes six named inbound adapters that emit the closed v1 neutral contract", () => {
    const outputs = [
      InitialInventoryAdapter.adapt(seedFixture),
      ExtraHopAdapter.adapt({ flowRef: "flow-001", endpointKey: "asset-001", endpointName: "Synthetic Service", estateClass: "source-code", issueType: "tls-protocol", observation: "Synthetic TLS observation." }),
      VulnerabilityManagerAdapter.adapt(scannerFixture),
      PkiInventoryAdapter.adapt({ certificateRef: "cert-001", relyingPartyKey: "asset-001", relyingPartyName: "Synthetic Service", estateClass: "source-code", issueType: "certificate-trust", certificateFact: "Synthetic certificate observation." }),
      SastAdapter.adapt({ resultRef: "sast-001", repositoryAssetKey: "asset-001", applicationName: "Synthetic Service", estateClass: "source-code", issueType: "source-code-crypto-use", codeFact: "Synthetic source observation." }),
      CmdbAdapter.adapt({ ciRef: "ci-001", correlationKey: "asset-001", ciName: "Synthetic Service", estateClass: "source-code", issueType: "cryptographic-dependency", contextFact: "Synthetic CMDB observation." }),
    ];
    expect(outputs.map((observation) => observation.feedId)).toEqual(evidenceObservationSchema.$defs.feedId.enum);

    for (const observation of outputs) {
      expect(() => assertEvidenceObservationContract(observation)).not.toThrow();
      expect(Object.keys(observation).sort()).toEqual([...evidenceObservationSchema.required].sort());
      expect(observation).toMatchObject({
        schemaVersion: "pqc.evidence-observation.v1",
        feedId: observation.feedId,
        adapter: { version: "1.0.0" },
        source: { collectedAt: null },
        provenance: { assessment: "assumption", confidence: "illustrative" },
        safety: { synthetic: true, containsSecret: false, rawPayloadRetained: false },
      });
    }
  });

  it("keeps five read-only enrichment feeds while exposing two local import adapters", () => {
    expect(EVIDENCE_FUSION_FEEDS).toHaveLength(5);
    expect(EVIDENCE_FUSION_FEEDS.map((feed) => feed.id)).toEqual([
      "extrahop-internet-tls",
      "vulnerability-manager",
      "pki-inventory",
      "sast",
      "cmdb",
    ]);
    expect(EVIDENCE_FUSION_FEEDS.filter((feed) => feed.status === "LOCAL IMPORT ADAPTER").map((feed) => feed.id)).toEqual([
      "pki-inventory",
      "sast",
    ]);
    expect(EVIDENCE_FUSION_FEEDS.filter((feed) => feed.status === "MODELED · NOT CONNECTED")).toHaveLength(3);
    expect(EVIDENCE_FUSION_FEEDS.every((feed) => feed.authorityBoundary.length > 20)).toBe(true);
    expect(EVIDENCE_FUSION_FEEDS.find((feed) => feed.id === "vulnerability-manager")?.signals).toEqual(
      expect.arrayContaining(["SSL plugin findings", "Crypto-relevant CVEs"]),
    );
  });

  it("bootstraps ten synthetic seeds and keeps honest correlation, conflict, unmatched, and dedupe counts", () => {
    const observations = adaptSyntheticFeedFixtures();
    expect(observations.every((observation) => observation.safety.synthetic)).toBe(true);
    expect(EVIDENCE_FUSION_VIEW).toMatchObject({
      seedAssetCount: 10,
      seedObservationCount: 36,
      rawEnrichmentObservationCount: 12,
      uniqueEnrichmentEvidenceCount: 11,
      exactDuplicateCount: 1,
      sourceReconciliationCount: 0,
      candidateCount: 11,
      correlatedCount: 2,
      conflictCount: 1,
      unmatchedCount: 8,
      reviewQueueCount: 11,
    });

    const seedOnly = EVIDENCE_FUSION_VIEW.records.find((record) => record.canonicalAssetKey === "syn-ca-04");
    expect(seedOnly?.correlation.status).toBe("unmatched");
    expect(seedOnly?.review.reasons).toContain("Synthetic seed-inventory record has no modeled enrichment observation");

    const enrichmentOnly = EVIDENCE_FUSION_VIEW.records.find((record) => record.canonicalAssetKey === "orphan-service-77");
    expect(enrichmentOnly?.correlation.status).toBe("unmatched");
    expect(enrichmentOnly?.review.reasons).toContain("Enrichment observation has no matching synthetic seed-inventory record");

    const conflict = EVIDENCE_FUSION_VIEW.records.find((record) => record.canonicalAssetKey === "syn-pay-java-02");
    expect(conflict?.correlation).toMatchObject({
      status: "conflict",
      duplicateCount: 1,
      conflictFields: ["displayName", "estateClass"],
    });
    expect(conflict?.freshness).toEqual({ newestObservedAt: null, stale: null });
  });

  it("deduplicates only structurally identical observations from the same feed and native record", () => {
    const seed = InitialInventoryAdapter.adapt(seedFixture);
    const first = VulnerabilityManagerAdapter.adapt(scannerFixture);
    const identical = VulnerabilityManagerAdapter.adapt(scannerFixture);
    const [record] = fuseEvidenceObservations([seed, first, identical]).records;

    expect(record.correlation).toMatchObject({ status: "correlated", duplicateCount: 1, conflictFields: [] });
    expect(record.evidenceRefs).toHaveLength(2);
  });

  it("treats semantically identical closed-contract objects as duplicates regardless of key order", () => {
    const seed = InitialInventoryAdapter.adapt(seedFixture);
    const first = VulnerabilityManagerAdapter.adapt(scannerFixture);
    const reordered: EvidenceObservationV1 = {
      safety: {
        rawPayloadRetained: first.safety.rawPayloadRetained,
        containsSecret: first.safety.containsSecret,
        synthetic: first.safety.synthetic,
      },
      provenance: {
        sourceLocator: first.provenance.sourceLocator,
        confidence: first.provenance.confidence,
        assessment: first.provenance.assessment,
      },
      finding: { fact: first.finding.fact },
      classification: { issueType: first.classification.issueType },
      subject: {
        estateClass: first.subject.estateClass,
        assetHint: first.subject.assetHint,
        candidateKey: first.subject.candidateKey,
      },
      source: { collectedAt: first.source.collectedAt, recordRef: first.source.recordRef },
      adapter: { version: first.adapter.version, name: first.adapter.name },
      feedId: first.feedId,
      observationId: first.observationId,
      schemaVersion: first.schemaVersion,
    };
    const [record] = fuseEvidenceObservations([seed, first, reordered]).records;

    expect(record.correlation).toMatchObject({ status: "correlated", duplicateCount: 1, conflictFields: [] });
  });

  it("derives canonical synthetic status from every contribution", () => {
    const seed = InitialInventoryAdapter.adapt(seedFixture);
    const syntheticEnrichment = VulnerabilityManagerAdapter.adapt(scannerFixture);
    const nonSyntheticContractExample: EvidenceObservationV1 = {
      ...syntheticEnrichment,
      observationId: "obs:vulnerability-manager:scanner-real-002",
      source: { recordRef: "scanner-real-002", collectedAt: "2026-08-13T12:00:00Z" },
      provenance: {
        assessment: "verified",
        confidence: "high",
        sourceLocator: "approved-connector-record:scanner-real-002",
      },
      safety: { synthetic: false, containsSecret: false, rawPayloadRetained: false },
    };

    const [mixed] = fuseEvidenceObservations([seed, nonSyntheticContractExample]).records;
    const [onlyNonSynthetic] = fuseEvidenceObservations([nonSyntheticContractExample]).records;
    expect(mixed.safety).toEqual({ synthetic: true, evidenceComposition: "mixed", containsSecret: false, rawPayloadRetained: false });
    expect(onlyNonSynthetic.safety).toEqual({ synthetic: false, evidenceComposition: "non_synthetic", containsSecret: false, rawPayloadRetained: false });
  });

  it("retains the newest known collection time without inventing a staleness policy", () => {
    const base = VulnerabilityManagerAdapter.adapt(scannerFixture);
    const older: EvidenceObservationV1 = {
      ...base,
      observationId: "obs:vulnerability-manager:scanner-older",
      source: { recordRef: "scanner-older", collectedAt: "2026-08-11T12:00:00Z" },
      provenance: { assessment: "verified", confidence: "high", sourceLocator: "approved-connector-record:scanner-older" },
      safety: { synthetic: false, containsSecret: false, rawPayloadRetained: false },
    };
    const newer: EvidenceObservationV1 = {
      ...base,
      observationId: "obs:vulnerability-manager:scanner-newer",
      source: { recordRef: "scanner-newer", collectedAt: "2026-08-13T12:00:00Z" },
      provenance: { assessment: "verified", confidence: "high", sourceLocator: "approved-connector-record:scanner-newer" },
      safety: { synthetic: false, containsSecret: false, rawPayloadRetained: false },
    };

    const [record] = fuseEvidenceObservations([newer, older]).records;
    expect(record.freshness).toEqual({ newestObservedAt: "2026-08-13T12:00:00Z", stale: null });
  });

  it("excludes every variant of a disputed source identity from canonical evidence", () => {
    const seed = InitialInventoryAdapter.adapt(seedFixture);
    const first = VulnerabilityManagerAdapter.adapt(scannerFixture);
    const divergent: EvidenceObservationV1 = {
      ...VulnerabilityManagerAdapter.adapt({ ...scannerFixture, finding: "Different synthetic content under the same native reference." }),
      observationId: "obs:vulnerability-manager:scanner-001-replay",
    };
    const result = fuseEvidenceObservations([seed, first, divergent]);
    const [record] = result.records;

    expect(record.correlation).toMatchObject({ status: "unmatched", duplicateCount: 0, conflictFields: [] });
    expect(record.evidenceRefs.map((ref) => ref.observationId)).toEqual([seed.observationId]);
    expect(result.sourceReconciliationQueue).toHaveLength(1);
    expect(result.sourceReconciliationQueue[0]).toMatchObject({
      conflictFields: expect.arrayContaining(["sourceRecord", "finding"]),
      review: { required: true, reasons: ["Disputed source identity is excluded from canonical evidence"] },
    });
    expect(result.sourceReconciliationQueue[0].variants).toHaveLength(2);
    expect(result.sourceReconciliationQueue[0].variants.every((variant) => variant.trustedCanonicalContribution === false)).toBe(true);
  });

  it("keeps a disputed candidate key only in bounded source reconciliation metadata", () => {
    const seed = InitialInventoryAdapter.adapt(seedFixture);
    const first = VulnerabilityManagerAdapter.adapt(scannerFixture);
    const divergent: EvidenceObservationV1 = {
      ...VulnerabilityManagerAdapter.adapt({
        ...scannerFixture,
        assetKey: "different-asset-999",
        estateClass: "ots-cots",
        finding: "Divergent synthetic replay.",
      }),
      observationId: "obs:vulnerability-manager:scanner-001-other-asset",
    };
    const result = fuseEvidenceObservations([seed, first, divergent]);

    expect(result.records).toHaveLength(1);
    expect(result.records[0].canonicalAssetKey).toBe("asset-001");
    expect(result.records[0].evidenceRefs).toHaveLength(1);
    expect(result.sourceReconciliationQueue[0].conflictFields).toEqual(expect.arrayContaining(["sourceRecord", "candidateKey", "estateClass", "finding"]));
    expect(JSON.stringify(result.sourceReconciliationQueue)).not.toContain("different-asset-999");
  });

  it("quarantines every divergent replay without projecting its native source locator", () => {
    const seed = InitialInventoryAdapter.adapt(seedFixture);
    const base = VulnerabilityManagerAdapter.adapt(scannerFixture);
    const nativeLocator = "https://private.example.invalid/native/path?identity=withheld";
    const first: EvidenceObservationV1 = {
      ...base,
      observationId: "obs:vulnerability-manager:replay-a",
      source: { ...base.source, recordRef: nativeLocator },
    };
    const second: EvidenceObservationV1 = {
      ...first,
      observationId: "obs:vulnerability-manager:replay-b",
      finding: { fact: "Divergent replay B." },
    };
    const third: EvidenceObservationV1 = {
      ...first,
      observationId: "obs:vulnerability-manager:replay-c",
      finding: { fact: "Divergent replay C." },
    };

    const result = fuseEvidenceObservations([third, seed, first, { ...first }, second]);
    const [queueItem] = result.sourceReconciliationQueue;

    expect(queueItem.variants).toHaveLength(3);
    expect(queueItem.variants.map((item) => item.replayOrdinal)).toEqual([1, 2, 3]);
    expect(queueItem.variants.every((item) => item.sourceIdentityRef === queueItem.sourceIdentityRef)).toBe(true);
    expect(queueItem.variants.find((item) => item.observationId === first.observationId)?.duplicateSubmissionCount).toBe(1);
    expect(queueItem.variants.every((item) => item.trustedCanonicalContribution === false)).toBe(true);
    expect(JSON.stringify(result)).not.toContain(nativeLocator);
  });

  it("is permutation invariant and leaves unseeded disputed canonical fields unresolved", () => {
    const extraHop = ExtraHopAdapter.adapt({
      flowRef: "unseeded-flow",
      endpointKey: "unseeded-asset",
      endpointName: "Network hint",
      estateClass: "third-party-saas",
      issueType: "tls-protocol",
      observation: "Synthetic traffic hint.",
    });
    const cmdb = CmdbAdapter.adapt({
      ciRef: "unseeded-ci",
      correlationKey: "unseeded-asset",
      ciName: "CMDB hint",
      estateClass: "ots-cots",
      issueType: "vendor-control",
      contextFact: "Synthetic CMDB correlation hint.",
    });
    const forward = fuseEvidenceObservations([extraHop, cmdb]);
    const reverse = fuseEvidenceObservations([cmdb, extraHop]);

    expect(reverse).toEqual(forward);
    expect(forward.records[0]).toMatchObject({ displayName: null, estateClass: null });
    expect(forward.records[0].correlation).toMatchObject({
      status: "conflict",
      conflictFields: ["displayName", "estateClass"],
    });

    const fixtures = adaptSyntheticFeedFixtures();
    expect(fuseEvidenceObservations([...fixtures].reverse())).toEqual(fuseEvidenceObservations(fixtures));
  });

  it("preserves cross-feed corroboration even when native references match", () => {
    const seed = InitialInventoryAdapter.adapt(seedFixture);
    const extraHop = ExtraHopAdapter.adapt({ flowRef: "shared-001", endpointKey: "asset-001", endpointName: "Synthetic Service", estateClass: "source-code", issueType: "tls-protocol", observation: "Synthetic TLS observation." });
    const pki = PkiInventoryAdapter.adapt({ certificateRef: "shared-001", relyingPartyKey: "asset-001", relyingPartyName: "Synthetic Service", estateClass: "source-code", issueType: "certificate-trust", certificateFact: "Synthetic certificate observation." });
    const [record] = fuseEvidenceObservations([seed, extraHop, pki]).records;

    expect(record.correlation).toMatchObject({ status: "correlated", duplicateCount: 0 });
    expect(record.evidenceRefs.map((item) => item.feedId)).toEqual([
      "initial-inventory",
      "extrahop-internet-tls",
      "pki-inventory",
    ]);
  });

  it("rejects unsafe or malformed contract values without echoing their content", () => {
    const valid = VulnerabilityManagerAdapter.adapt(scannerFixture);
    const adversarial: unknown[] = [
      { ...valid, safety: { ...valid.safety, containsSecret: true } },
      { ...valid, unexpectedNativePayload: { token: "must-not-enter-core" } },
      { ...valid, finding: { fact: "line one\nline two" } },
      { ...valid, subject: { ...valid.subject, candidateKey: "   " } },
      { ...valid, source: { ...valid.source, recordRef: "   " } },
      { ...valid, source: { ...valid.source, collectedAt: "2026-08-13T12:00:00Z" } },
      { ...valid, adapter: { ...valid.adapter, version: "١.٠.٠" } },
    ];

    for (const value of adversarial) {
      expect(() => fuseEvidenceObservations([value as EvidenceObservationV1])).toThrow(/^Evidence observation rejected:/);
    }
  });

  it("rejects a reused observationId when any canonical observation field differs", () => {
    const first = VulnerabilityManagerAdapter.adapt(scannerFixture);
    const sameFeedMutation: EvidenceObservationV1 = {
      ...first,
      finding: { fact: "Changed content under a reused observation ID." },
    };
    const crossFeedMutation: EvidenceObservationV1 = {
      ...first,
      feedId: "cmdb",
      adapter: { name: "cmdb-adapter", version: "1.0.0" },
    };

    for (const mutation of [sameFeedMutation, crossFeedMutation]) {
      expect(() => fuseEvidenceObservations([first, mutation])).toThrow(
        "Evidence observation rejected: observationId is not globally unique",
      );
    }
    expect(() => fuseEvidenceObservations([first, { ...first }])).not.toThrow();
  });

  it("reports every mutable disputed source field without trusting a variant", () => {
    const first = VulnerabilityManagerAdapter.adapt(scannerFixture);
    const adapterVariant: EvidenceObservationV1 = {
      ...first,
      observationId: "obs:vulnerability-manager:adapter-replay",
      adapter: { ...first.adapter, version: "1.0.1" },
    };
    const provenanceVariant: EvidenceObservationV1 = {
      ...first,
      observationId: "obs:vulnerability-manager:provenance-replay",
      provenance: {
        assessment: "probable",
        confidence: "moderate",
        sourceLocator: "approved-connector-record:provenance-replay",
      },
      safety: { ...first.safety, synthetic: false },
    };

    const result = fuseEvidenceObservations([first, adapterVariant, provenanceVariant]);
    expect(result.records).toHaveLength(0);
    expect(result.sourceReconciliationQueue[0].conflictFields).toEqual(expect.arrayContaining([
      "observationId",
      "adapterVersion",
      "assessment",
      "confidence",
      "sourceLocator",
      "synthetic",
    ]));
    expect(result.sourceReconciliationQueue[0].variants.every((variant) => variant.trustedCanonicalContribution === false)).toBe(true);
  });

  it("keeps the runtime output assertion aligned with the closed canonical contract", () => {
    const record = EVIDENCE_FUSION_VIEW.records[0];
    expect(() => assertCanonicalCryptoRecordContract(record)).not.toThrow();
    expect(() => assertCanonicalCryptoRecordContract({ ...record, rawPayload: { unsafe: true } })).toThrow(
      /^Canonical record rejected:/,
    );
    expect(() => assertCanonicalCryptoRecordContract({
      ...record,
      safety: { ...record.safety, evidenceComposition: "non_synthetic" },
    })).toThrow(/^Canonical record rejected:/);
    expect(() => assertCanonicalCryptoRecordContract({ ...record, recordId: "record:" })).toThrow(/^Canonical record rejected:/);
    expect(() => assertCanonicalCryptoRecordContract({
      ...record,
      correlation: { status: "conflict", duplicateCount: 0, conflictFields: Array.from({ length: 51 }, (_, index) => `field${index}`) },
    })).toThrow(/^Canonical record rejected:/);
    expect(() => assertCanonicalCryptoRecordContract({
      ...record,
      correlation: { status: "conflict", duplicateCount: 0, conflictFields: ["a".repeat(81)] },
    })).toThrow(/^Canonical record rejected:/);
    const correlated = EVIDENCE_FUSION_VIEW.records.find((item) => item.correlation.status === "correlated");
    expect(correlated).toBeDefined();
    expect(() => assertCanonicalCryptoRecordContract({
      ...correlated,
      displayName: null,
      freshness: { newestObservedAt: "2026-08-13T12:00:00Z", stale: false },
      review: { required: true, reasons: [] },
    })).toThrow(/^Canonical record rejected:/);
  });

  it("exposes a closed versioned fusion-result contract", () => {
    const result = fuseEvidenceObservations(adaptSyntheticFeedFixtures());
    expect(result.schemaVersion).toBe("pqc.evidence-fusion-result.v1");
    expect(() => assertEvidenceFusionResultContract(result)).not.toThrow();
    expect(() => assertEvidenceFusionResultContract({ ...result, rawNativePayload: true })).toThrow(/^Evidence fusion rejected:/);
  });

  it("matches the schema-validated cross-language conformance vector", () => {
    const actual = fuseEvidenceObservations([
      CmdbAdapter.adapt({
        ciRef: "ci-503",
        correlationKey: "orphan-service-77",
        ciName: null,
        estateClass: "ots-cots",
        issueType: "cryptographic-dependency",
        contextFact: "Synthetic CI cannot yet be correlated to the seed inventory.",
      }),
    ]);
    expect(actual).toEqual(fusionResultConformance);
  });

  it("keeps outbound records aligned to the canonical contract surface", () => {
    for (const record of EVIDENCE_FUSION_VIEW.records) {
      expect(Object.keys(record).sort()).toEqual([...canonicalRecordSchema.required].sort());
      expect(canonicalRecordSchema.$defs.estateClass.enum).toContain(record.estateClass);
      expect(record.issueTypes.every((type) => canonicalRecordSchema.$defs.issueType.enum.includes(type))).toBe(true);
      expect(record.evidenceRefs.every((ref) => evidenceObservationSchema.$defs.feedId.enum.includes(ref.feedId))).toBe(true);
      if (record.correlation.status === "correlated") expect(record.correlation.conflictFields).toEqual([]);
    }
  });
});
