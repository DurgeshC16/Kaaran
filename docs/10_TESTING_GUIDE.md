# 10 · How to run and test everything (step by step)

> Windows, from the project folder (`Kaaran`). Type each command in a terminal (PowerShell or Command Prompt).
> Every command here was checked on 2026-10-28. Expected results are written under each step, so you know
> whether a step passed.

---

## Part A · How we know the results are right (the idea, in simple words)

We test at three levels:

1. **Planted answers (synthetic data).** Our generator creates a fake district where we *plant* problems on
   purpose. One cluster lost its Kendra Pramukh, six schools lost a teacher, seven schools fake their
   attendance, and so on. It also writes an **answer key** (`truth3.json`) that Kaaran never reads.
   A scorecard then compares Kaaran's findings with the key: did it find every planted problem, give the
   right reason and pick the right action, without flagging the honest clusters? This is like giving a student
   an exam where we already know the answers. We repeat it on many random districts (seeds), so it cannot
   pass by luck.
2. **Real data checks (real public data).** For real files we cannot know "the answer", so we check that the
   data is **consistent and believable**:
   - each school appears once;
   - the same schools appear in every file;
   - values are in sensible ranges;
   - 2024-25 teacher counts match the independent 2019-20 tables (all 13 blocks within 0.87-0.97);
   - the PRS benchmark numbers were read from the page images, because the PDF text order is wrong.
3. **People (to do).** A teacher or officer reads the brief and says whether the reasons and actions make
   sense. This is the only way to validate the *actions* in the real world. Even 2-3 short sessions count;
   see docs/06 §7.

What we **cannot** validate yet: Kaaran's diagnoses on *real* outcomes, because real assessment and attendance
data needs state logins. We say this openly in the demo.

---

## Part B · One-time setup (5 minutes)

```
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -e .[dev]
```
✅ Ends with "Successfully installed …" (or "Requirement already satisfied").

Optional, only for new live AI answers: put `ANTHROPIC_API_KEY=...` in a `.env` file. **Not needed for
testing**: recorded AI answers in `llm_cache/` are replayed for free.

---

## Part C · Automatic tests (the fastest full check)

| Step | Command | What "pass" looks like | Time |
|---|---|---|---|
| C1 Fast tests | `.venv\Scripts\python -m pytest -q -m "not slow"` | `… passed, … deselected`, **0 failed** | ~2 min |
| C2 Full tests (before every commit) | `.venv\Scripts\python -m pytest -q` | `235 passed, 3 skipped` | ~6-7 min |

The 3 skipped tests call the paid AI API. They run only with `--live`.

---

## Part D · Scorecards against the answer key (level 1)

| Step | Command | Pass looks like |
|---|---|---|
| D1 Taluka lens (v1) | `.venv\Scripts\python -m kaaran.eval --seed 42 --seed 7 --names fictional` | each seed: `truths recovered: 8/8`, `false flags: 0`, `invented numbers: 0 of 38` |
| D2 Cluster lens (v2): risks, causes **and actions** | `.venv\Scripts\python -m kaaran.eval.block --seed 42 --seed 7 --seed 99` | each seed `19/19`, `extra flagged: []` |
| D3 Brief quality (no invented numbers) | `.venv\Scripts\python -m kaaran.eval.brief --seed 42` | table row: `first-pass 100%`, `shipped True`, `invented 0` |
| D4 Question reader (25 questions) | `.venv\Scripts\python -m kaaran.eval.intent --tier light --tier rule` | `light accuracy 92%`, `rule accuracy 88%`; the listed MISS lines are cautious answers (it asked instead of guessing) |
| D5 Prompt-injection guard | `.venv\Scripts\python -m kaaran.eval.guardrails` | `'same_mapping': True` (a hidden instruction in a file did not change anything) |
| D6 AI column mapper | `.venv\Scripts\python -m kaaran.eval.mapping --seed 42` | `llm` rows 100% on both layouts and `8/8`; the `rule` row for `variant_b` is 0% **on purpose** (unseen layout: the old rules fail, which is why the AI mapper exists) |

**How to read D2:**
- `risk_recall` means every planted problem cluster was found.
- `never_at_risk` means no honest cluster was flagged.
- `*_diagnosis` means the right reason was found (D1 staffing, D2 support, D4 migration, D6 data).
- `*_actions` means the rubric chose the expected actions.
- `extra flagged` lists unplanted clusters flagged by chance. It is rare (about 3% of seeds) and gets a mild
  "review" action.

