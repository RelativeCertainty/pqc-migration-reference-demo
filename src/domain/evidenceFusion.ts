import { CRYPTO_SYSTEMS } from "./data";
import { fuseEvidenceObservations } from "./evidenceFusionCore";
import type {
  CryptoIssueType,
  SoftwareEstateClass,
} from "./model";

export type EvidenceFeedId =
  | "initial-inventory"
  | "extrahop-internet-tls"
  | "vulnerability-manager"
  | "pki-inventory"
  | "sast"
  | "cmdb";

export interface EvidenceObservationV1 {
  readonly schemaVersion: "pqc.evidence-observation.v1";
  readonly observationId: string;
  readonly feedId: EvidenceFeedId;
  readonly adapter: { readonly name: string; readonly version: string };
  readonly source: { readonly recordRef: string; readonly collectedAt: string | null };
  readonly subject: {
    readonly candidateKey: string;
    readonly assetHint: string | null;
    readonly estateClass: SoftwareEstateClass;
  };
  readonly classification: { readonly issueType: CryptoIssueType };
  readonly finding: { readonly fact: string };
  readonly provenance: {
    readonly assessment: "verified" | "partially-verified" | "probable" | "assumption" | "unresolved";
    readonly confidence: "high" | "moderate" | "low" | "illustrative";
    readonly sourceLocator: string;
  };
  readonly safety: {
    readonly synthetic: boolean;
    readonly containsSecret: false;
    readonly rawPayloadRetained: false;
  };
}

export interface CanonicalCryptoRecordV1 {
  readonly schemaVersion: "pqc.canonical-crypto-record.v1";
  readonly recordId: string;
  readonly canonicalAssetKey: string;
  readonly displayName: string | null;
  readonly estateClass: SoftwareEstateClass | null;
  readonly issueTypes: readonly CryptoIssueType[];
  readonly evidenceRefs: readonly {
    readonly observationId: string;
    readonly feedId: EvidenceFeedId;
    readonly assessment: EvidenceObservationV1["provenance"]["assessment"];
  }[];
  readonly correlation: {
    readonly status: "correlated" | "conflict" | "unmatched";
    readonly duplicateCount: number;
    readonly conflictFields: readonly string[];
  };
  readonly freshness: { readonly newestObservedAt: string | null; readonly stale: boolean | null };
  readonly review: { readonly required: boolean; readonly reasons: readonly string[] };
  readonly safety: {
    readonly synthetic: boolean;
    readonly evidenceComposition: "synthetic_only" | "mixed" | "non_synthetic";
    readonly containsSecret: false;
    readonly rawPayloadRetained: false;
  };
}

export interface SourceReconciliationItemV1 {
  readonly sourceIdentityRef: string;
  readonly feedId: EvidenceFeedId;
  readonly conflictFields: readonly string[];
  readonly variants: readonly {
    readonly replayOrdinal: number;
    readonly observationId: string;
    readonly feedId: EvidenceFeedId;
    readonly sourceIdentityRef: string;
    readonly conflictFields: readonly string[];
    readonly duplicateSubmissionCount: number;
    readonly trustedCanonicalContribution: false;
  }[];
  readonly review: {
    readonly required: true;
    readonly reasons: readonly ["Disputed source identity is excluded from canonical evidence"];
  };
}

export interface EvidenceFusionResultV1 {
  readonly schemaVersion: "pqc.evidence-fusion-result.v1";
  readonly records: readonly CanonicalCryptoRecordV1[];
  readonly sourceReconciliationQueue: readonly SourceReconciliationItemV1[];
}

export interface EvidenceFusionFeed {
  readonly id: EvidenceFeedId;
  readonly label: string;
  readonly family: string;
  readonly signals: readonly string[];
  readonly issueTypes: readonly CryptoIssueType[];
  readonly contribution: string;
  readonly authorityBoundary: string;
  readonly status: "MODELED · NOT CONNECTED" | "LOCAL IMPORT ADAPTER";
}

export interface InboundEvidenceAdapter<TNative> {
  readonly feedId: EvidenceFeedId;
  readonly name: string;
  readonly version: "1.0.0";
  adapt(input: TNative): EvidenceObservationV1;
}

export interface CanonicalRecordViewPort {
  present(
    result: EvidenceFusionResultV1,
    sourceObservations: readonly EvidenceObservationV1[],
  ): EvidenceFusionViewModel;
}

