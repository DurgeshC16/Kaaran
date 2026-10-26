"""Block evidence pack (schema block-1.0): the contract between the block-lens engines and the language layer.

Same building blocks as the v1 pack (numbers with provenance and display strings, entities, sets, periods,
findings with params, outline), so the existing filler, writer and verifier work unchanged. The outline has
three parts (attention / why / action) plus an appendix, decided by written rules below, never by an LLM.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pandas as pd

from .. import evidence as E
from ..brief import texts as X  # noqa: F401  (registers block wording)
from ..brief.texts_block import ACTION_TEMPLATE
from ..synth.config import NAME_SETS
from .ingest import BlockIngest, ingest_block
from .insights import ATT_LOW, BlockAnalysis, ClusterResult, analyze_block
from .rubric import ActionPick, load_rubric, pick_actions
from .trust import BlockTrust, run_block_trust

SCHEMA = "block-1.0"
MARKER = "SYNTHETIC DEMO DATA - NOT REAL"
BRIEF_ACTIONS_PER_CLUSTER = 2
CAUSE_ORDER = ("D1", "D2", "D4", "D3")
CAUSE_TEMPLATE = {"D1": "diag.staffing", "D2": "diag.support", "D3": "diag.absence", "D4": "diag.migration"}
HYPOTHESIS = {"D1": "staffing", "D2": "support", "D3": "absence", "D4": "migration", "D5": "duty", "D7": "competency",
              "D8": "unexplained"}
FINDING_TYPES = ("RISK", "CAUSE", "DATA", "TWIN", "ACTION")
LABELS = ("STRONG", "WEAK", "INSUFFICIENT", "RED_FLAG", "RULED_OUT", "LEARN_FROM", "CLEARED", "ACTION")


def _mr_block_name(name: str) -> str | None:
    for names in NAME_SETS.values():
        for en, _variants, mr in names.values():
            if en.lower() == name.lower():
                return mr
    return None


class PackBuilder:
    def __init__(self, ing: BlockIngest):
        self.ing = ing
        self.sources = [{k: s[k] for k in ("id", "file", "kind", "sha256", "synthetic")} for s in ing.report["sources"]]
        self.file_id = {s["file"]: s["id"] for s in self.sources}
        self.numbers, self.entities, self.sets, self.periods, self.findings = {}, {}, {}, {}, []

    # ---- registries ----
    def prov(self, view: str, where: dict, rows: pd.DataFrame) -> list[dict]:
        if rows is None or rows.empty or "src_file" not in rows:
            return [{"kind": "constant", "rule_id": view, "name": str(where)}]
        out = []
        for f, g in rows.groupby("src_file"):
            out.append({"kind": "query", "source": self.file_id.get(f, "S?"), "view": view, "where": where, "n_rows": int(len(g))})
        return out

    def number(self, nid: str, value: float, unit: str, decimals: int, prov: list[dict], op: str, **extra) -> dict:
        n = {"value": round(float(value), 4), "unit": unit, "decimals": decimals, "provenance": prov,
             "derivation": {"op": op, "inputs": extra.pop("inputs", [])}, **extra}
        n["display"] = E.format_number(n["value"], unit, decimals)
        if unit in E.CHANGE_UNITS:
            n["direction"] = "down" if value < 0 else "up" if value > 0 else "flat"
        self.numbers[nid] = n
        return {"number": nid}

    def school_set(self, sid: str, rule_id: str, codes) -> dict:
        codes = sorted(set(codes))
        for c in codes:
            self.school(c)
        self.sets[sid] = {"kind": "school", "rule_id": rule_id, "members": [f"S{c}" for c in codes]}
        return {"set": sid}

    def school(self, code: str) -> str:
        eid = f"S{code}"
        if eid not in self.entities:
            s = self.ing.tables["schools"].set_index("udise_code").loc[code]
            self.entities[eid] = {"kind": "school", "code": code, "name_en": s["school_name"], "cluster": f"C{s['cluster_id']}"}
        return eid

    def cluster(self, cid: str) -> dict:
        eid = f"C{cid}"
        if eid not in self.entities:
            row = self.ing.tables["clusters"].set_index("cluster_id").loc[cid]
            village = str(row["cluster_name"]).replace(" Kendra", "")
            self.entities[eid] = {"kind": "cluster", "code": cid, "name_en": f"{village} Kendra", "name_mr": village}  # Marathi templates add केंद्रातील/केंद्रात/केंद्राचा
        return {"entity": eid}

    def block(self, name: str) -> dict:
        eid = "B" + "".join(ch for ch in name.title() if ch.isalnum())
        if eid not in self.entities:
            self.entities[eid] = {"kind": "block", "name_en": name, "name_mr": _mr_block_name(name)}
        return {"entity": eid}

    def period(self, pid: str, kind: str, frm: str, to: str) -> dict:
        self.periods[pid] = {"kind": kind, "from": frm, "to": to}
        return {"period": pid}

    def finding(self, **f) -> dict:
        f.setdefault("caveats", [])
        f.setdefault("criteria", [])
        f.setdefault("related", [])
        if MARKER and self.ing.report.get("synthetic") and f["type"] != "ACTION":
            f["caveats"].insert(0, {"template_key": "caveat.synthetic_data", "params": {}})
        self.findings.append(f)
        return f


def _assess_rows(tables, codes, years, rounds, subject=None):
    a = tables["assessment"]
    a = a[a["udise_code"].isin(codes) & a["academic_year"].isin(years) & a["round"].isin(rounds)]
    if subject in ("maths", "language"):
        a = a[a["competency"].str.startswith("M" if subject == "maths" else "L")]
    return a


def build_block_pack(raw_dir: str | Path, focus_block: str | None = None, ing: BlockIngest | None = None,
                     trust: BlockTrust | None = None) -> dict:
    ing = ing or ingest_block(raw_dir)
    trust = trust or run_block_trust(ing.tables)
    blocks = sorted(ing.tables["schools"]["block"].unique())
    focus = focus_block or blocks[0]
    an = analyze_block(ing.tables, trust, focus)
    per_cluster, brief_actions, rubric_log = pick_actions(an, ing.tables)
    return _assemble(ing, trust, an, per_cluster, brief_actions, rubric_log)


def _assemble(ing: BlockIngest, trust: BlockTrust, an: BlockAnalysis, per_cluster: dict, brief_actions: list,
              rubric_log: list) -> dict:
    t = ing.tables
    w = an.window
    b = PackBuilder(ing)
    years, rounds = [w["previous"], w["current"]], w["rounds"]
    focus_ref = b.block(an.focus_block)
    p_cmp = b.period("p.cmp", "year_range", w["previous"], w["current"])
    p_cur = b.period("p.cur", "academic_year", w["current"], w["current"])
    order = sorted(an.clusters.values(), key=lambda r: (-r.weight, r.cluster_id))
    attention, why, action, appendix = [], [], [], []

    def cid_short(cid):
        return cid.replace("-", "")

    # ---------- A: what needs attention ----------
    for r in [r for r in order if r.status == "AT_RISK"]:
        c = b.cluster(r.cluster_id)
        cs = cid_short(r.cluster_id)
        sch = b.school_set(f"set.cluster.{cs}", "CLUSTER", r.schools)
        fid = f"F.risk.{cs}"
        crit = [{"id": k, "weight": v} for k, v in ((k, {"DROP": 3, "LEVEL": 2, "ATTENDANCE": 3, "COMPETENCY": 1}[k]) for k in r.risk)]
        drop_ = r.risk.get("DROP", {})
        label = "STRONG" if r.weight >= 4 or (drop_ and (drop_["t"] <= -3 or drop_["droppers"] >= 4)) else "WEAK"
        if "DROP" in r.risk:
            d = r.risk["DROP"]
            rows = _assess_rows(t, r.schools, years, rounds, d["subject"])
            drop = b.number(f"n.drop.{cs}", d["mean"], "pct_point_change", 1, b.prov("assessment", {
                "cluster_id": r.cluster_id, "academic_year": years, "round": rounds, "subject": d["subject"]}, rows), "mean_rel_change")
            params = {"cluster": c, "schools": sch, "subject": {"text_key": f"subject.{d['subject']}"}, "drop": drop, "period": p_cmp}
            key = "risk.cluster_drop"
            if d["route"] == "pocket":
                o = an.changes[(an.changes["subject"] == "overall") & an.changes["udise_code"].isin(r.schools)]
                params["pocket"] = b.school_set(f"set.pocket.{cs}", "RISK-POCKET", o.loc[o["rel"] <= -10, "udise_code"])
                key = "risk.cluster_pocket"
        elif "ATTENDANCE" in r.risk:
            last = an.context["low_att_months"]
            att = t["attendance"]
            lows = att[att["udise_code"].isin(r.schools) & att["month"].isin(last) & (att["attendance_pct"] < ATT_LOW)]
            low_codes = lows.groupby("udise_code").size()
            params = {"cluster": c, "low": b.school_set(f"set.lowatt.{cs}", "RISK-ATTENDANCE", low_codes[low_codes >= 2].index),
                      "threshold": b.number("n.const.att_low", ATT_LOW, "pct", 0, [{"kind": "constant", "rule_id": "RISK-ATTENDANCE", "name": "ATT_LOW"}], "constant"),
                      "period": b.period(f"p.att.{cs}", "month_range", last[0], last[-1])}
            key = "risk.cluster_absence"
        else:
            lv = r.risk["LEVEL"]
            rows = _assess_rows(t, r.schools, [w["current"]], rounds)
            params = {"cluster": c,
                      "level": b.number(f"n.level.{cs}", lv["level"], "pct", 1, b.prov("assessment", {"cluster_id": r.cluster_id, "academic_year": w["current"], "round": rounds}, rows), "mean"),
                      "block_level": b.number(f"n.level.block.{cs}", lv["block_median"], "pct", 1, [{"kind": "constant", "rule_id": "RISK-LEVEL", "name": "median of the block's cluster levels"}], "median")}
            key = "risk.cluster_level"
        attention.append(b.finding(id=fid, type="RISK", label=label, rule_id="RISK-SCAN", template_key=key, params=params,
                                   criteria=crit)["id"])
    for r in [r for r in order if r.status == "DATA"]:
        cs = cid_short(r.cluster_id)
        flags = trust.school_flags[(trust.school_flags["rule"] == "TRUST-FLAT") & trust.school_flags["udise_code"].isin(r.schools)]
        months = sorted({m for ms in flags["months"] for m in ms})
        attention.append(b.finding(
            id=f"F.data.flat.{cs}", type="DATA", label="RED_FLAG", rule_id="TRUST-CLUSTER-FLAG", template_key="data.cluster_flat",
            params={"cluster": b.cluster(r.cluster_id), "flagged": b.school_set(f"set.flagged.{cs}", "TRUST-FLAT", flags["udise_code"]),
                    "period": b.period(f"p.flat.{cs}", "month_range", months[0], months[-1])})["id"])
    for r in [r for r in order if r.status == "INSUFFICIENT"]:
        cs = cid_short(r.cluster_id)
        miss = trust.school_flags[(trust.school_flags["label"] == "INSUFFICIENT") & trust.school_flags["udise_code"].isin(r.schools)]
        attention.append(b.finding(
            id=f"F.data.insufficient.{cs}", type="DATA", label="INSUFFICIENT", rule_id="TRUST-CLUSTER-INSUFFICIENT",
            template_key="data.cluster_insufficient",
            params={"cluster": b.cluster(r.cluster_id), "missing": b.school_set(f"set.missing.{cs}", "TRUST-MISSING", miss["udise_code"])})["id"])

    # ---------- B: why it may be happening ----------
    pd_by_cluster = {}
    for p in an.positive_deviants:
        pd_by_cluster.setdefault(p["cluster_id"], []).append(p)
    comp_fallback = {}
    for r in [r for r in order if r.status == "AT_RISK"]:
        cs = cid_short(r.cluster_id)
        c = b.cluster(r.cluster_id)
        causes = [d for d in CAUSE_ORDER if d in r.checks and r.checks[d].status in ("STRONG", "WEAK")]
        causes.sort(key=lambda d: (r.checks[d].status != "STRONG", CAUSE_ORDER.index(d)))
        for d in causes[:1]:
            why.append(_cause_finding(b, an, r, d, c, cs, p_cur, years, rounds)["id"])
        for d in causes[1:]:
            appendix.append(_cause_finding(b, an, r, d, c, cs, p_cur, years, rounds)["id"])
        if "D8" in r.checks:
            why.append(b.finding(id=f"F.diag.{cs}.D8", type="CAUSE", label="WEAK", hypothesis="unexplained", rule_id="DIAG-D8",
                                 template_key="diag.no_clear_pattern", params={"cluster": c})["id"])
        comps = r.competencies or _weakest(t, an, r)
        comp_fallback[r.cluster_id] = comps
        if r.competencies:
            why.append(_competency_finding(b, t, an, r, c, cs, rounds)["id"])
        for d in ("D1", "D2", "D3"):
            if d in r.checks and r.checks[d].status == "RULED_OUT":
                appendix.append(_cause_finding(b, an, r, d, c, cs, p_cur, years, rounds)["id"])
        for p in pd_by_cluster.get(r.cluster_id, []):
            pcode = p["udise_code"]
            why.append(b.finding(
                id=f"F.learn.{pcode}", type="TWIN", label="LEARN_FROM", rule_id="POSITIVE-DEVIANCE", template_key="learn.positive_deviant",
                params={"cluster": c, "pd": b.school_set(f"set.pd.{pcode}", "POSITIVE-DEVIANCE", [pcode]),
                        "constraint": {"text_key": f"constraint.{p['constraint']}"},
                        "gain": b.number(f"n.pd.{pcode}", p["rel"], "pct_point_change", 1,
                                         b.prov("assessment", {"udise_code": pcode, "academic_year": years, "round": rounds},
                                                _assess_rows(t, [pcode], years, rounds)), "rel_change")})["id"])
    if an.duty is not None:
        st = an.duty.stats
        posts = t["posts"][t["posts"]["month"].isin(st["months"])]
        why.append(b.finding(
            id="F.diag.duty", type="CAUSE", label=an.duty.status, hypothesis="duty", rule_id="DIAG-D5",
            template_key="diag.duty_ruled_out" if an.duty.status == "RULED_OUT" else "diag.duty_associated",
            criteria=an.duty.criteria,
            params={"period": b.period("p.duty", "month_range", st["months"][0], st["months"][-1]),
                    "days": b.number("n.duty.days", st["duty_days"], "index", 1, b.prov("posts", {"month": st["months"]}, posts), "mean"),
                    "n": b.number("n.duty.clusters", st["n_clusters"], "count", 0, [{"kind": "constant", "rule_id": "DIAG-D5", "name": "clusters compared"}], "count", of="schools"),
                    "no_drop": b.number("n.duty.no_drop", st["n_no_drop"], "count", 0, [{"kind": "constant", "rule_id": "DIAG-D5", "name": "clusters without a drop"}], "count")})["id"])
    tw = an.twin
    if tw.get("twin"):
        o = an.changes[an.changes["subject"] == "overall"]
        params = {"twin": b.block(tw["twin"]), "focus": focus_ref,
                  "twin_change": b.number("n.twin.change", tw["block_change"][tw["twin"]], "pct_point_change", 1,
                                          b.prov("assessment", {"block": tw["twin"], "academic_year": years, "round": rounds},
                                                 _assess_rows(t, o.loc[o["block"] == tw["twin"], "udise_code"], years, rounds)), "mean_change"),
                  "focus_change": b.number("n.focus.change", tw["focus_change"], "pct_point_change", 1,
                                           b.prov("assessment", {"block": an.focus_block, "academic_year": years, "round": rounds},
                                                  _assess_rows(t, o.loc[o["block"] == an.focus_block, "udise_code"], years, rounds)), "mean_change")}
        if tw.get("decoy"):
            params["decoy"] = b.block(tw["decoy"])
        why.append(b.finding(id="F.twin", type="TWIN", label="LEARN_FROM", rule_id="TWIN-BLOCK",
                             template_key="twin.block" if tw.get("decoy") else "twin.block", params=params)["id"])

    # ---------- C: what to do ----------
    rubric = load_rubric()
    for r in sorted(an.clusters.values(), key=lambda r: ({"AT_RISK": 0, "DATA": 1, "INSUFFICIENT": 2}.get(r.status, 3), -r.weight, r.cluster_id)):
        picks = per_cluster.get(r.cluster_id, [])
        for i, pk in enumerate(picks):
            f = _action_finding(b, t, an, r, pk, comp_fallback.get(r.cluster_id, []), rubric)
            (action if i < BRIEF_ACTIONS_PER_CLUSTER else appendix).append(f["id"])
    for pk in brief_actions:
        f = _action_finding(b, t, an, None, pk, [], rubric)
        action.append(f["id"])

    # ---------- appendix: cleared ----------
    fs_codes = set(t["schools"].loc[t["schools"]["block"] == an.focus_block, "udise_code"])
    cleared = sorted(set(trust.cleared["udise_code"]) & fs_codes)
    if cleared:
        appendix.append(b.finding(id="F.data.cleared", type="DATA", label="CLEARED", rule_id="TRUST-CLEARED",
                                  template_key="data.cleared_block",
                                  params={"schools": b.school_set("set.cleared", "TRUST-CLEARED", cleared)})["id"])

    district = "D" + str(t["schools"]["udise_code"].iloc[0])[2:4]
    b.entities[district] = {"kind": "district", "code": district[1:], "name_en": "SYNTHETIC DEMO DISTRICT" if ing.report["synthetic"] else "District"}
    pack = {
        "schema_version": SCHEMA, "synthetic": bool(ing.report["synthetic"]), "marker": MARKER if ing.report["synthetic"] else "",
        "rubric_version": rubric["rubric_version"],
        "scope": {"district": district, "focus": focus_ref["entity"], "level": "block", "period": "p.cmp",
                  "comparison": w, "question": "question.block_attention"},
        "sources": b.sources, "entities": b.entities, "entity_sets": b.sets, "periods": b.periods, "numbers": b.numbers,
        "findings": b.findings,
        "outline": [{"section": s, "finding_ids": ids} for s, ids in
                    (("attention", attention), ("why", why), ("action", action), ("appendix", appendix)) if ids],
        "actions_by_cluster": {cid: [p.id for p in picks] for cid, picks in per_cluster.items()},
        "rubric_log": rubric_log,
        "summary": {cid: {"status": r.status, "weight": r.weight, "risk": list(r.risk),
                          "checks": {k: v.status for k, v in r.checks.items()}} for cid, r in an.clusters.items()},
    }
    problems = validate_block_pack(pack)
    if problems:
        raise ValueError(f"invalid block pack: {problems[:5]}")
    return pack


def _cause_finding(b, an, r: ClusterResult, d: str, c, cs, p_cur, years, rounds) -> dict:
    t = b.ing.tables
    chk = r.checks[d]
    subject = "maths" if d == "D2" else "overall"
    codes = chk.schools or r.schools
    rows = _assess_rows(t, codes, years, rounds, subject)
    params = {"cluster": c}
    diff_val = chk.stats.get("exposed_mean")
    if d in ("D1", "D3"):
        params["exposed"] = b.school_set(f"set.exposed.{cs}.{d}", f"DIAG-{d}", codes)
        params["diff"] = b.number(f"n.diff.{cs}.{d}", diff_val, "pct_point_change", 1, b.prov("assessment", {
            "udise_code": "exposed set", "academic_year": years, "round": rounds}, rows), "mean_rel_change")
        if d == "D1":
            params["period"] = p_cur
    elif d == "D2":
        visits = t["visits"]
        v = visits[visits["udise_code"].isin(codes)]
        params["before"] = b.number(f"n.visits.before.{cs}", chk.stats["visits_before"], "index", 1, b.prov("visits", {
            "udise_code": "cluster schools", "academic_year": an.window["previous"], "visitor_role": "Kendra Pramukh"}, v), "rate")
        params["now"] = b.number(f"n.visits.now.{cs}", chk.stats["visits_now"], "index", 1, b.prov("visits", {
            "udise_code": "cluster schools", "academic_year": an.window["current"], "visitor_role": "Kendra Pramukh"}, v), "rate")
        params["diff"] = b.number(f"n.diff.{cs}.{d}", diff_val, "pct_point_change", 1, b.prov("assessment", {
            "cluster_id": r.cluster_id, "academic_year": years, "round": rounds, "subject": "maths"}, rows), "mean_rel_change")
    elif d == "D4":
        att = t["attendance"]
        params["mig"] = b.school_set(f"set.mig.{cs}", "DIAG-D4", codes)
        params["gap"] = b.number(f"n.mig.gap.{cs}", chk.stats["winter_gap"], "pct_point_change", 1, b.prov("attendance", {
            "udise_code": "migration set", "months": "Nov-Mar vs Jun-Oct"}, att[att["udise_code"].isin(codes)]), "seasonal_gap")
    caveats = [{"template_key": "caveat.associated_not_caused", "params": {}}] if chk.status == "WEAK" else []
    if d == "D1" and an.positive_deviants:
        caveats.append({"template_key": "caveat.positive_deviants_separate", "params": {}})
    key = CAUSE_TEMPLATE[d]
    return b.finding(id=f"F.diag.{cs}.{d}", type="CAUSE", label=chk.status, hypothesis=HYPOTHESIS[d], rule_id=f"DIAG-{d}",
                     template_key=key, params=params, criteria=[{**x, "number": None} for x in chk.criteria], caveats=caveats)


def _competency_finding(b, t, an, r, c, cs, rounds) -> dict:
    comps = r.competencies[:2]
    params = {"cluster": c}
    for slot, comp in zip(("compa", "compb"), comps):
        code = comp["competency"]
        rows = _assess_rows(t, r.schools, [an.window["current"]], rounds)
        rows = rows[rows["competency"] == code]
        params[slot] = {"text_key": f"comp.{code}"}
        params[f"{slot}_level"] = b.number(f"n.comp.{cs}.{code}", comp["level"], "pct", 1, b.prov("assessment", {
            "cluster_id": r.cluster_id, "competency": code, "academic_year": an.window["current"], "round": rounds}, rows), "mean")
        params[f"{slot}_block"] = b.number(f"n.comp.block.{code}", comp["block_level"], "pct", 1, [{
            "kind": "constant", "rule_id": "DIAG-D7", "name": f"block mean of {code}"}], "mean")
    key = "diag.competency2" if len(comps) == 2 else "diag.competency"
    return b.finding(id=f"F.diag.{cs}.D7", type="CAUSE", label=r.checks["D7"].status, hypothesis="competency", rule_id="DIAG-D7",
                     template_key=key, params=params)


def _weakest(t, an, r) -> list:
    """Descriptive fallback for action wording: the cluster's lowest maths competency relative to the block."""
    w = an.window
    a = t["assessment"]
    a = a[(a["academic_year"] == w["current"]) & a["round"].isin(w["rounds"]) & a["competency"].str.startswith("M")]
    block_codes = set(t["schools"].loc[t["schools"]["block"] == an.focus_block, "udise_code"])
    blockmean = a[a["udise_code"].isin(block_codes)].groupby("competency")["pct"].mean()
    clmean = a[a["udise_code"].isin(r.schools)].groupby("competency")["pct"].mean()
    rel = (clmean - blockmean).sort_values()
    return [{"competency": k, "level": float(clmean[k]), "block_level": float(blockmean[k])} for k in rel.index[:1]]


