using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

/// <summary>
/// Versioned deterministic interpretation of an attributable synthetic baseline.
/// No source calls, evidence invention, risk acceptance, or effect authority.
/// Finding identity is independent of display filters and action dispositions.
/// </summary>
public static class AnalysisProjection
{
    private const string Unknown = "unknown";
    private const string MethodId = "evidence-linked-enterprise-analysis";
    private const string MethodVersion = "1.0.0";
    private static readonly JsonSerializerOptions JsonOptions = new() { PropertyNamingPolicy = JsonNamingPolicy.CamelCase };

    public static JsonObject Build(JsonObject baselineProjection, AnalysisFilter? filter = null)
    {
        filter ??= new AnalysisFilter();
        ValidateFilter(filter);
        var baseline = O(baselineProjection["baseline"]);
        if (baseline["synthetic"]?.GetValue<bool>() != true || S(baseline, "tenantId") != "synthetic-enterprise")
            throw new DemoValidationException("analysis_synthetic_baseline_required");
        var baselineId = S(baseline, "baselineId");
        var inventory = R(baselineProjection, "inventory");
        var observations = R(baselineProjection, "observations");
        var uses = R(baselineProjection, "riskReviews");
        var contexts = R(baselineProjection, "contextReviews");
        var limitations = R(baselineProjection, "limitations");
        var profiles = R(baselineProjection, "sourceProfiles");
        var areas = R(baselineProjection, "estateAreas");
        var dependencies = R(baselineProjection, "dependencies");
        var bySubject = observations.GroupBy(row => S(row, "subject_ref")).ToDictionary(g => g.Key, g => g.ToArray(), StringComparer.Ordinal);
        var usesBySubject = uses.GroupBy(row => S(row, "subject_ref")).ToDictionary(g => g.Key, g => g.ToArray(), StringComparer.Ordinal);
        var limitsBySubject = limitations.GroupBy(row => S(row, "subject_ref")).ToDictionary(g => g.Key, g => g.Select(r => S(r, "code")).Distinct().Order(StringComparer.Ordinal).ToArray(), StringComparer.Ordinal);
        var inventoryById = inventory.ToDictionary(row => S(row, "subject_ref"), StringComparer.Ordinal);
        var allAssets = inventory.Select(row => Asset(row, bySubject, usesBySubject, limitsBySubject, profiles, inventoryById))
            .OrderBy(asset => asset.Label, StringComparer.Ordinal).ThenBy(asset => asset.Id, StringComparer.Ordinal).ToArray();
        var selected = allAssets.Where(asset => Matches(asset, filter)).ToArray();
        var selectedIds = selected.Select(asset => asset.Id).ToHashSet(StringComparer.Ordinal);
        var selectedUses = uses.Where(row => selectedIds.Contains(S(row, "subject_ref"))).ToArray();
        var allFindings = allAssets.Select(asset => Finding(asset, usesBySubject.GetValueOrDefault(asset.Id) ?? [],
                limitsBySubject.GetValueOrDefault(asset.Id) ?? [], contexts.Any(c => S(c, "subject_ref") == asset.Id), baselineId))
            .Where(finding => finding is not null).Cast<AnalysisFinding>().ToArray();
        var findings = allFindings.Where(finding => selectedIds.Contains(finding.SubjectId)).OrderBy(f => PriorityOrder(f.Priority))
            .ThenBy(f => f.SubjectLabel, StringComparer.Ordinal).ThenBy(f => f.Id, StringComparer.Ordinal).ToArray();
        var riskScenarios = findings.Select(f => new AnalysisLinkedRecord(f.RiskScenarioId, f.SubjectId, ScenarioTitle(f),
            f.Implication + " This is a conditional assessment scenario, not proof of an attack or a prediction of a quantum-computer date.", f.ObservationRefs,
            f.Owner, "Validate the protection role, exposure path, relying parties and applicable lifetime with the accountable review functions.", f.Readiness, f.EvidenceState)).ToArray();
        var assetsById = allAssets.ToDictionary(a => a.Id, StringComparer.Ordinal);
        var impacts = findings.Select(f => Impact(f, assetsById[f.SubjectId])).ToArray();
        var recommendations = findings.Select(f => new AnalysisLinkedRecord(f.RecommendationId, f.SubjectId, "Recommended next assessment action",
            f.PriorityRationale, f.ObservationRefs, f.Owner, f.Recommendation, f.Readiness, f.EvidenceState)).ToArray();
        var decisions = findings.Select(f => new AnalysisLinkedRecord(f.DecisionId, f.SubjectId, DecisionTitle(f),
            "The evidence and business context must be reviewed by the designated owner before this item can support an accepted assessment position.", f.ObservationRefs,
            f.Owner, f.Priority == "resolve_evidence" ? "Confirm the authoritative source, owner and dated evidence-reconciliation route; record any remaining limitation."
                : "Confirm the interpretation, business consequence and next investigation priority; this decision does not authorize a source-system change.", f.Readiness, f.EvidenceState)).ToArray();
        var coverage = Coverage(areas, profiles, selected, filter);
        var exposureMeanings = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            ["classical_public_key_recorded"] = "Source records a classical public-key mechanism; exposure requires role, context and evidence review.",
            ["mixed_classical_and_hybrid"] = "Hybrid key exchange and classical authentication coexist; one does not remove the other dependency.",
            ["hybrid_key_exchange_recorded"] = "A hybrid exchange mechanism is recorded; observed negotiation and authentication remain separate questions.",
            ["pqc_signature_recorded"] = "A PQC signature mechanism is recorded; interoperability and trust validation are not automatically established.",
            ["symmetric_parameter_review"] = "Symmetric protection needs purpose, parameter and custody review, not automatic public-key replacement.",
            ["unknown_cryptographic_parameters"] = "A cryptographic use is present but its parameters cannot support a reliable conclusion.",
            ["conflicting_cryptographic_evidence"] = "Conflicting evidence prevents selection of one authoritative cryptographic condition.",
            ["context_not_cryptographic_use"] = "Context or capability metadata is not proof of an active cryptographic use."
        };
        var readinessMeanings = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            ["evidence_prerequisites_missing"] = "Resolve evidence and context prerequisites before migration design.",
            ["independent_verification_required"] = "Configured or reported conditions need independent behavioral verification.",
            ["product_qualification_required"] = "Exact-product support, compatibility, authorized plan and recovery remain unqualified.",
            ["not_assessed"] = "No migration-readiness assessment is justified by this context record."
        };
        return new JsonObject
        {
            ["schemaVersion"] = "pqc.enterprise.analysis.v1", ["baseline"] = baseline.DeepClone(),
            ["method"] = Node(new AnalysisMethod(MethodId, MethodVersion, "illustrative_not_enterprise_approved",
                "Order of assessment attention, not a numerical risk rating or migration approval. Evidence gaps do not reduce exposure.", O(baselineProjection["method"]).DeepClone().AsObject(),
                "Exposure, readiness and priority distributions count findings. Asset and coverage indicators count distinct selected subjects; memberships can overlap.", exposureMeanings, readinessMeanings)),
            ["filterOptions"] = new JsonObject
            {
                ["services"] = Node(Options(allAssets.SelectMany(a => a.ServiceIds), id => ServiceLabel(id, inventoryById))),
                ["owners"] = Node(Options(allAssets.SelectMany(a => a.OwnerIds), OwnerLabel)),
                ["environments"] = Node(Options(allAssets.SelectMany(a => a.Environments), Human)),
                ["technologies"] = Node(Options(allAssets.SelectMany(a => a.Technologies), Human)),
                ["families"] = Node(profiles.Select(p => new AnalysisOption(S(p, "family_id"), S(p, "name"))).OrderBy(p => p.Label, StringComparer.Ordinal).ToArray())
            },
            ["selectedFilters"] = Node(filter), ["assets"] = Node(selected), ["findings"] = Node(findings),
            ["riskScenarios"] = Node(riskScenarios), ["businessImpacts"] = Node(impacts), ["recommendations"] = Node(recommendations), ["decisions"] = Node(decisions),
            ["coverage"] = Node(coverage), ["graph"] = Node(Graph(selected, allAssets, selectedUses, dependencies, bySubject, usesBySubject, inventoryById, findings)),
            ["summary"] = new JsonObject
            {
                ["assets"] = selected.Length, ["findings"] = findings.Length,
                ["observations"] = observations.Count(o => selectedIds.Contains(S(o, "subject_ref"))), ["cryptographicUses"] = selectedUses.Length,
                ["contextOnlyAssets"] = selected.Count(a => a.IsContextOnly), ["staleAssets"] = selected.Count(a => a.IsStale), ["disputedAssets"] = selected.Count(a => a.IsDisputed),
                ["sourceFamilies"] = selected.SelectMany(a => a.FamilyIds).Distinct().Count(), ["estateAreas"] = selected.SelectMany(a => a.AreaRefs).Distinct().Count(),
                ["decisionsRequired"] = decisions.Length, ["exposureCounts"] = Node(Counts(findings.Select(f => f.Exposure))),
                ["readinessCounts"] = Node(Counts(findings.Select(f => f.Readiness))), ["priorityCounts"] = Node(Counts(findings.Select(f => f.Priority)))
            },
            ["boundary"] = "Synthetic, unaccepted, evidence-linked analysis. Source-reported product capability is not independently verified behavior; priority is not an approved risk rating. No source writes, accepted exceptions or execution authority are created."
        };
    }

    private static AnalysisAsset Asset(JsonObject row, Dictionary<string, JsonObject[]> observations, Dictionary<string, JsonObject[]> uses,
        Dictionary<string, string[]> limitations, JsonObject[] profiles, Dictionary<string, JsonObject> inventory)
    {
        var id = S(row, "subject_ref");
        var ownObservations = observations.GetValueOrDefault(id) ?? [];
        var ownUses = uses.GetValueOrDefault(id) ?? [];
        var facts = ownObservations.Select(o => O(o["facts"])).ToArray();
        var isApplication = A(row, "fact_types").Contains("application", StringComparer.Ordinal);
        var applicationRefs = Values(facts, "application_ref");
        if (isApplication) applicationRefs = [id];
        // Join actual normalized source relationships, not application names,
        // array positions, or a pre-authored analytical context assignment.
        applicationRefs = applicationRefs.Concat(facts.SelectMany(f => R(f, "relationships"))
            .Where(relation => S(relation, "relationship") is "belongs_to_application" or "application_ref")
            .Select(relation => S(relation, "target_ref"))).Where(value => value.Length > 0).Distinct().Order(StringComparer.Ordinal).ToArray();
        var applicationObservations = applicationRefs.Where(observations.ContainsKey).SelectMany(app => observations[app]).Where(o => S(o, "fact_type") == "application").ToArray();
        var applicationFacts = applicationObservations.Select(o => O(o["facts"])).ToArray();
        var contextFacts = facts.Concat(applicationFacts).ToArray();
        var serviceIds = Values(contextFacts, "business_service_ref");
        var ownerIds = Values(contextFacts, "owner_ref");
        var environments = Values(contextFacts, "environment");
        var criticalities = Values(contextFacts, "criticality").Concat(Values(contextFacts, "business_criticality")).Distinct().ToArray();
        var technologies = new[] { "product_label", "engine_name", "package_name", "runtime_platform", "protocol", "tunnel_protocol" }
            .SelectMany(field => Values(facts, field)).Distinct().Order(StringComparer.Ordinal).ToArray();
        if (technologies.Length == 0) technologies = A(row, "fact_types").Select(Human).Distinct().Order(StringComparer.Ordinal).ToArray();
        var sourceIds = A(row, "source_instance_refs").ToHashSet(StringComparer.Ordinal);
        var families = profiles.Where(p => A(p, "source_instance_refs").Any(sourceIds.Contains)).ToArray();
        var codes = limitations.GetValueOrDefault(id) ?? [];
        var disputed = S(row, "conflict_status") != "no_conflict_in_snapshot" || codes.Contains("conflicting_observations", StringComparer.Ordinal);
        var stale = codes.Contains("stale_evidence", StringComparer.Ordinal);
        var useBases = ownUses.SelectMany(u => A(u, "evidence_bases")).Distinct().ToArray();
        var evidenceState = disputed ? "disputed" : stale ? "stale" : ownObservations.Length == 0 ? "unresolved" : ownUses.Length == 0 ? "context_only"
            : useBases.Length > 0 && !useBases.Contains("observed", StringComparer.Ordinal) ? "configured_or_reported" : "observed_record";
        return new AnalysisAsset(id, A(row, "display_names").FirstOrDefault() ?? Short(id), families.Select(p => S(p, "family_id")).Distinct().Order(StringComparer.Ordinal).ToArray(),
            families.Select(p => S(p, "area_ref")).Distinct().Order(StringComparer.Ordinal).ToArray(), Single(serviceIds), Combined(serviceIds, value => ServiceLabel(value, inventory)),
            Single(applicationRefs), Combined(applicationRefs, value => inventory.TryGetValue(value, out var app) ? A(app, "display_names").FirstOrDefault() ?? Short(value) : "Unresolved application " + Short(value)),
            Combined(ownerIds, OwnerLabel), Combined(environments, Human), Combined(technologies, Human), criticalities.Length == 1 ? criticalities[0] : criticalities.Length > 1 ? "conflicting" : Unknown,
            evidenceState, ownObservations.Select(o => S(o, "observation_id")).Distinct().Order(StringComparer.Ordinal).ToArray(), ownUses.Select(u => S(u, "use_id")).Distinct().Order(StringComparer.Ordinal).ToArray(),
            OrUnknown(serviceIds), OrUnknown(applicationRefs), OrUnknown(ownerIds), OrUnknown(environments), OrUnknown(technologies), stale, disputed, ownUses.Length == 0,
            applicationObservations.Select(o => S(o, "observation_id")).Distinct().Order(StringComparer.Ordinal).ToArray());
    }

    private static AnalysisFinding? Finding(AnalysisAsset asset, JsonObject[] uses, string[] sourceLimitations, bool hasContextReview, string baselineId)
    {
        var limitations = sourceLimitations.Concat(uses.SelectMany(u => A(u, "limitation_codes"))).Distinct().Order(StringComparer.Ordinal).ToArray();
        // Application metadata is expected to be contextual. Do not manufacture
        // a missing-crypto finding solely because a CMDB application has no
        // direct cryptographic-use record; its dependencies carry those uses.
        if (uses.Length == 0 && !hasContextReview && !asset.IsStale && !asset.IsDisputed && !limitations.Any(IsMaterialGap)) return null;
        var postures = uses.Select(u => S(u, "algorithm_posture")).ToHashSet(StringComparer.Ordinal);
        var classical = postures.Contains("classical_method_review_candidate");
        var hybrid = postures.Contains("hybrid_key_exchange_recorded");
        var unknownParameters = postures.Contains("unknown") || limitations.Contains("cryptographic_parameters_unknown", StringComparer.Ordinal);
        var exposure = asset.IsDisputed ? "conflicting_cryptographic_evidence" : uses.Length == 0 ? "context_not_cryptographic_use" : unknownParameters ? "unknown_cryptographic_parameters"
            : classical && hybrid ? "mixed_classical_and_hybrid" : classical ? "classical_public_key_recorded" : hybrid ? "hybrid_key_exchange_recorded"
            : postures.Contains("pqc_signature_mechanism_recorded") ? "pqc_signature_recorded" : "symmetric_parameter_review";
        var evidenceGap = asset.IsDisputed || asset.IsStale || unknownParameters || limitations.Any(IsMaterialGap);
        var reported = uses.Any(u => A(u, "evidence_bases").Any(b => b is "configured" or "vendor_reported"));
        var readiness = uses.Length == 0 ? "not_assessed" : evidenceGap ? "evidence_prerequisites_missing" : reported ? "independent_verification_required" : "product_qualification_required";
        var priority = evidenceGap ? "resolve_evidence" : uses.Length == 0 ? "context_only" : classical && (asset.Criticality is "high" or "critical") ? "prioritize_review" : "planned_review";
        var id = Id("finding", MethodId + "@" + MethodVersion, baselineId, asset.Id, exposure);
        var names = uses.SelectMany(u => A(u, "algorithm_variants")).Distinct().Order(StringComparer.Ordinal).ToArray();
        var roles = uses.Select(u => Human(S(u, "role"))).Distinct().Order(StringComparer.Ordinal).ToArray();
        var observation = uses.Length == 0
            ? $"{asset.Label} supplies context or capability metadata without an explicit cryptographic-use record. Its records cannot establish that a listed mechanism is active."
            : $"{asset.Label} has {uses.Length.ToString(CultureInfo.InvariantCulture)} recorded cryptographic use(s): {string.Join(", ", names.Length == 0 ? ["algorithm not supplied"] : names)} for {string.Join(", ", roles)}. Evidence state: {Human(asset.EvidenceState)}.";
        var implication = exposure switch
        {
            "conflicting_cryptographic_evidence" => "The differing observations prevent a defensible selection of the current mechanism. Choosing the more favourable variant would conceal uncertainty in both reports.",
            "context_not_cryptographic_use" => "A package, platform, policy or vendor statement cannot establish active cryptographic behavior, accepted risk or a completed migration.",
            "unknown_cryptographic_parameters" => "The protection role may be present, but missing algorithms or parameters prevent a reliable technical exposure assessment.",
            "mixed_classical_and_hybrid" => "The recorded hybrid key exchange does not remove the separately recorded classical authentication dependency. Assess confidentiality and signature trust as distinct migration concerns.",
            "classical_public_key_recorded" => "The recorded public-key mechanisms warrant role-specific transition review. Determine the protection lifetime and relying-party dependency before selecting a migration pattern; this is not a measured risk rating.",
            "hybrid_key_exchange_recorded" => "A recorded hybrid exchange is not proof that all clients negotiated it, that fallback is controlled, or that certificate/host authentication is post-quantum.",
            "pqc_signature_recorded" => "The signature mechanism still needs verifier, compatibility and trust-chain evidence. Mechanism presence alone cannot establish an asset-wide migration outcome.",
            _ => "Symmetric encryption, wrapping and integrity mechanisms need purpose, parameter, custody and recovery review; they must not be treated as classical public-key mechanisms merely because they use cryptography."
        };
        // Protection role, classical posture and confidentiality lifetime must
        // belong to the SAME use. A classical signature must never borrow the
        // confidentiality lifetime of a separate hybrid key exchange.
        var longLivedClassicalExchange = uses.Any(u => S(u, "algorithm_posture") == "classical_method_review_candidate" &&
            S(u, "purpose") == "key_establishment" && Number(u, "confidentiality_days_remaining") >= 1825);
        if (longLivedClassicalExchange) implication += " An attributable classical key-establishment use also records a long confidentiality horizon; review a store-now/decrypt-later scenario for that use, retaining uncertainty about capture opportunity and adversary capability. Signature trust remains a separate question.";
        if (asset.IsStale) implication += " Stale observations may no longer describe the deployed condition.";
        var recommendation = asset.IsDisputed ? "Reconcile the conflicting source records with the designated platform owner; retain both variants and document the authoritative disposition."
            : asset.IsStale ? "Obtain a dated read-only refresh and compare the mechanism, owner and dependencies before using this item in migration design."
            : unknownParameters ? "Request the exact algorithm, parameters, implementation version and protection role from the owner-confirmed source route."
            : uses.Length == 0 ? "Confirm whether this source can identify active uses or only contextual capability; collect attributable consumer/implementation evidence or retain a coverage limitation."
            : reported ? "Verify configured or vendor-reported behavior against an approved independent observation; keep claim provenance and exact product version visible."
            : hybrid || postures.Contains("pqc_signature_mechanism_recorded") ? "Design a bounded interoperability and relying-party verification plan; distinguish key establishment from authentication and define failure/fallback checks."
            : classical ? "Review the applicable migration pattern with the source and application owners, document compatibility/vendor prerequisites and proposed independent verification; do not execute a change."
            : "Review the purpose, mode, key-management dependency and restoration behavior with the information owner; do not assume re-encryption is required.";
        var priorityRationale = priority switch
        {
            "resolve_evidence" => "Missing, stale, disputed or incomplete evidence blocks an accepted assessment interpretation. Investigative priority does not imply reduced exposure.",
            "prioritize_review" => $"A classical public-key mechanism is attributable to source-reported {asset.Criticality} application criticality; the review order is illustrative and still needs business disposition.",
            "context_only" => "Clarify context and coverage without assigning a cryptographic risk rating to capability metadata.",
            _ => "The evidence supports a bounded review candidate, while business impact, exact-product support, compatibility and approval remain separate prerequisites."
        };
        var evidenceRefs = asset.ObservationRefs.Concat(asset.ContextObservationRefs).Distinct().Order(StringComparer.Ordinal).ToArray();
        return new AnalysisFinding(id, asset.Id, asset.Label, [asset.Id], FindingTitle(exposure, asset), observation, implication, recommendation,
            priority, priorityRationale, asset.EvidenceState, evidenceGap ? "limited_by_evidence" : reported ? "attributed_claim_only" : "source_attributed_not_independently_verified",
            asset.Owner, asset.ServiceId, asset.ServiceLabel, asset.Environment, asset.Technology, asset.FamilyIds, evidenceRefs, limitations,
            Id("scenario", id), Id("impact", id), Id("recommendation", id), Id("decision", id), exposure, readiness);
    }

    private static AnalysisLinkedRecord Impact(AnalysisFinding finding, AnalysisAsset asset)
    {
        var rationale = asset.ServiceId == Unknown
            ? "No unique attributable business-service context is available. Financial, customer, regulatory and operational impact cannot be quantified from the current evidence."
            : $"The source relationship connects this condition to {asset.ServiceLabel} through {asset.ApplicationLabel}. Recorded application criticality: {Human(asset.Criticality)}. A failed compatibility change or loss of trust could disrupt relying parties; the business owner must establish actual consequence and tolerance.";
        return new AnalysisLinkedRecord(finding.ImpactId, asset.Id, "Business and operational consequence to validate", rationale, finding.ObservationRefs, asset.Owner,
            "Confirm the affected service, protected information lifetime, recovery expectations and business obligations. Do not infer a monetary loss, regulatory violation or accepted impact from this mock baseline.", finding.Readiness, finding.EvidenceState);
    }

    private static AnalysisCoverage[] Coverage(JsonObject[] areas, JsonObject[] profiles, AnalysisAsset[] selected, AnalysisFilter filter) => areas.Select(area =>
    {
        var areaId = S(area, "area_ref");
        var areaProfiles = profiles.Where(p => S(p, "area_ref") == areaId && (string.IsNullOrWhiteSpace(filter.Family) || S(p, "family_id") == filter.Family)).ToArray();
        var members = selected.Where(a => a.AreaRefs.Contains(areaId, StringComparer.Ordinal)).ToArray();
        return new AnalysisCoverage(areaId, S(area, "name"), areaProfiles.Length, members.Length, members.Count(a => a.IsContextOnly), members.Count(a => a.IsStale), members.Count(a => a.IsDisputed),
            areaProfiles.Count(p => !members.Any(a => a.FamilyIds.Contains(S(p, "family_id"), StringComparer.Ordinal))),
            "Distinct selected synthetic subjects. Stale, disputed and no-use-context memberships overlap; no enterprise denominator or completion percentage is inferred.",
            "Missing counts known selected subjects without a direct cryptographic-use record, including legitimate contextual sources. MissingFamilies counts scoped catalog families absent from the selected records, not failed collection or enterprise absence.");
    }).OrderBy(row => row.AreaId, StringComparer.Ordinal).ToArray();

    private static AnalysisGraph Graph(AnalysisAsset[] selected, AnalysisAsset[] all, JsonObject[] selectedUses, JsonObject[] dependencies,
        Dictionary<string, JsonObject[]> observations, Dictionary<string, JsonObject[]> usesBySubject, Dictionary<string, JsonObject> inventory, AnalysisFinding[] findings)
    {
        var selectedIds = selected.Select(a => a.Id).ToHashSet(StringComparer.Ordinal);
        var byId = all.ToDictionary(a => a.Id, StringComparer.Ordinal);
        var nodes = new Dictionary<string, AnalysisGraphNode>(StringComparer.Ordinal);
        var edges = new Dictionary<string, AnalysisGraphEdge>(StringComparer.Ordinal);
        void AddSubject(string id)
        {
            if (nodes.ContainsKey(id)) return;
            if (byId.TryGetValue(id, out var asset))
            {
                var kind = inventory.TryGetValue(id, out var row) && A(row, "fact_types").Contains("application", StringComparer.Ordinal) ? "application" : "asset";
                nodes[id] = new AnalysisGraphNode(id, asset.Label, kind, id, selectedIds.Contains(id), asset.AreaRefs);
            }
            else nodes[id] = new AnalysisGraphNode(id, "Unresolved reference " + Short(id), "external_reference", id, false, []);
        }
        void AddEdge(string source, string target, string relationship, string[] evidence)
        {
            var id = Id("edge", source, target, relationship);
            edges[id] = new AnalysisGraphEdge(id, source, target, relationship, evidence.Distinct().Order(StringComparer.Ordinal).ToArray());
        }
        foreach (var asset in selected)
        {
            AddSubject(asset.Id);
            foreach (var appId in asset.ApplicationIds.Where(id => id != Unknown))
            {
                AddSubject(appId);
                if (appId != asset.Id) AddEdge(appId, asset.Id, "has_cryptographic_dependency", asset.ObservationRefs);
                if (!observations.TryGetValue(appId, out var appObservations)) continue;
                foreach (var observation in appObservations.Where(o => S(o, "fact_type") == "application"))
                {
                    var service = S(O(observation["facts"]), "business_service_ref");
                    if (string.IsNullOrEmpty(service)) continue;
                    nodes[service] = new AnalysisGraphNode(service, ServiceLabel(service, inventory), "business_service", service, selectedIds.Contains(service), []);
                    AddEdge(service, appId, "supported_by_application", [S(observation, "observation_id")]);
                }
            }
        }
        foreach (var use in selectedUses)
        {
            var subject = S(use, "subject_ref");
            var useId = "use-" + S(use, "use_id");
            var label = Human(S(use, "role")) + " · " + string.Join(" / ", A(use, "algorithm_variants"));
            if (A(use, "algorithm_variants").Length == 0) label += "algorithm unknown";
            nodes[useId] = new AnalysisGraphNode(useId, label, "cryptographic_use", subject, true, byId[subject].AreaRefs);
            AddEdge(subject, useId, "has_cryptographic_use", A(use, "observation_refs"));
        }
        foreach (var dependency in dependencies.Where(d => selectedIds.Contains(S(d, "from_ref")) || selectedIds.Contains(S(d, "to_ref"))))
        {
            var source = S(dependency, "from_ref"); var target = S(dependency, "to_ref");
            AddSubject(source); AddSubject(target);
            AddEdge(source, target, S(dependency, "relationship"), A(dependency, "observation_refs"));
        }
        // A filtered application/context source can still show its directly
        // attributable crypto dependencies. Such neighbours and uses are marked
        // outside the selected inventory and never inflate filtered indicators.
        foreach (var contextAsset in nodes.Values.Where(n => n.Kind == "asset" && !n.InScope).ToArray())
            foreach (var use in usesBySubject.GetValueOrDefault(contextAsset.Id) ?? [])
            {
                var useId = "use-" + S(use, "use_id");
                nodes[useId] = new AnalysisGraphNode(useId, Human(S(use, "role")) + " · " + string.Join(" / ", A(use, "algorithm_variants")),
                    "cryptographic_use", contextAsset.Id, false, contextAsset.AreaRefs);
                AddEdge(contextAsset.Id, useId, "has_cryptographic_use", A(use, "observation_refs"));
            }
        // Keep complete service/application/use chains in the bounded view. A
        // filter never mutates the underlying model or the stable identities.
        var chosen = new HashSet<string>(StringComparer.Ordinal);
        void Choose(string id) { if (chosen.Count < 30 && nodes.ContainsKey(id)) chosen.Add(id); }
        var ranked = selected.OrderBy(a => findings.FirstOrDefault(f => f.SubjectId == a.Id) is { } f ? PriorityOrder(f.Priority) : 5)
            .ThenByDescending(a => a.UseIds.Length > 0).ThenBy(a => a.Label, StringComparer.Ordinal).ToArray();
        foreach (var asset in ranked)
        {
            if (chosen.Count >= 26) break;
            foreach (var service in asset.ServiceIds.Where(s => s != Unknown)) Choose(service);
            foreach (var application in asset.ApplicationIds.Where(s => s != Unknown)) Choose(application);
            Choose(asset.Id);
            foreach (var use in (usesBySubject.GetValueOrDefault(asset.Id) ?? []).Take(2)) Choose("use-" + S(use, "use_id"));
            if (asset.UseIds.Length == 0)
            {
                var neighbour = dependencies.Where(d => S(d, "to_ref") == asset.Id).Select(d => S(d, "from_ref"))
                    .FirstOrDefault(id => usesBySubject.ContainsKey(id));
                if (neighbour is not null)
                {
                    Choose(neighbour);
                    foreach (var use in usesBySubject[neighbour].Take(1)) Choose("use-" + S(use, "use_id"));
                }
            }
        }
        foreach (var edge in edges.Values.OrderBy(e => e.Id, StringComparer.Ordinal))
            if (chosen.Contains(edge.Source) || chosen.Contains(edge.Target)) { Choose(edge.Source); Choose(edge.Target); }
        var visibleNodes = nodes.Values.Where(n => chosen.Contains(n.Id)).OrderBy(n => NodeOrder(n.Kind)).ThenBy(n => n.Label, StringComparer.Ordinal).ToArray();
        var visibleEdges = edges.Values.Where(e => chosen.Contains(e.Source) && chosen.Contains(e.Target)).OrderBy(e => e.Id, StringComparer.Ordinal).ToArray();
        return new AnalysisGraph(visibleNodes, visibleEdges, nodes.Count, visibleNodes.Length, nodes.Count > visibleNodes.Length);
    }

    private static string FindingTitle(string exposure, AnalysisAsset asset) => exposure switch
    {
        "conflicting_cryptographic_evidence" => "Reconcile conflicting cryptographic observations",
        "context_not_cryptographic_use" => "Distinguish capability context from active cryptographic use",
        "unknown_cryptographic_parameters" => "Complete the missing cryptographic parameters",
        "mixed_classical_and_hybrid" => "Hybrid exchange still depends on separate classical authentication",
        "classical_public_key_recorded" when asset.IsStale => "Refresh stale evidence before classical-mechanism review",
        "classical_public_key_recorded" => "Review the role-specific classical public-key dependency",
        "hybrid_key_exchange_recorded" => "Verify hybrid negotiation and authentication independently",
        "pqc_signature_recorded" => "Verify the recorded PQC signature and relying parties",
        _ => "Review symmetric protection parameters and recovery dependencies"
    };
    private static string ScenarioTitle(AnalysisFinding finding) => finding.Exposure switch
    {
        "mixed_classical_and_hybrid" => "Separate key-establishment and authentication scenario",
        "classical_public_key_recorded" => "Role-specific classical-mechanism transition scenario",
        _ => "Evidence and compatibility scenario"
    };
    private static string DecisionTitle(AnalysisFinding finding) => finding.Priority == "resolve_evidence" ? "Resolve the evidence route and limitation disposition" : "Confirm the assessment interpretation and next priority";
    private static bool IsMaterialGap(string code) => code is "missing_business_context" or "business_context_requires_review" or "missing_relationship" or "unresolved_dependency" or "cryptographic_parameters_unknown" or "conflicting_observations";
    private static int PriorityOrder(string value) => value switch { "resolve_evidence" => 0, "prioritize_review" => 1, "planned_review" => 2, _ => 3 };
    private static int NodeOrder(string kind) => kind switch { "business_service" => 0, "application" => 1, "asset" => 2, "cryptographic_use" => 3, _ => 4 };
    private static bool Matches(AnalysisAsset asset, AnalysisFilter filter) =>
        Match(filter.Service, asset.ServiceIds) && Match(filter.Owner, asset.OwnerIds) && Match(filter.Environment, asset.Environments) && Match(filter.Technology, asset.Technologies) && Match(filter.Family, asset.FamilyIds);
    private static bool Match(string? filter, string[] values) => string.IsNullOrWhiteSpace(filter) || values.Contains(filter, StringComparer.Ordinal);
    private static void ValidateFilter(AnalysisFilter filter)
    {
        foreach (var value in new[] { filter.Service, filter.Owner, filter.Environment, filter.Technology, filter.Family })
            if (value is not null && (value.Length > 200 || value.Any(char.IsControl))) throw new DemoValidationException("invalid_analysis_filter");
    }
    private static AnalysisOption[] Options(IEnumerable<string> ids, Func<string, string> label) => ids.Distinct().Select(id => new AnalysisOption(id, label(id))).OrderBy(o => o.Label, StringComparer.Ordinal).ToArray();
    private static AnalysisCount[] Counts(IEnumerable<string> values) => values.GroupBy(v => v).Select(g => new AnalysisCount(g.Key, g.Count())).OrderByDescending(c => c.Count).ThenBy(c => c.Id, StringComparer.Ordinal).ToArray();
    private static string ServiceLabel(string id, Dictionary<string, JsonObject> inventory) => id == Unknown ? "Unknown service" : inventory.TryGetValue(id, out var row)
        ? A(row, "display_names").FirstOrDefault() ?? "Service reference " + Short(id) : "Service reference " + Short(id) + " (name not supplied)";
    private static string OwnerLabel(string id) => id == Unknown ? "Owner route not supplied" : "Owner reference " + Short(id) + " (name not supplied)";
    private static string Combined(string[] values, Func<string, string> label) => values.Length == 0 ? label(Unknown) : values.Length == 1 ? label(values[0]) : "Multiple recorded values: " + string.Join("; ", values.Select(label));
    private static string Single(string[] values) => values.Length == 0 ? Unknown : values.Length == 1 ? values[0] : "multiple";
    private static string[] OrUnknown(string[] values) => values.Length == 0 ? [Unknown] : values;
    private static string[] Values(IEnumerable<JsonObject> rows, string key) => rows.Select(row => S(row, key)).Where(v => !string.IsNullOrWhiteSpace(v)).Distinct().Order(StringComparer.Ordinal).ToArray();
    private static string Short(string id) => id.Length > 12 ? id[^12..] : id;
    private static string Human(string value) => string.IsNullOrWhiteSpace(value) || value == Unknown ? "Unknown" : value.Replace('_', ' ');
    private static string Id(string kind, params string[] parts) => kind + "-" + Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(string.Join("\n", parts))));
    private static JsonNode? Node<T>(T value) => JsonSerializer.SerializeToNode(value, JsonOptions);
    private static JsonObject O(JsonNode? value) => value as JsonObject ?? new JsonObject();
    private static string S(JsonObject row, string key) => row[key] is JsonValue value && value.TryGetValue<string>(out var result) ? result : "";
    private static string[] A(JsonObject row, string key) => row[key] is JsonArray array ? array.OfType<JsonValue>().Where(value => value.TryGetValue<string>(out _)).Select(value => value.GetValue<string>()).ToArray() : [];
    private static JsonObject[] R(JsonObject row, string key) => row[key] is JsonArray array ? array.OfType<JsonObject>().ToArray() : [];
    private static double Number(JsonObject row, string key) => row[key] is JsonValue value && value.TryGetValue<double>(out var number) ? number : 0;
}
