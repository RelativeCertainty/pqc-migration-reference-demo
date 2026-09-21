using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

public sealed class DiscoveryState
{
    public DiscoveryExchangeState Exchange { get; set; } = new();
    public List<DiscoveryRequest> Requests { get; set; } = [];
    public List<DiscoveryCollection> Collections { get; set; } = [];
    public List<DiscoveryStandard> Standards { get; set; } = DiscoveryWorkflow.StandardTemplates();
    public List<DiscoveryInvestigation> Investigations { get; set; } = [];
}
public sealed record DiscoveryQuestion(string Id,string Prompt,string WhyItMatters,List<string> Examples,string UsefulResponse);
public sealed record DiscoveryGuidance(string Introduction,string HandlingNotice,string ReviewNotice,string SubmissionReceipt,string LegacyNotice);
public sealed class DiscoveryAnswer
{
    public string Status { get; set; } = "unanswered";
    public string Text { get; set; } = "";
    public string Reference { get; set; } = "";
    public string AssertedBy { get; set; } = "";
    public string RecordedBy { get; set; } = "";
}
public sealed class DiscoveryProductRef
{
    public string Id { get; set; } = "";
    public string Label { get; set; } = "";
    public string Product { get; set; } = "";
    public string Environment { get; set; } = "";
    public string RecordedBy { get; set; } = "";
    public string RecordedAt { get; set; } = "";
}
public sealed class DiscoveryRequest
{
    public string Id { get; set; } = "";
    public string Title { get; set; } = "";
    public string FamilyId { get; set; } = "";
    public string FamilyName { get; set; } = "";
    // An omitted version in a legacy snapshot must not acquire newer wording.
    // New requests explicitly select the current version at creation.
    public string TemplateVersion { get; set; } = "pqc.discovery.v1";
    public string TemplateSha256 { get; set; } = "";
    public List<DiscoveryQuestion> Questions { get; set; } = [];
    public List<string> Examples { get; set; } = [];
    public string AssignedTo { get; set; } = "";
    public string Status { get; set; } = "draft";
    public Dictionary<string,DiscoveryAnswer> Answers { get; set; } = new(StringComparer.Ordinal);
    public List<DiscoveryProductRef> ProductRefs { get; set; } = [];
    public DiscoverySubmission? Submission { get; set; }
    public List<DiscoveryHistoryEntry> History { get; set; } = [];
    public string? Receipt { get; set; }
}
public sealed record DiscoverySubmission(string SubmittedAt,string SubmittedBy,string ContentSha256);
public sealed record DiscoveryHistoryEntry(string Operation,int Revision,string Actor,string OccurredAt,string Reason,string? PreviousSubmissionSha256);
public sealed record DiscoveryValidation(bool CanSubmit,List<string> Issues);
public sealed class DiscoveryStandard
{
    public string Id { get; set; } = "";
    public string Title { get; set; } = "";
    public string Version { get; set; } = "pqc.standard-proposal.v1";
    public string Status { get; set; } = "draft";
    public string Purpose { get; set; } = "";
    public int Revision { get; set; }
    public string RecordedBy { get; set; } = "";
    public string RecordedAt { get; set; } = "";
    public string ObservedPractice { get; set; } = "";
    public List<DiscoveryPublicationRef> PublicationRefs { get; set; } = [];
    public string ProposalText { get; set; } = "";
    public string ExistingRequirementStatus { get; set; } = "unassessed";
    public List<string> ExistingRequirementRefs { get; set; } = [];
    public string AuthorityStatus { get; set; } = "unassigned";
    public string ProposedAuthority { get; set; } = "";
    public string ConflictReviewStatus { get; set; } = "unassessed";
    public string ConflictNote { get; set; } = "";
}
public sealed record DiscoveryPublicationRef(string Title,string Url,string Status);
public sealed partial class DiscoveryInvestigation
{
    public string Id { get; set; } = "";
    public string RequestId { get; set; } = "";
    public string FamilyId { get; set; } = "";
    public List<string> ProductRefIds { get; set; } = [];
    public List<DiscoveryProductRef> ProductRefs { get; set; } = [];
    public string AssignedTo { get; set; } = "";
    public string Status { get; set; } = "planned";
    public string Purpose { get; set; } = "";
    public string ResearchSummary { get; set; } = "";
    public string ProposedMethod { get; set; } = "";
    public List<string> DocumentationRefs { get; set; } = [];
    public string Limitation { get; set; } = "";
    public int Revision { get; set; }
    public string RecordedBy { get; set; } = "";
    public string RecordedAt { get; set; } = "";
    public string? IntakeRequestId { get; set; }
    public List<DiscoveryEvidenceReview> EvidenceReviews { get; set; } = [];
}
public interface IDiscoveryStore
{
    JsonObject Discovery(string id,string principal);
    JsonObject DiscoveryRequest(string id,string requestId,string principal);
    JsonObject DiscoveryCommand(string id,AssessmentCommand command,string principal);
}
