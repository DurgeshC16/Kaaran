"""Stage 1 mapping proposer: variant_b hold-out layout, file summaries, LLM mapping (replayed), fallbacks."""

from __future__ import annotations

import json
import re

import pytest

from kaaran.eval.mapping import evaluate_seed
from kaaran.ingest import ingest
from kaaran.ingest import mapping as M
from kaaran.llm import LLMClient, LLMResult
from kaaran.llm.file_summary import summarize
from kaaran.llm.mapper import propose_with_llm
from kaaran.synth.generate import generate

VALUE_COLUMNS = {
    "schools": ["udise_code", "school_name", "taluka_id", "enrol_total", "toilets", "library", "drinking_water", "classrooms"],
    "scores": ["udise_code", "academic_year", "mean_score", "students_appeared"],
    "teacher_posts": ["udise_code", "academic_year", "subject", "sanctioned", "working"],
    "election_duty": ["taluka_id", "month", "deployed_pct"],
    "talukas": ["taluka_id", "taluka", "n_schools", "poverty_index"],
}


@pytest.fixture(scope="session")
def variant42(tmp_path_factory):
    out = tmp_path_factory.mktemp("variant_b_42")
    generate(seed=42, out=out, layout="variant_b")
    return out


def test_variant_b_changes_layout_not_values(variant42, demo_dir):
    truth = json.loads((variant42 / "ground_truth.json").read_text(encoding="utf-8"))
    assert truth["layout"]["name"] == "variant_b" and len(truth["layout"]["tables"]) == 12
    errors = M.validate(M.propose(variant42 / "raw"), variant42 / "raw")
    assert any(e["code"] == "ROLE_MISSING" for e in errors)  # the rule-based baseline fails on the hold-out
    llm = ingest(variant42 / "raw", proposer="llm")  # replays the recorded proposal
    assert llm.report["mapping_proposer"]["source"] == "llm"
    base = ingest(demo_dir / "raw")
    for table, cols in VALUE_COLUMNS.items():
        a = llm.tables[table][cols].sort_values(cols[:2]).reset_index(drop=True)
        b = base.tables[table][cols].sort_values(cols[:2]).reset_index(drop=True)
        assert a.astype(str).equals(b.astype(str)), table


def test_file_summary_holds_no_codes_names_or_numbers(variant42, clean):
    summaries = summarize(variant42 / "raw")
    text = json.dumps(summaries, ensure_ascii=False)
    assert not re.findall(r"(?<!\d)\d{9,11}(?!\d)", text)
    assert not any(name in text for name in clean["schools"]["school_name"].head(200))
    for t in summaries:
        for c in t.get("columns", []):
            for v in c["profile"].get("values", []):
                assert not re.search(r"[0-8]", v), v  # digits are masked as 9
                assert len(v) <= 30


@pytest.mark.parametrize("seed", [42, pytest.param(7, marks=pytest.mark.slow), pytest.param(2026, marks=pytest.mark.slow)])
def test_llm_mapping_accuracy_vs_baseline(seed):
    rows = {(r["layout"], r["proposer"]): r for r in evaluate_seed(seed)}
    assert rows[("default", "rule")]["all"] == 1.0
    assert rows[("variant_b", "rule")]["valid"] is False and rows[("variant_b", "rule")]["required"] < 0.5
    for layout in ("default", "variant_b"):
        r = rows[(layout, "llm")]
        assert r["valid"] and r["source"] == "llm" and r["required"] == 1.0 and r["all"] == 1.0 and r["tables"] == 1.0
    assert rows[("variant_b", "llm")]["scorecard"] == "8/8"


def test_no_recording_falls_back_to_rule_baseline(demo_dir, tmp_path):
    client = LLMClient(mode="replay", cache_dir=tmp_path / "empty_cache", usage_log=tmp_path / "u.jsonl")
    mapping, info = propose_with_llm(demo_dir / "raw", client)
    assert info["source"] == "rule_fallback" and info["errors"][0]["code"] == "LLM_UNAVAILABLE"
    assert mapping == M.propose(demo_dir / "raw")


class BadClient:
    """Returns a mapping that names a header that does not exist; counts calls."""

    def __init__(self):
        self.calls = 0

    def call(self, **kw):
        self.calls += 1
        bad = {"tables": [{"file": "pat_scores.csv", "sheet": None, "role": "scores", "header_row": 2,
                           "fields": [{"field": "udise_code", "source": "column", "column": "No such header"}]}]}
        return LLMResult(text=json.dumps(bad), data=bad, model="fake", cached=False, usage={}, cost_usd=0.0, latency_s=0.0,
                         stop_reason="end_turn", key=f"k{self.calls}")


def test_invalid_llm_mapping_retries_once_then_falls_back(demo_dir):
    client = BadClient()
    mapping, info = propose_with_llm(demo_dir / "raw", client)
    assert client.calls == 2 and info["source"] == "rule_fallback"
    codes = {e["code"] for attempt in info["errors"] for e in attempt["errors"]}
    assert "HEADER_NOT_FOUND" in codes or "ROLE_MISSING" in codes
    assert all("value" not in e for attempt in info["errors"] for e in attempt["errors"])  # shapes only
    assert mapping == M.propose(demo_dir / "raw")
