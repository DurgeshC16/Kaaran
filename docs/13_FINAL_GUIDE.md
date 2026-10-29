# 13 · Final guide: what Kaaran is, what we built, how to demo it, and answers to the product owner

> For the team (recording the video, presenting) and for judges. Written 2026-10-29.
> Every figure comes from the repository: PROGRESS.md, docs/09_PROGRESS_REPORT.md, or commands run on
> 2026-10-29 in replay mode (no AI cost). Items marked **TODO** were not verifiable when this was written.
> Demo data is **SYNTHETIC** (made up, in real government formats). Real public data is used only as aggregates.

---

## 1. Kaaran in one minute

**The problem.** A Block Education Officer (BEO) in Maharashtra looks after 150-300 schools in 10-20 clusters
(kendras). A District Education Officer (DEO) looks after all the blocks. Every month data arrives: attendance,
teacher posts, assessment rounds, and UDISE+ once a year. The data sits in separate portals and Excel sheets.
Nobody joins it or checks whether it can be trusted. The monthly review meeting (बैठक) ends with general
instructions like "improve attendance". **Officers have plenty of data. What they lack is the analysis.**

**What Kaaran is.** Kaaran (कारण, "reason") is an **AI data analyst** for these officers. It is not a dashboard
and not a chatbot. The officer asks in Marathi or English, typed or by voice, on the web or on WhatsApp.
Sometimes the officer does not even ask: new data arrives and Kaaran sends an alert. The officer gets:
- a **direct answer** in one line, computed by code;
- **kendra cards** for each cluster: what happened, why (with a confidence label from fixed rules), and what to
  do (with an owner and a deadline);
- a one-page **evidence brief** (PDF). Click any figure and you see its source file, sheet and rows;
- a short **voice reply** (Sarvam AI).

> "Existing systems give officers data. Kaaran gives them a data analyst."
> मराठी: अधिकाऱ्यांकडे डेटा भरपूर आहे; कारण त्यांना विश्लेषक देतो - काय झाले, का झाले, आणि सोमवारी काय करावे.

**The rules we never break.**
- Claude never writes a number. Code computes every figure, and every figure has a source.
- Confidence labels come from written rules.
- The wording is "associated with" unless the strong-evidence rule passes.
- Data is checked before it is analysed.
- Only aggregates reach the AI.
- Marathi comes first.
- Synthetic data is always marked SYNTHETIC.

---

## 2. Everything we built

Status as of 2026-10-29. Source: PROGRESS.md, docs/09, and the commands named below.

### 2.1 Messy-file reader + AI column mapper
- **What it does.** It reads the files an office already has (Excel, CSV, PDF) into DuckDB. Every row keeps its
  source: file, sheet or page, and row number.
- **Block-lens ingest** (`src/kaaran/block/ingest.py`):
  - recognises Marathi and English headers in **18 raw files** in real formats: UDISE+ microdata
    `prof1/prof2/tch/enr1`, the kendra list, monthly teacher posts with duty days, monthly attendance,
    competency-wise assessment in 3 rounds, the visit log and the training register;
  - reports every fix it makes;
  - round trip back to the clean tables: 100%.
- **AI column mapper** (`src/kaaran/llm/mapper.py`, called by `ingest(..., proposer="llm")` in `src/kaaran/ingest/pipeline.py`; run it with `python -m kaaran.eval --layout variant_b --proposer llm` or `python -m kaaran.eval.mapping`):
  - Claude proposes a column mapping, and code validates it against a closed vocabulary;
  - Claude sees only headers and columns with few distinct values, never school names, codes or figures;
  - on the unseen hold-out layout `variant_b`: rule baseline 0% (invalid), **Claude 100% on the first attempt**,
    scorecard 8/8 (seeds 42, 7, 2026);
  - cost about $0.05 per proposal.
  - Note: the mapper is proven on the v1 (taluka) files. The block-lens ingest currently uses the bilingual rule
    recogniser (see §5b).

### 2.2 Trust checks (before any analysis)
- **Code:** `src/kaaran/block/trust.py`. Rules are in docs/CONFIDENCE_RULES.md.
- **What it flags:**
  - flat runs (for example 100% attendance for 3 or more months);
  - missing data;
  - implausible combinations (full attendance but low results).
- **Protecting honest schools:** a school whose numbers are low but believable is **CLEARED**, so honest schools
  are not punished.
- **What happens to flagged data:** it is reported and kept out of the analysis until someone checks it. The only
  action given for such a cluster is "verify registers". Flagged data is never silently dropped.
- **Result (v1 engine):** 0 false flags on 5 seeds.

### 2.3 Cluster-lens insight engine
- **Code:** `src/kaaran/block/insights.py`.
- **Risk scanner.** Each school's change is compared with the block median, which removes district-wide events.
  It has a broad-drop route and a pocket route, plus chronic absence and low level.
- **Diagnoses D1-D8.** D1 staffing, D2 support (fewer Kendra Pramukh visits), D3 absence, D4 seasonal migration,
  D5 non-teaching duty (tested and usually ruled out), D6 data problem, D7 competency focus, D8 no clear reason.
