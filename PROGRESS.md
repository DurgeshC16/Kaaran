# Kaaran: Progress

Deadline: 2026-11-01 (submit by afternoon).
Budget: development <= $180, runtime/evals <= $60, demo/judging <= $40. Reserve untouched.
Cumulative checkpoints: $60 by Oct 22, $130 by Oct 25, $200 by Oct 29.

## Current phase: v2 rethink (after mentor review 2026-10-24). Docs 01-08 written 2026-10-27; implementation = Phase 5 (docs/07).

v2 in one line: block -> cluster lens, 4 data domains in real formats (UDISE+ microdata), three-part brief (attention / why / what to do), decision rubric for actions, proactive alerts, baithak pack, voice. Plan and stages: docs/07_ROADMAP_AND_PHASES.md.

Phase 4 stages:
- [x] Demo service, HTML/PDF brief, web demo with click-to-source and school drill-down
- [x] WhatsApp: Cloud API webhook (signature, dedupe), bot (summary + PDF), local simulator
- [x] Voice in (Marathi speech-to-text) and voice summary out (Sarvam AI, 2026-10-28)
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

## Phase 8 result (2026-10-29): final build from user testing round 2 (answers that fit the question, UI, deploy, docs)
- **Round 2 (2026-10-29):** the product owner tested 12 questions, voice and WhatsApp. The log is in docs/USER_TESTING.md and the regressions in tests/test_officer_questions.py.
- **Answer modes** (`block/workspace.py _direct_answer`, `block/view.py`):

  | Mode | When | Answer |
  |---|---|---|
  | fact | a figure | 1–2 lines plus the source files |
  | rank | best/worst/highest/lowest | top 3 blocks |
  | cards | needs attention, why it fell, a block overview | kendra cards: what / why with its label / what to do with owner |
  | cluster | a kendra | its status plus its card |
  | dq | which records are unreliable | the kendras named, why they are excluded, what to check |
  | why_up | why it improved | the rise, the kendras that rose most, the inputs that moved, "associated with" wording |
  | twin | similar block did better | the learn-from card |

  In every mode the full A/B/C brief sits behind a "📄 Show the full evidence brief" button.
- **New scopes and inputs:**
  - **District scope:** "how many schools in Solapur", and a figure asked with no place, get district totals. "Why …" with no place still asks which taluka.
  - **Multi-part questions:** "X shala kiti, Y PTR kiti, Z shikshak kiti kami" is answered part by part, misspellings included.
  - **New metrics:** kendra count, single-teacher schools, vacancies, pupils.
- **Conversation and language:**
  - **Follow-ups:** after "which taluka?", the next reply completes the earlier question. This works on web (`context`), voice and WhatsApp (per sender).
  - **Reply language** follows the question (Devanagari → mr; Marathi typed in Latin letters → mr; English → en). STT detects the spoken language automatically.
- **WhatsApp:**
  - Short answers come as text + voice note + a "reply 'report'" hint.
  - Card answers come as text + PDF + voice.
  - 'report' after a short answer opens the full brief.
- **Web:**
  - A per-answer voice reply (`/api/answers/{id}/voice`).
  - Role home pages `/api/home` (DEO: district tiles, blocks needing attention, all blocks; BEO: block tiles, kendra cards, all kendras).
  - UI redesigned in government-portal style.
- **Deploy:**
  - Dockerfile is ready for Hugging Face Spaces: uid 1000; the synthetic data is generated at build time; healthcheck. The local build and smoke test pass, including the Chromium PDF.
  - `scripts/deploy_hf.py` creates the Space, sets secrets and variables, and pushes committed app files only. No force push, no new dependencies.
- **Dependency:** python-pptx 1.0.2 was added as dev-only (approved) for `scripts/make_deck.py`. It pulls in lxml, so `kaaran/__init__.py` pins openpyxl's pure-Python writer (`OPENPYXL_LXML=False`) to keep generated Excel files byte-identical.
- **Docs:** README (submission rules), docs/USER_TESTING.md, docs/DEPLOY.md, docs/13_FINAL_GUIDE.md (everything built, video test cases, market, data and generalisation answers), docs/12 video script, docs/Kaaran_Build_Deck.pptx.

