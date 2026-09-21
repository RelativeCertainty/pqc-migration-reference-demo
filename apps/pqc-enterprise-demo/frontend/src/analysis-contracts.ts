import type { Baseline } from './contracts';

export type AnalysisFilter = 'service' | 'owner' | 'environment' | 'technology' | 'family';
export type FilterState = Record<AnalysisFilter, string>;
export type Finding = {
  id: string; subjectId: string; subjectLabel: string; affectedSubjectIds: string[];
  title: string; observation: string; implication: string; recommendation: string;
  priority: string; priorityRationale: string; evidenceState: string; confidence: string;
  owner: string; serviceId: string; serviceLabel: string; environment: string; technology: string;
  familyIds: string[]; observationRefs: string[]; limitationCodes: string[];
  riskScenarioId: string; impactId: string; recommendationId: string; decisionId: string;
  exposure: string; readiness: string;
};
export type AnalysisRecord = { id: string; subjectId: string; title: string; rationale: string;
  observationRefs: string[]; owner: string; action: string; readiness: string; evidenceState: string };
export type Distribution = { id: string; count: number }[];
export type Analysis = {
  schemaVersion: string; baseline: Baseline; method: { id: string; version: string; status: string; priorityMeaning: string };
  filterOptions: Record<'services' | 'owners' | 'environments' | 'technologies' | 'families', { id: string; label: string }[]>;
  selectedFilters: FilterState;
  summary: { assets: number; findings: number; observations: number; cryptographicUses: number;
    contextOnlyAssets: number; staleAssets: number; disputedAssets: number; sourceFamilies: number;
    estateAreas: number; decisionsRequired: number; exposureCounts: Distribution; readinessCounts: Distribution; priorityCounts: Distribution };
  assets: { id: string; label: string; familyIds: string[]; areaRefs: string[]; serviceId: string; serviceLabel: string;
    applicationId: string; applicationLabel: string; owner: string; environment: string; technology: string;
    criticality: string; evidenceState: string; observationRefs: string[]; useIds: string[];
    isStale: boolean; isDisputed: boolean; isContextOnly: boolean }[];
  findings: Finding[]; riskScenarios: AnalysisRecord[]; businessImpacts: AnalysisRecord[];
  recommendations: AnalysisRecord[]; decisions: AnalysisRecord[];
  coverage: { areaId: string; label: string; familyCount: number; present: number; missing: number;
    stale: number; disputed: number; denominator: string; missingMeaning: string; missingFamilies?: number }[];
  graph: { nodes: { id: string; label: string; kind: string; subjectId: string; inScope: boolean; areaRefs: string[] }[];
    edges: { id: string; source: string; target: string; relationship: string; observationRefs: string[] }[];
    totalNodes: number; displayedNodes: number; truncated: boolean };
  boundary: string;
};
export type ActionRecord = {
  id: string; findingId: string; operation: string; disposition: string | null; note: string;
  revision: number; createdAt: string; actor: string; evidenceRequestDraft: string | null;
  status: 'in_review' | 'needs_evidence' | 'reviewed' | 'deferred'; synthetic: true;
  externalDelivery: false; executionAuthorized: false;
};
export type Narrative = {
  executiveSummary: { title: string; body: string }[];
  sections: { id: string; title: string; summary: string; paragraphs: string[]; findingIds: string[] }[];
  nextSteps: { title: string; owner: string; action: string; decisionRequired: string; consequence: string; dueAt?: string }[];
  questions: string[]; caveats: string[];
};
