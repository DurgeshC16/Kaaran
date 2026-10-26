# 08 · Data download guide (do this, then tell Claude the file names)

> Real files go in `data/real/<source>/`, which git ignores; they are never committed (rule 8).
> After downloading, tell Claude the folder and file names. It will read only headers, row counts and
> page summaries, never whole files.
> Links checked on 2026-10-27. Government sites change; if a link moves, search the title given.

## Priority

| # | Source | Priority | Why we need it | Folder |
|---|---|---|---|---|
| 1 | UDISE+ 2024-25 **school-level microdata**, Maharashtra | **MUST** | the real school list, teachers, enrolment (PTR), support visits for a real block | `data/real/udise_2425/` |
| 2 | PARAKH Rashtriya Sarvekshan 2024: Solapur district (have) + Maharashtra state report | **MUST** | real learning benchmark + competency codes | `data/real/prs2024/` |
| 3 | Samagra Shiksha PAB minutes, Maharashtra 2025-26 (and 2026-27 if published) | **MUST** | which interventions are funded → realistic actions in the rubric | `data/real/pab/` |
| 4 | Foundational Learning Study 2022: Maharashtra state report | SHOULD | grade 3 FLN baseline, competency framing | `data/real/fls2022/` |
| 5 | NAS 2021 district report card: Solapur | SHOULD | older benchmark (shown with a "not comparable" note) | `data/real/nas2021/` |
| 6 | ASER 2024 Maharashtra (district estimates) | COULD | independent rural check | `data/real/aser2024/` |
| 7 | NFHS-5 Solapur district fact sheet | COULD | context (literacy, child indicators) | `data/real/nfhs5/` |
| 8 | AIKosh / data.gov.in UDISE+ items for Solapur | COULD | older teacher tables (2019-20) | `data/real/aikosh/` |
| 9 | HCES 2022-23 / 2023-24 fact sheets | COULD | consumption context (state level only) | `data/real/hces/` |

## Steps

### 1. UDISE+ 2024-25 microdata (MUST)
1. Open **https://microdata.udiseplus.gov.in** (linked from https://udiseplus.gov.in).
2. Register: name, e-mail, mobile (OTP), organisation (college), purpose ("research / hackathon prototype
   for education officers"). Accept the data-use terms.
3. Choose year **2024-25**, state **Maharashtra** (state code 27). Download all files offered for the
   state. Expect six CSVs named like `27_prof1.csv, 27_prof2.csv, 27_fac.csv, 27_enr1.csv, 27_enr2.csv,
   27_tch.csv`, plus the schema PDF (`dsp_schema.pdf`).
4. Put them in `data/real/udise_2425/`. Do not open the big CSVs in Excel (they are large); just tell
   Claude the names and sizes.
5. Format reference (already checked): the public Delhi release on OpenCity uses the same layout:
   https://data.opencity.in/dataset/delhi-udise-2024-25
6. If registration is blocked or slow, tell Claude. The v3 generator writes the same format
   synthetically, and the demo still works.

### 2. PARAKH Rashtriya Sarvekshan 2024 (MUST)
1. You already have the Solapur district report. Claude moved it to
   `data/real/prs2024/Report_Solapur_IND27496.pdf`.
2. State report: open **https://parakh.ncert.gov.in/prs-reports-2024**, choose the state report card for
   **Maharashtra**, download the PDF into the same folder.
3. Optional (for the "twin block" story at district level): the district list is at
   https://parakh.ncert.gov.in/prs-reports-2024-districtlist. Download 2-3 neighbouring districts (e.g.
   Sangli, Satara, Osmanabad/Dharashiv) if you want district comparisons.

### 3. Samagra Shiksha PAB minutes, Maharashtra (MUST)
1. 2025-26: **https://dsel.education.gov.in/sites/default/files/pab/MH2526.pdf**
2. 2024-25: https://dsel.education.gov.in/sites/default/files/pab/Maharashtra_PAB_2024_25.pdf
3. 2026-27: check the PAB section of https://dsel.education.gov.in (it may not be published yet).
4. Save in `data/real/pab/`. Claude will extract the approved FLN / teacher-training / remedial line
   items to ground the rubric (doc 06), not to compute findings.

### 4. Foundational Learning Study 2022 (SHOULD)
1. State reports follow this pattern: `https://dsel.education.gov.in/sites/default/files/FLS/State/<state>.pdf`.
   Try **.../FLS/State/maharashtra.pdf**. If that fails, search "FLS 2022 Maharashtra state report".
2. Low-performing-district reports are in `.../FLS/LPD/` (e.g. Yavatmal.pdf for Maharashtra).
3. Save in `data/real/fls2022/`.

### 5. NAS 2021 district report card: Solapur (SHOULD)
1. Open **https://ncert.nic.in/DRC_2021.php?ln=en** (or the NAS section on the PARAKH portal).
2. Download Maharashtra → Solapur. If it comes as a large RAR of PDFs, extract only Solapur.
3. Save in `data/real/nas2021/`.

### 6. ASER 2024 (COULD)
1. https://asercentre.org → Reports → ASER 2024 → Maharashtra state report / district estimates PDF.
2. Microdata needs a request form on the ASER site; submit it only if time allows (approval takes days).

### 7. NFHS-5 Solapur fact sheet (COULD)
1. http://rchiips.org/nfhs/ → NFHS-5 → District Fact Sheets → Maharashtra → Solapur (PDF).

### 8. AIKosh / data.gov.in (COULD)
1. https://aikosh.indiaai.gov.in → Datasets → search "Solapur UDISE" (teacher data 2019-20 per district
   exists for several Maharashtra districts, e.g. Aurangabad, Sindhudurg, Nandurbar).
2. https://data.gov.in → search "UDISE Maharashtra". Older (to 2019-20); use only if #1 fails.

### 9. HCES (COULD)
1. https://mospi.gov.in → Household Consumption Expenditure Survey 2023-24 fact sheet (state-level MPCE).

## Data that is NOT public (needs a request)

| Data | Holder | How to ask |
|---|---|---|
| School-wise assessment results (state periodic assessment) | SCERT Maharashtra / district DIET | Letter from the college + problem statement, asking for an anonymised school-wise export for one block |
| Monthly student attendance | State MIS (SARAL / Vidya Samiksha Kendra) via the ZP education office | Same letter; aggregated school-month % is enough |
| Teacher posts sanctioned vs working | ZP education office (establishment section) | Same letter |
| Cluster (kendra) list for a block | BEO office | Usually a one-page list; ask the team teacher's BEO office |

A template request letter will be added to `docs/` when we contact an office (doc 07, after the hackathon).

## After you download

Reply with something like:
`downloaded: data/real/udise_2425/27_prof1.csv (… MB), 27_tch.csv …; data/real/pab/MH2526.pdf; …`
Claude will then (a) check headers and row counts, (b) filter Solapur → one block, (c) wire the
connector, (d) add the verified benchmark numbers with page references.
