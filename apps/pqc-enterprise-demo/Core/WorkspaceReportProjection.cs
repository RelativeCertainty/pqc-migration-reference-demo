using System.Net;
using System.Text;
using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

/// <summary>Deterministic reading surface for controller-selected workspace revisions.
/// It cannot admit evidence, choose a newer Phase 1 package, or record acceptance.</summary>
public static class WorkspaceReportProjection
{
    public const string TemplateVersion = "pqc.response-to-report.html.v4";
    public static JsonObject Apply(JsonObject report, JsonObject input)
    {
        if (input["hasActivity"]?.GetValue<bool>() == false) return report;
        var receipts = Rows(input, "receipts");
        var identities = Rows(input, "identities");
        var bundles = Rows(input, "bundles").Where(b => Text(b, "status") == "admitted").ToArray();
        var conclusions = Rows(input, "consequences").Where(c => Text(c, "status") == "recorded").ToArray();
        if (receipts.Length + identities.Length + bundles.Length + conclusions.Length == 0) return report;
        var workspace = (JsonObject)input.DeepClone();
        workspace["hasActivity"] = true;
        workspace["bundles"] = Copy(bundles);
        workspace["consequences"] = Copy(conclusions);
        workspace["templateVersion"] = TemplateVersion;
        workspace["enterpriseCoveragePercent"] = null;
        workspace["populationBasis"] = "Returned information and reviewed identities in this assessment only; the enterprise population is unknown.";
        var declared = identities.Where(i => Text(i, "decision") != "unresolved").Select(i => Text(i, "canonicalId")).Where(s => s.Length > 0).Distinct(StringComparer.Ordinal).ToArray();
        var examined = bundles.Select(b => Text(b, "canonicalId")).Where(s => declared.Contains(s, StringComparer.Ordinal)).Distinct(StringComparer.Ordinal).Count();
        workspace["populationStatement"] = declared.Length == 0
            ? "No reviewed system/source binding population has been established. Known records are not a coverage denominator."
            : $"{examined} of {declared.Length} reported system/source bindings have admitted supporting records. This counts reviewed returned-row bindings, not independently examined target deployments or enterprise completeness. Evidence sources may describe other systems.";
        report["workspace"] = workspace;
        var manifest = Object(report["manifest"]);
        manifest["workspaceInputFingerprint"] = Text(input, "inputFingerprint");
        manifest["workspaceTemplateVersion"] = TemplateVersion;
        manifest["receiptRefs"] = Strings(receipts.Select(r => Text(r, "id")));
        manifest["identityDecisionRefs"] = Strings(identities.Select(r => Text(r, "id")));
        manifest["workspaceEvidenceRefs"] = Strings(bundles.SelectMany(b => Rows(b, "observations")).Select(ObservationId));
        manifest["consequenceRefs"] = Strings(conclusions.Select(c => Text(c, "id")));
        var narrative = Object(report["narrative"]);
        var phase2 = Text(report, "phase") == "phase2";
        var summaryConclusions = conclusions.Where(c => Text(c, "productId").Length == 0).ToArray();
        if (summaryConclusions.Length == 0) summaryConclusions = conclusions.Take(3).ToArray();
        narrative["executiveSummary"] = new JsonArray(
            new JsonObject { ["title"] = "What is established", ["body"] = conclusions.Length == 0
                ? "Returned information is available for assessment work. No new reviewed conclusion has been recorded through this workspace."
                : conclusions.Length<=3 ? string.Join(" ", summaryConclusions.Select(c => phase2 ? Text(c, "phase2Consequence", "phase1Conclusion") : Text(c, "phase1Conclusion", "conclusion")).Distinct(StringComparer.Ordinal))
                : $"This bounded assessment records {conclusions.Length} reviewed interpretations across {Rows(report,"coverageRows").Select(c=>Text(c,"areaId")).Distinct().Count()} discovery domains. Read the domain positions and their qualifications below; this is not enterprise-wide coverage or proof of migration readiness." },
            new JsonObject { ["title"] = "What remains uncertain", ["body"] = Limitations(conclusions).Take(3).DefaultIfEmpty(
                "Scope, corroboration and dependencies require explicit review. Questionnaire receipt alone is not technical verification.").Aggregate((a, b) => a + " " + b) },
            new JsonObject { ["title"] = "What happens next", ["body"] = conclusions.Length == 0
                ? "The assessment lead reconciles the returned systems and arranges permitted investigation. Technical review and admission remain separate."
                : string.Join(" ", conclusions.Select(c => Text(c, "nextDecision")).Distinct(StringComparer.Ordinal).Take(3)) });
        if (phase2) narrative["executiveSummary"] = Phase2Executive(report, conclusions);
        return report;
    }

