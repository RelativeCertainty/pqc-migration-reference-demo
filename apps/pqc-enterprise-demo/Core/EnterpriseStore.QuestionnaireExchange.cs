using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

public sealed class QuestionnaireExchangeState
{
    public List<QuestionnaireExport> Exports {get;set;}=[];
    public List<QuestionnaireImport> Imports {get;set;}=[];
}
public sealed class QuestionnaireExport
{
    public string Id {get;set;}="";
    public string AssignmentId {get;set;}="";
    public string AssignedTo {get;set;}="";
    public string TemplateSha256 {get;set;}="";
    public Dictionary<string,Dictionary<string,string>> Baseline {get;set;}=new(StringComparer.Ordinal);
    public string BytesBase64 {get;set;}="";
    public string Sha256 {get;set;}="";
}
public sealed class QuestionnaireImport
{
    public string Id {get;set;}="";
    public string AssignmentId {get;set;}="";
    public string ExportId {get;set;}="";
    public string PrincipalId {get;set;}="";
    public string SourceSha256 {get;set;}="";
    public string OriginalBase64 {get;set;}="";
    public string PreviewFingerprint {get;set;}="";
    public List<QuestionnaireChange> Changes {get;set;}=[];
    public bool Committed {get;set;}
}
public sealed record QuestionnaireChange(string QuestionId,Dictionary<string,string> Baseline,Dictionary<string,string> Current,Dictionary<string,string> Returned,string State);

