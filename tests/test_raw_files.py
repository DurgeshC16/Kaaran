"""Raw files open with standard readers and contain the planted messiness recorded in the log."""

from __future__ import annotations

import difflib
import hashlib
import json
import re

import openpyxl
import pandas as pd
import pdfplumber
import pytest
from openpyxl.utils import get_column_letter

RAW_FILES = [
    "udise_2023.xlsx",
    "attendance_jan-dec.pdf",
    "crosswalk.xlsx",
    "pat_scores.csv",
    "teacher_posts.xlsx",
    "election_duty.csv",
    "taluka_profile.csv",
]
PDF_MONTHS = ["2024-01", "2024-02", "2024-03", "2024-06", "2024-07", "2024-08", "2024-09", "2024-10", "2024-11", "2024-12"]
MONTH_NUM = {name: i for i, name in enumerate(
    ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
     "November", "December"])}
HEADING = re.compile(r"^Monthly attendance summary - (\w+) (\d{4}) - Taluka: (.+)$")
ROW = re.compile(r"^(\d+) (.+) (SC\d{5}) (\d+) (\d+\.\d) (\d+\.\d)$")
TABLE_HEADER = "Sr No School Name Short Code Enrolled Present Avg %"


def log_items(gt, file, kind=None, sheet=None):
    return [m for m in gt["messiness"] if m["file"] == file and (kind is None or m["kind"] == kind)
            and (sheet is None or m["sheet"] == sheet)]


def log_count(gt, file, kind, sheet=None):
    items = log_items(gt, file, kind, sheet)
    assert items, f"no log entry {file}/{kind}/{sheet}"
    return sum(m["count"] for m in items)


@pytest.fixture(scope="session")
def raw(demo_dir):
    return demo_dir / "raw"


@pytest.fixture(scope="session")
def pdf_pages(raw) -> list[str]:
    with pdfplumber.open(raw / "attendance_jan-dec.pdf") as pdf:
        return [page.extract_text() or "" for page in pdf.pages]


@pytest.fixture(scope="session")
def pdf_rows(pdf_pages) -> pd.DataFrame:
    """Parse the attendance PDF; a section heading carries over to continuation pages."""
    rows, taluka, month = [], None, None
    for text in pdf_pages:
        for line in text.splitlines():
            if m := HEADING.match(line):
                month = f"{m.group(2)}-{MONTH_NUM[m.group(1)]:02d}"
                taluka = m.group(3)
            elif m := ROW.match(line):
                rows.append((taluka, month, int(m.group(1)), m.group(2), m.group(3), int(m.group(4)),
                             float(m.group(5)), float(m.group(6))))
    return pd.DataFrame(rows, columns=["taluka", "month", "sr", "name", "short_code", "enrolled", "present", "pct"])


@pytest.fixture(scope="session")
def profile(raw) -> pd.DataFrame:
    return pd.read_excel(raw / "udise_2023.xlsx", sheet_name="School Profile", header=3, dtype={"UDISE Code": str})


@pytest.fixture(scope="session")
def crosswalk(raw) -> pd.DataFrame:
    return pd.read_excel(raw / "crosswalk.xlsx", header=2, dtype=str)


# ---------- generic ----------


def test_raw_files_exist_and_open(raw):
    for name in RAW_FILES:
        assert (raw / name).stat().st_size > 0
    for name in ("udise_2023.xlsx", "crosswalk.xlsx", "teacher_posts.xlsx"):
        openpyxl.load_workbook(raw / name, read_only=True).close()
    assert len(pd.read_csv(raw / "pat_scores.csv", skiprows=1, encoding="utf-8-sig")) > 6000
    assert len(pd.read_csv(raw / "election_duty.csv", skiprows=1)) > 0


def test_every_file_carries_synthetic_marker(raw, demo_dir):
    for name in ("udise_2023.xlsx", "crosswalk.xlsx", "teacher_posts.xlsx"):
        wb = openpyxl.load_workbook(raw / name)
        assert "SYNTHETIC" in wb.properties.title
        for ws in wb.worksheets:
            assert "SYNTHETIC" in str(ws["A1"].value)
    for name in ("pat_scores.csv", "election_duty.csv", "taluka_profile.csv"):
        first = (raw / name).read_text(encoding="utf-8-sig").splitlines()[0]
        assert "SYNTHETIC" in first
    for name in ("ground_truth.json", "manifest.json"):
        assert json.loads((demo_dir / name).read_text(encoding="utf-8"))["synthetic"] is True


