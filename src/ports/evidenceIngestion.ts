import type {
  EvidenceFeedId,
  EvidenceObservationV1,
} from "../domain/evidenceFusion";
import type { SoftwareEstateClass } from "../domain/model";

export type EvidenceAdapterId = "snyk-code-sarif" | "venafi-certificate-search";

export interface EvidenceImportContext {
  readonly assetKey: string;
  readonly assetName: string;
  readonly estateClass: SoftwareEstateClass;
  readonly collectedAt: string | null;
  readonly sourceName: string;
  readonly synthetic: boolean;
}

export interface AdapterDiagnostic {
  readonly level: "warning" | "information";
  readonly code: string;
  readonly message: string;
  readonly sourceRef: string | null;
}

export interface EvidenceImportRunV1 {
  readonly schemaVersion: "pqc.evidence-import-run.v1";
  readonly adapterId: EvidenceAdapterId;
  readonly adapterName: string;
  readonly adapterVersion: "1.0.0";
  readonly feedId: EvidenceFeedId;
  readonly sourceName: string;
  readonly acceptedCount: number;
  readonly skippedCount: number;
  readonly observations: readonly EvidenceObservationV1[];
  readonly diagnostics: readonly AdapterDiagnostic[];
  readonly safety: {
    readonly synthetic: boolean;
    readonly containsSecret: false;
    readonly rawPayloadRetained: false;
  };
}

export interface EvidenceBatchAdapter {
  readonly id: EvidenceAdapterId;
  readonly name: string;
  readonly version: "1.0.0";
  readonly feedId: EvidenceFeedId;
  adapt(payload: unknown, context: EvidenceImportContext): EvidenceImportRunV1;
}

export interface EvidenceImportRequest {
  readonly adapterId: EvidenceAdapterId;
  readonly payload: unknown;
  readonly context: EvidenceImportContext;
}

export interface RunMigrationSliceInputPort<TOutput> {
  execute(requests: readonly EvidenceImportRequest[]): TOutput;
}
