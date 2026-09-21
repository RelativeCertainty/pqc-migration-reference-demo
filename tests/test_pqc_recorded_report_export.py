"""Read-only export preserves report bytes; it never regenerates missing reports."""
from contextlib import closing
import json
import sqlite3

import pytest

from scripts import export_pqc_recorded_reports as exporter

ASSESSMENT = "assessment-" + "a" * 32
P1 = "assessment-report-" + "b" * 32
P2 = "assessment-report-" + "c" * 32


def prepared(monkeypatch, tmp_path):
    monkeypatch.setattr(exporter, "ROOT", tmp_path)
    root = tmp_path / "artifacts/pqc-enterprise-demo"
    state = root / "state"
    state.mkdir(parents=True, mode=0o700)
    (state / ".synthetic-demo-store").write_bytes(exporter.MARKER)
    snapshot = {"id": ASSESSMENT, "phase1InputReportId": P1, "gates": [
        {"id": "PQC-P1-G03", "documentId": P1, "state": "qualified"},
        {"id": "PQC-P2-G03", "documentId": P2, "state": "qualified"}]}
    first = '{"title":"Synthetic exact P1", "manifest":{}}'
    p1_hash = exporter.digest(first.encode())
    second = json.dumps({"title": "Synthetic exact P2", "manifest": {"selectedPhase1": {"reportId": P1, "contentSha256": p1_hash}}})
    with closing(sqlite3.connect(state / "enterprise-demo.sqlite3")) as db:
        db.executescript("""PRAGMA user_version=4;
            CREATE TABLE assessment_versions(assessment_id,revision,snapshot_sha256,snapshot_json);
            CREATE TABLE assessment_documents(assessment_id,id,phase,created_at,content_sha256,content_json,input_fingerprint,assessment_revision,phase1_report_id);
            CREATE TABLE workspace_report_html(assessment_id,report_id,content_sha256,html);""")
        # Keep the exact application's magic value explicit instead of decimal drift.
        db.execute(f"PRAGMA application_id={0x50514345}")
        value = json.dumps(snapshot)
        db.execute("INSERT INTO assessment_versions VALUES(?,?,?,?)", (ASSESSMENT, 123, exporter.digest(value.encode()), value))
        for report, phase, content in ((P1, "phase1", first), (P2, "phase2", second)):
            html = "<!doctype html><html><body><h1>" + phase + " — stored synthetic report</h1></body></html>\n"
            db.execute("INSERT INTO assessment_documents VALUES(?,?,?,?,?,?,?,?,?)", (ASSESSMENT, report, phase, "2026-09-17T20:00:00Z", exporter.digest(content.encode()), content, "input-digest", 120, P1 if phase == "phase2" else None))
            db.execute("INSERT INTO workspace_report_html VALUES(?,?,?,?)", (ASSESSMENT, report, exporter.digest(html.encode()), html))
        db.commit()
    return state, root / "export", first, second


def test_export_exact_bytes_and_hashes_without_database_writes(monkeypatch, tmp_path):
    state, output, p1, p2 = prepared(monkeypatch, tmp_path)
    database = state / "enterprise-demo.sqlite3"
    before = database.read_bytes()
    result = exporter.export(state, output, ASSESSMENT, P1, P2)
    assert database.read_bytes() == before
    assert (output / "Phase_1_Current_State.content.json").read_bytes() == p1.encode()
    assert (output / "Phase_2_Risk_and_Recommendations.content.json").read_bytes() == p2.encode()
    for entry in result["files"]:
        assert exporter.digest((output / entry["name"]).read_bytes()) == entry["sha256"]
    assert result["assessmentRevision"] == 123
    assert all(row["enterpriseAcceptance"] == "not_recorded" for row in result["reports"])
    assert output.stat().st_mode & 0o077 == 0
    with pytest.raises(ValueError, match="new_output_outside_state_required"):
        exporter.export(state, output, ASSESSMENT, P1, P2)


@pytest.mark.parametrize("problem", ["missing_html", "html_hash", "lineage", "wrong_assessment", "unreviewed"])
def test_refuse_missing_corrupt_or_unreviewed_exact_reports(monkeypatch, tmp_path, problem):
    state, output, _, _ = prepared(monkeypatch, tmp_path)
    with closing(sqlite3.connect(state / "enterprise-demo.sqlite3")) as db:
        if problem == "missing_html":
            db.execute("DELETE FROM workspace_report_html WHERE report_id=?", (P2,))
        elif problem == "html_hash":
            db.execute("UPDATE workspace_report_html SET html='altered' WHERE report_id=?", (P2,))
        elif problem == "lineage":
            db.execute("UPDATE assessment_documents SET phase1_report_id=? WHERE id=?", (P2, P2))
        elif problem == "wrong_assessment":
            db.execute("UPDATE assessment_documents SET assessment_id='other' WHERE id=?", (P2,))
        elif problem == "unreviewed":
            value = json.loads(db.execute("SELECT snapshot_json FROM assessment_versions").fetchone()[0])
            value["gates"][1]["state"] = "submitted"
            raw = json.dumps(value)
            db.execute("UPDATE assessment_versions SET snapshot_json=?,snapshot_sha256=?", (raw, exporter.digest(raw.encode())))
        db.commit()
    with pytest.raises(ValueError):
        exporter.export(state, output, ASSESSMENT, P1, P2)
    assert not output.exists()


def test_refuse_symlink_and_output_in_state(monkeypatch, tmp_path):
    state, output, _, _ = prepared(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="new_output_outside_state_required"):
        exporter.export(state, state / "bad-output", ASSESSMENT, P1, P2)
    link = state.parent / "linked-state"
    link.symlink_to(state, target_is_directory=True)
    with pytest.raises(ValueError, match="isolated_nonsymlink_path_required"):
        exporter.export(link, output, ASSESSMENT, P1, P2)
