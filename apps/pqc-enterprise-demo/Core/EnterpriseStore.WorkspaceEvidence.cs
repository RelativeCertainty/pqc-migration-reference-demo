using System.Security.Cryptography;
using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

public sealed partial class EnterpriseStore
{
    public JsonObject StageWorkspaceEvidence(string id,string requestId,string productId,int revision,string key,string principal,byte[] original,JsonObject parsed)
    {
        if(original.Length is <2 or >32768)throw new DemoValidationException("workspace_evidence_limit");
        var sha=Convert.ToHexStringLower(SHA256.HashData(original));
        lock(gate)
        {
            var bundleId="wbundle-"+AssessmentWorkflow.Hash(new{id,requestId,productId,sha})[..24];
            var command=new AssessmentCommand("workspace_stage_evidence",requestId,new(){["productId"]=productId,["artifactSha256"]=sha},revision,key);
            var state=WorkspaceCommit(id,command,principal,s=>
            {
                DiscoveryEvidence.RequireGates(s);var request=DiscoveryWorkflow.Request(s,requestId,principal);
                if(!s.Scope.IncludedFamilyIds.Contains(request.FamilyId))throw new DemoConflictException("workspace_source_not_in_scope");
                var sourceFamily=WText(parsed,"familyId");
                if(!s.Scope.IncludedFamilyIds.Contains(sourceFamily))throw new DemoConflictException("workspace_source_not_in_scope");
                if(request.Status!="submitted")throw new DemoConflictException("workspace_response_required");
                var product=WorkspaceFind(s,"workspace_products",productId);
                if(WText(product,"requestId")!=requestId)throw new DemoValidationException("workspace_product_scope_invalid");
                if(WText(WorkspaceFind(s,"workspace_receipts",WText(product,"receiptId")),"status")!="applied")throw new DemoConflictException("workspace_receipt_review_required");
                if(WorkspaceRows(s,"workspace_bundles").Any(b=>WText(b,"id")==bundleId))throw new DemoConflictException("workspace_evidence_duplicate");
                var parsedRows=Rows(parsed,"observations");
                if(parsedRows.Count is <1 or >32||WorkspaceRows(s,"workspace_observations").Count+parsedRows.Count>512)throw new DemoConflictException("workspace_evidence_capacity_limit");
                var identity=WorkspaceRows(s,"workspace_identities").SingleOrDefault(i=>WText(i,"productId")==productId);
                var canonical=identity is null?"":WText(identity,"canonicalId");var kind=WText(parsed,"kind");var now=DateTimeOffset.UtcNow.ToString("O");
                var sourceId="wsource-"+AssessmentWorkflow.Hash(new{s.Id,sourceFamily,kind,source=WText(parsed,"sourceId")})[..24];
                var bundle=new JsonObject{["id"]=bundleId,["bundleId"]=bundleId,["requestId"]=requestId,["productId"]=productId,["canonicalId"]=canonical,["kind"]=kind,
                    ["familyId"]=sourceFamily,["productLabel"]=WText(product,"deployment",WText(product,"product")),["product"]=WText(product,"product"),["environment"]=WText(product,"environment"),
                    ["sourceId"]=sourceId,["sourceLabel"]=WText(parsed,"sourceLabel"),["collectedAt"]=WText(parsed,"collectedAt"),["artifactSha256"]=sha,["status"]="staged",["stagedBy"]=principal,["stagedAt"]=now,["reviewedBy"]="",["reviewRationale"]=""};
                var effects=new List<(string Table,JsonObject Record)>{("workspace_bundles",bundle)};
                foreach(var item in parsedRows)
                {
                    var record=(JsonObject)item.DeepClone();var nativeId=WText(record,"nativeId");
                    var subject=WorkspaceEvidenceSubject(s.Id,canonical,productId,kind,nativeId,WText(record,"nativeSubjectRef"));
                    record["id"]="wobservation-"+AssessmentWorkflow.Hash(new{bundleId,nativeId})[..24];record["systemId"]=subject;record["sourceSystemId"]=sourceId;
                    record["requestId"]=requestId;record["bundleId"]=bundleId;record["productId"]=productId;record["canonicalId"]=canonical;record["kind"]=kind;record["collectedAt"]=WText(parsed,"collectedAt");record["artifactSha256"]=sha;
                    effects.Add(("workspace_observations",record));
                }
                return effects;
            },original);
            return new JsonObject{["assessmentId"]=id,["revision"]=state.Revision,["case"]=WorkspaceCase(state,requestId,principal),["effect"]="Synthetic source facts staged for independent technical review; not yet part of the accepted evidence set."};
        }
    }

