using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

/// <summary>Pure synthetic assessment command evaluator. It cannot write state,
/// collect evidence, grant production authority, or record owner acceptance.</summary>
public static class AssessmentWorkflow
{
    public const string Identity = "pqc_enterprise_assessment@0.1.0";
    public static readonly AssessmentPersona[] Personas =
    [
        new("synthetic-demo:analyst", "assessment-lead", "Assessment lead"),
        new("synthetic-demo:contributor", "contributor", "Source contributor"),
        new("synthetic-demo:contributor-two", "contributor", "Second source contributor"),
        new("synthetic-demo:reviewer", "technical-reviewer", "Technical reviewer"),
        new("synthetic-demo:sponsor", "sponsor", "Engagement sponsor"),
        new("synthetic-demo:information-owner", "information-owner", "Information owner"),
        new("synthetic-demo:risk-lead", "risk-lead", "Risk lead"),
        new("synthetic-demo:business-reviewer", "business-reviewer", "Business reviewer"),
        new("synthetic-demo:viewer", "viewer", "Read-only viewer")
    ];
    public static readonly AssessmentStage[] Stages =
    [
        new(1,"Establish the assessment","What are we assessing, and under whose authority?"),
        new(2,"Establish sources and obtain evidence","Which systems and functions can supply the facts?"),
        new(3,"Validate the enterprise map","Which observations and conclusions can we rely upon?"),
        new(4,"Deliver Phase 1","Is this exact current-state report fit for the next phase?"),
        new(5,"Establish the analysis basis","Which accepted input and method govern the analysis?"),
        new(6,"Assess consequences and recommend action","Why does the condition matter, and what should happen next?"),
        new(7,"Deliver Phase 2","Is this exact risk review justified and actionable?")
    ];
    public static readonly string[] Depths = ["routing", "inventory", "dependency_cohort"];

    public static List<AssessmentGate> NewGates() =>
    [
        Gate("PQC-G00", "Governance and information handling", 1, "sponsor", "information-owner"),
        Gate("PQC-P1-G01", "Scope and source readiness", 2, "assessment-lead", "sponsor"),
        Gate("PQC-P1-G02", "Baseline validation", 3, "assessment-lead", "technical-reviewer"),
        Gate("PQC-P1-G03", "Phase 1 deliverable acceptance", 4, "assessment-lead", "sponsor"),
        Gate("PQC-P2-G01", "Phase 2 method and input readiness", 5, "risk-lead", "sponsor"),
        Gate("PQC-P2-G02", "Analysis validation", 6, "risk-lead", "business-reviewer"),
        Gate("PQC-P2-G03", "Phase 2 deliverable acceptance", 7, "risk-lead", "sponsor")
    ];

