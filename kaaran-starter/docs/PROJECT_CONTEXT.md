# Kaaran: Project Context

Distilled from the Challenge 4 problem statement, the hackathon guidelines and our ideate deck.
Read this for product scope and judging criteria. The original files are in docs/source/. Open them only if a detail is missing here.

## Event and status
AI for Foundational Learning Hackathon (ShikshaNext x Anthropic, on Hack2skill). Team EASY COMPANY (4 members, one is a government primary school teacher in Khadki, Pune). Our idea Kaaran was selected, so we are in the **Build stage**.

| Date | Milestone |
|------|-----------|
| 2026-11-01, 11:59pm | Build submission deadline (submit hours early) |
| 2026-11-10 | Top 10 announced, extra credits |
| 2026-11-18, 10am-2pm | In-person final: 10-12 slide pitch + live demo (pre-recorded backup recommended) |

## The challenge: Challenge 4, "Data to Action"
Block and district education officers need support in using education assessment and monitoring data to take necessary actions. Three sub-problems:
1. Officials struggle to access data, derive insights and understand what actions are needed to address gaps. **(We target this one.)**
2. Data is collected at multiple levels with limited systems to collate it into a clear overall view.
3. Officials are often unaware what actions are planned in response to data findings and who is executing them, which reduces accountability.
Partial solutions are explicitly allowed. Kaaran also touches 2 (joins messy files) and 3 (action forwarding, next-month re-check).
Suggested data: PARAKH Foundational Learning Study reports, NAS dashboard (PARAKH), UDISE+. Reading: "Using Data to Improve Teaching and Learning in India" (Education for All in India, 2024).

## Build-stage judging
| Criterion | Weight | What they look for |
|-----------|--------|--------------------|
| Efficacy and user-centricity | 35% | Impact on the challenge; intuitive UI; built for user constraints (vernacular, voice-first, contextual); **proof of testing and refinement from user input** |
| Effective AI use and technical strength | 30% | LLM used according to its strengths; technical depth; **guardrails and error handling**; works in real scenarios |
| Innovation and creativity | 25% | Novel AI-centred approach; clear differentiation from existing solutions |
| Future roadmap | 10% | Pathway to further development and integration into existing systems |

## Build submission requires
1. A public, testable demo link (plus any software needed to test it).
2. GitHub source code (judges inspect it to verify how AI is used).
3. A public YouTube demo video of 3 minutes: challenge, UI walkthrough, key features, ease-of-use features. Judges need not watch past 3 minutes.
4. A short PowerPoint covering: AI/LLM usage in layers (data input, processing, guardrails, evaluation, output); guardrails for wrong AI output; how it works in low-connectivity and low-cost-device settings (what degrades gracefully); user inputs and testing evidence (1-2 pages); future roadmap (1-2 pages).

## Rules that affect engineering
- AI must be central to the solution. Source code is used to verify this.
- Work must be original and built during the hackathon window. Open-source libraries, public APIs, datasets and AI coding assistants are allowed.
- Credits: USD 500 for Build, +USD 500 for the final, +USD 250 if we open-source the code (no effect on scoring). Our internal target: development <= $180, runtime/evals <= $60, demo/judging <= $40.

## Kaaran in one paragraph
An officer sends a Marathi WhatsApp-style voice question ("Why did Pandharpur fall in maths?") plus the files their office already has. Kaaran returns a one-page Marathi Evidence Brief and a one-minute voice summary: what happened, why, how sure we are, and what to do on Monday. Not a dashboard, not a chatbot: "existing systems give officers data, Kaaran gives them a data analyst."