public sealed partial class EnterpriseStore
{
    private static QuestionnaireWorkbookQuestion WorkbookQuestion(QuestionnaireQuestion q)=>new(q.Id,q.Prompt,q.Section,q.ResponseType,q.Required,q.EvidenceExpectation,q.CompletionCriteria,q.WhyItMatters,q.AllowedValues.ToArray());
    private static Dictionary<string,string> WorkbookFields(QuestionnaireAnswer answer)=>new(StringComparer.Ordinal)
    {
        ["status"]=answer.Status,["text"]=answer.Text,["evidenceRefs"]=string.Join('\n',answer.EvidenceRefs),["rationale"]=answer.Rationale,
        ["nextOwner"]=answer.NextOwner,["nextDate"]=answer.NextDate,["blocker"]=answer.Blocker,["scheduleEffect"]=answer.ScheduleEffect,
        ["assertedBy"]=answer.AssertedBy,["attestationOwner"]=answer.AttestationOwner,["attestationDate"]=answer.AttestationDate,["attestationQualification"]=answer.AttestationQualification
    };
    private static Dictionary<string,Dictionary<string,string>> WorkbookBaseline(QuestionnaireAssignment a)=>a.Template.Questions.ToDictionary(q=>q.Id,q=>WorkbookFields(a.Answers.GetValueOrDefault(q.Id)??new()),StringComparer.Ordinal);
    private static bool SameQuestion(Dictionary<string,string> left,Dictionary<string,string> right)=>QuestionnaireWorkbook.Fields.All(f=>left.GetValueOrDefault(f,"")==right.GetValueOrDefault(f,""));
    private static string WorkbookFingerprint(QuestionnaireAssignment a)=>AssessmentWorkflow.Hash(new{a.Id,a.AssignedTo,a.TemplateSha256,a.Status,a.Answers});
    private static JsonObject ImportFields(Dictionary<string,string> fields)
    {
        var result=new JsonObject();
        foreach(var field in QuestionnaireWorkbook.Fields)
            if(field!="assertedBy")result[field]=field=="evidenceRefs"?new JsonArray(QuestionnaireWorkbook.SplitLines(fields.GetValueOrDefault(field,"")).Select(s=>(JsonNode?)JsonValue.Create(s)).ToArray()):JsonValue.Create(fields.GetValueOrDefault(field,""));
        return result;
    }
    public JsonObject ExportQuestionnaire(string id,string assignmentId,int revision,string key,string principal)
    {
        lock(gate)
        {
            var state=QuestionnaireCommit(id,new("questionnaire_export",assignmentId,new(),revision,key),principal,s=>
            {
                var a=QuestionnaireWorkflow.Assignment(s,assignmentId,principal,true);QuestionnaireWorkflow.EnsureEditable(a);
                if(s.Questionnaires.Exchange.Exports.Count>=108||s.Questionnaires.Exchange.Exports.Count(e=>e.AssignmentId==a.Id)>=4)throw new DemoConflictException("questionnaire_export_limit");
                var exportId="qexport-"+Guid.NewGuid().ToString("N");var baseline=WorkbookBaseline(a);
                var bytes=QuestionnaireWorkbook.Write(exportId,id,a.Id,a.TemplateId,a.TemplateVersion,a.TemplateSha256,a.Deployment.Label,a.Template.Questions.Select(WorkbookQuestion).ToArray(),baseline,a.ScheduleEffects);
                s.Questionnaires.Exchange.Exports.Add(new(){Id=exportId,AssignmentId=a.Id,AssignedTo=a.AssignedTo,TemplateSha256=a.TemplateSha256,Baseline=baseline,BytesBase64=Convert.ToBase64String(bytes),Sha256=Convert.ToHexStringLower(SHA256.HashData(bytes))});
                a.Receipt="Full 27-question workbook exported. This creates an offline copy, not delivery, a response, or an approval.";
            });
            var export=state.Questionnaires.Exchange.Exports.Last(e=>e.AssignmentId==assignmentId);
            return new JsonObject{["exportId"]=export.Id,["downloadUrl"]=$"/api/assessments/{id}/questionnaires/exports/{export.Id}/download",["revision"]=state.Revision};
        }
    }
    public byte[] DownloadQuestionnaire(string id,string exportId,string principal)
    {
        lock(gate)
        {
            EnsureOpen();var state=ReadAssessment(id,principal);var export=state.Questionnaires.Exchange.Exports.SingleOrDefault(e=>e.Id==exportId)??throw new DemoValidationException("questionnaire_export_not_found");
            var a=QuestionnaireWorkflow.Assignment(state,export.AssignmentId,principal);
            if(a.AssignedTo!=export.AssignedTo||a.TemplateSha256!=export.TemplateSha256)throw new DemoConflictException("questionnaire_export_stale");
            var bytes=Convert.FromBase64String(export.BytesBase64);if(Convert.ToHexStringLower(SHA256.HashData(bytes))!=export.Sha256)throw new DemoStoreException("questionnaire_export_integrity_failed");return bytes;
        }
    }
    public JsonObject PreviewQuestionnaire(string id,string assignmentId,int revision,string key,string principal,IntakeWorkbookReturn returned,byte[] original)
    {
        if(original.Length>IntakeWorkbook.MaxInputBytes)throw new DemoValidationException("intake_upload_limit");
        lock(gate)
        {
            var hash=Convert.ToHexStringLower(SHA256.HashData(original));
            var state=QuestionnaireCommit(id,new("questionnaire_preview",assignmentId,new(){["sourceSha256"]=hash},revision,key),principal,s=>
            {
                var a=QuestionnaireWorkflow.Assignment(s,assignmentId,principal,true);QuestionnaireWorkflow.EnsureEditable(a);
                var export=s.Questionnaires.Exchange.Exports.SingleOrDefault(e=>e.Id==returned.ExportId&&e.AssignmentId==assignmentId)??throw new DemoValidationException("questionnaire_export_not_found");
                if(export.AssignedTo!=a.AssignedTo||export.TemplateSha256!=a.TemplateSha256)throw new DemoConflictException("questionnaire_export_stale");
                if(s.Questionnaires.Exchange.Imports.Count>=108||s.Questionnaires.Exchange.Imports.Count(i=>i.AssignmentId==a.Id)>=4)throw new DemoConflictException("questionnaire_import_limit");
                if(returned.Answers.Count!=27||!returned.Answers.Keys.ToHashSet(StringComparer.Ordinal).SetEquals(export.Baseline.Keys))throw new DemoValidationException("questionnaire_workbook_question_set");
                var current=WorkbookBaseline(a);var changes=new List<QuestionnaireChange>();
                foreach(var q in a.Template.Questions)
                {
                    QuestionnaireWorkbookAnswer decoded;
                    try{decoded=JsonSerializer.Deserialize<QuestionnaireWorkbookAnswer>(returned.Answers[q.Id],AssessmentJson.Options)??throw new JsonException();}
                    catch(JsonException){throw new DemoValidationException("questionnaire_workbook_invalid");}
                    if(decoded.AssessmentId!=s.Id||decoded.AssignmentId!=a.Id||decoded.TemplateId!=a.TemplateId||decoded.TemplateVersion!=a.TemplateVersion||decoded.TemplateSha256!=a.TemplateSha256||
                        decoded.DefinitionSha256!=QuestionnaireWorkbook.DefinitionHash(WorkbookQuestion(q))||decoded.Fields.Count!=QuestionnaireWorkbook.Fields.Length||decoded.Fields.Keys.Any(f=>!QuestionnaireWorkbook.Fields.Contains(f,StringComparer.Ordinal)))throw new DemoValidationException("questionnaire_workbook_definition_changed");
                    // Blank means unchanged from the EXPORT, not permission to
                    // combine a stale status with concurrently edited content.
                    var proposed=export.Baseline[q.Id].ToDictionary(p=>p.Key,p=>string.IsNullOrEmpty(decoded.Fields[p.Key])?p.Value:decoded.Fields[p.Key],StringComparer.Ordinal);
                    _=QuestionnaireWorkflow.MergeAnswer(a,q.Id,ImportFields(proposed),principal,QuestionnaireWorkflow.Coordinator(s,principal));
                    if(ImportedAttribution(proposed["assertedBy"]).Length>4096)throw new DemoValidationException("questionnaire_answer_invalid");
                    var kind=SameQuestion(proposed,export.Baseline[q.Id])||SameQuestion(proposed,current[q.Id])?"unchanged":SameQuestion(current[q.Id],export.Baseline[q.Id])?"change":"conflict";
                    changes.Add(new(q.Id,export.Baseline[q.Id],current[q.Id],proposed,kind));
                }
                s.Questionnaires.Exchange.Imports.Add(new(){Id="qimport-"+Guid.NewGuid().ToString("N"),AssignmentId=a.Id,ExportId=export.Id,PrincipalId=principal,SourceSha256=hash,OriginalBase64=Convert.ToBase64String(original),PreviewFingerprint=WorkbookFingerprint(a),Changes=changes});
                a.Receipt="Workbook staged for review; no response has changed. Resolve whole-question conflicts, then apply. Submission remains separate.";
            });
            var preview=state.Questionnaires.Exchange.Imports.Last(i=>i.AssignmentId==assignmentId&&i.SourceSha256==hash&&i.PrincipalId==principal);
            return new JsonObject{["revision"]=state.Revision,["import"]=JsonSerializer.SerializeToNode(preview,AssessmentJson.Options) is JsonObject obj?SafePreview(obj):null};
        }
    }
    private static JsonObject SafePreview(JsonObject result){result.Remove("originalBase64");result.Remove("previewFingerprint");return result;}
    public JsonObject CommitQuestionnaireImport(string id,string importId,int revision,string key,string principal,JsonObject choices)
    {
        lock(gate)
        {
            EnsureOpen();var prior=ReadAssessment(id,principal);var initial=prior.Questionnaires.Exchange.Imports.SingleOrDefault(i=>i.Id==importId)??throw new DemoValidationException("questionnaire_import_not_found");
            _=QuestionnaireWorkflow.Assignment(prior,initial.AssignmentId,principal,true);
            if(initial.PrincipalId!=principal)throw new DemoValidationException("assessment_forbidden");
            var state=QuestionnaireCommit(id,new("questionnaire_import_commit",initial.AssignmentId,new(){["importId"]=importId,["choices"]=choices.DeepClone()},revision,key),principal,s=>
            {
                var a=QuestionnaireWorkflow.Assignment(s,initial.AssignmentId,principal,true);QuestionnaireWorkflow.EnsureEditable(a);
                var import=s.Questionnaires.Exchange.Imports.Single(i=>i.Id==importId);
                if(import.Committed)throw new DemoConflictException("questionnaire_import_already_committed");
                if(import.PreviewFingerprint!=WorkbookFingerprint(a))throw new DemoConflictException("questionnaire_preview_stale");
                if(choices.Any(c=>!import.Changes.Any(change=>change.QuestionId==c.Key)||c.Value is not JsonValue value||!value.TryGetValue<string>(out var choice)||choice is not("current" or "returned")))throw new DemoValidationException("questionnaire_import_choice_invalid");
                foreach(var change in import.Changes)
                {
                    var choice=choices[change.QuestionId]?.GetValue<string>();
                    if(change.State=="conflict"&&choice is null)throw new DemoValidationException("questionnaire_import_conflict_unresolved");
                    if(change.State=="unchanged"||choice=="current")continue;
                    var answer=QuestionnaireWorkflow.MergeAnswer(a,change.QuestionId,ImportFields(change.Returned),principal,QuestionnaireWorkflow.Coordinator(s,principal));
                    answer.AssertedBy=ImportedAttribution(change.Returned["assertedBy"]);
                    answer.RecordedBy=principal;a.Answers[change.QuestionId]=answer;
                }
                import.Committed=true;a.Receipt="Workbook changes applied as a draft response. The authenticated importer is recorded separately from unverified workbook attribution. Validate and submit separately.";
            });
            return QuestionnaireWorkflow.Detail(state,initial.AssignmentId,principal);
        }
    }
    private static string ImportedAttribution(string author)
    {
        const string prefix="Unverified workbook attribution: ";
        return string.IsNullOrWhiteSpace(author)||author=="Unverified workbook author"?"Unverified workbook author":author.StartsWith(prefix,StringComparison.Ordinal)?author:prefix+author;
    }
}