## Phase 6.5 result (2026-10-28): direct answers (fix for "dummy answers" from user testing)
- Root causes:
  - The demo runs in replay mode, so any question not already recorded falls back to the rule matcher. The matcher refused valid questions (PTR, "how many schools", "what should I do").
  - Factual questions got the generic brief and an unrelated pointer.
  - Kendra questions and "which block needs most attention" got a request to clarify.
  - When two places were named, one was silently dropped.
- `block/answers.py`:
  - computes each block's and each kendra's facts from the canonical tables (trusted records only where trust matters). The facts are schools, clusters, working, sanctioned and vacant posts, single-teacher schools, PTR, schools with PTR over 30, attendance (last 3 months), low-attendance schools, maths and language level and change, Kendra Pramukh visits, and flagged or incomplete schools;
  - each fact has query provenance;
  - fixed Marathi/English templates with placeholders turn facts into sentences. No LLM is involved.
  - Facts are kept outside the evidence pack (`BlockWorkspace.facts/answer_pack`), so the prompts of recorded briefs do not change.
- `BlockWorkspace.resolve`, deterministic fixes on top of the intent plan:
  - a named kendra opens its block, matched by fuzzy Devanagari-to-Latin romanisation;
  - "which block needs most attention" opens the top alert and shows a ranked line;
  - a data question naming a block is never refused as out of scope;
  - a second named block gets the same figures side by side, plus a note that the brief is about the first block.
- Service:
  - greeting/help reply;
  - the "थेट उत्तर / Direct answer" section comes first in the reply, the web page (blue box, clickable figures) and the WhatsApp text;
  - the drill-down finds fact ids, including a compared block's.
- Rankings: "which block has the best maths / lowest PTR / least attendance" ranks the blocks by that figure. The top 3 are shown with clickable figures, and the top block's brief follows.
- Rule fallback:
  - wider topic words, including transliterated ones;
  - a bare place ("What about Karmala?") counts as in scope;
  - off-topic words are refused;
  - people patterns are refused ("which teacher", "list of … teachers", "who is the …");
  - place names must start at a word boundary; Marathi oblique forms match ("सांगोल्यासारखा");
  - places are listed in the order they were said.
  - Intent rule-tier accuracy went from 88% to 96% (25 questions).
- Adversarial review (4 lenses, 8 agents): 23 findings confirmed, all fixed. Main fixes:
  - PTR cited an assessment file;
  - blank cells crashed the block's answers;
  - "which block has the best X" got the attention ranking;
  - any question naming a block was answered;
  - fuzzy kendra swaps;
  - "madhale" matched Madha;
  - schools with no teacher were left out of PTR > 30;
  - learning figures without INSUFFICIENT schools had no coverage note;
  - "0.0 points lower";
  - unrelated pointer notes;
  - English examples in the Marathi help;
  - "reasons" claimed for unexplained kendras;
  - trust counts had no source.
- Tests: tests/test_answers.py (17). Facts are checked against the generator's clean tables, the provenance files per view, blank cells, zero-teacher schools, rankings, kendra matching, scope/people refusals, the drill-down and the evidence download.

## Phase 6.3 result (2026-10-28): voice (Sarvam AI) + PAB funding links
- `src/kaaran/voice/`:
  - `sarvam.py`: SarvamClient (httpx, no new dependency).
    - STT: saaras:v4, mr-IN, keyterms = place names.
    - TTS: bulbul:v4-flash, ritu_mr_narration / ritu_en_edtech, MP3. Devanagari digits are converted to ASCII before TTS. Audio is cached by text hash in data/voice_cache/.
    - Usage log goes to data/voice_usage.jsonl.
    - Per-process spend cap `KAARAN_MAX_VOICE_INR` (default 100).
    - Every failure raises VoiceUnavailable with a fixed reason code.
  - `script.py`: a one-minute spoken script built from the brief summary.
    - Lens-aware: block lens = attention / why / what to do; taluka lens = trend / cause / data warning / action.
    - Data warnings and actions are always spoken, and the rule-based labels are spoken with them.
    - Brackets, symbols and "%" are made speakable.
- Web:
  - mic button (MediaRecorder, max 28 s): POST /api/voice/ask returns the transcript, then the normal answer;
  - 🔊 Listen button: GET /api/briefs/{id}/voice (MP3);
  - GET /api/voice/status;
  - a Sarvam notice appears when voice is on.
