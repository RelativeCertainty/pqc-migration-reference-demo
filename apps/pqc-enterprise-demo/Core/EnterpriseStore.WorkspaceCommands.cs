using System.Security.Cryptography;
using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

public sealed partial class EnterpriseStore
{
    public JsonObject ReceiveOperationalReturn(string id,string requestId,int revision,string key,string principal,string filename,byte[] original,OperationalReturnDto parsed)
    {
        if(original.Length is <4 or >IntakeWorkbook.MaxInputBytes)throw new DemoValidationException("intake_upload_limit");
        if(filename.Length>240||filename.Any(char.IsControl)||filename!=Path.GetFileName(filename))throw new DemoValidationException("workspace_filename_invalid");
        var sha=Convert.ToHexStringLower(SHA256.HashData(original));
        lock(gate)
        {
            var existing=ReadAssessment(id,principal);WorkspaceLead(existing,principal);
            var request=DiscoveryWorkflow.Request(existing,requestId,principal);
            if(request.FamilyId!=parsed.FamilyId||request.TemplateVersion!=parsed.TemplateVersion)throw new DemoValidationException("workspace_template_mismatch");
            if(parsed.Answers.Count!=5||!parsed.Answers.Select(a=>a.QuestionId).ToHashSet(StringComparer.Ordinal).SetEquals(request.Questions.Select(q=>q.Id)))throw new DemoValidationException("workspace_question_set_invalid");
            // The operational template hash is checked by its dedicated parser;
            // it is not the app-export hash, and no fictitious export is created.
            var command=new AssessmentCommand("receipt_receive",requestId,new JsonObject{["artifactSha256"]=sha,["filename"]=filename,["profile"]=parsed.Profile},revision,key);
            var receiptId="wreceipt-"+AssessmentWorkflow.Hash(new{id,requestId,sha})[..24];
            ValidateAssessmentKey(key);
            var commandHash=AssessmentWorkflow.Hash(new{command.Operation,command.TargetId,command.Fields,command.ExpectedRevision,principal});
            using(var lookup=Command("SELECT request_sha256,revision FROM assessment_commands WHERE assessment_id=$id AND idempotency_key=$key",null,("$id",id),("$key",key)))
            using(var reader=lookup.ExecuteReader())if(reader.Read())
            {
                if(reader.GetString(0)!=commandHash)throw new DemoConflictException("idempotency_request_changed");var replayRevision=reader.GetInt32(1);reader.Close();
                var replay=ReadAssessment(id,principal,replayRevision);
                if(replay.Events.Any(e=>e.Revision==replayRevision&&e.Operation=="receipt_duplicate"))
                    return DuplicateReceiptResult(replay,WorkspaceRows(replay,"workspace_receipts").Single(r=>WText(r,"artifactSha256")==sha),principal);
                return new JsonObject{["assessmentId"]=id,["revision"]=replay.Revision,["receipt"]=ReceiptView(replay,WorkspaceFind(replay,"workspace_receipts",receiptId)),["case"]=WorkspaceCase(replay,requestId,principal),["effect"]="Workbook received for coordinator review. No source readiness, technical finding or approval has been created."};
            }
            var duplicate=WorkspaceRows(existing,"workspace_receipts").SingleOrDefault(r=>WText(r,"artifactSha256")==sha);
            if(duplicate is not null)
            {
                // A duplicate creates no receipt, product, artifact or report basis,
                // but its command outcome must still bind the idempotency key.
                var recorded=WorkspaceCommit(id,command,principal,_=>[],eventOperation:"receipt_duplicate");
                return DuplicateReceiptResult(recorded,duplicate,principal);
            }
            var state=WorkspaceCommit(id,command,principal,s=>
            {
                if(WorkspaceRows(s,"workspace_receipts").Count>=200)throw new DemoConflictException("workspace_receipt_capacity_limit");
                var now=DateTimeOffset.UtcNow.ToString("O");
                var receipt=new JsonObject{["id"]=receiptId,["requestId"]=requestId,["status"]="staged",["filename"]=filename,["artifactSha256"]=sha,
                    ["profile"]=parsed.Profile,["familyId"]=parsed.FamilyId,["templateVersion"]=parsed.TemplateVersion,["templateSha256"]=parsed.TemplateSha256,["questionnaireId"]=parsed.QuestionnaireId,
                    ["receivedAt"]=now,["receivedBy"]=principal,["respondent"]=parsed.Respondent,["team"]=parsed.Team,["knownOwner"]=parsed.KnownOwner,["responseDate"]=parsed.ResponseDate,["scope"]=parsed.Scope,["jiraKey"]=parsed.JiraKey,["coordinatorNote"]=parsed.CoordinatorNote,
                    ["attributionBoundary"]="Workbook names are attributed statements, not authenticated identities or approvals.",
                    ["answers"]=new JsonArray(parsed.Answers.Select(a=>(JsonNode)AssessmentJson.Object(a)).ToArray()),["previewFingerprint"]=ReceiptCurrentFingerprint(s,requestId),["appliedBy"]=""};
                var effects=new List<(string Table,JsonObject Record)>{("workspace_receipts",receipt)};
                for(var index=0;index<parsed.Products.Count;index++)
                {
                    var product=AssessmentJson.Object(parsed.Products[index]);product["id"]="wproduct-"+AssessmentWorkflow.Hash(new{receiptId,index})[..24];product["receiptId"]=receiptId;product["requestId"]=requestId;
                    effects.Add(("workspace_products",product));
                }
                return effects;
            },original);
            return new JsonObject{["assessmentId"]=id,["revision"]=state.Revision,["receipt"]=ReceiptView(state,WorkspaceFind(state,"workspace_receipts",receiptId)),["case"]=WorkspaceCase(state,requestId,principal),["effect"]="Workbook received for coordinator review. No source readiness, technical finding or approval has been created."};
        }
    }

