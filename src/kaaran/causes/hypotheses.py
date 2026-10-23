"""CAUSE findings: election duty, teacher vacancy, infrastructure and attendance hypotheses."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import confidence as K
from ..evidence import Builder
from .data import SUBJECT, corr_t, school_wide, taluka_means, welch_t
from .trend import change_number

ASSOCIATED = [{"template_key": "caveat.associated_not_caused", "params": {}}]


def association_caveat(label: str) -> list[dict]:
    """'An association, not a proven cause' fits WEAK findings only (STRONG meets the criteria; RULED_OUT found no link)."""
    return list(ASSOCIATED) if label == "WEAK" else []


def _inconclusive(b: Builder, fid: str, hypothesis: str, focus: str, criteria: list, sample: dict) -> dict:
    return b.finding(id=fid, type="CAUSE", label="INSUFFICIENT", rule_id="CAUSE-INSUFFICIENT", hypothesis=hypothesis, origin="default",
                     template_key="cause.inconclusive",
                     params={"taluka": {"entity": focus}, "hypothesis": {"text_key": f"hypothesis.{hypothesis}"}},
                     criteria=criteria, sample=sample)


# ---------- election duty (taluka-level exposure) ----------


def heavy_duty_years(duty: pd.DataFrame) -> pd.DataFrame:
    """(taluka_id, academic_year) with >= ELECTION_HEAVY_PCT % of teachers deployed in >= ELECTION_HEAVY_MONTHS months."""
    heavy = duty[duty["deployed_pct"] >= K.ELECTION_HEAVY_PCT]
    n = heavy.groupby(["taluka_id", "academic_year"]).size()
    return n[n >= K.ELECTION_HEAVY_MONTHS].reset_index()[["taluka_id", "academic_year"]]


def election(b: Builder, tables: dict, sc: pd.DataFrame, focus: str, insufficient: bool) -> dict | None:
    exposed = heavy_duty_years(tables["election_duty"])
    tm = taluka_means(sc)
    years = sorted(tm.columns)
    focus_years = sorted(y for y in exposed.loc[exposed["taluka_id"] == focus, "academic_year"] if y in years and years.index(y) > 0)
    if not focus_years:
        return None  # hypothesis does not apply: the focus taluka had no heavy election duty
    y = focus_years[-1]
    prev = years[years.index(y) - 1]
    comparison = sorted(set(exposed.loc[exposed["academic_year"] == y, "taluka_id"]) - {focus})
    focus_change = change_number(b, sc, tm, focus, prev, y)
    changes = {t: tm.loc[t, y] - tm.loc[t, prev] for t in comparison}
    n_no_drop = sum(1 for v in changes.values() if v > K.DROP_POINTS)
    n_rows = int((sc["taluka_id"].isin(comparison) & sc["academic_year"].isin([prev, y])).sum())
    nd = b.number(f"n.count.election_no_drop.{y}", n_no_drop, "count", 0,
                  [b.query("scores", {"taluka_id": comparison, "academic_year": [prev, y], "subject": SUBJECT}, n_rows),
                   b.constant("CAUSE-ELECTION", "DROP_POINTS")], "count_where", of="talukas")
    duty_rows = int((tables["election_duty"]["academic_year"] == y).sum())
    b.number(f"n.count.election_exposed.{y}", len(comparison), "count", 0,
             [b.query("election_duty", {"academic_year": y}, duty_rows), b.constant("CAUSE-ELECTION", "ELECTION_HEAVY_PCT")],
             "count_where", of="talukas")
    sid = b.taluka_set(f"set.election_comparison.{y}", "CAUSE-ELECTION", comparison) if comparison else None
    label, key, criteria = K.election_label(tm.loc[focus, y] - tm.loc[focus, prev], len(comparison), n_no_drop, insufficient,
                                            {"focus_change": focus_change, "no_drop": nd})
    sample = {"n_talukas": len(comparison) + 1}
    if key == "cause.inconclusive":
        return _inconclusive(b, "F.cause.election", "election", focus, criteria, sample)
    params = {"taluka": {"entity": focus}, "period": {"period": b.period("academic_year", y, y)}, "focus_change": {"number": focus_change}}
    if key != "cause.election.no_link":
        params |= {"similar": {"set": sid}, "n_similar_no_drop": {"number": nd}}
    rule = "CAUSE-ELECTION" if label == "WEAK" else "CAUSE-RULED-OUT"
    return b.finding(id="F.cause.election", type="CAUSE", label=label, rule_id=rule, hypothesis="election", origin="default",
                     template_key=key, params=params, criteria=criteria, sample=sample, caveats=association_caveat(label))


# ---------- teacher vacancy (school-level exposure) ----------


def vacancy(b: Builder, tables: dict, sc: pd.DataFrame, focus: str, insufficient: bool) -> tuple[dict | None, dict]:
    posts = tables["teacher_posts"]
    vac = posts[(posts["subject"] == SUBJECT) & (posts["working"] == 0)]
    start = vac.groupby("udise_code")["academic_year"].min()
    wide = school_wide(sc)
    years = sorted(wide.columns)
    y0, y1 = years[0], years[-1]
    change = (wide[y1] - wide[y0]).dropna()
    taluka = sc.drop_duplicates("udise_code").set_index("udise_code")["taluka_id"]
    in_focus = change[change.index.map(taluka) == focus]
    exposed_codes = sorted(c for c in start.index if c in in_focus.index and start[c] > y0)
    info = {"schools": exposed_codes, "share": 0.0}
    if not exposed_codes:
        return None, info
    since = start[exposed_codes].min()
    e, u = in_focus[in_focus.index.isin(exposed_codes)], in_focus[~in_focus.index.isin(exposed_codes)]
    t = welch_t(e, u)
    total = in_focus.mean()
    share = 100 * len(e) / len(in_focus) * e.mean() / total if total < 0 else 0.0
    outside = change[change.index.map(taluka) != focus]
    out_exp = [c for c in start.index if c in outside.index and start[c] > y0]
    rep_t = welch_t(outside[outside.index.isin(out_exp)], outside[~outside.index.isin(out_exp)]) if len(out_exp) >= K.REPLICATION_MIN_SCHOOLS else None
    pre_year = years[years.index(since) - 1]
    pre = (wide.loc[exposed_codes, pre_year] - wide.loc[exposed_codes, y0]).mean() if pre_year != y0 else 0.0

    sid = b.school_set(f"set.vacancy_maths.{focus}", "CAUSE-SCHOOL-EXPOSURE", exposed_codes)
    n_posts = int(((vac["udise_code"].isin(exposed_codes)) & (vac["academic_year"] == since)).sum())
    n_exp = b.number(f"n.count.schools.vacancy_maths.{focus}", len(exposed_codes), "count", 0,
                     [b.query("teacher_posts", {"taluka_id": focus, "academic_year": since, "subject": SUBJECT, "working": 0}, n_posts)],
                     "count", entity=focus, of="schools")
    q_all = b.query("scores", {"taluka_id": focus, "academic_year": [y0, y1], "subject": SUBJECT}, 2 * len(in_focus))
    g = b.number(f"n.score_change.vacancy_maths.{focus}", e.mean(), "score_change", 1,
                 [b.query("scores", {"udise_code": exposed_codes, "academic_year": [y0, y1], "subject": SUBJECT}, 2 * len(e))],
                 "mean_change", entity=focus, n=len(e))
    o = b.number(f"n.score_change.other_schools.{focus}", u.mean(), "score_change", 1, [q_all], "mean_change", entity=focus, n=len(u))
    sh = b.number(f"n.pct.share_of_decline.vacancy_maths.{focus}", share, "pct", 1, [q_all], "share_of_decline", inputs=[g, n_exp], entity=focus)
    nt = b.number(f"n.t.vacancy_maths.{focus}", t, "t_stat", 2, [q_all], "mean_change", inputs=[g, o], entity=focus, n=len(in_focus))
    nums = {"t": nt, "share": sh}
    if rep_t is not None:
        nums["rep_t"] = b.number(f"n.t.vacancy_maths.outside.{focus}", rep_t, "t_stat", 2,
                                 [b.query("scores", {"udise_code": out_exp, "academic_year": [y0, y1], "subject": SUBJECT}, 2 * len(out_exp))],
                                 "mean_change", n=len(outside))
    nums["pre"] = b.number(f"n.score_change.vacancy_maths.pre.{focus}", pre, "score_change", 1,
                           [b.query("scores", {"udise_code": exposed_codes, "academic_year": [y0, pre_year], "subject": SUBJECT}, 2 * len(e))],
                           "mean_change", entity=focus, n=len(e))
    label, key, criteria = K.exposure_label(t, share, rep_t, pre, insufficient, nums)
    info["share"] = share
    sample = {"n_schools": int(len(in_focus))}
    if key == "cause.inconclusive":
        return _inconclusive(b, "F.cause.vacancy", "vacancy", focus, criteria, sample), info
    params = {"taluka": {"entity": focus}, "subject": {"text_key": "subject.maths"}, "group_change": {"number": g}, "others_change": {"number": o}}
    if key != "cause.vacancy.no_link":
        params["schools"] = {"set": sid}
    if key == "cause.vacancy.concentrated":
        params |= {"since": {"period": b.period("academic_year", since, since)}, "share_of_decline": {"number": sh}}
    rule = {"STRONG": "CAUSE-SCHOOL-EXPOSURE", "WEAK": "CAUSE-SCHOOL-EXPOSURE", "RULED_OUT": "CAUSE-RULED-OUT"}[label]
    caveats = association_caveat(label)
    return b.finding(id="F.cause.vacancy", type="CAUSE", label=label, rule_id=rule, hypothesis="vacancy", origin="default",
                     template_key=key, params=params, criteria=criteria, sample=sample, caveats=caveats), info


# ---------- infrastructure (correlation, pre-registered index) ----------

INFRA_COMPONENTS = ("toilets", "library", "drinking_water", "classrooms_per_pupil")


def infra_index(schools: pd.DataFrame) -> pd.Series:
    """Pre-registered index: mean of district-standardised toilets, library, drinking water, classrooms per pupil."""
    x = pd.DataFrame({"toilets": schools["toilets"], "library": schools["library"], "drinking_water": schools["drinking_water"],
                      "classrooms_per_pupil": schools["classrooms"] / schools["enrol_total"].clip(lower=1)}).astype(float)
    z = (x - x.mean()) / x.std(ddof=0).replace(0, 1)
    return pd.Series(z.mean(axis=1).to_numpy(), index=schools["udise_code"].to_numpy())


def infrastructure(b: Builder, tables: dict, sc: pd.DataFrame, focus: str, insufficient: bool, exclude=frozenset()) -> dict:
    schools = tables["schools"]
    idx = infra_index(schools)
    wide = school_wide(sc)
    years = sorted(wide.columns)
    y0, y1 = years[0], years[-1]
    change = (wide[y1] - wide[y0]).dropna()
    codes = [c for c in schools.loc[schools["taluka_id"] == focus, "udise_code"] if c in change.index and c not in exclude]
    r, t, n = corr_t(idx[codes], change[codes])
    by_taluka = idx.groupby(schools.set_index("udise_code")["taluka_id"]).mean()
    lowest = by_taluka.idxmin()
    tm = taluka_means(sc)
    low_change = change_number(b, sc, tm, lowest, y0, y1)
    stable = abs(tm.loc[lowest, y1] - tm.loc[lowest, y0]) <= K.LOWEST_INFRA_STABLE
    nr = b.number(f"n.corr.infra_vs_change.{focus}", r, "corr", 2,
                  [b.query("schools", {"udise_code": codes}, len(codes)),
                   b.query("scores", {"udise_code": codes, "academic_year": [y0, y1], "subject": SUBJECT}, 2 * len(codes))],
                  "corr", entity=focus, n=n)
    label, key, criteria = K.correlation_label("infrastructure", t, stable, insufficient, {"r": nr, "lowest_change": low_change})
    if key == "cause.inconclusive":
        return _inconclusive(b, "F.cause.infrastructure", "infrastructure", focus, criteria, {"n_schools": n})
    params = {"taluka": {"entity": focus}, "r": {"number": nr}}
    if key == "cause.infra.no_link":
        params |= {"lowest_infra_taluka": {"entity": b.taluka(lowest)}, "lowest_infra_change": {"number": low_change}}
    rule = "CAUSE-RULED-OUT" if label == "RULED_OUT" else "CAUSE-CORRELATION"
    return b.finding(id="F.cause.infrastructure", type="CAUSE", label=label, rule_id=rule, hypothesis="infrastructure", origin="default",
                     template_key=key, params=params, criteria=criteria, sample={"n_schools": n},
                     caveats=[{"template_key": "caveat.static_infra_snapshot", "params": {}}] + association_caveat(label))


# ---------- attendance (correlation, after trust exclusions) ----------


def attendance(b: Builder, tables: dict, sc: pd.DataFrame, att: pd.DataFrame, focus: str, insufficient: bool,
               exclude=frozenset()) -> dict | None:
    if att.empty:
        return None
    year = att.groupby("academic_year").size().idxmax()  # the school year the attendance file mostly covers
    years = sorted(set(sc["academic_year"]))
    if year not in years or years.index(year) == 0:
        return None
    prev = years[years.index(year) - 1]
    a = att[(att["taluka_id"] == focus) & (att["academic_year"] == year)].groupby("udise_code")["attendance_pct"].mean()
    wide = school_wide(sc)
    change = (wide[year] - wide[prev]).dropna()
    codes = [c for c in a.index if c in change.index and c not in exclude]
    r, t, n = corr_t(a[codes], change[codes])
    canon = tables["attendance"]
    n_att = int((canon["udise_code"].isin(codes) & (canon["academic_year"] == year)).sum())
    prov = [b.query("attendance", {"udise_code": codes, "academic_year": year}, n_att),
            b.query("scores", {"udise_code": codes, "academic_year": [prev, year], "subject": SUBJECT}, 2 * len(codes))]
    used = int((att["udise_code"].isin(codes) & (att["academic_year"] == year)).sum())
    if used < n_att:  # months removed by trust flags are named, not hidden
        prov += [b.constant("TRUST-FLAT-SCHOOL", "excluded_months"), b.constant("TRUST-JUMP-ATTENDANCE", "excluded_months")]
    nr = b.number(f"n.corr.attendance_vs_change.{focus}", 0.0 if np.isnan(r) else r, "corr", 2, prov, "corr", entity=focus, n=n)
    label, key, criteria = K.correlation_label("attendance", 0.0 if np.isnan(t) else t, None, insufficient or n < 10, {"r": nr})
    sample = {"n_schools": n}
    if key == "cause.inconclusive":
        return _inconclusive(b, "F.cause.attendance", "attendance", focus, criteria, sample)
    rule = "CAUSE-RULED-OUT" if label == "RULED_OUT" else "CAUSE-CORRELATION"
    return b.finding(id="F.cause.attendance", type="CAUSE", label=label, rule_id=rule, hypothesis="attendance", origin="default",
                     template_key=key, params={"taluka": {"entity": focus}, "r": {"number": nr}}, criteria=criteria, sample=sample,
                     caveats=association_caveat(label))
