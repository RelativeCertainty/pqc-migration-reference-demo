export type SectionId =
  | "overview"
  | "architecture"
  | "tvm-mapping"
  | "inventory"
  | "lab"
  | "prioritization"
  | "workflow"
  | "scenarios"
  | "decisions"
  | "patterns"
  | "posture"
  | "dashboard"
  | "questions";

export interface NavigationSection {
  id: SectionId;
  shortLabel: string;
  title: string;
  eyebrow: string;
  interviewStep?: number;
}

export type InventoryPriority = "Urgent" | "High" | "Moderate" | "Low";
export type SoftwareEstateClass = "source-code" | "ots-cots" | "third-party-saas";
export type CryptoIssueType =
  | "tls-protocol"
  | "certificate-trust"
  | "implementation-configuration"
  | "source-code-crypto-use"
  | "cryptographic-dependency"
  | "algorithm-key-strength"
  | "vendor-control";
export type MigrationStatus =
  | "Discovery"
  | "Assessment"
  | "Planned"
  | "Pilot"
  | "Migrating"
  | "Validated"
  | "Exception";

export type SyntheticSystemId =
  | "syn-api-edge-01"
  | "syn-pay-java-02"
  | "syn-vpn-03"
  | "syn-ca-04"
  | "syn-k8s-05"
  | "syn-sign-06"
  | "syn-sftp-07"
  | "syn-ssh-08"
  | "syn-mobile-09"
  | "syn-archive-10";

export type EvidenceAssessment =
  | "verified"
  | "partially_verified"
  | "probable"
  | "assumption"
  | "unresolved";

export interface EvidenceProvenance {
  readonly kind: "synthetic_fixture";
  readonly sourceLocator: string;
  readonly synthetic: true;
}

export interface EvidenceConfidence {
  readonly level: "illustrative";
  readonly rationale: string;
}

export interface EvidenceObservation {
  readonly kind: "synthetic_fixture_declaration";
  readonly observedAt: null;
  readonly declaredOn: string;
  readonly runtimeObserved: false;
}

export interface EvidenceDisposition {
  readonly state: EvidenceAssessment;
  readonly owner: string;
  readonly reviewDate: string;
}

export interface EvidenceTestReference {
  readonly result: "not_executed_in_artifact";
  readonly locator: string;
  readonly scope: string;
}

export interface SyntheticEvidenceRecord {
  readonly evidenceId: string;
  readonly systemId: SyntheticSystemId;
  readonly stageRef: "pqc-lifecycle-stage:2";
  readonly provenance: EvidenceProvenance;
  readonly confidence: EvidenceConfidence;
  readonly observation: EvidenceObservation;
  readonly evidence: EvidenceDisposition;
  readonly test: EvidenceTestReference;
  readonly residualGaps: readonly string[];
}

export interface SyntheticEvidenceArtifact {
  readonly schemaVersion: "pqc.synthetic-evidence.v1";
  readonly artifactId: "pqc-reference-demo-discovery-inventory";
  readonly artifactVersion: "1.0.0";
  readonly synthetic: true;
  readonly declaredOn: string;
  readonly stage: {
    readonly ref: "pqc-lifecycle-stage:2";
    readonly ordinal: 2;
    readonly label: "Discovery & Inventory";
  };
  readonly records: readonly SyntheticEvidenceRecord[];
}

export interface CryptoSystem {
  id: SyntheticSystemId;
  synthetic: true;
  asset: string;
  application: string;
  estateClass: SoftwareEstateClass;
  issueTypes: readonly CryptoIssueType[];
  businessService: string;
  environment: "Production" | "Pre-production" | "Development";
  owner: string;
  cryptographicUse: string;
  protocol: string;
  algorithm: string;
  credential: string;
  issuer: string;
  runtime: string;
  exposure: "Internet" | "Partner" | "Internal" | "Restricted";
  sensitivity: "Critical" | "High" | "Moderate" | "Low";
  retention: string;
  dependencyCount: number;
  vendorManaged: boolean;
  cryptoAgility: "High" | "Moderate" | "Low";
  readiness: "Ready" | "Assessing" | "Blocked" | "Unknown";
  priority: InventoryPriority;
  status: MigrationStatus;
  migrationPattern: string;
  evidence: SyntheticEvidenceRecord;
}

export interface MaturityScenario {
  id: "mature" | "partial" | "fragmented" | "low-visibility";
  label: string;
  headline: string;
  available: string[];
  strategy: string;
  customEngineering: "Low" | "Moderate" | "Moderate to high" | "High initially";
  manualEffort: "Low" | "Medium" | "High";
  integrationNeed: "Medium" | "High";
  timeToValue: "Faster" | "Balanced" | "Slower initially";
  decision: string;
}

export interface MigrationPattern {
  id: string;
  title: string;
  scope: string;
  steps: string[];
  validation: string;
  caveat: string;
}

export interface QuestionGroup {
  category: string;
  questions: string[];
}

export interface RiskInputs {
  algorithmRisk: number;
  dataSensitivity: number;
  retentionLifetime: number;
  harvestNowRelevance: number;
  publicExposure: number;
  businessCriticality: number;
  dependencyDepth: number;
  migrationComplexity: number;
  vendorDependency: number;
  platformReadiness: number;
  cryptoAgility: number;
  compensatingControls: number;
}

export interface RiskContribution {
  key: keyof RiskInputs;
  label: string;
  points: number;
  kind: "driver" | "reduction";
}

export interface RiskResult {
  score: number;
  priority: InventoryPriority;
  contributions: RiskContribution[];
  primaryDrivers: RiskContribution[];
}

export interface RuntimePosture {
  schema_version: "pqc-posture.v2";
  evidence_tier: "request_transport_observation";
  observed_at: string;
  hostname: string;
  request_transport: {
    tls_version: { state: "observed" | "unavailable"; value: string | null };
    tls_cipher: { state: "observed" | "unavailable"; value: string | null };
    http_protocol: { state: "observed" | "unavailable"; value: string | null };
    exact_session_key_exchange: { state: "not_observable"; explanation: string };
  };
  hostname_capability: {
    state: "not_observable_by_handler";
    explanation: string;
  };
  visitor_edge_post_quantum_signatures: {
    state: "not_deployed";
    explanation: string;
  };
  access_control: {
    state: "not_observable_by_handler";
    target: "Cloudflare Access";
  };
  evidence_separation: {
    algorithm_standards: string;
    cryptographic_module: string;
  };
  data_posture: {
    storage: "none";
    upstream_origin_dependency: "none";
    dataset: "synthetic_only";
    request_logging: "not_implemented_by_application";
  };
  approved_deployment_label: {
    label: "PQC migration reference package";
    eligible: false;
    reason: string;
  };
}

export type EvidenceState =
  | "Supported"
  | "Final standard"
  | "Observed"
  | "Development evidence"
  | "Planned"
  | "Environment dependent"
  | "Not validated"
  | "Not observable"
  | "Not deployed"
  | "Not implemented";
