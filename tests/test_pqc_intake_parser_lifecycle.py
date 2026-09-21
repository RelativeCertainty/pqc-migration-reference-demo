"""Opt-in lifecycle proofs for the real isolated HTTP workbook parser lane.

No implicit build/download, broad service stop, production state, or real data.
Each test uses a copied candidate bundle: a parser belongs to the test only when
its systemd ExecStart and process command line contain that unique DLL path.
The cancellation proof briefly pauses that exact disposable process through a
pidfd, disconnects the HTTP request, and observes application-owned cleanup.
"""
from __future__ import annotations

from io import BytesIO
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import struct
import subprocess
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from tests.test_pqc_enterprise_demo_http import Server, fixture_input
from tests.test_pqc_intake_http import Intake, request_record


DLL = os.environ.get("PQC_ENTERPRISE_DEMO_DLL")
RUN = os.environ.get("PQC_INTAKE_LIFECYCLE_PROOF") == "1"
pytestmark = pytest.mark.skipif(not DLL or not RUN,
    reason="explicit built DLL and PQC_INTAKE_LIFECYCLE_PROOF=1 required; isolated parser fault injection")
UNIT_NAME = re.compile(r"^pqc-intake-parser-[a-f0-9]{32}\.service$")
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def manager(*arguments):
    result = subprocess.run(["/usr/bin/systemctl", "--user", *arguments],
        capture_output=True, text=True, timeout=4)
    assert result.returncode == 0, "read-only test-unit inspection failed"
    return result.stdout


def unit_state(unit):
    assert UNIT_NAME.fullmatch(unit), "not a parser-generated unit identifier"
    text = manager("show", "--property=ExecStart,ActiveState,SubState,MainPID,MemoryMax,MemorySwapMax,CPUQuotaPerSecUSec,RuntimeMaxUSec,PrivateNetwork,NoNewPrivileges", unit)
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


def own_units(dll):
    """List read-only; a name prefix by itself never establishes ownership."""
    text = manager("list-units", "--all", "--type=service", "--plain", "--no-legend", "pqc-intake-parser-*.service")
    result = {}
    for line in text.splitlines():
        unit = line.split()[0] if line.split() else ""
        if not UNIT_NAME.fullmatch(unit):
            continue
        state = unit_state(unit)
        if str(dll) in state.get("ExecStart", ""):
            result[unit] = state
    return result


@pytest.fixture
def lifecycle_app(tmp_path, fixture_input):
    assert hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"), "Linux pidfd support required for exact-process fault injection"
    original = Path(DLL).resolve()
    bundle = tmp_path / "unique-candidate-bundle"
    bundle.mkdir(mode=0o700)
    selected = [path for path in original.parent.iterdir() if path.is_file() and path.suffix in {".dll", ".json", ".so"}]
    runtimes = original.parent / "runtimes"
    if runtimes.is_dir():
        selected += [path for path in runtimes.rglob("*") if path.is_file()]
    assert sum(path.stat().st_size for path in selected) <= 96 * 1024 * 1024, "candidate-copy budget exceeded"
    for source in selected:
        assert not source.is_symlink(), "candidate-copy symlink refused"
        target = bundle / source.relative_to(original.parent)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    unique_dll = bundle / original.name
    assert unique_dll.is_file()
    app = Server(tmp_path, fixture_input, dll=unique_dll)
    try:
        yield app.start(), unique_dll
    finally:
        # Application cleanup owns parser-service termination. This fixture
        # stops only its own HTTP process; it never issues a service stop.
        app.stop()


def make_request(app):
    intake = Intake(app)
    request_id = intake.create_request("Synthetic parser lifecycle proof")
    system_id = intake.system(request_id, "Synthetic isolated deployment", product="NGINX example")
    intake.save(request_id, {system_id + "/owner": "Synthetic platform function"})
    _, workbook = intake.export(request_id)
    return intake, request_id, workbook


def wait_drained(dll, deadline_seconds=12):
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        active = {name: state for name, state in own_units(dll).items()
            if state.get("ActiveState") not in {"inactive", "failed"}}
        if not active:
            return
        time.sleep(0.04)
    pytest.fail("an exact test-owned parser unit remained active after the cleanup bound")


