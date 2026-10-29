"""Build docs/Kaaran_Build_Deck.pptx (12 slides, 16:9) with python-pptx.

Run: .venv\\Scripts\\python scripts\\make_deck.py [--out docs/Kaaran_Build_Deck.pptx] [--check-only]

Every figure on the slides comes from the repository: PROGRESS.md, docs/09_PROGRESS_REPORT.md,
docs/01, docs/03, docs/07, docs/11, and eval/test runs in replay mode (2026-10-29):
  python -m kaaran.eval.intent --tier light --tier main --tier rule -> 92% / 100% / 96% (25 questions)
  python -m kaaran.eval.block --seed 42 --seed 7 --seed 99 --seed 2026 --seed 11 --seed 77 -> 19/19 each, no extra flags
  python -m kaaran.eval --seed 42 --seed 2026 --seed 1 --seed 99 (+ --seed 7 --names fictional) -> 8/8, 0 false flags
  python -m kaaran.eval.mapping --seed 42 -> variant_b: rule 0%, LLM 100%; kaaran.eval.brief --seed 42 -> 0 invented
  python -m kaaran.eval.guardrails -> same mapping with and without the injected text
  (the ~98% recall over 60 seeds is the 27 Oct calibration in PROGRESS.md, not re-run)
  python -m pytest --co -q                   -> 289 tests collected (246 fast)
Demo data is SYNTHETIC; slides that show it say so.
After saving, the deck is re-opened and every text frame is checked for overflow (estimate).
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "Kaaran_Build_Deck.pptx"

# Palette (matches the web product)
NAVY = RGBColor(0x12, 0x32, 0x4F)
SAFFRON = RGBColor(0xFF, 0x99, 0x33)
GREEN = RGBColor(0x13, 0x88, 0x08)
INK = RGBColor(0x1F, 0x29, 0x37)
GREY = RGBColor(0x5B, 0x67, 0x75)
LIGHT = RGBColor(0xF3, 0xF6, 0xF9)
LINE = RGBColor(0xD5, 0xDC, 0xE4)
SAFFRON_BG = RGBColor(0xFF, 0xF1, 0xE0)
GREEN_BG = RGBColor(0xE6, 0xF4, 0xE4)
NAVY_BG = RGBColor(0xE4, 0xEB, 0xF2)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

LATIN = "Segoe UI"
DEVA = "Nirmala UI"  # Windows Devanagari font; Noto Sans Devanagari is the fallback on other systems

SLIDE_W, SLIDE_H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.6)
REPO = "https://github.com/DurgeshC16/Kaaran"


# ---------------------------------------------------------------- helpers

def is_deva(text: str) -> bool:
    return any("ऀ" <= ch <= "ॿ" for ch in text)


def style_run(run, size, bold=False, color=INK, italic=False):
    f = run.font
    f.size = Pt(size)
    f.bold = bold
    f.italic = italic
    f.color.rgb = color
    f.name = DEVA if is_deva(run.text) and not any(c.isascii() and c.isalpha() for c in run.text) else LATIN
    rpr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        el = rpr.find(qn(tag))
        if el is None:
            el = rpr.makeelement(qn(tag), {})
            latin = rpr.find(qn("a:latin"))
            latin.addnext(el) if tag == "a:ea" else rpr.find(qn("a:ea")).addnext(el)
        el.set("typeface", DEVA)


def set_bullet(p, level_in=0.28):
    ppr = p._p.get_or_add_pPr()
    ppr.set("marL", str(Inches(level_in)))
    ppr.set("indent", str(-Inches(0.22)))
    bu_font = ppr.makeelement(qn("a:buFont"), {"typeface": "Arial"})
    bu_char = ppr.makeelement(qn("a:buChar"), {"char": "•"})
    ppr.append(bu_font)
    ppr.append(bu_char)


def text_box(slide, x, y, w, h, paras, anchor=MSO_ANCHOR.TOP, fill=None, line=None, margin=0.08, name=None):
    """paras: list of dicts {t: text or [(text, overrides)], size, bold, color, bullet, align, space}."""
    if fill is not None or line is not None:
        shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
        shp.shadow.inherit = False
        if fill is None:
            shp.fill.background()
        else:
            shp.fill.solid()
            shp.fill.fore_color.rgb = fill
        if line is None:
            shp.line.fill.background()
        else:
            shp.line.color.rgb = line
            shp.line.width = Pt(1)
    else:
        shp = slide.shapes.add_textbox(x, y, w, h)
    if name:
        shp.name = name
    tf = shp.text_frame
    tf.word_wrap = True
    tf.auto_size = None
    tf.vertical_anchor = anchor
    for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, side, Inches(margin))
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = para.get("align", PP_ALIGN.LEFT)
        if i:
            p.space_before = Pt(para.get("space", 6))
        p.line_spacing = 1.05
        segs = para["t"] if isinstance(para["t"], list) else [(para["t"], {})]
        for seg, over in segs:
            r = p.add_run()
            r.text = seg
            style_run(r, over.get("size", para.get("size", 18)), over.get("bold", para.get("bold", False)),
                      over.get("color", para.get("color", INK)), over.get("italic", False))
        if para.get("bullet"):
            set_bullet(p)
    return shp


def P(t, size=18, **kw):
    return {"t": t, "size": size, **kw}


def B(t, size=18, **kw):
    return {"t": t, "size": size, "bullet": True, **kw}


def rect(slide, x, y, w, h, color, shape=MSO_SHAPE.RECTANGLE):
    s = slide.shapes.add_shape(shape, x, y, w, h)
    s.shadow.inherit = False
    s.fill.solid()
    s.fill.fore_color.rgb = color
    s.line.fill.background()
    return s


def base_slide(prs, title, subtitle=None, num=None, synthetic=False):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    # thin tricolour accent bar at the very top: saffron | white | green
    third = int(SLIDE_W / 3)
    rect(s, 0, 0, third, Inches(0.09), SAFFRON)
    rect(s, 2 * third, 0, SLIDE_W - 2 * third, Inches(0.09), GREEN)
    text_box(s, MARGIN, Inches(0.3), SLIDE_W - 2 * MARGIN, Inches(0.75),
             [P(title, 30, bold=True, color=NAVY)], anchor=MSO_ANCHOR.MIDDLE, margin=0.02, name="title")
    if subtitle:
        text_box(s, MARGIN, Inches(1.02), SLIDE_W - 2 * MARGIN, Inches(0.45),
                 [P(subtitle, 17, color=GREY)], margin=0.02, name="subtitle")
    rect(s, MARGIN, Inches(1.5), Inches(1.2), Inches(0.05), SAFFRON)
    # footer
    rect(s, MARGIN, Inches(7.0), SLIDE_W - 2 * MARGIN, Emu(9525), LINE)
    text_box(s, MARGIN, Inches(7.05), Inches(8), Inches(0.35),
             [P("Kaaran (कारण) · Team EASY COMPANY · Challenge 4: Data to Action", 11, color=GREY)], margin=0.02)
    if num:
        text_box(s, SLIDE_W - MARGIN - Inches(0.8), Inches(7.05), Inches(0.8), Inches(0.35),
                 [P(str(num), 11, color=GREY, align=PP_ALIGN.RIGHT)], margin=0.02)
    if synthetic:
        tag = text_box(s, SLIDE_W - MARGIN - Inches(3.2), Inches(0.42), Inches(3.2), Inches(0.42),
                       [P("Demo data: SYNTHETIC", 14, bold=True, color=RGBColor(0x9A, 0x4D, 0x00), align=PP_ALIGN.CENTER)],
                       anchor=MSO_ANCHOR.MIDDLE, fill=SAFFRON_BG, line=SAFFRON, margin=0.04)
        tag.name = "synthetic-tag"
    return s


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def card(slide, x, y, w, h, head, body, accent=NAVY, bg=LIGHT, head_size=17, body_size=14):
    rect(slide, x, y, Inches(0.08), h, accent)
    paras = [P(head, head_size, bold=True, color=accent if accent != SAFFRON else RGBColor(0x9A, 0x4D, 0x00))]
    for line in body if isinstance(body, list) else [body]:
        paras.append(P(line, body_size, color=INK, space=4))
    return text_box(slide, x + Inches(0.08), y, w - Inches(0.08), h, paras, fill=bg, margin=0.12)


def kpi(slide, x, y, w, h, big, caption, color=NAVY, bg=LIGHT):
    return text_box(slide, x, y, w, h, [P(big, 30, bold=True, color=color, align=PP_ALIGN.CENTER),
                                        P(caption, 14, color=INK, align=PP_ALIGN.CENTER, space=4)],
                    anchor=MSO_ANCHOR.MIDDLE, fill=bg, margin=0.1)


def grid(n_cols, n_rows, top, bottom=Inches(6.85), gap=Inches(0.2), left=MARGIN, right=None):
    right = right if right is not None else SLIDE_W - MARGIN
    w = int((right - left - gap * (n_cols - 1)) / n_cols)
    h = int((bottom - top - gap * (n_rows - 1)) / n_rows)
    return [(left + c * (w + gap), top + r * (h + gap), w, h) for r in range(n_rows) for c in range(n_cols)]


# ---------------------------------------------------------------- slides

def s01_title(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    third = int(SLIDE_W / 3)
    rect(s, 0, 0, third, Inches(0.14), SAFFRON)
    rect(s, 2 * third, 0, SLIDE_W - 2 * third, Inches(0.14), GREEN)
    rect(s, 0, Inches(7.36), third, Inches(0.14), SAFFRON)
    rect(s, 2 * third, Inches(7.36), SLIDE_W - 2 * third, Inches(0.14), GREEN)
    text_box(s, Inches(0.9), Inches(1.3), Inches(11.5), Inches(1.3),
             [P([("Kaaran ", {}), ("(कारण)", {"color": SAFFRON})], 60, bold=True, color=NAVY)], margin=0.02)
    text_box(s, Inches(0.9), Inches(2.65), Inches(12.0), Inches(0.7),
             [P("An AI data analyst for Block and District Education Officers", 26, color=NAVY)], margin=0.02)
    rect(s, Inches(0.9), Inches(3.5), Inches(1.6), Inches(0.06), SAFFRON)
    text_box(s, Inches(0.9), Inches(3.8), Inches(11.5), Inches(1.4),
             [P("Existing systems give officers data. Kaaran gives them a data analyst.", 22, color=INK),
              P("प्रश्न मराठीत विचारा: थेट उत्तर, कारण, आणि काय करावे, पुराव्यासह.", 20, color=GREY, space=10)],
             margin=0.02)
    text_box(s, Inches(0.9), Inches(5.6), Inches(11.5), Inches(1.0),
             [P("Team EASY COMPANY  ·  AI for Foundational Learning Hackathon (ShikshaNext x Anthropic)", 16, color=GREY),
              P("Challenge 4: Data to Action  ·  Build stage, November 2026", 16, color=GREY, space=4)], margin=0.02)
    notes(s, "Kaaran means 'reason' in Marathi. It is an AI data analyst for block and district education officers in "
             "Maharashtra: the officer asks in Marathi or English, by text or voice, on the web or WhatsApp, and gets a "
             "direct answer, the likely reason, and what to do, with every number traceable to its source. "
             "All demo data is synthetic and marked so; we also run real public UDISE+ data for Solapur.")


def s02_problem(prs):
    s = base_slide(prs, "The problem: data does not turn into action",
                   "The gap: a specific, trusted, doable action for one officer before the review meeting (बैठक)", 2)
    left_w = Inches(7.6)
    text_box(s, MARGIN, Inches(1.8), left_w, Inches(5.0), [
        B("A BEO in Maharashtra looks after 150-300 schools in 10-20 clusters (kendras)", 18),
        B("Assessment, attendance and teacher data sit in different portals and Excel sheets", 18, space=10),
        B("The monthly review ends with generic instructions: \"improve attendance\", \"conduct training\"", 18, space=10),
        B("Assessments alone did not change learning: MP school-quality programme, 1,774 schools "
          "(Muralidharan & Singh 2020)", 18, space=10),
        B("Administrative data is often inflated (Singh 2020): data must be checked before it is trusted", 18, space=10),
        B("Most officers do not open dashboards unprompted (mentor review)", 18, space=10),
    ])
    x2 = MARGIN + left_w + Inches(0.4)
    w2 = SLIDE_W - MARGIN - x2
    text_box(s, x2, Inches(1.8), w2, Inches(0.5), [P("Design constraints of the user", 18, bold=True, color=NAVY)], margin=0.02)
    items = [("Low data literacy", "plain language, no dashboards"),
             ("Marathi first, voice first", "मराठी प्रथम, आवाजाने प्रश्न"),
             ("Basic Android, patchy network", "WhatsApp, one-page PDF"),
             ("Messy multi-format files", "the AI does the joining"),
             ("Accountability culture", "evidence, not blame")]
    y = Inches(2.35)
    for head, body in items:
        card(s, x2, y, w2, Inches(0.82), head, body, accent=SAFFRON if "Marathi" in head else NAVY,
             head_size=15, body_size=14)
        y += Inches(0.9)
    notes(s, "The officer is not short of data; the gap is turning data into a specific action he trusts and can do. "
             "Research shows assessments alone do not change learning and administrative data is often inflated, "
             "so Kaaran checks data first and ends every answer with a concrete action. "
             "The right side lists the user constraints we designed for.")


def s03_what(prs):
    s = base_slide(prs, "What Kaaran does", "Officer asks, or new data arrives, and Kaaran answers in Marathi first", 3,
                   synthetic=True)
    steps = [("Ask", "Marathi or English; typed or voice; web or WhatsApp. Or an alert arrives unasked"),
             ("Direct answer", "थेट उत्तर: one line computed by code, figures clickable"),
             ("Kendra cards", "What happened · why (rule-based label) · what to do, owner, timing"),
             ("Evidence brief", "One-page PDF; every figure opens its file, sheet and rows"),
             ("Voice note", "One-minute Marathi voice summary (Sarvam AI) with the PDF on WhatsApp")]
    n = len(steps)
    gap = Inches(0.12)
    w = int((SLIDE_W - 2 * MARGIN - gap * (n - 1)) / n)
    top, h = Inches(1.85), Inches(2.35)
    for i, (head, body) in enumerate(steps):
        x = MARGIN + i * (w + gap)
        shp = s.shapes.add_shape(MSO_SHAPE.CHEVRON if i else MSO_SHAPE.PENTAGON, x, top, w, Inches(0.6))
        shp.shadow.inherit = False
        shp.fill.solid()
        shp.fill.fore_color.rgb = NAVY if i % 2 == 0 else RGBColor(0x2A, 0x5A, 0x85)
        shp.line.fill.background()
        tf = shp.text_frame
        tf.word_wrap = False
        tf.margin_left = tf.margin_right = Inches(0.2)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = head
        style_run(r, 15, bold=True, color=WHITE)
        text_box(s, x, top + Inches(0.7), w, h - Inches(0.7), [P(body, 16, color=INK)], fill=LIGHT, margin=0.12)
    # three-part brief
    y2 = Inches(4.45)
    text_box(s, MARGIN, y2, Inches(8), Inches(0.45),
             [P("The three-part brief and kendra cards", 18, bold=True, color=NAVY)], margin=0.02)
    parts = [("A · लक्ष देण्याची गरज", "What needs attention", SAFFRON, SAFFRON_BG),
             ("B · असे का होत असावे", "Why it may be happening", NAVY, NAVY_BG),
             ("C · काय करावे", "What to do: owner, deadline, follow-up", GREEN, GREEN_BG)]
    for (x, y, w3, h3), (mr, en, acc, bg) in zip(grid(3, 1, y2 + Inches(0.5), Inches(5.95)), parts):
        card(s, x, y, w3, h3, mr, en, accent=acc, bg=bg, head_size=18, body_size=14)
    text_box(s, MARGIN, Inches(6.08), SLIDE_W - 2 * MARGIN, Inches(0.85), [
        P([("Example: ", {"bold": True, "color": NAVY}), ("\"पंढरपूर मध्ये किती केंद्रे आहेत?\"  →  ", {}),
           ("\"पंढरपूरमध्ये १२ केंद्रे आहेत (१४० शाळा).\"", {"bold": True})], 15, color=INK),
        P("Same answer in English: \"Pandharpur has 12 clusters (kendras) with 140 schools.\" "
          "Each figure opens its source.", 14, color=GREY, space=3)], margin=0.02)
    notes(s, "The officer asks in his own words; Kaaran first gives a one-line direct answer computed by code, then kendra "
             "cards with what happened, why with a rule-based confidence label, and what to do with an owner and timing. "
             "The one-page brief and PDF make every figure clickable to its source, and a one-minute Marathi voice summary "
             "goes out on WhatsApp. It can also start without a question: a district scan sends an alert, and the reply "
             "'अहवाल' opens the brief. The example figure is from the synthetic demo district.")


def s04_layers(prs):
    s = base_slide(prs, "AI in layers: where the LLM is used, and where it is not",
                   "Claude does language and messy headers; code does every number, label and action", 4)
    layers = [
        ("DATA INPUT", "AI column mapper: Claude proposes a mapping for messy files, code validates it · "
                       "question reader (Claude Haiku, rule fallback) · Marathi speech-to-text (Sarvam)",
         "AI + code check", SAFFRON, SAFFRON_BG),
        ("PROCESSING", "Deterministic engines (pandas, DuckDB): trust checks → cluster risk scan → diagnoses D1-D8 "
                       "→ decision rubric A1-A13 with constraint checks",
         "CODE ONLY", GREEN, GREEN_BG),
        ("GUARDRAILS", "Number placeholders · sentence verifier · rule-based labels · prompt-injection masking · "
                       "refusals · spend caps · template fallback",
         "CODE ONLY", GREEN, GREEN_BG),
        ("EVALUATION", "Answer-key scorecards on planted districts · invented-number detector · intent eval · "
                       "prompt-injection test",
         "CODE ONLY", GREEN, GREEN_BG),
        ("OUTPUT", "Claude writes Marathi/English wording with {{n:id}} placeholders; code fills every number; "
                   "Sarvam text-to-speech for the voice summary",
         "AI wording + code", SAFFRON, SAFFRON_BG),
    ]
    top = Inches(1.8)
    row_h, gap = Inches(0.85), Inches(0.08)
    label_w, tag_w = Inches(1.9), Inches(1.7)
    arrow_x = MARGIN
    body_x = MARGIN + Inches(0.5) + label_w + Inches(0.12)
    tag_x = SLIDE_W - MARGIN - tag_w
    body_w = tag_x - Inches(0.12) - body_x
    # flow arrow on the left
    arr = s.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, arrow_x, top, Inches(0.38), 5 * row_h + 4 * gap)
    arr.shadow.inherit = False
    arr.fill.solid()
    arr.fill.fore_color.rgb = LINE
    arr.line.fill.background()
    for i, (label, body, tag, acc, bg) in enumerate(layers):
        y = top + i * (row_h + gap)
        lab = text_box(s, MARGIN + Inches(0.5), y, label_w, row_h, [P(label, 17, bold=True, color=WHITE, align=PP_ALIGN.CENTER)],
                       anchor=MSO_ANCHOR.MIDDLE, fill=NAVY, margin=0.06)
        text_box(s, body_x, y, body_w, row_h, [P(body, 14, color=INK)], anchor=MSO_ANCHOR.MIDDLE, fill=LIGHT, margin=0.12)
        text_box(s, tag_x, y, tag_w, row_h, [P(tag, 15, bold=True, color=acc if acc == GREEN else RGBColor(0x9A, 0x4D, 0x00),
                                               align=PP_ALIGN.CENTER)],
                 anchor=MSO_ANCHOR.MIDDLE, fill=bg, line=acc, margin=0.06)
    text_box(s, MARGIN, Inches(6.45), SLIDE_W - 2 * MARGIN, Inches(0.45), [
        P("Cost: ~$0.08 per block brief (Sonnet), ~$0.0002 per question (Haiku); analysis, alerts and actions use no AI.",
          14, color=GREY)], margin=0.02)
    notes(s, "The LLM is used only where it is strong: understanding the officer's question, mapping messy column headers, "
             "and writing Marathi and English sentences. Everything between input and output is deterministic code: "
             "trust checks, risk scan, diagnoses and the decision rubric. Even the AI layers are wrapped in code checks: "
             "mappings are validated, intents use closed lists, and wording can only reference numbers through placeholders.")


def s05_guardrails(prs):
    s = base_slide(prs, "Guardrails against wrong AI output", "Every guardrail is code, and each one is tested", 5)
    items = [
        ("Numbers only from code", "AI writes {{n:id}}; code fills the value with file, sheet and row provenance", NAVY),
        ("Verifier on every sentence", "Valid placeholders, no stray digits or number words, no causal words unless "
                                       "STRONG, no school names → 1 retry → template", NAVY),
        ("Rule-based confidence labels", "STRONG needs effect + share + replication + no pre-trend; else \"associated with\"",
         NAVY),
        ("Prompt-injection masking", "File contents reach the AI only as masked summaries; an injected file gives the "
                                     "same mapping (tested)", NAVY),
        ("Refusals and clarifying", "Never ranks or names individual teachers or students; off-topic refused; "
                                    "asks instead of guessing", SAFFRON),
        ("Spend caps", "Live Claude capped per process (default $15); Sarvam voice capped (default ₹100)", SAFFRON),
        ("Template fallback", "Without the AI: rule question reader and template brief, same numbers and actions", GREEN),
        ("Human in the loop", "Actions are recommendations: the officer confirms or closes each one in the baithak "
                              "tracker, with its follow-up metric", GREEN),
    ]
    for (x, y, w, h), (head, body, acc) in zip(grid(4, 2, Inches(1.8), Inches(6.3)), items):
        card(s, x, y, w, h, head, body, accent=acc, head_size=16, body_size=14)
    text_box(s, MARGIN, Inches(6.42), SLIDE_W - 2 * MARGIN, Inches(0.5), [
        P("Privacy: only aggregates reach the AI; school lists and identifiable data stay on the server.", 14,
          bold=True, color=NAVY)], margin=0.02)
    notes(s, "The AI cannot write a number: it writes placeholders and code fills them from the evidence pack. A verifier "
             "checks every sentence for stray digits, number words, causal wording and school names, retries once, then "
             "falls back to fixed templates. Labels and actions come from written rules, and every action stays a "
             "recommendation until the officer confirms it in the baithak tracker.")


def s06_eval(prs, tests_total, tests_fast):
    s = base_slide(prs, "Evaluation: proof, not promises",
                   "Planted-truth districts with a hidden answer key; re-run in replay mode on 29 Oct 2026", 6, synthetic=True)
    tiles = [
        ("19/19", "block-lens checks on each of 6 seeds (risks, diagnoses, actions)", NAVY),
        ("~98%", "recall over 60 seeds (calibration, 27 Oct); ~3% extra flags (small-school noise)", NAVY),
        ("0", "invented numbers in briefs (verified by code on every brief)", GREEN),
        ("8/8", "planted truths on 5 seeds (v2 taluka lens), 0 false flags", NAVY),
        ("96%", "intent accuracy, rule fallback, 25 questions (Haiku 92%, Sonnet 100%)", NAVY),
        ("100%", "AI column mapping on an unseen file layout (rule baseline 0%)", NAVY),
        ("16 + 23", "adversarial-review findings confirmed and fixed (voice; direct answers)", SAFFRON),
        (f"{tests_total}", f"automated tests ({tests_fast} in the fast suite; live-API tests opt-in)", GREEN),
    ]
    for (x, y, w, h), (big, cap, col) in zip(grid(4, 2, Inches(1.8), Inches(6.35)), tiles):
        kpi(s, x, y, w, h, big, cap, color=col if col != SAFFRON else RGBColor(0x9A, 0x4D, 0x00))
    text_box(s, MARGIN, Inches(6.45), SLIDE_W - 2 * MARGIN, Inches(0.45), [
        P("The answer key is read only by the eval harness, never by the engine.", 14, color=GREY)], margin=0.02)
    notes(s, "We generate synthetic districts in real government formats with planted problems and a hidden answer key, "
             "then score Kaaran on whether it finds them: 19 of 19 checks on six seeds, about 98 percent recall over 60. "
             "Zero invented numbers is checked by code on every brief. Two multi-agent adversarial reviews found 16 and 23 "
             "issues, all fixed and covered by tests.")


def s07_lowconn(prs):
    s = base_slide(prs, "Works on low-cost phones and patchy networks",
                   "Text first; the AI is optional; everything degrades to a working answer", 7)
    cols = [
        ("Built for low-cost devices", GREEN, GREEN_BG, [
            "WhatsApp text first (fits one 4,096-character message)",
            "One-page PDF brief, readable on a phone",
            "Voice notes for officers who prefer listening",
            "Web page with no external scripts or CDNs",
            "Analysis, alerts, actions need no AI"]),
        ("Needs connectivity", SAFFRON, SAFFRON_BG, [
            "Officer's phone: only to send the question and get the text reply; PDF and voice are extra downloads",
            "Live Claude: new question wordings, new brief wording",
            "Sarvam AI: speech-to-text and voice summary",
            "WhatsApp Cloud API delivery"]),
        ("Degrades gracefully to", NAVY, NAVY_BG, [
            "No Claude: replay cache + rule question reader + template brief (same numbers, actions)",
            "No voice: mic hidden; WhatsApp asks the officer to type",
            "PDF fails: the voice summary is still sent",
            "Spend cap reached: template wording"]),
    ]
    for (x, y, w, h), (head, acc, bg, lines) in zip(grid(3, 1, Inches(1.8), Inches(6.85), gap=Inches(0.25)), cols):
        rect(s, x, y, w, Inches(0.08), acc)
        paras = [P(head, 21, bold=True, color=acc if acc != SAFFRON else RGBColor(0x9A, 0x4D, 0x00))]
        paras += [B(t, 16, space=12) for t in lines]
        text_box(s, x, y + Inches(0.08), w, h - Inches(0.08), paras, fill=bg, margin=0.16)
    notes(s, "Officers use basic Android phones on patchy networks, so the default reply is a short WhatsApp text, then a "
             "one-page PDF and a voice note. On the officer's side only the text exchange needs a network; on the server "
             "side, live Claude, Sarvam voice and WhatsApp delivery do. Without Claude, the rule-based question reader and template brief give the same numbers "
             "and actions, because the analysis never depended on the AI.")


def s08_real(prs):
    s = base_slide(prs, "Real public data: Solapur district, UDISE+ 2024-25",
                   "Aggregates only; self-reported data; raw files never leave the machine or the repo", 8)
    tiles = [
        ("4,698", "schools in 13 blocks validated; 11/11 data checks pass", NAVY),
        ("2,900", "ZP schools · 9,534 teachers · PTR 20.1", NAVY),
        ("99", "single-teacher schools (Sangola 27, Malshiras 20)", SAFFRON),
        ("789", "schools report no cluster (CRC) visit last year; Solapur North 77 of 98 (79%)", SAFFRON),
        ("-8%", "local-body teachers vs 2019-20 (AIKosh cross-check; every block 0.87-0.97)", NAVY),
        ("213", "posts needed by RTE norms: 89 coverable by redeployment, 124 new posts", NAVY),
        ("75 / 64 / 60", "PRS 2024 grade 3 maths: Solapur / Maharashtra / India", GREEN),
        ("18/18", "PAB 2026-27 citations verified: 7 rubric actions linked to funded line items", GREEN),
    ]
    for (x, y, w, h), (big, cap, col) in zip(grid(4, 2, Inches(1.8), Inches(6.3)), tiles):
        kpi(s, x, y, w, h, big, cap, color=col if col != SAFFRON else RGBColor(0x9A, 0x4D, 0x00))
    text_box(s, MARGIN, Inches(6.38), SLIDE_W - 2 * MARGIN, Inches(0.58), [
        P("These are the inputs our rubric uses. Outcomes (assessment, monthly attendance) need state logins, "
          "so they stay synthetic until a pilot.", 14, color=GREY)], margin=0.02)
    notes(s, "To show this is not only a synthetic demo, we ran the real UDISE+ 2024-25 microdata for Solapur through "
             "validation and an aggregate block snapshot: 99 single-teacher schools and 789 schools with no cluster visit "
             "reported. Teacher numbers were cross-checked against 2019-20, PRS 2024 gives the learning benchmark, and "
             "rubric actions cite the Samagra Shiksha PAB 2026-27 line items that already fund them.")


def s09_testing(prs):
    s = base_slide(prs, "User input and testing: what we changed", "Three rounds of feedback, each one changed the product", 9)
    rounds = [
        ("Mentor review", "24 Oct · Central Square Foundation", NAVY, NAVY_BG, [
            "Most officers will never ask first → proactive alerts",
            "Actions were the weak part → decision rubric with constraints",
            "Three-part brief: attention / why / what to do",
            "4 core data domains; baithak (review meeting) loop"]),
        ("Team test", "28 Oct · \"dummy answers\" to everyday questions", SAFFRON, SAFFRON_BG, [
            "PTR, \"how many schools\", \"what should I do\": refused or a generic brief",
            "→ direct answers computed by code, fixed templates",
            "Rule-tier intent accuracy 88% → 96%",
            "Adversarial code review after it: 23 fixes"]),
        ("Product-owner test", "29 Oct · 12 prepared officer questions", GREEN, GREEN_BG, [
            "Short answers: counts in one line; ranking shows only the ranking",
            "Kendra cards for \"which kendras need attention\"",
            "Follow-ups complete a voice or clarified question",
            "Reply in the question's language; 3 questions → 3 answers"]),
    ]
    for (x, y, w, h), (head, when, acc, bg, lines) in zip(grid(3, 1, Inches(1.8), Inches(6.2), gap=Inches(0.25)), rounds):
        rect(s, x, y, w, Inches(0.08), acc)
        ac = acc if acc != SAFFRON else RGBColor(0x9A, 0x4D, 0x00)
        paras = [P(head, 20, bold=True, color=ac), P(when, 14, color=GREY, space=2)]
        paras += [B(t, 16, space=8) for t in lines]
        text_box(s, x, y + Inches(0.08), w, h - Inches(0.08), paras, fill=bg, margin=0.16)
    text_box(s, MARGIN, Inches(6.27), SLIDE_W - 2 * MARGIN, Inches(0.68), [
        P("Each question that gave a long or wrong answer is now a regression test (13 tests, tests/test_officer_questions.py).",
          14, color=GREY),
        P("Not yet done: sessions with serving BEOs and Kendra Pramukhs; they are the first step of the pilot.", 14,
          bold=True, color=NAVY, space=2)],
             margin=0.02)
    notes(s, "Our mentor's review reshaped the product: alerts instead of waiting for questions, a three-part brief, and a "
             "decision rubric for actions. In our own team test everyday questions got 'dummy answers', so we built direct "
             "answers computed by code. Our product owner then asked 12 prepared officer-style questions; the fixes were "
             "shorter answers, kendra cards, follow-ups and replying in the question's language, each locked in by a test. "
             "We have not yet run sessions with serving officers; that is the first step of the pilot. "
             "TODO: add quotes from the team's government-school teacher review of a printed brief if available.")


def s10_innovation(prs):
    s = base_slide(prs, "Innovation: beyond dashboards",
                   "UDISE+ dashboards and Vidya Samiksha Kendras (VSK) show what; Kaaran explains why and what to do", 10)
    rows = [("Capability", "Dashboards (UDISE+, VSK)", "Kaaran"),
            ("Starts without a question", "partly (alerts in some states)", "scans on data arrival, sends an alert"),
            ("Checks data trust first", "no", "rule-based trust checks, reported"),
            ("Explains why", "no", "fixed cause tests; rules causes out"),
            ("Actions with owner and timing", "no", "decision rubric with constraint checks"),
            ("Every number traceable", "partly", "click to file, sheet and rows; verified"),
            ("Marathi, voice, WhatsApp", "rarely", "yes: मराठी प्रथम, voice in and out")]
    top = Inches(1.8)
    widths = [Inches(3.7), Inches(3.6), SLIDE_W - 2 * MARGIN - Inches(7.3)]
    tbl = s.shapes.add_table(len(rows), 3, MARGIN, top, sum(widths, Emu(0)), Inches(0.6) * len(rows)).table
    for c, w in enumerate(widths):
        tbl.columns[c].width = w
    for r, row in enumerate(rows):
        tbl.rows[r].height = Inches(0.6)
        for c, val in enumerate(row):
            cell = tbl.cell(r, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = NAVY if r == 0 else (GREEN_BG if c == 2 else (LIGHT if r % 2 else WHITE))
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = cell.margin_right = Inches(0.1)
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            run = p.add_run()
            run.text = val
            style_run(run, 15, bold=(r == 0 or c == 0), color=WHITE if r == 0 else (GREEN if c == 2 else INK))
    text_box(s, MARGIN, Inches(6.15), SLIDE_W - 2 * MARGIN, Inches(0.75), [
        P("New: differential diagnosis per kendra, positive deviance (a school that improved despite the same gap), "
          "and actions tied to funded PAB line items.", 15, color=NAVY, bold=True)], margin=0.02)
    notes(s, "Dashboards like UDISE+ and the Vidya Samiksha Kendras show what happened; the officer still has to work out why "
             "and what to do. Kaaran checks trust first, tests causes with fixed thresholds, gives each kendra its own "
             "diagnosis and an action with an owner, and speaks Marathi. It is not a chatbot over data: the AI never "
             "chooses a number, a label or an action.")


def s11_roadmap(prs):
    s = base_slide(prs, "Roadmap: one block → district → state", "From hackathon prototype to the state's systems", 11)
    stages = [("Nov-Dec 2026", "Data request / MoU with Solapur ZP for one block; rubric review with DIET/SCERT"),
              ("Jan-Mar 2027", "Pilot, one block: weekly scans on authorised exports, monthly baithak packs, action tracking"),
              ("Apr-Jun 2027", "District rollout; state MIS / VSK as the data source, so alerts start from the system"),
              ("2027-28", "State scale: config packs per state; rubric as a shared state asset; self-hosted Indic models; target cost < ₹500 per block per month")]
    top = Inches(1.8)
    n = len(stages)
    gap = Inches(0.15)
    w = int((SLIDE_W - 2 * MARGIN - gap * (n - 1)) / n)
    for i, (when, what) in enumerate(stages):
        x = MARGIN + i * (w + gap)
        shp = s.shapes.add_shape(MSO_SHAPE.CHEVRON if i else MSO_SHAPE.PENTAGON, x, top, w, Inches(0.55))
        shp.shadow.inherit = False
        shp.fill.solid()
        shp.fill.fore_color.rgb = [SAFFRON, NAVY, RGBColor(0x2A, 0x5A, 0x85), GREEN][i]
        shp.line.fill.background()
        shp.text_frame.word_wrap = False
        p = shp.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = when
        style_run(r, 15, bold=True, color=WHITE)
        text_box(s, x, top + Inches(0.65), w, Inches(1.75), [P(what, 14, color=INK)], fill=LIGHT, margin=0.12)
    y2 = Inches(4.35)
    half = int((SLIDE_W - 2 * MARGIN - Inches(0.3)) / 2)
    text_box(s, MARGIN, y2, half, Inches(2.5), [
        P("Integrations", 18, bold=True, color=NAVY),
        B("UDISE+ microdata (format already supported)", 14, space=6),
        B("Vidya Samiksha Kendra / state MIS exports", 14, space=6),
        B("WhatsApp template messages for weekly alerts", 14, space=6),
        B("Samagra Shiksha PAB line items for actions", 14, space=6),
        B("Config per state: mappings, rubric, texts", 14, space=6)], fill=NAVY_BG, margin=0.16)
    text_box(s, MARGIN + half + Inches(0.3), y2, half, Inches(2.5), [
        P("Pilot success metrics", 18, bold=True, color=GREEN),
        B("New data to usable brief: < 5 minutes", 14, space=6),
        B("Numbers without a source: 0", 14, space=6),
        B("Trust flags confirmed in the field: ≥ 50%", 14, space=6),
        B("Actions judged doable and relevant: ≥ 60%", 14, space=6),
        B("Weekly use without prompting, for 3 months", 14, space=6)],
             fill=GREEN_BG, margin=0.16)
    notes(s, "Next is a data request with the Solapur Zilla Parishad and a rubric review with DIET and SCERT faculty, then a "
             "one-block pilot from January to March 2027 measured on time to answer, flags confirmed in the field and "
             "actions completed. District rollout connects to the state MIS and Vidya Samiksha Kendra so alerts start from "
             "the system, and state scale adds config packs per state and self-hosted Indic models.")


def s12_close(prs):
    s = base_slide(prs, "Try Kaaran", "धन्यवाद · Thank you", 12)
    text_box(s, MARGIN, Inches(1.9), Inches(7.4), Inches(3.4), [
        P([("Demo: ", {"bold": True, "color": NAVY}), ("TODO: public demo link", {"color": SAFFRON, "bold": True})], 22),
        P([("Code: ", {"bold": True, "color": NAVY}), (REPO, {})], 22, space=14),
        P([("Video: ", {"bold": True, "color": NAVY}), ("TODO: YouTube link (3 minutes)", {"color": SAFFRON, "bold": True})],
          22, space=14),
        P("Runs offline in replay mode: rule fallbacks and recorded AI responses, no API key needed.", 16, color=GREY,
          space=18)], margin=0.02)
    x2 = MARGIN + Inches(7.8)
    text_box(s, x2, Inches(1.9), SLIDE_W - MARGIN - x2, Inches(3.4), [
        P("Ask it, for example", 18, bold=True, color=NAVY),
        B("पंढरपूर मध्ये कोणत्या केंद्रांकडे लक्ष द्यावे?", 17, space=8),
        B("Why did maths fall in Pandharpur?", 16, space=8),
        B("Which block has the best maths results?", 16, space=8),
        B("Malshiras cha nikal changla ka aala?", 16, space=8)], fill=LIGHT, margin=0.18)
    text_box(s, MARGIN, Inches(5.7), SLIDE_W - 2 * MARGIN, Inches(1.1), [
        P("Kaaran: from data to action, in Marathi, with evidence.", 26, bold=True, color=NAVY, align=PP_ALIGN.CENTER),
        P("Demo data is SYNTHETIC and marked so; real public data is UDISE+ 2024-25 (aggregates only).", 14, color=GREY,
          align=PP_ALIGN.CENTER, space=6)], margin=0.02)
    notes(s, "The demo link and the source code are open for judges; the repository shows exactly where the AI is used and "
             "how every number is computed. The example questions work in the offline replay mode. "
             "Kaaran turns education data into a specific, trusted, doable action, in Marathi, with evidence.")


# ---------------------------------------------------------------- overflow check

def _char_w(ch: str) -> float:
    """Average advance width in em (rough, Segoe UI / Nirmala UI)."""
    if "ऀ" <= ch <= "ॿ":
        return 0.55 if not ("ा" <= ch <= "्") else 0.15  # vowel signs mostly combine
    if ch in " .,;:'!|i1l()-·":
        return 0.3
    if ch.isupper() or ch in "mwMW%@":
        return 0.68
    return 0.53


def estimate_height(tf, width_emu) -> float:
    """Estimated text height in points for a text frame of the given inner width."""
    total = 0.0
    width_pt = width_emu / 12700
    for i, p in enumerate(tf.paragraphs):
        runs = list(p.runs)
        if not runs:
            continue
        size = max((r.font.size.pt if r.font.size else 18) for r in runs)
        ppr = p._p.pPr
        indent = (int(ppr.get("marL", 0)) / 12700) if ppr is not None else 0
        avail = max(width_pt - indent, 10)
        # word wrap
        lines, cur = 1, 0.0
        for r in runs:
            rs = r.font.size.pt if r.font.size else size
            for word in r.text.split(" "):
                ww = sum(_char_w(c) for c in word + " ") * rs * (1.06 if r.font.bold else 1.0)
                if cur + ww > avail and cur > 0:
                    lines += 1
                    cur = ww
                else:
                    cur += ww
        total += lines * size * 1.2 * 1.05
        if i and p.space_before is not None:
            total += p.space_before.pt
    return total


def check_fit(path: Path) -> list[str]:
    prs = Presentation(str(path))
    problems = []
    for n, slide in enumerate(prs.slides, 1):
        for shp in slide.shapes:
            frames = []
            if shp.has_text_frame and shp.text_frame.text.strip():
                frames.append((shp.text_frame, shp.width, shp.height, shp.text_frame))
            if shp.has_table:
                tbl = shp.table
                for r_i, row in enumerate(tbl.rows):
                    for c_i, cell in enumerate(row.cells):
                        frames.append((cell.text_frame, tbl.columns[c_i].width, row.height, cell))
            for tf, w, h, owner in frames:
                ml = (owner.margin_left or Inches(0.1)) + (owner.margin_right or Inches(0.1))
                mt = (owner.margin_top or Inches(0.05)) + (owner.margin_bottom or Inches(0.05))
                need = estimate_height(tf, w - ml)
                have = (h - mt) / 12700
                if need > have * 1.0:
                    problems.append(f"slide {n}: '{tf.text[:50]}' needs ~{need:.0f}pt, box {have:.0f}pt")
            if shp.left + shp.width > SLIDE_W + 10 or shp.top + shp.height > SLIDE_H + 10:
                problems.append(f"slide {n}: shape '{shp.name}' extends past the slide edge")
    return problems


# ---------------------------------------------------------------- main

def build(out: Path, tests_total: str, tests_fast: str) -> None:
    prs = Presentation()
    prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H
    s01_title(prs)
    s02_problem(prs)
    s03_what(prs)
    s04_layers(prs)
    s05_guardrails(prs)
    s06_eval(prs, tests_total, tests_fast)
    s07_lowconn(prs)
    s08_real(prs)
    s09_testing(prs)
    s10_innovation(prs)
    s11_roadmap(prs)
    s12_close(prs)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--tests-total", default="289", help="from: pytest --co -q (289 collected on 2026-10-29)")
    ap.add_argument("--tests-fast", default="246", help="from: pytest -m 'not slow' --co -q")
    ap.add_argument("--check-only", action="store_true")
    a = ap.parse_args(argv)
    if not a.check_only:
        build(a.out, a.tests_total, a.tests_fast)
        print(f"wrote {a.out}")
    problems = check_fit(a.out)
    for p in problems:
        print("OVERFLOW?", p)
    print(f"fit check: {len(problems)} possible overflow(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
