using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace PqcEnterpriseDemo;

/// <summary>Closed synthetic source normalizer and pure admitted-evidence projection.
/// No network, executable expressions, inferred enterprise facts or source mutation.</summary>
public static class WorkspaceEvidenceProjection
{
    public const string Version = "pqc.workspace.source-normalizer.v1";
    public static JsonObject Parse(byte[] bytes)
    {
        if(bytes.Length is <2 or >32768)throw new DemoValidationException("workspace_evidence_limit");
        try
        {
            using var document=JsonDocument.Parse(bytes,new JsonDocumentOptions{MaxDepth=10});
            var root=document.RootElement;
            if(root.TryGetProperty("schemaVersion",out var schema)&&schema.GetString()==WorkspaceRegisteredSource.Schema)
                return WorkspaceRegisteredSource.Parse(bytes,root);
            Closed(root,["schemaVersion","synthetic","kind","familyId","sourceInstanceId","sourceLabel","collectedAt","records"]);
            if(root.GetProperty("schemaVersion").GetString()!="pqc.response-to-report.reference.v1"||root.GetProperty("synthetic").ValueKind!=JsonValueKind.True)Invalid();
            var kind=Text(root,"kind",32);if(kind is not("context" or "certificate" or "tls"))Invalid();
            var family=Text(root,"familyId",80);var source=Identifier(root,"sourceInstanceId");
            // These are three closed development source contracts, not generic
            // evidence support for every catalog family or a vendor API claim.
            if(family!=(kind switch{"context"=>"cmdb","certificate"=>"certificate-lifecycle",_=>"traffic-termination"}))Invalid();
            var collection=Date(root,"collectedAt");var rows=root.GetProperty("records");
            if(rows.ValueKind!=JsonValueKind.Array||rows.GetArrayLength() is <1 or >32)Invalid();
            var result=new JsonArray();var ids=new HashSet<string>(StringComparer.Ordinal);
            foreach(var row in rows.EnumerateArray())
            {
                var fields=kind switch{
                    "context"=>new[]{"nativeId","name","serviceId","owner","environment","basis","sourceUpdatedAt"},
                    "certificate"=>["nativeId","applicationId","signatureAlgorithm","publicKeyAlgorithm","publicKeyBits","basis","sourceUpdatedAt"],
                    _=>["nativeId","deployment","hostname","applicationId","certificateId","basis","keyExchange","authentication","sourceUpdatedAt"]};
                Closed(row,fields);var id=Identifier(row,"nativeId");if(!ids.Add(id))Invalid();
                var basis=Text(row,"basis",32);if(basis is not("testimony" or "documentation" or "configured" or "observed" or "independent_verification"))Invalid();
                var observed=Date(row,"sourceUpdatedAt");
                if(DateTimeOffset.Parse(observed,CultureInfo.InvariantCulture)>DateTimeOffset.Parse(collection,CultureInfo.InvariantCulture))Invalid();
                var normalized=new JsonObject{["nativeId"]=id,["familyId"]=family,["basis"]=basis,["observedAt"]=observed,["kind"]=kind,["normalizerVersion"]=Version,["synthetic"]=true};
                foreach(var name in fields.Where(n=>n is not("nativeId" or "basis" or "sourceUpdatedAt")))
                {
                    if(name=="publicKeyBits")
                    {
                        if(!row.GetProperty(name).TryGetInt32(out var bits)||bits is <1 or >65536)Invalid();
                        normalized[name]=bits;
                    }
                    else normalized[name]=Text(row,name,name is "name" or "owner"?256:253);
                }
                if(kind=="tls"&&!Regex.IsMatch(S(normalized,"hostname"),"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\\.(?:example|test|invalid)$",RegexOptions.CultureInvariant,TimeSpan.FromMilliseconds(100)))Invalid();
                normalized["supports"]=kind=="context"?"Attributed application and service context; ownership remains reported until confirmed.":basis=="configured"?"A recorded configuration, not a negotiated connection.":basis=="observed"?"A modeled runtime observation for this endpoint and time; not independent enterprise verification.":"The fields in this synthetic source record, with the stated evidence basis.";
                normalized["cannotEstablish"]="Enterprise completeness, whole-application PQC readiness, permission to change a system, business impact or information lifetime.";
                result.Add(normalized);
            }
            return new JsonObject{["kind"]=kind,["sourceId"]=source,["sourceLabel"]=Text(root,"sourceLabel",256),["familyId"]=family,["collectedAt"]=collection,["observations"]=result};
        }
        catch(Exception e) when(e is JsonException or InvalidOperationException or KeyNotFoundException or FormatException or ArgumentException)
        {throw new DemoValidationException("workspace_synthetic_source_invalid");}
    }

