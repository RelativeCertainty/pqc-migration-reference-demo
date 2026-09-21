using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

/// <summary>Pure, manifest-bound development simulator. Produces a local review
/// artifact, never sends a request, records acceptance or writes authoritative state.</summary>
public sealed class ReviewWorker
{
    public const string Identity = "pqc_enterprise_review@0.1.0";
    public static string ManifestSha256 => ResourceHash("PqcEnterpriseDemo.ReviewWorkerManifest");
    public static string PipelineSha256 => ResourceHash("PqcEnterpriseDemo.ReviewPipelineManifest");

    public (JsonObject Record, JsonObject Result) Execute(JsonObject invocation, JsonObject request, JsonObject finding, string createdAt)
    {
        var input = invocation["input"]!.AsObject();
        if (invocation["worker"]?.GetValue<string>() != Identity || invocation["tenant"]?.GetValue<string>() != "synthetic-enterprise" ||
            invocation["environment"]?.GetValue<string>() != "development-synthetic" || input["synthetic"]?.GetValue<bool>() != true ||
            invocation["meta"]?["candidateManifestSha256"]?.GetValue<string>() != ManifestSha256 ||
            invocation["meta"]?["candidatePipelineSha256"]?.GetValue<string>() != PipelineSha256 ||
            input["request_sha256"]?.GetValue<string>() != Hash(request.ToJsonString()) ||
            input["findingId"]?.GetValue<string>() != finding["id"]?.GetValue<string>())
            throw new DemoValidationException("review_worker_admission_invalid");
        var operation = request["operation"]!.GetValue<string>();
        var disposition = request["disposition"]?.GetValue<string>();
        var status = operation switch
        {
            "investigate" or "review_finding" => "in_review",
            "prepare_evidence_request" => "needs_evidence",
            "record_disposition" when disposition is "needs_evidence" or "reviewed" or "deferred" => disposition,
            _ => throw new DemoValidationException("invalid_review_operation")
        };
        var id = "action-" + invocation["id"]!.GetValue<string>();
        string? draft = null;
        if (operation == "prepare_evidence_request")
        {
            draft = $"DRAFT — NOT SENT\nSubject: Information request — {finding["title"]}\n\n" +
                $"Suggested recipient function (confirm routing): {finding["owner"] ?? JsonValue.Create("Owner confirmation required")}\n" +
                $"Assessment context: {finding["observation"]}\n" +
                $"Why it matters: {finding["implication"]}\n" +
                $"Assessment team's proposed follow-up (not a task assigned to you): {finding["recommendation"]}\n\n" +
                "Could you point us to an existing inventory, report, documentation or team that could help clarify this? " +
                "A product name, document reference, referral or 'not sure' is useful. " +
                "Please mention any known access restrictions, information-sharing considerations or gaps.\n\n" +
                "This request helps us locate existing information; it does not ask you to create documents or demonstrate compliance. " +
                "Do not send credentials, private keys, sensitive files or customer data. " +
                "The assessment team will coordinate follow-up. Any later collection or system access must be agreed separately " +
                "with the appropriate owner; replying does not grant permission.\n\n" +
                "This is a synthetic local request draft; it has not been emailed or sent to a ticketing provider.";
        }
        var record = new JsonObject
        {
            ["id"] = id, ["findingId"] = input["findingId"]!.DeepClone(), ["baselineId"] = input["baselineId"]!.DeepClone(),
            ["findingSha256"] = Hash(finding.ToJsonString()), ["operation"] = operation, ["disposition"] = disposition,
            ["note"] = request["note"]!.DeepClone(), ["revision"] = request["expectedRevision"]!.GetValue<int>() + 1,
            ["createdAt"] = createdAt, ["actor"] = "synthetic-demo:analyst", ["evidenceRequestDraft"] = draft,
            ["status"] = status, ["synthetic"] = true, ["externalDelivery"] = false, ["executionAuthorized"] = false,
            ["acceptanceRecorded"] = false, ["reviewMeaning"] = "local_analyst_annotation_not_verified_migration_or_owner_acceptance"
        };
        var result = new JsonObject
        {
            ["success"] = true, ["retryable"] = false, ["status"] = "completed",
            ["output"] = new JsonObject { ["actionId"] = id, ["artifact_sha256"] = Hash(record.ToJsonString()), ["synthetic"] = true },
            ["trace"] = new JsonObject { ["traceparent"] = invocation["trace"]?["traceparent"]?.DeepClone() }
        };
        return (record, result);
    }

    internal static string Hash(string value) => Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(value)));
    private static string ResourceHash(string name)
    {
        using var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(name) ?? throw new DemoStoreException("candidate_manifest_missing");
        return Convert.ToHexStringLower(SHA256.HashData(stream));
    }
}
