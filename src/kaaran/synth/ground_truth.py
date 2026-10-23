"""Answer key: conventions, one entry per planted truth, and (later) the messiness log."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import GENERATOR_VERSION, SYNTHETIC_MARKER
from . import config as C
from .plant import Planted
from .tables import flat_months, focus_infra_r

CONVENTIONS = {
    "taluka_score": "unweighted mean of school mean_score over schools that reported that year",
    "rank": "1 = highest taluka_score among the 11 talukas",
    "change": "later year minus earlier year",
    "decline_share": "(n_vacancy / n_schools) * vacancy-group mean change / taluka mean change, 2021-22 to 2025-26",
    "academic_year": "'2023-24' runs Jun 2023 to Mar 2024; school months Jun-Mar",
    "bare_year": "a bare year in raw files is the END year: 2024 means 2023-24",
    "month": "calendar 'YYYY-MM'",
    "udise_code": "11-digit string: '00' (non-existent state) + district '99' + block 2 + village 3 + school 2",
    "election_duty_rule": f">= {C.ELECTION_THRESHOLD:g}% of teachers deployed for >= {C.ELECTION_MIN_MONTHS} months in a year",
    "insufficient_rule": "school misses >= 3 attendance months or >= 2 academic years of scores",
    "group_thresholds": "thresholds on schools moving or talukas staying within a band are on group means",
}


def _ranks(year_idx: int) -> dict[str, int]:
    vals = {t.key: t.scores[year_idx] for t in C.TALUKAS}
    order = sorted(vals, key=lambda k: -vals[k])
    return {k: i + 1 for i, k in enumerate(order)}


def _r(x: float) -> float:
    return round(float(x), 3)


def build(seed: int, names: str, clean: dict[str, pd.DataFrame], planted: Planted) -> dict:
    name = {k: v[0] for k, v in C.NAME_SETS[names].items()}
    spec = C.TALUKA_BY_KEY
    first, last = C.YEARS[0], C.YEARS[-1]
    before, during = "2023-24", C.ELECTION_YEAR
    r0, r4 = _ranks(0), _ranks(len(C.YEARS) - 1)
    focus, twin, decoy = spec[C.FOCUS], spec[C.TWIN], spec[C.DECOY]
    election = [t.key for t in C.TALUKAS if t.election]
    comparison = [k for k in election if k not in (C.FOCUS, C.DIPPER)]
    i_before, i_during = C.year_index(before), C.year_index(during)

    def change(key: str, a: int = 0, b: int = len(C.YEARS) - 1) -> float:
        return _r(spec[key].scores[b] - spec[key].scores[a])

    n_vac, n_all = C.FOCUS_VACANCY, C.FOCUS_SCHOOLS
    vac_change = C.VACANCY_PATTERN[-1] - C.VACANCY_PATTERN[0]
    share = n_vac / n_all * vac_change / (focus.scores[-1] - focus.scores[0])

    schools = clean["schools"]
    infra = schools.groupby("taluka_key")["infra_index"].mean().sort_values()
    enrol = schools.groupby("taluka_key")["enrol_total"].mean()
    flagged = sorted(set(planted.sparse_attendance) | set(planted.sparse_scores))
    flats = flat_months(planted)

    truths = [
        {
            "id": "T1",
            "name": "REAL_DECLINE",
            "description": f"{name[C.FOCUS]} falls from rank {r0[C.FOCUS]} to {r4[C.FOCUS]} of 11; the decline holds in a school-level paired comparison.",
            "entities": {"talukas": [name[C.FOCUS]]},
            "expected": {
                "taluka_score": {first: _r(focus.scores[0]), last: _r(focus.scores[-1])},
                "change": change(C.FOCUS),
                "change_tolerance": 0.1,
                "min_drop": 3.0,
                "rank": {first: r0[C.FOCUS], last: r4[C.FOCUS]},
                "below_baseline_from": "2023-24",
                "paired_t_max": -3.0,
            },
            "verdict": "STRONG",
        },
        {
            "id": "T2",
            "name": "ELECTION_EXCUSE_WEAK",
            "description": f"{len(election)} talukas had heavy election duty in {during}; 5 of the 6 besides {name[C.FOCUS]} stayed within +/-1, one dipped for an unrelated reason.",
            "entities": {
                "talukas": [name[k] for k in election],
                "comparison_talukas": [name[k] for k in comparison],
                "unrelated_dip_taluka": name[C.DIPPER],
            },
            "expected": {
                "election_year": during,
                "election_months": sorted(C.ELECTION_MONTHS),
                "threshold_pct": C.ELECTION_THRESHOLD,
                "min_months": C.ELECTION_MIN_MONTHS,
                "change_window": [before, during],
                "focus_change": change(C.FOCUS, i_before, i_during),
                "comparison_max_abs_change": 1.0,
                "comparison_changes": {name[k]: change(k, i_before, i_during) for k in comparison},
                "unrelated_dip_change": change(C.DIPPER, i_before, i_during),
                "unrelated_dip_tolerance": 0.3,
                "unrelated_dip_cause": "none planted (no signal in any table)",
            },
            "verdict": "WEAK_CAUSE",
        },
        {
            "id": "T3",
            "name": "VACANCY_CAUSE",
            "description": f"{n_vac} {name[C.FOCUS]} schools have had no maths teacher since {C.VACANCY_START_YEAR}; they explain most of the decline.",
            "entities": {
                "talukas": [name[C.FOCUS]],
                "schools": planted.vacancy_focus,
                "same_pattern_other_talukas": planted.vacancy_other,
            },
            "expected": {
                "vacancy_start_year": C.VACANCY_START_YEAR,
                "vacancy_group_change_by_year": dict(zip(C.YEARS, C.VACANCY_PATTERN)),
                "vacancy_group_drop_range": [20.0, 30.0],
                "other_schools_change": C.FOCUS_OTHERS_PATTERN[-1],
                "other_schools_max_abs_change": 2.0,
                "decline_share": _r(share),
                "min_decline_share": 0.60,
            },
            "verdict": "STRONG",
        },
        {
            "id": "T4",
            "name": "TWIN_BLOCK",
            "description": f"{name[C.TWIN]} matches {name[C.FOCUS]} on size, enrolment, poverty and election duty, has no maths vacancies, and improved. {name[C.DECOY]} is a closer match that did not improve (decoy).",
            "entities": {"talukas": [name[C.TWIN]], "focus": name[C.FOCUS], "decoy": name[C.DECOY]},
            "expected": {
                "tolerances": {"n_schools_pct": 10.0, "poverty_abs": 0.05, "mean_enrolment_pct": 5.0},
                "n_schools": {name[k]: spec[k].n_schools for k in (C.FOCUS, C.TWIN, C.DECOY)},
                "poverty_index": {name[k]: spec[k].poverty for k in (C.FOCUS, C.TWIN, C.DECOY)},
                "mean_enrolment": {name[k]: _r(enrol[k]) for k in (C.FOCUS, C.TWIN, C.DECOY)},
                "twin_change": change(C.TWIN),
                "twin_min_change": 6.0,
                "twin_rank": {first: r0[C.TWIN], last: r4[C.TWIN]},
                "decoy_change": change(C.DECOY),
                "decoy_max_change": 1.0,
            },
            "verdict": "LEARN_FROM",
        },
        {
            "id": "T5",
            "name": "FLAT_ATTENDANCE",
            "description": f"{len(planted.flat_focus)} {name[C.FOCUS]} schools report exactly 100.0% attendance for 4 consecutive months in {during}; {len(planted.flat_noise)} more are scattered elsewhere.",
            "entities": {
                "talukas": [name[C.FOCUS]],
                "schools": planted.flat_focus,
                "scattered_schools": sorted(planted.flat_noise),
            },
            "expected": {
                "value": 100.0,
                "run_months": C.FLAT_RUN,
                "focus_months": list(C.FLAT_FOCUS_MONTHS),
                "flat_months_by_school": flats,
                "n_focus": len(planted.flat_focus),
                "n_scattered": len(planted.flat_noise),
            },
            "verdict": "RED_FLAG",
        },
        {
            "id": "T6",
            "name": "INSUFFICIENT_DATA",
            "description": f"{name[C.SPARSE]}: {len(flagged)} of {spec[C.SPARSE].n_schools} schools miss >= 3 attendance months or >= 2 score years.",
            "entities": {"talukas": [name[C.SPARSE]], "schools": flagged},
            "expected": {
                "missing_attendance_months": planted.sparse_attendance,
                "missing_score_years": planted.sparse_scores,
                "flagged_share": _r(len(flagged) / spec[C.SPARSE].n_schools),
                "min_flagged_share": 0.40,
                "other_talukas_max_flagged_share": 0.10,
            },
            "verdict": "INSUFFICIENT",
        },
        {
            "id": "T7",
            "name": "INFRA_DECOY",
            "description": f"{name[C.INFRA_LOW]} has the worst infrastructure but stable scores; within {name[C.FOCUS]} infrastructure is unrelated to the decline.",
            "entities": {"talukas": [name[C.INFRA_LOW], name[C.FOCUS]]},
            "expected": {
                "infra_index_mean": {name[k]: _r(v) for k, v in infra.items()},
                "lowest_margin_min": 0.10,
                "infra_low_change": change(C.INFRA_LOW),
                "infra_low_max_abs_yearly_change": 1.0,
                "focus_infra_change_r": _r(focus_infra_r(schools, clean["scores"])),
                "focus_max_abs_r": 0.10,
            },
            "verdict": "NOT_A_CAUSE",
        },
        {
            "id": "T8",
            "name": "HONEST_LOW_ATTENDANCE",
            "description": f"{len(planted.honest_low)} {name[C.FOCUS]} schools have genuinely low but natural attendance and ordinary scores; trust checks must not flag them.",
            "entities": {"talukas": [name[C.FOCUS]], "schools": planted.honest_low},
            "expected": {"mean_attendance_range": [78.0, 84.0], "max_equal_consecutive_months": 2},
            "verdict": "NOT_FLAGGED",
        },
    ]

    return {
        "synthetic": True,
        "marker": SYNTHETIC_MARKER,
        "district": C.DISTRICT_NAME,
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "taluka_name_set": names,
        "talukas": {t.key: name[t.key] for t in C.TALUKAS},
        "taluka_score_targets": {name[t.key]: dict(zip(C.YEARS, map(_r, t.scores))) for t in C.TALUKAS},
        "conventions": CONVENTIONS,
        "truths": truths,
        "messiness": [],
    }


def to_jsonable(obj):
    """Convert numpy scalars so json.dumps works."""
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    return obj
