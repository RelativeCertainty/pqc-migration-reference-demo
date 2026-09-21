using System.Text.Json.Nodes;
using Microsoft.AspNetCore.Http.Features;

namespace PqcEnterpriseDemo.Api;

internal static class QuestionnaireEndpoints
{
    public static void MapQuestionnaireEndpoints(this WebApplication app,IEnterpriseStore enterprise,DemoSessions sessions)
    {
        var store=(IQuestionnaireStore)enterprise;
        static string Principal(HttpContext context)=>DemoSessions.Current(context)?.PrincipalId ?? throw new DemoHttpException(401,"authentication_required");
        app.MapGet("/api/assessments/{id}/questionnaires",(string id,HttpContext context)=>Results.Json(store.Questionnaires(id,Principal(context))));
        app.MapGet("/api/assessments/{id}/questionnaires/{assignmentId}",(string id,string assignmentId,HttpContext context)=>Results.Json(store.Questionnaire(id,assignmentId,Principal(context))));
        app.MapPost("/api/assessments/{id}/questionnaires/commands",async (string id,HttpContext context)=>
        {
            DemoHttp.Identifier(id);sessions.AdmitAction();var key=context.Request.Headers["Idempotency-Key"].ToString();DemoHttp.IdempotencyKey(key);
            if(context.Features.Get<IHttpMaxRequestBodySizeFeature>() is {IsReadOnly:false} feature)feature.MaxRequestBodySize=262144;
            var body=await DemoHttp.ReadBoundedClosedBody(context,262144,"operation","targetId","fields","expectedRevision");
            var operation=DemoHttp.RequiredText(body,"operation",48);
            var target=body["targetId"] is null?null:DemoHttp.RequiredText(body,"targetId",160);
            if(target is not null)DemoHttp.Identifier(target);
            if(body["expectedRevision"] is not JsonValue node || !node.TryGetValue<int>(out var revision) || revision<1)throw new DemoHttpException(400,"invalid_expected_revision");
            if(body["fields"] is not JsonObject fields)throw new DemoHttpException(400,"invalid_request_fields");
            return Results.Json(store.QuestionnaireCommand(id,new(operation,target,fields,revision,key),Principal(context)));
        });
    }
}
