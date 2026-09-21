using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

public sealed partial class EnterpriseStore
{
    private const string WorkspaceBoundary="Synthetic response-to-report rehearsal. Received testimony, reviewed identity, technical observations and report acceptance are separate. No email delivery, live source connection, enterprise approval or migration execution is enabled.";
    public JsonObject AssessmentWork(string id,string principal)
    {
        lock(gate)
        {
            var state=ReadAssessment(id,principal);WorkspaceStaff(state,principal);AssessmentWorkflow.Refresh(state,principal);
            return new JsonObject{["assessmentId"]=id,["assessmentName"]=state.Name,["revision"]=state.Revision,["mode"]=state.ScenarioVersion??state.Mode,
                ["items"]=new JsonArray(state.Discovery.Requests.Select(r=>(JsonNode)WorkspaceTask(state,r,principal)).OrderBy(r=>WText((JsonObject)r,"state")=="needs_action"?0:WText((JsonObject)r,"state")=="recorded"?3:1).ToArray()),
                ["gateActions"]=new JsonArray(state.NextActions.Where(a=>a.Operation is "decide_gate" or "submit_gate" or "generate_report").Select(a=>(JsonNode)AssessmentJson.Object(a)).ToArray()),
                ["canReceive"]=AssessmentWorkflow.Role(state,principal)=="assessment-lead",["boundary"]=WorkspaceBoundary};
        }
    }
    public JsonObject AssessmentWorkCase(string id,string requestId,string principal)
    {lock(gate){var state=ReadAssessment(id,principal);WorkspaceStaff(state,principal);return WorkspaceCase(state,requestId,principal);}}

    private JsonObject WorkspaceTask(AssessmentState state,DiscoveryRequest request,string principal)
    {
        var role=AssessmentWorkflow.Role(state,principal);var receipts=WorkspaceRows(state,"workspace_receipts",request.Id);
        var applied=receipts.Where(r=>WText(r,"status")=="applied").Select(r=>WText(r,"id")).ToHashSet(StringComparer.Ordinal);
        var products=WorkspaceRows(state,"workspace_products",request.Id).Where(p=>applied.Contains(WText(p,"receiptId"))).ToArray();
        var identities=WorkspaceRows(state,"workspace_identities",request.Id);var bundles=WorkspaceBundleRows(state,request.Id);
        var consequences=WorkspaceRows(state,"workspace_consequences",request.Id);
        var task="Review returned information";var next="Assessment lead";var neededRole="assessment-lead";var status="needs_action";
        var why="Identify the reported products and information routes, preserving what remains unknown.";
        var effect="Recording a response makes it available for investigation, not technical verification.";
        if(receipts.Any(r=>WText(r,"status")=="staged")) {task="Review received questionnaire";why="A workbook is waiting for comparison with current answers.";effect="Chosen answers are recorded as attributed input; conflicting versions remain in history.";}
        else if(request.Status!="submitted") {task="Waiting for a useful response";next="Source team / coordinator";neededRole="contributor";status="waiting";effect="A partial response, referral or explicit unknown is sufficient.";}
        else if(products.Any(p=>!identities.Any(i=>WText(i,"productId")==WText(p,"id")))) {task="Identify products and deployments";why="Reported rows may describe separate systems or repeated references to the same deployment.";effect="Explicit identity decisions connect reported rows; original assertions remain unchanged.";}
        else if(bundles.Any(b=>WText(b,"status") is "staged" or "identity_review_required")) {task="Review technical records";next="Technical review lead";neededRole="technical-reviewer";why="Inspect actual source fields and competing observations, including changed deployment bindings, before qualifying a bundle.";effect="Factual review permits lead consideration for admission; it does not verify live behavior.";}
        else if(bundles.Any(b=>WText(b,"status")=="qualified")) {task="Admit reviewed technical records";why="An independent reviewer has qualified a bounded bundle.";effect="Admission updates this assessment's map and report inputs after its gates are satisfied.";}
        else if(bundles.Any(b=>WText(b,"status")=="needs_clarification")) {task="Resolve a source clarification";next="Assigned investigator / source function";status="waiting";why="A reviewer could not qualify the supplied records.";effect="A new corrected capture is reviewed separately; the earlier review stays unchanged.";}
        else if(consequences.Any(c=>WText(c,"status")=="needs_review")) {task="Re-review the assessment consequence";why="A relied-upon identity or evidence binding changed. Earlier conclusions remain historical only.";effect="Record a fresh supported interpretation; unrelated conclusions and frozen reports remain unchanged.";}
        else if(consequences.Count>0)
        {
            var consequence=consequences[^1];var pending=WText(consequence,"limitation").Length>0||WText(consequence,"nextDecision").Length>0;
            task=pending?"Consequence recorded; follow-up remains":"Assessment consequence recorded";status=pending?"waiting":"recorded";next=WText(consequence,"responsibleFunction","Gate reviewers / assessment lead");
            why=pending?WText(consequence,"nextDecision"):"A conclusion and limitations are recorded for report preparation.";effect="The recorded interpretation is preserved; unresolved limitations and formal report review remain unfinished work.";
        }
        else if(bundles.Any(b=>WText(b,"status")=="admitted")) {task="Explain the assessment consequence";why="Reviewed observations need a clear conclusion, limitation and next decision.";effect="The exact interpretation becomes a versioned input to report drafts.";}
        else {task="Investigate or record the limitation";status="in_progress";why="A useful response identifies where to investigate; no technical bundle is admitted yet.";effect="Research can proceed without claiming source access, readiness or verified cryptography.";}
        if(status=="needs_action"&&role!=neededRole)status="waiting";
        var canAct=role==neededRole&&(status is "needs_action" or "in_progress");
        var step=task switch{"Review received questionnaire" or "Waiting for a useful response"=>"returned","Identify products and deployments"=>"systems","Review technical records" or "Admit reviewed technical records" or "Resolve a source clarification" or "Investigate or record the limitation"=>"technical",_=>"consequence"};
        return new JsonObject{["requestId"]=request.Id,["title"]=request.Title,["familyId"]=request.FamilyId,["familyName"]=request.FamilyName,["state"]=status,["task"]=task,["step"]=step,["why"]=why,["effect"]=effect,["nextFunction"]=next,["canAct"]=canAct};
    }