    private JsonObject DuplicateReceiptResult(AssessmentState state,JsonObject receipt,string principal)=>new()
    { ["assessmentId"]=state.Id,["revision"]=state.Revision,["duplicate"]=true,["existingRequestId"]=WText(receipt,"requestId"),["receipt"]=ReceiptView(state,receipt),["case"]=WorkspaceCase(state,WText(receipt,"requestId"),principal),["effect"]="This exact file has already been received in this assessment. The duplicate command outcome was recorded; no duplicate task, response or source artifact was created. Review its existing request binding." };

    private static string ReceiptCurrentFingerprint(AssessmentState state,string requestId)
    {
        var r=state.Discovery.Requests.Single(r=>r.Id==requestId);
        return AssessmentWorkflow.Hash(new{r.Id,r.TemplateVersion,r.TemplateSha256,r.Status,r.Answers,r.ProductRefs});
    }
    private JsonObject ReceiptView(AssessmentState state,JsonObject receipt)
    {
        var view=(JsonObject)receipt.DeepClone();var request=state.Discovery.Requests.Single(r=>r.Id==WText(receipt,"requestId"));
        view["products"]=new JsonArray(WorkspaceRows(state,"workspace_products",request.Id).Where(p=>WText(p,"receiptId")==WText(receipt,"id")).Select(p=>(JsonNode)p).ToArray());
        view["comparison"]=new JsonArray(Rows(receipt,"answers").Select(answer=>
        {
            var qid=WText(answer,"questionId");var current=AssessmentJson.Object(request.Answers.GetValueOrDefault(qid)??new DiscoveryAnswer());
            var returned=ToDiscoveryAnswer(answer,"attributed workbook author",WText(receipt,"receivedBy"));
            var previous=request.Answers.GetValueOrDefault(qid)??new();
            var same=previous.Status==returned.Status&&previous.Text==returned.Text&&previous.Reference==returned.Reference;
            var kind=same?"unchanged":previous.Status=="unanswered"&&previous.Text.Length==0?"change":"conflict";
            return (JsonNode)new JsonObject{["questionId"]=qid,["current"]=current,["returned"]=AssessmentJson.Object(returned),["state"]=kind};
        }).ToArray());
        return view;
    }
    private static DiscoveryAnswer ToDiscoveryAnswer(JsonObject answer,string attributed,string principal)=>new()
    {Status=WText(answer,"status","unanswered"),Text=WText(answer,"text"),Reference=WText(answer,"reference"),AssertedBy=WText(answer,"attribution").Length>0?WText(answer,"attribution"):attributed,RecordedBy=principal};

