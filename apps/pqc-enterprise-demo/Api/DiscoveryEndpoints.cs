using Microsoft.AspNetCore.Http.Features;
using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo.Api;

internal static class DiscoveryEndpoints
{
    public static void MapDiscoveryEndpoints(this WebApplication app,IEnterpriseStore enterprise,DemoSessions sessions)
    {
        var store=(IDiscoveryStore)enterprise;
        static string Principal(HttpContext c)=>DemoSessions.Current(c)?.PrincipalId??throw new DemoHttpException(401,"authentication_required");
        app.MapGet("/api/assessments/{id}/discovery",(string id,HttpContext c)=>Results.Json(store.Discovery(id,Principal(c))));
        app.MapGet("/api/assessments/{id}/discovery/{requestId}",(string id,string requestId,HttpContext c)=>Results.Json(store.DiscoveryRequest(id,requestId,Principal(c))));
        app.MapPost("/api/assessments/{id}/discovery/commands",async(string id,HttpContext c)=>
        {
            DemoHttp.Identifier(id);sessions.AdmitAction();var key=c.Request.Headers["Idempotency-Key"].ToString();DemoHttp.IdempotencyKey(key);
            if(c.Features.Get<IHttpMaxRequestBodySizeFeature>() is {IsReadOnly:false} feature)feature.MaxRequestBodySize=131072;
            var body=await DemoHttp.ReadBoundedClosedBody(c,131072,"operation","targetId","fields","expectedRevision");
            var operation=DemoHttp.RequiredText(body,"operation",48);var target=body["targetId"] is null?null:DemoHttp.RequiredText(body,"targetId",160);
            if(target is not null)DemoHttp.Identifier(target);
            if(body["expectedRevision"] is not JsonValue node||!node.TryGetValue<int>(out var revision)||revision<1)throw new DemoHttpException(400,"invalid_expected_revision");
            if(body["fields"] is not JsonObject fields)throw new DemoHttpException(400,"invalid_request_fields");
            return Results.Json(store.DiscoveryCommand(id,new(operation,target,fields,revision,key),Principal(c)));
        });
    }
}
