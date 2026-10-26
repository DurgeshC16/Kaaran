# 07 · Roadmap and phases

> Today: 27 Oct 2026. Build deadline: **1 Nov 2026** (submit by the afternoon). Top 10: 10 Nov.
> Final pitch + live demo: 18 Nov. Each stage ends with green tests, a commit and a push (CLAUDE.md).

---

## 1. Where we are (done)

| Phase | Dates | Result |
|---|---|---|
| 1 · Foundation | 18-23 Oct | Synthetic district generator (7 messy files, 8 planted truths, deterministic per seed) |
| 2 · Deterministic engines | 23 Oct | Ingest to DuckDB with provenance, trust checks, causes, twins, confidence rules, evidence pack, eval: **8/8 truths on 5 seeds**, 0 false flags |
| 3 · AI layers | 23 Oct | Claude wrapper (replay cache, cost cap), AI column mapper (100% on hold-out layout), intent parser, Marathi/English writer, verifier: **0 invented numbers**, ~$0.05/brief |
| 4a · Demo | 24 Oct | Web demo (click-to-source, school lists, PDF), WhatsApp bot (signed webhook, dedupe, simulator), 22 briefs recorded; 203 tests |
| Review | 24 Oct | Mentor review (Rupala, CSF) → rethink v2 (doc 01) |

## 2. Plan to submission

Priority: **M** must (needed to win), **S** should, **C** could (only if ahead of schedule).

### Phase 5 · Block lens + decision rubric (27-28 Oct)

| Stage | What | Pri | Done when |
|---|---|---|---|
| 5.1 | **Synthetic v3 generator**: district → blocks → clusters → schools; UDISE+ microdata columns (`prof1, prof2, tch, enr1`); kendra list; competency-wise assessment (3 rounds/year); monthly attendance, teacher posts with duty days, support-visit log, training register; messiness kept; new planted truths (two clusters with opposite causes, positive deviant, migration, data problem, surplus school); answer key incl. expected actions | M | deterministic per seed; truths hold on 20 seeds; tests |
| 5.2 | **Ingest v2**: UDISE+ microdata connector, kendra list, new canonical tables, mapping vocabulary extended; old files still ingest | M | round trip 100% vs clean tables |
| 5.3 | **Trust v2**: impossible combinations (high attendance + low learning), PTR sanity, assessment spikes, freshness | M | planted data problems found, honest schools cleared |
| 5.4 | **Insight engine**: risk scanner, cluster diagnosis D1-D8, competency focus, positive deviance (reuses causes/twins tests) | M | answer-key clusters found, diagnoses correct, 0 false at-risk |
| 5.5 | **Rubric engine** reading `config/rubric_v1.json` (A1-A13 with constraint checks) | M | expected action per scenario chosen; constraint failures logged |
| 5.6 | **Evidence pack v1.1 + three-part brief** (A/B/C + appendix), texts, templates, verifier sections; LLM prose re-recorded | M | one page; verifier passes; 0 invented numbers on 5 seeds |
| 5.7 | **Eval v3**: risk recall/precision, diagnosis accuracy, action accuracy, invented numbers | M | scorecard all green on 5 seeds |

### Phase 6 · Proactive loop + voice + upload (29 Oct)

| Stage | What | Pri |
|---|---|---|
| 6.1 | **Scan + alerts**: "new data arrived" → scan all blocks → alert inbox (web) + WhatsApp alert text (simulator; template-message payload ready for Meta approval) | M |
| 6.2 | **Baithak pack** (cluster agenda + actions + owners) and **action tracker** (confirm → store → re-check on next data) | S |
| 6.3 | **Voice**: STT for Marathi questions and a one-minute Marathi voice summary (provider decision below) | S |
| 6.4 | **Web upload** of the officer's files (needs `python-multipart`) | C |

### Phase 7 · Real data + users + deploy (30 Oct)

