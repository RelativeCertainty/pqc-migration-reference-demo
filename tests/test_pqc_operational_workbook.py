"""Frozen operational Excel compatibility; no live app, providers or real returns.

The parser runs as an explicit prebuilt C# child. Tests never build/install and
never read downloaded/mailed responses. Frozen blank forms are public templates.
"""
from __future__ import annotations

from datetime import date
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import subprocess
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

import pytest

from scripts.build_pqc_response_to_report_fixtures import edit, workbook

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/"tests/fixtures/pqc-operational-return-v1"
CATALOG=json.loads((FIXTURES/"catalog.json").read_text())
FORM=next(f for f in CATALOG["forms"] if f["familyId"]=="traffic-termination")
NS="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DLL=os.environ.get("PQC_ENTERPRISE_DEMO_DLL")
requires_parser=pytest.mark.skipif(not DLL,reason="explicit prebuilt candidate DLL required; no implicit build")


def blank(form=FORM):
    return (FIXTURES/"blanks"/form["filename"]).read_bytes()


def package(parts):
    output=BytesIO()
    with ZipFile(output,"w",ZIP_DEFLATED) as archive:
        for name,value in parts.items():archive.writestr(name,value)
    return output.getvalue()


def transform(data,sheet,change):
    _,paths,parts=workbook(data)
    root=ET.fromstring(parts[paths[sheet]])
    change(root)
    parts[paths[sheet]]=ET.tostring(root,encoding="utf-8",xml_declaration=True)
    return package(parts)


def parse(data,mode="--operational-workbook-parser"):
    process=subprocess.run(["dotnet",DLL,mode],input=data,capture_output=True,timeout=25,
        env={**os.environ,"DOTNET_PROCESSOR_COUNT":"1","DOTNET_gcServer":"0"})
    return process.returncode,json.loads(process.stdout) if process.returncode==0 else process.stderr.decode()


def test_frozen_27_forms_and_both_definition_copies_are_exact_public_blanks():
    assert len(CATALOG["forms"])==27
    assert len({f["familyId"] for f in CATALOG["forms"]})==27
    assert len({f["domainId"] for f in CATALOG["forms"]})==10
    assert (FIXTURES/"catalog.json").read_bytes()==(ROOT/"apps/pqc-enterprise-demo/ReferenceData/operational-return-v1.catalog.json").read_bytes()
    for form in CATALOG["forms"]:
        data=blank(form)
        assert hashlib.sha256(data).hexdigest()==form["blankSha256"]
        sheets,_,_=workbook(data)
        assert list(sheets)==CATALOG["sheets"]
        assert form["templateVersion"]=="pqc.discovery.v2"
        assert form["deliveryEdition"]=="pqc.discovery.email-return.v1"
        assert all(not sheets["Start here"].get(address) for address in form["respondentCells"].values())
        assert all(not sheets["Five questions"].get(q[field]) for q in form["questions"] for field in ("status","text","reference","attribution","followUp"))
        assert not sheets["Version & return record"].get(form["coordinatorCell"])
        assert not any(int(address[1:]) in range(4,11) for address in sheets["Products & deployments"])


@requires_parser
@pytest.mark.parametrize("form",CATALOG["forms"],ids=lambda f:f["familyId"])
def test_all_27_distributed_six_sheet_forms_parse_without_export_binding(form):
    code,result=parse(blank(form))
    assert code==0,result
    assert result["profile"]=="pqc.discovery.email-return.v1"
    assert result["familyId"]==form["familyId"]
    assert result["templateSha256"]==form["templateSha256"]
    assert result["questionnaireId"]==form["questionnaireId"]
    assert result["products"]==[]
    assert len(result["answers"])==5
    assert all(a["status"]=="unanswered" for a in result["answers"])
    assert [a["prompt"] for a in result["answers"]]==[q["prompt"] for q in form["questions"]]
    assert not {"assessmentId","requestId","exportId","originalBase64"}.intersection(result)


