"""Complete-questionnaire HTTP contracts; explicit built DLL and template file only.

Uses isolated synthetic state. Never builds, downloads, sends communications or
records enterprise/owner acceptance. Original template text is read-only input.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
from uuid import uuid4

import pytest

from tests.test_pqc_enterprise_demo_http import Client, Server, Workspace, fixture_input

DLL = os.environ.get("PQC_ENTERPRISE_DEMO_DLL")
CATALOG = os.environ.get("PQC_QUESTIONNAIRE_CATALOG_FILE")
pytestmark = pytest.mark.skipif(not DLL or not CATALOG, reason="explicit candidate DLL and original template catalog required")


@pytest.fixture
def questionnaire_server(tmp_path, fixture_input):
    server = Server(tmp_path, fixture_input)
    try:
        yield server.start()
    finally:
        server.stop()


class Forms:
    def __init__(self, server):
        self.ws = Workspace(Client(server.origin).login(), "fresh")
        self.route = self.ws.route + "/questionnaires"

    def actor(self, role="analyst"):
        return self.ws.actor(role)

    def revision(self):
        return self.ws.refresh()["revision"]

    def command(self, operation, target=None, fields=None, role="analyst", expected=200, key=None, revision=None):
        body = {"operation": operation, "targetId": target, "fields": fields or {},
            "expectedRevision": self.revision() if revision is None else revision}
        result = self.actor(role).request(self.route + "/commands", method="POST", body=body,
            headers={"Idempotency-Key": key or uuid4().hex})
        assert result[0] == expected, (operation, result[0], result[1])
        return result[1]

    def create(self, template="SRC-RFI-003", recipient="contributor", label="Synthetic east deployment"):
        result = self.command("questionnaire_create", fields={"templateId": template,
            "title": "Synthetic source questionnaire", "assignedTo": "synthetic-demo:" + recipient,
            "deployment": {"label": label, "product": "Synthetic reference product", "environment": "synthetic-test"}})
        return result["assignments"][-1]["id"]

    def detail(self, assignment, role="analyst"):
        result = self.actor(role).request(self.route + "/" + assignment)
        assert result[0] == 200, result[1]
        return result[1]


def all_unresolved(detail):
    return {question["id"]: {"status": "unknown", "text": "", "evidenceRefs": [],
        "rationale": "Synthetic source route awaits a bounded response.",
        "nextOwner": "Synthetic platform coordination function", "nextDate": "2026-09-22",
        "blocker": "Synthetic representative export not supplied", "scheduleEffect": "blocks_source_profile"}
        for question in detail["assignment"]["template"]["questions"]}


def test_original_27_form_catalog_and_exact_question_snapshots(questionnaire_server):
    forms = Forms(questionnaire_server)
    status, index, _ = forms.actor().request(forms.route)
    assert status == 200 and index["catalog"]["available"]
    templates = index["catalog"]["templates"]
    assert {template["id"] for template in templates} == {f"SRC-RFI-{i:03d}" for i in range(1, 28)}
    assert all(len(template["questions"]) == 27 for template in templates)
    assert sum(len(template["questions"]) for template in templates) == 729
    original = json.loads(Path(CATALOG).read_text())
    original_template = next(template for template in original["templates"] if template["id"] == "SRC-RFI-003")
    assignment = forms.create()
    detail = forms.detail(assignment, "contributor")
    assert detail["assignment"]["template"]["questions"] == original_template["questions"]
    assert detail["assignment"]["templateVersion"] == original["catalogVersion"]
    assert detail["assignment"]["sourceSha256"] == original["sourceSha256"]
    assert detail["assignment"]["operatingContract"] == original["operatingContract"]
    assert len(detail["assignment"]["answers"]) == 27
    assert all(answer["status"] == "unanswered" for answer in detail["assignment"]["answers"].values())
    assert not detail["validation"]["canSubmit"]
    assert forms.ws.refresh()["intake"]["requests"] == []


def test_assignments_are_separate_deployments_and_contributor_scoped(questionnaire_server):
    forms = Forms(questionnaire_server)
    assert forms.actor("contributor").request(forms.route)[0] == 403
    assert forms.actor("contributor").request("/api/assessments")[1] == []
    first = forms.create(label="Synthetic same-named deployment")
    second = forms.create(recipient="contributor-two", label="Synthetic same-named deployment")
    assert first != second
    assert forms.detail(first)["assignment"]["deployment"]["id"] != forms.detail(second)["assignment"]["deployment"]["id"]
    for role, visible, hidden in (("contributor", first, second), ("contributor-two", second, first)):
        status, index, _ = forms.actor(role).request(forms.route)
        assert status == 200
        assert [assignment["id"] for assignment in index["assignments"]] == [visible]
        assert index["catalog"]["templates"] == []
        assert forms.actor(role).request(forms.route + "/" + hidden)[0] == 403
        assert forms.actor(role).request(forms.ws.route)[0] == 403
        assert forms.actor(role).request(forms.ws.route + "/reports")[0] == 403
        assert forms.ws.state["id"] in {row["id"] for row in forms.actor(role).request("/api/assessments")[1]}
    forms.command("questionnaire_save", second, {"answers": {}}, role="contributor", expected=403)
    forms.command("questionnaire_create", fields={"templateId": "SRC-RFI-003", "title": "Denied", "assignedTo": "synthetic-demo:contributor",
        "deployment": {"label": "No", "product": "", "environment": ""}}, role="contributor", expected=403)


def test_partial_save_validation_and_explicit_unknown_submission(questionnaire_server):
    forms = Forms(questionnaire_server)
    assignment = forms.create()
    qid = "SRC-RFI-003/CQ-01"
    partial = forms.command("questionnaire_save", assignment, {"answers": {qid: {"status": "answered", "text": "Synthetic incomplete profile"}}}, "contributor")
    assert partial["assignment"]["answers"][qid]["recordedBy"] == "synthetic-demo:contributor"
    assert partial["assignment"]["answers"][qid]["assertedBy"] == "synthetic-demo:contributor"
    assert partial["assignment"]["status"] == "draft"
    assert not partial["validation"]["canSubmit"]
    assert any(issue["questionId"] == qid and issue["field"] == "evidenceRefs" for issue in partial["validation"]["issues"])
    forms.command("questionnaire_submit", assignment, role="contributor", expected=409)
    answers = all_unresolved(partial)
    saved = forms.command("questionnaire_save", assignment, {"answers": answers}, "contributor")
    assert saved["validation"]["canSubmit"]
    submitted = forms.command("questionnaire_submit", assignment, role="contributor")
    assert submitted["assignment"]["status"] == "submitted"
    assert not submitted["canEdit"]
    assert len(submitted["assignment"]["submission"]["unresolvedQuestionIds"]) == 27
    forms.command("questionnaire_save", assignment, {"answers": {}}, "contributor", expected=409)
    state = forms.ws.refresh()
    assert all(gate["state"] == "not_submitted" for gate in state["gates"])
    assert not state["documents"]
    assert all(not source["observationIds"] for source in state["sources"])


def test_controlled_attestation_is_a_response_not_authenticated_approval(questionnaire_server):
    forms = Forms(questionnaire_server)
    assignment = forms.create()
    detail = forms.detail(assignment)
    answers = all_unresolved(detail)
    qid = "SRC-RFI-003/CQ-24"
    answers[qid] = {"status": "answered", "text": "yes_with_qualifications", "evidenceRefs": ["synthetic-reference:owner-response"]}
    partial = forms.command("questionnaire_save", assignment, {"answers": answers}, "contributor")
    fields = {issue["field"] for issue in partial["validation"]["issues"] if issue["questionId"] == qid}
    assert {"attestationOwner", "attestationDate", "attestationQualification"} <= fields
    answers[qid].update(attestationOwner="Synthetic named source owner", attestationDate="2026-09-08",
        attestationQualification="All technical questions remain explicitly unknown.")
    ready = forms.command("questionnaire_save", assignment, {"answers": {qid: answers[qid]}}, "contributor")
    assert ready["validation"]["canSubmit"]
    submitted = forms.command("questionnaire_submit", assignment, role="contributor")
    assert submitted["assignment"]["answers"][qid]["text"] == "yes_with_qualifications"
    assert all(gate["state"] == "not_submitted" for gate in forms.ws.refresh()["gates"])
    forms.command("questionnaire_reopen", assignment, {"reason": "Synthetic correction of the response"})
    invalid = forms.command("questionnaire_save", assignment, {"answers": {qid: {"text": "APPROVED"}}}, "contributor")
    assert any(issue["field"] == "text" for issue in invalid["validation"]["issues"])


def test_replay_revision_conflicts_and_reassignment_revoke_previous_access(questionnaire_server):
    forms = Forms(questionnaire_server)
    revision = forms.revision()
    fields = {"templateId": "SRC-RFI-003", "title": "Synthetic replay", "assignedTo": "synthetic-demo:contributor",
        "deployment": {"label": "Synthetic replay deployment", "product": "", "environment": ""}}
    key = uuid4().hex
    first = forms.command("questionnaire_create", fields=fields, revision=revision, key=key)
    assert forms.command("questionnaire_create", fields=fields, revision=revision, key=key) == first
    forms.command("questionnaire_create", fields={**fields, "title": "Changed"}, revision=revision, key=key, expected=409)
    assert len(forms.actor().request(forms.route)[1]["assignments"]) == 1
    assignment = first["assignments"][0]["id"]
    response_key = uuid4().hex
    response_revision = forms.revision()
    answer_fields = {"answers": {"SRC-RFI-003/CQ-01": {"text": "Synthetic old response"}}}
    forms.command("questionnaire_save", assignment, answer_fields, "contributor", key=response_key, revision=response_revision)
    forms.command("questionnaire_save", assignment, answer_fields, "contributor", revision=response_revision, expected=409)
    forms.command("questionnaire_reassign", assignment, {"assignedTo": "synthetic-demo:contributor-two", "reason": "Synthetic correct routing"})
    assert forms.actor("contributor").request(forms.route + "/" + assignment)[0] == 403
    forms.command("questionnaire_save", assignment, answer_fields, "contributor", key=response_key, revision=response_revision, expected=403)
    assert forms.detail(assignment, "contributor-two")["assignment"]["answers"]["SRC-RFI-003/CQ-01"]["recordedBy"] == "synthetic-demo:contributor"


def test_wrong_question_and_forged_identity_rejected_and_restart_preserves_snapshot(questionnaire_server):
    forms = Forms(questionnaire_server)
    assignment = forms.create()
    forms.command("questionnaire_save", assignment, {"answers": {"SRC-RFI-002/CQ-01": {"text": "Wrong source form"}}}, "contributor", expected=400)
    forms.command("questionnaire_save", assignment, {"answers": {"SRC-RFI-003/CQ-01": {"recordedBy": "synthetic-demo:sponsor"}}}, "contributor", expected=400)
    forms.command("questionnaire_save", assignment, {"answers": {"SRC-RFI-003/CQ-01": {"assertedBy": "synthetic-demo:sponsor"}}}, "contributor", expected=400)
    saved = forms.command("questionnaire_save", assignment, {"answers": {"SRC-RFI-003/CQ-01": {
        "text": "Synthetic meeting response", "assertedBy": "Synthetic meeting respondent"}}})
    answer = saved["assignment"]["answers"]["SRC-RFI-003/CQ-01"]
    assert answer["assertedBy"] == "Synthetic meeting respondent"
    assert answer["recordedBy"] == "synthetic-demo:analyst"
    # Web form round-trips may include unchanged answer fields. Editing a
    # different question must not erase previously attributed statements.
    untouched = {key: value for key, value in answer.items() if key != "recordedBy"}
    continued = forms.command("questionnaire_save", assignment, {"answers": {
        "SRC-RFI-003/CQ-01": untouched,
        "SRC-RFI-003/CQ-02": {"text": "Synthetic contributor's own correction"}}}, "contributor")
    assert continued["assignment"]["answers"]["SRC-RFI-003/CQ-01"] == answer
    assert continued["assignment"]["answers"]["SRC-RFI-003/CQ-02"]["assertedBy"] == "synthetic-demo:contributor"
    edited = forms.command("questionnaire_save", assignment, {"answers": {
        "SRC-RFI-003/CQ-01": {**untouched, "text": "Synthetic contributor's revised statement"}}}, "contributor")
    assert edited["assignment"]["answers"]["SRC-RFI-003/CQ-01"]["assertedBy"] == "synthetic-demo:contributor"
    before = forms.detail(assignment)
    questionnaire_server.stop()
    questionnaire_server.start()
    assert forms.actor().request(forms.route + "/" + assignment)[0] == 401
    forms.actor().login()
    assert forms.detail(assignment) == before


def test_backup_restore_preserves_pinned_draft_and_submission_without_original_catalog(tmp_path, fixture_input, monkeypatch):
    """Catalog availability or a newer edition cannot rewrite assigned forms."""
    server = Server(tmp_path, fixture_input)
    try:
        server.start()
        forms = Forms(server)
        draft_id = forms.create(label="Synthetic draft deployment")
        submitted_id = forms.create(label="Synthetic submitted deployment")
        forms.command("questionnaire_save", draft_id, {"answers": {
            "SRC-RFI-003/CQ-01": {"status": "unknown", "text": "Synthetic draft retained exactly",
                "rationale": "Partial response, intentionally not ready to submit."}}}, "contributor")
        forms.command("questionnaire_save", submitted_id,
            {"answers": all_unresolved(forms.detail(submitted_id))}, "contributor")
        forms.command("questionnaire_submit", submitted_id, role="contributor")
        before = {assignment: forms.detail(assignment) for assignment in (draft_id, submitted_id)}
        state_before = forms.ws.refresh()
        assert before[draft_id]["assignment"]["status"] == "draft"
        assert before[submitted_id]["assignment"]["submission"]["contentSha256"]
        server.stop()

        backup = tmp_path / "questionnaire-backup"
        completed = subprocess.run(["dotnet", str(Path(DLL).resolve()), "--data-dir", str(server.data),
            "--fixture", str(fixture_input), "--backup-dir", str(backup)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        assert completed.returncode == 0, "isolated questionnaire backup failed"
        restored_path = tmp_path / "questionnaire-restored-copy"
        shutil.copytree(backup, restored_path)
        server.data = restored_path

        # Restart with no external catalog: existing pinned forms remain usable.
        monkeypatch.delenv("PQC_QUESTIONNAIRE_CATALOG_FILE", raising=False)
        server.start()
        restored = Client(server.origin).login()
        assert restored.request(forms.route)[1]["catalog"]["available"] is False
        for assignment, snapshot in before.items():
            assert restored.request(forms.route + "/" + assignment)[1] == snapshot
        assert restored.request(forms.ws.route)[1] == state_before
        server.stop()

        # Supply a synthetic newer catalog without touching the original file.
        changed = json.loads(Path(CATALOG).read_text())
        changed["sourceSha256"] = "1" * 64
        changed["catalogVersion"] = changed["sourceSchemaVersion"] + "@sha256:" + changed["sourceSha256"]
        changed_template = next(t for t in changed["templates"] if t["id"] == "SRC-RFI-003")
        changed_template["title"] = "Synthetic newer template title"
        changed_template["questions"][0]["prompt"] = "Synthetic newer question, not the assigned question."
        changed_path = tmp_path / "synthetic-newer-catalog.json"
        changed_path.write_text(json.dumps(changed))
        changed_path.chmod(0o600)
        monkeypatch.setenv("PQC_QUESTIONNAIRE_CATALOG_FILE", str(changed_path))
        server.start()
        restored = Client(server.origin).login()
        assert restored.request(forms.route)[1]["catalog"]["catalogVersion"] == changed["catalogVersion"]
        for assignment, snapshot in before.items():
            assert restored.request(forms.route + "/" + assignment)[1] == snapshot
        assert restored.request(forms.ws.route)[1] == state_before
        server.stop()
        with sqlite3.connect(restored_path / "enterprise-demo.sqlite3") as database:
            assert database.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            for table in ("assessment_versions", "assessment_commands", "assessment_events"):
                with pytest.raises(sqlite3.DatabaseError, match="immutable"):
                    database.execute(f"DELETE FROM {table}")
    finally:
        server.stop()


def test_reopen_and_reassignment_reasons_are_preserved_in_immutable_snapshots(questionnaire_server):
    forms = Forms(questionnaire_server)
    assignment = forms.create()
    forms.command("questionnaire_save", assignment,
        {"answers": all_unresolved(forms.detail(assignment))}, "contributor")
    submitted = forms.command("questionnaire_submit", assignment, role="contributor")
    submitted_revision = submitted["revision"]
    submitted_sha = submitted["assignment"]["submission"]["contentSha256"]
    reopened = forms.command("questionnaire_reopen", assignment,
        {"reason": "Synthetic returned response requires a clarified product boundary."})
    reopen_entry = reopened["assignment"]["history"][0]
    assert reopen_entry["operation"] == "questionnaire_reopen"
    assert reopen_entry["reason"] == "Synthetic returned response requires a clarified product boundary."
    assert reopen_entry["actor"] == "synthetic-demo:analyst"
    assert reopen_entry["revision"] == reopened["revision"]
    assert reopen_entry["occurredAt"]
    assert reopen_entry["previousSubmissionSha256"] == submitted_sha
    reassigned = forms.command("questionnaire_reassign", assignment,
        {"assignedTo": "synthetic-demo:contributor-two", "reason": "Synthetic original recipient referred the deployment."})
    reassign_entry = reassigned["assignment"]["history"][1]
    assert reassign_entry["operation"] == "questionnaire_reassign"
    assert reassign_entry["reason"] == "Synthetic original recipient referred the deployment."
    assert reassign_entry["actor"] == "synthetic-demo:analyst"
    assert reassign_entry["previousAssignedTo"] == "synthetic-demo:contributor"
    assert reassign_entry["assignedTo"] == "synthetic-demo:contributor-two"
    assert reassign_entry["revision"] == reassigned["revision"]
    assert reassign_entry["occurredAt"]
    latest = forms.command("questionnaire_reassign", assignment,
        {"assignedTo": "synthetic-demo:contributor", "reason": "Synthetic corrected referral returns to original recipient."})
    assert latest["assignment"]["history"][:2] == [reopen_entry, reassign_entry]
    with sqlite3.connect(questionnaire_server.data / "enterprise-demo.sqlite3") as database:
        def pinned(revision):
            snapshot = json.loads(database.execute(
                "SELECT snapshot_json FROM assessment_versions WHERE assessment_id=? AND revision=?",
                (forms.ws.state["id"], revision)).fetchone()[0])
            return next(a for a in snapshot["questionnaires"]["assignments"] if a["id"] == assignment)
        assert pinned(submitted_revision)["submission"]["contentSha256"] == submitted_sha
        assert pinned(submitted_revision)["history"] == []
        assert pinned(reopened["revision"])["history"] == [reopen_entry]
