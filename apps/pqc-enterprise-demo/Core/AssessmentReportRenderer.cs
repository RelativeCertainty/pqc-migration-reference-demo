using System.Net;
using System.Text;
using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

/// <summary>
/// Pure, assessment-scoped report projection. It neither selects a latest report
/// nor records acceptance. The controller supplies and commits the frozen inputs.
/// </summary>
public static class AssessmentReportRenderer
{
    private const string Boundary = "Synthetic development assessment. No enterprise facts, enterprise acceptance, regulatory compliance, risk acceptance or migration execution authority are established by this report.";

    public static JsonObject Build(string phase, JsonObject assessmentSnapshot,
        JsonObject scopedEvidenceProjection, JsonObject? explicitPhase1Manifest, JsonObject? workspaceInput = null)
    {
        if (phase is not ("phase1" or "phase2")) throw new DemoValidationException("invalid_report_phase");
        if (assessmentSnapshot["synthetic"]?.GetValue<bool>() != true)
            throw new DemoValidationException("assessment_report_synthetic_required");
        if (phase == "phase2" && (explicitPhase1Manifest is null ||
            S(explicitPhase1Manifest, "reportId").Length == 0 || S(explicitPhase1Manifest, "contentSha256").Length != 64 ||
            S(explicitPhase1Manifest, "inputFingerprint").Length == 0))
            throw new DemoValidationException("assessment_report_explicit_phase1_manifest_required");

        var scope = O(assessmentSnapshot["scope"]);
        var method = O(assessmentSnapshot["method"]);
        var included = Strings(scope, "includedFamilyIds").ToHashSet(StringComparer.Ordinal);
        var sources = Rows(assessmentSnapshot, "sources").Where(s => included.Contains(S(s, "familyId"))).ToArray();
        var packages = Rows(assessmentSnapshot, "packages").Where(p => included.Contains(S(p, "familyId"))).ToArray();
        var bounded = BoundProjection(scopedEvidenceProjection, included, sources, packages);
        var intakeState=AssessmentJson.State(assessmentSnapshot.ToJsonString());
        IntakeEvidenceProjection.Merge(intakeState,bounded);
        DiscoveryReportProjection.MergeEvidence(intakeState,bounded);
        var observations = Rows(bounded, "observations");
        var inventory = Rows(bounded, "inventory");
        var analysis = AnalysisProjection.Build(bounded);
        var findings = Rows(analysis, "findings");
        var allSubjects = inventory.Select(r => S(r, "subject_ref")).ToHashSet(StringComparer.Ordinal);
        var allObservations = observations.Select(r => S(r, "observation_id")).ToHashSet(StringComparer.Ordinal);
        var profiles = Rows(bounded, "sourceProfiles");
        var familyObservations = profiles.ToDictionary(p => S(p, "family_id"),
            p => observations.Where(o => Strings(p, "source_instance_refs").Contains(S(o, "source_instance_id"), StringComparer.Ordinal)).ToArray(), StringComparer.Ordinal);
        var coverage = new JsonArray();
        var enablement = new JsonArray();
        var nextSteps = new JsonArray();
        foreach (var source in sources)
        {
            var familyId = S(source, "familyId");
            var evidence = familyObservations.GetValueOrDefault(familyId) ?? [];
            var familyPackages = packages.Where(p => S(p, "familyId") == familyId).ToArray();
            var subjects = evidence.Select(o => S(o, "subject_ref")).Distinct(StringComparer.Ordinal).Count();
            var depth = S(O(scope["depthByFamily"]), familyId, "routing");
            var depthPackage = familyPackages.FirstOrDefault() ?? new JsonObject();
            var achievedDepth = S(depthPackage, "achievedDepth", evidence.Length > 0 ? "inventory" : "not_established");
            // A declaration of deeper scope is not evidence that the deeper
            // investigation was carried out. Preserve both facts separately.
            var depthLimitation = S(depthPackage, "depthLimitation", depth == "dependency_cohort"
                ? "Dependency-cohort depth is planned, not validated. This increment has no application/service cohort selector or independently reviewed cohort-completeness proof."
                : evidence.Length == 0 ? "No technical evidence has been admitted; recorded route information does not establish inventory depth."
                : "The bounded synthetic inventory does not establish complete enterprise inventory or independently verified runtime behavior.");
            var owner = S(source, "ownerFunction", "Accountable function not identified");
            var limitations = familyPackages.SelectMany(p => Strings(p, "limitationCodes"))
                .Concat(familyPackages.Select(p => S(p, "qualification")).Where(s => s.Length > 0)).Distinct(StringComparer.Ordinal).ToArray();
            coverage.Add(new JsonObject
            {
                ["familyId"] = familyId, ["name"] = S(source, "name", familyId), ["areaId"] = S(source, "areaId"),
                ["depth"] = depth, ["plannedDepth"] = depth, ["achievedDepth"] = achievedDepth,
                ["depthLimitation"] = depthLimitation, ["sourceState"] = S(source, "state", "unanswered"), ["observations"] = evidence.Length,
                ["subjects"] = subjects, ["packages"] = familyPackages.Length,
                ["populationState"] = "enterprise_denominator_unknown", ["populationTotal"] = null, ["coveragePercent"] = null,
                ["populationMeaning"] = "Counts describe admitted synthetic records only. The enterprise population has not been enumerated; no completeness percentage or statistical confidence is inferred.",
                ["limitation"] = depthLimitation + " " + (evidence.Length == 0 ? "No technical observations admitted for this family. A route response is not cryptographic evidence."
                    : depth == "routing" ? "Evidence is available, but this cycle authorizes source routing rather than a comprehensive domain assessment."
                    : depth == "inventory" ? "This inventory describes the admitted records only; the complete source-instance population and representativeness of any sample are unproved."
                    : depth == "dependency_cohort" ? "Any recorded correlations describe selected evidence only; unexamined instances, relying parties and environments remain outside this claim."
                    : "The assessment depth is not recognized; no broader assurance is inferred from these records."),
                ["qualifications"] = Array(limitations)
            });
            var routeRecorded = S(source, "accessRoute").Length > 0;
            var ownerRecorded = S(source, "ownerFunction").Length > 0;
            enablement.Add(new JsonObject
            {
                ["familyId"] = familyId, ["name"] = S(source, "name", familyId), ["owner"] = owner,
                ["ownerState"] = ownerRecorded ? "recorded_not_independently_verified" : "not_identified",
                ["systemOfRecord"] = S(source, "systemOfRecord", "Not identified"), ["product"] = S(source, "product", "Not confirmed"),
                ["route"] = S(source, "accessRoute", "No route recorded"),
                ["routeState"] = routeRecorded ? "recorded_not_exercised_by_this_report" : "not_identified",
                ["responseState"] = S(source, "state", "unanswered"), ["note"] = S(source, "note"),
                ["assertedBy"] = S(source, "assertedBy", "Information supplier not identified"),
                ["recordedBy"] = S(source, "respondedBy", "Recorder not identified"),
                ["responseAndProvenance"] = S(source, "note", "No response detail recorded") + " Supplied by: " +
                    S(source, "assertedBy", "not identified") + "; recorded by: " + S(source, "respondedBy", "not identified") + ".",
                ["dueAt"] = S(source, "dueAt", "Date to be agreed"), ["evidenceOrigin"] = S(source, "evidenceOrigin", "not_admitted"),
                ["interpretation"] = "Owner and route entries describe assessment enablement, not willingness, maturity, technical migration readiness or an exercised enterprise integration."
            });
            if (!ownerRecorded || !routeRecorded || evidence.Length == 0 || S(source, "state") is "blocked" or "unanswered")
                nextSteps.Add(Step(S(source, "name", familyId), owner,
                    !ownerRecorded ? "Identify the accountable source function and an authorized contact."
                    : !routeRecorded ? "Agree a permitted read-only route, required evidence and a response date."
                    : "Resolve the recorded source constraint or arrange a bounded evidence delivery and review.",
                    "Confirm the route, timing and permitted evidence, or explicitly retain the limitation.",
                    "Without this input, conclusions remain limited to the currently admitted evidence.", S(source, "dueAt", "Date to be agreed")));
        }

        var scenarioRows = new JsonArray();
        foreach (var package in packages)
        {
            var reviewedAnalysis = O(package["analysis"]);
            var selectedIds = Strings(package, "subjectIds").Where(allSubjects.Contains).ToHashSet(StringComparer.Ordinal);
            var packageEvidence = observations.Where(o => selectedIds.Contains(S(o, "subject_ref")) &&
                Strings(package, "observationIds").Contains(S(o, "observation_id"), StringComparer.Ordinal)).ToArray();
            var packageFindings = findings.Where(f => selectedIds.Contains(S(f, "subjectId"))).ToArray();
            var source = sources.FirstOrDefault(s => S(s, "familyId") == S(package, "familyId")) ?? new JsonObject();
            var owner = S(source, "ownerFunction", "Accountable function not identified");
            var supplied = S(reviewedAnalysis, "scenario").Length > 0;
            scenarioRows.Add(new JsonObject
            {
                ["packageId"] = S(package, "id"), ["label"] = S(package, "label"), ["familyId"] = S(package, "familyId"),
                ["areaId"] = S(source,"areaId"), ["areaName"] = DomainName(S(source,"areaId")),
                ["conclusion"] = S(package, "conclusion", "No reviewed current-state conclusion recorded"),
                ["packageState"] = S(package, "state"), ["qualification"] = S(package, "qualification"),
                ["scenario"] = S(reviewedAnalysis, "scenario", "Scenario not yet specified: establish the protection role, threat event, exposure path and affected business outcome."),
                ["scenarioState"] = supplied ? S(reviewedAnalysis, "state", "ready") : "not_assessed",
                ["businessImpact"] = S(reviewedAnalysis, "businessImpact", "Not established. Confirm the affected service, protected information and operational or business consequence."),
                ["protectedInformation"] = S(reviewedAnalysis,"protectedInformation","Protected-information scope requires an attributed business statement."),
                ["protectedInformationLifetime"] = S(reviewedAnalysis,"lifetime",Lifetime(packageEvidence)),
                ["businessStatementBy"] = S(reviewedAnalysis,"assertedBy","No separate attributed business statement recorded"),
                ["businessStatementDate"] = S(reviewedAnalysis,"statementDate","Not recorded"),
                ["businessStatementBasis"] = "Attributed synthetic business input, distinct from technical observations; designated review does not turn a modeled statement into an enterprise fact.",
                ["businessReviewedBy"] = S(reviewedAnalysis,"reviewedBy","Not reviewed"),
                ["compatibilityConstraints"] = S(reviewedAnalysis,"compatibilityConstraints","Exact client, verifier and dependency compatibility requires investigation."),
                ["operationalConstraints"] = S(reviewedAnalysis,"operationalConstraints","Maintenance, recovery and operational ownership constraints remain to be established."),
                ["exposure"] = Array(packageFindings.Select(f => Human(S(f, "exposure"))).Distinct(StringComparer.Ordinal)),
                ["technicalReadiness"] = "Not qualified by this assessment. Exact product/version support, compatibility and recovery need separate proof.",
                ["vendorConstraints"] = S(reviewedAnalysis,"vendorConstraints",VendorConstraints(packageEvidence)),
                ["organizationalEnablement"] = S(source, "note", "Confirm accountable owner, permitted source route, available resources and decision timetable."),
                ["confidence"] = supplied ? S(reviewedAnalysis, "confidence", "unknown") : "unknown",
                ["confidenceBasis"] = S(reviewedAnalysis, "rationale", "Confidence has not been justified against a reviewed assessment method."),
                ["priority"] = supplied ? S(reviewedAnalysis, "priority", "planned_review") : "not_assessed",
                ["priorityMeaning"] = "Assessment attention only; not an approved numerical risk rating or authorization to remediate.",
                ["recommendation"] = S(reviewedAnalysis, "recommendation", "Complete the missing context and resolve evidence qualifications before recommending migration."),
                ["owner"] = S(reviewedAnalysis,"responsibleFunction",owner), ["nextDecision"] = S(reviewedAnalysis,"nextDecision","Confirm the interpretation, remaining uncertainty and next assessment action; migration authorization remains separate."),
                ["analysisQualification"] = S(reviewedAnalysis, "qualification"),
                ["reviewDate"] = S(reviewedAnalysis, "reviewDate", "Review date not recorded"),
                ["observationRefs"] = Array(packageEvidence.Select(o => S(o, "observation_id"))),
                ["subjectRefs"] = Array(selectedIds.Order(StringComparer.Ordinal))
            });
            if (phase == "phase2") nextSteps.Add(Step(S(package, "label"), owner,
                S(reviewedAnalysis, "recommendation", "Resolve the scenario, business impact and evidence-confidence basis."),
                "Designated reviewers must disposition the analysis and its qualifications.",
                "An unresolved scenario remains a qualified assessment item; it cannot justify execution.", S(reviewedAnalysis, "reviewDate", "Date to be agreed")));
        }

        var unresolvedQuestions = Rows(assessmentSnapshot, "questions").Where(q => S(q, "state") is not ("supported" or "complete" or "answered" or "accepted" or "not_applicable")).ToArray();
        if (nextSteps.Count == 0) nextSteps.Add(Step("Review the assessment position", "Designated report reviewers",
            "Review this exact report and its limitations against the declared scope and questions.",
            "Record the permitted reliance and any qualifications in the separate decision register.",
            "A report artifact alone does not establish acceptance or permission to change a source system.", S(scope, "reviewDate", "Date to be agreed")));

        var withEvidence = coverage.OfType<JsonObject>().Count(r => Number(r, "observations") > 0);
        var title = phase == "phase1" ? "Current-State PQC Assessment" : "PQC Risk and Migration-Priority Assessment";
        var caveats = new[]
        {
            Boundary,
            "The enterprise asset and source-instance populations are not enumerated here. Selected-family and record counts are not enterprise coverage percentages.",
            "Relationships to records outside this selection are not expanded into the report. Their omission is not evidence that those dependencies do not exist.",
            "A synthetic fixture exercises software and reporting behavior; it does not prove a vendor API, operational access route, live negotiation or enterprise integration.",
            "Evidence may be reported, configured, observed or independently tested; these are different claims. Owner testimony may establish context, not negotiated cryptography.",
            "Exposure, business impact, evidence confidence, technical migration readiness and assessment enablement remain separate dimensions.",
            "The method is illustrative, not an enterprise-approved risk model. Priorities guide investigation; missing evidence does not lower exposure.",
            "Gate decisions and current reliance status are maintained separately from immutable report bytes. This report does not grant risk acceptance or Phase 3/4 execution authority.",
            "NIST references inform this design. They do not establish certification, endorsement, product approval or automatic compliance."
        };
        var report = new JsonObject
        {
            ["schemaVersion"] = "pqc.assessment.report.v1", ["phase"] = phase, ["title"] = title, ["synthetic"] = true,
            ["assessment"] = new JsonObject { ["id"] = S(assessmentSnapshot, "id"), ["name"] = S(assessmentSnapshot, "name"),
                ["revision"] = Number(assessmentSnapshot, "revision"), ["scopeRevision"] = Number(scope, "revision") },
            ["manifest"] = new JsonObject
            {
                ["assessmentId"] = S(assessmentSnapshot, "id"), ["assessmentRevision"] = Number(assessmentSnapshot, "revision"),
                ["scopeRevision"] = Number(scope, "revision"), ["methodRevision"] = Number(method, "revision"),
                ["dataBaselineId"] = S(O(bounded["baseline"]), "baselineId"), ["dataAsOf"] = S(O(bounded["baseline"]), "asOf"),
                ["selectedPhase1"] = phase == "phase2" ? explicitPhase1Manifest!.DeepClone() : null,
                ["includedFamilyIds"] = Array(included.Order(StringComparer.Ordinal)),
                ["subjectRefs"] = Array(allSubjects.Order(StringComparer.Ordinal)), ["observationRefs"] = Array(allObservations.Order(StringComparer.Ordinal)),
                ["packages"] = Array(packages.Select(p => new JsonObject { ["id"] = S(p, "id"), ["revision"] = Number(p, "revision"),
                    ["state"] = S(p, "state"), ["qualification"] = S(p, "qualification") })),
                ["questions"] = assessmentSnapshot["questions"]?.DeepClone() ?? new JsonArray(),
                ["limitationRefs"] = Array(Rows(bounded, "limitations").Select(l => S(l, "code")).Where(s => s.Length > 0).Distinct(StringComparer.Ordinal)),
                ["acceptanceAuthority"] = "Separate authenticated gate decisions; not encoded as approval in this artifact"
            },
            ["scope"] = scope.DeepClone(), ["method"] = method.DeepClone(),
            ["intake"] = IntakeWorkflow.ReportPreview(intakeState),
            ["discovery"] = DiscoveryReportProjection.Build(intakeState),
            ["assessmentIndicators"] = assessmentSnapshot["metrics"]?.DeepClone() ?? new JsonObject(),
            ["summary"] = new JsonObject { ["selectedFamilies"] = sources.Length, ["familiesWithEvidence"] = withEvidence,
                ["subjects"] = inventory.Length, ["observations"] = observations.Length, ["packages"] = packages.Length,
                ["unresolvedQuestions"] = unresolvedQuestions.Length, ["enterpriseCoveragePercent"] = null },
            ["narrative"] = new JsonObject
            {
                ["executiveSummary"] = Array(new[]
                {
                    new JsonObject { ["title"] = "What this cycle can describe", ["body"] = observations.Length == 0
                        ? $"The assessment scopes {sources.Length} source families, but no technical observations have been admitted. This is a scope and enablement assessment, not a cryptographic inventory conclusion."
                        : $"The selected synthetic evidence contains {observations.Length} observations about {inventory.Length} subjects across {withEvidence} of {sources.Length} scoped source families. Conclusions apply to these records and the stated depth, not the enterprise as a whole." },
                    new JsonObject { ["title"] = phase == "phase1" ? "What remains unresolved" : "What the analysis must establish", ["body"] = phase == "phase1"
                        ? $"{sources.Length - withEvidence} scoped families have no admitted technical observations. Unknown populations, unexamined dependencies, source constraints and package qualifications remain visible limitations—not evidence of low exposure."
                        : "Assess each cryptographic-use scenario against its protected information, lifetime, relying parties and business consequence. Review confidence and vendor or organizational constraints separately from exposure; do not infer migration readiness from an algorithm name." },
                    new JsonObject { ["title"] = "The decision required", ["body"] = phase == "phase1"
                        ? "Agree what reliance this bounded current-state package can support, who owns unresolved source routes, and which gaps must be resolved before Phase 2 analysis. Record a dated, qualified decision on this exact report."
                        : "Disposition the evidence-linked scenarios, investigation priorities and remaining limitations. Assign the next action and accountable function; any migration design or execution requires a separate future authorization." }
                }),
                ["sections"] = Sections(phase, scope, method, observations.Length, explicitPhase1Manifest),
                ["nextSteps"] = nextSteps,
                ["questions"] = Array(unresolvedQuestions.Select(q => S(q, "text")).Where(s => s.Length > 0)), ["caveats"] = Array(caveats)
            },
            ["coverageRows"] = coverage, ["enablementRows"] = enablement,
            ["findings"] = Array(findings.Select(f => new JsonObject
            {
                ["id"] = S(f, "id"), ["subjectId"] = S(f, "subjectId"), ["subjectLabel"] = S(f, "subjectLabel"),
                ["title"] = S(f, "title"), ["observation"] = S(f, "observation"), ["evidenceState"] = S(f, "evidenceState"),
                ["confidence"] = S(f, "confidence"), ["exposure"] = S(f, "exposure"),
                ["observationRefs"] = f["observationRefs"]?.DeepClone() ?? new JsonArray(),
                ["interpretationStatus"] = "Illustrative evidence interpretation; not an approved risk rating"
            })),
            ["scenarioRows"] = phase == "phase2" ? scenarioRows : new JsonArray(),
            ["packageRows"] = Array(packages.Select(p => new JsonObject { ["id"] = S(p, "id"), ["label"] = S(p, "label"),
                ["state"] = S(p, "state"), ["conclusion"] = S(p, "conclusion", "No conclusion recorded"),
                ["qualification"] = S(p, "qualification"), ["reviewDate"] = S(p, "reviewDate", "Not recorded") })),
            ["evidenceReferences"] = Array(observations.Select(o => new JsonObject { ["observationId"] = S(o, "observation_id"),
                ["subjectId"] = S(o, "subject_ref"), ["sourceInstance"] = S(o, "source_instance_id"),
                ["observedAt"] = S(o, "observed_at"), ["custodyRef"] = S(o, "evidence_ref"),
                ["factType"] = S(o, "fact_type"), ["origin"] = "synthetic_fixture_not_live_collection" })),
            ["references"] = References(), ["boundary"] = Boundary
        };
        return workspaceInput is null ? report : WorkspaceReportProjection.Apply(report, workspaceInput);
    }

