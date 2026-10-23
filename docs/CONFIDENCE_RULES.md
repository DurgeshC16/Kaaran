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

## Analysis rules (Phase 2B, implemented in src/kaaran/confidence.py)
Inputs: canonical tables after trust exclusions (flagged score/attendance cells removed). Talukas marked INSUFFICIENT get INSUFFICIENT findings.

The scores metric is the unweighted mean of school means. Changes run from the first to the last year in the file.

**Trend**

| rule_id | Gives | Rule and constants | Rationale |
|---|---|---|---|
| TREND-STRONG | TREND STRONG (`trend.decline_rank` / `trend.rise_rank`) | School-level paired t <= `TREND_T_STRONG` = -3, abs(change) >= `TREND_MIN_CHANGE` = 2 points, and below (above) the starting level in each of the last `TREND_PERSIST_YEARS` = 3 years | t <= -3 is about p < 0.005 for ~100+ schools. 2 points is about one between-taluka SD. Persistence separates a decline from a one-year dip ("holds across years") |
| TREND-WEAK | TREND WEAK (`trend.decline_weak` or `trend.no_clear_change`) | Paired t <= `TREND_T_WEAK` = -2 without the other criteria, or no clear change | A pattern that does not meet the STRONG bar |
| TREND-INSUFFICIENT | TREND INSUFFICIENT | The taluka is INSUFFICIENT in trust | Too much data missing to judge |

**Causes**

| rule_id | Gives | Rule and constants | Rationale |
|---|---|---|---|
| CAUSE-SCHOOL-EXPOSURE | CAUSE STRONG (`cause.vacancy.concentrated`), else WEAK (`cause.vacancy.associated`) | Exposure = a school reported 0 working maths teachers from some year after the first. STRONG needs all four: (1) Welch t of first-to-last change, exposed vs unexposed in the focus taluka, <= `EXPOSURE_T_STRONG` = -3; (2) the exposed schools account for >= `EXPOSURE_MIN_SHARE` = 50% of the taluka's decline; (3) the same comparison outside the focus taluka (>= 3 exposed schools) gives t <= `REPLICATION_T` = -3; (4) before exposure the exposed schools changed by no more than `PRE_EXPOSURE_MAX_CHANGE` = 2 points. WEAK if only t <= -2 | The documented STRONG criteria: effect, size ("main" cause), replication elsewhere and timing. This is the only case where causal wording is allowed |
| CAUSE-ELECTION | CAUSE WEAK (`cause.election.similar_blocks_no_drop`, or `cause.election.associated`) | Exposure = >= `ELECTION_HEAVY_PCT` = 30% of teachers deployed in >= `ELECTION_HEAVY_MONTHS` = 2 months of a year. The focus taluka "dropped" if its change into the exposure year is <= `DROP_POINTS` = -1.0. If it dropped and >= `SIMILAR_NO_DROP_SHARE` = 2/3 of the other exposed talukas did not, the result is "similar blocks with the same duty did not drop" | -1.0 is about 2 standard errors of a taluka mean. Exposure is at taluka level with about 7 units, so this is never STRONG |
| CAUSE-CORRELATION | CAUSE WEAK (`cause.infra.associated` / `cause.attendance.associated`) | abs(t) of the correlation >= `CORR_T_ASSOCIATED` = 3 | Association only, never causal |
| CAUSE-RULED-OUT | CAUSE RULED_OUT (`*.no_link`) | Correlation abs(t) < `CORR_T_NO_LINK` = 2. For infrastructure, the worst-infrastructure taluka must also have changed by no more than `LOWEST_INFRA_STABLE` = 1 point. Election: the focus taluka did not drop. Vacancy: t > -2 | Officers read it as "no link found in this data" |
| CAUSE-INSUFFICIENT | CAUSE INSUFFICIENT (`cause.inconclusive`) | Between the no-link and association bars, a failed stability check, fewer than 10 schools, or an INSUFFICIENT taluka | Honest "cannot tell" |

**Correlational hypotheses**
- Infrastructure index (pre-registered): the mean of the district-standardised toilets, library (1/0), drinking water (1/0) and classrooms per enrolled pupil, correlated with each school's score change.
- Attendance: the school's mean attendance in the school year the attendance file mostly covers, with flagged months excluded, correlated with the score change into that year.
- Both are tested on schools **not exposed to a STRONG school-level cause**, so the main cause's large drops cannot create or hide a secondary correlation.
  - Without this rule, seed 42 showed a chance attendance correlation of t = -3.2; it is -2.5 without the 11 vacancy schools, which gives "inconclusive".
  - Infrastructure stays below abs(t) = 1.7 on 10 seeds either way.

