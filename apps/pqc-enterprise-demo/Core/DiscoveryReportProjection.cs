using System.Net;
using System.Text;
using System.Text.Json.Nodes;

namespace PqcEnterpriseDemo;

/// <summary>Pure, versioned interpretation of submitted discovery and admitted
/// synthetic evidence. Neither a received answer nor a draft standard is fact
/// verification or enterprise policy.</summary>
public static class DiscoveryReportProjection
{
    public const string MethodVersion="pqc.discovery.interpretation.v1";
    private static IEnumerable<DiscoveryRequest> Requests(AssessmentState s)=>s.Discovery.Requests.Where(r=>s.Scope.IncludedFamilyIds.Contains(r.FamilyId));
    private static IEnumerable<DiscoveryInvestigation> Investigations(AssessmentState s)=>s.Discovery.Investigations.Where(i=>Requests(s).Any(r=>r.Id==i.RequestId));

    public static string Fingerprint(AssessmentState s,string legacy)
    {
        // Preserve old immutable report/gate identities when discovery has not
        // been used. Merely exporting a workbook is never a report change.
        if(!Requests(s).Any(r=>r.Status=="submitted") && !Investigations(s).Any() &&
            AssessmentWorkflow.Hash(s.Discovery.Standards)==AssessmentWorkflow.Hash(DiscoveryWorkflow.StandardTemplates()))return legacy;
        return AssessmentWorkflow.Hash(new{legacy,method=MethodVersion,
            responses=Requests(s).Where(r=>r.Status=="submitted").Select(r=>new{r.Id,r.FamilyId,r.TemplateVersion,r.TemplateSha256,r.Answers,r.ProductRefs,r.Submission}),
            standards=s.Discovery.Standards,
            investigations=Investigations(s).Select(i=>new{i.Id,i.RequestId,i.ProductRefs,i.AssignedTo,i.Status,i.Purpose,i.ResearchSummary,i.ProposedMethod,i.DocumentationRefs,i.Limitation,i.EvidenceReviews})});
    }

    public static JsonObject Build(AssessmentState state)
    {
        var requests=Requests(state).Where(r=>r.Status=="submitted").ToArray();
        var investigations=Investigations(state).ToArray();
        return AssessmentJson.Object(new{
            schemaVersion="pqc.discovery.report-input.v1",methodVersion=MethodVersion,
            hasActivity=requests.Length>0 || investigations.Length>0 || AssessmentWorkflow.Hash(state.Discovery.Standards)!=AssessmentWorkflow.Hash(DiscoveryWorkflow.StandardTemplates()),
            summary=$"{requests.Length} submitted contribution(s); {investigations.Length} engineer-owned investigation(s). Response received is not source readiness or technical verification.",
            responses=requests.Select(r=>new{r.Id,r.Title,r.FamilyId,r.TemplateVersion,r.TemplateSha256,r.Submission,
                interpretation="Attributed discovery contribution, not an established technical fact or permission to access a source.",
                answers=r.Questions.Select(q=>new{questionId=q.Id,prompt=q.Prompt,answer=r.Answers.GetValueOrDefault(q.Id)??new DiscoveryAnswer()}),
                reportedProducts=r.ProductRefs}),
            standards=state.Discovery.Standards,
            investigations=investigations.Select(i=>new{i.Id,i.RequestId,i.FamilyId,i.ProductRefs,i.AssignedTo,i.Status,i.Purpose,i.ResearchSummary,i.ProposedMethod,i.DocumentationRefs,i.Limitation,
                evidence=i.EvidenceReviews.Select(b=>new{b.BatchId,b.ProductLabel,b.SourceLabel,b.Status,b.ObservationCount,b.ContentSha256,b.StagedBy,b.ReviewedBy,b.ReviewRationale,b.AdmittedBy,
                    observationRefs=state.Intake.Batches.Where(x=>b.Status=="admitted" && b.BatchIds.Contains(x.Id) && x.Status=="admitted").SelectMany(x=>x.Observations).Select(o=>o.Id)})}),
            limitations=new[]{"The enterprise population is unknown; classification coverage is not inventory completeness.",
                "An unknown policy answer does not prove no policy exists. Existing requirements and their authority must be checked separately.",
                "Proposed standards support recommendations for review, never retrospective noncompliance findings. No standard is adopted by this workflow.",
                "Documentation research does not qualify an installed product or grant access. Only the closed synthetic TLS evidence format is exercised in this candidate.",
                "Application/service dependencies, information lifetime, client compatibility and independent runtime verification require separate evidence."},
            nextDecision="Confirm existing requirements and designated review authority; disposition remaining evidence limitations. No enterprise adoption, access grant or migration action is enabled."
        });
    }

