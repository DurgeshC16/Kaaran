# 11 · Pitch deck (10-12 slides): content and speaker notes

> Submission asks for: AI usage in layers (input, processing, guardrails, evaluation, output), guardrails for
> wrong AI output, low-connectivity / low-cost-device behaviour, user inputs and testing evidence (1-2 slides),
> future roadmap (1-2 slides). Numbers below are from the repository (docs/09) and must be re-checked before
> the deck is exported. Demo data is SYNTHETIC: say so on every slide that shows a brief.

---

### Slide 1 · Title
**Kaaran (कारण): an AI data analyst for education officers**
"Existing systems give officers data. Kaaran gives them a data analyst." Team EASY COMPANY · Challenge 4, Data to Action.

### Slide 2 · The problem (one officer, Monday morning)
- A BEO looks after 150-300 schools in 10-20 clusters. Assessment, attendance and teacher data arrive in
  different portals and Excel sheets.
- The monthly review (बैठक) ends with generic instructions: "improve attendance", "conduct training".
- Research: assessments alone do not change learning (Madhya Pradesh school-quality study, 1,774 schools,
  no learning effect, Muralidharan & Singh 2020), and administrative data is often inflated (Singh 2020).
- **Gap: from data to a specific, trusted, doable action.**

### Slide 3 · What Kaaran does (the three-part brief)
Screenshot of the brief (SYNTHETIC banner visible):
**A · लक्ष देण्याची गरज** (what needs attention) → **B · असे का होत असावे** (why) → **C · काय करावे** (what to do, with
owner and deadline). Marathi first, English second; a one-page PDF, a one-minute Marathi voice summary, and
click-to-source on every number.

### Slide 4 · It starts without a question
New data arrives → Kaaran scans every block → an alert reaches the officer on WhatsApp: "३ केंद्रांना तातडीने लक्ष
देण्याची गरज". Reply "अहवाल" → brief + PDF + voice note. (The mentor's point: most officers will never ask first.)

### Slide 5 · Different clusters, different reasons, different actions
The same block, three clusters falling for three different reasons:
| Cluster | Why (rule-based, with evidence strength) | Action (from the decision rubric) | Funded under (PAB 2026-27) |
|---|---|---|---|
| Support gap | Kendra Pramukh visits 1.3 → 0.1 per school-month; subtraction weakest | weekly classroom visits for a month; cluster training | C476 CRC academic support; C6779 FLN teacher capacity |
| Staffing gap | 6 schools lost a teacher; now multigrade | redeploy from 2 surplus schools (PTR < 20); multigrade support | C6800 FLN learning material |
| Migration | attendance falls Nov-Mar every year | migration tracking, seasonal hostel, bridge classes | C380 residential special training (migrant) |
Plus: one school improved despite the same shortage → peer visit; poll duty ruled out; Malshiras = twin block.

### Slide 6 · AI in layers (where the LLM is used and where it is not)
| Layer | What happens | Who does it |
|---|---|---|
| Input | Marathi voice → text (Sarvam speech-to-text); question → validated plan (closed lists; asks instead of guessing) | Sarvam AI, Claude Haiku |
| Processing | messy columns → canonical fields (AI proposes, code validates); trust checks; risk scan; diagnosis; positive deviance | Claude Sonnet (mapping), **code** (everything else) |
| Decisions | actions from a versioned rubric with constraint checks (e.g. redeploy only if a surplus school exists) | **code** |
| Output | Marathi/English wording with placeholders; code fills every number; voice note | Claude Sonnet, code, Sarvam text-to-speech |
| Evaluation | answer-key scorecards, invented-number detector, prompt-injection test | code |

### Slide 7 · Guardrails for wrong AI output
1. **The AI cannot write a number**: it writes `{{n:id}}`; code fills values from the evidence pack.
2. **Verifier on every sentence**: no digits, no causal words unless STRONG, no school names, all sections present →
   one retry → fixed templates. Result: **0 invented numbers**.
3. **Labels and actions come from written rules**, never from the AI.
4. **Trust before analysis**: fake-looking attendance is flagged and acted on ("verify registers"), never silently used.
5. **Clarify, don't guess; refuse ranking individuals.**
6. **Prompt injection**: file contents reach the AI only as masked summaries (tested).
7. **Privacy**: only aggregates reach the AI; school lists stay on the server.

### Slide 8 · Built for low connectivity and low-cost phones
- WhatsApp first: text summary (< 4 KB), one-page PDF (~100 KB), voice note for officers who prefer listening.
- Works without the AI: rule-based question reading + template brief (same numbers and actions).
- Alerts, analysis and actions need no AI at all (free, instant).
- Web page has no external scripts/CDNs; works on slow networks.

### Slide 9 · Proof: evaluation
| What | Result |
|---|---|
| Planted problems found (synthetic district, answer key hidden from the engine) | 19/19 checks on 6 random districts; ~98% recall over 60 |
| Invented numbers in briefs | 0 |
| Real public data (UDISE+ 2024-25 Solapur, 4,698 schools) | 18/18 data checks; teacher counts cross-checked against 2019-20 |
| AI cost | ~₹4 per block brief per data refresh; alerts and analysis free |

### Slide 10 · Real data today (Solapur, UDISE+ 2024-25, ZP schools; self-reported)
99 single-teacher schools (Sangola 27); 789 schools report no CRC visit last year (Solapur North 79%); teachers 8%
below 2019-20 in every block; PRS 2024 grade 3 maths: Solapur 75%, Maharashtra 64%, India 60%.
"These are the inputs our rubric uses; outcomes need state logins, which a pilot would provide."

### Slide 11 · User input and testing *(fill with real sessions)*
- Mentor review (Central Square Foundation): changed the trigger (alerts), the brief (three parts), the actions
  (rubric with constraints) and the data scope (4 domains). Before/after screenshots.
- Team member who is a government primary teacher: review of the brief and actions (add quotes).
- What we changed because of feedback: list.

### Slide 12 · Roadmap
| When | Step |
|---|---|
| Nov-Dec 2026 | data request / MoU with a Zilla Parishad; rubric review with DIET/SCERT |
| Jan-Mar 2027 | one-block pilot: weekly alerts, monthly baithak packs, action tracking (measure: time to answer, flags confirmed in the field, actions done) |
| 2027 | district rollout; state MIS / VSK as the data source (alerts start from the system); self-hosted Indic speech models |
| Scale | config per state (mappings, rubric, texts); ~₹4 per block per month for AI wording |
