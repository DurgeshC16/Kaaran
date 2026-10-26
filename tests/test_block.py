"""Block lens (v2): ingest round trip, trust checks and insight engine scored against truth3.json."""

from __future__ import annotations

import pandas as pd
import pytest

from kaaran.block.ingest import ingest_block
from kaaran.block.insights import analyze_block
from kaaran.block.trust import run_block_trust
from kaaran.eval.block import score
from kaaran.synth3.generate import generate


@pytest.fixture(scope="session")
def block_folder(tmp_path_factory):
    out = tmp_path_factory.mktemp("block42")
    generate(42, out)
    return out


@pytest.fixture(scope="session")
def block_run(block_folder):
    ing = ingest_block(block_folder / "raw")
    trust = run_block_trust(ing.tables)
    return ing, trust, analyze_block(ing.tables, trust, "Pandharpur")


def test_ingest_round_trip(block_folder, block_run):
    ing, _, _ = block_run
    clean = {k: pd.read_parquet(block_folder / "clean" / f"{k}.parquet") for k in ("attendance", "assessment", "posts")}
    for name, key, col in (("attendance", ["udise_code", "month"], "attendance_pct"),
                           ("assessment", ["udise_code", "academic_year", "round", "competency"], "pct"),
                           ("posts", ["udise_code", "month"], "working")):
        got, want = ing.tables[name], clean[name]
        assert len(got) == len(want)
        m = got.merge(want, on=key, suffixes=("_i", "_c"))
        assert len(m) == len(want) and (m[f"{col}_i"].astype(float) - m[f"{col}_c"]).abs().max() == 0
    assert len(ing.tables["schools"]) == 1292 and ing.tables["schools"]["cluster_id"].notna().all()
    assert {"src_file", "src_sheet", "src_row"} <= set(ing.tables["assessment"].columns)


def test_ingest_reports_fixes(block_run):
    ing, _, _ = block_run
    kinds = {f["kind"] for f in ing.report["fixes"]}
    assert {"udise_zero_padded", "percent_text_parsed", "exact_duplicates_removed", "mixed_date_formats"} <= kinds
    assert ing.report["synthetic"] and len(ing.report["recognised"]) == 53


def test_trust_flags_and_clears(block_run, block_folder):
    import json

    _, trust, _ = block_run
    truth = json.loads((block_folder / "truth3.json").read_text(encoding="utf-8"))
    sc = {s["kind"]: s for s in truth["scenarios"]}
    flat = set(trust.school_flags.loc[trust.school_flags["rule"] == "TRUST-FLAT", "udise_code"])
    assert set(sc["data_problem"]["schools"]) <= flat
    assert flat <= set(sc["data_problem"]["schools"]) | set(truth["district_noise"]["flat_elsewhere"])  # no false flags
    assert set(sc["honest_low_attendance"]["schools"]) <= set(trust.cleared["udise_code"])
    assert set(trust.cluster_flags["cluster_id"]) == {sc["data_problem"]["cluster"], sc["insufficient_data"]["cluster"]}


def test_insights_match_answer_key(block_folder):
    card = score(block_folder)
    assert card["passed"] == card["total"], {k: v for k, v in card["checks"].items() if not v["ok"]}


def test_staffing_gap_is_strong_with_all_criteria(block_run):
    _, _, an = block_run
    d1 = next(r for r in an.clusters.values() if "D1" in r.checks).checks["D1"]
    assert d1.status == "STRONG" and all(c["passed"] for c in d1.criteria)
    assert an.duty.status == "RULED_OUT" and an.twin["twin"] == "Malshiras" and an.twin["decoy"] == "Sangola"


@pytest.mark.slow
@pytest.mark.parametrize("seed, names", [(7, "fictional"), (2026, "solapur"), (99, "solapur")])
def test_insights_other_seeds(tmp_path, seed, names):
    generate(seed, tmp_path, names)
    card = score(tmp_path)
    assert card["passed"] == card["total"], {k: v for k, v in card["checks"].items() if not v["ok"]}
