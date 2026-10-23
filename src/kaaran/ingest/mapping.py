"""Column mapping: a JSON object that says how each raw file/sheet maps onto canonical fields.

The rule-based `propose()` ships now; in Phase 3 Claude proposes the same JSON from file summaries.
Either way `validate()` checks it against a closed vocabulary (roles, fields, source kinds,
normalizers) before deterministic code applies it. LLM-supplied regexes or code are never accepted.

Mapping v1:
{
  "mapping_version": 1,
  "entries": [
    {"file": "pat_scores.csv", "sheet": null, "role": "scores",
     "read": {"format": "csv", "header_row": 2},
     "fields": {"udise_code": {"source": {"col": "SCHOOL_CD"}, "normalizer": "udise11"}, ...},
     "ignore": []}
  ]
}
Field sources: {"col": <header>} | {"sheet_name": true} | {"section": "taluka" | "month"} | {"const": <value>}.
"""

from __future__ import annotations

import re
from pathlib import Path

from .readers import FORMATS, header_candidates

MAPPING_VERSION = 1

ROLES = {
    "school_profile": ({"udise_code", "school_name", "taluka"}, {"cluster", "cluster_code", "village", "management"}),
    "enrolment": ({"udise_code", "enrol_std1", "enrol_std2", "enrol_std3", "enrol_std4", "enrol_std5"},
                  {"enrol_total", "school_name", "taluka"}),
    "infrastructure": ({"udise_code", "toilets", "library", "drinking_water", "classrooms"}, {"school_name", "taluka"}),
    "crosswalk": ({"short_code", "udise_code"}, {"taluka"}),
    "scores": ({"udise_code", "academic_year", "subject", "mean_score"}, {"std", "students_appeared"}),
    "teacher_posts": ({"udise_code", "academic_year", "subject", "sanctioned", "working"}, {"vacant", "as_on", "school_name", "taluka"}),
    "election_duty": ({"taluka", "from_date", "deployed_pct"}, {"to_date", "duty", "sr_no"}),
    "attendance_pdf": ({"taluka", "month", "school_name", "short_code", "attendance_pct"}, {"sr_no", "enrolled", "present_avg"}),
    "taluka_profile": ({"taluka", "poverty_index"}, set()),
}
OPTIONAL_ROLES = {"taluka_profile"}
NORMALIZERS = ("udise11", "code", "int", "float", "share", "text", "yes_no", "academic_year", "subject", "date", "month")
DEFAULT_NORMALIZER = {
    "udise_code": "udise11", "short_code": "code", "school_name": "text", "taluka": "text", "cluster": "text",
    "cluster_code": "text", "village": "text", "management": "text", "enrol_total": "int", "toilets": "int",
    "library": "yes_no", "drinking_water": "yes_no", "classrooms": "int", "academic_year": "academic_year",
    "subject": "subject", "mean_score": "float", "std": "int", "students_appeared": "int", "sanctioned": "int",
    "working": "int", "vacant": "int", "as_on": "date", "from_date": "date", "to_date": "date", "deployed_pct": "float",
    "duty": "text", "sr_no": "int", "poverty_index": "share", "month": "month", "enrolled": "int", "present_avg": "float", "attendance_pct": "float",
    **{f"enrol_std{i}": "int" for i in range(1, 6)},
}
SECTION_FIELDS = ("taluka", "month")
YEAR_SHEET = re.compile(r"(\d{4}-\d{2}|\d{2}-\d{2}|\d{4})")  # a sheet named like an academic year

