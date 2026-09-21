using System.Text.Json.Nodes;
using Microsoft.AspNetCore.Http.Features;

namespace PqcEnterpriseDemo.Api;

internal static class WorkspaceEndpoints
{
    public static void MapWorkspaceEndpoints(this WebApplication app,IEnterpriseStore enterprise,DemoSessions sessions)
    {
        var store=(IAssessmentWorkStore)enterprise;
        static string Principal(HttpContext c)=>DemoSessions.Current(c)?.PrincipalId??throw new DemoHttpException(401,"authentication_required");
        static string Key(HttpContext c){var key=c.Request.Headers["Idempotency-Key"].ToString();DemoHttp.IdempotencyKey(key);return key;}
        static AssessmentCommand Decode(JsonObject body,string key)
        {
            var operation=DemoHttp.RequiredText(body,"operation",48);var target=body["targetId"] is null?null:DemoHttp.RequiredText(body,"targetId",160);
            if(body["expectedRevision"] is not JsonValue v||!v.TryGetValue<int>(out var revision)||revision<1||body["fields"] is not JsonObject fields)throw new DemoHttpException(400,"invalid_request_fields");
            return new(operation,target,fields,revision,key);
        }
        void Coordinator(string id,HttpContext c)
        {if(store.AssessmentWork(id,Principal(c))["canReceive"]?.GetValue<bool>()!=true)throw new DemoHttpException(403,"assessment_forbidden");}
        app.MapGet("/api/assessments/{id}/work",(string id,HttpContext c)=>Results.Json(store.AssessmentWork(id,Principal(c))));
        app.MapGet("/api/assessments/{id}/work/{requestId}",(string id,string requestId,HttpContext c)=>Results.Json(store.AssessmentWorkCase(id,requestId,Principal(c))));
        app.MapGet("/api/assessments/{id}/receipts/{receiptId}",(string id,string receiptId,HttpContext c)=>Results.Json(store.WorkspaceReceipt(id,receiptId,Principal(c))));
        app.MapGet("/api/assessments/{id}/evidence/{bundleId}/observations",(string id,string bundleId,HttpContext c)=>Results.Json(store.WorkspaceObservations(id,bundleId,Principal(c),DemoHttp.QueryInt(c,"page",1,1,10000),DemoHttp.QueryInt(c,"pageSize",25,1,100))));
        app.MapPost("/api/assessments/{id}/receipts",async(string id,HttpContext c)=>
        {
            Coordinator(id,c);sessions.AdmitAction();var key=Key(c);
            var request=DemoHttp.QueryText(c,"requestId",160)??throw new DemoHttpException(400,"workspace_request_required");
            _=store.AssessmentWorkCase(id,request,Principal(c));
            var revision=DemoHttp.QueryInt(c,"expectedRevision",0,1,int.MaxValue);
            var filename=DemoHttp.QueryText(c,"filename",240)??"returned-questionnaire.xlsx";
            if(c.Request.ContentType is not("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" or "application/octet-stream"))throw new DemoHttpException(415,"xlsx_content_type_required");
            var bytes=await Bytes(c,IntakeWorkbook.MaxInputBytes);var parsed=await IntakeParserProcess.ParseOperational(bytes,c.RequestAborted);
            return Results.Json(store.ReceiveOperationalReturn(id,request,revision,key,Principal(c),filename,bytes,parsed));
        });
        app.MapPost("/api/assessments/{id}/work/{requestId}/evidence",async(string id,string requestId,HttpContext c)=>
        {
            Coordinator(id,c);sessions.AdmitAction();var key=Key(c);_=store.AssessmentWorkCase(id,requestId,Principal(c));
            if(!c.Request.HasJsonContentType())throw new DemoHttpException(415,"json_content_type_required");
            var product=DemoHttp.QueryText(c,"productId",160)??throw new DemoHttpException(400,"workspace_product_required");var revision=DemoHttp.QueryInt(c,"expectedRevision",0,1,int.MaxValue);
            var bytes=await Bytes(c,32768);var parsed=WorkspaceEvidenceProjection.Parse(bytes);
            return Results.Json(store.StageWorkspaceEvidence(id,requestId,product,revision,key,Principal(c),bytes,parsed));
        });
        app.MapPost("/api/assessments/{id}/work/commands",async(string id,HttpContext c)=>
        {sessions.AdmitAction();var key=Key(c);var body=await DemoHttp.ReadBoundedClosedBody(c,32768,"operation","targetId","expectedRevision","fields");return Results.Json(store.WorkspaceCommand(id,Decode(body,key),Principal(c)));});
        app.MapPost("/api/assessments/{id}/report-impact/preview",async(string id,HttpContext c)=>
        {sessions.AdmitAction();var body=await DemoHttp.ReadBoundedClosedBody(c,32768,"operation","targetId","expectedRevision","fields");return Results.Json(store.PreviewWorkspaceConsequence(id,Decode(body,"preview-only"),Principal(c)));});
    }
    private static async Task<byte[]> Bytes(HttpContext c,int maximum)
    {
        if(c.Features.Get<IHttpMaxRequestBodySizeFeature>() is {IsReadOnly:false} f)f.MaxRequestBodySize=maximum;
        if(c.Request.ContentLength>maximum)throw new DemoHttpException(413,"workspace_input_limit");using var output=new MemoryStream();var buffer=new byte[4096];int length;
        while((length=await c.Request.Body.ReadAsync(buffer,c.RequestAborted))>0){if(output.Length+length>maximum)throw new DemoHttpException(413,"workspace_input_limit");output.Write(buffer,0,length);}return output.ToArray();
    }
}
