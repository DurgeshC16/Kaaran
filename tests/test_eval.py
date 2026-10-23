"""Stage 6 eval harness and analyze pipeline: raw files -> evidence pack -> scorecard vs ground_truth.json."""

from __future__ import annotations

import pytest

from kaaran import evidence as E
from kaaran.analyze import main as analyze_cli
from kaaran.eval import evaluate_folder, format_scorecard
from kaaran.eval.__main__ import main as eval_cli

OTHER_SEEDS = [(7, "fictional"), (2026, "solapur"), (1, "solapur"), (99, "solapur")]


@pytest.fixture(scope="session")
def evaluated(dataset):
    cache = {}

    def get(seed, names):
        if (seed, names) not in cache:
            cache[(seed, names)] = evaluate_folder(dataset(seed, names))
        return cache[(seed, names)]

    return get


def test_seed42_recovers_all_eight_truths(evaluated):
    card, analysis = evaluated(42, "solapur")
    assert card["recovered"] == 8, format_scorecard(card)
    assert card["wrong_verdicts"] == [] and card["missing_findings"] == []
    assert card["false_flags"] == [] and card["t8_flagged"] == []
    assert card["invented_numbers"] == []
    assert card["provenance_mismatches"] == [] and card["queries_checked"] > 20


@pytest.mark.slow
@pytest.mark.parametrize("seed, names", OTHER_SEEDS, ids=[f"seed{s}-{n}" for s, n in OTHER_SEEDS])
def test_other_seeds_recover_at_least_seven(evaluated, seed, names):
    card, _ = evaluated(seed, names)
    assert card["recovered"] >= 7, format_scorecard(card)
    assert card["invented_numbers"] == [] and card["provenance_mismatches"] == []
    assert card["t8_flagged"] == []


def test_pack_outline_follows_the_written_rule(evaluated):
    _, analysis = evaluated(42, "solapur")
    pack = analysis.pack
    assert E.validate(pack) == [] and pack["illustrative"] is False
    findings = {f["id"]: f for f in pack["findings"]}
    sections = {o["section"]: [findings[i] for i in o["finding_ids"]] for o in pack["outline"]}
    assert [f["type"] for f in sections["trend"]] == ["TREND"]
    assert sections["election_check"][0]["hypothesis"] == "election"
    assert sections["main_cause"][0]["hypothesis"] == "vacancy" and sections["main_cause"][0]["label"] == "STRONG"
    assert sections["twin"][0]["label"] == "LEARN_FROM"
    assert {f["label"] for f in sections["data_warning"]} == {"RED_FLAG", "CLEARED"}
    assert {f["template_key"] for f in sections["action"]} == {"action.redeploy_teachers", "action.exposure_visit", "action.verify_registers"}
    assert all(f["params"]["taluka"]["entity"] == pack["scope"]["focus"] for f in sections["data_warning"])
    # Every non-action finding says the data is synthetic; nothing leaks to the LLM view.
    assert all(f["caveats"][0]["template_key"] == "caveat.synthetic_data" for f in pack["findings"] if f["type"] != "ACTION")
    assert E.contains_identifiers(E.llm_view(pack)) == []


def test_analyze_and_eval_clis(demo_dir, tmp_path, capsys):
    out = tmp_path / "pack.json"
    assert analyze_cli([str(demo_dir / "raw"), "--focus", "पंढरपूर", "--out", str(out)]) == 0  # Marathi name works
    assert E.validate(E.load(out)) == []
    assert "main_cause" in capsys.readouterr().out
    assert eval_cli(["--seed", "42", "--json", str(tmp_path / "card.json")]) == 0
    assert "truths recovered: 8/8" in capsys.readouterr().out
