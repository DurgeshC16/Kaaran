"""Deterministic ingest: raw files + mapping JSON -> canonical tables (with provenance) -> DuckDB.

Every fix is logged in the ingest report. Nothing is silently dropped: rows that cannot be linked
or parsed are kept in `ingest_unresolved` and reported.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

from . import mapping as M
from . import normalize as N
from .readers import FORMATS, csv_rows, pdf_lines, pdf_page_count, xlsx_rows

# Name matching for attendance short codes missing from the crosswalk: candidates are roster schools of the
# same taluka not already linked; pairs are assigned one-to-one, best similarity first (ties: closest enrolment).
NAME_MATCH_MIN = 0.6
NAME_ABBREVIATIONS = ((r"\bzpps\b", "zp primary school"), (r"\bps\b", "primary school"), (r"\bno(\d)", r"no \1"))
SECTION_PATTERNS = {
    "month_year_taluka": re.compile(
        r"(January|February|March|April|May|June|July|August|September|October|November|December) (\d{4}) - Taluka: (.+)$"),
}
PDF_FIELD_PATTERNS = {"int": r"(\d+)", "float": r"(\d+(?:\.\d+)?)", "code": r"([A-Z]{1,4}\d{3,8})", "text": r"(.+?)"}
CANONICAL_COLUMNS = {
    "talukas": ["taluka_id", "block_code", "taluka", "taluka_mr", "n_schools", "poverty_index"],
    "schools": ["udise_code", "short_code", "school_name", "village", "taluka_id", "cluster_code", "cluster",
                "enrol_std1", "enrol_std2", "enrol_std3", "enrol_std4", "enrol_std5", "enrol_total",
                "toilets", "library", "drinking_water", "classrooms"],
    "scores": ["udise_code", "taluka_id", "academic_year", "std", "subject", "mean_score", "students_appeared"],
    "attendance": ["udise_code", "taluka_id", "academic_year", "month", "enrolled", "present_avg", "attendance_pct"],
    "teacher_posts": ["udise_code", "taluka_id", "academic_year", "subject", "sanctioned", "working"],
    "election_duty": ["taluka_id", "academic_year", "month", "deployed_pct"],
}
SRC_COLUMNS = ["src_id", "src_sheet", "src_page", "src_section", "src_row"]
FIX_UNITS = {
    "header_row_detected": "sheets", "title_lines_skipped": "rows", "bom_removed": "files",
    "marathi_headers_mapped": "columns", "code_zero_padded": "rows", "taluka_variant_resolved": "rows",
    "year_format_normalized": "rows", "bare_year_convention": "flag", "subject_label_normalized": "rows",
    "yes_no_marathi": "cells", "exact_duplicates_removed": "rows", "conflicting_duplicates": "rows",
    "negative_vacancy_recomputed": "rows", "vacancy_mismatch": "rows", "date_format_parsed": "rows",
    "pdf_header_repeats_skipped": "pages", "pdf_continuation_pages": "pages", "link_crosswalk": "schools",
    "link_name_match": "schools", "link_unresolved": "schools", "unparsed_values": "cells", "percent_to_share": "rows",
    "taluka_name_unresolved": "rows",
}


class IngestError(Exception):
    def __init__(self, errors: list[dict]):
        super().__init__(f"mapping invalid: {errors[:5]}")
        self.errors = errors


@dataclass
class IngestResult:
    tables: dict[str, pd.DataFrame]
    report: dict
    mapping: dict
    db_path: str | None


class FixLog:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, kind: str, count: int, file: str | None = None, sheet: str | None = None, detail: str = "", examples=None):
        if count <= 0 and FIX_UNITS[kind] != "flag":
            return
        item = {"kind": kind, "unit": FIX_UNITS[kind], "count": int(count), "file": file, "sheet": sheet, "detail": detail}
        if examples is not None and len(examples):
            item["examples"] = [str(e) for e in list(examples)[:5]]
        self.items.append(item)

    def total(self, kind: str, file: str | None = None, sheet: str | None = None, detail: str | None = None) -> int:
        return sum(i["count"] for i in self.items if i["kind"] == kind and (file is None or i["file"] == file)
                   and (sheet is None or i["sheet"] == sheet) and (detail is None or i["detail"] == detail))


# ---------- reading mapped entries ----------


def _is_devanagari(s: str) -> bool:
    return any("ऀ" <= ch <= "ॿ" for ch in s)


def _frame(header: list, rows: list[tuple[int, tuple]]) -> pd.DataFrame:
    data = []
    for row_no, cells in rows:
        if all(c is None or str(c).strip() == "" for c in cells):
            continue
        rec = {str(h): (cells[j] if j < len(cells) else None) for j, h in enumerate(header) if h not in (None, "")}
        rec["src_row"] = row_no
        data.append(rec)
    return pd.DataFrame(data, dtype=object)


def _read_entry(entry: dict, raw: Path, sources: dict[str, dict], log: FixLog) -> pd.DataFrame:
    path = raw / entry["file"]
    src_id = sources[entry["file"]]["id"]
    read = entry["read"]
    fmt = read["format"]
    frames = []
    if fmt == "xlsx":
        sheets = xlsx_rows(path)
        names = list(sheets) if entry.get("sheet") == "*" else [entry["sheet"]]
        for name in names:
            rows = sheets[name]
            h = read["header_row"]
            header = list(rows[h - 1])
            df = _frame(header, [(i + 1, r) for i, r in enumerate(rows) if i + 1 > h])
            df["src_sheet"] = name
            if h > 1:
                log.add("header_row_detected", 1, entry["file"], name, f"header on row {h}; {h - 1} title/group rows skipped")
            marathi = [c for c in header if c and _is_devanagari(str(c))]
            log.add("marathi_headers_mapped", len(marathi), entry["file"], name, "Devanagari headers mapped to canonical fields")
            frames.append(df)
    elif fmt == "csv":
        encoding, bom, rows = csv_rows(path)
        h = read["header_row"]
        header = list(rows[h - 1])
        titles = sum(1 for r in rows[: h - 1] if r and str(r[0]).startswith("#"))
        log.add("title_lines_skipped", titles, entry["file"], None, "title lines above the header")
        if bom:
            log.add("bom_removed", 1, entry["file"], None, "UTF-8 byte order mark")
        df = _frame(header, [(i + 1, r) for i, r in enumerate(rows) if i + 1 > h])
        df["src_sheet"] = None
        frames.append(df)
    else:
        frames.append(_read_pdf(entry, path, log))
    df = pd.concat(frames, ignore_index=True)
    df["src_id"] = src_id
    for col in ("src_page", "src_section"):
        if col not in df:
            df[col] = None
    return df


def _read_pdf(entry: dict, path: Path, log: FixLog) -> pd.DataFrame:
    read = entry["read"]
    columns = read["columns"]
    by_col = {spec["source"]["col"]: (f, spec["normalizer"]) for f, spec in entry["fields"].items() if "col" in spec["source"]}
    parts = [PDF_FIELD_PATTERNS.get(by_col.get(label, (None, "text"))[1], r"(.+?)") for label in columns]
    row_re = re.compile("^" + " ".join(parts) + "$")
    head_re = SECTION_PATTERNS[read["section_pattern"]]
    header_text = " ".join(columns)
    rows, section, header_pages, continuation = [], None, set(), set()
    seen_heading_on_page: set[int] = set()
    for page, _, text in pdf_lines(path):
        if text == header_text:
            header_pages.add(page)
            continue
        h = head_re.search(text)
        if h:
            section = (h.group(3).strip(), N.month_from_heading(h.group(1), h.group(2)))
            seen_heading_on_page.add(page)
            continue
        m = row_re.match(text)
        if m and section:
            if page not in seen_heading_on_page:
                continuation.add(page)
            rec = dict(zip(columns, m.groups()))
            rec["_taluka"], rec["_month"] = section
            rec["src_page"] = page
            rec["src_section"] = f"Taluka: {section[0]} | {section[1]}"
            rows.append(rec)
    log.add("pdf_header_repeats_skipped", len(header_pages), entry["file"], None, "table header line repeated on each page")
    log.add("pdf_continuation_pages", len(continuation), entry["file"], None, "pages continuing a section without its heading")
    df = pd.DataFrame(rows, dtype=object)
    sr = next((spec["source"]["col"] for f, spec in entry["fields"].items() if f == "sr_no"), None)
    df["src_row"] = df[sr].astype(int) if sr else range(1, len(df) + 1)
    df["src_sheet"] = None
    return df


def _apply_fields(entry: dict, df: pd.DataFrame, log: FixLog) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    file, sheet = entry["file"], (entry.get("sheet") if entry.get("sheet") != "*" else None)
    fields = entry["fields"]
    order = sorted(fields, key=lambda f: (f == "academic_year", f))  # academic_year last: it may use udise_code as key
    for f in order:
        spec = fields[f]
        src, norm = spec["source"], spec["normalizer"]
        if "col" in src:
            raw = df[src["col"]]
        elif "sheet_name" in src:
            raw = df["src_sheet"]
        elif "section" in src:
            raw = df["_taluka" if src["section"] == "taluka" else "_month"]
        else:
            raw = pd.Series([src["const"]] * len(df), index=df.index, dtype=object)
        out["raw_" + f] = raw
        if norm == "month":
            out[f] = raw
            continue
        if norm == "academic_year":
            keys = out["udise_code"] if "udise_code" in out else None
            values, stats = N.academic_year(raw, keys)
            for kind in ("short", "bare"):
                log.add("year_format_normalized", stats["formats"].get(kind, 0), file, sheet, f"year format {kind}")
            if stats["bare_year_convention"]:
                log.add("bare_year_convention", 1, file, sheet,
                        f"bare years read as {stats['bare_year_convention']} year; collisions {stats['convention_collisions']}")
        elif norm == "date":
            partner = None
            if f == "from_date" and "to_date" in fields and "col" in fields["to_date"]["source"]:
                partner = df[fields["to_date"]["source"]["col"]]
            values, stats = N.dates(raw, partner)
            for fmt, n in stats["formats"].items():
                log.add("date_format_parsed", n, file, sheet, f"{f}: {fmt}")
        else:
            values, stats = N.REGISTRY[norm](raw)
            if norm == "udise11":
                log.add("code_zero_padded", stats["zero_padded"], file, sheet, "numeric codes lost leading zeros; padded to 11 digits")
            if norm == "subject":
                for label, n in stats["relabelled"].items():
                    log.add("subject_label_normalized", n, file, sheet, f"'{label}' -> canonical subject")
            if norm == "share":
                log.add("percent_to_share", stats["percent_to_share"], file, sheet, f"{f}: percentages converted to 0-1 shares")
            if norm == "yes_no":
                for label, n in stats["marathi_values"].items():
                    log.add("yes_no_marathi", n, file, sheet, f"{f}: '{label}'")
        unparsed = int((values.isna() & raw.map(lambda v: not N._blank(v))).sum())
        log.add("unparsed_values", unparsed, file, sheet, f"{f}: values that did not parse")
        out[f] = values
    for col in SRC_COLUMNS:
        out[col] = df[col].to_numpy()
    return out


# ---------- assembly ----------


def _norm_name(name: str) -> str:
    s = name.lower().replace(".", "").replace(",", "")
    for pat, rep in NAME_ABBREVIATIONS:
        s = re.sub(pat, rep, s)
    return " ".join(s.split())


def _talukas(parts: list[pd.DataFrame]) -> tuple[pd.DataFrame, dict[str, str]]:
    """Canonical taluka per UDISE block code: most frequent Latin spelling; Marathi = most frequent Devanagari."""
    spellings = pd.concat([p[["udise_code", "taluka"]] for p in parts if "taluka" in p], ignore_index=True).dropna()
    spellings["block"] = spellings["udise_code"].str[4:6]
    rows, variants = [], {}
    profile = parts[0]
    for block, g in spellings.groupby("block"):
        counts = Counter(g["taluka"])
        latin = [s for s, _ in counts.most_common() if not _is_devanagari(s)]
        deva = [s for s, _ in counts.most_common() if _is_devanagari(s)]
        tid = f"T{block}"
        rows.append({"taluka_id": tid, "block_code": block, "taluka": latin[0] if latin else deva[0],
                     "taluka_mr": deva[0] if deva else None,
                     "n_schools": int((profile["udise_code"].str[4:6] == block).sum())})
        for s in counts:
            variants[s.lower()] = tid
    return pd.DataFrame(rows), variants


def _resolve_logged(df: pd.DataFrame, variants: dict[str, str], canonical: dict[str, str], talukas: pd.DataFrame,
                    file: str, log: FixLog) -> pd.Series:
    """Resolve taluka names in tables without UDISE codes; log spelling variants and unresolved names."""
    ids = _resolve_names(df["taluka"], variants, canonical)
    name_of = talukas.set_index("taluka_id")["taluka"]
    differs = ids.notna() & (df["taluka"] != ids.map(name_of))
    log.add("taluka_variant_resolved", int(differs.sum()), file, None, "taluka spelling resolved by name", df.loc[differs, "taluka"].unique())
    log.add("taluka_name_unresolved", int(ids.isna().sum()), file, None, "taluka names that matched no known taluka",
            df.loc[ids.isna(), "taluka"].unique())
    return ids


def _resolve_names(names: pd.Series, variants: dict[str, str], canonical: dict[str, str]) -> pd.Series:
    def one(n):
        if n is None:
            return None
        if n.lower() in variants:
            return variants[n.lower()]
        close = difflib.get_close_matches(n.lower(), list(canonical), n=1, cutoff=0.8)
        return canonical[close[0]] if close else None
    return names.map(one)


def _variant_fixes(df: pd.DataFrame, talukas: pd.DataFrame, file: str, log: FixLog) -> None:
    name_of = talukas.set_index("taluka_id")["taluka"]
    tid = "T" + df["udise_code"].str[4:6]
    differs = df["taluka"].notna() & (df["taluka"] != tid.map(name_of))
    for sheet, g in df[differs].groupby(df["src_sheet"].fillna(""), dropna=False):
        log.add("taluka_variant_resolved", len(g), file, sheet or None, "taluka spelling resolved through the UDISE block code",
                g["taluka"].unique())


def _dedupe(df: pd.DataFrame, key: list[str], file: str, log: FixLog) -> pd.DataFrame:
    raw_cols = [c for c in df.columns if c.startswith("raw_")]
    exact = df.duplicated(raw_cols, keep="first")
    log.add("exact_duplicates_removed", int(exact.sum()), file, None, "identical rows removed (first kept)",
            df.loc[exact, "src_row"])
    df = df.loc[~exact]
    conflict = df.duplicated(key, keep=False)
    if conflict.any():
        log.add("conflicting_duplicates", int(conflict.sum()), file, None,
                f"same {key} with different values; first kept, all flagged", df.loc[conflict, "src_row"])
    return df.drop_duplicates(key, keep="first")


def _link_attendance(att: pd.DataFrame, crosswalk: pd.DataFrame, schools: pd.DataFrame, file: str, log: FixLog) -> pd.DataFrame:
    cw = dict(zip(crosswalk["short_code"], crosswalk["udise_code"]))
    links = []
    linked = set(cw.values())
    pdf_schools = att.drop_duplicates("short_code")[["short_code", "school_name", "taluka_id", "enrolled"]]
    for r in pdf_schools.itertuples(index=False):
        if r.short_code in cw:
            links.append((r.short_code, cw[r.short_code], "crosswalk", 1.0))
    log.add("link_crosswalk", len(links), file, None, "short codes linked through crosswalk.xlsx")
    unmatched = pdf_schools[~pdf_schools["short_code"].isin(cw)]
    # One-to-one assignment within each taluka: best-scoring (name similarity, then closest enrolment) pairs
    # first; each school and each short code is used once. Pairs below NAME_MATCH_MIN are never accepted.
    enrol = schools.set_index("udise_code")["enrol_total"]
    pairs = []
    for r in unmatched.itertuples(index=False):
        cands = schools[(schools["taluka_id"] == r.taluka_id) & ~schools["udise_code"].isin(linked)]
        q = _norm_name(r.school_name)
        for n, c in zip(cands["school_name"], cands["udise_code"]):
            score = difflib.SequenceMatcher(None, q, _norm_name(n)).ratio()
            if score >= NAME_MATCH_MIN:
                total = enrol.get(c)
                gap = abs(float(r.enrolled) - float(total)) / max(float(total), 1.0) if pd.notna(r.enrolled) and pd.notna(total) else 1.0
                pairs.append((-round(score, 6), round(gap, 6), r.short_code, c))
    taken_codes, matched = set(), []
    for neg_score, _, short, udise in sorted(pairs):
        if short in matched or udise in taken_codes:
            continue
        links.append((short, udise, "name_match", round(-neg_score, 3)))
        taken_codes.add(udise)
        matched.append(short)
    unresolved = [s for s in unmatched["short_code"] if s not in matched]
    log.add("link_name_match", len(matched), file, None,
            f"short codes missing from the crosswalk, matched one-to-one by name within the taluka (min similarity {NAME_MATCH_MIN})",
            matched)
    log.add("link_unresolved", len(unresolved), file, None, "short codes that could not be linked; rows kept in ingest_unresolved", unresolved)
    return pd.DataFrame(links, columns=["short_code", "udise_code", "link_method", "link_score"])


def _sources(raw: Path) -> dict[str, dict]:
    out = {}
    for i, path in enumerate(sorted(p for p in raw.iterdir() if p.suffix.lower() in FORMATS), start=1):
        fmt = FORMATS[path.suffix.lower()]
        synthetic, marker_at = False, None
        if fmt == "xlsx":
            first = next(iter(xlsx_rows(path).values()))
            if first and first[0] and "SYNTHETIC" in str(first[0][0]):
                synthetic, marker_at = True, "cell A1 of every sheet" if all(
                    r and r[0] and "SYNTHETIC" in str(r[0][0]) for r in xlsx_rows(path).values()) else "cell A1"
        elif fmt == "csv":
            rows = csv_rows(path)[2]
            if rows and "SYNTHETIC" in " ".join(rows[0]):
                synthetic, marker_at = True, "line 1"
        else:
            lines = pdf_lines(path)
            pages = {p for p, _, t in lines if "SYNTHETIC" in t}
            if pages:
                synthetic = True
                marker_at = "every page" if len(pages) == pdf_page_count(path) else f"{len(pages)} pages"
        out[path.name] = {"id": f"S{i}", "file": path.name, "kind": fmt, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                          "synthetic": synthetic, "marker_at": marker_at}
    return out


def ingest(raw_dir: str | Path, db_path: str | Path | None = None, mapping: dict | None = None,
           proposer: str = "rule") -> IngestResult:
    """proposer: "rule" (deterministic baseline) or "llm" (Claude proposes, code validates; falls back to "rule")."""
    raw = Path(raw_dir)
    log = FixLog()
    proposer_info = {"source": "provided" if mapping else "rule"}
    if mapping is None and proposer == "llm":
        from ..llm.mapper import propose_with_llm

        mapping, proposer_info = propose_with_llm(raw)
    mapping = mapping or M.propose(raw)
    errors = M.validate(mapping, raw)
    if errors:
        raise IngestError(errors)
    sources = _sources(raw)
    by_role: dict[str, list[tuple[dict, pd.DataFrame]]] = {}
    for entry in mapping["entries"]:
        df = _read_entry(entry, raw, sources, log)
        by_role.setdefault(entry["role"], []).append((entry, _apply_fields(entry, df, log)))

    def role(name):
        return by_role[name][0]

    prof_e, profile = role("school_profile")
    parts = [profile] + [d for r in ("enrolment", "infrastructure") for _, d in by_role.get(r, [])]
    talukas, variants = _talukas(parts)
    canonical_names = {n.lower(): t for n, t in zip(talukas["taluka"], talukas["taluka_id"])}
    for r in ("school_profile", "enrolment", "infrastructure", "teacher_posts"):
        for e, d in by_role.get(r, []):
            if "taluka" in d:
                _variant_fixes(d, talukas, e["file"], log)

    schools = profile.copy()
    schools["taluka_id"] = "T" + schools["udise_code"].str[4:6]
    for r in ("enrolment", "infrastructure"):
        for _, d in by_role.get(r, []):
            keep = [c for c in d.columns if c in CANONICAL_COLUMNS["schools"] and c not in ("udise_code", "school_name", "taluka_id")]
            extra = d[["udise_code", *keep, "src_row"]].rename(columns={"src_row": f"src_row_{r}"})
            schools = schools.merge(extra, on="udise_code", how="left")

    _, cw = role("crosswalk")
    att_e, att = role("attendance_pdf")
    att["taluka_id"] = _resolve_logged(att, variants, canonical_names, talukas, att_e["file"], log)
    links = _link_attendance(att, cw, schools, att_e["file"], log)
    att = att.merge(links, on="short_code", how="left")
    schools = schools.merge(links.drop_duplicates("udise_code")[["udise_code", "short_code"]], on="udise_code", how="left")
    unresolved = att[att["udise_code"].isna()]
    att = att[att["udise_code"].notna()].copy()
    att["academic_year"] = att["month"].map(N.academic_year_of_month)

    sc_e, scores = role("scores")
    scores = _dedupe(scores, ["udise_code", "academic_year", "subject"], sc_e["file"], log)
    scores["taluka_id"] = "T" + scores["udise_code"].str[4:6]

    posts = pd.concat([d for _, d in by_role["teacher_posts"]], ignore_index=True)
    tp_file = by_role["teacher_posts"][0][0]["file"]
    posts["taluka_id"] = "T" + posts["udise_code"].str[4:6]
    if "vacant" in posts:
        expected = posts["sanctioned"] - posts["working"]
        negative = (posts["vacant"] < 0) & (posts["vacant"] == -expected)
        log.add("negative_vacancy_recomputed", int(negative.sum()), tp_file, None,
                "vacancy stored as working - sanctioned; recomputed as sanctioned - working",
                posts.loc[negative, "src_sheet"].unique())
        mismatch = (posts["vacant"].abs() != expected.abs()) & posts["vacant"].notna()
        log.add("vacancy_mismatch", int(mismatch.sum()), tp_file, None, "vacant column disagrees with sanctioned - working")
    posts = _dedupe(posts, ["udise_code", "academic_year", "subject"], tp_file, log)

    el_e, election = role("election_duty")
    election["taluka_id"] = _resolve_logged(election, variants, canonical_names, talukas, el_e["file"], log)
    election["month"] = election["from_date"].map(lambda d: None if d is None else f"{d.year:04d}-{d.month:02d}")
    election["academic_year"] = election["month"].map(lambda m: None if m is None else N.academic_year_of_month(m))
    election = _dedupe(election, ["taluka_id", "month"], el_e["file"], log)

    talukas["poverty_index"] = pd.Series([None] * len(talukas), dtype="Float64")
    if "taluka_profile" in by_role:
        pr_e, profile_t = role("taluka_profile")
        profile_t = profile_t.assign(taluka_id=_resolve_logged(profile_t, variants, canonical_names, talukas, pr_e["file"], log))
        poverty = profile_t.dropna(subset=["taluka_id"]).drop_duplicates("taluka_id").set_index("taluka_id")["poverty_index"]
        talukas["poverty_index"] = talukas["taluka_id"].map(poverty).astype("Float64")

    tables = {
        "talukas": talukas.assign(src_id=sources[prof_e["file"]]["id"], src_sheet=prof_e["sheet"], src_page=None,
                                  src_section=None, src_row=None),
        "schools": schools,
        "scores": scores,
        "attendance": att,
        "teacher_posts": posts,
        "election_duty": election,
    }
    for name, cols in CANONICAL_COLUMNS.items():
        extra = [c for c in tables[name].columns if c.startswith("src_row_") or c in ("short_code", "link_method", "link_score")
                 and name == "attendance"]
        tables[name] = tables[name][cols + [c for c in extra if c not in cols] + SRC_COLUMNS].sort_values(
            [c for c in ("udise_code", "taluka_id", "academic_year", "month", "subject") if c in cols]).reset_index(drop=True)
    tables["school_links"] = links.sort_values("short_code").reset_index(drop=True)
    tables["ingest_unresolved"] = unresolved[["short_code", "school_name", "taluka_id", "month"] + SRC_COLUMNS].reset_index(drop=True)
    tables["sources"] = pd.DataFrame(list(sources.values()))
    tables["ingest_fixes"] = pd.DataFrame(log.items, columns=["kind", "unit", "count", "file", "sheet", "detail", "examples"])

    mapping_sha = hashlib.sha256(json.dumps(mapping, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    report = {
        "synthetic": any(s["synthetic"] for s in sources.values()),
        "mapping_source": mapping.get("source", "provided"),
        "mapping_proposer": proposer_info,
        "mapping_sha256": mapping_sha,
        "sources": list(sources.values()),
        "tables": {k: int(len(v)) for k, v in tables.items() if k in CANONICAL_COLUMNS},
        "fixes": log.items,
        "unresolved_rows": int(len(unresolved)),
    }
    if db_path is not None:
        write_duckdb(tables, db_path)
    return IngestResult(tables=tables, report=report, mapping=mapping, db_path=None if db_path is None else str(db_path))


def write_duckdb(tables: dict[str, pd.DataFrame], db_path: str | Path) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        for name, df in tables.items():
            frame = df.copy()
            for col in frame.columns:
                if frame[col].dtype == object:
                    frame[col] = frame[col].map(lambda v: None if v is None else (json.dumps(v) if isinstance(v, list) else str(v)))
            con.register("_frame", frame)
            con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM _frame")
            con.unregister("_frame")
    finally:
        con.close()
