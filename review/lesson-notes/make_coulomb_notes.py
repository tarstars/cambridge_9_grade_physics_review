#!/usr/bin/env python3
"""Lesson notes #1: 'From Nothing to Coulomb's Law' — corrected & extended notes PDF.

Regenerate with:  python3 make_coulomb_notes.py   (needs reportlab; uses DejaVu fonts)
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                HRFlowable, KeepTogether)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "2026-07-12-coulomb-law-notes.pdf")

INK = HexColor("#1f2430"); ACCENT = HexColor("#2f6fed"); MUTED = HexColor("#5b6473")
LINE = HexColor("#e2e5ea"); BOX = HexColor("#f2f6ff")

# --- fonts: DejaVu for full Unicode (ε, ₀, ×, μ, …) -------------------------
FD = "/usr/share/fonts/truetype/dejavu"
pdfmetrics.registerFont(TTFont("DejaVu", os.path.join(FD, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", os.path.join(FD, "DejaVuSans-Bold.ttf")))
oblique = os.path.join(FD, "DejaVuSans-Oblique.ttf")
if os.path.exists(oblique):
    pdfmetrics.registerFont(TTFont("DejaVu-Oblique", oblique))
    pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold",
                                  italic="DejaVu-Oblique", boldItalic="DejaVu-Bold")
else:
    pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold",
                                  italic="DejaVu", boldItalic="DejaVu-Bold")

def st(name, **kw):
    base = dict(fontName="DejaVu", fontSize=10, leading=14, textColor=INK)
    base.update(kw)
    return ParagraphStyle(name, **base)

H1 = st("H1", fontName="DejaVu-Bold", fontSize=19, leading=23, spaceAfter=2)
SUB = st("SUB", fontSize=10, leading=13, textColor=MUTED, spaceAfter=10)
H2 = st("H2", fontName="DejaVu-Bold", fontSize=12.5, leading=16, textColor=ACCENT,
        spaceBefore=13, spaceAfter=4)
BODY = st("BODY", spaceAfter=5)
STEP = st("STEP", fontSize=10.3, leading=13.5)
NOTE = st("NOTE", fontSize=8.8, leading=11.5, textColor=MUTED)
FRM = st("FRM", fontName="DejaVu-Bold", fontSize=14, leading=17)
FRs = st("FRs", fontSize=11, leading=13)

def frac(num, den, style, pad=2):
    """Stacked fraction as a small table with a line between."""
    t = Table([[Paragraph(num, style)], [Paragraph(den, style)]])
    t.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (0, 0), 1.1, INK),
        ("TOPPADDING", (0, 0), (-1, -1), pad),
        ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t

def row(cells, widths=None):
    t = Table([cells], colWidths=widths)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t

STEPS = [
    ("Everything is made of particles.",
     "Matter is made of atoms, and atoms are made of protons, neutrons and electrons."),
    ("Electric charge is a property of a particle.",
     "Just as a particle has mass, it can carry charge. Charge is measured in coulombs (C)."),
    ("Particles can be positive, negative, or neutral.",
     "The proton is positive, the electron is negative, the neutron is neutral."),
    ("Charge is quantised: it comes in steps of the elementary charge e.",
     "Every observed charge is a whole-number multiple of e. The proton carries exactly +e and the "
     "electron exactly −e. (Fine print: quarks carry ±e/3 and ±2e/3, but they are never seen alone.)"),
    ("Charged particles interact: they attract or repel each other.",
     "Neutral particles feel no electric force."),
    ("Like charges repel; unlike charges attract.",
     "+ and + push apart, − and − push apart, + and − pull together."),
    ("The net charge of a body counts its imbalance of particles:  Q = (N₊ − N₋) · e.",
     "N₊ = number of positive charges (protons), N₋ = number of negative ones (electrons). Most bodies "
     "have N₊ ≈ N₋, so they are neutral."),
    ("Charge is conserved.",
     "Charge is never created or destroyed — it only moves from one body to another (e.g. rubbing a "
     "balloon moves electrons onto it)."),
    ("Coulomb's law tells us how strong the force is.",
     "See the box below — the climax of the chain."),
]

FIXES = [
    ("dipell / dispell", "repel"),
    ("magnitue", "magnitude"),
    ("charge particles", "charged particles"),
    ("equal signs of charge …", "like charges …"),
    ("opposite – attract", "unlike (opposite) charges attract"),
    ("Coulomb law: k*q1*q2/(r*r)", "Coulomb's law: F = k·|q₁|·|q₂| / r²"),
]

CONSTANTS = [
    ("Elementary charge", "e", "1.602 × 10⁻¹⁹ C", "exact: 1.602 176 634 × 10⁻¹⁹ C"),
    ("Electron charge", "−e", "−1.602 × 10⁻¹⁹ C", "proton: +e"),
    ("Coulomb constant", "k = 1/(4πε₀)", "8.99 × 10⁹ N·m²/C²", "remember as ≈ 9 × 10⁹"),
    ("Vacuum permittivity", "ε₀", "8.854 × 10⁻¹² C²/(N·m²)", "same thing as F/m"),
    ("Charges in 1 coulomb", "1 C / e", "6.24 × 10¹⁸", "1 C is a *huge* charge"),
    ("Electron mass", "mₑ", "9.11 × 10⁻³¹ kg", "proton is ≈1836× heavier"),
]

REFS = [
    ("Siyavula, Physical Sciences Gr 10",
     "docs/textbook/siyavula-physical-sciences/Gr10_PhysicalSciences_Learner_Eng.pdf",
     "ch 16 Electrostatics — §16.2 Two kinds of charge (PDF p.276), §16.3 Conservation of charge "
     "(PDF p.282), §16.4 Quantisation of charge (PDF p.284). Closest match to these notes."),
    ("CK-12, Physical Science Workbook",
     "docs/textbook/ck12-physical-science/CK-12-Physical-Science-MS-Workbook-with-Answers.pdf",
     "lesson 23.1 Electric Charge (printed p.276 ≈ PDF p.283) — practice worksheets; answers in "
     "ch 26.23 (printed p.417)."),
    ("NCERT, Class 9 Science",
     "docs/textbook/ncert-class9-physics/other-chapters/ch08-journey-inside-the-atom.pdf",
     "§8.2–8.6 (PDF pp.2–12) — protons & electrons, atomic number: why atoms are neutral and where "
     "the charges sit."),
    ("Cambridge Lower Secondary, Stage 7",
     "docs/textbook/cambridge/Cambridge_Lower_Secondary_Science_2ed_7_Learners_book.pdf",
     "Unit 9, §9.1 Flow of electricity (≈ p.287) — moving charge = current: the next step after "
     "these notes."),
]

def build():
    doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=1.9*cm, rightMargin=1.9*cm,
                            topMargin=1.6*cm, bottomMargin=1.6*cm,
                            title="From Nothing to Coulomb's Law — lesson notes")
    S = []
    S.append(Paragraph("From Nothing to Coulomb's Law", H1))
    S.append(Paragraph("Electricity — lesson notes · discussion of 12 July 2026 · Dad's notes, "
                       "corrected and extended", SUB))
    S.append(HRFlowable(width="100%", thickness=1, color=LINE))

    # --- chain of ideas ---
    S.append(Paragraph("The chain of ideas", H2))
    rows = []
    for n, (head, sub) in enumerate(STEPS, 1):
        rows.append([Paragraph(f"<b>{n}</b>", st("N", fontName="DejaVu-Bold", textColor=ACCENT)),
                     Paragraph(f"<b>{head}</b><br/><font size=8.8 color=#5b6473>{sub}</font>", STEP)])
    t = Table(rows, colWidths=[0.75*cm, None])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    S.append(t)

    # --- Coulomb's law box ---
    S.append(Paragraph("Coulomb's law", H2))
    formula = row([
        Paragraph("F&nbsp;&nbsp;=&nbsp;&nbsp;k ·", FRM),
        frac("|q₁| · |q₂|", "r²", FRs),
        Paragraph("&nbsp;&nbsp;&nbsp;with&nbsp;&nbsp;&nbsp;k&nbsp;=", FRs),
        frac("1", "4πε₀", FRs),
        Paragraph("&nbsp;≈&nbsp;8.99 × 10⁹ N·m²/C²", FRs),
    ])
    inner = [
        formula, Spacer(1, 6),
        Paragraph("• <b>q₁, q₂</b> — the two charges (in coulombs); <b>r</b> — the distance between "
                  "them (in metres). Valid for <b>point charges</b> (small compared with r).", BODY),
        Paragraph("• The force acts <b>along the line joining the charges</b>: like charges are pushed "
                  "apart, unlike charges pulled together. Both charges feel the <b>same</b> force, in "
                  "opposite directions (Newton's third law).", BODY),
        Paragraph("• <b>Inverse square:</b> double the distance → one quarter of the force.", BODY),
        Paragraph("<b>Worked example.</b> Two charges of 1 μC each, 10 cm apart:  "
                  "F = 8.99×10⁹ · (10⁻⁶)² / (0.1)² ≈ <b>0.9 N</b> — about the weight of a small apple.",
                  BODY),
        Paragraph("Scale check: two charges of 1 C at 1 m would push with 9×10⁹ N (≈ the weight of "
                  "900 000 tonnes) — that is why real charges are microcoulombs.", NOTE),
    ]
    box = Table([[inner]], colWidths=[None])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BOX),
        ("BOX", (0, 0), (-1, -1), 1, ACCENT),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    S.append(box)

    # --- constants ---
    S.append(Paragraph("Constants worth remembering", H2))
    crows = [[Paragraph("<b>Quantity</b>", BODY), Paragraph("<b>Symbol</b>", BODY),
              Paragraph("<b>Value</b>", BODY), Paragraph("<b>Note</b>", BODY)]]
    for name, sym, val, note in CONSTANTS:
        crows.append([Paragraph(name, BODY), Paragraph(sym, BODY),
                      Paragraph(val, BODY), Paragraph(f"<font size=8.6 color=#5b6473>{note}</font>", BODY)])
    ct = Table(crows, colWidths=[4.4*cm, 2.9*cm, 4.6*cm, None])
    ct.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.9, ACCENT),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
    ]))
    S.append(ct)

    # --- English fixes ---
    S.append(Paragraph("English fixes from the draft", H2))
    frows = [[Paragraph("<b>In the draft</b>", BODY), Paragraph("<b>Correct</b>", BODY)]]
    for a, b in FIXES:
        frows.append([Paragraph(f"<font color=#a33>{a}</font>", BODY), Paragraph(b, BODY)])
    ft = Table(frows, colWidths=[7.4*cm, None])
    ft.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.9, ACCENT),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
    ]))
    S.append(ft)

    # --- references ---
    S.append(Paragraph("Where to read (from our archive)", H2))
    for name, path, where in REFS:
        S.append(KeepTogether([
            Paragraph(f"<b>{name}</b> — <font size=8.6 face='DejaVu' color=#5b6473>{path}</font>", BODY),
            Paragraph(f"<font size=9.2>{where}</font>", st("RW", leftIndent=12, spaceAfter=7)),
        ]))
    S.append(Paragraph("The fully quantitative Coulomb's-law chapter is in <b>Siyavula Physical Sciences "
                       "Grade 11</b> (free, openly licensed) — not in the archive yet; easy to add.", NOTE))

    def footer(canvas, d):
        canvas.saveState()
        canvas.setStrokeColor(LINE); canvas.line(1.9*cm, 1.15*cm, A4[0]-1.9*cm, 1.15*cm)
        canvas.setFont("DejaVu", 8); canvas.setFillColor(MUTED)
        canvas.drawString(1.9*cm, 0.8*cm, "From Nothing to Coulomb's Law — lesson notes")
        canvas.drawRightString(A4[0]-1.9*cm, 0.8*cm, "Page %d" % d.page)
        canvas.restoreState()

    doc.build(S, onFirstPage=footer, onLaterPages=footer)
    print("wrote", OUT)

if __name__ == "__main__":
    build()
