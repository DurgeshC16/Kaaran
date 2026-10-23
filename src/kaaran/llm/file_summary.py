"""Deterministic file summaries: the only view of a raw file the mapping proposer (Claude) gets.

Rule 5 / data-not-instructions:
- sheet names and header cells are passed as quoted data;
- each column gets a coarse value-shape profile (e.g. "11-digit code", "integer, 1-100"), never values;
- distinct values are listed only for low-variety columns (<= LOW_VARIETY_MAX values, each <= MAX_VALUE_LEN chars),
  with every digit replaced by 9 ("2023-24" -> "9999-99"); school names, codes and numbers never appear;
- long free text (where an injected instruction could hide) is never shown.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

from ..ingest.readers import FORMATS, csv_rows, xlsx_rows

HEADER_SCAN_ROWS = 15
SAMPLE_ROWS = 400
LOW_VARIETY_MAX = 30
MAX_VALUE_LEN = 30


def _cells(row) -> list:
    return list(row) if row else []


def _filled(row) -> int:
    return sum(1 for c in _cells(row) if c is not None and str(c).strip() != "")


def _is_numberlike(v) -> bool:
    return isinstance(v, (int, float)) or bool(re.fullmatch(r"-?\d+(\.\d+)?%?", str(v).strip()))


def detect_header_row(rows: list) -> int | None:
    """First row (1-based) whose filled cells are all text and number at least 60% of the widest early row."""
    early = rows[:HEADER_SCAN_ROWS]
    widest = max((_filled(r) for r in rows[:20]), default=0)
    need = max(2, math.ceil(0.6 * widest))
    for i, r in enumerate(early):
        cells = [c for c in _cells(r) if c is not None and str(c).strip() != ""]
        if len(cells) >= need and not any(_is_numberlike(c) for c in cells):
            return i + 1
    return None


def _shape(v) -> str:
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int) or (isinstance(v, float) and float(v).is_integer()):
        n = abs(int(v))
        digits = len(str(n))
        return "11-digit code" if digits == 11 else ("9-10 digit number (code with lost leading zeros?)" if digits in (9, 10) else "integer")
    if isinstance(v, float):
        return "decimal"
    s = str(v).strip()
    if re.fullmatch(r"\d{11}", s):
        return "11-digit code"
    if re.fullmatch(r"[A-Z]{1,4}\d{3,8}", s):
        return "short alphanumeric code"
    if re.fullmatch(r"-?\d+", s):
        return "integer"
    if re.fullmatch(r"-?\d+\.\d+%?", s):
        return "decimal"
    if re.fullmatch(r"\d{1,4}[/.\-]\d{1,2}[/.\-]\d{2,4}", s):
        return "date"
    if re.fullmatch(r"\d{4}-\d{2}|\d{2}-\d{2}|\d{4}", s):
        return "year label"
    if any("ऀ" <= ch <= "ॿ" for ch in s):
        return "Devanagari text"
    return "text"


def _magnitude(values) -> str:
    nums = []
    for v in values:
        try:
            nums.append(abs(float(str(v).replace("%", ""))))
        except ValueError:
            pass
    if not nums:
        return ""
    top = max(nums)
    for limit, label in ((1, "between 0 and 1"), (100, "up to 100"), (1000, "up to 1000")):
        if top <= limit:
            return label
    return "above 1000"


def _mask(s: str) -> str:
    return re.sub(r"\d", "9", s)


def profile_column(values: list) -> dict:
    vals = [v for v in values if v is not None and str(v).strip() != ""]
    filled = len(vals) / len(values) if values else 0.0
    if not vals:
        return {"filled": "empty"}
    shapes = Counter(_shape(v) for v in vals)
    main = shapes.most_common(1)[0][0]
    prof = {"filled": "mostly" if filled >= 0.8 else ("partly" if filled >= 0.2 else "rarely"), "shape": main}
    if len(shapes) > 1:
        prof["other_shapes"] = sorted(s for s in shapes if s != main)
    if main in ("integer", "decimal"):
        prof["magnitude"] = _magnitude(vals)
        if any(float(str(v).replace("%", "")) < 0 for v in vals if _is_numberlike(v)):
            prof["has_negative"] = True
    distinct = {str(v).strip() for v in vals}
    prof["distinct"] = "few" if len(distinct) <= 5 else ("some" if len(distinct) <= LOW_VARIETY_MAX else "many")
    numeric_like = main in ("integer", "decimal", "11-digit code", "9-10 digit number (code with lost leading zeros?)",
                            "short alphanumeric code")
    if len(distinct) <= LOW_VARIETY_MAX and not numeric_like and all(len(d) <= MAX_VALUE_LEN for d in distinct):
        prof["values"] = sorted({_mask(d) for d in distinct})
    return prof


def summarize_table(file: str, sheet: str | None, rows: list) -> dict:
    h = detect_header_row(rows)
    out = {"file": file, "sheet": sheet, "physical_rows": len(rows), "header_row": h}
    if h is None:
        return out | {"note": "no header row found"}
    header = _cells(rows[h - 1])
    data = rows[h:h + SAMPLE_ROWS]
    out["title_rows_above_header"] = sum(1 for r in rows[: h - 1] if _filled(r))
    cols = []
    for j, name in enumerate(header):
        if name is None or str(name).strip() == "":
            continue
        values = [(_cells(r)[j] if j < len(_cells(r)) else None) for r in data]
        cols.append({"header": str(name), "profile": profile_column(values)})
    out["columns"] = cols
    return out


def summarize(raw_dir: str | Path) -> list[dict]:
    """Summaries for every tabular file (xlsx sheets, csv). PDFs keep their rule-based header parsing."""
    tables = []
    for path in sorted(Path(raw_dir).iterdir()):
        fmt = FORMATS.get(path.suffix.lower())
        if fmt == "xlsx":
            for sheet, rows in xlsx_rows(path).items():
                tables.append(summarize_table(path.name, sheet, rows))
        elif fmt == "csv":
            _, _, rows = csv_rows(path)
            tables.append(summarize_table(path.name, None, list(rows)))
    return tables