## Users and constraints
Users: District Education Officer (which blocks, why, what to fix first; wants a one-page brief before review meetings), Block Education Officer (defend or correct his block's story with evidence), Kendra Pramukh (which of his 10-15 schools need a visit).
Design constraints: low data literacy (no dashboards, plain language); Marathi first, voice first; basic Android phone and patchy network (WhatsApp, PDF, SMS fallback); messy multi-format files (AI does the joining); unreliable data (trust flags before conclusions); accountability culture (evidence, not blame).

## The Evidence Brief (6 items, each with a confidence label)
Marathi headings are from the deck. Have a native speaker verify them.
1. कल (trend): real decline, 4th to 9th of 11 talukas since 2021. STRONG
2. निवडणूक कारण तपासले (election excuse check): 5 of 6 similar talukas with the same election did not drop. WEAK CAUSE
3. संभाव्य मुख्य कारण (probable main cause): drop concentrated in 11 schools with maths teacher vacant since 2023. STRONG
4. जुळा तालुका (twin block): Malshiras, same size and poverty, but improved. LEARN FROM
5. डेटा इशारा (data warning): 23 schools show 100% attendance for 4 straight months. RED FLAG
6. सुचवलेली कृती (suggested action): redeploy teachers to the 11 schools; exposure visit to Malshiras. ACTION
Confidence levels: Strong (holds across years and against similar blocks: act on it), Weak (a pattern exists but similar blocks show it too: investigate before acting), Not enough data (missing or flagged unreliable: collect better data first).

## The five engines
1. Messy-File Reader: reads Excel/PDF/CSV, matches school codes, months and years automatically.
2. Data Trust Check: flags impossible patterns (flat 100% attendance, sudden jumps, missing schools) before they mislead, and protects honest teachers whose real numbers look worse.
3. Cause Tester: tests each suspected cause (attendance, teacher vacancy, infrastructure, election duty) against the data.
4. Twin-Block Finder: finds similar blocks that did better (positive deviance, borrowed from public health).
5. Brief Writer: Marathi one-pager plus voice note, with confidence labels and actions within the officer's powers.

## Architecture (from the deck)
1. User channels: WhatsApp (voice + files), web portal for DEO, SMS fallback.
2. Input processing: Marathi speech-to-text (Bhashini / AI4Bharat), Claude intent parser (question to analysis plan), file intake (Excel/PDF/CSV).
3. AI agent core (Claude orchestrator): Messy-File Reader, Cause Tester (proposes hypotheses, writes analysis code), Twin-Block Finder, Brief Writer.
4. Compute and data: Python sandbox (pandas, statsmodels, scikit-learn) where ALL numbers are computed; DuckDB unified store; Data Trust Engine (anomaly rules + z-scores vs history).
5. Guardrails: no LLM-generated numbers; every claim cites a source cell; confidence labels; verifier pass re-checks numbers in the text against computed results; PII stays on the district server and only aggregates reach the LLM.
6. Outputs: 1-page Evidence Brief PDF (Marathi/English), 1-minute voice summary, school-level drill-down list, action forwarded to the BEO (officer-confirmed).
Planned data: UDISE+, NAS 2021 district report cards, PARAKH Rashtriya Sarvekshan 2024, Election Commission schedules, state attendance/PAT, plus synthetic block data that mirrors real messy formats.

## Proposed MVP scope (adjustable)
- **Must:** synthetic data + answer key; messy-file ingestion; trust check; cause tester; twin finder; Marathi Evidence Brief PDF with provenance; web demo (typed or recorded Marathi question + file upload); eval harness scoring planted-truth recovery and invented numbers.
- **Should:** one-minute voice summary; school drill-down; action confirmation and next-month re-check.
- **Stretch:** WhatsApp channel, SMS fallback, scanned-sheet reading, BAITHAK (review-meeting assistant).

## Known risks (from our own review)
- User-testing evidence is scored but we have none yet. Get real officer or teacher feedback early.
- Avoid overclaiming causation. Say "associated with" unless rule-based STRONG criteria are met. Sample sizes are small (11 talukas).
- A judge-testable link matters more than WhatsApp. Web demo first, WhatsApp shown in the video.
- Real block-level data is hard to get. Be upfront that demos use synthetic data, and run at least one real public dataset through the pipeline.
- Scope is large for two weeks. Build one thin end-to-end slice first.
- Deck cleanup: "[TEAM NAME]" footers on slides 6-7, Std 1-3 vs 1-2 inconsistency, soften "never applied" claim.
