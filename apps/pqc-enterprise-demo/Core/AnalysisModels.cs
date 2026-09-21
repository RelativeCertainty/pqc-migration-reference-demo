using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

public sealed record AnalysisFilter(string? Service = null, string? Owner = null, string? Environment = null, string? Technology = null, string? Family = null);
public sealed record AnalysisOption(string Id, string Label);
public sealed record AnalysisCount(string Id, int Count);

public sealed record AnalysisAsset(
    string Id, string Label, string[] FamilyIds, string[] AreaRefs,
    string ServiceId, string ServiceLabel, string ApplicationId, string ApplicationLabel,
    string Owner, string Environment, string Technology, string Criticality, string EvidenceState,
    string[] ObservationRefs, string[] UseIds,
    string[] ServiceIds, string[] ApplicationIds, string[] OwnerIds, string[] Environments, string[] Technologies,
    bool IsStale, bool IsDisputed, bool IsContextOnly, string[] ContextObservationRefs);

public sealed record AnalysisFinding(
    string Id, string SubjectId, string SubjectLabel, string[] AffectedSubjectIds,
    string Title, string Observation, string Implication, string Recommendation,
    string Priority, string PriorityRationale, string EvidenceState, string Confidence,
    string Owner, string ServiceId, string ServiceLabel, string Environment, string Technology,
    string[] FamilyIds, string[] ObservationRefs, string[] LimitationCodes,
    string RiskScenarioId, string ImpactId, string RecommendationId, string DecisionId,
    string Exposure, string Readiness);

public sealed record AnalysisLinkedRecord(
    string Id, string SubjectId, string Title, string Rationale, string[] ObservationRefs,
    string Owner, string Action, string Readiness, string EvidenceState,
    string Status = "proposed_review_not_authorization");

public sealed record AnalysisCoverage(
    string AreaId, string Label, int FamilyCount, int Present, int Missing, int Stale, int Disputed,
    int MissingFamilies, string Denominator, string MissingMeaning);

public sealed record AnalysisGraphNode(string Id, string Label, string Kind, string SubjectId, bool InScope, string[] AreaRefs);
public sealed record AnalysisGraphEdge(string Id, string Source, string Target, string Relationship, string[] ObservationRefs);
public sealed record AnalysisGraph(AnalysisGraphNode[] Nodes, AnalysisGraphEdge[] Edges, int TotalNodes, int DisplayedNodes, bool Truncated,
    string Boundary = "Bounded evidence-linked projection; outside-filter neighbours are context, not selected inventory. Reference-only service names and unresolved targets are not invented facts.");

public sealed record AnalysisMethod(string Id, string Version, string Status, string PriorityMeaning,
    JsonObject SourceMethod, string CountGrain,
    Dictionary<string, string> ExposureMeanings, Dictionary<string, string> ReadinessMeanings);
