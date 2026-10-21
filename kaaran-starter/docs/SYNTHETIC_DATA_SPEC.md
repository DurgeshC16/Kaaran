# Synthetic Data Spec (Phase 1)

Purpose: generate a fictional but realistic district dataset with **planted truths**, so every Kaaran engine can be tested against a known answer key.
Rules: deterministic for a given seed, no LLM calls, every output file marked SYNTHETIC.

## Build order (important)
1. Generate **clean truth tables** with the planted effects. Verify them with plain pandas tests.
2. Only then add the **messiness layer** and write the raw files.
Tests for step 1 must not depend on any Kaaran engine.

## Scope
- One district labelled "SYNTHETIC DEMO DISTRICT", 11 talukas. Default names: Pandharpur, Malshiras, Karmala, Mangalvedha, Sangola, Madha, Mohol, Barshi, Akkalkot, North Solapur, South Solapur. Names come from config.
- Schools per taluka: 90-160 (Pandharpur >= 140). About 1,300 in total.
- Per school: 11-digit UDISE-style code (string), English name, cluster (kendra) of 10-15 schools, enrolment Std 1-5 (20-150), static infrastructure (toilets, library, drinking water, classrooms).
- Per taluka: poverty index 0-1 and school count (used for twin matching).
- Years: academic years 2021-22 to 2025-26 (configurable).
- Per school-year: Std 3 numeracy mean score (0-100) and students appeared; monthly attendance (school months Jun-Mar); teacher posts sanctioned/working by subject (maths, language, other); election-duty deployment by month.

## Baseline model
score = taluka_base + school_effect + year_trend + noise, clipped to 0-100.
Taluka bases are similar (mean about 55, sd about 3). Year-to-year noise is large enough that ranks shuffle by about +/-2 naturally.
Attendance baseline 84-91% with seasonal dips (monsoon, harvest, festivals). Poverty correlates weakly and negatively with scores.

## Planted truths (written to ground_truth.json)
Each truth has: id, description, entities, expected numbers with tolerances, expected verdict.

| ID | Planted truth | Expected verdict |
|----|---------------|------------------|
| T1 REAL_DECLINE | Pandharpur's taluka rank falls from 4th of 11 (2021-22) to 9th of 11 (2025-26). Mean drop >= 8 points, clear in a school-level paired comparison. | STRONG |
| T2 ELECTION_EXCUSE_WEAK | In 2024-25, 7 talukas (Pandharpur + 6 others) have election duty: >= 30% of teachers deployed for >= 2 months. Of the 6 others, 5 stay within +/-2 points. One dips about 3.5 points for an unrelated reason. | WEAK_CAUSE |
| T3 VACANCY_CAUSE | 11 Pandharpur schools have had no maths teacher since the start of 2023-24. Their scores drop >= 20 points and account for >= 60% of the taluka's total decline. Other Pandharpur schools move <= 2 points. About 8 vacancy schools in other talukas show the same drop pattern. | STRONG |
| T4 TWIN_BLOCK | Malshiras matches Pandharpur on school count (+/-10%), enrolment, poverty index (+/-0.05) and election duty, has no maths vacancies, and improves >= 6 points (rank 8th to 3rd). Also plant a decoy: one taluka with similar covariates that did NOT improve. | LEARN_FROM |
| T5 FLAT_ATTENDANCE | 23 Pandharpur schools report exactly 100.0% attendance for 4 consecutive months in 2024-25. About 30 more such schools are scattered across the district as noise. | RED_FLAG |
| T6 INSUFFICIENT_DATA | Mangalvedha: >= 40% of schools are missing >= 3 attendance months or >= 2 years of scores. | INSUFFICIENT |
| T7 INFRA_DECOY | Karmala has the worst infrastructure but stable scores. Within Pandharpur, infrastructure is uncorrelated with the decline (|r| < 0.1). | not a cause |
| T8 HONEST_LOW_ATTENDANCE | 15 Pandharpur schools have realistic low attendance (78-84%, natural variation) and ordinary scores. The trust check must NOT flag them. | not flagged |

## Messy raw files (second pass)
Written to `data/synthetic/<name>/raw/`:
1. `udise_2023.xlsx`: sheets School Profile, Enrolment, Infrastructure. 3 title rows above headers, merged cells, mixed-case headers, one sheet with Marathi headers. School codes stored as text in one sheet and as numbers (leading zeros lost) in another. Taluka spelling variants (Pandharpur / Pandharpoor / Pandharpura / पंढरपूर) in about 8% of rows.
2. `attendance_jan-dec.pdf`: text-based PDF tables per taluka and month. Columns: Sr No, School Name, Short Code, Enrolled, Present Avg, %. Headers repeat on each page. Some schools missing.
3. `crosswalk.xlsx`: short code to UDISE code, covering about 97% of schools. The rest need fuzzy name matching.
4. `pat_scores.csv`: SCHOOL_CD, Year, Std, Subject, Avg_Marks, Students_Appeared. Year formats mixed ("2023-24", "23-24", 2024). Subject labels mixed (Maths / Math / गणित). UTF-8 with BOM. About 2% duplicate rows.
5. `teacher_posts.xlsx`: sanctioned vs working posts by subject. As-on dates vary. Vacancies sometimes stored as negative numbers.
6. `election_duty.csv`: taluka, month, deployed teacher percentage, in an Election Commission schedule style with two date formats.

Optional, later: Devanagari school names (Noto Sans Devanagari, OFL licence) and a scanned-image attendance sheet.

## Outputs
- `data/synthetic/<name>/clean/*.parquet`: truth tables, used only by tests and the answer key.
- `data/synthetic/<name>/raw/`: the messy files above.
- `data/synthetic/<name>/ground_truth.json`: one entry per planted truth.
- `data/synthetic/<name>/manifest.json`: seed, version, file hashes.
- Command: `python -m kaaran.synth --seed 42 --out data/synthetic/demo`

## Acceptance tests (pytest)
- Determinism: the same seed gives identical file hashes.
- One assertion per planted truth T1-T8, with tolerances, using plain pandas on the clean tables.
- Every raw file opens with pandas, openpyxl or a PDF reader, and contains the planted messiness (counts of spelling variants, mixed year formats, lost leading zeros).
- At least 95% of attendance rows join to UDISE codes through the crosswalk. The rest need fuzzy matching.
- Every file carries a SYNTHETIC marker. No real personal data anywhere.
