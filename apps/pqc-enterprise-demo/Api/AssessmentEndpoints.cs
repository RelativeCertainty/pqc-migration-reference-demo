using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo.Api;

/// <summary>Same-origin, authenticated ingress to the isolated assessment
/// application. Identity and request authority are never read from the body.</summary>
internal static class AssessmentEndpoints
{
    public static void MapAssessmentEndpoints(this WebApplication app, IEnterpriseStore enterprise, DemoSessions sessions)
    {
        var store = (IAssessmentStore)enterprise;
        var queries = (IAssessmentQueries)enterprise;
        static string Principal(HttpContext context) => DemoSessions.Current(context)?.PrincipalId
            ?? throw new DemoHttpException(401, "authentication_required");

        app.MapGet("/api/assessments/catalog", (HttpContext context) => Results.Json(store.Catalog(Principal(context))));
        app.MapGet("/api/assessments", (HttpContext context) => Results.Json(store.ListAssessments(Principal(context))));
        app.MapPost("/api/assessments", async (HttpContext context) =>
        {
            sessions.AdmitAction();
            var key = context.Request.Headers["Idempotency-Key"].ToString();
            DemoHttp.IdempotencyKey(key);
            var body = await DemoHttp.ReadClosedBody(context, "name", "mode");
            return Results.Json(store.CreateAssessment(DemoHttp.RequiredText(body, "name", 120),
                DemoHttp.RequiredText(body, "mode", 32), key, Principal(context)), statusCode: 201);
        });
        app.MapGet("/api/assessments/{id}", (string id, HttpContext context) =>
        {
            DemoHttp.Identifier(id);
            return Results.Json(store.GetAssessment(id, Principal(context)));
        });
        app.MapPost("/api/assessments/{id}/commands", async (string id, HttpContext context) =>
        {
            DemoHttp.Identifier(id);
            sessions.AdmitAction();
            var key = context.Request.Headers["Idempotency-Key"].ToString();
            DemoHttp.IdempotencyKey(key);
            var body = await DemoHttp.ReadBoundedClosedBody(context, 16384, "operation", "targetId", "expectedRevision", "fields");
            var operation = DemoHttp.RequiredText(body, "operation", 48);
            var target = body["targetId"] is null ? null : DemoHttp.RequiredText(body, "targetId", 160);
            if (target is not null) DemoHttp.Identifier(target);
            if (body["expectedRevision"] is not JsonValue revisionValue || !revisionValue.TryGetValue<int>(out var revision) || revision < 0)
                throw new DemoHttpException(400, "invalid_expected_revision");
            if (body["fields"] is not JsonObject fields) throw new DemoHttpException(400, "invalid_request_fields");
            return Results.Json(store.ExecuteAssessmentCommand(id,
                new AssessmentCommand(operation, target, fields, revision, key), Principal(context)));
        });
        app.MapGet("/api/assessments/{id}/analysis", (string id, HttpContext context) =>
            Results.Json(queries.AssessmentAnalysis(id, Principal(context), Filter(context))));
        app.MapGet("/api/assessments/{id}/dashboard", (string id, HttpContext context) =>
            Results.Json(queries.AssessmentDashboard(id, Principal(context))));
        app.MapGet("/api/assessments/{id}/sources", (string id, HttpContext context) =>
            Results.Json(queries.AssessmentSources(id, Principal(context))));
        app.MapGet("/api/assessments/{id}/assets", (string id, HttpContext context) =>
            Results.Json(queries.AssessmentAssets(id, Principal(context),
                DemoHttp.QueryText(context, "q", 200), DemoHttp.QueryText(context, "family", 80), DemoHttp.QueryText(context, "status", 40),
                DemoHttp.QueryInt(context, "page", 1, 1, 10000), DemoHttp.QueryInt(context, "pageSize", 25, 1, 100))));
        app.MapGet("/api/assessments/{id}/assets/{assetId}", (string id, string assetId, HttpContext context) =>
        {
            DemoHttp.Identifier(assetId);
            var asset = queries.AssessmentAsset(id, assetId, Principal(context));
            return asset is null ? DemoHttp.NotFound() : Results.Json(asset);
        });
        app.MapGet("/api/assessments/{id}/reports", (string id, HttpContext context) =>
            Results.Json(queries.AssessmentReports(id, Principal(context))));
        app.MapGet("/api/assessments/{id}/reports/{reportId}", (string id, string reportId, HttpContext context) =>
        {
            DemoHttp.Identifier(reportId);
            var report = store.GetAssessmentReport(id, reportId, Principal(context));
            return report is null ? DemoHttp.NotFound() : Results.Json(report);
        });
        app.MapGet("/api/assessments/{id}/reports/{reportId}/download", (string id, string reportId, HttpContext context) =>
        {
            DemoHttp.Identifier(reportId);
            var format = DemoHttp.QueryText(context, "format", 8) ?? "html";
            if (format is not ("html" or "json")) throw new DemoHttpException(400, "invalid_report_format");
            if (format == "json")
            {
                var report = store.GetAssessmentReport(id, reportId, Principal(context));
                if (report is null) return DemoHttp.NotFound();
                context.Response.Headers["Content-Disposition"] = $"attachment; filename=\"pqc-{reportId}.json\"";
                return Results.Json(report);
            }
            var html = store.RenderAssessmentReportHtml(id, reportId, Principal(context));
            if (html is null) return DemoHttp.NotFound();
            context.Response.Headers["Content-Security-Policy"] = DemoHttp.ReportContentSecurityPolicy(html);
            context.Response.Headers["Content-Disposition"] = $"inline; filename=\"pqc-{reportId}.html\"";
            return Results.Content(html, "text/html; charset=utf-8");
        });
        app.MapGet("/api/assessments/{id}/runs", (string id, HttpContext context) =>
            Results.Json(queries.AssessmentRuns(id, Principal(context))));
        app.MapGet("/api/assessments/{id}/actions", (string id, HttpContext context) =>
        {
            _ = store.GetAssessment(id, Principal(context));
            return Results.Json(new JsonArray()); // Legacy annotations are not assessment tasks.
        });
        app.MapGet("/api/assessments/{id}/actions/{findingId}", (string id, string findingId, HttpContext context) =>
        {
            DemoHttp.Identifier(findingId);
            _ = store.GetAssessment(id, Principal(context));
            return Results.Json(new JsonArray());
        });
    }

    private static AnalysisFilter Filter(HttpContext context) => new(
        DemoHttp.QueryText(context, "service", 160), DemoHttp.QueryText(context, "owner", 160),
        DemoHttp.QueryText(context, "environment", 160), DemoHttp.QueryText(context, "technology", 160),
        DemoHttp.QueryText(context, "family", 80));
}
