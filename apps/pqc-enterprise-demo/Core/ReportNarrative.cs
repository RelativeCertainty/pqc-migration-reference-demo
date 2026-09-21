using System.Globalization;
using System.Net;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

/// <summary>
/// Deterministic, evidence-bounded report copy over the same C# analysis used by
/// the application. It does not introduce another risk classifier or infer
/// business ownership, product support, human acceptance, or completed migration.
/// </summary>
public static class ReportNarrative
{
    public static string RenderHtml(JsonObject report)
    {
        var content = report["content"]!.AsObject();
        var narrative = content["narrative"]!.AsObject();
        var analysis = content["analysis"]!.AsObject();
        var metadata = report["metadata"]!.AsObject();
        var baseline = content["baseline"]!.AsObject();
        var title = Text(content, "title");
        var html = new StringBuilder("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>");
        html.Append(E(title)).Append("</title><style>").Append(ReportCss).Append("</style></head><body>");
        html.Append("<header class=\"report-header\"><div class=\"page-width\"><p class=\"eyebrow\">Enterprise PQC · Synthetic assessment draft</p><h1>").Append(E(title)).Append("</h1>");
        html.Append("<p class=\"header-context\">Post-quantum cryptography: evidence, business meaning and the next accountable decision.</p></div></header><main class=\"page-width\">");
        html.Append("<section class=\"executive\" aria-labelledby=\"executive-title\"><p class=\"eyebrow\">For decision-makers</p><h2 id=\"executive-title\">Executive summary</h2>");
        foreach (var point in Rows(narrative, "executiveSummary"))
            html.Append("<article class=\"executive-point\"><h3>").Append(E(Text(point, "title"))).Append("</h3><p>").Append(E(Text(point, "body"))).Append("</p></article>");
        html.Append("</section><aside class=\"status-note\"><strong>Synthetic draft · not accepted.</strong> As of ").Append(E(Text(baseline, "asOf")));
        html.Append(". No enterprise coverage, approved risk position, qualified integration or authority to execute migration is claimed.</aside>");
        html.Append("<nav aria-label=\"Report sections\" class=\"contents\"><strong>In this report</strong><ol>");
        foreach (var section in Rows(narrative, "sections")) html.Append("<li><a href=\"#").Append(E(Text(section, "id"))).Append("\">").Append(E(Text(section, "title"))).Append("</a></li>");
        html.Append("<li><a href=\"#proposed-actions\">Proposed actions and accountable routes</a></li><li><a href=\"#decision-questions\">Questions for the review</a></li><li><a href=\"#appendices\">Technical and evidence appendices</a></li></ol></nav>");
        var findingIndex = Rows(analysis, "findings").ToDictionary(f => Text(f, "id"), StringComparer.Ordinal);
        foreach (var section in Rows(narrative, "sections"))
        {
            html.Append("<section class=\"narrative-section\" id=\"").Append(E(Text(section, "id"))).Append("\"><h2>").Append(E(Text(section, "title"))).Append("</h2>");
            html.Append("<p class=\"section-conclusion\">").Append(E(Text(section, "summary"))).Append("</p>");
            foreach (var paragraph in Strings(section, "paragraphs")) html.Append("<p>").Append(E(paragraph)).Append("</p>");
            var linkedFindings = Strings(section, "findingIds").Where(findingIndex.ContainsKey).ToArray();
            if (linkedFindings.Length > 0)
            {
                html.Append("<p class=\"linked-evidence\">Supporting findings: ");
                for (var i = 0; i < linkedFindings.Length; i++)
                {
                    if (i > 0) html.Append(" · ");
                    html.Append("<a href=\"#finding-").Append(E(linkedFindings[i])).Append("\">").Append(E(Text(findingIndex[linkedFindings[i]], "title"))).Append("</a>");
                }
                html.Append("</p>");
            }
            html.Append("</section>");
        }
        html.Append("<section class=\"narrative-section\" id=\"proposed-actions\"><h2>Proposed actions and accountable routes</h2><p class=\"section-conclusion\">These are proposed investigations and review decisions, not approved implementation work.</p><ol class=\"actions\">");
        foreach (var step in Rows(narrative, "nextSteps"))
        {
            html.Append("<li><h3>").Append(E(Text(step, "title"))).Append("</h3><p><strong>Accountable route:</strong> ").Append(E(Text(step, "owner"))).Append("</p>");
            html.Append("<p><strong>Next action:</strong> ").Append(E(Text(step, "action"))).Append("</p><p><strong>Decision needed:</strong> ").Append(E(Text(step, "decisionRequired"))).Append("</p>");
            html.Append("<p><strong>Why this matters:</strong> ").Append(E(Text(step, "consequence"))).Append("</p></li>");
        }
        html.Append("</ol></section><section class=\"narrative-section\" id=\"decision-questions\"><h2>Questions for the review</h2>");
        List(html, Strings(narrative, "questions"));
        html.Append("</section><section class=\"narrative-section\"><h2>Limits on interpretation and use</h2>");
        List(html, Strings(narrative, "caveats"));
        html.Append("</section><section class=\"appendices\" id=\"appendices\"><h2>Technical and evidence appendices</h2><p>The narrative above is the report. The material below makes it auditable: detailed findings, input identity, method references and the complete retained records. Expand the relevant appendix for inspection; the JSON export preserves every field.</p>");
        html.Append("<details open><summary>A. Material findings and their evidence links</summary>");
        var referenced = Rows(narrative, "sections").SelectMany(s => Strings(s, "findingIds")).Distinct(StringComparer.Ordinal).Where(findingIndex.ContainsKey).ToList();
        foreach (var id in referenced)
        {
            var finding = findingIndex[id];
            html.Append("<article class=\"finding\" id=\"finding-").Append(E(id)).Append("\"><p class=\"eyebrow\">Illustrative priority: ").Append(E(Human(Text(finding, "priority")))).Append("</p><h3>").Append(E(Text(finding, "title"))).Append("</h3>");
            html.Append("<p><strong>Subject:</strong> ").Append(E(Text(finding, "subjectLabel"))).Append("</p>");
            Pair(html, "Observed condition", Text(finding, "observation"));
            Pair(html, "Business / technical implication", Text(finding, "implication"));
            Pair(html, "Priority rationale", Text(finding, "priorityRationale"));
            Pair(html, "Proposed treatment direction", Text(finding, "recommendation"));
            Pair(html, "Owner context", Owner(finding));
            Pair(html, "Evidence state / confidence", $"{Human(Text(finding, "evidenceState"))} / {Human(Text(finding, "confidence"))}");
            Pair(html, "Exposure / readiness", $"{Human(Text(finding, "exposure"))} / {Human(Text(finding, "readiness"))}");
            html.Append("<details><summary>Inspect evidence identifiers</summary><p class=\"reference-list\"><strong>Subject reference:</strong> <code>").Append(E(Text(finding, "subjectId"))).Append("</code></p>");
            html.Append("<p class=\"reference-list\"><strong>Observation references:</strong> ").Append(E(string.Join("; ", Strings(finding, "observationRefs")))).Append("</p></details></article>");
        }
        html.Append("</details><details><summary>B. Input identity, Phase 1 binding and review snapshot</summary><dl class=\"identity\">");
        Definition(html, "Report ID", Text(metadata, "id"));
        Definition(html, "Stored JSON content SHA-256", Text(metadata, "contentSha256"));
        Definition(html, "Baseline ID", Text(baseline, "baselineId"));
        Definition(html, "Fixture SHA-256", Text(baseline, "inputSha256"));
        Definition(html, "Analysis version", Text(content, "analysisVersion"));
        Definition(html, "Acceptance", "Unaccepted synthetic development evidence");
        html.Append("</dl><p>The report hash covers the stored compact report-content JSON encoded as UTF-8. It does not cover the API response wrapper or this rendered HTML document.</p>");
        if (content["phase1Input"] is JsonObject phase1) JsonDetail(html, "Bound Phase 1 input", phase1);
        JsonDetail(html, "Frozen local analyst actions (not risk acceptance)", content["actionRecords"]);
        JsonDetail(html, "Source and custody provenance", content["provenance"]);
        html.Append("</details><details><summary>C. Analysis method and primary references</summary>");
        var method = analysis["method"]!.AsObject();
        Pair(html, "Analysis method", $"{Text(method, "id")} / {Text(method, "version")} / {Text(method, "status")}");
        Pair(html, "Priority interpretation", Text(method, "priorityMeaning"));
        var preparation = content["method"] as JsonObject;
        if (preparation is not null)
        {
            Pair(html, "Preparation method", $"{Text(preparation, "id")} / {Text(preparation, "version")} / {Text(preparation, "status")}");
            html.Append("<ul>");
            foreach (var reference in Rows(preparation, "references"))
            {
                html.Append("<li>");
                var url = Text(reference, "url");
                if (Uri.TryCreate(url, UriKind.Absolute, out var uri) && uri.Scheme == "https")
                    html.Append("<a rel=\"noreferrer\" href=\"").Append(E(url)).Append("\">").Append(E(Text(reference, "title"))).Append("</a>");
                else html.Append(E(Text(reference, "title")));
                html.Append(" — ").Append(E(Text(reference, "supports"))).Append("</li>");
            }
            html.Append("</ul>");
            JsonDetail(html, "Complete preparation-method rules", preparation);
        }
        html.Append("</details><details><summary>D. Full analysis and normalized record appendix</summary><p>These records are retained for traceability. They are not a substitute for the executive findings and proposed decisions above. The JSON download contains the complete immutable snapshot.</p>");
        foreach (var field in new[] { "analysis", "summary", "sourceProfiles", "estateAreas", "inventory", "observations", "dependencies", "riskReviews", "contextReviews", "migrationCandidates", "limitations" })
            if (content[field] is not null) JsonDetail(html, Human(field), content[field]);
        html.Append("</details></section><footer><p>Generated by the C# report-projection Worker from an immutable synthetic evidence baseline and frozen local review context. No human acceptance, independent migration verification, enterprise product approval or source-system execution authority is recorded.</p><p>Use the JSON export for complete machine-readable provenance; use this narrative for discussion and factual review.</p></footer></main></body></html>");
        return html.ToString();
    }

