"""v3 generator (block lens): planted scenarios hold, real-format files, SYNTHETIC markers, determinism."""

from __future__ import annotations

import json

import pandas as pd
import pytest
from openpyxl import load_workbook

from kaaran.synth3 import SYNTHETIC_MARKER
from kaaran.synth3 import config as C
from kaaran.synth3.generate import generate
from kaaran.synth3.world import build_world

UDISE_COLUMNS = {
    "prof1": ["udise_sch_code", "school_name", "state", "district", "block", "rural_urban", "lgd_vill_name",
              "lgd_vill_panchayat_name", "school_category", "school_type", "lowclass", "highclass", "managment",
              "medium_instr1", "avg_instr_days"],
    "prof2": ["udise_sch_code", "acad_inspections", "crc_coordinator", "block_level_officers", "district_officers",
              "smc_exists", "smc_smdc_meetings"],
    "tch": ["udise_sch_code", "total_tch", "male", "female", "regular", "contract", "class_taught_pr",
            "teacher_involve_non_training_assignment"],
}


@pytest.fixture(scope="session")
def world():
    return build_world(42)


@pytest.fixture(scope="session")
def block_demo(tmp_path_factory):
    out = tmp_path_factory.mktemp("block_demo")
    generate(42, out)
    return out


def focus(w):
    return w.schools[w.schools["block_key"] == C.FOCUS]


def maths_el_change(w, frame_filter=None) -> pd.Series:
    a = w.assessment[(w.assessment["subject"] == "maths") & (w.assessment["round"] == "EL")]
    m = a.merge(w.schools[["udise_code", "block_key", "cluster_idx"]], on="udise_code")
    m = m[m["block_key"] == C.FOCUS]
    by = m.groupby(["cluster_idx", "academic_year"])["pct"].mean().unstack()
    return by[C.YEARS[-1]] - by[C.YEARS[-2]]


def test_hierarchy_and_roles(world):
    f = focus(world)
    assert f["cluster_idx"].nunique() == 12 and len(f) == 140
    roles = f.groupby("role").size().to_dict()
    assert roles["staffing_gap"] == C.STAFFING_GAP_SCHOOLS and roles["positive_deviant"] == 1
    assert roles["flat"] == C.FLAT_SCHOOLS and roles["migration"] == C.MIGRATION_SCHOOLS
    assert roles["insufficient"] == C.INSUFFICIENT_SCHOOLS and roles["honest_low"] == C.HONEST_LOW_SCHOOLS
    assert (f.loc[f["cluster_idx"] == C.SUPPORT_GAP, "role"] == "support_gap").all()
    assert not f.loc[f["kendra_school"], "role"].isin(["staffing_gap", "flat", "migration", "insufficient"]).any()


def test_support_gap_visits_and_learning(world):
    f = focus(world)
    gap = set(f.loc[f["cluster_idx"] == C.SUPPORT_GAP, "udise_code"])
    v = world.visits[world.visits["visitor_role"] == "Kendra Pramukh"]
    v = v[v["udise_code"].isin(gap)]
    after = (v["date"].str[:7] >= C.SUPPORT_GAP_START).sum() / (len(gap) * 10)  # 10 school months in 2025-26
    before = (v["date"].str[:7] < C.SUPPORT_GAP_START).sum() / (len(gap) * 20)
    assert after < 0.3 < 1.0 < before
    change = maths_el_change(world)
    assert change[C.SUPPORT_GAP] <= -6 and change[C.SUPPORT_GAP] == change.min()
    t = world.training.merge(f[["udise_code", "cluster_idx"]], on="udise_code")
    assert t.loc[t["cluster_idx"] == C.SUPPORT_GAP, "date"].max() < "2024-06"  # last trained more than a year ago


def test_staffing_gap_and_surplus(world):
    f = focus(world)
    p = world.posts.merge(f[["udise_code", "role"]], on="udise_code")
    gap = p[p["role"] == "staffing_gap"]
    assert (gap.loc[gap["month"] >= C.STAFFING_GAP_START, "working"] < gap.loc[gap["month"] >= C.STAFFING_GAP_START, "sanctioned"]).all()
    assert (gap.loc[gap["month"] < C.STAFFING_GAP_START, "working"] == gap.loc[gap["month"] < C.STAFFING_GAP_START, "sanctioned"]).all()
    e = world.enrolment.assign(t=lambda d: d["boys"] + d["girls"]).groupby(["udise_code", "academic_year"])["t"].sum()
    for code in f.loc[f["role"] == "surplus", "udise_code"]:
        working = p[(p["udise_code"] == code) & (p["month"] == "2025-09")]["working"].iloc[0]
        assert e[(code, "2025-26")] / working < 18


