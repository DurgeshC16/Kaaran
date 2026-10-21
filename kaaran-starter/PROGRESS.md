# Kaaran: Progress

Deadline: 2026-11-01 (submit by afternoon).
Budget: development <= $180, runtime/evals <= $60, demo/judging <= $40. Reserve untouched.
Cumulative checkpoints: $60 by Oct 22, $130 by Oct 25, $200 by Oct 29.

## Current phase: 1 (Foundation, Oct 18-19)

- [ ] Auth works (`/status` shows the API key), model set (`/model opusplan`)
- [ ] Repo initialised, private GitHub remote, first commit pushed
- [ ] Plan for scaffold + generator approved
- [ ] Scaffold: pyproject, package layout, pytest runs
- [ ] Clean truth tables with planted truths T1-T8 + ground_truth.json
- [ ] Tests prove each planted truth from the clean tables
- [ ] Messiness layer + raw file writers (xlsx, csv, pdf)
- [ ] Determinism test (same seed -> identical hashes)
- [ ] PROGRESS.md updated, pushed

## Next task
Get the plan for the scaffold and generator approved (see docs/SYNTHETIC_DATA_SPEC.md).

## Decisions
(none yet)

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
