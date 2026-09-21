using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

public static class QuestionnaireWorkflow
{
    public const string Boundary="Synthetic questionnaire responses only. Submission records a response, not technical verification, enterprise acceptance, evidence admission or migration authorization.";
    public static bool Coordinator(AssessmentState state,string principal)=>AssessmentWorkflow.Role(state,principal)=="assessment-lead";
    public static QuestionnaireAssignment Assignment(AssessmentState state,string? id,string principal,bool write=false)
    {
        _=AssessmentWorkflow.Role(state,principal);
        var assignment=state.Questionnaires.Assignments.SingleOrDefault(a=>a.Id==id) ?? throw new DemoValidationException("questionnaire_assignment_not_found");
        if(IntakeWorkflow.Contributor(principal) && assignment.AssignedTo!=principal || write && !Coordinator(state,principal) && assignment.AssignedTo!=principal)
            throw new DemoValidationException("assessment_forbidden");
        if(AssessmentWorkflow.Hash(assignment.Template)!=assignment.TemplateSha256)throw new DemoStoreException("questionnaire_template_integrity_failed");
        return assignment;
    }
    public static void EnsureEditable(QuestionnaireAssignment assignment)
    {if(assignment.Status!="draft")throw new DemoConflictException("questionnaire_submitted_read_only");}
    public static string Text(JsonObject fields,string key,int max=4096)
    {
        if(fields[key] is null)return "";
        if(fields[key] is not JsonValue node || !node.TryGetValue<string>(out var value) || value.Length>max || value.Any(c=>char.IsControl(c) && c is not ('\n' or '\r' or '\t')))
            throw new DemoValidationException("questionnaire_answer_invalid");
        return value;
    }
    private static string Required(JsonObject fields,string key,int max=512)
    {var value=Text(fields,key,max);if(string.IsNullOrWhiteSpace(value))throw new DemoValidationException("questionnaire_field_required");return value;}
    private static bool Date(string value)=>DateOnly.TryParseExact(value,"yyyy-MM-dd",CultureInfo.InvariantCulture,DateTimeStyles.None,out _);
    public static QuestionnaireValidation Validate(QuestionnaireAssignment assignment)
    {
        var issues=new List<QuestionnaireIssue>();
        foreach(var question in assignment.Template.Questions)
        {
            var answer=assignment.Answers.GetValueOrDefault(question.Id) ?? new();
            void Need(bool condition,string field,string message){if(!condition)issues.Add(new(question.Id,field,message));}
            if(answer.Status=="unanswered")
            {if(question.Required)Need(false,"status","Choose an answer or explicitly record unknown, blocked, unavailable or not applicable.");continue;}
            if(answer.Status=="answered")
            {
                Need(!string.IsNullOrWhiteSpace(answer.Text),"text","Provide the response; an answered status alone is not an answer.");
                Need(answer.EvidenceRefs.Any(r=>!string.IsNullOrWhiteSpace(r)),"evidenceRefs","Provide the requested supporting reference; otherwise use an explicit unresolved status.");
                if(question.AllowedValues.Count>0)Need(question.AllowedValues.Contains(answer.Text,StringComparer.Ordinal),"text","Choose an exact allowed value from this question's source contract.");
                if(question.SourceId=="CQ-24")
                {
                    Need(!string.IsNullOrWhiteSpace(answer.AttestationOwner),"attestationOwner","Name the accountable owner whose attestation is being recorded.");
                    Need(Date(answer.AttestationDate),"attestationDate","Record the attestation date as YYYY-MM-DD.");
                    if(answer.Text=="yes_with_qualifications")Need(!string.IsNullOrWhiteSpace(answer.AttestationQualification),"attestationQualification","State the attestation qualifications.");
                }
            }
            if(answer.Status is "unknown" or "blocked" or "unavailable")
            {
                Need(!string.IsNullOrWhiteSpace(answer.Rationale),"rationale","Explain the unanswered question or constraint.");
                Need(!string.IsNullOrWhiteSpace(answer.NextOwner),"nextOwner","Identify the next responsible function; do not invent an owner.");
                Need(Date(answer.NextDate),"nextDate","Record the agreed next-action date as YYYY-MM-DD; do not invent a date.");
                Need(!string.IsNullOrWhiteSpace(answer.Blocker),"blocker","Describe what prevents a supported answer.");
                Need(assignment.ScheduleEffects.Contains(answer.ScheduleEffect,StringComparer.Ordinal),"scheduleEffect","Select the stated schedule effect.");
            }
            if(answer.Status=="not_applicable")Need(!string.IsNullOrWhiteSpace(answer.Rationale),"rationale","Explain why this question is not applicable to this deployment.");
        }
        return new(issues.Count==0,issues);
    }
    public static QuestionnaireAnswer MergeAnswer(QuestionnaireAssignment assignment,string questionId,JsonObject value,string principal,bool coordinator)
    {
        if(!assignment.Template.Questions.Any(q=>q.Id==questionId))throw new DemoValidationException("questionnaire_question_not_in_template");
        string[] allowed=["status","text","evidenceRefs","rationale","nextOwner","nextDate","blocker","scheduleEffect","assertedBy","attestationOwner","attestationDate","attestationQualification"];
        if(value.Any(p=>!allowed.Contains(p.Key,StringComparer.Ordinal)))throw new DemoValidationException("questionnaire_answer_field_invalid");
        var previous=assignment.Answers.GetValueOrDefault(questionId)??new();
        var answer=JsonSerializer.Deserialize<QuestionnaireAnswer>(JsonSerializer.Serialize(previous,AssessmentJson.Options),AssessmentJson.Options)!;
        foreach(var item in value)
        {
            if(item.Key=="evidenceRefs")
            {
                if(item.Value is not JsonArray refs || refs.Count>12)throw new DemoValidationException("questionnaire_evidence_refs_invalid");
                answer.EvidenceRefs=refs.Select(r=>r is JsonValue v && v.TryGetValue<string>(out var s) && s.Length is >0 and <=1024 && !s.Any(char.IsControl)?s:throw new DemoValidationException("questionnaire_evidence_refs_invalid")).ToList();
                continue;
            }
            var text=Text(value,item.Key,item.Key=="text"?8192:4096);
            switch(item.Key)
            {
                case "status": if(text is not ("unanswered" or "answered" or "unknown" or "blocked" or "unavailable" or "not_applicable"))throw new DemoValidationException("questionnaire_answer_status_invalid");answer.Status=text;break;
                case "text":answer.Text=text;break;case "rationale":answer.Rationale=text;break;case "nextOwner":answer.NextOwner=text;break;
                case "nextDate":answer.NextDate=text;break;case "blocker":answer.Blocker=text;break;case "scheduleEffect":answer.ScheduleEffect=text;break;
                case "assertedBy":if(!coordinator && text.Length>0 && text!=principal && text!=previous.AssertedBy)throw new DemoValidationException("questionnaire_attribution_forbidden");answer.AssertedBy=text;break;
                case "attestationOwner":answer.AttestationOwner=text;break;case "attestationDate":answer.AttestationDate=text;break;case "attestationQualification":answer.AttestationQualification=text;break;
            }
        }
        // Saving a form must not reattribute untouched meeting or workbook answers.
        // A contributor may round-trip an existing attributed value, but cannot
        // introduce another identity. A materially edited response is theirs.
        if(AssessmentWorkflow.Hash(answer)==AssessmentWorkflow.Hash(previous))return answer;
        answer.RecordedBy=principal;
        if(!coordinator || string.IsNullOrWhiteSpace(answer.AssertedBy))answer.AssertedBy=principal;
        return answer;
    }
    public static void Apply(AssessmentState state,AssessmentCommand command,string principal)
    {
        var f=command.Fields;var coordinator=Coordinator(state,principal);
        if(command.Operation=="questionnaire_create")
        {
            if(!coordinator)throw new DemoValidationException("assessment_forbidden");
            AssessmentWorkflow.Closed(f,"templateId","title","assignedTo","deployment");
            if(state.Questionnaires.Assignments.Count>=100)throw new DemoConflictException("questionnaire_assignment_limit");
            var catalog=QuestionnaireCatalogLoader.Current ?? throw new DemoConflictException("questionnaire_catalog_unavailable");
            var template=catalog.Templates.SingleOrDefault(t=>t.Id==Required(f,"templateId")) ?? throw new DemoValidationException("questionnaire_template_not_found");
            var recipient=Required(f,"assignedTo");Recipient(state,recipient);
            if(f["deployment"] is not JsonObject deployment)throw new DemoValidationException("questionnaire_deployment_required");
            AssessmentWorkflow.Closed(deployment,"label","product","environment");
            var id="questionnaire-"+AssessmentWorkflow.Hash(new{state.Id,state.Revision,command.IdempotencyKey})[..24];
            var snapshot=JsonSerializer.Deserialize<QuestionnaireTemplate>(JsonSerializer.Serialize(template,AssessmentJson.Options),AssessmentJson.Options)!;
            state.Questionnaires.Assignments.Add(new(){Id=id,Title=Required(f,"title"),TemplateId=template.Id,TemplateVersion=catalog.CatalogVersion,TemplateSha256=AssessmentWorkflow.Hash(snapshot),Template=snapshot,
                SourceSchemaVersion=catalog.SourceSchemaVersion,SourceSha256=catalog.SourceSha256,SourceClassification=catalog.SourceClassification,SourceStatus=catalog.SourceStatus,RecognitionBoundary=catalog.RecognitionBoundary,
                OperatingContract=(JsonObject)catalog.OperatingContract.DeepClone(),ScheduleEffects=[..catalog.ScheduleEffects],AssignedTo=recipient,
                Deployment=new(){Id="deployment-"+AssessmentWorkflow.Hash(new{assessmentId=state.Id,assignmentId=id})[..24],Label=Required(deployment,"label"),Product=Text(deployment,"product",512),Environment=Text(deployment,"environment",512)},
                Answers=template.Questions.ToDictionary(q=>q.Id,_=>new QuestionnaireAnswer(),StringComparer.Ordinal),Receipt="Questionnaire assigned, not sent. Open the assignment to answer the full source form."});
            return;
        }
        var assignment=Assignment(state,command.TargetId,principal,true);
        switch(command.Operation)
        {
            case "questionnaire_save":
                EnsureEditable(assignment);AssessmentWorkflow.Closed(f,"answers");
                if(f["answers"] is not JsonObject answers || answers.Count>27)throw new DemoValidationException("questionnaire_answers_invalid");
                foreach(var answer in answers)assignment.Answers[answer.Key]=MergeAnswer(assignment,answer.Key,answer.Value as JsonObject ?? throw new DemoValidationException("questionnaire_answer_invalid"),principal,coordinator);
                assignment.Receipt="Draft saved. Unanswered questions remain visible; no submission or approval was recorded.";break;
            case "questionnaire_submit":
                EnsureEditable(assignment);AssessmentWorkflow.Closed(f);
                if(!Validate(assignment).CanSubmit)throw new DemoConflictException("questionnaire_submission_incomplete");
                assignment.Status="submitted";
                assignment.Submission=new(DateTimeOffset.UtcNow.ToString("O"),principal,assignment.Answers.Where(a=>a.Value.Status is "unknown" or "blocked" or "unavailable").Select(a=>a.Key).ToList(),AssessmentWorkflow.Hash(new{assignment.TemplateSha256,assignment.Deployment,assignment.Answers}));
                assignment.Receipt="Response submitted to the coordinator. This records supplied answers and limitations, not verified evidence or formal acceptance.";break;
            case "questionnaire_reopen":
                if(!coordinator)throw new DemoValidationException("assessment_forbidden");AssessmentWorkflow.Closed(f,"reason");var reopenReason=Required(f,"reason");
                assignment.History.Add(new(command.Operation,state.Revision+1,principal,DateTimeOffset.UtcNow.ToString("O"),reopenReason,assignment.AssignedTo,assignment.AssignedTo,assignment.Submission?.ContentSha256));
                assignment.Status="draft";assignment.Submission=null;assignment.Receipt="A new draft is open. Earlier submitted revisions remain in immutable history.";break;
            case "questionnaire_reassign":
                if(!coordinator)throw new DemoValidationException("assessment_forbidden");EnsureEditable(assignment);AssessmentWorkflow.Closed(f,"assignedTo","reason");var reassignReason=Required(f,"reason");
                var assigned=Required(f,"assignedTo");Recipient(state,assigned);
                assignment.History.Add(new(command.Operation,state.Revision+1,principal,DateTimeOffset.UtcNow.ToString("O"),reassignReason,assignment.AssignedTo,assigned,null));
                assignment.AssignedTo=assigned;assignment.Receipt="Assignment changed; the previous contributor no longer has access.";break;
            default:throw new DemoValidationException("questionnaire_operation_invalid");
        }
    }
    private static void Recipient(AssessmentState state,string principal)
    {if(!IntakeWorkflow.Contributor(principal) || !state.Assignments.Any(a=>a.PrincipalId==principal))throw new DemoValidationException("questionnaire_recipient_invalid");}
    public static JsonObject Detail(AssessmentState state,string id,string principal)
    {
        var assignment=Assignment(state,id,principal);var coordinator=Coordinator(state,principal);
        return AssessmentJson.Object(new{assessmentId=state.Id,assessmentName=state.Name,revision=state.Revision,assignment,
            canEdit=assignment.Status=="draft" && (coordinator || assignment.AssignedTo==principal),canCoordinate=coordinator,
            validation=Validate(assignment),receipt=assignment.Receipt,boundary=Boundary});
    }
}
