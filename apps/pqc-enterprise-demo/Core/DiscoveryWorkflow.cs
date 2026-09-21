using System.Text.Json;
using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

public static class DiscoveryWorkflow
{
    public const string TemplateVersion="pqc.discovery.v2";
    public const string Boundary="Synthetic source discovery, draft standards proposals and engineering research. A response helps identify information; it does not verify technical behavior, authorize access or complete the assessment. Proposals are not adopted policy; migration execution remains unavailable.";
    public static readonly DiscoveryGuidance Guidance=new(
        "Help us identify the software used for this function, the teams familiar with it, and any existing information we should start with. Product names, document references, referrals and not sure are useful answers.",
        "You do not need to create documents or demonstrate compliance. Do not submit credentials or sensitive files. Any later collection or system access will be agreed separately with the appropriate owner.",
        "A partial answer, referral or explicit unknown is enough to submit. The assessment team owns follow-up; submitting does not authorize access or complete the assessment.",
        "Your response has been received. The assessment team will review it and coordinate any follow-up. No further response is required now.",
        "This saved form retains its original questions. References to evidence mean existing information that may help the assessment; you do not need to produce documents, establish policy or authorize access.");
    public static DiscoveryGuidance GuidanceFor(string templateVersion)=>Guidance with{LegacyNotice=templateVersion==TemplateVersion?"":Guidance.LegacyNotice};
    public static bool Coordinate(AssessmentState s,string p)=>AssessmentWorkflow.Role(s,p)=="assessment-lead";
    public static bool Coordinator(AssessmentState s,string p)=>Coordinate(s,p);
    public static bool Research(AssessmentState s,string p)=>AssessmentWorkflow.Role(s,p) is "assessment-lead" or "technical-reviewer";
    public static List<DiscoveryQuestion> Questions(List<string> examples)=>[
        new("DQ-01","Which products or services in this software class do you know are used?","Identify a useful starting point; do not enumerate the whole enterprise.",[..examples],"A product name, one known deployment, a referral or 'I do not know' is useful."),
        new("DQ-02","Which team or contact should we speak with?","Route the next conversation without asking you to identify every ownership role.",[],"A team name, an existing contact route or 'not my team'."),
        new("DQ-03","Is there an existing inventory, configuration report or other reference we can start from?","Reuse existing information before asking anyone to produce a new inventory.",[],"Name or reference an existing record if known. Do not submit credentials or sensitive files."),
        new("DQ-04","Which application, business service or environment does your answer concern, if known?","Keep a partial answer attached to its actual scope; multiple products or deployments may be mentioned.",[],"One known service or environment is enough; optional product/deployment entries can keep them separate."),
        new("DQ-05","Are there any access restrictions, information-sharing considerations, or known gaps we should understand?","Understand known access, sharing or availability considerations without asking you to establish policy or resolve them.",[],"Share what you know. None known or not sure is sufficient; you do not need to establish policy or resolve the issue yourself.")];
    public static List<DiscoveryStandard> StandardTemplates()
    {
        List<DiscoveryStandard> standards=[
        new(){Id="assessment-evidence",Title="Assessment and evidence proposal",Purpose="Define a defensible assessment without making respondents design the evidence system.",ProposalText="PROPOSED — NOT ADOPTED\nScope: selected services, cryptographic uses, investigation depth and reporting cutoffs.\nEvidence: distinguish attributed statements, documentation/configuration, runtime observations and independent tests. Preserve source, custody reference, timestamp, scope and limitations.\nHandling: propose a minimal field allowlist; exclude credentials, private keys and unnecessary personal/customer data. Confirm applicable classification, retention and permitted environments before collection.\nQuality: keep source authority, conflicts, freshness, sampling and unknown populations explicit. Do not infer enterprise completeness from populated source families.\nReview: propose factual-review, limitation-disposition and report-reliance roles separately. Existing requirements and conflicts require explicit enterprise review. Acceptance of this proposal is not implemented here."},
        new(){Id="crypto-agility",Title="Crypto-agility design proposal",Purpose="Describe changeable cryptographic uses and compatibility obligations, not a single PQC-ready flag.",ProposalText="PROPOSED — NOT ADOPTED\nModel key establishment, authentication, data protection and software signing separately, with implementation/version and relying-party dependencies.\nRecord inventory evidence separately from claimed vendor capability, configured algorithms, negotiated behavior and independent verification.\nPropose algorithm/configuration separation, versioned compatibility profiles, dependency provenance and explicit legacy-data policies.\nEvaluate target options against applicable standards, enterprise requirements and exact-product support; do not prescribe one algorithm for every use.\nRequire representative interoperability and operational tests before proposing migration cohorts. Changes to policy or production cryptography require separate authorization; this draft grants neither."},
        new(){Id="migration-assurance",Title="Migration assurance proposal",Purpose="Define what a future migration would need to prove before execution and closure.",ProposalText="PROPOSED — NOT ADOPTED\nPrepare a versioned migration case with affected uses, alternatives, prerequisites, exact target cohort, business consequence and unsupported capabilities.\nBind future authorization to an immutable plan, scope, permitted operations and maintenance window. Ticket completion is not cryptographic verification.\nPropose bounded canaries, explicit fallback rejection, access/application compatibility checks and independently collected outcome evidence.\nUse rollback only where actually supported; otherwise require recovery or forward-remediation steps.\nPreserve failed attempts, exceptions and limitations. Close only against declared verification criteria, then rediscover for regression. Phase 3/4 execution and automated policy adoption remain unavailable."}
        ];
        standards[0].PublicationRefs=[new("NIST SP 800-30 Rev. 1 — Guide for Conducting Risk Assessments","https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-30r1.pdf","Final guidance"),new("NIST SP 800-53A Rev. 5 — Assessing Security and Privacy Controls in Information Systems and Organizations","https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-53Ar5.pdf","Final guidance")];
        standards[1].PublicationRefs=[new("NIST CSWP 39upd1 — Considerations for Achieving Crypto Agility","https://csrc.nist.gov/pubs/cswp/39/upd1/considerations-for-achieving-crypto-agility/final","Final guidance")];
        standards[2].PublicationRefs=[new("NIST IR 8547 — Transition to Post-Quantum Cryptography Standards","https://csrc.nist.gov/pubs/ir/8547/ipd","Initial Public Draft — not binding enterprise requirements")];
        return standards;
    }
    public static DiscoveryRequest Request(AssessmentState state,string? id,string principal,bool write=false)
    {
        _=AssessmentWorkflow.Role(state,principal);
        var request=state.Discovery.Requests.SingleOrDefault(r=>r.Id==id)??throw new DemoValidationException("discovery_request_not_found");
        if(IntakeWorkflow.Contributor(principal)&&request.AssignedTo!=principal || write&&!Coordinate(state,principal)&&request.AssignedTo!=principal)throw new DemoValidationException("assessment_forbidden");
        if(AssessmentWorkflow.Hash(request.Questions)!=request.TemplateSha256)throw new DemoStoreException("discovery_template_integrity_failed");
        return request;
    }
    public static DiscoveryInvestigation Investigation(AssessmentState state,string? id,string principal)
    {
        if(!Research(state,principal))throw new DemoValidationException("assessment_forbidden");
        return state.Discovery.Investigations.SingleOrDefault(i=>i.Id==id)??throw new DemoValidationException("discovery_investigation_not_found");
    }
    public static void EnsureEditable(DiscoveryRequest r){if(r.Status!="draft")throw new DemoConflictException("discovery_submitted_read_only");}
    public static string Text(JsonObject f,string key,int max=4096)=>QuestionnaireWorkflow.Text(f,key,max);
    private static string Required(JsonObject f,string key,int max=256){var v=Text(f,key,max);if(string.IsNullOrWhiteSpace(v))throw new DemoValidationException("discovery_field_required");return v;}
    private static void Allowed(JsonObject f,params string[] keys){if(f.Any(p=>!keys.Contains(p.Key,StringComparer.Ordinal)))throw new DemoValidationException("discovery_fields_invalid");}
    public static DiscoveryValidation Validate(DiscoveryRequest r)
    {
        var useful=r.Answers.Values.Any(a=>a.Status is "unknown" or "not_my_team" or "referral" or "not_applicable" || !string.IsNullOrWhiteSpace(a.Text)||!string.IsNullOrWhiteSpace(a.Reference))||r.ProductRefs.Count>0;
        return new(useful,useful?[]:["Provide one useful answer, referral or explicit unknown before submitting. The other questions may remain unanswered."]);
    }
    public static DiscoveryAnswer MergeAnswer(DiscoveryRequest request,string id,JsonObject f,string principal,bool coordinator)
    {
        if(!request.Questions.Any(q=>q.Id==id))throw new DemoValidationException("discovery_question_not_found");
        Allowed(f,"status","text","reference","assertedBy");
        var previous=request.Answers.GetValueOrDefault(id)??new();
        var answer=JsonSerializer.Deserialize<DiscoveryAnswer>(JsonSerializer.Serialize(previous,AssessmentJson.Options),AssessmentJson.Options)!;
        foreach(var field in f)
        {
            var value=Text(f,field.Key,field.Key=="reference"?1024:4096);
            switch(field.Key)
            {
                case "status":if(value is not("unanswered" or "answered" or "unknown" or "blocked" or "disputed" or "not_my_team" or "referral" or "not_applicable"))throw new DemoValidationException("discovery_status_invalid");answer.Status=value;break;
                case "text":answer.Text=value;break;case "reference":answer.Reference=value;break;
                case "assertedBy":if(!coordinator&&value.Length>0&&value!=principal&&value!=previous.AssertedBy)throw new DemoValidationException("discovery_attribution_forbidden");answer.AssertedBy=value;break;
            }
        }
        if(AssessmentWorkflow.Hash(answer)==AssessmentWorkflow.Hash(previous))return answer;
        answer.RecordedBy=principal;if(!coordinator||string.IsNullOrWhiteSpace(answer.AssertedBy))answer.AssertedBy=principal;return answer;
    }
    public static void Authorize(AssessmentState s,AssessmentCommand c,string p)
    {
        var role=AssessmentWorkflow.Role(s,p);
        if(c.Operation is "discovery_create" or "discovery_update_standard" or "discovery_create_investigation" or "discovery_collection_create" or "discovery_collection_export")
        {if(!Coordinate(s,p))throw new DemoValidationException("assessment_forbidden");return;}
        if(c.Operation is "discovery_update_investigation" or "discovery_add_product" or "discovery_stage_evidence" or "discovery_review_evidence" or "discovery_admit_evidence")
        {
            var investigation=Investigation(s,c.TargetId,p);
            if(c.Operation=="discovery_review_evidence"?role!="technical-reviewer":c.Operation=="discovery_update_investigation"?!Coordinate(s,p)&&investigation.AssignedTo!=p:!Coordinate(s,p))throw new DemoValidationException("assessment_forbidden");
            return;
        }
        _=Request(s,c.TargetId,p,true);
        if(c.Operation=="discovery_reopen"&&!Coordinate(s,p))throw new DemoValidationException("assessment_forbidden");
    }
    public static void Apply(AssessmentState s,AssessmentCommand c,string p)
    {
        var f=c.Fields;
        if(c.Operation is "discovery_review_evidence" or "discovery_admit_evidence"){DiscoveryEvidence.Apply(s,c,p);return;}
        if(c.Operation=="discovery_create")
        {
            AssessmentWorkflow.Closed(f,"title","familyId","assignedTo");if(s.Discovery.Requests.Count>=100)throw new DemoConflictException("discovery_request_limit");
            var family=s.Sources.SingleOrDefault(v=>v.FamilyId==Required(f,"familyId"))??throw new DemoValidationException("discovery_family_not_found");
            var assigned=Required(f,"assignedTo");if(!IntakeWorkflow.Contributor(assigned)||!s.Assignments.Any(a=>a.PrincipalId==assigned))throw new DemoValidationException("discovery_recipient_invalid");
            var questions=Questions(family.Examples);var id="discovery-"+AssessmentWorkflow.Hash(new{assessmentId=s.Id,s.Revision,c.IdempotencyKey})[..24];
            s.Discovery.Requests.Add(new(){Id=id,Title=Required(f,"title"),FamilyId=family.FamilyId,FamilyName=family.Name,TemplateVersion=TemplateVersion,Questions=questions,TemplateSha256=AssessmentWorkflow.Hash(questions),Examples=[..family.Examples],AssignedTo=assigned,Answers=questions.ToDictionary(q=>q.Id,_=>new DiscoveryAnswer(),StringComparer.Ordinal),Receipt="Five-question discovery request created, not sent. A useful partial response is enough."});return;
        }
        if(c.Operation=="discovery_update_standard")
        {
            var standard=s.Discovery.Standards.SingleOrDefault(v=>v.Id==c.TargetId)??throw new DemoValidationException("discovery_standard_not_found");
            Allowed(f,"proposalText","observedPractice","existingRequirementStatus","existingRequirementRefs","authorityStatus","proposedAuthority","conflictReviewStatus","conflictNote");
            foreach(var field in f)
            {
                if(field.Key=="existingRequirementRefs"){standard.ExistingRequirementRefs=References(f,field.Key);continue;}
                var text=Text(f,field.Key,field.Key=="proposalText"?16384:4096);
                switch(field.Key)
                {
                    case "proposalText":standard.ProposalText=text;break;
                    case "observedPractice":standard.ObservedPractice=text;break;
                    case "existingRequirementStatus":if(text is not("unassessed" or "reported_existing" or "not_identified" or "conflict_reported"))throw new DemoValidationException("discovery_status_invalid");standard.ExistingRequirementStatus=text;break;
                    case "authorityStatus":if(text is not("unassigned" or "proposed_owner" or "review_requested"))throw new DemoValidationException("discovery_status_invalid");standard.AuthorityStatus=text;break;
                    case "proposedAuthority":standard.ProposedAuthority=text;break;
                    case "conflictReviewStatus":if(text is not("unassessed" or "no_conflict_reported" or "conflict_reported"))throw new DemoValidationException("discovery_status_invalid");standard.ConflictReviewStatus=text;break;
                    case "conflictNote":standard.ConflictNote=text;break;
                }
            }
            standard.Revision=s.Revision+1;standard.RecordedBy=p;standard.RecordedAt=DateTimeOffset.UtcNow.ToString("O");return;
        }
        if(c.Operation=="discovery_create_investigation")
        {
            AssessmentWorkflow.Closed(f,"purpose","assignedTo","productRefIds");var request=Request(s,c.TargetId,p);if(s.Discovery.Investigations.Count>=100)throw new DemoConflictException("discovery_investigation_limit");
            var assigned=Required(f,"assignedTo");if(!Research(s,assigned))throw new DemoValidationException("discovery_investigator_invalid");
            var refs=References(f,"productRefIds");if(refs.Any(id=>!request.ProductRefs.Any(r=>r.Id==id)))throw new DemoValidationException("discovery_product_ref_invalid");
            var products=JsonSerializer.Deserialize<List<DiscoveryProductRef>>(JsonSerializer.Serialize(request.ProductRefs.Where(product=>refs.Contains(product.Id)),AssessmentJson.Options),AssessmentJson.Options)!;
            s.Discovery.Investigations.Add(new(){Id="investigation-"+AssessmentWorkflow.Hash(new{assessmentId=s.Id,s.Revision,c.IdempotencyKey})[..24],RequestId=request.Id,FamilyId=request.FamilyId,ProductRefIds=refs,ProductRefs=products,AssignedTo=assigned,Purpose=Required(f,"purpose",4096),Revision=s.Revision+1,RecordedBy=p,RecordedAt=DateTimeOffset.UtcNow.ToString("O")});return;
        }
        if(c.Operation=="discovery_add_product")
        {
            var investigation=Investigation(s,c.TargetId,p);AssessmentWorkflow.Closed(f,"label","product","environment");
            if(investigation.ProductRefs.Count>=20)throw new DemoConflictException("discovery_product_limit");
            var product=new DiscoveryProductRef{Id="product-"+AssessmentWorkflow.Hash(new{investigationId=investigation.Id,s.Revision,c.IdempotencyKey})[..24],Label=Required(f,"label"),Product=Text(f,"product",256),Environment=Text(f,"environment",256),RecordedBy=p,RecordedAt=DateTimeOffset.UtcNow.ToString("O")};
            investigation.ProductRefs.Add(product);investigation.ProductRefIds.Add(product.Id);
            investigation.Revision=s.Revision+1;investigation.RecordedBy=p;investigation.RecordedAt=product.RecordedAt;return;
        }
        if(c.Operation=="discovery_update_investigation")
        {
            var investigation=Investigation(s,c.TargetId,p);Allowed(f,"status","researchSummary","proposedMethod","documentationRefs","limitation");
            foreach(var field in f)
            {
                if(field.Key=="documentationRefs"){investigation.DocumentationRefs=References(f,field.Key);continue;}
                var text=Text(f,field.Key);
                switch(field.Key){case "status":if(text is not("planned" or "researching" or "ready_for_review" or "blocked"))throw new DemoValidationException("discovery_status_invalid");investigation.Status=text;break;case "researchSummary":investigation.ResearchSummary=text;break;case "proposedMethod":investigation.ProposedMethod=text;break;case "limitation":investigation.Limitation=text;break;}
            }
            investigation.Revision=s.Revision+1;investigation.RecordedBy=p;investigation.RecordedAt=DateTimeOffset.UtcNow.ToString("O");return;
        }
        var r=Request(s,c.TargetId,p,true);
        switch(c.Operation)
        {
            case "discovery_save":
                EnsureEditable(r);Allowed(f,"answers","productRefs");
                if(f.ContainsKey("answers"))
                {
                    if(f["answers"] is not JsonObject answers||answers.Count>5)throw new DemoValidationException("discovery_answers_invalid");
                    foreach(var a in answers)r.Answers[a.Key]=MergeAnswer(r,a.Key,a.Value as JsonObject??throw new DemoValidationException("discovery_answers_invalid"),p,Coordinate(s,p));
                }
                if(f.ContainsKey("productRefs"))UpdateProducts(s,r,f["productRefs"],p);
                r.Receipt="Draft saved. Submit when you have a useful partial response; there is no obligation to answer every question.";break;
            case "discovery_submit":
                EnsureEditable(r);AssessmentWorkflow.Closed(f);if(!Validate(r).CanSubmit)throw new DemoConflictException("discovery_response_empty");
                r.Status="submitted";r.Submission=new(DateTimeOffset.UtcNow.ToString("O"),p,AssessmentWorkflow.Hash(new{r.TemplateSha256,r.Answers,r.ProductRefs}));
                r.Receipt=Guidance.SubmissionReceipt;break;
            case "discovery_reopen":
                AssessmentWorkflow.Closed(f,"reason");var reason=Required(f,"reason",4096);
                r.History.Add(new(c.Operation,s.Revision+1,p,DateTimeOffset.UtcNow.ToString("O"),reason,r.Submission?.ContentSha256));r.Status="draft";r.Submission=null;r.Receipt="A correction draft is open; the earlier submitted response remains in immutable history.";break;
            default:throw new DemoValidationException("discovery_operation_invalid");
        }
    }
    private static List<string> References(JsonObject f,string key)
    {
        if(f[key] is not JsonArray values||values.Count>32)throw new DemoValidationException("discovery_references_invalid");
        return values.Select(v=>v is JsonValue n&&n.TryGetValue<string>(out var text)&&!string.IsNullOrWhiteSpace(text)&&text.Length<=1024&&!text.Any(char.IsControl)?text:throw new DemoValidationException("discovery_references_invalid")).Distinct(StringComparer.Ordinal).ToList();
    }
    private static void UpdateProducts(AssessmentState s,DiscoveryRequest r,JsonNode? value,string principal)
    {
        if(value is not JsonArray values||values.Count>20)throw new DemoValidationException("discovery_products_invalid");
        var next=new List<DiscoveryProductRef>();
        foreach(var node in values)
        {
            var f=node as JsonObject??throw new DemoValidationException("discovery_products_invalid");AssessmentWorkflow.Closed(f,"id","label","product","environment");var id=Text(f,"id",160);
            if(id.Length==0)id="product-"+AssessmentWorkflow.Hash(new{requestId=r.Id,s.Revision,index=next.Count})[..24];
            else if(!r.ProductRefs.Any(p=>p.Id==id))throw new DemoValidationException("discovery_product_ref_invalid");
            if(next.Any(p=>p.Id==id))throw new DemoValidationException("discovery_product_ref_invalid");
            var previous=r.ProductRefs.SingleOrDefault(p=>p.Id==id);
            var product=new DiscoveryProductRef{Id=id,Label=Required(f,"label"),Product=Text(f,"product",256),Environment=Text(f,"environment",256)};
            var unchanged=previous is not null&&previous.Label==product.Label&&previous.Product==product.Product&&previous.Environment==product.Environment;
            product.RecordedBy=unchanged?previous!.RecordedBy:principal;product.RecordedAt=unchanged?previous!.RecordedAt:DateTimeOffset.UtcNow.ToString("O");next.Add(product);
        }
        foreach(var id in s.Discovery.Investigations.Where(i=>i.RequestId==r.Id).SelectMany(i=>i.ProductRefIds).Distinct().Where(id=>r.ProductRefs.Any(product=>product.Id==id)))
            if(!next.Any(p=>p.Id==id)||AssessmentWorkflow.Hash(next.Single(p=>p.Id==id))!=AssessmentWorkflow.Hash(r.ProductRefs.Single(p=>p.Id==id)))throw new DemoConflictException("discovery_investigated_product_immutable");
        r.ProductRefs=next;
    }
    public static JsonObject Detail(AssessmentState s,string id,string p)
    {
        var request=Request(s,id,p);var coordinator=Coordinate(s,p);
        return AssessmentJson.Object(new{assessmentId=s.Id,assessmentName=s.Name,revision=s.Revision,request,guidance=GuidanceFor(request.TemplateVersion),recognition=DiscoveryRecognition.ForFamily(request.FamilyId),canEdit=request.Status=="draft"&&(coordinator||request.AssignedTo==p),canCoordinate=coordinator,validation=Validate(request),boundary=Boundary});
    }
}
