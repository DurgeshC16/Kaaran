"""Three-part block brief (A what needs attention / B why / C what to do): Markdown, interactive HTML, print HTML,
and the LLM writer with the same placeholders, verifier, retry and template fallback as v1.
"""

from __future__ import annotations

import html
import re

from ..brief import texts as X
from ..brief.html import _caveats_html, fill_html, LABEL_CLASS, PRINT_CSS
from ..brief.render import caveat_lines, fill
from ..brief.texts_block import BLOCK_HEADINGS, BLOCK_SECTIONS, BLOCK_TITLE
from ..brief.writer import SYSTEM, Brief, write_brief

BLOCK_SYSTEM = SYSTEM + """

This brief is about CLUSTERS (केंद्र) inside one block (तालुका) and the actions the officer can take. A cluster \
placeholder {{e:C...}} gives only the cluster's name: in Marathi always add the word "केंद्र" after it with the case \
ending on that word, for example "{{e:C08K03}} केंद्रातील", "{{e:C08K03}} केंद्रात", "{{e:C08K03}} केंद्राचा". \
For ACTION findings write one clear instruction (what to do, where), not a description; never name a school."""

LABEL_CLASS.update({"STRONG": "strong", "WEAK": "weak"})
RISK_CLASS = {"STRONG": "redflag", "WEAK": "weak"}
SECTION_REQUIRED = {s: BLOCK_HEADINGS[s] for s in BLOCK_SECTIONS}


def _badge(f: dict, i: int) -> str:
    return X.BADGES[(f["type"], f["label"])][i]


def _focus_name(pack: dict, lang: str) -> str:
    e = pack["entities"][pack["scope"]["focus"]]
    return (e.get("name_mr") or e["name_en"]) if lang == "mr" else e["name_en"]


def _owner(f: dict, i: int) -> str:
    act = f["action"]
    owner = X.ACTORS[act["actor_role"]][i]
    when = X.HORIZONS.get(act.get("horizon"), ("", ""))[i]
    return owner + (f", {when}" if when else "")


def render_block_markdown(pack: dict, prose: dict[str, dict], lang: str, sources: dict[str, str] | None = None) -> str:
    i = 0 if lang == "mr" else 1
    findings = {f["id"]: f for f in pack["findings"]}
    lines = [f"# {BLOCK_TITLE[i]}: {_focus_name(pack, lang)}", ""]
    if pack.get("synthetic"):
        lines += [f"> **{X.BANNER[i]}**", ""]
    outline = {o["section"]: o["finding_ids"] for o in pack["outline"]}
    for name in list(BLOCK_SECTIONS) + ["appendix"]:
        ids = outline.get(name, [])
        if not ids and name == "appendix":
            continue
        lines += [f"## {BLOCK_HEADINGS[name][i]}", ""]
        if not ids:
            lines += [X.NOT_APPLICABLE[i], ""]
        for n, fid in enumerate(ids, start=1):
            f = findings[fid]
            text = fill(prose[fid][lang], pack, lang)
            if f["type"] == "ACTION":
                lines.append(f"{n}. {text} — *{_owner(f, i)}*")
            else:
                lines.append(f"- **[{_badge(f, i)}]** {text}")
                for c in caveat_lines(f, pack, lang):
                    lines.append(f"  - *{'टीप' if lang == 'mr' else 'Note'}: {c}*")
        lines.append("")
    used_llm = any(str(v).startswith("llm") for v in (sources or {}).values())
    foot = ("सर्व आकडे कोडने मोजले आहेत; प्रत्येक आकड्याचा स्रोत पुरावा पॅकमध्ये आहे. कृती ठरावीक निर्णय-तक्त्यातून सुचवल्या आहेत."
            if lang == "mr" else
            "All figures are computed by code; each figure's source is in the evidence pack. Actions come from a fixed decision rubric.")
    how = ("मजकूर: AI लेखक + कोड तपासणी" if used_llm else "मजकूर: ठरावीक साचे") if lang == "mr" else \
          ("Wording: AI writer + code checks" if used_llm else "Wording: fixed templates")
    lines += ["---", f"*{foot} {how}.*", ""]
    return "\n".join(lines)


