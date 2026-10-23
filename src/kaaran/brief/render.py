"""Placeholder filling and Markdown rendering. Every number, name and period in a brief comes from here.

Placeholders: {{n:<number id>}} display string; {{e:<entity id>}} name; {{s:<set id>}} set size;
{{p:<period id>}} period text; {{t:<text key>}} fixed wording. Templates use [[param]] and are expanded first.
"""

from __future__ import annotations

import re

from ..evidence import format_number
from . import texts as X

PLACEHOLDER = re.compile(r"\{\{([nespt]):([^{}]+?)\}\}")
TEMPLATE_PARAM = re.compile(r"\[\[([a-z_]+)\]\]")
KIND_CODE = {"number": "n", "entity": "e", "set": "s", "period": "p", "text_key": "t"}
MR_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")


class FillError(ValueError):
    pass


def expand_template(text: str, params: dict) -> str:
    def sub(m):
        ref = params.get(m.group(1))
        if ref is None:
            raise FillError(f"template param {m.group(1)!r} missing")
        kind, value = next(iter(ref.items()))
        return "{{" + KIND_CODE[kind] + ":" + str(value) + "}}"
    return TEMPLATE_PARAM.sub(sub, text)


def template_text(finding: dict, lang: str) -> str:
    i = 0 if lang == "mr" else 1
    text = expand_template(X.TEMPLATES[finding["template_key"]][i], finding["params"])
    if finding["template_key"] == "twin.learn_from" and "decoy" in finding["params"]:
        text += " " + expand_template(X.TEMPLATES["twin.decoy"][i], finding["params"])
    return text


def period_text(per: dict, lang: str) -> str:
    def month(m):
        y, mm = m.split("-")
        name = (X.MONTHS_MR if lang == "mr" else X.MONTHS_EN)[int(mm)]
        return name, y
    if per["kind"] == "month_range":
        (m1, y1), (m2, y2) = month(per["from"]), month(per["to"])
        joiner = " ते " if lang == "mr" else " to "
        text = f"{m1}{joiner}{m2} {y2}" if y1 == y2 else f"{m1} {y1}{joiner}{m2} {y2}"
    elif per["kind"] == "month":
        m, y = month(per["from"])
        text = f"{m} {y}"
    elif per["from"] == per["to"]:
        text = per["from"]
    else:
        text = f"{per['from']}{' ते ' if lang == 'mr' else ' to '}{per['to']}"
    return text.translate(MR_DIGITS) if lang == "mr" else text


# Marathi postpositions written after a name placeholder are joined to the name ("{{e:T08}} चा" -> "पंढरपूरचा").
# Only endings that attach without changing the name's stem; others ("त", "तील") need a native form, so the writer
# is told to put them on the word "तालुका" instead.
MR_SUFFIXES = ("च्या", "चा", "ची", "चे", "ला", "ने", "मध्ये", "मधील", "कडे", "कडून", "पेक्षा", "साठी", "सारखा", "सारखी",
               "सारखे")
MR_JOIN = re.compile(r"(\{\{e:[^{}]+\}\})\s+(" + "|".join(MR_SUFFIXES) + r")(?=[\s,.;:!?)\]]|$)")


def fill(text: str, pack: dict, lang: str) -> str:
    if lang == "mr":
        text = MR_JOIN.sub(lambda m: m.group(1) + m.group(2), text)

    def sub(m):
        kind, ref = m.group(1), m.group(2).strip()
        if kind == "n":
            n = pack["numbers"].get(ref)
            if n is None:
                raise FillError(f"unknown number {ref!r}")
            return n["display"]["mr" if lang == "mr" else "en"]
        if kind == "e":
            e = pack["entities"].get(ref)
            if e is None:
                raise FillError(f"unknown entity {ref!r}")
            return (e.get("name_mr") or e["name_en"]) if lang == "mr" else e["name_en"]
        if kind == "s":
            s = pack["entity_sets"].get(ref)
            if s is None:
                raise FillError(f"unknown set {ref!r}")
            size = s["size"] if "size" in s else len(s["members"])
            return format_number(size, "count", 0)["mr" if lang == "mr" else "en"]
        if kind == "p":
            per = pack["periods"].get(ref)
            if per is None:
                raise FillError(f"unknown period {ref!r}")
            return period_text(per, lang)
        if ref not in X.TEXT_KEYS:
            raise FillError(f"unknown text key {ref!r}")
        return X.TEXT_KEYS[ref][0 if lang == "mr" else 1]
    return PLACEHOLDER.sub(sub, text)


