"""Real-data input brief: teacher rationalisation potential per block from UDISE+ microdata (no outcomes needed).

For local-body PRIMARY-only schools (category 1, classes 1-5) the RTE schedule sets the teachers a school needs:
at least 2, and one per 30 pupils (simplified: required = max(2, ceil(pupils / 30))). Per block this gives
- schools short of teachers and the posts they need,
- schools with teachers beyond the norm and how many could move,
- how much of the shortage could be covered by redeployment inside the block (rubric action A1), the rest needing new
  or guest teachers (A2).
Aggregates only; values are self-reported to UDISE+; schools with more classes are not judged here.
"""

from __future__ import annotations

import math

import pandas as pd

from .udise import LOCAL_BODY, enrolment

PRIMARY_ONLY = 1
MIN_TEACHERS = 2
RTE_PTR = 30


def required_teachers(pupils: float) -> int:
    return max(MIN_TEACHERS, math.ceil(pupils / RTE_PTR)) if pupils > 0 else MIN_TEACHERS


def rationalisation(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    p1, tc = t["prof1"], t["tch"]
    df = (p1[["pseudocode", "block", "managment", "school_category"]]
          .merge(tc[["pseudocode", "total_tch"]], on="pseudocode")
          .merge(enrolment(t["enr1"]), on="pseudocode", how="left"))
    df = df[(df["managment"] == LOCAL_BODY) & (df["school_category"] == PRIMARY_ONLY)].copy()
    df["enrol_1_8"] = df["enrol_1_8"].fillna(0)
    df["required"] = df["enrol_1_8"].map(required_teachers)
    df["gap"] = df["required"] - df["total_tch"]
    rows = []
    for block, g in df.groupby("block"):
        short = g[g["gap"] > 0]
        extra = g[g["gap"] < 0]
        need, spare = int(short["gap"].sum()), int(-extra["gap"].sum())
        rows.append({"block": block, "primary_schools": int(len(g)), "schools_short": int(len(short)), "posts_needed": need,
                     "schools_with_extra": int(len(extra)), "extra_teachers": spare,
                     "covered_by_redeployment": min(need, spare), "still_needed": max(0, need - spare),
                     "single_teacher_schools": int((g["total_tch"] == 1).sum())})
    out = pd.DataFrame(rows).set_index("block").sort_values("posts_needed", ascending=False)
    return out


def rationalisation_markdown(r: pd.DataFrame, district: str, year: str) -> str:
    lines = [f"## Teacher rationalisation potential (REAL PUBLIC DATA: {district}, UDISE+ {year})", "",
             "Local-body primary-only schools. The rule is the RTE norm: at least 2 teachers and one per 30 pupils. "
             "This is self-reported data, and decisions belong to the officer.", "",
             "| Block | Primary schools | Schools short | Posts needed | Schools with extra | Extra teachers | Could be covered by redeployment | Still needed |",
             "|---|---|---|---|---|---|---|---|"]
    for b, x in r.iterrows():
        lines.append(f"| {b} | {x.primary_schools} | {x.schools_short} | {x.posts_needed} | {x.schools_with_extra} | {x.extra_teachers} | "
                     f"{x.covered_by_redeployment} | {x.still_needed} |")
    tot = r.sum(numeric_only=True)
    lines += ["", f"District: {int(tot.posts_needed)} posts needed in {int(tot.schools_short)} schools. "
              f"{int(tot.covered_by_redeployment)} of these could be covered by moving teachers inside the same block (rubric A1). "
              f"{int(tot.still_needed)} would need new or guest teachers (A2)."]
    return "\n".join(lines) + "\n"