export interface EvidenceFusionViewModel {
  readonly seedAssetCount: number;
  readonly seedObservationCount: number;
  readonly rawEnrichmentObservationCount: number;
  readonly uniqueEnrichmentEvidenceCount: number;
  readonly rawObservationCount: number;
  readonly uniqueEvidenceCount: number;
  readonly exactDuplicateCount: number;
  readonly sourceReconciliationCount: number;
  readonly candidateCount: number;
  readonly correlatedCount: number;
  readonly conflictCount: number;
  readonly unmatchedCount: number;
  readonly reviewQueueCount: number;
  readonly records: readonly CanonicalCryptoRecordV1[];
  readonly sourceReconciliationQueue: readonly SourceReconciliationItemV1[];
}

export interface InitialInventoryNativeRecord {
  readonly rowRef: string;
  readonly assetKey: string;
  readonly assetName: string;
  readonly estateClass: SoftwareEstateClass;
  readonly issueType: CryptoIssueType;
  readonly assertion: string;
}

export interface ExtraHopNativeRecord {
  readonly flowRef: string;
  readonly endpointKey: string;
  readonly endpointName: string;
  readonly estateClass: SoftwareEstateClass;
  readonly issueType: "tls-protocol" | "certificate-trust";
  readonly observation: string;
}

export interface VulnerabilityManagerNativeRecord {
  readonly pluginRef: string;
  readonly assetKey: string;
  readonly assetName: string;
  readonly estateClass: SoftwareEstateClass;
  readonly issueType: "tls-protocol" | "algorithm-key-strength" | "implementation-configuration" | "cryptographic-dependency";
  readonly finding: string;
}

export interface PkiInventoryNativeRecord {
  readonly certificateRef: string;
  readonly relyingPartyKey: string;
  readonly relyingPartyName: string;
  readonly estateClass: SoftwareEstateClass;
  readonly issueType: "certificate-trust" | "cryptographic-dependency";
  readonly certificateFact: string;
}

export interface SastNativeRecord {
  readonly resultRef: string;
  readonly repositoryAssetKey: string;
  readonly applicationName: string;
  readonly estateClass: SoftwareEstateClass;
  readonly issueType: "source-code-crypto-use" | "implementation-configuration" | "cryptographic-dependency";
  readonly codeFact: string;
}

export interface CmdbNativeRecord {
  readonly ciRef: string;
  readonly correlationKey: string;
  readonly ciName: string | null;
  readonly estateClass: SoftwareEstateClass;
  readonly issueType: "cryptographic-dependency" | "vendor-control";
  readonly contextFact: string;
}

const safety = { synthetic: true, containsSecret: false, rawPayloadRetained: false } as const;

function buildSyntheticObservation(
  feedId: EvidenceFeedId,
  name: string,
  input: {
    recordRef: string;
    candidateKey: string;
    assetHint: string | null;
    estateClass: SoftwareEstateClass;
    issueType: CryptoIssueType;
    fact: string;
  },
): EvidenceObservationV1 {
  return {
    schemaVersion: "pqc.evidence-observation.v1",
    observationId: `obs:${feedId}:${input.recordRef}`,
    feedId,
    adapter: { name, version: "1.0.0" },
    source: { recordRef: input.recordRef, collectedAt: null },
    subject: {
      candidateKey: input.candidateKey,
      assetHint: input.assetHint,
      estateClass: input.estateClass,
    },
    classification: { issueType: input.issueType },
    finding: { fact: input.fact },
    provenance: {
      assessment: "assumption",
      confidence: "illustrative",
      sourceLocator: "src/domain/evidenceFusion.ts",
    },
    safety,
  };
}

