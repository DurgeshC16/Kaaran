"""Planted truths T1-T8, verified with plain pandas on the clean tables (no Kaaran engines)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
from conftest import FIRST, LAST, YEARS, all_months

from kaaran.synth.generate import CLEAN_TABLES


def ranks(col: pd.Series) -> pd.Series:
    return col.rank(ascending=False, method="min").astype(int)


def longest_equal_run(values: list[float]) -> int:
    best = run = 1
    for a, b in zip(values, values[1:]):
        run = run + 1 if a == b else 1
        best = max(best, run)
    return best


# ---------- scope and baseline ----------


def test_scope(clean, gt):
    talukas, schools = clean["talukas"], clean["schools"]
    assert gt["synthetic"] is True and "SYNTHETIC" in gt["district"]
    assert len(talukas) == 11
    assert 1200 <= len(schools) <= 1400
    counts = schools.groupby("taluka").size()
    assert counts.between(90, 160).all()
    focus = gt["truths"][0]["entities"]["talukas"][0]
    assert counts[focus] >= 140
    codes = schools["udise_code"]
    assert codes.is_unique and schools["short_code"].is_unique
    assert codes.str.fullmatch(r"00\d{9}").all()
    clusters = schools.groupby(["taluka", "cluster_code"]).size()
    assert clusters.between(10, 15).all()
    assert schools["enrol_total"].between(20, 150).all()
    stds = schools[[f"enrol_std{i}" for i in range(1, 6)]].sum(axis=1)
    assert (stds == schools["enrol_total"]).all()
    assert sorted(clean["scores"]["academic_year"].unique()) == YEARS


def test_every_clean_table_is_marked_synthetic(demo_dir):
    for key in CLEAN_TABLES:
        meta = pq.read_schema(demo_dir / "clean" / f"{key}.parquet").metadata
        assert meta[b"synthetic"] == b"true"
        assert b"SYNTHETIC" in meta[b"marker"]


def test_baseline(clean, taluka_scores, gt, truths):
    first = taluka_scores[FIRST]
    assert 54.0 <= first.mean() <= 56.0
    assert 1.5 <= first.std() <= 3.0
    # Weak negative poverty association at taluka level.
    pov = clean["talukas"].set_index("taluka")["poverty_index"]
    r = np.corrcoef(pov.loc[taluka_scores.index], taluka_scores.mean(axis=1))[0, 1]
    assert -0.7 <= r <= -0.2
    assert clean["scores"]["mean_score"].between(0, 100).all()
    # Ordinary schools: attendance 84-91 on average, never above 98 unless planted flat.
    att = clean["attendance"]
    planted = set(truths["T5"]["entities"]["schools"]) | set(truths["T5"]["entities"]["scattered_schools"])
    planted |= set(truths["T8"]["entities"]["schools"])
    normal = att[~att["udise_code"].isin(planted)]
    means = normal.groupby("udise_code")["attendance_pct"].mean()
    assert means.between(83.5, 91.5).mean() >= 0.95
    assert normal["attendance_pct"].max() <= 98.0


def test_planted_school_sets_are_disjoint(truths):
    t3 = set(truths["T3"]["entities"]["schools"]) | set(truths["T3"]["entities"]["same_pattern_other_talukas"])
    t5 = set(truths["T5"]["entities"]["schools"]) | set(truths["T5"]["entities"]["scattered_schools"])
    t8 = set(truths["T8"]["entities"]["schools"])
    assert not (t3 & t5) and not (t3 & t8) and not (t5 & t8)


# ---------- T1 REAL_DECLINE ----------


def test_t1_real_decline(truths, taluka_scores, school_wide, clean):
    t = truths["T1"]
    assert t["verdict"] == "STRONG"
    focus = t["entities"]["talukas"][0]
    change = taluka_scores.loc[focus, LAST] - taluka_scores.loc[focus, FIRST]
    assert change <= -t["expected"]["min_drop"]
    assert change == pytest.approx(t["expected"]["change"], abs=t["expected"]["change_tolerance"])
    assert ranks(taluka_scores[FIRST])[focus] == 4
    assert ranks(taluka_scores[LAST])[focus] == 9
    for y in YEARS[2:]:
        assert taluka_scores.loc[focus, y] < taluka_scores.loc[focus, FIRST]
    # School-level paired comparison.
    focus_codes = clean["schools"].loc[clean["schools"]["taluka"] == focus, "udise_code"]
    diff = (school_wide.loc[focus_codes, LAST] - school_wide.loc[focus_codes, FIRST]).dropna()
    t_stat = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff)))
    assert t_stat <= t["expected"]["paired_t_max"]


# ---------- T2 ELECTION_EXCUSE_WEAK ----------


def test_t2_election_excuse_weak(truths, clean, taluka_scores):
    t = truths["T2"]
    e = t["expected"]
    assert t["verdict"] == "WEAK_CAUSE"
    duty = clean["election_duty"]
    heavy = duty[duty["deployed_pct"] >= e["threshold_pct"]]
    months = heavy.groupby(["taluka", "academic_year"]).size()
    qualifying = months[months >= e["min_months"]]
    assert set(qualifying.index.get_level_values("academic_year")) == {e["election_year"]}
    assert set(qualifying.index.get_level_values("taluka")) == set(t["entities"]["talukas"])
    assert len(t["entities"]["talukas"]) == 7

    before, during = e["change_window"]
    change = taluka_scores[during] - taluka_scores[before]
    focus = truths["T1"]["entities"]["talukas"][0]
    comparison = t["entities"]["comparison_talukas"]
    assert len(comparison) == 5
    assert change[comparison].abs().max() <= e["comparison_max_abs_change"]
    dipper = t["entities"]["unrelated_dip_taluka"]
    assert change[dipper] == pytest.approx(e["unrelated_dip_change"], abs=e["unrelated_dip_tolerance"])
    assert change[dipper] == pytest.approx(-1.5, abs=0.3)
    assert change[focus] < change[dipper]  # the unrelated dip is smaller than Pandharpur's


# ---------- T3 VACANCY_CAUSE ----------


def test_t3_vacancy_cause(truths, clean, school_wide):
    t = truths["T3"]
    e = t["expected"]
    assert t["verdict"] == "STRONG"
    focus = t["entities"]["talukas"][0]
    vac_focus = set(t["entities"]["schools"])
    vac_other = set(t["entities"]["same_pattern_other_talukas"])
    assert len(vac_focus) == 11 and len(vac_other) == 8

    posts = clean["teacher_posts"]
    maths = posts[posts["subject"] == "maths"]
    vacant = maths[maths["working"] == 0]
    start = YEARS.index(e["vacancy_start_year"])
    for i, y in enumerate(YEARS):
        codes = set(vacant.loc[vacant["academic_year"] == y, "udise_code"])
        assert codes == ((vac_focus | vac_other) if i >= start else set())
    twin = truths["T4"]["entities"]["talukas"][0]
    twin_codes = clean["schools"].loc[clean["schools"]["taluka"] == twin, "udise_code"]
    assert not vacant["udise_code"].isin(twin_codes).any()

    focus_codes = list(clean["schools"].loc[clean["schools"]["taluka"] == focus, "udise_code"])
    change = school_wide[LAST] - school_wide[FIRST]
    vac_change = change[list(vac_focus)].mean()
    rest_change = change[[c for c in focus_codes if c not in vac_focus]].mean()
    taluka_change = change[focus_codes].mean()
    lo, hi = e["vacancy_group_drop_range"]
    assert lo <= -vac_change <= hi
    assert abs(rest_change) <= e["other_schools_max_abs_change"]
    share = len(vac_focus) / len(focus_codes) * vac_change / taluka_change
    assert share >= e["min_decline_share"]
    assert lo <= -change[list(vac_other)].mean() <= hi
    # Pre-vacancy years look ordinary: no drop before the vacancy starts.
    pre = school_wide.loc[list(vac_focus), YEARS[start - 1]] - school_wide.loc[list(vac_focus), FIRST]
    assert abs(pre.mean()) <= 2.0


# ---------- T4 TWIN_BLOCK ----------


def test_t4_twin_block(truths, clean, taluka_scores):
    t = truths["T4"]
    e = t["expected"]
    tol = e["tolerances"]
    assert t["verdict"] == "LEARN_FROM"
    focus, twin, decoy = t["entities"]["focus"], t["entities"]["talukas"][0], t["entities"]["decoy"]
    tal = clean["talukas"].set_index("taluka")
    enrol = clean["schools"].groupby("taluka")["enrol_total"].mean()
    election = set(truths["T2"]["entities"]["talukas"])
    for other in (twin, decoy):
        assert abs(tal.loc[other, "n_schools"] / tal.loc[focus, "n_schools"] - 1) * 100 <= tol["n_schools_pct"]
        assert abs(tal.loc[other, "poverty_index"] - tal.loc[focus, "poverty_index"]) <= tol["poverty_abs"]
        assert abs(enrol[other] / enrol[focus] - 1) * 100 <= tol["mean_enrolment_pct"]
        assert other in election
    # Only the twin and the decoy are size-matched to the focus taluka.
    size_close = tal.index[(tal["n_schools"] / tal.loc[focus, "n_schools"] - 1).abs() * 100 <= tol["n_schools_pct"]]
    assert set(size_close) == {focus, twin, decoy}
    # The decoy is the closer match on poverty and size, but did not improve.
    assert abs(tal.loc[decoy, "poverty_index"] - tal.loc[focus, "poverty_index"]) < abs(
        tal.loc[twin, "poverty_index"] - tal.loc[focus, "poverty_index"]
    )
    twin_change = taluka_scores.loc[twin, LAST] - taluka_scores.loc[twin, FIRST]
    decoy_change = taluka_scores.loc[decoy, LAST] - taluka_scores.loc[decoy, FIRST]
    assert twin_change >= e["twin_min_change"]
    assert ranks(taluka_scores[FIRST])[twin] == 8
    assert ranks(taluka_scores[LAST])[twin] == 3
    assert decoy_change <= e["decoy_max_change"]


# ---------- T5 FLAT_ATTENDANCE ----------


def test_t5_flat_attendance(truths, clean):
    t = truths["T5"]
    e = t["expected"]
    assert t["verdict"] == "RED_FLAG"
    focus = t["entities"]["talukas"][0]
    order = {m: i for i, m in enumerate(all_months())}
    att = clean["attendance"].merge(clean["schools"][["udise_code", "taluka"]], on="udise_code")
    flat = att[att["attendance_pct"] == 100.0]
    runs = flat.groupby("udise_code")["month"].apply(lambda s: sorted(s, key=order.get))
    for code, months in runs.items():
        idx = [order[m] for m in months]
        assert len(idx) == e["run_months"] and idx == list(range(idx[0], idx[0] + e["run_months"]))
        assert all(m.startswith("2024-") for m in months)
    flat_taluka = flat.drop_duplicates("udise_code").set_index("udise_code")["taluka"]
    in_focus = set(flat_taluka.index[flat_taluka == focus])
    elsewhere = set(flat_taluka.index[flat_taluka != focus])
    assert in_focus == set(t["entities"]["schools"]) and len(in_focus) == 23
    assert elsewhere == set(t["entities"]["scattered_schools"]) and 25 <= len(elsewhere) <= 35
    for code in in_focus:
        assert runs[code] == e["focus_months"]
    # Scattered, not concentrated: no other taluka has more than a third of Pandharpur's count.
    assert flat_taluka[flat_taluka != focus].value_counts().max() < 23 / 3


# ---------- T6 INSUFFICIENT_DATA ----------


def test_t6_insufficient_data(truths, clean):
    t = truths["T6"]
    e = t["expected"]
    assert t["verdict"] == "INSUFFICIENT"
    schools = clean["schools"].set_index("udise_code")
    n_months = len(all_months())
    miss_att = n_months - clean["attendance"].groupby("udise_code").size().reindex(schools.index, fill_value=0)
    miss_scores = len(YEARS) - clean["scores"].groupby("udise_code").size().reindex(schools.index, fill_value=0)
    flagged = (miss_att >= 3) | (miss_scores >= 2)
    share = flagged.groupby(schools["taluka"]).mean()
    sparse = t["entities"]["talukas"][0]
    assert share[sparse] >= e["min_flagged_share"]
    assert share.drop(sparse).max() < e["other_talukas_max_flagged_share"]
    assert set(flagged.index[flagged]) == set(t["entities"]["schools"])
    # Ordinary gaps elsewhere stay small: <= 3% of schools miss any month.
    any_gap = (miss_att > 0).groupby(schools["taluka"]).mean()
    assert any_gap.drop(sparse).max() <= 0.03


# ---------- T7 INFRA_DECOY ----------


def test_t7_infra_decoy(truths, clean, taluka_scores, school_wide):
    t = truths["T7"]
    e = t["expected"]
    assert t["verdict"] == "NOT_A_CAUSE"
    low, focus = t["entities"]["talukas"]
    infra = clean["schools"].groupby("taluka")["infra_index"].mean().sort_values()
    assert infra.index[0] == low
    assert infra.iloc[1] - infra.iloc[0] >= e["lowest_margin_min"]
    yearly = taluka_scores.loc[low, YEARS].diff().dropna()
    assert yearly.abs().max() <= e["infra_low_max_abs_yearly_change"]
    assert abs(taluka_scores.loc[low, LAST] - taluka_scores.loc[low, FIRST]) <= 1.0
    fs = clean["schools"][clean["schools"]["taluka"] == focus].set_index("udise_code")
    change = (school_wide[LAST] - school_wide[FIRST]).reindex(fs.index)
    r = np.corrcoef(fs["infra_index"], change)[0, 1]
    assert abs(r) < e["focus_max_abs_r"]


# ---------- T8 HONEST_LOW_ATTENDANCE ----------


def test_t8_honest_low_attendance(truths, clean, school_wide):
    t = truths["T8"]
    e = t["expected"]
    assert t["verdict"] == "NOT_FLAGGED"
    honest = t["entities"]["schools"]
    assert len(honest) == 15
    order = {m: i for i, m in enumerate(all_months())}
    att = clean["attendance"][clean["attendance"]["udise_code"].isin(honest)]
    lo, hi = e["mean_attendance_range"]
    for code, g in att.groupby("udise_code"):
        assert lo <= g["attendance_pct"].mean() <= hi
        values = g.sort_values("month", key=lambda s: s.map(order))["attendance_pct"].tolist()
        assert longest_equal_run(values) <= e["max_equal_consecutive_months"]
        assert max(values) < 100.0
        assert np.std(values) > 0.5  # natural variation, not a pasted constant
    # Ordinary scores: within the 5th-95th percentile of other Pandharpur schools.
    focus = t["entities"]["talukas"][0]
    vac = set(truths["T3"]["entities"]["schools"])
    focus_codes = clean["schools"].loc[clean["schools"]["taluka"] == focus, "udise_code"]
    others = [c for c in focus_codes if c not in vac and c not in honest]
    five_year = school_wide.mean(axis=1)
    p5, p95 = five_year[others].quantile([0.05, 0.95])
    assert five_year[honest].between(p5, p95).all()
