"""Closed-profile parser proofs: byte fixtures only, no Office or implicit build.

Set PQC_ENTERPRISE_DEMO_DLL to the explicitly built candidate. The parser CLI
receives only synthetic bytes through stdin. Run this module inside the same
bounded test cgroup as the HTTP tests. Actual Excel/LibreOffice save compatibility
and visual quality are separate qualification checks, not claimed here.
"""
from __future__ import annotations

from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
from urllib.request import Request
from uuid import uuid4
import warnings
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from tests.test_pqc_enterprise_demo_http import Client, Server, Workspace, fixture_input


DLL = os.environ.get("PQC_ENTERPRISE_DEMO_DLL")
pytestmark = pytest.mark.skipif(not DLL, reason="explicit built C# DLL required; no implicit build/download")
SHEET = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CONTENT = "http://schemas.openxmlformats.org/package/2006/content-types"


def xml(node):
    # OPC's .NET package reader requires unprefixed Types/Default/Override
    # elements. Use the Office-generated default-namespace serialization, not
    # ElementTree's otherwise valid ns0-prefixed alternative.
    ET.register_namespace("", node.tag.split("}")[0][1:])
    return ET.tostring(node, encoding="utf-8", xml_declaration=True)


def inline_cell(row, address, value):
    cell = ET.SubElement(row, f"{{{SHEET}}}c", r=address, t="inlineStr")
    text = ET.SubElement(ET.SubElement(cell, f"{{{SHEET}}}is"), f"{{{SHEET}}}t")
    text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    text.text = value
    return cell


def worksheet(rows):
    result = ET.Element(f"{{{SHEET}}}worksheet")
    data = ET.SubElement(result, f"{{{SHEET}}}sheetData")
    for number, values in rows:
        row = ET.SubElement(data, f"{{{SHEET}}}row", r=str(number))
        for column, value in enumerate(values):
            inline_cell(row, f"{chr(65 + column)}{number}", value)
    return result


