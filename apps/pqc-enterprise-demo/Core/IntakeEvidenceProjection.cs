using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

/// <summary>One assessment's admitted intake evidence joins its investigation
/// projection. Staged files and questionnaire testimony never become observations.</summary>
public static class IntakeEvidenceProjection
{
    public static void Merge(AssessmentState state,JsonObject projection)
    {
        var requests=state.Intake.Requests.Where(r=>state.Scope.IncludedFamilyIds.Contains(r.FamilyId)).ToDictionary(r=>r.Id);
        var batches=state.Intake.Batches.Where(b=>b.Status=="admitted" && requests.ContainsKey(b.RequestId)).ToArray();
        if(batches.Length==0)return;
        var observationRows=projection["observations"]!.AsArray();var inventory=projection["inventory"]!.AsArray();
        foreach(var group in batches.GroupBy(b=>b.SystemId))
        {
            var system=state.Intake.Systems.Single(s=>s.Id==group.Key);
            var observations=group.SelectMany(b=>b.Observations).DistinctBy(o=>o.Id).ToArray();
            var conflict=observations.GroupBy(o=>new{o.SourceSystemId,o.NativeId}).Any(g=>g.Select(o=>new{o.Hostname,o.KeyExchange,o.Authentication}).Distinct().Count()>1);
            foreach(var batch in group)
            {
                var profile=projection["sourceProfiles"]!.AsArray().OfType<JsonObject>().Single(p=>p["family_id"]?.GetValue<string>()==requests[batch.RequestId].FamilyId);
                if(profile["source_instance_refs"] is not JsonArray sources)profile["source_instance_refs"]=sources=new();
                if(!sources.Any(s=>s?.GetValue<string>()==batch.SourceSystemId))sources.Add(batch.SourceSystemId);
                foreach(var o in batch.Observations)
                {
                    if(observationRows.OfType<JsonObject>().Any(r=>r["observation_id"]?.GetValue<string>()==o.Id))continue;
                    observationRows.Add(new JsonObject{["observation_id"]=o.Id,["subject_ref"]=o.SystemId,["source_instance_id"]=o.SourceSystemId,["subject_kind"]="tls_endpoint",
                        ["evidence_basis"]=o.Basis,["observed_at"]=null,["received_at"]=batch.ReceivedAt,["evidence_ref"]="intake-custody:"+batch.Id,["evidence_sha256"]=o.ContentSha256,
                        ["facts"]=new JsonObject{["hostname"]=o.Hostname,["key_exchange_group"]=o.KeyExchange,["certificate_signature_algorithm"]=o.Authentication,["independently_verified"]=false},
                        ["normalizer_version"]="pqc.intake.tls-binding.v1",["native_record_id"]=o.NativeId,["relationship_status"]="application_and_certificate_targets_unresolved"});
                }
            }
            if(!inventory.OfType<JsonObject>().Any(r=>r["subject_ref"]?.GetValue<string>()==system.Id))
                inventory.Add(new JsonObject{["subject_ref"]=system.Id,["subject_kind"]="tls_endpoint",["display_names"]=new JsonArray(system.Label),
                    ["source_instance_refs"]=new JsonArray(observations.Select(o=>o.SourceSystemId).Distinct().Select(s=>(JsonNode?)JsonValue.Create(s)).ToArray()),
                    ["observation_refs"]=new JsonArray(observations.Select(o=>(JsonNode?)JsonValue.Create(o.Id)).ToArray()),
                    ["conflict_status"]=conflict?"conflicting_observations":"no_conflict_in_snapshot",["synthetic"]=true});
            var limitations=projection["limitations"]!.AsArray();
            if(!limitations.OfType<JsonObject>().Any(l=>l["subject_ref"]?.GetValue<string>()==system.Id && l["code"]?.GetValue<string>()=="intake_unverified_reference"))
                limitations.Add(new JsonObject{["subject_ref"]=system.Id,["code"]="intake_unverified_reference",["description"]="Source-supplied basis; observation time, enterprise population, application/certificate relationship bindings and independent runtime verification remain unestablished."});
        }
        projection["baseline"]!["assetCount"]=inventory.Count;
    }
}