| Stage | What | Pri |
|---|---|---|
| 7.1 | **Real data run**: PRS 2024 Solapur benchmark (verified numbers with page refs) in the brief; UDISE+ 2024-25 Maharashtra microdata → real school frame of one block (`--frame`), outcomes synthetic, SYNTHETIC-marked, kept in `data/real/` | M |
| 7.2 | **User testing**: ≥ 3 sessions (team teacher, teachers/HMs, an officer if possible) using the interview guide (doc 06 §7); log in `docs/USER_TESTING.md`; apply top fixes | M |
| 7.3 | **Deploy** a public demo link (small VM or PaaS + HTTPS); replay mode by default; live LLM with a spend cap | M |
| 7.4 | Hardening: error pages, timeouts, logs, README, `docs/DEMO.md` refresh | M |

### Phase 8 · Story (31 Oct) → submit (1 Nov)

| Stage | What | Pri |
|---|---|---|
| 8.1 | 3-minute video: problem (15 s) → alert arrives on WhatsApp → three-part brief → click to source → actions differ per cluster → baithak pack → guardrails (30 s) → real data + user testing → roadmap | M |
| 8.2 | 10-12 slide deck: AI layers, guardrails, low-connectivity behaviour, user testing evidence, roadmap (submission requirements in PROJECT_CONTEXT.md) | M |
| 8.3 | Final checks: public link, repo public decision (user), README, licence decision (user) | M |

### Cut order if we fall behind
6.4 → 6.2 action tracker (keep baithak pack) → 6.3 TTS (keep STT) → 5.3 freshness rule. Never cut: 5.1,
5.4, 5.5, 5.6, 7.1 benchmark, 7.2, 7.3.

## 3. Decisions needed from the team

| # | Decision | Recommendation |
|---|---|---|
| D1 | Approve the v2 re-scope (block → cluster lens, 4 domains, A/B/C brief, rubric actions, proactive alerts) | **Yes** (mentor feedback) |
| D2 | Keep the v1 taluka pipeline working until v2 passes its eval, then retire the 6-section brief | **Yes** (no broken demo at any time) |
| D3 | Download real files (doc 08) and place them in `data/real/` | Needed by 30 Oct |
| D4 | Speech provider for the demo: hosted API (Bodhan AI / Sarvam / Bhashini; needs an API key) vs self-hosted IndicConformer (adds heavy dependencies: NeMo/PyTorch) | **Hosted API for the demo, self-hosted in the pilot**; new dependency only for the HTTP client already installed |
| D5 | New dependencies: `python-multipart` (upload), possibly `scipy` (stats intervals) | approve when the stage starts |
| D6 | LLM budget for re-recording v3 briefs and intents | ≈ $3-5 |
| D7 | Repo public + licence (open-source credit +$250) | team decision |

## 4. After the hackathon

| When | Milestone | Success measure |
|---|---|---|
| Nov 2026 | Top 10 → final (18 Nov): live demo on a real block frame; user-testing evidence | top 10 |
| Nov-Dec 2026 | Data request / MoU with a ZP education office (Solapur) for one block; rubric review with DIET/SCERT faculty | signed request; rubric v2 |
| Jan-Mar 2027 | **Pilot, one block**: weekly scans on authorised exports, monthly baithak packs, action tracking | time to answer < 5 min; ≥ 50% flags confirmed; ≥ 60% actions accepted; weekly use |
| Apr-Jun 2027 | District rollout; integration with state MIS / Vidya Samiksha Kendra as a data source (alerts start from the system) | all BEOs in the district receive monthly briefs |
| 2027-28 | State scale: config packs per state; rubric as a shared state asset; self-hosted Indic models | cost per block per month < ₹500 |

## 5. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| v3 rewrite overruns the deadline | medium | extend, don't rewrite: reuse ingest/trust/causes/brief; keep v1 demo alive (D2); cut order above |
| Rubric thresholds feel wrong to officers | medium | publish them, mark as starting values, change from interviews, version them |
| No real school-level outcomes before submission | high | be explicit: real inputs (UDISE+ format/frame), real benchmarks (PRS), synthetic outcomes in real formats |
| Voice quality on dialects/noise | medium | confirmation questions; gazetteer snapping; text always works |
| WhatsApp template approval takes time | medium | simulator + web inbox for the demo; template payload ready |
| LLM cost / availability | low | replay cache, templates, spend cap; analysis needs no LLM |