@pytest.mark.slow
def test_every_pdf_page_carries_synthetic_marker(pdf_pages):
    assert all("SYNTHETIC" in page for page in pdf_pages)


def test_messiness_log_covers_every_raw_file(gt):
    files = {m["file"] for m in gt["messiness"]}
    assert files == set(RAW_FILES)
    for m in gt["messiness"]:
        assert m["kind"] and m["detail"] and m["count"] >= 0


def test_manifest_hashes_match_files(demo_dir):
    manifest = json.loads((demo_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["synthetic"] is True and isinstance(manifest["seed"], int)
    expected = {f"raw/{n}" for n in RAW_FILES} | {"ground_truth.json"}
    assert expected <= set(manifest["files"])
    for rel, entry in manifest["files"].items():
        data = (demo_dir / rel).read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]
        assert len(data) == entry["bytes"]
    assert "pandas" in manifest["library_versions"]


# ---------- 1. udise_2023.xlsx ----------


def test_udise_workbook_messiness(raw, gt, clean, profile):
    file = "udise_2023.xlsx"
    wb = openpyxl.load_workbook(raw / file)
    assert wb.sheetnames == ["School Profile", "Enrolment", "Infrastructure"]
    for ws in wb.worksheets:
        merged = {str(r) for r in ws.merged_cells.ranges}
        last = get_column_letter(ws.max_column)
        assert {f"A{i}:{last}{i}" for i in (1, 2, 3)} <= merged  # 3 merged title rows
    assert any(str(r).startswith("D4:") for r in wb["Enrolment"].merged_cells.ranges)  # merged group header

    # Mixed-case headers; Marathi headers on one sheet.
    assert {"school NAME", "TALUKA", "cluster code"} <= set(profile.columns)
    infra = pd.read_excel(raw / file, sheet_name="Infrastructure", header=3, dtype={"यूडायस कोड": str})
    assert {"यूडायस कोड", "तालुका", "ग्रंथालय"} <= set(infra.columns)
    assert set(infra["ग्रंथालय"]) == {"होय", "नाही"}

    # Codes: text with leading zeros in two sheets, numbers with zeros lost in Enrolment.
    assert profile["UDISE Code"].str.fullmatch(r"00\d{9}").all()
    assert infra["यूडायस कोड"].str.fullmatch(r"00\d{9}").all()
    enrol = pd.read_excel(raw / file, sheet_name="Enrolment", header=4)
    assert pd.api.types.is_integer_dtype(enrol["UDISE Code"])
    assert (enrol["UDISE Code"].astype(str).str.len() == 9).all()
    assert set(enrol["UDISE Code"].astype(str).str.zfill(11)) == set(clean["schools"]["udise_code"])

    # Taluka spelling variants in about 8% of rows per sheet.
    canonical = set(clean["talukas"]["taluka"])
    for sheet, frame, col in (("School Profile", profile, "TALUKA"), ("Enrolment", enrol, "Taluka"),
                              ("Infrastructure", infra, "तालुका")):
        variants = frame[~frame[col].isin(canonical)]
        assert len(variants) == log_count(gt, file, "taluka_spelling_variant", sheet)
        assert 0.06 <= len(variants) / len(frame) <= 0.10
        assert variants[col].str.contains(r"[ऀ-ॿ]").any()  # some in Devanagari
    focus = clean["talukas"].set_index("taluka_key").loc["pandharpur", "taluka"]
    if focus == "Pandharpur":
        assert set(profile["TALUKA"]) & {"Pandharpoor", "Pandharpura", "पंढरपूर"}


# ---------- 2. attendance_jan-dec.pdf ----------


@pytest.mark.slow
def test_attendance_pdf_structure(pdf_pages, pdf_rows, gt, clean, demo_dir):
    file = "attendance_jan-dec.pdf"
    pages_with_rows = [p for p in pdf_pages if any(ROW.match(line) for line in p.splitlines())]
    assert len(pages_with_rows) > 100
    assert all(TABLE_HEADER in p for p in pages_with_rows)  # header repeats on every page
    continuation = [p for p in pages_with_rows if not any(HEADING.match(line) for line in p.splitlines())]
    assert continuation  # tables run over pages; only the header row repeats, not the section heading
    assert sorted(pdf_rows["month"].unique()) == PDF_MONTHS
    assert set(pdf_rows["taluka"]) == set(clean["talukas"]["taluka"])

    manifest = json.loads((demo_dir / "manifest.json").read_text(encoding="utf-8"))
    assert len(pdf_rows) == manifest["files"][f"raw/{file}"]["rows"]
    window = clean["attendance"][clean["attendance"]["month"].isin(PDF_MONTHS)]
    omitted = log_count(gt, file, "rows_omitted")
    assert len(pdf_rows) == len(window) - omitted
    assert 0.005 <= omitted / len(window) <= 0.015

    # Some schools missing in some months; T6 gaps and T5 flat runs are visible in the PDF.
    per_section = pdf_rows.groupby(["taluka", "month"]).size()
    n_schools = clean["talukas"].set_index("taluka")["n_schools"]
    assert (per_section < n_schools.reindex(per_section.index.get_level_values("taluka")).to_numpy()).any()
    truths = {t["id"]: t for t in gt["truths"]}
    short = clean["schools"].set_index("udise_code")["short_code"]
    flat_focus = set(short[truths["T5"]["entities"]["schools"]])
    flat_rows = pdf_rows[pdf_rows["pct"] == 100.0]
    focus_flat = flat_rows[flat_rows["short_code"].isin(flat_focus)]
    assert set(focus_flat["short_code"]) == flat_focus
    assert set(focus_flat["month"]) == set(truths["T5"]["expected"]["focus_months"])


@pytest.mark.slow
def test_attendance_pdf_names_are_messy(pdf_rows, gt, clean):
    file = "attendance_jan-dec.pdf"
    names = clean["schools"].set_index("short_code")["school_name"]
    printed = pdf_rows.drop_duplicates("short_code").set_index("short_code")["name"]
    differs = (printed != names.reindex(printed.index)).sum()
    logged = log_count(gt, file, "school_name_abbreviated") + log_count(gt, file, "school_name_misspelt")
    assert differs > 0.25 * len(printed)
    assert differs <= logged  # a few logged schools may be absent from the PDF
    assert printed.str.startswith("ZPPS").any()


# ---------- 3. crosswalk.xlsx + join ----------


def normalise(name: str) -> str:
    name = name.lower().replace(".", "").replace(",", "")
    name = re.sub(r"\bzpps\b", "zp primary school", name)
    name = re.sub(r"\bps\b", "primary school", name)
    name = re.sub(r"\bno(\d)", r"no \1", name)
    return " ".join(name.split())


@pytest.mark.slow
def test_crosswalk_join_and_fuzzy_fallback(pdf_rows, crosswalk, profile, gt, clean):
    file = "crosswalk.xlsx"
    assert {"Short Code", "UDISE Code"} <= set(crosswalk.columns)
    coverage = len(crosswalk) / len(clean["schools"])
    assert 0.96 <= coverage <= 0.98
    assert len(clean["schools"]) - len(crosswalk) == log_count(gt, file, "crosswalk_missing_schools")

    joined = pdf_rows["short_code"].isin(crosswalk["Short Code"])
    assert 0.95 <= joined.mean() < 1.0

    # The rest can be matched by fuzzy name matching within the taluka (block code is in the UDISE code).
    block_to_taluka = clean["talukas"].set_index("block_code")["taluka"]
    prof = profile.assign(block_taluka=profile["UDISE Code"].str[4:6].map(block_to_taluka))
    truth = clean["schools"].set_index("short_code")["udise_code"]
    unmatched = pdf_rows.loc[~joined].drop_duplicates("short_code")
    correct = 0
    for _, row in unmatched.iterrows():
        cands = prof[prof["block_taluka"] == row["taluka"]]
        by_norm = {normalise(n): c for n, c in zip(cands["school NAME"], cands["UDISE Code"])}
        best = difflib.get_close_matches(normalise(row["name"]), list(by_norm), n=1, cutoff=0.6)
        correct += bool(best) and by_norm[best[0]] == truth[row["short_code"]]
    assert len(unmatched) > 0
    assert correct / len(unmatched) >= 0.9


# ---------- 4. pat_scores.csv ----------


def test_pat_scores_messiness(raw, gt, clean):
    file = "pat_scores.csv"
    data = (raw / file).read_bytes()
    assert data.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
    df = pd.read_csv(raw / file, skiprows=1, encoding="utf-8-sig", dtype=str)
    assert list(df.columns) == ["SCHOOL_CD", "Year", "Std", "Subject", "Avg_Marks", "Students_Appeared"]
    assert df["SCHOOL_CD"].str.fullmatch(r"00\d{9}").all()
    lost = pd.read_csv(raw / file, skiprows=1, encoding="utf-8-sig")  # default parsing loses leading zeros
    assert pd.api.types.is_integer_dtype(lost["SCHOOL_CD"])

    patterns = {"long": r"\d{4}-\d{2}", "short": r"\d{2}-\d{2}", "end_year": r"\d{4}"}
    for fmt, pattern in patterns.items():
        n = df["Year"].str.fullmatch(pattern).sum()
        assert n == log_count(gt, file, f"year_format_{fmt}") and n > 0
    assert set(df["Subject"]) == {"Maths", "Math", "गणित"}

    dups = df.duplicated().sum()
    assert dups == log_count(gt, file, "exact_duplicate_rows")
    assert 0.015 <= dups / len(df) <= 0.025
    assert len(df) - dups == len(clean["scores"])


# ---------- 5. teacher_posts.xlsx ----------


def test_teacher_posts_messiness(raw, gt, clean):
    file = "teacher_posts.xlsx"
    sheets = pd.read_excel(raw / file, sheet_name=None, header=2, dtype={"UDISE Code": str})
    assert list(sheets) == ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]
    allrows = pd.concat(sheets.values(), ignore_index=True)
    assert len(allrows) == len(clean["teacher_posts"])
    negative = (allrows["Vacant"] < 0).sum()
    assert negative == log_count(gt, file, "negative_vacancy_convention") and negative > 0
    assert (allrows["Vacant"].abs() == allrows["Sanctioned"] - allrows["Working"]).all()
    formats = {re.sub(r"\d", "9", d) for d in allrows["As On"]}
    assert len(formats) >= 3
    for frame in sheets.values():
        assert frame["As On"].nunique() >= 2  # dates vary within a year


