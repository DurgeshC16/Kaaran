"""Real-data module on a tiny FAKE file set in the real UDISE+ microdata format (real data never enters tests or git)."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from kaaran.real.udise import RealDataError, cross_check_aikosh, load_microdata, snapshot, validate, write_report


def write_fake(folder, bad_ids=False):
    folder.mkdir(parents=True, exist_ok=True)
    schools = [  # pseudocode, block, management, category, teachers, crc visits, non-teaching, pupils per class (1-5)
        (101, "ALPHA", 3, 1, 1, 0, 0, 8), (102, "ALPHA", 3, 1, 2, 6, 1, 20),
        (103, "ALPHA", 4, 2, 9, 3, 0, 40), (201, "BETA", 3, 2, 3, 0, 2, 7), (202, "BETA", 3, 1, 0, 2, 0, 5),
    ]
    pd.DataFrame([{"pseudocode": c, "district": "TESTDIST", "block": b, "managment": m, "school_category": cat,
                   "lowclass": 1, "highclass": 5, "rural_urban": 1} for c, b, m, cat, *_ in schools]).to_csv(folder / "9999_prof1.csv", index=False)
    pd.DataFrame([{"pseudocode": c, "crc_coordinator": v, "block_level_officers": 1, "acad_inspections": 1}
                  for c, _b, _m, _c, _t, v, _n, _p in schools]).to_csv(folder / "9999_prof2.csv", index=False)
    tch = [{"pseudocode": c, "total_tch": t, "contract": 0, "teacher_involve_non_training_assignment": n}
           for c, _b, _m, _c, t, _v, n, _p in schools]
    if bad_ids:
        tch[0]["pseudocode"] = 999
    pd.DataFrame(tch).to_csv(folder / "9999_tch.csv", index=False)
    rows = []
    for c, *_rest, per in schools:
        row = {"pseudocode": c, "item_group": 1, "item_id": 1}
        for i in range(1, 9):
            row[f"c{i}_b"], row[f"c{i}_g"] = (per // 2, per - per // 2) if i <= 5 else (0, 0)
        rows.append(row)
        rows.append({**row, "item_group": 2, "item_id": 5})  # religion rows must not be double counted
    pd.DataFrame(rows).to_csv(folder / "9999_enr1.csv", index=False)
    return folder


def test_snapshot_counts(tmp_path):
    snap = snapshot(load_microdata(write_fake(tmp_path / "u")))
    b = snap.blocks
    assert set(b.index) == {"ALPHA", "BETA"} and int(b.loc["ALPHA", "schools"]) == 2  # management 4 excluded
    assert int(b.loc["ALPHA", "single_teacher"]) == 1 and int(b.loc["BETA", "zero_teacher"]) == 1
    assert int(b.loc["ALPHA", "pupils"]) == 8 * 5 + 20 * 5  # classes 1-5, item_group 1 only
    assert int(b.loc["ALPHA", "ptr_over_30"]) == 2  # 40 pupils / 1 teacher and 100 / 2 (the aided school is excluded)
    assert int(b.loc["BETA", "no_crc_visit"]) == 1 and snap.totals["schools"] == 4
    assert all(c["ok"] for c in snap.checks)


def test_inconsistent_files_are_refused(tmp_path):
    t = load_microdata(write_fake(tmp_path / "u", bad_ids=True))
    assert any(not c["ok"] for c in validate(t))
    with pytest.raises(RealDataError):
        snapshot(t)


def test_report_is_aggregate_only(tmp_path):
    snap = snapshot(load_microdata(write_fake(tmp_path / "u")))
    aik = tmp_path / "aikosh.csv"
    pd.DataFrame([{"Block_Name": "ALPHA", "School_Management_Name": "Local body", "Total_Teacher": 3},
                  {"Block_Name": "BETA", "School_Management_Name": "Local body", "Total_Teacher": 3}]).to_csv(aik, index=False)
    cross_check_aikosh(snap, aik)
    j, m = write_report(snap, tmp_path / "out", {"districts": {"X": {"maths": 70, "language": 75, "page": 15}},
                                                  "state": {"maths": 64, "language": 69}, "india": {"maths": 60, "language": 64}})
    text = j.read_text(encoding="utf-8") + m.read_text(encoding="utf-8")
    assert "REAL" in text and "101" not in json.dumps(json.loads(j.read_text(encoding="utf-8"))["blocks"])
    assert "| ALPHA | 2 |" in m.read_text(encoding="utf-8")
    assert snap.checks[-1]["id"] == "local_body_mapping_vs_2019_20" and snap.checks[-1]["ok"]
