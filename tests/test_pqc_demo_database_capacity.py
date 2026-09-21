"""Bounded synthetic SQLite capacity, with genuine SQLITE_FULL rollback proof.

Only newly generated pytest state is used. Padding is a test-only table in a
stopped test database, never an alteration or pruning of assessment history.
The built DLL must be supplied explicitly; no build or deployment is performed.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess

import pytest

from tests.test_pqc_enterprise_demo_http import (
    Client, Server, Workspace, fixture_input, scope_fields,
)

DLL = os.environ.get("PQC_ENTERPRISE_DEMO_DLL")
pytestmark = pytest.mark.skipif(not DLL, reason="explicit newly built DLL required; no implicit build")
MIB = 1024 * 1024


def database(app):
    return app.data / "enterprise-demo.sqlite3"


def history(path):
    """Read all durable app rows without copying large test-padding BLOBs."""
    with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as db:
        tables = [row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name!='test_capacity_padding' ORDER BY name")]
        return {name: sorted(db.execute('SELECT * FROM "' + name + '"').fetchall(), key=repr) for name in tables}


def assert_history_retained(before, after):
    for table, rows in before.items():
        assert all(row in after[table] for row in rows), table


def refused_start(app, fixture):
    result = subprocess.run([
        "dotnet", str(Path(DLL).resolve()), "--data-dir", str(app.data),
        "--fixture", str(fixture), "--web-root", str(app.web), "--port", str(app.port),
    ], capture_output=True, timeout=20,
        env={**os.environ, "DOTNET_PROCESSOR_COUNT": "1", "DOTNET_gcServer": "0"})
    assert result.returncode == 2
    return result.stderr.decode()


def pad_stopped_test_database(path, target_mib, *, page_size=4096):
    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA journal_mode=DELETE")
        if db.execute("PRAGMA page_size").fetchone()[0] != page_size:
            db.execute(f"PRAGMA page_size={page_size}")
            db.execute("VACUUM")
        assert db.execute("PRAGMA page_size").fetchone()[0] == page_size
        db.execute("CREATE TABLE test_capacity_padding(payload BLOB NOT NULL)")
        pages = db.execute("PRAGMA page_count").fetchone()[0]
        target_pages = target_mib * MIB // page_size
        # Each overflow page spends four bytes on its next-page pointer. Leave
        # a few pages free: enough to open, too few for the next real snapshot.
        size = (target_pages - pages - 3) * (page_size - 4)
        assert size > 0
        db.execute("INSERT INTO test_capacity_padding VALUES(zeroblob(?))", (size,))
        db.commit()
        count = db.execute("PRAGMA page_count").fetchone()[0]
        assert target_pages - 5 <= count < target_pages
        assert db.execute("PRAGMA freelist_count").fetchone()[0] == 0
        assert db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        return count, page_size


@pytest.mark.parametrize("invalid", ["", "0", "129", "513", "unlimited", " 512"])
def test_server_rejects_invalid_capacity_before_creating_database(monkeypatch, tmp_path, fixture_input, invalid):
    app = Server(tmp_path, fixture_input)
    monkeypatch.setenv("PQC_DEMO_DATABASE_MAX_MIB", invalid)
    assert "demo_database_limit_invalid" in refused_start(app, fixture_input)
    assert not database(app).exists()


def test_capacity_setting_does_not_modify_an_unrecognized_database(monkeypatch, tmp_path, fixture_input):
    app = Server(tmp_path, fixture_input)
    path = database(app)
    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA application_id=42")
        db.execute("CREATE TABLE unrelated(value TEXT)")
        db.execute("INSERT INTO unrelated VALUES('synthetic test only')")
        db.commit()
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setenv("PQC_DEMO_DATABASE_MAX_MIB", "512")
    refused_start(app, fixture_input)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("page_size", [4096, 8192])
def test_default_full_write_rolls_back_then_same_request_succeeds_once_with_512(
        monkeypatch, tmp_path, fixture_input, page_size):
    monkeypatch.delenv("PQC_DEMO_DATABASE_MAX_MIB", raising=False)
    app = Server(tmp_path, fixture_input)
    try:
        app.start()
        ws = Workspace(Client(app.origin).login(), mode="fresh")
        ws.command("update_scope", fields=scope_fields(ws))
        report = ws.report("phase1")
        report_path = ws.route + "/reports/" + report["metadata"]["id"]
        fields = {**scope_fields(ws), "objective": "Synthetic capacity retry, with all history retained"}
        payload = ws.payload("update_scope", fields=fields)
        headers = {"Idempotency-Key": "capacity-retry-identical-request"}
        app.stop()
        before = history(database(app))
        pages, size = pad_stopped_test_database(database(app), 128, page_size=page_size)
        snapshot_length = max(len(row[3].encode()) for row in before["assessment_versions"])
        assert (128 * MIB // size - pages) * size < snapshot_length
        app.start()
        client = Client(app.origin).login()
        status, result, _ = client.request(ws.route + "/commands", method="POST", body=payload, headers=headers)
        assert status == 503, result
        assert result == {"error": {"code": "demo_database_capacity_exceeded"}}
        assert history(database(app)) == before, "FULL must not leave commands, events, snapshots or report writes"
        assert client.request(ws.route)[1]["revision"] == payload["expectedRevision"]
        assert client.request(report_path)[1] == report
        app.stop()
        monkeypatch.setenv("PQC_DEMO_DATABASE_MAX_MIB", "512")
        app.start()
        client = Client(app.origin).login()
        status, result, _ = client.request(ws.route + "/commands", method="POST", body=payload, headers=headers)
        assert status == 200, result
        assert result["revision"] == payload["expectedRevision"] + 1
        assert client.request(ws.route + "/commands", method="POST", body=payload, headers=headers)[1] == result
        after = history(database(app))
        assert_history_retained(before, after)
        for table in ("assessment_versions", "assessment_commands", "assessment_events"):
            assert len(after[table]) == len(before[table]) + 1, table
        assert client.request(report_path)[1] == report
    finally:
        app.stop()


def test_projected_220_mib_copy_refuses_default_then_opens_with_512_without_history_loss(
        monkeypatch, tmp_path, fixture_input):
    monkeypatch.delenv("PQC_DEMO_DATABASE_MAX_MIB", raising=False)
    app = Server(tmp_path, fixture_input)
    try:
        app.start()
        ws = Workspace(Client(app.origin).login(), mode="fresh")
        ws.command("update_scope", fields=scope_fields(ws))
        app.stop()
        before = history(database(app))
        # All state here is newly generated; copy via SQLite's backup API to
        # prove the configured larger budget accepts an intact copied store.
        copy_dir = tmp_path / "copied-state"
        copy_dir.mkdir(mode=0o700)
        for source in app.data.iterdir():
            if source.name.endswith(".sqlite3") or source.name in {"instance.lock"}:
                continue
            if source.is_file():
                (copy_dir / source.name).write_bytes(source.read_bytes())
        copy_path = copy_dir / "enterprise-demo.sqlite3"
        with closing(sqlite3.connect(database(app))) as source, closing(sqlite3.connect(copy_path)) as target:
            source.backup(target)
        copied = Server(tmp_path, fixture_input, data=copy_dir)
        pad_stopped_test_database(copy_path, 220)
        assert "demo_database_limit_exceeded" in refused_start(copied, fixture_input)
        assert history(copy_path) == before
        monkeypatch.setenv("PQC_DEMO_DATABASE_MAX_MIB", "512")
        try:
            copied.start()
            client = Client(copied.origin).login()
            assert client.request(ws.route)[1]["revision"] == ws.state["revision"]
            assert history(copy_path) == before
        finally:
            copied.stop()
        assert history(database(app)) == before
    finally:
        app.stop()
