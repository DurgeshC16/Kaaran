"""Value normalizers (closed registry). Each returns (values, stats) so every fix can be reported."""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter

import pandas as pd

YEAR_MIN, YEAR_MAX = 2000, 2100
# A bare year like "2024" is ambiguous. The convention giving no duplicate (school, year) keys wins;
# with no evidence either way, END year is assumed (2024 = 2023-24), the usual board-exam reading.
DEFAULT_BARE_YEAR = "end"
# Ambiguous day/month dates (01/10/2024) default to day-first, the Indian convention.
DEFAULT_DATE_ORDER = "dmy"
DATE_FORMATS = {
    "dmy_slash": "%d/%m/%Y", "mdy_slash": "%m/%d/%Y", "ymd_dash": "%Y-%m-%d", "dmy_dash": "%d-%m-%Y",
    "mdy_dash": "%m-%d-%Y", "dmy_dot": "%d.%m.%Y",
}
SUBJECTS = {
    "maths": {"maths", "math", "mathematics", "गणित"},
    "language": {"language", "marathi", "भाषा", "मराठी"},
    "other": {"other", "others", "इतर"},
}
YES = {"1", "yes", "y", "true", "होय", "हो"}
NO = {"0", "no", "n", "false", "नाही"}
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"],
    start=1)}


def _blank(v) -> bool:
    return v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == ""


def text(values: pd.Series) -> tuple[pd.Series, dict]:
    return values.map(lambda v: None if _blank(v) else " ".join(str(v).split())), {}


def code(values: pd.Series) -> tuple[pd.Series, dict]:
    return values.map(lambda v: None if _blank(v) else str(v).strip().upper()), {}


def udise11(values: pd.Series) -> tuple[pd.Series, dict]:
    """11-digit string codes; numbers that lost leading zeros are zero-padded."""
    padded = 0
    out = []
    for v in values:
        if _blank(v):
            out.append(None)
            continue
        s = str(int(v)) if isinstance(v, (int, float)) else str(v).strip()
        s = s[:-2] if s.endswith(".0") else s
        if s.isdigit() and 9 <= len(s) < 11:
            s, padded = s.zfill(11), padded + 1
        out.append(s if s.isdigit() and len(s) == 11 else None)
    return pd.Series(out, index=values.index, dtype=object), {"zero_padded": padded}


def _number(v):
    if _blank(v):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def float_(values: pd.Series) -> tuple[pd.Series, dict]:
    return values.map(_number).astype("Float64"), {}


def int_(values: pd.Series) -> tuple[pd.Series, dict]:
    nums = values.map(_number)
    return nums.map(lambda x: None if x is None else int(round(x))).astype("Int64"), {}


def yes_no(values: pd.Series) -> tuple[pd.Series, dict]:
    marathi = Counter()
    out = []
    for v in values:
        s = "" if _blank(v) else str(v).strip().lower()
        if s in ("होय", "हो", "नाही"):
            marathi[s] += 1
        out.append(1 if s in YES else 0 if s in NO else None)
    return pd.Series(out, index=values.index).astype("Int64"), {"marathi_values": dict(marathi)}


def subject(values: pd.Series) -> tuple[pd.Series, dict]:
    relabelled = Counter()
    out = []
    for v in values:
        s = "" if _blank(v) else str(v).strip()
        key = next((k for k, labels in SUBJECTS.items() if s.lower() in labels), None)
        if key and s.lower() != key:
            relabelled[s] += 1
        out.append(key)
    return pd.Series(out, index=values.index, dtype=object), {"relabelled": dict(relabelled)}


def _year_kind(s: str) -> str | None:
    if re.fullmatch(r"\d{4}-\d{2}", s):
        return "long"
    if re.fullmatch(r"\d{2}-\d{2}", s):
        return "short"
    if re.fullmatch(r"\d{4}", s):
        return "bare"
    return None


def _year_label(s: str, kind: str, convention: str) -> str | None:
    if kind == "long":
        start = int(s[:4])
    elif kind == "short":
        start = 2000 + int(s[:2])
    else:
        start = int(s) - 1 if convention == "end" else int(s)
    if not YEAR_MIN <= start <= YEAR_MAX:
        return None
    return f"{start}-{(start + 1) % 100:02d}"


