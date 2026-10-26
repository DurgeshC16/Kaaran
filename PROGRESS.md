# Kaaran: Progress

Deadline: 2026-11-01 (submit by afternoon).
Budget: development <= $180, runtime/evals <= $60, demo/judging <= $40. Reserve untouched.
Cumulative checkpoints: $60 by Oct 22, $130 by Oct 25, $200 by Oct 29.

## Current phase: v2 rethink (after mentor review 2026-10-24). Docs 01-08 written 2026-10-27; implementation = Phase 5 (docs/07).

v2 in one line: block -> cluster lens, 4 data domains in real formats (UDISE+ microdata), three-part brief (attention / why / what to do), decision rubric for actions, proactive alerts, baithak pack, voice. Plan and stages: docs/07_ROADMAP_AND_PHASES.md.

Phase 4 stages:
- [x] Demo service, HTML/PDF brief, web demo with click-to-source and school drill-down
- [x] WhatsApp: Cloud API webhook (signature, dedupe), bot (summary + PDF), local simulator
- [ ] Voice in (Marathi speech-to-text) and voice summary out
- [ ] Officer file upload (web), then WhatsApp media
- [ ] Deploy (public link) + real Meta test number connected

Phase 3 stages:
- [x] Stage 0: LLM foundation (anthropic 2.1.0, wrapper with cache/replay, usage log, spend cap; auth + model ids verified live)
- [x] Stage 1: mapping proposer (Messy-File Reader) + variant_b hold-out layout
- [x] Stage 2: intent parser
- [x] Stage 3: Brief Writer (Marathi + English, placeholders)
- [x] Stage 4: verifier
- [x] Stage 5: guardrail tests + brief eval + sample briefs

Phase 2 (deterministic engines): done 2026-10-23.
Phase 1 (Foundation): done 2026-10-23 (synthetic generator, 27 tests, see "Phase 1 result").

Phase 2 stages:
- [x] Stage 0: housekeeping (schedule, slow marker, CLAUDE.md commands and git rule)
- [x] Stage 1: evidence contract (docs/EVIDENCE_SCHEMA.md, sample evidence pack)
- [x] Stage 2: ingest (raw files -> DuckDB with provenance, mapping JSON, ingest report, round trip)
- [x] Stage 3: trust checks (flat runs, jumps, missing data, duplicates; docs/CONFIDENCE_RULES.md)
- [x] Phase 2B: Stage 4 causes, Stage 5 twins (+ taluka profile file), Stage 6 analyze + eval harness, Stage 7 real sample pack

Phase 3 prerequisite: auth works (`/status` shows the API key) and model set; first needed in Phase 3.

## Phase 5 result (2026-10-27): block lens + decision rubric
- 5.1 `kaaran.synth3`: v3 district (block -> cluster -> school, 1,292 schools).
  - 18 real-format raw files (UDISE+ microdata columns, kendra list, monthly posts with duty days, monthly attendance, competency-wise assessment in 3 rounds, visit log, training register).
  - 11 planted scenarios with expected diagnoses and actions (truth3.json).
- 5.2 `block/ingest.py`: bilingual header recognition, provenance on every row, fixes reported; round trip 100%.
- 5.3 `block/trust.py`: flat runs, missing data, implausible combination, honest-low cleared, cluster data / insufficient alerts.
- 5.4 `block/insights.py`:
  - Risk scanner, with broad-drop and pocket routes, chronic absence and low level.
  - Diagnosis D1 staffing, D2 support (cluster visit drop), D3 absence, D4 migration, D5 duty (ruled out), D6 data, D7 competency (level-based), D8 none.
  - STRONG needs effect + share + replication + no pre-trend.
  - Positive deviants are analysed separately; surplus schools; twin/decoy block.
- 5.5 `block/rubric.py` + `rubric_v1.json`: A1-A13 with constraint checks; skipped rows are logged with the failed constraint.
- 5.6 `block/pack.py` (schema block-1.0, reuses filler/writer/verifier) + `block/brief.py`: three-part brief (A attention / B why / C what to do), Markdown, interactive HTML, print HTML.
- 5.7 `eval/block.py`: **19/19 on seeds 42, 7, 99, 2026, 11, 77** (risk recall, never-at-risk, 4 diagnoses, competency subset, duty, insufficient, honest, flat, positive deviant, surplus, twin/decoy, 5 rubric actions).
  - Calibration over 60 seeds: ~98% recall, ~3% extra flags (documented noise from small schools).
