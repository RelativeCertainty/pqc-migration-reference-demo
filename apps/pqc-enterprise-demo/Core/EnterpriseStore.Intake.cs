using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

public sealed partial class EnterpriseStore : IIntakeStore
{
    public JsonObject IntakeView(string id,string principal)
    {
        lock(gate)
        {
            EnsureOpen();var state=ReadAssessment(id,principal);
            if(IntakeWorkflow.Contributor(principal) && !state.Intake.Requests.Any(r=>r.AssignedTo==principal))throw new DemoValidationException("assessment_forbidden");
            return IntakeWorkflow.Projection(state,principal);
        }
    }
    public JsonObject IntakeCommand(string id,AssessmentCommand command,string principal)
    {
        lock(gate)
        {
            var state=IntakeCommit(id,command,principal,s=>IntakeWorkflow.Apply(s,command,principal,DateTimeOffset.UtcNow.ToString("O")),false);
            return IntakeWorkflow.Projection(state,principal);
        }
    }
    // Called only while holding the store gate. Reuses the checksummed append-only
    // assessment journal and simulated manifest-bound result commit, not a parallel ledger.
    private AssessmentState IntakeCommit(string id,AssessmentCommand command,string principal,Action<AssessmentState> evaluate,bool append=true)
    {
        EnsureOpen();ValidateAssessmentKey(command.IdempotencyKey);
        var current=ReadAssessment(id,principal);
        if(current.BaselineId!=baselineId)throw new DemoConflictException("assessment_baseline_unavailable");
        if(command.TargetId is not null)
        {
            var target=IntakeWorkflow.Request(current,command.TargetId,principal);
            if(!current.Scope.IncludedFamilyIds.Contains(target.FamilyId))throw new DemoConflictException("intake_request_out_of_scope");
        }
        else if(!IntakeWorkflow.Coordinate(current,principal))throw new DemoValidationException("assessment_forbidden");
        var role=AssessmentWorkflow.Role(current,principal);
        if(command.Operation=="intake_review_response")
        {if(role!="technical-reviewer")throw new DemoValidationException("assessment_forbidden");}
        else if(command.Operation is "intake_admit_evidence" or "intake_create_request")
        {if(role!="assessment-lead")throw new DemoValidationException("assessment_forbidden");}
        else if(command.TargetId is not null)_=IntakeWorkflow.Request(current,command.TargetId,principal,true);
        var requestHash=AssessmentWorkflow.Hash(new{command.Operation,command.TargetId,command.Fields,command.ExpectedRevision,principal});
        using(var lookup=Command("SELECT request_sha256,revision FROM assessment_commands WHERE assessment_id=$id AND idempotency_key=$key",null,("$id",id),("$key",command.IdempotencyKey)))
        using(var reader=lookup.ExecuteReader())
            if(reader.Read())
            {
                if(reader.GetString(0)!=requestHash)throw new DemoConflictException("idempotency_request_changed");
                var revision=reader.GetInt32(1);reader.Close();
                return ReadAssessment(id,principal,revision);
            }
        if(current.Revision!=command.ExpectedRevision)throw new DemoConflictException("assessment_revision_changed");
        if(current.Events.Count>=2000)throw new DemoConflictException("assessment_event_limit");
        evaluate(current);
        if(append)
        {
            current.Revision++;current.UpdatedAt=DateTimeOffset.UtcNow.ToString("O");
            current.Events.Add(new(current.Revision,command.Operation,command.TargetId,principal,current.UpdatedAt,"user_entered_synthetic"));
            AssessmentWorkflow.Refresh(current,principal);
        }
        if(Encoding.UTF8.GetByteCount(JsonSerializer.Serialize(current,AssessmentJson.Options))>AssessmentJson.MaxSnapshotBytes)throw new DemoConflictException("intake_snapshot_capacity_limit");
        using var transaction=connection.BeginTransaction();
        using(var check=Command("SELECT max(revision) FROM assessment_versions WHERE assessment_id=$id",transaction,("$id",id)))
            if(Convert.ToInt32(check.ExecuteScalar(),CultureInfo.InvariantCulture)!=command.ExpectedRevision)throw new DemoConflictException("assessment_revision_changed");
        PersistAssessment(current,command,principal,requestHash,transaction);
        transaction.Commit();return current;
    }
    public JsonObject ExportIntake(string id,string requestId,int revision,string key,string principal)
    {
        lock(gate)
        {
            var command=new AssessmentCommand("intake_export",requestId,new(),revision,key);
            var state=IntakeCommit(id,command,principal,s=>
            {
                var request=IntakeWorkflow.Request(s,requestId,principal,true);
                if(s.Intake.Exports.Count>=25)throw new DemoConflictException("intake_export_limit");
                var rows=IntakeWorkflow.AnswerRows(s,request);
                var labels=rows.Keys.ToDictionary(k=>k,k=>
                {
                    var pair=k.Split('/');var label=pair[0]==request.Id?"Whole request":s.Intake.Systems.Single(i=>i.Id==pair[0]).Label;
                    return label+" — "+IntakeWorkflow.Questions.Single(q=>q.Id==pair[1]).Label;
                },StringComparer.Ordinal);
                var exportId=IntakeWorkflow.NewId("export",s,requestId);
                var bytes=IntakeWorkbook.Write(exportId,id,requestId,rows,labels);
                s.Intake.Exports.Add(new IntakeExport{Id=exportId,RequestId=requestId,TemplateVersion=request.TemplateVersion,AssignedTo=request.AssignedTo,Baseline=rows,RowLabels=labels,BytesBase64=Convert.ToBase64String(bytes),Sha256=Convert.ToHexStringLower(SHA256.HashData(bytes))});
                s.Intake.Receipt=new("Workbook created from the server-held response snapshot. Export does not mean delivered or answered.",request.AssignedTo,requestId);
            });
            var export=state.Intake.Exports.Last(e=>e.RequestId==requestId);
            return new JsonObject{["exportId"]=export.Id,["downloadUrl"]=$"/api/assessments/{id}/intake/exports/{export.Id}/download",["revision"]=state.Revision};
        }
    }
    public byte[] DownloadIntake(string id,string exportId,string principal)
    {
        lock(gate)
        {
            EnsureOpen();var state=ReadAssessment(id,principal);
            var export=state.Intake.Exports.SingleOrDefault(e=>e.Id==exportId) ?? throw new DemoValidationException("intake_export_not_found");
            var request=IntakeWorkflow.Request(state,export.RequestId,principal);
            if(export.AssignedTo!=request.AssignedTo)throw new DemoConflictException("intake_export_stale");
            var bytes=Convert.FromBase64String(export.BytesBase64);
            if(Convert.ToHexStringLower(SHA256.HashData(bytes))!=export.Sha256)throw new DemoStoreException("intake_export_integrity_failed");
            return bytes;
        }
    }
    public JsonObject PreviewIntake(string id,string requestId,int revision,string key,string principal,IntakeWorkbookReturn workbook,byte[] original)
    {
        if(original.Length>1_048_576)throw new DemoValidationException("intake_upload_limit");
        lock(gate)
        {
            var hash=Convert.ToHexStringLower(SHA256.HashData(original));
            var command=new AssessmentCommand("intake_preview",requestId,new JsonObject{["sourceSha256"]=hash},revision,key);
            var state=IntakeCommit(id,command,principal,s=>
            {
                var request=IntakeWorkflow.Request(s,requestId,principal,true);
                if(s.Intake.Imports.Count>=25)throw new DemoConflictException("intake_import_limit");
                var export=s.Intake.Exports.SingleOrDefault(e=>e.Id==workbook.ExportId && e.RequestId==requestId) ?? throw new DemoValidationException("intake_export_binding_invalid");
                if(export.AssignedTo!=request.AssignedTo || export.TemplateVersion!=request.TemplateVersion)throw new DemoConflictException("intake_export_stale");
                var valid=IntakeWorkflow.AnswerRows(s,request);
                if(workbook.Answers.Any(a=>!export.Baseline.ContainsKey(a.Key) || !valid.ContainsKey(a.Key) || a.Value.Length>512))throw new DemoValidationException("intake_question_scope_invalid");
                var preview=new IntakeImport{Id=IntakeWorkflow.NewId("preview",s,requestId),RequestId=requestId,ExportId=export.Id,PrincipalId=principal,RequestFingerprint=IntakeWorkflow.RequestFingerprint(s,request),SourceSha256=hash,OriginalBase64=Convert.ToBase64String(original),Returned=workbook.Answers};
                foreach(var (answerKey,returned) in workbook.Answers)
                {
                    var baseline=export.Baseline[answerKey];var current=request.Answers.GetValueOrDefault(answerKey,"");
                    var change=string.IsNullOrWhiteSpace(returned) || returned==baseline || returned==current?"unchanged":current==baseline?"change":"conflict";
                    preview.Changes.Add(new(answerKey,baseline,current,returned,change));
                }
                s.Intake.Imports.Add(preview);
                s.Intake.Receipt=new("Workbook validated against its server-held export snapshot. No answers changed. Review proposed edits and resolve conflicts.",principal,requestId);
            });
            var result=state.Intake.Imports.Last(p=>p.RequestId==requestId && p.PrincipalId==principal);
            return AssessmentJson.Object(new{previewId=result.Id,revision=state.Revision,changes=result.Changes});
        }
    }
    public JsonObject StageIntakeEvidence(string id,string requestId,string systemId,string sourceSystemId,int revision,string key,string principal,byte[] original)
    {
        // Small closed reference format; parsing is bounded and rejects duplicate members.
        var records=IntakeTlsEvidence.Parse(original);
        var hash=Convert.ToHexStringLower(SHA256.HashData(original));
        lock(gate)
        {
            var command=new AssessmentCommand("intake_stage_evidence",requestId,new JsonObject{["sourceSha256"]=hash,["systemId"]=systemId,["sourceSystemId"]=sourceSystemId},revision,key);
            var state=IntakeCommit(id,command,principal,s=>
            {
                var request=IntakeWorkflow.Request(s,requestId,principal,true);
                if(request.FamilyId!="traffic-termination")throw new DemoValidationException("intake_format_not_qualified_for_family");
                if(s.Intake.Batches.Count>=20)throw new DemoConflictException("intake_batch_limit");
                var system=s.Intake.Systems.SingleOrDefault(x=>x.Id==systemId && x.RequestId==requestId && x.SystemRole is "subject" or "both") ?? throw new DemoValidationException("intake_subject_binding_invalid");
                var source=s.Intake.Systems.SingleOrDefault(x=>x.Id==sourceSystemId && x.RequestId==requestId && x.SystemRole is "source" or "both") ?? throw new DemoValidationException("intake_source_binding_invalid");
                if(source.AboutSystemId.Length>0 && source.AboutSystemId!=system.Id)throw new DemoValidationException("intake_subject_binding_invalid");
                if(s.Intake.Batches.Any(b=>b.RequestId==requestId && b.SystemId==systemId && b.SourceSystemId==sourceSystemId && b.ContentSha256==hash))throw new DemoConflictException("intake_duplicate_evidence");
                var batch=new IntakeBatch{Id=IntakeWorkflow.NewId("batch",s,requestId),RequestId=requestId,SystemId=system.Id,SourceSystemId=source.Id,ContentSha256=hash,OriginalBase64=Convert.ToBase64String(original),ReceivedAt=DateTimeOffset.UtcNow.ToString("O")};
                batch.Observations=records.Select(r=>new IntakeObservation("intake-observation-"+AssessmentWorkflow.Hash(new{assessment=s.Id,source=source.Id,subject=system.Id,native=r.Id,hash}),system.Id,source.Id,r.Id,r.Hostname,r.KeyExchange,r.Authentication,r.Basis,hash)).ToList();
                s.Intake.Batches.Add(batch);
                s.Intake.Receipt=new($"{records.Count} synthetic TLS records staged, not admitted. Source namespace is bound to the selected evidence-producing system; application/certificate relationships remain unresolved.","Assessment lead",requestId);
            });
            return IntakeWorkflow.Projection(state,principal);
        }
    }
}
