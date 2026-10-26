"""Insight engine (block lens, no LLM): risk scanner, differential diagnosis per cluster, competency focus,
positive deviants, surplus schools, twin block. Rules and thresholds: docs/06_DECISION_RUBRICS.md.

Comparison: the latest year with an endline vs the year before, rounds ML + EL, school by school.
"rel" = a school's change minus the median change of its block (removes district-wide events such as poll duty).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .trust import BlockTrust

# risk scanner
DROP_MEAN = -5.0
DROP_T = -2.0
POCKET_DROP = -10.0
POCKET_MIN = 4
POCKET_MEAN = -3.0
LEVEL_GAP = 5.0
ATT_LOW = 75.0
ATT_MONTHS = 4  # Dec-Mar: peak seasonal absence
COMP_LOW = 50.0
RISK_WEIGHTS = {"DROP": 3, "LEVEL": 2, "ATTENDANCE": 3, "COMPETENCY": 1}  # chronic absence alone needs attention
AT_RISK = 3
# diagnosis
STRONG_T = -3.0
WEAK_T = -2.0
STRONG_DIFF = -5.0
WEAK_DIFF = -3.0
SHARE_MIN = 0.5
REPLICATION_T = -2.0
PRIOR_MAX_DROP = -2.0
STAFF_GAP_MONTHS = 3
VISITS_LOW = 0.5
VISITS_BEFORE = 0.8
TRAINING_STALE_DAYS = 365
ABSENCE_DROP = -5.0
MIGRATION_GAP = 10.0
MIGRATION_YEARS = 2
MIGRATION_MIN_SCHOOLS = 3
DUTY_HEAVY = 5.0
DUTY_NO_DROP_SHARE = 2 / 3
COMP_DIFF = -5.0
COMP_T = -2.5
PD_REL = 3.0
SURPLUS_PTR = 20.0
SURPLUS_MIN_TEACHERS = 3
TWIN_MAX_DISTANCE = 1.0
TWIN_MIN_GAIN = 2.0
WINTER = (11, 12, 1, 2, 3)
MONSOON = (6, 7, 8, 9, 10)


def _t_one(x: pd.Series) -> float:
    x = x.dropna()
    if len(x) < 3 or x.std(ddof=1) == 0:
        return 0.0
    return float(x.mean() / (x.std(ddof=1) / math.sqrt(len(x))))


def _welch(a: pd.Series, b: pd.Series) -> float:
    a, b = a.dropna(), b.dropna()
    if len(a) < 2 or len(b) < 2:
        return 0.0
    se = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return float((a.mean() - b.mean()) / se) if se else 0.0


@dataclass
class Check:
    id: str
    status: str  # STRONG | WEAK | RULED_OUT | NOT_APPLICABLE
    stats: dict = field(default_factory=dict)
    schools: list = field(default_factory=list)
    criteria: list = field(default_factory=list)


@dataclass
class ClusterResult:
    cluster_id: str
    block: str
    n_schools: int
    status: str  # AT_RISK | DATA | INSUFFICIENT | OK
    risk: dict = field(default_factory=dict)  # trigger -> stats
    weight: int = 0
    checks: dict = field(default_factory=dict)  # D1..D8 -> Check
    competencies: list = field(default_factory=list)
    schools: list = field(default_factory=list)


@dataclass
class BlockAnalysis:
    focus_block: str
    window: dict
    changes: pd.DataFrame
    clusters: dict
    duty: Check | None
    positive_deviants: list
    surplus: list
    twin: dict
    context: dict


def school_changes(tables: dict, trust: BlockTrust) -> pd.DataFrame:
    w = trust.comparison
    a = tables["assessment"]
    a = a[a["round"].isin(w["rounds"]) & a["academic_year"].isin([w["previous"], w["current"]])]
    a = a[~a["udise_code"].isin(trust.insufficient)]
    comp_subject = {c: ("maths" if c.startswith("M") else "language") for c in a["competency"].unique()}
    a = a.assign(subject=a["competency"].map(comp_subject))
    rows = []
    for subj, sub in (("maths", a[a["subject"] == "maths"]), ("language", a[a["subject"] == "language"]), ("overall", a)):
        m = sub.groupby(["udise_code", "academic_year"])["pct"].mean().unstack()
        n = sub.groupby(["udise_code", "academic_year"]).size().unstack()
        df = pd.DataFrame({"prev": m.get(w["previous"]), "cur": m.get(w["current"]),
                           "n_rows": n.sum(axis=1)}).dropna(subset=["prev", "cur"])
        df["subject"] = subj
        rows.append(df.reset_index())
    ch = pd.concat(rows, ignore_index=True)
    ch["chg"] = ch["cur"] - ch["prev"]
    ch = ch.merge(tables["schools"][["udise_code", "block", "cluster_id"]], on="udise_code", how="left")
    med = ch.groupby(["block", "subject"])["chg"].transform("median")
    ch["rel"] = ch["chg"] - med
    return ch


def _prior_changes(tables: dict, trust: BlockTrust) -> pd.Series:
    """Overall change in the year before the comparison (for the timing check)."""
    a = tables["assessment"]
    years = sorted(a["academic_year"].unique())
    prev = trust.comparison["previous"]
    if years.index(prev) == 0:
        return pd.Series(dtype=float)
    before = years[years.index(prev) - 1]
    a = a[a["round"].isin(trust.comparison["rounds"]) & a["academic_year"].isin([before, prev])]
    m = a.groupby(["udise_code", "academic_year"])["pct"].mean().unstack()
    return (m[prev] - m[before]).dropna()


def _risk(cluster: pd.DataFrame, ch: pd.DataFrame, block_levels: pd.Series, att_low_count: int, n_valid: int,
          comp_low: list) -> tuple[dict, int]:
    triggers = {}
    best = None
    for subj in ("maths", "language", "overall"):
        rel = ch[(ch["subject"] == subj) & ch["udise_code"].isin(cluster["udise_code"])]["rel"]
        if len(rel) < 3:
            continue
        mean, t, drops = float(rel.mean()), _t_one(rel), int((rel <= POCKET_DROP).sum())
        pocket = subj == "overall" and drops >= POCKET_MIN and mean <= POCKET_MEAN  # pockets judged on both subjects
        hit = (mean <= DROP_MEAN and t <= DROP_T) or pocket
        if hit and (best is None or mean < best["mean"]):
            best = {"subject": subj, "mean": mean, "t": t, "droppers": drops, "n": int(len(rel)),
                    "route": "broad" if (mean <= DROP_MEAN and t <= DROP_T) else "pocket"}
    if best:
        triggers["DROP"] = best
    cid = cluster["cluster_id"].iloc[0]
    if cid in block_levels.index and len(block_levels) >= 4:
        level, med, q1 = float(block_levels[cid]), float(block_levels.median()), float(block_levels.quantile(0.25))
        if level <= q1 and level <= med - LEVEL_GAP:
            triggers["LEVEL"] = {"level": level, "block_median": med}
    if n_valid and att_low_count >= max(3, math.ceil(n_valid / 4)):
        triggers["ATTENDANCE"] = {"schools_low": att_low_count, "n": n_valid}
    if len(comp_low) >= 2:
        triggers["COMPETENCY"] = {"low": comp_low}
    return triggers, sum(RISK_WEIGHTS[k] for k in triggers)


def _exposure_test(exposed: set, cluster_codes: set, focus_codes: set, district_codes: set, ch: pd.DataFrame,
                   prior: pd.Series, subject: str = "overall", min_in_cluster: int = 2, deviants: set = frozenset()) -> Check | None:
    """Exposed vs unexposed schools. Positive deviants (improved despite the exposure) are analysed separately."""
    exposed = exposed - set(deviants)
    in_cluster = exposed & cluster_codes
    if len(in_cluster) < min_in_cluster:
        return None
    o = ch[ch["subject"] == subject].set_index("udise_code")["rel"]
    exp_focus = o.reindex(sorted(exposed & focus_codes)).dropna()
    unexp_focus = o.reindex(sorted(focus_codes - exposed)).dropna()
    t = _welch(exp_focus, unexp_focus)
    diff = float(exp_focus.mean() - unexp_focus.mean()) if len(exp_focus) and len(unexp_focus) else 0.0
    cl = o.reindex(sorted(cluster_codes)).dropna()
    total = float(cl[cl < 0].sum())
    contrib = float(o.reindex(sorted(in_cluster)).dropna().clip(upper=0).sum())
    share = min(1.0, contrib / total) if total < 0 else 0.0
    outside = o.reindex(sorted(exposed & (district_codes - focus_codes))).dropna()
    rep_t = _t_one(outside) if len(outside) >= 3 else 0.0
    replicated = len(outside) >= 3 and rep_t <= REPLICATION_T and outside.mean() <= WEAK_DIFF
    pri = prior.reindex(sorted(in_cluster)).dropna()
    pri_others = prior.reindex(sorted(focus_codes - exposed)).dropna()
    pre_t = _welch(pri, pri_others)
    pre_diff = float(pri.mean() - pri_others.mean()) if len(pri) and len(pri_others) else 0.0
    timing_ok = len(pri) < 2 or not (pre_t <= WEAK_T and pre_diff <= WEAK_DIFF)  # no pre-existing decline
    criteria = [
        {"id": "effect_t", "value": round(t, 2), "threshold": STRONG_T, "passed": t <= STRONG_T},
        {"id": "effect_diff", "value": round(diff, 2), "threshold": STRONG_DIFF, "passed": diff <= STRONG_DIFF},
        {"id": "share_of_decline", "value": round(share, 3), "threshold": SHARE_MIN, "passed": share >= SHARE_MIN},
        {"id": "replication", "value": round(rep_t, 2), "threshold": REPLICATION_T, "passed": bool(replicated)},
        {"id": "timing", "value": round(pre_diff, 2), "threshold": WEAK_DIFF, "passed": bool(timing_ok)},
    ]
    if all(c["passed"] for c in criteria):
        status = "STRONG"
    elif t <= WEAK_T and diff <= WEAK_DIFF:
        status = "WEAK"
    else:
        status = "RULED_OUT"
    stats = {"t": t, "diff": diff, "share": share, "replication_t": rep_t, "n_replication": int(len(outside)),
             "exposed_mean": float(o.reindex(sorted(in_cluster)).dropna().mean()),
             "others_mean": float(unexp_focus.mean()) if len(unexp_focus) else None,
             "n_exposed_cluster": len(in_cluster), "n_exposed_focus": int(len(exp_focus)),
             "prior_change": float(pri.mean()) if len(pri) else None}
    return Check("", status, stats, sorted(in_cluster), criteria)


def analyze_block(tables: dict, trust: BlockTrust, focus_block: str) -> BlockAnalysis:
    w = trust.comparison
    schools = tables["schools"]
    blocks = sorted(schools["block"].unique())
    focus = next((b for b in blocks if b.lower() == focus_block.lower()), None)
    if focus is None:
        raise KeyError(f"unknown block {focus_block!r}; known: {blocks}")
    ch = school_changes(tables, trust)
    prior = _prior_changes(tables, trust)
    district_codes = set(schools["udise_code"]) - trust.insufficient
    fs = schools[schools["block"] == focus]
    focus_codes = set(fs["udise_code"]) - trust.insufficient

    # ---- exposures (district-wide, for replication) ----
    posts = tables["posts"]
    gap_months = (posts[posts["academic_year"] == w["current"]].assign(gap=lambda d: d["working"] < d["sanctioned"])
                  .groupby("udise_code")["gap"].sum())
    staffing = set(gap_months[gap_months >= STAFF_GAP_MONTHS].index)
    visits = tables["visits"]
    kp = visits[visits["visitor_role"].str.lower().str.contains("kendra")].assign(
        year=lambda d: d["date"].str[:7].map(lambda m: f"{int(m[:4]) if int(m[5:]) >= 6 else int(m[:4]) - 1}-"
                                              f"{((int(m[:4]) if int(m[5:]) >= 6 else int(m[:4]) - 1) + 1) % 100:02d}"))
    months_per_year = tables["attendance"].groupby("academic_year")["month"].nunique()
    rate = kp.groupby(["udise_code", "year"]).size().unstack(fill_value=0)
    rate_cur = rate.get(w["current"], pd.Series(dtype=float)).reindex(sorted(district_codes), fill_value=0) / months_per_year[w["current"]]
    rate_prev = rate.get(w["previous"], pd.Series(dtype=float)).reindex(sorted(district_codes), fill_value=0) / months_per_year[w["previous"]]
    # support gap is a cluster-level event (Kendra Pramukh post vacant): judge the cluster's mean visit rate
    cl_of = schools.set_index("udise_code")["cluster_id"]
    cl_cur, cl_prev = rate_cur.groupby(cl_of).mean(), rate_prev.groupby(cl_of).mean()
    gap_clusters = set(cl_cur[(cl_cur < VISITS_LOW) & (cl_prev.reindex(cl_cur.index) >= VISITS_BEFORE)].index)
    support = {c for c in district_codes if cl_of.get(c) in gap_clusters} - staffing
    training = tables["training"]
    last_training = training.groupby("udise_code")["date"].max()
    end_cur = f"{int(w['current'][:4]) + 1}-03-31"
    stale = {c for c in district_codes
             if c not in last_training or (pd.Timestamp(end_cur) - pd.Timestamp(last_training[c])).days > TRAINING_STALE_DAYS}
    att = tables["attendance"][~tables["attendance"]["udise_code"].isin(trust.excluded_attendance)]
    att = att.assign(mnum=att["month"].str[5:].astype(int))
    same = att[att["academic_year"].isin([w["previous"], w["current"]])]
    am = same.groupby(["udise_code", "academic_year"])["attendance_pct"].mean().unstack()
    absence = set(am.index[(am.get(w["current"]) - am.get(w["previous"])) <= ABSENCE_DROP])
    seasonal = att.assign(season=np.where(att["mnum"].isin(WINTER), "w", "m")).groupby(
        ["udise_code", "academic_year", "season"])["attendance_pct"].mean().unstack()
    seasonal["gap"] = seasonal["m"] - seasonal["w"]
    pattern_years = (seasonal["gap"] >= MIGRATION_GAP).groupby(level=0).sum()
    migration = set(pattern_years[pattern_years >= MIGRATION_YEARS].index)
    last3 = sorted(att.loc[att["academic_year"] == w["current"], "month"].unique())[-ATT_MONTHS:]
    low_att = att[att["month"].isin(last3)].assign(low=lambda d: d["attendance_pct"] < ATT_LOW).groupby("udise_code")["low"].sum()

    pds = _positive_deviants(ch, focus_codes, staffing, support)
    deviants = {p["udise_code"] for p in pds}
    # ---- cluster loop ----
    cur_level = ch[ch["subject"] == "overall"].groupby("cluster_id")["cur"].mean()
    focus_clusters = sorted(fs["cluster_id"].dropna().unique())
    block_levels = cur_level.reindex(focus_clusters).dropna()
    flag_by_cluster = {(r.cluster_id, r.label): r for r in trust.cluster_flags.itertuples(index=False)}
    comp = tables["assessment"]
    comp = comp[comp["round"].isin(w["rounds"]) & comp["academic_year"].isin([w["previous"], w["current"]])
                & ~comp["udise_code"].isin(trust.insufficient)]
    comp_cur = comp[comp["academic_year"] == w["current"]].merge(schools[["udise_code", "cluster_id"]], on="udise_code")
    results = {}
    for cid in focus_clusters:
        cs = fs[fs["cluster_id"] == cid]
        codes = set(cs["udise_code"])
        valid = codes - trust.insufficient
        res = ClusterResult(cid, focus, len(cs), "OK", schools=sorted(codes))
        if (cid, "INSUFFICIENT") in flag_by_cluster:
            res.status = "INSUFFICIENT"
            results[cid] = res
            continue
        comp_means = comp_cur[comp_cur["cluster_id"] == cid].groupby("competency")["pct"].mean()
        comp_low = sorted(comp_means[comp_means < COMP_LOW].index)
        att_low = int((low_att.reindex(sorted(valid - trust.excluded_attendance)).fillna(0) >= 2).sum())
        res.risk, res.weight = _risk(cs, ch, block_levels, att_low, len(valid - trust.excluded_attendance), comp_low)
        if (cid, "RED_FLAG") in flag_by_cluster:
            res.status = "DATA"
        elif res.weight >= AT_RISK:
            res.status = "AT_RISK"
        if res.status in ("AT_RISK", "DATA"):
            res.checks = _diagnose(res, valid, focus_codes, district_codes, ch, prior, staffing, support, absence, migration,
                                   stale, (cid, "RED_FLAG") in flag_by_cluster, rate_cur, rate_prev, seasonal, deviants)
            res.competencies = _competency_focus(comp[comp["udise_code"].isin(focus_codes)], valid, w) if res.status == "AT_RISK" else []
            if res.competencies:
                res.checks["D7"] = Check("D7", "STRONG" if res.competencies[0]["t"] <= STRONG_T else "WEAK",
                                         {"competencies": res.competencies}, sorted(valid))
            causes = [k for k in ("D1", "D2", "D3", "D4", "D6") if res.checks.get(k) and res.checks[k].status in ("STRONG", "WEAK")]
            if not causes and res.status == "AT_RISK":
                res.checks["D8"] = Check("D8", "WEAK", {}, sorted(valid))
        results[cid] = res

    duty = _duty_check(tables, w, results, focus)
    surplus = _surplus(tables, w, focus_codes)
    twin = _twin(ch, tables, w, focus)
    context = {"staffing": staffing, "support": support, "stale_training": stale, "absence": absence,
               "migration": migration, "kp_rate_cur": rate_cur, "kp_rate_prev": rate_prev,
               "last_training": last_training, "low_att_months": last3}
    return BlockAnalysis(focus, w, ch, results, duty, pds, surplus, twin, context)


def _diagnose(res, valid, focus_codes, district_codes, ch, prior, staffing, support, absence, migration, stale, red_flag,
              rate_cur, rate_prev, seasonal, deviants=frozenset()) -> dict:
    checks = {}
    for did, exposed, subject, min_n in (("D1", staffing, "overall", 2), ("D2", support, "maths", 3),
                                         ("D3", absence, "overall", 2)):
        c = _exposure_test(exposed, valid, focus_codes, district_codes, ch, prior, subject, min_n, deviants)
        if c is not None:
            c.id = did
            if did == "D2":
                codes = sorted(exposed & valid)
                c.stats["visits_now"] = float(rate_cur.reindex(codes).mean())
                c.stats["visits_before"] = float(rate_prev.reindex(codes).mean())
                c.stats["training_stale"] = len(set(codes) & stale)
            checks[did] = c
    mig = sorted(migration & valid)
    if len(mig) >= MIGRATION_MIN_SCHOOLS:
        gaps = seasonal["gap"].unstack()
        cur_gap = gaps.reindex(mig).iloc[:, -1]
        years_all = int((gaps.reindex(mig) >= MIGRATION_GAP).all(axis=1).sum())
        status = "STRONG" if years_all >= MIGRATION_MIN_SCHOOLS else "WEAK"
        checks["D4"] = Check("D4", status, {"n": len(mig), "winter_gap": float(cur_gap.mean()), "years": int(gaps.shape[1])},
                             mig, [{"id": "pattern_years", "value": int(gaps.shape[1]), "threshold": MIGRATION_YEARS,
                                    "passed": True}])
    if red_flag:
        checks["D6"] = Check("D6", "STRONG", {}, [])
    return checks


def _competency_focus(comp: pd.DataFrame, valid: set, w: dict) -> list:
    """Competencies where the cluster is weakest relative to the block's profile (current year, ML + EL).

    For each school: deviation from the block mean of each competency, minus the school's own mean deviation in
    that subject; then the cluster mean and t across schools. Levels (not changes) halve the noise of small schools.
    """
    cur = comp[comp["academic_year"] == w["current"]]
    out = []
    for subj, prefix in (("maths", "M"), ("language", "L")):
        s = cur[cur["competency"].str.startswith(prefix)]
        m = s.groupby(["udise_code", "competency"])["pct"].mean().unstack()
        dev = m - m.mean()  # vs the block (comp is already limited to the focus block's valid schools)
        rel = dev.sub(dev.mean(axis=1), axis=0).reindex(sorted(valid)).dropna(how="all")
        for code in rel.columns:
            col = rel[code].dropna()
            mean, t = float(col.mean()), _t_one(col)
            if mean <= COMP_DIFF and t <= COMP_T:
                out.append({"competency": code, "subject": subj, "rel": mean, "t": t,
                            "level": float(m.reindex(sorted(valid))[code].mean()), "block_level": float(m[code].mean()),
                            "n": int(col.size)})
    return sorted(out, key=lambda d: d["rel"])[:2]


def _duty_check(tables: dict, w: dict, results: dict, focus: str) -> Check | None:
    p = tables["posts"]
    p = p[p["academic_year"] == w["current"]]
    by_month = p.groupby("month")["duty_days"].mean()
    heavy = sorted(by_month[by_month >= DUTY_HEAVY].index)
    if not heavy:
        return None
    others = [r for r in results.values() if r.status in ("OK", "AT_RISK")]
    no_drop = [r for r in others if "DROP" not in r.risk]
    share = len(no_drop) / len(others) if others else 0.0
    status = "RULED_OUT" if share >= DUTY_NO_DROP_SHARE else "WEAK"
    return Check("D5", status, {"months": heavy, "duty_days": float(by_month[heavy].mean()), "share_no_drop": share,
                                "n_clusters": len(others), "n_no_drop": len(no_drop)}, [],
                 [{"id": "share_same_duty_no_drop", "value": round(share, 3), "threshold": DUTY_NO_DROP_SHARE,
                   "passed": share >= DUTY_NO_DROP_SHARE}])


def _positive_deviants(ch: pd.DataFrame, focus_codes: set, staffing: set, support: set) -> list:
    o = ch[ch["subject"] == "overall"].set_index("udise_code")
    out = []
    for kind, exposed in (("staffing_gap", staffing), ("support_gap", support)):
        group = o.reindex(sorted(exposed & focus_codes)).dropna(subset=["rel"])
        if len(group) < 3 or group["rel"].mean() > STRONG_DIFF:
            continue
        for code, r in group[group["rel"] >= PD_REL].iterrows():
            out.append({"udise_code": code, "constraint": kind, "rel": float(r["rel"]), "chg": float(r["chg"]),
                        "group_mean": float(group["rel"].mean()), "cluster_id": r["cluster_id"]})
    return out


def _surplus(tables: dict, w: dict, focus_codes: set) -> list:
    y = tables["udise_year"]
    enrol = y[y["academic_year"] == w["current"]].set_index("udise_code")["enrol_total"]
    p = tables["posts"]
    sep = p[(p["academic_year"] == w["current"]) & (p["month"].str[5:] == "09")].set_index("udise_code")["working"]
    out = []
    for code in sorted(focus_codes):
        if code in enrol and code in sep and sep[code] >= SURPLUS_MIN_TEACHERS:
            ptr = float(enrol[code]) / float(sep[code])
            if ptr < SURPLUS_PTR:
                out.append({"udise_code": code, "ptr": ptr, "working": int(sep[code]), "enrol": int(enrol[code])})
    return out


def _twin(ch: pd.DataFrame, tables: dict, w: dict, focus: str) -> dict:
    o = ch[ch["subject"] == "overall"]
    blk = o.groupby("block").agg(chg=("chg", "mean"), t=("chg", lambda x: _t_one(x)), n=("chg", "size"))
    y = tables["udise_year"]
    yc = y[y["academic_year"] == w["current"]].merge(tables["schools"][["udise_code", "block", "rural_urban"]], on="udise_code")
    cov = yc.groupby("block").agg(n_schools=("udise_code", "size"), enrol=("enrol_total", "mean"),
                                  ptr=("enrol_total", "sum"), teachers=("total_tch", "sum"),
                                  rural=("rural_urban", lambda s: float((s == 1).mean())))
    cov["ptr"] = cov["ptr"] / cov["teachers"]
    cov = cov[["n_schools", "enrol", "ptr"]]
    z = (cov - cov.mean()) / cov.std(ddof=0).replace(0, 1)
    dist = np.sqrt(((z - z.loc[focus]) ** 2).mean(axis=1)).drop(focus)
    similar = dist[dist <= TWIN_MAX_DISTANCE].sort_values()
    gain = blk["chg"] - blk.loc[focus, "chg"]
    twin = next((b for b in similar.index if blk.loc[b, "chg"] >= TWIN_MIN_GAIN and blk.loc[b, "t"] >= 2), None)
    decoy = next((b for b in similar.index if b != twin and blk.loc[b, "chg"] < TWIN_MIN_GAIN), None)
    return {"twin": twin, "decoy": decoy, "distance": dist.to_dict(), "block_change": blk["chg"].to_dict(),
            "focus_change": float(blk.loc[focus, "chg"]), "gain": gain.to_dict(), "covariates": cov.to_dict("index")}
