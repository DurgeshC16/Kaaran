"""Messiness layer: turns the clean tables into the six raw files and logs every injected mess.

Each file has its own random stream, so changing one file's messiness never shifts another's.
"""

from __future__ import annotations

import calendar
from pathlib import Path

import numpy as np
import pandas as pd

from . import SYNTHETIC_MARKER
from . import config as C
from .plant import Planted
from .rng import stream
from .tables import flat_months
from .writers import Sheet, write_csv, write_pdf_tables, write_xlsx

VARIANT_SHARE = 0.08
CROSSWALK_MISSING_SHARE = 0.03
PDF_OMIT_SHARE = 0.01
DUPLICATE_SHARE = 0.02
NEGATIVE_VACANCY_SHARE = 0.25  # share of taluka-years whose clerk stores vacancies as negatives
PDF_MONTHS = ("2024-01", "2024-02", "2024-03", "2024-06", "2024-07", "2024-08", "2024-09", "2024-10", "2024-11", "2024-12")
YEAR_FORMATS = (("long", 0.5), ("short", 0.3), ("end_year", 0.2))  # 2023-24 / 23-24 / 2024
SUBJECT_LABELS = (("Maths", 0.60), ("Math", 0.25), ("गणित", 0.15))
AS_ON_FORMATS = ("30/09/{y}", "01-07-{y}", "{y}-12-31", "31.08.{y}")
DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d")
ABBREVIATIONS = (
    ("ZP Kendra Primary School", "ZP Kendra PS"),
    ("ZP Marathi Primary School", "ZP Marathi PS"),
    ("ZP Urdu Primary School", "ZP Urdu PS"),
    ("ZP Primary School", "ZPPS"),
    (" No. ", " No."),
)
DUTY_LABELS = {
    "2021-12": "Gram Panchayat General Election 2021 - polling duty",
    "2024-03": "Lok Sabha General Election 2024 - preparation and training",
    "2024-09": "Vidhan Sabha General Election 2024 - training",
    "2024-10": "Vidhan Sabha General Election 2024 - polling duty",
    "2024-11": "Vidhan Sabha General Election 2024 - polling and counting duty",
    "2025-12": "Local Body General Election 2025 - polling duty",
}
MARATHI_YES_NO = {1: "होय", 0: "नाही"}

FILES = (
    "udise_2023.xlsx",
    "attendance_jan-dec.pdf",
    "crosswalk.xlsx",
    "pat_scores.csv",
    "teacher_posts.xlsx",
    "election_duty.csv",
    "taluka_profile.csv",
)


class MessLog:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, file: str, kind: str, count: int, detail: str, sheet: str | None = None, keys=None) -> None:
        item = {"file": file, "sheet": sheet, "kind": kind, "count": int(count), "detail": detail}
        if keys is not None:
            item["keys"] = keys
        self.items.append(item)


def _title(*lines: str) -> list[str]:
    return [SYNTHETIC_MARKER, *lines]


def _choice(rng: np.random.Generator, options, n: int) -> list:
    labels = [o for o, _ in options]
    return [str(v) for v in rng.choice(labels, n, p=[w for _, w in options])]


def _taluka_variants(frame: pd.DataFrame, col: str, code_col: str, names: str, rng, log: MessLog, file: str, sheet: str):
    name_set = C.NAME_SETS[names]
    key_by_name = {v[0]: k for k, v in name_set.items()}
    k = round(VARIANT_SHARE * len(frame))
    rows = np.sort(rng.choice(len(frame), k, replace=False))
    values = frame[col].tolist()
    for i in rows:
        _, variants, name_mr = name_set[key_by_name[values[i]]]
        values[i] = str(rng.choice([*variants, name_mr]))
    frame[col] = values
    keys = [str(frame[code_col].iloc[i]) for i in rows]
    log.add(file, "taluka_spelling_variant", k, f"taluka spelled as a variant or in Devanagari in {k} of {len(frame)} rows", sheet, keys)


# ---------- 1. udise_2023.xlsx ----------


