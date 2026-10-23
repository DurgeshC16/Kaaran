# Kaaran: Progress

Deadline: 2026-11-01 (submit by afternoon).
Budget: development <= $180, runtime/evals <= $60, demo/judging <= $40. Reserve untouched.
Cumulative checkpoints: $60 by Oct 22, $130 by Oct 25, $200 by Oct 29.

## Current phase: 4 next (web demo + PDF, Oct 27-29). Phase 3 (AI layers) done 2026-10-23.

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
Phase 4 (Oct 27-29), web demo + PDF:
- FastAPI app: question (text, Marathi recording later) + file upload -> intent -> ingest (LLM mapping, rule fallback) -> trust -> analyze -> brief.
- Devanagari one-page PDF of the brief.
- School drill-down from the full pack, done in code (never from the LLM).
- Show the SYNTHETIC banner everywhere.
- Native-speaker review of data/samples/brief_seed*_mr.md, in parallel with user testing.

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

## Spend ledger
| Date | What | Spend ($) | Cumulative ($) |
|------|------|-----------|----------------|
| 2026-10-23 13:55 | Phase 1 + Phase 2 stages 0-3 (incl. three Opus plan reviews) | 35 | 35 |

## Schedule (re-planned 2026-10-23)
- Phase 2, deterministic core engines: Oct 23-25
- Phase 3, AI layers: Oct 25-27
- Phase 4, web demo + PDF: Oct 27-29
- User testing: in parallel, until Oct 28
- Hardening and deploy: Oct 30
- Video and deck: Oct 31
- Submit: Nov 1 afternoon
