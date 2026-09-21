using System.Globalization;
using System.IO.Compression;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace PqcCapacityConfigurator.Exports;

/// <summary>Deterministic capacity-review documents; never a provisioning authority.</summary>
public static class ReviewPackage
{
    private static readonly DateTimeOffset ArchiveTimestamp = new(2000, 1, 1, 0, 0, 0, TimeSpan.Zero);
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };
    private static readonly HashSet<string> SecretNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "password", "passwords", "token", "accesstoken", "refreshtoken", "apikey", "clientsecret",
        "privatekey", "privatekeypem", "connectionstring", "dsn", "credentials", "credential", "secretvalue"
    };

    public static byte[] Build(JsonObject scenario, JsonObject result)
    {
        ArgumentNullException.ThrowIfNull(scenario);
        ArgumentNullException.ThrowIfNull(result);
        if (Encoding.UTF8.GetByteCount(scenario.ToJsonString()) > 65536 ||
            Encoding.UTF8.GetByteCount(result.ToJsonString()) > 2 * 1024 * 1024)
            throw new ArgumentException("review_package_input_too_large");

        var redactions = 0;
        var safeScenario = (JsonObject)Sanitize(scenario, ref redactions)!;
        var safeResult = (JsonObject)Sanitize(result, ref redactions)!;
        // Never silently change the scenario represented by the calculation input hash.
        if (redactions != 0) throw new ArgumentException("review_package_input_contains_excluded_fields");
        // A review export cannot inherit an accidental readiness or deployment claim.
        safeResult["deployable"] = false;
        safeResult["performanceVerified"] = false;
        var allocations = safeResult["allocations"] as JsonArray ?? new JsonArray();
        var platform = Read(safeScenario["platform"]);
        var scenarioName = Read(safeScenario["id"] ?? safeScenario["name"], "unnamed-review");
        var requested = new JsonArray();
        foreach (var item in allocations.OfType<JsonObject>())
            requested.Add(new JsonObject
            {
                ["tier"] = Read(item["tier"]),
                ["instances"] = NumberOrNull(item["instances"]),
                ["vcpu_per_instance"] = NumberOrNull(item["cpuPerInstance"]),
                ["memory_gib_per_instance"] = NumberOrNull(item["memoryGiBPerInstance"]),
                ["local_disk_gib_per_instance"] = NumberOrNull(item["localDiskGiBPerInstance"])
            });

        var gates = new JsonArray();
        foreach (var (id, detail) in new[]
        {
            ("platform", "Approved hosting product/version, placement, quotas, routes and operating team."),
            ("sql_server", "SQL Server edition/version, licensing, HA, storage/IOPS and deployment authority."),
            ("enterprise_identity", "Enterprise SSO, service identities and assessment authorization."),
            ("backup_restore", "Approved backup/retention and measured restore/failover evidence."),
            ("secrets", "Approved secrets/key-custody bindings; no values in this package."),
            ("retention", "Approved evidence, observations, reports and telemetry lifecycle rules."),
            ("owner_validation", "Named owner review and targeted product observations, recorded separately."),
            ("performance", "Representative throughput, query latency, failure and capacity tests.")
        })
            gates.Add(new JsonObject { ["id"] = id, ["status"] = "unverified_in_review_export", ["requiredEvidence"] = detail });

        var contract = new JsonObject
        {
            ["schemaVersion"] = "pqc.capacity.deployment-contract.v1",
            ["mode"] = "review_only", ["enabled"] = false, ["deployable"] = false,
            ["performanceVerified"] = false, ["scenarioId"] = scenarioName,
            ["platformCandidate"] = platform, ["requestedAllocations"] = requested.DeepClone(),
            ["modelVersion"] = safeResult["modelVersion"]?.DeepClone(),
            ["inputHash"] = safeResult["inputHash"]?.DeepClone(),
            ["gates"] = gates, ["calculationBlockers"] = safeResult["blockers"]?.DeepClone() ?? new JsonArray(),
            ["phase3ExecutionEnabled"] = false, ["phase4ExecutionEnabled"] = false,
            ["authorityNotice"] = "Requested capacity is not approved infrastructure. This package creates no resources or authorization."
        };
        var tfvars = new JsonObject
        {
            ["scenario_id"] = scenarioName, ["platform_candidate"] = platform,
            ["deployable"] = false, ["requested_allocations"] = requested
        };
        var provenance = new JsonObject
        {
            ["schemaVersion"] = "pqc.capacity.source-provenance.v1",
            ["sourceId"] = "PQC-PHYSICAL-CAPACITY-DRAFT-2026-09-11",
            ["sourceDate"] = "2026-09-11", ["status"] = "inherited_draft_assumptions_not_approved_sizing",
            ["modelVersion"] = safeResult["modelVersion"]?.DeepClone(),
            ["inputHash"] = safeResult["inputHash"]?.DeepClone(),
            ["redactedFieldCount"] = redactions,
            ["hashNotice"] = "inputHash identifies the calculation inputs. Recognized secret fields and local paths cause export rejection; inputs are never silently redacted into a different scenario.",
            ["modelSources"] = safeResult["sources"]?.DeepClone() ?? new JsonArray(),
            ["officialReferencesCheckedOn"] = "2026-09-14",
            ["officialReferences"] = new JsonArray
            {
                new JsonObject { ["title"] = "Terraform modules", ["url"] = "https://developer.hashicorp.com/terraform/language/modules", ["status"] = "official_product_documentation" },
                new JsonObject { ["title"] = "Terraform plan command", ["url"] = "https://developer.hashicorp.com/terraform/cli/commands/plan", ["status"] = "official_product_documentation" },
                new JsonObject { ["title"] = "Cloud Foundry application manifest attributes", ["url"] = "https://docs.cloudfoundry.org/devguide/deploy-apps/manifest-attributes.html", ["status"] = "official_product_documentation" },
                new JsonObject { ["title"] = "SQL Server memory configuration options", ["url"] = "https://learn.microsoft.com/en-us/sql/database-engine/configure-windows/server-memory-server-configuration-options?view=sql-server-ver17", ["status"] = "official_product_documentation" }
            },
            ["qualification"] = "Official documentation explains product behavior, not enterprise selection, benchmark performance or approval."
        };

        var files = new SortedDictionary<string, byte[]>(StringComparer.Ordinal);
        void Add(string path, string content) => files.Add(path, Encoding.UTF8.GetBytes(content.Replace("\r\n", "\n")));
        void AddJson(string path, JsonNode value) => Add(path, value.ToJsonString(JsonOptions) + "\n");
        AddJson("scenario.json", safeScenario);
        AddJson("result.json", safeResult);
        AddJson("deployment-contract.json", contract);
        AddJson("source-provenance.json", provenance);
        AddJson("capacity-profile.tfvars.json", tfvars);
        Add("assumptions.csv", CsvRows("assumptions", safeResult["assumptions"] ?? safeScenario));
        Add("model-inputs.csv", ModelInputs(safeScenario));
        Add("estimates.csv", Estimates(safeResult));
        Add("capacity-one-line.svg", CapacityDiagram(allocations));
        Add("decisions.readable.html", DecisionHtml(scenarioName, platform, safeResult, contract));
        Add("README_IMPORT.md", Readme);
        Add("README_IMPORT.readable.html", HtmlDocument("Capacity review package — instructions", "<pre>" + H(Readme) + "</pre>"));
        Add("terraform-review/versions.tf", "terraform {\n  required_version = \">= 1.5.0, < 2.0.0\"\n}\n");
        Add("terraform-review/variables.tf", VariablesTf);
        Add("terraform-review/main.tf", MainTf);
        // The same exact variable keys are accepted by this output-only module.
        AddJson("terraform-review/capacity-profile.tfvars.json", tfvars);
        if (IsCloudFoundry(platform)) Add("cloud-foundry-manifest.review.yaml", CloudFoundryPreview(allocations));

        var entries = new JsonArray();
        foreach (var (path, bytes) in files)
            entries.Add(new JsonObject
            {
                ["path"] = path, ["bytes"] = bytes.Length,
                ["sha256"] = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant()
            });
        AddJson("manifest.json", new JsonObject
        {
            ["schemaVersion"] = "pqc.capacity.review-package.v1", ["mode"] = "review_only",
            ["deployable"] = false, ["entryTimestamp"] = "2000-01-01T00:00:00Z",
            ["digestScope"] = "All package members except manifest.json; no self-referential digest.", ["entries"] = entries
        });
        using var stream = new MemoryStream();
        using (var archive = new ZipArchive(stream, ZipArchiveMode.Create, true))
            foreach (var (path, bytes) in files)
            {
                var entry = archive.CreateEntry(path, CompressionLevel.Optimal);
                entry.LastWriteTime = ArchiveTimestamp;
                entry.ExternalAttributes = 0;
                using var body = entry.Open();
                body.Write(bytes);
            }
        return stream.ToArray();
    }

    private static bool IsCloudFoundry(string platform) =>
        platform.Replace("-", "").Replace("_", "").Replace(" ", "").ToLowerInvariant() is "pcf" or "cloudfoundry" or "pivotalcloudfoundry";

    private static JsonNode? NumberOrNull(JsonNode? node) =>
        node is JsonValue && node.GetValueKind() == JsonValueKind.Number &&
        double.TryParse(node.ToJsonString(), NumberStyles.Float, CultureInfo.InvariantCulture, out var n) &&
        double.IsFinite(n) ? node.DeepClone() : null;

    private static JsonNode? Sanitize(JsonNode? node, ref int redactions, int depth = 0)
    {
        if (depth > 24) throw new ArgumentException("review_package_input_too_deep");
        if (node is JsonObject obj)
        {
            var clean = new JsonObject();
            foreach (var (key, value) in obj.OrderBy(kv => kv.Key, StringComparer.Ordinal))
            {
                if (SecretNames.Contains(key.Replace("_", "").Replace("-", "")))
                { clean[key] = "[excluded: secret-bearing field]"; redactions++; }
                else clean[key] = Sanitize(value, ref redactions, depth + 1);
            }
            return clean;
        }
        if (node is JsonArray array)
        {
            var clean = new JsonArray();
            foreach (var item in array) clean.Add(Sanitize(item, ref redactions, depth + 1));
            return clean;
        }
        if (node is JsonValue scalar && scalar.TryGetValue<string>(out var text))
        {
            if (text.StartsWith('/') || text.Contains("/home/", StringComparison.Ordinal) || text.Contains("/Users/", StringComparison.Ordinal) ||
                text.StartsWith("file:", StringComparison.OrdinalIgnoreCase) ||
                (text.Length > 2 && char.IsLetter(text[0]) && text[1] == ':' && text[2] is '\\' or '/'))
            { redactions++; return JsonValue.Create("[excluded: local path]"); }
            return JsonValue.Create(text);
        }
        return node?.DeepClone();
    }

    private static string Read(JsonNode? value, string missing = "unknown") => value is null ? missing :
        value is JsonValue scalar && scalar.TryGetValue<string>(out var text) ? text : value.ToJsonString();

    private static string Cell(string? value)
    {
        var text = value ?? "unknown";
        var first = text.AsSpan().TrimStart();
        if ((first.Length > 0 && "=+-@".Contains(first[0])) || (text.Length > 0 && text[0] is '\t' or '\r' or '\n')) text = "'" + text;
        return "\"" + text.Replace("\"", "\"\"") + "\"";
    }

    private static string CsvRows(string section, JsonNode? node)
    {
        var rows = new StringBuilder("section,field,value\n");
        foreach (var (field, value) in Flatten(node)) rows.Append(Cell(section)).Append(',').Append(Cell(field)).Append(',').Append(Cell(value)).Append('\n');
        return rows.ToString();
    }

    private static string Estimates(JsonObject result)
    {
        var rows = new StringBuilder("section,field,value\n");
        foreach (var section in new[] { "allocations", "rates", "demands", "storage", "totals", "equations", "cost" })
            foreach (var (field, value) in Flatten(result[section]))
                rows.Append(Cell(section)).Append(',').Append(Cell(field)).Append(',').Append(Cell(value)).Append('\n');
        return rows.ToString();
    }

    private static string ModelInputs(JsonObject scenario)
    {
        var rows = new StringBuilder("parameter,value,status,basis\n");
        if (scenario["parameters"] is JsonObject parameters)
            foreach (var (key, value) in parameters.OrderBy(kv => kv.Key, StringComparer.Ordinal))
                rows.Append(Cell(key)).Append(',').Append(Cell(Read(value))).Append(',')
                    .Append(Cell(value is null ? "unknown" : "resolved_model_input")).Append(',')
                    .Append(Cell("Scenario and model defaults; not independently measured by this tool.")).Append('\n');
        return rows.ToString();
    }

    private static IEnumerable<(string Field, string Value)> Flatten(JsonNode? value, string path = "value")
    {
        if (value is JsonObject obj && obj.Count > 0)
        {
            foreach (var (key, child) in obj.OrderBy(kv => kv.Key, StringComparer.Ordinal))
                foreach (var row in Flatten(child, path == "value" ? key : path + "." + key)) yield return row;
        }
        else if (value is JsonArray array && array.Count > 0)
        {
            for (var i = 0; i < array.Count; i++) foreach (var row in Flatten(array[i], path + "[" + i + "]")) yield return row;
        }
        else yield return (path, Read(value));
    }

    private static string H(string text) => WebUtility.HtmlEncode(text);

    private static string DecisionHtml(string name, string platform, JsonObject result, JsonObject contract)
    {
        var body = new StringBuilder("<p class='status'>REVIEW ONLY · UNVALIDATED CAPACITY ESTIMATE · NO DEPLOYMENT AUTHORITY</p>");
        body.Append("<h1>Capacity and deployment review</h1><p>Scenario: <strong>").Append(H(name))
            .Append("</strong> · Platform candidate: ").Append(H(platform)).Append("</p>");
        body.Append("<h2>What this result means</h2><p>The calculated resources are a proposal for an explicit workload and assumptions. They are not benchmark results, a purchase approval, a confirmed enterprise platform selection or a deployment. Unknown values remain unknown. Phase 3/4 migration execution remains disabled.</p>");
        body.Append("<h2>Requested topology at a glance</h2><img src='capacity-one-line.svg' alt='Browser to API to authoritative SQL with transactional outbox, then worker and evidence store; witness shown only when allocated.' style='display:block;width:100%;height:auto;background:white;border:1px solid #bed0db'><p>The SQL outbox supplies durable worker commands. The API does not own a separate outbox. This diagram displays calculated allocations; it does not establish high availability, platform approval or deployed infrastructure.</p>");
        body.Append("<h2>Requested capacity</h2><table><thead><tr><th>Tier</th><th>Instances</th><th>vCPU / instance</th><th>GiB RAM / instance</th><th>Local disk GiB / instance</th></tr></thead><tbody>");
        foreach (var item in (result["allocations"] as JsonArray ?? new JsonArray()).OfType<JsonObject>())
        {
            body.Append("<tr>");
            foreach (var key in new[] { "tier", "instances", "cpuPerInstance", "memoryGiBPerInstance", "localDiskGiBPerInstance" })
                body.Append("<td>").Append(H(Read(item[key]))).Append("</td>");
            body.Append("</tr>");
        }
        body.Append("</tbody></table><h2>Calculation blockers and warnings</h2>");
        foreach (var key in new[] { "blockers", "warnings" })
        {
            body.Append("<h3>").Append(H(key)).Append("</h3><ul>");
            if (result[key] is JsonArray list && list.Count > 0)
                foreach (var item in list) body.Append("<li>").Append(H(Read(item is JsonObject record ? record["message"] ?? record : item))).Append("</li>");
            else body.Append("<li>No entries recorded. This does not establish deployment readiness.</li>");
            body.Append("</ul>");
        }
        body.Append("<h2>Decisions required before activation</h2><ul>");
        foreach (var gate in (JsonArray)contract["gates"]!)
            body.Append("<li><strong>").Append(H(Read(gate?["id"]))).Append(":</strong> ").Append(H(Read(gate?["requiredEvidence"]))).Append(" Status: unverified in this export.</li>");
        body.Append("</ul><h2>Next useful step</h2><p>Review the workload and service-rate assumptions, confirm the supported platform and data services, and run a separately authorized bounded performance and recovery exercise. Then revise the scenario. No field in this package records human approval.</p><p>See model-inputs.csv for every resolved numeric parameter, assumptions.csv and estimates.csv for inspectable assumptions/calculations, deployment-contract.json for disabled capability boundaries, and source-provenance.json for source status.</p>");
        return HtmlDocument("Capacity review — " + name, body.ToString());
    }

    private static string CapacityDiagram(JsonArray allocations)
    {
        JsonObject? Tier(string name) => allocations.OfType<JsonObject>().FirstOrDefault(a => Read(a["tier"]) == name);
        string Value(JsonObject? row, string key) => NumberOrNull(row?[key]) is { } number &&
            double.TryParse(number.ToJsonString(), NumberStyles.Float, CultureInfo.InvariantCulture, out var n)
                ? n.ToString("G6", CultureInfo.InvariantCulture) : Read(row?[key]);
        var svg = new StringBuilder("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1560 740' role='img' aria-labelledby='title desc'><title id='title'>PQC requested capacity — one-line review</title><desc id='desc'>Browser connects to API, then SQL Server. The transactional command outbox is inside SQL Server and supplies workers. Workers store evidence artifacts. A witness appears only if the result allocates one. All values are estimates, not deployed resources.</desc><defs><marker id='arrow' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='7' markerHeight='7' orient='auto-start-reverse'><path d='M0 0 L10 5 L0 10 Z' fill='#28586d'/></marker></defs><style>text{font-family:Arial,sans-serif;fill:#18313f}.title{font-size:29px;font-weight:700}.sub{font-size:18px;fill:#405d6d}.head{font-size:20px;font-weight:700}.body{font-size:17px}.small{font-size:15px;fill:#405d6d}.card{fill:#f4f8fa;stroke:#28586d;stroke-width:2}.flow{fill:none;stroke:#28586d;stroke-width:3;marker-end:url(#arrow)}</style><rect width='1560' height='740' fill='white'/>");
        void Text(int x, int y, string text, string css = "body") => svg.Append("<text x='").Append(x).Append("' y='").Append(y).Append("' class='").Append(css).Append("'>").Append(H(text)).Append("</text>");
        void Card(int x, int y, int width, int height, string title)
        {
            svg.Append("<rect class='card' x='").Append(x).Append("' y='").Append(y).Append("' width='").Append(width).Append("' height='").Append(height).Append("' rx='12'/>");
            Text(x + 18, y + 34, title, "head");
        }
        void Line(int x1, int y1, int x2, int y2, bool dashed = false) => svg.Append("<path class='flow' d='M ").Append(x1).Append(' ').Append(y1).Append(" L ").Append(x2).Append(' ').Append(y2).Append("'").Append(dashed ? " stroke-dasharray='7 5'" : "").Append("/>");
        void Allocation(int x, int y, JsonObject? row, string countLabel)
        {
            Text(x, y, Value(row, "instances") + " " + countLabel);
            Text(x, y + 31, Value(row, "cpuPerInstance") + " vCPU / instance");
            Text(x, y + 62, Value(row, "memoryGiBPerInstance") + " GiB RAM / instance");
            Text(x, y + 93, Value(row, "localDiskGiBPerInstance") + " GiB disk / instance", "small");
        }
        Text(30, 44, "Requested capacity and command flow", "title");
        Text(30, 78, "REVIEW ONLY · Unmeasured assumptions · No provisioning, approval or migration execution", "sub");
        Card(30, 180, 160, 135, "Browser / UI");
        Text(48, 250, "HTTPS route", "small"); Text(48, 276, "to be approved", "small");
        Card(245, 150, 240, 220, "C# API"); Allocation(263, 221, Tier("api"), "instances");
        Card(540, 125, 335, 270, "SQL Server authority"); Allocation(558, 196, Tier("sql"), "database copies");
        Text(558, 325, "One write authority", "small"); Text(558, 356, "Transactional command outbox", "head");
        Card(930, 150, 250, 220, "C# workers"); Allocation(948, 221, Tier("worker"), "instances");
        Card(1235, 165, 285, 200, "Evidence artifact service");
        Text(1253, 239, "Encrypted retained artifacts", "small");
        Text(1253, 270, "See separate storage estimate", "small");
        Text(1253, 301, "Service binding unresolved", "small");
        Line(190, 247, 243, 247); Line(485, 247, 538, 247); Line(875, 247, 928, 247); Line(1180, 247, 1233, 247);
        if (Tier("witness") is { } witness)
        {
            Card(560, 476, 340, 148, "Quorum witness (proposed)");
            Text(578, 544, Value(witness, "instances") + " instance · " + Value(witness, "cpuPerInstance") + " vCPU · " + Value(witness, "memoryGiBPerInstance") + " GiB RAM");
            Text(578, 575, Value(witness, "localDiskGiBPerInstance") + " GiB local disk", "small");
            Text(578, 601, "Not a data copy or backup", "small");
            Line(710, 395, 710, 474, true);
        }
        else Text(560, 502, "No witness allocation supplied by this result.", "small");
        Text(30, 668, "Enterprise identity, secrets, backup/DR, monitoring and platform routes require separate qualification.", "sub");
        Text(30, 701, "Labels use up to six significant digits from the C# result; exact values remain in result.json. No capacity certification is implied.", "small");
        return svg.Append("</svg>\n").ToString();
    }

    private static string HtmlDocument(string title, string content) => "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>" + H(title) + "</title><style>body{font:16px/1.55 system-ui,sans-serif;color:#18313f;background:#f5f8fa;max-width:1080px;margin:32px auto;padding:24px}h1,h2,h3{color:#122b39}h2{margin-top:32px}.status{font-weight:700;color:#763b00;background:#fff0cf;padding:12px}table{border-collapse:collapse;width:100%;background:white}th,td{padding:10px;text-align:left;border:1px solid #bed0db;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere}li{margin-bottom:10px}@media print{body{margin:0;padding:12mm;background:white}table{font-size:11px}tr{break-inside:avoid}h2,h3{break-after:avoid}}</style></head><body>" + content + "</body></html>";

    private static string CloudFoundryPreview(JsonArray allocations)
    {
        var text = new StringBuilder("# REVIEW ONLY. This is not a deployable manifest. No platform approval is implied.\n# Placeholders must not be treated as approved images, routes or service bindings.\n# The platform owner must separately qualify app/worker process types and disk quotas.\n# SQL, witness, evidence and unknown tiers are NOT placed as Cloud Foundry apps.\n# Review all requested allocations separately in deployment-contract.json.\nreview_only: true\ndeployable: false\nphase3_execution_enabled: false\nphase4_execution_enabled: false\napplications:\n");
        var index = 0;
        foreach (var item in allocations.OfType<JsonObject>())
        {
            // Exact C# model tiers only; do not infer platform placement from a label.
            if (Read(item["tier"]) is not ("api" or "worker")) continue;
            index++;
            text.Append("  - name: APPROVED-APP-NAME-").Append(index).Append("\n    # Candidate tier: ").Append(Read(item["tier"]).Replace("\n", " ").Replace("\r", " "))
                .Append("\n    # Requested vCPU per instance: ").Append(Read(NumberOrNull(item["cpuPerInstance"])))
                .Append("\n    # Requested RAM GiB per instance: ").Append(Read(NumberOrNull(item["memoryGiBPerInstance"])))
                .Append("\n    # Requested local disk GiB per instance: ").Append(Read(NumberOrNull(item["localDiskGiBPerInstance"])))
                .Append("\n    instances: ").Append(Read(NumberOrNull(item["instances"]), "null # unknown"))
                .Append("\n    memory: APPROVED-MEMORY-QUOTA\n    disk_quota: APPROVED-DISK-QUOTA\n    no-route: true\n    docker:\n      image: APPROVED-REGISTRY/APP@sha256:APPROVED-DIGEST\n    services:\n      - APPROVED-SERVICE-BINDING\n    # An approved authenticated route, if needed, is configured separately.\n");
        }
        if (index == 0) text.Append("  [] # No recognized stateless allocation supplied; platform mapping remains unresolved.\n");
        return text.ToString();
    }

    private const string VariablesTf = """
        variable "scenario_id" {
          type = string
        }
        variable "platform_candidate" {
          type = string
        }
        variable "deployable" {
          type    = bool
          default = false
          validation {
            condition     = var.deployable == false
            error_message = "This module is review-only and cannot authorize deployment."
          }
        }
        variable "requested_allocations" {
          type = list(object({
            tier                        = string
            instances                   = number
            vcpu_per_instance           = number
            memory_gib_per_instance     = number
            local_disk_gib_per_instance = number
          }))
          description = "Unvalidated requested capacity; null means unknown, never zero by inference."
        }
        """;

    private const string MainTf = """
        # Output-only review module: no resources, providers, data sources or provisioners.
        output "capacity_review" {
          value = {
            mode                  = "review_only"
            deployable            = false
            scenario_id           = var.scenario_id
            platform_candidate    = var.platform_candidate
            requested_allocations = var.requested_allocations
          }
          precondition {
            condition     = var.deployable == false
            error_message = "Deployment is disabled in this review package."
          }
        }
        """;

    private const string Readme = """
        # PQC capacity review package

        Status: REVIEW ONLY. No infrastructure has been created, changed or approved.

        Open decisions.readable.html first; it includes capacity-one-line.svg. Review scenario.json,
        model-inputs.csv (every resolved parameter), assumptions.csv and estimates.csv;
        distinguish workload assumptions from calculated estimates and measured observations.
        result.json always records deployable=false and performanceVerified=false.
        deployment-contract.json lists unresolved activation decisions and keeps Phase 3/4 disabled.
        A diagnostic package may contain calculation blockers; exporting it does not clear them.

        Terraform review inputs
        capacity-profile.tfvars.json contains only the four variables declared in
        terraform-review/variables.tf. An identical copy is included beside that output-only module.
        main.tf declares outputs only: no resources, provider configuration, data sources,
        credentials, provisioners or external commands. It cannot provision the enterprise app.
        With Terraform already installed, `terraform -chdir=terraform-review fmt -check` is an
        optional offline syntax-format check. No initialization, downloads or apply are needed
        to read this package. Do not mistake review metadata for an approved provisioning root.

        When present, cloud-foundry-manifest.review.yaml is a NONDEPLOYABLE placeholder preview.
        Hosting product/version, process types, routes, image digests and service bindings must be
        separately approved and qualified. No deployment command is supplied.

        Before activation, resolve platform, SQL Server, enterprise identity, secrets, retention,
        operating ownership, backup/restore and representative performance qualification.
        Confirm cost and tenancy boundaries. No scenario selection or export grants authority.

        Integrity and privacy
        manifest.json records size and SHA-256 of every other member. It excludes itself to avoid
        a self-referential digest. Entries use fixed names, sorted order and a fixed timestamp for
        repeatable bytes. Recognized secret fields and local paths cause export rejection; do not enter
        secrets, connection strings, source records or personal data into capacity scenarios.
        CSV text is quoted and formula-leading text is escaped. Empty measurements remain unknown.
        source-provenance.json identifies inherited draft assumptions, not enterprise approval.
        """;
}
