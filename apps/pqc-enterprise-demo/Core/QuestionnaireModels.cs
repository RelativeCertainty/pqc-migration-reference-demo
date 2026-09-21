using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace PqcEnterpriseDemo;

public sealed class QuestionnaireCatalog
{
    public string SchemaVersion { get; set; } = "";
    public string CatalogId { get; set; } = "";
    public string CatalogVersion { get; set; } = "";
    public string SourceSchemaVersion { get; set; } = "";
    public string SourceSha256 { get; set; } = "";
    public string SourceClassification { get; set; } = "";
    public string SourceStatus { get; set; } = "";
    public string RecognitionBoundary { get; set; } = "";
    public string RecognitionSha256 { get; set; } = "";
    public JsonObject OperatingContract { get; set; } = new();
    public List<string> ScheduleEffects { get; set; } = [];
    public List<QuestionnaireTemplate> Templates { get; set; } = [];
}
public sealed class QuestionnaireTemplate
{
    public string Id { get; set; } = "";
    public string Title { get; set; } = "";
    public string SystemType { get; set; } = "";
    public string Purpose { get; set; } = "";
    public string RequiredSourceProfile { get; set; } = "";
    public string DefaultCoordinatingRole { get; set; } = "";
    public List<string> ExpectedContributingRoles { get; set; } = [];
    public List<string> Examples { get; set; } = [];
    public List<QuestionnaireQuestion> Questions { get; set; } = [];
}
public sealed class QuestionnaireQuestion
{
    public string Id { get; set; } = "";
    public string SourceId { get; set; } = "";
    public string Section { get; set; } = "";
    public string Prompt { get; set; } = "";
    public string WhyItMatters { get; set; } = "";
    public string ResponseType { get; set; } = "";
    public bool Required { get; set; }
    public string EvidenceExpectation { get; set; } = "";
    public string CompletionCriteria { get; set; } = "";
    public List<string> AllowedValues { get; set; } = [];
}
public sealed class QuestionnaireState
{
    public List<QuestionnaireAssignment> Assignments { get; set; } = [];
    public QuestionnaireExchangeState Exchange { get; set; } = new();
}
public sealed class QuestionnaireDeployment
{
    public string Id { get; set; } = "";
    public string Label { get; set; } = "";
    public string Product { get; set; } = "";
    public string Environment { get; set; } = "";
}
public sealed class QuestionnaireAnswer
{
    public string Status { get; set; } = "unanswered";
    public string Text { get; set; } = "";
    public List<string> EvidenceRefs { get; set; } = [];
    public string Rationale { get; set; } = "";
    public string NextOwner { get; set; } = "";
    public string NextDate { get; set; } = "";
    public string Blocker { get; set; } = "";
    public string ScheduleEffect { get; set; } = "";
    public string AssertedBy { get; set; } = "";
    public string RecordedBy { get; set; } = "";
    public string AttestationOwner { get; set; } = "";
    public string AttestationDate { get; set; } = "";
    public string AttestationQualification { get; set; } = "";
}
public sealed class QuestionnaireAssignment
{
    public string Id { get; set; } = "";
    public string Title { get; set; } = "";
    public string TemplateId { get; set; } = "";
    public string TemplateVersion { get; set; } = "";
    public string TemplateSha256 { get; set; } = "";
    public string SourceSchemaVersion { get; set; } = "";
    public string SourceSha256 { get; set; } = "";
    public string SourceClassification { get; set; } = "";
    public string SourceStatus { get; set; } = "";
    public string RecognitionBoundary { get; set; } = "";
    public QuestionnaireTemplate Template { get; set; } = new();
    public JsonObject OperatingContract { get; set; } = new();
    public List<string> ScheduleEffects { get; set; } = [];
    public QuestionnaireDeployment Deployment { get; set; } = new();
    public string AssignedTo { get; set; } = "";
    public string Status { get; set; } = "draft";
    public Dictionary<string,QuestionnaireAnswer> Answers { get; set; } = new(StringComparer.Ordinal);
    public QuestionnaireSubmission? Submission { get; set; }
    public List<QuestionnaireHistoryEntry> History { get; set; } = [];
    public string? Receipt { get; set; }
}
public sealed record QuestionnaireSubmission(string SubmittedAt,string SubmittedBy,List<string> UnresolvedQuestionIds,string ContentSha256);
public sealed record QuestionnaireHistoryEntry(string Operation,int Revision,string Actor,string OccurredAt,string Reason,string PreviousAssignedTo,string AssignedTo,string? PreviousSubmissionSha256);
public sealed record QuestionnaireIssue(string QuestionId,string Field,string Message);
public sealed record QuestionnaireValidation(bool CanSubmit,List<QuestionnaireIssue> Issues);
public interface IQuestionnaireStore
{
    JsonObject Questionnaires(string id,string principal);
    JsonObject Questionnaire(string id,string assignmentId,string principal);
    JsonObject QuestionnaireCommand(string id,AssessmentCommand command,string principal);
}