- **STRONG label.** It needs all four: an effect, a share of schools, replication, and no pre-trend.
- **Positive deviance.** A school that improved under the same constraint is shown as "learn from".
- **Twin block.** A block similar in size and PTR is suggested for an exposure visit. A decoy block is checked
  and reported.

### 2.4 Decision rubric with Samagra Shiksha PAB funding links
- **Code:** `src/kaaran/block/rubric.py` + `src/kaaran/block/rubric_v1.json` (actions A1-A13).
- **Constraints first.** Each action has constraint checks. For example, "redeploy" is allowed only if a surplus
  school exists. A skipped action is logged with the constraint that failed.
- **Every action has:** an owner (Kendra Pramukh, BEO, DEO), a horizon (this week or this month) and a follow-up
  metric.
- **Funding links.** 7 actions are linked to **Samagra Shiksha PAB 2026-27 Maharashtra** line items, for example
  C476 p.57 (CRC academic support) and C6800 p.62 (FLN teaching material).
  - `python -m kaaran.real --pab` checks each citation against the real PAB CSV (Maharashtra rows only):
    **18/18 checks**.
- The LLM never chooses an action.

### 2.5 Evidence pack with provenance
- **Code:** `src/kaaran/block/pack.py`, schema `block-1.0` (contract in docs/EVIDENCE_SCHEMA.md).
- **What is in it:** every number has a display value in Marathi and English, an operation, and provenance. The
  provenance is a query (view, filter, row count, file) or cells.
- **Verified example** (run 2026-10-29): "Kendra Pramukh visits 1.3 per school-month" points to `visit_log.csv`,
  filter Kendra Pramukh, 2024-25, cluster schools, **439 rows**.
- `llm_view` strips schools, set members and per-school numbers before anything reaches Claude.

### 2.6 Marathi/English brief writer + verifier
- **Writer.** Claude Sonnet writes the sentences with placeholders (`{{n:id}}`, `{{e:}}`, `{{s:}}`, `{{p:}}`).
  Code fills in every figure and name (`src/kaaran/brief/render.py`, `writer.py`).
- **Verifier** (`src/kaaran/brief/verify.py`). It rejects a sentence if it has:
  - a digit, or a figure written as a word;
  - an unknown placeholder, or one that belongs to another finding;
  - a causal word outside a STRONG finding;
  - a school name;
  - Marathi text that is not mostly Devanagari.

  At brief level it also rejects a missing section heading.
  
  A rejected brief gets one retry, then falls back to fixed templates.
- **Results:**
  - **0 invented numbers** on every brief;
  - block briefs: 22/23 findings passed on the first attempt and 1 after retry;
  - cost about **$0.08 per block brief** (Sonnet). Briefs are cached per data refresh.
- **Three-part brief:**
  - **A** लक्ष देण्याची गरज (what needs attention);
  - **B** असे का होत असावे (why);
  - **C** काय करावे (what to do).

### 2.7 Direct answers (everyday questions, no LLM)
- **Code:** `src/kaaran/block/answers.py`. Facts are computed from the canonical tables, and each has provenance.
  Fixed Marathi/English templates turn them into sentences.
- **Facts:** schools, clusters, working / sanctioned / vacant posts, single-teacher schools, PTR, schools with
  PTR > 30, 3-month attendance, maths and language level and change, Kendra Pramukh visits, and flagged or
  incomplete schools.
- **Answer modes** (all verified 2026-10-29, see §3):
  - facts ("how many schools");
  - **rankings** ("which block has the best maths");
  - **district** totals ("how many schools in Solapur");
  - **multi-part** questions (three questions in one message get three answers);
  - **why it improved** (with "associated with" wording);
  - **data quality** (which kendras have suspicious records);
  - **follow-ups** after a clarification ("which taluka?" → "Pandharpur");
  - **reply language** follows the question (English question → English reply; Marathi or transliterated
    Marathi → Marathi).
- **Tolerant reading.** Misspellings and transliteration are understood ("pandharpoor madhe kiti shala ahet").
  Kendra names are matched by fuzzy Devanagari-to-Latin matching.
- **Intent eval, rule tier** (`python -m kaaran.eval.intent --tier rule`, run 2026-10-29): **96%** on 25
  questions (up from 88%). The recorded Claude tiers: Haiku 92%, Sonnet 100%. Haiku is used because it costs
  about $0.0002 per question.

### 2.8 Proactive alerts
- **When it runs:** when new data arrives, before anyone asks. Kaaran scans all 11 blocks.
- **What the officer gets:** alerts ranked by urgency, for example "🔔 New assessment results are in (2025-26).
  In Pandharpur, 3 clusters need attention now; records in 1 cluster need checking."
- **Cost:** the scan uses no LLM, so it is free and instant.
- **On WhatsApp:** the officer replies `अहवाल` / `report` and gets the brief.

### 2.9 Baithak (review meeting) pack + action tracker
- **The pack:** every rubric action grouped by owner, with the evidence lines, the follow-up metric, the funding
  line and a status (open / confirmed / done).
