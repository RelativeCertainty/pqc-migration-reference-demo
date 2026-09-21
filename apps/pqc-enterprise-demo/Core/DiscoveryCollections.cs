namespace PqcEnterpriseDemo;

// Additive assessment snapshot fields. Existing raw historical versions are never rewritten.
public sealed class DiscoveryCollection
{
    public string Id {get;set;}="";
    public string AssignedTo {get;set;}="";
    public string CreatedAt {get;set;}="";
    public List<string> RequestIds {get;set;}=[];
    public List<DiscoveryCollectionPackage> Packages {get;set;}=[];
}
public sealed class DiscoveryCollectionPackage
{
    public string Id {get;set;}="";
    public string CreatedAt {get;set;}="";
    public List<DiscoveryCollectionEntry> Entries {get;set;}=[];
    public string IndexBytesBase64 {get;set;}="";
    public string IndexSha256 {get;set;}="";
    public string ZipBytesBase64 {get;set;}="";
    public string ZipSha256 {get;set;}="";
}
public sealed record DiscoveryCollectionEntry(string FamilyId,string RequestId,string ExportId,string Filename,string Sha256);