    public static string RenderHtml(string reportId, string createdAt, JsonObject content)
    {
        if (content["workspace"] is JsonObject workspace && workspace["hasActivity"]?.GetValue<bool>() == true)
            return WorkspaceReportProjection.RenderHtml(reportId, createdAt, content);
        var html = new StringBuilder("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">");
        html.Append("<title>").Append(E(S(content, "title"))).Append("</title><style>").Append(Css).Append("</style></head><body><main>");
        html.Append("<header><p class=\"eyebrow\">PQC assessment workspace · Synthetic development snapshot</p><h1>").Append(E(S(content, "title"))).Append("</h1><p class=\"subtitle\">")
            .Append(E(S(O(content["assessment"]), "name"))).Append("</p><p class=\"meta\">Generated ").Append(E(createdAt)).Append(" · Assessment revision ")
            .Append(Number(O(content["assessment"]), "revision")).Append("</p></header>");
        html.Append("<aside class=\"notice\">").Append(E(Boundary)).Append(" Current reliance and review decisions are maintained separately in the assessment workspace.</aside>");
        var narrative = O(content["narrative"]);
        html.Append("<section aria-labelledby=\"executive\"><h2 id=\"executive\">Executive position</h2><div class=\"executive-grid\">");
        foreach (var item in Rows(narrative, "executiveSummary")) Card(html, S(item, "title"), S(item, "body"));
        html.Append("</div></section><nav aria-label=\"Report contents\">Read: <a href=\"#basis\">Assessment basis</a> · <a href=\"#coverage\">Coverage and limitations</a> · <a href=\"#enablement\">Source enablement</a> · <a href=\"#conclusions\">Conclusions</a> · <a href=\"#actions\">Next decisions</a> · <a href=\"#references\">References</a></nav>");
        var indicators = O(content["assessmentIndicators"]);
        if (indicators.Count > 0)
        {
            var answerability = O(indicators["questionAnswerability"]);
            var enablement = O(indicators["sourceEnablement"]);
            var backlog = O(indicators["decisionBacklog"]);
            html.Append("<section><h2>Assessment operating indicators</h2><p class=\"meta\">Snapshot date: ").Append(E(S(indicators, "asOf"))).Append(". Current assessment only; no enterprise coverage, service-level target or employee performance score.</p><div class=\"executive-grid\">");
            Card(html, "Question answerability", $"{Number(answerability, "supported")} supported; {Number(answerability, "qualified")} qualified; {Number(answerability, "unanswered")} unanswered in a set of {Number(answerability, "total")} questions. " + S(answerability, "definition"));
            Card(html, "Source enablement", $"{Number(enablement, "documentedRoutes")} documented routes and {Number(enablement, "syntheticSamplesAdmitted")} admitted synthetic samples among {Number(enablement, "total")} scoped source families. " + S(enablement, "definition"));
            Card(html, "Decisions awaiting a reviewer", $"{Number(backlog, "pendingSlots")} unfilled required-role slots on submitted gates. Oldest submitted-review age: {Value(backlog["oldestAgeDays"])} calendar days. " + S(backlog, "definition"));
            html.Append("</div><p>The starter question set covers source routing and evidence availability. It is not yet a complete registry of every material business, cryptographic-use, dependency or report-acceptance question.</p></section>");
        }
        if(content["discovery"] is JsonObject discovery && discovery["hasActivity"]?.GetValue<bool>()==true)
            html.Append(DiscoveryReportProjection.RenderHtml(discovery));
        if(content["intake"] is JsonObject intake && Strings(intake,"conclusions").Length>0)
        {
            html.Append("<section id=\"intake\"><h2>Discovery responses and admitted source evidence</h2><p>").Append(E(S(intake,"summary"))).Append("</p><h3>What the responses establish</h3>");
            List(html,Strings(intake,"conclusions"));html.Append("<h3>Remaining limitations</h3>");List(html,Strings(intake,"limitations"));
            html.Append("<h3>Next decisions and handoffs</h3>");List(html,Strings(intake,"nextDecisions"));html.Append("</section>");
        }
        html.Append("<section id=\"basis\"><h2>Assessment basis and permitted interpretation</h2>");
        foreach (var section in Rows(narrative, "sections"))
        {
            html.Append("<h3>").Append(E(S(section, "title"))).Append("</h3><p>").Append(E(S(section, "summary"))).Append("</p>");
            foreach (var p in Strings(section, "paragraphs")) html.Append("<p>").Append(E(p)).Append("</p>");
        }
        html.Append("</section><section id=\"coverage\"><h2>Coverage and limitations</h2><p>These are counts of selected synthetic records, not percentages of the enterprise. Source routing, bounded inventory and dependency-cohort investigation are different depths. No enterprise population denominator or statistical sampling inference has been established.</p>");
        Table(html, Rows(content, "coverageRows"), [("name", "Scoped source family"), ("plannedDepth", "Planned depth"), ("achievedDepth", "Depth supported so far"), ("subjects", "Subjects"), ("observations", "Observations"), ("limitation", "What cannot be concluded")]);
        var excluded = O(O(content["scope"])["excludedReasons"]);
        if (excluded.Count > 0)
        {
            html.Append("<h3>Explicit exclusions</h3><ul>");
            foreach (var item in excluded) html.Append("<li><strong>").Append(E(item.Key)).Append(":</strong> ").Append(E(Value(item.Value))).Append("</li>");
            html.Append("</ul>");
        }
        html.Append("</section><section id=\"enablement\"><h2>Assessment enablement: the routes needed to obtain evidence</h2><p>Recorded ownership, source routes and constraints show what this cycle can mobilize. They are not a score of cooperation, organizational maturity or migration readiness. Fixture evidence does not prove that a live route has been exercised.</p>");
        Table(html, Rows(content, "enablementRows"), [("name", "Source family"), ("owner", "Accountable function"), ("systemOfRecord", "System of record"), ("route", "Read-only evidence route"), ("responseAndProvenance", "Response and provenance"), ("dueAt", "Next date")]);
        html.Append("</section><section id=\"conclusions\"><h2>").Append(S(content, "phase") == "phase2" ? "Evidence-linked scenarios and recommendations" : "Current-state positions and review status").Append("</h2>");
        if (S(content, "phase") == "phase2")
        {
            var scenarios = Rows(content, "scenarioRows");
            if (scenarios.Length == 0) html.Append("<p>No assessment packages support a scenario yet. No risk conclusions or migration recommendations are inferred from an empty selection.</p>");
            foreach (var row in scenarios)
            {
                html.Append("<article class=\"finding\"><h3>").Append(E(S(row, "label"))).Append("</h3>");
                Terms(html, row, [("scenario", "Scenario"), ("businessImpact", "Business consequence"), ("protectedInformation", "Protected information"), ("protectedInformationLifetime", "Confidentiality / trust lifetime"),
                    ("businessStatementBy", "Statement attributed to"), ("businessStatementDate", "Statement date"),
                    ("exposure", "Recorded exposure"), ("confidence", "Evidence confidence"), ("confidenceBasis", "Confidence / priority rationale"),
                    ("priority", "Investigation priority"), ("technicalReadiness", "Technical migration readiness"), ("vendorConstraints", "Vendor / implementation constraints"),
                    ("compatibilityConstraints", "Compatibility constraints"), ("operationalConstraints", "Operational constraints"),
                    ("organizationalEnablement", "Organizational enablement"), ("recommendation", "Recommended next action"), ("owner", "Accountable function"),
                    ("nextDecision", "Decision needed"), ("qualification", "Evidence qualification"), ("analysisQualification", "Analysis qualification")]);
                html.Append("<p class=\"meta\">Review state: ").Append(E(Human(S(row, "scenarioState")))).Append(". Evidence references: ").Append(E(string.Join(", ", Strings(row, "observationRefs")))).Append("</p></article>");
            }
        }
        else Table(html, Rows(content, "packageRows"), [("label", "Assessment package"), ("state", "Review state"), ("conclusion", "Current-state conclusion"), ("qualification", "Qualification / limitation"), ("reviewDate", "Review date")]);
        html.Append("</section><section id=\"actions\"><h2>Next decisions and accountable actions</h2>");
        Table(html, Rows(narrative, "nextSteps"), [("title", "Item"), ("owner", "Accountable function"), ("action", "Next action"), ("decisionRequired", "Decision required"), ("dueAt", "Date"), ("consequence", "If unresolved")]);
        var questions = Strings(narrative, "questions");
        if (questions.Length > 0) { html.Append("<h3>Questions still limited or unanswered</h3>"); List(html, questions); }
        html.Append("</section><section><h2>Interpretation safeguards</h2>"); List(html, Strings(narrative, "caveats")); html.Append("</section>");
        html.Append("<section id=\"references\"><h2>Primary guidance and applicability</h2><p>These sources support the assessment design; the report's judgments and workflow are project decisions, not NIST-prescribed gates.</p><ol>");
        foreach (var reference in Rows(content, "references"))
        {
            var url = S(reference, "url");
            html.Append("<li>");
            if (Uri.TryCreate(url, UriKind.Absolute, out var parsed) && parsed.Scheme == "https" &&
                (parsed.Host == "nist.gov" || parsed.Host.EndsWith(".nist.gov", StringComparison.Ordinal)))
                html.Append("<a href=\"").Append(E(url)).Append("\">").Append(E(S(reference, "title"))).Append("</a>");
            else html.Append(E(S(reference, "title")));
            html.Append(" <span class=\"status\">").Append(E(S(reference, "status"))).Append("</span><p>").Append(E(S(reference, "supports"))).Append("</p></li>");
        }
        html.Append("</ol></section><details><summary>Traceability appendix — frozen inputs and attributable evidence</summary><p>This appendix is for record-level review. It contains references, not source payloads, private keys, credentials or database dumps.</p>");
        var manifest = O(content["manifest"]);
        html.Append("<dl><dt>Report identifier</dt><dd>").Append(E(reportId)).Append("</dd><dt>Evidence baseline</dt><dd>").Append(E(S(manifest, "dataBaselineId"))).Append("</dd></dl>");
        var phase1 = O(manifest["selectedPhase1"]);
        if (phase1.Count > 0) Terms(html, phase1, [("reportId", "Explicit Phase 1 input"), ("contentSha256", "Phase 1 content hash"), ("inputFingerprint", "Phase 1 input fingerprint")]);
        Table(html, Rows(content, "evidenceReferences"), [("observationId", "Observation"), ("subjectId", "Subject"), ("sourceInstance", "Source instance"), ("observedAt", "Observed at"), ("custodyRef", "Custody reference")]);
        html.Append("</details><footer><p>Report reference: ").Append(E(reportId)).Append("</p><p>Use the browser's Print → Save as PDF for a fixed reading copy. Keep this report identifier with any exported copy. This snapshot does not change when later review decisions are recorded.</p></footer></main></body></html>");
        return html.ToString();
    }

    private static JsonObject BoundProjection(JsonObject projection, HashSet<string> included, JsonObject[] sources, JsonObject[] packages)
    {
        var membership = sources.Concat(packages).ToArray();
        var subjectIds = membership.SelectMany(s => Strings(s, "subjectIds")).ToHashSet(StringComparer.Ordinal);
        var observationIds = membership.SelectMany(s => Strings(s, "observationIds")).ToHashSet(StringComparer.Ordinal);
        var observations = Rows(projection, "observations").Where(o => subjectIds.Contains(S(o, "subject_ref")) && observationIds.Contains(S(o, "observation_id"))).ToArray();
        var admitted = observations.Select(o => S(o, "observation_id")).ToHashSet(StringComparer.Ordinal);
        var baseline = O(projection["baseline"]);
        var result = new JsonObject
        {
            ["baseline"] = new JsonObject { ["baselineId"] = S(baseline, "baselineId"), ["asOf"] = S(baseline, "asOf"), ["synthetic"] = baseline["synthetic"]?.DeepClone(), ["tenantId"] = S(baseline, "tenantId") },
            ["method"] = projection["method"]?.DeepClone() ?? new JsonObject(),
            ["observations"] = Array(observations), ["inventory"] = Array(Rows(projection, "inventory").Where(r => subjectIds.Contains(S(r, "subject_ref")))),
            ["sourceProfiles"] = Array(Rows(projection, "sourceProfiles").Where(p => included.Contains(S(p, "family_id")))),
            ["estateAreas"] = projection["estateAreas"]?.DeepClone() ?? new JsonArray(),
            ["dependencies"] = Array(Rows(projection, "dependencies").Where(d => subjectIds.Contains(S(d, "from_ref")) && subjectIds.Contains(S(d, "to_ref")))),
            ["limitations"] = Array(Rows(projection, "limitations").Where(r => subjectIds.Contains(S(r, "subject_ref"))))
        };
        foreach (var kind in new[] { "riskReviews", "contextReviews" })
            result[kind] = Array(Rows(projection, kind).Where(r => subjectIds.Contains(S(r, "subject_ref")) &&
                Strings(r, "observation_refs").Length > 0 && Strings(r, "observation_refs").All(admitted.Contains)));
        return result;
    }

    private static JsonArray Sections(string phase, JsonObject scope, JsonObject method, int observationCount, JsonObject? phase1) => Array(new[]
    {
        new JsonObject { ["id"] = "objective", ["title"] = "The decision this assessment supports", ["summary"] = S(scope, "objective", "The assessment objective is not yet recorded."),
            ["paragraphs"] = Array(new[] { "Cycle goal: " + S(scope, "cycleGoal", "Not specified"), "Information handling: " + S(scope, "handling", "Not specified; do not infer permission to retain source data."), "Review date: " + S(scope, "reviewDate", "To be agreed") }) },
        new JsonObject { ["id"] = "method", ["title"] = "Method and evidence strength", ["summary"] = S(method, "description", S(scope, "method", "A method has not been recorded.")),
            ["paragraphs"] = Array(new[] { "Method: " + S(method, "name", "Not named") + "; revision " + Number(method, "revision") + "; status: " + Human(S(method, "status", "illustrative_not_enterprise_approved")) + ".",
                "Confidence rules: " + S(method, "confidenceRules", "Not specified; no confidence rating is inferred."),
                "Prioritization rules: " + S(method, "prioritizationRules", "Not specified; no approved risk rating is inferred.") }) },
        new JsonObject { ["id"] = "handoff", ["title"] = phase == "phase1" ? "What Phase 2 receives — and does not receive" : "The explicit Phase 1 input", ["summary"] = phase == "phase1"
            ? "Phase 2 can consume this exact current-state snapshot: scoped membership, evidence references, reviewed positions, qualifications and unresolved questions. A separate decision records whether that input is suitable for the intended analysis."
            : "This analysis references Phase 1 report " + S(phase1 ?? new JsonObject(), "reportId") + ". It does not automatically attach whichever report happens to be newest.",
            ["paragraphs"] = Array(new[] { observationCount == 0 ? "No technical evidence has been admitted. This report cannot establish cryptographic inventory, algorithm exposure or migration priority." : "The reported uses and dependency context describe admitted synthetic evidence. They do not establish unobserved runtime behavior or a complete enterprise map.",
                "Phase 1 records current conditions, evidence quality and enablement constraints. Phase 2 interprets risk scenarios and recommended priorities. Neither phase authorizes source-system remediation.",
                "Future Phase 3/4 work would require qualified product-specific patterns, immutable plans, separately bound approvals, independent verification and recovery. Those execution capabilities are not enabled here." }) }
    });

    public static string DomainName(string id) => id switch
    {
        "area-01"=>"Enterprise context", "area-02"=>"PKI and trust", "area-03"=>"Encrypted traffic", "area-04"=>"Machine access",
        "area-05"=>"Software delivery", "area-06"=>"Cloud, keys and identity", "area-07"=>"Protected data", "area-08"=>"Distributed endpoints",
        "area-09"=>"Specialized and regulated cryptography", "area-10"=>"Governance and assurance", _=>"Unclassified scope"
    };

    private static string Lifetime(JsonObject[] observations)
    {
        var values = observations.Select(o => O(o["facts"]))
            .SelectMany(f => new[] { Fact(f, "information_lifetime_basis", "Lifetime basis"), Fact(f, "confidentiality_lifetime", "Confidentiality lifetime"),
                Fact(f, "protected_information", "Protected information"), Fact(f, "data_retention_period", "Retention period"),
                Fact(f, "confidentiality_until", "Confidentiality required until"), Fact(f, "signature_trust_until", "Signature trust required until") })
            .Where(s => s.Length > 0).Distinct(StringComparer.Ordinal).ToArray();
        return values.Length == 0 ? "Not established in the selected observations. Ask the data/service owner what must remain confidential or trustworthy, for how long, and on what basis." : string.Join("; ", values) + " (source-recorded context; requires review)";
    }

    private static string VendorConstraints(JsonObject[] observations)
    {
        var values = observations.Select(o => O(o["facts"]))
            .SelectMany(f => new[] { S(f, "vendor_dependency"), S(f, "migration_constraint"), S(f, "support_status"), S(f, "product_version") })
            .Where(s => s.Length > 0).Distinct(StringComparer.Ordinal).ToArray();
        return values.Length == 0 ? "Exact-product support and vendor commitments have not been qualified. Record the edition/version, supported interface and evidence of compatibility." : string.Join("; ", values) + " (reported, not a qualified migration capability)";
    }

    private static JsonArray References() => Array(new[]
    {
        Reference("NIST SP 800-30 Rev. 1 — Guide for Conducting Risk Assessments", "Final · September 2012", "https://csrc.nist.gov/pubs/sp/800/30/r1/final", "Supports explicit assessment purpose, scope, assumptions, sources, methods, uncertainty and risk scenarios. This report is not a claim of a full NIST risk assessment."),
        Reference("NIST CSWP 39upd1 — Considerations for Achieving Crypto Agility: Strategies and Practices", "Final · December 2025; updated June 2026", "https://csrc.nist.gov/pubs/cswp/39/upd1/considerations-for-achieving-crypto-agility/final", "Supports cryptographic inventory, dependency awareness, governance and managed change that preserves operations. It is guidance, not a certification framework."),
        Reference("NCCoE — Migration to Post-Quantum Cryptography", "Ongoing project · current discovery and interoperability work", "https://www.nccoe.nist.gov/applied-cryptography/migration-to-pqc", "Supports cryptographic discovery and interoperability investigation. Product examples and this synthetic fixture do not establish enterprise product compatibility."),
        Reference("NIST SP 1301 — NIST Cybersecurity Framework 2.0: Quick-Start Guide for Creating and Using Organizational Profiles", "Final · February 2024", "https://csrc.nist.gov/pubs/sp/1301/final", "Supports scoped current/target profiles and prioritized improvement actions. Our enablement profile is a project-specific assessment aid, not an assigned CSF Tier or organizational maturity score."),
        Reference("NIST SP 800-55 Vol. 1 — Measurement Guide for Information Security: Volume 1 — Identifying and Selecting Measures", "Final · December 2024", "https://csrc.nist.gov/pubs/sp/800/55/v1/final", "Supports defined measures, population and data-quality context. Partial-source counts cannot establish the completeness of an unknown enterprise population."),
        Reference("NIST SP 800-53A Rev. 5 — Assessing Security and Privacy Controls in Information Systems and Organizations", "Final · January 2022", "https://csrc.nist.gov/pubs/sp/800/53/a/r5/final", "The examine/interview/test distinction informs our evidence-strength model. This application is not performing or certifying a complete SP 800-53A control assessment."),
        Reference("NIST IR 8547 — Transition to Post-Quantum Cryptography Standards", "INITIAL PUBLIC DRAFT · November 2024 · not final requirements", "https://csrc.nist.gov/pubs/ir/8547/ipd", "Provides draft transition direction. It does not supply a binding project deadline or authorize a source-system change."),
        Reference("NIST — Post-Quantum Cryptography publications: FIPS 203, 204 and 205", "Final algorithm standards · August 2024", "https://csrc.nist.gov/Projects/Post-Quantum-Cryptography/publications", "FIPS 203 standardizes ML-KEM; FIPS 204 standardizes ML-DSA; FIPS 205 standardizes SLH-DSA. Algorithm standards are not an enterprise migration methodology or proof that a product is PQC-ready.")
    });

    private static JsonObject Reference(string title, string status, string url, string supports) => new() { ["title"] = title, ["status"] = status, ["url"] = url, ["supports"] = supports };
    private static JsonObject Step(string title, string owner, string action, string decision, string consequence, string date) => new() { ["title"] = title, ["owner"] = owner, ["action"] = action, ["decisionRequired"] = decision, ["consequence"] = consequence, ["dueAt"] = date };
    private static JsonObject O(JsonNode? node) => node as JsonObject ?? new JsonObject();
    private static JsonObject[] Rows(JsonObject node, string key) => node[key] is JsonArray array ? array.OfType<JsonObject>().ToArray() : [];
    private static string[] Strings(JsonObject node, string key) => node[key] is JsonArray array ? array.Select(Value).Where(s => s.Length > 0).ToArray() : [];
    private static string S(JsonObject node, string key, string fallback = "") => node[key] is JsonValue value && value.TryGetValue<string>(out var text) && !string.IsNullOrWhiteSpace(text) ? text : fallback;
    private static int Number(JsonObject node, string key) => node[key] is JsonValue value && value.TryGetValue<int>(out var number) ? number : 0;
    private static string Fact(JsonObject node, string key, string label) => S(node, key) is { Length: > 0 } value ? label + ": " + value : "";
    private static string Value(JsonNode? node) => node is JsonValue value && value.TryGetValue<string>(out var text) ? text : node is JsonArray array ? string.Join("; ", array.Select(Value)) : node?.ToJsonString() ?? "";
    private static string Human(string value) => value.Replace('_', ' ');
    private static string E(string value) => WebUtility.HtmlEncode(value);
    private static JsonArray Array(IEnumerable<string> values) => new(values.Select(v => (JsonNode?)JsonValue.Create(v)).ToArray());
    private static JsonArray Array(IEnumerable<JsonObject> values) => new(values.Select(v => v.DeepClone()).ToArray());
    private static void Card(StringBuilder html, string title, string body) => html.Append("<article class=\"summary-card\"><h3>").Append(E(title)).Append("</h3><p>").Append(E(body)).Append("</p></article>");
    private static void List(StringBuilder html, IEnumerable<string> values) { html.Append("<ul>"); foreach (var value in values) html.Append("<li>").Append(E(value)).Append("</li>"); html.Append("</ul>"); }
    private static void Terms(StringBuilder html, JsonObject row, (string Key, string Label)[] fields)
    {
        html.Append("<dl>");
        foreach (var field in fields) html.Append("<dt>").Append(E(field.Label)).Append("</dt><dd>").Append(E(Value(row[field.Key]) is { Length: > 0 } value ? Human(value) : "Not recorded")).Append("</dd>");
        html.Append("</dl>");
    }
    private static void Table(StringBuilder html, JsonObject[] rows, (string Key, string Label)[] fields)
    {
        if (rows.Length == 0) { html.Append("<p class=\"empty\">No records in this assessment selection. No global catalog records have been substituted.</p>"); return; }
        html.Append("<div class=\"table-wrap\"><table><thead><tr>");
        foreach (var field in fields) html.Append("<th scope=\"col\">").Append(E(field.Label)).Append("</th>");
        html.Append("</tr></thead><tbody>");
        foreach (var row in rows)
        {
            html.Append("<tr>");
            foreach (var field in fields) html.Append("<td>").Append(E(Value(row[field.Key]) is { Length: > 0 } value ? Human(value) : "Not recorded")).Append("</td>");
            html.Append("</tr>");
        }
        html.Append("</tbody></table></div>");
    }

    // One fixed block permits a strict hash-bound style CSP without unsafe-inline.
    private const string Css = """
        :root{color-scheme:light;font-family:Arial,Helvetica,sans-serif;color:#162d43;background:#eef2f6}*{box-sizing:border-box}body{margin:0;font-size:16px;line-height:1.6}main{max-width:1160px;margin:32px auto;background:#fff;padding:44px 48px;border:1px solid #d6dfe8}header{border-bottom:3px solid #245f80;padding-bottom:20px;margin-bottom:22px}.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.09em;font-weight:700;color:#24607a}h1{font-size:36px;line-height:1.15;margin:14px 0}h2{font-size:24px;line-height:1.25;margin:0 0 16px}h3{font-size:18px;line-height:1.35;margin:18px 0 8px}p{margin:8px 0 14px}.subtitle{font-size:20px}.meta,footer{color:#526779;font-size:12px;overflow-wrap:anywhere}.notice{background:#fff5dc;border-left:4px solid #9b6718;padding:14px 18px;font-size:14px}section{margin:34px 0;scroll-margin-top:20px}.executive-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.summary-card{background:#f3f7fa;border:1px solid #dbe5ec;padding:18px}.summary-card h3{margin-top:0;color:#174e6a}.summary-card p{font-size:15px;margin-bottom:0}nav{font-size:13px;padding:16px 0;border-top:1px solid #d6dfe8;border-bottom:1px solid #d6dfe8}a{color:#125a88;text-decoration:underline;text-underline-offset:3px}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px;line-height:1.45}th{text-align:left;background:#e8eff5;color:#153a54;font-size:12px}td,th{padding:11px 10px;border-bottom:1px solid #d9e2e9;vertical-align:top;overflow-wrap:anywhere}tbody tr:nth-child(even){background:#f7f9fb}th:first-child,td:first-child{min-width:130px}dt{font-weight:700;color:#214a65}dd{margin:0 0 12px;overflow-wrap:anywhere}li{margin:8px 0}.finding{border-top:2px solid #b9cddb;padding:14px 0 8px}.finding dl{display:grid;grid-template-columns:210px minmax(0,1fr);gap:6px 18px}.finding dt,.finding dd{margin:0}.status{display:block;font-weight:700;color:#745315;font-size:12px}details{border:1px solid #d6dfe8;padding:18px;margin:28px 0}summary{cursor:pointer;font-weight:700}.empty{border-left:3px solid #8b9daf;padding:12px 16px;background:#f4f7fa}footer{border-top:1px solid #d6dfe8;padding-top:18px}@media(max-width:760px){main{margin:0;padding:24px 18px;border:0}h1{font-size:28px}.executive-grid{grid-template-columns:1fr}.finding dl{grid-template-columns:1fr}.finding dd{margin-bottom:12px}table{min-width:660px}}@media print{@page{size:A4 landscape;margin:15mm}body{background:white;font-size:11px}main{max-width:none;margin:0;padding:0;border:0}h1{font-size:26px}h2{font-size:19px}h3{font-size:14px}.subtitle{font-size:16px}nav{display:none}.executive-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.summary-card p,.notice{font-size:11px}table{font-size:9px;min-width:0}th{font-size:9px}td,th{padding:7px 6px}thead{display:table-header-group}tr,.summary-card{break-inside:avoid}h2,h3{break-after:avoid}section{margin:20px 0}.table-wrap{overflow:visible}a{color:inherit}.finding dl{grid-template-columns:180px minmax(0,1fr)}details{display:none}footer{font-size:9px}}
        """;
}
