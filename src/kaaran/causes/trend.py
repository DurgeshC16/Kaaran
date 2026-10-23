"""TREND finding: taluka score change, rank change and a school-level paired test."""

from __future__ import annotations

import pandas as pd

from .. import confidence as K
from ..evidence import Builder
from .data import SUBJECT, paired_t, school_wide, taluka_means


def mean_number(b: Builder, sc: pd.DataFrame, tm: pd.DataFrame, tid: str, year: str) -> str:
    n = int(((sc["taluka_id"] == tid) & (sc["academic_year"] == year)).sum())
    return b.number(f"n.score_mean.{tid}.{year}", tm.loc[tid, year], "score", 1,
                    [b.query("scores", {"taluka_id": tid, "academic_year": year, "subject": SUBJECT}, n)],
                    "mean", entity=b.taluka(tid), n=n)


def change_number(b: Builder, sc: pd.DataFrame, tm: pd.DataFrame, tid: str, y0: str, y1: str) -> str:
    a, c = mean_number(b, sc, tm, tid, y1), mean_number(b, sc, tm, tid, y0)
    value = round(b.numbers[a]["value"] - b.numbers[c]["value"], 1)  # change of the displayed means
    return b.number(f"n.score_change.{tid}.{y0}_{y1}", value, "score_change", 1, op="diff", inputs=[a, c], entity=tid)


def rank_number(b: Builder, sc: pd.DataFrame, tm: pd.DataFrame, tid: str, year: str) -> str:
    ranks = tm[year].rank(ascending=False, method="min")
    n = int((sc["academic_year"] == year).sum())
    return b.number(f"n.rank.{tid}.{year}", int(ranks[tid]), "rank", 0,
                    [b.query("scores", {"academic_year": year, "subject": SUBJECT}, n)], "rank_desc",
                    entity=b.taluka(tid), out_of=int(ranks.notna().sum()))


def analyse_trend(b: Builder, sc: pd.DataFrame, focus: str, insufficient: bool) -> dict:
    tm = taluka_means(sc)
    years = sorted(tm.columns)
    y0, y1 = years[0], years[-1]
    wide = school_wide(sc[sc["taluka_id"] == focus])
    diff = (wide[y1] - wide[y0]).dropna()
    t = paired_t(diff)
    s0, s1 = mean_number(b, sc, tm, focus, y0), mean_number(b, sc, tm, focus, y1)
    ch = change_number(b, sc, tm, focus, y0, y1)
    r0, r1 = rank_number(b, sc, tm, focus, y0), rank_number(b, sc, tm, focus, y1)
    nt = b.number(f"n.paired_t.{focus}.{y0}_{y1}", t, "t_stat", 2,
                  [b.query("scores", {"taluka_id": focus, "academic_year": [y0, y1], "subject": SUBJECT}, 2 * len(diff))],
                  "paired_t", entity=focus, n=len(diff))
    change = tm.loc[focus, y1] - tm.loc[focus, y0]
    last = years[-K.TREND_PERSIST_YEARS:]
    persistent = bool((tm.loc[focus, last] < tm.loc[focus, y0]).all()) if change < 0 else bool((tm.loc[focus, last] > tm.loc[focus, y0]).all())
    label, key, criteria = K.trend_label(t, change, persistent, insufficient, {"t": nt, "change": ch})
    params = {"taluka": {"entity": focus}, "period": {"period": b.period("year_range", y0, y1)}, "change": {"number": ch}}
    if key != "trend.no_clear_change":
        params |= {"score_from": {"number": s0}, "score_to": {"number": s1}, "rank_from": {"number": r0}, "rank_to": {"number": r1}}
    rule = {"STRONG": "TREND-STRONG", "WEAK": "TREND-WEAK", "INSUFFICIENT": "TREND-INSUFFICIENT"}[label]
    return b.finding(id="F.trend", type="TREND", label=label, rule_id=rule, template_key=key, params=params, criteria=criteria,
                     sample={"n_schools": int(len(diff)), "n_talukas": int(tm[y1].notna().sum())})
