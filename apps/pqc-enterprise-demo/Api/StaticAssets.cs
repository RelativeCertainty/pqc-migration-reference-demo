using System.Security.Cryptography;
using System.Text;
using Microsoft.AspNetCore.Http.Features;
using Microsoft.AspNetCore.StaticFiles;
using PqcEnterpriseDemo.Api;

namespace PqcEnterpriseDemo;

/// <summary>Port of the Go asset integrity boundary, with one immutable in-memory UI snapshot.</summary>
public sealed class StaticAssets
{
    private readonly Dictionary<string, byte[]> files = new(StringComparer.Ordinal);
    public string? ManifestSha256 { get; private set; }
    private const string Manifest = "asset-manifest.sha256";
    private static bool SafeName(string name) => name.Length > 0 && !name.Contains('\\') &&
        !name.Split('/').Any(part => part.Length == 0 || part.StartsWith('.')) &&
        !name.EndsWith(".map", StringComparison.OrdinalIgnoreCase) && name != "_headers";

    public static StaticAssets Load(string root)
    {
        var result = new StaticAssets();
        if ((File.GetAttributes(root) & FileAttributes.ReparsePoint) != 0)
            throw new DemoHttpException(400, "unsafe_ui_path");
        var paths = new List<string>();
        void Visit(string directory)
        {
            foreach (var entry in Directory.EnumerateFileSystemEntries(directory))
            {
                var attributes = File.GetAttributes(entry);
                if ((attributes & FileAttributes.ReparsePoint) != 0) throw new DemoHttpException(400, "unsafe_ui_path");
                if ((attributes & FileAttributes.Directory) != 0) Visit(entry); else paths.Add(entry);
                if (paths.Count > 2048) throw new DemoHttpException(400, "ui_size_limit");
            }
        }
        Visit(root);
        long bytes = 0;
        foreach (var path in paths)
        {
            var name = Path.GetRelativePath(root, path).Replace(Path.DirectorySeparatorChar, '/');
            if (!SafeName(name)) throw new DemoHttpException(400, "unsafe_ui_asset");
            bytes += new FileInfo(path).Length;
            if (bytes > 32 * 1024 * 1024) throw new DemoHttpException(400, "ui_size_limit");
            result.files.Add(name, File.ReadAllBytes(path));
        }
        if (result.files.Remove(Manifest, out var manifest))
        {
            var expected = new HashSet<string>(StringComparer.Ordinal);
            foreach (var line in Encoding.UTF8.GetString(manifest).TrimEnd('\n').Split('\n'))
            {
                var parts = line.Split("  ", 2, StringSplitOptions.None);
                if (parts.Length != 2 || !SafeName(parts[1]) || !expected.Add(parts[1]) ||
                    !result.files.TryGetValue(parts[1], out var content) ||
                    parts[0] != Convert.ToHexStringLower(SHA256.HashData(content)))
                    throw new DemoHttpException(400, "ui_manifest_mismatch");
            }
            if (!expected.SetEquals(result.files.Keys) || !expected.Contains("index.html"))
                throw new DemoHttpException(400, "ui_manifest_incomplete");
            result.ManifestSha256 = Convert.ToHexStringLower(SHA256.HashData(manifest));
        }
        return result;
    }

    public static bool SafeRequest(HttpContext context)
    {
        var decoded = context.Request.Path.Value ?? "/";
        var raw = (context.Features.Get<IHttpRequestFeature>()?.RawTarget ?? decoded).Split('?')[0];
        if (decoded.Contains('\\') || decoded.Any(char.IsControl) ||
            new[] { "%00", "%2e", "%2f", "%5c" }.Any(value => raw.Contains(value, StringComparison.OrdinalIgnoreCase))) return false;
        var segments = decoded.Trim('/').Split('/');
        if (segments.Any(part => part.StartsWith('.')) || decoded.Contains("//")) return false;
        return decoded != "/_headers" && !decoded.EndsWith('/' + Manifest, StringComparison.Ordinal) &&
            !decoded.EndsWith(".map", StringComparison.OrdinalIgnoreCase);
    }

    public byte[]? Find(string path) => files.GetValueOrDefault(path == "/" ? "index.html" : path.TrimStart('/'));

    public async Task Send(HttpContext context, string path, byte[] content)
    {
        var provider = new FileExtensionContentTypeProvider();
        provider.TryGetContentType(path == "/" ? "index.html" : path, out var type);
        context.Response.ContentType = type ?? "application/octet-stream";
        context.Response.ContentLength = content.Length;
        if (ManifestSha256 is not null) context.Response.Headers["X-PQC-UI-Manifest"] = ManifestSha256;
        if (!HttpMethods.IsHead(context.Request.Method)) await context.Response.Body.WriteAsync(content, context.RequestAborted);
    }
}