def parts(answers=None):
    answers = answers if answers is not None else {"deployment-001/owner": "Synthetic platform function", "deployment-002/owner": ""}
    types = ET.Element(f"{{{CONTENT}}}Types")
    ET.SubElement(types, f"{{{CONTENT}}}Default", Extension="rels", ContentType="application/vnd.openxmlformats-package.relationships+xml")
    ET.SubElement(types, f"{{{CONTENT}}}Default", Extension="xml", ContentType="application/xml")
    ET.SubElement(types, f"{{{CONTENT}}}Override", PartName="/xl/workbook.xml", ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml")
    for index in (1, 2):
        ET.SubElement(types, f"{{{CONTENT}}}Override", PartName=f"/xl/worksheets/sheet{index}.xml", ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml")
    root_rels = ET.Element(f"{{{REL}}}Relationships")
    ET.SubElement(root_rels, f"{{{REL}}}Relationship", Id="rId1", Type=OFFICE_REL + "/officeDocument", Target="xl/workbook.xml")
    workbook = ET.Element(f"{{{SHEET}}}workbook")
    sheets = ET.SubElement(workbook, f"{{{SHEET}}}sheets")
    workbook_rels = ET.Element(f"{{{REL}}}Relationships")
    for index, name in enumerate(("Responses", "Return manifest"), 1):
        ET.SubElement(sheets, f"{{{SHEET}}}sheet", name=name, sheetId=str(index), attrib={f"{{{OFFICE_REL}}}id": f"rId{index}"})
        ET.SubElement(workbook_rels, f"{{{REL}}}Relationship", Id=f"rId{index}", Type=OFFICE_REL + "/worksheet", Target=f"worksheets/sheet{index}.xml")
    rows = [(6, ("Record ID", "Question or purpose", "Your answer (text)"))]
    rows += [(index, (key, "Identify the responsible function or explain what remains unknown.", value)) for index, (key, value) in enumerate(answers.items(), 7)]
    metadata = [(1, ("format", "pqc.intake.return.v1")), (2, ("export_id", "export-synthetic-001")),
        (3, ("assessment_id", "assessment-synthetic-001")), (4, ("request_id", "request-synthetic-001")),
        (5, ("notice", "Untrusted return locator; no approval authority."))]
    return {"[Content_Types].xml": xml(types), "_rels/.rels": xml(root_rels),
        "xl/workbook.xml": xml(workbook), "xl/_rels/workbook.xml.rels": xml(workbook_rels),
        "xl/worksheets/sheet1.xml": xml(worksheet(rows)), "xl/worksheets/sheet2.xml": xml(worksheet(metadata))}


def package(entries):
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return output.getvalue()


def add_core_property(entries, payload):
    types = ET.fromstring(entries["[Content_Types].xml"])
    ET.SubElement(types, f"{{{CONTENT}}}Override", PartName="/docProps/core.xml", ContentType="application/vnd.openxmlformats-package.core-properties+xml")
    entries["[Content_Types].xml"] = xml(types)
    entries["docProps/core.xml"] = payload


def parse(payload):
    return subprocess.run(["dotnet", str(Path(DLL).resolve()), "--intake-workbook-parser"],
        input=payload, capture_output=True, timeout=15,
        env={**os.environ, "DOTNET_CLI_TELEMETRY_OPTOUT": "1", "DOTNET_PROCESSOR_COUNT": "1"})


def rejects(payload, expected=None):
    result = parse(payload)
    assert result.returncode == 2
    assert not result.stdout  # no partially parsed response or payload on failure
    code = result.stderr.decode().strip()
    assert code.startswith("workbook_") or code in {"intake_parser_invalid", "intake_parser_output_limit"}
    assert "\n" not in code and len(code) < 100
    if expected is not None:
        assert code == expected


def test_two_deployments_partial_response_preserves_text_and_stable_ids():
    answers = {"deployment-001/owner": "0000123", "deployment-002/owner": "", "deployment-002/referral": "I do not know"}
    result = parse(package(parts(answers)))
    assert result.returncode == 0, result.stderr.decode()
    parsed = json.loads(result.stdout)
    assert parsed == {"exportId": "export-synthetic-001", "answers": answers}
    assert "baseline" not in parsed and "assessmentId" not in parsed


def test_real_export_uses_the_same_two_deployment_answers_and_valid_text_cells(tmp_path, fixture_input):
    """SDK writer -> authenticated export -> parser, using isolated synthetic state."""
    app = Server(tmp_path, fixture_input)
    try:
        app.start()
        lead = Client(app.origin).login()
        ws = Workspace(lead, mode="fresh")
        contributor = Client(app.origin).login("contributor")
        route = ws.route + "/intake"

        def command(actor, operation, target=None, fields=None):
            revision = actor.request(route)[1]["revision"]
            status, result, _ = actor.request(route + "/commands", method="POST",
                body={"operation": operation, "targetId": target, "fields": fields or {}, "expectedRevision": revision},
                headers={"Idempotency-Key": uuid4().hex})
            assert status == 200, result
            return result

        current = command(lead, "intake_create_request", fields={"title": "Synthetic deployment route", "familyId": "traffic-termination", "assignedTo": "synthetic-demo:contributor"})
        request_id = current["requests"][0]["id"]
        for label, environment in (("Synthetic portal A", "test"), ("Synthetic portal B", "staging")):
            current = command(contributor, "intake_add_system", request_id,
                {"label": label, "environment": environment, "product": "NGINX example", "systemRole": "subject", "aboutSystemId": ""})
        first, second = current["systems"]
        answers = {first["id"] + "/owner": "0000123", second["id"] + "/owner": "=literal-not-a-formula"}
        current = command(contributor, "intake_save_response", request_id, {"answers": answers, "assertedBy": "synthetic-demo:contributor"})
        status, exported, _ = contributor.request(route + "/exports/" + request_id, method="POST",
            body={"expectedRevision": current["revision"]}, headers={"Idempotency-Key": uuid4().hex})
        assert status == 200, exported
        download = contributor.opener.open(Request(app.origin + exported["downloadUrl"], headers={"Origin": app.origin}), timeout=10)
        payload = download.read()
        assert download.headers["Content-Type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with ZipFile(BytesIO(payload)) as archive:
            assert archive.testzip() is None
            sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
            assert not sheet.findall(f".//{{{SHEET}}}f")
            assert all(cell.attrib.get("t") == "inlineStr" for cell in sheet.findall(f".//{{{SHEET}}}c"))
            assert "SYNTHETIC ONLY" in "".join(sheet.itertext())
        result = parse(payload)
        assert result.returncode == 0, result.stderr.decode()
        returned = json.loads(result.stdout)
        assert returned["exportId"] == exported["exportId"]
        assert all(returned["answers"][key] == value for key, value in answers.items())
        assert len(returned["answers"]) == 12  # request + two deployments, four routing questions each
    finally:
        app.stop()


@pytest.mark.parametrize("text", ["=1+1", "+00123", "-00123", "@owner", "  unknown  ", "line one\nline two", "café / 日本語"])
def test_explicit_strings_are_not_evaluated_or_trimmed(text):
    answers = {"deployment-001/owner": text}
    result = parse(package(parts(answers)))
    assert result.returncode == 0, result.stderr.decode()
    assert json.loads(result.stdout)["answers"] == answers


def test_shared_string_storage_is_supported_without_numeric_coercion():
    entries = parts({"deployment-001/owner": "0000123"})
    sheet = ET.fromstring(entries["xl/worksheets/sheet1.xml"])
    cell = sheet.find(f".//{{{SHEET}}}c[@r='C7']")
    cell.clear(); cell.set("r", "C7"); cell.set("t", "s")
    ET.SubElement(cell, f"{{{SHEET}}}v").text = "0"
    entries["xl/worksheets/sheet1.xml"] = xml(sheet)
    strings = ET.Element(f"{{{SHEET}}}sst", count="1", uniqueCount="1")
    ET.SubElement(ET.SubElement(strings, f"{{{SHEET}}}si"), f"{{{SHEET}}}t").text = "0000123"
    entries["xl/sharedStrings.xml"] = xml(strings)
    rels = ET.fromstring(entries["xl/_rels/workbook.xml.rels"])
    ET.SubElement(rels, f"{{{REL}}}Relationship", Id="rId3", Type=OFFICE_REL + "/sharedStrings", Target="sharedStrings.xml")
    entries["xl/_rels/workbook.xml.rels"] = xml(rels)
    types = ET.fromstring(entries["[Content_Types].xml"])
    ET.SubElement(types, f"{{{CONTENT}}}Override", PartName="/xl/sharedStrings.xml", ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml")
    entries["[Content_Types].xml"] = xml(types)
    result = parse(package(entries))
    assert result.returncode == 0, result.stderr.decode()
    assert json.loads(result.stdout)["answers"]["deployment-001/owner"] == "0000123"


def unused_defaults(entries):
    types = ET.fromstring(entries["[Content_Types].xml"])
    for extension, mime in (("png", "image/png"), ("jpeg", "image/jpeg"), ("fntdata", "application/x-fontdata")):
        ET.SubElement(types, f"{{{CONTENT}}}Default", Extension=extension, ContentType=mime)
    entries["[Content_Types].xml"] = xml(types)
    return entries


def test_unused_office_image_and_font_mime_defaults_are_harmless_metadata():
    result = parse(package(unused_defaults(parts())))
    assert result.returncode == 0, result.stderr.decode()
    assert json.loads(result.stdout)["answers"]["deployment-001/owner"] == "Synthetic platform function"


@pytest.mark.parametrize("name", ["xl/media/image1.png", "xl/media/image1.jpeg", "xl/fonts/font1.fntdata"])
def test_unused_mime_declaration_never_permits_actual_image_or_font_parts(name):
    entries = unused_defaults(parts())
    entries[name] = b"synthetic unsupported payload"
    rejects(package(entries), "workbook_unsupported_package")


def test_actual_part_effective_mime_must_match_even_with_harmless_defaults():
    entries = unused_defaults(parts())
    types = ET.fromstring(entries["[Content_Types].xml"])
    types.find(f"{{{CONTENT}}}Override[@PartName='/xl/worksheets/sheet1.xml']").set("ContentType", "image/png")
    entries["[Content_Types].xml"] = xml(types)
    rejects(package(entries), "workbook_unsupported_package")


def test_duplicate_unused_default_is_still_invalid():
    entries = unused_defaults(parts())
    types = ET.fromstring(entries["[Content_Types].xml"])
    ET.SubElement(types, f"{{{CONTENT}}}Default", Extension="PNG", ContentType="image/png")
    entries["[Content_Types].xml"] = xml(types)
    rejects(package(entries), "workbook_invalid")


@pytest.mark.parametrize("extension,mime", [("../png", "image/png"), ("png", "not a MIME type"), ("png", "https://synthetic.invalid/image")])
def test_malformed_unused_default_is_still_invalid(extension, mime):
    entries = parts()
    types = ET.fromstring(entries["[Content_Types].xml"])
    ET.SubElement(types, f"{{{CONTENT}}}Default", Extension=extension, ContentType=mime)
    entries["[Content_Types].xml"] = xml(types)
    rejects(package(entries), "workbook_invalid")


def test_formula_with_cached_answer_is_rejected_without_echo():
    entries = parts()
    sheet = ET.fromstring(entries["xl/worksheets/sheet1.xml"])
    cell = sheet.find(f".//{{{SHEET}}}c[@r='C7']")
    cell.clear(); cell.set("r", "C7")
    ET.SubElement(cell, f"{{{SHEET}}}f").text = 'WEBSERVICE("https://synthetic.invalid/do-not-fetch")'
    ET.SubElement(cell, f"{{{SHEET}}}v").text = "12345"
    entries["xl/worksheets/sheet1.xml"] = xml(sheet)
    rejects(package(entries), "workbook_formula_not_allowed")


@pytest.mark.parametrize("name", ["xl/vbaProject.bin", "xl/embeddings/object.bin", "xl/connections.xml", "xl/externalLinks/externalLink1.xml", "../outside.xml", "xl/../outside.xml", "xl\\outside.xml", "/xl/workbook.xml"])
def test_unqualified_parts_and_unsafe_paths_are_rejected(name):
    entries = parts(); entries[name] = b"<synthetic/>"
    rejects(package(entries), "workbook_unsupported_package")


def test_duplicate_zip_names_are_rejected_before_package_interpretation():
    output = BytesIO(package(parts()))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with ZipFile(output, "a", compression=ZIP_DEFLATED) as archive:
            archive.writestr("xl/workbook.xml", b"<synthetic/>")
    rejects(output.getvalue(), "workbook_unsupported_package")


def test_external_relationship_is_rejected_without_fetching():
    entries = parts()
    rels = ET.fromstring(entries["xl/_rels/workbook.xml.rels"])
    first = next(iter(rels)); first.set("TargetMode", "External"); first.set("Target", "https://synthetic.invalid/sheet.xml")
    entries["xl/_rels/workbook.xml.rels"] = xml(rels)
    rejects(package(entries), "workbook_unsupported_package")


def test_unknown_legacy_format_is_explicitly_unsupported():
    entries = parts()
    sheet = ET.fromstring(entries["xl/worksheets/sheet2.xml"])
    sheet.find(f".//{{{SHEET}}}c[@r='B1']//{{{SHEET}}}t").text = "legacy-questionnaire.v2"
    entries["xl/worksheets/sheet2.xml"] = xml(sheet)
    rejects(package(entries), "workbook_unsupported_profile")


def test_duplicate_stable_row_identifiers_are_rejected():
    entries = parts()
    sheet = ET.fromstring(entries["xl/worksheets/sheet1.xml"])
    sheet.find(f".//{{{SHEET}}}c[@r='A8']//{{{SHEET}}}t").text = "deployment-001/owner"
    entries["xl/worksheets/sheet1.xml"] = xml(sheet)
    rejects(package(entries), "workbook_invalid_rows")


def test_numeric_answer_is_rejected_instead_of_silently_losing_identifier_zeros():
    entries = parts()
    sheet = ET.fromstring(entries["xl/worksheets/sheet1.xml"])
    cell = sheet.find(f".//{{{SHEET}}}c[@r='C7']")
    cell.clear(); cell.set("r", "C7")
    ET.SubElement(cell, f"{{{SHEET}}}v").text = "123"
    entries["xl/worksheets/sheet1.xml"] = xml(sheet)
    rejects(package(entries), "workbook_text_cells_required")


def test_xml_entity_declaration_is_rejected():
    entries = parts()
    add_core_property(entries, b'<!DOCTYPE root [<!ENTITY xx SYSTEM "file:///synthetic-do-not-read">]><root>&xx;</root>')
    rejects(package(entries), "workbook_invalid")


def test_xml_depth_is_bounded_before_sdk_load():
    entries = parts()
    add_core_property(entries, b"<root>" * 34 + b"</root>" * 34)
    rejects(package(entries), "workbook_limits_exceeded")


def test_compressed_bomb_and_oversized_input_are_rejected():
    entries = parts()
    add_core_property(entries, b"<root>" + b"x" * (8 * 1024 * 1024) + b"</root>")
    rejects(package(entries), "workbook_limits_exceeded")
    rejects(b"PK\x03\x04" + b"x" * 1_048_576)


@pytest.mark.parametrize("payload", [b"not an xlsx document", b"\xd0\xcf\x11\xe0encrypted-office-document", b"PK\x03\x04truncated"])
def test_nonzip_encrypted_and_truncated_packages_fail_safely(payload):
    rejects(payload)


def test_answer_row_count_is_bounded():
    entries = parts({f"deployment-{number:03}/owner": "unknown" for number in range(501)})
    rejects(package(entries), "workbook_invalid_rows")