def block_fragment(pack: dict, prose: dict[str, dict], lang: str, sources: dict[str, str] | None = None,
                   interactive: bool = True, include_appendix: bool = True) -> str:
    i = 0 if lang == "mr" else 1
    findings = {f["id"]: f for f in pack["findings"]}
    parts = [f'<div class="brief block-brief" lang="{lang}">',
             f'<h2 class="brief-title">{html.escape(BLOCK_TITLE[i])}: {html.escape(_focus_name(pack, lang))}</h2>']
    if pack.get("synthetic"):
        parts.append(f'<div class="banner">{html.escape(X.BANNER[i])}</div>')
    outline = {o["section"]: o["finding_ids"] for o in pack["outline"]}
    letters = {"attention": "A", "why": "B", "action": "C", "appendix": ""}
    for name in list(BLOCK_SECTIONS) + (["appendix"] if include_appendix else []):
        ids = outline.get(name, [])
        if not ids and name == "appendix":
            continue
        head = (letters[name] + " · " if letters[name] else "") + BLOCK_HEADINGS[name][i]
        parts.append(f'<section class="sec-{name}"><h3>{html.escape(head)}</h3>')
        if name == "action":
            parts.append('<ol class="actions">')
        for fid in ids:
            f = findings[fid]
            text = fill_html(prose[fid][lang], pack, lang, interactive)
            if f["type"] == "ACTION":
                parts.append(f'<li>{text} <span class="owner">— {html.escape(_owner(f, i))}</span></li>')
            else:
                cls = RISK_CLASS.get(f["label"], "") if f["type"] == "RISK" else LABEL_CLASS.get(f["label"], "")
                badge = f'<span class="badge {cls}">{html.escape(_badge(f, i))}</span>'
                parts.append(f'<div class="finding">{badge} <span class="text">{text}</span>{_caveats_html(f, pack, lang)}</div>')
        if not ids:
            parts.append(f'<p class="na">{html.escape(X.NOT_APPLICABLE[i])}</p>')
        if name == "action":
            parts.append("</ol>")
        parts.append("</section>")
    used_llm = any(str(v).startswith("llm") for v in (sources or {}).values())
    if lang == "mr":
        foot = "सर्व आकडे कोडने मोजले आहेत; कृती ठरावीक निर्णय-तक्त्यातून. " + ("मजकूर: AI लेखक + कोड तपासणी." if used_llm else "मजकूर: ठरावीक साचे.")
    else:
        foot = "All figures computed by code; actions from a fixed decision rubric. " + ("Wording: AI writer + code checks." if used_llm else "Wording: fixed templates.")
    parts.append(f'<div class="footer">{html.escape(foot)}</div></div>')
    return "\n".join(parts)


def block_print_document(pack: dict, prose: dict[str, dict], lang: str, sources: dict[str, str] | None = None) -> str:
    body = block_fragment(pack, prose, lang, sources, interactive=False, include_appendix=False)
    title = re.sub(r"<[^>]+>", "", body.split("</h2>")[0])
    css = PRINT_CSS + "ol.actions { margin: 2px 0; padding-left: 18px; } ol.actions li { margin: 2px 0; }\n"
    return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
            f"<style>{css}</style></head><body>{body}</body></html>")


def write_block_brief(pack: dict, use_llm: bool = True, client=None, tier: str = "main") -> Brief:
    """LLM wording where it passes the verifier; templates elsewhere. Tier "main": the light model ran past its output
    limit on this ~25-finding JSON in testing (2026-10-27); one brief per block per data refresh costs about $0.08."""
    return write_brief(pack, use_llm=use_llm, client=client, system=BLOCK_SYSTEM, tier=tier,
                       render=render_block_markdown, sections=SECTION_REQUIRED)
