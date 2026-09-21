export type IntakeRequest = {
  id: string; title: string; familyId: string; assignedTo: string; status: string;
  whyItMatters: string; examples: string[]; systemIds: string[]; answers: Record<string, string>;
  assertedBy: string; recordedBy: string; determination: string; limitation: string;
};
export type IntakeSystem = {
  id: string; requestId: string; label: string; product: string; environment: string;
  systemRole: 'subject' | 'source' | 'both'; aboutSystemId: string;
};
export type IntakeQuestion = { id: string; label: string; whyItMatters: string; usefulResponse: string };
export type IntakeView = {
  assessmentId: string; assessmentName: string; revision: number; role: string; synthetic: true;
  requests: IntakeRequest[]; systems: IntakeSystem[]; questions: IntakeQuestion[];
  eligibleFamilyIds?: string[];
  receipt: { effect: string; nextResponsible: string; nextAction: string } | null;
  evidence: { id: string; systemId: string; sourceSystemId: string; hostname: string; keyExchange: string; authentication: string; basis: string; contentSha256: string }[];
  pendingEvidence: { id: string; requestId: string; systemId: string; sourceSystemId: string; count: number; contentSha256: string }[];
  reportPreview: { summary: string; conclusions: string[]; limitations: string[]; nextDecisions: string[] };
  canCoordinate: boolean; canReview: boolean; canAdmit: boolean; boundary: string;
};
export type IntakeExport = { exportId: string; downloadUrl: string; revision: number };
export type IntakeImport = {
  previewId: string; revision: number;
  changes: { key: string; baseline: string; current: string; returned: string; state: 'change' | 'conflict' | 'unchanged' }[];
};
export type IntakeCommand = { operation: string; targetId: string | null; fields: Record<string, unknown>; expectedRevision: number };
