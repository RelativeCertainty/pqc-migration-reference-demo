using System.Globalization;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Microsoft.Data.Sqlite;

namespace PqcEnterpriseDemo;

/// <summary>
/// Isolated synthetic development adapter. Never accepts a DSN, enterprise data,
/// a tenant parameter, source credentials, or a source-system effect operation.
/// SQLite is a demo adapter, not a production database selection.
/// </summary>
public sealed partial class EnterpriseStore : IEnterpriseStore
{
    private const int ApplicationId = 0x50514345;
    private const string Marker = "pqc-enterprise-demo-synthetic-only-v1\n";
    private static readonly string[] Kinds = ["inventory", "dependencies", "sourceProfiles", "estateAreas", "observations", "riskReviews", "contextReviews", "limitations", "migrationCandidates"];
    private readonly object gate = new();
    private readonly SqliteConnection connection;
    private readonly FileStream lease;
    private readonly string root;
    private readonly string baselineId;
    private readonly string inputSha256;
    private readonly string asOf;
    private bool disposed;

    public EnterpriseStore(string root, string fixturePath)
    {
        // Explicit bounded synthetic capacity, never an unbounded/production setting.
        var databaseLimitMiB = Environment.GetEnvironmentVariable("PQC_DEMO_DATABASE_MAX_MIB") switch
        {
            null or "128" => 128,
            "256" => 256,
            "512" => 512,
            _ => throw new DemoStoreException("demo_database_limit_invalid")
        };
        this.root = PrepareDirectory(root);
        try { lease = new FileStream(Path.Combine(this.root, "instance.lock"), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None); }
        catch (IOException) { throw new DemoConflictException("demo_store_already_in_use"); }
        OwnerOnly(Path.Combine(this.root, "instance.lock"));
        var dbPath = Path.Combine(this.root, "enterprise-demo.sqlite3");
        var existed = File.Exists(dbPath);
        RefuseLink(dbPath);
        connection = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = dbPath, Mode = existed ? SqliteOpenMode.ReadWrite : SqliteOpenMode.ReadWriteCreate, Pooling = false }.ToString());
        try
        {
            connection.Open();
            OwnerOnly(dbPath);
            var pageSize = Convert.ToInt64(Scalar("PRAGMA page_size"), CultureInfo.InvariantCulture);
            var maximumPages = databaseLimitMiB * 1024L * 1024L / pageSize;
            var currentPages = Convert.ToInt64(Scalar("PRAGMA page_count"), CultureInfo.InvariantCulture);
            // SQLite will otherwise silently return the existing page count when a
            // requested maximum is too small. Refuse; never prune immutable history.
            if (currentPages > maximumPages) throw new DemoStoreException("demo_database_limit_exceeded");
            var appId = Convert.ToInt32(Scalar("PRAGMA application_id"), CultureInfo.InvariantCulture);
            if (existed && appId != ApplicationId) throw new DemoValidationException("wrong_database_application_id");
            if (!existed) Execute($"PRAGMA application_id={ApplicationId}");
            var schemaVersion = Convert.ToInt32(Scalar("PRAGMA user_version"), CultureInfo.InvariantCulture);
            if (existed && schemaVersion is not (1 or 2 or 3 or 4)) throw new DemoValidationException("unsupported_database_schema");
            if (existed) ValidateLegacyAssessmentStore(schemaVersion >= 3 ? 2 : schemaVersion);
            var appliedMaximum = Convert.ToInt64(Scalar($"PRAGMA max_page_count={maximumPages}"), CultureInfo.InvariantCulture);
            if (appliedMaximum != maximumPages) throw new DemoStoreException("demo_database_limit_unavailable");
            Execute("PRAGMA foreign_keys=ON; PRAGMA busy_timeout=5000; PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;");
            if (schemaVersion < 3) InitializeSchema();
            if (!string.Equals(Scalar("PRAGMA quick_check")?.ToString(), "ok", StringComparison.Ordinal)) throw new DemoValidationException("database_integrity_failed");
            RefuseLink(fixturePath);
            var info = new FileInfo(fixturePath);
            if (!info.Exists || info.Length is < 2 or > 16_777_216) throw new DemoValidationException("fixture_size_out_of_bounds");
            var bytes = File.ReadAllBytes(fixturePath);
            inputSha256 = Convert.ToHexStringLower(SHA256.HashData(bytes));
            baselineId = "baseline-" + inputSha256;
            var fixture = ParseObject(Encoding.UTF8.GetString(bytes));
            ValidateFixture(fixture);
            asOf = Text(fixture, "asOf");
            Import(fixture);
            InitializeAssessmentSchema();
            InitializeWorkspaceSchema();
            foreach (var file in Directory.EnumerateFiles(this.root)) OwnerOnly(file);
        }
        catch
        {
            connection.Dispose();
            lease.Dispose();
            throw;
        }
    }

    private void InitializeSchema()
    {
        using var transaction = connection.BeginTransaction();
        Execute("""
            CREATE TABLE IF NOT EXISTS baselines (
              id TEXT PRIMARY KEY, input_sha256 TEXT NOT NULL UNIQUE, as_of TEXT NOT NULL,
              created_at TEXT NOT NULL, metadata_json TEXT NOT NULL, method_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS records (
              baseline_id TEXT NOT NULL REFERENCES baselines(id), kind TEXT NOT NULL,
              position INTEGER NOT NULL, record_key TEXT NOT NULL, payload_json TEXT NOT NULL,
              PRIMARY KEY(baseline_id,kind,position));
            CREATE INDEX IF NOT EXISTS records_lookup ON records(baseline_id,kind,record_key);
            CREATE TABLE IF NOT EXISTS worker_runs (
              id TEXT PRIMARY KEY, baseline_id TEXT NOT NULL REFERENCES baselines(id),
              phase TEXT NOT NULL CHECK(phase IN ('phase1','phase2')), idempotency_key TEXT NOT NULL,
              actor TEXT NOT NULL, created_at TEXT NOT NULL, status TEXT NOT NULL,
              invocation_json TEXT NOT NULL, result_json TEXT NOT NULL,
              UNIQUE(baseline_id,idempotency_key));
            CREATE TABLE IF NOT EXISTS reports (
              id TEXT PRIMARY KEY, baseline_id TEXT NOT NULL REFERENCES baselines(id),
              worker_run_id TEXT NOT NULL UNIQUE REFERENCES worker_runs(id), phase TEXT NOT NULL,
              created_at TEXT NOT NULL, content_sha256 TEXT NOT NULL, content_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS run_events (
              id INTEGER PRIMARY KEY, worker_run_id TEXT NOT NULL REFERENCES worker_runs(id),
              kind TEXT NOT NULL, metadata_json TEXT NOT NULL);
            """, transaction);
        InitializeActionsSchema(transaction);
        foreach (var table in new[] { "baselines", "records", "reports", "worker_runs", "run_events" })
            foreach (var action in new[] { "UPDATE", "DELETE" })
                Execute($"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{action} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable_record'); END;", transaction);
        Execute("PRAGMA user_version=2;", transaction);
        transaction.Commit();
    }

    private static void ValidateFixture(JsonObject fixture)
    {
        if (Text(fixture, "schemaVersion") != "pqc.enterprise.synthetic-input.v1" || fixture["synthetic"]?.GetValue<bool>() != true || Text(fixture, "tenantId") != "synthetic-enterprise")
            throw new DemoValidationException("synthetic_fixture_required");
        if (!DateTimeOffset.TryParse(Text(fixture, "asOf"), CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal, out _)) throw new DemoValidationException("invalid_fixture_as_of");
        foreach (var kind in Kinds)
            if (fixture[kind] is not JsonArray rows || rows.Count > 50_000 || rows.Any(row => row is not JsonObject)) throw new DemoValidationException("invalid_fixture_records");
        if (fixture["method"] is not JsonObject || Rows(fixture, "inventory").Count == 0) throw new DemoValidationException("fixture_missing_method_or_inventory");
        var subjects = UniqueIds(Rows(fixture, "inventory"), "subject_ref");
        var observations = UniqueIds(Rows(fixture, "observations"), "observation_id");
        _ = UniqueIds(Rows(fixture, "sourceProfiles"), "family_id");
        var areas = UniqueIds(Rows(fixture, "estateAreas"), "area_ref");
        _ = UniqueIds(Rows(fixture, "riskReviews"), "use_id");
        var observationSubjects = Rows(fixture, "observations").ToDictionary(r => Text(r, "observation_id"), r => Text(r, "subject_ref"), StringComparer.Ordinal);
        var observationsById = Rows(fixture, "observations").ToDictionary(r => Text(r, "observation_id"), StringComparer.Ordinal);
        var instances = new HashSet<string>(StringComparer.Ordinal);
        foreach (var profile in Rows(fixture, "sourceProfiles"))
        {
            if (!areas.Contains(Text(profile, "area_ref"))) throw new DemoValidationException("dangling_source_area");
            foreach (var instance in Strings(profile, "source_instance_refs"))
                if (!instances.Add(instance)) throw new DemoValidationException("ambiguous_source_instance");
        }
        foreach (var row in Rows(fixture, "inventory"))
        {
            foreach (var reference in Strings(row, "observation_refs"))
                if (!observations.Contains(reference) || observationSubjects[reference] != Text(row, "subject_ref")) throw new DemoValidationException("dangling_inventory_observation");
            foreach (var instance in Strings(row, "source_instance_refs"))
                if (!instances.Contains(instance)) throw new DemoValidationException("dangling_inventory_source");
        }
        foreach (var observation in Rows(fixture, "observations"))
            if (!instances.Contains(Text(observation, "source_instance_id"))) throw new DemoValidationException("dangling_observation_source");
        if (fixture["method"]?["numerical_scoring"]?.GetValue<bool>() != false || fixture["method"]?["risk_rating_assigned"]?.GetValue<bool>() != false || Text(fixture["method"]!.AsObject(), "status") != "illustrative_not_enterprise_approved")
            throw new DemoValidationException("fixture_claims_approved_method");
        foreach (var kind in new[] { "observations", "riskReviews", "contextReviews", "limitations", "migrationCandidates" })
            foreach (var row in Rows(fixture, kind))
                if ((kind != "limitations" || row["subject_ref"] is not null) && !subjects.Contains(Text(row, "subject_ref"))) throw new DemoValidationException("dangling_subject_reference");
        foreach (var row in Rows(fixture, "riskReviews"))
        {
            if (row["risk_rating"] is not null || row["execution_authorized"]?.GetValue<bool>() == true || row["residual_risk_accepted"]?.GetValue<bool>() == true)
                throw new DemoValidationException("fixture_claims_unsupported_authority");
            foreach (var reference in Strings(row, "observation_refs"))
                if (!observations.Contains(reference) || observationSubjects[reference] != Text(row, "subject_ref")) throw new DemoValidationException("dangling_use_observation");
        }
        foreach (var row in Rows(fixture, "contextReviews"))
            if (row["execution_authorized"]?.GetValue<bool>() == true || row["residual_risk_accepted"]?.GetValue<bool>() == true || row["source_claim_is_approval"]?.GetValue<bool>() == true || row["source_claim_is_verified_migration"]?.GetValue<bool>() == true)
                throw new DemoValidationException("fixture_claims_unsupported_authority");
        foreach (var row in Rows(fixture, "migrationCandidates"))
            if (row["live_execution_authorized"]?.GetValue<bool>() == true) throw new DemoValidationException("fixture_claims_execution_authority");
        foreach (var kind in new[] { "contextReviews", "migrationCandidates" })
            foreach (var row in Rows(fixture, kind))
                foreach (var reference in Strings(row, "observation_refs"))
                    if (!observations.Contains(reference) || observationSubjects[reference] != Text(row, "subject_ref")) throw new DemoValidationException("cross_subject_evidence_reference");
        foreach (var kind in new[] { "riskReviews", "contextReviews", "migrationCandidates" })
            foreach (var row in Rows(fixture, kind))
                foreach (var evidence in Rows(row, "evidence"))
                {
                    var reference = Text(evidence, "observation_ref");
                    if (!observationsById.TryGetValue(reference, out var observation) || Text(observation, "subject_ref") != Text(row, "subject_ref"))
                        throw new DemoValidationException("cross_subject_evidence_reference");
                    if (Text(evidence, "source_instance_ref") != Text(observation, "source_instance_id") || Text(evidence, "observed_at") != Text(observation, "observed_at") ||
                        Text(evidence, "custody_ref") != Text(observation, "evidence_ref") || Text(evidence, "custody_sha256") != Text(observation, "evidence_sha256"))
                        throw new DemoValidationException("evidence_provenance_mismatch");
                }
        foreach (var row in Rows(fixture, "dependencies"))
        {
            if (!subjects.Contains(Text(row, "from_ref"))) throw new DemoValidationException("dangling_dependency_source");
            if (row["target_present"]?.GetValue<bool>() == true && !subjects.Contains(Text(row, "to_ref"))) throw new DemoValidationException("incorrect_dependency_target_presence");
        }
    }

    private void Import(JsonObject fixture)
    {
        if (Scalar("SELECT id FROM baselines WHERE id=$id", ("$id", baselineId)) is not null)
        {
            VerifyImportedFixture(fixture);
            return;
        }
        using var transaction = connection.BeginTransaction();
        Execute("INSERT INTO baselines VALUES($id,$sha,$asof,$created,$metadata,$method)", transaction,
            ("$id", baselineId), ("$sha", inputSha256), ("$asof", asOf), ("$created", DateTimeOffset.UtcNow.ToString("O")),
            ("$metadata", FixtureMetadata(fixture).ToJsonString()),
            ("$method", fixture["method"]!.ToJsonString()));
        foreach (var kind in Kinds)
        {
            var position = 0;
            foreach (var row in Rows(fixture, kind))
            {
                var key = Text(row, "subject_ref", Text(row, "family_id", Text(row, "area_ref", Text(row, "observation_id", position.ToString(CultureInfo.InvariantCulture)))));
                Execute("INSERT INTO records VALUES($id,$kind,$position,$key,$payload)", transaction,
                    ("$id", baselineId), ("$kind", kind), ("$position", position++), ("$key", key), ("$payload", row.ToJsonString()));
            }
        }
        transaction.Commit();
        VerifyImportedFixture(fixture);
    }

    private static JsonObject FixtureMetadata(JsonObject fixture) => new()
    {
        ["origin"] = fixture["origin"]?.DeepClone(), ["sourceBinding"] = fixture["sourceBinding"]?.DeepClone(),
        ["sourcePageReceipts"] = fixture["sourcePageReceipts"]?.DeepClone(), ["custodyReferences"] = fixture["custodyReferences"]?.DeepClone(),
        ["freshnessDays"] = fixture["freshnessDays"]?.DeepClone(), ["tenantId"] = "synthetic-enterprise", ["synthetic"] = true, ["acceptanceStatus"] = "unaccepted"
    };

    private void VerifyImportedFixture(JsonObject fixture)
    {
        using (var command = Command("SELECT input_sha256,as_of,metadata_json,method_json FROM baselines WHERE id=$id", null, ("$id", baselineId)))
        using (var reader = command.ExecuteReader())
        {
            if (!reader.Read() || reader.GetString(0) != inputSha256 || reader.GetString(1) != asOf ||
                !JsonNode.DeepEquals(ParseObject(reader.GetString(2)), FixtureMetadata(fixture)) ||
                !JsonNode.DeepEquals(ParseObject(reader.GetString(3)), fixture["method"])) throw new DemoValidationException("baseline_integrity_failed");
        }
        var total = Convert.ToInt32(Scalar("SELECT count(*) FROM records WHERE baseline_id=$id", ("$id", baselineId)), CultureInfo.InvariantCulture);
        if (total != Kinds.Sum(kind => Rows(fixture, kind).Count)) throw new DemoValidationException("baseline_integrity_failed");
        foreach (var kind in Kinds)
        {
            var expected = Rows(fixture, kind);
            using var command = Command("SELECT position,record_key,payload_json FROM records WHERE baseline_id=$id AND kind=$kind ORDER BY position", null, ("$id", baselineId), ("$kind", kind));
            using var reader = command.ExecuteReader();
            var position = 0;
            while (reader.Read())
            {
                if (position >= expected.Count || reader.GetInt32(0) != position || !JsonNode.DeepEquals(ParseObject(reader.GetString(2)), expected[position])) throw new DemoValidationException("baseline_integrity_failed");
                var row = expected[position];
                var key = Text(row, "subject_ref", Text(row, "family_id", Text(row, "area_ref", Text(row, "observation_id", position.ToString(CultureInfo.InvariantCulture)))));
                if (reader.GetString(1) != key) throw new DemoValidationException("baseline_integrity_failed");
                position++;
            }
            if (position != expected.Count) throw new DemoValidationException("baseline_integrity_failed");
        }
    }

    public JsonObject Metadata()
    {
        lock (gate)
        {
            EnsureOpen();
            return new JsonObject { ["baselineId"] = baselineId, ["inputSha256"] = inputSha256, ["asOf"] = asOf,
                ["tenantId"] = "synthetic-enterprise", ["synthetic"] = true, ["assetCount"] = Count("inventory"),
                ["acceptanceStatus"] = "unaccepted", ["sourceSystemWriteAuthority"] = false };
        }
    }

    public JsonObject Dashboard()
    {
        lock (gate)
        {
            EnsureOpen();
            var assets = AssetRows();
            return new JsonObject
            {
                ["baseline"] = Metadata(),
                ["counts"] = new JsonObject
                {
                    ["assets"] = assets.Count, ["observations"] = Count("observations"), ["dependencies"] = Count("dependencies"),
                    ["cryptographicUses"] = Count("riskReviews"), ["sourceFamilies"] = Count("sourceProfiles"), ["estateAreas"] = Count("estateAreas"),
                    ["limitations"] = Count("limitations"), ["conflictedAssets"] = assets.Count(a => Text(a, "status") == "conflict"),
                    ["staleAssets"] = ReadRows("limitations").Where(r => Text(r, "code") == "stale_evidence").Select(r => Text(r, "subject_ref")).Distinct().Count(),
                    ["contextOnlyAssets"] = assets.Count(a => a["cryptographicUseCount"]!.GetValue<int>() == 0),
                    ["reports"] = Convert.ToInt32(Scalar("SELECT count(*) FROM reports WHERE baseline_id=$id", ("$id", baselineId)), CultureInfo.InvariantCulture)
                },
                ["families"] = Sources(), ["triageLanes"] = GroupCounts(ReadRows("riskReviews"), "triage_lane"),
                ["limitations"] = GroupCounts(ReadRows("limitations"), "code"),
                ["boundary"] = "Synthetic development evidence only. No enterprise coverage, accepted risk, approved migration, or live integration is claimed."
            };
        }
    }

    public JsonObject Assets(string? q, string? family, string? status, int page, int pageSize)
    {
        lock (gate)
        {
            EnsureOpen();
            if (page < 1 || page > 10_000 || pageSize is < 1 or > 100 || (q?.Length ?? 0) > 200 || (family?.Length ?? 0) > 100 || (status?.Length ?? 0) > 100) throw new DemoValidationException("invalid_asset_query");
            var searchIndex = string.IsNullOrWhiteSpace(q) ? null : BuildAssetSearchIndex();
            var filtered = AssetRows().Where(a => string.IsNullOrWhiteSpace(q) || a.ToJsonString().Contains(q, StringComparison.OrdinalIgnoreCase) ||
                    (searchIndex!.TryGetValue(Text(a, "id"), out var searchText) && searchText.Contains(q, StringComparison.OrdinalIgnoreCase)))
                .Where(a => string.IsNullOrWhiteSpace(family) || Strings(a, "familyIds").Contains(family, StringComparer.Ordinal))
                // Dashboard cards describe overlapping evidence memberships.
                // The primary display badge still has conflict > stale > context
                // precedence, but card drill-downs must preserve their counts.
                .Where(a => string.IsNullOrWhiteSpace(status) || (status switch
                {
                    "conflict" => a["hasConflict"]!.GetValue<bool>(),
                    "stale" => a["isStale"]!.GetValue<bool>(),
                    "context_only" => a["isContextOnly"]!.GetValue<bool>(),
                    _ => Text(a, "status") == status
                })).ToList();
            return new JsonObject { ["items"] = Array(filtered.Skip((page - 1) * pageSize).Take(pageSize)), ["total"] = filtered.Count, ["page"] = page, ["pageSize"] = pageSize };
        }
    }

    public JsonObject? Asset(string id)
    {
        lock (gate)
        {
            EnsureOpen();
            var asset = AssetRows().FirstOrDefault(a => Text(a, "id") == id);
            if (asset is null) return null;
            return new JsonObject { ["asset"] = asset, ["baseline"] = Metadata(),
                ["observations"] = Array(ReadRows("observations").Where(r => Text(r, "subject_ref") == id)),
                ["dependencies"] = Array(ReadRows("dependencies").Where(r => Text(r, "from_ref") == id || Text(r, "to_ref") == id)),
                ["cryptographicUses"] = Array(ReadRows("riskReviews").Where(r => Text(r, "subject_ref") == id)),
                ["limitations"] = Array(ReadRows("limitations").Where(r => Text(r, "subject_ref") == id)) };
        }
    }

    public JsonArray Sources()
    {
        lock (gate)
        {
            EnsureOpen();
            var observations = ReadRows("observations");
            return Array(ReadRows("sourceProfiles").Select(profile =>
            {
                var instances = Strings(profile, "source_instance_refs").ToHashSet(StringComparer.Ordinal);
                var sourceObservations = observations.Where(o => instances.Contains(Text(o, "source_instance_id"))).ToList();
                return new JsonObject { ["id"] = Text(profile, "family_id"), ["name"] = Text(profile, "name"), ["areaRef"] = Text(profile, "area_ref"),
                    ["assetCount"] = sourceObservations.Select(o => Text(o, "subject_ref")).Distinct().Count(), ["observationCount"] = sourceObservations.Count,
                    ["status"] = "synthetic_only", ["profile"] = profile.DeepClone() };
            }));
        }
    }

    private List<JsonObject> AssetRows()
    {
        var profiles = ReadRows("sourceProfiles");
        var risks = ReadRows("riskReviews").GroupBy(r => Text(r, "subject_ref")).ToDictionary(g => g.Key, g => g.Count(), StringComparer.Ordinal);
        var limitations = ReadRows("limitations");
        return ReadRows("inventory").Select(row =>
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

    private Dictionary<string, string> BuildAssetSearchIndex()
    {
        // Only selected normalized descriptive fields are searchable. Custody
        // blobs, source payloads, credentials and filesystem content are never
        // loaded or searched by this application adapter.
        var fields = new HashSet<string>(StringComparer.Ordinal)
        {
            "algorithm", "algorithm_variants", "public_key_algorithm", "public_key_bits", "signature_algorithm",
            "key_exchange", "key_exchange_algorithm", "key_bits", "key_size", "protocol", "protocol_version",
            "version", "implementation", "implementation_version", "library", "library_name", "library_version",
            "runtime_version", "package_name", "package_version", "name", "common_name", "repository_name",
            "deployment_version", "engine_version", "firmware_version", "module_version", "os_version", "platform_version",
            "engine_name", "service_name", "hostname", "listener_hostname", "gateway_hostname", "runtime_platform", "product_label",
            "supported_algorithms", "supported_mechanisms", "key_exchange_group", "owner_route", "business_criticality",
            "owner", "owner_ref", "accountable_owner", "accountable_owner_ref", "application_ref", "application_refs",
            "business_service_ref", "criticality", "purpose", "role", "fact_type", "source_instance_id",
            "triage_lane", "assessment_status", "algorithm_posture", "information_lifetime_basis"
        };
        var index = new Dictionary<string, StringBuilder>(StringComparer.Ordinal);
        foreach (var kind in new[] { "observations", "riskReviews", "contextReviews" })
            foreach (var row in ReadRows(kind))
            {
                var id = Text(row, "subject_ref");
                if (!index.TryGetValue(id, out var text)) index[id] = text = new StringBuilder();
                IndexFields(row, fields, text);
            }
        return index.ToDictionary(entry => entry.Key, entry => entry.Value.ToString(), StringComparer.Ordinal);
    }

    private static void IndexFields(JsonNode? node, HashSet<string> fields, StringBuilder text)
    {
        if (node is JsonObject obj)
        {
            foreach (var property in obj)
            {
                if (fields.Contains(property.Key))
                {
                    if (property.Value is JsonValue value) text.Append(' ').Append(value.ToString());
                    else if (property.Value is JsonArray values)
                        foreach (var item in values.OfType<JsonValue>()) text.Append(' ').Append(item.ToString());
                }
                if (property.Value is JsonObject or JsonArray) IndexFields(property.Value, fields, text);
            }
        }
        else if (node is JsonArray array)
            foreach (var item in array) IndexFields(item, fields, text);
    }

    public void Backup(string destination)
    {
        lock (gate)
        {
            EnsureOpen();
            var target = PrepareDirectory(destination);
            if (target == root || File.Exists(Path.Combine(target, "enterprise-demo.sqlite3"))) throw new DemoConflictException("backup_target_exists");
            using var copy = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = Path.Combine(target, "enterprise-demo.sqlite3"), Pooling = false }.ToString());
            copy.Open();
            connection.BackupDatabase(copy);
            OwnerOnly(Path.Combine(target, "enterprise-demo.sqlite3"));
        }
    }

    private static string PrepareDirectory(string path)
    {
        if (!Path.IsPathFullyQualified(path)) throw new DemoValidationException("absolute_dedicated_store_directory_required");
        path = Path.TrimEndingDirectorySeparator(Path.GetFullPath(path));
        if (path == Path.GetPathRoot(path) || path == Path.GetFullPath(Directory.GetCurrentDirectory()) || path == Environment.GetFolderPath(Environment.SpecialFolder.UserProfile) || path == Path.TrimEndingDirectorySeparator(Path.GetTempPath())) throw new DemoValidationException("broad_store_directory_refused");
        var cursor = new DirectoryInfo(path);
        while (cursor is not null) { if (cursor.Exists && (cursor.Attributes & FileAttributes.ReparsePoint) != 0) throw new DemoValidationException("symlink_store_path_refused"); cursor = cursor.Parent; }
        var markerPath = Path.Combine(path, ".synthetic-demo-store");
        if (Directory.Exists(path) && Directory.EnumerateFileSystemEntries(path).Any())
        {
            RefuseLink(markerPath);
            if (!File.Exists(markerPath) || new FileInfo(markerPath).Length != Encoding.UTF8.GetByteCount(Marker) || File.ReadAllText(markerPath) != Marker) throw new DemoValidationException("unowned_store_directory_refused");
            if (!OperatingSystem.IsWindows() && (File.GetUnixFileMode(path) & (UnixFileMode.GroupRead | UnixFileMode.GroupWrite | UnixFileMode.GroupExecute | UnixFileMode.OtherRead | UnixFileMode.OtherWrite | UnixFileMode.OtherExecute)) != 0) throw new DemoValidationException("store_directory_permissions_unsafe");
            foreach (var entry in Directory.EnumerateFileSystemEntries(path))
            {
                RefuseLink(entry);
                if (Directory.Exists(entry) || !new[] { ".synthetic-demo-store", "enterprise-demo.sqlite3", "enterprise-demo.sqlite3-wal", "enterprise-demo.sqlite3-shm", "instance.lock" }.Contains(Path.GetFileName(entry), StringComparer.Ordinal)) throw new DemoValidationException("unexpected_store_content");
            }
        }
        else
        {
            Directory.CreateDirectory(path);
            if (!OperatingSystem.IsWindows()) File.SetUnixFileMode(path, UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute);
            using var marker = new FileStream(markerPath, FileMode.CreateNew, FileAccess.Write, FileShare.None);
            marker.Write(Encoding.UTF8.GetBytes(Marker));
            marker.Flush(true);
            OwnerOnly(markerPath);
        }
        return path;
    }

    private static void RefuseLink(string path)
    {
        var file = new FileInfo(path);
        if (file.LinkTarget is not null || (file.Exists && (file.Attributes & FileAttributes.ReparsePoint) != 0)) throw new DemoValidationException("symlink_file_refused");
    }
    private static void OwnerOnly(string path) { if (!OperatingSystem.IsWindows()) File.SetUnixFileMode(path, UnixFileMode.UserRead | UnixFileMode.UserWrite); }
    private void EnsureOpen() { if (disposed) throw new DemoStoreException("store_closed"); }
    public void Dispose() { lock (gate) { if (disposed) return; disposed = true; connection.Dispose(); lease.Dispose(); } }
    private static JsonObject ParseObject(string json) => JsonNode.Parse(json, documentOptions: new JsonDocumentOptions { MaxDepth = 40 }) as JsonObject ?? throw new DemoValidationException("invalid_json_object");
    private static string Text(JsonObject row, string key, string fallback = "") => row[key] is JsonValue value && value.TryGetValue<string>(out var text) ? text : fallback;
    private static IEnumerable<string> Strings(JsonObject row, string key) => row[key] is JsonArray values ? values.OfType<JsonValue>().Select(v => v.GetValue<string>()) : [];
    private static List<JsonObject> Rows(JsonObject row, string key) => row[key] is JsonArray values ? values.OfType<JsonObject>().ToList() : [];
    private static HashSet<string> UniqueIds(List<JsonObject> rows, string key)
    {
        var set = new HashSet<string>(StringComparer.Ordinal);
        foreach (var row in rows)
        {
            var id = Text(row, key);
            if (id.Length is < 1 or > 160 || id.Any(c => !char.IsAsciiLetterOrDigit(c) && c is not (':' or '_' or '-' or '.')) || !set.Add(id)) throw new DemoValidationException("invalid_or_duplicate_record_identity");
        }
        return set;
    }
    private static JsonArray Array(IEnumerable<JsonObject> rows) => new(rows.Select(row => (JsonNode?)row.DeepClone()).ToArray());
    private static JsonArray GroupCounts(IEnumerable<JsonObject> rows, string key) => Array(rows.GroupBy(row => Text(row, key, "unknown")).OrderByDescending(g => g.Count()).ThenBy(g => g.Key, StringComparer.Ordinal).Select(g => new JsonObject { ["id"] = g.Key, ["count"] = g.Count() }));
    private int Count(string kind) => Convert.ToInt32(Scalar("SELECT count(*) FROM records WHERE baseline_id=$id AND kind=$kind", ("$id", baselineId), ("$kind", kind)), CultureInfo.InvariantCulture);
    private List<JsonObject> ReadRows(string kind)
    {
        using var command = Command("SELECT payload_json FROM records WHERE baseline_id=$id AND kind=$kind ORDER BY position", null, ("$id", baselineId), ("$kind", kind));
        using var reader = command.ExecuteReader();
        var rows = new List<JsonObject>();
        while (reader.Read()) rows.Add(ParseObject(reader.GetString(0)));
        return rows;
    }
    private SqliteCommand Command(string sql, SqliteTransaction? transaction, params (string Name, object Value)[] parameters)
    {
        var command = connection.CreateCommand(); command.CommandText = sql; command.Transaction = transaction;
        foreach (var parameter in parameters) command.Parameters.AddWithValue(parameter.Name, parameter.Value);
        return command;
    }
    private object? Scalar(string sql, params (string Name, object Value)[] parameters) { using var command = Command(sql, null, parameters); return command.ExecuteScalar(); }
    private void Execute(string sql, params (string Name, object Value)[] parameters) => Execute(sql, null, parameters);
    private void Execute(string sql, SqliteTransaction? transaction, params (string Name, object Value)[] parameters) { using var command = Command(sql, transaction, parameters); command.ExecuteNonQuery(); }
}
