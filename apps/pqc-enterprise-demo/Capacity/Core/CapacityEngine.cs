using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace PqcCapacityConfigurator.Core;

/// <summary>Pure bounded planning arithmetic. No I/O, provisioning, source access or approval effects.</summary>
public static class CapacityEngine
{
    public const string ModelVersion = "pqc.capacity.model.v1";
    public static IReadOnlyList<string> SelfTest() => CapacitySelfTest.Run();
    private const double GiB = 1_073_741_824;
    private static readonly IReadOnlyDictionary<string, ParameterDefinition> DefinitionByKey =
        Catalog.Definitions.ToDictionary(d => d.Key, StringComparer.Ordinal);

    public static ValidationResult Validate(Scenario? scenario)
    {
        var errors = new Dictionary<string, string[]>(StringComparer.Ordinal);
        void Error(string key, string text) => errors[key] = new[] { text };
        if (scenario is null)
            return new(false, new Dictionary<string, string[]> { ["scenario"] = new[] { "A scenario object is required." } });
        if (scenario.SchemaVersion != "pqc.capacity.scenario.v1")
            Error("schemaVersion", "Supported schemaVersion is pqc.capacity.scenario.v1.");
        if (string.IsNullOrWhiteSpace(scenario.Name) || scenario.Name.Length > 120 || scenario.Name.Any(char.IsControl))
            Error("name", "Use a nonempty name of at most 120 characters without control characters.");
        if (scenario.ProfileId is not null && (scenario.ProfileId.Length > 80 || scenario.ProfileId.Any(char.IsControl)))
            Error("profileId", "Profile ID must be at most 80 characters without control characters.");
        if (scenario.Availability is not ("single" or "ha")) Error("availability", "Choose single or ha.");
        if (scenario.HistoryMode is not ("changed" or "full")) Error("historyMode", "Choose changed or full.");
        if (scenario.Platform is not ("unselected" or "managed-vm" or "cloud-foundry"))
            Error("platform", "Choose unselected, managed-vm or cloud-foundry.");
        if (scenario.Parameters is null) Error("parameters", "Parameters must be an object, not null.");
        else
        {
            if (scenario.Parameters.Count > Catalog.Definitions.Count)
            {
                Error("parameters", "Too many parameter keys.");
                return new(false, errors);
            }
            foreach (var pair in scenario.Parameters)
            {
                if (!DefinitionByKey.TryGetValue(pair.Key, out var d))
                    Error($"parameters.{pair.Key}", "Unknown parameter; keys are case-sensitive.");
                else if (!double.IsFinite(pair.Value)) Error($"parameters.{pair.Key}", "Use a finite number.");
                else if (pair.Value < d.Min || pair.Value > d.Max)
                    Error($"parameters.{pair.Key}", $"Value must be between {F(d.Min)} and {F(d.Max)} {d.Unit}.");
                else if (d.Integer && pair.Value != Math.Truncate(pair.Value))
                    Error($"parameters.{pair.Key}", "Use a whole number.");
            }
        }
        if (errors.Count != 0) return new(false, errors);
        var p = Resolve(scenario);
        double P(string key) => p[key];
        if (P("harvestHours") > P("collectionIntervalHours"))
            Error("parameters.harvestHours", "Harvest window cannot exceed the collection interval in this non-overlapping model.");
        var harvest = P("assets") * P("observationsPerAsset");
        var collections = Math.Max(1, Math.Ceiling(P("observationDays") * 24 / P("collectionIntervalHours")));
        if (harvest * collections > 9_007_199_254_740_991)
            Error("parameters.observationDays", "Retained membership count exceeds this model's exact numeric-count bound.");
        var burst = P("activeUsers") * P("apiCalls") / P("actionIntervalSec") * P("apiBurst");
        var ingest = harvest / (P("harvestHours") * 3600) * P("ingestBurst");
        var api = burst * P("apiCpuMs") / 1000 * P("growth") / P("apiUtilization");
        var worker = (ingest * P("workerCpuMs") / 1000 + P("workerBackgroundCores")) * P("growth") / P("workerUtilization");
        var sql = (burst * P("sqlApiCpuMs") / 1000 + ingest * P("sqlObservationCpuMs") / 1000 + P("sqlBackgroundCores")) * P("growth") / P("sqlUtilization");
        var failure = scenario.Availability == "ha" ? 1 : 0;
        if (Math.Ceiling(api / P("apiCpuPerInstance")) + failure > 10000)
            Error("parameters.activeUsers", "Modeled API topology exceeds the supported 10,000-instance planning bound.");
        if (Math.Ceiling(worker / P("workerCpuPerInstance")) + failure > 10000)
            Error("parameters.assets", "Modeled worker topology exceeds the supported 10,000-instance planning bound.");
        if (RoundUp(Math.Max(sql, P("sqlCpuMinimum")), P("sqlCpuIncrement")) > 65536)
            Error("parameters.sqlApiCpuMs", "Modeled SQL primary exceeds the supported 65,536-vCPU arithmetic bound; no such SKU is asserted.");
        return new(errors.Count == 0, errors);
    }

