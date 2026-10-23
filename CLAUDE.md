# Kaaran (कारण)

AI data analyst for Block and District Education Officers (AI for Foundational Learning Hackathon, Challenge 4, sub-part 1).
An officer asks "why did X fall?" by Marathi voice note and gets a one-page Marathi Evidence Brief plus a one-minute voice summary.
Build-stage deadline: 2026-11-01. Budget discipline matters: keep sessions short and focused.

## Non-negotiable rules
1. The LLM never produces numbers. Every number is computed in Python (pandas, DuckDB, statsmodels) and carries provenance: source file, sheet or page, row or cell.
2. Confidence labels (STRONG / WEAK / INSUFFICIENT) come from deterministic rules in code, never from LLM judgment.
3. Use "associated with", not "caused by", unless the rule-based criteria for STRONG are met.
4. Trust checks run before analysis. Unreliable data is flagged and reported, never silently dropped.
5. Identifiable data stays local. Only aggregates are sent to the LLM.
6. Officer-facing output is Marathi first (Devanagari), English second.
7. All demo data is synthetic and carries a SYNTHETIC marker. Never present it as a real finding.
8. Never commit secrets (.env) or real data.

## Stack
Python 3.11+, pandas, DuckDB, statsmodels, scikit-learn, FastAPI, pytest, Anthropic SDK.
Model names come from env vars (KAARAN_MODEL_MAIN, KAARAN_MODEL_LIGHT). Never hardcode them.
The synthetic data generator (src/kaaran/synth) makes NO LLM calls and is deterministic for a given seed.

## Commands (Windows)
- Setup: `py -3.11 -m venv .venv` then `.venv\Scripts\python -m pip install -e .[dev]` (versions pinned in pyproject.toml)
- Tests: `.venv\Scripts\python -m pytest -q`
- Generate data: `.venv\Scripts\python -m kaaran.synth --seed 42 --out data/synthetic/demo`

## Layout
- src/kaaran/synth: synthetic data generator and answer key
- src/kaaran/ingest, trust, causes, twins, brief, llm, api: the engines (later phases)
- tests/: pytest suites
- data/synthetic/: generated data (git-ignored except small samples)
- docs/: specs (see docs/SYNTHETIC_DATA_SPEC.md); docs/source/ holds local-only originals (git-ignored)
- prompts/: LLM prompt templates (later phases)

## Working agreement
- Start every session by reading PROGRESS.md.
- Read docs/PROJECT_CONTEXT.md for judging criteria, product scope and MVP priorities.
- For changes touching more than two files, propose a short plan first and wait for approval.
- Do not read whole data files. Use head(), schema summaries and row counts.
- Do not add dependencies without asking. Prefer what is already installed.
- Commit after tests pass (see Git workflow).
- Keep replies short. Do not recap diffs I can see in git.
- At the end of a task, update PROGRESS.md (done, next task, decisions made).

## Git workflow
- Remote: origin = https://github.com/DurgeshC16/Kaaran.git, branch main.
- After each completed stage or meaningful change, with tests green:
  1. Run `git status` and confirm no .env, data/real/ or docs/source/ files are staged.
  2. Commit, then immediately `git push`.
- Commit message: first line `phaseN: <what was just done>` (max 72 chars), then a body listing what changed, how many tests pass, decisions made, and what is next.
- Never force-push.
- Never push failing tests unless the message starts with `wip:` and explains why.

## Compaction
When compacting, keep: current phase, decisions made, failing tests, list of files changed.
