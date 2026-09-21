"""Report source guards and reusable semantic checks for the real HTTP lane.

The source checks do not claim runtime, rendering, vendor or owner acceptance.
The HTTP suite can call the helpers against actual controller-produced reports.
No build, download, service startup or external source call occurs here.
"""
from __future__ import annotations

import copy
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import urlparse
import pytest


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "apps/pqc-enterprise-demo/Core/AssessmentReportRenderer.cs"


def assert_executive_summary(content, *, phase):
    """Version-aware reading contract; never equate unreviewed prose with findings."""
    summary = content["narrative"]["executiveSummary"]
    assert all(item["title"] and item["body"] for item in summary)
    if phase != "phase2" or content["manifest"].get("workspaceTemplateVersion") != "pqc.response-to-report.html.v4":
        assert len(summary) == 3
        return
    rows = content["scenarioRows"]
    reviewed = [row for row in rows if row["scenarioState"] in {"accepted", "qualified"}
                and row.get("businessReviewedBy") not in {None, "", "Not reviewed"}]
    assert summary[0]["title"] == "Phase 2 business position"
    if not reviewed:
        assert len(summary) == 2
        assert "No designated business review" in summary[0]["body"]
        assert summary[1]["title"] == "Decision needed"
        text = " ".join(item["body"] for item in summary)
        for row in rows:
            for field in ("businessImpact", "protectedInformationLifetime", "recommendation"):
                if row.get(field):
                    assert row[field] not in text, "unreviewed_business_claim_in_executive_summary"
        return
    rank = {"prioritize_review": 0, "planned_review": 1, "defer": 2}
    domains = {}
    for row in reviewed:
        domains.setdefault(row["areaId"], []).append(row)
    leading = [min(group, key=lambda row: (rank.get(row["priority"], 3), row["familyId"])) for group in domains.values()]
    highlights = sorted(leading, key=lambda row: (rank.get(row["priority"], 3), row["areaId"]))[:3]
    assert len(summary) == 3 + len(highlights)
    assert summary[-2]["title"] == "Why these decisions receive attention"
    assert summary[-1]["title"] == "Qualifications and material unknowns"
    assert "not numerical risk ratings" in summary[-2]["body"]
    assert f"{len(reviewed)} of {len(rows)} scoped scenario interpretations" in summary[0]["body"]
    assert f"highlights {len(highlights)} of {len(domains)} reviewed domains" in summary[-1]["body"]
    for item, row in zip(summary[1:-2], highlights):
        assert item["title"].endswith(" — " + row["label"])
        for field in ("businessImpact", "protectedInformationLifetime", "recommendation", "owner", "nextDecision"):
            assert row[field] and row[field] in item["body"], field
    for row in reviewed:
        if row.get("confidenceBasis"):
            assert row["confidenceBasis"] in summary[-2]["body"]


def assert_report_content(content, *, phase, subjects=None, observations=None, phase1=None):
    """Exercise this against a generated artifact, not an authored expected blob."""
    assert content["schemaVersion"] == "pqc.assessment.report.v1"
    assert content["phase"] == phase
    assert content["synthetic"] is True
    manifest = content["manifest"]
    assert manifest["assessmentId"] == content["assessment"]["id"]
    assert len(manifest["subjectRefs"]) == len(set(manifest["subjectRefs"]))
    assert len(manifest["observationRefs"]) == len(set(manifest["observationRefs"]))
    assert content["summary"]["subjects"] == len(manifest["subjectRefs"])
    assert content["summary"]["observations"] == len(manifest["observationRefs"])
    assert content["summary"]["enterpriseCoveragePercent"] is None
    for row in content["coverageRows"]:
        assert row["populationTotal"] is None
        assert row["coveragePercent"] is None
        assert row["populationState"] == "enterprise_denominator_unknown"
        assert row["populationMeaning"] and row["limitation"]
        assert row["plannedDepth"] in {"routing", "inventory", "dependency_cohort"}
        assert row["achievedDepth"] in {"not_established", "routing", "inventory"}
        if row["plannedDepth"] == "dependency_cohort":
            assert row["depthLimitation"]
    selected_subjects = set(manifest["subjectRefs"])
    selected_observations = set(manifest["observationRefs"])
    if subjects is not None:
        assert selected_subjects == set(subjects)
    if observations is not None:
        assert selected_observations == set(observations)
    for finding in content["findings"]:
        assert finding["subjectId"] in selected_subjects
        assert set(finding["observationRefs"]) <= selected_observations
    for reference in content["evidenceReferences"]:
        assert reference["subjectId"] in selected_subjects
        assert reference["observationId"] in selected_observations
        assert reference["origin"] == "synthetic_fixture_not_live_collection"
    assert_executive_summary(content, phase=phase)
    assert content["narrative"]["nextSteps"]
    assert content["narrative"]["caveats"]
    indicators = content.get("assessmentIndicators", {})
    if indicators:
        answers = indicators["questionAnswerability"]
        assert answers["supported"] + answers["qualified"] + answers["unanswered"] == answers["total"]
        enablement = indicators["sourceEnablement"]
        assert 0 <= enablement["documentedRoutes"] <= enablement["total"]
        assert 0 <= enablement["syntheticSamplesAdmitted"] <= enablement["total"]
        assert indicators["decisionBacklog"]["pendingSlots"] >= 0
        assert indicators["asOf"]
    if phase == "phase1":
        assert manifest["selectedPhase1"] is None
        assert content["scenarioRows"] == []
    else:
        assert manifest["selectedPhase1"]["reportId"]
        assert len(manifest["selectedPhase1"]["contentSha256"]) == 64
        if phase1 is not None:
            assert manifest["selectedPhase1"] == phase1
        for row in content["scenarioRows"]:
            assert set(row["subjectRefs"]) <= selected_subjects
            assert set(row["observationRefs"]) <= selected_observations
            for field in ("businessImpact", "protectedInformationLifetime", "confidenceBasis",
                          "technicalReadiness", "vendorConstraints", "organizationalEnablement",
                          "owner", "recommendation", "nextDecision"):
                assert row[field]
    assert "execution authority" in content["boundary"]


