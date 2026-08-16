import importRunSchema from "../../contracts/evidence-import-run.v1.schema.json";
import evidencePackageSchema from "../../contracts/migration-evidence-package.v1.schema.json";
import workItemSchema from "../../contracts/migration-work-item.v1.schema.json";
import snykSyntheticSarif from "../fixtures/snyk-code.synthetic.sarif.json";
import venafiSyntheticSearch from "../fixtures/venafi-certificate-search.synthetic.json";
import { SnykCodeSarifAdapter } from "../adapters/snykCodeSarif";
import { VenafiCertificateSearchAdapter } from "../adapters/venafiCertificateSearch";
import { assertEvidenceObservationContract } from "../domain/evidenceFusionCore";
import type { EvidenceImportContext, EvidenceImportRequest } from "../ports/evidenceIngestion";
import { RunMigrationSliceService } from "./runMigrationSlice";

const snykContext: EvidenceImportContext = {
  assetKey: "syn-sign-06",
  assetName: "Document Signing Service",
  estateClass: "source-code",
  collectedAt: null,
  sourceName: "snyk-code.synthetic.sarif.json",
  synthetic: true,
};

const venafiContext: EvidenceImportContext = {
  assetKey: "syn-api-edge-01",
  assetName: "Customer API Gateway",
  estateClass: "third-party-saas",
  collectedAt: null,
  sourceName: "venafi-certificate-search.synthetic.json",
  synthetic: true,
};

const defaultRequests: readonly EvidenceImportRequest[] = [
  { adapterId: "snyk-code-sarif", payload: snykSyntheticSarif, context: snykContext },
  { adapterId: "venafi-certificate-search", payload: venafiSyntheticSearch, context: venafiContext },
];

describe("local evidence adapters", () => {
  it("normalizes only crypto-relevant Snyk Code SARIF findings", () => {
    const result = SnykCodeSarifAdapter.adapt(snykSyntheticSarif, snykContext);

    expect(result).toMatchObject({
      schemaVersion: "pqc.evidence-import-run.v1",
      adapterId: "snyk-code-sarif",
      feedId: "sast",
      acceptedCount: 3,
      skippedCount: 1,
      safety: { synthetic: true, containsSecret: false, rawPayloadRetained: false },
    });
    expect(Object.keys(result).sort()).toEqual([...importRunSchema.required].sort());
    expect(result.observations.map((observation) => observation.classification.issueType)).toEqual([
      "source-code-crypto-use",
      "implementation-configuration",
      "cryptographic-dependency",
    ]);
    for (const observation of result.observations) {
      expect(() => assertEvidenceObservationContract(observation)).not.toThrow();
      expect(observation).toMatchObject({
        feedId: "sast",
        subject: { candidateKey: "syn-sign-06", estateClass: "source-code" },
        provenance: { assessment: "assumption", confidence: "illustrative" },
        safety: { synthetic: true, containsSecret: false, rawPayloadRetained: false },
      });
    }
  });

  it("normalizes a bounded Venafi search response into separate PKI evidence types", () => {
    const result = VenafiCertificateSearchAdapter.adapt(venafiSyntheticSearch, venafiContext);

    expect(result).toMatchObject({
      schemaVersion: "pqc.evidence-import-run.v1",
      adapterId: "venafi-certificate-search",
      feedId: "pki-inventory",
      acceptedCount: 6,
      skippedCount: 0,
      safety: { synthetic: true, containsSecret: false, rawPayloadRetained: false },
    });
    expect(new Set(result.observations.map((observation) => observation.classification.issueType))).toEqual(new Set([
      "certificate-trust",
      "algorithm-key-strength",
      "cryptographic-dependency",
    ]));
    expect(result.observations.every((observation) => observation.subject.candidateKey === "syn-api-edge-01")).toBe(true);
    expect(result.observations.every((observation) => observation.safety.rawPayloadRetained === false)).toBe(true);
  });

  it("fails closed on invalid formats and correlation context", () => {
    expect(() => SnykCodeSarifAdapter.adapt({ version: "2.0.0", runs: [] }, snykContext)).toThrow("SARIF 2.1.0");
    expect(() => VenafiCertificateSearchAdapter.adapt({ certificates: [] }, { ...venafiContext, collectedAt: "2026-08-16T10:00:00-06:00" })).toThrow("canonical UTC timestamp");
    expect(() => VenafiCertificateSearchAdapter.adapt({ unknown: [] }, venafiContext)).toThrow("must contain a certificates");
  });

  it("marks user-selected files as non-synthetic without elevating source evidence to runtime proof", () => {
    const result = SnykCodeSarifAdapter.adapt(snykSyntheticSarif, {
      ...snykContext,
      collectedAt: "2026-08-16T16:00:00Z",
      sourceName: "local-scan.sarif.json",
      synthetic: false,
    });

    expect(result.safety.synthetic).toBe(false);
    expect(result.sourceName).toBe("local-snyk-code-sarif");
    expect(result.observations.every((observation) => observation.provenance.assessment === "unresolved")).toBe(true);
    expect(result.observations.every((observation) => observation.provenance.confidence === "low")).toBe(true);
    expect(result.observations.every((observation) => observation.subject.assetHint === null)).toBe(true);
    expect(result.observations.every((observation) => observation.source.collectedAt === "2026-08-16T16:00:00Z")).toBe(true);
  });

  it("rejects the wrong SARIF producer and skips certificate rows without identity", () => {
    const run = snykSyntheticSarif.runs[0];
    const wrongProducer = {
      ...snykSyntheticSarif,
      runs: [{ ...run, tool: { driver: { ...run.tool.driver, name: "Generic Analyzer" } } }],
    };
    expect(() => SnykCodeSarifAdapter.adapt(wrongProducer, snykContext)).toThrow("does not identify a Snyk producer");

    const result = VenafiCertificateSearchAdapter.adapt({ certificates: [{}] }, venafiContext);
    expect(result).toMatchObject({ acceptedCount: 0, skippedCount: 1 });
    expect(result.diagnostics).toContainEqual(expect.objectContaining({ code: "invalid-certificate" }));
  });

  it("rejects more certificate rows than one bounded import can normalize", () => {
    const certificates = Array.from({ length: 31 }, (_, index) => ({ id: `synthetic-certificate-${index + 1}` }));
    expect(() => VenafiCertificateSearchAdapter.adapt({ certificates }, venafiContext)).toThrow("30-certificate safety limit");
  });
});

