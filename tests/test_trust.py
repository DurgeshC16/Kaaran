"""Stage 3 trust checks, run on data ingested from the RAW files (not the clean tables)."""

from __future__ import annotations

import pandas as pd
import pytest
from conftest import EXTRA_SEEDS, load_truth

from kaaran import evidence as E
from kaaran.ingest.__main__ import main as ingest_cli
from kaaran.trust import as_pack, run_trust
from kaaran.trust import rules as R
from kaaran.trust.__main__ import main as trust_cli

SEEDS = [pytest.param(42, "solapur", id="seed42")] + [
    pytest.param(s, n, id=f"seed{s}-{n}", marks=pytest.mark.slow) for s, n in EXTRA_SEEDS
]


@pytest.fixture(scope="session")
def trusted(ingested):
    cache = {}

    def get(seed, names):
        if (seed, names) not in cache:
            folder, result = ingested(seed, names)
            cache[(seed, names)] = (folder, result, run_trust(result.tables, result.report))
        return cache[(seed, names)]

    return get


def truths(folder):
    return {t["id"]: t for t in load_truth(folder)["truths"]}


def taluka_id(result, name):
    t = result.tables["talukas"]
    return t.loc[t["taluka"] == name, "taluka_id"].item()


@pytest.mark.parametrize("seed, names", SEEDS)
def test_t5_every_flat_school_flagged_and_concentration_in_focus(trusted, seed, names):
    folder, ing, tr = trusted(seed, names)
    t5 = truths(folder)["T5"]
    planted = set(t5["entities"]["schools"]) | set(t5["entities"]["scattered_schools"])
    flat = tr.flags[tr.flags["rule_id"] == "TRUST-FLAT-SCHOOL"]
    assert set(flat["entity_id"]) == planted
    assert (flat["value"] >= R.FLAT_RUN_MIN_MONTHS).all()
    focus = taluka_id(ing, t5["entities"]["talukas"][0])
    assert tr.report["red_flag_talukas"] == [focus]
    finding = next(f for f in tr.fragment["findings"] if f["rule_id"] == "TRUST-FLAT-TALUKA")
    assert {m[1:] for m in tr.fragment["entity_sets"][finding["params"]["schools"]["set"]]["members"]} == set(t5["entities"]["schools"])
    assert tr.fragment["periods"][finding["params"]["months"]["period"]] == {"kind": "month_range", "from": "2024-08", "to": "2024-11"}


@pytest.mark.parametrize("seed, names", SEEDS)
def test_t8_honest_low_attendance_never_flagged(trusted, seed, names):
    folder, _, tr = trusted(seed, names)
    t = truths(folder)
    honest = set(t["T8"]["entities"]["schools"])
    flat = set(t["T5"]["entities"]["schools"]) | set(t["T5"]["entities"]["scattered_schools"])
    assert not (honest & tr.flagged_schools())
    assert not (honest & set(tr.flags["entity_id"]))  # not even a jump flag
    assert honest <= set(tr.cleared)
    assert not (flat & set(tr.cleared))


@pytest.mark.parametrize("seed, names", SEEDS)
def test_t6_reported_as_insufficient(trusted, seed, names):
    folder, ing, tr = trusted(seed, names)
    t6 = truths(folder)["T6"]
    sparse = taluka_id(ing, t6["entities"]["talukas"][0])
    assert tr.report["insufficient_talukas"] == [sparse]
    missing = tr.flags[tr.flags["rule_id"] == "TRUST-MISSING-SCHOOL"]
    assert set(missing["entity_id"]) == set(t6["entities"]["schools"])
    share = tr.talukas.set_index("taluka_id")["insufficient_share"]
    assert share[sparse] >= R.TALUKA_INSUFFICIENT_SHARE and share.drop(sparse).max() < 0.10


@pytest.mark.parametrize("seed, names", SEEDS)
def test_omitted_rows_and_duplicates_are_reported(trusted, seed, names):
    folder, _, tr = trusted(seed, names)
    truth = load_truth(folder)
    omitted = {tuple(k.split("|")) for m in truth["messiness"] if m["kind"] == "rows_omitted" for k in m["keys"]}
    reported = set(zip(tr.missing["udise_code"], tr.missing["month"]))
    assert omitted <= reported
    dups = sum(m["count"] for m in truth["messiness"] if m["kind"] == "exact_duplicate_rows")
    assert tr.report["exact_duplicates_removed_at_ingest"] == dups
    assert tr.report["conflicting_duplicates"] == 0