export const EVIDENCE_FUSION_FEEDS: readonly EvidenceFusionFeed[] = [
  {
    id: "extrahop-internet-tls",
    label: "ExtraHop Internet TLS + certificates",
    family: "Network evidence",
    signals: ["Internet TLS protocol", "Handshake algorithm hints", "Presented certificate metadata"],
    issueTypes: ["tls-protocol", "certificate-trust"],
    contribution: "Observed synthetic traffic and certificate clues for candidate assets.",
    authorityBoundary: "Observed traffic is not a complete crypto inventory and does not prove unobserved paths.",
    status: "MODELED · NOT CONNECTED",
  },
  {
    id: "vulnerability-manager",
    label: "Vulnerability manager",
    family: "Scanner evidence",
    signals: ["SSL plugin findings", "Weak crypto configuration", "Crypto-relevant CVEs"],
    issueTypes: ["tls-protocol", "algorithm-key-strength", "implementation-configuration", "cryptographic-dependency"],
    contribution: "Separates SSL-plugin output from crypto-vulnerability signals for enrichment.",
    authorityBoundary: "A scanner finding is a finding—not authoritative proof of complete cryptographic use.",
    status: "MODELED · NOT CONNECTED",
  },
  {
    id: "pki-inventory",
    label: "PKI inventory / Venafi",
    family: "Trust evidence",
    signals: ["Certificates and profiles", "Issuer hierarchy", "Validity and relying-party hints"],
    issueTypes: ["certificate-trust", "cryptographic-dependency"],
    contribution: "The local Venafi certificate-search adapter supplies bounded certificate, algorithm, trust, and instance metadata.",
    authorityBoundary: "PKI inventory is authoritative only for its governed PKI scope, not all crypto use.",
    status: "LOCAL IMPORT ADAPTER",
  },
  {
    id: "sast",
    label: "SAST / Snyk Code",
    family: "Source evidence",
    signals: ["Crypto API calls", "Embedded algorithms", "Library and dependency references"],
    issueTypes: ["source-code-crypto-use", "implementation-configuration", "cryptographic-dependency"],
    contribution: "The local Snyk Code SARIF adapter locates crypto-relevant source findings for application-owner review.",
    authorityBoundary: "SAST sees analyzed source; it does not prove deployed runtime behavior or opaque products.",
    status: "LOCAL IMPORT ADAPTER",
  },
  {
    id: "cmdb",
    label: "CMDB",
    family: "Business context",
    signals: ["CI correlation identifier", "Bounded classification hint", "Typed business context deferred to v2"],
    issueTypes: ["cryptographic-dependency", "vendor-control"],
    contribution: "Provides a bounded synthetic identity hint for correlation in this finding-shaped v1 contract.",
    authorityBoundary: "V1 does not normalize typed owner, service, lifecycle, criticality, or relationship fields.",
    status: "MODELED · NOT CONNECTED",
  },
] as const;

export const INITIAL_INVENTORY_SOURCE = {
  id: "initial-inventory",
  label: "Initial inventory bootstrap",
  contribution: "Ten synthetic stand-ins seed canonical asset identities before five modeled feeds enrich and reconcile them.",
  authorityBoundary: "No client inventory was imported; these rows are illustrative fixtures only.",
  status: "MODELED · NOT CONNECTED",
} as const;

export const ESTATE_ROUTING: Readonly<Record<SoftwareEstateClass, {
  label: string;
  ownerPath: string;
  changePath: string;
  validationPath: string;
}>> = {
  "source-code": {
    label: "Source code",
    ownerPath: "Application + repository owner",
    changePath: "Code/library change through SDLC",
    validationPath: "Build tests, SAST rescan, deployed-behavior evidence",
  },
  "ots-cots": {
    label: "OTS / COTS",
    ownerPath: "Product + platform owner",
    changePath: "Installed-version upgrade or supported configuration",
    validationPath: "Vendor evidence plus installed-version and behavior readback",
  },
  "third-party-saas": {
    label: "Third-party / SaaS",
    ownerPath: "Connection + service owner",
    changePath: "Vendor roadmap, contract, integration, or replacement",
    validationPath: "Provider evidence plus observed connection behavior",
  },
} as const;

export const ISSUE_TYPE_LABELS: Readonly<Record<CryptoIssueType, string>> = {
  "tls-protocol": "TLS / protocol",
  "certificate-trust": "Certificate / trust",
  "implementation-configuration": "Implementation / configuration",
  "source-code-crypto-use": "Source-code crypto use",
  "cryptographic-dependency": "Cryptographic dependency",
  "algorithm-key-strength": "Algorithm / key strength",
  "vendor-control": "Vendor control / readiness",
};

export const InitialInventoryAdapter: InboundEvidenceAdapter<InitialInventoryNativeRecord> = {
  feedId: "initial-inventory", name: "initial-inventory-fixture-adapter", version: "1.0.0",
  adapt: (input) => buildSyntheticObservation("initial-inventory", "initial-inventory-fixture-adapter", {
    recordRef: input.rowRef, candidateKey: input.assetKey, assetHint: input.assetName,
    estateClass: input.estateClass, issueType: input.issueType, fact: input.assertion,
  }),
};

export const ExtraHopAdapter: InboundEvidenceAdapter<ExtraHopNativeRecord> = {
  feedId: "extrahop-internet-tls", name: "extrahop-fixture-adapter", version: "1.0.0",
  adapt: (input) => buildSyntheticObservation("extrahop-internet-tls", "extrahop-fixture-adapter", {
    recordRef: input.flowRef, candidateKey: input.endpointKey, assetHint: input.endpointName,
    estateClass: input.estateClass, issueType: input.issueType, fact: input.observation,
  }),
};

