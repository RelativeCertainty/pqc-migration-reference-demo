namespace PqcCapacityConfigurator.Core;

/// <summary>Small deterministic arithmetic checks. No infrastructure or synthetic asset population is created.</summary>
public static class CapacitySelfTest
{
    public static IReadOnlyList<string> Run()
    {
        var passed = new List<string>();
        void Check(string id, bool condition)
        {
            if (!condition) throw new InvalidOperationException("Capacity self-test failed: " + id);
            passed.Add(id);
        }
        static bool Near(double actual, double expected) => Math.Abs(actual - expected) <= Math.Max(1e-8, Math.Abs(expected) * 1e-10);
        static Scenario Change(Scenario input, string key, double value)
        {
            var parameters = new Dictionary<string, double>(input.Parameters, StringComparer.Ordinal) { [key] = value };
            return input with { Parameters = parameters };
        }
        var enterprise = Catalog.Presets().Single(p => p.ProfileId == "enterprise");
        var result = CapacityEngine.Calculate(enterprise);
        Check("catalog-keys-unique", Catalog.Definitions.Select(d => d.Key).Distinct(StringComparer.Ordinal).Count() == Catalog.Definitions.Count);
        Check("default-api-six-cores", Near(result.Demands["apiRequiredCores"], 6));
        Check("default-worker-12.25-cores", Near(result.Demands["workerRequiredCores"], 12.25));
        Check("default-sql-15.538-cores", Near(result.Demands["sqlRequiredCores"], 15.53809523809524));
        Check("default-total-70-cpu", Near(result.Totals["cpu"], 70));
        Check("default-total-404-GiB", Near(result.Totals["memoryGiB"], 404));
        Check("default-local-3392-GiB", Near(result.Totals["localDiskGiB"], 3392));
        Check("default-89M-observation-versions", Near(result.Storage["retainedObservationVersions"], 89_000_000));
        Check("default-3.96B-memberships", Near(result.Storage["retainedLineageMemberships"], 3_960_000_000));
        Check("default-sql-provision", Near(result.Storage["sqlProvisionGiBPerCopy"], 814.6851239885603));
        Check("default-sql-rounded-1TiB", Near(result.Storage["sqlAllocatedGiBPerCopy"], 1024));
        Check("default-object-provision", Near(result.Storage["objectProvisionGiB"] / 1024, 1.4715705599103657));
        Check("default-object-rounded-2TiB", Near(result.Storage["objectAllocatedGiB"], 2048));
        Check("default-warning-stress-exceeds-named", result.Warnings.Any(w => w.Code == "active-exceeds-named"));
        Check("no-deployment-or-performance-claim", !result.Deployable && !result.PerformanceVerified && result.Blockers.Count > 0);
        Check("pricing-unavailable-not-free", !result.Cost.IsAvailable && result.Cost.TotalMonthly is null && result.Cost.Breakdown.Count == 0);
        var priced = CapacityEngine.Calculate(Change(Change(Change(enterprise, "pricingProvided", 1), "vcpuMonthlyRate", 10), "sqlCoreMonthlyRate", 20));
        Check("explicit-cost-all-allocated-copies", Near(priced.Cost.TotalMonthly!.Value, 70 * 10 + 32 * 20));
        Check("cost-zero-and-excluded-rates-visible", priced.Warnings.Any(w => w.Code == "zero-price-categories") && priced.Warnings.Any(w => w.Code == "cost-excludes-services"));
        Check("backup-independent-allowance-visible", result.Warnings.Any(w => w.Code == "backup-allowance-independent"));
        Check("all-presets-valid", Catalog.Presets().All(p => CapacityEngine.Validate(p).IsValid));
        var single = CapacityEngine.Calculate(enterprise with { Availability = "single" });
        Check("ha-adds-failure-reserve", result.Totals["cpu"] > single.Totals["cpu"] && result.Totals["memoryGiB"] > single.Totals["memoryGiB"]);
        Check("ha-does-not-divide-sql-writes", Near(single.Demands["sqlRequiredCores"], result.Demands["sqlRequiredCores"]) && single.Allocations.Single(a => a.Tier == "sql").Instances == 1);
        Check("surviving-capacity-admits-work", result.Allocations.Where(a => a.Tier != "witness").All(a => a.SurvivingCores >= a.RequiredCores));
        var more = CapacityEngine.Calculate(Change(enterprise, "assets", 2_000_000));
        Check("asset-growth-increases-storage-worker-demand", more.Storage["sqlProvisionGiBPerCopy"] > result.Storage["sqlProvisionGiBPerCopy"] && more.Demands["workerRequiredCores"] > result.Demands["workerRequiredCores"]);
        var longer = CapacityEngine.Calculate(Change(enterprise, "observationDays", 792));
        Check("longer-history-increases-storage", longer.Storage["sqlProvisionGiBPerCopy"] > result.Storage["sqlProvisionGiBPerCopy"]);
        var full = CapacityEngine.Calculate(enterprise with { HistoryMode = "full" });
        Check("full-history-retains-full-populations", Near(full.Storage["retainedObservationVersions"], 3_960_000_000) && full.Storage["sqlProvisionGiBPerCopy"] > result.Storage["sqlProvisionGiBPerCopy"]);
        Check("full-history-14.186TiB", Near(full.Storage["sqlProvisionGiBPerCopy"] / 1024, 14.18614691921643));
        var noChanges = CapacityEngine.Calculate(Change(enterprise, "changeFractionPerCollection", 0));
        Check("unchanged-records-preserve-lineage", Near(noChanges.Storage["retainedObservationVersions"], 10_000_000) && Near(noChanges.Storage["retainedLineageMemberships"], 3_960_000_000));
        var allChanged = CapacityEngine.Calculate(Change(enterprise, "changeFractionPerCollection", 1));
        Check("all-changed-equivalent-storage-to-full", Near(allChanged.Storage["sqlProvisionGiBPerCopy"], full.Storage["sqlProvisionGiBPerCopy"]));
        var measured = CapacityEngine.Calculate(Change(enterprise, "apiWorkingSetGiB", 40));
        Check("memory-respects-working-set-headroom", Near(measured.Allocations.Single(a => a.Tier == "api").MemoryGiBPerInstance, 52));
        var inadequateSource = CapacityEngine.Calculate(Change(enterprise, "sourceIngressMaxRecordsPerSecond", 1));
        Check("source-limit-not-fixed-with-cpu", inadequateSource.Warnings.Any(w => w.Code == "source-throughput-insufficient") && inadequateSource.Blockers.Any(w => w.Code == "source-throughput-insufficient"));
        var curated = CapacityEngine.Calculate(Change(enterprise, "curatedEvidenceGiB", 100));
        Check("curated-evidence-adds-budget", curated.Storage["objectProvisionGiB"] > result.Storage["objectProvisionGiB"] && !curated.Warnings.Any(w => w.Code == "curated-retention-unbudgeted"));
        var reordered = enterprise with { Parameters = enterprise.Parameters.Reverse().ToDictionary(p => p.Key, p => p.Value, StringComparer.Ordinal) };
        Check("canonical-hash-independent-of-key-order", result.InputHash == CapacityEngine.Calculate(reordered).InputHash);
        Check("changed-input-changes-hash", result.InputHash != more.InputHash);
        Check("default-merge-explicit-in-output", CapacityEngine.Calculate(new Scenario()).Scenario.Parameters.Count == Catalog.Definitions.Count);
        Check("input-not-mutated", enterprise.Parameters["assets"] == 1_000_000);
        Check("reject-unknown-key", !CapacityEngine.Validate(Change(enterprise, "unexpected", 1)).IsValid);
        Check("reject-wrong-case-key", !CapacityEngine.Validate(Change(enterprise, "Assets", 1)).IsValid);
        Check("reject-nan", !CapacityEngine.Validate(Change(enterprise, "assets", double.NaN)).IsValid);
        Check("reject-infinity", !CapacityEngine.Validate(Change(enterprise, "assets", double.PositiveInfinity)).IsValid);
        Check("reject-out-of-range", !CapacityEngine.Validate(Change(enterprise, "assets", 100_000_001)).IsValid);
        Check("reject-fractional-integer", !CapacityEngine.Validate(Change(enterprise, "namedUsers", 4.5)).IsValid);
        Check("reject-zero-utilization", !CapacityEngine.Validate(Change(enterprise, "sqlUtilization", 0)).IsValid);
        Check("reject-zero-raw-retention", !CapacityEngine.Validate(Change(enterprise, "rawDays", 0)).IsValid);
        Check("reject-overlapping-harvest-model", !CapacityEngine.Validate(Change(enterprise, "harvestHours", 25)).IsValid);
        Check("reject-null-scenario", !CapacityEngine.Validate(null).IsValid);
        Check("reject-null-parameters", !CapacityEngine.Validate(enterprise with { Parameters = null! }).IsValid);
        Check("reject-null-name", !CapacityEngine.Validate(enterprise with { Name = null! }).IsValid);
        Check("reject-null-enum", !CapacityEngine.Validate(enterprise with { Availability = null! }).IsValid);
        Check("reject-invalid-schema", !CapacityEngine.Validate(enterprise with { SchemaVersion = "other" }).IsValid);
        Check("reject-invalid-platform", !CapacityEngine.Validate(enterprise with { Platform = "production" }).IsValid);
        Check("reject-invalid-history", !CapacityEngine.Validate(enterprise with { HistoryMode = "discard" }).IsValid);
        var refused = false;
        try { CapacityEngine.Calculate(Change(enterprise, "assets", -1)); }
        catch (ScenarioValidationException e) { refused = e.FieldErrors.ContainsKey("parameters.assets"); }
        Check("calculate-refuses-invalid-input", refused);
        return passed;
    }
}