def academic_year(values: pd.Series, keys: pd.Series | None = None) -> tuple[pd.Series, dict]:
    """'2023-24' / '23-24' / bare year -> '2023-24'. The bare-year convention is detected from the data:
    the reading that yields no duplicate (key, year) pairs wins (keys = e.g. school code)."""
    raw = values.map(lambda v: None if _blank(v) else str(v).strip().replace(".0", ""))
    kinds = raw.map(lambda s: None if s is None else _year_kind(s))
    counts = Counter(k for k in kinds if k)
    collisions = {}
    convention = DEFAULT_BARE_YEAR
    if counts.get("bare") and keys is not None:
        for conv in ("end", "start"):
            labels = [None if k is None else _year_label(s, k, conv) for s, k in zip(raw, kinds)]
            collisions[conv] = int(pd.DataFrame({"k": keys.to_numpy(), "y": labels}).duplicated().sum())
        if collisions["start"] < collisions["end"]:
            convention = "start"
    out = [None if k is None else _year_label(s, k, convention) for s, k in zip(raw, kinds)]
    stats = {"formats": dict(counts), "bare_year_convention": convention if counts.get("bare") else None,
             "convention_collisions": collisions, "unparsed": int(sum(1 for s, k in zip(raw, kinds) if s and not k))}
    return pd.Series(out, index=values.index, dtype=object), stats


def academic_year_of_month(month: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    start = y if m >= 6 else y - 1
    return f"{start}-{(start + 1) % 100:02d}"


def month_from_heading(month_name: str, year: str) -> str | None:
    m = MONTHS.get(month_name.lower())
    return f"{int(year):04d}-{m:02d}" if m else None


def _parse(s: str, fmt: str) -> dt.date | None:
    try:
        return dt.datetime.strptime(s, fmt).date()
    except ValueError:
        return None


def dates(values: pd.Series, partner: pd.Series | None = None) -> tuple[pd.Series, dict]:
    """Parse a date column. Day/month order is chosen per column: the order under which every value
    parses (and, with a partner To column, From <= To within one month); ties -> DEFAULT_DATE_ORDER."""
    raw = values.map(lambda v: None if _blank(v) else (v.date().isoformat() if hasattr(v, "date") else str(v).strip()))
    praw = None if partner is None else partner.map(lambda v: None if _blank(v) else str(v).strip())
    shape = raw.map(lambda s: None if s is None else ("slash" if "/" in s else "dot" if "." in s else
                                                      "ymd" if re.match(r"\d{4}-", s) else "dash"))
    chosen = {}
    for sh in sorted(set(shape.dropna())):
        options = {"slash": ["dmy_slash", "mdy_slash"], "dash": ["dmy_dash", "mdy_dash"], "dot": ["dmy_dot"], "ymd": ["ymd_dash"]}[sh]
        idx = shape[shape == sh].index
        ok = {}
        for opt in options:
            parsed = [_parse(raw[i], DATE_FORMATS[opt]) for i in idx]
            valid = sum(p is not None for p in parsed)
            if praw is not None:
                to = [None if praw[i] is None else _first_parse(praw[i], DATE_FORMATS[opt]) for i in idx]
                valid = sum(p is not None and t is not None and p <= t and (t - p).days <= 31 for p, t in zip(parsed, to))
            ok[opt] = valid
        best = max(ok.values())
        winners = [o for o in options if ok[o] == best]
        chosen[sh] = next((o for o in winners if o.startswith(DEFAULT_DATE_ORDER)), winners[0])
    out, counts = [], Counter()
    for s, sh in zip(raw, shape):
        d = None if s is None else _parse(s, DATE_FORMATS[chosen[sh]])
        if d is not None:
            counts[DATE_FORMATS[chosen[sh]]] += 1
        out.append(d)
    unparsed = sum(1 for s, d in zip(raw, out) if s and d is None)
    return pd.Series(out, index=values.index, dtype=object), {"formats": dict(counts), "unparsed": unparsed}


def _first_parse(s: str, preferred: str) -> dt.date | None:
    d = _parse(s, preferred)
    if d:
        return d
    return next((p for f in DATE_FORMATS.values() if (p := _parse(s, f))), None)


REGISTRY = {"text": text, "code": code, "udise11": udise11, "float": float_, "int": int_, "yes_no": yes_no,
            "subject": subject, "academic_year": academic_year, "date": dates}
