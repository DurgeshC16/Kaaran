"""Officer-facing answer views (block lens): a short answer card first, kendra cards for "what needs attention / why",
and the full evidence brief behind one button.

Everything here is layout. Figures come from placeholders filled by code (render.fill / html.fill_html); the card
texts are the verified brief prose of each finding. Marathi first, English second.
"""

from __future__ import annotations

import html
import re

from ..brief import texts as X
from ..brief.html import fill_html
from ..brief.render import fill

HEAD = {
    "answer": ("थेट उत्तर", "Direct answer"),
    "cards": ("केंद्रनिहाय सारांश", "Cluster by cluster"),
    "what": ("काय झाले", "What happened"),
    "why": ("का", "Why"),
    "todo": ("काय करावे", "What to do"),
    "block": ("संपूर्ण तालुका", "Whole block"),
    "evidence": ("📄 पूर्ण पुरावा अहवाल पहा (प्रत्येक आकड्याचा स्रोत)", "📄 Show the full evidence brief (source of every figure)"),
    "source": ("स्रोत", "Source"),
    "synthetic": ("कृत्रिम डेमो डेटा", "Synthetic demo data"),
    "click": ("निळ्या आकड्यावर क्लिक करा: फाइल, शीट व ओळी दिसतील.", "Click a blue figure to see its file, sheet and rows."),
}
STATUS_CLASS = {("RISK", "STRONG"): "at-risk", ("RISK", "WEAK"): "watch", ("DATA", "RED_FLAG"): "red-flag",
                ("DATA", "INSUFFICIENT"): "no-data"}
LABEL_CLASS = {"STRONG": "strong", "WEAK": "weak", "RULED_OUT": "ruled-out", "LEARN_FROM": "learn", "INSUFFICIENT": "no-data",
               "RED_FLAG": "red-flag", "ACTION": "action"}
FIRST_SENTENCE = re.compile(r"^(.+?[.।])(\s|$)")


def _badge(f: dict, i: int) -> str:
    return X.BADGES[(f["type"], f["label"])][i]


def _owner(f: dict, i: int) -> str:
    act = f["action"]
    when = X.HORIZONS.get(act.get("horizon"), ("", ""))[i]
    return X.ACTORS[act["actor_role"]][i] + (f", {when}" if when else "")


def _cluster_of(f: dict) -> str | None:
    c = f.get("params", {}).get("cluster")
    return c.get("entity") if isinstance(c, dict) else None


def cards(pack: dict, only: set[str] | None = None, kinds: set[str] | None = None) -> list[dict]:
    """Kendra cards from the brief outline: one per cluster in A (what), with its B lines (why) and C lines (what to do).
    A last 'whole block' card holds block-level why/what-to-do lines. `only` keeps those cluster entity ids;
    `kinds` keeps cards whose status finding type is in it (e.g. {"DATA"})."""
    findings = {f["id"]: f for f in pack["findings"]}
    outline = {o["section"]: o["finding_ids"] for o in pack["outline"]}
    out, by_eid = [], {}
    for fid in outline.get("attention", []):
        f = findings[fid]
        eid = _cluster_of(f)
        if eid is None or (only is not None and eid not in only) or (kinds is not None and f["type"] not in kinds):
            continue
        card = {"entity": eid, "status": fid, "why": [], "todo": []}
        by_eid[eid] = card
        out.append(card)
    block = {"entity": None, "status": None, "why": [], "todo": []}
    for sec, key in (("why", "why"), ("action", "todo")):
        for fid in outline.get(sec, []):
            eid = _cluster_of(findings[fid])
            if eid in by_eid:
                by_eid[eid][key].append(fid)
            elif eid is None and only is None and kinds is None:
                block[key].append(fid)
    if block["why"] or block["todo"]:
        out.append(block)
    return out


def _short_html(text: str) -> str:
    """First sentence of filled HTML (cards stay short; the full text is in the evidence brief). Never cuts inside a tag."""
    for m in re.finditer(r"[.।](\s|$)", text):
        head = text[:m.end()].rstrip()
        if head.count("<") == head.count(">") and head.count("<span") == head.count("</span>"):
            return head
    return text


def _short(text: str) -> str:
    m = FIRST_SENTENCE.match(text)
    return m.group(1) if m else text


