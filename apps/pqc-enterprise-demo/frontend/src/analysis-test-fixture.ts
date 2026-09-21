// Contract fixtures for tests only. The application never imports this module.
import type { Analysis, Finding } from './analysis-contracts';

export const testFinding: Finding = {
  id: 'finding-test', subjectId: 'asset-test', subjectLabel: 'Synthetic edge', affectedSubjectIds: ['asset-test'],
  title: 'Resolve conflicting key-exchange evidence', observation: 'Two synthetic observations disagree about the configured exchange.',
  implication: 'The review cannot rely on an unqualified configuration assertion.', recommendation: 'Request a dated configuration readback from the responsible platform owner.',
  priority: 'resolve_evidence', priorityRationale: 'Conflicting source records must be reconciled before relying on a conclusion.',
  evidenceState: 'disputed', confidence: 'limited', owner: 'owner-test', serviceId: 'service-test', serviceLabel: 'Synthetic service',
  environment: 'test', technology: 'TLS', familyIds: ['traffic'], observationRefs: ['observation-test'], limitationCodes: ['conflict'],
  riskScenarioId: 'risk-test', impactId: 'impact-test', recommendationId: 'recommendation-test', decisionId: 'decision-test',
  exposure: 'public_key_use', readiness: 'needs_qualification',
};
export const testAnalysis: Analysis = {
  schemaVersion: 'pqc.enterprise.analysis.v1',
  baseline: { baselineId: 'synthetic-baseline-test', inputSha256: 'a'.repeat(64), asOf: '2026-09-01T00:00:00Z', tenantId: 'synthetic-test', synthetic: true, assetCount: 17, acceptanceStatus: 'unaccepted', sourceSystemWriteAuthority: false },
  method: { id: 'synthetic-review', version: '1.0', status: 'illustrative', priorityMeaning: 'Review priority is not an enterprise risk rating.' },
  filterOptions: { services: [{ id: 'service-test', label: 'Synthetic service' }], owners: [{ id: 'owner-test', label: 'Synthetic owner' }], environments: [{ id: 'test', label: 'Test' }], technologies: [{ id: 'TLS', label: 'TLS' }], families: [{ id: 'traffic', label: 'Traffic termination' }] },
  selectedFilters: { service: '', owner: '', environment: '', technology: '', family: '' },
  summary: { assets: 17, findings: 1, observations: 20, cryptographicUses: 29, contextOnlyAssets: 3, staleAssets: 2, disputedAssets: 1, sourceFamilies: 2, estateAreas: 2, decisionsRequired: 1,
    exposureCounts: [{ id: 'public_key_use', count: 1 }], readinessCounts: [{ id: 'needs_qualification', count: 1 }], priorityCounts: [{ id: 'resolve_evidence', count: 1 }] },
  assets: [{ id: 'asset-test', label: 'Synthetic edge', familyIds: ['traffic'], areaRefs: ['area-03'], serviceId: 'service-test', serviceLabel: 'Synthetic service', applicationId: 'app-test', applicationLabel: 'Synthetic application', owner: 'owner-test', environment: 'test', technology: 'TLS', criticality: 'not_assessed', evidenceState: 'disputed', observationRefs: ['observation-test'], useIds: ['use-test'], isStale: false, isDisputed: true, isContextOnly: false }], findings: [testFinding], riskScenarios: [], businessImpacts: [], recommendations: [],
  decisions: [{ id: 'decision-test', subjectId: 'asset-test', title: 'Identify the source authority', rationale: 'The source observations disagree.', observationRefs: ['observation-test'], owner: 'owner-test', action: 'Request the authoritative readback.', readiness: 'needs_qualification', evidenceState: 'disputed' }],
  coverage: [{ areaId: 'area-03', label: 'Encrypted traffic', familyCount: 1, present: 1, missing: 0, stale: 0, disputed: 1, denominator: 'selected subjects', missingMeaning: 'No use evidence', missingFamilies: 0 }],
  graph: { nodes: [{ id: 'node-asset', label: 'Synthetic edge', kind: 'asset', subjectId: 'asset-test', inScope: true, areaRefs: ['area-03'] }, { id: 'node-use', label: 'TLS key exchange', kind: 'cryptographic_use', subjectId: 'asset-test', inScope: true, areaRefs: ['area-03'] }],
    edges: [{ id: 'edge-test', source: 'node-asset', target: 'node-use', relationship: 'uses', observationRefs: ['observation-test'] }], totalNodes: 2, displayedNodes: 2, truncated: false },
  boundary: 'Synthetic test fixture only.',
};
