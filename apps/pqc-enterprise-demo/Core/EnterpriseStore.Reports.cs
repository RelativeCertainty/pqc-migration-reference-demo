using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace PqcEnterpriseDemo;

public sealed partial class EnterpriseStore
{
    public JsonArray Reports()
    {
        lock (gate)
        {
            EnsureOpen();
            using var command = Command("SELECT id,phase,created_at,content_sha256,worker_run_id FROM reports WHERE baseline_id=$baseline ORDER BY created_at DESC,id", null, ("$baseline", baselineId));
            using var reader = command.ExecuteReader();
            var results = new JsonArray();
            while (reader.Read()) results.Add(ReportMetadata(reader.GetString(0), reader.GetString(1), reader.GetString(2), reader.GetString(3), reader.GetString(4)));
            return results;
        }
    }

    public JsonObject? Report(string id)
    {
        lock (gate)
        {
            EnsureOpen();
            using var command = Command("SELECT phase,created_at,content_sha256,worker_run_id,content_json FROM reports WHERE id=$id AND baseline_id=$baseline", null, ("$id", id), ("$baseline", baselineId));
            using var reader = command.ExecuteReader();
            if (!reader.Read()) return null;
            var contentJson = reader.GetString(4);
            var digest = Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(contentJson)));
            if (digest != reader.GetString(2)) throw new DemoStoreException("report_integrity_failed");
            return new JsonObject { ["metadata"] = ReportMetadata(id, reader.GetString(0), reader.GetString(1), digest, reader.GetString(3)), ["content"] = ParseObject(contentJson) };
        }
    }

    // Compatibility entry point only. New reports must be produced through
    // an assessment-scoped command; historical report reads remain supported.
    public JsonObject CreateReport(string phase, string idempotencyKey, string actor)
        => throw new DemoConflictException("assessment_context_required");

    public JsonArray Runs()
    {
        lock (gate)
        {
            EnsureOpen();
            using var command = Command("SELECT w.id,r.id,w.phase,w.status,w.actor,w.created_at,w.result_json,w.invocation_json FROM worker_runs w JOIN reports r ON r.worker_run_id=w.id WHERE w.baseline_id=$baseline ORDER BY w.created_at DESC,w.id", null, ("$baseline", baselineId));
            using var reader = command.ExecuteReader();
            var result = new JsonArray();
            while (reader.Read())
            {
                var workerResult = ParseObject(reader.GetString(6));
                var workerInvocation = ParseObject(reader.GetString(7));
                var output = workerResult["output"]!.AsObject();
                result.Add(new JsonObject { ["id"] = reader.GetString(0), ["reportId"] = reader.GetString(1), ["phase"] = reader.GetString(2),
                    ["status"] = reader.GetString(3), ["actor"] = reader.GetString(4), ["createdAt"] = reader.GetString(5),
                    ["manifestId"] = workerInvocation["worker"]?.DeepClone(), ["baselineId"] = baselineId, ["result"] = new JsonObject { ["reportId"] = output["reportId"]!.DeepClone(), ["contentSha256"] = output["artifact_sha256"]!.DeepClone(), ["synthetic"] = true },
                    ["workerResult"] = workerResult, ["workerInvocation"] = workerInvocation,
                    ["runtimeEvidence"] = "development-only-controller-worker-simulation" });
            }
            reader.Close();
            foreach (var actionRun in ActionRuns()) result.Add(actionRun?.DeepClone());
            return new JsonArray(result.OfType<JsonObject>().OrderByDescending(r => Text(r, "createdAt"), StringComparer.Ordinal).ThenBy(r => Text(r, "id"), StringComparer.Ordinal).Select(r => (JsonNode?)r.DeepClone()).ToArray());
        }
    }

    private JsonObject ReportMetadata(string id, string phase, string created, string digest, string workerRunId) => new()
    {
        ["id"] = id, ["phase"] = phase, ["title"] = phase == "phase1" ? "Phase 1 — Current-state assessment" : "Phase 2 — Risk and migration review",
        ["baselineId"] = baselineId, ["inputSha256"] = inputSha256, ["createdAt"] = created, ["contentSha256"] = digest,
        ["contentHashScope"] = "compact_report_content_json_utf8",
        ["synthetic"] = true, ["acceptanceStatus"] = "unaccepted", ["workerRunId"] = workerRunId
    };

    public string? RenderReportHtml(string id)
    {
        var report = Report(id);
        if (report is null) return null;
        var content = report["content"]!.AsObject();
        if (Text(content, "schemaVersion") == "pqc.enterprise.report.v2" && content["narrative"] is JsonObject)
            return ReportNarrative.RenderHtml(report);
        var phase = Text(content, "phase");
        static string E(string text) => WebUtility.HtmlEncode(text);
        var html = new StringBuilder("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>");
        html.Append(E(Text(content, "title"))).Append("</title><style>");
        html.Append("body{font:16px/1.55 system-ui,sans-serif;color:#152b3c;background:#f4f7fa;margin:0}main{max-width:1120px;margin:0 auto;padding:40px 28px;background:white}h1{font-size:2.1rem;line-height:1.2}h2{margin-top:2.3rem;border-bottom:1px solid #c5d5df;padding-bottom:.4rem}h3{font-size:1.05rem}p,li{max-width:90ch}.notice{padding:16px 20px;background:#fff5db;border-left:4px solid #9a6500}table{width:100%;border-collapse:collapse;font-size:.87rem;table-layout:fixed}th,td{text-align:left;vertical-align:top;padding:9px;border-bottom:1px solid #dce5eb;overflow-wrap:anywhere}th{background:#eaf0f5}code{overflow-wrap:anywhere}details{margin:12px 0;padding:12px;border:1px solid #dce5eb}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.79rem}a{color:#075885}.label{text-transform:uppercase;letter-spacing:.09em;font-size:.77rem;color:#436179}footer{margin-top:3rem;color:#526578;font-size:.8rem}@media print{body{background:white}main{padding:0;max-width:none}details{break-inside:avoid}thead{display:table-header-group}tr{break-inside:avoid}h2,h3{break-after:avoid}.no-print{display:none}}");
        html.Append("</style></head><body><main><p class=\"label\">Enterprise PQC · synthetic development report</p><h1>").Append(E(Text(content, "title"))).Append("</h1>");
        html.Append("<p class=\"notice\">Synthetic data, unaccepted baseline, and illustrative method. This is not an enterprise assessment, approved risk position, NIST certification, qualified product integration, or migration authorization.</p>");
        html.Append("<p>As of: ").Append(E(Text(content["baseline"]!.AsObject(), "asOf"))).Append("<br>Baseline: <code>").Append(E(baselineId)).Append("</code><br>Input SHA-256: <code>").Append(E(inputSha256)).Append("</code><br>Snapshot JSON SHA-256: <code>").Append(E(Text(report["metadata"]!.AsObject(), "contentSha256"))).Append("</code><br>This snapshot hash covers compact report-content JSON encoded as UTF-8, not the API response wrapper or this HTML document.</p>");
        html.Append("<h2>Assessment summary</h2><ul>");
        foreach (var metric in content["summary"]!.AsObject()) html.Append("<li>").Append(E(Human(metric.Key))).Append(": ").Append(E(metric.Value?.ToString() ?? "unknown")).Append("</li>");
        html.Append("</ul><h2>Evidence boundary and source families</h2><p>All product names are recognition examples. Source routes and exact product bindings remain unconfirmed; synthetic coverage does not establish enterprise coverage.</p>");
        AppendTable(html, Rows(content, "sourceProfiles"), [("name", "Source family"), ("recognition_examples", "Recognition examples"), ("evidence_targets", "Evidence targets"), ("enterprise_route_status", "Enterprise route")]);
        if (phase == "phase1")
        {
            html.Append("<h2>Current-state inventory</h2><p>Each subject retains observation identifiers, source attribution and conflicting variants. These records do not imply asset-wide PQC readiness.</p>");
            AppendTable(html, Rows(content, "inventory"), [("display_names", "Subject"), ("fact_types", "Observed kinds"), ("source_instance_refs", "Sources"), ("conflict_status", "Reconciliation"), ("subject_ref", "Stable reference")]);
            html.Append("<h2>Dependency map</h2>");
            AppendTable(html, Rows(content, "dependencies"), [("from_ref", "From"), ("relationship", "Relationship"), ("to_ref", "To"), ("target_present", "Target in baseline")]);
            html.Append("<h2>Evidence appendix</h2><p>References identify the preparatory fixture's evidence custody. This demo stores attributable normalized observations, not the encrypted source artifacts themselves.</p>");
            foreach (var observation in Rows(content, "observations"))
            {
                html.Append("<details><summary>").Append(E(Text(observation, "fact_type"))).Append(" · ").Append(E(Text(observation, "source_instance_id"))).Append(" · ").Append(E(Text(observation, "observed_at"))).Append("</summary><pre>");
                html.Append(E(observation.ToJsonString(new System.Text.Json.JsonSerializerOptions { WriteIndented = true }))).Append("</pre></details>");
            }
            html.Append("<h2>Phase 1 to Phase 2 handoff</h2>"); AppendList(html, content["handoff"] as JsonArray);
        }
        else
        {
            html.Append("<h2>Phase 1 input contract</h2><p>This draft is derived from Phase 1 report <code>").Append(E(Text(content, "phase1ReportId"))).Append("</code>, bound to the same immutable evidence baseline. Phase 1 report SHA-256: <code>").Append(E(Text(content, "phase1ReportSha256"))).Append("</code>. Neither report records human acceptance; enterprise reliance still requires the applicable review and acceptance gate.</p>");
            html.Append("<h2>Method and interpretive boundaries</h2><p>No numerical risk score is assigned. Exposure, evidence quality, migration feasibility and execution authority are separate. Configured or vendor-reported capability is not observed cryptographic negotiation.</p>");
            var method = content["method"]!.AsObject();
            html.Append("<p>Method: ").Append(E(Text(method, "id"))).Append(" · version ").Append(E(Text(method, "version"))).Append(" · ").Append(E(Text(method, "status"))).Append("</p>");
            AppendTable(html, Rows(method, "rules"), [("id", "Rule"), ("rule", "Interpretation")]);
            html.Append("<h2>Use-level risk review register</h2>");
            AppendTable(html, Rows(content, "riskReviews"), [("subject_ref", "Subject"), ("purpose", "Purpose"), ("role", "Protocol / implementation role"), ("algorithm_variants", "Algorithms"), ("triage_lane", "Review lane"), ("limitation_codes", "Limitations")]);
            html.Append("<h2>Context records: not proof of cryptographic use</h2>");
            AppendTable(html, Rows(content, "contextReviews"), [("subject_ref", "Subject"), ("fact_type", "Context type"), ("rationale_code", "Rationale"), ("limitation_codes", "Limitations")]);
            html.Append("<h2>Migration candidates — not authorized work</h2>");
            AppendTable(html, Rows(content, "migrationCandidates"), [("pattern_ref", "Candidate pattern"), ("subject_ref", "Subject"), ("candidate_state", "State"), ("blocking_limitation_codes", "Blockers"), ("prerequisites", "Prerequisites")]);
            html.Append("<h2>Lookahead</h2>"); AppendList(html, content["lookahead"] as JsonArray);
            html.Append("<h2>Method references</h2><ul>");
            foreach (var reference in Rows(method, "references"))
            {
                var url = Text(reference, "url");
                html.Append("<li>");
                if (Uri.TryCreate(url, UriKind.Absolute, out var uri) && uri.Scheme == "https") html.Append("<a rel=\"noreferrer\" href=\"").Append(E(url)).Append("\">").Append(E(Text(reference, "title"))).Append("</a>");
                else html.Append(E(Text(reference, "title")));
                html.Append(" — ").Append(E(Text(reference, "supports"))).Append("</li>");
            }
            html.Append("</ul>");
        }
        html.Append("<h2>Recorded limitations</h2>");
        AppendTable(html, Rows(content, "limitations"), [("code", "Limitation"), ("subject_ref", "Affected subject")]);
        html.Append("<footer>Generated by the C# report-projection Worker from the durable synthetic baseline. Complete machine-readable content, provenance and hashes are available in the JSON export. No human acceptance or enterprise execution authority is recorded.</footer></main></body></html>");
        return html.ToString();
    }

    private static string Human(string key) => Regex.Replace(key, "([a-z])([A-Z])", "$1 $2");
    private static void AppendList(StringBuilder html, JsonArray? values)
    {
        html.Append("<ul>");
        if (values is not null) foreach (var value in values) html.Append("<li>").Append(WebUtility.HtmlEncode(value?.ToString() ?? "unknown")).Append("</li>");
        html.Append("</ul>");
    }
    private static void AppendTable(StringBuilder html, List<JsonObject> rows, (string Key, string Label)[] columns)
    {
        if (rows.Count == 0) { html.Append("<p>No records in this bounded baseline; no conclusion is inferred.</p>"); return; }
        html.Append("<table><thead><tr>");
        foreach (var column in columns) html.Append("<th scope=\"col\">").Append(WebUtility.HtmlEncode(column.Label)).Append("</th>");
        html.Append("</tr></thead><tbody>");
        foreach (var row in rows)
        {
            html.Append("<tr>");
            foreach (var column in columns)
            {
                var value = row[column.Key];
                var text = value is JsonArray array ? string.Join("; ", array.Select(v => v?.ToString() ?? "unknown")) : value?.ToString() ?? "Unknown / not supplied";
                html.Append("<td>").Append(WebUtility.HtmlEncode(text)).Append("</td>");
            }
            html.Append("</tr>");
        }
        html.Append("</tbody></table>");
    }
}
