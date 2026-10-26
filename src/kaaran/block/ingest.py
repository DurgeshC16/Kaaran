"""Ingest v2 (block lens): real-format raw files -> canonical tables with provenance.

Recognises each file/sheet by its header (English, Marathi or both in one cell), reads it, normalises values
and keeps `src_file, src_sheet, src_row` on every row. Fixes (zero-padded UDISE codes, % text, duplicates,
mixed date formats) and unresolved rows are reported, never dropped silently.

Canonical tables: schools, clusters, udise_year, posts, attendance, assessment, visits, training.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from ..ingest.mapping import norm_header
from ..ingest.normalize import float_, int_, udise11
from ..ingest.readers import FORMATS, csv_rows, xlsx_rows

HEADER_SCAN_ROWS = 15
MARKER = "SYNTHETIC"

# field -> header phrases (normalised; matched as whole-word sequences inside the header; longest match wins)
PHRASES = {
    "udise_code": ["udise sch code", "udise code", "udise", "pseudocode", "यूडायस कोड", "udise कोड"],
    "school_name": ["school name", "school", "शाळेचे नाव"],
    "block": ["block", "तालुका"],
    "cluster_name": ["kendra", "केंद्र", "cluster"],
    "cluster_code": ["kendra code", "केंद्र कोड", "cluster code"],
    "month": ["month", "महिना"],
    "sanctioned": ["sanctioned", "मंजूर पदे"],
    "working": ["working", "कार्यरत"],
    "vacant": ["vacant", "रिक्त"],
    "duty_days": ["non teaching duty days", "अशैक्षणिक कामाचे दिवस"],
    "enrolled": ["enrolled", "पटसंख्या"],
    "attendance_pct": ["attendance", "उपस्थिती"],
    "grade": ["grade", "इयत्ता"],
    "assessed": ["students assessed", "मूल्यमापन झालेले विद्यार्थी"],
    "visit_date": ["visit date"],
    "visitor_role": ["visitor"],
    "purpose": ["purpose"],
    "classroom_observed": ["classroom observed"],
    "training": ["training"],
    "start_date": ["start date"],
    "days": ["days"],
    "teachers_trained": ["teachers trained"],
    # UDISE+ microdata names (exact after normalisation)
    "rural_urban": ["rural urban"], "village": ["lgd vill name"], "school_category": ["school category"],
    "lowclass": ["lowclass"], "highclass": ["highclass"], "management": ["managment", "management"],
    "instr_days": ["avg instr days"], "acad_inspections": ["acad inspections"], "crc_visits": ["crc coordinator"],
    "brc_visits": ["block level officers"], "district_visits": ["district officers"],
    "smc_meetings": ["smc smdc meetings"], "total_tch": ["total tch"], "regular": ["regular"], "contract": ["contract"],
    "non_teaching_teachers": ["teacher involve non training assignment"], "item_group": ["item group"],
    "item_id": ["item id"],
}
COMPETENCY = re.compile(r"^(M[1-9]|L[1-9])\b")
ENROL_COL = re.compile(r"^c(\d{1,2}) ([bg])$")
YEAR = re.compile(r"(20\d{2})-(\d{2})")
ROUND_WORDS = {"BL": ["baseline", "पायाभूत"], "ML": ["midline", "मध्यावधी"], "EL": ["endline", "अंतिम"]}
MONTH_ABBR = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

ROLES = {  # role -> (required fields, distinguishing fields)
    "udise_prof1": ({"udise_code", "block", "lowclass", "highclass"}, set()),
    "udise_prof2": ({"udise_code", "crc_visits"}, set()),
    "udise_tch": ({"udise_code", "total_tch"}, set()),
    "udise_enr1": ({"udise_code", "item_group", "item_id"}, set()),
    "kendra_list": ({"udise_code", "cluster_name", "cluster_code", "block"}, set()),
    "posts": ({"udise_code", "month", "sanctioned", "working"}, set()),
    "attendance": ({"udise_code", "attendance_pct"}, set()),
    "assessment": ({"udise_code", "grade", "assessed"}, set()),
    "visits": ({"udise_code", "visit_date", "visitor_role"}, set()),
    "training": ({"udise_code", "training", "start_date"}, set()),
}
ROLE_ORDER = ["udise_enr1", "udise_prof1", "udise_prof2", "udise_tch", "kendra_list", "posts", "assessment", "visits",
              "training", "attendance"]


class BlockIngestError(Exception):
    pass


@dataclass
class BlockIngest:
    tables: dict[str, pd.DataFrame]
    report: dict = field(default_factory=dict)


def _phrase_hit(header: str, phrase: str) -> bool:
    return f" {phrase} " in f" {header} "


def field_for(header) -> str | None:
    h = norm_header(header)
    if not h:
        return None
    if COMPETENCY.match(str(header).strip()):
        return "competency:" + COMPETENCY.match(str(header).strip()).group(1)
    if ENROL_COL.match(h):
        return "enrol:" + h.replace(" ", "_")
    best, best_len = None, 0
    for f, phrases in PHRASES.items():
        for p in phrases:
            if _phrase_hit(h, p) and len(p) > best_len:
                best, best_len = f, len(p)
    return best


def _map_header(cells) -> dict[str, int]:
    out: dict[str, int] = {}
    for j, c in enumerate(cells or ()):
        f = field_for(c)
        if f and f not in out:
            out[f] = j
    return out


def _role(fields: set[str]) -> str | None:
    for role in ROLE_ORDER:
        if ROLES[role][0] <= fields:
            return role
    return None


def _tables_of(path: Path) -> dict[str | None, list[tuple]]:
    fmt = FORMATS.get(path.suffix.lower())
    if fmt == "xlsx":
        return xlsx_rows(path)
    if fmt == "csv":
        return {None: list(csv_rows(path)[2])}
    return {}


def _detect(rows: list[tuple]) -> tuple[int, dict[str, int], str] | None:
    best = None
    for i, cells in enumerate(rows[:HEADER_SCAN_ROWS]):
        mapped = _map_header(cells)
        role = _role(set(mapped))
        if role and (best is None or len(mapped) > len(best[1])):
            best = (i, mapped, role)
    return best


def _year_from(*texts) -> str | None:
    for t in texts:
        m = YEAR.search(str(t or ""))
        if m:
            return f"{m.group(1)}-{m.group(2)}"
    return None


def _round_from(sheet: str | None) -> str | None:
    s = str(sheet or "").lower()
    return next((k for k, words in ROUND_WORDS.items() if any(w in s for w in words)), None)


def _month_from_sheet(sheet: str | None) -> str | None:
    m = re.match(r"([A-Za-z]{3})[a-z]*[- ]?(20\d{2})", str(sheet or "").strip())
    if not m or m.group(1).lower() not in MONTH_ABBR:
        return None
    return f"{m.group(2)}-{MONTH_ABBR[m.group(1).lower()]:02d}"


def _month_value(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, (dt.date, dt.datetime)):
        return f"{v.year:04d}-{v.month:02d}"
    s = str(v).strip()
    m = re.match(r"(20\d{2})-(\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    return _month_from_sheet(s)


DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d/%m/%y", "%d.%m.%Y")


def _date_value(v) -> tuple[str | None, str | None]:
    if v is None or str(v).strip() == "":
        return None, None
    if isinstance(v, (dt.date, dt.datetime)):
        return v.strftime("%Y-%m-%d"), "excel_date"
    s = str(v).strip()
    for f in DATE_FORMATS:
        try:
            return dt.datetime.strptime(s, f).strftime("%Y-%m-%d"), f
        except ValueError:
            continue
    return None, None


def _frame(rows: list[tuple], header_idx: int, mapping: dict[str, int], file: str, sheet: str | None) -> pd.DataFrame:
    data = []
    for i in range(header_idx + 1, len(rows)):
        cells = rows[i] or ()
        if not any(c not in (None, "") for c in cells):
            continue
        rec = {f: (cells[j] if j < len(cells) else None) for f, j in mapping.items()}
        rec["src_row"] = i + 1
        data.append(rec)
    df = pd.DataFrame(data)
    df["src_file"], df["src_sheet"] = file, sheet
    return df


class FixLog:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, kind: str, count: int, file: str, sheet: str | None = None, **detail):
        if count:
            self.items.append({"kind": kind, "count": int(count), "file": file, "sheet": sheet, **detail})


def _codes(df: pd.DataFrame, log: FixLog, file: str, sheet) -> pd.DataFrame:
    codes, stats = udise11(df["udise_code"])
    log.add("udise_zero_padded", stats["zero_padded"], file, sheet)
    df = df.assign(udise_code=codes)
    bad = df["udise_code"].isna().sum()
    log.add("udise_unreadable", bad, file, sheet)
    return df[df["udise_code"].notna()]


def _numbers(df: pd.DataFrame, cols: list[str], log: FixLog, file: str, sheet, as_int=False) -> pd.DataFrame:
    for c in cols:
        if c not in df:
            continue
        texty = df[c].map(lambda v: isinstance(v, str) and "%" in v).sum()
        log.add("percent_text_parsed", texty, file, sheet, column=c)
        df[c] = (int_ if as_int else float_)(df[c])[0]
    return df


def _dedupe(df: pd.DataFrame, key: list[str], log: FixLog, file: str, sheet) -> pd.DataFrame:
    value_cols = [c for c in df.columns if not c.startswith("src_")]
    exact = df.duplicated(subset=value_cols, keep="first")
    log.add("exact_duplicates_removed", exact.sum(), file, sheet)
    df = df[~exact]
    conflict = df.duplicated(subset=key, keep=False)
    log.add("conflicting_duplicates_kept", conflict.sum(), file, sheet, key=key)
    return df


def _read(path: Path, log: FixLog, recognised: list[dict]) -> dict[str, list[pd.DataFrame]]:
    parts: dict[str, list[pd.DataFrame]] = {}
    for sheet, rows in _tables_of(path).items():
        det = _detect(rows)
        if det is None:
            log.add("table_not_recognised", 1, path.name, sheet)
            continue
        idx, mapping, role = det
        df = _frame(rows, idx, mapping, path.name, sheet)
        if df.empty:
            continue
        recognised.append({"file": path.name, "sheet": sheet, "role": role, "header_row": idx + 1, "rows": len(df)})
        df = _codes(df, log, path.name, sheet)
        year = _year_from(path.name, sheet)
        if role.startswith("udise_"):
            df["academic_year"] = year
        elif role == "attendance":
            month = _month_from_sheet(sheet)
            if month is None:
                log.add("month_not_found", len(df), path.name, sheet)
                continue
            df["month"] = month
            df = _numbers(df, ["attendance_pct"], log, path.name, sheet)
            df = _numbers(df, ["enrolled"], log, path.name, sheet, as_int=True)
        elif role == "posts":
            df["month"] = df["month"].map(_month_value)
            df = _numbers(df, ["duty_days"], log, path.name, sheet)
            df = _numbers(df, ["sanctioned", "working", "vacant"], log, path.name, sheet, as_int=True)
        elif role == "assessment":
            rkey = _round_from(sheet)
            if rkey is None or year is None:
                log.add("round_or_year_not_found", len(df), path.name, sheet)
                continue
            comp_cols = [c for c in df.columns if c.startswith("competency:")]
            df = _numbers(df, comp_cols, log, path.name, sheet)
            df = _numbers(df, ["grade", "assessed"], log, path.name, sheet, as_int=True)
            df = _dedupe(df, ["udise_code", "grade"], log, path.name, sheet)
            long = df.melt(id_vars=["udise_code", "grade", "assessed", "src_file", "src_sheet", "src_row"],
                           value_vars=comp_cols, var_name="competency", value_name="pct")
            long["competency"] = long["competency"].str.split(":").str[1]
            long["academic_year"], long["round"] = year, rkey
            df = long
        elif role in ("visits", "training"):
            col = "visit_date" if role == "visits" else "start_date"
            parsed = df[col].map(_date_value)
            df["date"] = parsed.map(lambda x: x[0])
            formats = parsed.map(lambda x: x[1]).value_counts().to_dict()
            if len(formats) > 1:
                log.add("mixed_date_formats", len(df), path.name, sheet, formats={k: int(v) for k, v in formats.items()})
            log.add("date_unparsed", df["date"].isna().sum(), path.name, sheet)
            if role == "visits" and "classroom_observed" in df:
                df["classroom_observed"] = df["classroom_observed"].map(lambda v: str(v).strip().lower() in ("yes", "y", "1", "होय"))
            if role == "training":
                df = _numbers(df, ["days", "teachers_trained"], log, path.name, sheet, as_int=True)
        parts.setdefault(role, []).append(df)
    return parts


def _cat(parts, role) -> pd.DataFrame:
    frames = parts.get(role, [])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _sources(raw: Path) -> list[dict]:
    out = []
    for i, p in enumerate(sorted(x for x in raw.iterdir() if x.suffix.lower() in FORMATS), start=1):
        data = p.read_bytes()
        out.append({"id": f"S{i}", "file": p.name, "kind": FORMATS[p.suffix.lower()],
                    "sha256": hashlib.sha256(data).hexdigest(), "synthetic": MARKER.encode() in data[:4000] or p.suffix == ".xlsx" and _xlsx_marker(p)})
    return out


def _xlsx_marker(p: Path) -> bool:
    return any(rows and rows[0] and MARKER in str(rows[0][0]) for rows in xlsx_rows(p).values())


def ingest_block(raw_dir: str | Path) -> BlockIngest:
    raw = Path(raw_dir)
    log, recognised = FixLog(), []
    parts: dict[str, list[pd.DataFrame]] = {}
    for path in sorted(raw.iterdir()):
        if path.suffix.lower() not in (".xlsx", ".csv"):
            continue
        for role, frames in _read(path, log, recognised).items():
            parts.setdefault(role, []).extend(frames)
    missing = [r for r in ("udise_prof1", "kendra_list", "assessment", "attendance", "posts") if r not in parts]
    if missing:
        raise BlockIngestError(f"required data not found: {missing}")

    prof1 = _cat(parts, "udise_prof1")
    latest = prof1["academic_year"].max()
    p1 = prof1[prof1["academic_year"] == latest]
    kl = _cat(parts, "kendra_list")
    kl = kl.assign(cluster_name=kl["cluster_name"].map(lambda v: " ".join(str(v).split())),
                   cluster_code=kl["cluster_code"].map(lambda v: str(v).strip()),
                   block=kl["block"].map(lambda v: " ".join(str(v).split())))
    schools = p1[["udise_code", "school_name", "block", "rural_urban", "village", "school_category", "lowclass", "highclass",
                  "management", "src_file", "src_sheet", "src_row"]].copy()
    schools["block"] = schools["block"].map(lambda v: str(v).strip().title())
    schools = schools.merge(kl[["udise_code", "cluster_code", "cluster_name"]].rename(columns={"cluster_code": "cluster_id"}),
                            on="udise_code", how="left")
    no_cluster = schools["cluster_id"].isna().sum()
    log.add("school_without_cluster", no_cluster, "kendra_list.xlsx")
    for c in ("rural_urban", "school_category", "lowclass", "highclass", "management"):
        schools[c] = int_(schools[c])[0]
    clusters = (kl.groupby(["cluster_code", "cluster_name", "block"]).size().rename("n_schools").reset_index()
                .rename(columns={"cluster_code": "cluster_id"}))
    clusters["block"] = clusters["block"].map(lambda v: str(v).strip().title())
    known = set(schools["udise_code"])

    # UDISE+ yearly facts
    yearly = None
    for role, cols in (("udise_tch", ["total_tch", "regular", "contract", "non_teaching_teachers"]),
                       ("udise_prof2", ["acad_inspections", "crc_visits", "brc_visits", "district_visits", "smc_meetings"])):
        df = _cat(parts, role)
        if df.empty:
            continue
        df = df[["udise_code", "academic_year", *[c for c in cols if c in df]]].copy()
        for c in cols:
            if c in df:
                df[c] = int_(df[c])[0]
        yearly = df if yearly is None else yearly.merge(df, on=["udise_code", "academic_year"], how="outer")
    enr = _cat(parts, "udise_enr1")
    if not enr.empty:
        enr = enr[int_(enr["item_group"])[0] == 1]
        enrol_cols = [c for c in enr.columns if c.startswith("enrol:")]
        for c in enrol_cols:
            enr[c] = int_(enr[c])[0]
        e = enr.groupby(["udise_code", "academic_year"])[enrol_cols].sum()
        by_class = {}
        for c in enrol_cols:
            cls = int(ENROL_COL.match(c.split(":")[1].replace("_", " ")).group(1))
            by_class.setdefault(cls, []).append(c)
        e2 = pd.DataFrame({f"enrol_c{k}": e[v].sum(axis=1) for k, v in sorted(by_class.items())})
        e2["enrol_total"] = e2.sum(axis=1)
        e2 = e2.reset_index()
        yearly = e2 if yearly is None else yearly.merge(e2, on=["udise_code", "academic_year"], how="outer")

    posts = _cat(parts, "posts")
    posts = _dedupe(posts, ["udise_code", "month"], log, "teacher_posts", None)
    att = _cat(parts, "attendance")
    att = _dedupe(att, ["udise_code", "month"], log, "student_attendance", None)
    assess = _cat(parts, "assessment")
    visits = _cat(parts, "visits")
    training = _cat(parts, "training")
    tables = {"schools": schools, "clusters": clusters, "udise_year": yearly if yearly is not None else pd.DataFrame(),
              "posts": posts, "attendance": att, "assessment": assess, "visits": visits, "training": training}
    for name in ("posts", "attendance", "assessment", "visits", "training"):
        df = tables[name]
        if df.empty:
            continue
        unknown = ~df["udise_code"].isin(known)
        log.add("unresolved_school_code", unknown.sum(), name)
        tables[name] = df[~unknown].reset_index(drop=True)
    for name, df in tables.items():
        if "month" in df:
            df["academic_year"] = df["month"].map(lambda m: None if m is None else
                                                  f"{int(m[:4]) if int(m[5:7]) >= 6 else int(m[:4]) - 1}-"
                                                  f"{((int(m[:4]) if int(m[5:7]) >= 6 else int(m[:4]) - 1) + 1) % 100:02d}")
    report = {"recognised": recognised, "fixes": log.items, "sources": _sources(raw),
              "rows": {k: int(len(v)) for k, v in tables.items()},
              "synthetic": all(s["synthetic"] for s in _sources(raw))}
    return BlockIngest(tables=tables, report=report)
