#!/usr/bin/env python3
"""Freeze verified public blank forms or create isolated synthetic response fixtures.

No network, app mutation, enterprise data or implicit downloads. Outputs are
create-only. The freeze command verifies original hashes and all cell values
before copying the later formatting-only editions. Generate uses only frozen
public blanks. This is test fixture production, not a response-submission tool.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED
from io import BytesIO

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/pqc-operational-return-v1"
CATALOG = ROOT / "apps/pqc-enterprise-demo/ReferenceData/operational-return-v1.catalog.json"
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
SHEETS = ["Start here", "Five questions", "Products & deployments", "Question help", "Software examples", "Version & return record"]
LABELS = {"Jira issue key, if assigned": "jiraIssueKey", "Recipient / intended team": "intendedTeam", "Respondent name / team": "respondent", "Owner / responsible function, if known": "owner", "Response date (YYYY-MM-DD)": "responseDate", "Known scope / service / environment": "scope"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def workbook(data):
    with ZipFile(BytesIO(data)) as z:
        assert z.testzip() is None
        parts = {name: z.read(name) for name in z.namelist()}
    assert not any(x in name.lower() for name in parts for x in ("vbaproject", "externallinks/", "embeddings/"))
    strings = []
    if "xl/sharedStrings.xml" in parts:
        strings = ["".join(t.text or "" for t in node.iter(f"{{{NS}}}t")) for node in ET.fromstring(parts["xl/sharedStrings.xml"])]
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(parts["xl/_rels/workbook.xml.rels"])}
    sheets, paths = {}, {}
    for sheet in ET.fromstring(parts["xl/workbook.xml"]).find(f"{{{NS}}}sheets"):
        target = rels[sheet.get(f"{{{REL}}}id")]
        path = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
        paths[sheet.get("name")] = path
        cells = {}
        for c in ET.fromstring(parts[path]).iter(f"{{{NS}}}c"):
            assert c.find(f"{{{NS}}}f") is None
            raw = c.findtext(f"{{{NS}}}v", "")
            text = strings[int(raw)] if c.get("t") == "s" else "".join(t.text or "" for t in c.iter(f"{{{NS}}}t")) if c.get("t") == "inlineStr" else raw
            if text:
                cells[c.get("r")] = text
        sheets[sheet.get("name")] = cells
    return sheets, paths, parts


def write_new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as f:
        f.write(data)


def freeze(args):
    if args.output.exists() or args.catalog.exists():
        raise ValueError("freeze_output_exists")
    originals = json.loads(args.source_manifest.read_text())
    layouts = {x["family"]: x for x in json.loads(args.layout_manifest.read_text())}
    assert len(originals) == len(layouts) == 27
    definitions, copies = [], []
    for form in sorted(originals, key=lambda x: x["familyId"]):
        original = Path(form["path"]).read_bytes()
        assert digest(original) == form["sha256"]
        layout = layouts[form["familyId"]]
        data = Path(layout["output"]).read_bytes()
        assert digest(data) == layout["sha256"]
        cells, _, _ = workbook(data)
        old, _, _ = workbook(original)
        assert cells == old and list(cells) == SHEETS
        respondent = {key: "D" + address[1:] for address, text in cells["Start here"].items() if (key := LABELS.get(text))}
        assert len(respondent) == 6
        questions = []
        for address, value in cells["Five questions"].items():
            if re.match(r"DQ-0[1-5]  ", value):
                n = int(address[1:])
                questions.append({"id": value[:5], "prompt": value[7:], "promptCell": address, "status": f"D{n+1}", "text": f"A{n+3}", "reference": f"D{n+4}", "attribution": f"D{n+5}", "followUp": f"D{n+6}"})
        assert len(questions) == 5
        questions.sort(key=lambda q: q["id"])
        coordinator = "A16"
        assert cells["Version & return record"]["A15"].startswith("Optional coordinator notes:")
        assert all(not cells["Start here"].get(a) for a in respondent.values())
        assert all(not cells["Five questions"].get(q[f]) for q in questions for f in ("status", "text", "reference", "attribution", "followUp"))
        assert not cells["Version & return record"].get(coordinator)
        assert not any(int(a[1:]) in range(4,11) for a in cells["Products & deployments"])
        assert all("SYNTHETIC PRACTICE ONLY" not in v for s in cells.values() for v in s.values())
        filename = form["familyId"] + ".xlsx"
        definitions.append({"familyId": form["familyId"], "domainId": form["domainId"], "questionnaireId": form["questionnaireId"], "workItemId": form["workItemId"], "templateVersion": form["sourceTemplateVersion"], "templateSha256": form["sourceTemplateSha256"], "sourceWorkbookSha256": form["sourceSha256"], "deliveryEdition": form["deliveryEdition"], "blankSha256": digest(data), "originalBlankSha256": digest(original), "filename": filename, "respondentCells": respondent, "questions": questions, "coordinatorCell": coordinator, "readonlyCells": cells, "productFooter": cells["Products & deployments"]["A11"]})
        copies.append((filename, data))
    result = {"schemaVersion": "pqc.operational-return-compatibility.v1", "classification": "public_blank_templates_no_responses", "sheets": SHEETS, "forms": definitions}
    encoded = (json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode()
    write_new(args.catalog, encoded)
    write_new(args.output / "catalog.json", encoded)
    for filename, data in copies:
        write_new(args.output / "blanks" / filename, data)
    print(json.dumps({"frozenForms": len(copies), "catalogSha256": digest(encoded), "externalActions": 0}))


def edit(data, changes):
    _, paths, parts = workbook(data)
    for sheet, edits in changes.items():
        root = ET.fromstring(parts[paths[sheet]])
        rows = root.find(f"{{{NS}}}sheetData")
        for address, value in edits.items():
            n = int(re.search(r"\d+", address)[0])
            row = next((r for r in rows if r.get("r") == str(n)), None)
            if row is None:
                row = ET.SubElement(rows, f"{{{NS}}}row", {"r": str(n)})
            cell = next((c for c in row if c.get("r") == address), None)
            if cell is None:
                cell = ET.SubElement(row, f"{{{NS}}}c", {"r": address})
            for child in list(cell): cell.remove(child)
            cell.set("t", "inlineStr")
            ET.SubElement(ET.SubElement(cell, f"{{{NS}}}is"), f"{{{NS}}}t").text = value
        parts[paths[sheet]] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as z:
        for name, content in parts.items(): z.writestr(name, content)
    return output.getvalue()


def generate(args):
    if args.output.exists(): raise ValueError("scenario_output_exists")
    catalog = json.loads((args.fixtures / "catalog.json").read_text())
    spec = next(f for f in catalog["forms"] if f["familyId"] == "traffic-termination")
    blank = (args.fixtures / "blanks" / spec["filename"]).read_bytes()
    assert digest(blank) == spec["blankSha256"]
    start = {spec["respondentCells"][key]: value for key, value in {"intendedTeam": "Synthetic network platform team", "respondent": "Synthetic source respondent / network team", "owner": "Not confirmed — synthetic referral", "responseDate": "2026-09-14", "scope": "Synthetic portal service; east, west and edge deployments; not enterprise enumeration"}.items()}
    answers = {}
    values = {"DQ-01": ("Answered", "F5 BIG-IP and NGINX; see deployment rows. Synthetic recognition examples, not enterprise selections or qualified integrations.", ""), "DQ-02": ("Referral", "Synthetic network team can identify the responsible function.", "Synthetic network platform team"), "DQ-03": ("Answered", "Existing configuration list available; runtime capture for edge is blocked pending handling route.", ""), "DQ-04": ("Unanswered", "", ""), "DQ-05": ("Unknown", "I do not know which policy applies; this is not evidence that no policy exists.", "Policy function to confirm existing requirements")}
    for q in spec["questions"]:
        status, text, follow = values[q["id"]]
        answers.update({q["status"]: status, q["text"]: text, q["followUp"]: follow})
    rows = [
        ["F5 BIG-IP", "gateway-east", "synthetic-test-east", "Synthetic portal", "Synthetic network", "portal-app-001", "synthetic:configuration-east", "Synthetic recognition example; no product qualification"],
        ["F5 BIG-IP", "gateway-west", "synthetic-test-west", "Synthetic portal", "Synthetic network", "portal-app-001", "synthetic:configuration-west", "Synthetic recognition example; no product qualification"],
        ["NGINX", "edge-third", "synthetic-test-edge", "Synthetic portal", "Unknown", "portal-app-001", "", "Collection blocked: handling route unresolved; synthetic example"],
        ["F5 BIG-IP", "gateway-east", "synthetic-test-east", "Synthetic portal", "Synthetic network", "portal-app-001", "synthetic:second-reference-east", "Suspected duplicate reference; coordinator must reconcile"],
    ]
    products = {f"{chr(65+c)}{r+4}": value for r,row in enumerate(rows) for c,value in enumerate(row)}
    first = edit(blank, {"Start here": start, "Five questions": answers, "Products & deployments": products})
    revised = edit(first, {"Five questions": {spec["questions"][0]["text"]: "Revised synthetic response: east configured hybrid; older observation lists classical exchange."}})
    files = {"traffic-initial.xlsx": first, "traffic-duplicate.xlsx": first, "traffic-revised.xlsx": revised}
    # Metadata-only reference fixtures. Exact normalization/admission remains a
    # separate C# contract; these records never claim vendor wire qualification.
    context = {"schemaVersion": "pqc.response-to-report.reference.v1", "synthetic": True, "familyId": "cmdb", "sourceInstanceId": "synthetic-cmdb", "collectedAt": "2026-09-14T12:00:00Z", "records": [{"nativeId": "portal-app-001", "name": "Synthetic portal application", "serviceId": "portal-service-001", "owner": "Synthetic application team", "environment": "synthetic-test", "sourceUpdatedAt": "2026-09-13T12:00:00Z"}]}
    certificate = {"schemaVersion": "pqc.response-to-report.reference.v1", "synthetic": True, "familyId": "certificate-lifecycle", "sourceInstanceId": "synthetic-pki", "collectedAt": "2026-09-14T12:00:00Z", "records": [{"nativeId": "portal-cert-001", "applicationId": "portal-app-001", "signatureAlgorithm": "ecdsa-with-SHA256", "publicKeyAlgorithm": "EC", "publicKeyBits": 256, "sourceUpdatedAt": "2026-09-13T12:00:00Z"}]}
    tls = {"schemaVersion": "pqc.response-to-report.reference.v1", "synthetic": True, "familyId": "traffic-termination", "sourceInstanceId": "synthetic-tls-config", "collectedAt": "2026-09-14T12:00:00Z", "records": [{"nativeId": "east-endpoint-001", "deployment": "gateway-east", "hostname": "portal-east.example", "applicationId": "portal-app-001", "certificateId": "portal-cert-001", "basis": "configured", "keyExchange": "X25519MLKEM768", "authentication": "ecdsa-with-SHA256", "sourceUpdatedAt": "2026-09-13T12:00:00Z"}]}
    for source, kind, label in ((context,"context","Synthetic CMDB export"),(certificate,"certificate","Synthetic certificate metadata"),(tls,"tls","Synthetic TLS configuration")):
        source.update(kind=kind,sourceLabel=label)
        for record in source["records"]:
            record.setdefault("basis","documentation")
    observed = json.loads(json.dumps(tls));observed["sourceInstanceId"]="synthetic-tls-observation";observed["sourceLabel"]="Synthetic TLS observation";observed["records"][0].update(basis="observed",keyExchange="X25519",sourceUpdatedAt="2026-09-12T12:00:00Z")
    blocked = {"schemaVersion":"pqc.response-to-report.blocked-source.v1","synthetic":True,"deployment":"edge-third","state":"blocked","reason":"handling_route_unresolved","causeBasis":"Synthetic exercise scenario; no enterprise restriction inferred","nextFunction":"Synthetic assessment coordination","observations":[],"standardsStatus":"proposed_not_adopted","executionAuthorized":False}
    for name, value in {"context.json": context, "certificate.json": certificate, "tls-configured.json": tls, "tls-observed.json": observed, "blocked-source.json": blocked}.items():
        files[name]=(json.dumps(value,indent=2)+"\n").encode()
    for name, data in files.items(): write_new(args.output/name,data)
    report={"schemaVersion":"pqc.response-to-report.synthetic-scenario.v1","synthetic":True,"expected":{"products":2,"distinctDeployments":3,"reportedRows":4,"suspectedDuplicateRows":1,"blockedSources":1,"enterpriseConnections":0,"adoptedStandards":0},"sourceTemplateSha256":spec["templateSha256"],"files":[{"name":name,"bytes":len(data),"sha256":digest(data)} for name,data in files.items()]}
    write_new(args.output/"scenario.json",(json.dumps(report,indent=2)+"\n").encode())
    print(json.dumps({"output":str(args.output),"files":len(files),"synthetic":True,"externalActions":0}))


if __name__ == "__main__":
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest="command",required=True)
    f=sub.add_parser("freeze");f.add_argument("--source-manifest",type=Path,required=True);f.add_argument("--layout-manifest",type=Path,required=True);f.add_argument("--output",type=Path,default=FIXTURES);f.add_argument("--catalog",type=Path,default=CATALOG)
    g=sub.add_parser("generate");g.add_argument("--fixtures",type=Path,default=FIXTURES);g.add_argument("--output",type=Path,required=True)
    a=p.parse_args();freeze(a) if a.command=="freeze" else generate(a)