def udise_workbook(clean, names: str, seed: int, log: MessLog, path: Path) -> int:
    rng = stream(seed, "messy:udise")
    file = path.name
    s = clean["schools"]
    profile = pd.DataFrame(
        {
            "UDISE Code": s["udise_code"],
            "school NAME": s["school_name"],
            "TALUKA": s["taluka"],
            "Cluster": s["cluster"],
            "cluster code": s["cluster_code"],
            "Village Name": s["village"],
            "Management": "Zilla Parishad",
        }
    )
    _taluka_variants(profile, "TALUKA", "UDISE Code", names, rng, log, file, "School Profile")

    enrol = pd.DataFrame(
        {
            "UDISE Code": s["udise_code"].astype("int64"),  # leading "00" lost
            "School Name": s["school_name"],
            "Taluka": s["taluka"],
            **{f"Std {i}": s[f"enrol_std{i}"] for i in range(1, 6)},
            "Total": s["enrol_total"],
        }
    ).sort_values("School Name", kind="stable", ignore_index=True)
    _taluka_variants(enrol, "Taluka", "UDISE Code", names, rng, log, file, "Enrolment")
    log.add(file, "code_stored_as_number", len(enrol), "UDISE codes stored as numbers; leading '00' lost (9 digits)", "Enrolment")

    infra = pd.DataFrame(
        {
            "यूडायस कोड": s["udise_code"],
            "शाळेचे नाव": s["school_name"],
            "तालुका": s["taluka"],
            "शौचालये": s["toilets"],
            "ग्रंथालय": s["library"].map(MARATHI_YES_NO),
            "पिण्याचे पाणी": s["drinking_water"].map(MARATHI_YES_NO),
            "वर्गखोल्या": s["classrooms"],
        }
    )
    _taluka_variants(infra, "तालुका", "यूडायस कोड", names, rng, log, file, "Infrastructure")
    log.add(file, "marathi_headers", 1, "Infrastructure sheet uses Marathi headers and होय/नाही values", "Infrastructure")

    sub = f"UDISE+ 2023-24 | {C.DISTRICT_NAME}"
    note = "Generated by kaaran.synth for testing. Not real data."
    write_xlsx(
        path,
        [
            Sheet("School Profile", _title(f"{sub} | School Profile", note), profile, text_columns=("UDISE Code",)),
            Sheet(
                "Enrolment",
                _title(f"{sub} | Enrolment", note),
                enrol,
                group_header=[("School", 3), ("Enrolment 2023-24 (Std 1-5)", 6)],
            ),
            Sheet("Infrastructure", _title(f"{sub} | पायाभूत सुविधा", note), infra, text_columns=("यूडायस कोड",)),
        ],
    )
    log.add(file, "title_rows_and_merged_cells", 3, "3 merged title rows above headers on every sheet; Enrolment has a merged group header row")
    return len(profile) + len(enrol) + len(infra)


# ---------- 2. attendance_jan-dec.pdf ----------


def _abbreviate(name: str) -> str:
    for long, short in ABBREVIATIONS:
        name = name.replace(long, short)
    return name


def _typo(word: str, rng) -> str:
    i = int(rng.integers(1, len(word) - 1))
    if rng.random() < 0.5:
        return word[:i] + word[i + 1] + word[i] + word[i + 2 :]
    return word[:i] + word[i + 1 :]


def attendance_names(clean, seed: int, log: MessLog, file: str) -> pd.Series:
    """Names as printed by the attendance system: abbreviated or misspelt for some schools."""
    rng = stream(seed, "messy:pdf_names")
    s = clean["schools"]
    out, abbreviated, misspelt = [], [], []
    for code, name, village in zip(s["udise_code"], s["school_name"], s["village"]):
        u = rng.random()
        if u < 0.60:
            out.append(name)
            continue
        new = _abbreviate(name)
        if u >= 0.90:
            new = new.replace(village, _typo(village, rng))
            misspelt.append(code)
        else:
            abbreviated.append(code)
        out.append(new)
    log.add(file, "school_name_abbreviated", len(abbreviated), "prefix abbreviated (e.g. ZPPS)", keys=abbreviated)
    log.add(file, "school_name_misspelt", len(misspelt), "village name misspelt (and prefix abbreviated)", keys=misspelt)
    return pd.Series(out, index=s["udise_code"].to_numpy())


