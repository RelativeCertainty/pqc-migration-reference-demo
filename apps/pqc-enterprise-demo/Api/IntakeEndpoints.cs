using System.Text.Json.Nodes;
using Microsoft.AspNetCore.Http.Features;

namespace PqcEnterpriseDemo.Api;

internal static class IntakeEndpoints
{
    public static void MapIntakeEndpoints(this WebApplication app,IEnterpriseStore enterprise,DemoSessions sessions)
    {
        var store=(IIntakeStore)enterprise;
        static string Principal(HttpContext c)=>DemoSessions.Current(c)?.PrincipalId ?? throw new DemoHttpException(401,"authentication_required");
        static string Key(HttpContext c){var key=c.Request.Headers["Idempotency-Key"].ToString();DemoHttp.IdempotencyKey(key);return key;}
        static int Revision(JsonObject b)=>b["expectedRevision"] is JsonValue v && v.TryGetValue<int>(out var n) && n>=1?n:throw new DemoHttpException(400,"invalid_expected_revision");
        void RequestAccess(string id,string request,HttpContext c)
        {
            DemoHttp.Identifier(id);DemoHttp.Identifier(request);
            var view=store.IntakeView(id,Principal(c));
            if(view["requests"] is not JsonArray rows || !rows.OfType<JsonObject>().Any(r=>r["id"]?.GetValue<string>()==request))throw new DemoHttpException(403,"assessment_forbidden");
            if(view["canCoordinate"]?.GetValue<bool>()!=true && !IntakeWorkflow.Contributor(Principal(c)))throw new DemoHttpException(403,"assessment_forbidden");
            var family=rows.OfType<JsonObject>().Single(r=>r["id"]?.GetValue<string>()==request)["familyId"]?.GetValue<string>();
            if(view["eligibleFamilyIds"] is not JsonArray families || !families.Any(f=>f?.GetValue<string>()==family))throw new DemoHttpException(409,"intake_request_out_of_scope");
        }
        app.MapGet("/api/assessments/{id}/intake",(string id,HttpContext c)=>Results.Json(store.IntakeView(id,Principal(c))));
        app.MapPost("/api/assessments/{id}/intake/commands",async (string id,HttpContext c)=>
        {
            sessions.AdmitAction();var key=Key(c);
            var b=await DemoHttp.ReadBoundedClosedBody(c,16384,"operation","targetId","fields","expectedRevision");
            var target=b["targetId"] is null?null:DemoHttp.RequiredText(b,"targetId",160);
            if(b["fields"] is not JsonObject fields)throw new DemoHttpException(400,"invalid_request_fields");
            return Results.Json(store.IntakeCommand(id,new(DemoHttp.RequiredText(b,"operation",48),target,fields,Revision(b),key),Principal(c)));
        });
        app.MapPost("/api/assessments/{id}/intake/exports/{requestId}",async (string id,string requestId,HttpContext c)=>
        {
            RequestAccess(id,requestId,c);sessions.AdmitAction();var key=Key(c);
            var b=await DemoHttp.ReadClosedBody(c,"expectedRevision");
            return Results.Json(store.ExportIntake(id,requestId,Revision(b),key,Principal(c)));
        });
        app.MapGet("/api/assessments/{id}/intake/exports/{exportId}/download",(string id,string exportId,HttpContext c)=>
            Results.File(store.DownloadIntake(id,exportId,Principal(c)),"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet","synthetic-source-questionnaire.xlsx"));
        app.MapPost("/api/assessments/{id}/intake/imports/{requestId}",async (string id,string requestId,HttpContext c)=>
        {
            RequestAccess(id,requestId,c);sessions.AdmitAction();var key=Key(c);
            if(c.Request.ContentType is not ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" or "application/octet-stream"))throw new DemoHttpException(415,"xlsx_content_type_required");
            var revision=DemoHttp.QueryInt(c,"expectedRevision",0,1,int.MaxValue);
            var bytes=await ReadBytes(c,1_048_576);
            var workbook=await IntakeParserProcess.Parse(bytes,c.RequestAborted);
            return Results.Json(store.PreviewIntake(id,requestId,revision,key,Principal(c),workbook,bytes));
        });
        app.MapPost("/api/assessments/{id}/intake/evidence/{requestId}",async (string id,string requestId,HttpContext c)=>
        {
            RequestAccess(id,requestId,c);sessions.AdmitAction();var key=Key(c);
            if(!c.Request.HasJsonContentType())throw new DemoHttpException(415,"json_content_type_required");
            var system=DemoHttp.QueryText(c,"systemId",160) ?? throw new DemoHttpException(400,"intake_system_required");
            var source=DemoHttp.QueryText(c,"sourceSystemId",160) ?? throw new DemoHttpException(400,"intake_source_required");
            var revision=DemoHttp.QueryInt(c,"expectedRevision",0,1,int.MaxValue);
            var bytes=await ReadBytes(c,32768);
            return Results.Json(store.StageIntakeEvidence(id,requestId,system,source,revision,key,Principal(c),bytes));
        });
    }
    private static async Task<byte[]> ReadBytes(HttpContext c,int limit)
    {
        if(c.Features.Get<IHttpMaxRequestBodySizeFeature>() is {IsReadOnly:false} feature)feature.MaxRequestBodySize=limit;
        if(c.Request.ContentLength>limit)throw new DemoHttpException(413,"intake_upload_limit");
        using var output=new MemoryStream();var buffer=new byte[4096];int read;
        while((read=await c.Request.Body.ReadAsync(buffer,c.RequestAborted))>0)
        {
            if(output.Length+read>limit)throw new DemoHttpException(413,"intake_upload_limit");
            output.Write(buffer,0,read);
        }
        return output.ToArray();
    }
}