def test_trust_findings_are_valid_evidence(trusted):
    _, ing, tr = trusted(42, "solapur")
    pack = as_pack(tr.fragment, ing.report, focus="T08")
    assert E.validate(pack) == []
    labels = {(f["rule_id"], f["label"]) for f in pack["findings"]}
    assert ("TRUST-FLAT-TALUKA", "RED_FLAG") in labels and ("TRUST-INSUFFICIENT-TALUKA", "INSUFFICIENT") in labels
    assert E.contains_identifiers(E.llm_view(pack)) == []
    for p in tr.flags["provenance"]:
        assert p.startswith("[")


# ---------- rule unit tests on toy data ----------


def _att(series: dict[str, list[tuple[str, float]]]) -> pd.DataFrame:
    return pd.DataFrame([(c, "T01", m, v) for c, rows in series.items() for m, v in rows],
                        columns=["udise_code", "taluka_id", "month", "attendance_pct"])


def test_flat_run_needs_consecutive_months():
    att = _att({
        "a": [("2024-06", 100.0), ("2024-07", 100.0), ("2024-08", 100.0)],
        "b": [("2024-06", 100.0), ("2024-07", 100.0), ("2024-09", 100.0)],  # gap breaks the run
        "c": [("2024-03", 100.0), ("2024-06", 100.0), ("2024-07", 100.0)],  # vacation (Apr-May) breaks it too
    })
    assert list(R.flat_runs(att)["udise_code"]) == ["a"]


def test_attendance_jump_uses_own_history():
    months = ["2024-01", "2024-02", "2024-03", "2024-06", "2024-07", "2024-08", "2024-09", "2024-10"]
    steady = [86.0, 86.5, 85.8, 86.2, 85.9, 86.3, 86.1, 86.0]
    noisy = [80.0, 84.0, 77.0, 83.0, 75.0, 82.0, 76.0, 84.0]  # swings of ~7 pp are this school's normal
    spiky = [86.0, 86.5, 85.8, 99.0, 85.9, 86.3, 86.1, 86.0]  # one 13 pp jump
    att = _att({"steady": list(zip(months, steady)), "noisy": list(zip(months, noisy)), "spiky": list(zip(months, spiky))})
    hits = R.attendance_jumps(att)
    assert set(hits["udise_code"]) == {"spiky"}


def test_score_jumps_classified_spike_persisting_unconfirmed():
    rows = []
    years = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]
    for i in range(200):  # background schools with ordinary noise
        for j, y in enumerate(years):
            rows.append((f"bg{i:03d}", y, 55 + ((i * 7 + j * 3) % 9) - 4, 25))
    rows += [("spike", y, v, 25) for y, v in zip(years, [55, 56, 90, 55, 56])]
    rows += [("shift", y, v, 25) for y, v in zip(years, [55, 56, 25, 24, 25])]
    rows += [("late", y, v, 25) for y, v in zip(years, [55, 56, 55, 56, 90])]
    scores = pd.DataFrame(rows, columns=["udise_code", "academic_year", "mean_score", "students_appeared"])
    got = R.score_jumps(scores)
    status = dict(zip(got["udise_code"] + "|" + got["academic_year"], got["status"]))
    assert status["spike|2023-24"] == "spike" and status["shift|2023-24"] == "persisting" and status["late|2025-26"] == "unconfirmed"
    assert not got["udise_code"].str.startswith("bg").any()


def test_cleared_picks_lowest_unflagged_schools():
    months = [f"2024-{m:02d}" for m in (1, 2, 3, 6, 7, 8, 9, 10)]
    series = {f"s{i:02d}": [(m, 85.0 + i * 0.1) for m in months] for i in range(40)}
    series["flagged_low"] = [(m, 70.0) for m in months]
    series["short_low"] = [(m, 71.0) for m in months[:5]]  # too few months to judge
    got = R.cleared(_att(series), flagged={"flagged_low"})
    assert got == ["s00", "s01", "s02"]  # ceil(5% of 42) = 3


def test_trust_cli(demo_dir, tmp_path, capsys):
    db = tmp_path / "kaaran.duckdb"
    assert ingest_cli([str(demo_dir / "raw"), "--db", str(db)]) == 0
    assert trust_cli(["--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "Pandharpur" in out and "Mangalvedha" in out
    assert (tmp_path / "trust_report.json").exists() and (tmp_path / "trust_evidence.json").exists()
    assert E.validate(E.load(tmp_path / "trust_evidence.json")) == []
