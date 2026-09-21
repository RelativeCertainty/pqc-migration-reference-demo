using Microsoft.AspNetCore.Http.Features;

namespace PqcEnterpriseDemo.Api;

internal static class DiscoveryEvidenceEndpoints
{
    public static void MapDiscoveryEvidenceEndpoints(this WebApplication app,IEnterpriseStore enterprise,DemoSessions sessions)
    {
        var store=(IDiscoveryEvidenceStore)enterprise;
        app.MapPost("/api/assessments/{id}/discovery/investigations/{investigationId}/evidence",async(string id,string investigationId,HttpContext c)=>
        {
            var principal=DemoSessions.Current(c)?.PrincipalId ?? throw new DemoHttpException(401,"authentication_required");
            // Admit only the staff role before reading the bounded body. The
            // transactional command repeats assessment and gate admission.
            var view=((IDiscoveryStore)enterprise).Discovery(id,principal);
            if(view["canCoordinate"]?.GetValue<bool>()!=true)throw new DemoHttpException(403,"assessment_forbidden");
            sessions.AdmitAction();DemoHttp.Identifier(id);DemoHttp.Identifier(investigationId);
            var key=c.Request.Headers["Idempotency-Key"].ToString();DemoHttp.IdempotencyKey(key);
            if(!c.Request.HasJsonContentType())throw new DemoHttpException(415,"json_content_type_required");
            var product=DemoHttp.QueryText(c,"productRefId",160) ?? throw new DemoHttpException(400,"discovery_product_required");
            var source=DemoHttp.QueryText(c,"sourceLabel",256) ?? throw new DemoHttpException(400,"discovery_source_label_required");
            var revision=DemoHttp.QueryInt(c,"expectedRevision",0,1,int.MaxValue);
            const int limit=32768;
            if(c.Features.Get<IHttpMaxRequestBodySizeFeature>() is {IsReadOnly:false} feature)feature.MaxRequestBodySize=limit;
            if(c.Request.ContentLength>limit)throw new DemoHttpException(413,"discovery_evidence_limit");
            using var output=new MemoryStream();var buffer=new byte[4096];int read;
            while((read=await c.Request.Body.ReadAsync(buffer,c.RequestAborted))>0)
            {if(output.Length+read>limit)throw new DemoHttpException(413,"discovery_evidence_limit");output.Write(buffer,0,read);}
            return Results.Json(store.StageDiscoveryEvidence(id,investigationId,product,source,revision,key,principal,output.ToArray()));
        });
    }
}