- WhatsApp:
  - an incoming voice note is downloaded from Meta, sent to STT, and the bot replies "🎤 I heard: ..."; the question then takes the same path as a typed one;
  - after the PDF, the bot sends the MP3 voice summary (also when the PDF fails);
  - voice off gives a "please type" message;
  - failures give fixed bilingual reasons (the raw API text is never shown).
  - The simulator has a mic. MP3 arrives as an audio message; a voice-note bubble would need OGG/Opus and ffmpeg (not installed).
- Live check:
  - TTS returns in about 3 s;
  - STT is correct for पंढरपूर/मंगळवेढा;
  - the first Marathi summary takes about 14 s, and replays come from the cache.
- Rubric `funded_under`: 7 actions are linked to Samagra Shiksha PAB 2026-27 Maharashtra line items (code, page). They are shown in the baithak pack.
  - `kaaran.real --pab` verifies each citation against the PAB CSV, using Maharashtra rows only. Real run: 18/18 checks.
- `real/inputs.py`: RTE-norm teacher rationalisation, now in `kaaran.real` (JSON and Markdown report) and on the /real page.
  - Real Solapur: 213 posts needed, 89 coverable by redeployment, 124 needing new posts.
- Deploy prep:
  - Dockerfile: python 3.11-slim, Chromium and Noto fonts, replay mode;
  - .dockerignore keeps out .env and data;
  - KAARAN_HOST/PORT;
  - Chromium `--no-sandbox` switch.
- Docs: 11 pitch deck outline, 12 video script, DEMO.md voice section, testing guide E7b.
- Adversarial review: 16 findings confirmed and fixed. Main fixes:
  - the taluka-lens script had dropped trend and cause;
  - raw errors were shown to officers;
  - no spend cap;
  - the PAB check had no state filter;
  - the privacy notice was wrong;
  - no voice note when the PDF was missing;
  - test isolation.

## Phase 7.1 result (2026-10-28): real public data
- The user downloaded real files to data/real/ (git-ignored):
  - UDISE+ 2024-25 microdata for **Solapur district** (`2730_*`, 4,698 schools, 13 blocks);
  - PRS 2024 Solapur/Sangli/Satara;
  - AIKosh 2019-20 teachers (Solapur); PAB 2026-27 CSV (India, Maharashtra); FLS 2022; ASER 2024; HCES.
  - NAS 2021 PDF uses a legacy font (unreadable without OCR; skipped). The data.gov.in item failed (not needed). The nfhs5/ folder holds ASER copies.
- `src/kaaran/real/udise.py` + `python -m kaaran.real`:
  - validation (unique ids, same schools across files, ranges, single district);
  - aggregate block snapshot for local-body elementary schools (PTR, one-teacher / no-teacher schools, PTR > 30, no CRC visit, non-teaching teachers);
  - cross-check against AIKosh 2019-20, which validates management code 3 = local body via per-block teacher totals (ratios 0.87-0.97); 11/11 checks pass.
  - Reports go to data/real/reports/.
- `data/real/prs2024/benchmarks.json`: grade-3 maths/language for 3 districts, read from the rendered page 15 (hand-verified).
- Web page `/real` + `GET /api/real/snapshot` (local data only).
- Real findings (self-reported, aggregates):
  - 2,900 ZP schools, PTR 20.1, 99 single-teacher schools (Sangola 27, Malshiras 20);
  - 789 schools report no CRC visit (Solapur North 79%); Karmala 17.5% of teachers on non-teaching work;
  - local-body teachers 8% below 2019-20 overall.
- docs/09_PROGRESS_REPORT.md and docs/10_TESTING_GUIDE.md (step-by-step run/test/validate; all commands verified).
- Tests: 235 passed, 3 skipped (new: tests/test_real.py with a fake file set in the real format).

## Phase 6.1 result (2026-10-27): cluster lens in the product + proactive alerts
- `block/workspace.py`: block-kind dataset workspace (same interface as v1).
  - Packs for all 11 blocks are built at startup (~10 s); briefs and PDFs are cached.
  - District scan -> alerts. Open a block from an alert.
  - Baithak pack: all rubric actions by owner, with evidence, follow-up metric and status; action tracker in `actions.json` next to the data.