def assert_usable_preview(intake, request_id, workbook):
    status, result, _ = intake.import_preview(request_id, workbook)
    assert status == 200, (status, result)
    assert result["previewId"] and result["changes"]
    assert all(change["state"] == "unchanged" for change in result["changes"])


def test_invalid_workbook_then_valid_import_recovers_the_parser_lane(lifecycle_app):
    app, dll = lifecycle_app
    intake, request_id, workbook = make_request(app)
    before = request_record(intake.view(), request_id)["answers"]
    revision = intake.view()["revision"]
    status, result, _ = intake.import_preview(request_id, b"not-an-xlsx-synthetic-input")
    assert status == 400 and result["error"]["code"] == "workbook_rejected_or_parser_unavailable"
    wait_drained(dll)
    assert intake.view()["revision"] == revision
    assert request_record(intake.view(), request_id)["answers"] == before
    assert_usable_preview(intake, request_id, workbook)
    wait_drained(dll)


def substantial_workbook(workbook):
    """Bounded parser exercise; foreign row IDs cannot pass controller admission."""
    output = BytesIO()
    with ZipFile(BytesIO(workbook)) as source, ZipFile(output, "w", compression=ZIP_DEFLATED) as target:
        for name in source.namelist():
            value = source.read(name)
            if name == "xl/worksheets/sheet1.xml":
                sheet = ET.fromstring(value)
                data = sheet.find(f"{{{NS}}}sheetData")
                for row in list(data):
                    if int(row.attrib["r"]) > 6:
                        data.remove(row)
                for index in range(500):
                    number = index + 7
                    row = ET.SubElement(data, f"{{{NS}}}row", r=str(number))
                    for column, text in zip("ABC", (f"synthetic-lifecycle-{index:03}/owner", "Synthetic bounded parser question. " * 25, "Synthetic response only. " * 50)):
                        cell = ET.SubElement(row, f"{{{NS}}}c", r=f"{column}{number}", t="inlineStr")
                        ET.SubElement(ET.SubElement(cell, f"{{{NS}}}is"), f"{{{NS}}}t").text = text
                ET.register_namespace("", NS)
                value = ET.tostring(sheet, encoding="utf-8", xml_declaration=True)
                assert len(value) < 2 * 1024 * 1024
            target.writestr(name, value)
    value = output.getvalue()
    assert len(value) < 1_048_576
    return value


