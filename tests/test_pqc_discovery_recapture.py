"""Repeated synthetic captures enrich uses without inventing migration progress."""
from __future__ import annotations

import copy
import os
from urllib.parse import quote

import pytest

from tests.test_pqc_discovery_evidence import DiscoveryJourney, discovery_evidence_server, fixture_input

pytestmark = pytest.mark.skipif(
    not os.environ.get("PQC_ENTERPRISE_DEMO_DLL"), reason="explicit isolated C# build required"
)


def admit(d, **capture):
    result = d.stage(d.products[0], **capture)
    bundle = result["investigation"]["evidenceReviews"][-1]
    d.command(
        "discovery_review_evidence", d.investigation,
        {"batchId": bundle["batchId"], "determination": "qualified",
         "rationale": "Retain this synthetic capture and its source-attributed basis; no independent runtime proof or supersession is asserted."},
        "reviewer",
    )
    d.command("discovery_admit_evidence", d.investigation, {"batchId": bundle["batchId"]})


def analysis(d):
    status, body, _ = d.ws.client.request(d.ws.route + "/analysis")
    assert status == 200, body
    return body


def detail(d, subject_id):
    status, body, _ = d.ws.client.request(d.ws.route + "/assets/" + quote(subject_id, safe=""))
    assert status == 200, body
    return body


def test_recapture_preserves_subject_role_ids_and_immutable_report(discovery_evidence_server):
    d = DiscoveryJourney(discovery_evidence_server).prepare()
    d.gates()
    d.resume_after_restart(discovery_evidence_server)
    admit(d)
    initial = analysis(d)
    assert initial["summary"]["assets"] == 1
    assert initial["summary"]["cryptographicUses"] == 2
    subject = initial["assets"][0]["id"]
    original = detail(d, subject)
    use_ids = {u["use_id"] for u in original["cryptographicUses"]}
    original_observation = original["observations"][0]["observation_id"]
    before = copy.deepcopy(d.ws.report("phase1"))

    # A second endpoint changes the file hash but not the first endpoint's
    # native identity or facts. Both captures must remain as provenance.
    admit(d, count=2)
    after = analysis(d)
    assert after["summary"]["assets"] == 2
    assert after["summary"]["cryptographicUses"] == 4
    current = detail(d, subject)
    refs = {o["observation_id"] for o in current["observations"]}
    assert len(refs) == 2 and original_observation in refs
    assert {u["use_id"] for u in current["cryptographicUses"]} == use_ids
    assert all(set(u["observation_refs"]) == refs for u in current["cryptographicUses"])
    assert all(len(u["algorithm_variants"]) == 1 for u in current["cryptographicUses"])
    assert not next(a for a in after["assets"] if a["id"] == subject)["isDisputed"]
    report = d.ws.report("phase1")
    assert report["content"]["summary"]["observations"] == 3
    assert len(set(report["content"]["manifest"]["observationRefs"])) == 3
    assert len(report["content"]["findings"]) == 2
    assert d.ws.client.request(d.ws.route + "/reports/" + before["metadata"]["id"])[1] == before


def test_basis_change_is_not_conflict_but_crypto_change_remains_disputed(discovery_evidence_server):
    d = DiscoveryJourney(discovery_evidence_server).prepare()
    d.gates()
    d.resume_after_restart(discovery_evidence_server)
    admit(d, basis="configured")
    subject = analysis(d)["assets"][0]["id"]
    original_ids = {u["use_id"] for u in detail(d, subject)["cryptographicUses"]}
    admit(d, basis="observed")
    corroborated = analysis(d)
    assert corroborated["summary"]["assets"] == 1
    assert corroborated["summary"]["cryptographicUses"] == 2
    assert not corroborated["assets"][0]["isDisputed"]
    assert corroborated["findings"][0]["exposure"] == "classical_public_key_recorded"
    uses = detail(d, subject)["cryptographicUses"]
    assert {u["use_id"] for u in uses} == original_ids
    assert all(u["evidence_bases"] == ["configured", "observed"] for u in uses)
    assert all(len(u["observation_refs"]) == 2 for u in uses)
    assert all(u["independently_verified"] is False for u in uses)
    before = copy.deepcopy(d.ws.report("phase1"))

    # Later hybrid data is not permission to discard the earlier classical
    # fact. Current selection requires an explicit disposition, not a timestamp.
    admit(d, hybrid=True, basis="configured")
    disputed = analysis(d)
    assert disputed["summary"]["assets"] == 1
    assert disputed["summary"]["cryptographicUses"] == 2
    assert disputed["assets"][0]["isDisputed"]
    assert disputed["findings"][0]["exposure"] == "conflicting_cryptographic_evidence"
    assert disputed["findings"][0]["readiness"] == "evidence_prerequisites_missing"
    current = detail(d, subject)
    assert {u["use_id"] for u in current["cryptographicUses"]} == original_ids
    roles = {u["role"]: u for u in current["cryptographicUses"]}
    assert roles["transport_key_exchange"]["algorithm_variants"] == ["X25519", "X25519MLKEM768"]
    assert roles["transport_key_exchange"]["algorithm_posture"] == "unknown"
    assert "cryptographic_parameters_unknown" in roles["transport_key_exchange"]["limitation_codes"]
    assert roles["certificate_signature"]["algorithm_posture"] == "classical_method_review_candidate"
    assert all(len(u["observation_refs"]) == 3 for u in roles.values())
    after = d.ws.report("phase1")
    assert after["content"]["findings"][0]["exposure"] == "conflicting_cryptographic_evidence"
    assert len(after["content"]["manifest"]["observationRefs"]) == 3
    assert d.ws.client.request(d.ws.route + "/reports/" + before["metadata"]["id"])[1] == before
