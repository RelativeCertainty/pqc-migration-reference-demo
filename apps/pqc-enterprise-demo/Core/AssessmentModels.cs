using System.Text.Json;
using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

public interface IAssessmentStore
{
    JsonObject Catalog(string principal);
    JsonArray ListAssessments(string principal);
    JsonObject CreateAssessment(string name, string mode, string key, string principal);
    JsonObject GetAssessment(string id, string principal);
    JsonObject ExecuteAssessmentCommand(string id, AssessmentCommand command, string principal);
    JsonObject AssessmentEvidenceSelection(string id, string principal);
    JsonObject? GetAssessmentReport(string id, string reportId, string principal);
    string? RenderAssessmentReportHtml(string id, string reportId, string principal);
    JsonArray AssessmentRuns(string id, string principal);
}

public sealed record AssessmentCommand(string Operation, string? TargetId, JsonObject Fields, int ExpectedRevision, string IdempotencyKey);
public sealed record AssessmentPersona(string PrincipalId, string Role, string Label);
public sealed record AssessmentStage(int Id, string Label, string Question);
public sealed record AssessmentRequirement(string Label, bool Satisfied);
public sealed record AssessmentNextAction(string Label, string Operation, string? TargetId, int Stage);
public sealed record AssessmentQuestion(string Id, string Text, string WhyItMatters, string DoneWhen, string State, string? FamilyId);
public sealed record AssessmentEvent(int Revision, string Operation, string? TargetId, string PrincipalId, string CreatedAt, string Origin);
public sealed record AssessmentAnswerability(int Supported,int Qualified,int Unanswered,int Total,string Definition);
public sealed record AssessmentEnablement(int DocumentedRoutes,int SyntheticSamplesAdmitted,int Total,string Definition);
public sealed record AssessmentPendingDecision(string GateId,string Role,string SubmittedAt,int AgeDays);
public sealed record AssessmentDecisionBacklog(int PendingSlots,int OldestAgeDays,List<AssessmentPendingDecision> Items,string Definition);
public sealed record AssessmentMetrics(AssessmentAnswerability QuestionAnswerability,AssessmentEnablement SourceEnablement,AssessmentDecisionBacklog DecisionBacklog,string AsOf);

public sealed class AssessmentScope
{
    public string Objective { get; set; } = "";
    public string Handling { get; set; } = "";
    public string Method { get; set; } = "";
    public string CycleGoal { get; set; } = "";
    public string ReviewDate { get; set; } = "";
    public List<string> IncludedFamilyIds { get; set; } = [];
    public Dictionary<string, string> ExcludedReasons { get; set; } = new(StringComparer.Ordinal);
    public Dictionary<string, string> DepthByFamily { get; set; } = new(StringComparer.Ordinal);
    public int Revision { get; set; }
}

public sealed class AssessmentSource
{
    public string Id { get; set; } = "";
    public string FamilyId { get; set; } = "";
    public string Name { get; set; } = "";
    public string AreaId { get; set; } = "";
    public List<string> Examples { get; set; } = [];
    public string State { get; set; } = "unanswered";
    public string SystemOfRecord { get; set; } = "";
    public string Product { get; set; } = "";
    public string OwnerFunction { get; set; } = "";
    public string AccessRoute { get; set; } = "";
    public string Note { get; set; } = "";
    public string DueAt { get; set; } = "";
    public List<string> ObservationIds { get; set; } = [];
    public List<string> SubjectIds { get; set; } = [];
    public string EvidenceOrigin { get; set; } = "not_admitted";
    public string RespondedBy { get; set; } = "";
    public string AssertedBy { get; set; } = "";
    public string UpdatedAt { get; set; } = "";
}

