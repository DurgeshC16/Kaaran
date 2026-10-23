"""Trust rules: pure functions over the canonical tables. Constants are documented in docs/CONFIDENCE_RULES.md.

None of these thresholds is fitted to a seed or copied from the answer key; each has its own rationale
(see the constant comments and CONFIDENCE_RULES.md, which also records a multi-seed robustness check).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

# --- flat attendance (TRUST-FLAT-SCHOOL / TRUST-FLAT-TALUKA)
FLAT_VALUE_MIN = 99.95  # reported monthly average attendance of 100.0% (rounded)
FLAT_RUN_MIN_MONTHS = 3  # three calendar-consecutive months at 100% is implausible for a whole school
TALUKA_FLAT_MIN_SCHOOLS = 10  # a concentration needs enough schools to be more than chance
TALUKA_FLAT_RATIO_MIN = 3.0  # taluka share of flat schools at least 3x the rest of the district

# --- attendance jumps vs the school's own history (TRUST-JUMP-ATTENDANCE)
JUMP_MIN_PP = 10.0  # a month-to-month swing of 10 percentage points (after removing the district's seasonal change)
JUMP_Z_MIN = 4.0  # ... that is also 4 robust SDs outside the school's own month-to-month changes
JUMP_MAD_FLOOR = 0.5  # pp; floor on the robust SD so very steady schools do not produce infinite z
JUMP_MIN_MONTHS = 4  # need at least 4 months to speak of a history

# --- score spikes (TRUST-SPIKE-SCORE)
SCORE_JUMP_MIN = 20.0  # points between consecutive years
SCORE_Z_MIN = 5.0  # sampling-noise z (scaled by students tested; noise SD estimated from the data)
SCORE_REVERT_SHARE = 0.5  # a spike is a jump whose next change recovers at least half of it

# --- missing data (TRUST-MISSING-SCHOOL / TRUST-INSUFFICIENT-TALUKA)
MISSING_MONTHS_MIN = 3  # of the attendance months present in the file for the school's taluka
MISSING_YEARS_MIN = 2  # of the score years present in the file
TALUKA_INSUFFICIENT_SHARE = 0.20  # one school in five without usable data makes taluka comparisons unreliable

# --- cleared low attendance (TRUST-CLEARED)
CLEARED_SHARE = 0.05  # district-wide lowest 5% by mean attendance ...
CLEARED_MIN_MONTHS = 7  # ... among schools with at least 7 months reported and no trust flag


def month_index(month: str) -> int:
    return int(month[:4]) * 12 + int(month[5:7]) - 1


def flat_runs(att: pd.DataFrame) -> pd.DataFrame:
    """Runs of >= FLAT_RUN_MIN_MONTHS calendar-consecutive months at 100%. A missing month breaks a run."""
    rows = []
    hits = att[att["attendance_pct"] >= FLAT_VALUE_MIN].sort_values(["udise_code", "month"])
    for code, g in hits.groupby("udise_code"):
        idx = g["month"].map(month_index).to_list()
        months = g["month"].to_list()
        start = 0
        for i in range(1, len(idx) + 1):
            if i == len(idx) or idx[i] != idx[i - 1] + 1:
                if i - start >= FLAT_RUN_MIN_MONTHS:
                    rows.append({"udise_code": code, "first_month": months[start], "last_month": months[i - 1],
                                 "n_months": i - start, "src_rows": g.iloc[start:i]})
                start = i
    return pd.DataFrame(rows, columns=["udise_code", "first_month", "last_month", "n_months", "src_rows"])


def attendance_jumps(att: pd.DataFrame) -> pd.DataFrame:
    """Month-to-month swings far outside the school's own history, after removing the district's seasonal change."""
    a = att[["udise_code", "month", "attendance_pct"]].copy()
    a["resid"] = a["attendance_pct"] - a.groupby("month")["attendance_pct"].transform("median")
    a = a.sort_values(["udise_code", "month"])
    a["d"] = a.groupby("udise_code")["resid"].diff()
    a["prev_month"] = a.groupby("udise_code")["month"].shift()
    out = []
    for code, g in a.groupby("udise_code"):
        if len(g) < JUMP_MIN_MONTHS:
            continue
        d = g["d"].dropna()
        med = d.median()
        sd = max(1.4826 * (d - med).abs().median(), JUMP_MAD_FLOOR)
        z = (d - med) / sd
        hit = (d.abs() >= JUMP_MIN_PP) & (z.abs() >= JUMP_Z_MIN)
        for i in d.index[hit]:
            out.append({"udise_code": code, "from_month": g.at[i, "prev_month"], "to_month": g.at[i, "month"],
                        "change_pp": round(float(d[i]), 2), "z": round(float(z[i]), 2)})
    return pd.DataFrame(out, columns=["udise_code", "from_month", "to_month", "change_pp", "z"])


def score_jumps(scores: pd.DataFrame) -> pd.DataFrame:
    """Large year-over-year changes, z scaled by sampling noise; classified spike / persisting / unconfirmed."""
    s = scores.sort_values(["udise_code", "academic_year"]).copy()
    g = s.groupby("udise_code")
    s["prev_score"], s["prev_n"], s["prev_year"] = g["mean_score"].shift(), g["students_appeared"].shift(), g["academic_year"].shift()
    s["next_score"] = g["mean_score"].shift(-1)
    pairs = s.dropna(subset=["prev_score"]).copy()
    pairs["delta"] = pairs["mean_score"] - pairs["prev_score"]
    pairs["se_unit"] = np.sqrt(1 / pairs["students_appeared"].astype(float) + 1 / pairs["prev_n"].astype(float))
    sigma = float((pairs["delta"].abs() / pairs["se_unit"]).median() / 0.6745)  # robust student-level noise SD
    pairs["z"] = pairs["delta"] / (sigma * pairs["se_unit"])
    big = pairs[(pairs["delta"].abs() >= SCORE_JUMP_MIN) & (pairs["z"].abs() >= SCORE_Z_MIN)].copy()

    def status(r):
        if pd.isna(r["next_score"]):
            return "unconfirmed"
        back = r["next_score"] - r["mean_score"]
        return "spike" if np.sign(back) == -np.sign(r["delta"]) and abs(back) >= SCORE_REVERT_SHARE * abs(r["delta"]) else "persisting"

    big["status"] = big.apply(status, axis=1) if len(big) else pd.Series(dtype=object)
    big["sigma"] = sigma
    return big[["udise_code", "prev_year", "academic_year", "delta", "z", "status", "sigma"]].reset_index(drop=True)


def missing_data(schools: pd.DataFrame, att: pd.DataFrame, scores: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(per-school missing counts, every missing (school, month) pair). Expected months are the months present in
    the file for the school's taluka; expected years are the score years present in the file."""
    months_by_taluka = att.groupby("taluka_id")["month"].agg(lambda s: sorted(set(s)))
    years = sorted(set(scores["academic_year"]))
    have_m = att.groupby("udise_code")["month"].agg(set)
    have_y = scores.groupby("udise_code")["academic_year"].agg(set)
    per_school, pairs = [], []
    for code, tid in zip(schools["udise_code"], schools["taluka_id"]):
        expected = months_by_taluka.get(tid, [])
        got_m = have_m.get(code, set())
        miss_m = [m for m in expected if m not in got_m]
        miss_y = [y for y in years if y not in have_y.get(code, set())]
        pairs += [(code, tid, m) for m in miss_m]
        per_school.append({"udise_code": code, "taluka_id": tid, "months_expected": len(expected), "months_missing": len(miss_m),
                           "years_expected": len(years), "years_missing": len(miss_y), "missing_years": miss_y})
    return pd.DataFrame(per_school), pd.DataFrame(pairs, columns=["udise_code", "taluka_id", "month"])


def cleared(att: pd.DataFrame, flagged: set[str]) -> list[str]:
    """Lowest ceil(5% of all reporting schools) by mean attendance, among eligible unflagged schools."""
    stats = att.groupby("udise_code")["attendance_pct"].agg(["mean", "count"])
    k = math.ceil(CLEARED_SHARE * len(stats))
    eligible = stats[(stats["count"] >= CLEARED_MIN_MONTHS) & ~stats.index.isin(flagged)]
    return sorted(eligible.sort_values("mean", kind="stable").head(k).index)