def attendance_pdf(clean, planted: Planted, names: str, seed: int, log: MessLog, path: Path) -> int:
    rng = stream(seed, "messy:pdf")
    file = path.name
    s = clean["schools"].set_index("udise_code")
    pdf_name = attendance_names(clean, seed, log, file)
    att = clean["attendance"][clean["attendance"]["month"].isin(PDF_MONTHS)].copy()

    protected = set(flat_months(planted)) | set(planted.honest_low) | set(planted.all_missing_attendance())
    candidates = sorted(set(att["udise_code"]) - protected)
    k = round(PDF_OMIT_SHARE * len(att))
    omit_codes = sorted(rng.choice(candidates, k, replace=False).tolist())
    omitted = {c: str(rng.choice(PDF_MONTHS)) for c in omit_codes}
    drop = [omitted.get(c) == m for c, m in zip(att["udise_code"], att["month"])]
    att = att.loc[~np.array(drop)]
    log.add(file, "rows_omitted", k, "school-months missing from the PDF (beyond the planted T6 gaps); at most one per school",
            keys=[f"{c}|{m}" for c, m in omitted.items()])

    att["taluka"] = att["udise_code"].map(s["taluka"])
    att["School Name"] = att["udise_code"].map(pdf_name)
    sections = []
    for t in C.TALUKAS:
        name = C.NAME_SETS[names][t.key][0]
        for month in PDF_MONTHS:
            g = att[(att["taluka"] == name) & (att["month"] == month)].sort_values("School Name", kind="stable")
            frame = pd.DataFrame(
                {
                    "Sr No": range(1, len(g) + 1),
                    "School Name": g["School Name"].to_numpy(),
                    "Short Code": g["udise_code"].map(s["short_code"]).to_numpy(),
                    "Enrolled": g["enrolled"].to_numpy(),
                    "Present Avg": [f"{v:.1f}" for v in g["present_avg"]],
                    "%": [f"{v:.1f}" for v in g["attendance_pct"]],
                }
            )
            month_name = calendar.month_name[int(month[5:])]
            sections.append((f"Monthly attendance summary - {month_name} {month[:4]} - Taluka: {name}", frame))
    write_pdf_tables(path, f"Attendance Jan-Dec 2024 | {C.DISTRICT_NAME}", sections, [14, 74, 22, 20, 22, 16])
    log.add(file, "header_repeats_each_page", 1, "table header row repeats on every page; section headings do not")
    return len(att)


# ---------- 3. crosswalk.xlsx ----------


def crosswalk(clean, seed: int, log: MessLog, path: Path) -> int:
    rng = stream(seed, "messy:crosswalk")
    s = clean["schools"]
    k = round(CROSSWALK_MISSING_SHARE * len(s))
    missing = set(rng.choice(s["short_code"].to_numpy(), k, replace=False).tolist())
    cw = s.loc[~s["short_code"].isin(missing), ["short_code", "udise_code", "taluka"]]
    cw = cw.rename(columns={"short_code": "Short Code", "udise_code": "UDISE Code", "taluka": "Taluka"})
    cw = cw.sort_values("Short Code", ignore_index=True)
    write_xlsx(
        path,
        [Sheet("Crosswalk", _title(f"Attendance short code to UDISE code | {C.DISTRICT_NAME}"), cw, text_columns=("UDISE Code",))],
    )
    log.add(path.name, "crosswalk_missing_schools", k, "schools absent from the crosswalk; need fuzzy name matching", "Crosswalk",
            keys=sorted(missing))
    return len(cw)


# ---------- 4. pat_scores.csv ----------