export const VulnerabilityManagerAdapter: InboundEvidenceAdapter<VulnerabilityManagerNativeRecord> = {
  feedId: "vulnerability-manager", name: "vm-fixture-adapter", version: "1.0.0",
  adapt: (input) => buildSyntheticObservation("vulnerability-manager", "vm-fixture-adapter", {
    recordRef: input.pluginRef, candidateKey: input.assetKey, assetHint: input.assetName,
    estateClass: input.estateClass, issueType: input.issueType, fact: input.finding,
  }),
};

export const PkiInventoryAdapter: InboundEvidenceAdapter<PkiInventoryNativeRecord> = {
  feedId: "pki-inventory", name: "pki-fixture-adapter", version: "1.0.0",
  adapt: (input) => buildSyntheticObservation("pki-inventory", "pki-fixture-adapter", {
    recordRef: input.certificateRef, candidateKey: input.relyingPartyKey, assetHint: input.relyingPartyName,
    estateClass: input.estateClass, issueType: input.issueType, fact: input.certificateFact,
  }),
};

export const SastAdapter: InboundEvidenceAdapter<SastNativeRecord> = {
  feedId: "sast", name: "sast-fixture-adapter", version: "1.0.0",
  adapt: (input) => buildSyntheticObservation("sast", "sast-fixture-adapter", {
    recordRef: input.resultRef, candidateKey: input.repositoryAssetKey, assetHint: input.applicationName,
    estateClass: input.estateClass, issueType: input.issueType, fact: input.codeFact,
  }),
};

export const CmdbAdapter: InboundEvidenceAdapter<CmdbNativeRecord> = {
  feedId: "cmdb", name: "cmdb-fixture-adapter", version: "1.0.0",
  adapt: (input) => buildSyntheticObservation("cmdb", "cmdb-fixture-adapter", {
    recordRef: input.ciRef, candidateKey: input.correlationKey, assetHint: input.ciName,
    estateClass: input.estateClass, issueType: input.issueType, fact: input.contextFact,
  }),
};

const INITIAL_INVENTORY_FIXTURES: readonly InitialInventoryNativeRecord[] = CRYPTO_SYSTEMS.flatMap(
  (system) => system.issueTypes.map((issueType) => ({
    rowRef: `${system.id}:${issueType}`,
    assetKey: system.id,
    assetName: system.asset,
    estateClass: system.estateClass,
    issueType,
    assertion: `Synthetic seed row classifies ${system.asset} for ${ISSUE_TYPE_LABELS[issueType].toLowerCase()} review.`,
  })),
);

const EXTRAHOP_FIXTURES: readonly ExtraHopNativeRecord[] = [
  { flowRef: "tls-101", endpointKey: " syn-api-edge-01 ", endpointName: "Customer API Gateway", estateClass: "third-party-saas", issueType: "tls-protocol", observation: "Synthetic Internet flow advertises a TLS 1.3 endpoint." },
  { flowRef: "tls-102", endpointKey: "syn-api-edge-01", endpointName: "Customer API Gateway", estateClass: "third-party-saas", issueType: "certificate-trust", observation: "Synthetic flow presents an enterprise-issued edge certificate." },
];

const VULNERABILITY_MANAGER_FIXTURES: readonly VulnerabilityManagerNativeRecord[] = [
  { pluginRef: "ssl-plugin-201", assetKey: "SYN-PAY-JAVA-02", assetName: "Internal Java Payment Service", estateClass: "source-code", issueType: "tls-protocol", finding: "Synthetic SSL plugin flags a legacy protocol path." },
  { pluginRef: "crypto-cve-202", assetKey: "syn-pay-java-02", assetName: "Internal Java Payment Service", estateClass: "source-code", issueType: "implementation-configuration", finding: "Synthetic crypto-library vulnerability requires version validation." },
  { pluginRef: "crypto-strength-203", assetKey: "syn-pay-java-02", assetName: "Internal Java Payment Service", estateClass: "source-code", issueType: "algorithm-key-strength", finding: "Synthetic non-TLS finding flags an algorithm and key-strength review." },
  { pluginRef: "ssl-plugin-201", assetKey: "SYN-PAY-JAVA-02", assetName: "Internal Java Payment Service", estateClass: "source-code", issueType: "tls-protocol", finding: "Synthetic SSL plugin flags a legacy protocol path." },
];

