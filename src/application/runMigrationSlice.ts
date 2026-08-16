import { SnykCodeSarifAdapter } from "../adapters/snykCodeSarif";
import { VenafiCertificateSearchAdapter } from "../adapters/venafiCertificateSearch";
import { stableSafeId } from "../adapters/adapterSupport";
import {
  adaptSyntheticFeedFixtures,
  fuseEvidenceObservations,
} from "../domain/evidenceFusion";
import {
  planMigrationWorkItems,
  type MigrationEvidencePackageV1,
} from "../domain/migrationPlanning";
import type {
  EvidenceBatchAdapter,
  EvidenceImportRequest,
  RunMigrationSliceInputPort,
} from "../ports/evidenceIngestion";

const DEFAULT_ADAPTERS: readonly EvidenceBatchAdapter[] = [
  SnykCodeSarifAdapter,
  VenafiCertificateSearchAdapter,
];
const MAX_IMPORTED_OBSERVATIONS_PER_ASSET = 90;

function packageTimestamp(requests: readonly EvidenceImportRequest[]): string | null {
  return requests
    .map((request) => request.context.collectedAt)
    .filter((value): value is string => value !== null)
    .sort()
    .at(-1) ?? null;
}

export class RunMigrationSliceService implements RunMigrationSliceInputPort<MigrationEvidencePackageV1> {
  private readonly adapters: ReadonlyMap<string, EvidenceBatchAdapter>;

  constructor(adapters: readonly EvidenceBatchAdapter[] = DEFAULT_ADAPTERS) {
    this.adapters = new Map(adapters.map((adapter) => [adapter.id, adapter]));
  }

  execute(requests: readonly EvidenceImportRequest[]): MigrationEvidencePackageV1 {
    if (requests.length === 0) throw new Error("At least one evidence import is required.");
    if (requests.length > 10) throw new Error("A local migration-slice run accepts at most ten imports.");

    const importRuns = requests.map((request) => {
      const adapter = this.adapters.get(request.adapterId);
      if (!adapter) throw new Error(`No evidence adapter is registered for ${request.adapterId}.`);
      return adapter.adapt(request.payload, request.context);
    });
    const importedObservations = importRuns.flatMap((run) => [...run.observations]);
    const importedByAsset = new Map<string, number>();
    for (const observation of importedObservations) {
      const assetKey = observation.subject.candidateKey;
      const count = (importedByAsset.get(assetKey) ?? 0) + 1;
      if (count > MAX_IMPORTED_OBSERVATIONS_PER_ASSET) {
        throw new Error(`Combined imports exceed the ${MAX_IMPORTED_OBSERVATIONS_PER_ASSET}-observation local safety limit for ${assetKey}. Split the evidence into separately reviewed runs.`);
      }
      importedByAsset.set(assetKey, count);
    }
    const seedObservations = adaptSyntheticFeedFixtures().filter((observation) => observation.feedId === "initial-inventory");
    const fusion = fuseEvidenceObservations([...seedObservations, ...importedObservations]);
    const importedIds = new Set(importedObservations.map((observation) => observation.observationId));
    const workItems = planMigrationWorkItems(fusion, importedIds);
    const relevantRecordIds = new Set(workItems.map((item) => item.canonicalRecordId));
    const boundedFusion = {
      ...fusion,
      records: fusion.records.filter((record) => relevantRecordIds.has(record.recordId)),
    };
    const timestamp = packageTimestamp(requests);
    const acceptedObservations = importRuns.reduce((sum, run) => sum + run.acceptedCount, 0);
    const skippedNativeRecords = importRuns.reduce((sum, run) => sum + run.skippedCount, 0);
    const packageId = stableSafeId(
      "migration-package",
      [
        ...requests.map((request) => `${request.adapterId}:${request.context.assetKey}`),
        ...importedObservations.map((observation) => observation.observationId),
      ].sort().join("\u0000"),
    );

    return {
      schemaVersion: "pqc.migration-evidence-package.v1",
      packageId,
      generatedAt: timestamp,
      outcome: "bounded-migration-assessment",
      summary: {
        adapterRuns: importRuns.length,
        acceptedObservations,
        skippedNativeRecords,
        canonicalCandidates: boundedFusion.records.length,
        proposedWorkItems: workItems.length,
        reviewRequired: workItems.filter((item) => item.review.required).length + boundedFusion.sourceReconciliationQueue.length,
      },
      importRuns,
      fusion: boundedFusion,
      workItems,
      assurance: {
        rawPayloadRetained: false,
        containsSecret: false,
        automaticChangeAuthorized: false,
        limitation: "This package proposes reviewable work. It does not prove runtime behavior, authorize change, or attest migration completion.",
      },
    };
  }
}

export const runMigrationSlice = new RunMigrationSliceService();