    // Intake supplies immutable source observations and endpoint identities.
    // This layer adds two separate use-level interpretations for the analysis
    // engine. Only bundles qualified by an independent reviewer and admitted
    // through the controller can contribute these rows.
    public static void MergeEvidence(AssessmentState state,JsonObject projection)
    {
        var admitted=Investigations(state).SelectMany(i=>i.EvidenceReviews)
            .Where(b=>b.Status=="admitted" && b.ReviewedBy.Length>0 && b.ReviewedBy!=b.StagedBy)
            .SelectMany(b=>b.BatchIds).ToHashSet(StringComparer.Ordinal);
        if(admitted.Count==0)return;
        var uses=projection["riskReviews"]!.AsArray();
        var observations=projection["observations"]!.AsArray().OfType<JsonObject>().ToDictionary(o=>o["observation_id"]!.GetValue<string>());
        var records=state.Intake.Batches.Where(b=>admitted.Contains(b.Id) && b.Status=="admitted")
            .SelectMany(b=>b.Observations).DistinctBy(o=>o.Id).Where(o=>observations.ContainsKey(o.Id));
        foreach(var group in records.GroupBy(o=>o.SystemId).OrderBy(g=>g.Key,StringComparer.Ordinal))
        {
            var evidence=group.OrderBy(o=>o.Id,StringComparer.Ordinal).ToArray();
            var system=state.Intake.Systems.Single(s=>s.Id==group.Key);
            foreach(var record in evidence)
            {
                var observation=observations[record.Id];
                observation["fact_type"]="tls_endpoint";
                observation["facts"]!["product_label"]=system.Product;
                observation["facts"]!["environment"]=system.Environment;
                observation["facts"]!["context_basis"]="reported_deployment_binding";
            }
            var asset=projection["inventory"]!.AsArray().OfType<JsonObject>().Single(a=>a["subject_ref"]!.GetValue<string>()==group.Key);
            asset["fact_types"]=new JsonArray("tls_endpoint");
            // A new capture is evidence for the same subject/role, not another
            // cryptographic use. Retain all variants; never select a newer or
            // more favorable posture and never clear the inventory conflict.
            AddUse("key_establishment","transport_key_exchange",evidence.Select(o=>o.KeyExchange),ExchangePosture);
            AddUse("authentication","certificate_signature",evidence.Select(o=>o.Authentication),SignaturePosture);
            void AddUse(string purpose,string role,IEnumerable<string> algorithms,Func<string,string> classify)
            {
                var variants=algorithms.Distinct(StringComparer.Ordinal).Order(StringComparer.Ordinal).ToArray();
                var postures=variants.Select(classify).Distinct(StringComparer.Ordinal).ToArray();
                var posture=postures.Length==1?postures[0]:"unknown";
                var useId="discovery-use-"+AssessmentWorkflow.Hash(new{subjectRef=group.Key,role,method=MethodVersion})[..24];
                var row=new JsonObject{["use_id"]=useId,["subject_ref"]=group.Key,["purpose"]=purpose,["role"]=role,
                    ["algorithm_variants"]=new JsonArray(variants.Select(a=>(JsonNode?)JsonValue.Create(a)).ToArray()),["algorithm_posture"]=posture,
                    ["evidence_bases"]=new JsonArray(evidence.Select(o=>o.Basis).Distinct(StringComparer.Ordinal).Order(StringComparer.Ordinal).Select(b=>(JsonNode?)JsonValue.Create(b)).ToArray()),
                    ["observation_refs"]=new JsonArray(evidence.Select(o=>(JsonNode?)JsonValue.Create(o.Id)).ToArray()),["confidentiality_days_remaining"]=null,["trust_days_remaining"]=null,
                    ["limitation_codes"]=posture=="unknown"?new JsonArray("cryptographic_parameters_unknown","missing_business_context","unresolved_dependency"):new JsonArray("missing_business_context","unresolved_dependency"),
                    ["assessment_status"]="illustrative_review_candidate",["method_version"]=MethodVersion,["independently_verified"]=false};
                var existing=uses.OfType<JsonObject>().SingleOrDefault(u=>u["use_id"]?.GetValue<string>()==useId);
                if(existing is null)uses.Add(row);else uses[uses.IndexOf(existing)]=row;
            }
        }
    }

    // Closed, deliberately narrow classifiers: unknown names remain unknown.
    // Hybrid groups: OpenSSL 3.5 SSL_CTX_set1_groups documentation, HISTORY.
    private static string ExchangePosture(string value)=>value.ToUpperInvariant() switch
    {
        "X25519MLKEM768" or "SECP256R1MLKEM768" or "SECP384R1MLKEM1024"=>"hybrid_key_exchange_recorded",
        "X25519" or "X448" or "P-256" or "P-384" or "P-521" or "SECP256R1" or "SECP384R1" or "SECP521R1" or "FFDHE2048" or "FFDHE3072"=>"classical_method_review_candidate",
        _=>"unknown"
    };
    private static string SignaturePosture(string value)=>value.ToUpperInvariant() switch
    {
        "SHA256WITHRSAENCRYPTION" or "SHA384WITHRSAENCRYPTION" or "SHA512WITHRSAENCRYPTION" or "RSA" or "RSASSA-PSS" or "ECDSA-WITH-SHA256" or "ECDSA-WITH-SHA384" or "ED25519" or "ED448"=>"classical_method_review_candidate",
        "ML-DSA-44" or "ML-DSA-65" or "ML-DSA-87"=>"pqc_signature_mechanism_recorded",
        _=>"unknown"
    };