def _year_label(year: str, fmt: str) -> str:
    if fmt == "long":
        return year
    if fmt == "short":
        return year[2:]
    return str(int(year[:4]) + 1)


def pat_scores(clean, seed: int, log: MessLog, path: Path) -> int:
    rng = stream(seed, "messy:pat")
    file = path.name
    sc = clean["scores"].sort_values(["udise_code", "academic_year"], ignore_index=True)
    fmts = _choice(rng, YEAR_FORMATS, len(sc))
    subjects = _choice(rng, SUBJECT_LABELS, len(sc))
    frame = pd.DataFrame(
        {
            "SCHOOL_CD": sc["udise_code"],
            "Year": [_year_label(y, f) for y, f in zip(sc["academic_year"], fmts)],
            "Std": sc["std"],
            "Subject": subjects,
            "Avg_Marks": sc["mean_score"],
            "Students_Appeared": sc["students_appeared"],
        }
    )
    frame["_fmt"] = fmts
    k = round(DUPLICATE_SHARE * len(frame))
    dup = np.sort(rng.choice(len(frame), k, replace=False))
    frame = pd.concat([frame, frame.iloc[dup]]).sort_index(kind="stable").reset_index(drop=True)
    log.add(file, "exact_duplicate_rows", k, "rows repeated verbatim right after the original",
            keys=[f"{sc['udise_code'].iloc[i]}|{sc['academic_year'].iloc[i]}" for i in dup])
    # Counts below are over the rows as written (duplicates included).
    for fmt, _ in YEAR_FORMATS:
        log.add(file, f"year_format_{fmt}", int((frame["_fmt"] == fmt).sum()),
                "academic year written as 2023-24 / 23-24 / 2024 (end year)")
    for label, _ in SUBJECT_LABELS:
        log.add(file, "subject_label", int((frame["Subject"] == label).sum()), f"subject written as '{label}'",
                keys=[label])
    frame = frame.drop(columns="_fmt")
    log.add(file, "utf8_bom_and_title_line", 1, "UTF-8 with BOM; first line is a title line (read with skiprows=1)")
    write_csv(path, f"# {SYNTHETIC_MARKER} | PAT Std 3 maths scores 2021-22 to 2025-26 | {C.DISTRICT_NAME}", frame, "utf-8-sig")
    return len(frame)


# ---------- 5. teacher_posts.xlsx ----------


def teacher_posts(clean, seed: int, log: MessLog, path: Path) -> int:
    rng = stream(seed, "messy:posts")
    file = path.name
    s = clean["schools"].set_index("udise_code")
    posts = clean["teacher_posts"]
    sheets, negative_blocks, negative_rows, as_on_log = [], [], 0, {}
    for year in C.YEARS:
        p = posts[posts["academic_year"] == year]
        taluka = p["udise_code"].map(s["taluka"])
        start = int(year[:4])
        as_on, negative = {}, {}
        for t in sorted(taluka.unique()):
            as_on[t] = AS_ON_FORMATS[int(rng.integers(len(AS_ON_FORMATS)))].format(y=start)
            negative[t] = bool(rng.random() < NEGATIVE_VACANCY_SHARE)
            if negative[t]:
                negative_blocks.append(f"{t}|{year}")
        as_on_log[year] = as_on
        sign = np.where(taluka.map(negative).to_numpy(dtype=bool), -1, 1)
        vacant = sign * (p["sanctioned"].to_numpy() - p["working"].to_numpy())
        negative_rows += int((vacant < 0).sum())
        frame = pd.DataFrame(
            {
                "UDISE Code": p["udise_code"].to_numpy(),
                "School Name": p["udise_code"].map(s["school_name"]).to_numpy(),
                "Taluka": taluka.to_numpy(),
                "Subject": p["subject"].str.capitalize().to_numpy(),
                "Sanctioned": p["sanctioned"].to_numpy(),
                "Working": p["working"].to_numpy(),
                "Vacant": vacant,
                "As On": taluka.map(as_on).to_numpy(),
            }
        )
        sheets.append(Sheet(year, _title(f"Teacher posts {year} (sanctioned vs working) | {C.DISTRICT_NAME}"), frame,
                            text_columns=("UDISE Code",)))
    write_xlsx(path, sheets)
    log.add(file, "negative_vacancy_convention", negative_rows,
            "in some taluka-years the Vacant column is stored as working - sanctioned (negative)", keys=negative_blocks)
    log.add(file, "as_on_date_formats", len(AS_ON_FORMATS), "as-on dates differ by taluka and year, in 4 formats",
            keys=[f"{y}|{t}|{d}" for y, m in as_on_log.items() for t, d in m.items()])
    return int(len(posts))


