"""Analysis inputs after trust exclusions, plus the small statistics the cause tester needs (numpy only)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

SUBJECT = "maths"


def _excluded(flags: pd.DataFrame, metric: str) -> pd.DataFrame:
    f = flags[(flags["entity_kind"] == "school") & (flags["metric"] == metric) & flags["label"].eq("RED_FLAG")]
    return f[["entity_id", "period_from", "period_to"]]


def analysis_scores(tables: dict, trust) -> pd.DataFrame:
    """Maths scores without the cells trust flagged (score spikes); flagged schools otherwise stay in."""
    sc = tables["scores"]
    sc = sc[sc["subject"] == SUBJECT][["udise_code", "taluka_id", "academic_year", "mean_score", "students_appeared"]].copy()
    ex = _excluded(trust.flags, "scores")
    drop = set(zip(ex["entity_id"], ex["period_to"]))
    return sc[[(c, y) not in drop for c, y in zip(sc["udise_code"], sc["academic_year"])]].reset_index(drop=True)


def analysis_attendance(tables: dict, trust) -> pd.DataFrame:
    """Attendance without flagged months (flat runs, jumps), per the trust-exclusion rule."""
    att = tables["attendance"][["udise_code", "taluka_id", "academic_year", "month", "attendance_pct"]].copy()
    ex = _excluded(trust.flags, "attendance")
    keep = np.ones(len(att), dtype=bool)
    for code, frm, to in ex.itertuples(index=False):
        keep &= ~((att["udise_code"] == code) & (att["month"] >= frm) & (att["month"] <= to)).to_numpy()
    return att[keep].reset_index(drop=True)


def taluka_means(sc: pd.DataFrame) -> pd.DataFrame:
    return sc.groupby(["taluka_id", "academic_year"])["mean_score"].mean().unstack()


def school_wide(sc: pd.DataFrame) -> pd.DataFrame:
    return sc.pivot(index="udise_code", columns="academic_year", values="mean_score")


def welch_t(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    se = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return float((a.mean() - b.mean()) / se) if se > 0 else float("nan")


def paired_t(diff) -> float:
    d = np.asarray(diff, float)
    if len(d) < 2 or d.std(ddof=1) == 0:
        return float("nan")
    return float(d.mean() / (d.std(ddof=1) / math.sqrt(len(d))))


def corr_t(x, y) -> tuple[float, float, int]:
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = ~(np.isnan(x) | np.isnan(y))
    x, y = x[ok], y[ok]
    n = len(x)
    if n < 3 or x.std() == 0 or y.std() == 0:
        return float("nan"), float("nan"), n
    r = float(np.corrcoef(x, y)[0, 1])
    t = r * math.sqrt((n - 2) / max(1 - r * r, 1e-12))
    return r, float(t), n
