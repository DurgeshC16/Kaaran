# Synthetic Data Spec (Phase 1, v2)

Purpose: generate a fictional but realistic district dataset with **planted truths**, so every Kaaran engine can be tested against a known answer key.
Rules: deterministic for a given seed, no LLM calls, every output file marked SYNTHETIC.
v2 (2026-10-23): T1-T8 made numerically consistent as a set (v1 asked for an 8-point taluka drop from 11 schools, which is arithmetically impossible).

## Build order (important)
1. Generate **clean truth tables** with the planted effects. Verify them with plain pandas tests.
2. Only then add the **messiness layer** and write the raw files.
Tests for step 1 must not depend on any Kaaran engine.

## Scope
- One district labelled "SYNTHETIC DEMO DISTRICT", 11 talukas, 1,292 schools (counts in the table below).
- Taluka names come from config. Two ready-made sets: `solapur` (default: real Solapur taluka names) and `fictional`. Switching is one line in `src/kaaran/synth/config.py` (`TALUKA_NAMES`) or `--names fictional` on the CLI. Each set carries spelling variants and a Devanagari form per taluka.
- Per school: 11-digit UDISE-style code (string) with the non-existent state prefix `00` (format `00` + district `99` + block 2 + village 3 + school 2), so leading zeros are real and codes can never collide with real schools (Maharashtra codes start with 27). Also: short code used by the attendance system, English name, cluster (kendra) of 10-15 schools, enrolment Std 1-5 (20-150 total), static infrastructure (toilets, library, drinking water, classrooms).
- Per taluka: poverty index 0-1 and school count (used for twin matching).
- Years: academic years 2021-22 to 2025-26 (configurable). School months Jun-Mar.
- Per school-year: Std 3 maths mean score (0-100) and students appeared; monthly attendance; teacher posts sanctioned/working by subject (maths, language, other). Per taluka-month: election-duty deployment.

## Metric definitions (also written to ground_truth.json)
- Taluka score = unweighted mean of school mean scores, over schools that reported that year.
- Rank 1 = highest taluka score.
- "Change" = later year minus earlier year. Decline share = (vacancy schools / all schools) x vacancy-group mean change / taluka mean change, over 2021-22 to 2025-26.
- Thresholds on "schools move", "talukas stay within" and "drop" are about **group means**. A single school's Std 3 mean has sampling noise of about +/-4-8 points (5-30 students).

## Baseline model
score = taluka target + school effect (sd 7, persistent) + sampling noise (sd 16/sqrt(students appeared)), then shifted per (taluka, group, year) so group means hit the targets below exactly, clipped to 0-100 and rounded to 0.1.
District mean rises 55.1 -> 56.6 (post-COVID recovery). Taluka sd is about 2 in 2021-22; neighbouring talukas are >= 0.2 apart in every year, so rounding cannot flip a rank. Poverty correlates weakly and negatively with scores (r about -0.4 to -0.5 at taluka level).
Attendance baseline 84-91% per school with seasonal dips (monsoon Jul-Aug, harvest Oct, Diwali Nov) and monthly noise. Only planted T5 schools ever report above 98.0%.

## Taluka score targets (Std 3 maths, rank after #)

| Taluka | Schools | Poverty | Election 24-25 | 2021-22 | 2022-23 | 2023-24 | 2024-25 | 2025-26 | 23-24 -> 24-25 | Total | Role |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Barshi | 121 | 0.40 | yes | 58.2 #1 | 58.9 | 59.7 | 60.3 | 61.2 #1 | +0.6 | +3.0 | |
| North Solapur | 92 | 0.48 | | 57.6 #2 | 58.6 | 59.0 | 60.6 | 60.9 #2 | +1.6 | +3.3 | 3 vacancy schools |
| Madha | 118 | 0.38 | yes | 56.5 #3 | 57.3 | 57.8 | 58.5 | 59.0 #4 | +0.7 | +2.5 | |
| Pandharpur | 140 | 0.42 | yes | 56.0 #4 | 55.91 | 55.41 | 53.35 | 52.69 #9 | -2.06 | -3.31 | T1 T3 T5 T8 |
| Sangola | 138 | 0.43 | yes | 55.6 #5 | 55.6 | 54.9 | 55.1 | 55.3 #7 | +0.2 | -0.3 | T4 decoy |
| South Solapur | 108 | 0.56 | | 55.1 #6 | 56.3 | 56.7 | 57.3 | 57.6 #5 | +0.6 | +2.5 | 3 vacancy schools |
| Mohol | 108 | 0.35 | yes | 54.6 #7 | 54.9 | 56.2 | 55.4 | 56.4 #6 | -0.8 | +1.8 | |
| Malshiras | 134 | 0.45 | yes | 54.0 #8 | 55.3 | 57.4 | 58.2 | 60.5 #3 | +0.8 | +6.5 | T4 twin |
| Akkalkot | 117 | 0.52 | yes | 53.5 #9 | 54.3 | 55.2 | 53.7 | 54.1 #8 | -1.5 | +0.6 | T2 unrelated dip |
| Mangalvedha | 100 | 0.58 | | 52.4 #10 | 52.6 | 53.1 | 52.6 | 52.4 #10 | -0.5 | 0.0 | T6 |
| Karmala | 116 | 0.50 | | 52.0 #11 | 52.9 | 52.3 | 52.9 | 52.0 #11 | +0.6 | 0.0 | T7, 2 vacancy schools |