# Header synonyms (normalised: lower case, punctuation and underscores to spaces). English and Marathi.
SYNONYMS = {
    "udise_code": ["udise code", "udise", "school cd", "school code", "यूडायस कोड"],
    "school_name": ["school name", "name of school", "शाळेचे नाव"],
    "taluka": ["taluka", "block", "तालुका"],
    "cluster": ["cluster", "kendra"],
    "cluster_code": ["cluster code", "kendra code"],
    "village": ["village name", "village", "गाव"],
    "management": ["management"],
    "enrol_total": ["total", "total enrolment"],
    "toilets": ["toilets", "शौचालये"],
    "library": ["library", "ग्रंथालय"],
    "drinking_water": ["drinking water", "पिण्याचे पाणी"],
    "classrooms": ["classrooms", "वर्गखोल्या"],
    "short_code": ["short code"],
    "academic_year": ["year", "academic year"],
    "std": ["std", "class", "standard"],
    "subject": ["subject", "विषय"],
    "mean_score": ["avg marks", "average marks", "mean score"],
    "students_appeared": ["students appeared"],
    "sanctioned": ["sanctioned"],
    "working": ["working"],
    "vacant": ["vacant", "vacancy"],
    "as_on": ["as on", "as on date"],
    "deployed_pct": ["deployed teachers", "deployed teachers pct", "deployed pct"],
    "from_date": ["from", "from date"],
    "to_date": ["to", "to date"],
    "duty": ["duty", "duty type"],
    "sr_no": ["sr no", "sr", "serial no"],
    "poverty_index": ["poverty index", "poverty headcount ratio", "poverty", "दारिद्र्य निर्देशांक"],
    "enrolled": ["enrolled"],
    "present_avg": ["present avg", "average present"],
    **{f"enrol_std{i}": [f"std {i}", f"class {i}"] for i in range(1, 6)},
}


def norm_header(h) -> str:
    text = "" if h is None else str(h)
    text = re.sub(r"[%()._:/\-]+", " ", text.lower())
    return " ".join(text.split())


_LOOKUP = {s: field for field, syns in SYNONYMS.items() for s in syns if s}


def field_for(header) -> str | None:
    return _LOOKUP.get(norm_header(header))


def _role_for(fields: set[str]) -> str | None:
    best, best_hits = None, 0
    for role, (required, optional) in ROLES.items():
        if role == "attendance_pdf" or not required <= fields:
            continue
        hits = len(fields & (required | optional))
        if hits > best_hits:
            best, best_hits = role, hits
    return best


def propose(raw_dir: str | Path) -> dict:
    """Rule-based baseline: find each table's header row by synonym hits, map columns, pick the role."""
    entries = []
    for path in sorted(Path(raw_dir).iterdir()):
        fmt = FORMATS.get(path.suffix.lower())
        if fmt is None:
            continue
        if fmt == "pdf":
            entries.append(_propose_pdf(path))
            continue
        tables = header_candidates(path)
        signatures = {}
        for sheet, rows in tables.items():
            best_row, best_map = None, {}
            for row_no, cells in rows:
                mapped = {}
                for c in cells:
                    f = field_for(c)
                    if f and f not in mapped:
                        mapped[f] = c
                if len(mapped) >= 2 and len(mapped) > len(best_map):
                    best_row, best_map = row_no, mapped
            if best_row is None:
                continue
            fields = {f: {"source": {"col": str(h)}, "normalizer": DEFAULT_NORMALIZER[f]} for f, h in best_map.items()}
            if "academic_year" not in fields and sheet and YEAR_SHEET.fullmatch(str(sheet).strip()):
                fields["academic_year"] = {"source": {"sheet_name": True}, "normalizer": "academic_year"}
            role = _role_for(set(fields))
            if role is None:
                continue
            allowed = ROLES[role][0] | ROLES[role][1]
            fields = {f: v for f, v in fields.items() if f in allowed}
            headers = [str(c) for c in dict(rows)[best_row] if c not in (None, "")]
            used = {v["source"].get("col") for v in fields.values()}
            entry = {"file": path.name, "sheet": sheet, "role": role, "read": {"format": fmt, "header_row": best_row},
                     "fields": dict(sorted(fields.items())), "ignore": [h for h in headers if h not in used]}
            signatures.setdefault((role, best_row, tuple(sorted(fields))), []).append(entry)
        for (role, _, _), group in signatures.items():
            if role == "teacher_posts" and len(group) > 1:  # one entry for all year sheets with the same layout
                group[0]["sheet"] = "*"
                entries.append(group[0])
            else:
                entries.extend(group)
    return {"mapping_version": MAPPING_VERSION, "source": "rule_baseline", "entries": entries}


