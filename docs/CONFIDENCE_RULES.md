# Confidence Rules

Every label in an Evidence pack comes from one of the deterministic rules below. A finding cites its rule through `rule_id`.
- Thresholds are documented constants, each with its own rationale. They are never tuned to one seed and never copied from the answer key.
- Trust rules (Stage 3) and 2B rules (trend, cause, twin, action) fill in the thresholds and rationale when they are implemented. Until then, this file lists the rule ids so packs can cite them.

## How trust flags affect later analyses
- A trust flag applies to one (entity, metric, period).
- Downstream engines leave out only the flagged cells for that metric and period, and attach `caveat.flagged_data_excluded`.
- A taluka labelled INSUFFICIENT has its TREND and CAUSE findings capped at INSUFFICIENT.
- CLEARED schools stay in every analysis.
- Ingest fixes are not trust flags: exact duplicate removed, link made by name matching, spelling or format normalised. Only trust labels count.

## Trust rules (Stage 3)
| rule_id | Gives | Rule (thresholds added in Stage 3) |
|---|---|---|
| TRUST-FLAT-SCHOOL | school flag | Implausibly flat attendance (runs at 100%) |
| TRUST-FLAT-TALUKA | DATA RED_FLAG | Flat-attendance schools concentrated in one taluka |
| TRUST-JUMP-ATTENDANCE | school flag | Month-to-month swing far outside the school's own history |
| TRUST-SPIKE-SCORE | school flag | One-year score spike that reverts |
| TRUST-MISSING-SCHOOL | school flag | Too many missing attendance months or score years |
| TRUST-INSUFFICIENT-TALUKA | DATA INSUFFICIENT | Too many schools without usable data |
| TRUST-DUPLICATE-CONFLICT | school flag | Same key reported with different values |
| TRUST-CLEARED | DATA CLEARED | Low attendance that passes every check |

## Analysis rules (Phase 2B)
| rule_id | Gives |
|---|---|
| TREND-STRONG | TREND STRONG |
| TREND-WEAK | TREND WEAK |
| TREND-INSUFFICIENT | TREND INSUFFICIENT |
| CAUSE-SCHOOL-EXPOSURE | CAUSE STRONG (school-level exposure, e.g. maths vacancy) |
| CAUSE-ELECTION | CAUSE WEAK (similar exposed talukas did not drop) |
| CAUSE-RULED-OUT | CAUSE RULED_OUT (no link found in this data) |
| CAUSE-INSUFFICIENT | CAUSE INSUFFICIENT |
| TWIN-LEARN-FROM | TWIN LEARN_FROM |
| TWIN-NONE | TWIN INSUFFICIENT (no similar taluka did better) |
| ACTION-CATALOG | ACTION (from a fixed catalog keyed by the supporting finding) |