@requires_parser
def test_complete_raw_attribution_and_all_eight_product_columns_are_preserved():
    data=(FIXTURES/"synthetic-scenario/traffic-initial.xlsx").read_bytes()
    code,result=parse(data);assert code==0,result
    assert len(result["products"])==4
    assert len({p["product"] for p in result["products"]})==2
    assert len({p["deployment"] for p in result["products"]})==3
    assert result["answers"][1]["status"]=="referral"
    assert result["answers"][3]["status"]=="unanswered"
    assert result["answers"][4]["status"]=="unknown"
    assert "not evidence" in result["answers"][4]["text"]
    assert "Suspected duplicate" in result["products"][3]["notes"]
    assert result["products"][0]["applicationService"]=="Synthetic portal"
    assert result["products"][0]["dependencies"]=="portal-app-001"
    assert "Products & deployments!A4:H4"==result["products"][0]["provenance"]
    q=FORM["questions"][0]
    data=edit(data,{"Five questions":{q["attribution"]:"Asserted by Synthetic specialist; recorded by Synthetic coordinator",q["followUp"]:"Refer to Synthetic network team"},"Version & return record":{FORM["coordinatorCell"]:"Unverified coordination note — no authority granted"}})
    code,result=parse(data);assert code==0,result
    assert result["answers"][0]["attribution"]=="Asserted by Synthetic specialist; recorded by Synthetic coordinator"
    assert result["answers"][0]["followUp"]=="Refer to Synthetic network team"
    assert result["coordinatorNote"]=="Unverified coordination note — no authority granted"


@requires_parser
@pytest.mark.parametrize("status,expected",[("Unanswered","unanswered"),("Answered","answered"),("Unknown","unknown"),("Blocked","blocked"),("Not applicable","not_applicable"),("Disputed","disputed"),("Referral","referral"),("Not my team","not_my_team")])
def test_all_operational_statuses_remain_distinct(status,expected):
    code,result=parse(edit(blank(),{"Five questions":{FORM["questions"][0]["status"]:status}}))
    assert code==0,result
    assert result["answers"][0]["status"]==expected


@requires_parser
@pytest.mark.parametrize("sheet,address,value",[("Version & return record","D3","PQC-DQ-made-up"),("Version & return record","D6","pqc.discovery.v999"),("Version & return record","D7","0"*64),("Version & return record","D9","unrecognized"),("Five questions","A4","DQ-01  Changed question"),("Question help","A3","Changed explanation")])
def test_changed_definition_or_binding_is_rejected(sheet,address,value):
    assert parse(edit(blank(),{sheet:{address:value}}))[0]==2


@requires_parser
def test_renamed_file_and_formatting_do_not_define_identity():
    # The child receives bytes, never a filename. Styles and row heights are
    # cosmetic and must not be used as answer identity or authentication.
    data=transform(blank(),"Five questions",lambda root:root.find(f".//{{{NS}}}row").set("ht","67"))
    assert parse(data)[0]==0


@requires_parser
def test_numeric_and_iso_date_cells_and_shared_strings_are_supported():
    address=FORM["respondentCells"]["responseDate"]
    data=edit(blank(),{"Start here":{address:"2026-09-14"}})
    def change(kind,value):
        def apply(root):
            cell=next(c for c in root.iter(f"{{{NS}}}c") if c.get("r")==address)
            for child in list(cell):cell.remove(child)
            cell.set("t",kind);ET.SubElement(cell,f"{{{NS}}}v").text=value
        return apply
    for kind,value in [("n",str((date(2026,9,14)-date(1899,12,30)).days)),("d","2026-09-14T00:00:00"),("d","2026-09-14T00:00:00.000"),("d","2026-09-14T00:00:00Z")]:
        code,result=parse(transform(data,"Start here",change(kind,value)))
        assert code==0,result
        assert result["responseDate"]=="2026-09-14"
    assert parse(transform(data,"Start here",change("n","60")))[0]==2
    for value in ("not a date","2026-02-30T00:00:00","09/14/2026", "=1+1"):
        assert parse(transform(data,"Start here",change("d",value)))[0]==2
    # The frozen LibreOffice corrected editions actually use shared strings.
    with ZipFile(BytesIO(blank())) as z:assert "xl/sharedStrings.xml" in z.namelist()


