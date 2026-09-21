using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Microsoft.Data.Sqlite;

namespace PqcEnterpriseDemo;

public sealed partial class EnterpriseStore : IAssessmentStore
{
    private const string AssessmentSchema = """
        CREATE TABLE assessment_schema_migrations(version INTEGER PRIMARY KEY,source_sha256 TEXT NOT NULL,applied_at TEXT NOT NULL);
        CREATE TABLE assessment_cases(id TEXT PRIMARY KEY,baseline_id TEXT NOT NULL REFERENCES baselines(id),name TEXT NOT NULL,mode TEXT NOT NULL CHECK(mode IN ('fresh','worked_example')),created_by TEXT NOT NULL,created_at TEXT NOT NULL,create_key TEXT NOT NULL UNIQUE,create_sha256 TEXT NOT NULL);
        CREATE TABLE assessment_versions(assessment_id TEXT NOT NULL REFERENCES assessment_cases(id),revision INTEGER NOT NULL CHECK(revision>0),snapshot_sha256 TEXT NOT NULL,snapshot_json TEXT NOT NULL,PRIMARY KEY(assessment_id,revision));
        CREATE TABLE assessment_commands(id TEXT PRIMARY KEY,assessment_id TEXT NOT NULL REFERENCES assessment_cases(id),revision INTEGER NOT NULL,idempotency_key TEXT NOT NULL,request_sha256 TEXT NOT NULL,principal_id TEXT NOT NULL,created_at TEXT NOT NULL,invocation_json TEXT NOT NULL,result_json TEXT NOT NULL,UNIQUE(assessment_id,idempotency_key),FOREIGN KEY(assessment_id,revision) REFERENCES assessment_versions(assessment_id,revision));
        CREATE TABLE assessment_events(assessment_id TEXT NOT NULL REFERENCES assessment_cases(id),revision INTEGER NOT NULL,event_json TEXT NOT NULL,event_sha256 TEXT NOT NULL,PRIMARY KEY(assessment_id,revision));
        CREATE TABLE assessment_documents(id TEXT PRIMARY KEY,assessment_id TEXT NOT NULL REFERENCES assessment_cases(id),phase TEXT NOT NULL CHECK(phase IN ('phase1','phase2')),created_at TEXT NOT NULL,content_sha256 TEXT NOT NULL,content_json TEXT NOT NULL,input_fingerprint TEXT NOT NULL,assessment_revision INTEGER NOT NULL,phase1_report_id TEXT REFERENCES assessment_documents(id));
        CREATE INDEX assessment_documents_scope ON assessment_documents(assessment_id,phase);
        """;
    private static readonly string[] AssessmentTables = ["assessment_schema_migrations","assessment_cases","assessment_versions","assessment_commands","assessment_events","assessment_documents"];
    private static string ImmutableTriggerSql(string table,string operation) => $"CREATE TRIGGER immutable_{table}_{operation} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'immutable_record'); END;";
    private static string NormalizeSchemaSql(string sql) => Regex.Replace(sql,"\\s+"," ").Trim().TrimEnd(';').Replace(" IF NOT EXISTS","",StringComparison.OrdinalIgnoreCase).ToUpperInvariant();
    private void ValidateImmutableTrigger(string table,string operation,string code)
    {
        var sql=Scalar("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=$name",("$name","immutable_"+table+"_"+operation))?.ToString();
        if(sql is null || NormalizeSchemaSql(sql)!=NormalizeSchemaSql(ImmutableTriggerSql(table,operation)))throw new DemoStoreException(code);
    }
    private void ValidateColumns(string table,IReadOnlyList<string> expected,string code)
    {
        using var query=Command("SELECT name FROM pragma_table_info($table) ORDER BY cid",null,("$table",table));
        using var reader=query.ExecuteReader();var actual=new List<string>();while(reader.Read())actual.Add(reader.GetString(0));
        if(!actual.SequenceEqual(expected,StringComparer.Ordinal))throw new DemoStoreException(code);
    }

    private void ValidateLegacyAssessmentStore(int version)
    {
        if(version is not (1 or 2))throw new DemoValidationException("unsupported_database_schema");
        var tables=new List<string>{"baselines","records","worker_runs","reports","run_events"};
        if(version==2)tables.AddRange(["review_runs","review_records"]);
        foreach(var table in tables)
        {
            if(Convert.ToInt32(Scalar("SELECT count(*) FROM sqlite_master WHERE type='table' AND name=$name",("$name",table)),CultureInfo.InvariantCulture)!=1)throw new DemoStoreException("legacy_schema_integrity_failed");
            foreach(var operation in new[]{"UPDATE","DELETE"})ValidateImmutableTrigger(table,operation,"legacy_schema_integrity_failed");
        }
        ValidateColumns("baselines",["id","input_sha256","as_of","created_at","metadata_json","method_json"],"legacy_schema_integrity_failed");
        ValidateColumns("records",["baseline_id","kind","position","record_key","payload_json"],"legacy_schema_integrity_failed");
        ValidateColumns("worker_runs",["id","baseline_id","phase","idempotency_key","actor","created_at","status","invocation_json","result_json"],"legacy_schema_integrity_failed");
        ValidateColumns("reports",["id","baseline_id","worker_run_id","phase","created_at","content_sha256","content_json"],"legacy_schema_integrity_failed");
        ValidateColumns("run_events",["id","worker_run_id","kind","metadata_json"],"legacy_schema_integrity_failed");
        if(version==2)
        {
            ValidateColumns("review_runs",["id","baseline_id","finding_id","idempotency_key","request_sha256","actor","created_at","invocation_json","result_json"],"legacy_schema_integrity_failed");
            ValidateColumns("review_records",["id","run_id","baseline_id","finding_id","revision","record_sha256","record_json"],"legacy_schema_integrity_failed");
        }
    }

