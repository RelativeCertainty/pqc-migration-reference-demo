using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

public sealed class DiscoveryExchangeState
{
    public List<DiscoveryExport> Exports {get;set;}=[];
    public List<DiscoveryImport> Imports {get;set;}=[];
}
public sealed class DiscoveryExport
{
    public string Id {get;set;}="";
    public string RequestId {get;set;}="";
    public string AssignedTo {get;set;}="";
    public string TemplateSha256 {get;set;}="";
    public Dictionary<string,Dictionary<string,string>> Baseline {get;set;}=new(StringComparer.Ordinal);
    public string BytesBase64 {get;set;}="";
    public string Sha256 {get;set;}="";
}
public sealed class DiscoveryImport
{
    public string Id {get;set;}="";
    public string RequestId {get;set;}="";
    public string ExportId {get;set;}="";
    public string PrincipalId {get;set;}="";
    public string SourceSha256 {get;set;}="";
    public string OriginalBase64 {get;set;}="";
    public string PreviewFingerprint {get;set;}="";
    public List<DiscoveryChange> Changes {get;set;}=[];
    public bool Committed {get;set;}
}
public sealed record DiscoveryChange(string QuestionId,Dictionary<string,string> Baseline,Dictionary<string,string> Current,Dictionary<string,string> Returned,string State);

