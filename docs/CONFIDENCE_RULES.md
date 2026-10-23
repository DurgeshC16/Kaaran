# Confidence Rules

Every label in an Evidence pack comes from one of the deterministic rules below. A finding cites its rule through `rule_id`.
- Thresholds are documented constants, each with its own rationale. They are never tuned to one seed and never copied from the answer key.
- Trust rules (Stage 3) are filled in below. The 2B rules (trend, cause, twin, action) get thresholds and rationale when they are implemented.

## How trust flags affect later analyses
- A trust flag applies to one (entity, metric, period).
- Downstream engines leave out only the flagged cells for that metric and period, and attach `caveat.flagged_data_excluded`.
- A taluka labelled INSUFFICIENT has its TREND and CAUSE findings capped at INSUFFICIENT.
- CLEARED schools stay in every analysis.
- Ingest fixes are not trust flags: exact duplicate removed, link made by name matching, spelling or format normalised. Only trust labels count.

## Trust rules (Stage 3, implemented in src/kaaran/trust/rules.py)
Inputs are the canonical tables built by ingest from the raw files.
- "Flagged" means a school carries a RED_FLAG or INSUFFICIENT trust label.
- "Expected months" are the attendance months present in the file for the school's taluka. The Jan-Dec 2024 PDF holds 10 school months, because Apr-May are vacation.
- "Consecutive" means calendar-consecutive months. A missing month, or the Apr-May vacation, breaks a run.

| rule_id | Gives | Rule and constants | Rationale |
|---|---|---|---|
| TRUST-FLAT-SCHOOL | school RED_FLAG | >= `FLAT_RUN_MIN_MONTHS` = 3 consecutive months with average attendance >= `FLAT_VALUE_MIN` = 99.95% (i.e. reported 100.0%) | A whole school averaging 100% for three months running is implausible; registers filled in without checking are the usual explanation |
| TRUST-FLAT-TALUKA | DATA RED_FLAG | taluka has >= `TALUKA_FLAT_MIN_SCHOOLS` = 10 flat schools and a share >= `TALUKA_FLAT_RATIO_MIN` = 3x the rest of the district | Separates a local pattern from isolated cases; a minimum count keeps small talukas from tripping it by chance |
| TRUST-JUMP-ATTENDANCE | school RED_FLAG | After subtracting the district's median for each month (removes seasonality), a month-to-month change d with abs(d) >= `JUMP_MIN_PP` = 10 pp and abs(d - median(d)) / max(1.4826 * MAD(d), `JUMP_MAD_FLOOR` = 0.5) >= `JUMP_Z_MIN` = 4, with >= `JUMP_MIN_MONTHS` = 4 months reported | Compared with the school's own history, so a naturally volatile school is not punished. Rejected alternative: a district-wide z flagged honest low-attendance schools in 3 of 8 seeds |
| TRUST-SPIKE-SCORE | school RED_FLAG | Year-over-year change delta with abs(delta) >= `SCORE_JUMP_MIN` = 20 points and abs(z) >= `SCORE_Z_MIN` = 5. z = delta / (sigma * sqrt(1/n1 + 1/n2)), where sigma is estimated from the data as median(abs(delta) / sqrt(1/n1 + 1/n2)) / 0.6745. Flagged only if the next change reverts >= `SCORE_REVERT_SHARE` = 50% | A one-year spike that reverts looks like a data error. A jump that persists is a real change: it is kept as a `trust_annotations` row (status `persisting`, or `unconfirmed` in the last year) for the cause tester, and is never a flag |
| TRUST-MISSING-SCHOOL | school INSUFFICIENT | >= `MISSING_MONTHS_MIN` = 3 missing attendance months, or >= `MISSING_YEARS_MIN` = 2 missing score years | With 3 of 10 months or 2 of 5 years missing, a school's trend and attendance cannot be judged |
| TRUST-INSUFFICIENT-TALUKA | DATA INSUFFICIENT | >= `TALUKA_INSUFFICIENT_SHARE` = 20% of the taluka's schools are INSUFFICIENT | With one school in five unusable, taluka-level comparisons are unreliable |
| TRUST-DUPLICATE-CONFLICT | school RED_FLAG | Same key (school, year, subject) reported with different values. Ingest keeps the first row and reports all of them | Exact duplicates are an ingest fix (removed and reported), not a trust flag |
| TRUST-CLEARED | DATA CLEARED | The district-wide lowest ceil(`CLEARED_SHARE` = 5% of reporting schools) by mean attendance, among schools with >= `CLEARED_MIN_MONTHS` = 7 months reported and no trust flag | Shows officers that low but natural numbers were checked and are not suspicious (protects honest teachers) |

Every missing (school, month) pair is listed in `trust_missing`, flagged or not. Rows the source file left out show up there.

### Robustness check (not tuned to one seed)
Full raw pipeline (generate -> ingest raw files -> trust) on 20 seeds: 1, 2, 3, 4, 5, 6, 8, 9, 11, 13, 17, 21, 34, 55, 89, 144, 233, 377, 610, 987. Seeds 42, 7 (fictional names) and 2026 are also covered by the test suite.

| Check | Result on every seed |
|---|---|
| T5 flat schools flagged | 53 of 53, no other school flat-flagged |
| RED_FLAG talukas | Pandharpur only |
| T6 insufficient set | equals the answer key; Mangalvedha the only INSUFFICIENT taluka; every other taluka 0% |
| T8 honest schools | 0 flagged by any rule; 15 of 15 CLEARED |
| Attendance-jump flags outside T5 schools | 0 |
| Score spikes | 0 (no spikes are planted) |
| Crosswalk gaps linked by name | all correct, none unresolved |

The sweep caught one real defect, which is fixed. Name matching first required a unique best match per short code. In seeds 1 and 2, two schools missing from the crosswalk had near-identical names (Palewadi / Palwad), so both were left unresolved and wrongly looked like schools with no attendance. Matching is now a one-to-one assignment within the taluka.

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
