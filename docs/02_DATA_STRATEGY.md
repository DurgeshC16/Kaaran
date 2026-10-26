# 02 · Data strategy: the data availability matrix

> The mentor's first deliverable: "figure out which datasets your model can accurately solve for."
> This file is that answer. Download steps are in 08. Generator details stay in SYNTHETIC_DATA_SPEC.md
> (v2, current) until the v3 generator replaces it (plan in 07).

---

## 1. Principles

1. **Few domains, done accurately.** Four core domains that drive foundational learning, plus two support
   signals that decide which action fits. Everything else is context.
2. **Real formats, always.** Synthetic files use the column names and layouts of the real systems
   (UDISE+ microdata, state assessment and attendance exports). Moving to real data is then a file swap,
   not a rewrite.
3. **Real where public, synthetic where not, and say which is which.** Every synthetic file and every
   output built on it carries the SYNTHETIC marker. Real data lives only in `data/real/` (git-ignored).
4. **Granularity follows the decision.** A BEO acts on clusters and schools, monthly. Data that only exists
   per district per three years (NAS, PRS) is a benchmark, not a trigger.
5. **Identifiable data stays local.** Only aggregates reach the LLM (rule 5).

## 2. The four core domains + two support signals

The causal chain the mentor described for a foundational classroom: *is a teacher there → how many
children per teacher → do children come → are they learning*. Support signals explain why a cluster with
enough teachers still fails.

