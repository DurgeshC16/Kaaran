"""Stage 4 verifier: bad LLM outputs are caught, retried once, then replaced by the template."""

from __future__ import annotations

import copy

import pytest
from conftest import EXTRA_SEEDS

from kaaran.analyze import analyze
from kaaran.brief import template_prose, write_brief
from kaaran.brief.verify import verify_brief, verify_markdown, verify_text
from kaaran.llm import LLMResult


@pytest.fixture(scope="session")
def pack42(demo_dir):
    return analyze(demo_dir / "raw", "Pandharpur").pack


def finding(pack, fid):
    return next(f for f in pack["findings"] if f["id"] == fid)


def test_template_prose_passes_the_verifier(pack42):
    prose = template_prose(pack42)
    for f in pack42["findings"]:
        for lang in ("mr", "en"):
            assert verify_text(prose[f["id"]][lang], f, pack42, lang) == [], (f["id"], lang)


@pytest.mark.slow
@pytest.mark.parametrize("seed, names", EXTRA_SEEDS)
def test_template_prose_passes_on_other_seeds(dataset, seed, names):
    pack = analyze(dataset(seed, names) / "raw", next(t for t in __import__("json").loads(
        (dataset(seed, names) / "ground_truth.json").read_text(encoding="utf-8"))["truths"] if t["id"] == "T1")["entities"]["talukas"][0]).pack
    brief = write_brief(pack, use_llm=False)
    assert brief.info["verification"]["passed"], brief.info["verification"]


@pytest.mark.parametrize("fid, lang, text, code", [
    ("F.trend", "en", "The score fell by 28 points.", "DIGIT"),
    ("F.trend", "mr", "गुण २८ ने घसरले.", "DIGIT"),
    ("F.trend", "en", "Eleven schools fell and twenty did not.", "SPELLED_NUMBER"),
    ("F.trend", "mr", "अकरा शाळांचे गुण घसरले.", "SPELLED_NUMBER"),
    ("F.trend", "en", "It fell to {{n:n.does.not.exist}}.", "PLACEHOLDER_UNKNOWN"),
    ("F.trend", "en", "Malshiras rose by {{n:n.score_change.T05.2021-22_2025-26}}.", "PLACEHOLDER_NOT_ALLOWED"),
    ("F.cause.election", "en", "The fall was due to election duty.", "CAUSAL_WORDING"),
    ("F.cause.election", "mr", "निवडणूक कामामुळे गुण घसरले.", "CAUSAL_WORDING"),
    ("F.data.flat.T08", "en", "Teachers caused the fake attendance.", "CAUSAL_WORDING"),
    ("F.trend", "mr", "The score fell over the period.", "NOT_MARATHI"),
    ("F.trend", "en", "It fell {{n:n.score_mean.T08.2021-22.", "PLACEHOLDER_MALFORMED"),
    ("F.trend", "en", "", "EMPTY"),
])
def test_verifier_catches_bad_text(pack42, fid, lang, text, code):
    problems = verify_text(text, finding(pack42, fid), pack42, lang)
    assert any(p.startswith(code) for p in problems), problems


@pytest.mark.parametrize("fid, lang, text", [
    ("F.cause.election", "en", "This does not show that election duty caused the fall."),  # negated
    ("F.cause.election", "mr", "निवडणूक काम कारण आहे असे सिद्ध होत नाही."),  # negated
    ("F.cause.election", "mr", "त्यामुळे निवडणूक कामाचा संबंध कमकुवत दिसतो."),  # connective "therefore"
    ("F.cause.vacancy", "en", "The fall is mostly because of vacant maths posts."),  # STRONG cause may use causal words
])
def test_verifier_allows_legitimate_wording(pack42, fid, lang, text):
    assert verify_text(text, finding(pack42, fid), pack42, lang) == []


def test_school_names_are_caught(pack42):
    school = next(e["name_en"] for e in pack42["entities"].values() if e["kind"] == "school")
    assert "SCHOOL_NAME" in verify_text(f"Visit {school} first.", finding(pack42, "F.action.verify_registers"), pack42, "en")


def test_missing_section_is_caught(pack42):
    md = write_brief(pack42, use_llm=False).markdown["en"]
    assert verify_markdown(md, "en") == []
    assert verify_markdown(md.replace("## Twin taluka", "## Something else"), "en") == ["MISSING_SECTION twin"]


class ScriptedClient:
    """Returns one scripted writer answer per call (first answer, then the retry)."""

    def __init__(self, answers):
        self.answers, self.calls = list(answers), []

    def call(self, **kw):
        self.calls.append(kw)
        data = self.answers.pop(0)
        return LLMResult(text="", data=data, model="fake", cached=False, usage={}, cost_usd=0.01, latency_s=1.0,
                         stop_reason="end_turn", key=f"k{len(self.calls)}")


def _answer(prose, overrides=None, drop=()):
    items = [{"id": fid, **copy.deepcopy(p)} for fid, p in prose.items() if fid not in drop]
    for it in items:
        it.update((overrides or {}).get(it["id"], {}))
    return {"findings": items}


BAD = {
    "F.trend": {"en": "The score fell by 3.3 points over five years."},  # invented / literal numbers
    "F.cause.election": {"mr": "निवडणूक कामामुळे गुण घसरले.", "en": "The fall was due to election duty."},  # causal on WEAK
    "F.twin": {"en": "Copy {{e:T99}}."},  # unknown placeholder
}


def test_bad_outputs_retry_then_succeed(pack42):
    good = template_prose(pack42)
    client = ScriptedClient([_answer(good, BAD, drop=("F.action.exposure_visit",)), _answer(good)])
    brief = write_brief(pack42, client=client)
    assert len(client.calls) == 2
    retried = {"F.trend", "F.cause.election", "F.twin", "F.action.exposure_visit"}
    assert {fid for fid, s in brief.sources.items() if s == "llm_retry"} == retried
    assert all(brief.sources[fid] == "llm" for fid in good if fid not in retried)
    assert "<problems>" in client.calls[1]["user"] and "DIGIT" in client.calls[1]["user"]
    assert brief.info["verification"]["passed"]


def test_bad_outputs_twice_fall_back_to_templates(pack42):
    good = template_prose(pack42)
    client = ScriptedClient([_answer(good, BAD), _answer(good, BAD)])
    brief = write_brief(pack42, client=client)
    for fid in BAD:
        assert brief.sources[fid] == "template" and brief.prose[fid] == good[fid]
    assert brief.info["verification"]["passed"]  # what ships always passes
    assert set(brief.info["problems"]) == set(BAD)
    report = verify_brief(brief.prose, brief.markdown, pack42)
    assert report["passed"]