    public static string RenderHtml(JsonObject discovery)
    {
        static string E(string? text)=>WebUtility.HtmlEncode(text??"");
        static string S(JsonNode? o,string key)=>o?[key]?.GetValue<string>()??"";
        static IEnumerable<JsonObject> Rows(JsonNode? o,string key)=>(o?[key] as JsonArray)?.OfType<JsonObject>()??[];
        var html=new StringBuilder("<section id=\"discovery\"><h2>Discovery, investigation and proposed standards</h2><p>");
        html.Append(E(S(discovery,"summary"))).Append("</p><h3>What contributors told us</h3>");
        foreach(var response in Rows(discovery,"responses"))
        {
            html.Append("<article><h4>").Append(E(S(response,"title"))).Append("</h4><p>Attributed response — not technical verification.</p><dl>");
            foreach(var answer in Rows(response,"answers"))
            {
                var a=answer["answer"];
                html.Append("<dt>").Append(E(S(answer,"prompt"))).Append("</dt><dd>").Append(E(S(a,"status").Replace('_',' '))).Append(": ")
                    .Append(E(S(a,"text"))).Append("<small> Reference: ").Append(E(S(a,"reference"))).Append(" · Asserted by: ")
                    .Append(E(S(a,"assertedBy"))).Append(" · Recorded by: ").Append(E(S(a,"recordedBy"))).Append("</small></dd>");
            }
            html.Append("</dl></article>");
        }
        html.Append("<h3>Engineering work and its report consequence</h3>");
        foreach(var investigation in Rows(discovery,"investigations"))
        {
            html.Append("<article><h4>").Append(E(S(investigation,"purpose"))).Append("</h4><p>Status: ").Append(E(S(investigation,"status").Replace('_',' ')))
                .Append(" · Assigned to: ").Append(E(S(investigation,"assignedTo"))).Append("</p><p>").Append(E(S(investigation,"researchSummary")))
                .Append("</p><p>Limitation: ").Append(E(S(investigation,"limitation"))).Append("</p><ul>");
            foreach(var evidence in Rows(investigation,"evidence"))
                html.Append("<li>").Append(E(S(evidence,"productLabel"))).Append(" — ").Append(E(S(evidence,"status"))).Append("; ")
                    .Append(evidence["observationCount"]?.ToString()).Append(" observation(s). ").Append(S(evidence,"status")=="admitted"?"Included in the map and technical report inputs.":"Not included in technical report inputs.")
                    .Append(" Review: ").Append(E(S(evidence,"reviewRationale"))).Append("</li>");
            html.Append("</ul></article>");
        }
        html.Append("<h3>Standards proposed for review — not adopted policy</h3><p>Compare documented practice with proposals to identify recommendations, not retrospective noncompliance.</p>");
        foreach(var standard in Rows(discovery,"standards"))
        {
            html.Append("<article><h4>").Append(E(S(standard,"title"))).Append("</h4><p>").Append(E(S(standard,"version"))).Append(" · ")
                .Append(E(S(standard,"status"))).Append("</p><p style=\"white-space:pre-line\">").Append(E(S(standard,"proposalText")))
                .Append("</p><p>Existing requirement: ").Append(E(S(standard,"existingRequirementStatus"))).Append(". Authority: ")
                .Append(E(S(standard,"proposedAuthority"))).Append(" (candidate, not adoption). Conflict review: ").Append(E(S(standard,"conflictReviewStatus")))
                .Append(". ").Append(E(S(standard,"conflictNote"))).Append("</p></article>");
            html.Append("<p>Recorded practice (attributed, not automatically verified): ").Append(E(S(standard,"observedPractice"))).Append("</p><ul>");
            foreach(var reference in Rows(standard,"publicationRefs"))
            {
                var url=S(reference,"url");
                if(Uri.TryCreate(url,UriKind.Absolute,out var uri) && uri.Scheme=="https" && (uri.Host=="csrc.nist.gov" || uri.Host=="www.nccoe.nist.gov" || uri.Host=="nvlpubs.nist.gov"))
                    html.Append("<li><a href=\"").Append(E(url)).Append("\" rel=\"noreferrer\">").Append(E(S(reference,"title"))).Append("</a> — ").Append(E(S(reference,"status"))).Append("</li>");
            }
            html.Append("</ul>");
        }
        html.Append("<h3>Limits and next decision</h3><ul>");
        foreach(var limitation in discovery["limitations"]!.AsArray())html.Append("<li>").Append(E(limitation?.GetValue<string>())).Append("</li>");
        return html.Append("</ul><p>").Append(E(S(discovery,"nextDecision"))).Append("</p></section>").ToString();
    }
}