- LLM writer for block briefs:
  - Sonnet: 22/23 findings first attempt, 1 after retry, verified, about $0.08 per brief.
  - Haiku ran past its 16k output limit on this JSON, so it stays on intent only.
- Live spend this phase: ~$0.17.
- Tests: 227 passed, 3 skipped.

## Phase 4 result, part 1: web + WhatsApp demo (2026-10-24)
- Run: `python -m kaaran.api` -> http://127.0.0.1:8000 (web), /whatsapp (simulator), /whatsapp/webhook (Meta). Setup and demo script: docs/DEMO.md.
- `src/kaaran/service.py`:
  - Datasets: `solapur` (seed 42) and `fictional` (seed 7), generated if missing.
  - Ingest, trust and all taluka packs are built once per dataset (about 5 s). Briefs and PDFs are cached.
  - `ask()` runs intent -> clarify | refuse | brief, then a code-built summary with "which section answers you" notes.
- `brief/html.py` + `brief/pdf.py`: interactive HTML (numbers and school counts are click targets) and a one-page A4 PDF via headless Edge/Chrome (Devanagari shaped correctly; about 2 s).
- Web UI (no external resources): Marathi/English toggle, examples, history, PDF/evidence downloads, drawers for sources (file, sheet/page, rows, derivation) and school/taluka lists.
- `whatsapp.py`:
  - Graph v26.0 client: text messages, PDF upload to /media, document messages.
  - Webhook: HMAC-SHA256 check of X-Hub-Signature-256 (POST rejected without the app secret), message-id de-duplication.
  - Background processing; masked event log.
  - Commands: help, english, marathi. Typed questions only.
