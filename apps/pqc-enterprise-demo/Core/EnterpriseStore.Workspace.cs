using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Microsoft.Data.Sqlite;

namespace PqcEnterpriseDemo;

public sealed partial class EnterpriseStore : IAssessmentWorkStore
{
    private static readonly string[] WorkspaceRecords = ["workspace_receipts", "workspace_products", "workspace_identities", "workspace_consequences", "workspace_bundles", "workspace_observations", "workspace_technical_reviews"];
    private static readonly string[] WorkspaceTables = ["workspace_artifacts", "workspace_receipts", "workspace_products", "workspace_identities", "workspace_consequences", "workspace_bundles", "workspace_observations", "workspace_technical_reviews", "workspace_report_html"];
    private static readonly string WorkspaceSchema = """
        CREATE TABLE workspace_artifacts(assessment_id TEXT NOT NULL REFERENCES assessment_cases(id),sha256 TEXT NOT NULL,byte_count INTEGER NOT NULL CHECK(byte_count>0),content BLOB NOT NULL,created_revision INTEGER NOT NULL,PRIMARY KEY(assessment_id,sha256),FOREIGN KEY(assessment_id,created_revision) REFERENCES assessment_versions(assessment_id,revision));
        CREATE TABLE workspace_report_html(assessment_id TEXT NOT NULL REFERENCES assessment_cases(id),report_id TEXT NOT NULL REFERENCES assessment_documents(id),content_sha256 TEXT NOT NULL,html TEXT NOT NULL,PRIMARY KEY(assessment_id,report_id));
        """ + string.Join("\n", WorkspaceRecords.Select(table => $"CREATE TABLE {table}(assessment_id TEXT NOT NULL REFERENCES assessment_cases(id),id TEXT NOT NULL,revision INTEGER NOT NULL,request_id TEXT NOT NULL,payload_sha256 TEXT NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(assessment_id,id,revision),FOREIGN KEY(assessment_id,revision) REFERENCES assessment_versions(assessment_id,revision));CREATE INDEX {table}_request ON {table}(assessment_id,request_id,revision);"));

    private void InitializeWorkspaceSchema()
    {
        var source=WorkspaceSchema+string.Join("\n",WorkspaceTables.SelectMany(t=>new[]{"UPDATE","DELETE"}.Select(o=>ImmutableTriggerSql(t,o))))+"\nPRAGMA user_version=4;";
        var digest=WorkspaceHash(source);
        var version=Convert.ToInt32(Scalar("PRAGMA user_version"),CultureInfo.InvariantCulture);
        if(version==4)
        {
            if(Scalar("SELECT source_sha256 FROM assessment_schema_migrations WHERE version=4")?.ToString()!=digest)throw new DemoStoreException("workspace_migration_digest_changed");
            foreach(var table in WorkspaceTables)
            {
                foreach(var action in new[]{"UPDATE","DELETE"})ValidateImmutableTrigger(table,action,"workspace_schema_integrity_failed");
                if(WorkspaceRecords.Contains(table))ValidateColumns(table,["assessment_id","id","revision","request_id","payload_sha256","payload_json"],"workspace_schema_integrity_failed");
            }
            ValidateColumns("workspace_artifacts",["assessment_id","sha256","byte_count","content","created_revision"],"workspace_schema_integrity_failed");
            ValidateColumns("workspace_report_html",["assessment_id","report_id","content_sha256","html"],"workspace_schema_integrity_failed");
            return;
        }
        if(version!=3)throw new DemoStoreException("workspace_previous_schema_required");
        if(Convert.ToInt32(Scalar("SELECT count(*) FROM sqlite_master WHERE name LIKE 'workspace_%'"),CultureInfo.InvariantCulture)>0)throw new DemoStoreException("partial_workspace_schema");
        using var tx=connection.BeginTransaction();
        Execute(WorkspaceSchema,tx);
        foreach(var table in WorkspaceTables)foreach(var action in new[]{"UPDATE","DELETE"})Execute(ImmutableTriggerSql(table,action),tx);
        Execute("INSERT INTO assessment_schema_migrations VALUES(4,$sha,$at)",tx,("$sha",digest),("$at",DateTimeOffset.UtcNow.ToString("O")));
        Execute("PRAGMA user_version=4",tx);tx.Commit();
    }