public sealed class AssessmentAnalysis
{
    public string Scenario { get; set; } = "";
    public string BusinessImpact { get; set; } = "";
    public string Recommendation { get; set; } = "";
    public string Priority { get; set; } = "planned_review";
    public string Rationale { get; set; } = "";
    public string Confidence { get; set; } = "unknown";
    public string State { get; set; } = "ready";
    public string SubmittedBy { get; set; } = "";
    public string ReviewedBy { get; set; } = "";
    public string Qualification { get; set; } = "";
    public string ReviewDate { get; set; } = "";
    // Optional additive fields: omit absent values so legacy report/gate
    // fingerprints remain byte-compatible until a new analysis is submitted.
    [System.Text.Json.Serialization.JsonIgnore(Condition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? ProtectedInformation { get; set; }
    [System.Text.Json.Serialization.JsonIgnore(Condition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? Lifetime { get; set; }
    [System.Text.Json.Serialization.JsonIgnore(Condition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? AssertedBy { get; set; }
    [System.Text.Json.Serialization.JsonIgnore(Condition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? StatementDate { get; set; }
    [System.Text.Json.Serialization.JsonIgnore(Condition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? CompatibilityConstraints { get; set; }
    [System.Text.Json.Serialization.JsonIgnore(Condition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? VendorConstraints { get; set; }
    [System.Text.Json.Serialization.JsonIgnore(Condition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? OperationalConstraints { get; set; }
    [System.Text.Json.Serialization.JsonIgnore(Condition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? ResponsibleFunction { get; set; }
    [System.Text.Json.Serialization.JsonIgnore(Condition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? NextDecision { get; set; }
}

public sealed class AssessmentPackage
{
    public string Id { get; set; } = "";
    public string FamilyId { get; set; } = "";
    public string Label { get; set; } = "";
    public string State { get; set; } = "ready";
    public string Conclusion { get; set; } = "";
    public string Qualification { get; set; } = "";
    public string SubmittedBy { get; set; } = "";
    public string ReviewedBy { get; set; } = "";
    public string ReviewRationale { get; set; } = "";
    public string ReviewDate { get; set; } = "";
    public int Revision { get; set; }
    public int EvidenceCount { get; set; }
    public int SubjectCount { get; set; }
    public List<string> ObservationIds { get; set; } = [];
    public List<string> SubjectIds { get; set; } = [];
    public List<string> LimitationCodes { get; set; } = [];
    public string PlannedDepth { get; set; } = "routing";
    public string AchievedDepth { get; set; } = "not_established";
    public string DepthLimitation { get; set; } = "";
    public AssessmentAnalysis Analysis { get; set; } = new();
}

public sealed class AssessmentGateDecision
{
    public string Id { get; set; } = "";
    public string PrincipalId { get; set; } = "";
    public string Role { get; set; } = "";
    public string Decision { get; set; } = "";
    public string Rationale { get; set; } = "";
    public string Qualification { get; set; } = "";
    public string ReviewDate { get; set; } = "";
    public string CreatedAt { get; set; } = "";
    public string Fingerprint { get; set; } = "";
    public string Origin { get; set; } = "user_entered_synthetic";
}

public sealed class AssessmentGate
{
    public string Id { get; set; } = "";
    public string Name { get; set; } = "";
    public int Stage { get; set; }
    public List<string> RequiredRoles { get; set; } = [];
    public string State { get; set; } = "not_submitted";
    public List<AssessmentRequirement> Requirements { get; set; } = [];
    public List<AssessmentGateDecision> Decisions { get; set; } = [];
    public int SubmissionRevision { get; set; }
    public string SubmittedBy { get; set; } = "";
    public string Fingerprint { get; set; } = "";
    public string? DocumentId { get; set; }
}

public sealed class AssessmentMethod
{
    public string Name { get; set; } = "";
    public string Description { get; set; } = "";
    public string ConfidenceRules { get; set; } = "";
    public string PrioritizationRules { get; set; } = "";
    public string Status { get; set; } = "illustrative_not_enterprise_approved";
    public int Revision { get; set; }
}

public sealed class AssessmentDocument
{
    public string Id { get; set; } = "";
    public string Phase { get; set; } = "";
    public string CreatedAt { get; set; } = "";
    public string ContentSha256 { get; set; } = "";
    public string InputFingerprint { get; set; } = "";
    public string Status { get; set; } = "draft";
    public string? Phase1ReportId { get; set; }
    public int AssessmentRevision { get; set; }
}

public sealed class AssessmentState
{
    public WorkspaceBinding Workspace { get; set; } = new();
    public DiscoveryState Discovery { get; set; } = new();
    public QuestionnaireState Questionnaires { get; set; } = new();
    public IntakeState Intake { get; set; } = new();
    public string SchemaVersion { get; set; } = "pqc.assessment.v1";
    public string Id { get; set; } = "";
    public string Name { get; set; } = "";
    public string Mode { get; set; } = "fresh";
    public string? ScenarioVersion { get; set; }
    public bool Synthetic { get; set; } = true;
    public int Revision { get; set; }
    public int Stage { get; set; } = 1;
    public string CreatedAt { get; set; } = "";
    public string UpdatedAt { get; set; } = "";
    public string BaselineId { get; set; } = "";
    public string CreatedBy { get; set; } = "";
    public string Boundary { get; set; } = "Synthetic assessment decisions only. No enterprise acceptance, owner product verdict, external delivery or migration execution authority.";
    public AssessmentScope Scope { get; set; } = new();
    public AssessmentMethod Method { get; set; } = new();
    public List<AssessmentPersona> Assignments { get; set; } = [];
    public List<AssessmentSource> Sources { get; set; } = [];
    public List<AssessmentPackage> Packages { get; set; } = [];
    public List<AssessmentGate> Gates { get; set; } = [];
    public List<AssessmentDocument> Documents { get; set; } = [];
    public List<AssessmentQuestion> Questions { get; set; } = [];
    public List<AssessmentNextAction> NextActions { get; set; } = [];
    public List<AssessmentEvent> Events { get; set; } = [];
    public List<string> AvailableOperations { get; set; } = [];
    public string? Phase1InputReportId { get; set; }
    public AssessmentMetrics? Metrics { get; set; }
}

public static class AssessmentJson
{
    // All assessment subsystems share one snapshot. A valid write by one
    // controller must not make another controller reject that same state.
    public const int MaxSnapshotBytes=8_388_608;
    public static readonly JsonSerializerOptions Options = new() { PropertyNamingPolicy = JsonNamingPolicy.CamelCase };
    public static JsonObject Object<T>(T value) => JsonSerializer.SerializeToNode(value, Options)!.AsObject();
    public static AssessmentState State(string value) => JsonSerializer.Deserialize<AssessmentState>(value, Options) ?? throw new DemoStoreException("assessment_state_invalid");
    public static AssessmentState Clone(AssessmentState value) => State(JsonSerializer.Serialize(value, Options));
}
