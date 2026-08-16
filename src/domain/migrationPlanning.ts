import type {
  CanonicalCryptoRecordV1,
  EvidenceFusionResultV1,
} from "./evidenceFusion";
import type { CryptoIssueType, InventoryPriority } from "./model";
import type { EvidenceImportRunV1 } from "../ports/evidenceIngestion";

export interface MigrationWorkItemV1 {
  readonly schemaVersion: "pqc.migration-work-item.v1";
  readonly workItemId: string;
  readonly canonicalRecordId: string;
  readonly assetKey: string;
  readonly displayName: string | null;
  readonly stage: "Risk Assessment & Planning";
  readonly state: "proposed";
  readonly priority: InventoryPriority;
  readonly issueTypes: readonly CryptoIssueType[];
  readonly decision: "migration-plan-required" | "evidence-review-required";
  readonly recommendedPattern: string;
  readonly rationale: readonly string[];
  readonly evidenceRefs: CanonicalCryptoRecordV1["evidenceRefs"];
  readonly authorityGates: readonly string[];
  readonly validationRequirements: readonly string[];
  readonly review: {
    readonly required: true;
    readonly owner: "Application and cryptographic-service owners";
    readonly approvalRecorded: false;
  };
}

export interface MigrationEvidencePackageV1 {
  readonly schemaVersion: "pqc.migration-evidence-package.v1";
  readonly packageId: string;
  readonly generatedAt: string | null;
  readonly outcome: "bounded-migration-assessment";
  readonly summary: {
    readonly adapterRuns: number;
    readonly acceptedObservations: number;
    readonly skippedNativeRecords: number;
    readonly canonicalCandidates: number;
    readonly proposedWorkItems: number;
    readonly reviewRequired: number;
  };
  readonly importRuns: readonly EvidenceImportRunV1[];
  readonly fusion: EvidenceFusionResultV1;
  readonly workItems: readonly MigrationWorkItemV1[];
  readonly assurance: {
    readonly rawPayloadRetained: false;
    readonly containsSecret: false;
    readonly automaticChangeAuthorized: false;
    readonly limitation: string;
  };
}

const issueRationale: Readonly<Record<CryptoIssueType, string>> = {
  "source-code-crypto-use": "Source-visible cryptographic use must be placed behind an owned crypto-agility boundary before algorithm transition.",
  "implementation-configuration": "The implementation or configuration requires correction and regression evidence independent of the PQC transition.",
  "cryptographic-dependency": "A cryptographic dependency requires an accountable owner, supported target state, and compatibility plan.",
  "algorithm-key-strength": "Public-key algorithm evidence places the asset in scope for quantum-risk assessment and transition planning.",
  "certificate-trust": "Certificate and trust dependencies require relying-party discovery, issuance policy review, and controlled transition sequencing.",
  "tls-protocol": "Protocol use requires interoperable target-state and rollback testing across every participating endpoint.",
  "vendor-control": "A vendor-controlled dependency requires roadmap evidence, contractual accountability, and a replacement or exception path.",
};

function priorityFor(record: CanonicalCryptoRecordV1): InventoryPriority {
  if (record.correlation.status === "conflict") return "Urgent";
  const issues = new Set(record.issueTypes);
  if (issues.has("algorithm-key-strength") && (issues.has("source-code-crypto-use") || issues.has("certificate-trust"))) return "High";
  if (issues.has("source-code-crypto-use") || issues.has("certificate-trust") || issues.has("vendor-control")) return "High";
  if (issues.has("implementation-configuration") || issues.has("cryptographic-dependency")) return "Moderate";
  return "Low";
}

function patternFor(record: CanonicalCryptoRecordV1): string {
  const issues = new Set(record.issueTypes);
  if (issues.has("source-code-crypto-use")) {
    return "Introduce an application-owned crypto-agility interface, inventory every caller, pilot an approved target profile, and retain bounded rollback.";
  }
  if (issues.has("certificate-trust")) {
    return "Map certificate instances and relying parties, define the approved issuance profile, then migrate through a compatibility-tested trust transition.";
  }
  if (issues.has("vendor-control")) {
    return "Obtain version-specific vendor evidence, define upgrade or replacement milestones, and govern any time-bounded exception.";
  }
  return "Establish the current cryptographic dependency, select an approved target state, pilot the change, and verify by rediscovery.";
}

function stableWorkItemId(record: CanonicalCryptoRecordV1): string {
  return `work-item:${record.canonicalAssetKey}`;
}

export function planMigrationWorkItems(
  fusion: EvidenceFusionResultV1,
  importedObservationIds: ReadonlySet<string>,
): MigrationWorkItemV1[] {
  return fusion.records
    .filter((record) => record.evidenceRefs.some((reference) => importedObservationIds.has(reference.observationId)))
    .map((record) => ({
      schemaVersion: "pqc.migration-work-item.v1" as const,
      workItemId: stableWorkItemId(record),
      canonicalRecordId: record.recordId,
      assetKey: record.canonicalAssetKey,
      displayName: record.displayName,
      stage: "Risk Assessment & Planning" as const,
      state: "proposed" as const,
      priority: priorityFor(record),
      issueTypes: record.issueTypes,
      decision: record.correlation.status === "conflict" || record.review.required
        ? "evidence-review-required" as const
        : "migration-plan-required" as const,
      recommendedPattern: patternFor(record),
      rationale: record.issueTypes.map((issueType) => issueRationale[issueType]),
      evidenceRefs: record.evidenceRefs,
      authorityGates: [
        "Application owner confirms the cryptographic dependency and blast radius.",
        "Cryptographic authority approves the target profile and interoperability window.",
        "Change authority approves execution, fallback, and evidence-retention requirements.",
      ],
      validationRequirements: [
        "Repeat source and inventory discovery after the change.",
        "Verify deployed behavior separately from configuration or source inspection.",
        "Exercise compatibility, failure, and rollback paths before completion is attested.",
      ],
      review: {
        required: true as const,
        owner: "Application and cryptographic-service owners" as const,
        approvalRecorded: false as const,
      },
    }))
    .sort((left, right) => left.workItemId.localeCompare(right.workItemId));
}
