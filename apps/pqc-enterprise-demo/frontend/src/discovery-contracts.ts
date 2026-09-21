export type DiscoveryAnswerStatus = 'unanswered' | 'answered' | 'unknown' | 'not_my_team' | 'referral' | 'not_applicable';
export interface DiscoveryAnswer { status: DiscoveryAnswerStatus; text: string; reference: string; assertedBy?: string; recordedBy?: string }
export interface DiscoveryProduct { id: string; label: string; product: string; environment: string }
export interface DiscoveryQuestion { id: string; prompt: string; whyItMatters: string; examples: string[]; usefulResponse: string }
export interface DiscoveryGuidance {
  introduction: string; handlingNotice: string; reviewNotice: string; submissionReceipt: string; legacyNotice: string;
}
export interface DiscoveryRecognitionExample { name: string; kind: string; url: string; note?: string }
export interface DiscoveryRecognitionFamily { id: string; name: string; examples: DiscoveryRecognitionExample[] }
export interface DiscoveryRecognitionDomain { id: string; name: string; families: DiscoveryRecognitionFamily[] }
export interface DiscoveryRecognition {
  catalogVersion: string; catalogSha256: string; reviewedAt: string; boundary: string; familyId: string;
  domain: DiscoveryRecognitionDomain; domains: DiscoveryRecognitionDomain[];
}
export interface DiscoveryRequest {
  id: string; title: string; familyId: string; familyName: string; templateVersion: string;
  questions: DiscoveryQuestion[]; examples: string[]; assignedTo: string; status: 'draft' | 'submitted';
  answers: Record<string, DiscoveryAnswer>; productRefs: DiscoveryProduct[];
  submission: { submittedAt: string; submittedBy: string; contentSha256: string } | null;
  receipt: string | null;
}
export interface DiscoveryStandard {
  id: string; title: string; version: string; status: 'draft'; purpose: string; proposalText: string;
  existingRequirementStatus: 'unassessed' | 'reported_existing' | 'not_identified' | 'conflict_reported';
  existingRequirementRefs: string[]; authorityStatus: 'unassigned' | 'proposed_owner' | 'review_requested';
  proposedAuthority: string; conflictReviewStatus: 'unassessed' | 'no_conflict_reported' | 'conflict_reported'; conflictNote: string;
  observedPractice?: string; revision?: number; publicationRefs?: { title: string; url: string; status: string }[];
}
export interface DiscoveryEvidenceReview {
  batchId: string; productRefId: string; productLabel: string; sourceLabel: string; observationCount: number;
  contentSha256: string; stagedBy: string; stagedAt: string;
  status: 'staged' | 'qualified' | 'needs_clarification' | 'admitted';
  reviewedBy: string; reviewedAt: string; reviewRationale: string; admittedBy: string; admittedAt: string;
}
export interface DiscoveryInvestigation {
  id: string; requestId: string; familyId: string; productRefIds: string[]; assignedTo: string;
  status: 'planned' | 'researching' | 'ready_for_review' | 'blocked'; purpose: string;
  researchSummary: string; proposedMethod: string; documentationRefs: string[]; limitation: string;
  intakeRequestId: string | null; evidenceReviews: DiscoveryEvidenceReview[];
  productRefs?: DiscoveryProduct[];
  canEditResearch?: boolean; canStageEvidence?: boolean; canReviewEvidence?: boolean; canAdmitEvidence?: boolean; evidenceBlockingReason?: string;
}
export interface DiscoveryList {
  assessmentId: string; assessmentName: string; revision: number; canCoordinate: boolean;
  collectionAvailable?: boolean;
  canResearch?: boolean; canReviewEvidence?: boolean; canStageEvidence?: boolean; canAdmitEvidence?: boolean;
  investigators?: { id: string; label: string }[];
  evidenceBlockingReason?: string;
  requests: DiscoveryRequest[]; families: { id: string; name: string; examples: string[] }[];
  standards: DiscoveryStandard[]; investigations: DiscoveryInvestigation[]; boundary: string;
}
export interface DiscoveryDetail {
  assessmentId: string; assessmentName: string; revision: number; request: DiscoveryRequest;
  guidance: DiscoveryGuidance;
  recognition?: DiscoveryRecognition | null;
  canEdit: boolean; canCoordinate: boolean; validation: { canSubmit: boolean; issues: string[] }; boundary: string;
}
export interface DiscoveryCommand { operation: string; targetId: string | null; fields: Record<string, unknown>; expectedRevision: number }
export interface DiscoveryExport { exportId: string; downloadUrl: string; revision: number }
export interface DiscoveryImport {
  revision: number;
  import: { id: string; changes: { questionId: string; baseline: Record<string, string>; current: Record<string, string>; returned: Record<string, string>; state: 'unchanged' | 'change' | 'conflict' }[] };
}
export interface DiscoveryCollectionForm {
  familyId: string; familyName: string; questions: DiscoveryQuestion[]; examples: DiscoveryRecognitionExample[];
}
export interface DiscoveryCollectionPackage {
  id: string; createdAt: string; zipUrl: string; indexUrl: string;
  forms: { familyId: string; requestId: string; filename: string; downloadUrl: string; sha256: string }[];
}
export interface DiscoveryCollectionRecord {
  id: string; assignedTo: string; createdAt: string;
  requests: { familyId: string; requestId: string; status: 'draft' | 'submitted' }[];
  packages: DiscoveryCollectionPackage[];
}
export interface DiscoveryCollectionCatalog {
  assessmentId: string; assessmentName: string; revision: number; canPrepare: boolean;
  templateVersion: string; domainCount: number; formCount: number; questionsPerForm: number; boundary: string;
  recipients: { id: string; label: string }[];
  domains: { id: string; name: string; forms: DiscoveryCollectionForm[] }[];
  collections: DiscoveryCollectionRecord[];
}
