using System.Globalization;
using System.Security.Cryptography;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace PqcEnterpriseDemo;

/// <summary>
/// Development-only bridge for exact, registered products of the repository's
/// closed reference normalizers. A hash registry is fixture admission, not source
/// authentication or a claim that a vendor adapter has been qualified. Arbitrary
/// normalized uploads and uploaded report conclusions are not accepted.
/// </summary>
public static class WorkspaceRegisteredSource
{
    public const string Schema = "pqc.workspace.registered-source-bundle.v1";
    public const string Normalizer = "workers.pqc.assessment_sources.normalize_page.v1";
    public const string RegistryEnvironment = "PQC_SYNTHETIC_BUNDLE_REGISTRY_FILE";
    private static readonly HashSet<string> Families = new(StringComparer.Ordinal)
    {
        "cmdb", "application-portfolio", "certificate-lifecycle", "certificate-authorities", "hsm",
        "traffic-termination", "api-and-mesh", "network-telemetry", "ssh", "vpn", "source-build",
        "dependency-analysis", "software-signing", "cloud-inventory", "kms", "secrets", "iam",
        "databases", "storage-backup", "data-governance", "communications", "endpoints", "embedded-ot",
        "specialized-transactions", "mainframe", "policy-exceptions", "vendor-assurance"
    };
    private static readonly HashSet<string> Bases = new(StringComparer.Ordinal) { "observed", "configured", "vendor_reported" };

    public static JsonObject Parse(byte[] bytes, JsonElement root)
    {
        Closed(root, "schemaVersion", "synthetic", "tenantId", "familyId", "sourceInstanceId", "sourceLabel",
            "collectedAt", "observedAt", "normalizerVersion", "rawSourceSha256", "rawSource", "records");
        if (String(root, "schemaVersion") != Schema || root.GetProperty("synthetic").ValueKind != JsonValueKind.True ||
            String(root, "normalizerVersion") != Normalizer) Invalid();
        var family = String(root, "familyId");
        var tenant = String(root, "tenantId");
        var source = String(root, "sourceInstanceId");
        if (!Families.Contains(family) || !Match(tenant, "^synthetic-[a-z0-9][a-z0-9-]{0,47}$") ||
            !Match(source, "^synthetic-[A-Za-z0-9][A-Za-z0-9_.:-]{0,117}$")) Invalid();
        var collected = Date(root, "collectedAt");
        var observed = Date(root, "observedAt");
        if (DateTimeOffset.Parse(observed, CultureInfo.InvariantCulture) > DateTimeOffset.Parse(collected, CultureInfo.InvariantCulture)) Invalid();
        var rawHash = String(root, "rawSourceSha256");
        if (!Match(rawHash, "^[a-f0-9]{64}$")) Invalid();
        var originalHash = Convert.ToHexStringLower(SHA256.HashData(bytes));
        RequireRegistered(originalHash, family, source, rawHash);

        // Canonical source bytes are independently bound in addition to the exact
        // outer artifact hash. Original source JSON remains in immutable custody.
        var raw = root.GetProperty("rawSource");
        Bounded(raw);
        var rawKind = family switch { "certificate-lifecycle" => "pki", "traffic-termination" => "tls", _ => family };
        if (raw.ValueKind != JsonValueKind.Object || String(raw, "kind") != rawKind ||
            raw.GetProperty("synthetic").ValueKind != JsonValueKind.True ||
            Convert.ToHexStringLower(SHA256.HashData(Canonical(raw))) != rawHash) Invalid();
        if (raw.TryGetProperty("tenant_id", out var rawTenant) && rawTenant.GetString() != tenant) Invalid();
        if (raw.TryGetProperty("source_instance_id", out var rawInstance) && rawInstance.GetString() != source) Invalid();
        var sourceRows = raw.GetProperty("records");
        var rows = root.GetProperty("records");
        if (rows.ValueKind != JsonValueKind.Array || rows.GetArrayLength() is < 1 or > 32 ||
            sourceRows.ValueKind != JsonValueKind.Array || sourceRows.GetArrayLength() != rows.GetArrayLength()) Invalid();
        var result = new JsonArray();
        var ids = new HashSet<string>(StringComparer.Ordinal);
        foreach (var row in rows.EnumerateArray())
        {
            Closed(row, "subject_ref", "fact_type", "assertion_kind", "facts");
            var nativeSubject = String(row, "subject_ref");
            var type = String(row, "fact_type");
            var basis = String(row, "assertion_kind");
            var expectedType = family switch { "cmdb" => "application", "certificate-lifecycle" => "certificate", "traffic-termination" => "tls_endpoint", _ => family.Replace('-', '_') };
            if (!Match(nativeSubject, "^pqc-ref:[a-f0-9]{64}$") || type != expectedType || !Bases.Contains(basis)) Invalid();
            var facts = row.GetProperty("facts");
            if (facts.ValueKind != JsonValueKind.Object) Invalid();
            Bounded(facts);
            var nativeId = String(facts, "native_id");
            if (!Match(nativeId, "^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$") || !ids.Add(nativeId)) Invalid();
            var sourceMatches = sourceRows.EnumerateArray().Where(r => String(r, "id") == nativeId).ToArray();
            if (sourceMatches.Length != 1 || String(sourceMatches[0], "evidence_basis") != basis ||
                nativeSubject != "pqc-ref:" + Convert.ToHexStringLower(SHA256.HashData(Canonical(JsonSerializer.SerializeToElement(new[] { tenant, source, "record", nativeId }))))) Invalid();
            ValidateFacts(facts);
            result.Add(new JsonObject
            {
                ["nativeId"] = nativeId, ["nativeSubjectRef"] = nativeSubject, ["familyId"] = family,
                ["factType"] = type, ["basis"] = basis, ["observedAt"] = observed, ["kind"] = "registered",
                ["normalizerVersion"] = Normalizer, ["sourceRawSha256"] = rawHash, ["synthetic"] = true,
                ["facts"] = JsonNode.Parse(facts.GetRawText()),
                ["supports"] = basis switch
                {
                    "configured" => "The stated synthetic configuration only; configuration does not establish negotiated behavior.",
                    "vendor_reported" => "A synthetic attributed product claim; not independently established product behavior.",
                    _ => "A modeled source observation for this record and time, not a live enterprise measurement."
                },
                ["cannotEstablish"] = "Enterprise completeness, confirmed ownership, whole-application PQC readiness, approved business impact or lifetime, permission to collect or change systems, or independent enterprise verification."
            });
        }
        return new JsonObject { ["kind"] = "registered", ["familyId"] = family, ["sourceId"] = source,
            ["sourceLabel"] = String(root, "sourceLabel"), ["collectedAt"] = collected,
            ["normalizerVersion"] = Normalizer, ["sourceRawSha256"] = rawHash, ["observations"] = result };
    }