# ---------- 6. election_duty.csv ----------


def test_election_duty_messiness(raw, gt):
    file = "election_duty.csv"
    df = pd.read_csv(raw / file, skiprows=1, dtype=str)
    slash = df["From"].str.fullmatch(r"\d{2}/\d{2}/\d{4}")
    iso = df["From"].str.fullmatch(r"\d{4}-\d{2}-\d{2}")
    assert (slash | iso).all()
    logged = {m["detail"]: m["count"] for m in log_items(gt, file, "date_format")}
    assert logged == {"dates written as %d/%m/%Y": slash.sum(), "dates written as %Y-%m-%d": iso.sum()}
    assert slash.sum() > 0 and iso.sum() > 0
    heavy = df[df["Deployed Teachers (%)"].astype(float) >= 30]
    t2 = next(t for t in gt["truths"] if t["id"] == "T2")
    assert set(heavy["Taluka"]) == set(t2["entities"]["talukas"])
    assert heavy["Duty"].str.contains("Vidhan Sabha General Election 2024").all()


def test_taluka_profile_messiness(raw, gt, clean):
    df = pd.read_csv(raw / "taluka_profile.csv", skiprows=1)
    assert len(df) == 11 and df["Poverty Headcount Ratio (%)"].between(1, 100).all()  # percent, not share
    variants = set(df["Taluka"]) - set(clean["talukas"]["taluka"])
    assert len(variants) == 1
    assert log_items(gt, "taluka_profile.csv", "poverty_as_percent")