def test_disconnected_request_cleans_exact_parser_and_allows_next_import(lifecycle_app):
    app, dll = lifecycle_app
    intake, request_id, workbook = make_request(app)
    actor = intake.actor("contributor")
    before = request_record(intake.view(), request_id)["answers"]
    payload = substantial_workbook(workbook)
    path = intake.route + "/imports/" + request_id + "?" + urlencode({"expectedRevision": intake.view()["revision"]})
    prepared = Request(app.origin + path)
    for handler in actor.opener.handlers:
        if hasattr(handler, "cookiejar"):
            handler.cookiejar.add_cookie_header(prepared)
    cookie = prepared.get_header("Cookie")
    assert cookie, "synthetic authenticated cookie required"
    captured = {}
    failure = []
    complete = threading.Event()

    def pause_own_parser():
        deadline = time.monotonic() + 10
        try:
            while time.monotonic() < deadline and not complete.is_set():
                for unit, state in own_units(dll).items():
                    pid = int(state.get("MainPID", "0"))
                    if pid <= 0 or state.get("ActiveState") != "active":
                        continue
                    descriptor = None
                    try:
                        descriptor = os.pidfd_open(pid)
                        command = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
                        if str(dll).encode() not in command or b"--intake-workbook-parser" not in command:
                            os.close(descriptor)
                            continue
                        signal.pidfd_send_signal(descriptor, signal.SIGSTOP)
                    except (ProcessLookupError, FileNotFoundError):
                        if descriptor is not None:
                            os.close(descriptor)
                        continue
                    captured.update(unit=unit, state=state, descriptor=descriptor)
                    complete.set()
                    return
                time.sleep(0.01)
        except Exception as error:
            failure.append(type(error).__name__)  # no command line or response payload
            complete.set()

    observer = threading.Thread(target=pause_own_parser, daemon=True)
    connection = socket.create_connection(("127.0.0.1", app.port), timeout=5)
    try:
        observer.start()
        header = (f"POST {path} HTTP/1.1\r\nHost: 127.0.0.1:{app.port}\r\nOrigin: {app.origin}\r\n"
            f"Cookie: {cookie}\r\nX-PQC-CSRF: {actor.csrf}\r\nIdempotency-Key: synthetic-cancellation-proof\r\n"
            "Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n"
            f"Content-Length: {len(payload)}\r\nConnection: keep-alive\r\n\r\n")
        connection.sendall(header.encode("ascii") + payload)
        assert complete.wait(11), "could not observe the exact disposable parser process; cancellation was not proved"
        assert not failure and captured, "could not safely bind the parser fault to this test"
        state = captured["state"]
        assert state["MemoryMax"] == "536870912" and state["MemorySwapMax"] == "0"
        assert state["CPUQuotaPerSecUSec"] == "1s" and state["RuntimeMaxUSec"] == "30s"
        assert state["PrivateNetwork"] == "yes" and state["NoNewPrivileges"] == "yes"
        # A parser that is still active must not admit or queue a second
        # parser; only the subsequent verified-cleanup handoff may wait.
        busy_status, busy_result, _ = intake.import_preview(request_id, workbook)
        assert busy_status == 429 and busy_result["error"]["code"] == "intake_parser_busy"
        active = {unit: status for unit, status in own_units(dll).items()
            if status.get("ActiveState") not in {"inactive", "failed"}}
        assert list(active) == [captured["unit"]], "active contention created another parser unit"
        # Force a disconnect while the exact child is paused. The application,
        # not this test, must terminate the manager-owned child before reuse.
        connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        connection.close()
        wait_drained(dll)
        assert request_record(intake.view(), request_id)["answers"] == before
        assert_usable_preview(intake, request_id, workbook)
        wait_drained(dll)
    finally:
        complete.set()
        connection.close()
        observer.join(timeout=5)
        if captured.get("descriptor") is not None:
            # Never leave a fault-injected process paused if the assertion
            # fails. A pidfd cannot accidentally signal a reused process ID.
            try:
                signal.pidfd_send_signal(captured["descriptor"], signal.SIGCONT)
            except ProcessLookupError:
                pass
            finally:
                os.close(captured["descriptor"])


@pytest.mark.skipif(os.environ.get("PQC_INTAKE_LIBREOFFICE_PROOF") != "1",
    reason="explicit independent LibreOffice open/save qualification requested")
def test_libreoffice_open_save_preserves_current_questionnaire_profile(lifecycle_app, tmp_path):
    """Independent Linux application save; this is not Microsoft Excel proof."""
    app, dll = lifecycle_app
    intake, request_id, _ = make_request(app)
    system = intake.view()["systems"][0]["id"]
    expected = {system + "/owner": "0000123", system + "/referral": "=literal-not-a-formula"}
    intake.save(request_id, expected)
    _, workbook = intake.export(request_id)
    before = subprocess.run(["dotnet", str(dll), "--intake-workbook-parser"], input=workbook,
        capture_output=True, timeout=15)
    assert before.returncode == 0
    source = tmp_path / "synthetic-questionnaire.xlsx"
    source.write_bytes(workbook)
    output = tmp_path / "office-roundtrip"
    output.mkdir()
    profile = tmp_path / "isolated-libreoffice-profile"
    office = shutil.which("libreoffice")
    assert office, "LibreOffice must already be installed; no implicit acquisition"
    converted = subprocess.run([office, "-env:UserInstallation=" + profile.as_uri(), "--headless",
        "--convert-to", "xlsx", "--outdir", str(output), str(source)],
        capture_output=True, timeout=45)
    assert converted.returncode == 0, "isolated LibreOffice conversion failed"
    returned_file = output / source.name
    assert returned_file.is_file(), "LibreOffice did not produce the saved workbook"
    with ZipFile(returned_file) as archive:
        assert archive.testzip() is None
        part_names = sorted(archive.namelist())
    returned = subprocess.run(["dotnet", str(dll), "--intake-workbook-parser"], input=returned_file.read_bytes(),
        capture_output=True, timeout=15)
    assert returned.returncode == 0, (returned.stderr.decode(), part_names)
    assert json.loads(returned.stdout) == json.loads(before.stdout)
    assert_usable_preview(intake, request_id, returned_file.read_bytes())
    wait_drained(dll)
