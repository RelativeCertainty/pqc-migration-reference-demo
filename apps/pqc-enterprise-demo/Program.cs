using System.Globalization;
using System.Net;
using System.Text.Json.Nodes;
using Microsoft.AspNetCore.Server.Kestrel.Core;
using PqcEnterpriseDemo.Api;

namespace PqcEnterpriseDemo;

/// <summary>
/// Development-only ingress adapter. It has no production database, provider,
/// directory-service, or source-system effect authority. Report requests enter
/// EnterpriseStore's simulated manifest-bound WorkerRun path, not a second
/// execution authority in the HTTP handlers.
/// </summary>
public static class Program
{
    public static async Task<int> Main(string[] args)
    {
        if (args.SequenceEqual(new[] { "--version" }))
        {
            Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new { version = "0.2.0", runtime = ".NET " + Environment.Version,
                source = typeof(Program).Assembly.GetCustomAttributes(typeof(System.Reflection.AssemblyInformationalVersionAttribute), false)
                    .Cast<System.Reflection.AssemblyInformationalVersionAttribute>().SingleOrDefault()?.InformationalVersion,
                profile = "synthetic-only", application = "one-csharp-react-host" }));
            return 0;
        }
        if(args.Length > 0 && args[0].StartsWith("--capacity-", StringComparison.Ordinal))return await CapacityEndpoints.Command(args);
        if(args.SequenceEqual(new[]{"--intake-workbook-parser"}))return await IntakeParserProcess.RunChild();
        if(args.SequenceEqual(new[]{"--questionnaire-workbook-parser"}))return await IntakeParserProcess.RunChild(true);
        if(args.SequenceEqual(new[]{"--discovery-workbook-parser"}))return await IntakeParserProcess.RunChild(discovery:true);
        if(args.SequenceEqual(new[]{"--operational-workbook-parser"}))return await IntakeParserProcess.RunChild(operational:true);
        try
        {
            var options = DemoHostOptions.Parse(args);
            using IEnterpriseStore store = new EnterpriseStore(options.DataDirectory, options.FixturePath);
            if (options.BackupDirectory is { } backup)
            {
                store.Backup(backup);
                Console.WriteLine("{\"status\":\"backup_complete\",\"synthetic\":true}");
                return 0;
            }
            var staticAssets = StaticAssets.Load(options.WebRoot);
            var sessions = new DemoSessions(options.Port);
            var origin = $"http://127.0.0.1:{options.Port.ToString(CultureInfo.InvariantCulture)}";
            var expectedHost = $"127.0.0.1:{options.Port.ToString(CultureInfo.InvariantCulture)}";

            // Do not inherit ASPNETCORE_URLS, JSON Kestrel endpoints, forwarded
            // headers, production configuration, secrets, or logging providers.
            var builder = WebApplication.CreateSlimBuilder(new WebApplicationOptions
            {
                Args = [],
                ContentRootPath = AppContext.BaseDirectory,
                WebRootPath = options.WebRoot,
                EnvironmentName = "Production"
            });
            builder.Configuration.Sources.Clear();
            builder.Logging.ClearProviders();
            builder.WebHost.ConfigureKestrel(server =>
            {
                server.AddServerHeader = false;
                server.Limits.MaxRequestBodySize = 16384;
                server.Limits.MaxConcurrentConnections = 32;
                server.Limits.MaxRequestHeaderCount = 40;
                server.Limits.MaxRequestHeadersTotalSize = 8192;
                server.Limits.RequestHeadersTimeout = TimeSpan.FromSeconds(10);
                server.Limits.KeepAliveTimeout = TimeSpan.FromSeconds(30);
                server.Listen(IPAddress.Loopback, options.Port, endpoint =>
                    endpoint.Protocols = HttpProtocols.Http1);
            });
            builder.Services.ConfigureHttpJsonOptions(json =>
            {
                json.SerializerOptions.MaxDepth = 32;
            });
            builder.Services.AddSingleton<IEnterpriseStore>(store);

            var app = builder.Build();
            app.Use(async (context, next) =>
            {
                context.Response.Headers["Cache-Control"] = "no-store";
                context.Response.Headers["X-Content-Type-Options"] = "nosniff";
                context.Response.Headers["X-Frame-Options"] = "DENY";
                context.Response.Headers["Cross-Origin-Resource-Policy"] = "same-origin";
                context.Response.Headers["Cross-Origin-Opener-Policy"] = "same-origin";
                context.Response.Headers["X-Robots-Tag"] = "noindex, nofollow, noarchive";
                context.Response.Headers["Referrer-Policy"] = "no-referrer";
                context.Response.Headers["Permissions-Policy"] = "accelerometer=(), camera=(), geolocation=(), gyroscope=(), microphone=(), payment=(), usb=()";
                context.Response.Headers["Content-Security-Policy"] =
                    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; " +
                    "font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; " +
                    "frame-ancestors 'none'; object-src 'none'";
                try
                {
                    if (context.Connection.RemoteIpAddress is not { } peer || !IPAddress.IsLoopback(peer))
                    {
                        await DemoHttp.Error(context, 403, "loopback_required");
                        return;
                    }
                    if (!string.Equals(context.Request.Host.Value, expectedHost, StringComparison.Ordinal))
                    {
                        await DemoHttp.Error(context, 400, "host_not_allowed");
                        return;
                    }
                    if (context.Request.QueryString.Value?.Length > 2048)
                    {
                        await DemoHttp.Error(context, 400, "query_too_large");
                        return;
                    }
                    var mutating = !HttpMethods.IsGet(context.Request.Method) && !HttpMethods.IsHead(context.Request.Method);
                    if (context.Request.Headers["Sec-Fetch-Site"].ToString() == "cross-site")
                    { await DemoHttp.Error(context, 403, "same_origin_required"); return; }
                    if (mutating && !string.Equals(context.Request.Headers.Origin.ToString(), origin, StringComparison.Ordinal))
                    {
                        await DemoHttp.Error(context, 403, "same_origin_required");
                        return;
                    }
                    var path = context.Request.Path.Value ?? "/";
                    if (!StaticAssets.SafeRequest(context))
                    { await DemoHttp.Error(context, 404, "not_found"); return; }
                    if (!context.Request.Path.StartsWithSegments("/api") && mutating)
                    { context.Response.Headers.Allow = "GET, HEAD"; await DemoHttp.Error(context, 405, "method_not_allowed"); return; }
                    var session = sessions.Find(context);
                    if (session is not null)
                        context.Items[DemoSessions.ContextKey] = session;
                    var publicSession = path == "/api/session" &&
                        (HttpMethods.IsGet(context.Request.Method) || HttpMethods.IsPost(context.Request.Method));
                    if (context.Request.Path.StartsWithSegments("/api") && !publicSession)
                    {
                        if (session is null)
                        {
                            await DemoHttp.Error(context, 401, "authentication_required");
                            return;
                        }
                        if (mutating && !sessions.ValidCsrf(context, session))
                        {
                            await DemoHttp.Error(context, 403, "csrf_required");
                            return;
                        }
                        if (path == "/api/posture" && mutating)
                        {
                            context.Response.Headers.Allow = "GET, HEAD";
                            await DemoHttp.Error(context, 405, "method_not_allowed");
                            return;
                        }
                        // Contributor sessions have only assignment-scoped intake surfaces.
                        // Legacy global graph/report/state APIs cannot disclose other responses.
                        if(IntakeWorkflow.Contributor(session.PrincipalId) && path!="/api/logout" &&
                            !(HttpMethods.IsGet(context.Request.Method) && path is "/api/assessments" or "/api/assessments/catalog") &&
                            !System.Text.RegularExpressions.Regex.IsMatch(path,"^/api/assessments/assessment-[a-f0-9]{32}/(?:intake|questionnaires|discovery)(?:/|$)"))
                        {
                            await DemoHttp.Error(context,403,"assessment_forbidden");return;
                        }
                    }
                    await next(context);
                }
                catch (DemoHttpException error)
                {
                    await DemoHttp.Error(context, error.Status, error.Code);
                }
                catch (DemoValidationException error)
                {
                    await DemoHttp.Error(context, error.Code switch
                    {
                        "assessment_forbidden" => 403,
                        "assessment_not_found" => 404,
                        _ => 400
                    }, error.Code);
                }
                catch (DemoConflictException error)
                {
                    await DemoHttp.Error(context, 409, error.Code);
                }
                catch (DemoStoreException error)
                {
                    await DemoHttp.Error(context, 503, error.Code);
                }
                catch (Microsoft.Data.Sqlite.SqliteException error) when (error.SqliteErrorCode == 13)
                {
                    // SQLITE_FULL: transactional command disposal rolls back before
                    // this boundary. Preserve the request identity for a safe retry.
                    await DemoHttp.Error(context, 503, "demo_database_capacity_exceeded");
                }
                catch (Microsoft.AspNetCore.Http.BadHttpRequestException)
                {
                    await DemoHttp.Error(context, 400, "invalid_request");
                }
                catch (OperationCanceledException) when (context.RequestAborted.IsCancellationRequested)
                {
                    context.Abort();
                }
                catch (Exception)
                {
                    // Never echo exception details, raw records, request bodies,
                    // SQL, credentials, or private paths to HTTP or console logs.
                    await DemoHttp.Error(context, 500, "internal_error");
                }
            });

            app.MapGet("/health/live", () => Results.Json(new { live = true, profile = "synthetic-only" }));
            app.MapGet("/health/ready", () =>
            {
                var metadata = store.Metadata();
                var ready = metadata["synthetic"]?.GetValue<bool>() == true &&
                    metadata["assetCount"]?.GetValue<int>() > 0 &&
                    !string.IsNullOrEmpty(metadata["baselineId"]?.GetValue<string>());
                return Results.Json(new { ready, profile = "synthetic-only", enterpriseReady = false },
                    statusCode: ready ? 200 : 503);
            });

            app.MapGet("/api/session", (HttpContext context) =>
                Results.Json(DemoSessions.View(DemoSessions.Current(context))));
            app.MapPost("/api/session", async (HttpContext context) =>
            {
                sessions.AdmitLogin();
                var body = await DemoHttp.ReadClosedBody(context, "role", "password");
                var role = DemoHttp.RequiredText(body, "role", 32);
                var password = DemoHttp.RequiredText(body, "password", 64);
                if (!DemoSessions.Personas.ContainsKey(role) || password != "synthetic-demo-only")
                    throw new DemoHttpException(401, "invalid_demo_identity");
                var session = sessions.Create(context, role);
                return Results.Json(DemoSessions.View(session));
            });
            app.MapPost("/api/logout", (HttpContext context) =>
            {
                sessions.Remove(context);
                return Results.Json(new { authenticated = false, synthetic = true });
            });

            app.MapGet("/api/dashboard", () => Results.Json(store.Dashboard()));
            app.MapGet("/api/analysis", (HttpContext context) => Results.Json(store.Analysis(new AnalysisFilter(
                DemoHttp.QueryText(context, "service", 160), DemoHttp.QueryText(context, "owner", 160),
                DemoHttp.QueryText(context, "environment", 160), DemoHttp.QueryText(context, "technology", 160),
                DemoHttp.QueryText(context, "family", 80)))));
            app.MapGet("/api/actions", () => Results.Json(store.Actions()));
            app.MapGet("/api/actions/{findingId}", (string findingId) =>
            {
                DemoHttp.Identifier(findingId);
                return Results.Json(store.ActionHistory(findingId));
            });
            app.MapPost("/api/actions/{findingId}", async (string findingId, HttpContext context) =>
            {
                DemoHttp.Identifier(findingId);
                if (DemoSessions.Current(context)!.Role != "analyst") throw new DemoHttpException(403, "analyst_role_required");
                sessions.AdmitAction();
                var key = context.Request.Headers["Idempotency-Key"].ToString();
                DemoHttp.IdempotencyKey(key);
                var body = await DemoHttp.ReadClosedBody(context, "operation", "disposition", "note", "expectedRevision");
                var operation = DemoHttp.RequiredText(body, "operation", 40);
                string? disposition = body["disposition"] is null ? null : DemoHttp.RequiredText(body, "disposition", 32);
                if (body["note"] is not JsonValue noteValue || !noteValue.TryGetValue<string>(out var note) || note.Length > 800 ||
                    note.Any(c => char.IsControl(c) && c is not ('\n' or '\r' or '\t')))
                    throw new DemoHttpException(400, "invalid_review_note");
                if (body["expectedRevision"] is not JsonValue revisionValue || !revisionValue.TryGetValue<int>(out var revision) || revision < 0)
                    throw new DemoHttpException(400, "invalid_expected_revision");
                // Historical annotations remain readable, but never become a
                // backdoor around assessment-specific command admission.
                return Results.Json(new { error = new { code = "assessment_context_required" } }, statusCode: 409);
            });
            app.MapGet("/api/sources", () => Results.Json(store.Sources()));
            app.MapGet("/api/assets", (HttpContext context) => Results.Json(store.Assets(
                DemoHttp.QueryText(context, "q", 200),
                DemoHttp.QueryText(context, "family", 80),
                DemoHttp.QueryText(context, "status", 40),
                DemoHttp.QueryInt(context, "page", 1, 1, 10000),
                DemoHttp.QueryInt(context, "pageSize", 25, 1, 100))));
            app.MapGet("/api/assets/{id}", (string id) =>
            {
                DemoHttp.Identifier(id);
                var asset = store.Asset(id);
                return asset is null ? DemoHttp.NotFound() : Results.Json(asset);
            });
            app.MapGet("/api/reports", () => Results.Json(store.Reports()));
            app.MapGet("/api/runs", () => Results.Json(store.Runs()));
            app.MapPost("/api/reports", async (HttpContext context) =>
            {
                var session = DemoSessions.Current(context)!;
                if (session.Role != "analyst")
                    throw new DemoHttpException(403, "analyst_role_required");
                sessions.AdmitReport();
                var key = context.Request.Headers["Idempotency-Key"].ToString();
                DemoHttp.IdempotencyKey(key);
                var body = await DemoHttp.ReadClosedBody(context, "phase");
                if (body["phase"] is not JsonValue value || !value.TryGetValue<int>(out var phase) || (phase != 1 && phase != 2))
                    throw new DemoHttpException(400, "invalid_report_phase");
                return Results.Json(new { error = new { code = "assessment_context_required" } }, statusCode: 409);
            });
            app.MapGet("/api/reports/{id}", (string id) =>
            {
                DemoHttp.Identifier(id);
                var report = store.Report(id);
                return report is null ? DemoHttp.NotFound() : Results.Json(report);
            });
            app.MapGet("/api/reports/{id}/download", (string id, HttpContext context) =>
            {
                DemoHttp.Identifier(id);
                var format = DemoHttp.QueryText(context, "format", 8) ?? "html";
                if (format != "html" && format != "json")
                    throw new DemoHttpException(400, "invalid_report_format");
                var report = store.Report(id);
                if (report is null)
                    return DemoHttp.NotFound();
                if (format == "html")
                {
                    var html = store.RenderReportHtml(id)!;
                    context.Response.Headers["Content-Security-Policy"] = DemoHttp.ReportContentSecurityPolicy(html);
                    context.Response.Headers["Content-Disposition"] = $"inline; filename=\"pqc-synthetic-{id}.html\"";
                    return Results.Content(html, "text/html; charset=utf-8");
                }
                context.Response.Headers["Content-Disposition"] = $"attachment; filename=\"pqc-synthetic-{id}.json\"";
                return Results.Json(report);
            });

            app.MapAssessmentEndpoints(store, sessions);
            app.MapReferenceEndpoints();
            app.MapCapacityEndpoints();
            app.MapMethods("/healthz", ["GET", "HEAD"], () => Results.Json(new { status = "ok" }));
            app.MapMethods("/readyz", ["GET", "HEAD"], () =>
            {
                var metadata = store.Metadata();
                var ready = metadata["synthetic"]?.GetValue<bool>() == true && metadata["assetCount"]?.GetValue<int>() > 0 && !string.IsNullOrEmpty(metadata["baselineId"]?.GetValue<string>());
                return Results.Json(new { status = ready ? "ready" : "not_ready", enterpriseReady = false }, statusCode: ready ? 200 : 503);
            });
            app.MapIntakeEndpoints(store,sessions);
            app.MapQuestionnaireEndpoints(store,sessions);
            app.MapQuestionnaireExchangeEndpoints(store,sessions);
            app.MapDiscoveryEndpoints(store,sessions);
            app.MapDiscoveryExchangeEndpoints(store,sessions);
            app.MapDiscoveryCollectionEndpoints(store,sessions);
            app.MapDiscoveryEvidenceEndpoints(store,sessions);
            app.MapWorkspaceEndpoints(store,sessions);

            app.Use(async (context, next) =>
            {
                var path = context.Request.Path.Value ?? "/";
                if (!path.StartsWith("/api", StringComparison.Ordinal) && staticAssets.Find(path) is { } asset)
                {
                    await staticAssets.Send(context, path, asset);
                    return;
                }
                await next(context);
            });
            // No SPA fallback for mistyped APIs, health paths, or static assets.
            app.MapFallback(async context =>
            {
                if (context.Request.Path.StartsWithSegments("/api") || context.Request.Path.StartsWithSegments("/health") ||
                    context.Request.Path.StartsWithSegments("/assets") || Path.HasExtension(context.Request.Path.Value))
                {
                    await DemoHttp.Error(context, 404, "not_found");
                    return;
                }
                var index = staticAssets.Find("/");
                if (index is null)
                {
                    await DemoHttp.Error(context, 503, "frontend_not_built");
                    return;
                }
                await staticAssets.Send(context, "/", index);
            });

            Console.WriteLine($"PQC synthetic-only development host: {origin}; no enterprise identity or source-system authority.");
            await app.RunAsync();
            return 0;
        }
        catch (DemoHttpException error)
        {
            Console.Error.WriteLine($"PQC demo startup refused: {error.Code}");
            return 2;
        }
        catch (DemoStoreException error)
        {
            Console.Error.WriteLine($"PQC demo startup refused: {error.Code}");
            return 2;
        }
        catch (Microsoft.Data.Sqlite.SqliteException error) when (error.SqliteErrorCode == 13)
        {
            Console.Error.WriteLine("PQC demo startup refused: demo_database_capacity_exceeded");
            return 2;
        }
        catch (Exception)
        {
            Console.Error.WriteLine("PQC demo startup failed: configuration_or_store_unavailable");
            return 2;
        }
    }
}
