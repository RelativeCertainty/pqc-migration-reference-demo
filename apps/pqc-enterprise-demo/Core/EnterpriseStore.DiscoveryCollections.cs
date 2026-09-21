using System.IO.Compression;
using System.Security.Cryptography;
using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

public sealed partial class EnterpriseStore
{
    private const string CollectionBoundary="All 27 software-class forms, grouped into ten PQC Discovery Domains. Five core questions per form; not 135 different questions or a requirement to answer every class. New collections create synthetic draft assignments only: no email, source access, evidence admission, policy adoption or assessment acceptance.";
    public JsonObject DiscoveryCatalog(string id,string principal)
    {lock(gate){EnsureOpen();return DiscoveryCatalogView(ReadAssessment(id,principal),principal);}}

    private static bool CollectionVisible(AssessmentState s,DiscoveryCollection c,string p)=>DiscoveryWorkflow.Coordinate(s,p)||c.AssignedTo==p;
    private static JsonObject AssessmentResponseView(AssessmentState s,string p)
    {
        var response=AssessmentJson.Object(s);
        var privateCollections=s.Discovery.Collections.Where(c=>!CollectionVisible(s,c,p)).ToArray();
        if(privateCollections.Length==0)return response;
        var privateIds=privateCollections.Select(c=>c.Id).ToHashSet(StringComparer.Ordinal);
        var privateExports=privateCollections.SelectMany(c=>c.Packages).SelectMany(package=>package.Entries).Select(e=>e.ExportId).ToHashSet(StringComparer.Ordinal);
        // Project only the returned copy. Never strip persisted snapshots, reports,
        // attribution or the assessment reviewer's ordinary question read access.
        var discovery=(JsonObject)response["discovery"]!;
        discovery["collections"]=new JsonArray(s.Discovery.Collections.Where(c=>!privateIds.Contains(c.Id)).Select(c=>(JsonNode)AssessmentJson.Object(c)).ToArray());
        ((JsonObject)discovery["exchange"]!)["exports"]=new JsonArray(s.Discovery.Exchange.Exports.Where(e=>!privateExports.Contains(e.Id)).Select(e=>(JsonNode)AssessmentJson.Object(e)).ToArray());
        ((JsonObject)discovery["exchange"]!)["imports"]=new JsonArray(s.Discovery.Exchange.Imports.Where(i=>!privateExports.Contains(i.ExportId)).Select(i=>(JsonNode)AssessmentJson.Object(i)).ToArray());
        return response;
    }
    private static DiscoveryCollection Collection(AssessmentState s,string id,string p)
    {
        var c=s.Discovery.Collections.SingleOrDefault(c=>c.Id==id)??throw new DemoValidationException("discovery_collection_not_found");
        if(!CollectionVisible(s,c,p))throw new DemoValidationException("assessment_forbidden");
        if(c.RequestIds.Count!=27||c.RequestIds.Distinct(StringComparer.Ordinal).Count()!=27)throw new DemoStoreException("discovery_collection_integrity_failed");
        foreach(var requestId in c.RequestIds)
            if(DiscoveryWorkflow.Request(s,requestId,p).AssignedTo!=c.AssignedTo)throw new DemoConflictException("discovery_collection_stale");
        if(!c.RequestIds.Select(rid=>s.Discovery.Requests.Single(r=>r.Id==rid).FamilyId).Order(StringComparer.Ordinal)
            .SequenceEqual(DiscoveryRecognition.Domains.SelectMany(d=>d.Families).Select(f=>f.Id).Order(StringComparer.Ordinal)))throw new DemoStoreException("discovery_collection_integrity_failed");
        return c;
    }
    private static JsonObject DiscoveryCatalogView(AssessmentState s,string p)
    {
        _=AssessmentWorkflow.Role(s,p);
        if(IntakeWorkflow.Contributor(p)&&!s.Discovery.Requests.Any(r=>r.AssignedTo==p))throw new DemoValidationException("assessment_forbidden");
        var lead=DiscoveryWorkflow.Coordinate(s,p);
        return AssessmentJson.Object(new{
            assessmentId=s.Id,assessmentName=s.Name,revision=s.Revision,canPrepare=lead,
            templateVersion=DiscoveryWorkflow.TemplateVersion,domainCount=10,formCount=27,questionsPerForm=5,boundary=CollectionBoundary,
            recipients=lead?s.Assignments.Where(a=>IntakeWorkflow.Contributor(a.PrincipalId)).Select(a=>new{id=a.PrincipalId,label=a.PrincipalId=="synthetic-demo:contributor"?"Source contributor 1":"Source contributor 2"}).ToArray():[],
            domains=DiscoveryRecognition.Domains.Select(d=>new{d.Id,d.Name,forms=d.Families.Select(f=>new{
                familyId=f.Id,familyName=f.Name,questions=DiscoveryWorkflow.Questions(s.Sources.Single(source=>source.FamilyId==f.Id).Examples),examples=f.Examples
            }).ToArray()}).ToArray(),
            collections=s.Discovery.Collections.Where(c=>CollectionVisible(s,c,p)).Select(c=>{
                _=Collection(s,c.Id,p);
                return new{c.Id,c.AssignedTo,c.CreatedAt,
                    requests=c.RequestIds.Select(rid=>{var r=s.Discovery.Requests.Single(r=>r.Id==rid);return new{r.FamilyId,requestId=r.Id,r.Status};}).ToArray(),
                    packages=c.Packages.Select(package=>new{package.Id,package.CreatedAt,
                        zipUrl=$"/api/assessments/{s.Id}/discovery/collections/{c.Id}/exports/{package.Id}/download",
                        indexUrl=$"/api/assessments/{s.Id}/discovery/collections/{c.Id}/exports/{package.Id}/index",
                        forms=package.Entries.Select(e=>new{e.FamilyId,e.RequestId,e.Filename,e.Sha256,downloadUrl=$"/api/assessments/{s.Id}/discovery/exports/{e.ExportId}/download"}).ToArray()
                    }).ToArray()};
            }).ToArray()
        });
    }
    public JsonObject CreateDiscoveryCollection(string id,string assignedTo,int revision,string key,string p)
    {
        lock(gate)
        {
            var state=DiscoveryCommit(id,new("discovery_collection_create",null,new(){["assignedTo"]=assignedTo},revision,key),p,s=>{
                if(!IntakeWorkflow.Contributor(assignedTo)||!s.Assignments.Any(a=>a.PrincipalId==assignedTo))throw new DemoValidationException("discovery_recipient_invalid");
                if(s.Discovery.Collections.Any(c=>c.AssignedTo==assignedTo))throw new DemoConflictException("discovery_collection_already_exists");
                if(s.Discovery.Requests.Count+27>100)throw new DemoConflictException("discovery_request_limit");
                var collection=new DiscoveryCollection{Id="dcollection-"+Guid.NewGuid().ToString("N"),AssignedTo=assignedTo,CreatedAt=DateTimeOffset.UtcNow.ToString("O")};
                foreach(var family in DiscoveryRecognition.Domains.SelectMany(d=>d.Families))
                {
                    DiscoveryWorkflow.Apply(s,new("discovery_create",null,new(){["title"]=family.Name+" — five-question discovery",["familyId"]=family.Id,["assignedTo"]=assignedTo},revision,key+":"+family.Id),p);
                    collection.RequestIds.Add(s.Discovery.Requests[^1].Id);
                }
                s.Discovery.Collections.Add(collection);
            });
            return DiscoveryCatalogView(state,p);
        }
    }
    public JsonObject ExportDiscoveryCollection(string id,string collectionId,int revision,string key,string p)
    {
        lock(gate)
        {
            var state=DiscoveryCommit(id,new("discovery_collection_export",collectionId,new(),revision,key),p,s=>{
                var collection=Collection(s,collectionId,p);
                if(collection.Packages.Count>=3)throw new DemoConflictException("discovery_collection_package_limit");
                if(s.Discovery.Exchange.Exports.Count+27>108||collection.RequestIds.Any(rid=>s.Discovery.Exchange.Exports.Count(e=>e.RequestId==rid)>=4))throw new DemoConflictException("discovery_export_limit");
                var package=new DiscoveryCollectionPackage{Id="dpackage-"+Guid.NewGuid().ToString("N"),CreatedAt=DateTimeOffset.UtcNow.ToString("O")};
                var requests=collection.RequestIds.Select(rid=>DiscoveryWorkflow.Request(s,rid,p)).ToArray();
                foreach(var domain in DiscoveryRecognition.Domains)
                foreach(var family in domain.Families)
                {
                    var request=requests.Single(r=>r.FamilyId==family.Id);var baseline=DiscoveryBaseline(request);var exportId="dexport-"+Guid.NewGuid().ToString("N");
                    var bytes=DiscoveryWorkbook.Write(exportId,id,request.Id,request.FamilyId,request.FamilyName,request.TemplateVersion,request.TemplateSha256,request.Questions,baseline);
                    var sha=Convert.ToHexStringLower(SHA256.HashData(bytes));
                    s.Discovery.Exchange.Exports.Add(new(){Id=exportId,RequestId=request.Id,AssignedTo=request.AssignedTo,TemplateSha256=request.TemplateSha256,Baseline=baseline,BytesBase64=Convert.ToBase64String(bytes),Sha256=sha});
                    package.Entries.Add(new(family.Id,request.Id,exportId,$"{domain.Id}/{family.Id}.xlsx",sha));
                }
                var index=DiscoveryCollectionWorkbook.Write(id,collection.Id,package.Id,collection.AssignedTo,requests,package.Entries);
                package.IndexBytesBase64=Convert.ToBase64String(index);package.IndexSha256=Convert.ToHexStringLower(SHA256.HashData(index));
                var files=package.Entries.Select(e=>(e.Filename,Convert.FromBase64String(s.Discovery.Exchange.Exports.Single(x=>x.Id==e.ExportId).BytesBase64))).ToList();
                files.Add(("00_Consolidated_Questions.xlsx",index));var zip=CollectionZip(files);
                package.ZipBytesBase64=Convert.ToBase64String(zip);package.ZipSha256=Convert.ToHexStringLower(SHA256.HashData(zip));
                collection.Packages.Add(package);
            });
            return DiscoveryCatalogView(state,p);
        }
    }
    public byte[] DownloadDiscoveryCollection(string id,string collectionId,string packageId,string p,bool indexOnly=false)
    {
        lock(gate)
        {
            EnsureOpen();var state=ReadAssessment(id,p);var collection=Collection(state,collectionId,p);
            var package=collection.Packages.SingleOrDefault(e=>e.Id==packageId)??throw new DemoValidationException("discovery_collection_package_not_found");
            var index=Convert.FromBase64String(package.IndexBytesBase64);
            if(Convert.ToHexStringLower(SHA256.HashData(index))!=package.IndexSha256||package.Entries.Count!=27||package.Entries.Select(e=>e.RequestId).Distinct().Count()!=27)throw new DemoStoreException("discovery_collection_integrity_failed");
            if(package.Entries.Select(e=>e.FamilyId).Distinct(StringComparer.Ordinal).Count()!=27)throw new DemoStoreException("discovery_collection_integrity_failed");
            foreach(var entry in package.Entries)
            {
                var domain=DiscoveryRecognition.ForFamily(entry.FamilyId)?.Domain??throw new DemoStoreException("discovery_collection_integrity_failed");
                var export=state.Discovery.Exchange.Exports.SingleOrDefault(e=>e.Id==entry.ExportId)??throw new DemoStoreException("discovery_collection_integrity_failed");
                if(!collection.RequestIds.Contains(entry.RequestId)||state.Discovery.Requests.Single(r=>r.Id==entry.RequestId).FamilyId!=entry.FamilyId||export.RequestId!=entry.RequestId||export.Sha256!=entry.Sha256||entry.Filename!=$"{domain.Id}/{entry.FamilyId}.xlsx")throw new DemoStoreException("discovery_collection_integrity_failed");
                _=DiscoveryExportBytes(state,entry.ExportId,p);
            }
            if(indexOnly)return index;
            var bytes=Convert.FromBase64String(package.ZipBytesBase64);
            if(Convert.ToHexStringLower(SHA256.HashData(bytes))!=package.ZipSha256)throw new DemoStoreException("discovery_collection_integrity_failed");
            return bytes;
        }
    }
    private static byte[] CollectionZip(IEnumerable<(string Name,byte[] Bytes)> files)
    {
        using var output=new MemoryStream();
        using(var zip=new ZipArchive(output,ZipArchiveMode.Create,true))
            foreach(var file in files.OrderBy(f=>f.Name,StringComparer.Ordinal))
            {
                var entry=zip.CreateEntry(file.Name,CompressionLevel.Optimal);entry.LastWriteTime=new DateTimeOffset(1980,1,1,0,0,0,TimeSpan.Zero);
                using var stream=entry.Open();stream.Write(file.Bytes);
            }
        return output.ToArray();
    }
}
