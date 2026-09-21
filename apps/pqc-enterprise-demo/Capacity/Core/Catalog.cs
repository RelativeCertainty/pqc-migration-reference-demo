namespace PqcCapacityConfigurator.Core;

public static class Catalog
{
    private static ParameterDefinition D(string key, string label, string group, string unit,
        double value, double min, double max, bool integer, string description, string basis = "assumed")
        => new(key, label, group, unit, value, min, max, integer, description, basis);

    public static IReadOnlyList<ParameterDefinition> Definitions { get; } = Array.AsReadOnly(new[]
    {
        D("assets", "Logical assets", "Workload", "assets", 1_000_000, 1, 100_000_000, true, "A logical asset is not a database row; uses, relationships and retained observations are additional.", "planning target"),
        D("namedUsers", "Named users", "Workload", "users", 240, 1, 1_000_000, true, "Account population, distinct from concurrently active users.", "planning target"),
        D("activeUsers", "Concurrent active users", "Workload", "users", 250, 1, 1_000_000, true, "Synthetic stress target; not simultaneous in-flight requests. May deliberately exceed named users.", "planning target"),
        D("apiCalls", "API calls per action", "Workload", "calls", 6, 1, 1000, false, "Includes screen fan-out, save and polling in the representative action mix."),
        D("actionIntervalSec", "Action interval", "Workload", "seconds", 15, 0.1, 3600, false, "Mean interval between modeled actions per active user."),
        D("apiBurst", "Interactive burst factor", "Workload", "factor", 1.5, 1, 20, false, "Explicit peak-to-base request-rate assumption."),
        D("observationsPerAsset", "Observations per asset per harvest", "Workload", "observations/asset", 10, 0.01, 1000, false, "Source record density, not a fixed product invariant."),
        D("harvestHours", "Full-harvest window", "Workload", "hours", 8, 0.01, 8760, false, "Desired time to process one full harvest; source quotas may prevent it.", "planning target"),
        D("ingestBurst", "Ingestion burst factor", "Workload", "factor", 3, 1, 20, false, "Peak-to-average normalization rate; does not authorize source concurrency."),
        D("sourceIngressMaxRecordsPerSecond", "Qualified source throughput limit", "Workload", "observations/second", 0, 0, 100_000_000, false, "Zero means unknown, not unlimited. Set only from qualified API/page-rate measurements."),
        D("apiCpuMs", "API CPU cost per request", "CPU", "CPU milliseconds", 20, 0.01, 10000, false, "Consumed application CPU time, not elapsed response latency; placeholder until measured."),
        D("workerCpuMs", "Worker CPU cost per observation", "CPU", "CPU milliseconds", 3, 0.001, 10000, false, "Normalization CPU, excluding SQL CPU; placeholder until measured."),
        D("sqlApiCpuMs", "SQL CPU cost per API request", "CPU", "CPU milliseconds", 8, 0.001, 10000, false, "SQL CPU attributed to the representative request mix; not network wait."),
        D("sqlObservationCpuMs", "SQL CPU cost per observation", "CPU", "CPU milliseconds", 4, 0.001, 10000, false, "SQL CPU attributed to ingestion, including the intended index design."),
        D("workerBackgroundCores", "Worker reporting/background reserve", "CPU", "cores", 3, 0, 1000, false, "Bounded simultaneous reporting and background CPU demand; baseline 2 + 1 cores."),
        D("sqlBackgroundCores", "SQL reporting/maintenance reserve", "CPU", "cores", 3, 0, 1000, false, "Bounded reporting and maintenance CPU demand; baseline 2 + 1 cores."),
        D("apiUtilization", "API target CPU utilization", "CPU", "fraction", 0.65, 0.1, 0.9, false, "Target after the admitted instance failure; reserve is not a latency guarantee."),
        D("workerUtilization", "Worker target CPU utilization", "CPU", "fraction", 0.65, 0.1, 0.9, false, "Target after the admitted instance failure."),
        D("sqlUtilization", "SQL target CPU utilization", "CPU", "fraction", 0.70, 0.1, 0.9, false, "One surviving primary must carry all modeled writes."),
        D("growth", "Growth allowance", "CPU", "factor", 1.3, 1, 5, false, "Multiplies modeled CPU demand and retained bytes; separate from utilization/free-space reserve."),
        D("apiCpuPerInstance", "API CPU per instance", "Topology", "vCPU", 4, 1, 128, true, "Placement choice; instance count is derived to retain the CPU budget after failure."),
        D("workerCpuPerInstance", "Worker CPU per instance", "Topology", "vCPU", 8, 1, 128, true, "Placement choice; larger instances and fewer replicas are alternative candidates."),
        D("minimumApiInstances", "Minimum API instances", "Topology", "instances", 1, 1, 100, true, "HA additionally reserves one failed instance; shared-host failure still requires placement proof."),
        D("minimumWorkerInstances", "Minimum worker instances", "Topology", "instances", 1, 1, 100, true, "Availability mode and workload can require more than this minimum."),
        D("sqlCpuMinimum", "SQL primary minimum CPU", "Topology", "vCPU", 16, 1, 512, true, "Provisional operating floor, not a vendor-required minimum."),
        D("sqlCpuIncrement", "SQL CPU rounding increment", "Topology", "vCPU", 8, 1, 128, true, "Rounds one primary's required cores upward; HA does not divide write demand."),
        D("witnessCpu", "Illustrative witness CPU", "Topology", "vCPU", 2, 1, 32, true, "HA-only placeholder; quorum implementation depends on the selected platform."),
        D("witnessMemoryGiB", "Illustrative witness memory", "Memory", "GiB", 4, 1, 128, false, "HA-only placeholder, not a third SQL data copy."),
        D("apiMemoryFloorGiB", "API memory floor", "Memory", "GiB/instance", 16, 1, 2048, false, "Provisional total-process/OS allowance; not derived from the asset count."),
        D("workerMemoryFloorGiB", "Worker memory floor", "Memory", "GiB/instance", 32, 1, 4096, false, "Provisional bound for runtime, batches, report jobs, caches and operating overhead."),
        D("sqlMemoryFloorGiB", "SQL memory floor", "Memory", "GiB/copy", 128, 1, 16384, false, "Provisional allowance for hot data/indexes, query grants and OS/non-buffer allocations."),
        D("apiWorkingSetGiB", "API measured working set", "Memory", "GiB/instance", 0, 0, 2048, false, "Zero means unmeasured. Nonzero must include all required instance memory consumers."),
        D("workerWorkingSetGiB", "Worker measured working set", "Memory", "GiB/instance", 0, 0, 4096, false, "Zero means unmeasured; use the admitted concurrent batch/report load."),
        D("sqlWorkingSetGiB", "SQL measured working set", "Memory", "GiB/copy", 0, 0, 16384, false, "Zero means unmeasured; include OS/native consumers outside server-memory limits."),
        D("memoryUtilization", "Working-set memory target", "Memory", "fraction", 0.8, 0.1, 0.95, false, "Memory candidate = maximum of floor and measured working set / target, rounded upward."),
        D("memoryIncrementGiB", "Memory rounding increment", "Memory", "GiB", 4, 1, 128, true, "Allocation increment, not an assertion about available vendor VM sizes."),
        D("usesPerAsset", "Cryptographic uses per asset", "History", "uses/asset", 4, 0, 1000, false, "Key establishment, signatures and data protection remain distinct uses."),
        D("edgesPerAsset", "Relationships per asset", "History", "edges/asset", 8, 0, 10000, false, "Mean density; qualification must include high-degree/skewed relationships."),
        D("assetBytes", "Logical asset row size", "History", "bytes", 2048, 1, 1_048_576, true, "Assumed logical bytes before the index/physical multiplier."),
        D("useBytes", "Cryptographic-use row size", "History", "bytes", 2048, 1, 1_048_576, true, "Assumed logical bytes, not measured SQL page occupancy."),
        D("edgeBytes", "Relationship row size", "History", "bytes", 256, 1, 1_048_576, true, "Assumed logical bytes per relationship."),
        D("observationBytes", "Observation-version size", "History", "bytes", 1024, 1, 1_048_576, true, "Normalized logical record size; retained full source objects are separate."),
        D("lineageBytes", "Collection-membership size", "History", "bytes", 32, 1, 65536, true, "Assumed compact membership bytes; preserve timestamps, scope and reconstruction semantics."),
        D("auditGiB", "Workflow/audit data allowance", "History", "GiB", 5, 0, 100000, false, "Provisional logical bytes; actual workflow/event retention must be measured."),
        D("observationDays", "Observation history window", "History", "days", 396, 1, 36500, true, "Planning duration, not adopted retention authority."),
        D("collectionIntervalHours", "Full-harvest interval", "History", "hours", 24, 1, 8760, false, "Retained harvest count = ceiling(history days × 24 / interval), minimum one."),
        D("changeFractionPerCollection", "Changed fraction per collection", "History", "fraction", 0.02, 0, 1, false, "Changed mode retains one initial population then this fraction per later collection; not deduplication proof."),
        D("overhead", "SQL index/physical multiplier", "Storage", "factor", 2, 1, 10, false, "Replace with measured schema/index/page overhead, including lineage representation."),
        D("maxFill", "Maximum storage fill", "Storage", "fraction", 0.7, 0.1, 0.95, false, "Allocated bytes = retained bytes × growth / maximum fill; separate from growth."),
        D("sqlDataIncrementGiB", "SQL data allocation increment", "Storage", "GiB", 1024, 1, 65536, true, "Historical 1-TiB rounding choice; smaller increments are available for smaller candidates."),
        D("rawKiB", "Raw source bytes per observation", "Storage", "KiB", 4, 0.01, 1024, false, "Mean pre-compression evidence object size."),
        D("rawDays", "Raw evidence retention", "Storage", "days", 30, 1, 36500, true, "Proposed duration; actual retention needs data-handling and reliance authority."),
        D("compression", "Stored/original raw-byte ratio", "Storage", "fraction", 0.6, 0.01, 1, false, "0.6 means stored size is 60% of original, not 60% saved."),
        D("acceptedMiBPerDay", "Accepted report artifacts per day", "Storage", "MiB/day", 50, 0, 1_000_000, false, "Report bytes do not themselves preserve underlying evidence reproducibility."),
        D("reportDays", "Accepted-report archive window", "Storage", "days", 2555, 1, 36500, true, "Seven years approximated as 2,555 days; not an adopted policy."),
        D("curatedEvidenceGiB", "Additional curated evidence/manifests", "Storage", "GiB", 0, 0, 100_000_000, false, "Separate incremental retained evidence for report reliance. Zero is unbudgeted, not permission to delete."),
        D("objectIncrementGiB", "Evidence-object allocation increment", "Storage", "GiB", 1024, 1, 65536, true, "Logical quota before provider replication, independent backup and DR."),
        D("apiDiskGiB", "API OS/log disk", "Storage", "GiB/instance", 80, 1, 65536, false, "Provisional bounded OS/log allowance, not measured consumption."),
        D("workerDiskGiB", "Worker OS/scratch disk", "Storage", "GiB/instance", 160, 1, 65536, false, "Provisional scratch/log allowance; bound concurrent jobs and retention."),
        D("sqlOsGiB", "SQL OS disk", "Storage", "GiB/copy", 100, 1, 65536, false, "Provisional operating-system allocation."),
        D("sqlLogGiB", "SQL transaction log disk", "Storage", "GiB/copy", 128, 1, 1_000_000, false, "Explicit candidate allowance; qualify peak log generation and blocked truncation."),
        D("sqlTempdbGiB", "SQL tempdb disk", "Storage", "GiB/copy", 64, 1, 1_000_000, false, "Explicit candidate allowance; qualify spills, version-store peaks and maintenance overlap."),
        D("witnessDiskGiB", "Witness OS disk", "Storage", "GiB", 40, 1, 65536, false, "HA-only provisional witness allowance."),
        D("backupFullCopies", "Retained full SQL backups", "Backup", "copies", 4, 0, 1000, true, "Illustrative backup count, not an adopted backup schedule."),
        D("backupFullStoredGiB", "Stored bytes per full backup", "Backup", "GiB", 500, 0, 100_000_000, false, "Independent measured/compressed backup assumption, not inferred from allocated SQL volume."),
        D("backupDifferentialCopies", "Retained differential backups", "Backup", "copies", 6, 0, 1000, true, "Illustrative count; restore chains must be qualified."),
        D("backupDifferentialStoredGiB", "Stored bytes per differential", "Backup", "GiB", 100, 0, 100_000_000, false, "Illustrative stored bytes per differential backup."),
        D("backupLogDays", "Transaction-log backup window", "Backup", "days", 14, 0, 36500, true, "Independent example retention; no schedule is enabled."),
        D("backupLogGiBPerDay", "Stored transaction-log backups", "Backup", "GiB/day", 50, 0, 100_000_000, false, "Measure actual transaction-log bytes and compression."),
        D("independentEvidenceCopies", "Additional recoverable evidence copies", "Backup", "copies", 1, 0, 10, true, "Independent copies beyond the primary logical object quota; provider replication alone is not backup proof."),
        D("rpoMinutes", "Proposed recovery point objective", "Backup", "minutes", 15, 0, 10080, false, "Planning target only; this engine does not establish backup frequency or achieved data loss.", "planning target"),
        D("rtoHours", "Proposed recovery time objective", "Backup", "hours", 4, 0.01, 720, false, "Planning target only; restore, failover and evidence consistency require actual tests.", "planning target"),
        D("pricingProvided", "Use entered price assumptions", "Costs", "0/1", 0, 0, 1, true, "Zero leaves cost unavailable; one uses explicitly entered USD unit rates, including any zero rates."),
        D("vcpuMonthlyRate", "Compute unit price", "Costs", "USD/vCPU-month", 0, 0, 100000, false, "For all allocated instances. Do not enter both bundled VM price and its constituent resources."),
        D("ramGiBMonthlyRate", "Memory unit price", "Costs", "USD/GiB-month", 0, 0, 100000, false, "Resource-based price assumption; not an actual provider quotation."),
        D("localDiskGiBMonthlyRate", "Local disk unit price", "Costs", "USD/GiB-month", 0, 0, 100000, false, "All allocated local disks, including both SQL copies in HA mode."),
        D("evidenceGiBMonthlyRate", "Primary evidence quota unit price", "Costs", "USD/GiB-month", 0, 0, 100000, false, "One allocated logical object quota; provider internal replication is not added separately."),
        D("backupGiBMonthlyRate", "Backup unit price", "Costs", "USD/GiB-month", 0, 0, 100000, false, "SQL backup reserve plus explicitly selected additional recoverable evidence copies."),
        D("sqlCoreMonthlyRate", "SQL licensing unit price", "Costs", "USD/core-month", 0, 0, 100000, false, "Conservatively charges both SQL copies; actual rights, agreements and passive failover treatment require confirmation.")
    });

