"""Twin-block finder (positive deviance, no LLM): the most similar taluka that improved.

Similarity = RMS distance of district-standardised covariates (school count, mean enrolment, poverty index)
among talukas with the same heavy election-duty years. A similar taluka that did not improve is reported
as the decoy, so the finder visibly chooses on outcome, not on similarity alone.
"""

from __future__ import annotations

import math

import pandas as pd

from .. import confidence as K
from ..causes.data import taluka_means
from ..causes.hypotheses import heavy_duty_years
from ..causes.trend import change_number, rank_number
from ..evidence import Builder

COVARIATES = ("n_schools", "mean_enrolment", "poverty_index")


def covariates(tables: dict) -> pd.DataFrame:
    t = tables["talukas"].set_index("taluka_id")
    enrol = tables["schools"].groupby("taluka_id")["enrol_total"].mean()
    return pd.DataFrame({"n_schools": t["n_schools"].astype(float), "mean_enrolment": enrol.astype(float),
                         "poverty_index": pd.to_numeric(t["poverty_index"], errors="coerce").astype(float)})


def find_twin(b: Builder, tables: dict, sc: pd.DataFrame, trust, focus: str) -> dict:
    cov = covariates(tables)
    used = [c for c in COVARIATES if cov[c].notna().all()]
    z = (cov[used] - cov[used].mean()) / cov[used].std(ddof=1)
    dist = ((z - z.loc[focus]) ** 2).mean(axis=1).map(math.sqrt)
    exposed = heavy_duty_years(tables["election_duty"]).groupby("taluka_id")["academic_year"].agg(frozenset)
    same_duty = {t for t in cov.index if exposed.get(t, frozenset()) == exposed.get(focus, frozenset())}
    excluded = set(trust.report.get("insufficient_talukas", [])) | {focus}
    tm = taluka_means(sc)
    years = sorted(tm.columns)
    y0, y1 = years[0], years[-1]
    change = tm[y1] - tm[y0]
    similar = [t for t in dist.sort_values().index if t not in excluded and t in same_duty and dist[t] <= K.TWIN_MAX_DISTANCE]
    improved = [t for t in similar if change[t] >= K.TWIN_MIN_IMPROVEMENT]
    caveats = [] if "poverty_index" in used else [{"template_key": "caveat.poverty_not_available", "params": {}}]
    focus_id = b.taluka(focus)
    n_rows = int(len(tables["schools"]))
    dist_prov = [b.query("schools", {"taluka_id": list(cov.index)}, n_rows), b.query("talukas", {"taluka_id": list(cov.index)}, len(cov))]
    if not improved:
        return b.finding(id="F.twin", type="TWIN", label="INSUFFICIENT", rule_id="TWIN-NONE", template_key="twin.none_found",
                         params={"focus": {"entity": focus_id}},
                         criteria=[{"id": "similar_and_improved", "passed": False, "threshold": K.TWIN_MIN_IMPROVEMENT}],
                         sample={"n_talukas": len(similar)}, caveats=caveats)
    twin = improved[0]
    decoys = [t for t in similar if t not in improved]
    tw_change = change_number(b, sc, tm, twin, y0, y1)
    d_twin = b.number(f"n.distance.twin.{twin}", dist[twin], "index", 2, dist_prov, "mean", entity=b.taluka(twin), n=len(used))

    def count(tid):
        n = int((tables["schools"]["taluka_id"] == tid).sum())
        return b.number(f"n.count.schools.{tid}", n, "count", 0, [b.query("schools", {"taluka_id": tid}, n)], "count",
                        entity=b.taluka(tid), of="schools")

    params = {"twin": {"entity": twin}, "focus": {"entity": focus_id}, "twin_change": {"number": tw_change},
              "twin_rank_from": {"number": rank_number(b, sc, tm, twin, y0)}, "twin_rank_to": {"number": rank_number(b, sc, tm, twin, y1)},
              "n_schools_twin": {"number": count(twin)}, "n_schools_focus": {"number": count(focus)}}
    if decoys:
        decoy = decoys[0]
        params |= {"decoy": {"entity": b.taluka(decoy)}, "decoy_change": {"number": change_number(b, sc, tm, decoy, y0, y1)}}
        b.number(f"n.distance.decoy.{decoy}", dist[decoy], "index", 2, dist_prov, "mean", entity=decoy, n=len(used))
    criteria = [{"id": "covariate_distance_max", "number": d_twin, "threshold": K.TWIN_MAX_DISTANCE, "passed": True},
                {"id": "same_election_duty_years", "passed": True},
                {"id": "improved_min", "number": tw_change, "threshold": K.TWIN_MIN_IMPROVEMENT, "passed": True}]
    return b.finding(id="F.twin", type="TWIN", label="LEARN_FROM", rule_id="TWIN-LEARN-FROM", template_key="twin.learn_from",
                     params=params, criteria=criteria, sample={"n_talukas": len(similar) + 1, "covariates": used}, caveats=caveats)
