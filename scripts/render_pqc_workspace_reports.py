#!/usr/bin/env python3
"""Fixed-layout reading copies of the frozen C# report HTML; no new conclusions.

All visible report prose plus its supporting appendix is carried into PDF.
No resource fetching, scripting, live data reads or HTML action execution.
"""
from __future__ import annotations
import argparse
import os
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether


class ReportBlocks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.body=False;self.skip=0;self.tag=None;self.parts=[];self.blocks=[];self.link=False
    def handle_starttag(self,tag,attrs):
        if tag=="body":self.body=True
        if not self.body:return
        if tag in ("nav","script","style"):self.skip+=1
        if self.skip:return
        if tag in ("h1","h2","h3","h4","p","li","summary","aside","dt","dd"):
            self.flush();self.tag=tag;self.parts=[]
        elif self.tag and tag in ("strong","b"):self.parts.append("<b>")
        elif self.tag and tag in ("em","i"):self.parts.append("<i>")
        elif self.tag and tag=="br":self.parts.append("<br/>")
        elif self.tag and tag=="a":
            href=dict(attrs).get("href", "")
            # Frozen report citations only: no fetching, file paths or active actions.
            if href.startswith(("https://csrc.nist.gov/", "https://www.nccoe.nist.gov/")):
                self.parts.append('<link href="'+escape(href,quote=True)+'" color="#126773">');self.link=True
    def handle_endtag(self,tag):
        if tag in ("nav","script","style") and self.skip:self.skip-=1;return
        if self.skip:return
        if tag==self.tag:self.flush()
        elif self.tag and tag in ("strong","b"):self.parts.append("</b>")
        elif self.tag and tag in ("em","i"):self.parts.append("</i>")
        elif self.tag and tag=="a" and self.link:self.parts.append("</link>");self.link=False
    def handle_data(self,data):
        if self.body and not self.skip and self.tag:self.parts.append(escape(data))
    def flush(self):
        if self.tag and "".join(self.parts).strip():self.blocks.append((self.tag,"".join(self.parts)))
        self.tag=None;self.parts=[]


def render(source:Path):
    os.umask(0o077)
    blocks=ReportBlocks();blocks.feed(source.read_text());blocks.flush()
    ink=colors.HexColor("#172D3B");teal=colors.HexColor("#126773")
    base=ParagraphStyle("Body",fontName="Helvetica",fontSize=10,leading=14,textColor=ink,spaceAfter=7,alignment=TA_LEFT,splitLongWords=True)
    styles={
        "p":base,
        "dt":ParagraphStyle("Term",parent=base,fontName="Helvetica-Bold",spaceBefore=7,spaceAfter=2,keepWithNext=True),
        "dd":ParagraphStyle("Definition",parent=base,leftIndent=10,spaceAfter=7),
        "li":ParagraphStyle("List",parent=base,leftIndent=11,firstLineIndent=-8,spaceAfter=5),
        "h1":ParagraphStyle("Title",parent=base,fontName="Helvetica-Bold",fontSize=23,leading=27,spaceBefore=5,spaceAfter=18,keepWithNext=True),
        "h2":ParagraphStyle("H2",parent=base,fontName="Helvetica-Bold",fontSize=15,leading=19,textColor=teal,spaceBefore=19,spaceAfter=10,keepWithNext=True),
        "h3":ParagraphStyle("H3",parent=base,fontName="Helvetica-Bold",fontSize=11,leading=15,spaceBefore=11,spaceAfter=6,keepWithNext=True),
        "h4":ParagraphStyle("H4",parent=base,fontName="Helvetica-Bold",fontSize=10,leading=14,spaceBefore=10,spaceAfter=5,keepWithNext=True),
        "summary":ParagraphStyle("Appendix",parent=base,fontName="Helvetica-Bold",fontSize=15,leading=19,textColor=teal,spaceBefore=22,spaceAfter=10,keepWithNext=True),
        "aside":ParagraphStyle("Boundary",parent=base,backColor=colors.HexColor("#FFF6E8"),borderPadding=10,spaceBefore=8,spaceAfter=17,fontSize=9,leading=13),
    }
    story=[];references=None
    for tag,text in blocks.blocks:
        if tag=="li":text="• "+text
        if tag=="h2" and text=="Guidance and applicability":references=[]
        paragraph=Paragraph(text,styles[tag])
        (references if references is not None else story).append(paragraph)
    if references:story.append(KeepTogether(references))
    output=source.with_suffix(".pdf")
    def furniture(canvas,doc):
        canvas.saveState();canvas.setStrokeColor(colors.HexColor("#CBD8DF"));canvas.line(44,39,A4[0]-44,39)
        canvas.setFont("Helvetica",8);canvas.setFillColor(colors.HexColor("#49616B"));canvas.drawString(44,26,"PQC / SYNTHETIC ASSESSMENT / Frozen C# report reading copy")
        canvas.drawRightString(A4[0]-44,26,f"{doc.page}");canvas.restoreState()
    doc=SimpleDocTemplate(str(output),pagesize=A4,rightMargin=44,leftMargin=44,topMargin=42,bottomMargin=51,
        title=source.stem.replace("_"," ")+" — Synthetic development report",author="PQC assessment workspace")
    doc.build(story,onFirstPage=furniture,onLaterPages=furniture)
    print(output)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("html",nargs="+",type=Path)
    for file in parser.parse_args().html:render(file)
