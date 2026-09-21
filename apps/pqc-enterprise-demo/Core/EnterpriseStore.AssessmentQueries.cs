using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

public interface IAssessmentQueries
{
    JsonObject AssessmentAnalysis(string id, string principal, AnalysisFilter? filter = null);
    JsonObject AssessmentDashboard(string id, string principal);
    JsonArray AssessmentSources(string id, string principal);
    JsonObject AssessmentAssets(string id, string principal, string? q, string? family, string? status, int page, int pageSize);
    JsonObject? AssessmentAsset(string id, string assetId, string principal);
    JsonArray AssessmentReports(string id, string principal);
    JsonArray AssessmentRuns(string id, string principal);
}

public sealed partial class EnterpriseStore : IAssessmentQueries
{
    // A display filter may narrow this projection, never its scope or gate basis.
    // The original fixture is shared immutable source material, not permission
    // to display all its records in every assessment.
    internal JsonObject AssessmentProjection(string id, string principal)
    {
        lock (gate)
        {
            EnsureOpen();
            var selection = AssessmentEvidenceSelection(id, principal);
            var subjects = Strings(selection, "subjectIds").ToHashSet(StringComparer.Ordinal);
            var observations = Strings(selection, "observationIds").ToHashSet(StringComparer.Ordinal);
            var families = Strings(selection, "familyIds").ToHashSet(StringComparer.Ordinal);
            var profiles = ReadRows("sourceProfiles").Where(p => families.Contains(Text(p, "family_id"))).ToList();
            var areas = profiles.Select(p => Text(p, "area_ref")).ToHashSet(StringComparer.Ordinal);
            var inventory = ReadRows("inventory").Where(r => subjects.Contains(Text(r, "subject_ref")) &&
                Strings(r, "observation_refs").Any() && Strings(r, "observation_refs").All(observations.Contains)).ToList();
            // Normalized inventory can merge multiple source observations. Fail
            // closed on partially selected subjects rather than leaking a merge.
            subjects = inventory.Select(r => Text(r, "subject_ref")).ToHashSet(StringComparer.Ordinal);
            var admitted = ReadRows("observations").Where(r => subjects.Contains(Text(r, "subject_ref")) && observations.Contains(Text(r, "observation_id"))).ToList();
            var metadata = Metadata();
            metadata["assessmentId"] = id;
            metadata["assetCount"] = inventory.Count;
            metadata["populationStatus"] = "unknown";
            var projection = new JsonObject { ["baseline"] = metadata,
                ["method"] = JsonNode.Parse(Scalar("SELECT method_json FROM baselines WHERE id=$id", ("$id", baselineId))!.ToString()!),
                ["inventory"] = Array(inventory), ["observations"] = Array(admitted),
                ["sourceProfiles"] = Array(profiles), ["estateAreas"] = Array(ReadRows("estateAreas").Where(a => areas.Contains(Text(a, "area_ref")))) };
            foreach (var kind in new[] { "riskReviews", "contextReviews", "migrationCandidates", "limitations" })
                projection[kind] = Array(ReadRows(kind).Where(r => subjects.Contains(Text(r, "subject_ref")) &&
                    Strings(r, "observation_refs").All(observations.Contains) &&
                    Rows(r, "evidence").All(e => observations.Contains(Text(e, "observation_ref")))));
            projection["dependencies"] = Array(ReadRows("dependencies").Where(r => subjects.Contains(Text(r, "from_ref")) && subjects.Contains(Text(r, "to_ref"))));
            projection["unselectedDependencyCount"] = ReadRows("dependencies").Count(r => subjects.Contains(Text(r, "from_ref")) && !subjects.Contains(Text(r, "to_ref")));
            IntakeEvidenceProjection.Merge(ReadAssessment(id,principal),projection);
            DiscoveryReportProjection.MergeEvidence(ReadAssessment(id,principal),projection);
            WorkspaceEvidenceProjection.MergeEvidence(WorkspaceReportInput(ReadAssessment(id,principal)),projection);
            return projection;
        }
    }

    public JsonObject AssessmentAnalysis(string id, string principal, AnalysisFilter? filter = null) =>
        AnalysisProjection.Build(AssessmentProjection(id, principal), filter);

    private static List<JsonObject> SelectedAssetRows(JsonObject projection)
    {
        var profiles = Rows(projection, "sourceProfiles");
        var risks = Rows(projection, "riskReviews").GroupBy(r => Text(r, "subject_ref")).ToDictionary(g => g.Key, g => g.Count(), StringComparer.Ordinal);
        var limitations = Rows(projection, "limitations");
        return Rows(projection, "inventory").Select(row =>
        {
            var id = Text(row, "subject_ref");
            var instances = Strings(row, "source_instance_refs").ToHashSet(StringComparer.Ordinal);
            var uses = risks.GetValueOrDefault(id);
            var conflict = Text(row, "conflict_status") != "no_conflict_in_snapshot";
            var stale = limitations.Any(l => Text(l, "subject_ref") == id && Text(l, "code") == "stale_evidence");
            return new JsonObject { ["id"] = id, ["displayName"] = Strings(row, "display_names").FirstOrDefault() ?? id,
                ["familyIds"] = new JsonArray(profiles.Where(p => Strings(p, "source_instance_refs").Any(instances.Contains)).Select(p => (JsonNode?)JsonValue.Create(Text(p, "family_id"))).ToArray()),
                ["status"] = conflict ? "conflict" : stale ? "stale" : uses == 0 ? "context_only" : "evidence_present",
                ["hasConflict"] = conflict, ["isStale"] = stale, ["isContextOnly"] = uses == 0,
                ["observationCount"] = Strings(row, "observation_refs").Count(), ["cryptographicUseCount"] = uses, ["asset"] = row.DeepClone() };
        }).OrderBy(a => Text(a, "displayName"), StringComparer.Ordinal).ThenBy(a => Text(a, "id"), StringComparer.Ordinal).ToList();
    }

