#!/usr/bin/env python3
"""Export exact stored synthetic report bytes, never generate or approve reports.

This is an explicitly invoked, owner-local artifact-custody operation, not an
application endpoint or authentication bypass. The operator must supply the
isolated state directory and both exact report IDs from the browser assessment.
No sessions, credentials, HTTP requests, report rendering or DB writes occur.
PDF reading copies can subsequently use render_pqc_workspace_reports.py.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
MARKER = b"pqc-enterprise-demo-synthetic-only-v1\n"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def isolated_path(path: Path, *, exists: bool) -> Path:
    path = path.absolute()
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("isolated_nonsymlink_path_required")
    path = path.resolve(strict=exists)
    if not path.is_relative_to(ROOT / "artifacts/pqc-enterprise-demo"):
        raise ValueError("isolated_demo_artifacts_path_required")
    return path


def export(state_dir: Path, output: Path, assessment_id: str, phase1_id: str, phase2_id: str):
    os.umask(0o077)
    for value, prefix in ((assessment_id, "assessment"), (phase1_id, "assessment-report"), (phase2_id, "assessment-report")):
        if not re.fullmatch(prefix + r"-[a-f0-9]{32}", value):
            raise ValueError("explicit_exact_assessment_and_report_ids_required")
    if phase1_id == phase2_id:
        raise ValueError("distinct_report_ids_required")
    state_dir = isolated_path(state_dir, exists=True)
    output = isolated_path(output, exists=False)
    if output.exists() or output.is_relative_to(state_dir):
        raise ValueError("new_output_outside_state_required")
    marker = isolated_path(state_dir / ".synthetic-demo-store", exists=True)
    if marker.read_bytes() != MARKER or state_dir.stat().st_mode & 0o077:
        raise ValueError("owner_only_synthetic_state_required")
    database = isolated_path(state_dir / "enterprise-demo.sqlite3", exists=True)
    for suffix in ("-wal", "-shm"):
        isolated_path(Path(str(database) + suffix), exists=False)
    assets = []
    report_metadata = []
    # mode=ro includes committed WAL state. Do not use immutable=1, which would
    # ignore a live WAL. All reads below share one consistent read transaction.
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=5)) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        if db.execute("PRAGMA application_id").fetchone()[0] != 0x50514345 or db.execute("PRAGMA user_version").fetchone()[0] != 4:
            raise ValueError("qualified_synthetic_schema_required")
        snapshot = db.execute("SELECT revision,snapshot_sha256,snapshot_json FROM assessment_versions WHERE assessment_id=? ORDER BY revision DESC LIMIT 1", (assessment_id,)).fetchone()
        if snapshot is None or digest(snapshot[2].encode()) != snapshot[1]:
            raise ValueError("assessment_snapshot_missing_or_corrupt")
        current = json.loads(snapshot[2])
        if current.get("id") != assessment_id or current.get("phase1InputReportId") != phase1_id:
            raise ValueError("exact_phase1_selection_required")
        gates = {gate["id"]: gate for gate in current.get("gates", [])}
        for gate_id, report_id in (("PQC-P1-G03", phase1_id), ("PQC-P2-G03", phase2_id)):
            gate = gates.get(gate_id, {})
            if gate.get("documentId") != report_id or gate.get("state") not in ("accepted", "qualified"):
                raise ValueError("exact_final_simulated_gate_review_required")
        for phase, report_id, stem in (("phase1", phase1_id, "Phase_1_Current_State"), ("phase2", phase2_id, "Phase_2_Risk_and_Recommendations")):
            row = db.execute("SELECT phase,created_at,content_sha256,content_json,input_fingerprint,assessment_revision,phase1_report_id FROM assessment_documents WHERE assessment_id=? AND id=?", (assessment_id, report_id)).fetchone()
            html = db.execute("SELECT content_sha256,html FROM workspace_report_html WHERE assessment_id=? AND report_id=?", (assessment_id, report_id)).fetchone()
            if row is None or html is None or row[0] != phase:
                raise ValueError("exact_frozen_report_missing")
            content_bytes, html_bytes = row[3].encode(), html[1].encode()
            if max(len(content_bytes), len(html_bytes)) > 8 * 1024**2:
                raise ValueError("bounded_report_size_exceeded")
            if digest(content_bytes) != row[2] or digest(html_bytes) != html[0]:
                raise ValueError("stored_report_hash_mismatch")
            content = json.loads(row[3])
            selected = content.get("manifest", {}).get("selectedPhase1")
            if phase == "phase2" and (row[6] != phase1_id or not isinstance(selected, dict)
                    or selected.get("reportId") != phase1_id or selected.get("contentSha256") != report_metadata[0]["contentSha256"]):
                raise ValueError("phase2_lineage_mismatch")
            metadata = {"id": report_id, "phase": phase, "createdAt": row[1], "contentSha256": row[2],
                "htmlSha256": html[0], "inputFingerprint": row[4], "assessmentRevision": row[5],
                "selectedPhase1ReportId": row[6], "synthetic": True, "enterpriseAcceptance": "not_recorded"}
            report_metadata.append(metadata)
            # Raw stored content stays byte-for-byte intact. Metadata is separate.
            assets.extend([(stem + ".html", html_bytes), (stem + ".content.json", content_bytes)])
        db.rollback()
    manifest = {"schemaVersion": "pqc.recorded-assessment.report-export.v1", "synthetic": True,
        "assessmentId": assessment_id, "assessmentRevision": snapshot[0], "snapshotSha256": snapshot[1],
        "exportedAt": datetime.now(timezone.utc).isoformat(), "reports": report_metadata,
        "files": [{"name": name, "bytes": len(data), "sha256": digest(data)} for name, data in assets],
        "authorityBoundary": "Read-only export of exact stored reports. Simulated gate decisions are not enterprise or owner acceptance. Recording linkage requires separate browser/video evidence; no API rehearsal is substituted."}
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, data in assets:
        with (output / name).open("xb") as stream:
            stream.write(data)
    with (output / "report-export-manifest.json").open("x") as stream:
        stream.write(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--assessment-id", required=True)
    parser.add_argument("--phase1-report-id", required=True)
    parser.add_argument("--phase2-report-id", required=True)
    args = parser.parse_args()
    try:
        result = export(args.state_dir, args.output, args.assessment_id, args.phase1_report_id, args.phase2_report_id)
    except (OSError, ValueError, KeyError, sqlite3.Error):
        raise SystemExit("Recorded report export refused: inspect explicit IDs, final simulated gates, stored hashes and isolated paths. No report was generated.") from None
    print(json.dumps({"assessmentId": result["assessmentId"], "reportIds": [row["id"] for row in result["reports"]], "files": len(result["files"])}))


if __name__ == "__main__":
    main()
