using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

public sealed partial class EnterpriseStore : IDiscoveryStore
{
    public JsonObject Discovery(string id,string principal)
    {lock(gate){EnsureOpen();return DiscoveryList(ReadAssessment(id,principal),principal);}}
    private JsonObject DiscoveryList(AssessmentState s,string principal)
    {
        var contributor=IntakeWorkflow.Contributor(principal);var role=AssessmentWorkflow.Role(s,principal);
        var visible=s.Discovery.Requests.Where(r=>!contributor||r.AssignedTo==principal).ToArray();
        if(contributor&&visible.Length==0)throw new DemoValidationException("assessment_forbidden");
        var lead=DiscoveryWorkflow.Coordinate(s,principal);
        var gates=AssessmentWorkflow.Passed(s,"PQC-G00")&&AssessmentWorkflow.Passed(s,"PQC-P1-G01");
        var investigations=contributor?[]:s.Discovery.Investigations.Select(i=>
        {
            var result=AssessmentJson.Object(i);var request=s.Discovery.Requests.Single(r=>r.Id==i.RequestId);
            var eligible=lead&&gates&&s.Scope.IncludedFamilyIds.Contains(i.FamilyId)&&request.Status=="submitted"&&i.FamilyId=="traffic-termination";
            result["canEditResearch"]=lead||role=="technical-reviewer"&&i.AssignedTo==principal;
            result["canStageEvidence"]=eligible;result["canAdmitEvidence"]=eligible&&i.EvidenceReviews.Any(b=>b.Status=="qualified");
            result["canReviewEvidence"]=role=="technical-reviewer"&&i.EvidenceReviews.Any(b=>b.Status=="staged"&&b.StagedBy!=principal);
            result["evidenceBlockingReason"]=!lead?"Evidence staging and admission are assessment-lead actions.":!gates?"Complete G00 and P1-G01 before controlled evidence admission.":!s.Scope.IncludedFamilyIds.Contains(i.FamilyId)?"This source family is outside the current assessment scope.":request.Status!="submitted"?"Receive a useful discovery response before staging evidence.":i.FamilyId!="traffic-termination"?"Only the bounded synthetic TLS evidence format is qualified in this increment.":"";
            return result;
        }).ToArray();
        return AssessmentJson.Object(new{assessmentId=s.Id,assessmentName=s.Name,revision=s.Revision,
            collectionAvailable=true,canCoordinate=lead,canResearch=DiscoveryWorkflow.Research(s,principal),canReviewEvidence=role=="technical-reviewer",canStageEvidence=lead&&gates,canAdmitEvidence=lead&&gates,
            evidenceBlockingReason=!lead?"Evidence staging and admission are assessment-lead actions.":!gates?"Complete G00 and P1-G01 before controlled evidence admission.":"",
            requests=visible,families=contributor?[]:s.Sources.Select(f=>new{id=f.FamilyId,name=f.Name,examples=f.Examples}).ToArray(),
            investigators=contributor?[]:s.Assignments.Where(a=>a.Role is "assessment-lead" or "technical-reviewer").Select(a=>new{id=a.PrincipalId,label=a.Role}).ToArray(),
            standards=contributor?[]:s.Discovery.Standards.ToArray(),investigations,boundary=DiscoveryWorkflow.Boundary});
    }
    public JsonObject DiscoveryRequest(string id,string requestId,string principal)
    {lock(gate){EnsureOpen();return DiscoveryWorkflow.Detail(ReadAssessment(id,principal),requestId,principal);}}
    public JsonObject DiscoveryCommand(string id,AssessmentCommand command,string principal)
    {
        lock(gate)
        {
            var state=DiscoveryCommit(id,command,principal,s=>DiscoveryWorkflow.Apply(s,command,principal));
            return command.Operation is "discovery_save" or "discovery_submit" or "discovery_reopen"?DiscoveryWorkflow.Detail(state,command.TargetId!,principal):DiscoveryList(state,principal);
        }
    }
    // Existing controller-owned transaction and immutable assessment journal;
    // no parallel workflow ledger, production dispatch or outbound authority.
    private AssessmentState DiscoveryCommit(string id,AssessmentCommand command,string principal,Action<AssessmentState> evaluate)
    {
        EnsureOpen();ValidateAssessmentKey(command.IdempotencyKey);
        var current=ReadAssessment(id,principal);
        if(current.BaselineId!=baselineId)throw new DemoConflictException("assessment_baseline_unavailable");
        AssessmentWorkflow.Refresh(current,principal);
        DiscoveryWorkflow.Authorize(current,command,principal);
        var hash=AssessmentWorkflow.Hash(new{command.Operation,command.TargetId,command.Fields,command.ExpectedRevision,principal});
        using(var query=Command("SELECT request_sha256,revision FROM assessment_commands WHERE assessment_id=$id AND idempotency_key=$key",null,("$id",id),("$key",command.IdempotencyKey)))
        using(var reader=query.ExecuteReader())
            if(reader.Read())
            {
                if(reader.GetString(0)!=hash)throw new DemoConflictException("idempotency_request_changed");
                var revision=reader.GetInt32(1);reader.Close();return ReadAssessment(id,principal,revision);
            }
        if(current.Revision!=command.ExpectedRevision)throw new DemoConflictException("assessment_revision_changed");
        if(current.Events.Count>=2000)throw new DemoConflictException("assessment_event_limit");
        evaluate(current);current.Revision++;current.UpdatedAt=DateTimeOffset.UtcNow.ToString("O");
        current.Events.Add(new(current.Revision,command.Operation,command.TargetId,principal,current.UpdatedAt,current.ScenarioVersion is not null?"scenario_generated":"user_entered_synthetic"));
        AssessmentWorkflow.Refresh(current,principal);
        if(Encoding.UTF8.GetByteCount(JsonSerializer.Serialize(current,AssessmentJson.Options))>AssessmentJson.MaxSnapshotBytes)throw new DemoConflictException("discovery_snapshot_capacity_limit");
        using var transaction=connection.BeginTransaction();
        using(var check=Command("SELECT max(revision) FROM assessment_versions WHERE assessment_id=$id",transaction,("$id",id)))
            if(Convert.ToInt32(check.ExecuteScalar(),CultureInfo.InvariantCulture)!=command.ExpectedRevision)throw new DemoConflictException("assessment_revision_changed");
        PersistAssessment(current,command,principal,hash,transaction);transaction.Commit();return current;
    }
}