    private void InitializeAssessmentSchema()
    {
        var version=Convert.ToInt32(Scalar("PRAGMA user_version"),CultureInfo.InvariantCulture);
        var migrationSource=AssessmentSchema+string.Join("\n",AssessmentTables.SelectMany(table=>new[]{"UPDATE","DELETE"}.Select(operation=>ImmutableTriggerSql(table,operation))))+"\nPRAGMA user_version=3;";
        var digest=Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(migrationSource)));
        if(version is 3 or 4)
        {
            foreach(var table in AssessmentTables)
            {
                if(Convert.ToInt32(Scalar("SELECT count(*) FROM sqlite_master WHERE type='table' AND name=$name",("$name",table)),CultureInfo.InvariantCulture)!=1) throw new DemoStoreException("assessment_schema_integrity_failed");
                foreach(var action in new[]{"UPDATE","DELETE"})ValidateImmutableTrigger(table,action,"assessment_schema_integrity_failed");
            }
            if(Convert.ToInt32(Scalar("SELECT count(*) FROM assessment_schema_migrations"),CultureInfo.InvariantCulture)!=(version==4?2:1) || Scalar("SELECT source_sha256 FROM assessment_schema_migrations WHERE version=3")?.ToString()!=digest) throw new DemoStoreException("assessment_migration_digest_changed");
            ValidateColumns("assessment_schema_migrations",["version","source_sha256","applied_at"],"assessment_schema_integrity_failed");
            ValidateColumns("assessment_cases",["id","baseline_id","name","mode","created_by","created_at","create_key","create_sha256"],"assessment_schema_integrity_failed");
            ValidateColumns("assessment_versions",["assessment_id","revision","snapshot_sha256","snapshot_json"],"assessment_schema_integrity_failed");
            ValidateColumns("assessment_commands",["id","assessment_id","revision","idempotency_key","request_sha256","principal_id","created_at","invocation_json","result_json"],"assessment_schema_integrity_failed");
            ValidateColumns("assessment_events",["assessment_id","revision","event_json","event_sha256"],"assessment_schema_integrity_failed");
            ValidateColumns("assessment_documents",["id","assessment_id","phase","created_at","content_sha256","content_json","input_fingerprint","assessment_revision","phase1_report_id"],"assessment_schema_integrity_failed");
            return;
        }
        if(version is not (1 or 2)) throw new DemoValidationException("unsupported_database_schema");
        if(Convert.ToInt32(Scalar("SELECT count(*) FROM sqlite_master WHERE name LIKE 'assessment_%'"),CultureInfo.InvariantCulture)>0) throw new DemoStoreException("partial_assessment_schema");
        using var transaction=connection.BeginTransaction();
        Execute(AssessmentSchema,transaction);
        Execute("INSERT INTO assessment_schema_migrations VALUES(3,$hash,$at)",transaction,("$hash",digest),("$at",DateTimeOffset.UtcNow.ToString("O")));
        foreach(var table in AssessmentTables)
            foreach(var action in new[]{"UPDATE","DELETE"})
                Execute(ImmutableTriggerSql(table,action),transaction);
        Execute("PRAGMA user_version=3",transaction);
        transaction.Commit();
    }

    public JsonObject Catalog(string principal)
    {
        lock(gate)
        {
            EnsureOpen(); AssessmentWorkflow.KnownPrincipal(principal);
            return new JsonObject { ["schemaVersion"]="pqc.assessment.catalog.v1",["synthetic"]=true,
                ["personas"]=JsonSerializer.SerializeToNode(AssessmentWorkflow.Personas,AssessmentJson.Options),
                ["stages"]=JsonSerializer.SerializeToNode(AssessmentWorkflow.Stages,AssessmentJson.Options),
                ["gates"]=JsonSerializer.SerializeToNode(AssessmentWorkflow.NewGates(),AssessmentJson.Options),
                ["sourceFamilies"]=JsonSerializer.SerializeToNode(SourceCatalog(),AssessmentJson.Options),
                ["depthOptions"]=new JsonArray(AssessmentWorkflow.Depths.Select(v=>(JsonNode)new JsonObject{["id"]=v,["label"]=v.Replace('_',' ')}).ToArray()),
                ["operations"]=JsonSerializer.SerializeToNode(AssessmentWorkflow.Operations(AssessmentWorkflow.Personas.Single(p=>p.PrincipalId==principal).Role)),
                ["boundary"]="Fixed synthetic personas and sample evidence; no enterprise identity, source access or execution authority." };
        }
    }

    public JsonArray ListAssessments(string principal)
    {
        lock(gate)
        {
            EnsureOpen(); AssessmentWorkflow.KnownPrincipal(principal);
            using var command=Command("SELECT id FROM assessment_cases ORDER BY created_at DESC,id LIMIT 100",null);
            using var reader=command.ExecuteReader(); var ids=new List<string>();while(reader.Read())ids.Add(reader.GetString(0));reader.Close();
            var visible=new List<AssessmentState>();
            foreach(var id in ids)
            {
                AssessmentState state;
                try{state=ReadAssessment(id,principal);}
                catch(DemoValidationException e) when(e.Code=="assessment_forbidden"){continue;}
                if(IntakeWorkflow.Contributor(principal) && !state.Intake.Requests.Any(r=>r.AssignedTo==principal) && !state.Questionnaires.Assignments.Any(a=>a.AssignedTo==principal) && !state.Discovery.Requests.Any(r=>r.AssignedTo==principal))continue;
                AssessmentWorkflow.Refresh(state,principal);visible.Add(state);
            }
            return new JsonArray(visible.Select(state=>
            {
                return (JsonNode)new JsonObject{["id"]=state.Id,["name"]=state.Name,["mode"]=state.Mode,["revision"]=state.Revision,["stage"]=state.Stage,["synthetic"]=true,["updatedAt"]=state.UpdatedAt,["baselineId"]=state.BaselineId};
            }).ToArray());
        }
    }

    public JsonObject CreateAssessment(string name,string mode,string key,string principal)
    {
        lock(gate)
        {
            EnsureOpen();AssessmentWorkflow.KnownPrincipal(principal);ValidateAssessmentKey(key);
            if(principal!="synthetic-demo:analyst")throw new DemoValidationException("assessment_forbidden");
            if(string.IsNullOrWhiteSpace(name) || name.Length>160 || name.Any(char.IsControl) || mode is not ("fresh" or "worked_example" or "response_to_report_example"))throw new DemoValidationException("assessment_create_invalid");
            var requestHash=AssessmentWorkflow.Hash(new{name=name.Trim(),mode,principal,baselineId});
            using(var lookup=Command("SELECT id,create_sha256 FROM assessment_cases WHERE create_key=$key",null,("$key",key)))
            using(var reader=lookup.ExecuteReader())
                if(reader.Read())
                {
                    if(reader.GetString(1)!=requestHash)throw new DemoConflictException("idempotency_request_changed");
                    var existing=reader.GetString(0);reader.Close();
                    var createdRevision=Convert.ToInt32(Scalar("SELECT revision FROM assessment_commands WHERE assessment_id=$id AND idempotency_key=$key",("$id",existing),("$key",key)),CultureInfo.InvariantCulture);
                    return VersionView(existing,createdRevision,principal);
                }
            if(Convert.ToInt32(Scalar("SELECT count(*) FROM assessment_cases"),CultureInfo.InvariantCulture)>=100)throw new DemoConflictException("assessment_retention_limit");
            var now=DateTimeOffset.UtcNow.ToString("O");
            var storageMode=mode=="response_to_report_example"?"fresh":mode;
            var state=new AssessmentState { Id="assessment-"+Guid.NewGuid().ToString("N"),Name=name.Trim(),Mode=storageMode,Revision=1,
                ScenarioVersion=mode=="worked_example"?"pqc.worked-example.v1":mode=="response_to_report_example"?"pqc.response-to-report.example.v1":null,
                CreatedAt=now,UpdatedAt=now,CreatedBy=principal,BaselineId=baselineId,Assignments=[..AssessmentWorkflow.Personas],Sources=SourceCatalog(),Gates=AssessmentWorkflow.NewGates() };
            state.Scope.IncludedFamilyIds=state.Sources.Select(s=>s.FamilyId).Order(StringComparer.Ordinal).ToList();
            state.Scope.DepthByFamily=state.Sources.ToDictionary(s=>s.FamilyId,_=>"routing",StringComparer.Ordinal);
            state.Packages=state.Sources.Select(s=>new AssessmentPackage{Id=s.FamilyId,FamilyId=s.FamilyId,Label=s.Name}).ToList();
            state.Events.Add(new(1,"create_assessment",null,principal,now,state.ScenarioVersion is not null?"scenario_generated":"user_entered_synthetic"));
            AssessmentWorkflow.Refresh(state,principal);
            if(mode=="worked_example") SeedWorkedExample(state,principal);
            using var transaction=connection.BeginTransaction();
            Execute("INSERT INTO assessment_cases VALUES($id,$base,$name,$mode,$actor,$at,$key,$sha)",transaction,("$id",state.Id),("$base",baselineId),("$name",state.Name),("$mode",storageMode),("$actor",principal),("$at",now),("$key",key),("$sha",requestHash));
            PersistAssessment(state,new AssessmentCommand("create_assessment",null,new JsonObject{["name"]=state.Name,["mode"]=mode},0,key),principal,requestHash,transaction);
            transaction.Commit();
            return GetAssessment(state.Id,principal);
        }
    }

    public JsonObject GetAssessment(string id,string principal)
    {
        lock(gate){EnsureOpen();var state=ReadAssessment(id,principal);AssessmentWorkflow.Refresh(state,principal);return AssessmentResponseView(state,principal);}
    }

    public JsonObject ExecuteAssessmentCommand(string id,AssessmentCommand command,string principal)
    {
        lock(gate)
        {
            EnsureOpen();ValidateAssessmentKey(command.IdempotencyKey);
            var state=ReadAssessment(id,principal);
            if(state.BaselineId!=baselineId)throw new DemoConflictException("assessment_baseline_unavailable");
            if(command.ExpectedRevision<1 || command.Operation.Length>48 || command.Fields.ToJsonString().Length>32768)throw new DemoValidationException("assessment_command_invalid");
            var requestHash=AssessmentWorkflow.Hash(new{command.Operation,command.TargetId,command.Fields,command.ExpectedRevision,principal});
            using(var lookup=Command("SELECT request_sha256,revision FROM assessment_commands WHERE assessment_id=$id AND idempotency_key=$key",null,("$id",id),("$key",command.IdempotencyKey)))
            using(var reader=lookup.ExecuteReader())
                if(reader.Read())
                {
                    if(reader.GetString(0)!=requestHash)throw new DemoConflictException("idempotency_request_changed");
                    var revision=reader.GetInt32(1);reader.Close();return VersionView(id,revision,principal);
                }
            if(state.Revision!=command.ExpectedRevision)throw new DemoConflictException("assessment_revision_changed");
            if(state.Events.Count>=2000)throw new DemoConflictException("assessment_event_limit");
            var now=DateTimeOffset.UtcNow.ToString("O");
            JsonObject? reportContent=null; AssessmentDocument? document=null;
            if(command.Operation=="generate_report")
            {
                if(state.Documents.Count>=50)throw new DemoConflictException("assessment_report_retention_limit");
                AssessmentWorkflow.Refresh(state,principal);
                if(!state.AvailableOperations.Contains("generate_report"))throw new DemoValidationException("assessment_forbidden");
                var phase=AssessmentWorkflow.Required(command.Fields,"phase");
                if(phase is not ("phase1" or "phase2"))throw new DemoValidationException("invalid_report_phase");
                AssessmentWorkflow.Closed(command.Fields,phase=="phase1"?["phase"]:["phase","phase1ReportId"]);
                if(state.Scope.Objective.Length==0)throw new DemoConflictException("assessment_scope_required");
                JsonObject? manifest=null;string? phase1Id=null;
                if(phase=="phase2")
                {
                    phase1Id=AssessmentWorkflow.Required(command.Fields,"phase1ReportId");
                    var inputGate=state.Gates.Single(g=>g.Id=="PQC-P1-G03");
                    if(state.Phase1InputReportId!=phase1Id || inputGate.DocumentId!=phase1Id || !AssessmentWorkflow.Accepted(inputGate.State))throw new DemoConflictException("selected_phase1_handoff_required");
                    var phase1=state.Documents.SingleOrDefault(d=>d.Id==phase1Id && d.Phase=="phase1") ?? throw new DemoValidationException("assessment_report_not_found");
                    if(phase1.InputFingerprint!=AssessmentWorkflow.ReportFingerprint(state,"phase1") || !AssessmentWorkflow.Accepted(phase1.Status))throw new DemoConflictException("phase1_inputs_require_review");
                    var frozenPhase1=GetAssessmentReport(id,phase1Id,principal) ?? throw new DemoStoreException("assessment_report_manifest_missing");
                    manifest=new JsonObject{["reportId"]=phase1.Id,["contentSha256"]=phase1.ContentSha256,["inputFingerprint"]=phase1.InputFingerprint,
                        ["scopeRevision"]=frozenPhase1["content"]?["manifest"]?["scopeRevision"]?.DeepClone(),["dataBaselineId"]=state.BaselineId,["acceptanceStatus"]=phase1.Status,
                        ["gateDecisionRefs"]=new JsonArray(state.Gates.Where(g=>g.Id=="PQC-P1-G03" && g.DocumentId==phase1Id).SelectMany(g=>g.Decisions.Where(d=>d.Fingerprint==g.Fingerprint)).Select(d=>(JsonNode?)JsonValue.Create(d.Id)).ToArray())};
                }
                var fingerprint=AssessmentWorkflow.ReportFingerprint(state,phase,phase1Id);
                var snapshot=AssessmentJson.Object(state);
                reportContent=AssessmentReportRenderer.Build(phase,snapshot,AssessmentProjection(id,principal),manifest,WorkspaceReportInput(state));
                var contentJson=reportContent.ToJsonString();
                if(Encoding.UTF8.GetByteCount(contentJson)>4_194_304)throw new DemoConflictException("assessment_report_artifact_limit");
                document=new AssessmentDocument{Id="assessment-report-"+Guid.NewGuid().ToString("N"),Phase=phase,CreatedAt=now,
                    ContentSha256=Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(contentJson))),InputFingerprint=fingerprint,
                    AssessmentRevision=state.Revision,Phase1ReportId=phase1Id};
                state.Documents.Add(document);state.Revision++;state.UpdatedAt=now;state.Events.Add(new(state.Revision,command.Operation,document.Id,principal,now,state.ScenarioVersion is not null?"scenario_generated":"user_entered_synthetic"));
                AssessmentWorkflow.Refresh(state,principal);
            }
            else AssessmentWorkflow.Apply(state,command,principal,now,command.Operation=="admit_sample"?SampleFor(state,command.TargetId):null);
            using var transaction=connection.BeginTransaction();
            using(var check=Command("SELECT max(revision) FROM assessment_versions WHERE assessment_id=$id",transaction,("$id",id)))
                if(Convert.ToInt32(check.ExecuteScalar(),CultureInfo.InvariantCulture)!=command.ExpectedRevision)throw new DemoConflictException("assessment_revision_changed");
            if(document is not null && reportContent is not null)
            {
                Execute("INSERT INTO assessment_documents VALUES($id,$assessment,$phase,$at,$sha,$content,$fingerprint,$revision,$phase1)",transaction,
                    ("$id",document.Id),("$assessment",id),("$phase",document.Phase),("$at",now),("$sha",document.ContentSha256),("$content",reportContent.ToJsonString()),
                    ("$fingerprint",document.InputFingerprint),("$revision",document.AssessmentRevision),("$phase1",(object?)document.Phase1ReportId??DBNull.Value));
                StoreWorkspaceReportHtml(id,document.Id,AssessmentReportRenderer.RenderHtml(document.Id,document.CreatedAt,reportContent),transaction);
            }
            PersistAssessment(state,command,principal,requestHash,transaction);
            transaction.Commit();return AssessmentResponseView(state,principal);
        }
    }

    public JsonObject AssessmentEvidenceSelection(string id,string principal)
    {
        lock(gate)
        {
            var state=ReadAssessment(id,principal);
            if(state.BaselineId!=baselineId)throw new DemoConflictException("assessment_baseline_unavailable");
            var sources=state.Sources.Where(s=>state.Scope.IncludedFamilyIds.Contains(s.FamilyId)).ToArray();
            return new JsonObject{["assessmentId"]=id,["baselineId"]=state.BaselineId,
                ["subjectIds"]=JsonSerializer.SerializeToNode(sources.SelectMany(s=>s.SubjectIds).Distinct().Order(StringComparer.Ordinal)),
                ["observationIds"]=JsonSerializer.SerializeToNode(sources.SelectMany(s=>s.ObservationIds).Distinct().Order(StringComparer.Ordinal)),
                ["familyIds"]=JsonSerializer.SerializeToNode(state.Scope.IncludedFamilyIds)};
        }
    }

    public JsonObject? GetAssessmentReport(string id,string reportId,string principal)
    {
        lock(gate)
        {
            var state=ReadAssessment(id,principal);
            using var query=Command("SELECT content_json,content_sha256,phase,created_at,input_fingerprint,assessment_revision FROM assessment_documents WHERE assessment_id=$assessment AND id=$report",null,("$assessment",id),("$report",reportId));
            using var reader=query.ExecuteReader();if(!reader.Read())return null;
            var content=reader.GetString(0);var hash=Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(content)));
            if(hash!=reader.GetString(1))throw new DemoStoreException("assessment_report_integrity_failed");
            var parsed=ParseObject(content);var revision=reader.GetInt32(5);
            var metadata=new JsonObject{["id"]=reportId,["phase"]=reader.GetString(2),["title"]=parsed["title"]?.DeepClone(),["baselineId"]=state.BaselineId,
                ["inputSha256"]=state.BaselineId.Replace("baseline-","",StringComparison.Ordinal),["createdAt"]=reader.GetString(3),["contentSha256"]=hash,
                ["inputFingerprint"]=reader.GetString(4),["assessmentRevision"]=revision,["synthetic"]=true,["acceptanceStatus"]="unaccepted",
                ["authorityBoundary"]="Enterprise acceptance not recorded; synthetic gate state is shown separately on the assessment."};
            reader.Close();metadata["workerRunId"]=Scalar("SELECT id FROM assessment_commands WHERE assessment_id=$id AND revision=$revision",("$id",id),("$revision",revision+1))?.ToString();
            return new JsonObject{["metadata"]=metadata,["content"]=parsed};
        }
    }
    public string? RenderAssessmentReportHtml(string id,string reportId,string principal)
    {
        lock(gate)
        {
            var report=GetAssessmentReport(id,reportId,principal);if(report is null)return null;
            return ReadWorkspaceReportHtml(id,reportId)??AssessmentReportRenderer.RenderHtml(reportId,report["metadata"]!["createdAt"]!.GetValue<string>(),report["content"]!.AsObject());
        }
    }

    public JsonArray AssessmentRuns(string id,string principal)
    {
        lock(gate)
        {
            var state=ReadAssessment(id,principal);
            using var query=Command("SELECT id,revision,principal_id,created_at,invocation_json,result_json FROM assessment_commands WHERE assessment_id=$id ORDER BY revision DESC LIMIT 2000",null,("$id",id));
            using var reader=query.ExecuteReader();var result=new JsonArray();
            while(reader.Read())
            {
                var revision=reader.GetInt32(1);var invocation=ParseObject(reader.GetString(4));var workerResult=ParseObject(reader.GetString(5));
                var document=state.Documents.SingleOrDefault(d=>d.AssessmentRevision+1==revision);
                result.Add(new JsonObject{["id"]=reader.GetString(0),["assessmentId"]=id,["revision"]=revision,["actor"]=reader.GetString(2),["createdAt"]=reader.GetString(3),
                    ["reportId"]=document?.Id,["phase"]=document?.Phase??"assessment",["status"]="completed",["manifestId"]=AssessmentWorkflow.Identity,["baselineId"]=state.BaselineId,
                    ["result"]=new JsonObject{["reportId"]=document?.Id,["actionId"]=document is null?id+"@"+revision.ToString(CultureInfo.InvariantCulture):null,
                        ["artifactSha256"]=workerResult["output"]?["artifact_sha256"]?.DeepClone(),["synthetic"]=true},
                    ["workerInvocation"]=invocation,["workerResult"]=workerResult,["runtimeEvidence"]="development-only-controller-worker-simulation"});
            }
            return result;
        }
    }

    private AssessmentState ReadAssessment(string id,string principal,int? revision=null)
    {
        AssessmentWorkflow.KnownPrincipal(principal);
        if(!Regex.IsMatch(id,"\\Aassessment-[a-f0-9]{32}\\z",RegexOptions.CultureInvariant))throw new DemoValidationException("assessment_not_found");
        using var query=Command("SELECT snapshot_json,snapshot_sha256 FROM assessment_versions WHERE assessment_id=$id"+(revision.HasValue?" AND revision=$revision":"")+" ORDER BY revision DESC LIMIT 1",null,
            revision.HasValue?[("$id",(object)id),("$revision",revision.Value)]:[("$id",(object)id)]);
        using var reader=query.ExecuteReader();if(!reader.Read())throw new DemoValidationException("assessment_not_found");
        var content=reader.GetString(0);if(Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(content)))!=reader.GetString(1))throw new DemoStoreException("assessment_state_integrity_failed");
        var state=AssessmentJson.State(content);_=AssessmentWorkflow.Role(state,principal);return state;
    }
    private JsonObject VersionView(string id,int revision,string principal)
    {
        // Replay returns the original committed response, including its as-of
        // metrics. A separate GET supplies current elapsed-time projections.
        return AssessmentResponseView(ReadAssessment(id,principal,revision),principal);
    }

    private List<AssessmentSource> SourceCatalog() => ReadRows("sourceProfiles").Select(profile=>
    {
        var examples=new List<string>();
        foreach(var key in new[]{"recognition_examples","technology_examples","product_examples","examples"})
            if(profile[key] is JsonArray values)examples.AddRange(values.OfType<JsonValue>().Select(v=>v.TryGetValue<string>(out var text)?text:"").Where(s=>s.Length>0));
        if(examples.Count==0)
        {
            var sourceIds=Strings(profile,"source_instance_refs").ToHashSet(StringComparer.Ordinal);
            examples=ReadRows("observations").Where(o=>sourceIds.Contains(Text(o,"source_instance_id"))).Select(o=>o["facts"] as JsonObject).OfType<JsonObject>()
                .SelectMany(f=>new[]{"product_label","engine_name","package_name","runtime_platform","protocol"}.Select(k=>f[k]?.ToString()??""))
                .Where(s=>s.Length>0).Distinct().Take(5).ToList();
        }
        return new AssessmentSource{Id=Text(profile,"family_id"),FamilyId=Text(profile,"family_id"),Name=Text(profile,"name"),AreaId=Text(profile,"area_ref"),Examples=examples};
    }).OrderBy(s=>s.AreaId,StringComparer.Ordinal).ThenBy(s=>s.FamilyId,StringComparer.Ordinal).ToList();

    private EvidenceSample SampleFor(AssessmentState state,string? familyId)
    {
        var source=state.Sources.SingleOrDefault(s=>s.FamilyId==familyId && state.Scope.IncludedFamilyIds.Contains(s.FamilyId)) ?? throw new DemoValidationException("assessment_source_not_in_scope");
        var profile=ReadRows("sourceProfiles").Single(p=>Text(p,"family_id")==source.FamilyId);
        var instances=Strings(profile,"source_instance_refs").ToHashSet(StringComparer.Ordinal);
        var observations=ReadRows("observations").Where(o=>instances.Contains(Text(o,"source_instance_id"))).ToArray();
        var observationIds=observations.Select(o=>Text(o,"observation_id")).Distinct().Order(StringComparer.Ordinal).ToList();
        var admitted=state.Sources.Where(s=>state.Scope.IncludedFamilyIds.Contains(s.FamilyId)).SelectMany(s=>s.ObservationIds).Concat(observationIds).ToHashSet(StringComparer.Ordinal);
        var observedSubjects=observations.Select(o=>Text(o,"subject_ref")).ToHashSet(StringComparer.Ordinal);
        var subjects=ReadRows("inventory").Where(i=>observedSubjects.Contains(Text(i,"subject_ref")) && Strings(i,"observation_refs").All(admitted.Contains)).Select(i=>Text(i,"subject_ref")).Order(StringComparer.Ordinal).ToList();
        var limitations=ReadRows("limitations").Where(l=>subjects.Contains(Text(l,"subject_ref"))).Select(l=>Text(l,"code")).Distinct().Order(StringComparer.Ordinal).ToList();
        if(subjects.Count<observedSubjects.Count)limitations.Add("unadmitted_source_observations_excluded");
        return new EvidenceSample(source.FamilyId,observationIds,subjects,limitations);
    }

    private void PersistAssessment(AssessmentState state,AssessmentCommand command,string principal,string requestHash,SqliteTransaction transaction)
    {
        var snapshot=JsonSerializer.Serialize(state,AssessmentJson.Options);var hash=Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(snapshot)));
        var id=Guid.NewGuid().ToString("N");var traceId=Convert.ToHexStringLower(RandomNumberGenerator.GetBytes(16));var spanId=Convert.ToHexStringLower(RandomNumberGenerator.GetBytes(8));var traceparent=$"00-{traceId}-{spanId}-01";
        var invocation=new JsonObject{["version"]="v1",["id"]=id,["trace"]=new JsonObject{["trace_id"]=traceId,["span_id"]=spanId,["traceparent"]=traceparent},
            ["pipeline_run_id"]="pipeline-"+id,["pipeline"]=AssessmentWorkflow.Identity,["worker"]=AssessmentWorkflow.Identity,["step"]="evaluate-assessment-command",
            ["tenant"]="synthetic-enterprise",["environment"]="development-synthetic",["domain"]="pqc_migration",["classification"]=new JsonObject{["data_class"]="internal",["data_sensitivity"]="none",["regulatory_scope"]="none"},["sensitivity"]="synthetic",
            ["input"]=new JsonObject{["assessmentId"]=state.Id,["operation"]=command.Operation,["request_sha256"]=requestHash,["expectedRevision"]=command.ExpectedRevision,["synthetic"]=true},
            ["meta"]=new JsonObject{["candidateManifestRef"]=AssessmentWorkflow.Identity,["candidateManifestSha256"]=AssessmentManifestHash("PqcEnterpriseDemo.AssessmentWorkerManifest"),
                ["candidatePipelineRef"]=AssessmentWorkflow.Identity,["candidatePipelineSha256"]=AssessmentManifestHash("PqcEnterpriseDemo.AssessmentPipelineManifest"),
                ["initiatingActor"]=principal,["idempotencyKey"]=command.IdempotencyKey,["scope"]=state.Id,["policyDecisionOrigin"]="development_simulator_not_enterprise_opa",
                ["capabilities"]=new JsonArray("pqc.contract_fixture.probe","artifact.read"),["networkAuthority"]="none",["sourceWriteAuthority"]=false,
                ["humanAcceptanceAuthority"]=false,["controllerOwnsCommit"]=true,["canonicalCatalogDispatch"]=false,["decisionBoundary"]="synthetic_assessment_only_not_owner_acceptance"}};
        var result=new JsonObject{["success"]=true,["retryable"]=false,["status"]="completed",["output"]=new JsonObject{["assessmentId"]=state.Id,["revision"]=state.Revision,["artifact_sha256"]=hash,["synthetic"]=true},["trace"]=new JsonObject{["traceparent"]=traceparent}};
        Execute("INSERT INTO assessment_versions VALUES($id,$revision,$sha,$snapshot)",transaction,("$id",state.Id),("$revision",state.Revision),("$sha",hash),("$snapshot",snapshot));
        foreach(var eventRecord in state.Events.Where(e=>e.Revision>command.ExpectedRevision))
            Execute("INSERT INTO assessment_events VALUES($id,$revision,$event,$sha)",transaction,("$id",state.Id),("$revision",eventRecord.Revision),("$event",JsonSerializer.Serialize(eventRecord,AssessmentJson.Options)),("$sha",AssessmentWorkflow.Hash(eventRecord)));
        Execute("INSERT INTO assessment_commands VALUES($run,$id,$revision,$key,$sha,$actor,$at,$invocation,$result)",transaction,("$run",id),("$id",state.Id),("$revision",state.Revision),("$key",command.IdempotencyKey),("$sha",requestHash),("$actor",principal),("$at",state.UpdatedAt),("$invocation",invocation.ToJsonString()),("$result",result.ToJsonString()));
    }

    private static string AssessmentManifestHash(string name)
    {
        using var stream=typeof(EnterpriseStore).Assembly.GetManifestResourceStream(name) ?? throw new DemoStoreException("candidate_manifest_missing");
        return Convert.ToHexStringLower(SHA256.HashData(stream));
    }
    private static void ValidateAssessmentKey(string key)
    {
        if(!Regex.IsMatch(key,"\\A[A-Za-z0-9._:-]{8,96}\\z",RegexOptions.CultureInvariant))throw new DemoValidationException("invalid_idempotency_key");
    }

    private void SeedWorkedExample(AssessmentState state,string principal)
    {
        // The example is a visible, restartable sequence of the SAME commands;
        // it never records enterprise acceptance or an owner product verdict.
        var families=state.Sources.GroupBy(s=>s.AreaId).Take(3).Select(g=>g.First().FamilyId).ToArray();
        var date=DateOnly.FromDateTime(DateTimeOffset.Parse(state.CreatedAt,CultureInfo.InvariantCulture).UtcDateTime.AddDays(14)).ToString("yyyy-MM-dd",CultureInfo.InvariantCulture);
        void Do(string operation,string? target,JsonObject fields,string actor)
        {
            var key="scenario-"+operation+"-"+(target??"root")+"-"+actor.Split(':')[1];
            var command=new AssessmentCommand(operation,target,fields,state.Revision,key);
            AssessmentWorkflow.Apply(state,command,actor,state.CreatedAt,operation=="admit_sample"?SampleFor(state,target):null,"scenario_generated");
        }
        var excluded=new JsonObject();foreach(var source in state.Sources.Where(s=>!families.Contains(s.FamilyId)))excluded[source.FamilyId]="Outside this bounded worked-example cohort; not an enterprise exclusion.";
        var depths=new JsonObject();foreach(var family in families)depths[family]="inventory";
        Do("update_scope",null,new JsonObject{["objective"]="Worked example: establish an evidence-linked current-state view for three source families.",["handling"]="Synthetic fixture metadata only; no enterprise collection or external delivery.",
            ["method"]="Attribute every conclusion to the fixed sample, retain conflicts and qualify incomplete evidence.",["cycleGoal"]="Produce a reviewable Phase 1 draft with explicit limitations.",["reviewDate"]=date,["includedFamilyIds"]=new JsonArray(families.Select(v=>(JsonNode?)JsonValue.Create(v)).ToArray()),["excludedReasons"]=excluded,["depthByFamily"]=depths},principal);
        JsonObject Decision(string message)=>new(){["decision"]="qualified",["rationale"]=message,["qualification"]="Scenario-generated decision for synthetic learning only, never an enterprise approval.",["reviewDate"]=date};
        Do("submit_gate","PQC-G00",new(),principal);
        Do("decide_gate","PQC-G00",Decision("Sample information-handling route reviewed."),"synthetic-demo:information-owner");
        Do("decide_gate","PQC-G00",Decision("Sample governance boundary reviewed."),"synthetic-demo:sponsor");
        foreach(var family in families)
        {
            var source=state.Sources.Single(s=>s.FamilyId==family);
            Do("source_response",family,new JsonObject{["state"]="route_confirmed",["systemOfRecord"]="Fixed synthetic "+source.Name+" fixture",["product"]=source.Examples.FirstOrDefault()??"Synthetic source profile",
                ["ownerFunction"]="Synthetic "+source.Name+" evidence function",["assertedBy"]="Synthetic source function in the worked example",["accessRoute"]="Bounded, pre-generated fixture; no live interface",["note"]="Scenario route only. Product examples do not establish an enterprise selection.",["dueAt"]=date},"synthetic-demo:contributor");
        }
        Do("submit_gate","PQC-P1-G01",new(),principal);
        Do("decide_gate","PQC-P1-G01",Decision("Sample source register and exclusions reviewed."),principal);
        Do("decide_gate","PQC-P1-G01",Decision("Bounded sample scope reviewed."),"synthetic-demo:sponsor");
        foreach(var family in families)
        {
            Do("admit_sample",family,new(),principal);
            Do("submit_package",family,new JsonObject{["conclusion"]="The admitted source observations establish the bounded sample, not completeness or verified runtime behavior.",["qualification"]="All source limitations remain attached; missing or disputed facts require later investigation."},principal);
            Do("review_package",family,new JsonObject{["decision"]="qualified",["rationale"]="The package preserves attributable observations and limitations.",["qualification"]="Synthetic sample only; every listed limitation remains unresolved for enterprise reliance.",["reviewDate"]=date},"synthetic-demo:reviewer");
        }
        Do("submit_gate","PQC-P1-G02",new(),principal);
        Do("decide_gate","PQC-P1-G02",Decision("Sample baseline prepared with explicit limitations."),principal);
        Do("decide_gate","PQC-P1-G02",Decision("Sample baseline independently reviewed in the worked scenario."),"synthetic-demo:reviewer");
        AssessmentWorkflow.Refresh(state,principal);
    }
}
