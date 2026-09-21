using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo.Api;

internal static class DiscoveryCollectionEndpoints
{
    public static void MapDiscoveryCollectionEndpoints(this WebApplication app,IEnterpriseStore enterprise,DemoSessions sessions)
    {
        var store=(EnterpriseStore)enterprise;
        static string Principal(HttpContext c)=>DemoSessions.Current(c)?.PrincipalId??throw new DemoHttpException(401,"authentication_required");
        static string Key(HttpContext c){var key=c.Request.Headers["Idempotency-Key"].ToString();DemoHttp.IdempotencyKey(key);return key;}
        static int Revision(JsonObject body)=>body["expectedRevision"] is JsonValue v&&v.TryGetValue<int>(out var n)&&n>=1?n:throw new DemoHttpException(400,"invalid_expected_revision");
        app.MapGet("/api/assessments/{id}/discovery/catalog",(string id,HttpContext c)=>{DemoHttp.Identifier(id);return Results.Json(store.DiscoveryCatalog(id,Principal(c)));});
        app.MapPost("/api/assessments/{id}/discovery/collections",async(string id,HttpContext c)=>{
            DemoHttp.Identifier(id);sessions.AdmitAction();var key=Key(c);var body=await DemoHttp.ReadClosedBody(c,"expectedRevision","assignedTo");
            if(body["assignedTo"] is not JsonValue v||!v.TryGetValue<string>(out var recipient)||recipient.Length>128)throw new DemoHttpException(400,"invalid_request_fields");
            return Results.Json(store.CreateDiscoveryCollection(id,recipient,Revision(body),key,Principal(c)));
        });
        app.MapPost("/api/assessments/{id}/discovery/collections/{collectionId}/exports",async(string id,string collectionId,HttpContext c)=>{
            DemoHttp.Identifier(id);DemoHttp.Identifier(collectionId);sessions.AdmitAction();var key=Key(c);var body=await DemoHttp.ReadClosedBody(c,"expectedRevision");
            return Results.Json(store.ExportDiscoveryCollection(id,collectionId,Revision(body),key,Principal(c)));
        });
        app.MapGet("/api/assessments/{id}/discovery/collections/{collectionId}/exports/{packageId}/download",(string id,string collectionId,string packageId,HttpContext c)=>{
            DemoHttp.Identifier(id);DemoHttp.Identifier(collectionId);DemoHttp.Identifier(packageId);
            return Results.File(store.DownloadDiscoveryCollection(id,collectionId,packageId,Principal(c)),"application/zip","PQC_Discovery_27_Forms_and_Consolidated_Questions.zip");
        });
        app.MapGet("/api/assessments/{id}/discovery/collections/{collectionId}/exports/{packageId}/index",(string id,string collectionId,string packageId,HttpContext c)=>{
            DemoHttp.Identifier(id);DemoHttp.Identifier(collectionId);DemoHttp.Identifier(packageId);
            return Results.File(store.DownloadDiscoveryCollection(id,collectionId,packageId,Principal(c),true),"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet","PQC_Discovery_Consolidated_Questions.xlsx");
        });
    }
}