    private const string ReportCss = """
        :root{color-scheme:light;font-family:Arial,Helvetica,sans-serif;color:#1d2c3a;background:#edf1f4}
        *{box-sizing:border-box}body{margin:0;font-size:16px;line-height:1.65}.page-width{width:min(100% - 48px,1040px);margin:0 auto}
        .report-header{background:#112838;color:#fff;border-bottom:5px solid #11857d;padding:42px 0 36px}.eyebrow{text-transform:uppercase;letter-spacing:.13em;font-size:.74rem;font-weight:700;margin:0 0 10px}.report-header .eyebrow{color:#a4d3d1}h1{font-size:2.55rem;line-height:1.18;letter-spacing:-.035em;margin:0;max-width:26ch}.header-context{margin:14px 0 0;color:#d1dee5;max-width:70ch}
        main.page-width{background:#fff;padding:40px 46px 30px;margin-bottom:32px}h2{font-size:1.55rem;line-height:1.3;letter-spacing:-.02em;margin:0 0 16px;color:#112838}h3{font-size:1.05rem;line-height:1.4;margin:0 0 8px}p{margin:0 0 16px;max-width:94ch}a{color:#075f69;text-decoration:underline;text-underline-offset:3px}a:hover{color:#003f46}a:focus-visible,summary:focus-visible{outline:3px solid #a76600;outline-offset:4px}
        .executive{border-bottom:1px solid #ccd8df;padding-bottom:12px}.executive .eyebrow{color:#146e69}.executive-point{border-left:3px solid #168980;padding:0 0 0 18px;margin:22px 0}.executive-point p{margin-bottom:0}.status-note{font-size:.88rem;background:#fbf3df;color:#5d470c;padding:14px 18px;margin:26px 0;border:1px solid #ddc990}.contents{font-size:.92rem;padding:16px 0 24px;border-bottom:1px solid #dbe3e8}.contents ol{columns:2;column-gap:40px;padding-left:24px;margin-bottom:0}.contents li{break-inside:avoid;padding:4px 0}.narrative-section{margin:36px 0 0}.section-conclusion{font-size:1.04rem;font-weight:700;color:#345463}.linked-evidence{background:#f3f7f9;border-left:2px solid #9ab1be;padding:12px 16px;font-size:.84rem}.actions{padding-left:25px}.actions>li{padding:0 0 22px 8px;margin:0 0 22px;border-bottom:1px solid #dae3e9}.actions p{font-size:.93rem;margin:8px 0}.appendices{border-top:2px solid #254e61;margin-top:44px;padding-top:28px}.appendices>p{font-size:.9rem;color:#45606f}details{border:1px solid #cbd8df;padding:0;margin:14px 0}summary{font-weight:700;background:#f3f6f8;padding:14px 18px;cursor:pointer}details>p,details>dl,details>ul,details>h3{margin:18px}details>details{margin:18px}.finding{padding:22px 20px;border-bottom:1px solid #d9e2e8;break-inside:avoid}.finding:last-child{border-bottom:0}.finding .eyebrow{color:#456476}.finding p{font-size:.88rem;margin-bottom:10px}.reference-list,code{overflow-wrap:anywhere;font-size:.79rem}.identity{display:grid;grid-template-columns:180px minmax(0,1fr);gap:7px 18px;font-size:.83rem}.identity dt{font-weight:700}.identity dd{margin:0;overflow-wrap:anywhere}pre{font:12px/1.55 ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere;padding:16px;max-height:450px;overflow:auto;background:#f8fafb;margin:0}footer{margin-top:42px;border-top:1px solid #d9e2e8;padding-top:18px;color:#526a78;font-size:.8rem}footer p{max-width:none}
        @media(max-width:650px){.page-width{width:100%}.report-header{padding:26px 22px}main.page-width{padding:26px 22px}.contents ol{columns:1}h1{font-size:2rem}.identity{display:block}.identity dd{margin-bottom:12px}}
        @media print{@page{margin:18mm}body{background:#fff;font-size:10.5pt;line-height:1.5}.page-width{width:100%;max-width:none}.report-header{padding:18px 20px;-webkit-print-color-adjust:exact;print-color-adjust:exact}main.page-width{padding:24px 0 0;margin:0}h1{font-size:25pt}h2{font-size:16pt}h2,h3,summary{break-after:avoid}.executive-point,.actions>li,.status-note{break-inside:avoid}.narrative-section{margin-top:25px}.contents{display:none}pre{max-height:none;overflow:visible}.appendices>details:not([open]){display:none}.appendices>details[open]{border:0}.finding{padding:16px 0}.identity{font-size:9pt}a{color:inherit}.reference-list{font-size:8pt}}
        """;