    public JsonObject WorkspaceReceipt(string id,string receiptId,string principal)
    {
        lock(gate){var state=ReadAssessment(id,principal);WorkspaceStaff(state,principal);return ReceiptView(state,WorkspaceFind(state,"workspace_receipts",receiptId));}
    }

    public JsonObject WorkspaceCommand(string id,AssessmentCommand command,string principal)
    {
        lock(gate)
        {
            string? requestId=null;
            var state=WorkspaceCommit(id,command,principal,s=>
            {
                var fields=command.Fields;var effects=new List<(string Table,JsonObject Record)>();
                switch(command.Operation)
                {
                    case "workspace_review_evidence":
                    case "workspace_admit_evidence":
                        var bundle=WorkspaceFind(s,"workspace_bundles",command.TargetId??"");requestId=WText(bundle,"requestId");
                        effects.AddRange(WorkspaceEvidenceCommand(s,command,principal));break;
                    case "receipt_apply":
                    {
                        WClosed(fields,"choices","note");var receipt=WorkspaceFind(s,"workspace_receipts",command.TargetId??"");requestId=WText(receipt,"requestId");
                        var request=DiscoveryWorkflow.Request(s,requestId,principal);WorkspaceLead(s,principal);
                        if(WText(receipt,"status")!="staged")throw new DemoConflictException("workspace_receipt_already_applied");
                        var choices=fields["choices"] as JsonObject??new JsonObject();
                        if(choices.Any(c=>!request.Questions.Any(q=>q.Id==c.Key)||c.Value?.ToString() is not("current" or "returned")))throw new DemoValidationException("workspace_receipt_choice_invalid");
                        // Show current-vs-returned every time. A stale receipt cannot
                        // silently overwrite a subsequently edited web response.
                        var view=ReceiptView(s,receipt);
                        foreach(var comparison in Rows(view,"comparison"))
                        {
                            var qid=WText(comparison,"questionId");var choice=choices[qid]?.GetValue<string>();
                            if(WText(comparison,"state")=="conflict"&&choice is null)throw new DemoConflictException("workspace_receipt_conflict_unresolved");
                            if(choice=="current"||WText(comparison,"state")=="unchanged")continue;
                            var answer=Rows(receipt,"answers").Single(a=>WText(a,"questionId")==qid);
                            // Empty cells are no instruction to erase existing knowledge.
                            if(WText(answer,"status","unanswered")=="unanswered"&&WText(answer,"text").Length==0)continue;
                            request.Answers[qid]=ToDiscoveryAnswer(answer,WText(receipt,"respondent","Unverified workbook respondent"),principal);
                        }
                        var products=WorkspaceRows(s,"workspace_products",requestId).Where(p=>WText(p,"receiptId")==WText(receipt,"id")).ToArray();
                        foreach(var product in products)
                            if(!request.ProductRefs.Any(p=>p.Id==WText(product,"id")))request.ProductRefs.Add(new DiscoveryProductRef{Id=WText(product,"id"),Label=WText(product,"deployment",WText(product,"product")),Product=WText(product,"product"),Environment=WText(product,"environment"),RecordedBy=principal,RecordedAt=s.UpdatedAt});
                        if(request.Answers.Values.All(a=>a.Status=="unanswered"&&a.Text.Length==0)&&request.ProductRefs.Count==0)throw new DemoConflictException("workspace_useful_response_required");
                        request.Status="submitted";request.Submission=new(DateTimeOffset.UtcNow.ToString("O"),principal,AssessmentWorkflow.Hash(new{request.Answers,request.ProductRefs}));
                        request.Receipt="Offline response recorded by the coordinator. Respondent attribution is unverified; technical review and access approval remain separate.";
                        var source=s.Sources.Single(source=>source.FamilyId==request.FamilyId);
                        if(source.State=="unanswered")
                        {source.State="unknown";source.Note="An attributed operational questionnaire response was received. Source ownership, permitted access and completeness remain unconfirmed.";source.RespondedBy=principal;source.AssertedBy=WText(receipt,"respondent");}
                        receipt["status"]="applied";receipt["appliedBy"]=principal;receipt["appliedAt"]=DateTimeOffset.UtcNow.ToString("O");receipt["note"]=WField(fields,"note");
                        effects.Add(("workspace_receipts",receipt));break;
                    }
                    case "reconcile_product":
                    {
                        WClosed(fields,"productId","decision","canonicalId","label","applicationService","team","rationale");requestId=command.TargetId??"";
                        _=DiscoveryWorkflow.Request(s,requestId,principal);var product=WorkspaceFind(s,"workspace_products",WField(fields,"productId",160,true));
                        if(WText(product,"requestId")!=requestId)throw new DemoValidationException("workspace_product_scope_invalid");
                        var receipt=WorkspaceFind(s,"workspace_receipts",WText(product,"receiptId"));if(WText(receipt,"status")!="applied")throw new DemoConflictException("workspace_receipt_review_required");
                        var decision=WField(fields,"decision",32,true);if(decision is not("distinct" or "same_system" or "unresolved"))throw new DemoValidationException("workspace_identity_decision_invalid");
                        var identities=WorkspaceRows(s,"workspace_identities");var canonical=WField(fields,"canonicalId",160);
                        if(decision=="same_system"&&!identities.Any(i=>WText(i,"canonicalId")==canonical&&WText(i,"decision")!="unresolved"))throw new DemoValidationException("workspace_canonical_identity_unknown");
                        if(decision=="distinct")canonical="wsystem-"+AssessmentWorkflow.Hash(new{s.Id,productId=WText(product,"id")})[..24];
                        if(decision=="unresolved")canonical="";
                        var identity=new JsonObject{["id"]="widentity-"+WText(product,"id"),["requestId"]=requestId,["productId"]=WText(product,"id"),["decision"]=decision,["canonicalId"]=canonical,
                            ["label"]=WField(fields,"label",256,true),["applicationService"]=WField(fields,"applicationService",1024),["team"]=WField(fields,"team",1024),["rationale"]=WField(fields,"rationale",4096,true),["recordedBy"]=principal,["recordedAt"]=DateTimeOffset.UtcNow.ToString("O"),["basis"]="reviewed_attributed_identity_not_runtime_verification"};
                        effects.Add(("workspace_identities",identity));
                        effects.AddRange(WorkspaceInvalidateIdentityBinding(s,requestId,WText(product,"id"),canonical,principal));break;
                    }
                    case "record_consequence":
                    {
                        requestId=command.TargetId??"";var preview=BuildWorkspaceConsequence(s,command,principal);
                        if(WField(fields,"previewFingerprint",64,true)!=WText(preview,"previewFingerprint"))throw new DemoConflictException("workspace_preview_stale");
                        var consequence=(JsonObject)preview["consequence"]!.DeepClone();consequence["id"]="wconsequence-"+AssessmentWorkflow.Hash(new{requestId,productId=WText(consequence,"productId"),purpose=WText(consequence,"cryptographicPurpose")})[..24];consequence["status"]="recorded";
                        consequence["recordedBy"]=principal;consequence["recordedAt"]=DateTimeOffset.UtcNow.ToString("O");effects.Add(("workspace_consequences",consequence));break;
                    }
                    default:throw new DemoValidationException("workspace_operation_invalid");
                }
                return effects;
            });
            if(requestId is null)
                requestId=command.Operation=="receipt_apply"?WText(WorkspaceFind(state,"workspace_receipts",command.TargetId??""),"requestId"):
                    command.Operation is "workspace_review_evidence" or "workspace_admit_evidence"?WText(WorkspaceFind(state,"workspace_bundles",command.TargetId??""),"requestId"):command.TargetId;
            return new JsonObject{["assessmentId"]=id,["revision"]=state.Revision,["case"]=WorkspaceCase(state,requestId??"",principal),["effect"]="Decision recorded in immutable assessment history. No enterprise acceptance, source access or migration execution was authorized."};
        }
    }