    private static void RequireRegistered(string hash, string family, string source, string rawHash)
    {
        var path = Environment.GetEnvironmentVariable(RegistryEnvironment);
        if (string.IsNullOrWhiteSpace(path)) throw new DemoValidationException("workspace_synthetic_registry_required");
        try
        {
            var full = Path.GetFullPath(path);
            var info = new FileInfo(full);
            if (!info.Exists || info.Length is < 2 or > 262144 || info.LinkTarget is not null) InvalidRegistry();
            for (var parent = info.Directory; parent is not null; parent = parent.Parent)
                if (parent.LinkTarget is not null) InvalidRegistry();
            using var document = JsonDocument.Parse(File.ReadAllBytes(full), new JsonDocumentOptions { MaxDepth = 4 });
            var registry = document.RootElement;
            Closed(registry, "schemaVersion", "synthetic", "entries");
            if (String(registry, "schemaVersion") != "pqc.workspace.synthetic-bundle-registry.v1" ||
                registry.GetProperty("synthetic").ValueKind != JsonValueKind.True) InvalidRegistry();
            var entries = registry.GetProperty("entries");
            if (entries.ValueKind != JsonValueKind.Array || entries.GetArrayLength() is < 1 or > 512) InvalidRegistry();
            var hashes = new HashSet<string>(StringComparer.Ordinal);
            var found = false;
            foreach (var entry in entries.EnumerateArray())
            {
                Closed(entry, "sha256", "familyId", "sourceInstanceId", "normalizerVersion", "rawSourceSha256");
                var candidate = String(entry, "sha256");
                if (!Match(candidate, "^[a-f0-9]{64}$") || !hashes.Add(candidate)) InvalidRegistry();
                if (candidate == hash)
                    found = String(entry, "familyId") == family && String(entry, "sourceInstanceId") == source &&
                        String(entry, "normalizerVersion") == Normalizer && String(entry, "rawSourceSha256") == rawHash;
            }
            if (!found) throw new DemoValidationException("workspace_synthetic_bundle_not_registered");
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or JsonException or ArgumentException or NotSupportedException)
        { throw new DemoValidationException("workspace_synthetic_registry_invalid"); }
    }

