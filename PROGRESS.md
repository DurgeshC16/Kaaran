# Kaaran: Progress

Deadline: 2026-11-01 (submit by afternoon).
Budget: development <= $180, runtime/evals <= $60, demo/judging <= $40. Reserve untouched.
Cumulative checkpoints: $60 by Oct 22, $130 by Oct 25, $200 by Oct 29.

## Current phase: 2 (Deterministic core engines, no LLM; Oct 23-25)

Phase 1 (Foundation): done 2026-10-23 (synthetic generator, 27 tests, see "Phase 1 result").

Phase 2 stages:
- [x] Stage 0: housekeeping (schedule, slow marker, CLAUDE.md commands and git rule)
- [x] Stage 1: evidence contract (docs/EVIDENCE_SCHEMA.md, sample evidence pack)
- [x] Stage 2: ingest (raw files -> DuckDB with provenance, mapping JSON, ingest report, round trip)
- [x] Stage 3: trust checks (flat runs, jumps, missing data, duplicates; docs/CONFIDENCE_RULES.md)
- [ ] Phase 2B: causes, twins, confidence rules, eval harness (Oct 24-25)

Phase 3 prerequisite: auth works (`/status` shows the API key) and model set; first needed in Phase 3.

## Phase 2 result so far (Stages 0-3, 2026-10-23)
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
Phase 2B (Oct 24-25): causes/ (vacancy, election, infrastructure), twins/ (size, enrolment, election duty; poverty caveat), confidence.py with TREND/CAUSE/TWIN/ACTION thresholds in docs/CONFIDENCE_RULES.md, pipeline.py building the full evidence pack (replace the illustrative sample), eval/ scorecard vs ground_truth.json on 3 seeds.

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