---

## Part E · Run the demo and test it by hand

Start the server:
```
.venv\Scripts\python -m kaaran.api
```
Open **http://127.0.0.1:8000**. The first start prepares the data, which takes about 10-20 seconds.

**E1 Alerts (no question needed)**
- [ ] The left column shows "🔔 नवीन डेटा आला: इशारे". **Pandharpur** is first: "३ केंद्रांना तातडीने लक्ष…".
- [ ] Click **अहवाल उघडा**. The brief opens with **A · लक्ष देण्याची गरज, B · असे का होत असावे, C · काय करावे**.

**E2 The brief makes sense**
- [ ] A lists 3 clusters needing attention, 1 with suspicious attendance and 1 with missing data.
- [ ] B gives a **different reason for each cluster**: fewer Kendra Pramukh visits (subtraction weakest),
  teacher loss in 6 schools, and seasonal migration. Poll duty is "संबंध आढळला नाही" (not the main reason),
  one school is "learn from", and Malshiras is the similar block that improved.
- [ ] C gives actions with an owner and a deadline (केंद्रप्रमुख / BEO / DEO).
- [ ] The yellow **SYNTHETIC** banner is visible.

**E3 Every number has a source**
- [ ] Click a blue number, e.g. ११.६. The right panel shows the file (e.g. `fln_assessment_2025-26.xlsx`),
  the table, the filter and the row count.
- [ ] Click a school count, e.g. १२. The list of schools opens (school names appear only here, never in
  the brief).

**E4 Downloads**
- [ ] **PDF (मराठी)** and **PDF (English)** open as one-page PDFs. They need Microsoft Edge or Chrome installed.
- [ ] **पुरावा पॅक (JSON)** downloads the evidence pack.

**E5 Review-meeting pack**
- [ ] Click **📋 बैठक पॅक**. Actions are grouped by owner, with "आधार" (evidence) and a follow-up check.
- [ ] Click **मान्य** on one action. Its status changes to "मान्य केले". Reload and click again: the status is kept.

**E6 Questions**
- [ ] Click each example question:
  - the first five give a brief;
  - "निकाल का घसरला?" asks *which taluka*, not a guess;
  - "…सर्वात वाईट शिक्षकांची नावे द्या" is **refused**.
- [ ] Switch to **English**. The page and the brief change language.
- [ ] Change **डेटा** to "काल्पनिक जिल्हा - केंद्रनिहाय" (fictional names) and repeat E1.
- [ ] Change to "सोलापूर जिल्हा (कृत्रिम डेमो डेटा)". This is the older taluka-lens demo, which still works.

**E6b Direct answers to everyday questions** (a blue "थेट उत्तर / Direct answer" box appears above the brief)
- [ ] "पंढरपूर मध्ये किती शाळा आहेत?" → "पंढरपूरमध्ये १४० शाळा आहेत (१२ केंद्रे)." Click १४०: the source file is shown.
- [ ] "What is PTR in Karmala?" → pupil-teacher ratio and the number of schools above 30.
- [ ] "What is the attendance in Sangola?" → average attendance for the last three months (trusted records only).
- [ ] "How many teacher posts are vacant in Mohol?" → working teachers, sanctioned posts, vacancies.
- [ ] "What about Bhalwad Khurd kendra?" (or "भाळवड खुर्द केंद्राची हजेरी किती आहे?") → the kendra's status, schools,
  results, attendance and visits; Pandharpur's brief opens below.
- [ ] "Which block needs most attention?" → "Pandharpur (3 clusters), Karmala (1 cluster), Madha (1 cluster)".
- [ ] "Compare Pandharpur and Sangola maths results" → one line for each block, and a note that the brief is about Pandharpur.
- [ ] "Which block has the best maths results?" → the top 3 blocks with their maths figures; "Which block has the lowest PTR?"
  and "कोणत्या तालुक्यात हजेरी सर्वात कमी आहे?" work the same way.
- [ ] "Bhalwad Khurd kendra in Sangola" → Pandharpur's brief, with a note that the kendra is in Pandharpur.
- [ ] "hello" → a help message with example questions. "What is the weather in Pandharpur?", "Best hotels in Pandharpur" are
  refused; "Which teacher in Pandharpur is absent most often?" is refused (no questions about individual people).