class _ReportParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.styles = 0
        self.tags = []
        self.links = []
        self.attributes = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.styles += tag == "style"
        self.attributes.extend(attrs)
        if tag == "a":
            self.links.append(dict(attrs).get("href", ""))


def assert_safe_report_html(html):
    parser = _ReportParser()
    parser.feed(html)
    assert parser.styles == 1
    assert not {"script", "iframe", "object", "embed", "form", "img", "link"} & set(parser.tags)
    assert not any(name.startswith("on") or name == "style" for name, _ in parser.attributes)
    for href in parser.links:
        if href.startswith("#"):
            continue
        url = urlparse(href)
        assert url.scheme == "https"
        assert url.hostname == "nist.gov" or url.hostname.endswith(".nist.gov")
    assert "Save as PDF" in html
    assert "enterpriseCoveragePercent" not in html  # no raw JSON as executive content


def test_guidance_reference_catalog_is_primary_and_status_qualified():
    source = RENDERER.read_text()
    records = re.findall(r'Reference\("([^"\n]+)", "([^"\n]+)", "([^"\n]+)",', source)
    assert len(records) == 8
    assert len({url for _, _, url in records}) == len(records)
    for title, status, url in records:
        parsed = urlparse(url)
        assert parsed.scheme == "https" and parsed.hostname.endswith(".nist.gov")
        assert title and status
    ir8547 = next(row for row in records if "IR 8547" in row[0])
    assert "INITIAL PUBLIC DRAFT" in ir8547[1]
    assert "not final requirements" in ir8547[1]
    agility = next(row for row in records if "39upd1" in row[0])
    assert agility[1].startswith("Final")
    assert agility[2].endswith("/final")


def test_renderer_owns_no_effect_authority_or_latest_report_lookup():
    source = RENDERER.read_text()
    for forbidden in ("HttpClient", "SqliteConnection", "File.Write", "File.Read", "Process.Start",
                      "ORDER BY created_at", '"accepted"] = true', '"executionAuthorized"] = true'):
        assert forbidden not in source
    assert "assessment_report_explicit_phase1_manifest_required" in source
    assert '["selectedPhase1"] = phase == "phase2" ? explicitPhase1Manifest!.DeepClone() : null' in source


def test_unknown_population_is_not_a_fabricated_coverage_percentage():
    source = RENDERER.read_text()
    assert '["populationTotal"] = null' in source
    assert '["coveragePercent"] = null' in source
    assert '["enterpriseCoveragePercent"] = null' in source
    assert "no completeness percentage or statistical confidence is inferred" in source
    assert "willingness, maturity" in source


def test_html_renderer_declares_fixed_csp_style_and_encoding_boundary():
    source = RENDERER.read_text()
    assert "WebUtility.HtmlEncode(value)" in source
    assert "private const string Css" in source
    assert source.count("<style>") == 1
    assert source.count("</style>") == 1
    assert "@media print" in source
    assert "<script" not in source
    assert 'Append(url)' not in source
    assert 'Append(E(url))' in source


def test_workspace_v4_unreviewed_executive_rejects_business_claims_and_wrong_count():
    row = dict(scenarioState="submitted", businessReviewedBy="Not reviewed", businessImpact="Unreviewed outage consequence.",
               protectedInformationLifetime="Unreviewed seven-year statement.", recommendation="Unreviewed migration recommendation.")
    content = dict(manifest={"workspaceTemplateVersion":"pqc.response-to-report.html.v4"}, scenarioRows=[row],
        narrative={"executiveSummary":[
            {"title":"Phase 2 business position","body":"No designated business review has established a reportable scenario interpretation."},
            {"title":"Decision needed","body":"Obtain independent designated business review; no execution is authorized."}]})
    assert_executive_summary(content,phase="phase2")
    changed=copy.deepcopy(content)
    changed["narrative"]["executiveSummary"][0]["body"] += " " + row["businessImpact"]
    with pytest.raises(AssertionError,match="unreviewed_business_claim"):
        assert_executive_summary(changed,phase="phase2")
    changed=copy.deepcopy(content)
    changed["narrative"]["executiveSummary"].append({"title":"Invented finding","body":"No basis."})
    with pytest.raises(AssertionError):
        assert_executive_summary(changed,phase="phase2")


def test_legacy_and_phase1_executive_contract_still_requires_exactly_three():
    content={"manifest":{},"narrative":{"executiveSummary":[{"title":f"Section {n}","body":"Existing report content."} for n in range(3)]}}
    assert_executive_summary(content,phase="phase1")
    assert_executive_summary(content,phase="phase2")
    content["manifest"]["workspaceTemplateVersion"]="pqc.response-to-report.html.v4"
    assert_executive_summary(content,phase="phase1")
    content["narrative"]["executiveSummary"].pop()
    with pytest.raises(AssertionError):
        assert_executive_summary(content,phase="phase1")