    public JsonObject PreviewWorkspaceConsequence(string id,AssessmentCommand command,string principal)
    {
        lock(gate){var state=ReadAssessment(id,principal);WorkspaceStaff(state,principal);if(command.Operation!="record_consequence")throw new DemoValidationException("workspace_operation_invalid");if(state.Revision!=command.ExpectedRevision)throw new DemoConflictException("assessment_revision_changed");return BuildWorkspaceConsequence(state,command,principal);}
    }
    private JsonObject BuildWorkspaceConsequence(AssessmentState state,AssessmentCommand command,string principal)
    {
        if(AssessmentWorkflow.Role(state,principal) is not("assessment-lead" or "risk-lead"))throw new DemoValidationException("assessment_forbidden");
        var request=DiscoveryWorkflow.Request(state,command.TargetId,principal);var f=command.Fields;
        WClosed(f,"phase1Conclusion","limitation","nextDecision","responsibleFunction","phase2Consequence","lifetime","confidence","previewFingerprint","productId","cryptographicPurpose","supportingObservationIds","contradictingObservationIds");
        var confidence=WField(f,"confidence",24,true);if(confidence is not("unknown" or "limited" or "supported"))throw new DemoValidationException("workspace_confidence_invalid");
        var bundles=WorkspaceBundleRows(state,request.Id).Where(b=>WText(b,"status")=="admitted").ToArray();
        var admitted=bundles.SelectMany(b=>Rows(b,"observations")).ToArray();
        var available=admitted.Select(o=>WText(o,"id")).ToHashSet(StringComparer.Ordinal);
        string[] References(string key)
        {
            if(f[key] is null)return [];
            if(f[key] is not JsonArray a||a.Count>512||a.Any(n=>n is not JsonValue v||!v.TryGetValue<string>(out _)))throw new DemoValidationException("workspace_evidence_selection_invalid");
            var values=a.Select(n=>n!.GetValue<string>()).ToArray();
            if(values.Distinct().Count()!=values.Length||values.Any(x=>!available.Contains(x)))throw new DemoValidationException("workspace_evidence_selection_invalid");return values.Order(StringComparer.Ordinal).ToArray();
        }
        var supporting=References("supportingObservationIds");var contradicting=References("contradictingObservationIds");
        if(supporting.Intersect(contradicting,StringComparer.Ordinal).Any())throw new DemoValidationException("workspace_evidence_selection_invalid");
        var observationRefs=supporting.Concat(contradicting).Order(StringComparer.Ordinal).ToArray();
        var selectedProduct=WField(f,"productId",160);var purpose=WField(f,"cryptographicPurpose",40);
        if(purpose.Length>0&&purpose is not("key_establishment" or "authentication" or "data_protection" or "software_signing" or "context" or "unknown"))throw new DemoValidationException("workspace_use_purpose_invalid");
        if(selectedProduct.Length>0)
        {
            var product=WorkspaceFind(state,"workspace_products",selectedProduct);if(WText(product,"requestId")!=request.Id)throw new DemoValidationException("workspace_product_scope_invalid");
            var canonical=WorkspaceRows(state,"workspace_identities",request.Id).SingleOrDefault(i=>WText(i,"productId")==selectedProduct)?["canonicalId"]?.GetValue<string>()??"";
            if(admitted.Where(o=>observationRefs.Contains(WText(o,"id"))).Any(o=>WText(o,"productId")!=selectedProduct&&(canonical.Length==0||WText(o,"canonicalId")!=canonical)))throw new DemoValidationException("workspace_evidence_deployment_mismatch");
        }
        if(confidence=="supported"&&supporting.Length==0)throw new DemoConflictException("workspace_supporting_evidence_required");
        if(confidence=="supported"&&admitted.Any(o=>supporting.Contains(WText(o,"id"))&&WText(o,"technicalDetermination")=="cannot_establish"))throw new DemoConflictException("workspace_technical_determination_insufficient");
        var limitation=WField(f,"limitation",4096);
        if(observationRefs.Length==0&&limitation.Length==0)throw new DemoValidationException("workspace_no_evidence_limitation_required");
        var consequence=new JsonObject{["requestId"]=request.Id,["status"]="preview",["phase1Conclusion"]=WField(f,"phase1Conclusion",4096,true),["limitation"]=limitation,
            ["productId"]=selectedProduct,["cryptographicPurpose"]=purpose.Length>0?purpose:"unknown",["supportingObservationIds"]=new JsonArray(supporting.Select(x=>(JsonNode?)JsonValue.Create(x)).ToArray()),["contradictingObservationIds"]=new JsonArray(contradicting.Select(x=>(JsonNode?)JsonValue.Create(x)).ToArray()),
            ["nextDecision"]=WField(f,"nextDecision",4096,true),["responsibleFunction"]=WField(f,"responsibleFunction",1024,true),["phase2Consequence"]=WField(f,"phase2Consequence",4096),["lifetime"]=WField(f,"lifetime",1024),["confidence"]=confidence,
            ["evidenceRefs"]=new JsonArray(observationRefs.Select(x=>(JsonNode?)JsonValue.Create(x)).ToArray()),
            ["evidenceRevisionRefs"]=new JsonArray(admitted.Where(o=>observationRefs.Contains(WText(o,"id"))).Select(o=>(JsonNode)new JsonObject{["id"]=WText(o,"id"),["revision"]=o["revision"]?.DeepClone(),["bundleId"]=WText(o,"bundleId"),["artifactSha256"]=WText(o,"artifactSha256")}).ToArray()),
            ["reviewRevisionRefs"]=new JsonArray(WorkspaceRows(state,"workspace_technical_reviews",request.Id).Where(r=>admitted.Any(o=>observationRefs.Contains(WText(o,"id"))&&WText(o,"bundleId")==WText(r,"bundleId"))).Select(r=>(JsonNode)new JsonObject{["id"]=WText(r,"id"),["revision"]=r["revision"]?.DeepClone()}).ToArray()),
            ["inputAssessmentRevision"]=state.Revision,
            ["identityRefs"]=new JsonArray(WorkspaceRows(state,"workspace_identities",request.Id).Select(i=>(JsonNode?)JsonValue.Create(WText(i,"id"))).ToArray()),
            ["receiptRefs"]=new JsonArray(WorkspaceRows(state,"workspace_receipts",request.Id).Where(r=>WText(r,"status")=="applied").Select(r=>(JsonNode?)JsonValue.Create(WText(r,"id"))).ToArray()),
            ["authorityBoundary"]="Assessment interpretation for review. Phase 2 business consequence and lifetime are attributed input, not independently verified or business-risk accepted."};
        var fingerprint=AssessmentWorkflow.Hash(new{assessmentId=state.Id,state.Revision,requestId=request.Id,consequence,principal});
        return new JsonObject{["revision"]=state.Revision,["previewFingerprint"]=fingerprint,["consequence"]=consequence,["phase1Text"]=consequence["phase1Conclusion"]!.DeepClone(),["phase2Text"]=consequence["phase2Consequence"]!.DeepClone(),["limitations"]=new JsonArray(limitation),["nextDecision"]=consequence["nextDecision"]!.DeepClone()};
    }
}
