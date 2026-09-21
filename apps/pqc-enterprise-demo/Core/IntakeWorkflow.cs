using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

/// <summary>Pure evaluator inside the existing synthetic assessment Worker/controller path.</summary>
public static class IntakeWorkflow
{
    public const string Boundary = "Synthetic questionnaire-to-report candidate. Responses are attributed statements, not verified inventory. No enterprise acceptance or execution authority.";
    public static readonly IntakeQuestion[] Questions =
    [
        new("owner","Which function owns or knows this system?","Routes the request to the people who can confirm the inventory.","A responsible function, an existing ownership reference, or 'I do not know'."),
        new("evidenceRoute","Where is the existing evidence held?","Identifies a possible read-only evidence route; does not authorize access.","A repository or system of record, such as a CMDB, certificate manager or approved configuration export."),
        new("referral","Who should we ask next?","Makes a useful handoff possible even if this is not your team's system.","Another function or 'not my team'; this app does not send a message."),
        new("limitation","What remains unknown or unavailable?","Keeps the current-state report honest about its limitations.","For example: owner not confirmed, export unavailable, or only one environment examined.")
    ];
    public static bool Contributor(string principal) => principal is "synthetic-demo:contributor" or "synthetic-demo:contributor-two";
    public static bool Coordinate(AssessmentState state,string principal) => AssessmentWorkflow.Role(state,principal)=="assessment-lead";
    public static IntakeRequest Request(AssessmentState state,string? id,string principal,bool write=false)
    {
        var request=state.Intake.Requests.SingleOrDefault(r=>r.Id==id) ?? throw new DemoValidationException("intake_request_not_found");
        var role=AssessmentWorkflow.Role(state,principal);
        if(Contributor(principal) && request.AssignedTo!=principal || write && role!="assessment-lead" && request.AssignedTo!=principal)
            throw new DemoValidationException("assessment_forbidden");
        return request;
    }
    public static string NewId(string kind,AssessmentState state,string? target) => "intake-"+kind+"-"+AssessmentWorkflow.Hash(new{state.Id,state.Revision,target})[..24];
    public static string Value(JsonObject fields,string key,bool required=false)
    {
        var text=required?AssessmentWorkflow.Required(fields,key):AssessmentWorkflow.Text(fields,key);
        if(text.Length>512)throw new DemoValidationException("intake_text_limit");
        return text;
    }
    public static Dictionary<string,string> AnswerRows(AssessmentState state,IntakeRequest request)
    {
        var rows=new Dictionary<string,string>(StringComparer.Ordinal);
        foreach(var scope in new[]{request.Id}.Concat(request.SystemIds))
            foreach(var q in Questions)rows.Add(scope+"/"+q.Id,request.Answers.GetValueOrDefault(scope+"/"+q.Id,""));
        return rows;
    }
    public static string RequestFingerprint(AssessmentState state,IntakeRequest request) => AssessmentWorkflow.Hash(new{request,systems=state.Intake.Systems.Where(s=>request.SystemIds.Contains(s.Id))});
    public static void Invalidate(IntakeRequest request,string principal)
    {
        request.Status="responding";request.RecordedBy=principal;request.Determination="awaiting_review";request.ReviewedBy="";request.Limitation="";
    }
    public static void Apply(AssessmentState state,AssessmentCommand command,string principal,string now)
    {
        var role=AssessmentWorkflow.Role(state,principal);
        if(command.ExpectedRevision!=state.Revision)throw new DemoConflictException("assessment_revision_changed");
        if(state.Intake.Requests.Count>20 || state.Intake.Systems.Count>80)throw new DemoConflictException("intake_capacity_limit");
        var f=command.Fields;
        switch(command.Operation)
        {
            case "intake_create_request":
                if(role!="assessment-lead")throw new DemoValidationException("assessment_forbidden");
                AssessmentWorkflow.Closed(f,"title","familyId","assignedTo");
                if(state.Intake.Requests.Count>=20)throw new DemoConflictException("intake_capacity_limit");
                var family=Value(f,"familyId",true);
                var source=state.Sources.SingleOrDefault(s=>s.FamilyId==family && state.Scope.IncludedFamilyIds.Contains(family)) ?? throw new DemoValidationException("assessment_source_not_in_scope");
                var assigned=Value(f,"assignedTo",true);
                if(!Contributor(assigned) || !state.Assignments.Any(a=>a.PrincipalId==assigned))throw new DemoValidationException("intake_recipient_invalid");
                var created=new IntakeRequest{Id=NewId("request",state,null),Title=Value(f,"title",true),FamilyId=family,AssignedTo=assigned,Examples=[..source.Examples]};
                state.Intake.Requests.Add(created);
                state.Intake.Receipt=new("Request created, not sent. Its assigned synthetic contributor can open My requests.",assigned,created.Id);
                break;
            case "intake_add_system":
                var request=Request(state,command.TargetId,principal,true);
                AssessmentWorkflow.Closed(f,"label","product","environment","systemRole","aboutSystemId");
                if(request.SystemIds.Count>=8 || state.Intake.Systems.Count>=80)throw new DemoConflictException("intake_capacity_limit");
                var systemRole=Value(f,"systemRole",true);
                if(systemRole is not ("subject" or "source" or "both"))throw new DemoValidationException("intake_system_role_invalid");
                var about=Value(f,"aboutSystemId");
                if(about.Length>0 && !request.SystemIds.Contains(about))throw new DemoValidationException("intake_subject_binding_invalid");
                var system=new IntakeSystem{Id=NewId("system",state,request.Id),RequestId=request.Id,Label=Value(f,"label",true),Product=Value(f,"product"),Environment=Value(f,"environment"),SystemRole=systemRole,AboutSystemId=about};
                state.Intake.Systems.Add(system);request.SystemIds.Add(system.Id);Invalidate(request,principal);
                state.Intake.Receipt=new("One distinct system recorded. Product and ownership statements still need confirmation; no evidence admitted.",request.AssignedTo,request.Id);
                break;
            case "intake_save_response":
                request=Request(state,command.TargetId,principal,true);
                AssessmentWorkflow.Closed(f,"answers","assertedBy");
                if(f["answers"] is not JsonObject answers || answers.Count>36)throw new DemoValidationException("intake_answers_invalid");
                var valid=AnswerRows(state,request);
                var asserted=Value(f,"assertedBy");
                if(Contributor(principal) && asserted.Length>0 && asserted!=principal)throw new DemoValidationException("intake_attribution_invalid");
                foreach(var item in answers)
                {
                    if(!valid.ContainsKey(item.Key))throw new DemoValidationException("intake_question_scope_invalid");
                    request.Answers[item.Key]=Value(answers,item.Key);
                }
                request.AssertedBy=Contributor(principal)?principal:asserted.Length>0?asserted:principal;
                Invalidate(request,principal);
                state.Intake.Receipt=new("Draft saved. These answers are attributed statements; they have not been submitted or technically verified.",request.AssignedTo,request.Id);
                break;
            case "intake_submit_response":
                request=Request(state,command.TargetId,principal,true);AssessmentWorkflow.Closed(f);
                if(request.SystemIds.Count==0 && request.Answers.Values.All(string.IsNullOrWhiteSpace))throw new DemoValidationException("intake_useful_response_required");
                request.Status="returned";request.RecordedBy=principal;
                if(request.AssertedBy.Length==0)request.AssertedBy=principal;
                state.Intake.Receipt=new($"Response submitted with {request.SystemIds.Count} identified system(s). Unknown answers remain limitations, not verified facts. The coordinator now has the handoff.","Assessment lead",request.Id);
                break;
            case "intake_review_response":
                if(role!="technical-reviewer")throw new DemoValidationException("assessment_forbidden");
                request=Request(state,command.TargetId,principal);
                AssessmentWorkflow.Closed(f,"determination","limitation");
                if(request.Status!="returned" || request.RecordedBy==principal)throw new DemoConflictException("intake_independent_review_required");
                var determination=Value(f,"determination",true);
                if(determination is not ("qualified" or "needs_clarification"))throw new DemoValidationException("intake_determination_invalid");
                request.Limitation=Value(f,"limitation",true);request.Determination=determination;request.ReviewedBy=principal;
                request.Status=determination=="qualified"?"closed_with_limitation":"clarification_needed";
                state.Intake.Receipt=new("Factual review recorded with an explicit limitation. No gate approval or enterprise completeness claim was created.","Assessment lead",request.Id);
                break;
            case "intake_commit_import":
                request=Request(state,command.TargetId,principal,true);AssessmentWorkflow.Closed(f,"previewId","choices");
                var preview=state.Intake.Imports.SingleOrDefault(p=>p.Id==Value(f,"previewId",true) && p.RequestId==request.Id && p.PrincipalId==principal) ?? throw new DemoValidationException("intake_preview_not_found");
                if(preview.Committed || preview.RequestFingerprint!=RequestFingerprint(state,request))throw new DemoConflictException("intake_preview_stale");
                var export=state.Intake.Exports.Single(e=>e.Id==preview.ExportId);
                if(export.AssignedTo!=request.AssignedTo || export.TemplateVersion!=request.TemplateVersion)throw new DemoConflictException("intake_export_stale");
                if(f["choices"] is not JsonObject choices || choices.Any(p=>!preview.Changes.Any(c=>c.Key==p.Key)))throw new DemoValidationException("intake_choices_invalid");
                foreach(var change in preview.Changes)
                {
                    var choice=choices[change.Key] is null?"current":Value(choices,change.Key,true);
                    if(choice is not ("current" or "returned" or "clear"))throw new DemoValidationException("intake_choice_invalid");
                    if(change.State=="conflict" && choices[change.Key] is null)throw new DemoValidationException("intake_conflict_resolution_required");
                    if(choice=="returned" && change.State!="unchanged")request.Answers[change.Key]=change.Returned;
                    else if(choice=="clear")request.Answers[change.Key]="";
                }
                preview.Committed=true;request.AssertedBy="Unverified workbook author; intended recipient "+request.AssignedTo;Invalidate(request,principal);
                state.Intake.Receipt=new("Selected workbook changes saved as a draft. Submit the response when ready; workbook text cannot approve a gate.",request.AssignedTo,request.Id);
                break;
            case "intake_admit_evidence":
                if(role!="assessment-lead")throw new DemoValidationException("assessment_forbidden");
                request=Request(state,command.TargetId,principal);AssessmentWorkflow.Closed(f,"batchId");
                if(!AssessmentWorkflow.Passed(state,"PQC-G00") || !AssessmentWorkflow.Passed(state,"PQC-P1-G01"))throw new DemoConflictException("assessment_prerequisite_gate_required");
                var batch=state.Intake.Batches.SingleOrDefault(b=>b.Id==Value(f,"batchId",true) && b.RequestId==request.Id) ?? throw new DemoValidationException("intake_batch_not_found");
                DiscoveryEvidence.RefuseLegacyAdmission(state,batch.Id);
                batch.Status="admitted";
                state.Intake.Receipt=new($"{batch.Observations.Count} synthetic TLS observation(s) admitted to this assessment's intake map and report inputs. Their supplied evidence basis is preserved, not independently verified.","Technical reviewer",request.Id);
                break;
            default: throw new DemoValidationException("intake_operation_invalid");
        }
        state.Revision++;state.UpdatedAt=now;
        state.Events.Add(new(state.Revision,command.Operation,command.TargetId,principal,now,"user_entered_synthetic"));
        AssessmentWorkflow.Refresh(state,principal);
    }
    public static JsonObject Projection(AssessmentState state,string principal)
    {
        var coordinator=Coordinate(state,principal);
        var role=AssessmentWorkflow.Role(state,principal);
        var requests=state.Intake.Requests.Where(r=>!Contributor(principal) || r.AssignedTo==principal).ToArray();
        var ids=requests.Select(r=>r.Id).ToHashSet(StringComparer.Ordinal);
        var systems=state.Intake.Systems.Where(s=>ids.Contains(s.RequestId)).ToArray();
        var batches=state.Intake.Batches.Where(b=>ids.Contains(b.RequestId)).ToArray();
        var observations=batches.Where(b=>b.Status=="admitted").SelectMany(b=>b.Observations).DistinctBy(o=>o.Id).ToArray();
        return AssessmentJson.Object(new{assessmentId=state.Id,assessmentName=state.Name,revision=state.Revision,role,synthetic=true,
            requests,systems,questions=Questions,eligibleFamilyIds=state.Scope.IncludedFamilyIds,receipt=Contributor(principal) && !requests.Any(r=>r.Id==state.Intake.Receipt?.NextAction)?null:state.Intake.Receipt,
            evidence=observations,pendingEvidence=batches.Where(b=>b.Status=="staged").Select(b=>new{b.Id,b.RequestId,b.SystemId,b.SourceSystemId,count=b.Observations.Count,b.ContentSha256}),
            reportPreview=ReportPreview(state,requests,systems,observations),canCoordinate=coordinator,canReview=role=="technical-reviewer",
            canAdmit=coordinator && AssessmentWorkflow.Passed(state,"PQC-G00") && AssessmentWorkflow.Passed(state,"PQC-P1-G01"),boundary=Boundary});
    }
    public static JsonObject ReportPreview(AssessmentState state,IEnumerable<IntakeRequest>? selected=null,IEnumerable<IntakeSystem>? selectedSystems=null,IEnumerable<IntakeObservation>? selectedObservations=null)
    {
        var requests=(selected??state.Intake.Requests).Where(r=>state.Scope.IncludedFamilyIds.Contains(r.FamilyId)).ToArray();
        var ids=requests.Select(r=>r.Id).ToHashSet();
        var systems=(selectedSystems??state.Intake.Systems).Where(s=>ids.Contains(s.RequestId)).ToArray();
        var systemIds=systems.Select(s=>s.Id).ToHashSet();
        var observations=(selectedObservations??state.Intake.Batches.Where(b=>b.Status=="admitted" && ids.Contains(b.RequestId)).SelectMany(b=>b.Observations).DistinctBy(o=>o.Id)).Where(o=>systemIds.Contains(o.SystemId)).ToArray();
        var conclusions=new List<string>();var limitations=new List<string>{"Enterprise population is unknown. These counts are not an enterprise coverage percentage."};
        var decisions=new List<string>();
        // Answers are free text, not normalized owner identities, confirmed
        // routes or assigned handoffs. Quote every response without attempting
        // to recognize words such as "unknown" or interpret them as approval.
        static string Response(string label,string value)=>string.IsNullOrWhiteSpace(value)
            ?$"{label} response: not provided."
            :$"{label} response: “{value}”.";
        static string RouteDecision(string label,string route,string referral)=>
            $"{label}: {Response("Evidence-location",route)} Review the response and establish an evidence route; obtain authorization before collection. {Response("Referral",referral)} The assessment lead must confirm the next responsible function.";
        foreach(var system in systems)
        {
            var request=requests.Single(r=>r.Id==system.RequestId);
            string Answer(string question,string fallback="")
            {
                var value=request.Answers.GetValueOrDefault(system.Id+"/"+question,"");
                if(string.IsNullOrWhiteSpace(value))value=request.Answers.GetValueOrDefault(request.Id+"/"+question,"");
                return string.IsNullOrWhiteSpace(value)?fallback:value;
            }
            var owner=Answer("owner");
            var roleLabel=system.SystemRole switch
            {
                "subject"=>"system being assessed",
                "source"=>"system supplying evidence",
                "both"=>"system being assessed and supplying evidence",
                _=>"system role not established"
            };
            conclusions.Add($"{system.Label}: {roleLabel}. {Response("Product",system.Product)} {Response("Ownership",owner)} These are attributed responses; confirm the responsible function separately. They do not verify technical behavior.");
            var evidence=observations.Where(o=>o.SystemId==system.Id).ToArray();
            foreach(var o in evidence)conclusions.Add($"{system.Label} / {o.Hostname}: key establishment {o.KeyExchange}; certificate authentication {o.Authentication}. Source labels this {o.Basis}; this app has not independently exercised the endpoint.");
            if(evidence.Length==0 && system.SystemRole!="source")limitations.Add($"{system.Label}: no technical observation admitted; do not infer cryptographic exposure or readiness.");
            var referral=Answer("referral");
            var route=Answer("evidenceRoute");
            decisions.Add(RouteDecision(system.Label,route,referral));
        }
        foreach(var request in requests)
        {
            if(!systems.Any(s=>s.RequestId==request.Id))
            {
                var owner=request.Answers.GetValueOrDefault(request.Id+"/owner","");
                var referral=request.Answers.GetValueOrDefault(request.Id+"/referral","");
                var route=request.Answers.GetValueOrDefault(request.Id+"/evidenceRoute","");
                conclusions.Add($"{request.Title}: {Response("Ownership",owner)} This is an attributed routing response; confirm the responsible function separately. No system identity or technical behavior has been established.");
                decisions.Add(RouteDecision(request.Title,route,referral));
            }
            limitations.AddRange(request.Answers.Where(a=>a.Key.EndsWith("/limitation",StringComparison.Ordinal) && a.Value.Length>0).Select(a=>request.Title+": "+a.Value));
            if(request.Limitation.Length>0)limitations.Add(request.Title+": "+request.Limitation);
            if(request.Determination!="qualified")limitations.Add(request.Title+": response interpretation has not completed factual review.");
        }
        return AssessmentJson.Object(new{schemaVersion="pqc.intake.report-input.v1",summary=$"{systems.Length} recorded systems and evidence sources; {requests.Count(r=>r.Status is "returned" or "closed_with_limitation")} returned requests; {observations.Length} admitted synthetic observations. Draft assessment input, not accepted deliverables.",
            conclusions,limitations=limitations.Distinct().ToArray(),nextDecisions=decisions.Distinct().ToArray(),evidence=observations,
            lineage=new{templateVersions=requests.Select(r=>r.TemplateVersion).Distinct(),assessmentId=state.Id,assessmentRevision=state.Revision,inputSha256=AssessmentWorkflow.Hash(new{requests,systems,observations})},
            phase2Reliance="Use only the explicitly accepted-or-qualified Phase 1 package. No questionnaire, upload or this preview grants reliance or migration authority."});
    }
}
