"""Decision rubric engine: diagnosis + constraint checks -> actions (never chosen by an LLM).

The table lives in rubric_v1.json (reviewable data). Each action applies only when its `when` matches and every
constraint check passes; checks that fail are logged with the reason. `exclusive` actions (data problems,
insufficient data) replace cause-specific actions: fix the data before acting on its results.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .insights import BlockAnalysis, ClusterResult

RUBRIC_PATH = Path(__file__).with_name("rubric_v1.json")
CAUSE_STATUSES = ("STRONG", "WEAK")
PTR_NORM = 30.0


@dataclass
class ActionPick:
    id: str
    cluster_id: str | None
    owner: str
    horizon: str
    follow_up: str
    based_on: list
    targets: list = field(default_factory=list)
    detail: dict = field(default_factory=dict)
    funded_under: dict | None = None  # PAB line that can pay for the action (citation)


def load_rubric(path: str | Path = RUBRIC_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _diag_ok(res: ClusterResult, did: str) -> bool:
    c = res.checks.get(did)
    return c is not None and c.status in CAUSE_STATUSES


def _constraint(name: str, res: ClusterResult, an: BlockAnalysis, tables: dict) -> tuple[bool, dict]:
    if name == "surplus_school_exists":
        return bool(an.surplus), {"surplus": [s["udise_code"] for s in an.surplus]}
    if name == "no_surplus_school":
        return not an.surplus, {}
    if name == "multigrade_schools":
        d1 = res.checks.get("D1")
        if not d1:
            return False, {}
        p = tables["posts"]
        w = an.window["current"]
        s = tables["schools"].set_index("udise_code")
        cur = p[(p["academic_year"] == w)].groupby("udise_code")["working"].min()
        multigrade = [c for c in d1.schools if c in cur and c in s.index and cur[c] < (s.at[c, "highclass"] or 4)]
        return bool(multigrade), {"multigrade": multigrade}
    if name == "visits_below_one":
        d2 = res.checks.get("D2")
        v = d2.stats.get("visits_now") if d2 else None
        return v is not None and v < 1.0, {"visits_now": v}
    if name == "training_stale":
        d2 = res.checks.get("D2")
        n = d2.stats.get("training_stale", 0) if d2 else 0
        return n > 0, {"schools_training_stale": n}
    if name == "teachers_available":
        staffing = an.context["staffing"] & set(res.schools)
        y = tables["udise_year"]
        cur = y[y["academic_year"] == an.window["current"]]
        cur = cur[cur["udise_code"].isin(res.schools)]
        ptr = float(cur["enrol_total"].sum() / cur["total_tch"].sum()) if cur["total_tch"].sum() else 999.0
        return ptr <= PTR_NORM and len(staffing) < 2, {"cluster_ptr": ptr, "staffing_gap_schools": len(staffing)}
    if name == "attendance_trusted":
        return res.status != "DATA", {}
    if name == "positive_deviant_same_constraint":
        kinds = {"D1": "staffing_gap", "D2": "support_gap"}
        wanted = {kinds[d] for d in kinds if _diag_ok(res, d)}
        pds = [p for p in an.positive_deviants if p["constraint"] in wanted]
        return bool(pds), {"positive_deviants": [p["udise_code"] for p in pds]}
    raise KeyError(f"unknown constraint {name!r}")


def pick_actions(an: BlockAnalysis, tables: dict, rubric: dict | None = None) -> tuple[dict[str, list[ActionPick]], list[ActionPick], list[dict]]:
    """-> (actions per cluster, brief-level actions, log of rows that matched but failed a constraint)."""
    rubric = rubric or load_rubric()
    per_cluster, log = {}, []
    limit = rubric["limits"]["per_cluster"]
    for cid, res in an.clusters.items():
        if res.status not in ("AT_RISK", "DATA", "INSUFFICIENT"):
            continue
        picks = []
        for row in sorted(rubric["actions"], key=lambda r: r["priority"]):
            when = row["when"]
            if "cluster_status" in when:
                matched = res.status in when["cluster_status"]
                based_on = [f"cluster:{res.status}"]
            else:
                ds = [d for d in when.get("diagnosis", []) if _diag_ok(res, d)]
                matched = bool(ds) and res.status == "AT_RISK"
                based_on = ds
            if not matched:
                continue
            details, ok = {}, True
            for c in row["constraints"]:
                passed, info = _constraint(c, res, an, tables)
                details[c] = info
                if not passed:
                    ok = False
                    log.append({"cluster_id": cid, "action": row["id"], "constraint": c, "info": info})
                    break
            if not ok:
                continue
            targets = sorted({x for info in details.values() for k, v in info.items() if isinstance(v, list) for x in v})
            picks.append(ActionPick(row["id"], cid, row["owner"], row["horizon"], row["follow_up"], based_on, targets, details,
                                    row.get("funded_under")))
            if row.get("exclusive"):
                break
        per_cluster[cid] = picks[:limit]
    brief = []
    for row in rubric["brief_level"]:
        when = row["when"]
        if "duty" in when and an.duty is not None and an.duty.status in when["duty"]:
            brief.append(ActionPick(row["id"], None, row["owner"], row["horizon"], row["follow_up"], ["D5"]))
        if when.get("twin") and an.twin.get("twin"):
            brief.append(ActionPick(row["id"], None, row["owner"], row["horizon"], row["follow_up"], ["twin"],
                                    detail={"twin": an.twin["twin"]}))
    return per_cluster, brief, log