    private static JsonArray SelectedSources(JsonObject projection) => Array(Rows(projection, "sourceProfiles").Select(profile =>
    {
        var instances = Strings(profile, "source_instance_refs").ToHashSet(StringComparer.Ordinal);
        var observations = Rows(projection, "observations").Where(o => instances.Contains(Text(o, "source_instance_id"))).ToArray();
        return new JsonObject { ["id"] = Text(profile, "family_id"), ["name"] = Text(profile, "name"), ["areaRef"] = Text(profile, "area_ref"),
            ["assetCount"] = observations.Select(o => Text(o, "subject_ref")).Distinct().Count(), ["observationCount"] = observations.Length,
            ["status"] = "synthetic_only", ["profile"] = profile.DeepClone() };
    }));

    public JsonArray AssessmentSources(string id, string principal) => SelectedSources(AssessmentProjection(id, principal));

    public JsonObject AssessmentDashboard(string id, string principal)
    {
        lock (gate)
        {
            var projection = AssessmentProjection(id, principal);
            var assets = SelectedAssetRows(projection);
            return new JsonObject { ["baseline"] = projection["baseline"]!.DeepClone(),
                ["counts"] = new JsonObject { ["assets"] = assets.Count, ["observations"] = Rows(projection, "observations").Count,
                    ["dependencies"] = Rows(projection, "dependencies").Count, ["cryptographicUses"] = Rows(projection, "riskReviews").Count,
                    ["sourceFamilies"] = Rows(projection, "sourceProfiles").Count, ["estateAreas"] = Rows(projection, "estateAreas").Count,
                    ["limitations"] = Rows(projection, "limitations").Count, ["conflictedAssets"] = assets.Count(a => a["hasConflict"]!.GetValue<bool>()),
                    ["staleAssets"] = assets.Count(a => a["isStale"]!.GetValue<bool>()), ["contextOnlyAssets"] = assets.Count(a => a["isContextOnly"]!.GetValue<bool>()),
                    ["reports"] = AssessmentReports(id, principal).Count },
                ["families"] = SelectedSources(projection), ["triageLanes"] = GroupCounts(Rows(projection, "riskReviews"), "triage_lane"),
                ["limitations"] = GroupCounts(Rows(projection, "limitations"), "code"),
                ["boundary"] = "Only evidence selected into this synthetic assessment is shown. Catalog families are not enterprise coverage. Unknown population: no completeness percentage. Filters cannot change assessment scope." };
        }
    }

    public JsonObject AssessmentAssets(string id, string principal, string? q, string? family, string? status, int page, int pageSize)
    {
        if (page < 1 || page > 10000 || pageSize is < 1 or > 100 || (q?.Length ?? 0) > 200 || (family?.Length ?? 0) > 100 || (status?.Length ?? 0) > 100)
            throw new DemoValidationException("invalid_asset_query");
        var projection = AssessmentProjection(id, principal);
        var analysis = AnalysisProjection.Build(projection);
        var search = Rows(analysis, "assets").ToDictionary(r => Text(r, "id"), r => r.ToJsonString(), StringComparer.Ordinal);
        var rows = SelectedAssetRows(projection).Where(a => string.IsNullOrWhiteSpace(q) || a.ToJsonString().Contains(q, StringComparison.OrdinalIgnoreCase) ||
                search.GetValueOrDefault(Text(a, "id"), "").Contains(q, StringComparison.OrdinalIgnoreCase))
            .Where(a => string.IsNullOrWhiteSpace(family) || Strings(a, "familyIds").Contains(family, StringComparer.Ordinal))
            .Where(a => string.IsNullOrWhiteSpace(status) || (status switch { "conflict" => a["hasConflict"]!.GetValue<bool>(),
                "stale" => a["isStale"]!.GetValue<bool>(), "context_only" => a["isContextOnly"]!.GetValue<bool>(), _ => Text(a, "status") == status })).ToList();
        return new JsonObject { ["items"] = Array(rows.Skip((page - 1) * pageSize).Take(pageSize)), ["total"] = rows.Count, ["page"] = page, ["pageSize"] = pageSize };
    }

    public JsonObject? AssessmentAsset(string id, string assetId, string principal)
    {
        var projection = AssessmentProjection(id, principal);
        var asset = SelectedAssetRows(projection).FirstOrDefault(a => Text(a, "id") == assetId);
        if (asset is null) return null;
        return new JsonObject { ["asset"] = asset, ["baseline"] = projection["baseline"]!.DeepClone(),
            ["observations"] = Array(Rows(projection, "observations").Where(r => Text(r, "subject_ref") == assetId)),
            ["dependencies"] = Array(Rows(projection, "dependencies").Where(r => Text(r, "from_ref") == assetId || Text(r, "to_ref") == assetId)),
            ["cryptographicUses"] = Array(Rows(projection, "riskReviews").Where(r => Text(r, "subject_ref") == assetId)),
            ["limitations"] = Array(Rows(projection, "limitations").Where(r => Text(r, "subject_ref") == assetId)) };
    }

    public JsonArray AssessmentReports(string id, string principal)
    {
        lock (gate)
        {
            var state = GetAssessment(id, principal);
            return Array(Rows(state, "documents").Select(d => GetAssessmentReport(id, Text(d, "id"), principal)?["metadata"]?.DeepClone()).OfType<JsonObject>());
        }
    }
}