def test_attendance_scenarios(world):
    a = world.attendance.merge(focus(world)[["udise_code", "role"]], on="udise_code")
    flat = a[(a["role"] == "flat") & a["month"].isin(C.FLAT_MONTHS)]
    assert len(flat) == C.FLAT_SCHOOLS * len(C.FLAT_MONTHS) and (flat["attendance_pct"] == 100.0).all()
    assert a.loc[a["role"] == "honest_low", "attendance_pct"].max() < 99
    assert a.loc[~a["role"].isin(["flat"]), "attendance_pct"].max() <= C.ATTENDANCE_CAP
    mig = a[a["role"] == "migration"].assign(m=lambda d: d["month"].str[5:].astype(int))
    winter = mig[mig["m"].isin([12, 1, 2])]["attendance_pct"].mean()
    monsoon_end = mig[mig["m"].isin([9, 10])]["attendance_pct"].mean()
    assert monsoon_end - winter >= 10
    ins = a[(a["role"] == "insufficient") & a["month"].isin(C.INSUFFICIENT_MISSING_MONTHS)]
    assert ins.empty
    el = world.assessment.merge(focus(world)[["udise_code", "role"]], on="udise_code")
    assert el[(el["role"] == "insufficient") & (el["academic_year"] == C.YEARS[-1]) & (el["round"] == "EL")].empty


def test_raw_files_real_formats_and_markers(block_demo):
    raw = block_demo / "raw"
    files = sorted(p.name for p in raw.iterdir())
    assert len(files) == 18
    for p in raw.iterdir():
        if p.suffix == ".csv":
            assert p.read_text(encoding="utf-8").splitlines()[0].startswith(SYNTHETIC_MARKER)
        else:
            wb = load_workbook(p, read_only=True)
            for ws in wb.worksheets:
                assert next(ws.iter_rows(min_row=1, max_row=1, values_only=True))[0] == SYNTHETIC_MARKER
    for year in C.YEARS[1:]:
        for kind, cols in UDISE_COLUMNS.items():
            header = pd.read_csv(raw / f"udise_{year}_{kind}.csv", skiprows=1, nrows=0).columns.tolist()
            assert header == cols, kind
        enr = pd.read_csv(raw / f"udise_{year}_enr1.csv", skiprows=1, nrows=5)
        assert {"item_group", "item_id", "c1_b", "c1_g", "c8_g"} <= set(enr.columns)


def test_truth_file(block_demo):
    truth = json.loads((block_demo / "truth3.json").read_text(encoding="utf-8"))
    assert truth["truth_version"] == 3 and truth["synthetic"]
    kinds = {s["kind"]: s for s in truth["scenarios"]}
    assert kinds["support_gap"]["expected_actions"] == ["A4", "A5", "A6"]
    assert kinds["staffing_gap"]["expected_actions"] == ["A1", "A3", "A12"]
    assert len(truth["at_risk_clusters"]) == 4 and not set(truth["at_risk_clusters"]) & set(truth["never_at_risk"])
    assert {m["kind"] for m in truth["messiness"]} >= {"udise_leading_zero_loss", "percent_as_text", "exact_duplicates",
                                                       "mixed_date_formats"}


@pytest.mark.slow
def test_deterministic(tmp_path):
    a = generate(7, tmp_path / "a", "fictional")
    b = generate(7, tmp_path / "b", "fictional")
    assert a["raw_files"] == b["raw_files"]


@pytest.mark.slow
@pytest.mark.parametrize("seed", [1, 7, 99, 2026])
def test_planted_signals_hold_on_other_seeds(seed):
    w = build_world(seed)
    change = maths_el_change(w)
    assert change[C.SUPPORT_GAP] <= -6
    assert change[C.SUPPORT_GAP] < change.drop([C.SUPPORT_GAP, C.STAFFING_GAP]).min()