Pandharpur is a mix of two groups: 11 vacancy schools (change vs 2021-22: 0, 0, -4, -22, -28) and 129 other schools (0, -0.1, -0.3, -1.0, -1.2).

## Planted truths (written to ground_truth.json)
Each truth has: id, description, entities, expected numbers with tolerances, expected verdict. Planted school sets for T3, T5 and T8 are disjoint.

| ID | Planted truth | Test asserts | Verdict |
|----|---------------|--------------|---------|
| T1 REAL_DECLINE | Pandharpur 56.0 -> 52.7 (-3.3), rank 4th -> 9th of 11, below its 2021-22 level in every year from 2023-24. School-level paired comparison 2021-22 vs 2025-26: mean -3.3, t about 4. | drop >= 3.0; ranks 4 and 9; paired t >= 3 | STRONG |
| T2 ELECTION_EXCUSE_WEAK | In 2024-25, 7 talukas (Pandharpur, Malshiras, Sangola, Madha, Mohol, Barshi, Akkalkot) have >= 30% of teachers on election duty for 2 months (Oct 2024 38-45%, Nov 2024 45-55%). The other 4 talukas <= 12%; no other taluka-month >= 30% in any year. Change 2023-24 -> 2024-25: Pandharpur -2.06; 5 of the 6 others within +/-1.0; Akkalkot dips 1.5 for an unrelated (unplanted) reason, less than Pandharpur. | 7 talukas meet the duty rule; 5 others within +/-1.0; Akkalkot -1.5 +/-0.3 and dip < Pandharpur's | WEAK_CAUSE |
| T3 VACANCY_CAUSE | 11 Pandharpur schools have 0 working maths teachers from 2023-24 on. Group change vs 2021-22: 0, 0, -4, -22, -28 (the Std 3 group tested each year has missed 1, 2, then 3 years of maths teaching). Other Pandharpur schools: -1.2. Vacancy schools explain 66.6% of the taluka decline. 8 more vacancy schools (Karmala 2, North Solapur 3, South Solapur 3) follow the same pattern. These 19 are the only maths vacancies in the district. | group drop 20-30; share >= 60%; others' change within +/-2; the 8 others drop 20-30; Malshiras has 0 maths vacancies | STRONG |
| T4 TWIN_BLOCK | Malshiras: 134 schools (-4% vs 140), poverty 0.45 (+0.03), mean enrolment within +/-5%, same election duty, no maths vacancies; 54.0 -> 60.5 (+6.5), rank 8th -> 3rd. Decoy Sangola: 138 schools (-1%), poverty 0.43 (+0.01), i.e. closer covariates, same election duty, no maths vacancies, but -0.3. No other taluka is within +/-10% on school count. | covariates within tolerance; Malshiras >= +6 and rank 3; decoy change <= +1 | LEARN_FROM |
| T5 FLAT_ATTENDANCE | 23 Pandharpur schools report exactly 100.0% for Aug-Nov 2024 (overlaps the election months). 30 more schools in other talukas have a 4-month run of 100.0% starting Jun-Sep 2024. | 23 in Pandharpur, about 30 elsewhere, runs are 4 consecutive months | RED_FLAG |
| T6 INSUFFICIENT_DATA | Mangalvedha: 46 of 100 schools flagged: 30 miss >= 3 attendance months in Jun-Dec 2024, 20 miss 2 score years, 4 in both. Other talukas: at most 3% of schools miss even one month, none miss >= 3. | >= 40% flagged; every other taluka < 10% | INSUFFICIENT |
| T7 INFRA_DECOY | Karmala has the lowest mean infrastructure index (about 0.40 vs 0.60-0.75 elsewhere) but stable scores (52.0 -> 52.0, every year within +/-1). Within Pandharpur, \|r(infrastructure index, score change)\| < 0.05 (enforced). | Karmala lowest by >= 0.1; \|r\| < 0.1 | NOT_A_CAUSE |
| T8 HONEST_LOW_ATTENDANCE | 15 Pandharpur schools have realistic low attendance: school mean 78-84%, months vary (sd about 1.5, seasonal dips), never flat, never 100. Their scores are ordinary. | means in [78, 84]; no 3 equal consecutive months; scores within Pandharpur's normal range | NOT_FLAGGED |

