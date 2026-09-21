using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

/// <summary>Application authority port. The initial implementation is an isolated
/// synthetic SQLite adapter; an enterprise SQL Server adapter must prove this
/// contract independently before any deployment selection is claimed.</summary>
public interface IEnterpriseStore : IDisposable
{
    JsonObject Metadata();
    JsonObject Dashboard();
    JsonObject Assets(string? q, string? family, string? status, int page, int pageSize);
    JsonObject? Asset(string id);
    JsonArray Sources();
    JsonArray Reports();
    JsonObject CreateReport(string phase, string idempotencyKey, string actor);
    JsonObject? Report(string id);
    string? RenderReportHtml(string id);
    JsonArray Runs();
    JsonObject Analysis(AnalysisFilter? filter = null);
    JsonArray Actions();
    JsonArray ActionHistory(string findingId);
    JsonObject RecordAction(string findingId, string operation, string? disposition, string note, int expectedRevision, string idempotencyKey, string actor);
    void Backup(string destination);
}
