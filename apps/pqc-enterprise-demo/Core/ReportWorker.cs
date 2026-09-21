using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

/// <summary>
/// Deterministic development-only Worker simulator. The controller supplies an
/// in-memory projection of its durable baseline; this Worker cannot write state,
/// accept a baseline, contact sources, dispatch PBA work, or execute a migration.
/// </summary>
public sealed class ReportWorker
{
    public const string Identity = "pqc_enterprise_report_projection@0.2.0";
    public static string ManifestSha256 => HashResource("PqcEnterpriseDemo.ReportWorkerManifest");
    public static string PipelineSha256 => HashResource("PqcEnterpriseDemo.ReportPipelineManifest");

    public ReportWorkerOutput Execute(JsonObject invocation, JsonObject baselineProjection)
    {
        if (invocation["worker"]?.GetValue<string>() != Identity || invocation["tenant"]?.GetValue<string>() != "synthetic-enterprise" ||
            invocation["environment"]?.GetValue<string>() != "development-synthetic" ||
            invocation["meta"]?["candidateManifestSha256"]?.GetValue<string>() != ManifestSha256 ||
            invocation["meta"]?["candidatePipelineSha256"]?.GetValue<string>() != PipelineSha256 ||
            invocation["input"]?["synthetic"]?.GetValue<bool>() != true)
            throw new DemoValidationException("worker_admission_invalid");
        var input = invocation["input"]!.AsObject();
        var phase = input["phase"]?.GetValue<string>();
        if (phase is not ("phase1" or "phase2")) throw new DemoValidationException("invalid_report_phase");
        if (input["baselineId"]?.GetValue<string>() != baselineProjection["baseline"]?["baselineId"]?.GetValue<string>()) throw new DemoValidationException("worker_baseline_mismatch");
        var analysis = AnalysisProjection.Build(baselineProjection);
        var analysisVersion = analysis["method"]?["version"]?.GetValue<string>() ?? throw new DemoValidationException("analysis_version_required");
        var content = new JsonObject
        {
            ["schemaVersion"] = "pqc.enterprise.report.v2", ["phase"] = phase, ["synthetic"] = true,
            ["title"] = phase == "phase1" ? "Phase 1 — Current-state assessment" : "Phase 2 — Risk and migration review",
            ["baseline"] = baselineProjection["baseline"]!.DeepClone(), ["summary"] = baselineProjection["summary"]!.DeepClone(),
            ["provenance"] = baselineProjection["provenance"]!.DeepClone(),
            ["authority"] = new JsonObject
            {
                ["baselineAcceptance"] = "unaccepted", ["assessmentMethod"] = "illustrative_not_enterprise_approved",
                ["sourceSystemWriteAuthority"] = false, ["migrationExecutionAuthorized"] = false,
                ["enterpriseCoveragePercent"] = null, ["nistCertificationOrEndorsement"] = false,
                ["independentProductValidation"] = "not_performed"
            },
            ["limitations"] = baselineProjection["limitations"]!.DeepClone(),
            ["sourceProfiles"] = baselineProjection["sourceProfiles"]!.DeepClone(),
            ["estateAreas"] = baselineProjection["estateAreas"]!.DeepClone(),
            ["analysisVersion"] = analysisVersion,
            ["analysis"] = analysis,
            ["method"] = baselineProjection["method"]!.DeepClone(),
            ["actionRecords"] = baselineProjection["actionRecords"]?.DeepClone() ?? new JsonArray()
        };
        if (phase == "phase1")
        {
            content["inventory"] = baselineProjection["inventory"]!.DeepClone();
            content["observations"] = baselineProjection["observations"]!.DeepClone();
            content["dependencies"] = baselineProjection["dependencies"]!.DeepClone();
            content["handoff"] = new JsonArray("Confirm the assessment boundary and source authorities.", "Review identity conflicts, stale observations, and unresolved dependencies.",
                "Accept or explicitly qualify the immutable baseline before enterprise Phase 2 reliance.", "This synthetic preview does not record human acceptance or authorize remediation.");
        }
        else
        {
            if (baselineProjection["phase1Report"] is not JsonObject phase1Report || phase1Report["baselineId"]?.GetValue<string>() != input["baselineId"]?.GetValue<string>())
                throw new DemoConflictException("phase1_report_required");
            if (phase1Report["phase"]?.GetValue<string>() != "phase1")
                throw new DemoValidationException("phase1_report_phase_invalid");
            content["phase1ReportId"] = phase1Report["id"]!.DeepClone();
            content["phase1ReportSha256"] = phase1Report["contentSha256"]!.DeepClone();
            var inputSchema = phase1Report["inputSchemaVersion"]?.GetValue<string>();
            if (inputSchema is not ("pqc.enterprise.report.v1" or "pqc.enterprise.report.v2"))
                throw new DemoValidationException("phase1_report_schema_unsupported");
            var inputAnalysisVersion = phase1Report["inputAnalysisVersion"]?.GetValue<string>();
            if (inputSchema == "pqc.enterprise.report.v2" && inputAnalysisVersion != analysisVersion)
                throw new DemoConflictException("phase1_analysis_version_mismatch");
            content["phase1Input"] = new JsonObject
            {
                ["reportId"] = phase1Report["id"]!.DeepClone(),
                ["contentSha256"] = phase1Report["contentSha256"]!.DeepClone(),
                ["baselineId"] = phase1Report["baselineId"]!.DeepClone(),
                ["schemaVersion"] = inputSchema,
                ["analysisVersion"] = inputAnalysisVersion,
                ["selection"] = "most_recent_persisted_phase1_for_same_baseline",
                ["compatibility"] = inputSchema == "pqc.enterprise.report.v2" ? "same_baseline_and_analysis_version" : "legacy_v1_same_baseline_without_analysis_narrative",
                ["acceptanceStatus"] = "unaccepted"
            };
            content["method"] = baselineProjection["method"]!.DeepClone();
            content["riskReviews"] = baselineProjection["riskReviews"]!.DeepClone();
            content["contextReviews"] = baselineProjection["contextReviews"]!.DeepClone();
            content["migrationCandidates"] = baselineProjection["migrationCandidates"]!.DeepClone();
            content["dependencies"] = baselineProjection["dependencies"]!.DeepClone();
            content["lookahead"] = new JsonArray(
                "Phase 3 proposal: design immutable migration plans, compatibility tests, independent verification and recovery; obtain separate execution authorization.",
                "Phase 4 proposal: qualify bounded migration waves and continuing assurance. Ticket closure is not verified cryptographic migration.",
                "Source-record normalization and use-level inputs originate in the version-bound preparation pipeline; C# produces the analysis, findings, business interpretation and immutable narrative report from persisted records.");
        }
        content["narrative"] = ReportNarrative.Build(phase, content);
        var contentJson = content.ToJsonString();
        var digest = Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(contentJson)));
        var reportId = "report-" + invocation["id"]!.GetValue<string>();
        var result = new JsonObject
        {
            ["success"] = true, ["retryable"] = false, ["status"] = "completed",
            ["output"] = new JsonObject { ["reportId"] = reportId, ["artifact_sha256"] = digest, ["synthetic"] = true },
            ["trace"] = new JsonObject { ["traceparent"] = invocation["trace"]?["traceparent"]?.DeepClone() }
        };
        return new ReportWorkerOutput(reportId, contentJson, digest, result);
    }

    private static string HashResource(string name)
    {
        using var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(name) ?? throw new DemoStoreException("candidate_manifest_missing");
        return Convert.ToHexStringLower(SHA256.HashData(stream));
    }
}

public sealed record ReportWorkerOutput(string ReportId, string ContentJson, string ContentSha256, JsonObject Result);
