using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

public sealed partial class EnterpriseStore
{
    private void InitializeActionsSchema(Microsoft.Data.Sqlite.SqliteTransaction transaction)
    {
        Execute("""
            CREATE TABLE IF NOT EXISTS review_runs (
              id TEXT PRIMARY KEY, baseline_id TEXT NOT NULL REFERENCES baselines(id),
              finding_id TEXT NOT NULL, idempotency_key TEXT NOT NULL, request_sha256 TEXT NOT NULL,
              actor TEXT NOT NULL, created_at TEXT NOT NULL, invocation_json TEXT NOT NULL, result_json TEXT NOT NULL,
              UNIQUE(baseline_id,idempotency_key));
            CREATE TABLE IF NOT EXISTS review_records (
              id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE REFERENCES review_runs(id),
              baseline_id TEXT NOT NULL REFERENCES baselines(id), finding_id TEXT NOT NULL,
              revision INTEGER NOT NULL CHECK(revision>0), record_sha256 TEXT NOT NULL, record_json TEXT NOT NULL,
              UNIQUE(baseline_id,finding_id,revision));
            """, transaction);
        foreach (var table in new[] { "review_runs", "review_records" })
            foreach (var action in new[] { "UPDATE", "DELETE" })
                Execute($"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{action} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable_record'); END;", transaction);
    }

    public JsonArray Actions()
    {
        lock (gate)
        {
            EnsureOpen();
            using var command = Command("""
                SELECT r.record_json,r.record_sha256 FROM review_records r
                WHERE r.baseline_id=$baseline AND r.revision=(
                  SELECT max(x.revision) FROM review_records x WHERE x.baseline_id=r.baseline_id AND x.finding_id=r.finding_id)
                ORDER BY r.finding_id
                """, null, ("$baseline", baselineId));
            using var reader = command.ExecuteReader();
            var rows = new JsonArray();
            while (reader.Read()) rows.Add(VerifyAction(reader.GetString(0), reader.GetString(1)));
            return rows;
        }
    }

    public JsonArray ActionHistory(string findingId)
    {
        lock (gate)
        {
            EnsureOpen();
            using var command = Command("SELECT record_json,record_sha256 FROM review_records WHERE baseline_id=$baseline AND finding_id=$finding ORDER BY revision", null,
                ("$baseline", baselineId), ("$finding", findingId));
            using var reader = command.ExecuteReader();
            var rows = new JsonArray();
            while (reader.Read()) rows.Add(VerifyAction(reader.GetString(0), reader.GetString(1)));
            return rows;
        }
    }

    private static JsonObject VerifyAction(string body, string hash)
    {
        if (ReviewWorker.Hash(body) != hash) throw new DemoStoreException("review_record_integrity_failed");
        return ParseObject(body);
    }

    // Compatibility entry point only. New decisions must be recorded through
    // an assessment-scoped command; historical action reads remain supported.
    public JsonObject RecordAction(string findingId, string operation, string? disposition, string note, int expectedRevision, string idempotencyKey, string actor)
        => throw new DemoConflictException("assessment_context_required");

    private JsonArray ActionRuns()
    {
        using var command = Command("SELECT id,actor,created_at,invocation_json,result_json FROM review_runs WHERE baseline_id=$baseline ORDER BY created_at DESC,id", null, ("$baseline", baselineId));
        using var reader = command.ExecuteReader();
        var rows = new JsonArray();
        while (reader.Read())
        {
            var invocation = ParseObject(reader.GetString(3));
            var result = ParseObject(reader.GetString(4));
            rows.Add(new JsonObject
            {
                ["id"] = reader.GetString(0), ["reportId"] = null, ["phase"] = "review", ["status"] = "completed", ["actor"] = reader.GetString(1),
                ["createdAt"] = reader.GetString(2), ["manifestId"] = invocation["worker"]!.DeepClone(), ["baselineId"] = baselineId,
                ["result"] = new JsonObject { ["actionId"] = result["output"]?["actionId"]?.DeepClone(), ["artifactSha256"] = result["output"]?["artifact_sha256"]?.DeepClone(), ["synthetic"] = true },
                ["workerInvocation"] = invocation, ["workerResult"] = result
            });
        }
        return rows;
    }
}