    private static void ValidateFacts(JsonElement facts)
    {
        if (facts.TryGetProperty("relationships", out var relations))
        {
            if (relations.ValueKind != JsonValueKind.Array || relations.GetArrayLength() > 16) Invalid();
            foreach (var relation in relations.EnumerateArray())
            {
                Closed(relation, "relationship", "target_ref");
                if (!Match(String(relation, "relationship"), "^[a-z][a-z0-9_]{0,63}$") ||
                    !Match(String(relation, "target_ref"), "^pqc-ref:[a-f0-9]{64}$")) Invalid();
            }
        }
        if (facts.TryGetProperty("cryptographic_uses", out var uses))
        {
            if (uses.ValueKind != JsonValueKind.Array || uses.GetArrayLength() > 16) Invalid();
            foreach (var use in uses.EnumerateArray())
            {
                Closed(use, "purpose", "role", "algorithm", "basis", "parameters", "protected_data_ref", "trust_until");
                if (String(use, "purpose") is not ("key_establishment" or "authentication" or "digital_signature" or "data_encryption" or "key_wrapping") ||
                    !Match(String(use, "role"), "^[a-z][a-z0-9_]{0,63}$") || !Bases.Contains(String(use, "basis"))) Invalid();
                Closed(use.GetProperty("parameters"), "key_bits", "protocol_version");
            }
        }
    }

    private static byte[] Canonical(JsonElement element)
    {
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream, new JsonWriterOptions { Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping })) Write(element, writer);
        return stream.ToArray();
        static void Write(JsonElement value, Utf8JsonWriter writer)
        {
            if (value.ValueKind == JsonValueKind.Object)
            {
                writer.WriteStartObject();
                foreach (var property in value.EnumerateObject().OrderBy(p => p.Name, StringComparer.Ordinal))
                { writer.WritePropertyName(property.Name); Write(property.Value, writer); }
                writer.WriteEndObject();
            }
            else if (value.ValueKind == JsonValueKind.Array)
            { writer.WriteStartArray(); foreach (var child in value.EnumerateArray()) Write(child, writer); writer.WriteEndArray(); }
            else value.WriteTo(writer);
        }
    }
    private static void Bounded(JsonElement value, int depth = 0)
    {
        if (depth > 6) Invalid();
        switch (value.ValueKind)
        {
            case JsonValueKind.Object:
                var keys = new HashSet<string>(StringComparer.Ordinal);
                foreach (var property in value.EnumerateObject())
                {
                    if (keys.Count >= 80 || !keys.Add(property.Name) || !Match(property.Name, "^[a-z][a-z0-9_]{0,79}$")) Invalid();
                    Bounded(property.Value, depth + 1);
                }
                break;
            case JsonValueKind.Array:
                if (value.GetArrayLength() > 32) Invalid();
                foreach (var child in value.EnumerateArray()) Bounded(child, depth + 1);
                break;
            case JsonValueKind.String:
                var text = value.GetString()!;
                if (text.Length > 256 || text.Any(c => c < 32 || c > 126) || text.Contains("://", StringComparison.Ordinal) || text.Contains("PRIVATE KEY", StringComparison.OrdinalIgnoreCase)) Invalid();
                break;
            case JsonValueKind.Number:
                if (!value.TryGetInt64(out _)) Invalid();
                break;
            case JsonValueKind.Null: case JsonValueKind.True: case JsonValueKind.False: break;
            default: Invalid(); break;
        }
    }
    private static string Date(JsonElement row, string name)
    {
        var value = String(row, name);
        if (!Match(value, @"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,7})?(Z|[+-][0-9]{2}:[0-9]{2})$") ||
            !DateTimeOffset.TryParse(value, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out _)) Invalid();
        return value;
    }
    private static string String(JsonElement row, string name)
    {
        var value = row.GetProperty(name).GetString();
        if (string.IsNullOrWhiteSpace(value) || value.Length > 256 || value.Any(char.IsControl)) Invalid();
        return value!;
    }
    private static bool Match(string value, string pattern) => Regex.IsMatch(value, pattern, RegexOptions.CultureInvariant, TimeSpan.FromMilliseconds(100));
    private static void Closed(JsonElement value, params string[] allowed)
    {
        if (value.ValueKind != JsonValueKind.Object) Invalid();
        var keys = new HashSet<string>(StringComparer.Ordinal);
        foreach (var property in value.EnumerateObject()) if (!allowed.Contains(property.Name) || !keys.Add(property.Name)) Invalid();
        if (keys.Count != allowed.Length) Invalid();
    }
    private static void Invalid() => throw new DemoValidationException("workspace_synthetic_source_invalid");
    private static void InvalidRegistry() => throw new DemoValidationException("workspace_synthetic_registry_invalid");
}