**Twins**

| rule_id | Gives | Rule and constants | Rationale |
|---|---|---|---|
| TWIN-LEARN-FROM | TWIN LEARN_FROM (`twin.learn_from`) | Candidates: talukas with the same heavy election-duty years as the focus taluka, not INSUFFICIENT. Covariates: school count, mean enrolment, poverty index, each standardised across the district's talukas. Similar = RMS z-distance <= `TWIN_MAX_DISTANCE` = 1.0. The twin is the most similar candidate that improved by >= `TWIN_MIN_IMPROVEMENT` = 3 points over the window. The most similar candidate that did not improve is reported as the decoy | Within one SD on average means "comparable block". 3 points is above the between-taluka year-to-year noise. Reporting the decoy shows the choice was made on outcome, not on similarity alone (positive deviance) |
| TWIN-NONE | TWIN INSUFFICIENT (`twin.none_found`) | No similar taluka improved | Nothing to learn from |

Without a poverty source, the covariate is dropped and the finding carries `caveat.poverty_not_available`.

**Actions**

| rule_id | Gives | Catalog (supporting finding -> action, actor) |
|---|---|---|
| ACTION-CATALOG | ACTION | STRONG vacancy cause -> `action.redeploy_teachers` to the exposed schools (DEO, this month). TWIN LEARN_FROM -> `action.exposure_visit` to the twin (BEO, this month). Focus taluka flat-attendance RED_FLAG -> `action.verify_registers` in the flagged schools (Kendra Pramukh, this week). Focus taluka INSUFFICIENT -> `action.collect_missing_data` (BEO). Every action is within the named officer's powers; the officer confirms before it is forwarded |

**Brief outline (src/kaaran/analyze.py)**
- trend: the TREND finding
- election_check: the election CAUSE
- main_cause: the best other CAUSE with label STRONG or WEAK (STRONG first)
- twin: the TWIN finding
- data_warning: DATA findings about the focus taluka
- action: the ACTION findings
- appendix: everything else (other hypotheses, district-wide DATA findings)

Only the focus taluka's CLEARED list is kept in a pack.

## Eval scorecard (src/kaaran/eval)
`python -m kaaran.eval --seed 42` runs the whole pipeline on the raw files and scores it against ground_truth.json. It reports:
- truths recovered (x/8)
- wrong verdicts
- false flags (flagged schools outside the planted T5/T6 sets; any T8 school flagged)
- invented numbers (no provenance and no derivation)
- provenance mismatches: each query provenance is re-run on the canonical tables; its row count, and for means, counts and ranks also its value, must match

Result on 2026-10-24 for seeds 42, 7 (fictional names), 2026, 1 and 99: 8/8 on every seed, with 0 false flags, 0 invented numbers and 0 provenance mismatches.

## Brief wording rules (Phase 3, src/kaaran/brief/verify.py)
Every brief sentence goes through a deterministic verifier before it ships, whether the LLM or a template wrote it. A sentence that fails gets one retry with the problem codes; if it fails again, the template sentence is used.

| Code | Rule |
|---|---|
| PLACEHOLDER_UNKNOWN / PLACEHOLDER_NOT_ALLOWED | Every `{{n:}}` `{{e:}}` `{{s:}}` `{{p:}}` placeholder exists in the evidence pack and belongs to that finding (its params, caveats, criteria) |
| DIGIT | No digits, Latin or Devanagari, outside placeholders: every figure is filled in by code |
| SPELLED_NUMBER | No figures written as words (English two-ninety, hundred, thousand, lakh, crore; Marathi दोन-वीस, शंभर, हजार, लाख, कोटी) |
| CAUSAL_WORDING | Causal words ("because of", "due to", "caused", "led to", "-मुळे", "कारणीभूत", "परिणामी", "कारण आहे") appear only in a CAUSE finding labelled STRONG. Negated sentences ("does not show it caused", "सिद्ध होत नाही") and the connective "त्यामुळे" ("therefore") are allowed |
| SCHOOL_NAME | No school names: the LLM never sees them, so any would be invented |
| NOT_MARATHI | Marathi text is at least 70% Devanagari letters |
| EMPTY / TOO_LONG / PLACEHOLDER_MALFORMED | Basic hygiene |
| MISSING_SECTION | All six brief sections appear (code renders "no finding" when a section is empty) |

Headings, label badges, action owners and horizons, the SYNTHETIC banner and every figure are rendered by code, never by the LLM.