| Domain | Indicators Kaaran computes | Why it matters for the BEO's decision |
|---|---|---|
| **A. Teacher availability** | working teachers, sanctioned vs working posts, vacancies, PTR (pupils per teacher), single-teacher and multigrade schools, regular vs contract | Decides between "get a teacher there" and "support the teachers who are there". RTE norm: PTR 30:1 primary, 35:1 upper primary. |
| **B. Student attendance** | monthly attendance %, months below threshold, flat/implausible runs (100% for months), seasonal dips (e.g. Nov-Mar sugarcane migration in Solapur region) | Absent children cannot learn; implausible attendance is the most common data-quality problem. |
| **C. Enrolment** | enrolment by class and gender, change year on year, small schools (< 20 pupils) | Denominator for PTR; falling enrolment signals migration or shift to private schools. |
| **D. Learning assessment** | competency-wise % correct (FLN: number sense, place value, addition/subtraction, reading comprehension…), grade 2-5, by assessment round; change between rounds | The outcome. Competency-level results turn "maths fell" into "place value fell in these 2 clusters". |
| *Support 1. Academic support* | CRC / Kendra Pramukh visits per school per month, BRC/BEO visits, academic inspections, teacher training days, SMC meetings | Distinguishes a teaching-support gap from a staffing gap (the mentor's cluster A vs cluster B example). |
| *Support 2. Non-teaching duty* | teachers on non-teaching assignments, duty days per month (elections, surveys) | Explains temporary dips; avoids blaming schools for a district-wide event. |
| *Context only* | rural/urban, management, medium of instruction, instructional days, BPL/EWS enrolment share, district poverty | Used to find comparable schools/blocks (twins, positive deviants), never as a "cause". |

## 3. The availability matrix

Legend: **REAL-PUBLIC** = downloadable now · **REAL-LOGIN** = exists, needs authorised access ·
**SYNTH** = we generate it in the real format · **BENCH** = real but only as a benchmark.

| Domain | Real source | Unit | Frequency | Access | Kaaran v2 uses |
|---|---|---|---|---|---|
| Teacher availability (counts, regular/contract, qualifications) | UDISE+ microdata `tch` file | school | yearly | **REAL-PUBLIC** (registration; pseudo school IDs) | real format; real file for the pilot block |
| Enrolment by class/gender/category | UDISE+ microdata `enr1`, `enr2` | school | yearly | **REAL-PUBLIC** | real format; real file for the pilot block |
| School profile (block, rural/urban, management, classes, instructional days) | UDISE+ microdata `prof1` | school | yearly | **REAL-PUBLIC** | real format |
| Academic support counts (CRC visits, BRC/BEO visits, inspections, SMC meetings) | UDISE+ microdata `prof2` | school | yearly | **REAL-PUBLIC** | yearly counts real format; **monthly** visit log SYNTH |
| Non-teaching assignments | UDISE+ `tch.teacher_involve_non_training_assignment` | school | yearly | **REAL-PUBLIC** | yearly count; monthly duty days SYNTH |
| Sanctioned vs working posts, monthly | State teacher HR / payroll systems | school | monthly | REAL-LOGIN | **SYNTH** (state-style Excel export) |
| Student attendance, monthly | State MIS (Maharashtra: SARAL / Vidya Samiksha Kendra) | school (student) | daily/monthly | REAL-LOGIN | **SYNTH** (PDF/Excel export, school-month %) |
| School-level assessment (competency-wise) | State assessment (SCERT Maharashtra periodic assessment tests), school-based assessments | school (student) | 2-3 rounds/year | REAL-LOGIN | **SYNTH** (competency codes aligned to NIPUN Bharat / PRS) |
| District learning levels by competency, grade 3/6/9 | PARAKH Rashtriya Sarvekshan 2024 district report | district (sample) | ~3 years | **REAL-PUBLIC** | **BENCH** (already downloaded: Solapur) |
| Grade 3 FLN baseline | NCERT Foundational Learning Study 2022 (state reports; low-performing district reports) | state / district | one-off | **REAL-PUBLIC** | **BENCH** |
| Grade 3/5/8/10 learning levels | NAS 2021 district report cards | district | 2017, 2021 | **REAL-PUBLIC** | BENCH (not comparable with PRS 2024; caveat) |
| Rural learning (reading, arithmetic) | ASER 2024 Maharashtra district estimates | district (rural) | ~2 years | **REAL-PUBLIC** | BENCH / independent check |
| Programme budgets and approved interventions | Samagra Shiksha PAB minutes (Maharashtra 2025-26, 2026-27 when published) | state / district | yearly | **REAL-PUBLIC** | grounds the action rubric (which interventions are funded) |
| Household consumption / poverty | HCES 2022-23 and 2023-24 (MoSPI); NFHS-5 district fact sheets; SECC via SHRUG | state / district / taluka | varies | REAL-PUBLIC | context for twins |
| Election / non-teaching events | Election Commission and State Election Commission schedules | constituency / date | events | REAL-PUBLIC | real dates (e.g. Lok Sabha poll in Solapur, 7 May 2024; Maharashtra assembly, 20 Nov 2024) |

**What this means in one sentence:** school-level *inputs* (teachers, enrolment, support counts) are real
and public through UDISE+ microdata; school-level *outcomes and monthly operations* (assessment,
attendance, posts, visits) are behind state logins, so we synthesise them in the state's export formats
until a pilot gives us authorised exports.

## 4. Facts we verified from real files

### 4.1 UDISE+ 2024-25 microdata (format verified from the public Delhi release on OpenCity)

Six CSV files per state, prefixed by the state code (Delhi = `07`, Maharashtra = `27`), one row per school
(`pseudocode` = a pseudo school ID, not the real UDISE code). Columns Kaaran uses:

| File | Columns used |
|---|---|
| `prof1` | `pseudocode, state, district, block, rural_urban, lgd_vill_name, lgd_vill_panchayat_name, school_category, school_type, lowclass, highclass, managment` (sic), `medium_instr1, avg_instr_days` |
| `prof2` | `pseudocode, acad_inspections, crc_coordinator` (CRC visits), `block_level_officers` (BRC/BEO visits), `district_officers, smc_exists, smc_smdc_meetings` |
| `tch` | `pseudocode, total_tch, male, female, regular, contract, part_time, graduate, post_graduate_and_above, trained_comp, class_taught_pr, class_taught_upr, teacher_involve_non_training_assignment` |
| `enr1` | `pseudocode, item_group, item_id, cpp_b, cpp_g, c1_b, c1_g … c12_b, c12_g` (long format: item_group 1 = social category General/SC/ST/OBC; 2 = religion; 3 item 13 = BPL; 4 = CWSN; 5 = repeaters; 10 item 32 = EWS) |
| `fac` | `pseudocode, total_class_rooms, electricity_availability, library_availability, total_boys_func_toilet, total_girls_func_toilet` … (context only) |

Implications:
- **PTR per school** = (sum of `c1..c5` boys+girls over `item_group = 1`) ÷ `class_taught_pr` (+ shared
  teachers). Computable from public data.
- **No cluster (kendra) column** in the public microdata. Cluster membership comes from the BEO office
  (a short school → kendra list) or is approximated by village panchayat. In synthetic data we generate a
  kendra list in the format a BEO office keeps.
- **Pseudo IDs** cannot be joined to state systems by UDISE code. In a real deployment the state exports
  carry real UDISE codes; the pseudo-ID limitation only affects public-data demos. Our name-matching
  crosswalk (already built) covers both.

### 4.2 PARAKH Rashtriya Sarvekshan 2024, Solapur district report (downloaded)

- 22 pages, district as the unit. Sample: **121 schools, 354 teachers, 3,400 students**; foundation stage
  (grade 3): 40 schools, 1,070 students.
- Grade 3 maths: **Solapur 75%, Maharashtra 64%, India 60%**. Grade 3 language: **79 / 69 / 64**
  (verified visually on page 15). Breakdowns by gender, location, management, social group; competency
  tables with codes (e.g. C-1.1 place value) for district / state / national.
- **Lesson for the ingest:** the PDF's text order does not match its visual layout (the maths numbers come
  out under the language heading). Any PDF number we use is checked against a rendered page image or a
  second extraction method before it enters an evidence pack.
