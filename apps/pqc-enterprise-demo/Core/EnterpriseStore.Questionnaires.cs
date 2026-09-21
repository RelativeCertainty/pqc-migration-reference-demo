using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

public sealed partial class EnterpriseStore : IQuestionnaireStore
{
    public JsonObject Questionnaires(string id,string principal)
    {lock(gate){EnsureOpen();return QuestionnaireList(ReadAssessment(id,principal),principal);}}
    private JsonObject QuestionnaireList(AssessmentState state,string principal)
    {
        var coordinator=QuestionnaireWorkflow.Coordinator(state,principal);
        var visible=state.Questionnaires.Assignments.Where(a=>!IntakeWorkflow.Contributor(principal) || a.AssignedTo==principal).ToArray();
        if(IntakeWorkflow.Contributor(principal) && visible.Length==0)throw new DemoValidationException("assessment_forbidden");
        var catalog=coordinator?QuestionnaireCatalogLoader.Current:null;
        return AssessmentJson.Object(new{assessmentId=state.Id,assessmentName=state.Name,revision=state.Revision,canCoordinate=coordinator,
            assignments=visible.Select(a=>new{a.Id,a.Title,a.TemplateId,a.TemplateVersion,a.Deployment,a.AssignedTo,a.Status,questionCount=a.Template.Questions.Count,answeredCount=a.Answers.Count(v=>v.Value.Status=="answered")}),
            catalog=new{available=catalog is not null,catalogId=catalog?.CatalogId,catalogVersion=catalog?.CatalogVersion,templates=catalog?.Templates??[],scheduleEffects=catalog?.ScheduleEffects??[]},boundary=QuestionnaireWorkflow.Boundary});
    }
    public JsonObject Questionnaire(string id,string assignmentId,string principal)
    {lock(gate){EnsureOpen();return QuestionnaireWorkflow.Detail(ReadAssessment(id,principal),assignmentId,principal);}}
    public JsonObject QuestionnaireCommand(string id,AssessmentCommand command,string principal)
    {
        lock(gate)
        {
            var state=QuestionnaireCommit(id,command,principal,s=>QuestionnaireWorkflow.Apply(s,command,principal));
            return command.Operation=="questionnaire_create"?QuestionnaireList(state,principal):QuestionnaireWorkflow.Detail(state,command.TargetId!,principal);
        }
    }
    // Reuses the existing controller-owned append-only assessment journal and
    // simulated manifest-bound Worker result; this is not production dispatch.
    private AssessmentState QuestionnaireCommit(string id,AssessmentCommand command,string principal,Action<AssessmentState> evaluate)
    {
        EnsureOpen();ValidateAssessmentKey(command.IdempotencyKey);
        var current=ReadAssessment(id,principal);
        if(current.BaselineId!=baselineId)throw new DemoConflictException("assessment_baseline_unavailable");
        if(command.TargetId is null)
        {if(command.Operation!="questionnaire_create" || !QuestionnaireWorkflow.Coordinator(current,principal))throw new DemoValidationException("assessment_forbidden");}
        else
        {
            _=QuestionnaireWorkflow.Assignment(current,command.TargetId,principal,true);
            if(command.Operation is "questionnaire_reopen" or "questionnaire_reassign" && !QuestionnaireWorkflow.Coordinator(current,principal))throw new DemoValidationException("assessment_forbidden");
        }
        var hash=AssessmentWorkflow.Hash(new{command.Operation,command.TargetId,command.Fields,command.ExpectedRevision,principal});
        using(var query=Command("SELECT request_sha256,revision FROM assessment_commands WHERE assessment_id=$id AND idempotency_key=$key",null,("$id",id),("$key",command.IdempotencyKey)))
        using(var reader=query.ExecuteReader())
            if(reader.Read())
            {
                if(reader.GetString(0)!=hash)throw new DemoConflictException("idempotency_request_changed");
                var revision=reader.GetInt32(1);reader.Close();
                return ReadAssessment(id,principal,revision);
            }
        if(current.Revision!=command.ExpectedRevision)throw new DemoConflictException("assessment_revision_changed");
        if(current.Events.Count>=2000)throw new DemoConflictException("assessment_event_limit");
        evaluate(current);current.Revision++;current.UpdatedAt=DateTimeOffset.UtcNow.ToString("O");
        current.Events.Add(new(current.Revision,command.Operation,command.TargetId,principal,current.UpdatedAt,"user_entered_synthetic"));
        if(Encoding.UTF8.GetByteCount(JsonSerializer.Serialize(current,AssessmentJson.Options))>AssessmentJson.MaxSnapshotBytes)throw new DemoConflictException("questionnaire_snapshot_capacity_limit");
        using var transaction=connection.BeginTransaction();
        using(var check=Command("SELECT max(revision) FROM assessment_versions WHERE assessment_id=$id",transaction,("$id",id)))
            if(Convert.ToInt32(check.ExecuteScalar(),CultureInfo.InvariantCulture)!=command.ExpectedRevision)throw new DemoConflictException("assessment_revision_changed");
        PersistAssessment(current,command,principal,hash,transaction);transaction.Commit();return current;
    }
}
