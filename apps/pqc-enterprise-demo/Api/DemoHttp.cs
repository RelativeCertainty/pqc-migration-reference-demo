using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo.Api;

internal sealed class DemoHttpException(int status, string code) : Exception(code)
{
    public int Status { get; } = status;
    public string Code { get; } = code;
}

internal static class DemoHttp
{
    public static string ReportContentSecurityPolicy(string html)
    {
        // The owned renderer emits one fixed CSS block. Authorize only those
        // exact bytes rather than weakening the application's style policy.
        const string opening = "<style>";
        const string closing = "</style>";
        var start = html.IndexOf(opening, StringComparison.Ordinal);
        var end = start < 0 ? -1 : html.IndexOf(closing, start + opening.Length, StringComparison.Ordinal);
        if (start < 0 || end < start || end - start > 65536 ||
            html.IndexOf(opening, end + closing.Length, StringComparison.Ordinal) >= 0)
            throw new DemoHttpException(500, "report_style_contract_invalid");
        var css = html[(start + opening.Length)..end];
        var digest = Convert.ToBase64String(SHA256.HashData(Encoding.UTF8.GetBytes(css)));
        return $"default-src 'none'; style-src 'sha256-{digest}'; base-uri 'none'; " +
            "form-action 'none'; frame-ancestors 'none'; object-src 'none'";
    }

    public static async Task Error(HttpContext context, int status, string code)
    {
        if (context.Response.HasStarted)
        {
            context.Abort();
            return;
        }
        context.Response.StatusCode = status;
        if (status == 429)
            context.Response.Headers["Retry-After"] = "60";
        await context.Response.WriteAsJsonAsync(new { error = new { code } }, context.RequestAborted);
    }

    public static IResult NotFound() => Results.Json(new { error = new { code = "not_found" } }, statusCode: 404);

    public static Task<JsonObject> ReadClosedBody(HttpContext context, params string[] fields) => ReadBoundedClosedBody(context, 2048, fields);

    public static async Task<JsonObject> ReadBoundedClosedBody(HttpContext context, int byteLimit, params string[] fields)
    {
        if (!context.Request.HasJsonContentType())
            throw new DemoHttpException(415, "json_content_type_required");
        if (context.Request.ContentLength > byteLimit)
            throw new DemoHttpException(413, "request_body_too_large");
        using var buffer = new MemoryStream();
        var block = new byte[512];
        int read;
        while ((read = await context.Request.Body.ReadAsync(block, context.RequestAborted)) > 0)
        {
            if (buffer.Length + read > byteLimit)
                throw new DemoHttpException(413, "request_body_too_large");
            buffer.Write(block, 0, read);
        }
        try
        {
            using var document = JsonDocument.Parse(buffer.ToArray(), new JsonDocumentOptions { MaxDepth = 6 });
            if (document.RootElement.ValueKind != JsonValueKind.Object)
                throw new DemoHttpException(400, "invalid_request_body");
            var seen = new HashSet<string>(StringComparer.Ordinal);
            foreach (var item in document.RootElement.EnumerateObject())
                if (!fields.Contains(item.Name, StringComparer.Ordinal) || !seen.Add(item.Name))
                    throw new DemoHttpException(400, "unexpected_request_field");
            if (fields.Any(field => !seen.Contains(field)))
                throw new DemoHttpException(400, "missing_request_field");
            RejectDuplicateMembers(document.RootElement);
            return JsonNode.Parse(document.RootElement.GetRawText())!.AsObject();
        }
        catch (JsonException)
        {
            throw new DemoHttpException(400, "invalid_json");
        }
    }

    private static void RejectDuplicateMembers(JsonElement element)
    {
        if (element.ValueKind == JsonValueKind.Object)
        {
            var seen = new HashSet<string>(StringComparer.Ordinal);
            foreach (var item in element.EnumerateObject())
            {
                if (!seen.Add(item.Name)) throw new DemoHttpException(400, "duplicate_request_field");
                RejectDuplicateMembers(item.Value);
            }
        }
        else if (element.ValueKind == JsonValueKind.Array)
            foreach (var item in element.EnumerateArray()) RejectDuplicateMembers(item);
    }

    public static string RequiredText(JsonObject body, string field, int max)
    {
        if (body[field] is not JsonValue value || !value.TryGetValue<string>(out var text) ||
            string.IsNullOrWhiteSpace(text) || text.Length > max || text.Any(char.IsControl))
            throw new DemoHttpException(400, "invalid_request_field");
        return text;
    }

    public static string? QueryText(HttpContext context, string field, int max)
    {
        if (!context.Request.Query.TryGetValue(field, out var values))
            return null;
        if (values.Count != 1 || values[0]?.Length > max || values[0]?.Any(char.IsControl) == true)
            throw new DemoHttpException(400, "invalid_query");
        return string.IsNullOrWhiteSpace(values[0]) ? null : values[0];
    }

    public static int QueryInt(HttpContext context, string field, int fallback, int min, int max)
    {
        var value = QueryText(context, field, 8);
        if (value is null)
            return fallback;
        if (!int.TryParse(value, NumberStyles.None, CultureInfo.InvariantCulture, out var result) || result < min || result > max)
            throw new DemoHttpException(400, "invalid_pagination");
        return result;
    }

    public static void Identifier(string value)
    {
        if (value.Length is < 1 or > 160 || !value.All(c => char.IsAsciiLetterOrDigit(c) || c is '-' or '_' or '.' or ':'))
            throw new DemoHttpException(400, "invalid_identifier");
    }

    public static void IdempotencyKey(string value)
    {
        if (value.Length is < 8 or > 96 || !value.All(c => char.IsAsciiLetterOrDigit(c) || c is '-' or '_' or '.' or ':'))
            throw new DemoHttpException(400, "invalid_idempotency_key");
    }
}