    private static JsonArray Phase2Executive(JsonObject report, JsonObject[] conclusions)
    {
        var all = Rows(report, "scenarioRows");
        var reviewed = all.Where(r => (Text(r, "scenarioState") is "accepted" or "qualified") &&
            Text(r, "businessReviewedBy").Length > 0 && Text(r, "businessReviewedBy") != "Not reviewed").ToArray();
        var result = new JsonArray();
        void Add(string title, string body) => result.Add(new JsonObject { ["title"] = title, ["body"] = body });
        if (reviewed.Length == 0)
        {
            Add("Phase 2 business position", "No designated business review has established a reportable scenario interpretation. Draft technical or business statements must not be read as reviewed consequences, priorities or recommendations.");
            Add("Decision needed", "The risk lead prepares the scoped scenarios and attributed business context; the independent business reviewer records the determination before the report can present a reviewed business position. Migration authorization remains separate.");
            return result;
        }
        var domains = reviewed.GroupBy(r => Text(r, "areaId")).ToArray();
        var highlights = domains.OrderBy(g => g.Min(r => PriorityRank(Text(r, "priority"))))
            .ThenBy(g => g.Key, StringComparer.Ordinal)
            .Select(g => g.OrderBy(r => PriorityRank(Text(r, "priority"))).ThenBy(r => Text(r, "familyId"), StringComparer.Ordinal).First())
            .Take(3).ToArray();
        Add("Phase 2 business position", $"The reviewed scenarios below identify conditional business consequences and the next assessment decisions. They rely on the exact selected Phase 1 basis, not an enterprise-wide inventory. {reviewed.Length} of {all.Length} scoped scenario interpretations have designated business review; {reviewed.Count(r => Text(r, "scenarioState") == "qualified")} retain explicit qualifications. These are not approved loss estimates, migration readiness or permission to execute changes.");
        foreach (var row in highlights)
        {
            Add(AssessmentReportRenderer.DomainName(Text(row, "areaId")) + " — " + Text(row, "label"),
                "Conditional business consequence: " + Text(row, "businessImpact") + " Relevant confidentiality/trust lifetime: " + Text(row, "protectedInformationLifetime") +
                " Recommended assessment action: " + Text(row, "recommendation") + " Responsible function: " + Text(row, "owner") + ". Next decision: " + Text(row, "nextDecision"));
        }
        var priorities = reviewed.GroupBy(r => Text(r, "priority")).OrderBy(g => PriorityRank(g.Key))
            .Select(g => Human(g.Key) + ": " + g.Count());
        var rationales = reviewed.Select(r => Text(r, "confidenceBasis")).Where(s => s.Length > 0).Distinct(StringComparer.Ordinal).ToArray();
        Add("Why these decisions receive attention", string.Join("; ", priorities) + ". These are the reviewers' recorded assessment-attention choices, not numerical risk ratings. " +
            string.Join(" ", rationales) + " Highlights select one leading source class per domain, ordered by recorded priority; equal-priority ties use stable domain and source-family order, not an invented ranking.");
        var limits = reviewed.Select(r => Text(r, "analysisQualification", "qualification")).Concat(Limitations(conclusions))
            .Where(s => s.Length > 0).Distinct(StringComparer.Ordinal).ToArray();
        Add("Qualifications and material unknowns", string.Join(" ", limits) +
            $" The opening highlights {highlights.Length} of {domains.Length} reviewed domains. The complete domain register below retains every scenario, recommendation, owner and next decision, including lower-priority and unresolved work. {all.Length - reviewed.Length} scoped interpretations lack designated business review and cannot support a reviewed business conclusion.");
        return result;
    }

    private static int PriorityRank(string priority) => priority switch { "prioritize_review" => 0, "planned_review" => 1, "defer" => 2, _ => 3 };

