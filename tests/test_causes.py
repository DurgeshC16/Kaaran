"""Stage 4 cause tester on raw-ingested data: trend, election, vacancy, infrastructure, attendance."""

from __future__ import annotations

import pytest
from conftest import EXTRA_SEEDS, load_truth

from kaaran import confidence as K
from kaaran import evidence as E
from kaaran.causes import resolve_taluka, run_causes
from kaaran.trust import as_pack, run_trust

SEEDS = [pytest.param(42, "solapur", id="seed42")] + [
    pytest.param(s, n, id=f"seed{s}-{n}", marks=pytest.mark.slow) for s, n in EXTRA_SEEDS
]


@pytest.fixture(scope="session")
def caused(ingested):
    cache = {}

    def get(seed, names, focus_truth="T1"):
        key = (seed, names, focus_truth)
        if key not in cache:
            folder, ing = ingested(seed, names)
            trust = run_trust(ing.tables, ing.report)
            truth = {t["id"]: t for t in load_truth(folder)["truths"]}
            focus = resolve_taluka(ing.tables, truth[focus_truth]["entities"]["talukas"][0])
            b, res = run_causes(ing.tables, trust, focus)
            cache[key] = (folder, ing, trust, truth, focus, b, res)
        return cache[key]

    return get


@pytest.mark.parametrize("seed, names", SEEDS)
def test_planted_causes_recovered(caused, seed, names):
    _, ing, trust, truth, focus, b, res = caused(seed, names)
    trend = res["trend"]
    assert (trend["label"], trend["template_key"]) == ("STRONG", "trend.decline_rank")
    assert b.numbers[trend["params"]["rank_from"]["number"]]["value"] == 4
    assert b.numbers[trend["params"]["rank_to"]["number"]]["value"] == 9
    assert b.numbers[trend["params"]["change"]["number"]]["value"] <= -3.0

    el = res["election"]
    assert (el["label"], el["template_key"]) == ("WEAK", "cause.election.similar_blocks_no_drop")
    assert b.numbers[el["params"]["n_similar_no_drop"]["number"]]["value"] == 5

    vac = res["vacancy"]
    assert (vac["label"], vac["template_key"]) == ("STRONG", "cause.vacancy.concentrated")
    members = {m[1:] for m in b.entity_sets[vac["params"]["schools"]["set"]]["members"]}
    assert members == set(truth["T3"]["entities"]["schools"])
    assert b.numbers[vac["params"]["share_of_decline"]["number"]]["value"] >= 60.0

    assert res["infrastructure"]["label"] == "RULED_OUT"
    att = res["attendance"]
    assert att is None or att["label"] in ("RULED_OUT", "INSUFFICIENT", "WEAK")
    assert att is None or att["template_key"] not in E.CAUSAL_TEMPLATE_KEYS


def test_cause_findings_form_a_valid_pack(caused):
    _, ing, trust, _, focus, b, _ = caused(42, "solapur")
    pack = as_pack(E.merge_fragments(trust.fragment, b.fragment()), ing.report, focus)
    assert E.validate(pack) == []
    assert E.contains_identifiers(E.llm_view(pack)) == []


def test_insufficient_taluka_caps_findings(caused):
    _, ing, trust, truth, _, _, _ = caused(42, "solapur")
    sparse = resolve_taluka(ing.tables, truth["T6"]["entities"]["talukas"][0])
    b, res = run_causes(ing.tables, trust, sparse)
    for k in ("trend", "election", "vacancy", "infrastructure", "attendance"):
        if res[k] is not None:
            assert res[k]["label"] == "INSUFFICIENT", k


# ---------- label rules ----------


def test_trend_label_rules():
    assert K.trend_label(-4, -3.0, True, False, {})[:2] == ("STRONG", "trend.decline_rank")
    assert K.trend_label(-4, -3.0, False, False, {})[:2] == ("WEAK", "trend.decline_weak")  # not persistent
    assert K.trend_label(-2.5, -1.0, True, False, {})[:2] == ("WEAK", "trend.decline_weak")
    assert K.trend_label(-1.0, -0.5, False, False, {})[:2] == ("WEAK", "trend.no_clear_change")
    assert K.trend_label(5, 4.0, True, False, {})[:2] == ("STRONG", "trend.rise_rank")
    assert K.trend_label(-9, -5.0, True, True, {})[0] == "INSUFFICIENT"


def test_exposure_label_needs_every_strong_criterion():
    assert K.exposure_label(-10, 66, -12, 0.1, False, {})[:2] == ("STRONG", "cause.vacancy.concentrated")
    assert K.exposure_label(-10, 30, -12, 0.1, False, {})[:2] == ("WEAK", "cause.vacancy.associated")  # explains too little
    assert K.exposure_label(-10, 66, None, 0.1, False, {})[:2] == ("WEAK", "cause.vacancy.associated")  # no replication
    assert K.exposure_label(-10, 66, -12, -4.0, False, {})[:2] == ("WEAK", "cause.vacancy.associated")  # already falling
    assert K.exposure_label(-1, 0, -1, 0, False, {})[:2] == ("RULED_OUT", "cause.vacancy.no_link")


def test_election_and_correlation_rules():
    assert K.election_label(-2.0, 6, 5, False, {})[:2] == ("WEAK", "cause.election.similar_blocks_no_drop")
    assert K.election_label(-2.0, 6, 2, False, {})[:2] == ("WEAK", "cause.election.associated")
    assert K.election_label(0.5, 6, 5, False, {})[:2] == ("RULED_OUT", "cause.election.no_link")
    assert K.correlation_label("infrastructure", 0.5, True, False, {})[:2] == ("RULED_OUT", "cause.infra.no_link")
    assert K.correlation_label("infrastructure", 0.5, False, False, {})[:2] == ("INSUFFICIENT", "cause.inconclusive")
    assert K.correlation_label("attendance", -3.5, None, False, {})[:2] == ("WEAK", "cause.attendance.associated")
    assert K.correlation_label("attendance", -2.5, None, False, {})[:2] == ("INSUFFICIENT", "cause.inconclusive")


def test_causal_wording_requires_strong(caused):
    _, ing, trust, _, focus, b, _ = caused(42, "solapur")
    pack = as_pack(E.merge_fragments(trust.fragment, b.fragment()), ing.report, focus)
    vac = next(f for f in pack["findings"] if f.get("hypothesis") == "vacancy")
    vac["label"] = "WEAK"
    assert any("causal wording" in p for p in E.validate(pack))
