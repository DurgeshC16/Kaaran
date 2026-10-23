"""Stage 5: prompt-injection guardrail and the brief-level eval over five seeds (replayed recordings)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kaaran.analyze import analyze
from kaaran.brief import write_brief
from kaaran.eval.brief import evaluate_folder, invented_numbers
from kaaran.eval.guardrails import INJECTED_CELL, INJECTED_CELL_SHORT, INJECTED_HEADER, check_injection, make_injected_copy
from kaaran.llm import LLMClient
from kaaran.llm.file_summary import summarize

BRIEF_SEEDS = [pytest.param(42, "solapur", id="seed42")] + [
    pytest.param(s, n, id=f"seed{s}-{n}", marks=pytest.mark.slow) for s, n in [(2026, "solapur"), (1, "solapur"), (99, "solapur"), (7, "fictional")]
]


def test_injected_instructions_do_not_change_the_mapping(demo_dir):
    result = check_injection(demo_dir / "raw")  # replays the recorded proposals
    assert result == {**result, "same_mapping": True, "clean_source": "llm", "injected_source": "llm"}


def test_long_injected_text_never_reaches_the_model(demo_dir, tmp_path):
    injected = make_injected_copy(demo_dir / "raw", tmp_path / "raw")
    text = json.dumps(summarize(injected), ensure_ascii=False)
    assert INJECTED_CELL not in text  # longer than the 30-char limit for shown values
    assert INJECTED_HEADER in text and INJECTED_CELL_SHORT in text  # these reach it, as quoted data, and are ignored


@pytest.mark.live
def test_injection_live(demo_dir, tmp_path):
    client = LLMClient(mode="live", cache_dir=tmp_path / "cache")
    assert check_injection(demo_dir / "raw", client)["same_mapping"]


@pytest.mark.parametrize("seed, names", BRIEF_SEEDS)
def test_brief_eval(dataset, seed, names):
    card, brief = evaluate_folder(dataset(seed, names))
    assert card["llm_available"] and card["template_fallback"] == 0, card
    assert card["first_pass_rate"] == 1.0 and card["shipped_passed"]
    assert card["invented_numbers"] == []
    assert 0 < card["cost_usd"] < 0.10  # recorded cost per brief


def test_invented_number_detector(demo_dir):
    pack = analyze(demo_dir / "raw", "Pandharpur").pack
    md = write_brief(pack, use_llm=False).markdown["mr"]
    assert invented_numbers(md, pack) == []
    assert invented_numbers(md + "\nएकूण १२३४ शाळा", pack) == ["१२३४"]


def test_sample_briefs_are_committed_for_review():
    samples = Path(__file__).resolve().parents[1] / "data" / "samples"
    briefs = sorted(samples.glob("brief_seed*_mr.md"))
    assert len(briefs) >= 3
    for b in briefs:
        text = b.read_text(encoding="utf-8")
        assert "SYNTHETIC" in text and "## कल" in text and "{{" not in text