def allowed_refs(finding: dict, pack: dict) -> dict[str, set]:
    """Placeholders a finding may use: its params, caveat params, criteria numbers (+ derivation inputs) and scope."""
    refs = {"n": set(), "e": set(), "s": set(), "p": set(), "t": set()}

    def add(params):
        for ref in params.values():
            kind, value = next(iter(ref.items()))
            refs[{"number": "n", "entity": "e", "set": "s", "period": "p", "text_key": "t"}[kind]].add(value)
    add(finding.get("params", {}))
    for c in finding.get("caveats", []):
        add(c.get("params", {}))
    for c in finding.get("criteria", []):
        if c.get("number"):
            refs["n"].add(c["number"])
    for nid in list(refs["n"]):
        refs["n"] |= set(pack["numbers"].get(nid, {}).get("derivation", {}).get("inputs", []))
    refs["e"].add(pack["scope"]["focus"])
    if pack["scope"].get("period"):
        refs["p"].add(pack["scope"]["period"])
    return refs



def caveat_lines(finding: dict, pack: dict, lang: str) -> list[str]:
    out = []
    for c in finding.get("caveats", []):
        key = c["template_key"]
        if key in X.SKIP_CAVEATS or key not in X.CAVEATS:
            continue
        text = expand_template(X.CAVEATS[key][0 if lang == "mr" else 1], c.get("params", {}))
        out.append(fill(text, pack, lang))
    return out


def render_markdown(pack: dict, prose: dict[str, dict], lang: str, sources: dict[str, str] | None = None) -> str:
    i = 0 if lang == "mr" else 1
    findings = {f["id"]: f for f in pack["findings"]}
    focus = pack["entities"][pack["scope"]["focus"]]
    focus_name = (focus.get("name_mr") or focus["name_en"]) if lang == "mr" else focus["name_en"]
    lines = [f"# {X.TITLE[i]}: {focus_name}", ""]
    if pack.get("synthetic"):
        lines += [f"> **{X.BANNER[i]}**", ""]
    q = X.QUESTION.get(pack["scope"].get("question"))
    if q:
        lines += [f"**{'प्रश्न' if lang == 'mr' else 'Question'}:** {q[i].format(taluka=focus_name)}", ""]
    outline = {o["section"]: o["finding_ids"] for o in pack["outline"]}
    for name in list(X.REQUIRED_SECTIONS) + ["appendix"]:
        if name not in outline:
            if name in X.REQUIRED_SECTIONS:  # every required section appears, even without a finding
                lines += [f"## {X.SECTION_HEADINGS[name][i]}", "", X.NOT_APPLICABLE[i], ""]
            continue
        section = {"section": name, "finding_ids": outline[name]}
        lines += [f"## {X.SECTION_HEADINGS[section['section']][i]}", ""]
        for fid in section["finding_ids"]:
            f = findings[fid]
            badge = X.BADGES[(f["type"], f["label"])][i]
            text = fill(prose[fid][lang], pack, lang)
            if f["type"] == "ACTION":
                act = f["action"]
                owner = X.ACTORS[act["actor_role"]][i]
                when = X.HORIZONS.get(act.get("horizon"), ("", ""))[i]
                lines.append(f"- **[{badge}]** {text} — *{owner}{', ' + when if when else ''}*")
            else:
                lines.append(f"**[{badge}]** {text}")
                for c in caveat_lines(f, pack, lang):
                    lines.append(f"  - *{'टीप' if lang == 'mr' else 'Note'}: {c}*")
            lines.append("")
    footer_mr = "सर्व आकडे कोडने मोजले आहेत; प्रत्येक आकड्याचा स्रोत (फाईल, शीट/पान, ओळ) पुरावा पॅकमध्ये आहे."
    footer_en = "All figures are computed by code; each figure's source (file, sheet/page, row) is in the evidence pack."
    src = sources or {}
    used_llm = any(v.startswith("llm") for v in src.values())
    how = ("मजकूर: AI लेखक + कोड तपासणी" if used_llm else "मजकूर: ठरावीक साचे") if lang == "mr" else \
          ("Wording: AI writer + code checks" if used_llm else "Wording: fixed templates")
    lines += ["---", f"*{footer_mr if lang == 'mr' else footer_en} {how}.*", ""]
    return "\n".join(lines)
