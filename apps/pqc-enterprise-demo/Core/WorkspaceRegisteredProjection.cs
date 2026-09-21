using System.Globalization;
using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

/// <summary>Read projection over admitted registered source records. Native
/// source relationships are assertions, never automatic deployment merges.</summary>
public static class WorkspaceRegisteredProjection
{
    public static void Merge(JsonObject workspace, JsonObject projection)
    {
        var bundles = Rows(workspace, "bundles").Where(b => S(b, "status") == "admitted" && S(b, "kind") == "registered").ToArray();
        var all = bundles.SelectMany(b => Rows(b, "observations").Select(r => (bundle: b, record: r))).ToArray();
        if (all.Length == 0) return;
        var observations = Array(projection, "observations"); var inventory = Array(projection, "inventory");
        var uses = Array(projection, "riskReviews"); var limitations = Array(projection, "limitations");
        var dependencies = Array(projection, "dependencies");
        foreach (var group in all.GroupBy(x => S(x.record, "systemId"), StringComparer.Ordinal))
        {
            var entries = group.DistinctBy(x => S(x.record, "id")).ToArray();
            var first = entries[0]; var type = S(first.record, "factType");
            var facts = entries.Select(x => (JsonObject)x.record["facts"]!).ToArray();
            var fields = facts.SelectMany(f => f.Select(v => v.Key)).Where(k => k is not ("native_id" or "relationships" or "cryptographic_uses" or "limitations") && !k.EndsWith("_basis", StringComparison.Ordinal)).Distinct().ToArray();
            var conflicts = fields.Where(k => facts.Select(f => f[k]?.ToJsonString() ?? "null").Distinct(StringComparer.Ordinal).Count() > 1).ToArray();
            var codes = facts.SelectMany(f => Strings(f["limitations"])).Concat(["workspace_synthetic_basis", "independent_runtime_verification_missing"]).ToHashSet(StringComparer.Ordinal);
            // Freshness compares source time with its recorded collection time,
            // not the machine clock. A later report can retain this exact basis.
            var freshness = projection["baseline"]?["freshnessDays"]?.GetValue<int>() ?? 30;
            if (entries.Any(e => (DateTimeOffset.Parse(S(e.record, "collectedAt"), CultureInfo.InvariantCulture) -
                                 DateTimeOffset.Parse(S(e.record, "observedAt"), CultureInfo.InvariantCulture)).TotalDays > freshness))
                codes.Add("stale_evidence");
            if (conflicts.Length > 0) codes.Add("conflicting_observations");
            foreach (var (bundle, record) in entries)
            {
                var fact = (JsonObject)record["facts"]!.DeepClone();
                fact["synthetic"] = true; fact["independently_verified"] = false;
                // The returned product identifies the evidence source or reviewed
                // binding, not necessarily the subject described by its records.
                // Only an actual source fact may label the subject's technology.
                fact["source_product_label"] = S(bundle, "product");
                fact["environment"] ??= JsonValue.Create(S(bundle, "environment"));
                var asserted = Relations(fact).DistinctBy(r => (r.relationship, r.target)).ToArray();
                var reviewedRelations = new JsonArray();
                foreach (var relation in asserted)
                {
                    var matches = all.Where(x => S(x.record, "nativeSubjectRef") == relation.target && S(x.record, "canonicalId").Length > 0)
                        .Select(x => S(x.record, "systemId")).Distinct(StringComparer.Ordinal).ToArray();
                    var resolved = S(record, "canonicalId").Length > 0 && matches.Length == 1;
                    reviewedRelations.Add(new JsonObject { ["relationship"] = relation.relationship, ["native_target_ref"] = relation.target,
                        ["target_ref"] = resolved ? JsonValue.Create(matches[0]) : null,
                        ["status"] = resolved ? "source_assertion_target_in_reviewed_scope" : matches.Length > 1 ? "ambiguous_reference" : "unresolved_reference" });
                    if (relation.factField.Length > 0)
                    {
                        fact["native_" + relation.factField] = relation.target;
                        fact[relation.factField] = resolved ? JsonValue.Create(matches[0]) : null;
                        fact[relation.factField + "_status"] = resolved ? "source_assertion_target_in_reviewed_scope" : "unresolved_reference";
                    }
                    if (!resolved) { codes.Add(matches.Length > 1 ? "unresolved_dependency" : "missing_relationship"); continue; }
                    Add(dependencies, "edge_id", new JsonObject
                    {
                        ["edge_id"] = "workspace-edge-" + AssessmentWorkflow.Hash(new { from = group.Key, to = matches[0], relation.relationship })[..24],
                        ["from_ref"] = group.Key, ["to_ref"] = matches[0], ["relationship"] = relation.relationship,
                        ["evidence_basis"] = "reviewed_synthetic_source_assertion_not_independent_relationship_verification",
                        ["observation_refs"] = Values(entries.Select(e => S(e.record, "id")))
                    });
                }
                fact["relationships"] = reviewedRelations;
                Add(observations, "observation_id", new JsonObject
                {
                    ["observation_id"] = S(record, "id"), ["subject_ref"] = group.Key, ["source_instance_id"] = S(record, "sourceSystemId"),
                    ["subject_kind"] = type, ["fact_type"] = type, ["evidence_basis"] = S(record, "basis"),
                    ["observed_at"] = S(record, "observedAt"), ["received_at"] = S(record, "collectedAt"),
                    ["evidence_ref"] = "workspace-custody:" + S(record, "bundleId"), ["evidence_sha256"] = S(record, "artifactSha256"),
                    ["source_raw_sha256"] = S(record, "sourceRawSha256"), ["native_record_id"] = S(record, "nativeId"),
                    ["facts"] = fact, ["normalizer_version"] = S(record, "normalizerVersion"),
                    ["relationship_status"] = S(record, "canonicalId").Length == 0 ? "unresolved_deployment" : "reviewed_deployment_binding"
                });
                var profile = Rows(projection, "sourceProfiles").SingleOrDefault(p => S(p, "family_id") == S(record, "familyId"));
                if (profile is not null)
                {
                    var sources = Array(profile, "source_instance_refs");
                    if (!Strings(sources).Contains(S(record, "sourceSystemId"), StringComparer.Ordinal)) sources.Add(S(record, "sourceSystemId"));
                }
            }
            Add(inventory, "subject_ref", new JsonObject
            {
                ["subject_ref"] = group.Key, ["subject_kind"] = type, ["fact_types"] = Values([type]),
                ["display_names"] = Values([S(facts[0], "name").Length > 0 ? S(facts[0], "name") : S(first.bundle, "productLabel") + " / " + S(first.record, "nativeId")]),
                ["source_instance_refs"] = Values(entries.Select(e => S(e.record, "sourceSystemId")).Distinct()),
                ["observation_refs"] = Values(entries.Select(e => S(e.record, "id"))),
                ["conflict_status"] = conflicts.Length > 0 ? "conflicting_observations" : "no_conflict_in_snapshot", ["synthetic"] = true
            });
            foreach (var code in codes.Order(StringComparer.Ordinal)) Add(limitations, "workspace_limit_id", new JsonObject
            {
                ["workspace_limit_id"] = AssessmentWorkflow.Hash(new { group.Key, code }), ["subject_ref"] = group.Key, ["code"] = code,
                ["description"] = code == "conflicting_observations" ? "Unresolved synthetic source variants: " + string.Join(", ", conflicts) + ". All bases remain distinct."
                    : code == "workspace_synthetic_basis" ? "Registered reference-dialect fixture only; no live vendor qualification, enterprise coverage or independent verification."
                    : code == "missing_relationship" ? "A source-reported target is absent from the admitted reviewed scope; no deployment identity was inferred."
                    : code == "stale_evidence" ? "Source observation age exceeded the declared freshness window at collection. Original source and collection times are retained."
                    : "Retained source limitation: " + code.Replace('_', ' ') + ". Review before relying on this record."
            });
            var useAssertions = entries.SelectMany(e => UseAssertions((JsonObject)e.record["facts"]!, S(e.record, "factType"), S(e.record, "basis"))
                .Select(u => (use: u, record: e.record))).ToArray();
            foreach (var useGroup in useAssertions.GroupBy(u => (purpose: S(u.use, "purpose"), role: S(u.use, "role"))))
            {
                var variants = useGroup.Select(u => S(u.use, "algorithm")).Where(a => a.Length > 0).Distinct(StringComparer.Ordinal).Order(StringComparer.Ordinal).ToArray();
                var postures = variants.Select(a => Posture(a, useGroup.Key.purpose)).Distinct().ToArray();
                var useCodes = codes.Concat(["missing_business_context"]).ToHashSet(StringComparer.Ordinal);
                if (variants.Length == 0) useCodes.Add("cryptographic_parameters_unknown");
                Add(uses, "use_id", new JsonObject
                {
                    ["use_id"] = "workspace-use-" + AssessmentWorkflow.Hash(new { subject = group.Key, useGroup.Key.purpose, useGroup.Key.role })[..24],
                    ["subject_ref"] = group.Key, ["purpose"] = useGroup.Key.purpose, ["role"] = useGroup.Key.role,
                    ["algorithm_variants"] = Values(variants), ["algorithm_posture"] = postures.Length == 1 ? postures[0] : "unknown",
                    ["evidence_bases"] = Values(useGroup.Select(u => S(u.use, "basis")).Distinct()),
                    ["observation_refs"] = Values(useGroup.Select(u => S(u.record, "id")).Distinct()),
                    ["confidentiality_days_remaining"] = null, ["trust_days_remaining"] = null,
                    ["reported_trust_until"] = Values(useGroup.Select(u => S(u.use, "trust_until")).Where(v => v.Length > 0).Distinct()),
                    ["information_lifetime_basis"] = "source assertions are not reviewed business lifetime determinations",
                    ["limitation_codes"] = Values(useCodes.Order(StringComparer.Ordinal)), ["assessment_status"] = "illustrative_review_candidate",
                    ["method_version"] = WorkspaceRegisteredSource.Normalizer, ["independently_verified"] = false
                });
            }
        }
        if (projection["baseline"] is JsonObject baseline) baseline["assetCount"] = inventory.Count;
    }