const PKI_FIXTURES: readonly PkiInventoryNativeRecord[] = [
  { certificateRef: "cert-301", relyingPartyKey: "syn-api-edge-01", relyingPartyName: "Customer API Gateway", estateClass: "third-party-saas", issueType: "certificate-trust", certificateFact: "Synthetic PKI record links the endpoint to an issuing profile." },
];

const SAST_FIXTURES: readonly SastNativeRecord[] = [
  { resultRef: "code-401", repositoryAssetKey: "syn-pay-java-02", applicationName: "Internal Java Payment Service", estateClass: "source-code", issueType: "source-code-crypto-use", codeFact: "Synthetic SAST result locates an RSA signing API call." },
  { resultRef: "code-402", repositoryAssetKey: "syn-pay-java-02", applicationName: "Ledger Relay", estateClass: "ots-cots", issueType: "source-code-crypto-use", codeFact: "Synthetic conflicting classification requires human reconciliation." },
];

const CMDB_FIXTURES: readonly CmdbNativeRecord[] = [
  { ciRef: "ci-501", correlationKey: "syn-pay-java-02", ciName: "Internal Java Payment Service", estateClass: "source-code", issueType: "cryptographic-dependency", contextFact: "Synthetic CI identity hint is a candidate correlation to the payment service." },
  { ciRef: "ci-502", correlationKey: "syn-vpn-03", ciName: "Corporate VPN", estateClass: "ots-cots", issueType: "vendor-control", contextFact: "Synthetic CI classifies the VPN as a vendor-controlled appliance." },
  { ciRef: "ci-503", correlationKey: "orphan-service-77", ciName: null, estateClass: "ots-cots", issueType: "cryptographic-dependency", contextFact: "Synthetic CI cannot yet be correlated to the seed inventory." },
];

export function adaptSyntheticFeedFixtures(): EvidenceObservationV1[] {
  return [
    ...INITIAL_INVENTORY_FIXTURES.map((fixture) => InitialInventoryAdapter.adapt(fixture)),
    ...EXTRAHOP_FIXTURES.map((fixture) => ExtraHopAdapter.adapt(fixture)),
    ...VULNERABILITY_MANAGER_FIXTURES.map((fixture) => VulnerabilityManagerAdapter.adapt(fixture)),
    ...PKI_FIXTURES.map((fixture) => PkiInventoryAdapter.adapt(fixture)),
    ...SAST_FIXTURES.map((fixture) => SastAdapter.adapt(fixture)),
    ...CMDB_FIXTURES.map((fixture) => CmdbAdapter.adapt(fixture)),
  ];
}

export { assertEvidenceObservationContract, fuseEvidenceObservations } from "./evidenceFusionCore";

export const evidenceFusionViewPort: CanonicalRecordViewPort = {
  present(result, sourceObservations) {
    const { records, sourceReconciliationQueue } = result;
    const exactDuplicateCount = records.reduce((sum, record) => sum + record.correlation.duplicateCount, 0);
    const uniqueEvidenceCount = records.reduce((sum, record) => sum + record.evidenceRefs.length, 0);
    return {
      seedAssetCount: new Set(sourceObservations.filter((observation) => observation.feedId === "initial-inventory").map((observation) => observation.subject.candidateKey.trim().toLowerCase().replaceAll(/\s+/gu, "-"))).size,
      seedObservationCount: sourceObservations.filter((observation) => observation.feedId === "initial-inventory").length,
      rawEnrichmentObservationCount: sourceObservations.filter((observation) => observation.feedId !== "initial-inventory").length,
      uniqueEnrichmentEvidenceCount: records.reduce((sum, record) => sum + record.evidenceRefs.filter((ref) => ref.feedId !== "initial-inventory").length, 0),
      rawObservationCount: sourceObservations.length,
      uniqueEvidenceCount,
      exactDuplicateCount,
      sourceReconciliationCount: sourceReconciliationQueue.length,
      candidateCount: records.length,
      correlatedCount: records.filter((record) => record.correlation.status === "correlated").length,
      conflictCount: records.filter((record) => record.correlation.status === "conflict").length,
      unmatchedCount: records.filter((record) => record.correlation.status === "unmatched").length,
      reviewQueueCount: records.filter((record) => record.review.required).length,
      records,
      sourceReconciliationQueue,
    };
  },
};

const SYNTHETIC_FEED_OBSERVATIONS = adaptSyntheticFeedFixtures();

export const EVIDENCE_FUSION_VIEW = evidenceFusionViewPort.present(
  fuseEvidenceObservations(SYNTHETIC_FEED_OBSERVATIONS),
  SYNTHETIC_FEED_OBSERVATIONS,
);
