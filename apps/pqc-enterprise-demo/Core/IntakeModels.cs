using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

// Additive optional state over the existing checksummed assessment snapshots.
// This isolated demonstration does not accept enterprise credentials or execute collection.
public sealed class IntakeState
{
    public string SchemaVersion { get; set; } = "pqc.intake.v1";
    public List<IntakeRequest> Requests { get; set; } = [];
    public List<IntakeSystem> Systems { get; set; } = [];
    public List<IntakeExport> Exports { get; set; } = [];
    public List<IntakeImport> Imports { get; set; } = [];
    public List<IntakeBatch> Batches { get; set; } = [];
    public IntakeReceipt? Receipt { get; set; }
}
public sealed class IntakeRequest
{
    public string Id { get; set; } = "";
    public string Title { get; set; } = "";
    public string FamilyId { get; set; } = "";
    public string AssignedTo { get; set; } = "";
    public string Status { get; set; } = "draft";
    public string WhyItMatters { get; set; } = "Identify which systems and functions can supply evidence for the current-state assessment.";
    public List<string> Examples { get; set; } = [];
    public List<string> SystemIds { get; set; } = [];
    public Dictionary<string,string> Answers { get; set; } = new(StringComparer.Ordinal);
    public string AssertedBy { get; set; } = "";
    public string RecordedBy { get; set; } = "";
    public string Determination { get; set; } = "awaiting_review";
    public string Limitation { get; set; } = "";
    public string ReviewedBy { get; set; } = "";
    public string TemplateVersion { get; set; } = "pqc.routing-questionnaire.v1";
}
public sealed class IntakeSystem
{
    public string Id { get; set; } = "";
    public string RequestId { get; set; } = "";
    public string Label { get; set; } = "";
    public string Product { get; set; } = "";
    public string Environment { get; set; } = "";
    public string SystemRole { get; set; } = "subject";
    public string AboutSystemId { get; set; } = "";
}
public sealed class IntakeExport
{
    public string Id { get; set; } = "";
    public string RequestId { get; set; } = "";
    public string TemplateVersion { get; set; } = "";
    public string AssignedTo { get; set; } = "";
    public Dictionary<string,string> Baseline { get; set; } = new(StringComparer.Ordinal);
    public Dictionary<string,string> RowLabels { get; set; } = new(StringComparer.Ordinal);
    public string BytesBase64 { get; set; } = "";
    public string Sha256 { get; set; } = "";
}
public sealed class IntakeImport
{
    public string Id { get; set; } = "";
    public string RequestId { get; set; } = "";
    public string ExportId { get; set; } = "";
    public string PrincipalId { get; set; } = "";
    public string RequestFingerprint { get; set; } = "";
    public string SourceSha256 { get; set; } = "";
    public string OriginalBase64 { get; set; } = "";
    public Dictionary<string,string> Returned { get; set; } = new(StringComparer.Ordinal);
    public List<IntakeChange> Changes { get; set; } = [];
    public bool Committed { get; set; }
}
public sealed record IntakeChange(string Key,string Baseline,string Current,string Returned,string State);
public sealed record IntakeReceipt(string Effect,string NextResponsible,string NextAction);
public sealed record IntakeQuestion(string Id,string Label,string WhyItMatters,string UsefulResponse);
public sealed class IntakeBatch
{
    public string Id { get; set; } = "";
    public string RequestId { get; set; } = "";
    public string SystemId { get; set; } = "";
    public string SourceSystemId { get; set; } = "";
    public string ContentSha256 { get; set; } = "";
    public string OriginalBase64 { get; set; } = "";
    public string Status { get; set; } = "staged";
    public string ReceivedAt { get; set; } = "";
    public List<IntakeObservation> Observations { get; set; } = [];
}
public sealed record IntakeObservation(string Id,string SystemId,string SourceSystemId,string NativeId,string Hostname,string KeyExchange,string Authentication,string Basis,string ContentSha256);

public interface IIntakeStore
{
    JsonObject IntakeView(string id,string principal);
    JsonObject IntakeCommand(string id,AssessmentCommand command,string principal);
    JsonObject ExportIntake(string id,string requestId,int revision,string key,string principal);
    byte[] DownloadIntake(string id,string exportId,string principal);
    JsonObject PreviewIntake(string id,string requestId,int revision,string key,string principal,IntakeWorkbookReturn workbook,byte[] original);
    JsonObject StageIntakeEvidence(string id,string requestId,string systemId,string sourceSystemId,int revision,string key,string principal,byte[] original);
}
