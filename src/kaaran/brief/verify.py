"""Deterministic verifier for brief prose (LLM or template). Any problem -> one retry -> template fallback.

Checks per finding and language:
- PLACEHOLDER_UNKNOWN / PLACEHOLDER_NOT_ALLOWED: every placeholder exists and belongs to this finding;
- DIGIT: no digits (Latin or Devanagari) outside placeholders; SPELLED_NUMBER: no figures written as words;
- CAUSAL_WORDING: causal words only for a CAUSE finding with label STRONG (negated sentences such as
  "does not prove a cause" / "सिद्ध होत नाही" are allowed);
- SCHOOL_NAME: no school names (the LLM never sees them, so any would be invented);
- NOT_MARATHI: Marathi text must be mostly Devanagari; EMPTY / TOO_LONG.
Brief level: MISSING_SECTION when a required section heading is absent from the rendered Markdown.
"""

from __future__ import annotations

import re

from . import texts as X
from .render import PLACEHOLDER, allowed_refs

MAX_CHARS = 700
EN_CAUSAL = re.compile(r"\b(caus(e|ed|es|ing)|because of|due to|led to|leads? to|result(s|ed)? (in|from)|as a result of|"
                       r"responsible for|blame[sd]?)\b", re.I)
EN_NEGATION = re.compile(r"\b(not|no|never|cannot|can't|doesn't|does not|did not|didn't|unproven|without)\b", re.I)
MR_CAUSAL = re.compile(r"(\S+मुळे|कारणीभूत|परिणामी|कारण आहे|कारण ठरल\S*|जबाबदार)")
MR_CONNECTIVES = {"त्यामुळे", "यामुळे"}  # "therefore" connectives, not a claim that X caused Y
MR_NEGATION = re.compile(r"(नाही|नाहीत|नसल्याचे|सिद्ध होत नाही|आढळला नाही)")
EN_NUMBER_WORDS = re.compile(r"\b(two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
                             r"seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|"
                             r"thousand|lakh|crore|dozen)\b", re.I)
MR_NUMBER_WORDS = re.compile(r"(?<![ऀ-ॿ])(दोन|तीन|चार|पाच|सहा|सात|आठ|नऊ|दहा|अकरा|बारा|तेरा|चौदा|पंधरा|सोळा|"
                             r"सतरा|अठरा|एकोणीस|वीस|तीस|चाळीस|पन्नास|शंभर|हजार|लाख|कोटी)(?![ऀ-ॿ])")
DIGITS = re.compile(r"[0-9०-९]")
KIND_KEY = {"n": "n", "e": "e", "s": "s", "p": "p", "t": "t"}


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?।])\s+", text) if s.strip()]


def verify_text(text: str, finding: dict, pack: dict, lang: str) -> list[str]:
    problems = []
    if not text or not text.strip():
        return ["EMPTY"]
    if len(text) > MAX_CHARS:
        problems.append("TOO_LONG")
    refs = allowed_refs(finding, pack)
    registry = {"n": pack["numbers"], "e": pack["entities"], "s": pack["entity_sets"], "p": pack["periods"], "t": X.TEXT_KEYS}
    for kind, ref in PLACEHOLDER.findall(text):
        ref = ref.strip()
        if ref not in registry[kind]:
            problems.append(f"PLACEHOLDER_UNKNOWN {{{{{kind}:{ref}}}}}")
        elif kind != "t" and ref not in refs[kind]:
            problems.append(f"PLACEHOLDER_NOT_ALLOWED {{{{{kind}:{ref}}}}}")
    bare = PLACEHOLDER.sub(" ", text)
    if "{{" in bare or "}}" in bare:
        problems.append("PLACEHOLDER_MALFORMED")
    if DIGITS.search(bare):
        problems.append("DIGIT")
    if (EN_NUMBER_WORDS if lang == "en" else MR_NUMBER_WORDS).search(bare):
        problems.append("SPELLED_NUMBER")
    strong_cause = finding["type"] == "CAUSE" and finding["label"] == "STRONG"
    if not strong_cause:
        for s in _sentences(bare):
            if lang == "en":
                if EN_CAUSAL.search(s) and not EN_NEGATION.search(s):
                    problems.append("CAUSAL_WORDING")
                    break
            else:
                hits = [m for m in MR_CAUSAL.findall(s) if m not in MR_CONNECTIVES]
                if hits and not MR_NEGATION.search(s):
                    problems.append("CAUSAL_WORDING")
                    break
    school_names = [e["name_en"] for e in pack["entities"].values() if e["kind"] == "school"]
    if any(n and n in text for n in school_names):
        problems.append("SCHOOL_NAME")
    if lang == "mr":
        letters = [c for c in bare if c.isalpha()]
        latin = sum(1 for c in letters if c.isascii())
        if letters and latin / len(letters) > 0.3:
            problems.append("NOT_MARATHI")
    return problems


def verify_markdown(markdown: str, lang: str, sections: dict | None = None) -> list[str]:
    """`sections`: {section: (mr heading, en heading)} that must appear; default = the v1 required sections."""
    i = 0 if lang == "mr" else 1
    sections = sections or {s: X.SECTION_HEADINGS[s] for s in X.REQUIRED_SECTIONS}
    return [f"MISSING_SECTION {s}" for s, h in sections.items() if f"## {h[i]}" not in markdown]


def verify_brief(prose: dict[str, dict], markdown: dict[str, str], pack: dict, sections: dict | None = None) -> dict:
    findings = {f["id"]: f for f in pack["findings"]}
    out = {"findings": {}, "brief": {}}
    for fid, f in findings.items():
        if fid not in prose:
            out["findings"][fid] = {"en": ["MISSING_FINDING"]}
            continue
        probs = {lang: verify_text(prose[fid][lang], f, pack, lang) for lang in ("mr", "en")}
        probs = {k: v for k, v in probs.items() if v}
        if probs:
            out["findings"][fid] = probs
    for lang, md in markdown.items():
        p = verify_markdown(md, lang, sections)
        if p:
            out["brief"][lang] = p
    out["passed"] = not out["findings"] and not out["brief"]
    return out