    private JsonObject WorkspaceCase(AssessmentState state,string requestId,string principal)
    {
        WorkspaceStaff(state,principal);var request=DiscoveryWorkflow.Request(state,requestId,principal);var role=AssessmentWorkflow.Role(state,principal);
        var actions=new List<string>();
        if(role=="assessment-lead")actions.AddRange(["receipt_receive","receipt_apply","reconcile_product","record_consequence","workspace_stage_evidence","workspace_admit_evidence","discovery_create_investigation","discovery_update_investigation","discovery_add_product","discovery_stage_evidence","discovery_admit_evidence"]);
        if(role=="technical-reviewer")actions.AddRange(["workspace_review_evidence","discovery_review_evidence","discovery_update_investigation"]);
        if(role=="risk-lead")actions.Add("record_consequence");
        var bundles=WorkspaceBundleRows(state,requestId);
        foreach(var bundle in bundles)
        {
            bundle["canReview"]=role=="technical-reviewer"&&(WText(bundle,"status") is "staged" or "identity_review_required")&&WText(bundle,"stagedBy")!=principal;
            bundle["canAdmit"]=role=="assessment-lead"&&WText(bundle,"status")=="qualified"&&AssessmentWorkflow.Passed(state,"PQC-G00")&&AssessmentWorkflow.Passed(state,"PQC-P1-G01");
        }
        var caseTargets=new HashSet<string>(StringComparer.Ordinal){requestId};
        foreach(var table in new[]{"workspace_receipts","workspace_products","workspace_bundles","workspace_identities","workspace_consequences"})
            foreach(var record in WorkspaceRows(state,table,requestId))caseTargets.Add(WText(record,"id"));
        foreach(var investigation in state.Discovery.Investigations.Where(i=>i.RequestId==requestId))caseTargets.Add(investigation.Id);
        var consequences=WorkspaceRows(state,"workspace_consequences",requestId).OrderBy(r=>r["revision"]!.GetValue<int>()).ToArray();
        var stageReasons=new List<string>();
        if(role!="assessment-lead")stageReasons.Add("The assessment lead records controlled synthetic source captures in this increment.");
        if(!AssessmentWorkflow.Passed(state,"PQC-G00")||!AssessmentWorkflow.Passed(state,"PQC-P1-G01"))stageReasons.Add("Boundary and source/access-register gates must pass before technical information is staged.");
        if(request.Status!="submitted")stageReasons.Add("Record a useful response before staging technical information.");
        if(!state.Scope.IncludedFamilyIds.Contains(request.FamilyId))stageReasons.Add("This request's family is outside the selected assessment scope.");
        if(!WorkspaceRows(state,"workspace_receipts",requestId).Any(r=>WText(r,"status")=="applied"&&WorkspaceRows(state,"workspace_products",requestId).Any(p=>WText(p,"receiptId")==WText(r,"id"))))stageReasons.Add("First record a returned form with an identified product or deployment.");
        return new JsonObject{["assessmentId"]=state.Id,["assessmentName"]=state.Name,["revision"]=state.Revision,["mode"]=state.ScenarioVersion??state.Mode,["task"]=WorkspaceTask(state,request,principal),
            ["request"]=AssessmentJson.Object(request),["investigations"]=new JsonArray(state.Discovery.Investigations.Where(i=>i.RequestId==requestId).Select(i=>(JsonNode)AssessmentJson.Object(i)).ToArray()),
            ["receipts"]=new JsonArray(WorkspaceRows(state,"workspace_receipts",requestId).Select(r=>(JsonNode)ReceiptView(state,r)).ToArray()),["identityDecisions"]=new JsonArray(WorkspaceRows(state,"workspace_identities",requestId).Select(i=>(JsonNode)i).ToArray()),
            ["technicalRecords"]=new JsonArray(bundles.Select(b=>(JsonNode)b).ToArray()),["consequence"]=consequences.LastOrDefault()?.DeepClone(),["consequences"]=new JsonArray(consequences.Select(r=>(JsonNode)r).ToArray()),
            ["history"]=new JsonArray(state.Events.Where(e=>e.TargetId is not null&&caseTargets.Contains(e.TargetId)).TakeLast(100).Select(e=>(JsonNode)AssessmentJson.Object(e)).ToArray()),
            ["documents"]=new JsonArray(state.Documents.Select(d=>(JsonNode)AssessmentJson.Object(d)).ToArray()),["allowedActions"]=new JsonArray(actions.Select(a=>(JsonNode?)JsonValue.Create(a)).ToArray()),["canStageEvidence"]=stageReasons.Count==0,["stageEvidenceBlockingReasons"]=new JsonArray(stageReasons.Select(a=>(JsonNode?)JsonValue.Create(a)).ToArray()),["boundary"]=WorkspaceBoundary};
    }

