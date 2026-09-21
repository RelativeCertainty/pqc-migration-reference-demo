using System.Security.Cryptography;
using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

public interface IDiscoveryEvidenceStore
{
    JsonObject StageDiscoveryEvidence(string id,string investigationId,string productRefId,string sourceLabel,
        int revision,string key,string principal,byte[] original);
}

public sealed partial class EnterpriseStore : IDiscoveryEvidenceStore
{
    public JsonObject StageDiscoveryEvidence(string id,string investigationId,string productRefId,string sourceLabel,
        int revision,string key,string principal,byte[] original)
    {
        // The only qualified parser in this increment is the closed synthetic
        // TLS dialect. Product manuals or questionnaire answers never enter here.
        var records=IntakeTlsEvidence.Parse(original);
        if (string.IsNullOrWhiteSpace(sourceLabel) || sourceLabel.Length>256) throw new DemoValidationException("discovery_source_label_required");
        var hash=Convert.ToHexStringLower(SHA256.HashData(original));
        lock(gate)
        {
            var command=new AssessmentCommand("discovery_stage_evidence",investigationId,
                new JsonObject{["productRefId"]=productRefId,["sourceLabel"]=sourceLabel,["sourceSha256"]=hash},revision,key);
            var state=DiscoveryCommit(id,command,principal,s=>
            {
                if (AssessmentWorkflow.Role(s,principal)!="assessment-lead") throw new DemoValidationException("assessment_forbidden");
                DiscoveryEvidence.RequireGates(s);
                var investigation=s.Discovery.Investigations.Single(i=>i.Id==investigationId);
                var request=s.Discovery.Requests.Single(r=>r.Id==investigation.RequestId);
                if(!s.Scope.IncludedFamilyIds.Contains(request.FamilyId))throw new DemoConflictException("discovery_source_not_in_scope");
                if (request.FamilyId!="traffic-termination") throw new DemoValidationException("discovery_format_not_qualified_for_family");
                if (request.Status!="submitted") throw new DemoConflictException("discovery_submitted_response_required");
                var product=investigation.ProductRefs.SingleOrDefault(p=>p.Id==productRefId)
                    ?? throw new DemoValidationException("discovery_product_binding_invalid");
                if (investigation.EvidenceReviews.Any(b=>b.ContentSha256==hash && b.ProductRefId==productRefId && b.SourceLabel==sourceLabel))
                    throw new DemoConflictException("discovery_duplicate_evidence");
                string Identity(string kind,object value)=>"discovery-"+kind+"-"+AssessmentWorkflow.Hash(value)[..24];
                var sourceId=Identity("source",new{assessmentId=s.Id,investigationId=investigation.Id,sourceLabel});
                var newRoute=investigation.IntakeRequestId is null or "";
                var existingSystems=s.Intake.Systems.Select(x=>x.Id).ToHashSet(StringComparer.Ordinal);
                var newSystems=records.Select(record=>Identity("endpoint",new{assessmentId=s.Id,productRefId,sourceId,nativeId=record.Id}))
                    .Append(sourceId).Distinct(StringComparer.Ordinal).Count(id=>!existingSystems.Contains(id));
                // Discovery shares the legacy intake state. Respect its limits
                // so a new bridge cannot make existing requests unwritable.
                // A recapture consumes batch capacity, not another identity.
                if(s.Intake.Batches.Count+records.Count>128 || s.Intake.Systems.Count+newSystems>80 ||
                    s.Intake.Requests.Count+(newRoute?1:0)>20 || investigation.EvidenceReviews.Count>=12)
                    throw new DemoConflictException("discovery_evidence_capacity_limit");
                var now=DateTimeOffset.UtcNow.ToString("O");
                if(newRoute)
                {
                    investigation.IntakeRequestId=Identity("evidence-route",new{assessmentId=s.Id,investigationId=investigation.Id});
                    s.Intake.Requests.Add(new IntakeRequest{Id=investigation.IntakeRequestId,Title="Engineering evidence: "+request.Title,
                        FamilyId=request.FamilyId,AssignedTo=principal,Status="responding",Examples=[..request.Examples],
                        RecordedBy=principal,AssertedBy="Synthetic engineering fixture",Limitation="No enterprise collection or independent runtime verification."});
                }
                var route=s.Intake.Requests.Single(r=>r.Id==investigation.IntakeRequestId);
                if(!s.Intake.Systems.Any(x=>x.Id==sourceId))
                {
                    s.Intake.Systems.Add(new IntakeSystem{Id=sourceId,RequestId=route.Id,Label=sourceLabel,SystemRole="source"});
                    route.SystemIds.Add(sourceId);
                }
                var bundle=new DiscoveryEvidenceReview{BatchId=Identity("bundle",new{assessmentId=s.Id,investigationId=investigation.Id,productRefId,sourceId,hash}),
                    ProductRefId=productRefId,ProductLabel=product.Label,SourceLabel=sourceLabel,ObservationCount=records.Count,
                    ContentSha256=hash,StagedBy=principal,StagedAt=now};
                foreach(var record in records)
                {
                    // A product/deployment is not a TLS endpoint. Keep native
                    // record identities in the evidence source's namespace.
                    var subjectId=Identity("endpoint",new{assessmentId=s.Id,productRefId,sourceId,nativeId=record.Id});
                    if(!s.Intake.Systems.Any(x=>x.Id==subjectId))
                    {
                        s.Intake.Systems.Add(new IntakeSystem{Id=subjectId,RequestId=route.Id,Label=product.Label+" · "+record.Hostname,
                            Product=product.Product,Environment=product.Environment,SystemRole="subject"});
                        route.SystemIds.Add(subjectId);
                    }
                    var batchId=Identity("record",new{bundle.BatchId,record.Id});
                    var observationId=Identity("observation",new{subjectId,sourceId,record.Id,hash});
                    s.Intake.Batches.Add(new IntakeBatch{Id=batchId,RequestId=route.Id,SystemId=subjectId,SourceSystemId=sourceId,
                        ContentSha256=hash,OriginalBase64=Convert.ToBase64String(original),ReceivedAt=now,
                        Observations=[new IntakeObservation(observationId,subjectId,sourceId,record.Id,record.Hostname,record.KeyExchange,record.Authentication,record.Basis,hash)]});
                    bundle.BatchIds.Add(batchId);
                }
                investigation.EvidenceReviews.Add(bundle);
            });
            return AssessmentJson.Object(new{assessmentId=id,revision=state.Revision,
                investigation=state.Discovery.Investigations.Single(i=>i.Id==investigationId),
                effect="Synthetic evidence staged for independent factual review. Map and report inputs are unchanged until qualified evidence is admitted."});
        }
    }
}
