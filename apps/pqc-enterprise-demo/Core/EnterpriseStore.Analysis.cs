using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

public sealed partial class EnterpriseStore
{
    public JsonObject Analysis(AnalysisFilter? filter = null)
    {
        lock (gate)
        {
            EnsureOpen();
            var projection = new JsonObject
            {
                ["baseline"] = Metadata(),
                ["method"] = ParseObject(Scalar("SELECT method_json FROM baselines WHERE id=$id", ("$id", baselineId))!.ToString()!)
            };
            foreach (var kind in Kinds) projection[kind] = Array(ReadRows(kind));
            return AnalysisProjection.Build(projection, filter);
        }
    }
}