def segment_header(line: str) -> list[str]:
    """Split a PDF header line into column labels by longest synonym phrase ('%' is its own label)."""
    words, labels, i = line.split(), [], 0
    while i < len(words):
        if words[i] == "%":
            labels.append("%")
            i += 1
            continue
        for j in range(len(words), i, -1):
            if "%" not in words[i:j] and norm_header(" ".join(words[i:j])) in _LOOKUP:
                labels.append(" ".join(words[i:j]))
                i = j
                break
        else:
            labels.append(words[i])
            i += 1
    return labels


def _pdf_field(label: str) -> str | None:
    return "attendance_pct" if label == "%" else field_for(label)


def _propose_pdf(path: Path) -> dict:
    from .readers import pdf_header_line

    header = segment_header(pdf_header_line(path))
    fields = {f: {"source": {"col": h}, "normalizer": DEFAULT_NORMALIZER[f]} for h in header if (f := _pdf_field(h))}
    fields["taluka"] = {"source": {"section": "taluka"}, "normalizer": "text"}
    fields["month"] = {"source": {"section": "month"}, "normalizer": "month"}
    return {"file": path.name, "sheet": None, "role": "attendance_pdf",
            "read": {"format": "pdf", "section_pattern": "month_year_taluka", "columns": header},
            "fields": dict(sorted(fields.items())), "ignore": []}


def validate(mapping: dict, raw_dir: str | Path) -> list[dict]:
    """Static checks against the files' headers. Errors describe shapes, never cell values."""
    errors: list[dict] = []

    def err(code, entry=None, **kw):
        e = {"code": code}
        if entry is not None:
            e |= {"file": entry.get("file"), "sheet": entry.get("sheet"), "role": entry.get("role")}
        errors.append(e | kw)

    if mapping.get("mapping_version") != MAPPING_VERSION or not isinstance(mapping.get("entries"), list):
        err("SCHEMA", detail="mapping_version 1 with an 'entries' list required")
        return errors
    raw_dir = Path(raw_dir)
    seen_roles: dict[str, int] = {}
    for entry in mapping["entries"]:
        role = entry.get("role")
        if role not in ROLES:
            err("UNKNOWN_ROLE", entry)
            continue
        seen_roles[role] = seen_roles.get(role, 0) + 1
        path = raw_dir / str(entry.get("file"))
        fmt = entry.get("read", {}).get("format")
        if not path.exists() or FORMATS.get(path.suffix.lower()) != fmt:
            err("FILE_NOT_FOUND", entry, detail=f"format {fmt}")
            continue
        required, optional = ROLES[role]
        fields = entry.get("fields", {})
        for f in set(fields) - required - optional:
            err("UNKNOWN_FIELD", entry, field=f)
        for f in required - set(fields):
            err("REQUIRED_FIELD_MISSING", entry, field=f)
        headers = _headers_for(entry, path)
        targets = []
        for f, spec in fields.items():
            if spec.get("normalizer") not in NORMALIZERS:
                err("UNKNOWN_NORMALIZER", entry, field=f)
            src = spec.get("source", {})
            if len(src) != 1 or next(iter(src)) not in ("col", "sheet_name", "section", "const"):
                err("SCHEMA", entry, field=f, detail="source must be one of col | sheet_name | section | const")
                continue
            if "col" in src:
                targets.append(src["col"])
                if headers is not None and src["col"] not in headers:
                    err("HEADER_NOT_FOUND", entry, field=f, column=src["col"])
            if "section" in src and (fmt != "pdf" or src["section"] not in SECTION_FIELDS):
                err("SCHEMA", entry, field=f, detail="section sources exist only for PDF taluka/month")
        if len(targets) != len(set(targets)):
            err("DUPLICATE_TARGET", entry, detail="one source column mapped to two fields")
    for role in ("school_profile", "scores", "attendance_pdf", "crosswalk", "teacher_posts", "election_duty"):
        if role not in seen_roles:
            err("ROLE_MISSING", None, role=role)
    return errors


def _headers_for(entry: dict, path: Path) -> list[str] | None:
    read = entry["read"]
    if read["format"] == "pdf":
        return [str(c) for c in read.get("columns", [])]
    tables = header_candidates(path)
    sheet = entry.get("sheet")
    names = list(tables) if sheet == "*" else [sheet]
    for name in names:
        rows = dict(tables.get(name, []))
        if read.get("header_row") not in rows:
            return []
        return [str(c) for c in rows[read["header_row"]] if c not in (None, "")]
    return []
