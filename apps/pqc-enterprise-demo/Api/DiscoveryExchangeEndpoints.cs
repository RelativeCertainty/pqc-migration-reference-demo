using System.Text.Json.Nodes;
using Microsoft.AspNetCore.Http.Features;

namespace PqcEnterpriseDemo.Api;

internal static class DiscoveryExchangeEndpoints
{
    public static void MapDiscoveryExchangeEndpoints(this WebApplication app,IEnterpriseStore enterprise,DemoSessions sessions)
    {
        var store=(EnterpriseStore)enterprise;
        static string Principal(HttpContext c)=>DemoSessions.Current(c)?.PrincipalId??throw new DemoHttpException(401,"authentication_required");
        static string Key(HttpContext c){var value=c.Request.Headers["Idempotency-Key"].ToString();DemoHttp.IdempotencyKey(value);return value;}
        static int Revision(JsonObject body)=>body["expectedRevision"] is JsonValue v&&v.TryGetValue<int>(out var n)&&n>=1?n:throw new DemoHttpException(400,"invalid_expected_revision");
        void Writable(string id,string request,HttpContext c)
        {DemoHttp.Identifier(id);DemoHttp.Identifier(request);var view=store.DiscoveryRequest(id,request,Principal(c));if(view["canEdit"]?.GetValue<bool>()!=true)throw new DemoHttpException(403,"assessment_forbidden");}
        app.MapPost("/api/assessments/{id}/discovery/exports/{requestId}",async(string id,string requestId,HttpContext c)=>
        {Writable(id,requestId,c);sessions.AdmitAction();var key=Key(c);var body=await DemoHttp.ReadClosedBody(c,"expectedRevision");return Results.Json(store.ExportDiscovery(id,requestId,Revision(body),key,Principal(c)));});
        app.MapGet("/api/assessments/{id}/discovery/exports/{exportId}/download",(string id,string exportId,HttpContext c)=>Results.File(store.DownloadDiscovery(id,exportId,Principal(c)),"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet","synthetic-five-question-discovery.xlsx"));
        app.MapPost("/api/assessments/{id}/discovery/imports/{requestId}",async(string id,string requestId,HttpContext c)=>
        {
            Writable(id,requestId,c);sessions.AdmitAction();var key=Key(c);
            if(c.Request.ContentType is not("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" or "application/octet-stream"))throw new DemoHttpException(415,"xlsx_content_type_required");
            var revision=DemoHttp.QueryInt(c,"expectedRevision",0,1,int.MaxValue);var bytes=await ReadBytes(c);var parsed=await IntakeParserProcess.Parse(bytes,c.RequestAborted,discovery:true);
            return Results.Json(store.PreviewDiscovery(id,requestId,revision,key,Principal(c),parsed,bytes));
        });
        app.MapPost("/api/assessments/{id}/discovery/imports/{importId}/commit",async(string id,string importId,HttpContext c)=>
        {
            DemoHttp.Identifier(id);DemoHttp.Identifier(importId);sessions.AdmitAction();var key=Key(c);var body=await DemoHttp.ReadBoundedClosedBody(c,16384,"expectedRevision","choices");
            if(body["choices"] is not JsonObject choices)throw new DemoHttpException(400,"invalid_request_fields");return Results.Json(store.CommitDiscoveryImport(id,importId,Revision(body),key,Principal(c),choices));
        });
    }
    private static async Task<byte[]> ReadBytes(HttpContext c)
    {
        if(c.Features.Get<IHttpMaxRequestBodySizeFeature>() is {IsReadOnly:false} feature)feature.MaxRequestBodySize=IntakeWorkbook.MaxInputBytes;
        if(c.Request.ContentLength>IntakeWorkbook.MaxInputBytes)throw new DemoHttpException(413,"intake_upload_limit");using var output=new MemoryStream();var buffer=new byte[4096];int n;
        while((n=await c.Request.Body.ReadAsync(buffer,c.RequestAborted))>0){if(output.Length+n>IntakeWorkbook.MaxInputBytes)throw new DemoHttpException(413,"intake_upload_limit");output.Write(buffer,0,n);}return output.ToArray();
    }
}