def card_text(card: dict, pack: dict, prose: dict, lang: str) -> dict:
    """Plain-text card (WhatsApp / voice): name, status badge, what, why lines (with labels), to-do lines (with owners)."""
    i = 0 if lang == "mr" else 1
    findings = {f["id"]: f for f in pack["findings"]}
    ent = pack["entities"].get(card["entity"] or "", {})
    name = ((ent.get("name_mr") or ent.get("name_en", "")) + (" केंद्र" if card["entity"] else "")) if lang == "mr" \
        else ent.get("name_en", "")
    if not card["entity"]:
        name = HEAD["block"][i]
    st = findings.get(card["status"]) if card["status"] else None
    return {
        "name": name,
        "badge": _badge(st, i) if st else "",
        "what": fill(prose[card["status"]][lang], pack, lang) if st else "",
        "why": [(_badge(findings[x], i), _short(fill(prose[x][lang], pack, lang))) for x in card["why"]],
        "todo": [(_short(fill(prose[x][lang], pack, lang)), _owner(findings[x], i)) for x in card["todo"]],
    }


def card_html(card: dict, pack: dict, prose: dict, lang: str) -> str:
    i = 0 if lang == "mr" else 1
    findings = {f["id"]: f for f in pack["findings"]}
    esc = html.escape
    if card["entity"]:
        ent = pack["entities"][card["entity"]]
        name = (ent.get("name_mr") or ent["name_en"]) + " केंद्र" if lang == "mr" else ent["name_en"]
    else:
        name = HEAD["block"][i]
    st = findings.get(card["status"]) if card["status"] else None
    cls = STATUS_CLASS.get((st["type"], st["label"]), "info") if st else "block"
    parts = [f'<article class="kcard kcard-{cls}"><header class="kcard-head"><span class="kcard-name">{esc(name)}</span>']
    if st:
        parts.append(f'<span class="badge b-{cls}">{esc(_badge(st, i))}</span>')
    parts.append("</header><dl class=\"kcard-body\">")
    if st:
        parts.append(f'<dt>{esc(HEAD["what"][i])}</dt><dd>{fill_html(prose[card["status"]][lang], pack, lang)}</dd>')
    if card["why"]:
        rows = "".join(f'<li><span class="badge b-{LABEL_CLASS.get(findings[x]["label"], "info")}">{esc(_badge(findings[x], i))}</span> '
                       f'{_short_html(fill_html(prose[x][lang], pack, lang))}</li>' for x in card["why"])
        parts.append(f'<dt>{esc(HEAD["why"][i])}</dt><dd><ul class="kcard-list">{rows}</ul></dd>')
    if card["todo"]:
        rows = "".join(f'<li>{_short_html(fill_html(prose[x][lang], pack, lang))} <span class="owner">— {esc(_owner(findings[x], i))}</span></li>'
                       for x in card["todo"])
        parts.append(f'<dt>{esc(HEAD["todo"][i])}</dt><dd><ul class="kcard-list todo">{rows}</ul></dd>')
    parts.append("</dl></article>")
    return "".join(parts)


def sources_of(fact_ids: list[str], numbers: dict, files: dict[str, str]) -> list[str]:
    """Distinct source file names behind a set of figures (for the one-line 'Source:' under an answer)."""
    out = []
    for nid in fact_ids:
        for p in numbers.get(nid, {}).get("provenance", []):
            f = files.get(p.get("source", ""))
            if f and f not in out:
                out.append(f)
    return out


def answer_html(mode: str, lines_html: list[str], notes: list[str], source_files: list[str], cards_html: list[str],
                brief_html: str, lang: str, synthetic: bool, evidence_label: str | None = None) -> str:
    """The whole answer: answer card, kendra cards, and the full brief folded behind one button."""
    i = 0 if lang == "mr" else 1
    esc = html.escape
    parts = [f'<div class="kaaran-answer mode-{esc(mode)}" lang="{lang}">']
    if lines_html or notes:
        parts.append('<section class="answer-card">')
        tag = f'<span class="tag-synthetic">{esc(HEAD["synthetic"][i])}</span>' if synthetic else ""
        parts.append(f'<h3 class="answer-head">{esc(HEAD["answer"][i])}{tag}</h3>')
        parts += [f'<p class="answer-line">{t}</p>' for t in lines_html]
        parts += [f'<p class="answer-note">👉 {esc(n)}</p>' for n in notes]
        if source_files:
            parts.append(f'<p class="answer-source">{esc(HEAD["source"][i])}: {esc(", ".join(source_files))} · {esc(HEAD["click"][i])}</p>')
        parts.append("</section>")
    if cards_html:
        parts.append(f'<section class="kendra-cards"><h3 class="cards-head">{esc(HEAD["cards"][i])}</h3>{"".join(cards_html)}</section>')
    parts.append(f'<details class="full-evidence"><summary>{esc(evidence_label or HEAD["evidence"][i])}</summary>{brief_html}</details>')
    parts.append("</div>")
    return "".join(parts)
