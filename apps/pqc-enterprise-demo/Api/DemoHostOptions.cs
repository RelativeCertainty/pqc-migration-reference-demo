using System.Globalization;

namespace PqcEnterpriseDemo.Api;

internal sealed record DemoHostOptions(string DataDirectory, string FixturePath, string WebRoot, int Port, string? BackupDirectory)
{
    public static DemoHostOptions Parse(string[] args)
    {
        var flags = new Dictionary<string, string>(StringComparer.Ordinal);
        for (var index = 0; index < args.Length; index += 2)
        {
            if (index + 1 >= args.Length || args[index] is not ("--data-dir" or "--fixture" or "--web-root" or "--port" or "--backup-dir") ||
                !flags.TryAdd(args[index], args[index + 1]))
                throw new DemoHttpException(400, "invalid_startup_arguments");
        }
        if (!flags.TryGetValue("--data-dir", out var data) || !flags.TryGetValue("--fixture", out var fixture))
            throw new DemoHttpException(400, "explicit_data_and_fixture_required");
        var backup = flags.GetValueOrDefault("--backup-dir");
        if (backup is not null && (flags.ContainsKey("--web-root") || flags.ContainsKey("--port")))
            throw new DemoHttpException(400, "backup_is_operator_only");
        var webRoot = flags.GetValueOrDefault("--web-root", Path.Combine(AppContext.BaseDirectory, "wwwroot"));
        foreach (var path in new[] { data, fixture, backup ?? webRoot })
            if (!Path.IsPathFullyQualified(path) || !string.Equals(Path.GetFullPath(path), path.TrimEnd(Path.DirectorySeparatorChar), StringComparison.Ordinal))
                throw new DemoHttpException(400, "absolute_canonical_paths_required");
        if (!Directory.Exists(data) || !File.Exists(fixture) || (backup is null && !Directory.Exists(webRoot)))
            throw new DemoHttpException(400, "explicit_paths_must_exist");
        if (data == Path.GetPathRoot(data) || new DirectoryInfo(data).LinkTarget is not null || new FileInfo(fixture).LinkTarget is not null)
            throw new DemoHttpException(400, "unsafe_runtime_path");
        var portText = flags.GetValueOrDefault("--port", "18473");
        if (!int.TryParse(portText, NumberStyles.None, CultureInfo.InvariantCulture, out var port) || port is < 1024 or > 65535 || port == 5432)
            throw new DemoHttpException(400, "invalid_loopback_port");
        return new DemoHostOptions(data, fixture, webRoot, port, backup);
    }
}
