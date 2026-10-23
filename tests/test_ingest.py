"""Stage 2 ingest: mapping JSON, messiness handling, round trip vs clean tables, provenance, DuckDB."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import duckdb
import pandas as pd
import pytest
from conftest import EXTRA_SEEDS, load_clean, load_truth

from kaaran.ingest import IngestError, ingest
from kaaran.ingest import normalize as N
from kaaran.ingest.__main__ import main as ingest_cli
from kaaran.ingest.mapping import propose, validate
from kaaran.ingest.readers import csv_rows, pdf_lines, xlsx_rows

ROOT = Path(__file__).resolve().parents[1]
PDF_MONTHS = ["2024-01", "2024-02", "2024-03", "2024-06", "2024-07", "2024-08", "2024-09", "2024-10", "2024-11", "2024-12"]
SEEDS = [pytest.param(42, "solapur", id="seed42")] + [
    pytest.param(s, n, id=f"seed{s}-{n}", marks=pytest.mark.slow) for s, n in EXTRA_SEEDS
]
TOL = 0.05


def fixes(result, kind, file=None, sheet=None, detail=None):
    return sum(f["count"] for f in result.report["fixes"] if f["kind"] == kind and (file is None or f["file"] == file)
               and (sheet is None or f["sheet"] == sheet) and (detail is None or f["detail"] == detail))


def log_items(truth, kind):
    return [m for m in truth["messiness"] if m["kind"] == kind]


# ---------- mapping JSON ----------


def test_rule_based_mapping_matches_committed_baseline(demo_dir):
    committed = json.loads((ROOT / "data" / "samples" / "mapping_baseline.json").read_text(encoding="utf-8"))
    assert propose(demo_dir / "raw") == committed
    assert validate(committed, demo_dir / "raw") == []
    roles = {e["role"] for e in committed["entries"]}
    assert roles == {"school_profile", "enrolment", "infrastructure", "crosswalk", "scores", "teacher_posts",
                     "election_duty", "attendance_pdf"}


@pytest.mark.parametrize(
    "mutate, code",
    [
        (lambda m: m.update(mapping_version=2), "SCHEMA"),
        (lambda m: m["entries"][0].update(role="made_up"), "UNKNOWN_ROLE"),
        (lambda m: m["entries"][3]["fields"]["mean_score"].update(normalizer="eval"), "UNKNOWN_NORMALIZER"),
        (lambda m: m["entries"][3]["fields"].pop("mean_score"), "REQUIRED_FIELD_MISSING"),
        (lambda m: m["entries"][3]["fields"]["mean_score"]["source"].update(col="Average"), "HEADER_NOT_FOUND"),
        (lambda m: m["entries"][3]["fields"].update(colour={"source": {"col": "Std"}, "normalizer": "text"}), "UNKNOWN_FIELD"),
        (lambda m: m["entries"][3]["fields"]["std"]["source"].update(col="Avg_Marks"), "DUPLICATE_TARGET"),
        (lambda m: m["entries"][3]["fields"]["std"].update(source={"section": "taluka"}), "SCHEMA"),
        (lambda m: m["entries"][3]["fields"]["std"].update(source={"regex": ".*"}), "SCHEMA"),
        (lambda m: m["entries"].pop(3), "ROLE_MISSING"),
    ],
)
def test_mapping_validation_rejects_bad_mappings(demo_dir, mutate, code):
    m = copy.deepcopy(propose(demo_dir / "raw"))
    assert m["entries"][3]["role"] == "scores"
    mutate(m)
    errors = validate(m, demo_dir / "raw")
    assert any(e["code"] == code for e in errors), errors
    assert all("value" not in e for e in errors)  # errors describe shapes, never cell values
    with pytest.raises(IngestError):
        ingest(demo_dir / "raw", None, m)


# ---------- messiness handling ----------

# Each messiness kind from the generator's log -> how ingest (or trust) handles it.
EXACT = "exact"
PRESENT = "present"
DOWNSTREAM = "downstream"
HANDLING = {
    "taluka_spelling_variant": (EXACT, "taluka_variant_resolved"),
    "code_stored_as_number": (EXACT, "code_zero_padded"),
    "exact_duplicate_rows": (EXACT, "exact_duplicates_removed"),
    "year_format_short": (EXACT, "year_format_normalized"),
    "year_format_end_year": (EXACT, "year_format_normalized"),
    "year_format_long": (PRESENT, None),
    "subject_label": (EXACT, "subject_label_normalized"),
    "negative_vacancy_convention": (EXACT, "negative_vacancy_recomputed"),
    "date_format": (EXACT, "date_format_parsed"),
    "crosswalk_missing_schools": (EXACT, "link_name_match"),
    "title_rows_and_merged_cells": (PRESENT, "header_row_detected"),
    "marathi_headers": (PRESENT, "marathi_headers_mapped"),
    "header_repeats_each_page": (PRESENT, "pdf_header_repeats_skipped"),
    "utf8_bom_and_title_line": (PRESENT, "bom_removed"),
    "as_on_date_formats": (PRESENT, "date_format_parsed"),
    "rows_omitted": (DOWNSTREAM, "trust: reported as missing months (Stage 3)"),
    "school_name_abbreviated": (DOWNSTREAM, "links are correct (round trip)"),
    "school_name_misspelt": (DOWNSTREAM, "links are correct (round trip)"),
}


@pytest.mark.parametrize("seed, names", SEEDS)
def test_every_messiness_item_is_handled(ingested, seed, names):
    folder, result = ingested(seed, names)
    truth = load_truth(folder)
    kinds = {m["kind"] for m in truth["messiness"]}
    assert kinds <= set(HANDLING), kinds - set(HANDLING)
    for m in truth["messiness"]:
        how, fix = HANDLING[m["kind"]]
        kind, file, sheet = m["kind"], m["file"], m["sheet"]
        if kind == "taluka_spelling_variant":
            assert fixes(result, fix, file, sheet) == m["count"], (kind, sheet)
        elif kind == "code_stored_as_number":
            assert fixes(result, fix, file, sheet) == m["count"]
        elif kind in ("exact_duplicate_rows", "negative_vacancy_convention"):
            assert fixes(result, fix, file) == m["count"], kind
        elif kind == "crosswalk_missing_schools":  # logged on the crosswalk, fixed while linking PDF rows
            assert fixes(result, fix) == m["count"], kind
        elif kind in ("year_format_short", "year_format_end_year"):
            label = "short" if kind.endswith("short") else "bare"
            assert fixes(result, fix, file, detail=f"year format {label}") == m["count"], kind
        elif kind == "subject_label":
            label = m["keys"][0]
            got = fixes(result, fix, file, detail=f"'{label}' -> canonical subject")
            assert got == (0 if label == "Maths" else m["count"]), label
        elif kind == "date_format":
            fmt = m["detail"].removeprefix("dates written as ")
            assert fixes(result, fix, file, detail=f"from_date: {fmt}") == m["count"]
        elif kind == "title_rows_and_merged_cells":
            sheets = {f["sheet"] for f in result.report["fixes"] if f["kind"] == fix and f["file"] == file}
            assert sheets == {"School Profile", "Enrolment", "Infrastructure"}
        elif kind == "utf8_bom_and_title_line":
            assert fixes(result, "bom_removed", file) == 1 and fixes(result, "title_lines_skipped", file) == 1
        elif kind == "as_on_date_formats":
            as_on = [f for f in result.report["fixes"] if f["kind"] == fix and f["detail"].startswith("as_on:")]
            assert len(as_on) >= 3
        elif how == PRESENT and fix:
            assert fixes(result, fix, file) >= 1, kind
    assert fixes(result, "unparsed_values") == 0
    assert fixes(result, "link_unresolved") == 0 and result.report["unresolved_rows"] == 0
    assert result.report["synthetic"] is True
    assert all(s["synthetic"] and s["marker_at"] for s in result.report["sources"])


def test_bare_year_convention_is_detected_from_the_data():
    years = pd.Series(["2023-24", "2024", "23-24", "2025"])
    keys = pd.Series(["a", "b", "c", "a"])
    values, stats = N.academic_year(years, keys)
    assert list(values) == ["2023-24", "2023-24", "2023-24", "2024-25"] and stats["bare_year_convention"] == "end"
    # If END-year reading collides, START-year wins.
    values, stats = N.academic_year(pd.Series(["2023-24", "2024"]), pd.Series(["a", "a"]))
    assert stats["bare_year_convention"] == "start" and list(values) == ["2023-24", "2024-25"]


def test_date_order_uses_partner_column():
    frm = pd.Series(["01/10/2024", "2024-11-01"])
    to = pd.Series(["31/10/2024", "2024-11-30"])
    values, stats = N.dates(frm, to)
    assert [str(v) for v in values] == ["2024-10-01", "2024-11-01"]
    assert stats["unparsed"] == 0


# ---------- round trip vs clean tables ----------


def _match(expected: pd.DataFrame, got: pd.DataFrame, keys: list[str], exact: list[str], close: list[str]) -> float:
    merged = expected.merge(got, on=keys, how="left", suffixes=("_c", "_i"), indicator=True)
    ok = merged["_merge"] == "both"
    for c in exact:
        ok &= merged[f"{c}_c"].astype(str) == merged[f"{c}_i"].astype(str)
    for c in close:
        ok &= (merged[f"{c}_c"].astype(float) - merged[f"{c}_i"].astype(float)).abs() <= TOL
    extra = len(got.merge(expected[keys], on=keys, how="left", indicator=True).query("_merge == 'left_only'"))
    assert extra == 0, f"{extra} ingested rows have no clean counterpart"
    return float(ok.mean())


@pytest.mark.parametrize("seed, names", SEEDS)
def test_round_trip_matches_clean_tables(ingested, seed, names):
    folder, result = ingested(seed, names)
    clean, truth, t = load_clean(folder), load_truth(folder), result.tables
    tid = "T" + clean["talukas"].set_index("taluka_key")["block_code"]
    taluka_id = clean["schools"].set_index("udise_code")["taluka_key"].map(tid)

    ct = clean["talukas"].assign(taluka_id="T" + clean["talukas"]["block_code"])
    assert _match(ct, t["talukas"], ["taluka_id"], ["taluka", "taluka_mr", "n_schools"], []) == 1.0

    cs = clean["schools"].assign(taluka_id=clean["schools"]["udise_code"].map(taluka_id))
    cols = ["short_code", "school_name", "village", "taluka_id", "cluster_code", "cluster", "enrol_std1", "enrol_std2",
            "enrol_std3", "enrol_std4", "enrol_std5", "enrol_total", "toilets", "library", "drinking_water", "classrooms"]
    assert _match(cs, t["schools"], ["udise_code"], cols, []) >= 0.99

    sc = clean["scores"].assign(subject=clean["scores"]["subject"].str.lower(), taluka_id=clean["scores"]["udise_code"].map(taluka_id))
    assert _match(sc, t["scores"], ["udise_code", "academic_year", "subject"], ["taluka_id", "std", "students_appeared"],
                  ["mean_score"]) >= 0.99

    omitted = {tuple(k.split("|")) for m in truth["messiness"] if m["kind"] == "rows_omitted" for k in m["keys"]}
    ca = clean["attendance"][clean["attendance"]["month"].isin(PDF_MONTHS)]
    ca = ca[[(c, m) not in omitted for c, m in zip(ca["udise_code"], ca["month"])]]
    ca = ca.assign(taluka_id=ca["udise_code"].map(taluka_id))
    assert _match(ca, t["attendance"], ["udise_code", "month"], ["academic_year", "taluka_id", "enrolled"],
                  ["attendance_pct", "present_avg"]) >= 0.99

    tp = clean["teacher_posts"].assign(taluka_id=clean["teacher_posts"]["udise_code"].map(taluka_id))
    assert _match(tp, t["teacher_posts"], ["udise_code", "academic_year", "subject"], ["taluka_id", "sanctioned", "working"], []) >= 0.99

    ed = clean["election_duty"].assign(taluka_id=clean["election_duty"]["taluka_key"].map(tid))
    assert _match(ed, t["election_duty"], ["taluka_id", "month"], ["academic_year"], ["deployed_pct"]) >= 0.99


# ---------- provenance ----------


def _xlsx_value(path, sheet, row, header_row, header):
    rows = xlsx_rows(path)[sheet]
    return rows[row - 1][list(rows[header_row - 1]).index(header)]


def test_provenance_points_at_source_cells(ingested):
    folder, result = ingested(42, "solapur")
    raw = folder / "raw"
    src = {s["id"]: s["file"] for s in result.report["sources"]}
    entries = {(e["role"], e["sheet"]): e for e in result.mapping["entries"]}

    schools = result.tables["schools"].sample(25, random_state=1)
    e = entries[("school_profile", "School Profile")]
    for r in schools.itertuples():
        assert src[r.src_id] == "udise_2023.xlsx" and r.src_sheet == "School Profile"
        assert _xlsx_value(raw / "udise_2023.xlsx", "School Profile", r.src_row, e["read"]["header_row"], "UDISE Code") == r.udise_code
        enrol = entries[("enrolment", "Enrolment")]
        value = _xlsx_value(raw / "udise_2023.xlsx", "Enrolment", r.src_row_enrolment, enrol["read"]["header_row"], "UDISE Code")
        assert str(value).zfill(11) == r.udise_code  # re-apply the logged normalizer (zero-padding)

    _, _, lines = csv_rows(raw / "pat_scores.csv")
    header = list(lines[1])
    for r in result.tables["scores"].sample(25, random_state=2).itertuples():
        assert src[r.src_id] == "pat_scores.csv"
        cells = dict(zip(header, lines[r.src_row - 1]))
        assert cells["SCHOOL_CD"] == r.udise_code and abs(float(cells["Avg_Marks"]) - r.mean_score) < 1e-9

    by_page = {}
    for page, _, text in pdf_lines(raw / "attendance_jan-dec.pdf"):
        by_page.setdefault(page, []).append(text)
    for r in result.tables["attendance"].sample(25, random_state=3).itertuples():
        assert src[r.src_id] == "attendance_jan-dec.pdf" and r.src_section.endswith(r.month)
        assert any(t.startswith(f"{r.src_row} ") and r.short_code in t and t.endswith(f"{r.attendance_pct:.1f}")
                   for t in by_page[r.src_page])

    posts = result.tables["teacher_posts"].sample(25, random_state=4)
    e = entries[("teacher_posts", "*")]
    for r in posts.itertuples():
        assert r.src_sheet == r.academic_year
        assert _xlsx_value(raw / "teacher_posts.xlsx", r.src_sheet, r.src_row, e["read"]["header_row"], "Working") == r.working


def test_duckdb_tables_written(ingested):
    _, result = ingested(42, "solapur")
    con = duckdb.connect(result.db_path, read_only=True)
    try:
        names = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        assert {"talukas", "schools", "scores", "attendance", "teacher_posts", "election_duty", "school_links",
                "ingest_fixes", "ingest_unresolved", "sources"} <= names
        for name, n in result.report["tables"].items():
            assert con.execute(f"SELECT count(*) FROM {name}").fetchone()[0] == n
        nulls = con.execute("SELECT count(*) FROM attendance WHERE src_page IS NULL OR src_section IS NULL OR src_row IS NULL").fetchone()[0]
        assert nulls == 0
        mean = con.execute("SELECT avg(mean_score) FROM scores WHERE taluka_id = 'T08' AND academic_year = '2025-26'").fetchone()[0]
        assert mean == pytest.approx(52.69, abs=0.05)
    finally:
        con.close()


def test_ingest_cli(demo_dir, tmp_path, capsys):
    db = tmp_path / "kaaran.duckdb"
    assert ingest_cli([str(demo_dir / "raw"), "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "SYNTHETIC" in out and db.exists() and (tmp_path / "ingest_report.json").exists()


def test_name_matching_is_one_to_one_for_near_identical_names():
    """Regression (seeds 1 and 2): two crosswalk gaps in one taluka with near-identical names must both link."""
    from kaaran.ingest.pipeline import FixLog, _link_attendance

    schools = pd.DataFrame({"udise_code": ["00990514801", "00990518601", "00990510101"],
                            "school_name": ["ZP Primary School Palewadi", "ZP Primary School Palwad", "ZP Primary School Khandwadi"],
                            "taluka_id": ["T05", "T05", "T05"], "enrol_total": [108, 109, 60]})
    att = pd.DataFrame({"short_code": ["SC74534", "SC15731", "SC00001"],
                        "school_name": ["ZP Primary School Palewadi", "ZPPS Palwad", "ZP Primary School Khandwadi"],
                        "taluka_id": ["T05", "T05", "T05"], "enrolled": [108, 109, 60]})
    crosswalk = pd.DataFrame({"short_code": ["SC00001"], "udise_code": ["00990510101"]})
    log = FixLog()
    links = _link_attendance(att, crosswalk, schools, "attendance.pdf", log).set_index("short_code")["udise_code"].to_dict()
    assert links == {"SC00001": "00990510101", "SC74534": "00990514801", "SC15731": "00990518601"}
    assert log.total("link_unresolved") == 0