describe("governed migration slice", () => {
  it("runs both adapters through fusion and emits closed proposal-only contracts", () => {
    const result = new RunMigrationSliceService().execute(defaultRequests);

    expect(Object.keys(result).sort()).toEqual([...evidencePackageSchema.required].sort());
    expect(result.packageId).toMatch(/^migration-package:[a-f0-9]{16}$/);
    expect(result.summary).toEqual({
      adapterRuns: 2,
      acceptedObservations: 9,
      skippedNativeRecords: 1,
      canonicalCandidates: 2,
      proposedWorkItems: 2,
      reviewRequired: 2,
    });
    expect(result.fusion.records.map((record) => record.canonicalAssetKey).sort()).toEqual([
      "syn-api-edge-01",
      "syn-sign-06",
    ]);
    expect(result.workItems).toHaveLength(2);
    for (const item of result.workItems) {
      expect(Object.keys(item).sort()).toEqual([...workItemSchema.required].sort());
      expect(item).toMatchObject({
        stage: "Risk Assessment & Planning",
        state: "proposed",
        review: { required: true, approvalRecorded: false },
      });
      expect(item.authorityGates).toHaveLength(3);
      expect(item.validationRequirements).toHaveLength(3);
    }
    expect(result.assurance).toEqual({
      rawPayloadRetained: false,
      containsSecret: false,
      automaticChangeAuthorized: false,
      limitation: expect.stringContaining("does not prove runtime behavior"),
    });
  });

  it("is deterministic for the same inputs and changes identity when correlation scope changes", () => {
    const service = new RunMigrationSliceService();
    const first = service.execute(defaultRequests);
    const replay = service.execute(defaultRequests);
    const changedScope = service.execute([
      { ...defaultRequests[0], context: { ...snykContext, assetKey: "syn-archive-10", assetName: "Research Archive Encryptor" } },
      defaultRequests[1],
    ]);

    expect(replay).toEqual(first);
    expect(changedScope.packageId).not.toBe(first.packageId);
  });

  it("withholds adversarial native fields and never manufactures actuation authority", () => {
    const sentinels = {
      privateKey: "sentinel-private-key-must-not-survive",
      token: "sentinel-token-must-not-survive",
      tool: "sentinel-tool-must-not-survive",
      rule: "sentinel-rule-must-not-survive",
      message: "sentinel-message-must-not-survive",
      path: "sentinel-path-must-not-survive",
      snykFile: "sentinel-snyk-filename-must-not-survive",
      certificateId: "sentinel-certificate-id-must-not-survive",
      subject: "sentinel-subject-must-not-survive",
      issuer: "sentinel-issuer-must-not-survive",
      algorithm: "sentinel-algorithm-must-not-survive",
      venafiFile: "sentinel-venafi-filename-must-not-survive",
    } as const;
    const nativePayload = {
      version: "2.1.0",
      privateKey: sentinels.privateKey,
      credentials: { token: sentinels.token },
      runs: [{
        tool: {
          driver: {
            name: `Snyk Code ${sentinels.tool}`,
            rules: [{
              id: `rsa-${sentinels.rule}`,
              shortDescription: { text: `RSA ${sentinels.rule}` },
            }],
          },
        },
        results: [{
          ruleId: `rsa-${sentinels.rule}`,
          level: "warning",
          message: { text: `RSA ${sentinels.message}` },
          locations: [{
            physicalLocation: {
              artifactLocation: { uri: `src/${sentinels.path}.ts` },
              region: { startLine: 7 },
            },
          }],
        }],
      }],
    };
    const certificatePayload = {
      certificates: [{
        id: sentinels.certificateId,
        subject: sentinels.subject,
        issuer: sentinels.issuer,
        keyAlgorithm: `RSA ${sentinels.algorithm}`,
        keySize: 2048,
        signatureAlgorithm: `SHA256withRSA ${sentinels.algorithm}`,
        instanceCount: 1,
        managed: true,
      }],
    };
    const result = new RunMigrationSliceService().execute([
      {
        adapterId: "snyk-code-sarif",
        payload: nativePayload,
        context: {
          ...snykContext,
          collectedAt: "2026-08-16T16:00:00Z",
          sourceName: sentinels.snykFile,
          synthetic: false,
        },
      },
      {
        adapterId: "venafi-certificate-search",
        payload: certificatePayload,
        context: {
          ...venafiContext,
          collectedAt: "2026-08-16T16:00:00Z",
          sourceName: sentinels.venafiFile,
          synthetic: false,
        },
      },
    ]);
    const serialized = JSON.stringify(result);

    for (const sentinel of Object.values(sentinels)) expect(serialized).not.toContain(sentinel);
    expect(serialized).not.toContain("privateKey");
    expect(result.importRuns.map((run) => run.sourceName)).toEqual([
      "local-snyk-code-sarif",
      "local-venafi-certificate-search",
    ]);
    expect(result.importRuns.flatMap((run) => run.observations).every((observation) => (
      observation.provenance.assessment === "unresolved"
      && observation.provenance.confidence === "low"
      && observation.subject.assetHint === null
    ))).toBe(true);
    expect(result.workItems.every((item) => item.review.approvalRecorded === false)).toBe(true);
    expect(result.assurance.automaticChangeAuthorized).toBe(false);
  });

  it("rejects empty, excessive, or unregistered import runs", () => {
    const service = new RunMigrationSliceService();
    expect(() => service.execute([])).toThrow("At least one evidence import");
    expect(() => service.execute(Array.from({ length: 11 }, () => defaultRequests[0]))).toThrow("at most ten imports");
    expect(() => new RunMigrationSliceService([]).execute(defaultRequests.slice(0, 1))).toThrow("No evidence adapter is registered");
  });

  it("bounds combined normalized evidence per correlation target before fusion", () => {
    const result = snykSyntheticSarif.runs[0].results[0];
    const excessiveSarif = {
      ...snykSyntheticSarif,
      runs: [{
        ...snykSyntheticSarif.runs[0],
        results: Array.from({ length: 91 }, (_, index) => ({
          ...result,
          message: { text: `RSA signing fixture ${index + 1}.` },
        })),
      }],
    };

    expect(() => new RunMigrationSliceService().execute([
      { adapterId: "snyk-code-sarif", payload: excessiveSarif, context: snykContext },
    ])).toThrow("90-observation local safety limit");
  });
});
