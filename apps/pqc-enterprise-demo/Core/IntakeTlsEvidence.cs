using System.Text.Json;
using System.Text.RegularExpressions;

namespace PqcEnterpriseDemo;

public sealed record IntakeTlsRecord(string Id,string Hostname,string KeyExchange,string Authentication,string Basis);

public static class IntakeTlsEvidence
{
    // Existing pba.pqc.reference-source-page.v1 TLS subset; neither arbitrary vendor
    // JSON nor evidence of an actual negotiated session. Independent verification is absent.
    public static List<IntakeTlsRecord> Parse(byte[] bytes)
    {
        if(bytes.Length>32768)throw new DemoValidationException("intake_evidence_limit");
        try
        {
            using var doc=JsonDocument.Parse(bytes,new JsonDocumentOptions{MaxDepth=5});
            var root=doc.RootElement;
            Closed(root,["schema_version","kind","synthetic","records"]);
            if(root.GetProperty("schema_version").GetString()!="pba.pqc.reference-source-page.v1" || root.GetProperty("kind").GetString()!="tls" || root.GetProperty("synthetic").ValueKind!=JsonValueKind.True)Invalid();
            var records=root.GetProperty("records");
            if(records.ValueKind!=JsonValueKind.Array || records.GetArrayLength() is <1 or >32)Invalid();
            var result=new List<IntakeTlsRecord>();var ids=new HashSet<string>();
            foreach(var row in records.EnumerateArray())
            {
                Closed(row,["id","evidence_basis","application_id","application_source","certificate_id","certificate_source","hostname","port","protocol","key_exchange_group","certificate_signature_algorithm"]);
                var id=Text(row,"id",128,"^[a-zA-Z0-9][a-zA-Z0-9_.:-]*$");
                if(!ids.Add(id))Invalid();
                foreach(var k in new[]{"application_id","application_source","certificate_id","certificate_source"})
                    if(row.GetProperty(k).ValueKind!=JsonValueKind.Null)_=Text(row,k,128,"^[a-zA-Z0-9][a-zA-Z0-9_.:-]*$");
                var hostname=Text(row,"hostname",253,"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\\.(?:example|test|invalid)$");
                var basis=Text(row,"evidence_basis",20,"^[a-z_]+$");
                if(basis is not ("observed" or "configured" or "vendor_reported"))Invalid();
                if(!row.GetProperty("port").TryGetInt32(out var port) || port is <1 or >65535)Invalid();
                if(row.GetProperty("protocol").GetString() is not ("TLSv1.2" or "TLSv1.3" or "unknown"))Invalid();
                result.Add(new(id,hostname,Algorithm(row,"key_exchange_group"),Algorithm(row,"certificate_signature_algorithm"),basis));
            }
            return result;
        }
        catch(Exception e) when(e is JsonException or InvalidOperationException or KeyNotFoundException or ArgumentException)
        {throw new DemoValidationException("intake_reference_evidence_invalid");}
    }
    private static string Algorithm(JsonElement row,string key)=>row.GetProperty(key).ValueKind==JsonValueKind.Null?"unknown":Text(row,key,80,"^[A-Za-z0-9][A-Za-z0-9_.+/-]*$");
    private static string Text(JsonElement row,string key,int max,string pattern)
    {
        var text=row.GetProperty(key).GetString();
        if(text is null || text.Length>max || !Regex.IsMatch(text,pattern,RegexOptions.CultureInvariant,TimeSpan.FromMilliseconds(100)))Invalid();
        return text!;
    }
    private static void Closed(JsonElement value,string[] names)
    {
        if(value.ValueKind!=JsonValueKind.Object)Invalid();
        var seen=new HashSet<string>();
        foreach(var p in value.EnumerateObject())if(!names.Contains(p.Name) || !seen.Add(p.Name))Invalid();
        if(seen.Count!=names.Length)Invalid();
    }
    private static void Invalid()=>throw new DemoValidationException("intake_reference_evidence_invalid");
}