public sealed partial class EnterpriseStore
{
    private static Dictionary<string,string> DiscoveryFields(DiscoveryAnswer answer)=>new(StringComparer.Ordinal)
    { ["status"]=answer.Status,["text"]=answer.Text,["reference"]=answer.Reference,["assertedBy"]=answer.AssertedBy };
    private static Dictionary<string,Dictionary<string,string>> DiscoveryBaseline(DiscoveryRequest request)=>request.Questions.ToDictionary(q=>q.Id,q=>DiscoveryFields(request.Answers.GetValueOrDefault(q.Id)??new()),StringComparer.Ordinal);
    private static bool SameDiscoveryQuestion(Dictionary<string,string> left,Dictionary<string,string> right)=>DiscoveryWorkbook.Fields.All(f=>left.GetValueOrDefault(f,"")==right.GetValueOrDefault(f,""));
    private static string DiscoveryFingerprint(DiscoveryRequest request)=>AssessmentWorkflow.Hash(new{request.Id,request.FamilyId,request.AssignedTo,request.TemplateVersion,request.TemplateSha256,request.Status,request.Answers,request.ProductRefs});
    private static JsonObject DiscoveryImportFields(Dictionary<string,string> fields)=>new(){["status"]=fields["status"],["text"]=fields["text"],["reference"]=fields["reference"]};
    public JsonObject ExportDiscovery(string id,string requestId,int revision,string key,string principal)
    {
        lock(gate)
        {
            var state=DiscoveryCommit(id,new("discovery_export",requestId,new(),revision,key),principal,s=>
            {
                var request=DiscoveryWorkflow.Request(s,requestId,principal,true);DiscoveryWorkflow.EnsureEditable(request);
                if(s.Discovery.Exchange.Exports.Count>=108||s.Discovery.Exchange.Exports.Count(e=>e.RequestId==requestId)>=4)throw new DemoConflictException("discovery_export_limit");
                var exportId="dexport-"+Guid.NewGuid().ToString("N");var baseline=DiscoveryBaseline(request);
                var bytes=DiscoveryWorkbook.Write(exportId,id,request.Id,request.FamilyId,request.FamilyName,request.TemplateVersion,request.TemplateSha256,request.Questions,baseline);
                s.Discovery.Exchange.Exports.Add(new(){Id=exportId,RequestId=requestId,AssignedTo=request.AssignedTo,TemplateSha256=request.TemplateSha256,Baseline=baseline,BytesBase64=Convert.ToBase64String(bytes),Sha256=Convert.ToHexStringLower(SHA256.HashData(bytes))});
                request.Receipt="Your five-question offline copy is ready. It has not been sent. Return it in the app when you have something useful to share; a partial response is welcome.";
            });
            var export=state.Discovery.Exchange.Exports.Last(e=>e.RequestId==requestId);
            return new JsonObject{["exportId"]=export.Id,["downloadUrl"]=$"/api/assessments/{id}/discovery/exports/{export.Id}/download",["revision"]=state.Revision};
        }
    }
    public byte[] DownloadDiscovery(string id,string exportId,string principal)
    {
        lock(gate)
        {
            EnsureOpen();return DiscoveryExportBytes(ReadAssessment(id,principal),exportId,principal);
        }
    }
    private static byte[] DiscoveryExportBytes(AssessmentState state,string exportId,string principal)
    {
        var export=state.Discovery.Exchange.Exports.SingleOrDefault(e=>e.Id==exportId)??throw new DemoValidationException("discovery_export_not_found");
        if(state.Discovery.Collections.Any(c=>c.Packages.Any(package=>package.Entries.Any(e=>e.ExportId==exportId))&&!CollectionVisible(state,c,principal)))throw new DemoValidationException("assessment_forbidden");
        var request=DiscoveryWorkflow.Request(state,export.RequestId,principal);
        if(request.AssignedTo!=export.AssignedTo||request.TemplateSha256!=export.TemplateSha256)throw new DemoConflictException("discovery_export_stale");
        var bytes=Convert.FromBase64String(export.BytesBase64);if(Convert.ToHexStringLower(SHA256.HashData(bytes))!=export.Sha256)throw new DemoStoreException("discovery_export_integrity_failed");return bytes;
    }
    public JsonObject PreviewDiscovery(string id,string requestId,int revision,string key,string principal,IntakeWorkbookReturn returned,byte[] original)
    {
        if(original.Length>IntakeWorkbook.MaxInputBytes)throw new DemoValidationException("intake_upload_limit");
        lock(gate)
        {
            var hash=Convert.ToHexStringLower(SHA256.HashData(original));
            var state=DiscoveryCommit(id,new("discovery_preview",requestId,new(){["sourceSha256"]=hash},revision,key),principal,s=>
            {
                var request=DiscoveryWorkflow.Request(s,requestId,principal,true);DiscoveryWorkflow.EnsureEditable(request);
                var export=s.Discovery.Exchange.Exports.SingleOrDefault(e=>e.Id==returned.ExportId&&e.RequestId==requestId)??throw new DemoValidationException("discovery_export_not_found");
                if(export.AssignedTo!=request.AssignedTo||export.TemplateSha256!=request.TemplateSha256)throw new DemoConflictException("discovery_export_stale");
                if(s.Discovery.Exchange.Imports.Count>=108||s.Discovery.Exchange.Imports.Count(i=>i.RequestId==requestId)>=4)throw new DemoConflictException("discovery_import_limit");
                if(returned.Answers.Count!=5||!returned.Answers.Keys.ToHashSet(StringComparer.Ordinal).SetEquals(export.Baseline.Keys))throw new DemoValidationException("discovery_workbook_question_set");
                var current=DiscoveryBaseline(request);var changes=new List<DiscoveryChange>();
                foreach(var question in request.Questions)
                {
                    DiscoveryWorkbookAnswer decoded;
                    try{decoded=JsonSerializer.Deserialize<DiscoveryWorkbookAnswer>(returned.Answers[question.Id],AssessmentJson.Options)??throw new JsonException();}
                    catch(JsonException){throw new DemoValidationException("discovery_workbook_invalid");}
                    if(decoded.AssessmentId!=s.Id||decoded.RequestId!=request.Id||decoded.TemplateVersion!=request.TemplateVersion||decoded.TemplateSha256!=request.TemplateSha256||decoded.FamilyId!=request.FamilyId||
                        decoded.DefinitionSha256!=DiscoveryWorkbook.DefinitionHash(question)||decoded.Fields.Count!=DiscoveryWorkbook.Fields.Length||decoded.Fields.Keys.Any(f=>!DiscoveryWorkbook.Fields.Contains(f,StringComparer.Ordinal)))throw new DemoValidationException("discovery_workbook_definition_changed");
                    var proposed=export.Baseline[question.Id].ToDictionary(p=>p.Key,p=>string.IsNullOrEmpty(decoded.Fields[p.Key])?p.Value:decoded.Fields[p.Key],StringComparer.Ordinal);
                    _=DiscoveryWorkflow.MergeAnswer(request,question.Id,DiscoveryImportFields(proposed),principal,DiscoveryWorkflow.Coordinate(s,principal));
                    if(ImportedAttribution(proposed["assertedBy"]).Length>4096)throw new DemoValidationException("discovery_answer_invalid");
                    var kind=SameDiscoveryQuestion(proposed,export.Baseline[question.Id])||SameDiscoveryQuestion(proposed,current[question.Id])?"unchanged":SameDiscoveryQuestion(current[question.Id],export.Baseline[question.Id])?"change":"conflict";
                    changes.Add(new(question.Id,export.Baseline[question.Id],current[question.Id],proposed,kind));
                }
                s.Discovery.Exchange.Imports.Add(new(){Id="dimport-"+Guid.NewGuid().ToString("N"),RequestId=requestId,ExportId=export.Id,PrincipalId=principal,SourceSha256=hash,OriginalBase64=Convert.ToBase64String(original),PreviewFingerprint=DiscoveryFingerprint(request),Changes=changes});
                request.Receipt="Offline response staged for review. Nothing has changed yet. Choose between competing whole-question responses, then apply as draft.";
            });
            var preview=state.Discovery.Exchange.Imports.Last(i=>i.RequestId==requestId&&i.SourceSha256==hash&&i.PrincipalId==principal);
            return new JsonObject{["revision"]=state.Revision,["import"]=AssessmentJson.Object(new{preview.Id,preview.RequestId,preview.ExportId,preview.PrincipalId,preview.SourceSha256,preview.Changes,preview.Committed})};
        }
    }
    public JsonObject CommitDiscoveryImport(string id,string importId,int revision,string key,string principal,JsonObject choices)
    {
        lock(gate)
        {
            EnsureOpen();var prior=ReadAssessment(id,principal);var initial=prior.Discovery.Exchange.Imports.SingleOrDefault(i=>i.Id==importId)??throw new DemoValidationException("discovery_import_not_found");
            _=DiscoveryWorkflow.Request(prior,initial.RequestId,principal,true);if(initial.PrincipalId!=principal)throw new DemoValidationException("assessment_forbidden");
            var state=DiscoveryCommit(id,new("discovery_import_commit",initial.RequestId,new(){["importId"]=importId,["choices"]=choices.DeepClone()},revision,key),principal,s=>
            {
                var request=DiscoveryWorkflow.Request(s,initial.RequestId,principal,true);DiscoveryWorkflow.EnsureEditable(request);var import=s.Discovery.Exchange.Imports.Single(i=>i.Id==importId);
                if(import.Committed)throw new DemoConflictException("discovery_import_already_committed");
                if(import.PreviewFingerprint!=DiscoveryFingerprint(request))throw new DemoConflictException("discovery_preview_stale");
                if(choices.Any(c=>!import.Changes.Any(change=>change.QuestionId==c.Key)||c.Value is not JsonValue value||!value.TryGetValue<string>(out var choice)||choice is not("current" or "returned")))throw new DemoValidationException("discovery_import_choice_invalid");
                foreach(var change in import.Changes)
                {
                    var choice=choices[change.QuestionId]?.GetValue<string>();if(change.State=="conflict"&&choice is null)throw new DemoValidationException("discovery_import_conflict_unresolved");
                    if(change.State=="unchanged"||choice=="current")continue;
                    var answer=DiscoveryWorkflow.MergeAnswer(request,change.QuestionId,DiscoveryImportFields(change.Returned),principal,DiscoveryWorkflow.Coordinate(s,principal));
                    answer.AssertedBy=ImportedAttribution(change.Returned["assertedBy"]);answer.RecordedBy=principal;request.Answers[change.QuestionId]=answer;
                }
                import.Committed=true;request.Receipt="Offline answers saved as a draft. Please review and submit when ready. Names supplied in the workbook have not been independently confirmed; your signed-in account is recorded as the importer. No access is authorized by this action.";
            });
            return DiscoveryWorkflow.Detail(state,initial.RequestId,principal);
        }
    }
}