def _action_finding(b, t, an, r: ClusterResult | None, pk: ActionPick, comps: list, rubric: dict) -> dict:
    key = ACTION_TEMPLATE[pk.id]
    params = {}
    cs = (r.cluster_id if r else "brief").replace("-", "")
    if r is not None:
        params["cluster"] = b.cluster(r.cluster_id)
    if pk.id == "A1":
        params["surplus"] = b.school_set("set.surplus", "RUBRIC-A1", [s["udise_code"] for s in an.surplus])
    if pk.id == "A2":
        params["gap"] = b.school_set(f"set.exposed.{cs}.D1", "DIAG-D1", r.checks["D1"].schools)
    if pk.id == "A3":
        params["multi"] = b.school_set(f"set.multigrade.{cs}", "RUBRIC-A3", pk.detail["multigrade_schools"]["multigrade"])
    if pk.id in ("A4", "A5"):
        comp = comps[0]["competency"] if comps else "M2"
        params["compa"] = {"text_key": f"comp.{comp}"}
        if pk.id == "A4":
            params["schools"] = b.school_set(f"set.cluster.{cs}", "CLUSTER", r.schools)
        else:
            last = an.context["last_training"].reindex(r.schools).dropna()
            month = str(last.max())[:7] if len(last) else an.window["previous"][:4] + "-08"
            params["last"] = b.period(f"p.training.{cs}", "month", month, month)
    if pk.id == "A7":
        params["exposed"] = b.school_set(f"set.exposed.{cs}.D3", "DIAG-D3", r.checks["D3"].schools)
    if pk.id == "A8":
        params["mig"] = b.school_set(f"set.mig.{cs}", "DIAG-D4", r.checks["D4"].schools)
    if pk.id == "A10":
        params["flagged"] = {"set": f"set.flagged.{cs}"}
    if pk.id == "A11":
        params["missing"] = {"set": f"set.missing.{cs}"}
    if pk.id == "A12":
        pds = pk.detail["positive_deviant_same_constraint"]["positive_deviants"]
        params["pd"] = b.school_set(f"set.pd.{pds[0]}", "POSITIVE-DEVIANCE", pds[:1])
    if pk.id == "A13":
        params["twin"] = b.block(pk.detail["twin"])
    targets = [m for ref in params.values() if "set" in ref for m in b.sets.get(ref["set"], {}).get("members", [])]
    return b.finding(id=f"F.action.{cs}.{pk.id}", type="ACTION", label="ACTION", rule_id=f"RUBRIC-{pk.id}", template_key=key,
                     params=params, action={"actor_role": pk.owner, "horizon": pk.horizon, "based_on": pk.based_on,
                                            "follow_up": pk.follow_up, "rubric_id": pk.id, "targets": targets,
                                            "within_officer_powers": True})