    private static AssessmentGate Gate(string id, string name, int stage, params string[] roles) => new() { Id=id, Name=name, Stage=stage, RequiredRoles=[.. roles] };
    public static bool Accepted(string state) => state is "accepted" or "qualified";
    public static string Hash<T>(T value) => Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(JsonSerializer.Serialize(value, AssessmentJson.Options))));
    public static string Role(AssessmentState state, string principal) => state.Assignments.SingleOrDefault(p => p.PrincipalId == principal)?.Role ?? throw new DemoValidationException("assessment_forbidden");
    public static void KnownPrincipal(string principal)
    {
        if (!Personas.Any(p => p.PrincipalId == principal)) throw new DemoValidationException("assessment_forbidden");
    }

    public static void Apply(AssessmentState state, AssessmentCommand command, string principal, string now,
        EvidenceSample? sample = null, string origin = "user_entered_synthetic")
    {
        if(state.ScenarioVersion is not null)origin="scenario_generated";
        Refresh(state, principal);
        var role = Role(state, principal);
        if (!Operations(role).Contains(command.Operation, StringComparer.Ordinal)) throw new DemoValidationException("assessment_forbidden");
        if (state.Revision != command.ExpectedRevision) throw new DemoConflictException("assessment_revision_changed");
        if (state.Events.Count >= 2000) throw new DemoConflictException("assessment_event_limit");
        switch (command.Operation)
        {
            case "update_scope":
                Closed(command.Fields, "objective", "handling", "method", "cycleGoal", "reviewDate", "includedFamilyIds", "excludedReasons", "depthByFamily");
                var included = List(command.Fields, "includedFamilyIds");
                if (included.Count == 0 || included.Any(id => !state.Sources.Any(s => s.FamilyId == id))) Invalid("assessment_scope_family_invalid");
                var exclusions = Map(command.Fields, "excludedReasons");
                var depths = Map(command.Fields, "depthByFamily");
                if (exclusions.Keys.Any(id => !state.Sources.Any(s=>s.FamilyId==id) || included.Contains(id)) ||
                    state.Sources.Where(s=>!included.Contains(s.FamilyId)).Any(s=>!exclusions.TryGetValue(s.FamilyId,out var reason) || string.IsNullOrWhiteSpace(reason)) ||
                    depths.Keys.Any(id=>!included.Contains(id)) || included.Any(id=>!depths.TryGetValue(id,out var depth) || !Depths.Contains(depth))) Invalid("assessment_scope_depth_or_exclusion_required");
                var scope = new AssessmentScope { Objective=Required(command.Fields,"objective"), Handling=Required(command.Fields,"handling"),
                    Method=Required(command.Fields,"method"), CycleGoal=Required(command.Fields,"cycleGoal"), ReviewDate=Date(command.Fields,"reviewDate"),
                    IncludedFamilyIds=included.Order(StringComparer.Ordinal).ToList(), ExcludedReasons=exclusions, DepthByFamily=depths, Revision=state.Scope.Revision };
                if(Hash(scope)!=Hash(state.Scope)){scope.Revision++;state.Scope=scope;}
                break;
            case "source_response":
                Closed(command.Fields,"state","systemOfRecord","product","ownerFunction","accessRoute","note","dueAt","assertedBy");
                var source = Source(state,command.TargetId);
                var previousSource=SourceBinding(source);
                var response = Choice(command.Fields,"state","route_confirmed","unknown","not_my_team","blocked");
                source.State=response; source.SystemOfRecord=Text(command.Fields,"systemOfRecord"); source.Product=Text(command.Fields,"product");
                source.OwnerFunction=Text(command.Fields,"ownerFunction"); source.AccessRoute=Text(command.Fields,"accessRoute");
                source.Note=Required(command.Fields,"note"); source.DueAt=Date(command.Fields,"dueAt"); source.RespondedBy=principal; source.AssertedBy=Required(command.Fields,"assertedBy"); source.UpdatedAt=now;
                if (response=="route_confirmed" && new[]{source.SystemOfRecord,source.Product,source.OwnerFunction,source.AccessRoute}.Any(string.IsNullOrWhiteSpace)) Invalid("confirmed_route_details_required");
                if(previousSource!=SourceBinding(source))ResetPackage(Package(state,source.FamilyId));
                break;
            case "admit_sample":
                Closed(command.Fields);
                NeedGate(state,"PQC-G00"); NeedGate(state,"PQC-P1-G01");
                source=Source(state,command.TargetId);
                if (source.State!="route_confirmed" || sample is null || sample.FamilyId!=source.FamilyId || sample.ObservationIds.Count==0) Invalid("approved_sample_route_required");
                if(source.ObservationIds.SequenceEqual(sample.ObservationIds) && source.SubjectIds.SequenceEqual(sample.SubjectIds))break;
                source.ObservationIds=[..sample.ObservationIds]; source.SubjectIds=[..sample.SubjectIds]; source.EvidenceOrigin="fixed_synthetic_fixture";
                var package=Package(state,source.FamilyId); ResetPackage(package);
                package.ObservationIds=[..sample.ObservationIds]; package.SubjectIds=[..sample.SubjectIds]; package.EvidenceCount=sample.ObservationIds.Count; package.SubjectCount=sample.SubjectIds.Count;
                package.LimitationCodes=[..sample.LimitationCodes]; package.State="in_progress";
                break;
            case "submit_package":
                Closed(command.Fields,"conclusion","qualification");
                NeedGate(state,"PQC-G00"); NeedGate(state,"PQC-P1-G01");
                package=Package(state,command.TargetId);
                package.Conclusion=Required(command.Fields,"conclusion"); package.Qualification=Text(command.Fields,"qualification");
                if (package.EvidenceCount==0 && string.IsNullOrWhiteSpace(package.Qualification)) Invalid("no_evidence_qualification_required");
                package.State="submitted"; package.SubmittedBy=principal; package.ReviewedBy=""; package.Revision++;
                break;
            case "review_package":
                Closed(command.Fields,"decision","rationale","qualification","reviewDate");
                package=Package(state,command.TargetId);
                if (package.State!="submitted") Conflict("package_submission_required");
                if (package.SubmittedBy==principal) Invalid("independent_package_reviewer_required");
                var decision=Choice(command.Fields,"decision","accepted","qualified","changes_requested");
                var qualification=Text(command.Fields,"qualification");
                if (decision=="accepted" && (package.EvidenceCount==0 || package.LimitationCodes.Count>0 || package.Qualification.Length>0 || package.DepthLimitation.Length>0)) Invalid("evidence_limitations_require_qualification");
                if (decision=="qualified" && qualification.Length==0) Invalid("qualification_required");
                package.State=decision; package.ReviewedBy=principal; package.ReviewRationale=Required(command.Fields,"rationale");
                package.Qualification=qualification.Length>0 ? qualification : package.Qualification; package.ReviewDate=Date(command.Fields,"reviewDate");
                break;
            case "set_method":
                Closed(command.Fields,"name","description","confidenceRules","prioritizationRules");
                var method=new AssessmentMethod { Name=Required(command.Fields,"name"),Description=Required(command.Fields,"description"),
                    ConfidenceRules=Required(command.Fields,"confidenceRules"),PrioritizationRules=Required(command.Fields,"prioritizationRules"), Revision=state.Method.Revision };
                if(Hash(method)!=Hash(state.Method)){method.Revision++;state.Method=method;}
                break;
            case "submit_analysis":
                Closed(command.Fields,"scenario","businessImpact","recommendation","priority","rationale","confidence",
                    "protectedInformation","lifetime","assertedBy","statementDate","compatibilityConstraints","vendorConstraints","operationalConstraints","responsibleFunction","nextDecision");
                package=Package(state,command.TargetId);
                string? BusinessText(string key) { var value=Text(command.Fields,key); return value.Length==0?null:value; }
                var statementDate=BusinessText("statementDate");
                if(statementDate is not null) _=Date(command.Fields,"statementDate");
                if(new[]{"protectedInformation","lifetime","compatibilityConstraints","vendorConstraints","operationalConstraints","responsibleFunction","nextDecision"}.Any(key=>BusinessText(key) is not null)
                    && (BusinessText("assertedBy") is null || statementDate is null)) Invalid("business_statement_attribution_required");
                package.Analysis=new AssessmentAnalysis { Scenario=Required(command.Fields,"scenario"),BusinessImpact=Required(command.Fields,"businessImpact"),
                    Recommendation=Required(command.Fields,"recommendation"),Priority=Choice(command.Fields,"priority","prioritize_review","planned_review","defer"),
                    Rationale=Required(command.Fields,"rationale"),Confidence=Choice(command.Fields,"confidence","unknown","limited","supported"),
                    ProtectedInformation=BusinessText("protectedInformation"),Lifetime=BusinessText("lifetime"),AssertedBy=BusinessText("assertedBy"),StatementDate=statementDate,
                    CompatibilityConstraints=BusinessText("compatibilityConstraints"),VendorConstraints=BusinessText("vendorConstraints"),OperationalConstraints=BusinessText("operationalConstraints"),
                    ResponsibleFunction=BusinessText("responsibleFunction"),NextDecision=BusinessText("nextDecision"),
                    State="submitted",SubmittedBy=principal };
                if (package.Analysis.Confidence=="supported" && (package.EvidenceCount==0 || package.LimitationCodes.Count>0)) Invalid("supported_analysis_requires_unqualified_evidence");
                break;
            case "review_analysis":
                Closed(command.Fields,"decision","rationale","qualification","reviewDate");
                package=Package(state,command.TargetId);
                if (package.Analysis.State!="submitted") Conflict("analysis_submission_required");
                if (package.Analysis.SubmittedBy==principal) Invalid("independent_analysis_reviewer_required");
                decision=Choice(command.Fields,"decision","accepted","qualified","changes_requested");
                qualification=Text(command.Fields,"qualification");
                if (decision=="qualified" && qualification.Length==0) Invalid("qualification_required");
                if (decision=="accepted" && (package.EvidenceCount==0 || package.Analysis.Confidence!="supported")) Invalid("analysis_limitations_require_qualification");
                package.Analysis.State=decision; package.Analysis.ReviewedBy=principal; package.Analysis.Qualification=qualification;
                package.Analysis.Rationale += " Review: " + Required(command.Fields,"rationale"); package.Analysis.ReviewDate=Date(command.Fields,"reviewDate");
                break;
            case "submit_gate":
                var gate=FindGate(state,command.TargetId);
                if (gate.Stage>=5 && role!="risk-lead" || gate.Stage<5 && role!="assessment-lead") Invalid("assessment_forbidden");
                if (gate.Id.EndsWith("G03",StringComparison.Ordinal))
                {
                    Closed(command.Fields,"reportId"); gate.DocumentId=Required(command.Fields,"reportId");
                    var phase=gate.Stage==4?"phase1":"phase2";
                    if (!state.Documents.Any(d=>d.Id==gate.DocumentId && d.Phase==phase)) Invalid("assessment_report_not_found");
                }
                else Closed(command.Fields);
                Refresh(state,principal);
                if (gate.Requirements.Any(r=>!r.Satisfied)) Conflict("gate_requirements_outstanding");
                var fingerprint=GateFingerprint(state,gate);
                if (gate.State=="rejected" && gate.Fingerprint==fingerprint) Conflict("rejected_submission_requires_revision");
                if (gate.State=="submitted" || Accepted(gate.State)) Conflict("gate_already_submitted");
                gate.State="submitted"; gate.SubmittedBy=principal; gate.SubmissionRevision=state.Revision+1; gate.Fingerprint=fingerprint;
                break;
            case "decide_gate":
                Closed(command.Fields,"decision","rationale","qualification","reviewDate");
                gate=FindGate(state,command.TargetId);
                if (!gate.RequiredRoles.Contains(role)) Invalid("assessment_forbidden");
                if (gate.State!="submitted" || gate.Fingerprint!=GateFingerprint(state,gate)) Conflict("current_gate_submission_required");
                if (gate.Decisions.Any(d=>d.Fingerprint==gate.Fingerprint && d.Role==role)) Conflict("gate_role_already_decided");
                decision=Choice(command.Fields,"decision","accepted","qualified","rejected"); qualification=Text(command.Fields,"qualification");
                if (decision=="qualified" && qualification.Length==0) Invalid("qualification_required");
                gate.Decisions.Add(new AssessmentGateDecision { Id="decision-"+Guid.NewGuid().ToString("N"),PrincipalId=principal,Role=role,Decision=decision,
                    Rationale=Required(command.Fields,"rationale"),Qualification=qualification,ReviewDate=Date(command.Fields,"reviewDate"),CreatedAt=now,Fingerprint=gate.Fingerprint,Origin=origin });
                var current=gate.Decisions.Where(d=>d.Fingerprint==gate.Fingerprint).ToArray();
                gate.State=current.Any(d=>d.Decision=="rejected")?"rejected":gate.RequiredRoles.All(r=>current.Any(d=>d.Role==r)) && current.Select(d=>d.PrincipalId).Distinct().Count()==gate.RequiredRoles.Count
                    ? current.Any(d=>d.Decision=="qualified")?"qualified":"accepted":"submitted";
                if (gate.Id=="PQC-P1-G03" && Accepted(gate.State)) state.Phase1InputReportId=gate.DocumentId;
                break;
            default: Invalid("unknown_assessment_operation"); break;
        }
        state.Revision++; state.UpdatedAt=now;
        state.Events.Add(new AssessmentEvent(state.Revision,command.Operation,command.TargetId,principal,now,origin));
        Refresh(state,principal);
    }

    public static void Refresh(AssessmentState state,string principal)
    {
        _=Role(state,principal);
        var sources=state.Sources.Where(s=>state.Scope.IncludedFamilyIds.Contains(s.FamilyId)).ToArray();
        foreach(var source in sources)
        {
            var package=Package(state,source.FamilyId);
            package.PlannedDepth=state.Scope.DepthByFamily.GetValueOrDefault(source.FamilyId,"routing");
            package.AchievedDepth=package.EvidenceCount>0?"inventory":source.State=="route_confirmed"?"routing":"not_established";
            package.DepthLimitation=package.PlannedDepth=="dependency_cohort"?"Dependency-cohort investigation is planned but unvalidated: this increment admits fixed family samples, not a user-selected service cohort."
                :package.PlannedDepth=="inventory" && package.EvidenceCount==0?"Inventory depth is planned; no technical evidence has been admitted.":"";
        }
        foreach (var gate in state.Gates)
        {
            gate.Requirements=Requirements(state,gate);
            if (gate.State is "submitted" or "accepted" or "qualified" && (gate.Fingerprint!=GateFingerprint(state,gate) || gate.Requirements.Any(r=>!r.Satisfied))) gate.State="needs_review";
        }
        foreach (var doc in state.Documents)
        {
            var gate=state.Gates.Single(g=>g.Id==(doc.Phase=="phase1"?"PQC-P1-G03":"PQC-P2-G03"));
            doc.Status=gate.DocumentId==doc.Id && Accepted(gate.State)?gate.State:doc.InputFingerprint==ReportFingerprint(state,doc.Phase,doc.Phase1ReportId)?"draft":"superseded_inputs";
        }
        state.Stage=state.Gates.FirstOrDefault(g=>!Accepted(g.State))?.Stage ?? 7;
        state.AvailableOperations=[..Operations(Role(state,principal))];
        state.Questions=sources.SelectMany(s=>new[]
        {
            new AssessmentQuestion("question-route-"+s.FamilyId,"What is the authoritative source for "+s.Name+"?","It establishes the route, responsible function and handling boundary—not observed cryptography.",
                "An attributable route answer or an explicit route limitation.",s.State=="route_confirmed"?"supported":s.State=="unanswered"?"unanswered":"qualified",s.FamilyId),
            new AssessmentQuestion("question-evidence-"+s.FamilyId,"What does the admitted "+s.Name+" evidence establish?","It bounds the cryptographic facts and dependencies this assessment may describe.",
                "Review source observations and retain each material limitation; this does not prove unobserved runtime behavior.",
                Accepted(Package(state,s.FamilyId).State)?Package(state,s.FamilyId).State=="accepted" && Package(state,s.FamilyId).EvidenceCount>0?"supported":"qualified":"unanswered",s.FamilyId)
        }).ToList();
        state.NextActions=[];
        foreach(var source in state.Sources.Where(s=>state.Scope.IncludedFamilyIds.Contains(s.FamilyId)))
        {
            var package=Package(state,source.FamilyId);
            if(source.State=="unanswered" && state.AvailableOperations.Contains("source_response")) state.NextActions.Add(new("Identify the source and owner for "+source.Name,"source_response",source.FamilyId,2));
            else if(source.State is "blocked" or "unknown" or "not_my_team" && state.AvailableOperations.Contains("source_response")) state.NextActions.Add(new("Resolve or escalate the source route for "+source.Name,"source_response",source.FamilyId,2));
            else if(source.State=="route_confirmed" && source.ObservationIds.Count==0 && state.AvailableOperations.Contains("admit_sample") && Passed(state,"PQC-P1-G01")) state.NextActions.Add(new("Admit the bounded sample for "+source.Name,"admit_sample",source.FamilyId,2));
            if(package.State is "ready" or "in_progress" or "changes_requested" && state.AvailableOperations.Contains("submit_package") && Passed(state,"PQC-P1-G01")) state.NextActions.Add(new(
                package.EvidenceCount>0?"Submit the evidence conclusion for "+source.Name:"Document the evidence limitation for "+source.Name,"submit_package",source.FamilyId,3));
            if(package.State=="submitted" && state.AvailableOperations.Contains("review_package")) state.NextActions.Add(new("Review the evidence package for "+source.Name,"review_package",source.FamilyId,3));
            if(package.Analysis.State is "ready" or "changes_requested" && state.AvailableOperations.Contains("submit_analysis") && Passed(state,"PQC-P2-G01"))state.NextActions.Add(new("Explain consequences and next action for "+source.Name,"submit_analysis",source.FamilyId,6));
            if(package.Analysis.State=="submitted" && state.AvailableOperations.Contains("review_analysis")) state.NextActions.Add(new("Review business consequences for "+source.Name,"review_analysis",source.FamilyId,6));
        }
        foreach(var gate in state.Gates)
        {
            if(gate.State=="submitted" && gate.RequiredRoles.Contains(Role(state,principal)) && !gate.Decisions.Any(d=>d.Fingerprint==gate.Fingerprint && d.Role==Role(state,principal))) state.NextActions.Add(new("Decide: "+gate.Name,"decide_gate",gate.Id,gate.Stage));
            else if(gate.State is "not_submitted" or "needs_review" && gate.Requirements.All(r=>r.Satisfied) && state.AvailableOperations.Contains("submit_gate") &&
                (gate.Stage>=5?Role(state,principal)=="risk-lead":Role(state,principal)=="assessment-lead")) state.NextActions.Add(new("Request review: "+gate.Name,"submit_gate",gate.Id,gate.Stage));
        }
        if(state.Scope.Objective.Length==0 && state.AvailableOperations.Contains("update_scope")) state.NextActions.Insert(0,new("Set the assessment objective and scope","update_scope",null,1));
        if(Passed(state,"PQC-P1-G02") && !Passed(state,"PQC-P1-G03") && state.AvailableOperations.Contains("generate_report"))state.NextActions.Add(new("Prepare the Phase 1 report for review","generate_report",null,4));
        if(Passed(state,"PQC-P1-G03") && state.Method.Name.Length==0 && state.AvailableOperations.Contains("set_method"))state.NextActions.Add(new("Define the illustrative Phase 2 method","set_method",null,5));
        if(Passed(state,"PQC-P2-G02") && !Passed(state,"PQC-P2-G03") && state.AvailableOperations.Contains("generate_report"))state.NextActions.Add(new("Prepare the Phase 2 report for review","generate_report",null,7));
        // Accepted limitations remain follow-up work, not a reason to obscure
        // the current deliverable. Stable ordering preserves catalog order
        // within each stage and keeps preparatory work available afterward.
        state.NextActions=state.NextActions
            .OrderBy(a=>a.Stage==state.Stage?0:a.Stage>state.Stage?1:2)
            .ThenBy(a=>a.Stage).Take(20).ToList();
        var now=DateTimeOffset.UtcNow;
        var pending=state.Gates.Where(g=>g.State=="submitted").SelectMany(g=>g.RequiredRoles
            .Where(role=>!g.Decisions.Any(d=>d.Fingerprint==g.Fingerprint && d.Role==role))
            .Select(role=>
            {
                var submittedAt=state.Events.SingleOrDefault(e=>e.Revision==g.SubmissionRevision)?.CreatedAt??state.UpdatedAt;
                var age=DateTimeOffset.TryParse(submittedAt,out var at)?Math.Max(0,(int)(now-at).TotalDays):0;
                return new AssessmentPendingDecision(g.Id,role,submittedAt,age);
            })).ToList();
        state.Metrics=new AssessmentMetrics(
            new(state.Questions.Count(q=>q.State=="supported"),state.Questions.Count(q=>q.State=="qualified"),state.Questions.Count(q=>q.State=="unanswered"),state.Questions.Count,
                "Current scoped question set: two questions per selected family. Supported means an attributable routing answer or reviewed source-evidence conclusion, never enterprise completeness or independently verified behavior. Qualified includes explicit no-evidence limitations. Excluded families are outside this denominator."),
            new(sources.Count(s=>s.State=="route_confirmed"),sources.Count(s=>s.ObservationIds.Count>0),sources.Length,
                "Counts of scoped families with an attributable route response and fixed synthetic evidence admitted. No live source route is exercised, no percentage or employee performance ranking is inferred."),
            new(pending.Count,pending.Count==0?0:pending.Max(p=>p.AgeDays),pending,
                "Unfilled required role slots on current submitted gates; age is elapsed calendar days since submission. Historical, rejected and superseded submissions are excluded. No service-level target or response-time performance judgment is implied."),now.ToString("yyyy-MM-dd",System.Globalization.CultureInfo.InvariantCulture));
    }

    private static List<AssessmentRequirement> Requirements(AssessmentState state,AssessmentGate gate)
    {
        var families=state.Scope.IncludedFamilyIds;
        var sources=state.Sources.Where(s=>families.Contains(s.FamilyId)).ToArray();
        var packages=state.Packages.Where(p=>families.Contains(p.FamilyId)).ToArray();
        bool Document(string phase) => state.Documents.Any(d=>d.Id==gate.DocumentId && d.Phase==phase && d.InputFingerprint==ReportFingerprint(state,phase,d.Phase1ReportId));
        return gate.Id switch
        {
            "PQC-G00" => [new("Objective and information-handling boundary recorded",state.Scope.Objective.Length>0 && state.Scope.Handling.Length>0),new("Named independent sponsor and information-owner functions assigned",RolesAssigned(state,gate))],
            "PQC-P1-G01" => [new("Governance and information handling accepted",Passed(state,"PQC-G00")),new("Scope, depth and method recorded",families.Count>0 && state.Scope.Method.Length>0 && families.All(state.Scope.DepthByFamily.ContainsKey)),new("Each source has a route response or an explicit access limitation",sources.Length>0 && sources.All(s=>s.State!="unanswered" && s.Note.Length>0))],
            "PQC-P1-G02" => [new("Scope and source readiness accepted",Passed(state,"PQC-P1-G01")),new("Every scoped package reviewed or explicitly qualified",packages.Length>0 && packages.All(p=>Accepted(p.State)))],
            "PQC-P1-G03" => [new("Baseline validation accepted",Passed(state,"PQC-P1-G02")),new("Select an exact Phase 1 report using current inputs",Document("phase1"))],
            "PQC-P2-G01" => [new("Phase 1 handoff accepted for the current inputs",Passed(state,"PQC-P1-G03") && state.Phase1InputReportId!=null),new("Illustrative method and confidence/priority rules recorded",state.Method.Name.Length>0 && state.Method.Description.Length>0 && state.Method.ConfidenceRules.Length>0 && state.Method.PrioritizationRules.Length>0)],
            "PQC-P2-G02" => [new("Phase 2 method and selected input accepted",Passed(state,"PQC-P2-G01")),new("Every scoped analysis has business review or qualification",packages.Length>0 && packages.All(p=>Accepted(p.Analysis.State)))],
            "PQC-P2-G03" => [new("Phase 2 analysis validated",Passed(state,"PQC-P2-G02")),new("Select an exact Phase 2 report using current inputs",Document("phase2"))],
            _=>throw new DemoValidationException("assessment_gate_invalid")
        };
    }

    public static string ReportFingerprint(AssessmentState state,string phase,string? phase1Id=null)
    {
        var legacy=Hash(new
    {
        state.BaselineId,state.Scope,
        sources=state.Sources.Where(s=>state.Scope.IncludedFamilyIds.Contains(s.FamilyId)).Select(s=>new{s.FamilyId,s.State,s.SystemOfRecord,s.Product,s.OwnerFunction,s.AccessRoute,s.Note,s.DueAt,s.AssertedBy,s.RespondedBy}),
        packages=state.Packages.Where(p=>state.Scope.IncludedFamilyIds.Contains(p.FamilyId)).Select(p=>new{p.FamilyId,p.State,p.Conclusion,p.Qualification,p.ObservationIds,p.SubjectIds,p.LimitationCodes,p.Revision,p.ReviewedBy,p.ReviewRationale}),
        analysis=phase=="phase2"?state.Packages.Where(p=>state.Scope.IncludedFamilyIds.Contains(p.FamilyId)).Select(p=>p.Analysis).ToArray():null,
        method=phase=="phase2"?state.Method:null,phase1ReportId=phase=="phase2"?phase1Id:null
        });
        // Preserve historical empty-intake fingerprints; exports/previews are not
        // report inputs and cannot invalidate acceptance just by being downloaded.
        var withIntake=state.Intake.Requests.Count==0?legacy:Hash(new{legacy,
            requests=state.Intake.Requests.Where(r=>state.Scope.IncludedFamilyIds.Contains(r.FamilyId)),
            systems=state.Intake.Systems.Where(s=>state.Intake.Requests.Any(r=>r.Id==s.RequestId && state.Scope.IncludedFamilyIds.Contains(r.FamilyId))),
            observations=state.Intake.Batches.Where(b=>b.Status=="admitted" && state.Intake.Requests.Any(r=>r.Id==b.RequestId && state.Scope.IncludedFamilyIds.Contains(r.FamilyId))).SelectMany(b=>b.Observations)});
        var discovery=DiscoveryReportProjection.Fingerprint(state,withIntake);
        var workspace=phase=="phase1"?(state.Workspace.Phase1MaterialFingerprint??state.Workspace.MaterialFingerprint):state.Workspace.MaterialFingerprint;
        return string.IsNullOrEmpty(workspace)?discovery:Hash(new{discovery,workspace});
    }

    private static string GateFingerprint(AssessmentState state,AssessmentGate gate)
    {
        object Material(string id) => id switch
        {
            "PQC-G00" => new {state.Scope.Objective,state.Scope.Handling,roles=state.Assignments.Where(p=>gate.RequiredRoles.Contains(p.Role))},
            "PQC-P1-G01" => new {state.Scope,previous=DecisionBinding(state,"PQC-G00"),sources=state.Sources.Where(s=>state.Scope.IncludedFamilyIds.Contains(s.FamilyId)).Select(s=>new{s.FamilyId,s.State,s.SystemOfRecord,s.Product,s.OwnerFunction,s.AccessRoute,s.Note,s.DueAt,s.AssertedBy,s.RespondedBy})},
            "PQC-P1-G02" => new {report=ReportFingerprint(state,"phase1"),previous=DecisionBinding(state,"PQC-P1-G01")},
            "PQC-P1-G03" => new {gate.DocumentId,report=ReportFingerprint(state,"phase1"),previous=DecisionBinding(state,"PQC-P1-G02")},
            "PQC-P2-G01" => new {state.Method,state.Phase1InputReportId,previous=DecisionBinding(state,"PQC-P1-G03")},
            "PQC-P2-G02" => new {report=ReportFingerprint(state,"phase2",state.Phase1InputReportId),previous=DecisionBinding(state,"PQC-P2-G01")},
            _ => new {gate.DocumentId,report=ReportFingerprint(state,"phase2",state.Phase1InputReportId),previous=DecisionBinding(state,"PQC-P2-G02")}
        };
        return Hash(Material(gate.Id));
    }
    private static object DecisionBinding(AssessmentState state,string id)
    {
        var gate=FindGate(state,id);
        return new {gate.Fingerprint,gate.State,decisions=gate.Decisions.Where(d=>d.Fingerprint==gate.Fingerprint).Select(d=>d.Id).Order(StringComparer.Ordinal)};
    }
    private static bool RolesAssigned(AssessmentState state,AssessmentGate gate) => gate.RequiredRoles.All(r=>state.Assignments.Count(a=>a.Role==r)==1) && state.Assignments.Where(a=>gate.RequiredRoles.Contains(a.Role)).Select(a=>a.PrincipalId).Distinct().Count()==gate.RequiredRoles.Count;
    public static bool Passed(AssessmentState state,string id) => Accepted(FindGate(state,id).State);
    private static void NeedGate(AssessmentState state,string id) { if(!Passed(state,id)) Conflict("assessment_prerequisite_gate_required"); }
    public static AssessmentGate FindGate(AssessmentState state,string? id) => state.Gates.SingleOrDefault(g=>g.Id==id) ?? throw new DemoValidationException("assessment_gate_invalid");
    private static AssessmentSource Source(AssessmentState state,string? id) => state.Sources.SingleOrDefault(s=>s.FamilyId==id && state.Scope.IncludedFamilyIds.Contains(s.FamilyId)) ?? throw new DemoValidationException("assessment_source_not_in_scope");
    private static AssessmentPackage Package(AssessmentState state,string? id) => state.Packages.SingleOrDefault(p=>p.FamilyId==id && state.Scope.IncludedFamilyIds.Contains(p.FamilyId)) ?? throw new DemoValidationException("assessment_package_not_in_scope");
    public static void AdmitDiscoveryObservations(AssessmentState state,string familyId,IntakeObservation[] observations)
    {
        var source=Source(state,familyId);
        source.ObservationIds=source.ObservationIds.Concat(observations.Select(o=>o.Id)).Distinct().Order(StringComparer.Ordinal).ToList();
        source.SubjectIds=source.SubjectIds.Concat(observations.Select(o=>o.SystemId)).Distinct().Order(StringComparer.Ordinal).ToList();
        source.EvidenceOrigin="admitted_synthetic_sources_not_live_collection";
        var package=Package(state,familyId);
        ResetPackage(package);
        package.ObservationIds=[..source.ObservationIds];package.SubjectIds=[..source.SubjectIds];
        package.EvidenceCount=package.ObservationIds.Count;package.SubjectCount=package.SubjectIds.Count;
        package.LimitationCodes=package.LimitationCodes.Concat(new[]{"missing_business_context","unresolved_dependency","intake_unverified_reference"}).Distinct().ToList();
        package.State="in_progress";
    }

    private static void ResetPackage(AssessmentPackage package) { package.State="ready";package.SubmittedBy="";package.ReviewedBy="";package.Revision++;package.Analysis.State="ready"; }
    private static string SourceBinding(AssessmentSource source)=>Hash(new{source.State,source.SystemOfRecord,source.Product,source.OwnerFunction,source.AccessRoute,source.Note,source.DueAt,source.AssertedBy,source.RespondedBy});
    public static string[] Operations(string role) => role switch
    {
        "assessment-lead" => ["update_scope","source_response","admit_sample","submit_package","submit_gate","decide_gate","submit_analysis","generate_report"],
        "contributor" => ["source_response","submit_package"],
        "technical-reviewer" => ["review_package","decide_gate"],
        "risk-lead" => ["set_method","submit_analysis","submit_gate","decide_gate","generate_report"],
        "business-reviewer" => ["review_analysis","decide_gate"],
        "sponsor" or "information-owner" => ["decide_gate"],
        _ => []
    };

    public static void Closed(JsonObject fields,params string[] names)
    {
        if(fields.Count!=names.Length || fields.Any(p=>!names.Contains(p.Key,StringComparer.Ordinal))) Invalid("assessment_fields_invalid");
    }
    public static string Text(JsonObject fields,string name)
    {
        if(fields[name] is not JsonValue value || !value.TryGetValue<string>(out var text) || text.Length>2048 || text.Any(c=>char.IsControl(c) && c is not ('\n' or '\r' or '\t'))) throw new DemoValidationException("assessment_text_invalid");
        return text.Trim();
    }
    public static string Required(JsonObject fields,string name) { var value=Text(fields,name);if(value.Length==0)Invalid("assessment_required_field");return value; }
    public static string Date(JsonObject fields,string name)
    {
        var value=Required(fields,name);
        if(!DateOnly.TryParseExact(value,"yyyy-MM-dd",System.Globalization.CultureInfo.InvariantCulture,System.Globalization.DateTimeStyles.None,out _)) Invalid("assessment_date_invalid");
        return value;
    }
    private static string Choice(JsonObject fields,string name,params string[] allowed) {var value=Required(fields,name);if(!allowed.Contains(value,StringComparer.Ordinal))Invalid("assessment_choice_invalid");return value;}
    private static List<string> List(JsonObject fields,string name)
    {
        if(fields[name] is not JsonArray values || values.Count>100 || values.Any(v=>v is not JsonValue j || !j.TryGetValue<string>(out _))) throw new DemoValidationException("assessment_list_invalid");
        var list=values.Select(v=>v!.GetValue<string>()).ToList();if(list.Distinct(StringComparer.Ordinal).Count()!=list.Count || list.Any(v=>v.Length is 0 or >160))Invalid("assessment_list_invalid");return list;
    }
    private static Dictionary<string,string> Map(JsonObject fields,string name)
    {
        if(fields[name] is not JsonObject values || values.Count>100) throw new DemoValidationException("assessment_map_invalid");
        return values.OrderBy(p=>p.Key,StringComparer.Ordinal).ToDictionary(p=>p.Key,p=>Text(values,p.Key),StringComparer.Ordinal);
    }
    [System.Diagnostics.CodeAnalysis.DoesNotReturn]
    private static void Invalid(string code) => throw new DemoValidationException(code);
    [System.Diagnostics.CodeAnalysis.DoesNotReturn]
    private static void Conflict(string code) => throw new DemoConflictException(code);
}

public sealed record EvidenceSample(string FamilyId,List<string> ObservationIds,List<string> SubjectIds,List<string> LimitationCodes);
