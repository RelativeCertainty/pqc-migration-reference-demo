import type { AssessmentDocument } from './assessment-contracts';
import type { DiscoveryInvestigation, DiscoveryRequest } from './discovery-contracts';

export type WorkState = 'needs_action' | 'in_progress' | 'waiting' | 'recorded';
export type WorkStep = 'returned' | 'systems' | 'technical' | 'consequence' | 'history';
export interface WorkItem {
  requestId: string; title: string; familyId: string; familyName: string; state: WorkState;
  task: string; why: string; effect: string; nextFunction: string; canAct: boolean; step?: WorkStep;
}
export interface WorkQueue { assessmentId: string; assessmentName: string; revision: number; items: WorkItem[]; boundary: string }
export interface ReceivedAnswer { questionId: string; prompt: string; status: string; text: string; reference: string; attribution: string; followUp: string }
export interface ReceivedProduct { id: string; product: string; deployment: string; environment: string; applicationService: string; team: string; dependencies: string; reference: string; notes: string; provenance?: string; receiptId?: string }
export interface OperationalReceipt {
  id: string; status: string; filename: string; artifactSha256: string; profile: string; familyId: string;
  receivedAt: string; receivedBy: string; respondent: string; team: string; responseDate: string; scope: string;
  answers: ReceivedAnswer[]; products: ReceivedProduct[];
  comparison: { questionId: string; current: Record<string, unknown>; returned: Record<string, unknown>; state: string }[];
}
export interface IdentityDecision { id: string; productId: string; decision: 'distinct' | 'same_system' | 'unresolved'; canonicalId: string; label: string; applicationService: string; team: string; rationale: string }
export interface TechnicalRecord {
  bundleId: string; investigationId: string; productLabel: string; sourceLabel: string; status: string;
  kind?: string; productId?: string; canonicalId?: string; proposedCanonicalId?: string; identityChangeReason?: string; canReview?: boolean; canAdmit?: boolean;
  observations: { id: string; systemId: string; sourceSystemId: string; nativeId: string; productId?: string; canonicalId?: string; label?: string; hostname?: string; keyExchange?: string; authentication?: string; basis?: string; observedAt?: string; collectedAt?: string; [key: string]: unknown }[];
  reviewRationale: string;
}
export interface WorkConsequence {
  id?: string; phase1Conclusion: string; limitation: string; nextDecision: string; responsibleFunction: string;
  phase2Consequence: string; lifetime: string; confidence: 'unknown' | 'limited' | 'supported'; status?: string;
  productId?: string; cryptographicPurpose?: string; supportingObservationIds?: string[]; contradictingObservationIds?: string[];
}
export interface WorkCase {
  assessmentId: string; assessmentName: string; revision: number; request: DiscoveryRequest;
  investigations: DiscoveryInvestigation[]; receipts: OperationalReceipt[]; identityDecisions: IdentityDecision[];
  technicalRecords: TechnicalRecord[]; consequence: WorkConsequence | null;
  consequences?: WorkConsequence[]; task?: WorkItem; canStageEvidence?: boolean; stageEvidenceBlockingReasons?: string[];
  history: { revision: number; operation: string; targetId?: string; principalId?: string; createdAt?: string; origin?: string }[];
  documents: AssessmentDocument[]; allowedActions: string[]; boundary: string;
}
export interface ImpactPreview { revision: number; previewFingerprint: string; consequence: WorkConsequence; phase1Text: string; phase2Text: string; limitations: string[]; nextDecision: string }
