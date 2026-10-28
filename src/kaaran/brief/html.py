"""HTML rendering of a brief: an interactive fragment for the web page and a print document for the PDF.

Same rules as the Markdown renderer: every figure, name and period is filled in by code; all other text
(including LLM prose) is HTML-escaped. Numbers become <span class="num" data-n="..."> (click = source) and
set sizes <span class="set" data-s="..."> (click = school list) in the interactive version.
"""

from __future__ import annotations

import html
import re

from ..evidence import format_number
from . import texts as X
from .render import MR_JOIN, PLACEHOLDER, caveat_lines, period_text, tidy

LABEL_CLASS = {"STRONG": "strong", "WEAK": "weak", "INSUFFICIENT": "insufficient", "RED_FLAG": "redflag",
               "LEARN_FROM": "learn", "RULED_OUT": "ruledout", "CLEARED": "cleared", "ACTION": "action"}


def fill_html(text: str, pack: dict, lang: str, interactive: bool = True) -> str:
    if lang == "mr":
        text = MR_JOIN.sub(lambda m: m.group(1) + m.group(2), text)
    out, pos = [], 0
    for m in PLACEHOLDER.finditer(text):
        out.append(html.escape(text[pos:m.start()]))
        kind, ref = m.group(1), m.group(2).strip()
        if kind == "n":
            shown = html.escape(pack["numbers"][ref]["display"]["mr" if lang == "mr" else "en"])
            out.append(f'<span class="num" data-n="{html.escape(ref)}">{shown}</span>' if interactive else f"<b>{shown}</b>")
        elif kind == "e":
            e = pack["entities"][ref]
            out.append(html.escape((e.get("name_mr") or e["name_en"]) if lang == "mr" else e["name_en"]))
        elif kind == "s":
            s = pack["entity_sets"][ref]
            size = html.escape(format_number(len(s["members"]), "count", 0)["mr" if lang == "mr" else "en"])
            out.append(f'<span class="set" data-s="{html.escape(ref)}">{size}</span>' if interactive else f"<b>{size}</b>")
        elif kind == "p":
            out.append(html.escape(period_text(pack["periods"][ref], lang)))
        else:
            out.append(html.escape(X.TEXT_KEYS[ref][0 if lang == "mr" else 1]))
        pos = m.end()
    out.append(html.escape(text[pos:]))
    return tidy("".join(out))


def _caveats_html(f: dict, pack: dict, lang: str) -> str:
    notes = caveat_lines(f, pack, lang)
    if not notes:
        return ""
    label = "टीप" if lang == "mr" else "Note"
    return "".join(f'<div class="caveat">{label}: {html.escape(n)}</div>' for n in notes)