- `service.py`: `DatasetSpec.kind`; default dataset `blocks` (v1 `solapur` / `fictional` kept). Adds `open_block()` and `alerts()`; intent gets a cluster-lens scope note (v1 prompt unchanged).
- API: `/api/datasets/{id}/alerts`, `POST /api/open`, `/api/briefs/{id}/baithak`, `POST /api/briefs/{id}/actions`, `/api/whatsapp/simulate_alert`; the print view comes from the workspace.
- Web: alerts inbox, three-part brief, baithak drawer with confirm/done. WhatsApp: the bot pushes an alert, and the reply `अहवाल` opens that block (summary + PDF). Simulator has a "Send alert" button.
- Recorded: block-lens intents for the 14 example questions (all correct) and the fictional focus brief. Live spend ~$0.09.
- Tests: 232 passed, 3 skipped (new: test_block_service.py).

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
- 7.2 Real school frame in the demo: synth3 `--frame` using the real Solapur UDISE+ schools (pseudocodes, enrolment, teachers) with synthetic outcomes; clusters approximated by village panchayat; SYNTHETIC-marked outputs kept in data/real/.
- Owner: Render Blueprint deploy (docs/DEPLOY.md, render.yaml); find WHATSAPP_PHONE_NUMBER_ID; permanent token; run scripts/check_webhook.py; then Meta Verify and save; tag `build-submission`.
- Record the video (docs/12) and polish the deck; submit before 2026-11-01 (hours early).
- 6.4 upload (raw-body, no new dependency), optional.
- Deploy; user testing (even 2-3 sessions; the user may skip it); video and deck.

## Decisions
- 2026-10-31 Pre-deploy audit: hosting compared (Render free primary; Koyeb free with card or Northflank sandbox as backup; Cloud Run/Oracle rejected: card, background-task CPU, reclaim/capacity risk). Repo may stay private if the Tech4Dev evaluator IDs get read access. Fixed: /healthz HEAD, WhatsApp report language, repeated heading, dangling rank sentence, Marathi subject join, webhook checker validates the token.
- 2026-10-30 Hosting: Hugging Face Docker Spaces need PRO (HTTP 402); owner chose the free route -> Render free plan (render.yaml). Image pre-builds briefs, PDFs and a prepared-state cache (kaaran.warm) and loads only the main dataset: under 512 MB / 0.1 CPU it is up in about 13 s, first answer about 16 s, then instant. Real-data aggregate goes to Render as a Secret File, never git.
- 2026-10-29 Hosting: Hugging Face Spaces (Docker). WhatsApp: Meta Cloud API with the owner's phone, and evaluators use the web simulator (a Meta test number only reaches registered phones). Live Claude on the host with a spend cap. Deck generated with python-pptx (dev-only).
- 2026-10-29 Answer shape: the short answer first, kendra cards only for attention/why questions, the full brief always one click away; reply language = question language.
- 2026-10-28 Direct answers: facts are computed by code and phrased by fixed templates (no LLM). They are kept outside the evidence pack so recorded brief prompts stay valid. A data question naming a place is never refused.
- 2026-10-28 Voice provider: Sarvam AI (saaras:v4 STT, bulbul:v4-flash TTS); key in .env only. Voice is optional: without a key, the mic and Listen buttons are hidden and WhatsApp asks the officer to type.
- 2026-10-28 Voice reply format: MP3 audio message (no ffmpeg dependency); spoken script built by code from the summary (no LLM, no new numbers).
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
- 2026-10-27 Cluster lens is the default demo dataset; alerts come from the deterministic scan (no LLM), so they are free and instant. Real WhatsApp proactive messages outside the 24-hour window need an approved Meta template (the simulator shows the flow).
- 2026-10-27 The intent prompt gets an optional scope note for the cluster lens. Without it, Haiku refused "Which clusters in Pandharpur need attention?" as out of scope.
- 2026-10-28 Real public data stays in data/real/ (outputs too). The committed code and tests use only fake files in the real format. PRS numbers are hand-verified from the page images, because PDF text order is unreliable.
- 2026-10-28 UDISE+ management code 3 = local body is validated by per-block teacher totals against the 2019-20 tables (their own ids are 16-18, so the codes cannot be compared directly).
- 2026-10-28 (user) Interviews may be skipped for now; the guide keeps a minimal version (the team teacher reviews one printed brief).