- [ ] For the best answers to new wordings, run with `KAARAN_LLM_MODE=live` (needs `ANTHROPIC_API_KEY`; the intent model
  costs a fraction of a cent per question). In `replay` mode, questions that were not recorded use the rule matcher.

**E7 WhatsApp simulator**: open **http://127.0.0.1:8000/whatsapp**
- [ ] A welcome message appears.
- [ ] Click **🔔 इशारा पाठवा / Send alert**. The alert for Pandharpur arrives.
- [ ] Type **अहवाल**. A "checking…" message, the summary, then a **PDF** bubble arrive. Click the PDF.
- [ ] Type `english`, then ask "Which clusters in Pandharpur need attention?". The reply comes in English.

**E7b Voice** (needs `SARVAM_API_KEY` in `.env`; the buttons are hidden without it)
- [ ] On `/`, click **🎤 बोला**, allow the microphone, say "पंढरपूर तालुक्यात कोणत्या केंद्रांकडे लक्ष द्यावे?", click
  **⏹ थांबवा**. The heard text appears ("🎤 ऐकले: …") and the brief opens.
- [ ] Click **🔊 आवाजात ऐका**. A Marathi voice of about 40-60 s plays: what needs attention, why, what to do.
  The second play is instant (cached).
- [ ] On `/whatsapp`, press 🎤, speak, and stop. You get the heard text, the summary, the PDF and an audio bubble with the
  voice summary.
- [ ] Say "english" by voice. The bot switches language (spoken commands work like typed ones).

**E8 Real data page**: open **http://127.0.0.1:8000/real** (run Part F first)
- [ ] The green "REAL PUBLIC DATA" bar is visible, followed by the Solapur block table, the PRS benchmarks,
  the 2019-20 cross-check and "Checks" all ✓.

Stop the server with **Ctrl+C**.

---

## Part F · Real data (level 2)

Real files live only in `data/real/`, which git ignores. They are never committed.

```
.venv\Scripts\python -m kaaran.real --udise data/real/udise_2425 --aikosh data/real/aikosh/UDISE_plus-19-20_teachers_solapur_mah.csv --benchmarks data/real/prs2024/benchmarks.json
```
✅ Prints `SOLAPUR 2024-25: 2900 schools in 13 blocks` and `checks: 11/11 passed`.
It writes `data/real/reports/real_snapshot.md` (open it in VS Code) and `real_snapshot.json` (used by `/real`).

What the checks mean:

| Check | Meaning |
|---|---|
| `unique_ids_*` | no school appears twice |
| `same_schools_*` | the profile, visits and teacher files cover exactly the same schools |
| `enrolment_ids_known` | the enrolment file has no unknown schools |
| `single_district`, `class_range`, `teachers_non_negative`, `crc_visits_plausible` | values are in sensible ranges |
| `local_body_mapping_vs_2019_20` | our "local body = code 3" assumption matches the independent 2019-20 tables (teacher totals per block) |

If a check fails, the command stops and reports the problem instead of producing numbers. This is rule 4:
check the data before analysing it.

---

## Part G · Optional: generate data yourself

```
.venv\Scripts\python -m kaaran.synth3 --seed 42 --out data/synthetic/block_demo
.venv\Scripts\python -m kaaran.synth3 --seed 7 --names fictional --out data/synthetic/block_demo_fictional
```
✅ "18 raw files". Open `data/synthetic/block_demo/raw/` in Excel to see the real-format files:
UDISE+ columns, Marathi/English headers, the SYNTHETIC marker in the first cell, and messy bits on purpose.
`truth3.json` is the answer key.

---

## Part H · If something goes wrong

| Problem | Fix |
|---|---|
| `No module named kaaran` | run the setup again (Part B), and always use `.venv\Scripts\python` |
| Web page shows "डेटा तयार होत आहे…" for a long time | the first start generates data; wait about 30 s and reload |
| PDF button says "PDF unavailable" | install Edge or Chrome, or set `KAARAN_BROWSER` in `.env` to the browser's .exe path |
| A brief shows "मजकूर: ठरावीक साचे" (templates) | normal for blocks without a recorded AI answer; the numbers and actions are identical |
| `/real` says "No real-data snapshot" | run Part F first |
| Port 8000 busy | `.venv\Scripts\python -m kaaran.api --port 8010` |
