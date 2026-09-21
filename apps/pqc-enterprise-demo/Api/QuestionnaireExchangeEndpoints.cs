using System.Text.Json.Nodes;
using Microsoft.AspNetCore.Http.Features;

namespace PqcEnterpriseDemo.Api;

internal static class QuestionnaireExchangeEndpoints
{
    public static void MapQuestionnaireExchangeEndpoints(this WebApplication app,IEnterpriseStore enterprise,DemoSessions sessions)
    {
        var store=(EnterpriseStore)enterprise;
        static string Principal(HttpContext c)=>DemoSessions.Current(c)?.PrincipalId??throw new DemoHttpException(401,"authentication_required");
        static string Key(HttpContext c){var value=c.Request.Headers["Idempotency-Key"].ToString();DemoHttp.IdempotencyKey(value);return value;}
        static int Revision(JsonObject body)=>body["expectedRevision"] is JsonValue v&&v.TryGetValue<int>(out var n)&&n>=1?n:throw new DemoHttpException(400,"invalid_expected_revision");
        void Writable(string id,string assignment,HttpContext c)
        {
            DemoHttp.Identifier(id);DemoHttp.Identifier(assignment);
            var view=store.Questionnaire(id,assignment,Principal(c));
            if(view["canEdit"]?.GetValue<bool>()!=true)throw new DemoHttpException(403,"assessment_forbidden");
        }
        app.MapPost("/api/assessments/{id}/questionnaires/exports/{assignmentId}",async(string id,string assignmentId,HttpContext c)=>
        {
            Writable(id,assignmentId,c);sessions.AdmitAction();var key=Key(c);var body=await DemoHttp.ReadClosedBody(c,"expectedRevision");
            return Results.Json(store.ExportQuestionnaire(id,assignmentId,Revision(body),key,Principal(c)));
        });
        app.MapGet("/api/assessments/{id}/questionnaires/exports/{exportId}/download",(string id,string exportId,HttpContext c)=>Results.File(store.DownloadQuestionnaire(id,exportId,Principal(c)),"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet","synthetic-full-source-questionnaire.xlsx"));
        app.MapPost("/api/assessments/{id}/questionnaires/imports/{assignmentId}",async(string id,string assignmentId,HttpContext c)=>
        {
            Writable(id,assignmentId,c);sessions.AdmitAction();var key=Key(c);
            if(c.Request.ContentType is not("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" or "application/octet-stream"))throw new DemoHttpException(415,"xlsx_content_type_required");
            var revision=DemoHttp.QueryInt(c,"expectedRevision",0,1,int.MaxValue);var bytes=await ReadBytes(c);
            var parsed=await IntakeParserProcess.Parse(bytes,c.RequestAborted,true);
            return Results.Json(store.PreviewQuestionnaire(id,assignmentId,revision,key,Principal(c),parsed,bytes));
        });
        app.MapPost("/api/assessments/{id}/questionnaires/imports/{importId}/commit",async(string id,string importId,HttpContext c)=>
        {
            DemoHttp.Identifier(id);DemoHttp.Identifier(importId);sessions.AdmitAction();var key=Key(c);
            var body=await DemoHttp.ReadBoundedClosedBody(c,16384,"expectedRevision","choices");
            if(body["choices"] is not JsonObject choices)throw new DemoHttpException(400,"invalid_request_fields");
            return Results.Json(store.CommitQuestionnaireImport(id,importId,Revision(body),key,Principal(c),choices));
        });
    }
    private static async Task<byte[]> ReadBytes(HttpContext c)
    {
        if(c.Features.Get<IHttpMaxRequestBodySizeFeature>() is {IsReadOnly:false} feature)feature.MaxRequestBodySize=IntakeWorkbook.MaxInputBytes;
        if(c.Request.ContentLength>IntakeWorkbook.MaxInputBytes)throw new DemoHttpException(413,"intake_upload_limit");
        using var output=new MemoryStream();var buffer=new byte[4096];int count;
        while((count=await c.Request.Body.ReadAsync(buffer,c.RequestAborted))>0){if(output.Length+count>IntakeWorkbook.MaxInputBytes)throw new DemoHttpException(413,"intake_upload_limit");output.Write(buffer,0,count);}
        return output.ToArray();
    }
}
