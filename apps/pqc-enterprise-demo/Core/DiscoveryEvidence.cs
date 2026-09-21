using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

// A factual review is not a standards adoption, access approval or verification
// of a live connection. Each immutable source bundle has its own review record.
public sealed class DiscoveryEvidenceReview
{
    public string BatchId { get; set; } = "";
    public List<string> BatchIds { get; set; } = [];
    public string ProductRefId { get; set; } = "";
    public string ProductLabel { get; set; } = "";
    public string SourceLabel { get; set; } = "";
    public int ObservationCount { get; set; }
    public string ContentSha256 { get; set; } = "";
    public string StagedBy { get; set; } = "";
    public string StagedAt { get; set; } = "";
    public string Status { get; set; } = "staged";
    public string ReviewedBy { get; set; } = "";
    public string ReviewedAt { get; set; } = "";
    public string ReviewRationale { get; set; } = "";
    public string AdmittedBy { get; set; } = "";
    public string AdmittedAt { get; set; } = "";
}

public static class DiscoveryEvidence
{
    public static void RequireGates(AssessmentState state)
    {
        if (!AssessmentWorkflow.Passed(state,"PQC-G00") || !AssessmentWorkflow.Passed(state,"PQC-P1-G01"))
            throw new DemoConflictException("assessment_prerequisite_gate_required");
    }

    public static void Apply(AssessmentState state, AssessmentCommand command, string principal)
    {
        var investigation = state.Discovery.Investigations.SingleOrDefault(i => i.Id == command.TargetId)
            ?? throw new DemoValidationException("discovery_investigation_not_found");
        if(!state.Scope.IncludedFamilyIds.Contains(investigation.FamilyId))throw new DemoConflictException("discovery_source_not_in_scope");
        var f = command.Fields;
        AssessmentWorkflow.Closed(f, command.Operation == "discovery_review_evidence"
            ? ["batchId","determination","rationale"] : ["batchId"]);
        var bundle = investigation.EvidenceReviews.SingleOrDefault(b => b.BatchId == AssessmentWorkflow.Required(f,"batchId"))
            ?? throw new DemoValidationException("discovery_evidence_not_found");
        var role = AssessmentWorkflow.Role(state,principal);
        var now = DateTimeOffset.UtcNow.ToString("O");
        if (command.Operation == "discovery_review_evidence")
        {
            if (role != "technical-reviewer" || principal == bundle.StagedBy)
                throw new DemoValidationException("discovery_independent_review_required");
            if (bundle.Status != "staged") throw new DemoConflictException("discovery_evidence_already_reviewed");
            var determination = AssessmentWorkflow.Required(f,"determination");
            if (determination is not ("qualified" or "needs_clarification")) throw new DemoValidationException("discovery_determination_invalid");
            var rationale = AssessmentWorkflow.Required(f,"rationale");
            if (rationale.Length > 2048) throw new DemoValidationException("discovery_text_limit");
            bundle.Status=determination; bundle.ReviewedBy=principal; bundle.ReviewedAt=now; bundle.ReviewRationale=rationale;
        }
        else if (command.Operation == "discovery_admit_evidence")
        {
            if (role != "assessment-lead") throw new DemoValidationException("assessment_forbidden");
            RequireGates(state);
            if (bundle.Status != "qualified" || bundle.ReviewedBy.Length == 0 || bundle.ReviewedBy == bundle.StagedBy)
                throw new DemoConflictException("discovery_qualified_evidence_review_required");
            foreach (var batchId in bundle.BatchIds)
            {
                var batch = state.Intake.Batches.Single(b => b.Id == batchId && b.RequestId == investigation.IntakeRequestId);
                if (batch.ContentSha256 != bundle.ContentSha256 || batch.Status != "staged")
                    throw new DemoConflictException("discovery_evidence_binding_changed");
                batch.Status = "admitted";
            }
            bundle.Status="admitted";bundle.AdmittedBy=principal;bundle.AdmittedAt=now;
            AssessmentWorkflow.AdmitDiscoveryObservations(state,investigation.FamilyId,
                state.Intake.Batches.Where(b=>bundle.BatchIds.Contains(b.Id)).SelectMany(b=>b.Observations).ToArray());
        }
        else throw new DemoValidationException("discovery_operation_invalid");
    }

    // The legacy intake command must not become a bypass around the new bundle
    // review. Only the discovery controller admits discovery-owned batches.
    public static void RefuseLegacyAdmission(AssessmentState state, string batchId)
    {
        if (state.Discovery.Investigations.Any(i => i.EvidenceReviews.Any(b => b.BatchIds.Contains(batchId))))
            throw new DemoConflictException("discovery_evidence_use_reviewed_admission");
    }
}