    public static string RenderHtml(string reportId, string createdAt, JsonObject report)
    {
        var phase2 = Text(report, "phase") == "phase2";
        var workspace = Object(report["workspace"]);
        var conclusions = Rows(workspace, "consequences");
        var identities = Rows(workspace, "identities");
        var bundles = Rows(workspace, "bundles");
        var receipts = Rows(workspace, "receipts");
        var html = new StringBuilder("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">");
        html.Append("<title>").Append(E(Text(report, "title"))).Append("</title><style>").Append(Css).Append("</style></head><body><main>");
        html.Append("<header><p class=\"eyebrow\">PQC assessment work · Synthetic demonstration</p><h1>").Append(E(Text(report, "title")))
            .Append("</h1><p class=\"subtitle\">").Append(E(Text(Object(report["assessment"]), "name")))
            .Append("</p><p class=\"meta\">Generated ").Append(E(createdAt)).Append(" · Frozen assessment revision ")
            .Append(E(Value(Object(report["assessment"])["revision"]))).Append("</p></header>");
        html.Append("<aside class=\"notice\">Synthetic records and simulated assessment decisions only. This report establishes no the example enterprise estate facts, enterprise acceptance, NIST certification or permission to execute migrations.</aside>");
        html.Append("<nav aria-label=\"Report contents\"><a href=\"#position\">Conclusions</a> · <a href=\"#scope\">Scope</a> · <a href=\"#systems\">Systems</a> · <a href=\"#limitations\">Limitations</a> · <a href=\"#decisions\">Decisions</a> · <a href=\"#basis\">Handoff</a> · <a href=\"#appendix\">Supporting records</a></nav>");
        html.Append("<section id=\"position\"><h2>Executive position</h2>");
        foreach (var item in Rows(Object(report["narrative"]), "executiveSummary"))
            Paragraph(html, Text(item, "title"), Text(item, "body"));
        html.Append("</section><section id=\"scope\"><h2>Scope and evidence basis</h2>");
        var scope = Object(report["scope"]);
        Paragraph(html, "Purpose", Text(scope, "objective"));
        Paragraph(html, "This cycle", Text(scope, "cycleGoal"));
        Paragraph(html, "Handling boundary", Text(scope, "handling"));
        html.Append("<p>").Append(E(Text(workspace, "populationBasis"))).Append(" Receipt, technical review, evidence admission and report acceptance are different achievements.</p>");
        if (workspace["populationStatement"] is JsonValue statement) html.Append("<p>").Append(E(statement.ToString())).Append("</p>");
        html.Append("<p class=\"meta\">Evidence strength remains explicit: attributed statement; examined documentation/configuration; runtime observation; independently exercised verification. Synthetic modeled observations do not prove that an enterprise endpoint was contacted.</p></section>");

        var coverage=Rows(report,"coverageRows");
        if(coverage.Length>0)
        {
            html.Append("<section id=\"domains\"><h2>Discovery-domain positions</h2><p>Each domain identifies the selected source classes and admitted record counts. These are not enterprise population percentages.</p>");
            foreach(var domain in coverage.GroupBy(r=>Text(r,"areaId")).OrderBy(g=>g.Key,StringComparer.Ordinal))
            {
                html.Append("<article class=\"record\"><h3>").Append(E(AssessmentReportRenderer.DomainName(domain.Key))).Append("</h3>");
                foreach(var row in domain) Paragraph(html,Text(row,"name"),Value(row["observations"])+" admitted record(s); "+Human(Text(row,"sourceState"))+"; "+Human(Text(row,"achievedDepth"))+" depth.");
                html.Append("</article>");
            }
            html.Append("</section>");
        }

        html.Append("<section id=\"systems\"><h2>Products, deployments and relationships</h2>");
        if (identities.Length == 0) html.Append("<p>No identity relationships have been reviewed. Product names in a returned questionnaire are reported assertions, not a verified inventory.</p>");
        foreach (var group in identities.GroupBy(i => Text(i, "canonicalId").Length > 0 ? Text(i, "canonicalId") : Text(i, "productId")))
        {
            var identity = group.First();
            html.Append("<article class=\"record\"><h3>").Append(E(Text(identity, "label", "canonicalId", "productId"))).Append("</h3>");
            Paragraph(html, "Identity decision", Human(Text(identity, "decision")));
            Paragraph(html, "Application or service", Text(identity, "applicationService"));
            Paragraph(html, "Responsible function", Text(identity, "team"));
            Paragraph(html, "Basis and limits", Text(identity, "rationale"));
            html.Append("<p class=\"meta\">").Append(group.Count()).Append(" retained reported-row reference(s) linked to this identity. Source assertions and decision revisions remain in the assessment history.</p>");
            html.Append("</article>");
        }
        html.Append("<p>Evidence-producing systems remain separate from the deployments they describe. A shared name alone is not proof that two records identify the same system.</p></section>");

        html.Append("<section id=\"findings\"><h2>").Append(phase2 ? "Risk scenarios and recommendations" : "Evidence-backed current-state conclusions").Append("</h2>");
        if (conclusions.Length == 0) html.Append("<p>No material conclusion has been recorded. Do not infer low exposure, source readiness or assessment completion from this absence.</p>");
        if(phase2) html.Append("<p>The current-state basis is retained in the exact Phase 1 report selected below. The domain analyses distinguish reviewed business statements from technical observations; neither constitutes enterprise risk acceptance.</p>");
        foreach (var conclusion in phase2?Array.Empty<JsonObject>():conclusions)
        {
            var deployment = identities.FirstOrDefault(i => Text(i, "productId") == Text(conclusion, "productId"));
            var sourceFamily = Text(receipts.FirstOrDefault(r => Text(r, "requestId") == Text(conclusion, "requestId")) ?? new JsonObject(), "familyId");
            var sourceClass = Text(coverage.FirstOrDefault(r => Text(r, "familyId") == sourceFamily) ?? new JsonObject(), "name");
            var cohortLabel = sourceClass.Length > 0 ? sourceClass + " · selected cohort" : "Selected cohort";
            html.Append("<article class=\"finding\"><h3>").Append(E(deployment is null ? cohortLabel : Text(deployment, "label"))).Append("</h3>");
            Paragraph(html, "Current-state conclusion", Text(conclusion, "phase1Conclusion", "conclusion"));
            Paragraph(html, "Evidence adequacy", Text(conclusion, "confidence"));
            Paragraph(html, "Cryptographic purpose", Human(Text(conclusion, "cryptographicPurpose")));
            Paragraph(html, "Qualification / limitation", Text(conclusion, "limitation"));
            if (phase2)
            {
                Paragraph(html, "Recorded business consequence", Text(conclusion, "phase2Consequence", "businessImpact"));
                Paragraph(html, "Confidentiality or trust lifetime", Text(conclusion, "lifetime"));
                Paragraph(html, "Business review status", Text(conclusion, "businessReviewStatus"));
                html.Append("<p class=\"meta\">Business statements require the designated business review and Phase 2 disposition. A technical review alone does not approve a business consequence or a lifetime assumption.</p>");
            }
            Paragraph(html, "Responsible function", Text(conclusion, "responsibleFunction"));
            Paragraph(html, "Next decision", Text(conclusion, "nextDecision"));
            html.Append("<p class=\"meta\">Migration readiness is not qualified by this assessment. Key establishment and authentication remain distinct cryptographic uses.</p></article>");
        }
        if (phase2 && Rows(report, "scenarioRows").Length > 0)
        {
            html.Append("<h3>Designated Phase 2 business review by domain</h3>");
            foreach (var domain in Rows(report,"scenarioRows").GroupBy(r=>Text(r,"areaId")).OrderBy(g=>g.Key,StringComparer.Ordinal))
            {
                html.Append("<section class=\"domain-analysis\"><h3>").Append(E(AssessmentReportRenderer.DomainName(domain.Key))).Append("</h3>");
                // Reuse genuinely shared business context without repeating the
                // lifetime/impact narrative for every family. Distinct family
                // scenario, action, confidence, priority, rationale and review remain visible below.
                foreach(var interpretation in domain.GroupBy(r=>string.Join("\u001f",new[]{"businessImpact","protectedInformation","protectedInformationLifetime","businessStatementBy","businessStatementDate","businessStatementBasis","compatibilityConstraints","vendorConstraints","operationalConstraints","owner"}.Select(k=>Text(r,k)))))
                {
                    var row=interpretation.First();
                    html.Append("<article class=\"record\">");
                    Paragraph(html,"Applies to source classes",string.Join("; ",interpretation.Select(r=>Text(r,"label"))));
                    Paragraph(html,"Protected information",Text(row,"protectedInformation"));
                    Paragraph(html,"Confidentiality / trust lifetime",Text(row,"protectedInformationLifetime"));
                    Paragraph(html,"Business statement",Text(row,"businessStatementBy")+" · "+Text(row,"businessStatementDate")+". "+Text(row,"businessStatementBasis"));
                    Paragraph(html, "Business impact", Text(row, "businessImpact"));
                    Paragraph(html,"Compatibility constraints",Text(row,"compatibilityConstraints"));
                    Paragraph(html,"Vendor constraints",Text(row,"vendorConstraints"));
                    Paragraph(html,"Operational constraints",Text(row,"operationalConstraints"));
                    Paragraph(html,"Responsible function",Text(row,"owner"));
                    foreach(var reviewed in interpretation)
                    {
                        Paragraph(html,Text(reviewed,"label")+" scenario",Text(reviewed,"scenario"));
                        Paragraph(html,Text(reviewed,"label")+" action",Text(reviewed,"recommendation"));
                        Paragraph(html,Text(reviewed,"label")+" next decision",Text(reviewed,"nextDecision"));
                        Paragraph(html,Text(reviewed,"label")+" assessment","Attention: "+Human(Text(reviewed,"priority"))+". Confidence: "+Human(Text(reviewed,"confidence"))+". Rationale: "+Text(reviewed,"confidenceBasis"));
                        Paragraph(html,Text(reviewed,"label")+" review",Human(Text(reviewed,"scenarioState"))+" by "+Text(reviewed,"businessReviewedBy")+"; "+Text(reviewed,"analysisQualification","qualification"));
                    }
                    html.Append("</article>");
                }
                html.Append("</section>");
            }
        }
        html.Append("</section><section id=\"limitations\"><h2>Conflicts, gaps and permitted reliance</h2>");
        if (Rows(workspace, "pendingBindings").Length + Rows(workspace, "pendingConsequences").Length > 0)
        {
            html.Append("<aside class=\"notice\">An identity correction requires targeted re-review. Affected source bindings and conclusions are excluded from current reliance until their designated review and admission are recorded. Earlier reports retain their original snapshots.</aside>");
            List(html, Rows(workspace, "pendingBindings").Select(b => Text(b, "reason")));
        }
        List(html, Limitations(conclusions).DefaultIfEmpty("No specific limitation has yet been dispositioned. That is not evidence that no limitation exists."));
        List(html, new[] {
            "The enterprise population is unknown. Examined records cannot establish enterprise completeness.",
            "Configuration describes a setting, not every negotiated connection. A conflicting observation requires scope, date and endpoint review; it does not automatically prove a downgrade or an inaccurate respondent.",
            "A blocked source remains unexamined. Questionnaire testimony may establish a reported system or responsible route, not its cryptographic behavior.",
            "Missing documentation is not proof that no policy exists. A proposed standard is not an adopted requirement." });
        html.Append("</section><section id=\"decisions\"><h2>Decisions and next responsible functions</h2>");
        foreach (var conclusion in conclusions.DistinctBy(c => (Text(c, "responsibleFunction"), Text(c, "nextDecision"))))
            Paragraph(html, Text(conclusion, "responsibleFunction"), Text(conclusion, "nextDecision"));
        if (conclusions.Length == 0) Paragraph(html, "Assessment lead", "Review the received information, establish identity relationships and arrange a permitted supporting-information route.");
        html.Append("<p>Dates are agreed in the work queue; this report does not invent commitments. Recording an assessment decision does not authorize collection, standards adoption, risk acceptance or remediation.</p></section>");
        html.Append("<section id=\"basis\"><h2>").Append(phase2 ? "Explicit Phase 1 basis" : "Phase 2 handoff").Append("</h2>");
        var selected = Object(Object(report["manifest"])["selectedPhase1"]);
        Paragraph(html, phase2 ? "Selected input" : "Permitted next use", phase2
            ? Text(selected, "reportId") + ". This exact input was selected; a newer report cannot replace it automatically."
            : "Use this exact report and its retained qualifications as a candidate Phase 2 input. Formal reliance requires the designated handoff decision.");
        html.Append("<p>Unsupported conclusions remain excluded. Later information creates a new review and report revision; it does not rewrite this snapshot.</p></section>");
        html.Append("<details id=\"appendix\"><summary>Supporting records and provenance</summary><p>These records explain the basis of the report. Technical admission and material conclusions are distinct from attributed questionnaire answers.</p>");
        foreach (var bundle in bundles)
        {
            html.Append("<h3>").Append(E(Text(bundle, "sourceLabel"))).Append("</h3>");
            foreach (var observation in Rows(bundle, "observations"))
            {
                html.Append("<article class=\"record\"><h4>").Append(E(Text(observation, "label", "nativeId", "id", "observation_id"))).Append("</h4>");
                foreach (var (key, label) in new[] { ("basis", "Evidence basis"), ("evidenceBasis", "Evidence basis"), ("evidence_basis", "Evidence basis"), ("observedAt", "Source observation date"), ("observed_at", "Source observation date"), ("collectedAt", "Collected at"), ("purpose", "Cryptographic purpose"), ("algorithm", "Recorded algorithm"), ("hostname", "Endpoint"), ("keyExchange", "Key establishment"), ("authentication", "Authentication signature"), ("signatureAlgorithm", "Certificate signature"), ("name", "Application"), ("serviceId", "Reported service"), ("owner", "Reported owner"), ("sourceSystemId", "Source identity"), ("supports", "Can support"), ("cannotEstablish", "Cannot establish") })
                    if (Text(observation, key).Length > 0) Paragraph(html, label, Human(Text(observation, key)));
                var facts = Object(observation["facts"]);
                foreach (var fact in facts) Paragraph(html, Human(fact.Key), Value(fact.Value));
                foreach (var key in new[] { "applicationId", "certificateId" })
                    if (Text(observation, key).Length > 0) Paragraph(html, key == "applicationId" ? "Native application reference" : "Native certificate reference", Text(observation, key));
                html.Append("</article>");
            }
        }
        foreach (var receipt in receipts)
        {
            html.Append("<h3>Returned information: ").Append(E(Text(receipt, "filename", "familyId"))).Append("</h3>");
            Paragraph(html, "Declared respondent (unverified)", Text(receipt, "respondent"));
            Paragraph(html, "Declared scope", Text(receipt, "scope"));
            Paragraph(html, "Receipt state", Human(Text(receipt, "status")));
            if (receipt["answers"] is JsonArray answers)
                foreach (var answer in answers.OfType<JsonObject>())
                    Paragraph(html, Text(answer, "questionId", "id") + " · " + Human(Text(answer, "status")), Text(answer, "text"));
        }
        Paragraph(html, "Report identifier", reportId);
        Paragraph(html, "Workspace input fingerprint", Text(workspace, "inputFingerprint"));
        html.Append("</details><section id=\"references\"><h2>Guidance and applicability</h2><p>The workflow is project-defined. NIST guidance informs the approach; it does not certify or approve this application.</p><ul>");
        foreach (var reference in Rows(report, "references"))
        {
            var url = Text(reference, "url");
            html.Append("<li>");
            if (Uri.TryCreate(url, UriKind.Absolute, out var uri) && uri.Scheme == "https" && (uri.Host == "nist.gov" || uri.Host.EndsWith(".nist.gov", StringComparison.Ordinal)))
                html.Append("<a href=\"").Append(E(url)).Append("\">").Append(E(Text(reference, "title"))).Append("</a>");
            else html.Append(E(Text(reference, "title")));
            html.Append(" — ").Append(E(Text(reference, "status"))).Append("</li>");
        }
        html.Append("</ul></section><footer><p>Use Print → Save as PDF for a fixed reading copy. Keep the report identifier with exported copies. Template: ").Append(E(TemplateVersion)).Append(".</p></footer></main></body></html>");
        return html.ToString();
    }

    private static string ObservationId(JsonObject row) => Text(row, "id", "observationId", "observation_id");
    private static IEnumerable<string> Limitations(JsonObject[] rows) => rows.Select(c => Text(c, "limitation")).Where(s => s.Length > 0).Distinct(StringComparer.Ordinal);
    private static JsonObject Object(JsonNode? node) => node as JsonObject ?? new JsonObject();
    private static JsonObject[] Rows(JsonObject node, string key) => (node[key] as JsonArray)?.OfType<JsonObject>().ToArray() ?? [];
    private static JsonArray Copy(IEnumerable<JsonObject> rows) => new(rows.Select(r => r.DeepClone()).ToArray());
    private static JsonArray Strings(IEnumerable<string> values) => new(values.Where(s => s.Length > 0).Distinct(StringComparer.Ordinal).Select(s => (JsonNode?)JsonValue.Create(s)).ToArray());
    private static string Text(JsonObject node, params string[] keys) => keys.Select(key => node[key] is JsonValue value ? value.ToString() : "").FirstOrDefault(value => !string.IsNullOrWhiteSpace(value)) ?? "";
    private static string Value(JsonNode? node) => node switch
    {
        JsonObject fields => fields.Count == 0 ? "None recorded" : string.Join("; ", fields.Select(field => Human(field.Key) + ": " + Value(field.Value))),
        JsonArray values => values.Count == 0 ? "None recorded" : string.Join("; ", values.Select(Value)),
        JsonValue value => value.ToString(),
        _ => "Not established"
    };
    private static string E(string text) => WebUtility.HtmlEncode(text);
    private static string Human(string text) => text.Replace('_', ' ');
    private static void Paragraph(StringBuilder html, string title, string body) => html.Append("<p><strong>").Append(E(title.Length == 0 ? "Not assigned" : title)).Append(":</strong> ").Append(E(body.Length == 0 ? "Not established; retain this limitation until reviewed." : body)).Append("</p>");
    private static void List(StringBuilder html, IEnumerable<string> items) { html.Append("<ul>"); foreach (var item in items) html.Append("<li>").Append(E(item)).Append("</li>"); html.Append("</ul>"); }
    private const string Css = """
        :root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#eef3f6;color:#172d3b;font:16px/1.58 Arial,sans-serif}main{max-width:1050px;margin:30px auto;padding:44px 58px;background:white;border:1px solid #d4e0e6}header{border-bottom:3px solid #167e83;padding-bottom:22px}.eyebrow{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#326773;font-weight:700}h1{font-size:34px;line-height:1.15;margin:.4em 0}h2{font-size:23px;line-height:1.25;margin:0 0 18px;color:#123b4f}h3{font-size:18px;line-height:1.35}h4{font-size:16px}.subtitle{font-size:19px}.meta,footer{font-size:12px;color:#49616b}.notice{border-left:4px solid #b67819;background:#fff6e8;padding:14px 18px;margin:24px 0}nav{font-size:14px;line-height:2;border-bottom:1px solid #d4e0e6;padding-bottom:20px}a{color:#126773;text-decoration:underline}section{margin-top:32px}p{margin:.6em 0}li{margin:.5em 0}.record{border:1px solid #d7e3e8;padding:16px 20px;margin:16px 0}.finding{border-left:4px solid #167e83;background:#f3f8fa;padding:18px 22px;margin:18px 0;break-inside:avoid}details{margin:32px 0;padding:18px;border:1px solid #cad8df}summary{font-size:18px;font-weight:700;cursor:pointer}footer{border-top:1px solid #ccdbe2;margin-top:32px;padding-top:16px}p,li{overflow-wrap:anywhere}@media(max-width:650px){main{margin:0;padding:22px;border:0}h1{font-size:27px}h2{font-size:21px}.record,.finding{padding:14px}}@media print{@page{size:A4;margin:18mm}body{background:white;font-size:10.5pt}main{max-width:none;border:0;margin:0;padding:0}h1{font-size:24pt}h2{font-size:16pt}h3{font-size:12pt}header{padding-bottom:10px}section{margin-top:22px}nav{display:none}.record,.finding{break-inside:avoid}h2,h3,h4{break-after:avoid}details{display:block}details>*{display:block}.notice{font-size:9pt}a{color:inherit}footer{font-size:8pt}}
        """;
}
