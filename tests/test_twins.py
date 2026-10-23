"""Stage 5 twin finder on raw-ingested data."""

from __future__ import annotations

import pandas as pd
import pytest
from conftest import EXTRA_SEEDS, load_truth

from kaaran import evidence as E
from kaaran.causes import resolve_taluka
from kaaran.causes.data import analysis_scores
from kaaran.evidence import Builder
from kaaran.trust import as_pack, run_trust
from kaaran.twins import find_twin

SEEDS = [pytest.param(42, "solapur", id="seed42")] + [
    pytest.param(s, n, id=f"seed{s}-{n}", marks=pytest.mark.slow) for s, n in EXTRA_SEEDS
]


def _run(ingested, seed, names, tables_override=None):
    folder, ing = ingested(seed, names)
    tables = tables_override(ing.tables) if tables_override else ing.tables
    trust = run_trust(tables, ing.report)
    truth = {t["id"]: t for t in load_truth(folder)["truths"]}
    focus = resolve_taluka(tables, truth["T4"]["entities"]["focus"])
    b = Builder(tables)
    return ing, tables, trust, truth, b, find_twin(b, tables, analysis_scores(tables, trust), trust, focus)


@pytest.mark.parametrize("seed, names", SEEDS)
def test_twin_is_the_improver_not_the_decoy(ingested, seed, names):
    ing, tables, trust, truth, b, f = _run(ingested, seed, names)
    t4 = truth["T4"]["entities"]
    assert (f["label"], f["rule_id"]) == ("LEARN_FROM", "TWIN-LEARN-FROM")
    assert f["params"]["twin"]["entity"] == resolve_taluka(tables, t4["talukas"][0])
    assert f["params"]["decoy"]["entity"] == resolve_taluka(tables, t4["decoy"])
    assert b.numbers[f["params"]["twin_change"]["number"]]["value"] >= 6.0
    assert b.numbers[f["params"]["twin_rank_to"]["number"]]["value"] == 3
    assert f["sample"]["covariates"] == ["n_schools", "mean_enrolment", "poverty_index"] and not f["caveats"]
    pack = as_pack(E.merge_fragments(trust.fragment, b.fragment()), ing.report)
    assert E.validate(pack) == []


def test_without_poverty_data_the_finding_carries_a_caveat(ingested):
    def drop_poverty(tables):
        t = dict(tables)
        t["talukas"] = tables["talukas"].assign(poverty_index=pd.Series([None] * len(tables["talukas"]), dtype="Float64"))
        return t

    *_, f = _run(ingested, 42, "solapur", drop_poverty)
    assert f["label"] == "LEARN_FROM"
    assert {c["template_key"] for c in f["caveats"]} == {"caveat.poverty_not_available"}


def test_no_improver_gives_insufficient(ingested):
    def flatten_scores(tables):
        t = dict(tables)
        s = tables["scores"].copy()
        s["mean_score"] = 50.0
        t["scores"] = s
        return t

    *_, f = _run(ingested, 42, "solapur", flatten_scores)
    assert (f["label"], f["template_key"]) == ("INSUFFICIENT", "twin.none_found")
