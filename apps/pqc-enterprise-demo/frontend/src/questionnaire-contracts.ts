export type QuestionnaireAnswerStatus = 'unanswered' | 'answered' | 'unknown' | 'blocked' | 'unavailable' | 'not_applicable';
export interface QuestionnaireAnswer {
  status: QuestionnaireAnswerStatus;
  text: string;
  evidenceRefs: string[];
  rationale: string;
  nextOwner: string;
  nextDate: string;
  blocker: string;
  scheduleEffect: string;
  attestationOwner: string;
  attestationDate: string;
  attestationQualification: string;
  assertedBy?: string;
  recordedBy?: string;
}
export interface QuestionnaireQuestion {
  id: string;
  sourceId?: string;
  section: string;
  prompt: string;
  whyItMatters: string;
  responseType: 'structured_profile' | 'reference_list' | 'long_text' | 'controlled_value' | string;
  required: boolean;
  evidenceExpectation: string;
  completionCriteria: string;
  allowedValues: string[];
}
export interface QuestionnaireTemplate {
  id: string;
  title: string;
  systemType: string;
  purpose?: string;
  requiredSourceProfile?: string;
  examples: string[];
  questions: QuestionnaireQuestion[];
}
export interface QuestionnaireAssignmentSummary {
  id: string;
  title: string;
  templateId: string;
  templateVersion: string;
  deployment: { id: string; label: string; product: string; environment: string };
  assignedTo: string;
  status: 'draft' | 'submitted';
  questionCount: number;
  answeredCount: number;
}
export interface QuestionnaireList {
  assessmentId: string;
  assessmentName: string;
  revision: number;
  canCoordinate: boolean;
  assignments: QuestionnaireAssignmentSummary[];
  catalog: { available: boolean; catalogId: string; catalogVersion: string; scheduleEffects?: string[]; templates: QuestionnaireTemplate[] };
}
export interface QuestionnaireDetail {
  assessmentId: string;
  assessmentName: string;
  revision: number;
  canEdit: boolean;
  canCoordinate: boolean;
  assignment: QuestionnaireAssignmentSummary & {
    template: QuestionnaireTemplate;
    scheduleEffects: string[];
    answers: Record<string, QuestionnaireAnswer>;
    submission: { submittedAt: string; submittedBy: string; unresolvedQuestionIds: string[] } | null;
  };
  validation: { canSubmit: boolean; issues: { questionId: string; field: string; message: string }[] };
  receipt: string | null;
}
export interface QuestionnaireCommand {
  operation: 'questionnaire_create' | 'questionnaire_save' | 'questionnaire_submit' | 'questionnaire_reopen' | 'questionnaire_reassign';
  targetId: string | null;
  expectedRevision: number;
  fields: Record<string, unknown>;
}
export interface QuestionnaireExport { exportId: string; downloadUrl: string; revision: number }
export interface QuestionnaireImport {
  revision: number;
  import: { id: string; assignmentId: string; exportId: string; committed: boolean; changes: { questionId: string; baseline: Record<string, string>; current: Record<string, string>; returned: Record<string, string>; state: 'unchanged' | 'change' | 'conflict' }[] };
}