public static class QuestionnaireCatalogLoader
{
    private static readonly Lazy<QuestionnaireCatalog?> Loaded=new(Load);
    public static QuestionnaireCatalog? Current=>Loaded.Value;
    private static QuestionnaireCatalog? Load()
    {
        var path=Environment.GetEnvironmentVariable("PQC_QUESTIONNAIRE_CATALOG_FILE");
        if(string.IsNullOrWhiteSpace(path))return null;
        try
        {
            var info=new FileInfo(Path.GetFullPath(path));
            if(!info.Exists || info.Length is <1 or >8_388_608 || info.LinkTarget is not null)throw new InvalidDataException();
            for(var parent=info.Directory;parent is not null;parent=parent.Parent)
                if(parent.LinkTarget is not null)throw new InvalidDataException();
            var content=File.ReadAllText(info.FullName);
            if(System.Text.Encoding.UTF8.GetByteCount(content)>8_388_608)throw new InvalidDataException();
            var catalog=JsonSerializer.Deserialize<QuestionnaireCatalog>(content,AssessmentJson.Options) ?? throw new InvalidDataException();
            if(catalog.Templates.Count!=27 || catalog.Templates.Select(t=>t.Id).Distinct().Count()!=27 ||
                catalog.SchemaVersion!="pqc.questionnaire-catalog.v1" || !Regex.IsMatch(catalog.SourceSha256,"\\A[a-f0-9]{64}\\z",RegexOptions.CultureInvariant) ||
                string.IsNullOrWhiteSpace(catalog.SourceSchemaVersion) || catalog.CatalogVersion!=catalog.SourceSchemaVersion+"@sha256:"+catalog.SourceSha256 ||
                string.IsNullOrWhiteSpace(catalog.SourceClassification) || string.IsNullOrWhiteSpace(catalog.SourceStatus) ||
                string.IsNullOrWhiteSpace(catalog.RecognitionBoundary) || catalog.ScheduleEffects.Count==0 || catalog.ScheduleEffects.Any(string.IsNullOrWhiteSpace))throw new InvalidDataException();
            var expected=Enumerable.Range(1,27).Select(n=>$"SRC-RFI-{n:000}").ToHashSet(StringComparer.Ordinal);
            if(!expected.SetEquals(catalog.Templates.Select(t=>t.Id)))throw new InvalidDataException();
            var questionIds=Enumerable.Range(1,24).Select(n=>$"CQ-{n:00}").Concat(Enumerable.Range(1,3).Select(n=>$"SQ-{n:00}")).ToHashSet(StringComparer.Ordinal);
            foreach(var template in catalog.Templates)
                if(template.Questions.Count!=27 || !questionIds.SetEquals(template.Questions.Select(q=>q.SourceId)) ||
                    template.Questions.Any(q=>q.Id!=template.Id+"/"+q.SourceId || string.IsNullOrWhiteSpace(q.Prompt) || string.IsNullOrWhiteSpace(q.Section) ||
                        !q.Required || string.IsNullOrWhiteSpace(q.EvidenceExpectation) || string.IsNullOrWhiteSpace(q.CompletionCriteria) ||
                        q.ResponseType is not ("controlled_value" or "long_text" or "reference_list" or "structured_profile") ||
                        q.AllowedValues.Any(string.IsNullOrWhiteSpace) || q.ResponseType=="controlled_value" && q.AllowedValues.Count==0))throw new InvalidDataException();
            return catalog;
        }
        catch(Exception e) when(e is IOException or UnauthorizedAccessException or JsonException or InvalidOperationException)
        {throw new DemoStoreException("questionnaire_catalog_invalid");}
    }
}