def validate_block_pack(pack: dict) -> list[str]:
    p = []
    reg = {"number": pack["numbers"], "entity": pack["entities"], "set": pack["entity_sets"], "period": pack["periods"]}
    for nid, n in pack["numbers"].items():
        if not n.get("provenance"):
            p.append(f"{nid}: no provenance")
        if "display" not in n:
            p.append(f"{nid}: no display")
    ids = set()
    for f in pack["findings"]:
        if f["id"] in ids:
            p.append(f"duplicate finding {f['id']}")
        ids.add(f["id"])
        if f["type"] not in FINDING_TYPES or f["label"] not in LABELS:
            p.append(f"{f['id']}: bad type/label")
        if f["template_key"] not in X.TEMPLATES:
            p.append(f"{f['id']}: unknown template {f['template_key']}")
        params = dict(f["params"])
        for c in f.get("caveats", []):
            params.update(c.get("params", {}))
        for name, ref in params.items():
            kind, value = next(iter(ref.items()))
            if kind == "text_key":
                if value not in X.TEXT_KEYS:
                    p.append(f"{f['id']}: unknown text key {value}")
            elif value not in reg[kind]:
                p.append(f"{f['id']}: {name} -> unknown {kind} {value}")
    for o in pack["outline"]:
        for fid in o["finding_ids"]:
            if fid not in ids:
                p.append(f"outline: unknown finding {fid}")
    return p


def strip_internal(pack: dict) -> dict:
    out = copy.deepcopy(pack)
    for k in ("rubric_log", "summary"):
        out.pop(k, None)
    return out
