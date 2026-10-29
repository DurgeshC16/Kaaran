"""Spoken summary script (about one minute) built by code from the verified three-part summary.

No new facts and no new numbers: every sentence is taken from the summary items (already filled by code and
checked by the verifier). Only speech-friendly clean-up happens here: brackets dropped, "%" spoken as a word,
symbols removed, and the text cut to fit about a minute of speech.
"""

from __future__ import annotations

import re

MAX_CHARS = {"mr": 900, "en": 900}  # roughly 55-65 seconds of speech at a normal pace
INTRO = ("कारण कडून {title}. ही कृत्रिम डेमो माहिती आहे.", "From Kaaran: {title}. This is synthetic demo data.")
OUTRO = ("पूर्ण एक पानी अहवाल आणि प्रत्येक आकड्याचा स्रोत PDF मध्ये आहे.",
         "The full one-page brief, with the source of every number, is in the PDF.")
# (section, spoken heading mr/en) in speaking order, per lens
BLOCK_PLAN = (("attention", ("लक्ष देण्याची गरज.", "What needs attention.")),
              ("why", ("असे का होत असावे.", "Why it may be happening.")),
              ("action", ("काय करावे.", "What to do.")))
TALUKA_PLAN = (("trend", ("कल.", "Trend.")),
               ("main_cause", ("संभाव्य मुख्य कारण.", "Probable main cause.")),
               ("election_check", ("निवडणूक कारण तपासले.", "Election-duty check.")),
               ("data_warning", ("डेटा इशारा.", "Data warning.")),
               ("action", ("सुचवलेली कृती.", "Suggested action.")))
OPTIONAL_SECTIONS = {"election_check"}  # dropped first when the script would run over a minute
WARNING_LABELS = {"RED_FLAG", "INSUFFICIENT"}  # data warnings are always spoken, never trimmed
LABELLED_TYPES = {"CAUSE", "TREND"}  # the rule-based confidence label is spoken with these lines


def speakable(text: str, lang: str) -> str:
    """Make a written sentence easy to speak: drop brackets, spell %, remove markdown symbols."""
    t = re.sub(r"\([^)]*\)", "", text)  # periods, codes and asides in brackets are for reading, not listening
    t = t.replace("%", " टक्के" if lang == "mr" else " percent")
    t = re.sub(r"[*_#>|•]", " ", t)
    t = t.replace("—", ",").replace(" - ", ", ")
    t = re.sub(r"\s+", " ", t)
    return re.sub(r"\s+([.,।])", r"\1", t).strip(" ,")


def _line(item: dict, lang: str) -> str:
    text = speakable(item["text"], lang)
    if item.get("type") in LABELLED_TYPES and item.get("badge"):
        text = f"{item['badge']}: {text}"  # rule-based label (STRONG / WEAK / ...) spoken, never decided here
    return text if text.endswith((".", "।")) else text + "."


def spoken_summary(summary: dict, lang: str) -> str:
    """Script for the voice note from Answer.summary[lang] (block or taluka lens).

    Lens is chosen from the sections present. Each part gets its top lines (2, then 1 if too long); data warnings
    (RED_FLAG / INSUFFICIENT) are always kept; "what to do" is never dropped; confidence labels are spoken.
    """
    i = 0 if lang == "mr" else 1
    title = summary.get("title", "")
    intro = INTRO[i].format(title=title) if summary.get("banner") else title + "."
    if any(it["section"] == "answer" or it["section"].startswith("card:") for it in summary.get("items", [])):
        return _answer_script(summary, lang, intro)
    by_section: dict[str, list] = {}
    for it in summary.get("items", []):
        by_section.setdefault(it["section"], []).append(it)
    plan = BLOCK_PLAN if ("attention" in by_section or "why" in by_section) else TALUKA_PLAN
    plan = [(s, h[i]) for s, h in plan if s in by_section]

    def build(per_part: int, optional: bool = True) -> str:
        body = []
        for section, heading in plan:
            if not optional and section in OPTIONAL_SECTIONS:
                continue
            items = by_section[section]
            keep = items[:per_part] + [it for it in items[per_part:] if it.get("label") in WARNING_LABELS]
            body.append(heading + " " + " ".join(_line(it, lang) for it in keep))
        return " ".join([intro] + body + [OUTRO[i]])

    for per_part, optional in ((2, True), (1, True), (1, False)):
        text = build(per_part, optional)
        if len(text) <= MAX_CHARS[lang]:
            return text
    return text  # one line per part (plus warnings and actions) is the floor


TODO_WORD = ("काय करावे", "What to do")
OUTRO_ANSWER = ("पूर्ण पुरावा अहवाल आणि प्रत्येक आकड्याचा स्रोत उपलब्ध आहे.", "The full evidence brief, with the source of every figure, is available.")


def _answer_script(summary: dict, lang: str, intro: str) -> str:
    """Block lens v2 summaries: the direct answer, then one short spoken card per kendra (what, why, what to do)."""
    i = 0 if lang == "mr" else 1
    answer = [_line(it, lang) for it in summary["items"] if it["section"] == "answer"]
    cards: dict[str, list] = {}
    for it in summary["items"]:
        if it["section"].startswith("card:"):
            cards.setdefault(it["section"], []).append(it)

    def card(items: list[dict]) -> str:
        what = next((it for it in items if it["type"] in ("RISK", "DATA")), None)
        why = (next((it for it in items if it["type"] == "TWIN"), None) if summary.get("mode") == "twin" else None) or next(
            (it for it in items if it["type"] == "CAUSE" and it.get("label") != "RULED_OUT"), None) or next(
            (it for it in items if it["type"] in ("TWIN", "CAUSE")), None)
        todo = next((it for it in items if it["type"] == "ACTION"), None)
        parts = [items[0]["heading"] + "."]
        parts += [_line(x, lang) for x in (what, why) if x]
        if todo:
            parts.append(f"{TODO_WORD[i]}: {speakable(todo['text'], lang).rstrip('.')}, {speakable(todo['owner'], lang).rstrip('.')}.")
        return " ".join(parts)

    spoken = [card(v) for v in cards.values()]
    for n in range(len(spoken), 0, -1):  # as many cards as fit in about a minute (at least one)
        text = " ".join([intro] + answer + spoken[:n] + [OUTRO_ANSWER[i]])
        if len(text) <= MAX_CHARS[lang] or n == 1:
            return text
    return " ".join([intro] + answer + [OUTRO_ANSWER[i]])
