"""Deterministic label rules for TREND, CAUSE, TWIN and ACTION findings (Phase 2B).

Every constant has its own rationale (docs/CONFIDENCE_RULES.md); none is fitted to a seed or copied from
the answer key. Each rule returns (label, template_key, criteria) so a finding can explain its label.
"""

from __future__ import annotations

# --- trend (TREND-*)
TREND_T_STRONG = -3.0  # paired school-level t; about p < 0.005, a clear change for ~100+ schools
TREND_T_WEAK = -2.0  # about p < 0.05
TREND_MIN_CHANGE = 2.0  # points; smaller taluka changes are within year-to-year noise between talukas
TREND_PERSIST_YEARS = 3  # below the starting level in each of the last 3 years = not a one-year dip

# --- causes with school-level exposure (CAUSE-SCHOOL-EXPOSURE)
EXPOSURE_T_STRONG = -3.0  # Welch t, exposed vs unexposed schools in the focus taluka
EXPOSURE_T_WEAK = -2.0
EXPOSURE_MIN_SHARE = 50.0  # % of the taluka's decline the exposed schools account for ("main" cause)
REPLICATION_T = -3.0  # the same exposure must show the same drop outside the focus taluka
REPLICATION_MIN_SCHOOLS = 3
PRE_EXPOSURE_MAX_CHANGE = 2.0  # points; exposed schools must not already be falling before exposure starts

# --- election duty (CAUSE-ELECTION)
ELECTION_HEAVY_PCT = 30.0  # policy definition: a third of teachers away ...
ELECTION_HEAVY_MONTHS = 2  # ... for at least two school months
DROP_POINTS = -1.0  # a taluka "dropped" if its yearly change is <= -1.0 point (about 2 SE of a taluka mean)
SIMILAR_NO_DROP_SHARE = 2 / 3  # most similar exposed talukas did not drop -> the excuse is weak

# --- correlational hypotheses: infrastructure, attendance (CAUSE-RULED-OUT / association)
CORR_T_NO_LINK = 2.0  # |t| below this = no link found
CORR_T_ASSOCIATED = 3.0  # |t| at or above this = association
LOWEST_INFRA_STABLE = 1.0  # points; the worst-infrastructure taluka must be stable for "ruled out"

# --- twins (TWIN-*)
TWIN_MAX_DISTANCE = 1.0  # RMS distance in taluka standard deviations across the covariates
TWIN_MIN_IMPROVEMENT = 3.0  # points over the window; larger than the taluka-level noise


def _c(cid, passed, number=None, threshold=None):
    c = {"id": cid, "passed": bool(passed)}
    if number:
        c["number"] = number
    if threshold is not None:
        c["threshold"] = threshold
    return c


def trend_label(t: float, change: float, persistent: bool, insufficient: bool, nums: dict) -> tuple[str, str, list]:
    criteria = [_c("paired_t_max", t <= TREND_T_STRONG, nums.get("t"), TREND_T_STRONG),
                _c("min_abs_change", abs(change) >= TREND_MIN_CHANGE, nums.get("change"), TREND_MIN_CHANGE),
                _c("persistent_last_years", persistent, threshold=TREND_PERSIST_YEARS)]
    if insufficient:
        return "INSUFFICIENT", "trend.no_clear_change", criteria + [_c("taluka_data_sufficient", False)]
    falling = change < 0
    if falling and t <= TREND_T_STRONG and abs(change) >= TREND_MIN_CHANGE and persistent:
        return "STRONG", "trend.decline_rank", criteria
    if not falling and t >= -TREND_T_STRONG and abs(change) >= TREND_MIN_CHANGE:
        return "STRONG", "trend.rise_rank", criteria
    if falling and t <= TREND_T_WEAK:
        return "WEAK", "trend.decline_weak", criteria
    return "WEAK", "trend.no_clear_change", criteria


def exposure_label(t: float, share: float, rep_t: float | None, pre_change: float | None, insufficient: bool,
                   nums: dict) -> tuple[str, str, list]:
    criteria = [_c("effect_t_max", t <= EXPOSURE_T_STRONG, nums.get("t"), EXPOSURE_T_STRONG),
                _c("share_of_decline_min", share >= EXPOSURE_MIN_SHARE, nums.get("share"), EXPOSURE_MIN_SHARE),
                _c("replicates_outside_focus", rep_t is not None and rep_t <= REPLICATION_T, nums.get("rep_t"), REPLICATION_T),
                _c("no_drop_before_exposure", pre_change is not None and abs(pre_change) <= PRE_EXPOSURE_MAX_CHANGE,
                   nums.get("pre"), PRE_EXPOSURE_MAX_CHANGE)]
    if insufficient:
        return "INSUFFICIENT", "cause.inconclusive", criteria
    if all(c["passed"] for c in criteria):
        return "STRONG", "cause.vacancy.concentrated", criteria
    if t <= EXPOSURE_T_WEAK:
        return "WEAK", "cause.vacancy.associated", criteria
    return "RULED_OUT", "cause.vacancy.no_link", criteria


def election_label(focus_change: float, n_comparison: int, n_no_drop: int, insufficient: bool, nums: dict) -> tuple[str, str, list]:
    dropped = focus_change <= DROP_POINTS
    share = n_no_drop / n_comparison if n_comparison else 0.0
    criteria = [_c("focus_dropped_in_exposure_year", dropped, nums.get("focus_change"), DROP_POINTS),
                _c("share_similar_no_drop_min", share >= SIMILAR_NO_DROP_SHARE, nums.get("no_drop"), round(SIMILAR_NO_DROP_SHARE, 2))]
    if insufficient or n_comparison == 0:
        return "INSUFFICIENT", "cause.inconclusive", criteria
    if not dropped:
        return "RULED_OUT", "cause.election.no_link", criteria
    if share >= SIMILAR_NO_DROP_SHARE:
        return "WEAK", "cause.election.similar_blocks_no_drop", criteria
    return "WEAK", "cause.election.associated", criteria  # taluka-level n is too small for STRONG


def correlation_label(hypothesis: str, t: float, stable_check: bool | None, insufficient: bool, nums: dict) -> tuple[str, str, list]:
    key = {"infrastructure": "infra", "attendance": "attendance"}[hypothesis]
    criteria = [_c("abs_t_max_no_link", abs(t) < CORR_T_NO_LINK, nums.get("r"), CORR_T_NO_LINK)]
    if stable_check is not None:
        criteria.append(_c("lowest_infra_taluka_stable", stable_check, nums.get("lowest_change"), LOWEST_INFRA_STABLE))
    if insufficient:
        return "INSUFFICIENT", "cause.inconclusive", criteria
    if abs(t) < CORR_T_NO_LINK and (stable_check is None or stable_check):
        return "RULED_OUT", f"cause.{key}.no_link", criteria
    if abs(t) >= CORR_T_ASSOCIATED:
        return "WEAK", f"cause.{key}.associated", criteria
    return "INSUFFICIENT", "cause.inconclusive", criteria