- **The tracker:** status is saved in `actions.json` next to the data, so next month's data can re-check whether
  the numbers moved.
- **Where:** API `/api/briefs/{id}/baithak` and `POST /api/briefs/{id}/actions`. Web: the "📋 बैठक पॅक" button.

### 2.10 Web UI with role homes
- **The web demo** (`python -m kaaran.api`, http://127.0.0.1:8000):
  - Marathi/English toggle and example questions;
  - alerts inbox;
  - direct answer first, then kendra cards, then the "📄 full evidence brief" button;
  - drawers that show the source of a figure and the list of schools;
  - PDF and evidence downloads;
  - 🎤 mic and 🔊 Listen buttons;
  - no external scripts or CDNs.
- **Role homes** (`GET /api/home?role=deo|beo`; tested in `tests/test_officer_questions.py`):
  - **DEO:** district tiles (schools 1,292, kendras 109, teachers working 4,770, vacant posts 27, PTR 26.2,
    3-month attendance 89.0%, maths 60.1% ▼1.1), the blocks that need attention, and an all-blocks table;
  - **BEO:** one block's tiles (Pandharpur: 140 schools, 12 kendras, PTR 26.5, maths 59.4% ▼2.0) and kendra cards.
  - **On the page:** a role bar ("I am: DEO / BEO", with a block picker for BEO) loads `/api/home`; the choice is
    remembered in the browser. Shareable links: `/?role=beo&block=BPandharpur`.
- **`/real`:** the real-data page (§2.13).

### 2.11 WhatsApp bot (text, voice notes, PDF, voice replies)
- **Code:** `src/kaaran/whatsapp.py`. Uses the Meta Cloud API, Graph v26.0.
- **Security:** the webhook checks the HMAC-SHA256 signature, so an unsigned POST is rejected. Message ids are
  de-duplicated, and phone numbers are masked in the log.
- **Short questions** (a figure, a ranking): the bot sends a text answer, a voice note, and "reply 'report' for
  the PDF".
- **Kendra-card questions:** the bot sends a summary, a one-page PDF and a voice note.
- **Voice note in:** the bot transcribes it, replies "🎤 I heard: ...", then answers as if it were typed.
- **Help and language:** `hi` / `मदत` gives help; `english` / `marathi` sets the reply language.
- **Simulator** at `/whatsapp` runs the same bot locally, with a "🔔 Send alert" button and a mic.
- **Real Meta test number: TODO** (not connected yet; needs Meta credentials and a public URL: the deployed Space, docs/DEPLOY.md §4, or a tunnel, docs/DEMO.md §3).

### 2.12 Voice (Sarvam AI)
- **Code:** `src/kaaran/voice/`.
- **Speech-to-text:** `saaras:v4`. Place names are passed as keyterms to help the recogniser with names such as पंढरपूर and मंगळवेढा
  (not yet measured on live audio).
- **Text-to-speech:** `bulbul:v4-flash`, Marathi and English voices, MP3. The spoken script is built by code
  from the verified summary, so it adds no new numbers. Audio is cached by text.
- **Cost** (docs/DEMO.md): speech-to-text about ₹0.49 per minute; text-to-speech roughly ₹0.6 per brief.
- **Safety:** a per-process spend cap (`KAARAN_MAX_VOICE_INR`, default 100). A failure gives a fixed bilingual
  reason, never the raw API message.
- **Without a key** the voice buttons hide and everything else works.

### 2.13 Real public data validation
- **Code:** `src/kaaran/real/`. Command: `python -m kaaran.real`. Files stay in `data/real/`, which is never
  committed.
- **UDISE+ 2024-25 microdata, Solapur:** 4,698 schools, 13 blocks. **11/11 data checks pass** (unique ids, same
  schools in every file, ranges, management mapping cross-checked against 2019-20; docs/09 §4).
- **Real findings** for ZP schools (self-reported, aggregates only):
  - 2,900 schools, 9,534 teachers, PTR 20.1;
  - **99 single-teacher schools**: Sangola 27, Malshiras 20;
  - **789 schools report no CRC visit** last year. In Solapur North it is 77 of 98 (79%);
  - Karmala has 17.5% of teachers on non-teaching work.
- **AIKosh 2019-20 cross-check:** local-body teachers are 8% lower overall, and every block is between 0.87 and
  0.97 of its 2019-20 figure.
- **PRS 2024 benchmarks** (grade 3, read from the page images): maths Solapur 75 / Sangli 68 / Satara 75;
  Maharashtra 64; India 60.
- **Teacher rationalisation (RTE norms):** 213 posts needed, 89 can be covered by redeployment, and 124 need new
  posts.
- **PAB citations:** 18/18 checks.

### 2.14 Evals and tests
| What | Result | How to reproduce |
|---|---|---|
| Block-lens scorecard vs hidden answer key | **19/19** on seed 42 (run 2026-10-29); 19/19 on seeds 42, 7, 99, 2026, 11, 77; recall ~98%, extra flags ~3% over 60 seeds | `python -m kaaran.eval.block --seed 42` |
| v1 taluka scorecard | 8/8 truths on 5 seeds, 0 false flags | `python -m kaaran.eval --seed 42` |
| Intent (25 questions) | rule 96% (run 2026-10-29), Haiku 92%, Sonnet 100% | `python -m kaaran.eval.intent --tier rule` |
| Invented numbers in briefs | 0 | `python -m kaaran.eval.brief --seed 42` |
| AI column mapper, hold-out layout | 100% (rule baseline 0%) | `python -m kaaran.eval.mapping --seed 42` |
| Prompt injection in a spreadsheet | ignored (it reaches the model as masked data) | `python -m kaaran.eval.guardrails` |
| Real data checks | 11/11 UDISE+, 18/18 with PAB | `python -m kaaran.real ...` |
| Automated tests | 289 collected. Full run on 2026-10-29 (replay, voice off): **286 passed, 3 skipped** (live-API tests, only with `--live`). The earlier xlsx byte-hash failure is fixed: `src/kaaran/__init__.py` pins `OPENPYXL_LXML=False`. | `python -m pytest -q` |
| Live AI spend so far | about $1.8 in total (docs/09) | `data/llm_usage.jsonl` |

---

## 3. Demo test cases (video and live demo)

Run with `KAARAN_LLM_MODE=replay` (free, offline). "Verified" means it was run through `Service.ask` or the
WhatsApp `Bot` on 2026-10-29 and gave the result shown. Voice cases were checked as text only (`KAARAN_VOICE=off`):
the transcript goes down the same path as typed text.

| # | Where | Input (Marathi / English) | What the viewer sees | Criterion it proves |
|---|---|---|---|---|
| 1 | WhatsApp simulator `/whatsapp` → **🔔 Send alert**, then reply | `अहवाल` / `report` | Alert: "🔔 नवीन मूल्यमापन निकाल आले (२०२५-२६). पंढरपूर तालुक्यात ३ केंद्रांना तातडीने लक्ष देण्याची गरज आहे; १ केंद्रातील हजेरीच्या नोंदी तपासायला हव्यात." Then the Pandharpur kendra summary + a one-page PDF. **Verified.** | Efficacy (proactive, nobody had to ask); Innovation |
| 2 | Web | `कोणत्या तालुक्याकडे सर्वात जास्त लक्ष द्यावे?` / `Which block needs most attention?` | "Most attention needed: Pandharpur (3 clusters), Karmala (1 cluster), Madha (1 cluster)", then Pandharpur's kendra cards. **Verified** (both languages). | Efficacy (DEO's first question) |
| 3 | Web | `पंढरपूर मध्ये किती शाळा आहेत?` / `How many schools are in Pandharpur?` | One line: "पंढरपूरमध्ये १४० शाळा आहेत (१२ केंद्रे)." / "Pandharpur has 140 schools in 12 clusters." Reply language follows the question. **Verified.** | User-centricity (Marathi first, short answers) |
| 4 | Web or WhatsApp | `pandharpoor madhe kiti shala ahet, karmala PTR kiti, mohol la shikshak kiti kami.` (misspelt, transliterated, 3 questions) | Three lines: Pandharpur 140 schools / Karmala PTR 26.5, 2 schools above 30 / Mohol 2 vacant posts, 498 working of 500 sanctioned. **Verified.** | User-centricity (real typing); Technical strength |
| 5 | Web | `गणितात सर्वात चांगला तालुका कोणता?` / `Which block has the best maths results?` | "गणिताचा सर्वाधिक सरासरी निकाल: माळशिरस ६५.२%, बार्शी ६५.२%, उत्तर सोलापूर ६३.३%." / "Highest maths results: Malshiras 65.2%, Barshi 65.2%, North Solapur 63.3%." Ranking only; the brief sits behind the button. **Verified (both).** Also `Which block has the highest PTR?` → "Mohol 26.7, Madha 26.7, Karmala 26.5" (**verified**). Do **not** use the Marathi PTR wording `सर्वात जास्त विद्यार्थी-शिक्षक प्रमाण कोणत्या तालुक्यात आहे?`: it is wrongly refused as a question about individuals (known issue, see the final report). | Efficacy |
| 6 | Web | `पंढरपूरचा निकाल का घसरला?` / `Why did Pandharpur fall?` | Direct line (maths 59.4%, 2.0 points lower; complete records for 136 of 140 schools), then **6 cards** (5 kendras + a whole-block card). Three clusters, three different reasons: Bhalwad Khurd (KP visits 1.3 → 0.1, subtraction weakest, **Strong evidence**), Bhalpur (seasonal migration, attendance about 14.7 points lower Nov-Mar), Takangaon (6 schools lost a teacher; 1 school improved anyway: **Learn from**). Also Dhanwade Khurd (**Red flag**: 7 schools with full attendance), Malpur Khurd (**Not enough data**), poll duty (**No link found**), and Malshiras as the twin block. Each card has an owner and timing. **Verified.** | Efficacy; Innovation (different causes → different actions); Guardrails (labels from rules) |
| 7 | Web | `Malshiras cha nikal changla ka aala?` / `Why did Malshiras improve?` | "maths rose 2.7 points to 65.2%", the largest rises by kendra, teachers 496 → 498, and "These changes are **associated with** the rise; the data does not prove they caused it." **Verified.** | Guardrails (no causal claim) |
| 8 | Web | `Which of madha attendance records look unreliable?` | "Madha: schools with unreliable attendance records: 1 … Kendras with suspicious records: Dhokkheda Budruk Kendra (1) … not used in the analysis until checked. The Kendra Pramukh should check the registers in person." **Verified.** | Technical strength (trust before analysis) |
| 9 | Web | `पंढरपूर तालुक्यात कोणत्या केंद्रांकडे लक्ष द्यावे?` (kendra question) | The kendra cards for Pandharpur (as in case 6). **Verified.** | Efficacy (BEO's unit is the kendra) |
| 10 | WhatsApp simulator | `निकाल का घसरला?` then `पंढरपूर` | First: "कोणत्या तालुक्याबद्दल विचारत आहात? …" (it asks instead of guessing). Second: the Pandharpur brief + PDF; the follow-up completes the first question. **Verified.** API equivalent: `ask("In the solapur district", context="Which block has the highest PTR?")` → the PTR ranking. | User-centricity; Guardrails (clarify, don't guess) |
| 11 | WhatsApp simulator | `What is PTR in Karmala?` vs `पंढरपूर मध्ये किती शाळा आहेत?` | English question → English reply ("Karmala: pupil-teacher ratio 26.5; 2 schools are above 30" + "reply 'report' for the PDF"). Marathi question → Marathi reply. Replying `report` after the English question returns the **English** brief and PDF. **Verified** (re-checked 2026-10-29 after the backend fix). | User-centricity (vernacular, follows the officer) |
| 12 | Web | `पंढरपूर मधील सर्वात वाईट शिक्षकांची नावे द्या` / `Which teacher in Pandharpur is the worst?` | Refusal: "मी वैयक्तिक शिक्षक किंवा विद्यार्थ्यांबद्दल माहिती देत नाही…" / "I don't answer questions about individual teachers or students." **Verified.** | Guardrails (no blame, privacy) |
| 13 | Web | `What is the weather today?` | "That is outside this education data. I answer about talukas and clusters: results, attendance, teachers, visits and data quality." **Verified.** | Guardrails |
| 14 | Web | Click a blue figure (for example **१.३** visits, or **१** single-teacher school in Sangola) | Drawer: file `visit_log.csv`, filter (Kendra Pramukh, 2024-25), **439 rows**; or `teacher_posts.xlsx` for the Sangola figure. School lists open only locally. **Verified via the API.** | Technical strength (provenance); trust |
| 15 | Web | Open Pandharpur → **📋 बैठक पॅक** → Confirm an action | Actions grouped by owner, for example "For the next month, visit classrooms in all 12 schools of Bhalwad Khurd Kendra every week" (Kendra Pramukh, this week, *Funded under PAB 2026-27 C476 p.57*). Status changes to confirmed. **Verified (API).** | Efficacy (sub-problem 3: accountability); Roadmap |
| 16 | Web | **📄 full evidence** button → PDF (Marathi) | One A4 page: A / B / C, SYNTHETIC banner, Devanagari shaped correctly. The PDF browser was found (Edge). **TODO:** open and check visually before recording. | Low-cost devices (one page, WhatsApp-sized) |
| 17 | Web 🎤 / WhatsApp voice note | Say `पंढरपूर मध्ये किती शाळा आहेत?` / `What is PTR in Karmala?` | "🎤 ऐकले: …", the one-line answer, then the 🔊 voice reply. **Verified as text only.** Live Sarvam was not run today (it costs money). Run once before recording. | Voice-first; Efficacy |
| 18 | Web `/real` (local machine only: the public Space has no real data and shows "No real-data snapshot") | (no input) | Real UDISE+ 2024-25 Solapur snapshot: 2,900 ZP schools, PTR 20.1, 99 single-teacher schools, 789 with no CRC visit, the 2019-20 cross-check, PRS benchmarks, rationalisation 213 / 89 / 124. The report file exists in `data/real/reports/`. | Works in real scenarios |

**For the video, pick:** 1 or 2, 6, 14, 16, 17, 4, 12, 18 (see docs/12_VIDEO_SCRIPT.md).

---

## 4. How it is useful in the market

### Who uses it, and who pays
- **Users:** the DEO (which blocks, why, and what to fix first, before the review meeting); the BEO (defend or
  correct the block's story with evidence); the Kendra Pramukh (which of the 10-15 schools to visit).
- **Buyers:**
  - **State Samagra Shiksha** (the PAB already funds the actions Kaaran recommends, see §2.4);
  - **SCERT / DIET** (owners of the assessment and of the rubric as a shared state asset);
  - **district Zilla Parishad** education departments (the pilot partner).

### How it fits existing systems (docs/01 §5, docs/05, docs/07 §4)
- **UDISE+** is the school frame and the input data. It is the same national format, and we already read it.
- **State MIS / Vidya Samiksha Kendra** would be the data source, so alerts start from the system instead of
  uploads. This is roadmap Apr-Jun 2027.
- **SCERT assessment exports** and attendance exports go through the same ingest + trust pipeline. Only a
  mapping is needed.
- **Hosting:** State Data Centre or MeghRaj (GI Cloud), for data residency.

### Cost (only figures that are in our docs)
- **AI wording:** about **$0.08 (~₹4) per block brief per data refresh** (PROGRESS.md, decision of 2026-10-27).
- **Intent:** about $0.0002 per question.
- **Free:** alerts, trust checks, analysis and actions use no AI.
- **Voice:** speech-to-text about ₹0.49 per minute; text-to-speech roughly ₹0.6 per brief, generated once
  (docs/DEMO.md).
- **State scale, order of magnitude:** 350 blocks × 4 briefs a month × $0.04 ≈ $56 a month for AI (docs/05 §5).
- **Target at state scale:** total cost per block per month < ₹500 (docs/07 §4).
- **Hosting and staff costs: TODO** (not estimated in the repo).

### Adoption path (docs/07 §4)
| When | Step | Success measure |
|---|---|---|
| Nov-Dec 2026 | Data request / MoU with a ZP education office (Solapur); rubric review with DIET/SCERT | signed request; rubric v2 |
| Jan-Mar 2027 | **One-block pilot**: weekly scans on authorised exports, monthly baithak packs, action tracking | time to answer < 5 min; ≥ 50% of flags confirmed in the field; ≥ 60% of actions accepted; weekly use |
| Apr-Jun 2027 | **District** rollout; state MIS / VSK as the data source | every BEO in the district gets a monthly brief |
| 2027-28 | **State** scale: a config pack per state, the rubric as a shared asset, self-hosted Indic speech models | < ₹500 per block per month |

---

## 5. Answers to the product owner's questions

### a) How and why are we using this kind of data? Why Pandharpur, Solapur, specific places?

**Why synthetic data.**
- Real school-level outcome data is **not public**. School-wise assessment results and monthly attendance sit
  behind state logins (SCERT, the state MIS). Monthly teacher posts sit with the ZP establishment section
  (docs/02 §3, docs/08 "Data that is NOT public").
- So we built a **synthetic district in real formats**:
  - UDISE+ microdata columns (`prof1`, `prof2`, `tch`, `enr1`);
  - a kendra list;
  - monthly teacher posts with duty days;
  - monthly attendance registers;
  - competency-wise assessment sheets in 3 rounds;
  - a visit log and a training register.
- In total: 1,292 schools, 109 clusters, 11 blocks (`kaaran.synth3`).
- **Planted, known truths** (11 scenarios in `truth3.json`) let us **measure accuracy**: did Kaaran find every
  planted problem, give the right reason and the right action, and avoid false alarms? You cannot score that on
  real data, where nobody knows the true answer.
- The engine never reads the answer key. Only `src/kaaran/eval` reads it.

**Why Solapur.**
- We downloaded and validated the **real UDISE+ 2024-25 microdata for Solapur** (4,698 schools, 11/11 checks).
- Solapur is **Marathi-speaking**.
- **PRS 2024** district benchmarks exist for Solapur and its neighbours.
- It fits the team's teacher context in Maharashtra.
- The synthetic district uses Solapur's real block names, so the demo feels real. A fictional-names version
  ships alongside (`blocks_fictional`).

**Why Pandharpur.** It is the block where the synthetic scenarios are planted:
- three clusters falling for three different reasons;
- one cluster with unreliable records;
- one with too little data;
- one positive-deviant school;
- poll duty ruled out.

This makes it the richest single example. It is **not** a claim about the real Pandharpur.

**How we keep it honest.**
- Every synthetic file, page, reply and PDF says **SYNTHETIC**.
- Real public data is used only as **aggregates** and stays in `data/real/`, which is never committed.
- The real findings (99 single-teacher schools, 789 schools with no CRC visit) are shown separately on `/real`.

> मराठी: शाळानिहाय निकाल व हजेरी सार्वजनिक नाहीत, म्हणून खऱ्या सरकारी नमुन्यांत कृत्रिम जिल्हा तयार केला व त्यात माहीत असलेली
> उत्तरे लपवली, जेणेकरून अचूकता मोजता येईल; सोलापूरचा खरा UDISE+ डेटा तपासला आहे, आणि सर्व कृत्रिम निकालांवर SYNTHETIC खूण असते.

### b) Can it be generalised to any state?

**Yes.** Most of Kaaran is the same in every state. What changes is data, not code.

| Part | Same everywhere | Changes per state | Where (file) |
|---|---|---|---|
| School frame, teachers, enrolment, support visits | **UDISE+ microdata** is national: the same `prof1/prof2/tch/enr1` columns for every state | nothing (only the state code in the file name) | `src/kaaran/block/ingest.py`, `src/kaaran/real/udise.py` |
| Learning benchmarks | **PARAKH PRS / NAS** are national | the district report to download | `data/real/prs2024/benchmarks.json` (local file, not committed; passed to `python -m kaaran.real --benchmarks`) |
| State assessment, attendance, posts exports | the canonical tables and trust rules | **layouts and header names differ** | bilingual header phrases in `src/kaaran/block/ingest.py` (`PHRASES`); **AI column mapper** for new layouts (`src/kaaran/llm/mapper.py`, 100% on an unseen layout) |
| Places (blocks, kendras) | the gazetteer is built from the data itself | the state's blocks from UDISE+; clusters from the **kendra list** (real UDISE+ microdata has no cluster column, so the list comes from the BEO office) | `kendra_list` role in `block/ingest.py`; gazetteer in `src/kaaran/llm/intent.py` |
| Analysis | trust checks, risk scan, diagnoses D1-D8, STRONG/WEAK rules | thresholds can be tuned (they are published as starting values) | `block/trust.py`, `block/insights.py`, docs/CONFIDENCE_RULES.md, docs/06 |
| Actions | the rubric engine | **the rubric JSON**: actions, owners, constraints and funding codes follow each state's PAB | `src/kaaran/block/rubric_v1.json` (today one file, for Maharashtra; one file per state is the plan) |
| Language | the placeholder system and the verifier | **text packs**: today every text is a (Marathi, English) pair; Hindi, Kannada etc. would be a new entry per text, plus native review | `src/kaaran/brief/texts.py`, `texts_block.py`, `block/view.py`; voice language codes in `src/kaaran/voice/` |
| Channels | web, WhatsApp, PDF, voice | nothing | `src/kaaran/api`, `src/kaaran/whatsapp.py` |

**Honest limits.**
- The AI mapper was evaluated on the v1 file set. Wiring it into the block-lens ingest is a small next step.
- A second language pack is not built yet.
- Each state's rubric must be reviewed by its SCERT and officers.

> मराठी: होय - UDISE+ व PARAKH राष्ट्रीय आहेत; राज्यानुसार फक्त फाइलचे नमुने (AI मॅपर), कृती-नियम (rubric JSON) आणि भाषा-पॅक बदलतात,
> विश्लेषणाचा कोड तोच राहतो.

### c) How will it access other public datasets when the region changes?

1. **Office exports.** The officer's own files (assessment, attendance, posts, kendra list) are dropped into the
   data folder, and the same ingest + trust pipeline runs.
   - Web upload is planned (stage 6.4). It needs an approved dependency (`python-multipart`), or a raw-body
     upload with no new dependency. **Not built yet.**
2. **UDISE+ public microdata.** Download it per state or district from microdata.udiseplus.gov.in after
   registration (steps in docs/08 §1). The format is the same for every state.
3. **Benchmarks.** PRS 2024 / NAS district report tables are read once per district and hand-verified against
   the page images (docs/08 §2, §5). PDF text order is unreliable.
4. **Funding.** The state's Samagra Shiksha PAB minutes. `kaaran.real --pab` verifies every rubric citation
   against the PAB CSV for that state (docs/08 §3).
5. **Future connectors.** State MIS / Vidya Samiksha Kendra APIs, so alerts start from the system with no
   uploads (roadmap 2027).

Whatever the source, the path is the same: **files → ingest (with provenance) → trust checks → analysis →
brief**. A new region means new files plus a mapping, not new code.

> मराठी: नवीन भागासाठी कार्यालयाच्या फाइल्स, UDISE+ मायक्रोडेटा आणि PARAKH/PAB अहवाल त्याच पाइपलाइनमधून जातात; पुढे VSK/राज्य MIS शी थेट जोडणी.

### d) How does it all work end to end, and what runs offline vs online?

```
 New data arrives (office files, UDISE+ export)        Officer asks (typed or voice; web or WhatsApp)
              |                                                       |
              v                                                       v
 [1] INGEST: files -> DuckDB, every row keeps            [A] VOICE -> TEXT (Sarvam STT)            ONLINE*
     file/sheet/row (rules; AI mapper for new layouts)   [B] READ QUESTION: rules + Claude Haiku   ONLINE* (rule fallback offline)
              |                                              -> closed-list plan, or "which taluka?", or refuse
              v                                                       |
 [2] TRUST CHECKS: flat runs, missing, implausible       OFFLINE      |
     -> flagged data reported, kept out of analysis                   |
              |                                                       |
              v                                                       |
 [3] INSIGHTS: risk scan, diagnoses D1-D8,               OFFLINE      |
     positive deviance, twin block, STRONG/WEAK rules                 |
              |                                                       |
              v                                                       |
 [4] RUBRIC: actions with constraints, owner,            OFFLINE      |
     deadline, follow-up, PAB funding line                            |
              |                                                       |
              v                                                       v
 [5] EVIDENCE PACK (every number + provenance) ------> [6] DIRECT ANSWER (code + fixed templates)   OFFLINE
              |                                         [7] BRIEF WORDING: Claude Sonnet writes        ONLINE* (template fallback offline)
              |                                             placeholders -> code fills numbers ->
              |                                             VERIFIER (no digits, no causal words,
              |                                             no school names) -> retry -> template
              v                                                       |
 [8] ALERTS to officers (no AI)                          OFFLINE      v
                                                        [9] OUTPUT: answer + kendra cards, PDF (headless browser),
                                                            click-to-source, baithak pack, voice reply (Sarvam TTS, ONLINE*)
```
\* Online steps all have an offline fallback, and recorded answers replay from `llm_cache/` (114 files).

| Runs offline (no internet, no AI) | Needs internet |
|---|---|
| ingest, trust checks, risk scan, diagnoses, rubric, evidence pack, alerts, direct answers, rule-based question reading, template brief, PDF, click-to-source, baithak pack | Claude (question reading for new wordings, brief wording, column mapping): recorded answers replay offline; Sarvam (voice in/out): without it, voice buttons hide; WhatsApp (Meta Cloud API) |

**When the AI is down or over budget,** officers get the same numbers, labels and actions in plainer template
wording.

> मराठी: डेटा तपासणी, विश्लेषण, कृती व आकडे पूर्णपणे ऑफलाइन कोडमध्ये होतात; इंटरनेट फक्त Claude (शब्दरचना), Sarvam (आवाज) व
> WhatsApp साठी लागते, आणि तेही नसले तरी उत्तर मिळते.

---

## 6. Constraints we worked under and how we handled them

| Constraint | What we did |
|---|---|
| **No real school-level outcome data** (it is behind state logins) | A synthetic district in **real formats**, with a hidden answer key, so accuracy is measured (19/19). Real public inputs (UDISE+ 2024-25 Solapur) are validated and shown separately. Moving to a pilot means swapping files, not code. |
| **No formal officer interviews yet** | Mentor review (Central Square Foundation, 24 Oct) changed the trigger (alerts), the brief (three parts), the actions (rubric with constraints) and the data scope (4 domains). **Team testing, round 1 (28 Oct):** "dummy answers" led to the direct-answer layer. **Round 2 (29 Oct, product owner):** the 12 questions that gave long or wrong answers became fixes plus 13 regression tests (`tests/test_officer_questions.py`). Log: `docs/USER_TESTING.md`. The team includes a government primary teacher; their structured review is not yet recorded. |
| **Budget caps** (development ≤ $180, runtime ≤ $60, demo ≤ $40) | Replay cache, per-process spend caps (`KAARAN_MAX_LIVE_USD`, `KAARAN_MAX_VOICE_INR`), Haiku for question reading, no AI in analysis or alerts. Total live AI spend about **$1.8** (docs/09). |
| **Low connectivity, low-cost phones** | WhatsApp first; a short text answer before any PDF; one-page PDF; voice note for officers who prefer listening; web page with no external scripts; everything except wording and voice works offline. |
| **Marathi quality** | Marathi first everywhere. Figures are filled by code in Devanagari digits. The headings follow the deck. Native-speaker review of the sample briefs is still pending (`data/samples/*_mr.md`; **TODO**). |
| **Short build window** | Thin end-to-end slice first, then a rethink after the mentor review. The v1 pipeline was kept working until v2 passed its eval. |

---

## 7. Submission checklist

Deadline: **1 Nov 2026, 11:59 pm** (we submit hours early). Requirements from docs/PROJECT_CONTEXT.md.

| # | Deliverable | Status (2026-10-29) | Owner |
|---|---|---|---|
| 1 | Public, testable demo link (+ any software needed) | ⏳ Dockerfile ready (uid 1000, data built into the image, replay mode, Chromium + Noto fonts) and `scripts/deploy_hf.py` (docs/DEPLOY.md); **not deployed yet** | TODO (team) |
| 2 | GitHub source code (judges check the AI usage) | ✅ github.com/DurgeshC16/Kaaran; current work is not committed yet; public/licence decision pending (open-source credit +$250) | TODO (team) |
| 3 | Public YouTube video, 3 minutes | ⏳ script ready (docs/12_VIDEO_SCRIPT.md); not recorded | TODO (team) |
| 4 | Short PowerPoint: AI in layers, guardrails, low connectivity, user testing (1-2 slides), roadmap (1-2 slides) | ⏳ `docs/Kaaran_Build_Deck.pptx` (12 slides) generated by `scripts/make_deck.py` from docs/11_PITCH_DECK.md; review the user-testing slide against `docs/USER_TESTING.md` | TODO (team) |

Build-stage rules to double-check before submitting:
- [ ] AI is central and visible in the code: `src/kaaran/llm/` (intent, mapper), `src/kaaran/brief/writer.py`
      + `verify.py`, `llm_cache/`.
- [ ] Original work from the hackathon window. Open-source libraries and APIs are listed in `pyproject.toml`.
- [ ] Full test suite green before the final commit (`.venv\Scripts\python -m pytest -q`).
- [ ] No `.env`, `data/real/` or `docs/source/` files staged (`git status`).
- [ ] SYNTHETIC banner visible in the video, the deck screenshots and the demo link.
- [ ] Real WhatsApp test number connected for the video, or say clearly that the simulator is shown.
- [x] `docs/USER_TESTING.md` written (feeds the deck's user-testing slide and the 35% criterion). Still open: the
      team teacher's structured review and any officer session.
