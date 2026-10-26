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


# ---------- rubric, pack and three-part brief ----------


@pytest.fixture(scope="session")
def block_pack(block_folder, block_run):
    from kaaran.block.pack import build_block_pack

    ing, trust, _ = block_run
    return build_block_pack(block_folder / "raw", "Pandharpur", ing=ing, trust=trust)


def test_rubric_actions_match_answer_key(block_folder, block_pack):
    card = score(block_folder, block_pack["actions_by_cluster"])
    assert card["passed"] == card["total"] == 19, {k: v for k, v in card["checks"].items() if not v["ok"]}
    assert any(r["action"] == "A2" and r["constraint"] == "no_surplus_school" for r in block_pack["rubric_log"])


def test_pack_is_valid_and_traceable(block_pack):
    from kaaran.block.pack import validate_block_pack

    assert validate_block_pack(block_pack) == []
    assert [o["section"] for o in block_pack["outline"]] == ["attention", "why", "action", "appendix"]
    assert all(n["provenance"] for n in block_pack["numbers"].values())
    query = [p for n in block_pack["numbers"].values() for p in n["provenance"] if p["kind"] == "query"]
    files = {s["id"] for s in block_pack["sources"]}
    assert query and all(p["source"] in files and p["n_rows"] > 0 for p in query)
    actions = [f for f in block_pack["findings"] if f["type"] == "ACTION"]
    assert actions and all(f["action"]["within_officer_powers"] and f["action"]["rubric_id"] for f in actions)


def test_template_brief_verifies(block_pack):
    from kaaran.block.brief import write_block_brief

    b = write_block_brief(block_pack, use_llm=False)
    assert b.info["verification"]["passed"], b.info["verification"]
    for lang, heading in (("mr", "## लक्ष देण्याची गरज"), ("en", "## What to do")):
        assert heading in b.markdown[lang] and "SYNTHETIC" in b.markdown[lang]
    school_names = [e["name_en"] for e in block_pack["entities"].values() if e["kind"] == "school"]
    assert not any(n in b.markdown["en"] for n in school_names)


def test_recorded_llm_brief_replays_and_verifies(block_pack):
    from kaaran.block.brief import write_block_brief

    b = write_block_brief(block_pack)  # replays the recorded Sonnet response
    assert b.info["llm_available"] and b.info["verification"]["passed"]
    assert all(s.startswith("llm") for s in b.sources.values())


def test_html_fragment_and_print(block_pack):
    from kaaran.block.brief import block_fragment, block_print_document, write_block_brief

    b = write_block_brief(block_pack, use_llm=False)
    frag = block_fragment(block_pack, b.prose, "mr", b.sources)
    assert "A · लक्ष देण्याची गरज" in frag and 'class="num"' in frag and 'class="set"' in frag
    doc = block_print_document(block_pack, b.prose, "en", b.sources)
    assert "C · What to do" in doc and 'class="num"' not in doc and "Other checks" not in doc