    private List<JsonObject> WorkspaceBundleRows(AssessmentState state,string? requestId=null)
    {
        var bundles=WorkspaceRows(state,"workspace_bundles",requestId);var observations=WorkspaceRows(state,"workspace_observations",requestId);
        var reviews=WorkspaceRows(state,"workspace_technical_reviews",requestId);
        foreach(var bundle in bundles)
        {
            var review=reviews.SingleOrDefault(r=>WText(r,"bundleId")==WText(bundle,"id"));
            bundle["recordDecisions"]=review?["recordDecisions"]?.DeepClone()??new JsonArray();
            bundle["observations"]=new JsonArray(observations.Where(o=>WText(o,"bundleId")==WText(bundle,"id")).Select(o=>
            {
                var record=(JsonObject)o.DeepClone();var decision=review is null?null:Rows(review,"recordDecisions").SingleOrDefault(d=>WText(d,"observationId")==WText(o,"id"));
                record["technicalDetermination"]=decision is null?"unreviewed":WText(decision,"determination");record["technicalRationale"]=decision is null?"":WText(decision,"rationale");return (JsonNode)record;
            }).ToArray());
        }
        foreach(var investigation in state.Discovery.Investigations.Where(i=>requestId is null||i.RequestId==requestId))
        foreach(var evidence in investigation.EvidenceReviews)
        {
            var bundle=AssessmentJson.Object(evidence);bundle["id"]=evidence.BatchId;bundle["bundleId"]=evidence.BatchId;bundle["requestId"]=investigation.RequestId;bundle["investigationId"]=investigation.Id;bundle["kind"]="tls";bundle["legacy"]=true;
            bundle["observations"]=new JsonArray(state.Intake.Batches.Where(b=>evidence.BatchIds.Contains(b.Id)).SelectMany(b=>b.Observations).Select(o=>(JsonNode)AssessmentJson.Object(o)).ToArray());bundles.Add(bundle);
        }
        return bundles;
    }
    public JsonObject WorkspaceObservations(string id,string bundleId,string principal,int page=1,int pageSize=25)
    {
        lock(gate)
        {
            var state=ReadAssessment(id,principal);WorkspaceStaff(state,principal);
            var bundle=WorkspaceBundleRows(state).SingleOrDefault(b=>WText(b,"bundleId")==bundleId)??throw new DemoValidationException("workspace_evidence_not_found");
            if(page<1||page>10000||pageSize<1||pageSize>100)throw new DemoValidationException("workspace_page_invalid");
            var observations=Rows(bundle,"observations").ToArray();var metadata=(JsonObject)bundle.DeepClone();metadata.Remove("observations");
            return new JsonObject{["assessmentId"]=id,["revision"]=state.Revision,["bundleId"]=bundleId,["bundle"]=metadata,["observations"]=new JsonArray(observations.Skip((page-1)*pageSize).Take(pageSize).Select(o=>o.DeepClone()).ToArray()),["page"]=page,["pageSize"]=pageSize,["total"]=observations.Length,["hasMore"]=page*pageSize<observations.Length,["boundary"]="Source fields are visible for factual review. Configured, reported and observed bases are distinct; this is not independent runtime verification."};
        }
    }