def brief_fragment(pack: dict, prose: dict[str, dict], lang: str, sources: dict[str, str] | None = None,
                   question: str | None = None, interactive: bool = True) -> str:
    i = 0 if lang == "mr" else 1
    findings = {f["id"]: f for f in pack["findings"]}
    focus = pack["entities"][pack["scope"]["focus"]]
    focus_name = (focus.get("name_mr") or focus["name_en"]) if lang == "mr" else focus["name_en"]
    parts = [f'<div class="brief" lang="{lang}">', f'<h2 class="brief-title">{html.escape(X.TITLE[i])}: {html.escape(focus_name)}</h2>']
    if pack.get("synthetic"):
        parts.append(f'<div class="banner">{html.escape(X.BANNER[i])}</div>')
    if question:
        parts.append(f'<div class="question"><b>{"प्रश्न" if lang == "mr" else "Question"}:</b> {html.escape(question)}</div>')
    outline = {o["section"]: o["finding_ids"] for o in pack["outline"]}
    for name in list(X.REQUIRED_SECTIONS) + ["appendix"]:
        if name not in outline:
            if name in X.REQUIRED_SECTIONS:
                parts.append(f'<section><h3>{html.escape(X.SECTION_HEADINGS[name][i])}</h3><p class="na">{html.escape(X.NOT_APPLICABLE[i])}</p></section>')
            continue
        parts.append(f'<section class="sec-{name}"><h3>{html.escape(X.SECTION_HEADINGS[name][i])}</h3>')
        if name == "action":
            parts.append("<ul class=\"actions\">")
        for fid in outline[name]:
            f = findings[fid]
            badge = f'<span class="badge {LABEL_CLASS[f["label"]]}">{html.escape(X.BADGES[(f["type"], f["label"])][i])}</span>'
            text = fill_html(prose[fid][lang], pack, lang, interactive)
            if f["type"] == "ACTION":
                act = f["action"]
                owner = html.escape(X.ACTORS[act["actor_role"]][i])
                when = html.escape(X.HORIZONS.get(act.get("horizon"), ("", ""))[i])
                parts.append(f'<li>{badge} {text} <span class="owner">— {owner}{", " + when if when else ""}</span></li>')
            else:
                parts.append(f'<div class="finding">{badge} <span class="text">{text}</span>{_caveats_html(f, pack, lang)}</div>')
        if name == "action":
            parts.append("</ul>")
        parts.append("</section>")
    used_llm = any(str(v).startswith("llm") for v in (sources or {}).values())
    if lang == "mr":
        how = "मजकूर: AI लेखक + कोड तपासणी" if used_llm else "मजकूर: ठरावीक साचे"
        foot = "सर्व आकडे कोडने मोजले आहेत; प्रत्येक आकड्याचा स्रोत पुरावा पॅकमध्ये आहे."
    else:
        how = "Wording: AI writer + code checks" if used_llm else "Wording: fixed templates"
        foot = "All figures are computed by code; each figure's source is in the evidence pack."
    parts.append(f'<div class="footer">{html.escape(foot)} {html.escape(how)}.</div></div>')
    return "\n".join(parts)


PRINT_CSS = """
@page { size: A4; margin: 11mm 12mm; }
body { font-family: "Noto Sans Devanagari", "Nirmala UI", "Mangal", "Segoe UI", sans-serif; font-size: 9.6pt; line-height: 1.38; color: #111; margin: 0; }
.brief-title { font-size: 14pt; margin: 0 0 4px; }
.banner { background: #fff3cd; border: 1px solid #e0b100; padding: 3px 7px; font-weight: 600; font-size: 8.8pt; margin-bottom: 4px; }
.question { margin: 3px 0 2px; }
section { margin-top: 5px; page-break-inside: avoid; }
h3 { font-size: 10.6pt; margin: 6px 0 2px; border-bottom: 1px solid #ccc; padding-bottom: 1px; }
.finding { margin: 2px 0 3px; }
.caveat { font-size: 8.2pt; color: #555; margin-left: 12px; font-style: italic; }
.badge { display: inline-block; font-size: 7.8pt; font-weight: 700; padding: 0 5px; border-radius: 3px; border: 1px solid; margin-right: 3px; }
.strong { color: #0b6e4f; border-color: #0b6e4f; } .weak { color: #a15c00; border-color: #a15c00; }
.insufficient { color: #555; border-color: #777; } .redflag { color: #b00020; border-color: #b00020; }
.learn { color: #0b57d0; border-color: #0b57d0; } .ruledout { color: #44546a; border-color: #44546a; }
.cleared { color: #2e7d32; border-color: #2e7d32; } .action { color: #6a1b9a; border-color: #6a1b9a; }
ul.actions { margin: 2px 0; padding-left: 16px; } ul.actions li { margin: 2px 0; }
.owner { color: #333; font-style: italic; }
.na { color: #666; margin: 2px 0; }
.footer { margin-top: 6px; font-size: 7.8pt; color: #555; border-top: 1px solid #ccc; padding-top: 3px; }
"""


def print_document(pack: dict, prose: dict[str, dict], lang: str, sources: dict[str, str] | None = None,
                   question: str | None = None) -> str:
    body = brief_fragment(pack, prose, lang, sources, question, interactive=False)
    title = re.sub(r"<[^>]+>", "", body.split("</h2>")[0])
    return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
            f"<style>{PRINT_CSS}</style></head><body>{body}</body></html>")