# ---------- 6. election_duty.csv ----------


def election_duty(clean, seed: int, log: MessLog, path: Path) -> int:
    rng = stream(seed, "messy:election")
    ed = clean["election_duty"]
    fmt_idx = rng.integers(len(DATE_FORMATS), size=len(ed))
    rows = []
    for i, (taluka, month, pct) in enumerate(zip(ed["taluka"], ed["month"], ed["deployed_pct"])):
        y, m = int(month[:4]), int(month[5:])
        first = pd.Timestamp(y, m, 1)
        last = pd.Timestamp(y, m, calendar.monthrange(y, m)[1])
        f = DATE_FORMATS[fmt_idx[i]]
        rows.append((i + 1, taluka, DUTY_LABELS[month], first.strftime(f), last.strftime(f), pct))
    frame = pd.DataFrame(rows, columns=["Sr.No.", "Taluka", "Duty", "From", "To", "Deployed Teachers (%)"])
    for j, f in enumerate(DATE_FORMATS):
        log.add(path.name, "date_format", int((fmt_idx == j).sum()), f"dates written as {f}")
    write_csv(path, f"# {SYNTHETIC_MARKER} | Election duty schedule (teachers deployed) | {C.DISTRICT_NAME}", frame)
    return len(frame)


# ---------- 7. taluka_profile.csv ----------


def taluka_profile(clean, names: str, seed: int, log: MessLog, path: Path) -> int:
    """Block-level poverty index (a district statistical handbook style table), stored as a percentage."""
    rng = stream(seed, "messy:taluka_profile")
    t = clean["talukas"]
    labels = t["taluka"].tolist()
    i = int(rng.integers(len(labels)))
    variant = C.NAME_SETS[names][t["taluka_key"].iloc[i]][1][0]
    labels[i] = variant
    frame = pd.DataFrame({"Taluka": labels, "Poverty Headcount Ratio (%)": (t["poverty_index"] * 100).round(1)})
    log.add(path.name, "poverty_as_percent", len(frame), "poverty index stored as a percentage (42.0) instead of a share (0.42)")
    log.add(path.name, "taluka_spelling_variant", 1, "taluka spelled as a variant", keys=[variant])
    write_csv(path, f"# {SYNTHETIC_MARKER} | Taluka profile: poverty headcount ratio | {C.DISTRICT_NAME}", frame)
    return len(frame)


def write_raw(clean, planted: Planted, out: Path, seed: int, names: str) -> tuple[list[dict], dict[str, int]]:
    out.mkdir(parents=True, exist_ok=True)
    log = MessLog()
    rows = {
        "udise_2023.xlsx": udise_workbook(clean, names, seed, log, out / "udise_2023.xlsx"),
        "attendance_jan-dec.pdf": attendance_pdf(clean, planted, names, seed, log, out / "attendance_jan-dec.pdf"),
        "crosswalk.xlsx": crosswalk(clean, seed, log, out / "crosswalk.xlsx"),
        "pat_scores.csv": pat_scores(clean, seed, log, out / "pat_scores.csv"),
        "teacher_posts.xlsx": teacher_posts(clean, seed, log, out / "teacher_posts.xlsx"),
        "election_duty.csv": election_duty(clean, seed, log, out / "election_duty.csv"),
        "taluka_profile.csv": taluka_profile(clean, names, seed, log, out / "taluka_profile.csv"),
    }
    return log.items, rows
