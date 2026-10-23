"""Stage 2 intent parser: validated plans, clarification instead of guessing, refusals (replayed recordings)."""

from __future__ import annotations

import pytest

from kaaran.eval.intent import run, seed42_talukas
from kaaran.llm import LLMClient
from kaaran.llm.intent import parse, validate_plan


@pytest.fixture(scope="module")
def gaz():
    return seed42_talukas()


def _never_guesses(result):
    """A miss may ask or refuse, but must never analyse the wrong place or answer a refused request."""
    import json

    from kaaran.eval.intent import FIXTURE

    expected = {q["id"]: q for q in json.loads(FIXTURE.read_text(encoding="utf-8"))["questions"]}
    for row in result["rows"]:
        exp, got = expected[row["id"]], row["got"]
        if got["status"] == "ok":
            assert exp["status"] == "ok" and got["taluka_id"] == exp["taluka_id"], row
        if exp["status"] == "refuse":
            assert got["status"] == "refuse", row


@pytest.mark.parametrize("tier, floor", [("light", 0.9), ("main", 0.9)])
def test_llm_intent_accuracy_on_25_questions(gaz, tier, floor):
    talukas, years = gaz
    result = run(tier, talukas=talukas, years=years)
    assert result["fallbacks"] == 0  # every answer replayed from the recordings
    assert result["accuracy"] >= floor, [r for r in result["rows"] if not r["ok"]]
    _never_guesses(result)


def test_rule_fallback_accuracy(gaz):
    talukas, years = gaz
    assert run("rule", talukas=talukas, years=years)["accuracy"] >= 0.8


def test_validator_turns_doubt_into_clarification():
    ids, years = {"T01", "T08"}, ["2021-22", "2025-26"]
    assert validate_plan({"status": "ok", "taluka_id": "T99", "compare_with": None}, ids, years)["reason"] == "unknown_place"
    p = validate_plan({"status": "ok", "taluka_id": None, "compare_with": None}, ids, years)
    assert (p["status"], p["reason"]) == ("clarify", "missing_place")
    p = validate_plan({"status": "ok", "taluka_id": "T08", "compare_with": None, "year_from": "2019-20", "year_to": "garbage"}, ids, years)
    assert p["status"] == "ok" and p["year_from"] is None and p["year_to"] is None and p["subject"] == "maths"
    p = validate_plan({"status": "refuse", "reason": "nonsense", "taluka_id": "T08", "compare_with": None}, ids, years)
    assert (p["status"], p["reason"], p["taluka_id"]) == ("refuse", "out_of_scope", None)


def test_without_recording_the_rule_matcher_answers(gaz, tmp_path):
    talukas, years = gaz
    client = LLMClient(mode="replay", cache_dir=tmp_path / "empty", usage_log=tmp_path / "u.jsonl")
    plan = parse("पंढरपूरचा गणिताचा निकाल का घसरला?", talukas, years, client=client)
    assert plan["source"] == "rule_fallback" and (plan["status"], plan["taluka_id"]) == ("ok", "T08")
