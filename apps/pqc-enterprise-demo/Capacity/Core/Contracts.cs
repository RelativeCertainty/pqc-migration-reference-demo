using System.Collections.Generic;

namespace PqcCapacityConfigurator.Core;

public sealed record Scenario
{
    public string SchemaVersion { get; init; } = "pqc.capacity.scenario.v1";
    public string Name { get; init; } = "Enterprise qualification candidate";
    public string? ProfileId { get; init; }
    public string Availability { get; init; } = "ha";
    public string HistoryMode { get; init; } = "changed";
    public string Platform { get; init; } = "unselected";
    public Dictionary<string, double> Parameters { get; init; } = new(StringComparer.Ordinal);
}

public sealed record ParameterDefinition(string Key, string Label, string Group, string Unit,
    double DefaultValue, double Min, double Max, bool Integer, string Description, string Basis);
public sealed record ValidationResult(bool IsValid, IReadOnlyDictionary<string, string[]> FieldErrors);
public sealed class ScenarioValidationException(ValidationResult validation)
    : ArgumentException("The scenario contains invalid fields.")
{
    public IReadOnlyDictionary<string, string[]> FieldErrors { get; } = validation.FieldErrors;
}
public sealed record CapacityNotice(string Code, string Message, string Severity = "warning");
public sealed record CapacityEquation(string Id, string Label, string Formula, string Substitution,
    double Value, string Unit, string Basis = "assumed");
public sealed record CapacityAllocation(string Tier, int Instances, double CpuPerInstance,
    double MemoryGiBPerInstance, double TotalCpu, double TotalMemoryGiB,
    double LocalDiskGiBPerInstance, double RequiredCores, double SurvivingCores);
public sealed record CapacityCost(bool IsAvailable, double? TotalMonthly, string Currency,
    string Basis, IReadOnlyDictionary<string, double> Breakdown);

public sealed record CapacityResult(
    string ModelVersion, string InputHash, Scenario Scenario,
    IReadOnlyDictionary<string, double> Rates,
    IReadOnlyDictionary<string, double> Demands,
    IReadOnlyList<CapacityAllocation> Allocations,
    IReadOnlyDictionary<string, double> Storage,
    IReadOnlyDictionary<string, double> Totals,
    IReadOnlyList<CapacityEquation> Equations,
    IReadOnlyList<CapacityNotice> Warnings,
    IReadOnlyList<CapacityNotice> Blockers,
    IReadOnlyList<string> Assumptions,
    CapacityCost Cost,
    bool Deployable = false, bool PerformanceVerified = false);