    private static IEnumerable<(string relationship, string target, string factField)> Relations(JsonObject facts)
    {
        foreach (var field in new[] { "application_ref", "certificate_ref" })
            if (S(facts, field).Length > 0) yield return (field == "application_ref" ? "belongs_to_application" : "uses_certificate", S(facts, field), field);
        foreach (var relation in Rows(facts, "relationships"))
            yield return (S(relation, "relationship"), S(relation, "target_ref"), "");
    }
    private static IEnumerable<JsonObject> UseAssertions(JsonObject facts, string type, string basis)
    {
        foreach (var use in Rows(facts, "cryptographic_uses")) yield return use;
        if (type == "tls_endpoint") yield return new JsonObject { ["purpose"] = "key_establishment", ["role"] = "transport_key_exchange", ["algorithm"] = facts["key_exchange_group"]?.DeepClone(), ["basis"] = basis };
        if (type is "tls_endpoint" or "certificate") yield return new JsonObject { ["purpose"] = "authentication", ["role"] = "certificate_signature",
            ["algorithm"] = facts[type == "certificate" ? "signature_algorithm" : "certificate_signature_algorithm"]?.DeepClone(), ["basis"] = basis };
    }
    private static string Posture(string algorithm, string purpose)
    {
        var value = algorithm.ToUpperInvariant();
        if (purpose == "key_establishment" && value is "X25519MLKEM768" or "SECP256R1MLKEM768" or "SECP384R1MLKEM1024" or "SNTRUP761X25519-SHA512") return "hybrid_key_exchange_recorded";
        if (value.StartsWith("ML-DSA", StringComparison.Ordinal) || value.StartsWith("SLH-DSA", StringComparison.Ordinal)) return "pqc_signature_mechanism_recorded";
        if (value.StartsWith("AES", StringComparison.Ordinal) || value.StartsWith("CHACHA", StringComparison.Ordinal)) return "symmetric_mechanism_separate_parameter_review";
        if (value.StartsWith("SHA", StringComparison.Ordinal) && !value.Contains("RSA", StringComparison.Ordinal)) return "hash_mechanism_separate_parameter_review";
        if (value.Contains("RSA", StringComparison.Ordinal) || value.Contains("ECDSA", StringComparison.Ordinal) || value.Contains("ED25519", StringComparison.Ordinal) ||
            value.Contains("ECDH", StringComparison.Ordinal) || value is "X25519" or "X448" or "P-256" or "P-384" or "P-521" or "SECP256R1" or "FFDHE2048") return "classical_method_review_candidate";
        return "unknown";
    }
    private static IEnumerable<string> Strings(JsonNode? node) => node is JsonArray array ? array.Select(v => v?.GetValue<string>() ?? "") : [];
    private static JsonArray Values(IEnumerable<string> values) => new(values.Select(v => (JsonNode?)JsonValue.Create(v)).ToArray());
    private static IEnumerable<JsonObject> Rows(JsonObject row, string field) => (row[field] as JsonArray)?.OfType<JsonObject>() ?? [];
    private static string S(JsonObject row, string field) => row[field]?.GetValue<string>() ?? "";
    private static JsonArray Array(JsonObject row, string field) { if (row[field] is JsonArray array) return array; var created = new JsonArray(); row[field] = created; return created; }
    private static void Add(JsonArray rows, string key, JsonObject row)
    { var previous = rows.OfType<JsonObject>().SingleOrDefault(r => S(r, key) == S(row, key)); if (previous is null) rows.Add(row); else rows[rows.IndexOf(previous)] = row; }
}
