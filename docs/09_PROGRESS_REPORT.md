# 09 · Progress report (as of 28 Oct 2026)

> Simple summary of what is built, what it proves, and what is left. Day-to-day log: PROGRESS.md.
> How to run and test everything yourself: docs/10_TESTING_GUIDE.md.

## 1. One-paragraph status

Kaaran works end to end on synthetic data in real formats, and it already processes **real public data**
for Solapur district:
- **Inputs:** the officer's question, or new data arriving.
- **Analysis:** data checks, the clusters that need attention, why, and actions from a fixed rule table.
- **Output:** a Marathi-first three-part brief, a PDF, and click-to-source for every number.
- **Channels:** web and WhatsApp (simulator and real webhook).

Not done yet:
- voice;
- uploading your own files;
- deployment;
- user interviews.

## 2. What is built (by phase)

| Phase | What it does | Proof |
|---|---|---|
| 1 Synthetic district v2 | 7 messy files for 11 talukas, 8 planted "truths", same output for the same seed | truths hold on 20+ seeds |
| 2 Deterministic engines | ingest with provenance, trust checks, cause tester, twin finder, confidence rules, evidence pack | **8/8 truths on 5 seeds**, 0 false flags |
| 3 AI layers | Claude wrapper (replay cache, cost cap), AI column mapper, question reader, Marathi/English writer, verifier | mapping 100% on an unseen layout; **0 invented numbers**; prompt injection ignored |
| 4a Demo | web page, PDF, WhatsApp bot (signed webhook, simulator) | 22 briefs recorded and verified |
| Rethink (24-27 Oct) | mentor review → v2 plan, docs 01-08, README | docs/01 |
| 5 Block lens + rubric | v3 data in **real UDISE+ formats** (1,292 schools, 109 clusters); cluster risk scan; diagnoses D1-D8; decision rubric A1-A13; three-part brief | **19/19 checks on 6 seeds** (risks, causes, actions); ~98% recall over 60 seeds |
| 6.1 Product | alerts inbox (no question needed), open from alert, baithak pack + action tracker, WhatsApp alert → "अहवाल" | 232 tests |
| 7.1 Real data (today) | real UDISE+ 2024-25 Solapur microdata: validation + block snapshot; PRS 2024 benchmarks for 3 districts; cross-check against 2019-20 | 11/11 data checks pass |

## 3. Real data: what we have and what it says

Downloaded files are in `data/real/`, which git ignores. They are never committed.

| Source | Used for | Status |
|---|---|---|
| UDISE+ 2024-25 microdata, Solapur (`2730_*`, 4,698 schools, 13 blocks) | teacher availability, PTR, support visits, non-teaching duty per block | ✅ working (`python -m kaaran.real`) |
| PARAKH PRS 2024: Solapur, Sangli, Satara | grade 3 benchmark (maths 75 / 68 / 75; Maharashtra 64; India 60) | ✅ values read from the page images, stored in `data/real/prs2024/benchmarks.json` |
| AIKosh UDISE+ 2019-20 teachers, Solapur | cross-check of the 2024-25 numbers | ✅ every block within 0.87-0.97 of 2019-20 |
| PAB 2026-27 Maharashtra (CSV) | grounds actions in funded programmes | ⏳ next: link rubric actions to PAB line items |
| FLS 2022, ASER 2024, HCES | reference and context | 📄 kept for reading |
| NAS 2021 Maharashtra | benchmark | ⚠️ legacy Marathi font, text unreadable without OCR; skipped (optional) |
| data.gov.in item | old tables | ❌ download failed; not needed (AIKosh + microdata cover it) |
| `nfhs5/` folder | — | ⚠️ contains ASER copies, not NFHS; can be deleted |

**Real findings from Solapur ZP schools in UDISE+ 2024-25** (self-reported; aggregates only):
- **Scale:** 2,900 schools, 9,534 teachers, PTR 20.1.
- **Single-teacher schools:** 99 across the district. **Sangola has 27** and **Malshiras 20**.
- **No cluster (CRC) visit reported last year:** 789 schools. In **Solapur North it is 77 of 98 (79%)**.
- **Non-teaching work:** **Karmala reports 17.5%** of teachers on it.
- **Teacher numbers:** local-body teachers are **8% lower than in 2019-20 overall**, and every block is lower (ratios 0.87-0.97).

These are the input signals the mentor asked for. They show the decision rubric can run on real data. Outcomes
(assessment, monthly attendance) still need state logins, so they stay synthetic.

## 4. Quality numbers

| What | Number |
|---|---|
| Automated tests | 235 passing (3 live-API tests run only on request) |
| Invented numbers in briefs | 0 (verified by code on every brief) |
| v2 truths found | 8/8 on 5 seeds |
| v3 block-lens checks | 19/19 on 6 seeds; recall about 98% and extra flags about 3% over 60 seeds (small-school noise, documented) |
| Real data checks | 11/11 (unique IDs, same schools in every file, ranges, management mapping cross-checked against 2019-20) |
| AI cost | about $0.08 per block brief (Sonnet); about $0.0002 per question (Haiku); analysis, alerts and actions are free (no AI) |
| Total live AI spend so far | about $1.8 (Phase 3 $0.84, Phase 4 $0.64, Phases 5-6 about $0.26) |

## 5. What is left (in order)

1. **Real data in the product.** Use the real Solapur school frame (real schools, teachers and enrolment) with
   synthetic outcomes, so the demo shows real blocks. Link actions to PAB 2026-27 line items.
2. **Voice:** Marathi speech-to-text and a voice summary through a hosted API. Needs a provider key: Bodhan AI,
   Sarvam or Bhashini.
3. **Upload:** the officer uploads their own files on the web (needs `python-multipart`, approval pending).
4. **Deploy** a public link.
5. **User testing.** Even 2-3 short sessions help a lot (35% of the score mentions "proof of testing").
   Minimum version: the team teacher reviews one printed brief using the guide in docs/06 §7.
6. Video (3 min) and deck.