    private static string WorkspaceHash(string value)=>Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(value)));
    private static string WText(JsonObject value,string key,string fallback="")=>value[key]?.GetValue<string>()??fallback;
    private static string WField(JsonObject fields,string key,int maximum=4096,bool required=false)
    {
        var text=fields[key] is null?"":fields[key] is JsonValue v&&v.TryGetValue<string>(out var s)?s:throw new DemoValidationException("workspace_field_invalid");
        if(text.Length>maximum||text.Any(c=>char.IsControl(c)&&c is not ('\n' or '\r' or '\t'))||required&&string.IsNullOrWhiteSpace(text))throw new DemoValidationException("workspace_field_invalid");
        return text.Trim();
    }
    private static void WClosed(JsonObject fields,params string[] allowed)
    {if(fields.Any(f=>!allowed.Contains(f.Key,StringComparer.Ordinal)))throw new DemoValidationException("workspace_fields_invalid");}
    private static void WorkspaceStaff(AssessmentState state,string principal)
    {if(AssessmentWorkflow.Role(state,principal) is "contributor")throw new DemoValidationException("assessment_forbidden");}
    private static void WorkspaceLead(AssessmentState state,string principal)
    {if(AssessmentWorkflow.Role(state,principal)!="assessment-lead")throw new DemoValidationException("assessment_forbidden");}

    private List<JsonObject> WorkspaceRows(AssessmentState state,string table,string? requestId=null)
    {
        if(!WorkspaceRecords.Contains(table))throw new DemoStoreException("workspace_table_invalid");
        using var query=Command($"SELECT r.payload_json,r.payload_sha256 FROM {table} r WHERE r.assessment_id=$id AND r.revision<=$revision AND ($request='' OR r.request_id=$request) AND NOT EXISTS(SELECT 1 FROM {table} n WHERE n.assessment_id=r.assessment_id AND n.id=r.id AND n.revision>r.revision AND n.revision<=$revision) ORDER BY r.revision,r.id",null,("$id",state.Id),("$revision",state.Revision),("$request",requestId??""));
        using var reader=query.ExecuteReader();var rows=new List<JsonObject>();
        while(reader.Read())
        {var payload=reader.GetString(0);if(WorkspaceHash(payload)!=reader.GetString(1))throw new DemoStoreException("workspace_record_integrity_failed");rows.Add(ParseObject(payload));}
        return rows;
    }
    private void WorkspaceInsert(string table,AssessmentState state,JsonObject value,SqliteTransaction tx)
    {
        if(!WorkspaceRecords.Contains(table))throw new DemoStoreException("workspace_table_invalid");
        value["revision"]=state.Revision;var json=value.ToJsonString();
        Execute($"INSERT INTO {table} VALUES($assessment,$id,$revision,$request,$sha,$json)",tx,("$assessment",state.Id),("$id",WText(value,"id")),("$revision",state.Revision),("$request",WText(value,"requestId")),("$sha",WorkspaceHash(json)),("$json",json));
    }
    private JsonObject WorkspaceFind(AssessmentState state,string table,string id)=>WorkspaceRows(state,table).SingleOrDefault(r=>WText(r,"id")==id)??throw new DemoValidationException("workspace_record_not_found");

    private AssessmentState WorkspaceCommit(string id,AssessmentCommand command,string principal,
        Func<AssessmentState,List<(string Table,JsonObject Record)>> evaluate,byte[]? artifact=null,string? eventOperation=null)
    {
        EnsureOpen();ValidateAssessmentKey(command.IdempotencyKey);
        var state=ReadAssessment(id,principal);WorkspaceStaff(state,principal);
        if(state.BaselineId!=baselineId)throw new DemoConflictException("assessment_baseline_unavailable");
        var role=AssessmentWorkflow.Role(state,principal);
        if(command.Operation=="workspace_review_evidence"?role!="technical-reviewer":command.Operation=="record_consequence"?role is not("assessment-lead" or "risk-lead"):role!="assessment-lead")throw new DemoValidationException("assessment_forbidden");
        var hash=AssessmentWorkflow.Hash(new{command.Operation,command.TargetId,command.Fields,command.ExpectedRevision,principal});
        using(var query=Command("SELECT request_sha256,revision FROM assessment_commands WHERE assessment_id=$id AND idempotency_key=$key",null,("$id",id),("$key",command.IdempotencyKey)))
        using(var reader=query.ExecuteReader())if(reader.Read())
        {if(reader.GetString(0)!=hash)throw new DemoConflictException("idempotency_request_changed");var revision=reader.GetInt32(1);reader.Close();return ReadAssessment(id,principal,revision);}
        if(state.Revision!=command.ExpectedRevision)throw new DemoConflictException("assessment_revision_changed");
        if(state.Events.Count>=2000)throw new DemoConflictException("assessment_event_limit");
        var effects=evaluate(state);
        var phase1Changes=effects.Where(e=>e.Table!="workspace_consequences" ||
            WorkspaceRows(state,"workspace_consequences").SingleOrDefault(r=>WText(r,"id")==WText(e.Record,"id")) is not JsonObject previous ||
            AssessmentWorkflow.Hash(WorkspacePhase1Consequence(previous))!=AssessmentWorkflow.Hash(WorkspacePhase1Consequence(e.Record))).ToArray();
        state.Revision++;state.Workspace.ThroughRevision=state.Revision;state.UpdatedAt=DateTimeOffset.UtcNow.ToString("O");
        state.Events.Add(new(state.Revision,eventOperation??command.Operation,command.TargetId,principal,state.UpdatedAt,state.ScenarioVersion is not null?"scenario_generated":"user_entered_synthetic"));
        // Receipt staging is administrative. Only reviewed decisions affect the report basis.
        if(command.Operation is "receipt_apply" or "reconcile_product" or "record_consequence" or "workspace_admit_evidence")
        {
            state.Workspace.Phase1MaterialFingerprint??=state.Workspace.MaterialFingerprint;
            if(phase1Changes.Length>0)
                state.Workspace.Phase1MaterialFingerprint=AssessmentWorkflow.Hash(new{previous=state.Workspace.Phase1MaterialFingerprint,command.Operation,command.TargetId,
                    effects=phase1Changes.Select(e=>e.Table=="workspace_consequences"?WorkspacePhase1Consequence(e.Record):e.Record)});
            state.Workspace.MaterialFingerprint=AssessmentWorkflow.Hash(new{previous=state.Workspace.MaterialFingerprint,command.Operation,command.TargetId,effects=effects.Select(e=>e.Record)});
        }
        AssessmentWorkflow.Refresh(state,principal);
        if(Encoding.UTF8.GetByteCount(JsonSerializer.Serialize(state,AssessmentJson.Options))>AssessmentJson.MaxSnapshotBytes)throw new DemoConflictException("workspace_snapshot_capacity_limit");
        using var tx=connection.BeginTransaction();
        using(var check=Command("SELECT max(revision) FROM assessment_versions WHERE assessment_id=$id",tx,("$id",id)))
            if(Convert.ToInt32(check.ExecuteScalar(),CultureInfo.InvariantCulture)!=command.ExpectedRevision)throw new DemoConflictException("assessment_revision_changed");
        PersistAssessment(state,command,principal,hash,tx);
        if(artifact is not null)
        {
            var sha=Convert.ToHexStringLower(SHA256.HashData(artifact));
            using var lookup=Command("SELECT sha256 FROM workspace_artifacts WHERE assessment_id=$id AND sha256=$sha",tx,("$id",id),("$sha",sha));
            if(lookup.ExecuteScalar() is null)
            {
                using var usage=Command("SELECT coalesce(sum(byte_count),0) FROM workspace_artifacts",tx);
                var total=Convert.ToInt64(usage.ExecuteScalar(),CultureInfo.InvariantCulture);
                if(total+artifact.Length>33_554_432)throw new DemoConflictException("workspace_custody_capacity_limit");
                Execute("INSERT INTO workspace_artifacts VALUES($id,$sha,$count,$bytes,$revision)",tx,("$id",id),("$sha",sha),("$count",artifact.Length),("$bytes",artifact),("$revision",state.Revision));
            }
        }
        foreach(var effect in effects)WorkspaceInsert(effect.Table,state,effect.Record,tx);
        tx.Commit();return state;
    }

    private static JsonObject WorkspacePhase1Consequence(JsonObject row)
    {
        var result=new JsonObject();
        foreach(var key in new[]{"id","requestId","productId","status","phase1Conclusion","limitation","nextDecision","responsibleFunction","confidence","cryptographicPurpose",
            "supportingObservationIds","contradictingObservationIds","evidenceRefs","evidenceRevisionRefs","reviewRevisionRefs","identityRefs","receiptRefs"})
            result[key]=row[key]?.DeepClone();
        return result;
    }

    private void StoreWorkspaceReportHtml(string assessmentId,string reportId,string html,SqliteTransaction tx)
    {Execute("INSERT INTO workspace_report_html VALUES($assessment,$report,$sha,$html)",tx,("$assessment",assessmentId),("$report",reportId),("$sha",WorkspaceHash(html)),("$html",html));}
    private string? ReadWorkspaceReportHtml(string assessmentId,string reportId)
    {
        using var query=Command("SELECT html,content_sha256 FROM workspace_report_html WHERE assessment_id=$assessment AND report_id=$report",null,("$assessment",assessmentId),("$report",reportId));
        using var reader=query.ExecuteReader();if(!reader.Read())return null;var html=reader.GetString(0);
        if(WorkspaceHash(html)!=reader.GetString(1))throw new DemoStoreException("workspace_report_integrity_failed");return html;
    }
}
