"""Build the clean v3 world: blocks -> clusters -> schools and their yearly / monthly / per-round tables.

Deterministic for a given seed (named random streams). No LLM. The raw (messy, real-format) files are
written from these tables by writers.py; the answer key comes from the roles assigned here (truth.py).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..synth import config as V2
from ..synth.entities import VILLAGE_HEADS, VILLAGE_TAILS, _village
from ..synth.rng import stream
from . import config as C

SUFFIXES = ("", " Budruk", " Khurd")


@dataclass
class World:
    seed: int
    names: str
    blocks: pd.DataFrame
    clusters: pd.DataFrame
    schools: pd.DataFrame
    enrolment: pd.DataFrame
    posts: pd.DataFrame
    attendance: pd.DataFrame
    assessment: pd.DataFrame
    visits: pd.DataFrame
    training: pd.DataFrame

    def tables(self) -> dict[str, pd.DataFrame]:
        return {k: getattr(self, k) for k in ("blocks", "clusters", "schools", "enrolment", "posts", "attendance",
                                              "assessment", "visits", "training")}


def months() -> list[str]:
    return [V2.month_label(y, m) for y in C.YEARS for m in C.SCHOOL_MONTHS]


def year_of(month: str) -> str:
    return V2.academic_year_of(month)


def _village_names(seed: int, n: int) -> list[str]:
    rng = stream(seed, "v3.villages")
    combos = [_village(h, t) + s for s in SUFFIXES for h in VILLAGE_HEADS for t in VILLAGE_TAILS]
    order = rng.permutation(len(combos))
    return [combos[i] for i in order[:n]]


def build_entities(seed: int, names: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    name_set = V2.NAME_SETS[names]
    blocks = pd.DataFrame([{"block_key": t.key, "block_code": t.block, "block": name_set[t.key][0],
                            "block_mr": name_set[t.key][2], "poverty": t.poverty, "n_schools": t.n_schools}
                           for t in V2.TALUKAS])
    villages = iter(_village_names(seed, int(blocks["n_schools"].sum())))
    rng = stream(seed, "v3.entities")
    cl_rows, sc_rows = [], []
    for b in blocks.itertuples(index=False):
        k = max(1, round(b.n_schools / 12))
        sizes = [b.n_schools // k + (1 if i < b.n_schools % k else 0) for i in range(k)]
        serial = 0
        for ci, size in enumerate(sizes, start=1):
            cid = f"{b.block_code}K{ci:02d}"
            kendra_village = None
            for si in range(size):
                serial += 1
                village = next(villages)
                udise = f"{C.STATE_PREFIX}{C.DISTRICT_CODE}{b.block_code}{serial:03d}01"
                if si == 0:
                    kendra_village = village
                    name = f"ZP Kendra Primary School {village}"
                else:
                    name = f"ZP Primary School {village}"
                high = 4 if rng.random() < 0.6 else 7
                sc_rows.append({"udise_code": udise, "school_name": name, "village": village, "block_key": b.block_key,
                                "cluster_id": cid, "cluster_idx": ci, "kendra_school": si == 0,
                                "rural_urban": 2 if (si == 0 and ci == 1) else 1, "management": 3,
                                "school_category": 1 if high == 4 else 2, "lowclass": 1, "highclass": high,
                                "role": "normal"})
            cl_rows.append({"cluster_id": cid, "block_key": b.block_key, "cluster_idx": ci,
                            "cluster_name": f"{kendra_village} Kendra", "n_schools": size})
    return blocks, pd.DataFrame(cl_rows), pd.DataFrame(sc_rows)


def assign_roles(schools: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Planted scenario roles (see config.py). Kendra schools never carry a planted role."""
    rng = stream(seed, "v3.roles")
    s = schools.copy()
    focus = s["block_key"] == C.FOCUS

    def pick(mask, n, role):
        idx = s.index[mask & (s["role"] == "normal") & ~s["kendra_school"]]
        chosen = rng.choice(idx, size=min(n, len(idx)), replace=False)
        s.loc[chosen, "role"] = role
        return chosen

    def cluster(i):
        return focus & (s["cluster_idx"] == i)

    s.loc[cluster(C.SUPPORT_GAP), "role"] = "support_gap"
    s.loc[(s["block_key"] == C.REPLICATION_BLOCK) & (s["cluster_idx"] == 2), "role"] = "support_gap"
    pick(cluster(C.STAFFING_GAP), C.STAFFING_GAP_SCHOOLS, "staffing_gap")
    pick(cluster(C.STAFFING_GAP), 1, "positive_deviant")
    pick(cluster(C.HONEST_LOW), C.HONEST_LOW_SCHOOLS, "honest_low")
    s.loc[cluster(C.IMPROVING), "role"] = "improving"
    pick(cluster(C.DATA_PROBLEM), C.FLAT_SCHOOLS, "flat")
    pick(cluster(C.SURPLUS), C.SURPLUS_SCHOOLS, "surplus")
    pick(cluster(C.MIGRATION), C.MIGRATION_SCHOOLS, "migration")
    pick(cluster(C.INSUFFICIENT), C.INSUFFICIENT_SCHOOLS, "insufficient")
    special = {C.SUPPORT_GAP, C.STAFFING_GAP, C.HONEST_LOW, C.IMPROVING, C.DATA_PROBLEM, C.SURPLUS, C.MIGRATION,
               C.INSUFFICIENT}
    for b in sorted(set(s["block_key"]) - {C.FOCUS}):
        mask = (s["block_key"] == b) & ~((s["block_key"] == C.REPLICATION_BLOCK) & (s["cluster_idx"] == 2))
        pick(mask, C.STAFFING_ELSEWHERE_PER_BLOCK, "staffing_elsewhere")
    others = s.index[(s["block_key"] != C.FOCUS) & (s["role"] == "normal") & ~s["kendra_school"]]
    s.loc[rng.choice(others, size=C.FLAT_ELSEWHERE, replace=False), "role"] = "flat_elsewhere"
    assert not (focus & s["cluster_idx"].isin(special) & (s["role"] == "staffing_elsewhere")).any()
    return s