- **Use in Kaaran:** a benchmark line in the brief ("district grade 3 maths 75% vs state 64%, PRS 2024")
  and the source of **competency codes** for our synthetic assessment. With only 40 grade-3 schools in the
  sample, it cannot say anything about a block, and the brief says so.

## 5. Data model v2 (canonical tables)

Hierarchy: **state → district → block (taluka) → cluster (kendra) → school**. Every row keeps provenance
columns (`src_file, src_sheet_or_page, src_row`), as in v1.

| Table | Grain | Key fields | From |
|---|---|---|---|
| `geo_school` | school | school_id (UDISE code or pseudocode), name, cluster_id, block_id, district_id, rural_urban, management, lowclass, highclass, multigrade_flag | UDISE+ prof1 + kendra list |
| `geo_cluster` | cluster | cluster_id, name, block_id, kendra_pramukh_post | kendra list |
| `enrolment` | school × year × class × gender | count | UDISE+ enr1 |
| `teachers_year` | school × year | total, regular, contract, non_teaching_assignment | UDISE+ tch |
| `teacher_posts` | school × month × subject/grade band | sanctioned, working, vacant, on_deputation, duty_days | state HR export (SYNTH) |
| `attendance` | school × month | student_attendance_pct, days_open, (teacher_attendance_pct) | state MIS export (SYNTH) |
| `assessment` | school × round × grade × competency | pct_correct, n_assessed | state assessment export (SYNTH) |
| `support_visits` | school × visit | date, visitor_role (CRC/KP/BRC/BEO), purpose | visit app export (SYNTH); yearly counts from prof2 |
| `training` | teacher-group × event | school_id, days, topic | training register (SYNTH) |
| `benchmarks` | district × source × grade × subject/competency | pct, comparator (state/national) | PRS 2024, FLS 2022, NAS 2021 (REAL) |
| `context` | district/taluka | poverty, literacy, migration indicators | NFHS-5, SECC/SHRUG, HCES (REAL) |

Derived metrics (code, with provenance): PTR, vacancy rate, attendance trend and seasonality, competency
change between rounds, visits per school-month, training coverage, non-teaching days, data completeness.

## 6. Synthetic data v3: what changes

| Aspect | v2 (current) | v3 (planned, see 07) |
|---|---|---|
| Hierarchy | district → 11 talukas → schools | district → 11 blocks → **clusters (10-15 per block)** → schools |
| Column names | our own ("udise_code", "mean_score") | **real UDISE+ microdata columns**; state-export-style headers in Marathi/English for the rest |
| Assessment | one maths mean score per school-year | **competency-wise % by grade and round** (codes aligned to NIPUN Bharat / PRS) |
| Teacher data | yearly posts, maths vacancy | monthly sanctioned vs working, multigrade, contract, duty days |
| Support | none | monthly CRC / Kendra Pramukh / BEO visit log, training register |
| Planted truths (answer key) | T1-T8 (taluka decline, vacancy cause, election non-cause, flat attendance, missing data, twin, decoy, honest low attendance) | v2 truths re-expressed at cluster level **plus**: two failing clusters with **opposite causes** (staffing gap vs support gap), a **positive-deviant** multigrade school, a **seasonal-migration** attendance pattern, a cluster where actions should be "accountability review", and a surplus-teacher school that makes redeployment possible |
| Messiness | yes (kept) | kept and extended to the new files |
| Real-frame option | no | `--frame data/real/udise/27_*.csv --block PANDHARPUR`: use the **real school list** (pseudo IDs, enrolment, teachers) of a real block and synthesise only outcomes and operations. Outputs stay SYNTHETIC-marked and never leave `data/real/`. |

## 7. Data quality rules carried over and added

Kept from v1 (docs/CONFIDENCE_RULES.md): flat attendance runs, deseasonalised jumps, reverting score
spikes, missing months/years, contradictory duplicates, honest-low-attendance clearance.

Added in v2:
- **Impossible combinations:** attendance near 100% with competency results far below the cluster (the
  mentor's example); enrolment rising while working teachers and attendance are flat for years.
- **PTR sanity:** PTR > 80 or teachers > enrolment → flag the source row, not the school.
- **Assessment integrity:** a school whose results jump more than the block's distribution allows between
  two rounds and fall back (reverting spike), or identical scores across all competencies.
- **Freshness:** each finding states its data period; a source older than the latest expected period is
  marked "outdated" and cannot trigger an alert.

## 8. What we tell judges about data (one paragraph)

Kaaran runs on the data a block office already has. School-level teacher and enrolment data is public
through UDISE+ microdata and we use its exact format. Assessment and attendance data sit behind state
logins, so for the demo we generate them in the same formats, with planted scenarios that we can score
against. District learning benchmarks come from the real PARAKH 2024 report. Moving a block from demo to
pilot means replacing the synthetic files with authorised exports: no code changes.