    private List<(string Table,JsonObject Record)> WorkspaceEvidenceCommand(AssessmentState state,AssessmentCommand command,string principal)
    {
        var bundle=WorkspaceFind(state,"workspace_bundles",command.TargetId??"");var requestId=WText(bundle,"requestId");
        var request=DiscoveryWorkflow.Request(state,requestId,principal);
        if(!state.Scope.IncludedFamilyIds.Contains(request.FamilyId))throw new DemoConflictException("workspace_source_not_in_scope");
        if(!state.Scope.IncludedFamilyIds.Contains(WText(bundle,"familyId")))throw new DemoConflictException("workspace_source_not_in_scope");
        var effects=new List<(string Table,JsonObject Record)>();
        if(command.Operation=="workspace_review_evidence")
        {
            WClosed(command.Fields,"determination","rationale","recordDecisions");
            if(AssessmentWorkflow.Role(state,principal)!="technical-reviewer"||WText(bundle,"stagedBy")==principal)throw new DemoValidationException("workspace_independent_review_required");
            if(WText(bundle,"status") is not("staged" or "identity_review_required"))throw new DemoConflictException("workspace_evidence_reviewed");
            var determination=WField(command.Fields,"determination",32,true);if(determination is not("qualified" or "needs_clarification"))throw new DemoValidationException("workspace_determination_invalid");
            var observations=WorkspaceRows(state,"workspace_observations",requestId).Where(o=>WText(o,"bundleId")==WText(bundle,"id")).ToArray();
            var decisions=command.Fields["recordDecisions"] as JsonArray??new JsonArray();
            if(decisions.Count>observations.Length)throw new DemoValidationException("workspace_record_decisions_invalid");
            var ids=new HashSet<string>(StringComparer.Ordinal);
            foreach(var node in decisions)
            {
                if(node is not JsonObject entry)throw new DemoValidationException("workspace_record_decisions_invalid");
                WClosed(entry,"observationId","determination","rationale");var observationId=WField(entry,"observationId",160,true);
                if(!observations.Any(o=>WText(o,"id")==observationId)||!ids.Add(observationId))throw new DemoValidationException("workspace_record_scope_invalid");
                if(WField(entry,"determination",32,true) is not("supports_claim" or "conflict" or "cannot_establish"))throw new DemoValidationException("workspace_record_determination_invalid");
                _=WField(entry,"rationale",2048,true);
            }
            if(determination=="qualified"&&ids.Count!=observations.Length)throw new DemoConflictException("workspace_each_record_review_required");
            if(determination=="qualified"&&bundle["bindingReviewRequired"]?.GetValue<bool>()==true)
            {
                var canonical=WText(bundle,"proposedCanonicalId");
                foreach(var observation in observations)
                {
                    var revised=(JsonObject)observation.DeepClone();var nativeId=WText(revised,"nativeId");var kind=WText(revised,"kind");var productId=WText(revised,"productId");
                    revised["captureCanonicalId"]=revised["captureCanonicalId"]?.DeepClone()??JsonValue.Create(WText(revised,"canonicalId"));
                    revised["previousBindingRevision"]=revised["revision"]!.DeepClone();revised["canonicalId"]=canonical;
                    revised["systemId"]=WorkspaceEvidenceSubject(state.Id,canonical,productId,kind,nativeId,WText(revised,"nativeSubjectRef"));
                    revised["bindingReviewedBy"]=principal;effects.Add(("workspace_observations",revised));
                }
                bundle["captureCanonicalId"]=bundle["captureCanonicalId"]?.DeepClone()??JsonValue.Create(WText(bundle,"canonicalId"));bundle["canonicalId"]=canonical;bundle["bindingReviewRequired"]=false;bundle["bindingReviewedBy"]=principal;
            }
            var rationale=WField(command.Fields,"rationale",4096,true);bundle["status"]=determination;bundle["reviewedBy"]=principal;bundle["reviewedAt"]=DateTimeOffset.UtcNow.ToString("O");bundle["reviewRationale"]=rationale;
            effects.Add(("workspace_technical_reviews",new JsonObject{["id"]="wreview-"+WText(bundle,"id"),["requestId"]=requestId,["bundleId"]=WText(bundle,"id"),["artifactSha256"]=WText(bundle,"artifactSha256"),["determination"]=determination,["rationale"]=rationale,["recordDecisions"]=decisions.DeepClone(),["reviewedBy"]=principal,["reviewedAt"]=bundle["reviewedAt"]!.DeepClone()}));
        }
        else
        {
            WClosed(command.Fields);WorkspaceLead(state,principal);DiscoveryEvidence.RequireGates(state);
            if(WText(bundle,"status")!="qualified"||WText(bundle,"reviewedBy").Length==0||WText(bundle,"reviewedBy")==WText(bundle,"stagedBy"))throw new DemoConflictException("workspace_review_required");
            bundle["status"]="admitted";bundle["admittedBy"]=principal;bundle["admittedAt"]=DateTimeOffset.UtcNow.ToString("O");
            var observations=WorkspaceRows(state,"workspace_observations",requestId).Where(o=>WText(o,"bundleId")==WText(bundle,"id")).ToArray();
            var source=state.Sources.Single(s=>s.FamilyId==WText(bundle,"familyId"));var package=state.Packages.Single(p=>p.FamilyId==WText(bundle,"familyId"));
            source.ObservationIds=source.ObservationIds.Concat(observations.Select(o=>WText(o,"id"))).Distinct().Order(StringComparer.Ordinal).ToList();
            source.SubjectIds=source.SubjectIds.Concat(observations.Select(o=>WText(o,"systemId"))).Distinct().Order(StringComparer.Ordinal).ToList();source.EvidenceOrigin="admitted_synthetic_workspace_sources";
            package.ObservationIds=[..source.ObservationIds];package.SubjectIds=[..source.SubjectIds];package.EvidenceCount=source.ObservationIds.Count;package.SubjectCount=source.SubjectIds.Count;
            package.Revision++;package.State="in_progress";package.SubmittedBy="";package.ReviewedBy="";package.Analysis.State="ready";
            package.LimitationCodes=package.LimitationCodes.Concat(new[]{"synthetic_workspace_evidence","independent_runtime_verification_missing"}).Distinct().ToList();
            if(!WorkspaceRows(state,"workspace_bundles").Any(b=>WText(b,"id")!=WText(bundle,"id")&&WText(b,"familyId")==WText(bundle,"familyId")&&b["bindingReviewRequired"]?.GetValue<bool>()==true))
                package.LimitationCodes.Remove("identity_binding_review_required");
        }
        effects.Add(("workspace_bundles",bundle));return effects;
    }

