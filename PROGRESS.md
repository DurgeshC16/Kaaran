# Kaaran: Progress

Deadline: 2026-11-01 (submit by afternoon).
Budget: development <= $180, runtime/evals <= $60, demo/judging <= $40. Reserve untouched.
Cumulative checkpoints: $60 by Oct 22, $130 by Oct 25, $200 by Oct 29.

## Current phase: 1 (Foundation, Oct 18-19; running late, now Oct 23)

- [ ] Auth works (`/status` shows the API key), model set (`/model opusplan`)
- [x] Repo initialised, GitHub remote (origin DurgeshC16/Kaaran, branch main), first commit pushed
- [x] Plan for scaffold + generator approved (2026-10-23)
- [x] Housekeeping: repo flattened, CLAUDE.md git workflow, spec v2
- [ ] Scaffold: pyproject, package layout, pytest runs
- [ ] Clean truth tables with planted truths T1-T8 + ground_truth.json
- [ ] Tests prove each planted truth from the clean tables
- [ ] Messiness layer + raw file writers (xlsx, csv, pdf)
- [ ] Determinism test (same seed -> identical hashes)
- [ ] PROGRESS.md updated, pushed

## Next task
Scaffold: .venv (Python 3.11), pyproject, package layout, smoke test.

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
- 2026-10-23 Dependencies approved: numpy, pandas, pyarrow, openpyxl, reportlab, pdfplumber, pytest. Fuzzy matching uses stdlib difflib; config is Python/JSON (no PyYAML).

## Spend ledger
| Date | What | Spend ($) | Cumulative ($) |
|------|------|-----------|----------------|

## Phases ahead
2. Core engines, no LLM (Oct 20-22): store, trust checks, cause tester, twin finder
3. AI layers + eval harness (Oct 23-25): file reader, intent parser, brief writer, verifier
4. Interface (Oct 26-27): web demo, voice, Devanagari PDF
5. Users + real data (Oct 28-29)
6. Hardening + deploy (Oct 30)
7. Video + deck (Oct 31)
8. Submit (Nov 1)
