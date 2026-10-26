"""Trust checks (block lens). Run before any analysis; flagged data is excluded where it is unreliable and reported.

School rules
- FLAT: >= 3 consecutive months of attendance >= 99.95% -> RED_FLAG (attendance not used in analysis).
- MISSING: >= 3 attendance months missing in the current year, or a comparison assessment round missing
  -> INSUFFICIENT (school left out of risk and diagnosis tests).
- IMPLAUSIBLE_COMBO: a FLAT school whose learning is in the bottom 20% of its block -> detail on the flag
  ("full attendance but low learning").
- CLEARED: the lowest 5% of schools by attendance (district), >= 7 months reported, no flag -> CLEARED.
Cluster rules
- DATA_FLAG: >= 20% of a cluster's schools RED_FLAG -> cluster data alert.
- INSUFFICIENT: >= 20% of a cluster's schools INSUFFICIENT -> conclusions withheld ("cannot tell").
Thresholds are published in docs/06_DECISION_RUBRICS.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

FLAT_VALUE = 99.95
FLAT_RUN = 3
MISSING_MONTHS = 3
CLUSTER_FLAG_SHARE = 0.20
CLUSTER_INSUFFICIENT_SHARE = 0.20
CLEARED_SHARE = 0.05
CLEARED_MIN_MONTHS = 7
COMBO_LOW_QUANTILE = 0.20


@dataclass
class BlockTrust:
    school_flags: pd.DataFrame  # udise_code, rule, label, detail, months
    cluster_flags: pd.DataFrame  # cluster_id, rule, label, share, n_flagged, n_schools
    cleared: pd.DataFrame
    excluded_attendance: set = field(default_factory=set)
    insufficient: set = field(default_factory=set)
    current_year: str = ""
    comparison: dict = field(default_factory=dict)


def comparison_window(assessment: pd.DataFrame) -> dict:
    """Latest year with an endline vs the year before, rounds ML + EL (same rounds both years)."""
    years = sorted(assessment.loc[assessment["round"] == "EL", "academic_year"].unique())
    if len(years) < 2:
        raise ValueError("need two years with an endline round to compare")
    return {"current": years[-1], "previous": years[-2], "rounds": ["ML", "EL"]}


def _flat_runs(att: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for code, g in att.sort_values("month").groupby("udise_code"):
        run, months, best = 0, [], []
        for m, v in zip(g["month"], g["attendance_pct"]):
            if v is not None and not pd.isna(v) and float(v) >= FLAT_VALUE:
                run += 1
                months.append(m)
                if run > len(best):
                    best = list(months)
            else:
                run, months = 0, []
        if len(best) >= FLAT_RUN:
            rows.append({"udise_code": code, "rule": "TRUST-FLAT", "label": "RED_FLAG", "months": best,
                         "detail": f"{len(best)} months at 100%"})
    return pd.DataFrame(rows, columns=["udise_code", "rule", "label", "months", "detail"])


def run_block_trust(tables: dict[str, pd.DataFrame]) -> BlockTrust:
    schools, att, assess = tables["schools"], tables["attendance"], tables["assessment"]
    window = comparison_window(assess)
    cur = window["current"]
    flags = _flat_runs(att)
    # missing data in the current year
    expected_months = sorted(att.loc[att["academic_year"] == cur, "month"].unique())
    have = att[att["academic_year"] == cur].groupby("udise_code")["month"].nunique()
    missing_att = (len(expected_months) - have.reindex(schools["udise_code"]).fillna(0)).astype(int)
    rounds_needed = {(window["current"], r) for r in window["rounds"]} | {(window["previous"], r) for r in window["rounds"]}
    got = assess.groupby("udise_code").apply(lambda g: set(zip(g["academic_year"], g["round"])), include_groups=False)
    miss_rows = []
    for code in schools["udise_code"]:
        lacking = rounds_needed - got.get(code, set())
        if missing_att[code] >= MISSING_MONTHS or lacking:
            parts = []
            if missing_att[code] >= MISSING_MONTHS:
                parts.append(f"{missing_att[code]} attendance months missing")
            if lacking:
                parts.append("assessment round missing: " + ", ".join(f"{y} {r}" for y, r in sorted(lacking)))
            miss_rows.append({"udise_code": code, "rule": "TRUST-MISSING", "label": "INSUFFICIENT", "months": [],
                              "detail": "; ".join(parts)})
    flags = pd.concat([flags, pd.DataFrame(miss_rows, columns=flags.columns)], ignore_index=True)
    # implausible combination: full attendance + low learning (relative to the block)
    cur_learning = (assess[(assess["academic_year"] == cur) & assess["round"].isin(window["rounds"])]
                    .groupby("udise_code")["pct"].mean())
    s = schools.set_index("udise_code")
    for i, r in flags[flags["rule"] == "TRUST-FLAT"].iterrows():
        block = s.at[r["udise_code"], "block"]
        peers = cur_learning.reindex(s.index[s["block"] == block]).dropna()
        own = cur_learning.get(r["udise_code"])
        if own is not None and len(peers) >= 10 and own <= peers.quantile(COMBO_LOW_QUANTILE):
            flags.at[i, "detail"] = r["detail"] + "; full attendance but learning in the bottom 20% of the block"
            flags.at[i, "rule"] = "TRUST-FLAT"
    red = set(flags.loc[flags["label"] == "RED_FLAG", "udise_code"])
    insufficient = set(flags.loc[flags["label"] == "INSUFFICIENT", "udise_code"])
    # cleared: honest low attendance
    ok = att[~att["udise_code"].isin(red | insufficient)]
    counts = ok.groupby("udise_code")["month"].nunique()
    means = ok.groupby("udise_code")["attendance_pct"].mean()[counts >= CLEARED_MIN_MONTHS]
    n_clear = math.ceil(CLEARED_SHARE * len(means))
    cleared = means.nsmallest(n_clear).rename("mean_attendance").reset_index()
    cleared["rule"], cleared["label"] = "TRUST-CLEARED", "CLEARED"
    # cluster rules
    crow = []
    sc = schools[["udise_code", "cluster_id"]]
    for cid, g in sc.groupby("cluster_id"):
        n = len(g)
        n_red = int(g["udise_code"].isin(red).sum())
        n_ins = int(g["udise_code"].isin(insufficient).sum())
        if n and n_red / n >= CLUSTER_FLAG_SHARE:
            crow.append({"cluster_id": cid, "rule": "TRUST-CLUSTER-FLAG", "label": "RED_FLAG", "share": round(n_red / n, 3),
                         "n_flagged": n_red, "n_schools": n})
        if n and n_ins / n >= CLUSTER_INSUFFICIENT_SHARE:
            crow.append({"cluster_id": cid, "rule": "TRUST-CLUSTER-INSUFFICIENT", "label": "INSUFFICIENT",
                         "share": round(n_ins / n, 3), "n_flagged": n_ins, "n_schools": n})
    cluster_flags = pd.DataFrame(crow, columns=["cluster_id", "rule", "label", "share", "n_flagged", "n_schools"])
    return BlockTrust(school_flags=flags, cluster_flags=cluster_flags, cleared=cleared, excluded_attendance=red,
                      insufficient=insufficient, current_year=cur, comparison=window)
