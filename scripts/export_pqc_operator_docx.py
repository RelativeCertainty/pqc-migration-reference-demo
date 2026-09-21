#!/usr/bin/env python3
"""Export the source-checked guide using the user-approved local office tools.

Does not modify guide text, operate the app or record human acceptance.
The output is not ready until render_docx.py and all-page visual review pass.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1] / "artifacts/pqc-enterprise-demo"


def export(package: Path):
    package = package.absolute()
    if any(p.is_symlink() for p in (package, *package.parents)) or not package.is_relative_to(ROOT):
        raise ValueError("private_candidate_required")
    source, target = package / "Operator_guide.md", package / "Operator_guide.docx"
    if target.exists() or not source.is_file():
        raise ValueError("existing_source_and_new_docx_required")
    os.umask(0o077)
    subprocess.run(["pandoc", str(source), "--from=markdown", "--to=docx", "--output", str(target)], check=True)
    doc = Document(target)
    for name in ("Normal", "Body Text", "First Paragraph", "Compact", "List Paragraph"):
        if name not in doc.styles:
            continue
        style = doc.styles[name]
        style.font.name = "Calibri"
        style.font.size = Pt(11)
        style.font.color.rgb = RGBColor.from_string("172D3B")
        fmt = style.paragraph_format
        fmt.space_before, fmt.space_after, fmt.line_spacing = Pt(0), Pt(6), 1.25
        fmt.widow_control = True
        fmt.keep_together = True
        fmt.alignment = 0
    for name, size, before, after, color in [
        ("Title", 23, 0, 4, "000000"), ("Subtitle", 14, 0, 16, "373737"),
        ("Heading 1", 16, 18, 10, "2E74B5"), ("Heading 2", 13, 14, 7, "2E74B5"),
        ("Heading 3", 12, 10, 5, "1F4D78")]:
        style = doc.styles[name]
        style.font.name, style.font.size = "Calibri", Pt(size)
        style.font.color.rgb = RGBColor.from_string(color)
        style.font.bold = name not in {"Subtitle"}
        fmt = style.paragraph_format
        fmt.space_before, fmt.space_after = Pt(before), Pt(after)
        fmt.line_spacing, fmt.keep_with_next = 1.1, True
        fmt.alignment = 0
    for name in ("Verbatim Char", "Source Code"):
        if name in doc.styles:
            doc.styles[name].font.name = "Liberation Mono"
            doc.styles[name].font.size = Pt(10)
    # Preserve Pandoc's semantic numbering and indentation, with exact compact
    # guide geometry rather than manually typed bullet/number characters.
    for level in doc.part.numbering_part.element.findall(".//" + qn("w:lvl")):
        ppr = level.find(qn("w:pPr"))
        if ppr is None:
            ppr = OxmlElement("w:pPr")
            level.append(ppr)
        for old in list(ppr):
            if old.tag in {qn("w:ind"), qn("w:tabs")}:
                ppr.remove(old)
        indent = OxmlElement("w:ind")
        indent.set(qn("w:left"), "540")
        indent.set(qn("w:hanging"), "270")
        ppr.append(indent)
        tabs, tab = OxmlElement("w:tabs"), OxmlElement("w:tab")
        tab.set(qn("w:val"), "num")
        tab.set(qn("w:pos"), "540")
        tabs.append(tab)
        ppr.append(tabs)
    for paragraph in doc.paragraphs:
        ppr = paragraph._p.pPr
        if ppr is not None and ppr.find(qn("w:numPr")) is not None:
            paragraph.paragraph_format.space_after = Pt(4)
            paragraph.paragraph_format.line_spacing = 1.25
    if doc.paragraphs:
        doc.paragraphs[0].style = doc.styles["Title"]
        if len(doc.paragraphs) > 1:
            doc.paragraphs[1].style = doc.styles["Subtitle"]
    for section in doc.sections:
        section.page_width, section.page_height = Inches(8.5), Inches(11)
        section.top_margin = section.bottom_margin = section.left_margin = section.right_margin = Inches(1)
        section.header_distance = section.footer_distance = Inches(.492)
        header = section.header.paragraphs[0]
        header.text = "PQC  /  OPERATOR FIELD GUIDE  /  SYNTHETIC DEVELOPMENT"
        header.paragraph_format.space_after = Pt(0)
        for run in header.runs:
            run.font.name, run.font.size = "Calibri", Pt(8)
            run.font.color.rgb = RGBColor.from_string("49616B")
        footer = section.footer.paragraphs[0]
        footer.alignment = 2
        footer.add_run("Synthetic training only · Page ")
        field = OxmlElement("w:fldSimple")
        field.set(qn("w:instr"), "PAGE")
        footer._p.append(field)
        for run in footer.runs:
            run.font.name, run.font.size = "Calibri", Pt(8)
    doc.core_properties.title = "PQC assessment: operator field guide"
    doc.core_properties.subject = "All-domain synthetic assessment workflow; source-checked instructions"
    doc.core_properties.author = "PQC assessment workspace"
    doc.save(target)
    os.chmod(target, 0o600)
    design = {"preset": "compact_reference_guide", "header": "memo_masthead",
              "geometry": {"page": "US Letter", "marginsInches": 1, "usableWidthDxa": 9360},
              "body": {"font": "Calibri", "sizePt": 11, "afterPt": 6, "lineSpacing": 1.25},
              "lists": {"leftDxa": 540, "hangingDxa": 270, "afterPt": 4, "lineSpacing": 1.25},
              "namedOverrides": {"furniture": "Calibri 8pt; muted #49616B header; synthetic footer",
                                 "masthead": "23pt black title, 14pt dark-gray subtitle; left aligned, no decorative rule",
                                 "literalReferences": "Liberation Mono 10pt for file names and literal values"},
              "tables": 0, "requiresEveryPageVisualReview": True,
              "browserWalkthroughVerified": False, "ownerOutcome": None}
    (package / "document-design.json").write_text(json.dumps(design, indent=2) + "\n")
    print(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    export(parser.parse_args().package)
