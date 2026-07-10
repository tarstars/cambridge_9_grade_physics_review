#!/usr/bin/env python3
"""Generate 'Physics — Topics to Master' PDF from the baseline results.

Reads assessment_tool/questions.json + results.json, lists every question still
scored 0 or 1, grouped into large topic blocks (biggest first), as a printable
checklist. Re-run after a re-test to get an updated list. Needs reportlab.
"""
import json, os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.colors import HexColor
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, HRFlowable, KeepTogether)
from reportlab.graphics.shapes import Drawing, Rect

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AT = os.path.join(ROOT, "assessment_tool")
OUT = os.path.join(ROOT, "review", "topics-to-master.pdf")

INK = HexColor("#1f2430"); ACCENT = HexColor("#2f6fed"); MUTED = HexColor("#5b6473")
LINE = HexColor("#e2e5ea"); RED = HexColor("#e5534b"); AMBER = HexColor("#d99413")

Q = json.load(open(os.path.join(AT, "questions.json"), encoding="utf-8"))
R = json.load(open(os.path.join(AT, "results.json"), encoding="utf-8"))
ans = R["sessions"][0]["answers"]
TEXT = {q["id"]: q["text"] for t in Q["topics"] for s in t["subtopics"] for q in s["questions"]}

# topic blocks (biggest first), each: (name, [ids in reading order], where-to-read)
BLOCKS = [
 ("Forces & mechanics",
  ["g8-6","g8-7","g8-8","g8-4","g8-5","g7-4","g7-6","g9-1","g9-2","g9-3","g9-4","g9-5","g9-6","g9-7","g9-8","g9-9","g9-10"],
  "NCERT ch4 &amp; ch6 · Cambridge Stage 8 §3"),
 ("Electricity &amp; magnetism",
  ["g7-16","g7-17","g7-18","g8-24","g8-25","g9-17","g9-18","g9-19","g9-20","g9-21","g9-22","g9-23"],
  "Siyavula ch15–17 · CK-12 ch23–25 · Cambridge Stage 7/8/9 §9"),
 ("Energy &amp; work (incl. heat)",
  ["g7-8","g7-9","g8-12","g8-14","g8-15","g8-17","g9-11","g9-12","g9-13","g9-14","g9-15"],
  "NCERT ch7 · CK-12 ch17–18 · Cambridge Stage 7 §3.5–3.7"),
 ("Optics / light",
  ["g8-18","g8-19","g8-20","g8-21","g8-22","g8-23"],
  "Cambridge Stage 8 §6.1–6.3 · CK-12 ch22"),
 ("Waves &amp; sound",
  ["g7-14","g7-15","g9-24","g9-25","g9-26","g9-27"],
  "NCERT ch10 · Siyavula ch8–10 · Cambridge Stage 9 §6"),
 ("Pressure &amp; fluids",
  ["g8-9","g8-10","g8-11","g9-16"],
  "CK-12 ch15 · Cambridge Stage 8 §3.5–3.6"),
 ("The atom",
  ["g9-28","g9-29"],
  "Siyavula ch4 · CK-12 ch5"),
 ("Maths &amp; practical skills",
  ["sk-1","sk-2","sk-4"],
  "Practice via the test's problems and worked examples"),
]

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Title"], fontSize=22, leading=25, textColor=INK, alignment=TA_LEFT, spaceAfter=2)
SUB = ParagraphStyle("SUB", parent=styles["Normal"], fontSize=10.5, leading=14, textColor=MUTED, spaceAfter=10)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, leading=16, textColor=ACCENT, spaceBefore=13, spaceAfter=1)
READ = ParagraphStyle("READ", parent=styles["Normal"], fontSize=8.7, leading=11, textColor=MUTED, spaceAfter=5)
ITEM = ParagraphStyle("ITEM", parent=styles["Normal"], fontSize=9.7, leading=12.5, textColor=INK)
LEG = ParagraphStyle("LEG", parent=styles["Normal"], fontSize=9, leading=13, textColor=INK, spaceAfter=2)

def checkbox():
    d = Drawing(12, 11)
    d.add(Rect(1, 0.5, 9, 9, fillColor=None, strokeColor=HexColor("#9aa2af"), strokeWidth=0.9))
    return d

def dot(mark):
    c = "#e5534b" if mark == 0 else "#d99413"
    return f'<font color="{c}">●</font>'

def build():
    weak = {i: ans[i]["mark"] for i in ans if ans[i].get("mark") in (0, 1)}
    n0 = sum(1 for m in weak.values() if m == 0)
    n1 = sum(1 for m in weak.values() if m == 1)
    doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=1.8*cm, rightMargin=1.8*cm,
                            topMargin=1.6*cm, bottomMargin=1.5*cm, title="Physics — Topics to Master")
    story = [Paragraph("Physics — Topics to Master", H1),
             Paragraph("From the baseline diagnostic (Grade 7–9 program, 28 Jun 2026). "
                       "Tick each box when he can explain it in English and solve a simple problem on it.", SUB),
             HRFlowable(width="100%", thickness=1, color=LINE), Spacer(1, 7),
             Paragraph(f'<b>{len(weak)} topics to master</b> &nbsp;—&nbsp; '
                       f'{dot(0)} <b>{n0}</b> not yet known &nbsp;&nbsp; {dot(1)} <b>{n1}</b> shaky. '
                       f'Grouped by topic, largest first.', LEG),
             Spacer(1, 2)]
    for name, ids, read in BLOCKS:
        items = [(i, TEXT[i], weak[i]) for i in ids if i in weak]
        if not items:
            continue
        head = Paragraph(f'{name} &nbsp;<font size="9" color="#5b6473">({len(items)} to master)</font>', H2)
        readp = Paragraph(f'Read: {read}', READ)
        rows = []
        for i, txt, mark in items:
            p = Paragraph(f'{dot(mark)}&nbsp; {esc(txt)} '
                          f'<font size="7.5" color="#9aa2af">{i}</font>', ITEM)
            rows.append([checkbox(), p])
        tbl = Table(rows, colWidths=[0.7*cm, None])
        tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (0, -1), 0),
            ("LEFTPADDING", (1, 0), (1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]))
        story.append(KeepTogether([head, readp]))
        story.append(tbl)

    def footer(canvas, d):
        canvas.saveState()
        canvas.setStrokeColor(LINE); canvas.line(1.8*cm, 1.2*cm, A4[0]-1.8*cm, 1.2*cm)
        canvas.setFont("Helvetica", 8); canvas.setFillColor(MUTED)
        canvas.drawString(1.8*cm, 0.85*cm, "Physics — Topics to Master")
        canvas.drawRightString(A4[0]-1.8*cm, 0.85*cm, "Page %d" % d.page)
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print("wrote", OUT, "|", len(weak), "topics")

if __name__ == "__main__":
    build()
