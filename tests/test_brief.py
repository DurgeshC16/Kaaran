"""Stage 3 Brief Writer: template brief, LLM brief (replayed), what the LLM sees, fallback, CLI."""

from __future__ import annotations

import json
import re

import pytest

from kaaran import evidence as E
from kaaran.analyze import analyze
from kaaran.brief import template_prose, write_brief
from kaaran.brief import texts as X
from kaaran.brief.__main__ import main as brief_cli
from kaaran.brief.writer import llm_input
from kaaran.llm import LLMClient


@pytest.fixture(scope="session")
def pack42(demo_dir):
    return analyze(demo_dir / "raw", "Pandharpur").pack


def _structure_ok(md: str, lang: str):
    i = 0 if lang == "mr" else 1
    for section in X.REQUIRED_SECTIONS:
        assert f"## {X.SECTION_HEADINGS[section][i]}" in md, section
    assert X.BANNER[i] in md
    assert "{{" not in md and "[[" not in md  # every placeholder filled
    for role in ("DEO", "BEO", "KENDRA_PRAMUKH"):
        assert X.ACTORS[role][i] in md


def test_template_brief_is_complete(pack42):
    brief = write_brief(pack42, use_llm=False)
    assert set(brief.sources.values()) == {"template"}
    for lang in ("mr", "en"):
        _structure_ok(brief.markdown[lang], lang)
    assert "५६.०" in brief.markdown["mr"] and "५२.७" in brief.markdown["mr"]  # code-filled Devanagari figures
    assert "56.0" in brief.markdown["en"] and "Malshiras" in brief.markdown["en"]
    appendix = brief.markdown["en"].split("## Other checks")[1]
    assert "attendance" in appendix  # the inconclusive attendance line sits in the appendix only
    assert "attendance" not in brief.markdown["en"].split("## Other checks")[0].split("## Data warning")[0]


def test_templates_contain_no_digits():
    for key, (mr, en) in X.TEMPLATES.items():
        assert not re.search(r"[0-9०-९]", mr + en), key
    for key, (mr, en) in X.CAVEATS.items():
        assert not re.search(r"[0-9०-९]", mr + en), key


def test_llm_brief_replays_and_fills(pack42):
    brief = write_brief(pack42)  # replay of the recorded seed-42 brief
    assert all(v.startswith("llm") for v in brief.sources.values()), brief.info
    for lang in ("mr", "en"):
        _structure_ok(brief.markdown[lang], lang)
    assert "AI" in brief.markdown["mr"].rsplit("---", 1)[-1]  # footer says the wording came from the AI writer


def test_llm_sees_aggregates_only(pack42):
    payload = llm_input(pack42)
    text = json.dumps(payload, ensure_ascii=False)
    assert E.contains_identifiers(payload) == []
    school_names = [e["name_en"] for e in pack42["entities"].values() if e["kind"] == "school"]
    assert school_names and not any(n in text for n in school_names)
    for f in payload["findings"]:
        assert f["facts_en"] and f["may_use"]
        assert all(k.startswith("{{") for k in f["may_use"])


def test_without_api_the_template_brief_is_used(pack42, tmp_path):
    client = LLMClient(mode="replay", cache_dir=tmp_path / "empty", usage_log=tmp_path / "u.jsonl")
    brief = write_brief(pack42, client=client)
    assert brief.info["llm_available"] is False and set(brief.sources.values()) == {"template"}
    assert brief.prose == template_prose(pack42)


def test_brief_cli(demo_dir, tmp_path):
    assert brief_cli([str(demo_dir / "raw"), "--focus", "Pandharpur", "--out-dir", str(tmp_path), "--no-llm"]) == 0
    md = (tmp_path / "brief_mr.md").read_text(encoding="utf-8")
    assert md.startswith("# पुरावा अहवाल: पंढरपूर")
    assert E.validate(E.load(tmp_path / "evidence.json")) == []