    public static JsonObject Build(string phase, JsonObject content)
    {
        var analysis = content["analysis"]!.AsObject();
        var summary = analysis["summary"]!.AsObject();
        // Preserve the analysis engine's declared ordering. The narrative layer
        // must not create a second prioritization method.
        var findings = Rows(analysis, "findings");
        var material = findings.Where(f => Text(f, "priority") != "context_only").Take(5).ToList();
        var sections = new JsonArray();
        var executive = new JsonArray();
        var actions = Rows(content, "actionRecords");
        var evidenceFirst = CountPriority(summary, "resolve_evidence");
        var reviewFirst = CountPriority(summary, "prioritize_review");
        var totalSubjects = Number(summary, "assets");
        var observations = Number(summary, "observations");
        var uses = Number(summary, "cryptographicUses");
        var families = Number(summary, "sourceFamilies");
        var areas = Number(summary, "estateAreas");
        var stale = Number(summary, "staleAssets");
        var disputed = Number(summary, "disputedAssets");
        var contextOnly = Number(summary, "contextOnlyAssets");
        var dependencyCount = (content["dependencies"] as JsonArray)?.Count ?? 0;
        var reviewStates = actions.GroupBy(a => Text(a, "status", "unknown")).OrderBy(g => g.Key, StringComparer.Ordinal)
            .Select(g => $"{g.Count().ToString(CultureInfo.InvariantCulture)} {Human(g.Key)}").ToArray();
        var reviewContext = actions.Count == 0
            ? "No local analyst dispositions are recorded in this report snapshot. This is an analysis draft awaiting review, not an accepted assessment."
            : $"This report freezes {actions.Count.ToString(CultureInfo.InvariantCulture)} local review records ({string.Join("; ", reviewStates)}). A reviewed or deferred item is only a local analyst disposition: it is not independent verification, risk acceptance, or authority to change a source system.";
        var scope = $"The bounded synthetic estate contains {totalSubjects} subjects, {observations} attributable observations and {uses} cryptographic-use review records across {families} source families and {areas} estate areas. These are counts inside this fixture, not measurements of a real enterprise or proof that all deployed systems have been discovered.";
        var quality = $"The source snapshot contains {stale} subjects with stale-evidence limitations and {disputed} subjects with disputed evidence. These categories can overlap. Evidence needing reconciliation stays visible and does not become a verified fact merely because it appears in a report.";
        var method = analysis["method"]!.AsObject();
        var methodExplanation = $"The C# analysis method {Text(method, "id")} version {Text(method, "version")} derives findings and investigation priorities from the persisted baseline. {Text(method, "priorityMeaning", "Priority expresses relative attention for review, not an approved risk score.")} The preparation method and its references are retained separately in the technical appendix.";

        if (phase == "phase1")
        {
            executive.Add(Point("A reviewable map exists; enterprise completeness is still unknown", scope));
            executive.Add(Point("Evidence quality determines how far the conclusions can go", quality));
            executive.Add(Point("The next gate is a factual review and a qualified handoff", "Use this report to confirm the scope, reconcile material findings and name the functions that can resolve missing ownership or source evidence. Phase 1 produces a traceable current-state baseline; it does not assign final Phase 2 risk ratings or authorize remediation."));
            sections.Add(Section("scope-method", "Scope and assessment method", "This is a synthetic rehearsal of the current-state assessment deliverable.",
                [scope, "Observations, interpretations, findings and limitations are separate records. Collection routes are modeled as read-only, and technology names are recognition examples rather than approved enterprise selections.", methodExplanation]));
            sections.Add(Section("inventory-dependencies", "What the map establishes", "Cryptographic use is connected to the systems and relationships that give it meaning.",
                [$"The report retains {dependencyCount.ToString(CultureInfo.InvariantCulture)} dependency records and identifies {contextOnly} context-only subjects. An application, software package or vendor record can be relevant context without proving that a particular algorithm is active.",
                 "Key establishment, certificate or software signatures, data encryption and library capability are distinct uses. A hybrid key exchange does not prove post-quantum certificate authentication; a package inventory does not prove deployed cryptographic behavior.",
                 "The investigation view and evidence appendix retain the subject and observation references needed to challenge an interpretation and inspect the supporting source record."]));
            sections.Add(Section("material-findings", "Material current-state findings", "Start with the conditions that most affect the defensibility of the map.", FindingParagraphs(material.Take(3)), material.Take(3)));
            sections.Add(Section("business-context", "Business context and accountable routes", "The technical inventory becomes useful when owners can explain what each dependency protects.",
                ["Service ownership, criticality, information lifetime, affected relying parties and restoration requirements determine the meaning of a cryptographic observation. A missing value remains a question for the accountable function, not a value supplied by the report generator.",
                 "The linked business-impact scenarios below are evidence-based illustrations inside the synthetic model. They are not quantified enterprise loss estimates, binding regulatory interpretations or commitments by a named business owner.",
                 reviewContext], material.Where(f => Text(f, "impactId") != "").Take(3)));
            sections.Add(Section("limitations", "Limitations and conclusions that must wait", "Unresolved evidence reduces the permitted conclusion, not the visibility of the issue.",
                [quality, "No enterprise coverage percentage, approved risk score, production collection result or qualified commercial-product integration is claimed. Vendor statements, configured capability and observed behavior must retain their different evidence status.",
                 "Before relying on this baseline, reviewers must resolve material contradictions or explicitly document the remaining limitations and the scope of the permitted handoff."]));
            sections.Add(Section("phase2-handoff", "Controlled handoff to Phase 2", "The report is an input package for analysis, not an execution permit.",
                ["The Phase 2 input is the immutable inventory, dependency and evidence baseline together with its material findings, limitations, source provenance and recorded review state. The receiving risk method must be named and versioned.",
                 "The application binds a Phase 2 report to an actual persisted Phase 1 report and the same baseline. A newer narrative Phase 1 also binds the analysis version; a legacy snapshot is explicitly identified rather than silently rewritten.",
                 "Enterprise use still requires the designated assessment, technical and business reviewers to accept or qualify that input. This synthetic report records no such acceptance."]));
        }
        else
        {
            executive.Add(Point("The immediate priority is defensible investigation, not a risk-score claim",
                $"The analysis places {evidenceFirst} finding records in evidence resolution and {reviewFirst} in priority review. These are explainable review queues, not severity ratings or a declaration that other findings are safe. Each proposed priority remains tied to its evidence, business context and uncertainty."));
            executive.Add(material.Count == 0
                ? Point("No material conclusion is invented", "The current bounded analysis does not supply a material finding to summarize. Missing evidence and incomplete collection still require review; an empty queue is not proof of safety.")
                : Point(Text(material[0], "title"), $"{Text(material[0], "observation")} {Text(material[0], "implication")} Recommended next step: {Text(material[0], "recommendation")}"));
            executive.Add(Point("Business consequences and treatment remain subject to accountable review",
                "This draft connects technical conditions to protected information, dependent services and migration constraints where the synthetic evidence supports that relationship. Unknown ownership, lifecycle commitments and operational consequences remain decisions to resolve. A feasible upgrade does not mean that exposure has already decreased."));
            var phase1 = content["phase1Input"]!.AsObject();
            var legacy = Text(phase1, "schemaVersion") == "pqc.enterprise.report.v1";
            sections.Add(Section("input-method", "Phase 1 input and Phase 2 method", "Every conclusion is bounded by the input baseline and the analysis method used here.",
                [scope, $"This report is bound to persisted Phase 1 report {Text(phase1, "reportId")} from the same baseline. Its content hash is retained in the technical appendix. The input is unaccepted synthetic development evidence.",
                 legacy ? "Legacy input compatibility: the selected Phase 1 snapshot predates the narrative analysis feature. Its original content is preserved. Phase 2 derives the new analysis from the unchanged baseline; it does not claim that the legacy report contained these findings or a new analysis version."
                        : $"The Phase 1 input and this report use analysis version {Text(content, "analysisVersion")}. Changing that version requires a new compatible Phase 1 report before a new Phase 2 report can be generated.", methodExplanation]));
            sections.Add(Section("technical-exposure", "Technical exposure and information lifetime", "Evaluate the cryptographic protection role, not an asset-wide readiness label.",
                FindingParagraphs(material.Take(3)).Concat([
                    "A long-lived confidentiality or signature-trust requirement affects the scenario only when it is supported by an attributable data-lifetime record. Without that link, the report requests confirmation instead of inventing a store-now/decrypt-later impact or a retention period.",
                    "The scenario record retains the affected subject, technical basis and uncertainty. It does not assert a date for a cryptographically relevant quantum computer or predict an adversary's actions."
                ]), material.Take(3)));
            sections.Add(Section("business-impact", "Business-service and operational meaning", "Use dependency context to explain why the issue matters to the business.",
                LinkedParagraphs(analysis, "businessImpacts").Take(3).Concat([
                    "Availability, confidentiality, authenticity, restoration and relying-party compatibility are separate consequences. No financial loss, regulatory violation or service criticality is asserted without a corresponding evidence record.",
                    "A missing owner or service relationship is a routing decision: identify the accountable function and obtain the context before presenting a final impact assessment."
                ]), material.Where(f => Text(f, "impactId") != "").Take(3)));
            sections.Add(Section("readiness-vendors", "Library, vendor and migration constraints", "Exposure and readiness must remain independent assessments.",
                ["Software and library records can establish provenance, version and configured capability; they do not by themselves prove runtime use, commercial support, interoperability or successful migration. Vendor statements remain attributed claims until appropriately qualified.",
                 "Use the readiness and blocker records to identify the exact product/version, dependent clients, support evidence and verification needed next. Ease of implementation changes the work sequence, not the fact of current exposure.",
                 "The proposed treatment here is investigation, compatibility assessment or planning. Production change design, irreversible effects, ticket creation in an external provider and migration execution require separate authority."],
                material.Where(f => Text(f, "readiness") != "").Take(3)));
            sections.Add(Section("priority-treatment", "Explainable priorities and proposed treatment", "Resolve the evidence and decisions that control the next useful action.",
                [$"The analysis method places {evidenceFirst} findings into evidence resolution before reliance and {reviewFirst} into priority review. Counts are finding records, not unique assets, and no category is an approved enterprise risk rating.",
                 "For each material finding, the linked record exposes the observed condition, consequence rationale, proposed priority and its explanation, evidence state, accountable-owner context and recommended action. Owners can challenge any factor rather than accepting an opaque score.",
                 reviewContext], material));
            sections.Add(Section("decisions-lookahead", "Decisions and the implementation lookahead", "An assessment can prepare authorized work without authorizing it.",
                ["The risk lead and accountable business and technology functions must disposition the proposed priorities, confirm ownership, validate the method and record the limits of any reliance. Deferred work needs an explicit rationale; a local deferred status is not an approved exception.",
                 "A proposed Phase 3 would turn selected findings into immutable migration plans, compatibility cohorts, independent verification criteria and recovery designs. A separately authorized workflow could then mediate change through ServiceNow, Jira or another work surface while the application retains the canonical case and evidence model.",
                 "A proposed Phase 4 would organize qualified changes into bounded waves and continuing assurance. Closing a ticket is not proof of changed cryptographic behavior; a successful migration requires independently verified outcomes and the authorized closure criteria."]));
        }

        var nextSteps = new JsonArray();
        foreach (var finding in material.Take(4))
            nextSteps.Add(new JsonObject
            {
                ["title"] = Text(finding, "title"), ["owner"] = Owner(finding),
                ["action"] = Text(finding, "recommendation", "Obtain the missing source evidence and review the finding."),
                ["decisionRequired"] = "Confirm the accountable function, evidence route and scope of the proposed investigation.",
                ["consequence"] = Text(finding, "implication", "The dependent conclusion remains qualified until the evidence is reviewed.")
            });
        nextSteps.Add(new JsonObject
        {
            ["title"] = phase == "phase1" ? "Disposition the Phase 1 handoff" : "Disposition the risk review draft",
            ["owner"] = phase == "phase1" ? "Assessment lead and designated reviewers — assignment to be confirmed" : "Risk lead and accountable business/technology reviewers — assignment to be confirmed",
            ["action"] = "Review material findings, reconcile feedback and record acceptance or explicit limitations through the authorized governance route.",
            ["decisionRequired"] = "Name the acceptance authority and the permitted scope of reliance; this demo does not perform that acceptance.",
            ["consequence"] = "Without disposition, the report remains a draft and cannot be represented as an accepted enterprise position."
        });
        var questions = new JsonArray(Rows(analysis, "decisions").Take(5).Select(d => (JsonNode?)JsonValue.Create($"{Text(d, "title")}: {Text(d, "action", Text(d, "rationale"))}")).ToArray());
        if (questions.Count == 0) questions.Add("Which accountable function will review the input scope, evidence limitations and permitted next step?");
        return new JsonObject
        {
            ["executiveSummary"] = executive, ["sections"] = sections, ["nextSteps"] = nextSteps,
            ["questions"] = questions,
            ["caveats"] = new JsonArray(
                "All estate data and progress shown here are synthetic. Enterprise coverage, actual product compatibility and production readiness are unknown.",
                "Source observations, vendor/configuration claims, analysis inferences and independent verification must not be treated as interchangeable evidence.",
                "Relative priority is an illustrative order of attention, not an approved risk rating; migration readiness does not reduce existing exposure.",
                "Local analyst notes and dispositions do not record human acceptance, risk acceptance, an approved exception or authority to execute a migration.",
                "This assessment draws on guidance from the National Institute of Standards and Technology (NIST); it does not claim NIST certification, endorsement or automatic compliance. Exact references are retained with the preparation method.")
        };
    }

