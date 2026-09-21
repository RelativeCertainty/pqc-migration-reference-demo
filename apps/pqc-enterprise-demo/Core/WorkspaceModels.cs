using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

/// <summary>Only small material references live in an assessment snapshot.
/// Original return bytes and versioned workspace records live in side tables.</summary>
public sealed class WorkspaceBinding
{
    public int ThroughRevision { get; set; }
    public string MaterialFingerprint { get; set; } = "";
    [System.Text.Json.Serialization.JsonIgnore(Condition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
    public string? Phase1MaterialFingerprint { get; set; }
}

public interface IAssessmentWorkStore
{
    JsonObject AssessmentWork(string assessmentId, string principal);
    JsonObject AssessmentWorkCase(string assessmentId, string requestId, string principal);
    JsonObject ReceiveOperationalReturn(string assessmentId, string requestId, int revision, string key,
        string principal, string filename, byte[] original, OperationalReturnDto parsed);
    JsonObject WorkspaceReceipt(string assessmentId, string receiptId, string principal);
    JsonObject WorkspaceCommand(string assessmentId, AssessmentCommand command, string principal);
    JsonObject PreviewWorkspaceConsequence(string assessmentId, AssessmentCommand command, string principal);
    JsonObject WorkspaceObservations(string assessmentId, string bundleId, string principal, int page=1, int pageSize=25);
    JsonObject StageWorkspaceEvidence(string assessmentId, string requestId, string productId, int revision,
        string key, string principal, byte[] original, JsonObject parsed);
}
