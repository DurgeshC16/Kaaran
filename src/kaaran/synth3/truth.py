"""Answer key for the v3 world (truth3.json): planted scenarios, expected risks, diagnoses and actions.

Only the eval harness reads this file. Expected actions follow docs/06_DECISION_RUBRICS.md.
"""

from __future__ import annotations

from . import config as C
from .world import World


def build_truth(w: World, messy: list[dict]) -> dict:
    s = w.schools
    focus = s[s["block_key"] == C.FOCUS]

    def cid(idx: int) -> str:
        return focus.loc[focus["cluster_idx"] == idx, "cluster_id"].iloc[0]

    def codes(role: str, frame=focus) -> list[str]:
        return sorted(frame.loc[frame["role"] == role, "udise_code"])

    k = {name: cid(getattr(C, name)) for name in ("SUPPORT_GAP", "STAFFING_GAP", "HONEST_LOW", "IMPROVING", "DATA_PROBLEM",
                                                    "SURPLUS", "MIGRATION", "INSUFFICIENT")}
    replication = s[(s["block_key"] == C.REPLICATION_BLOCK) & (s["cluster_idx"] == 2)]["cluster_id"].iloc[0]
    return {
        "truth_version": 3, "seed": w.seed, "names": w.names, "synthetic": True,
        "focus_block": C.FOCUS, "years": list(C.YEARS), "rounds": [r[0] for r in C.ROUNDS],
        "comparison": {"current": [C.YEARS[-1], ["ML", "EL"]], "previous": [C.YEARS[-2], ["ML", "EL"]]},
        "clusters": {role.lower(): cluster for role, cluster in k.items()},
        "scenarios": [
            {"id": "S1", "kind": "support_gap", "cluster": k["SUPPORT_GAP"], "start": C.SUPPORT_GAP_START,
             "expected_risk": True, "expected_diagnosis": ["D2", "D7"], "weak_competencies": sorted(C.SUPPORT_GAP_COMPETENCY),
             "expected_actions": ["A4", "A5", "A6"], "replication_cluster": replication},
            {"id": "S2", "kind": "staffing_gap", "cluster": k["STAFFING_GAP"], "schools": codes("staffing_gap"),
             "start": C.STAFFING_GAP_START, "expected_risk": True, "expected_diagnosis": ["D1"],
             "expected_actions": ["A1", "A3", "A12"], "surplus_schools": codes("surplus"),
             "positive_deviant": codes("positive_deviant")},
            {"id": "S3", "kind": "positive_deviant", "schools": codes("positive_deviant"), "constraint": "staffing_gap"},
            {"id": "S4", "kind": "data_problem", "cluster": k["DATA_PROBLEM"], "schools": codes("flat"),
             "months": list(C.FLAT_MONTHS), "expected_risk": True, "expected_diagnosis": ["D6"], "expected_actions": ["A10"]},
            {"id": "S5", "kind": "seasonal_migration", "cluster": k["MIGRATION"], "schools": codes("migration"),
             "expected_risk": True, "expected_diagnosis": ["D4"], "expected_actions": ["A8"]},
            {"id": "S6", "kind": "insufficient_data", "cluster": k["INSUFFICIENT"], "schools": codes("insufficient"),
             "expected_risk": False, "expected_label": "INSUFFICIENT", "expected_actions": ["A11"]},
            {"id": "S7", "kind": "honest_low_attendance", "cluster": k["HONEST_LOW"], "schools": codes("honest_low"),
             "expected_risk": False, "expected_flags": 0},
            {"id": "S8", "kind": "non_teaching_duty", "months": sorted(C.DUTY_MONTHS), "affects": "all blocks",
             "expected_diagnosis_status": {"D5": "RULED_OUT"}},
            {"id": "S9", "kind": "improving_cluster", "cluster": k["IMPROVING"], "expected_risk": False},
            {"id": "S10", "kind": "surplus_schools", "cluster": k["SURPLUS"], "schools": codes("surplus"),
             "expected_risk": False},
            {"id": "S11", "kind": "twin_block", "focus": C.FOCUS, "twin": C.TWIN, "decoy": C.DECOY},
        ],
        "at_risk_clusters": sorted([k["SUPPORT_GAP"], k["STAFFING_GAP"], k["DATA_PROBLEM"], k["MIGRATION"]]),
        "never_at_risk": sorted([k["HONEST_LOW"], k["IMPROVING"], k["SURPLUS"], k["INSUFFICIENT"]]),
        "district_noise": {"staffing_elsewhere": codes("staffing_elsewhere", s), "flat_elsewhere": codes("flat_elsewhere", s)},
        "messiness": messy,
        "known_noise": "Small schools (~10-25 pupils tested) make school-level results noisy; over 60 seeds the planted "
                       "at-risk clusters are found on ~98% of seeds and an unplanted cluster is flagged on ~3%.",
    }