    private static string WorkspaceEvidenceSubject(string assessmentId,string canonical,string productId,string kind,string nativeId,string nativeSubject)
    {
        var deployment=canonical.Length>0?canonical:productId;
        // The registered dialect spans 27 native namespaces; matching a short
        // native ID across families cannot establish the same enterprise system.
        return "wsubject-"+(kind=="registered"
            ?AssessmentWorkflow.Hash(new{Id=assessmentId,deployment,kind,nativeSubject})
            :AssessmentWorkflow.Hash(new{Id=assessmentId,deployment,kind,nativeId}))[..24];
    }

    private List<(string Table,JsonObject Record)> WorkspaceInvalidateIdentityBinding(AssessmentState state,string requestId,string productId,string canonical,string principal)
    {
        var effects=new List<(string Table,JsonObject Record)>();
        var bundles=WorkspaceRows(state,"workspace_bundles",requestId).Where(b=>WText(b,"productId")==productId&&(WText(b,"canonicalId")!=canonical||b["bindingReviewRequired"]?.GetValue<bool>()==true)).ToArray();
        if(bundles.Length==0)return effects;
        var bundleIds=bundles.Select(b=>WText(b,"id")).ToHashSet(StringComparer.Ordinal);
        var observations=WorkspaceRows(state,"workspace_observations",requestId).Where(o=>bundleIds.Contains(WText(o,"bundleId"))).ToArray();
        var affectedIds=observations.Select(o=>WText(o,"id")).ToHashSet(StringComparer.Ordinal);
        var affectedSubjects=observations.Select(o=>WText(o,"systemId")).ToHashSet(StringComparer.Ordinal);
        var remainingBundles=WorkspaceRows(state,"workspace_bundles").Where(b=>WText(b,"status")=="admitted"&&!bundleIds.Contains(WText(b,"id"))).Select(b=>WText(b,"id")).ToHashSet(StringComparer.Ordinal);
        var remainingSubjects=WorkspaceRows(state,"workspace_observations").Where(o=>remainingBundles.Contains(WText(o,"bundleId"))).Select(o=>WText(o,"systemId")).ToHashSet(StringComparer.Ordinal);
        foreach(var bundle in bundles)
        {
            bundle["status"]="identity_review_required";bundle["bindingReviewRequired"]=true;bundle["proposedCanonicalId"]=canonical;
            bundle["identityChangedBy"]=principal;bundle["identityChangedAtRevision"]=state.Revision+1;
            bundle["identityChangeReason"]="The reviewed deployment identity changed. This bundle is excluded from current report/map inputs until independent binding review and lead re-admission; original capture and prior report versions are preserved.";
            effects.Add(("workspace_bundles",bundle));
        }
        foreach(var family in bundles.Select(b=>WText(b,"familyId")).Distinct(StringComparer.Ordinal))
        {
            var source=state.Sources.Single(s=>s.FamilyId==family);var package=state.Packages.Single(p=>p.FamilyId==family);
            source.ObservationIds=source.ObservationIds.Where(id=>!affectedIds.Contains(id)).ToList();
            source.SubjectIds=source.SubjectIds.Where(id=>!affectedSubjects.Contains(id)||remainingSubjects.Contains(id)).ToList();
            package.ObservationIds=[..source.ObservationIds];package.SubjectIds=[..source.SubjectIds];package.EvidenceCount=source.ObservationIds.Count;package.SubjectCount=source.SubjectIds.Count;
            package.Revision++;package.State="in_progress";package.SubmittedBy="";package.ReviewedBy="";package.Analysis.State="ready";
            package.LimitationCodes=package.LimitationCodes.Concat(new[]{"identity_binding_review_required"}).Distinct().ToList();
        }
        foreach(var consequence in WorkspaceRows(state,"workspace_consequences",requestId).Where(c=>WText(c,"status")=="recorded"))
        {
            var refs=(consequence["evidenceRefs"] as JsonArray??new()).Select(n=>n?.GetValue<string>()??"");
            if(WText(consequence,"productId")==productId||WText(consequence,"productId").Length==0||refs.Any(affectedIds.Contains))
            {
                consequence["status"]="needs_review";consequence["reviewReason"]="A relied-upon deployment binding changed; re-review this conclusion after technical binding review.";consequence["invalidatedAtRevision"]=state.Revision+1;
                effects.Add(("workspace_consequences",consequence));
            }
        }
        return effects;
    }
}