def build_enrolment(schools: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = stream(seed, "v3.enrolment")
    rows = []
    for s in schools.itertuples(index=False):
        if s.role == "surplus":
            total0 = rng.integers(*C.SURPLUS_ENROLMENT)
            per_class = np.full(s.highclass, total0 / s.highclass)
        else:
            mean = 26 if s.kendra_school else 17
            per_class = rng.lognormal(math.log(mean), 0.35, size=s.highclass)
        for yi, year in enumerate(C.YEARS):
            drift = (1 - 0.04 * yi) if s.role == "surplus" else (1 + rng.normal(0, 0.03))
            for cls in range(1, s.highclass + 1):
                n = max(3, int(round(per_class[cls - 1] * drift * (1 + rng.normal(0, 0.08)))))
                girls = int(rng.binomial(n, 0.49))
                rows.append({"udise_code": s.udise_code, "academic_year": year, "cls": cls, "boys": n - girls,
                             "girls": girls})
    return pd.DataFrame(rows)


def _totals(enrolment: pd.DataFrame) -> pd.DataFrame:
    e = enrolment.assign(total=enrolment["boys"] + enrolment["girls"])
    return e.groupby(["udise_code", "academic_year"])["total"].sum().reset_index()


def build_posts(schools: pd.DataFrame, enrolment: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = stream(seed, "v3.posts")
    totals = _totals(enrolment).set_index(["udise_code", "academic_year"])["total"]
    rows = []
    all_months = months()
    for s in schools.itertuples(index=False):
        random_gap = None
        if s.role in ("normal", "honest_low", "improving") and rng.random() < C.RANDOM_VACANCY_RATE:
            start = int(rng.integers(0, len(all_months) - 4))
            random_gap = set(all_months[start:start + int(rng.integers(2, 5))])
        for m in all_months:
            y = year_of(m)
            enrol = int(totals[(s.udise_code, y)])
            sanctioned = max(C.MIN_POSTS, math.ceil(enrol / C.PUPILS_PER_POST))
            working = sanctioned
            if s.role in ("staffing_gap", "positive_deviant", "staffing_elsewhere"):
                sanctioned = max(sanctioned, 2)
                working = sanctioned - 1 if m >= C.STAFFING_GAP_START else sanctioned
                if m >= C.STAFFING_GAP_START:
                    working = 1 if sanctioned == 2 else working
            elif s.role == "surplus":
                sanctioned, working = C.MIN_POSTS, C.SURPLUS_TEACHERS
            elif random_gap and m in random_gap:
                working = sanctioned - 1
            lo, hi = C.DUTY_MONTHS.get(m, C.DUTY_BACKGROUND)
            rows.append({"udise_code": s.udise_code, "month": m, "academic_year": y, "sanctioned": sanctioned,
                         "working": working, "duty_days": round(float(rng.uniform(lo, hi)), 1)})
    return pd.DataFrame(rows)


def build_attendance(schools: pd.DataFrame, enrolment: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = stream(seed, "v3.attendance")
    totals = _totals(enrolment).set_index(["udise_code", "academic_year"])["total"]
    rows = []
    all_months = months()
    flat_elsewhere_runs = {}
    for s in schools.itertuples(index=False):
        if s.role == "flat_elsewhere":
            start = int(rng.integers(0, len(all_months) - 4))
            flat_elsewhere_runs[s.udise_code] = set(all_months[start:start + 4])
    for s in schools.itertuples(index=False):
        base = rng.uniform(*(C.HONEST_BASE if s.role == "honest_low" else C.NORMAL_BASE))
        sd = 2.2 if s.role == "honest_low" else 1.2
        for m in all_months:
            y = year_of(m)
            if s.role == "insufficient" and m in C.INSUFFICIENT_MISSING_MONTHS:
                continue
            if rng.random() < 0.01:  # background: an occasional missing month
                continue
            month_num = int(m[5:])
            pct = base + C.SEASONAL_ATTENDANCE[month_num] + rng.normal(0, sd)
            if s.role == "migration":
                pct += C.MIGRATION_DROP.get(month_num, 0.0) + rng.normal(0, 1.5)
            pct = min(pct, C.ATTENDANCE_CAP)
            if (s.role == "flat" and m in C.FLAT_MONTHS) or m in flat_elsewhere_runs.get(s.udise_code, ()):
                pct = 100.0
            enrolled = int(totals[(s.udise_code, y)])
            rows.append({"udise_code": s.udise_code, "month": m, "academic_year": y, "enrolled": enrolled,
                         "attendance_pct": round(float(pct), 1)})
    return pd.DataFrame(rows)


def build_assessment(schools: pd.DataFrame, blocks: pd.DataFrame, enrolment: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = stream(seed, "v3.assessment")
    g3 = enrolment[enrolment["cls"] == C.GRADE].assign(n=lambda d: d["boys"] + d["girls"])
    g3 = g3.set_index(["udise_code", "academic_year"])["n"]
    cluster_eff = {cid: rng.normal(0, C.CLUSTER_SD) for cid in sorted(schools["cluster_id"].unique())}
    rows = []
    for s in schools.itertuples(index=False):
        eff = float(np.clip(rng.normal(0, C.SCHOOL_SD), -C.SCHOOL_CLIP, C.SCHOOL_CLIP))
        trend = rng.normal(0, C.SCHOOL_TREND_SD)
        shift = cluster_eff[s.cluster_id] + eff
        if s.role == "flat":
            shift += C.FLAT_LEARNING_SHIFT
        if s.role == "migration" or (s.block_key == C.FOCUS and s.cluster_idx == C.MIGRATION):
            shift += C.MIGRATION_CLUSTER_SHIFT
        if s.role == "surplus":
            shift += 2.0
        for yi, year in enumerate(C.YEARS):
            level = C.BLOCK_LEVEL[s.block_key][yi]
            for rkey, *_ in C.ROUNDS:
                planted = _planted(s, year, rkey)
                n3 = int(g3.get((s.udise_code, year), 10))
                assessed = max(3, int(round(n3 * rng.uniform(*C.ASSESSED_SHARE))))  # same pupils take every competency
                for code, (subject, *_rest, offset) in C.COMPETENCIES.items():
                    extra = planted["all"] * (C.SUPPORT_GAP_LANGUAGE_FACTOR if subject == "language" and planted["support"] else 1)
                    extra += planted["by_comp"].get(code, 0.0)
                    true = (level + C.ROUND_OFFSET[rkey] + offset + shift + trend * yi + extra
                            + (C.LANGUAGE_OVER_MATHS if subject == "language" else 0.0))
                    p = min(max(true, 3.0), 98.0) / 100
                    if s.role == "insufficient" and year == C.YEARS[-1] and rkey == "EL":
                        continue
                    pct = 100.0 * rng.binomial(assessed, p) / assessed
                    rows.append({"udise_code": s.udise_code, "academic_year": year, "round": rkey, "grade": C.GRADE,
                                 "competency": code, "subject": subject, "assessed": assessed, "pct": round(pct, 1)})
    return pd.DataFrame(rows)


def _planted(s, year: str, rkey: str) -> dict:
    out = {"all": 0.0, "by_comp": {}, "support": False}
    if year == C.YEARS[-1] and rkey == "ML":
        out["all"] += C.DUTY_ML_EFFECT
    if s.role == "support_gap" and year == C.YEARS[-1] and rkey in C.SUPPORT_GAP_EFFECT:
        out["all"] += C.SUPPORT_GAP_EFFECT[rkey]
        factor = 0.5 if rkey == "ML" else 1.0
        out["by_comp"] = {k: v * factor for k, v in C.SUPPORT_GAP_COMPETENCY.items()}
        out["support"] = True
    ramp = {"BL": 0.4, "ML": 0.8, "EL": 1.0}[rkey]
    if s.role in ("staffing_gap", "staffing_elsewhere") and year in C.STAFFING_GAP_EFFECT:
        prev = C.STAFFING_GAP_EFFECT.get(C.YEARS[C.YEARS.index(year) - 1], 0.0)
        out["all"] += prev + (C.STAFFING_GAP_EFFECT[year] - prev) * ramp
    if s.role == "positive_deviant" and year in C.POSITIVE_DEVIANT_GAIN:
        prev = C.POSITIVE_DEVIANT_GAIN.get(C.YEARS[C.YEARS.index(year) - 1], 0.0)
        out["all"] += prev + (C.POSITIVE_DEVIANT_GAIN[year] - prev) * ramp
    if s.role == "improving" and year in C.IMPROVING_GAIN:
        out["all"] += C.IMPROVING_GAIN[year]
    if s.role == "migration" and rkey == "EL":
        out["all"] += C.MIGRATION_EL_EFFECT
    return out


def build_visits(schools: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = stream(seed, "v3.visits")
    rows = []
    for s in schools.itertuples(index=False):
        for m in months():
            gap = s.role == "support_gap" and m >= C.SUPPORT_GAP_START
            for role, rate in (("Kendra Pramukh", C.KP_VISIT_RATE_GAP if gap else C.KP_VISIT_RATE),
                               ("BRC", C.BRC_VISIT_RATE), ("BEO", C.BEO_VISIT_RATE)):
                for _ in range(int(rng.poisson(rate))):
                    academic = rng.random() < (0.7 if role == "Kendra Pramukh" else 0.5)
                    rows.append({"udise_code": s.udise_code, "date": f"{m}-{int(rng.integers(1, 29)):02d}",
                                 "visitor_role": role, "purpose": "academic" if academic else "administrative",
                                 "classroom_observed": bool(academic and rng.random() < 0.8)})
    return pd.DataFrame(rows).sort_values(["date", "udise_code", "visitor_role"]).reset_index(drop=True)


def build_training(schools: pd.DataFrame, posts: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = stream(seed, "v3.training")
    rows = []
    working = posts.set_index(["udise_code", "month"])["working"]
    for year in C.YEARS:
        month = V2.month_label(year, C.TRAINING_MONTH)
        for s in schools.itertuples(index=False):
            skip = s.role == "support_gap" and (s.block_key == C.FOCUS and year != C.YEARS[0]
                                                or s.block_key != C.FOCUS and year == C.YEARS[-1])
            if skip or rng.random() < 0.03:
                continue
            day = int(rng.integers(5, 25))
            rows.append({"udise_code": s.udise_code, "date": f"{month}-{day:02d}", "topic": "FLN maths pedagogy",
                         "teachers_trained": int(working[(s.udise_code, month)]), "days": C.TRAINING_DAYS})
    return pd.DataFrame(rows)


def build_world(seed: int = 42, names: str = V2.TALUKA_NAMES) -> World:
    blocks, clusters, schools = build_entities(seed, names)
    schools = assign_roles(schools, seed)
    enrolment = build_enrolment(schools, seed)
    posts = build_posts(schools, enrolment, seed)
    return World(seed=seed, names=names, blocks=blocks, clusters=clusters, schools=schools, enrolment=enrolment,
                 posts=posts, attendance=build_attendance(schools, enrolment, seed),
                 assessment=build_assessment(schools, blocks, enrolment, seed), visits=build_visits(schools, seed),
                 training=build_training(schools, posts, seed))
