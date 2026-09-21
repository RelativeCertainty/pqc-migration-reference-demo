using System.IO.Compression;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.Json.Serialization;
using Microsoft.AspNetCore.Http.Features;
using PqcCapacityConfigurator.Core;
using PqcCapacityConfigurator.Exports;

namespace PqcEnterpriseDemo;

/// <summary>Pure, non-persisting capacity calculations; never provisions resources.</summary>
public static class CapacityEndpoints
{
    public static readonly JsonSerializerOptions Options = new(JsonSerializerDefaults.Web)
    { WriteIndented = true, NumberHandling = JsonNumberHandling.Strict, UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow, MaxDepth = 16 };
    public static byte[] Package(CapacityResult result) => ReviewPackage.Build(
        JsonSerializer.SerializeToNode(result.Scenario, Options)!.AsObject(),
        JsonSerializer.SerializeToNode(result, Options)!.AsObject());

    public static void MapCapacityEndpoints(this WebApplication app)
    {
        app.MapGet("/api/capacity/catalog", () => Results.Json(new { modelVersion = "pqc.capacity.model.v1", definitions = Catalog.Definitions, presets = Catalog.Presets() }, Options));
        app.MapPost("/api/capacity/{operation}", async (string operation, HttpContext context) =>
        {
            if (operation is not ("calculate" or "compare" or "sensitivity" or "package")) return Results.NotFound();
            if (!context.Request.HasJsonContentType()) return Results.Json(new { error = "application_json_required" }, statusCode: 415);
            if (context.Request.ContentLength > 65536) return Results.StatusCode(413);
            var feature = context.Features.Get<IHttpMaxRequestBodySizeFeature>();
            if (feature is { IsReadOnly: false }) feature.MaxRequestBodySize = 65536;
            try
            {
                if (operation == "compare")
                {
                    var input = await context.Request.ReadFromJsonAsync<Comparison>(Options, context.RequestAborted);
                    if (input?.Scenarios is null || input.Scenarios.Length is < 1 or > 6 || input.Scenarios.Any(s => s is null))
                        return Results.Json(new { error = "one_to_six_scenarios_required" }, statusCode: 400);
                    return Results.Json(new { results = input.Scenarios.Select(CapacityEngine.Calculate).ToArray() }, Options);
                }
                var scenario = await context.Request.ReadFromJsonAsync<Scenario>(Options, context.RequestAborted) ?? throw new JsonException();
                var result = CapacityEngine.Calculate(scenario);
                if (operation == "package") return Results.File(Package(result), "application/zip", "pqc-capacity-review-package.zip");
                if (operation == "sensitivity")
                {
                    var cases = new List<object>();
                    foreach (var multiplier in new[] { .5, 1.0, 2.0 })
                    {
                        var parameters = new Dictionary<string, double>(result.Scenario.Parameters);
                        foreach (var key in new[] { "apiCpuMs", "workerCpuMs", "sqlApiCpuMs", "sqlObservationCpuMs" }) parameters[key] *= multiplier;
                        var changed = result.Scenario with { Parameters = parameters, Name = result.Scenario.Name[..Math.Min(96, result.Scenario.Name.Length)] + $" - {multiplier:0.0}x CPU cost" };
                        var valid = CapacityEngine.Validate(changed);
                        cases.Add(valid.IsValid ? (object)new { label = $"{multiplier:0.0}x CPU cost", result = CapacityEngine.Calculate(changed) }
                            : new { label = $"{multiplier:0.0}x CPU cost", error = "outside_parameter_bounds", fieldErrors = valid.FieldErrors });
                    }
                    return Results.Json(new { cases, meaning = "Input sensitivity; not a confidence interval or benchmark." }, Options);
                }
                return Results.Json(result, Options);
            }
            catch (ScenarioValidationException error) { return Results.Json(new { error = "invalid_scenario", fieldErrors = error.FieldErrors }, statusCode: 400); }
            catch (JsonException) { return Results.Json(new { error = "invalid_json_or_schema" }, statusCode: 400); }
            catch (ArgumentException) { return Results.Json(new { error = "review_package_contains_unsupported_content" }, statusCode: 400); }
        });
    }

    public static async Task<int> Command(string[] args)
    {
        try
        {
            if (args.SequenceEqual(new[] { "--capacity-self-test" }))
            { Console.WriteLine(JsonSerializer.Serialize(new { checks = CapacityEngine.SelfTest() }, Options)); return 0; }
            if (args.Length != (args[0] == "--capacity-evaluate" ? 2 : 3) || args[0] is not ("--capacity-evaluate" or "--capacity-package")) return 2;
            var info = new FileInfo(args[1]);
            if (!info.Exists || info.Length > 65536 || info.LinkTarget is not null) return 2;
            var scenario = JsonSerializer.Deserialize<Scenario>(await File.ReadAllTextAsync(info.FullName), Options) ?? throw new JsonException();
            var result = CapacityEngine.Calculate(scenario);
            if (args[0] == "--capacity-evaluate") Console.WriteLine(JsonSerializer.Serialize(result, Options));
            else
            {
                var bytes = Package(result);
                var options = new FileStreamOptions { Mode = FileMode.CreateNew, Access = FileAccess.Write, Share = FileShare.None };
                if (!OperatingSystem.IsWindows()) options.UnixCreateMode = UnixFileMode.UserRead | UnixFileMode.UserWrite;
                await using var stream = new FileStream(args[2], options);
                await stream.WriteAsync(bytes);
            }
            return 0;
        }
        catch (Exception error) when (error is ArgumentException or JsonException or IOException)
        { Console.Error.WriteLine("Capacity command refused; no infrastructure action occurred."); return 2; }
    }
    private sealed record Comparison(Scenario[] Scenarios);
}
