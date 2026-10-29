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
- Fast tests (everyday default): `.venv\Scripts\python -m pytest -q -m "not slow"`
- Full tests (run before every commit): `.venv\Scripts\python -m pytest -q` (adds `slow`: pdfplumber PDF reading, extra seeds)
- Live LLM tests (cost money, opt-in): `.venv\Scripts\python -m pytest -q --live -m live`. Normal runs replay recorded responses from `llm_cache/` (KAARAN_LLM_MODE=replay); `live` records new ones, `off` disables the LLM
- Generate data: `.venv\Scripts\python -m kaaran.synth --seed 42 --out data/synthetic/demo`
- Generate v3 block-lens data (real formats): `.venv\Scripts\python -m kaaran.synth3 --seed 42 --out data/synthetic/block_demo`
- Ingest raw files into DuckDB: `.venv\Scripts\python -m kaaran.ingest data/synthetic/demo/raw --db data/synthetic/demo/kaaran.duckdb` (writes ingest_report.json next to the db; `--write-mapping` dumps the rule-based mapping JSON)
- Trust checks: `.venv\Scripts\python -m kaaran.trust --db data/synthetic/demo/kaaran.duckdb` (writes trust_flags / trust_missing / trust_annotations tables, trust_report.json, trust_evidence.json)
- Evidence pack: `.venv\Scripts\python -m kaaran.analyze data/synthetic/demo/raw --focus Pandharpur --out evidence.json`
- Evidence Brief (Marathi + English): `.venv\Scripts\python -m kaaran.brief data/synthetic/demo/raw --focus Pandharpur --out-dir out` (`--no-llm` = template brief)
- Eval scorecard vs answer key: `.venv\Scripts\python -m kaaran.eval --seed 42` (repeat `--seed`; `--names fictional`; `--layout variant_b --proposer llm`)
- Intent eval (25 questions): `.venv\Scripts\python -m kaaran.eval.intent --tier light --tier main --tier rule`
- Brief eval (verifier pass, invented numbers, cost): `.venv\Scripts\python -m kaaran.eval.brief --seed 42 [--samples data/samples]`
- Block-lens scorecard (risks, diagnoses, rubric actions vs truth3.json): `.venv\Scripts\python -m kaaran.eval.block --seed 42 [--seed 7 ...]`
- Real public data snapshot (UDISE+ microdata in data/real/, never committed): `.venv\Scripts\python -m kaaran.real --udise data/real/udise_2425 --aikosh data/real/aikosh/UDISE_plus-19-20_teachers_solapur_mah.csv --benchmarks data/real/prs2024/benchmarks.json` (writes data/real/reports/; web page /real)
- Demo server (web + WhatsApp webhook): `.venv\Scripts\python -m kaaran.api` (http://127.0.0.1:8000, simulator at /whatsapp; setup in docs/DEMO.md)
- Voice (Sarvam AI, optional): set SARVAM_API_KEY in .env; check with `GET /api/voice/status`. Tests never call Sarvam (conftest sets KAARAN_VOICE=off)
- Deploy to Hugging Face Spaces (needs HF_TOKEN, HF_USER in .env): `.venv\Scripts\python scripts\deploy_hf.py` (docs/DEPLOY.md)
- Build the submission deck: `.venv\Scripts\python scripts\make_deck.py` (writes docs/Kaaran_Build_Deck.pptx)
- Prompt-injection check: `.venv\Scripts\python -m kaaran.eval.guardrails`
- Mapping eval (baseline vs LLM, both layouts): `.venv\Scripts\python -m kaaran.eval.mapping --seed 42` (`KAARAN_LLM_MODE=live` to record new responses)

## Layout
- src/kaaran/synth: synthetic data generator and answer key (v2, taluka lens)
- src/kaaran/block: block lens v2 (ingest, trust, insights = risk + diagnosis D1-D8, rubric.py + rubric_v1.json actions, pack.py block-1.0, brief.py three-part brief)
- src/kaaran/real: real public data (UDISE+ microdata validation + aggregate block snapshot, 2019-20 cross-check)
- src/kaaran/synth3: v3 generator (block -> cluster -> school, UDISE+ microdata columns, competency assessment; truth3.json)
- src/kaaran/evidence.py: Evidence pack contract (docs/EVIDENCE_SCHEMA.md)
- src/kaaran/ingest, trust: raw files -> DuckDB with provenance; trust checks (docs/CONFIDENCE_RULES.md)
- src/kaaran/causes, twins, confidence.py, analyze.py: cause tester, twin finder, label rules, end-to-end pack
- src/kaaran/eval: scorecard against ground_truth.json (the only engine-side reader of the answer key)
- src/kaaran/llm: Anthropic wrapper (cache/replay, usage log, spend cap), file summaries, mapping proposer
- llm_cache/: recorded LLM responses (committed; synthetic inputs only)
- src/kaaran/brief: Brief Writer (texts.py wording, render.py placeholder filling, writer.py LLM + fallback)
- src/kaaran/service.py: demo service (datasets, cached packs/briefs, question -> clarify | refuse | brief + summary)
- src/kaaran/brief/html.py, pdf.py: interactive/print HTML brief; PDF via headless Edge/Chrome
- src/kaaran/block/answers.py, view.py: direct answers (facts, rankings, district, why-it-improved, multi-part, language) and the answer views (answer card, kendra cards, brief behind a button)
- src/kaaran/voice: Sarvam STT/TTS client (cache, usage log, spend cap) and the spoken one-minute script
- src/kaaran/whatsapp.py: WhatsApp bot, Cloud API client, webhook signature + de-duplication
- src/kaaran/api: FastAPI app (web demo, drill-down, PDF, webhook, simulator) and static pages
- tests/: pytest suites
- data/synthetic/: generated data (git-ignored except small samples)
- docs/: 01 vision/rethink, 02 data strategy, 03 literature survey, 04 SRS, 05 architecture, 06 decision rubrics, 07 roadmap, 08 data download guide; plus EVIDENCE_SCHEMA, CONFIDENCE_RULES, SYNTHETIC_DATA_SPEC, DEMO. docs/source/ holds local-only originals (git-ignored)
- data/real/: real downloaded files (git-ignored; never commit)
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
- Commit message: subject `phaseN: <what was done>`, then a body with as much detail as needed: what changed, how many tests pass, decisions made, and what is next. Concise but complete.
- Never force-push.
- Never push failing tests unless the message starts with `wip:` and explains why.

## Compaction
When compacting, keep: current phase, decisions made, failing tests, list of files changed.