    private static JsonObject Point(string title, string body) => new() { ["title"] = title, ["body"] = body };
    private static string E(string value) => WebUtility.HtmlEncode(value);
    private static void Pair(StringBuilder html, string title, string body) => html.Append("<p><strong>").Append(E(title)).Append(":</strong> ").Append(E(body)).Append("</p>");
    private static void Definition(StringBuilder html, string title, string body) => html.Append("<dt>").Append(E(title)).Append("</dt><dd>").Append(E(body)).Append("</dd>");
    private static void List(StringBuilder html, IEnumerable<string> values)
    {
        html.Append("<ul>");
        foreach (var value in values) html.Append("<li>").Append(E(value)).Append("</li>");
        html.Append("</ul>");
    }
    private static void JsonDetail(StringBuilder html, string title, JsonNode? value)
    {
        html.Append("<details><summary>").Append(E(title)).Append("</summary><pre>").Append(E(value?.ToJsonString(new JsonSerializerOptions { WriteIndented = true }) ?? "Not supplied")).Append("</pre></details>");
    }
    private static IEnumerable<string> Strings(JsonObject row, string key) => (row[key] as JsonArray)?.OfType<JsonValue>().Select(v => v.GetValue<string>()) ?? [];
    private static JsonObject Section(string id, string title, string summary, IEnumerable<string> paragraphs, IEnumerable<JsonObject>? findings = null) => new()
    {
        ["id"] = id, ["title"] = title, ["summary"] = summary,
        ["paragraphs"] = new JsonArray(paragraphs.Select(p => (JsonNode?)JsonValue.Create(p)).ToArray()),
        ["findingIds"] = new JsonArray((findings ?? []).Select(f => (JsonNode?)JsonValue.Create(Text(f, "id"))).ToArray())
    };
    private static IEnumerable<string> FindingParagraphs(IEnumerable<JsonObject> findings)
    {
        var values = findings.ToList();
        if (values.Count == 0) return ["No material finding is available in this bounded analysis. That absence is not a conclusion about enterprise safety or coverage."];
        return values.Select(f => $"{Text(f, "title")}. Observation: {Text(f, "observation")} Why it matters: {Text(f, "implication")} Recommended investigation: {Text(f, "recommendation")}");
    }
    private static IEnumerable<string> LinkedParagraphs(JsonObject analysis, string field) => Rows(analysis, field).Select(row => $"{Text(row, "title")}. {Text(row, "rationale")} Proposed next step: {Text(row, "action")}");
    private static string Owner(JsonObject row) => Text(row, "owner") is { Length: > 0 } owner ? $"{owner} — synthetic owner context; enterprise assignment unconfirmed" : "Unassigned — accountable function to be nominated";
    private static string Human(string value) => value.Replace('_', ' ');
    private static List<JsonObject> Rows(JsonObject row, string key) => (row[key] as JsonArray)?.OfType<JsonObject>().ToList() ?? [];
    private static string Text(JsonObject row, string key, string fallback = "") => row[key] is JsonValue value && value.TryGetValue<string>(out var text) ? text : fallback;
    private static string Number(JsonObject row, string key) => row[key]?.ToString() ?? "unknown";
    private static string CountPriority(JsonObject summary, string key) => Rows(summary, "priorityCounts").FirstOrDefault(r => Text(r, "id") == key)?["count"]?.ToString() ?? "0";
}