    public static void MergeEvidence(JsonObject workspace,JsonObject projection)
    {
        WorkspaceRegisteredProjection.Merge(workspace,projection);
        var bundles=Rows(workspace,"bundles").Where(b=>S(b,"status")=="admitted"&&S(b,"kind")!="registered"&&b["legacy"]?.GetValue<bool>()!=true).ToArray();
        var all=bundles.SelectMany(b=>Rows(b,"observations").Select(o=>(bundle:b,record:o))).ToArray();
        if(all.Length==0)return;
        var observations=Array(projection,"observations");var inventory=Array(projection,"inventory");
        var uses=Array(projection,"riskReviews");var limits=Array(projection,"limitations");var dependencies=Array(projection,"dependencies");
        foreach(var group in all.GroupBy(x=>S(x.record,"systemId"),StringComparer.Ordinal))
        {
            var entries=group.DistinctBy(x=>S(x.record,"id")).ToArray();var first=entries[0];var kind=S(first.record,"kind");
            var type=kind=="context"?"application":kind=="certificate"?"certificate":"tls_endpoint";
            var facts=entries.Select(x=>Facts(x.record,x.bundle)).ToArray();
            var material=kind=="tls"?new[]{"hostname","key_exchange_group","certificate_signature_algorithm"}:kind=="certificate"?new[]{"signature_algorithm","public_key_algorithm","public_key_bits"}:new[]{"owner_ref","business_service_ref","environment"};
            var conflicts=material.Where(field=>facts.Select(f=>f[field]?.ToJsonString()??"null").Distinct(StringComparer.Ordinal).Count()>1).ToArray();
            foreach(var (bundle,record) in entries)
            {
                var fact=Facts(record,bundle);
                // Native references are linked only within an expressly reviewed canonical
                // deployment. An ambiguous or absent target remains an unresolved reference.
                var canonical=S(record,"canonicalId");
                foreach(var relation in new[]{(field:"applicationId",targetKind:"context",fact:"application_ref"),(field:"certificateId",targetKind:"certificate",fact:"certificate_ref")})
                {
                    var native=S(record,relation.field);
                    if(native.Length==0)continue;
                    var matches=canonical.Length==0||native.Length==0?[]:all.Where(x=>S(x.record,"canonicalId")==canonical&&S(x.record,"kind")==relation.targetKind&&S(x.record,"nativeId")==native).Select(x=>S(x.record,"systemId")).Distinct().ToArray();
                    if(matches.Length!=1)
                    {
                        fact[relation.fact+"_status"]=matches.Length==0?"unresolved_reference":"ambiguous_reference";
                        var code=matches.Length==0?"missing_relationship":"unresolved_dependency";
                        if(!limits.OfType<JsonObject>().Any(l=>S(l,"subject_ref")==group.Key&&S(l,"code")==code))
                            limits.Add(new JsonObject{["subject_ref"]=group.Key,["code"]=code,["description"]="Native application/certificate references remain unresolved or ambiguous within the reviewed deployment. The original native identifiers are retained; no canonical relationship was inferred."});
                        continue;
                    }
                    fact[relation.fact+"_status"]="resolved_within_reviewed_deployment";
                    fact[relation.fact]=matches[0];
                    var edgeId="workspace-edge-"+AssessmentWorkflow.Hash(new{from=group.Key,to=matches[0],relation.fact})[..24];
                    AddUnique(dependencies,"edge_id",new JsonObject{["edge_id"]=edgeId,["from_ref"]=group.Key,["to_ref"]=matches[0],["relationship"]=relation.fact,["evidence_basis"]="source_native_reference_with_reviewed_deployment_binding",["observation_refs"]=Strings([S(record,"id")])});
                }
                var normalized=new JsonObject{["observation_id"]=S(record,"id"),["subject_ref"]=group.Key,["source_instance_id"]=S(record,"sourceSystemId"),["subject_kind"]=type,["fact_type"]=type,
                    ["evidence_basis"]=S(record,"basis"),["observed_at"]=S(record,"observedAt"),["received_at"]=S(record,"collectedAt"),["evidence_ref"]="workspace-custody:"+S(record,"bundleId"),["evidence_sha256"]=S(record,"artifactSha256"),
                    ["native_record_id"]=S(record,"nativeId"),["facts"]=fact,["normalizer_version"]=Version,["relationship_status"]=canonical.Length==0?"unresolved_deployment":"reviewed_deployment_binding"};
                AddUnique(observations,"observation_id",normalized);
                var profile=Rows(projection,"sourceProfiles").SingleOrDefault(p=>S(p,"family_id")==S(record,"familyId"));
                if(profile is not null)
                {
                    var sources=Array(profile,"source_instance_refs");if(!sources.Any(n=>n?.GetValue<string>()==S(record,"sourceSystemId")))sources.Add(S(record,"sourceSystemId"));
                }
            }
            AddUnique(inventory,"subject_ref",new JsonObject{["subject_ref"]=group.Key,["subject_kind"]=type,["fact_types"]=Strings([type]),
                ["display_names"]=Strings([kind=="context"?S(first.record,"name"):S(first.bundle,"productLabel")+" / "+(S(first.record,"hostname").Length>0?S(first.record,"hostname"):S(first.record,"nativeId"))]),
                ["source_instance_refs"]=Strings(entries.Select(x=>S(x.record,"sourceSystemId")).Distinct()),["observation_refs"]=Strings(entries.Select(x=>S(x.record,"id"))),["conflict_status"]=conflicts.Length>0?"conflicting_observations":"no_conflict_in_snapshot",["synthetic"]=true});
            limits.Add(new JsonObject{["subject_ref"]=group.Key,["code"]="workspace_synthetic_basis",["description"]="Modeled source facts; independent enterprise verification, complete population and business lifetime remain unestablished."});
            if(conflicts.Length>0)limits.Add(new JsonObject{["subject_ref"]=group.Key,["code"]="conflicting_observations",["description"]="Unresolved source variants: "+string.Join(", ",conflicts)+". Configuration cannot override modeled runtime observations."});
            if(kind is "tls" or "certificate")
            {
                if(kind=="tls")AddUse("key_establishment","transport_key_exchange","keyExchange");
                AddUse("authentication","certificate_signature",kind=="tls"?"authentication":"signatureAlgorithm");
                void AddUse(string purpose,string role,string field)
                {
                    var variants=entries.Select(x=>S(x.record,field)).Distinct(StringComparer.Ordinal).Order(StringComparer.Ordinal).ToArray();
                    var postures=variants.Select(a=>Posture(a,purpose)).Distinct().ToArray();
                    AddUnique(uses,"use_id",new JsonObject{["use_id"]="workspace-use-"+AssessmentWorkflow.Hash(new{subject=group.Key,role})[..24],["subject_ref"]=group.Key,["purpose"]=purpose,["role"]=role,["algorithm_variants"]=Strings(variants),["algorithm_posture"]=postures.Length==1?postures[0]:"unknown",
                        ["evidence_bases"]=Strings(entries.Select(x=>S(x.record,"basis")).Distinct()),["observation_refs"]=Strings(entries.Select(x=>S(x.record,"id"))),["confidentiality_days_remaining"]=null,["trust_days_remaining"]=null,["limitation_codes"]=Strings(conflicts.Length>0?["conflicting_observations","missing_business_context"]:["missing_business_context"]),["assessment_status"]="illustrative_review_candidate",["method_version"]=Version,["independently_verified"]=false});
                }
            }
        }
        if(projection["baseline"] is JsonObject baseline)baseline["assetCount"]=inventory.Count;
    }
    private static JsonObject Facts(JsonObject record,JsonObject bundle)
    {
        var kind=S(record,"kind");var facts=new JsonObject{["product_label"]=kind=="tls"?S(bundle,"product"):kind=="context"?"Application context":"Certificate metadata",["environment"]=S(bundle,"environment"),["independently_verified"]=false,["synthetic"]=true};
        if(kind=="context") {facts["owner_ref"]=S(record,"owner");facts["business_service_ref"]=S(record,"serviceId");facts["environment"]=S(record,"environment");facts["name"]=S(record,"name");facts["context_basis"]="source_reported_not_confirmed_accountability";}
        if(kind=="tls") {facts["hostname"]=S(record,"hostname");facts["key_exchange_group"]=S(record,"keyExchange");facts["certificate_signature_algorithm"]=S(record,"authentication");}
        if(kind=="certificate") {facts["signature_algorithm"]=S(record,"signatureAlgorithm");facts["public_key_algorithm"]=S(record,"publicKeyAlgorithm");facts["public_key_bits"]=record["publicKeyBits"]?.DeepClone();}
        if(S(record,"applicationId").Length>0)facts["native_application_id"]=S(record,"applicationId");
        if(S(record,"certificateId").Length>0)facts["native_certificate_id"]=S(record,"certificateId");
        return facts;
    }
    private static string Posture(string algorithm,string purpose)=>algorithm.ToUpperInvariant() switch
    {
        "X25519MLKEM768" or "SECP256R1MLKEM768" or "SECP384R1MLKEM1024" when purpose=="key_establishment"=>"hybrid_key_exchange_recorded",
        "X25519" or "X448" or "P-256" or "P-384" or "SECP256R1" or "ECDSA-WITH-SHA256" or "ECDSA-WITH-SHA384" or "SHA256WITHRSAENCRYPTION" or "RSA" or "ED25519"=>"classical_method_review_candidate",
        "ML-DSA-44" or "ML-DSA-65" or "ML-DSA-87" when purpose=="authentication"=>"pqc_signature_mechanism_recorded",_=>"unknown"
    };
    private static void AddUnique(JsonArray array,string key,JsonObject row){var old=array.OfType<JsonObject>().SingleOrDefault(o=>S(o,key)==S(row,key));if(old is null)array.Add(row);else array[array.IndexOf(old)]=row;}
    private static JsonArray Array(JsonObject parent,string key){if(parent[key] is JsonArray value)return value;var result=new JsonArray();parent[key]=result;return result;}
    private static JsonArray Strings(IEnumerable<string> values)=>new(values.Select(v=>(JsonNode?)JsonValue.Create(v)).ToArray());
    private static IEnumerable<JsonObject> Rows(JsonObject o,string key)=>(o[key] as JsonArray)?.OfType<JsonObject>()??[];
    private static string S(JsonObject o,string key)=>o[key]?.GetValue<string>()??"";
    private static string Identifier(JsonElement row,string name){var s=Text(row,name,128);if(!Regex.IsMatch(s,"^[A-Za-z0-9][A-Za-z0-9_.:-]*$",RegexOptions.CultureInvariant,TimeSpan.FromMilliseconds(100)))Invalid();return s;}
    private static string Date(JsonElement row,string name)
    {
        var s=Text(row,name,64);
        if(!Regex.IsMatch(s,@"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,7})?(Z|[+-][0-9]{2}:[0-9]{2})$",RegexOptions.CultureInvariant,TimeSpan.FromMilliseconds(100))||
            !DateTimeOffset.TryParse(s,CultureInfo.InvariantCulture,DateTimeStyles.RoundtripKind,out _))Invalid();
        return s;
    }
    private static string Text(JsonElement row,string name,int maximum){var s=row.GetProperty(name).GetString();if(string.IsNullOrWhiteSpace(s)||s.Length>maximum||s.Any(char.IsControl))Invalid();return s!;}
    private static void Closed(JsonElement row,string[] allowed){if(row.ValueKind!=JsonValueKind.Object)Invalid();var seen=new HashSet<string>();foreach(var p in row.EnumerateObject())if(!allowed.Contains(p.Name)||!seen.Add(p.Name))Invalid();if(seen.Count!=allowed.Length)Invalid();}
    private static void Invalid()=>throw new DemoValidationException("workspace_synthetic_source_invalid");
}