## Messy raw files (second pass)
Written to `data/synthetic/<name>/raw/`. Every injected messiness item is recorded in the `messiness` section of ground_truth.json (file, sheet, kind, count, affected keys), so ingest and trust engines can be scored too.
1. `udise_2023.xlsx`: sheets School Profile, Enrolment, Infrastructure. 3 title rows above headers (first: SYNTHETIC marker), merged cells, mixed-case headers, Infrastructure sheet has Marathi headers. School codes stored as text in School Profile and Infrastructure, as numbers in Enrolment (leading `00` lost). Taluka spelling variants (e.g. Pandharpur / Pandharpoor / Pandharpura / पंढरपूर) in about 8% of rows.
2. `attendance_jan-dec.pdf`: calendar 2024 only (Jan-Mar from 2023-24, Jun-Dec from 2024-25; matches the file name and contains the T5 and T6 windows). Text-based tables per taluka and month, English only. Columns: Sr No, School Name, Short Code, Enrolled, Present Avg, %. Headers repeat on each page; SYNTHETIC marker on every page. School names abbreviated/misspelt in places. About 1% of school-months omitted (on top of the planted T6 gaps). The full 5-year attendance history stays in the clean tables.
3. `crosswalk.xlsx`: short code to UDISE code, covering about 97% of schools. The rest need fuzzy name matching.
4. `pat_scores.csv`: SCHOOL_CD, Year, Std, Subject, Avg_Marks, Students_Appeared. Year formats mixed ("2023-24", "23-24", 2024). A bare year is the END year: 2024 = 2023-24. Subject labels mixed (Maths / Math / गणित). UTF-8 with BOM. First line is a SYNTHETIC title line (read with `skiprows=1`). About 2% exact duplicate rows.
5. `teacher_posts.xlsx`: sanctioned vs working posts by subject, one sheet per academic year. As-on dates vary. Vacancies sometimes stored as negative numbers.
6. `election_duty.csv`: taluka, period from/to, deployed teacher percentage, in an Election Commission schedule style with two date formats. SYNTHETIC title line first.
7. `taluka_profile.csv` (added 2026-10-24, Phase 2B): taluka and poverty headcount ratio, in a district-handbook style. Poverty is stored as a percentage (42.0) rather than a share (0.42), and one taluka name is a spelling variant. SYNTHETIC title line first. The twin finder needs this file.

**Hold-out layout `variant_b`** (`--layout variant_b`, added 2026-10-23) tests the mapping proposer.
- Same values as the default layout, but the xlsx and csv files change shape:
  - headers reworded in English, Marathi and transliterated Marathi;
  - columns shuffled; junk columns added (Remarks, Checked By, Unnamed, Entry Date, Source);
  - sheets renamed (e.g. शाळा माहिती, Patsankhya, "Posts 2021-22" / "शिक्षक पदे 2022-23");
  - the Enrolment group header row dropped.
- The PDF is unchanged.
- ground_truth.json["layout"] records every rename, so a proposed mapping can be scored. The rule-based baseline fails on this layout by design.

Optional, later: Devanagari school names (Noto Sans Devanagari, OFL licence), Devanagari in the PDF, and a scanned-image attendance sheet.

