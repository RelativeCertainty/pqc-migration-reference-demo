"""Isolated schema evolution, durability and paired application/state rollback.

Both DLLs must be explicitly supplied. All application state is newly generated
under pytest temporary directories; no owner-operated database is copied/opened.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess

import pytest

from tests.test_pqc_enterprise_demo_http import Client, Server, Workspace, fixture_input

DLL=os.environ.get("PQC_ENTERPRISE_DEMO_DLL")
PREVIOUS=os.environ.get("PQC_ENTERPRISE_PREVIOUS_DLL")
pytestmark=pytest.mark.skipif(not DLL or not PREVIOUS,reason="explicit current and preserved v3 DLLs required; no implicit build/deployment")


def sql_state(folder):
    with sqlite3.connect(folder/"enterprise-demo.sqlite3") as db:
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        rows={table:sorted(db.execute('SELECT * FROM "'+table+'"').fetchall(),key=repr) for table in tables}
        return db.execute("PRAGMA user_version").fetchone()[0],rows


def backup(dll,source,fixture,destination):
    result=subprocess.run(["dotnet",str(Path(dll).resolve()),"--data-dir",str(source),"--fixture",str(fixture),"--backup-dir",str(destination)],
        capture_output=True,timeout=25,env={**os.environ,"DOTNET_PROCESSOR_COUNT":"1","DOTNET_gcServer":"0"})
    assert result.returncode==0,"isolated synthetic backup command failed"


def refused_start(dll,source,fixture,folder):
    result=subprocess.run(["dotnet",str(Path(dll).resolve()),"--data-dir",str(source),"--fixture",str(fixture),"--web-root",str(folder)],
        capture_output=True,timeout=20,env={**os.environ,"DOTNET_PROCESSOR_COUNT":"1","DOTNET_gcServer":"0"})
    assert result.returncode!=0,"invalid isolated schema must not start"
    return result


def v3_state(folder,fixture):
    server=Server(folder,fixture,dll=PREVIOUS)
    try:
        server.start()
        ws=Workspace(Client(server.origin).login(),name="Synthetic migration preservation case")
        report=ws.report("phase1")
        state=ws.refresh()
    finally:server.stop()
    assert sql_state(server.data)[0]==3,"provided previous release is not schema v3"
    return server,state,report


def test_v3_additive_migration_retains_old_records_and_new_frozen_report_survives_restart_restore(tmp_path,fixture_input):
    server,old_state,old_report=v3_state(tmp_path,fixture_input)
    _,before=sql_state(server.data)
    server.dll=DLL
    try:
        server.start()
        client=Client(server.origin).login()
        route="/api/assessments/"+old_state["id"]
        assert client.request(route+"/reports/"+old_report["metadata"]["id"])[1]==old_report
        status,current,_=client.request(route)
        assert status==200 and current["revision"]==old_state["revision"]
        # Exercise a fresh report through current API; its rendered HTML must be
        # immutable stored bytes rather than a future rerender of mutable state.
        ws=Workspace(client,name="Synthetic v4 immutable report")
        report=ws.report("phase1")
        download=ws.route+"/reports/"+report["metadata"]["id"]+"/download?format=html"
        status,html,_=client.request(download);assert status==200
        frozen_digest=hashlib.sha256(html.encode()).hexdigest()
        report_route=ws.route+"/reports/"+report["metadata"]["id"]
        server.stop()
        version,after=sql_state(server.data)
        assert version==4
        for table,rows in before.items():
            if table=="assessment_schema_migrations":assert set(rows)<=set(after[table])
            else:assert all(row in after[table] for row in rows),table
        assert len(after["assessment_schema_migrations"])==2
        assert after["workspace_report_html"]

        server.start()
        client=Client(server.origin).login()
        assert client.request(report_route)[1]==report
        assert hashlib.sha256(client.request(download)[1].encode()).hexdigest()==frozen_digest
        server.stop()
        backup_path=tmp_path/"v4-backup"
        backup(DLL,server.data,fixture_input,backup_path)
        restored=tmp_path/"v4-restored"
        shutil.copytree(backup_path,restored)
        server.data=restored
        server.start()
        client=Client(server.origin).login()
        assert client.request(report_route)[1]==report
        assert hashlib.sha256(client.request(download)[1].encode()).hexdigest()==frozen_digest
        server.stop()
        with sqlite3.connect(restored/"enterprise-demo.sqlite3") as db:
            assert db.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
            assert not db.execute("PRAGMA foreign_key_check").fetchall()
            for table in ("workspace_report_html","assessment_documents","assessment_versions"):
                with pytest.raises(sqlite3.DatabaseError,match="immutable"):
                    db.execute('DELETE FROM "'+table+'"')
    finally:server.stop()


def test_mid_migration_failure_rolls_back_all_v4_schema_and_leaves_v3_readable(tmp_path,fixture_input):
    server,state,report=v3_state(tmp_path,fixture_input)
    with sqlite3.connect(server.data/"enterprise-demo.sqlite3") as db:
        # Test-only fault injection after schema creation, at immutable ledger
        # insertion. No production schema or real assessment is involved.
        db.execute("CREATE TRIGGER synthetic_deny_v4 BEFORE INSERT ON assessment_schema_migrations WHEN NEW.version=4 BEGIN SELECT RAISE(ABORT,'synthetic_migration_fault'); END")
    before=sql_state(server.data)
    refused_start(DLL,server.data,fixture_input,server.web)
    assert sql_state(server.data)==before
    with sqlite3.connect(server.data/"enterprise-demo.sqlite3") as db:
        assert not db.execute("SELECT name FROM sqlite_master WHERE name LIKE 'workspace_%'").fetchall()
        assert db.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
    try:
        server.start()
        client=Client(server.origin).login()
        assert client.request("/api/assessments/"+state["id"]+"/reports/"+report["metadata"]["id"])[1]==report
    finally:server.stop()


def test_unsupported_partial_schema_is_refused_without_repair_or_data_loss(tmp_path,fixture_input):
    server,_,_=v3_state(tmp_path,fixture_input)
    with sqlite3.connect(server.data/"enterprise-demo.sqlite3") as db:
        db.execute("CREATE TABLE workspace_artifacts(unrecognized_shape TEXT)")
    before=sql_state(server.data)
    refused_start(DLL,server.data,fixture_input,server.web)
    assert sql_state(server.data)==before


def test_migration_digest_or_immutable_trigger_drift_is_refused(tmp_path,fixture_input):
    server=Server(tmp_path,fixture_input)
    try:server.start()
    finally:server.stop()
    with sqlite3.connect(server.data/"enterprise-demo.sqlite3") as db:
        db.execute("DROP TRIGGER immutable_workspace_receipts_UPDATE")
    before=sql_state(server.data)
    refused_start(DLL,server.data,fixture_input,server.web)
    assert sql_state(server.data)==before
    # Use a different newly generated state so a checksum failure is exercised
    # separately from the missing-trigger check above.
    folder=tmp_path/"digest-case";folder.mkdir()
    other=Server(folder,fixture_input)
    try:other.start()
    finally:other.stop()
    with sqlite3.connect(other.data/"enterprise-demo.sqlite3") as db:
        db.execute("DROP TRIGGER immutable_assessment_schema_migrations_UPDATE")
        db.execute("UPDATE assessment_schema_migrations SET source_sha256=? WHERE version=4",("0"*64,))
        db.execute("CREATE TRIGGER immutable_assessment_schema_migrations_UPDATE BEFORE UPDATE ON assessment_schema_migrations BEGIN SELECT RAISE(ABORT,'immutable_record'); END")
    before=sql_state(other.data)
    refused_start(DLL,other.data,fixture_input,other.web)
    assert sql_state(other.data)==before


def test_rollback_requires_matching_old_application_and_pre_migration_state(tmp_path,fixture_input):
    server,state,report=v3_state(tmp_path,fixture_input)
    previous_backup=tmp_path/"pre-v4-backup"
    backup(PREVIOUS,server.data,fixture_input,previous_backup)
    old_snapshot=sql_state(previous_backup)
    server.dll=DLL
    try:server.start()
    finally:server.stop()
    migrated=sql_state(server.data);assert migrated[0]==4
    refused_start(PREVIOUS,server.data,fixture_input,server.web)
    assert sql_state(server.data)==migrated
    restored=tmp_path/"paired-v3-restore"
    shutil.copytree(previous_backup,restored)
    server.data=restored;server.dll=PREVIOUS
    try:
        server.start()
        client=Client(server.origin).login()
        assert client.request("/api/assessments/"+state["id"]+"/reports/"+report["metadata"]["id"])[1]==report
    finally:server.stop()
    assert sql_state(restored)==old_snapshot