    internal JsonObject WorkspaceReportInput(AssessmentState state)
    {
        var families=state.Scope.IncludedFamilyIds.ToHashSet(StringComparer.Ordinal);
        var requests=state.Discovery.Requests.Where(r=>families.Contains(r.FamilyId)).Select(r=>r.Id).ToHashSet(StringComparer.Ordinal);
        var receipts=WorkspaceRows(state,"workspace_receipts").Where(r=>requests.Contains(WText(r,"requestId"))&&WText(r,"status")=="applied").Select(r=>ReceiptView(state,r)).ToArray();
        var identities=WorkspaceRows(state,"workspace_identities").Where(r=>requests.Contains(WText(r,"requestId"))).ToArray();
        var bundles=WorkspaceBundleRows(state).Where(b=>requests.Contains(WText(b,"requestId"))&&WText(b,"status")=="admitted").ToArray();
        var consequences=WorkspaceRows(state,"workspace_consequences").Where(r=>requests.Contains(WText(r,"requestId"))).ToArray();
        var pendingBindings=WorkspaceBundleRows(state).Where(b=>requests.Contains(WText(b,"requestId"))&&b["bindingReviewRequired"]?.GetValue<bool>()==true).ToArray();
        return new JsonObject{["schemaVersion"]="pqc.workspace.report-input.v1",["inputFingerprint"]=state.Workspace.MaterialFingerprint,
            ["hasActivity"]=receipts.Length>0||identities.Length>0||consequences.Length>0||bundles.Any(b=>b["legacy"]?.GetValue<bool>()!=true),
            ["receipts"]=new JsonArray(receipts.Select(r=>(JsonNode)r).ToArray()),["identities"]=new JsonArray(identities.Select(r=>(JsonNode)r).ToArray()),
            ["bundles"]=new JsonArray(bundles.Select(b=>(JsonNode)b).ToArray()),["consequences"]=new JsonArray(consequences.Select(r=>(JsonNode)r).ToArray()),
            ["pendingBindings"]=new JsonArray(pendingBindings.Select(b=>(JsonNode)new JsonObject{["bundleId"]=WText(b,"id"),["productId"]=WText(b,"productId"),["reason"]=WText(b,"identityChangeReason")}).ToArray()),["pendingConsequences"]=new JsonArray(consequences.Where(c=>WText(c,"status")=="needs_review").Select(c=>c.DeepClone()).ToArray()),
            ["history"]=new JsonArray(state.Events.Where(e=>e.Operation.StartsWith("workspace_",StringComparison.Ordinal)||e.Operation is "receipt_apply" or "reconcile_product" or "record_consequence").TakeLast(100).Select(e=>(JsonNode)AssessmentJson.Object(e)).ToArray()),["boundary"]=WorkspaceBoundary};
    }
}