## Outputs
- `data/synthetic/<name>/clean/*.parquet`: truth tables, used only by tests and the answer key. SYNTHETIC flag in file metadata.
- `data/synthetic/<name>/raw/`: the messy files above.
- `data/synthetic/<name>/ground_truth.json`: conventions, one entry per planted truth, messiness log.
- `data/synthetic/<name>/manifest.json`: seed, version, config hash, library versions, file sha256/size/rows. No timestamps.
- Command: `python -m kaaran.synth --seed 42 --out data/synthetic/demo [--names solapur|fictional] [--clean-only]`

## Acceptance tests (pytest)
- Determinism: the same seed gives identical file hashes (same library versions); a different seed gives different hashes. Excel files are re-zipped with fixed timestamps and PDFs use reportlab invariant mode to make this possible.
- One assertion group per planted truth T1-T8, with tolerances, using plain pandas on the clean tables.
- Every raw file opens with pandas, openpyxl or pdfplumber, and contains the planted messiness in the counts recorded in the messiness log.
- At least 95% of attendance rows join to UDISE codes through the crosswalk. The rest can be matched by fuzzy name matching (difflib).
- Every file carries a SYNTHETIC marker. No real personal data anywhere.

---

## v3 generator (block lens): `python -m kaaran.synth3 --seed 42 --out data/synthetic/block_demo`

Added 2026-10-27 (docs/02 §6, docs/06). v2 above stays as is for the current pipeline and its tests.

**World:** the same 11 blocks (taluka names, poverty, school counts) → clusters of ~12 schools (Pandharpur: 12
clusters, 140 schools) → 1,292 schools. Years 2023-24 to 2025-26; school months Jun-Mar; grade 3 assessment in
three rounds (BL Jul, ML Dec, EL Mar) with 9 competencies (maths M1-M5, Marathi L1-L4).

**Raw files (18, SYNTHETIC marker in the first cell or line of each):**
UDISE+ `prof1, prof2, tch, enr1` for 2024-25 and 2025-26 (real microdata column names, official-export variant
keyed by `udise_sch_code`); `kendra_list.xlsx`; `teacher_posts.xlsx` (monthly, with non-teaching duty days);
`student_attendance_<year>.xlsx` (one sheet per month); `fln_assessment_<year>.xlsx` (one sheet per round,
competency columns); `visit_log.csv` (Kendra Pramukh / BRC / BEO visits); `teacher_training.xlsx`.

**Planted scenarios (answer key `truth3.json`, focus block Pandharpur):**

| Id | Cluster | Scenario | Expected |
|---|---|---|---|
| S1 | K03 | Kendra Pramukh post vacant from Jun 2025: visits 1.3 → 0.12 per school-month, last training Aug 2023; maths falls (ML −4, EL −8.5) with place value (M2) and subtraction (M4) falling most; replication cluster in Madha | at risk; D2 + D7; A4, A5, A6 |
| S2 | K07 | 6 schools lose their second teacher in the Jun 2025 transfers (EL −18, ramping BL 40% / ML 80%); 2 vacancy schools per other block (replication) | at risk; D1; A1 (surplus schools exist), A3, A12 |
| S3 | K07 | one school with the same teacher loss improves (+6) | positive deviant → A12 peer visit |
| S4 | K09 | 7 schools report 100% attendance Aug-Nov 2025 while learning is 10 points lower | data alert; D6; A10 |
| S5 | K11 | 5 schools near sugar factories: attendance −8 to −16 points Nov-Mar every year; endline −7 | at risk; D4; A8 |
| S6 | K12 | 4 schools miss Aug-Nov 2025 attendance and the 2025-26 endline | "cannot tell"; A11 |
| S7 | K05 | 4 schools with honest low attendance (77-81%) | never flagged |
| S8 | all | local body poll duty Nov-Dec 2025 (8-12 days per teacher); ML 2025-26 −2.5 everywhere | D5 ruled out |
| S9-S11 | K08, K10, block | improving cluster; 2 surplus schools (PTR < 18); twin block Malshiras, decoy Sangola | not at risk; twin found |

**Known noise:** only ~10-25 pupils are tested per school, so school results are noisy (sd ~6-7 points per
year-on-year change). A calibration probe over 60 seeds found the planted at-risk clusters on ~98% of seeds and
an unplanted cluster flagged on ~3%. The risk rules (docs/06) use school-level paired comparisons, both subjects
and a "pocket" rule to stay robust.
