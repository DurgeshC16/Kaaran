"""Selection of the schools that carry planted truths (T3, T5, T6, T8) and of background gaps."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config as C
from .rng import stream


@dataclass
class Planted:
    vacancy_focus: list[str]
    vacancy_other: list[str]
    flat_focus: list[str]
    flat_noise: dict[str, str]  # udise -> first month of the 4-month 100.0% run
    honest_low: list[str]
    sparse_attendance: dict[str, list[str]]  # udise -> missing months (T6)
    sparse_scores: dict[str, list[str]]  # udise -> missing academic years (T6)
    missing_attendance: dict[str, list[str]] = field(default_factory=dict)  # background gaps
    missing_scores: dict[str, list[str]] = field(default_factory=dict)  # background gaps

    @property
    def vacancy(self) -> list[str]:
        return self.vacancy_focus + self.vacancy_other

    def all_missing_attendance(self) -> dict[str, list[str]]:
        return {**self.missing_attendance, **self.sparse_attendance}

    def all_missing_scores(self) -> dict[str, list[str]]:
        return {**self.missing_scores, **self.sparse_scores}


def draw_school_effects(schools: pd.DataFrame, seed: int) -> pd.Series:
    rng = stream(seed, "school_effects")
    eff = rng.normal(0, C.SCHOOL_EFFECT_SD, len(schools)).clip(-C.SCHOOL_EFFECT_CLIP, C.SCHOOL_EFFECT_CLIP)
    return pd.Series(eff, index=schools["udise_code"].to_numpy(), name="school_effect")


def _pick(rng: np.random.Generator, pool: list[str], k: int) -> list[str]:
    if len(pool) < k:
        raise RuntimeError(f"need {k} schools, pool has {len(pool)}")
    return sorted(rng.choice(np.array(pool, dtype=object), k, replace=False).tolist())


def select(schools: pd.DataFrame, effects: pd.Series, seed: int) -> Planted:
    rng = stream(seed, "planted")
    codes = schools["udise_code"].to_numpy()
    taluka = schools.set_index("udise_code")["taluka_key"]
    std3 = schools.set_index("udise_code")["enrol_std3"]
    eff = effects.reindex(codes)

    def in_taluka(key: str) -> list[str]:
        return [c for c in codes if taluka[c] == key]

    focus = in_taluka(C.FOCUS)
    ordinary = set(eff.index[eff.abs() <= C.ORDINARY_EFFECT])

    vacancy_focus = _pick(rng, [c for c in focus if c in ordinary], C.FOCUS_VACANCY)
    used = set(vacancy_focus)
    flat_focus = _pick(rng, [c for c in focus if c not in used], C.N_FLAT_FOCUS)
    used |= set(flat_focus)
    honest_pool = [c for c in focus if c not in used and abs(eff[c]) <= 4 and std3[c] >= 12]
    honest_low = _pick(rng, honest_pool, C.N_HONEST_LOW)
    used |= set(honest_low)

    vacancy_other: list[str] = []
    for t in C.TALUKAS:
        if t.key != C.FOCUS and t.n_vacancy:
            vacancy_other += _pick(rng, [c for c in in_taluka(t.key) if c in ordinary], t.n_vacancy)
    used |= set(vacancy_other)

    # Scattered evenly (3-4 per taluka) so the focus taluka's 23 stand out as a concentration.
    noise_talukas = [t.key for t in C.TALUKAS if t.key not in (C.FOCUS, C.SPARSE)]
    per_taluka = np.full(len(noise_talukas), C.N_FLAT_NOISE // len(noise_talukas))
    per_taluka[rng.permutation(len(noise_talukas))[: C.N_FLAT_NOISE % len(noise_talukas)]] += 1
    flat_noise_codes = []
    for key, k in zip(noise_talukas, per_taluka):
        flat_noise_codes += _pick(rng, [c for c in in_taluka(key) if c not in used], int(k))
    flat_noise = {c: str(rng.choice(C.FLAT_NOISE_STARTS)) for c in sorted(flat_noise_codes)}
    used |= set(flat_noise_codes)

    sparse = _pick(rng, in_taluka(C.SPARSE), C.N_SPARSE_ATTENDANCE + C.N_SPARSE_SCORES - C.N_SPARSE_OVERLAP)
    rng.shuffle(sparse)
    att_set = sorted(sparse[: C.N_SPARSE_ATTENDANCE])
    score_set = sorted(att_set[: C.N_SPARSE_OVERLAP] + sparse[C.N_SPARSE_ATTENDANCE :])
    sparse_attendance = {
        c: sorted(rng.choice(C.SPARSE_WINDOW, int(rng.integers(3, 6)), replace=False).tolist()) for c in att_set
    }
    sparse_scores = {c: sorted(rng.choice(C.YEARS, 2, replace=False).tolist()) for c in score_set}

    planted = Planted(
        vacancy_focus=vacancy_focus,
        vacancy_other=sorted(vacancy_other),
        flat_focus=flat_focus,
        flat_noise=dict(sorted(flat_noise.items())),
        honest_low=honest_low,
        sparse_attendance=sparse_attendance,
        sparse_scores=sparse_scores,
    )
    _background_gaps(planted, schools, rng, used | set(sparse))
    return planted


def _background_gaps(planted: Planted, schools: pd.DataFrame, rng: np.random.Generator, excluded: set[str]) -> None:
    """Ordinary reporting gaps that must NOT trigger the T6 rule (<= 2 months, <= 1 score year)."""
    all_months = [m for y in C.YEARS for m in C.months_of(y)]
    for t in C.TALUKAS:
        pool = [c for c in schools.loc[schools["taluka_key"] == t.key, "udise_code"] if c not in excluded]
        if t.key == C.SPARSE:
            for c in _pick(rng, pool, round(C.SPARSE_LIGHT_MISSING * len(pool))):
                k = int(rng.integers(1, 3))
                planted.missing_attendance[c] = sorted(rng.choice(all_months, k, replace=False).tolist())
            continue
        for c in _pick(rng, pool, round(C.BACKGROUND_ATTENDANCE_MISSING * t.n_schools)):
            planted.missing_attendance[c] = [str(rng.choice(all_months))]
        if t.key in (C.FOCUS, C.TWIN, C.DECOY):
            continue
        for c in _pick(rng, pool, round(C.BACKGROUND_SCORE_MISSING * t.n_schools)):
            planted.missing_scores[c] = [str(rng.choice(C.YEARS))]
    planted.missing_attendance = dict(sorted(planted.missing_attendance.items()))
    planted.missing_scores = dict(sorted(planted.missing_scores.items()))
