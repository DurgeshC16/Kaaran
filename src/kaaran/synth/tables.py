"""Clean truth tables: scores, attendance, teacher posts, election duty."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .entities import draw_infra
from .plant import Planted
from .rng import stream

N_YEARS = len(C.YEARS)


def _group_targets(df: pd.DataFrame) -> pd.Series:
    """Target mean per row's (taluka, year, vacancy group), from the spec tables."""
    counts = df.groupby(["taluka_key", "year_idx", "vacancy"]).size()
    targets = {}
    for t in C.TALUKAS:
        base0 = t.scores[0]
        for y in range(N_YEARS):
            vac_target = base0 + C.VACANCY_PATTERN[y]
            n_vac = int(counts.get((t.key, y, True), 0))
            n_rest = int(counts.get((t.key, y, False), 0))
            if t.key == C.FOCUS:
                rest_target = C.FOCUS_BASE + C.FOCUS_OTHERS_PATTERN[y]
            else:
                rest_target = (t.scores[y] * (n_vac + n_rest) - n_vac * vac_target) / n_rest
            targets[(t.key, y, True)] = vac_target
            targets[(t.key, y, False)] = rest_target
    keys = list(zip(df["taluka_key"], df["year_idx"], df["vacancy"]))
    return pd.Series([targets[k] for k in keys], index=df.index)


def build_scores(schools: pd.DataFrame, effects: pd.Series, planted: Planted, seed: int) -> pd.DataFrame:
    rng = stream(seed, "scores")
    codes = schools["udise_code"].to_numpy()
    n = len(codes)
    df = pd.DataFrame(
        {
            "udise_code": np.repeat(codes, N_YEARS),
            "taluka_key": np.repeat(schools["taluka_key"].to_numpy(), N_YEARS),
            "academic_year": np.tile(C.YEARS, n),
            "year_idx": np.tile(np.arange(N_YEARS), n),
        }
    )
    std3 = np.repeat(schools["enrol_std3"].to_numpy(), N_YEARS)
    cohort = np.maximum(3, np.round(std3 * rng.uniform(0.85, 1.1, len(df))))
    appeared = np.maximum(3, np.round(cohort * rng.uniform(0.85, 1.0, len(df)))).astype(int)
    noise = rng.normal(0, 1, len(df)) * C.STUDENT_SD / np.sqrt(appeared)
    vacancy = set(planted.vacancy)
    df["vacancy"] = df["udise_code"].isin(vacancy)
    pattern = np.array(C.VACANCY_PATTERN)[df["year_idx"].to_numpy()]
    df["students_appeared"] = appeared
    df["score"] = effects.reindex(df["udise_code"]).to_numpy() + noise + np.where(df["vacancy"], pattern, 0.0)

    missing = {(c, y) for c, ys in planted.all_missing_scores().items() for y in ys}
    keep = [(c, y) not in missing for c, y in zip(df["udise_code"], df["academic_year"])]
    df = df.loc[keep].reset_index(drop=True)

    # Shift each (taluka, year, group) so its mean hits the target exactly; re-shift after clipping.
    df["target"] = _group_targets(df)
    keys = ["taluka_key", "year_idx", "vacancy"]
    for _ in range(200):
        gap = df["target"] - df.groupby(keys)["score"].transform("mean")
        if gap.abs().max() < 1e-9:
            break
        df["score"] = (df["score"] + gap).clip(0, 100)
    else:
        raise RuntimeError("score calibration did not converge")

    df["mean_score"] = df["score"].round(1)
    df["std"] = C.STD
    df["subject"] = C.SUBJECT
    return df[["udise_code", "academic_year", "std", "subject", "mean_score", "students_appeared"]]


def flat_months(planted: Planted) -> dict[str, list[str]]:
    """udise -> months reported as exactly 100.0% (T5)."""
    year_months = C.months_of("2024-25")
    out = {c: list(C.FLAT_FOCUS_MONTHS) for c in planted.flat_focus}
    for c, start in planted.flat_noise.items():
        i = year_months.index(start)
        out[c] = year_months[i : i + C.FLAT_RUN]
    return dict(sorted(out.items()))