@requires_parser
@pytest.mark.parametrize("count,expected",[(200,0),(201,2)])
def test_added_product_rows_are_bounded_without_silent_truncation(count,expected):
    updates={"A11":""}
    for n in range(4,4+count):updates.update({f"A{n}":"Synthetic product",f"B{n}":f"Synthetic deployment {n}"})
    updates[f"A{4+count}"]=FORM["productFooter"]
    code,result=parse(edit(blank(),{"Products & deployments":updates}))
    assert code==expected,result
    if code==0:assert len(result["products"])==count


@requires_parser
def test_formulas_unsafe_dropdowns_unknown_cells_and_external_relationships_fail_closed():
    q=FORM["questions"][0]
    def formula(root):
        cell=next(c for c in root.iter(f"{{{NS}}}c") if c.get("r")==q["text"])
        ET.SubElement(cell,f"{{{NS}}}f").text="1+1"
    assert parse(transform(blank(),"Five questions",formula))[0]==2
    assert parse(transform(blank(),"Five questions",lambda root:setattr(next(root.iter(f"{{{NS}}}formula1")),"text","INDIRECT(\"A1\")")))[0]==2
    _,_,named_parts=workbook(blank())
    named_root=ET.fromstring(named_parts["xl/workbook.xml"])
    named=next(named_root.iter(f"{{{NS}}}definedName"))
    named.text="WEBSERVICE(\"https://example.invalid\")"
    named_parts["xl/workbook.xml"]=ET.tostring(named_root)
    assert parse(package(named_parts))[0]==2
    assert parse(edit(blank(),{"Question help":{"H100":"Undeclared answer"}}))[0]==2
    assert parse(edit(blank(),{"Five questions":{q["status"]:"Approved"}}))[0]==2
    _,_,parts=workbook(blank())
    root=ET.fromstring(parts["xl/_rels/workbook.xml.rels"])
    root[0].set("TargetMode","External");root[0].set("Target","https://example.invalid/source")
    parts["xl/_rels/workbook.xml.rels"]=ET.tostring(root)
    assert parse(package(parts))[0]==2
    parts["xl/vbaProject.bin"]=b"SYNTHETIC REJECTED MACRO"
    assert parse(package(parts))[0]==2
    assert parse(b"x"*1_048_577)[0]==2


@requires_parser
def test_duplicate_revised_response_and_legacy_modes_are_distinct():
    first=(FIXTURES/"synthetic-scenario/traffic-initial.xlsx").read_bytes()
    duplicate=(FIXTURES/"synthetic-scenario/traffic-duplicate.xlsx").read_bytes()
    revised=(FIXTURES/"synthetic-scenario/traffic-revised.xlsx").read_bytes()
    assert first==duplicate and revised!=first
    assert parse(first)==parse(duplicate)
    assert parse(revised)[1]["answers"][0]["text"]!=parse(first)[1]["answers"][0]["text"]
    for mode in ("--discovery-workbook-parser","--questionnaire-workbook-parser","--intake-workbook-parser"):
        assert parse(first,mode)[0]==2


def test_scenario_generator_is_create_only_and_bounds_authority(tmp_path):
    destination=tmp_path/"new-scenario"
    command=["python3",str(ROOT/"scripts/build_pqc_response_to_report_fixtures.py"),"generate","--output",str(destination)]
    result=subprocess.run(command,capture_output=True,timeout=15)
    assert result.returncode==0,result.stderr
    scenario=json.loads((destination/"scenario.json").read_text())
    assert scenario["expected"]=={"products":2,"distinctDeployments":3,"reportedRows":4,"suspectedDuplicateRows":1,"blockedSources":1,"enterpriseConnections":0,"adoptedStandards":0}
    for entry in scenario["files"]:
        assert hashlib.sha256((destination/entry["name"]).read_bytes()).hexdigest()==entry["sha256"]
    blocked=json.loads((destination/"blocked-source.json").read_text())
    assert blocked["observations"]==[] and blocked["executionAuthorized"] is False
    assert subprocess.run(command,capture_output=True,timeout=15).returncode!=0