- Recorded for the offline demo: example-question intents (14, all correct) and AI wording for all 22 briefs (11 talukas x 2 datasets). All 22 passed the verifier on the first attempt, with 0 template fallbacks.
- **Live spend: $0.64** (about $0.03 per brief).
- Fix: the Markdown brief shows "why did it fall?" only when the trend is a decline.
- Tests: 203 passed, 3 skipped (live), full suite about 5 min. New: test_service, test_whatsapp, test_api.
- Not done in this part: voice in/out, file upload, template messages after 24 h, deploy, connecting a real Meta number (needs the user's credentials and a tunnel).

## Phase 3 result (2026-10-23)
- LLM layer (`src/kaaran/llm`): anthropic 2.1.0. The wrapper has a replay cache (`llm_cache/`, 62 recordings committed), a usage log and a per-process spend cap. Tests and evals replay offline; live is opt-in (`pytest --live`, `KAARAN_LLM_MODE=live`).
- Mapping proposer (Messy-File Reader), seeds 42, 7 and 2026:
  - default layout: baseline 100%, LLM 100%;
  - hold-out variant_b: baseline 0% (invalid), LLM 100% on the first attempt, scorecard 8/8;
  - about $0.05 and 13-15 s per proposal.
- Intent parser (25 questions): LIGHT/Haiku 92% (misses conservative), MAIN/Sonnet 100%, rule fallback 88%. LIGHT kept; about $0.0002 per question.
- Brief Writer + verifier (5 seeds: 42, 2026, 1, 99, 7 fictional): first-attempt verifier pass 100% (12/12 findings), 0 template fallbacks, **0 invented numbers**, **about $0.049 and 17-19 s per brief** (claude-sonnet-5-5).
  - Template fallback brief when the API is unavailable.
  - Samples for native-speaker review: `data/samples/brief_seed42_mr.md`, `brief_seed2026_mr.md`, `brief_seed7_fictional_mr.md` (+ `_en`).
- Prompt injection: an instruction in a spreadsheet header plus a short instruction cell reached the model as data and did not change the mapping. Longer injected text is masked out of the summary.
- **Live spend in Phase 3: $0.84** (67 calls: mapping $0.39, briefs $0.34, intent $0.11, auth $0.0006).
- Tests: 167 passed, 3 skipped (live); full suite about 3 min.

## Phase 2B result (2026-10-23)
- Causes: `src/kaaran/causes` covers the trend (paired t, ranks, persistence) and 4 hypotheses: election duty, maths vacancy, infrastructure, attendance. Labels come from `src/kaaran/confidence.py`; thresholds are in docs/CONFIDENCE_RULES.md.
- Twins: `src/kaaran/twins` uses standardised school count, enrolment and poverty, with the same heavy election-duty years; it picks the most similar improver and reports the decoy. Poverty arrives in a 7th raw file, `taluka_profile.csv`.
- Pipeline: `python -m kaaran.analyze <raw> --focus Pandharpur --out pack.json` builds a validated, pruned evidence pack with an outline and actions. `data/samples/evidence_pandharpur.json` is now real engine output, and a test checks it equals a fresh run.
- **Scorecard** (`python -m kaaran.eval --seed N`, raw files only): seeds 42, 7 (fictional names), 2026, 1 and 99 each score **8/8**, with 0 wrong verdicts, 0 false flags (T8: 0), 0 invented numbers (of 38) and 0 provenance mismatches (35 queries re-run).
- Tests: 109 passing (full, about 2 min).

## Phase 2 result, Stages 0-3 (2026-10-23)
- Contract: docs/EVIDENCE_SCHEMA.md v1.0, src/kaaran/evidence.py (validate / finalize / llm_view), sample data/samples/evidence_pandharpur.json (illustrative until 2B regenerates it).
- Ingest: `python -m kaaran.ingest <raw> --db <db>`, about 2.5 s. Rule-based mapping JSON (committed as data/samples/mapping_baseline.json), validated against a closed vocabulary; 6 canonical tables + links/fixes/unresolved/sources in DuckDB, every row with src_* provenance. Round trip vs clean tables 100% on seeds 42, 7 (fictional names), 2026.
- Trust: `python -m kaaran.trust --db <db>`, about 1 s. From the RAW files: all 53 T5 schools flagged, Pandharpur the only RED_FLAG taluka, Mangalvedha the only INSUFFICIENT taluka (set = T6 exactly), no T8 school flagged and all 15 CLEARED. Same result on 20 more seeds (table in docs/CONFIDENCE_RULES.md).
- Tests: 86 passing (full, about 66 s); fast suite (`-m "not slow"`) about 35 s.

## Phase 1 result
- Generator: `python -m kaaran.synth --seed 42 --out data/synthetic/demo [--names fictional] [--clean-only]`, about 5 s.
- Output: 6 clean parquet tables, 6 messy raw files, ground_truth.json (T1-T8 + messiness log), manifest.json.
- Tests: 27 passing (about 40 s, mostly PDF parsing). `KAARAN_TEST_SEED=<n>` reruns the suite on another seed; truth tests passed on 20+ seeds, raw tests on 4.
- Code: src/kaaran/synth/{config,rng,entities,plant,tables,ground_truth,messy,writers,generate,__main__}.py; tests/{conftest,test_smoke,test_truths_clean,test_raw_files,test_cli,test_determinism}.py.

## Next task
Phase 6 (docs/07):
- 6.1 Block lens in the service, web and WhatsApp: question -> block brief; proactive district scan -> alerts inbox + WhatsApp alert.
- 6.2 Baithak pack (all rubric actions with owners) + action tracker.
- 6.3 Voice through a hosted API (team approved hosted for the demo; needs an API key: Bodhan AI / Sarvam / Bhashini).
Then Phase 7: real data run (user downloads per docs/08), user tests, deploy.

## Decisions
- 2026-10-23 Repo layout: project flattened from kaaran-starter/ to the repo root.
- 2026-10-23 docs/source/ (original problem statement, deck, guidelines) is local-only and git-ignored. docs/PROJECT_CONTEXT.md is the distilled version.
- 2026-10-23 Git workflow: commit + push after every green stage; message format `phaseN: ...` with a body (see CLAUDE.md).
- 2026-10-23 T1/T3 fix (option A): keep 11 vacancy schools; Pandharpur taluka drop is >= 3 points (planted -3.31), not >= 8. All T1-T8 numbers made consistent as a set; final table in docs/SYNTHETIC_DATA_SPEC.md (v2).
- 2026-10-23 T2: the unrelated dipper (Akkalkot) dips 1.5, less than Pandharpur's 2.06 in the election year; the 5 other election talukas stay within +/-1.
- 2026-10-23 UDISE-style codes use the non-existent state prefix "00" (real leading-zero loss, no collision with real codes).
- 2026-10-23 Attendance PDF covers calendar 2024 only (about 13k rows); full history stays in clean tables.
- 2026-10-23 Thresholds are on group means; T7 |r| < 0.1 enforced by deterministic redraw.
- 2026-10-23 Determinism: Excel re-zipped with fixed timestamps, reportlab invariant mode; identical hashes guaranteed only for the same pinned library versions.
- 2026-10-23 Conventions: bare year in PAT CSV = end year (2024 = 2023-24); duplicates are exact; CSV SYNTHETIC marker is a title line (skiprows=1); PDF English only.
- 2026-10-23 Messiness log: every injected messiness item is recorded in ground_truth.json.
- 2026-10-23 Taluka names: real Solapur names stay the default; a fictional set ships alongside; switch with one config line (or --names fictional). SYNTHETIC marker in every file and report title.
- 2026-10-23 T5 scattered schools are spread 3-4 per taluka (random picking concentrated 8 in one taluka).
- 2026-10-23 Raw-layer PDF omissions never touch planted T5/T6/T8 schools, so raw gaps cannot push a school over the T6 rule.
- 2026-10-23 Library versions pinned exactly in pyproject.toml (hash identity depends on them).
- 2026-10-23 Dependencies approved: numpy, pandas, pyarrow, openpyxl, reportlab, pdfplumber, pytest. Fuzzy matching uses stdlib difflib; config is Python/JSON (no PyYAML).

- 2026-10-23 Phase 2 plan approved with the recommended defaults, adjusted after a read-only 3-lens review:
  - DuckDB (pinned) is the store; `<data_dir>/kaaran.duckdb`, git-ignored.
  - PDF text via pypdfium2 (0.3 s vs 15 s); pdfplumber kept only for independent cross-check tests (marked slow).
  - Poverty index: no raw file has it. Deferred: twins match on size, enrolment, election duty with a "poverty not available" caveat; a taluka profile file only if time remains after 2B.
  - Round trip: expected rows = clean rows the raw files should contain (attendance = PDF months minus logged omissions), matched at 100%; omissions must appear as missing in trust.
  - Labels: the six requested + RULED_OUT (cause tested, no link) + CLEARED (low but natural, passed trust). DATA findings use RED_FLAG / INSUFFICIENT / CLEARED only.
  - Ingest fixes (dedup, name-matched links, normalisation) never count as flags; only trust labels do.
  - Expected attendance months = months present in the file (10), not 12.
  - Bare-year convention auto-detected (end-year gives 0 duplicate school-years, start-year 821).
  - 2B stats: numpy only (t-statistics, effect sizes); constants get their own rationale, never copied from ground_truth.json.
  - Tests: fast = `-m "not slow"`, full suite before every commit; no default addopts change.

- 2026-10-23 Stage 1 schema shaped by a read-only contract review: top-level registries (numbers, entities, sets, periods), provenance = cells | query | constant, outline decided by rule, llm_view for rule 5, {{n:<id>}} placeholders recommended for the Phase 3 Brief Writer.
- 2026-10-23 Attendance jumps are judged against the school's own history (deseasonalised); a district-wide z flagged honest T8 schools.
- 2026-10-23 Persisting score jumps are trust annotations for the cause tester, not flags; only reverting spikes are flagged.
- 2026-10-23 Name matching for crosswalk gaps is a one-to-one assignment within the taluka (a unique-best rule left two near-identical names unresolved on seeds 1-2).
- 2026-10-23 Trust inputs are ingested raw data; "expected months" = months present in the file for the taluka.
- 2026-10-23 Phase 3 Brief Writer: Claude writes `{{n:<id>}}` placeholders; code fills in the Marathi figures (display.mr) from the evidence pack.
- 2026-10-23 Phase 3 mapping proposals: Claude sees only headers plus columns with few distinct values (e.g. taluka spellings, होय/नाही); never school names, codes or numbers.
- 2026-10-23 Phase 2B: correlational hypotheses (infrastructure, attendance) are tested on schools not exposed to a STRONG school-level cause. Without that, seed 42 showed a chance attendance correlation (t -3.2) driven by the vacancy schools; it now reads "inconclusive".
- 2026-10-23 Phase 2B: template registry v2. WEAK uses "associated with" keys, RULED_OUT uses "no link" keys, INSUFFICIENT uses `cause.inconclusive`. The validator rejects the causal key `cause.vacancy.concentrated` unless the label is STRONG.
- 2026-10-23 Phase 2B: election duty is never STRONG (taluka-level exposure, about 7 units); twins must have exactly the same heavy election-duty years.
- 2026-10-23 Phase 2B: poverty arrives as a 7th raw file (taluka_profile.csv, percentages); without it, twins drop the covariate and add caveat.poverty_not_available.
- 2026-10-23 Phase 2B: packs keep district-wide RED_FLAG/INSUFFICIENT findings as appendix context, but only the focus taluka's CLEARED list.
- 2026-10-23 Phase 2B: the eval re-runs every query provenance. It found 3 real provenance errors (the correlations cited more rows than they used), now fixed.
- 2026-10-23 (user) taluka_profile.csv stays as the 7th raw file.
- 2026-10-23 (user) The "attendance tested, inconclusive" line appears only in the brief's appendix.
- 2026-10-23 Phase 3 plan approved with the recommended defaults:
  - Models from env: MAIN claude-sonnet-5-5, LIGHT claude-haiku-5-5 (.env.example).
  - Server-side refusal fallback ("default") on MAIN calls.
  - Recorded LLM responses are committed in llm_cache/ (synthetic inputs only), so tests, evals and the demo replay offline.
  - Spend cap per process: KAARAN_MAX_LIVE_USD=15. Live tests are opt-in with `pytest --live`.
  - Claude writes {{n:}}, {{e:}}, {{s:}} and {{p:}} placeholders; code fills values and names.
  - variant_b layout covers the xlsx and csv files; the PDF stays rule-parsed.
  - Brief output is Markdown (mr + en); the PDF comes in Phase 4. The Marathi wording needs native-speaker review.
- 2026-10-23 LLM settings resolve environment > .env > .env.example, so model ids are never hard-coded. ANTHROPIC_API_KEY comes from the environment.
- 2026-10-23 Intent parser stays on LIGHT (claude-haiku-5-5). 25 questions: LIGHT 92% (both misses conservative: it asked or refused, never a wrong taluka), MAIN 100%; the rule was to switch only if LIGHT is >10 points worse. Cost per question about $0.0002 (LIGHT) vs $0.0043 (MAIN).
- 2026-10-23 Prompts are not tuned on the eval questions (to avoid overfitting the 25-question set).
- 2026-10-23 Correlational wording fix: the "association, not cause" caveat goes on WEAK findings only.
- 2026-10-23 Brief prose is per finding (not per section), so the verifier can check that placeholders belong to the finding. Marathi case endings go on "तालुका" (stem changes of place names need a native form).
- 2026-10-23 The verifier allows the connective "त्यामुळे" (therefore) and negated causal sentences. Every other causal word outside a STRONG cause fails.
- 2026-10-24 Phase 4 demo scope (user): typed questions only, on the existing synthetic datasets. Voice in/out and file upload through WhatsApp are deferred.
- 2026-10-24 Dependencies added for the demo: fastapi 0.161.1, uvicorn 0.54.0, httpx 0.28.1 (pinned). File upload would need python-multipart (not added).
- 2026-10-24 PDF = the print HTML rendered by headless Edge/Chrome (reportlab cannot shape Devanagari). Without a browser, the PDF link returns 503 and /print serves the HTML.
- 2026-10-24 One brief type per taluka (the evidence pack). The question decides the taluka, and a code-written note points to the section that answers it. Comparisons answer the first taluka and ask for a second question.
- 2026-10-24 Replies are Marathi first. WhatsApp switches language per sender with "english" / "marathi".
- 2026-10-24 WhatsApp webhook POSTs must carry a valid X-Hub-Signature-256. Without WHATSAPP_APP_SECRET every POST is rejected (no unsigned mode).
- 2026-10-24 The brief and PDF never name schools (verifier). School lists appear only in the local web drill-down.
- 2026-10-24 Mentor review (Rupala, CSF): proactive nudges instead of waiting for questions; data availability matrix; 4 core domains; three-part brief; decision rubric for actions (main weakness); baithak loop; OCR out of scope; check Bodhan AI for voice.
- 2026-10-27 v2 rethink documented (docs/01-08, README). Real UDISE+ 2024-25 school-level microdata format verified (public Delhi release; pseudocode IDs; no cluster column). PRS 2024 Solapur: grade 3 maths 75 / MH 64 / India 60, language 79 / 69 / 64 (checked on the rendered page; PDF text order is misleading). Real PRS PDF moved to data/real/prs2024/.
- 2026-10-27 (team) Phase 5 approved as planned; voice via a hosted API for the demo; LLM budget "most feasible for end users".
- 2026-10-27 Block brief writer uses Sonnet (Haiku hit its output limit on the ~25-finding JSON). Cost is about $0.08 per block per data refresh (briefs are cached), about ₹4 per block per month.
- 2026-10-27 Risk = school-level paired change relative to the block median (removes district-wide events), ML + EL rounds. Pocket rule only on both subjects together; chronic absence (Dec-Mar) is an attention item on its own.
- 2026-10-27 Support gap is judged at cluster level (Kendra Pramukh post), since per-school visit counts are too noisy (Poisson). Positive deviants are excluded from exposure tests and shown separately. Timing = no pre-trend vs unexposed schools.
- 2026-10-27 Competency focus uses current levels vs the block's profile (not changes), which halves small-school noise. The answer key checks that every reported competency is a planted one.
- 2026-10-27 Exclusive data actions: a cluster with unreliable records gets only "verify registers"; its results are not acted on until verified.