    private static Dictionary<string, double> Resolve(Scenario scenario)
    {
        var result = new Dictionary<string, double>(StringComparer.Ordinal);
        foreach (var d in Catalog.Definitions.OrderBy(d => d.Key, StringComparer.Ordinal))
            result[d.Key] = scenario.Parameters.TryGetValue(d.Key, out var value) ? value : d.DefaultValue;
        return result;
    }

    public static CapacityResult Calculate(Scenario scenario)
    {
        var validation = Validate(scenario);
        if (!validation.IsValid) throw new ScenarioValidationException(validation);
        var p = Resolve(scenario);
        var canonical = scenario with { Name = scenario.Name.Trim(), Parameters = p };
        var serialized = JsonSerializer.Serialize(new { modelVersion = ModelVersion,
            schemaVersion = canonical.SchemaVersion, name = canonical.Name, profileId = canonical.ProfileId,
            availability = canonical.Availability, historyMode = canonical.HistoryMode,
            platform = canonical.Platform, parameters = p });
        var hash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(serialized))).ToLowerInvariant();
        double P(string key) => p[key];
        var equations = new List<CapacityEquation>();
        void Equation(string id, string label, string formula, string substitution, double value, string unit,
            string basis = "assumed") => equations.Add(new(id, label, formula, substitution, value, unit, basis));

        var baseRps = P("activeUsers") * P("apiCalls") / P("actionIntervalSec");
        var rps = baseRps * P("apiBurst");
        var harvest = P("assets") * P("observationsPerAsset");
        var ingest = harvest / (P("harvestHours") * 3600);
        var peakIngest = ingest * P("ingestBurst");
        var collections = Math.Max(1, Math.Ceiling(P("observationDays") * 24 / P("collectionIntervalHours")));
        Equation("api-rate", "Interactive request rate", "active users × calls / action interval × burst",
            $"{F(P("activeUsers"))} × {F(P("apiCalls"))} / {F(P("actionIntervalSec"))} × {F(P("apiBurst"))}", rps, "requests/second");
        Equation("ingestion-rate", "Peak ingestion rate", "assets × observations/asset / (harvest hours × 3600) × burst",
            $"{F(P("assets"))} × {F(P("observationsPerAsset"))} / ({F(P("harvestHours"))} × 3600) × {F(P("ingestBurst"))}", peakIngest, "observations/second");
        var apiRaw = rps * P("apiCpuMs") / 1000;
        var workerRaw = peakIngest * P("workerCpuMs") / 1000 + P("workerBackgroundCores");
        var sqlRaw = rps * P("sqlApiCpuMs") / 1000 + peakIngest * P("sqlObservationCpuMs") / 1000 + P("sqlBackgroundCores");
        var apiCores = apiRaw * P("growth") / P("apiUtilization");
        var workerCores = workerRaw * P("growth") / P("workerUtilization");
        var sqlCores = sqlRaw * P("growth") / P("sqlUtilization");
        foreach (var item in new[] { ("api", apiRaw, apiCores), ("worker", workerRaw, workerCores), ("sql", sqlRaw, sqlCores) })
            Equation(item.Item1 + "-cpu", item.Item1.ToUpperInvariant() + " surviving CPU budget",
                "raw CPU-seconds/second × growth / target utilization",
                $"{F(item.Item2)} × {F(P("growth"))} / {F(P(item.Item1 + "Utilization"))}", item.Item3, "cores");
        var failure = scenario.Availability == "ha" ? 1 : 0;
        var apiInstances = Math.Max((int)P("minimumApiInstances"), failure + (int)Math.Ceiling(apiCores / P("apiCpuPerInstance")));
        var workerInstances = Math.Max((int)P("minimumWorkerInstances"), failure + (int)Math.Ceiling(workerCores / P("workerCpuPerInstance")));
        var sqlInstances = failure + 1;
        var sqlCpu = RoundUp(Math.Max(sqlCores, P("sqlCpuMinimum")), P("sqlCpuIncrement"));
        double Memory(string tier)
        {
            var memory = RoundUp(Math.Max(P(tier + "MemoryFloorGiB"), P(tier + "WorkingSetGiB") / P("memoryUtilization")), P("memoryIncrementGiB"));
            Equation(tier + "-memory", tier.ToUpperInvariant() + " memory per instance",
                "roundUp(max(memory floor, working set / target), memory increment)",
                $"roundUp(max({F(P(tier + "MemoryFloorGiB"))}, {F(P(tier + "WorkingSetGiB"))} / {F(P("memoryUtilization"))}), {F(P("memoryIncrementGiB"))})", memory, "GiB/instance");
            return memory;
        }
        var apiMemory = Memory("api"); var workerMemory = Memory("worker"); var sqlMemory = Memory("sql");
        var versions = scenario.HistoryMode == "full" ? harvest * collections : harvest * (1 + (collections - 1) * P("changeFractionPerCollection"));
        var memberships = harvest * collections;
        var assetsGiB = P("assets") * P("assetBytes") / GiB;
        var usesGiB = P("assets") * P("usesPerAsset") * P("useBytes") / GiB;
        var edgesGiB = P("assets") * P("edgesPerAsset") * P("edgeBytes") / GiB;
        var observationsGiB = versions * P("observationBytes") / GiB;
        var lineageGiB = memberships * P("lineageBytes") / GiB;
        var logicalGiB = assetsGiB + usesGiB + edgesGiB + observationsGiB + lineageGiB + P("auditGiB");
        var sqlProvision = logicalGiB * P("overhead") * P("growth") / P("maxFill");
        var sqlAllocated = RoundUp(sqlProvision, P("sqlDataIncrementGiB"));
        var rawCollections = Math.Max(1, Math.Ceiling(P("rawDays") * 24 / P("collectionIntervalHours")));
        var rawGiB = harvest * P("rawKiB") * 1024 * rawCollections * P("compression") / GiB;
        var reportsGiB = P("acceptedMiBPerDay") * P("reportDays") / 1024;
        var objectProvision = (rawGiB + reportsGiB + P("curatedEvidenceGiB")) * P("growth") / P("maxFill");
        var objectAllocated = RoundUp(objectProvision, P("objectIncrementGiB"));
        var backupSql = (P("backupFullCopies") * P("backupFullStoredGiB") + P("backupDifferentialCopies") * P("backupDifferentialStoredGiB") + P("backupLogDays") * P("backupLogGiBPerDay")) / P("maxFill");
        var backupEvidence = objectAllocated * P("independentEvidenceCopies");
        Equation("observation-history", "Retained observation versions",
            scenario.HistoryMode == "full" ? "observations/harvest × retained collections" : "observations/harvest × (1 + (collections − 1) × changed fraction)",
            scenario.HistoryMode == "full" ? $"{F(harvest)} × {F(collections)}" : $"{F(harvest)} × (1 + ({F(collections)} − 1) × {F(P("changeFractionPerCollection"))})", versions, "versions");
        Equation("lineage", "Retained collection membership", "observations/harvest × retained collections",
            $"{F(harvest)} × {F(collections)}", memberships, "associations");
        Equation("sql-data", "SQL data/index provision per copy", "logical GiB × physical multiplier × growth / maximum fill",
            $"{F(logicalGiB)} × {F(P("overhead"))} × {F(P("growth"))} / {F(P("maxFill"))}", sqlProvision, "GiB/copy");
        Equation("evidence-store", "Primary evidence-object provision", "(raw + reports + curated evidence) × growth / maximum fill",
            $"({F(rawGiB)} + {F(reportsGiB)} + {F(P("curatedEvidenceGiB"))}) × {F(P("growth"))} / {F(P("maxFill"))}", objectProvision, "GiB");
        Equation("sql-backup", "Separate SQL backup provision", "(full copies × stored size + differential copies × stored size + log days × daily bytes) / maximum fill",
            $"({F(P("backupFullCopies"))} × {F(P("backupFullStoredGiB"))} + {F(P("backupDifferentialCopies"))} × {F(P("backupDifferentialStoredGiB"))} + {F(P("backupLogDays"))} × {F(P("backupLogGiBPerDay"))}) / {F(P("maxFill"))}", backupSql, "GiB");
        var allocations = new List<CapacityAllocation>();
        void Allocate(string tier, int instances, double cpu, double memory, double disk, double required, double surviving)
            => allocations.Add(new(tier, instances, cpu, memory, instances * cpu, instances * memory, disk, required, surviving));
        Allocate("api", apiInstances, P("apiCpuPerInstance"), apiMemory, P("apiDiskGiB"), apiCores, (apiInstances - failure) * P("apiCpuPerInstance"));
        Allocate("worker", workerInstances, P("workerCpuPerInstance"), workerMemory, P("workerDiskGiB"), workerCores, (workerInstances - failure) * P("workerCpuPerInstance"));
        Allocate("sql", sqlInstances, sqlCpu, sqlMemory, sqlAllocated + P("sqlOsGiB") + P("sqlLogGiB") + P("sqlTempdbGiB"), sqlCores, sqlCpu);
        if (failure == 1) Allocate("witness", 1, P("witnessCpu"), P("witnessMemoryGiB"), P("witnessDiskGiB"), 0, 0);
        Equation("api-instances", "API instance count", "max(minimum instances, failed instances + ceil(required cores / cores per instance))",
            $"max({F(P("minimumApiInstances"))}, {failure} + ceil({F(apiCores)} / {F(P("apiCpuPerInstance"))}))", apiInstances, "instances");
        Equation("worker-instances", "Worker instance count", "max(minimum instances, failed instances + ceil(required cores / cores per instance))",
            $"max({F(P("minimumWorkerInstances"))}, {failure} + ceil({F(workerCores)} / {F(P("workerCpuPerInstance"))}))", workerInstances, "instances");
        Equation("sql-primary", "One SQL primary CPU allocation", "roundUp(max(required cores, minimum cores), CPU increment)",
            $"roundUp(max({F(sqlCores)}, {F(P("sqlCpuMinimum"))}), {F(P("sqlCpuIncrement"))})", sqlCpu, "vCPU/primary");
        var totals = new Dictionary<string, double>
        {
            ["cpu"] = allocations.Sum(a => a.TotalCpu), ["memoryGiB"] = allocations.Sum(a => a.TotalMemoryGiB),
            ["localDiskGiB"] = allocations.Sum(a => a.Instances * a.LocalDiskGiBPerInstance),
            ["instanceCount"] = allocations.Sum(a => a.Instances), ["evidenceGiB"] = objectAllocated,
            ["backupGiB"] = backupSql + backupEvidence
        };
        var costBreakdown = new Dictionary<string, double>();
        var pricingAvailable = P("pricingProvided") == 1;
        if (pricingAvailable)
        {
            costBreakdown["compute"] = totals["cpu"] * P("vcpuMonthlyRate");
            costBreakdown["memory"] = totals["memoryGiB"] * P("ramGiBMonthlyRate");
            costBreakdown["localDisk"] = totals["localDiskGiB"] * P("localDiskGiBMonthlyRate");
            costBreakdown["primaryEvidence"] = objectAllocated * P("evidenceGiBMonthlyRate");
            costBreakdown["separateBackups"] = totals["backupGiB"] * P("backupGiBMonthlyRate");
            costBreakdown["sqlLicensing"] = sqlInstances * sqlCpu * P("sqlCoreMonthlyRate");
        }
        var cost = new CapacityCost(pricingAvailable, pricingAvailable ? costBreakdown.Values.Sum() : null,
            "USD", "User-entered resource unit rates, not a quotation. SQL licensing includes both HA copies conservatively. Excludes shared ingress/identity/platform services, DR compute, operations, support, egress, requests, taxes and vendor-specific minimums. Do not double-count bundled VM prices.", costBreakdown);
        if (pricingAvailable) Equation("cost", "Illustrative monthly cost", "compute + memory + local disk + primary evidence + separate backups + SQL licensing",
            string.Join(" + ", costBreakdown.Values.Select(F)), cost.TotalMonthly!.Value, "USD/month", "user-entered rates");
        var warnings = new List<CapacityNotice>
        {
            new("unmeasured-coefficients", "CPU milliseconds, record sizes, compression and operating floors are assumptions until measured against the actual schema and workload."),
            new("recovery-unverified", $"RPO {F(P("rpoMinutes"))} minutes and RTO {F(P("rtoHours"))} hours are proposed targets, not achieved recovery results."),
            new("history-design-unqualified", "Changed-history storage assumes lossless reconstruction with retained lineage; compact encoding, indexing and pruning are not implemented or qualified by this calculator."),
            new("auxiliary-storage-unmeasured", "OS/scratch/log/tempdb and backup quantities are explicit allowances, not measured peak demand; IOPS, latency and restore workspace need separate qualification."),
            new("backup-allowance-independent", "SQL backup sizes/counts are independent entered allowances: they do not automatically scale with assets, retained history or the growth factor. Enter projected stored backup sizes. Restore workspace, evidence-version history and backup-provider redundancy are additional budgets.")
        };
        if (P("backupFullCopies") == 0 || P("backupFullStoredGiB") == 0)
            warnings.Add(new("sql-full-backup-unbudgeted", "No full SQL backup bytes are budgeted. An independently approved recoverable backup chain and its storage still need to be established."));
        if (P("independentEvidenceCopies") == 0)
            warnings.Add(new("evidence-backup-unbudgeted", "No additional recoverable evidence copy is budgeted. Primary object-store replication must not be treated as proven independent backup."));
        if (pricingAvailable)
        {
            warnings.Add(new("cost-excludes-services", "Monthly cost is only the entered resource-price subtotal. Shared platform/identity/ingress, DR compute, operations/support, egress/request fees, taxes and vendor minimums remain outside this figure."));
            if (new[] { "vcpuMonthlyRate", "ramGiBMonthlyRate", "localDiskGiBMonthlyRate", "evidenceGiBMonthlyRate", "backupGiBMonthlyRate", "sqlCoreMonthlyRate" }.Any(key => P(key) == 0))
                warnings.Add(new("zero-price-categories", "One or more entered unit rates are zero. Those categories add no modeled cost; this is not evidence that the resources or licenses are free or already covered."));
        }
        if (P("activeUsers") > P("namedUsers")) warnings.Add(new("active-exceeds-named", "The concurrent-active stress case exceeds named users. This is deliberate only if retained as a separately agreed stress target."));
        if (P("sourceIngressMaxRecordsPerSecond") == 0) warnings.Add(new("source-throughput-unknown", "Source throughput and rate limits are unknown; the harvest window is not established by available worker CPU."));
        else if (P("sourceIngressMaxRecordsPerSecond") < ingest * P("growth")) warnings.Add(new("source-throughput-insufficient", $"Entered source throughput is below the growth-adjusted sustainable harvest demand of {F(ingest * P("growth"))} observations/second. Queueing or a longer window is needed; more workers do not resolve a source quota."));
        if (P("curatedEvidenceGiB") == 0) warnings.Add(new("curated-retention-unbudgeted", "No additional curated evidence/manifests budget is entered. Report-file retention does not preserve underlying evidence reproducibility; authorize and budget required evidence before expiry."));
        if (memberships >= 1_000_000_000) warnings.Add(new("billion-lineage-associations", "Retained lineage exceeds one billion associations; the row-size assumption is not proof of feasible indexing, partitioning or report reconstruction."));
        if (scenario.HistoryMode == "full") warnings.Add(new("full-history", "Full mode retains every harvest's observation versions in SQL, as well as collection lineage. Storage may be orders of magnitude larger than the current estate."));
        if (sqlCpu / sqlCores < 1.1) warnings.Add(new("sql-rounding-margin", "The SQL CPU allocation is less than 10% above the growth-and-utilization-adjusted requirement. Modest coefficient changes can exceed the selected target; this does not mean raw utilization is near 100%."));
        if (scenario.Availability == "single") warnings.Add(new("single-failure-domain", "Single mode carries no instance-failure reserve or SQL failover copy; it must not be described as highly available."));
        if (scenario.Platform == "cloud-foundry") warnings.Add(new("platform-unqualified", "Cloud Foundry quotas, CPU entitlement, placement and service bindings require confirmation; dedicated SQL and evidence services are not assumed to be supplied by the platform."));
        if (P("apiWorkingSetGiB") == 0 || P("workerWorkingSetGiB") == 0 || P("sqlWorkingSetGiB") == 0)
            warnings.Add(new("memory-unmeasured", "At least one working set is unmeasured; its memory floor is an operating-budget assumption, not a workload-derived requirement."));
        var blockers = new List<CapacityNotice>
        {
            new("qualification-required", "Load, isolation, failover, backup/restore and owner review are required before deployment capacity can be accepted.", "blocker"),
            new("authorization-required", "This configurator cannot authorize procurement, retention, source access, deployment or migration execution.", "blocker")
        };
        if (P("sourceIngressMaxRecordsPerSecond") > 0 && P("sourceIngressMaxRecordsPerSecond") < ingest * P("growth"))
            blockers.Add(new("source-throughput-insufficient", "The entered source limit cannot sustain the growth-adjusted harvest window. Revise the window, scope or independently qualified source capacity before accepting this scenario.", "blocker"));
        if (scenario.Platform == "unselected") blockers.Add(new("platform-decision", "Runtime platform, SQL edition/OS/HA topology and independent failure domains remain undecided.", "blocker"));
        var assumptions = new[]
        {
            "All output is a reproducible planning candidate, never a benchmark, vendor SKU guarantee or enterprise approval.",
            "Logical assets, cryptographic uses, current observations and retained collection membership are different populations.",
            "API and worker CPU coefficients exclude SQL CPU to avoid counting the same processing twice; elapsed I/O wait is not consumed CPU.",
            "HA reserves one API/worker instance failure and a complete SQL writer copy; actual host/zone placement and correlated failures require separate design.",
            "Memory floors and per-instance measured working sets are independent of asset density unless the user supplies a measured relationship.",
            "Data/index, object storage, backup storage and local log/tempdb/OS are separate quantities. Provider redundancy and DR compute are not inferred.",
            "Retained raw collections use ceiling(days × 24 / collection interval); calendar-boundary implementation and adopted retention policy remain separate.",
            "The object model has no additional full normalized snapshot copy. Add required copies and curated evidence explicitly; never discard needed provenance to fit the estimate.",
            "Cost rates are optional user inputs; a zero price is not a market-price claim. Counts include allocated resources, not only nominally busy resources.",
            "Phase 3/4 migration execution is not enabled or included in this assessment capacity model."
        };
        return new(ModelVersion, hash, canonical,
            new Dictionary<string, double> { ["baseRequestsPerSecond"] = baseRps, ["burstRequestsPerSecond"] = rps,
                ["observationsPerHarvest"] = harvest, ["steadyObservationsPerSecond"] = ingest,
                ["burstObservationsPerSecond"] = peakIngest, ["retainedCollections"] = collections },
            new Dictionary<string, double> { ["apiRequiredCores"] = apiCores, ["workerRequiredCores"] = workerCores,
                ["sqlRequiredCores"] = sqlCores, ["apiRawCores"] = apiRaw, ["workerRawCores"] = workerRaw, ["sqlRawCores"] = sqlRaw },
            allocations, new Dictionary<string, double>
            {
                ["assetsGiB"] = assetsGiB, ["usesGiB"] = usesGiB, ["edgesGiB"] = edgesGiB,
                ["observationVersionsGiB"] = observationsGiB, ["lineageGiB"] = lineageGiB, ["auditGiB"] = P("auditGiB"),
                ["retainedObservationVersions"] = versions, ["retainedLineageMemberships"] = memberships,
                ["sqlLogicalGiB"] = logicalGiB, ["sqlProvisionGiBPerCopy"] = sqlProvision,
                ["sqlAllocatedGiBPerCopy"] = sqlAllocated, ["sqlDataGiBAllCopies"] = sqlAllocated * sqlInstances,
                ["rawEvidenceGiB"] = rawGiB, ["acceptedReportsGiB"] = reportsGiB, ["curatedEvidenceGiB"] = P("curatedEvidenceGiB"),
                ["objectProvisionGiB"] = objectProvision, ["objectAllocatedGiB"] = objectAllocated,
                ["backupSqlGiB"] = backupSql, ["backupEvidenceGiB"] = backupEvidence
            }, totals, equations, warnings, blockers, assumptions, cost);
    }

    private static double RoundUp(double value, double increment) => Math.Ceiling(value / increment) * increment;
    private static string F(double value) => value.ToString("0.########", CultureInfo.InvariantCulture);
}