def build_attendance(schools: pd.DataFrame, planted: Planted, seed: int) -> pd.DataFrame:
    rng = stream(seed, "attendance")
    codes = schools["udise_code"].to_numpy()
    n = len(codes)
    labels = [C.month_label(y, m) for y in C.YEARS for m in C.SCHOOL_MONTHS]
    years = [y for y in C.YEARS for _ in C.SCHOOL_MONTHS]
    seasonal = np.array([C.SEASONAL_ATTENDANCE[m] for _ in C.YEARS for m in C.SCHOOL_MONTHS])

    honest = np.isin(codes, planted.honest_low)
    base = np.where(honest, rng.uniform(*C.HONEST_BASE, n), rng.uniform(*C.NORMAL_BASE, n))
    sd = np.where(honest, 1.5, 1.0)
    pct = base[:, None] + seasonal[None, :] + rng.normal(0, 1, (n, len(labels))) * sd[:, None]
    tenths = np.round(np.clip(pct, 55.0, C.ATTENDANCE_CAP) * 10).astype(int)

    flat = np.zeros_like(tenths, dtype=bool)
    row_of = {c: i for i, c in enumerate(codes)}
    col_of = {m: j for j, m in enumerate(labels)}
    for c, months in flat_months(planted).items():
        for m in months:
            flat[row_of[c], col_of[m]] = True
    tenths[flat] = 1000

    # No accidental flat runs: never three equal consecutive months outside planted T5 runs.
    for j in range(2, len(labels)):
        same = (tenths[:, j] == tenths[:, j - 1]) & (tenths[:, j - 1] == tenths[:, j - 2]) & ~flat[:, j]
        tenths[same, j] = np.where(tenths[same, j] >= C.ATTENDANCE_CAP * 10, tenths[same, j] - 1, tenths[same, j] + 1)

    enrol_year = np.round(
        schools["enrol_total"].to_numpy()[:, None] * rng.uniform(0.95, 1.05, (n, N_YEARS))
    ).astype(int)
    enrolled = np.repeat(enrol_year, len(C.SCHOOL_MONTHS), axis=1)

    df = pd.DataFrame(
        {
            "udise_code": np.repeat(codes, len(labels)),
            "academic_year": np.tile(years, n),
            "month": np.tile(labels, n),
            "enrolled": enrolled.ravel(),
            "attendance_pct": tenths.ravel() / 10,
        }
    )
    df["present_avg"] = (df["enrolled"] * df["attendance_pct"] / 100).round(1)
    missing = {(c, m) for c, ms in planted.all_missing_attendance().items() for m in ms}
    keep = [(c, m) not in missing for c, m in zip(df["udise_code"], df["month"])]
    df = df.loc[keep].reset_index(drop=True)
    return df[["udise_code", "academic_year", "month", "enrolled", "present_avg", "attendance_pct"]]


def build_teacher_posts(schools: pd.DataFrame, planted: Planted, seed: int) -> pd.DataFrame:
    rng = stream(seed, "teacher_posts")
    vacancy = set(planted.vacancy)
    start = C.year_index(C.VACANCY_START_YEAR)
    rows = []
    for code, total in zip(schools["udise_code"], schools["enrol_total"]):
        other_sanctioned = 1 + int(total > 60) + int(total > 110)
        for y, year in enumerate(C.YEARS):
            maths_working = 0 if (code in vacancy and y >= start) else 1
            lang_working = 1 - int(rng.random() < C.LANGUAGE_VACANCY_RATE)
            other_working = other_sanctioned - int(rng.random() < C.OTHER_VACANCY_RATE)
            rows += [
                (code, year, "maths", 1, maths_working),
                (code, year, "language", 1, lang_working),
                (code, year, "other", other_sanctioned, other_working),
            ]
    return pd.DataFrame(rows, columns=["udise_code", "academic_year", "subject", "sanctioned", "working"])


def build_election_duty(talukas: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = stream(seed, "election_duty")
    rows = []
    for t, name in zip(C.TALUKAS, talukas["taluka"]):
        for year in C.YEARS:
            for month in C.months_of(year):
                if month in C.ELECTION_MONTHS:
                    lo, hi = (C.ELECTION_MONTHS if t.election else C.ELECTION_LIGHT)[month]
                elif month in C.ELECTION_MINOR:
                    lo, hi = C.ELECTION_MINOR[month]
                else:
                    continue
                rows.append((t.key, name, year, month, round(float(rng.uniform(lo, hi)), 1)))
    return pd.DataFrame(rows, columns=["taluka_key", "taluka", "academic_year", "month", "deployed_pct"])


def focus_infra_r(schools: pd.DataFrame, scores: pd.DataFrame) -> float:
    wide = scores.pivot(index="udise_code", columns="academic_year", values="mean_score")
    change = (wide[C.YEARS[-1]] - wide[C.YEARS[0]]).dropna()
    focus = schools.loc[schools["taluka_key"] == C.FOCUS].set_index("udise_code")
    common = focus.index.intersection(change.index)
    return float(np.corrcoef(focus.loc[common, "infra_index"], change.loc[common])[0, 1])


def enforce_infra_independence(schools: pd.DataFrame, scores: pd.DataFrame, seed: int) -> pd.DataFrame:
    """T7: redraw the focus taluka's infrastructure until it is uncorrelated with its score change."""
    rng = stream(seed, "infra_redraw")
    schools = schools.copy()
    mask = (schools["taluka_key"] == C.FOCUS).to_numpy()
    cols = ["toilets", "library", "drinking_water", "classrooms", "infra_index"]
    for _ in range(1000):
        if abs(focus_infra_r(schools, scores)) < C.INFRA_MAX_ABS_R:
            return schools
        redraw = draw_infra(
            schools.loc[mask, "enrol_total"].to_numpy(), schools.loc[mask, "infra_quality"].to_numpy(), rng
        )
        for col in cols:
            schools.loc[mask, col] = redraw[col].to_numpy()
    raise RuntimeError("could not decorrelate focus infrastructure from score change")
