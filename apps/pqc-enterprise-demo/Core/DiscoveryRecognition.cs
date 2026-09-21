using System.Text.Json;

namespace PqcEnterpriseDemo;

public sealed record RecognitionExample(string Name,string Kind,string Url,string? Note);
public sealed record RecognitionFamily(string Id,string Name,List<RecognitionExample> Examples);
public sealed record RecognitionDomain(string Id,string Name,List<RecognitionFamily> Families);
public sealed record RecognitionDocument(List<RecognitionDomain> Domains);
public sealed record DiscoveryRecognitionView(string CatalogVersion,string CatalogSha256,string ReviewedAt,
    string Boundary,string FamilyId,RecognitionDomain Domain,IReadOnlyList<RecognitionDomain> Domains);

/// <summary>Public recognition guidance, never evidence of installed software or adapter capability.</summary>
public static class DiscoveryRecognition
{
    public const string Version="pqc.software-recognition.v1";
    public const string ReviewedAt="2026-09-10";
    public const string Boundary="Examples only — not a complete market inventory, confirmed enterprise stack, product recommendation, PQC-readiness claim or qualified connector list. Commercial off-the-shelf (COTS), off-the-shelf (OTS), enterprise software-as-a-service (SaaS), open-source and relevant hardware/platform examples are labelled. Multiple products and deployments can serve the same function. An unlisted product, existing inventory or referral is equally useful.";
    private static readonly Lazy<IReadOnlyList<RecognitionDomain>> Catalog=new(Load);
    public static IReadOnlyList<RecognitionDomain> Domains=>Catalog.Value;
    public static string Sha256=>AssessmentWorkflow.Hash(new{Version,ReviewedAt,Boundary,Domains});
    public static DiscoveryRecognitionView? ForFamily(string familyId)
    {
        var domain=Domains.SingleOrDefault(d=>d.Families.Any(f=>f.Id==familyId));
        return domain is null?null:new(Version,Sha256,ReviewedAt,Boundary,familyId,domain,Domains);
    }
    private static IReadOnlyList<RecognitionDomain> Load()
    {
        var domains=new List<RecognitionDomain>();
        foreach(var segment in new[]{"1-5","6-10"})
        {
            using var stream=typeof(DiscoveryRecognition).Assembly.GetManifestResourceStream("PqcEnterpriseDemo.Recognition."+segment)
                ??throw new DemoStoreException("discovery_recognition_missing");
            var document=JsonSerializer.Deserialize<RecognitionDocument>(stream,AssessmentJson.Options)
                ??throw new DemoStoreException("discovery_recognition_invalid");
            domains.AddRange(document.Domains);
        }
        var families=domains.SelectMany(d=>d.Families).ToArray();
        if(!domains.Select(d=>d.Id).Order(StringComparer.Ordinal).SequenceEqual(Enumerable.Range(1,10).Select(n=>$"area-{n:00}"))||
            families.Length!=27||families.Select(f=>f.Id).Distinct(StringComparer.Ordinal).Count()!=27||
            domains.Any(d=>string.IsNullOrWhiteSpace(d.Name)||d.Families.Count==0)||
            families.Any(f=>string.IsNullOrWhiteSpace(f.Name)||f.Examples.Count is <6 or >30||
                f.Examples.Select(e=>e.Name).Distinct(StringComparer.OrdinalIgnoreCase).Count()!=f.Examples.Count||
                f.Examples.Any(e=>string.IsNullOrWhiteSpace(e.Name)||e.Name.Length>160||e.Note?.Length>350||
                    e.Kind is not("COTS" or "SaaS" or "Open source" or "Hardware/platform")||
                    !Uri.TryCreate(e.Url,UriKind.Absolute,out var uri)||uri.Scheme!="https"||uri.UserInfo.Length>0)))
            throw new DemoStoreException("discovery_recognition_invalid");
        return domains.OrderBy(d=>d.Id,StringComparer.Ordinal).ToArray();
    }
}