    public static IReadOnlyList<Scenario> Presets()
    {
        Scenario Make(string id, string name, Dictionary<string, double> overrides, string availability = "ha")
        {
            var values = Definitions.ToDictionary(d => d.Key, d => d.DefaultValue, StringComparer.Ordinal);
            foreach (var pair in overrides) values[pair.Key] = pair.Value;
            return new Scenario { Name = name, ProfileId = id, Availability = availability, Parameters = values };
        }
        return new[]
        {
            Make("mvp", "MVP qualification candidate", new() {
                ["assets"] = 100_000, ["namedUsers"] = 40, ["activeUsers"] = 10,
                ["observationDays"] = 90, ["rawDays"] = 7,
                ["apiMemoryFloorGiB"] = 4, ["workerMemoryFloorGiB"] = 8, ["sqlMemoryFloorGiB"] = 32,
                ["sqlDataIncrementGiB"] = 64, ["objectIncrementGiB"] = 64 }, "single"),
            Make("growth", "Growth qualification candidate", new() {
                ["assets"] = 500_000, ["namedUsers"] = 120, ["activeUsers"] = 60,
                ["apiMemoryFloorGiB"] = 8, ["workerMemoryFloorGiB"] = 16, ["sqlMemoryFloorGiB"] = 64,
                ["sqlDataIncrementGiB"] = 256, ["objectIncrementGiB"] = 256 }),
            Make("enterprise", "Enterprise historical stress candidate", new())
        };
    }
}
