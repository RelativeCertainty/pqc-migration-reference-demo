export type AssessmentPersona = { principalId: string; role: string; label: string };
export type AssessmentStage = { id: number; label: string; question: string };
export type AssessmentScope = {
  objective: string; handling: string; method: string; cycleGoal: string; reviewDate: string;
  includedFamilyIds: string[]; excludedReasons: Record<string, string>; depthByFamily: Record<string, string>;
};
export type AssessmentSource = {
  id: string; familyId: string; name: string; areaId: string; examples: string[];
  state: 'unanswered' | 'route_confirmed' | 'unknown' | 'not_my_team' | 'blocked';
  systemOfRecord: string; product: string; ownerFunction: string; accessRoute: string; note: string; dueAt: string;
  observationIds: string[]; subjectIds: string[]; assertedBy: string; respondedBy: string;
};
export type AssessmentAnalysis = {
  scenario: string; businessImpact: string; recommendation: string; priority: string;
  rationale: string; confidence: string; state: string; submittedBy: string; reviewedBy: string;
  protectedInformation?: string; lifetime?: string; assertedBy?: string; statementDate?: string;
  compatibilityConstraints?: string; vendorConstraints?: string; operationalConstraints?: string;
  responsibleFunction?: string; nextDecision?: string;
};
export type AssessmentPackage = {
  id: string; familyId: string; label: string; state: string; conclusion: string; qualification: string;
  submittedBy: string; reviewedBy: string; revision: number; evidenceCount: number; subjectCount: number;
  observationIds: string[]; subjectIds: string[]; analysis: AssessmentAnalysis;
  plannedDepth?: string; achievedDepth?: string; depthLimitation?: string;
};
export type AssessmentDecision = {
  decision: string; rationale: string; qualification: string; reviewDate: string;
  principalId: string; role: string; createdAt: string; origin?: string; fingerprint?: string;
};
export type AssessmentGate = {
  id: string; name: string; stage: number; requiredRoles: string[]; state: string;
  requirements: { label: string; satisfied: boolean }[]; decisions: AssessmentDecision[];
  submissionRevision: number; fingerprint: string; documentId?: string | null;
};
export type AssessmentDocument = {
  id: string; phase: 'phase1' | 'phase2'; createdAt: string; contentSha256: string;
  inputFingerprint: string; status: string;
};
export type AssessmentDetail = {
  id: string; name: string; mode: 'fresh' | 'worked_example'; synthetic: true; revision: number; stage: number;
  scope: AssessmentScope; assignments: AssessmentPersona[]; sources: AssessmentSource[];
  packages: AssessmentPackage[]; gates: AssessmentGate[]; documents: AssessmentDocument[];
  nextActions: { label: string; operation: string; targetId: string; stage: number }[];
  events: { revision: number; operation: string; targetId: string; principalId: string; createdAt: string; origin: string }[];
  availableOperations: string[];
  phase1InputReportId?: string | null;
  method: { name: string; description: string; confidenceRules: string; prioritizationRules: string; status: string; revision: number };
  questions: { id: string; text: string; whyItMatters: string; doneWhen: string; state: string; familyId?: string | null }[];
  metrics?: {
    questionAnswerability: { supported: number; qualified: number; unanswered: number; total: number; definition: string };
    sourceEnablement: { documentedRoutes: number; syntheticSamplesAdmitted: number; total: number; definition: string };
    decisionBacklog: { pendingSlots: number; oldestAgeDays: number; items: { gateId: string; role: string; submittedAt: string; ageDays: number }[]; definition: string };
  };
};
export type AssessmentSummary = Pick<AssessmentDetail, 'id' | 'name' | 'mode' | 'synthetic' | 'revision' | 'stage'>;
export type AssessmentCatalog = {
  personas: AssessmentPersona[]; stages: AssessmentStage[]; sourceFamilies: AssessmentSource[];
  gates: AssessmentGate[]; operations: string[];
  depthOptions?: { id: string; label: string }[];
};
export type AssessmentCommand = {
  operation: string; targetId: string | null; expectedRevision: number; fields: Record<string, unknown>;
};
