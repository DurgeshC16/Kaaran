# User testing and refinement log

> This file records who tested Kaaran, what they asked, what went wrong, what we changed and which automated
> test now guards each fix. The judging criteria ask for "proof of testing and refinement from user input".
> The record is meant to be honest, so it says plainly what has **not** been done yet.

## Summary

| Round | Date | Who | Method | Findings | Changes shipped |
|---|---|---|---|---|---|
| 0 | 2026-10-24 | Mentor (Rupala, Central Square Foundation) | design review of the v1 demo and brief | 9 points | v2 rethink: proactive alerts, kendra lens, three-part brief, decision rubric, baithak pack (docs/01 §3) |
| 1 | 2026-10-28 | Team, testing the web and WhatsApp demo | hands-on with own questions | "dummy answers" to everyday questions | direct-answer layer (PROGRESS.md, Phase 6.5) |
| 2 | 2026-10-29 | Product owner (team) | structured test: 12 questions on the web, plus voice and WhatsApp | too much at once, a few wrong scopes, lost follow-up, wrong reply language | short answers first, evidence behind a button, follow-up context, language follows the question, role homes |
| Red team | 2026-10-28 | Internal adversarial code reviews (multi-agent) | 2 reviews of the voice and direct-answer stages | 16 + 23 confirmed findings | all fixed, each with a regression test where possible |
| Pilot | planned | BEOs, Kendra Pramukhs, one DEO | observation + interview (protocol below) | — | — |

**What has not happened yet:** no interviews with serving education officers (BEO, DEO or Kendra Pramukh) had
been completed by 2026-10-29. Our team of four includes a government primary school teacher (Khadki, Pune), and
the design draws on that experience, but the structured teacher review planned in docs/06 §7 is not yet
recorded here. Officer sessions are the first step of the pilot plan at the end of this file.

---

## Round 0: mentor review (2026-10-24)

The mentor reviewed the v1 product: taluka lens, six-part brief, typed questions. Full table and decisions:
[docs/01_VISION_AND_RETHINK.md §3](01_VISION_AND_RETHINK.md).

| # | What the mentor said | What we changed |
|---|---|---|
| 1 | Most officers will never ask a bot a question; a tool that waits does not scale. | **Proactive alerts**: a deterministic district scan runs when data arrives. The alerts inbox appears on the web, and WhatsApp gets an alert message ("अहवाल" opens the block). |
| 2 | Do not try to cover every dataset; build a data availability matrix. | Scope cut to 4 core domains (teachers/PTR, attendance, enrolment, learning) plus support visits and non-teaching duty (docs/02). |
| 3 | Public data is aggregated; synthetic data in real formats is valid. | v3 generator in **real UDISE+ microdata columns** and state-style exports (`kaaran.synth3`). The real UDISE+ 2024-25 Solapur microdata is processed as aggregates (`kaaran.real`). |
| 4 | Six parts are too many: use **what needs attention → why → what to do**. | Three-part brief A / B / C; labels in plain words. |
| 5 | Actions are the weakest part of every product; use a **decision rubric** that checks constraints first. | `block/rubric_v1.json` (A1-A13) with constraint checks. Owner, deadline and follow-up metric come from rules; the LLM never chooses an action. |
| 6 | Show what the naked eye misses ("two clusters fail for different reasons"). | **Kendra lens** with differential diagnosis D1-D8 per kendra, positive deviants and a twin block. |
| 7 | The baithak (monthly review) is where accountability happens. | **Baithak pack** with an action tracker (confirm / done). |
| 8 | OCR of handwritten registers is out of scope. | Agreed; not built. |
| 9 | Bhashini underperforms for voice; look at other stacks and cost. | Pluggable voice layer. The demo uses Sarvam AI (saaras:v4 STT, bulbul:v4-flash TTS) with a spend cap; an open model is planned for the pilot. |

---

## Round 1: team testing of the web and WhatsApp demo (2026-10-28)

**What happened.** Team members used the web demo and the WhatsApp simulator with their own everyday questions
("what is the PTR", "how many schools", "what should I do", questions about one kendra). Many replies looked like
**"dummy answers"**: a generic brief, a request to clarify, or a refusal.

**Root causes found** (PROGRESS.md, Phase 6.5):
- The demo runs in replay mode, so questions that had not been recorded went to the rule matcher, which
  refused valid questions (PTR, "how many schools", "what should I do").
- Factual questions got the generic brief plus an unrelated pointer.
- Kendra questions and "which block needs most attention" got a request to clarify.
- When two places were named, one was silently dropped.

**What we changed** (`src/kaaran/block/answers.py`, `BlockWorkspace.resolve`, service):
- A **direct-answer layer**. Each block's and kendra's facts are computed from the canonical tables (schools,
  kendras, posts, vacancies, single-teacher schools, PTR, attendance, maths/language level and change, Kendra
  Pramukh visits, flagged schools), each with query provenance. Fixed Marathi/English templates turn them into
  sentences, with no LLM.
- "थेट उत्तर / Direct answer" comes first on the web page and in WhatsApp; figures are clickable.
- A kendra name opens its block (fuzzy Devanagari-to-Latin matching). "Which block needs most attention" gives a
  ranked line. Two named blocks are answered side by side.
- Rankings by the asked figure ("best maths", "lowest PTR", "least attendance").
- Rule fallback widened (transliterated topic words, bare place names, Marathi oblique forms); off-topic and
  people questions are refused.

**Result.** The rule-tier intent accuracy on the 25-question set went from 88% to 96%. The new regression suite
is `tests/test_answers.py`.

---

## Round 2: product owner's structured test (2026-10-29)

**Method.** The product owner asked 12 prepared questions on the web demo (Marathi, English and transliterated
Marathi, some misspelt), then a voice question on the web and a voice question on WhatsApp. For each answer they
noted whether it answered the question and what was wrong.

**Main message:** *too much information at once.* An officer wants the asked detail first, in one or two lines,
with one strong piece of evidence and a reference. The full evidence should sit behind a button. The UI should
be simpler and plainer (a government-website feel, not flashy). Overall, Kaaran should feel connected to how
BEOs and DEOs work and give actual insights.

### Question by question

"Now answers" is the output of the current build on the demo dataset (synthetic, seed 42), taken from a local
run on 2026-10-29. Test names refer to `tests/test_officer_questions.py` unless another file is given.

| # | Question | Before | Feedback | What we changed | Now answers | Regression test |
|---|---|---|---|---|---|---|
| Q-1 | Which block has the best maths results? | Full A/B/C brief | Show only what was asked; no "what needs attention / what to do" for a ranking | Ranking card only (mode `rank`); the brief is behind a button | "Highest maths results: Malshiras 65.2%, Barshi 65.2%, North Solapur 63.3%." | `test_q1_ranking_shows_only_the_ranking`; `test_answers.py::test_rankings_by_the_asked_figure` |
| Q-2 | Malshiras cha nikal changla ka aala? (why did Malshiras improve?) | Only restated the figure; "Other checks" unclear | Explain why it improved; what does "Other checks" mean? | Rule-based "why it improved" answer: the rise, the kendras that rose most, the inputs that moved with it, "associated with" wording. "Other checks" moved inside the full evidence. | "Malshiras: maths rose 2.7 points this year, to 65.2%. Largest rises: Longaon Khurd Kendra (+5.0), Malner Budruk Kendra (+4.3). Working teachers went from 496 to 498. These changes are associated with the rise; the data does not prove they caused it." (in Marathi first) | `test_q2_why_it_improved_is_explained` |
| Q-3 | Hello | Help message with examples | Satisfied | No change | Help message with example questions; the Marathi help lists Marathi examples only. Known gap: a bare `Hello` gets `reply_lang` = Marathi, because the language detector has no English word to go on. | `test_answers.py::test_greeting_and_refusals`, `test_help_is_in_the_officers_language` |
| Q-4 | पंढरपूर मध्ये किती शाळा आहेत? / Pandharpur madhe kiti shala ahet | What / why / action | Only the asked detail | One-line factual answer with its source; the brief is behind a button | "पंढरपूरमध्ये १४० शाळा आहेत (१२ केंद्रे)." | `test_q4_q10_counts_are_one_line` |
| Q-5 | how many schools are there in solapur | Asked which taluka | Should answer for the district | District scope: district totals for district questions and for figures asked without a place | "Solapur district has 1,292 schools in 11 blocks and 109 clusters." | `test_q5_district_questions_get_district_figures` |
| Q-6 | what is today's date | Refused as outside the data | Satisfied | No change | "That is outside this education data. I answer about talukas and clusters: results, attendance, teachers, visits and data quality." | TODO: no dedicated test for this wording; the scope refusals are covered by `test_answers.py::test_scope_people_and_place_boundaries` |
| Q-7 | Which teacher in Pandharpur is absent most often? | Refused (no individual people) | Satisfied | No change | "I don't answer questions about individual teachers or students. Please ask about a taluka." | `test_answers.py::test_scope_people_and_place_boundaries` |
| Q-8 | Which block needs most attention? | Good content, but too detailed and messy | Clear flash-card style, government-website look | A ranked line plus **kendra cards** (what / why with label / what to do with owner); the full brief is behind a button; UI redesign | "Most attention needed: Pandharpur (3 clusters), Karmala (1 cluster), Madha (1 cluster)." followed by at least 3 kendra cards | `test_q8_attention_gets_kendra_cards` |
| Q-9 | How many single-teacher schools are in Sangola? | Many unrelated lines | 1-2 lines, one strong piece of evidence, a reference | Single-figure templates (single-teacher schools, vacancies, kendras, pupils) plus a source-file line | "Single-teacher schools in Sangola: 1 of 138." Source: `teacher_posts.xlsx` | `test_q9_single_teacher_schools_one_figure` |
| Q-10 | पंढरपूर मध्ये किती केंद्रे आहेत? | No proper answer; are data lookups in scope? | Answer it; clarify scope | Kendra-count answer. Scope: Kaaran is an analyst; simple lookups get one line, and the value is in *why* and *what to do* | "पंढरपूरमध्ये १२ केंद्रे आहेत (१४० शाळा)." | `test_q4_q10_counts_are_one_line` |
| Q-11 | Which of madha attendance records look unreliable? | Too much brief | Only the data issue | Data-quality answer: the kendras with suspicious records, why they are excluded, the action (check registers); data cards only | "Madha: schools with unreliable attendance records: 1 … Kendras with suspicious records (schools): Dhokkheda Budruk Kendra (1). They reported 100% attendance for 3 or more months in a row; this attendance is not used in the analysis until checked. The Kendra Pramukh should check the registers in person this week." | `test_q11_unreliable_records_name_the_kendra` |
| Q-12 | pandharpoor madhe kiti shala ahet, karmala PTR kiti, mohol la shikshak kiti kami. (misspelt, three questions) | Partly answered, then the whole brief | Answer every part | Multi-part questions are answered part by part, each with its own block (fuzzy spelling) | "Pandharpur has 140 schools in 12 clusters." / "Karmala: pupil-teacher ratio 26.5; 2 schools are above 30." / "Vacant teacher posts in Mohol: 2 (schools affected: 2); 498 working against 500 sanctioned." | `test_q12_three_questions_three_answers` |

### Voice and WhatsApp

| Channel | What happened | Feedback | What we changed | Regression test |
|---|---|---|---|---|
| Voice (web) | "which block need more attention" got "specify taluka". The reply "In the solapur district" was refused and the first question was lost. | Should understand it and keep the context | "need more attention" is understood. A reply to a clarifying question now **completes the previous question** (web, voice and WhatsApp). | `test_voice_followup_completes_the_question`, `test_whatsapp_followup_after_clarify` |
| WhatsApp (voice) | A question spoken in English got a Marathi reply | Reply in the language of the question | Speech-to-text now **auto-detects the spoken language**. Replies follow the language of the question, typed or spoken. | `test_reply_language_follows_the_question`, `test_whatsapp_english_question_gets_english_short_answer` (typed). Spoken: STT is called with automatic language detection; TODO: add a test with a faked English transcript. |
| Voice out | — | **Praised** the quality of the AI voice reply | No change | `tests/test_voice.py` |

### Overall changes from round 2

- **Short answers first.** Every answer has a mode: `fact`, `rank`, `why_up`, `dq`, `cards`, `cluster` or `twin`.
  - Facts, rankings and "why it improved" are lines only.
  - Attention questions (`cards`, `cluster`) show kendra cards.
  - The data-quality answer (`dq`) shows the data cards only.
  - The similar-block question (`twin`) shows the learn-from card.
  - The A/B/C brief and "Other checks" are inside "full evidence".
- **WhatsApp** sends the short answer first; the PDF comes on request (`REPORT_HINT`).
- **Role homes.** DEO = district picture (tiles, blocks needing attention, all blocks); BEO = "my kendras" as
  cards (`test_role_home_pages`, `GET /api/home?role=deo|beo`). On the web page, a role bar ("I am: DEO / BEO",
  with a block picker for BEO) opens the matching home.
- **UI redesign** toward a plain, government-website style. TODO: add a before/after screenshot.

---

## Internal red-team testing (adversarial code reviews)

Before stages 6.3 and 6.5 were committed, a multi-agent review tried to break each one from several lenses (correctness,
guardrails, privacy, officer experience). Only findings confirmed by a second pass were counted. All were fixed.

**Review 1: voice + PAB funding links (stage 6.3, 2026-10-28): 16 confirmed findings.** The main ones:
- the taluka-lens spoken script had dropped the trend and the cause;
- raw API errors were shown to officers (now fixed bilingual reasons);
- there was no voice spend cap (now `KAARAN_MAX_VOICE_INR`);
- the PAB citation check had no state filter (now Maharashtra rows only);
- the privacy notice was wrong;
- no voice note was sent when the PDF failed;
- test isolation.

**Review 2: direct answers (stage 6.5, 2026-10-28): 4 lenses, 8 agents, 23 confirmed findings.** The main ones:
- PTR cited an assessment file;
- blank cells crashed a block's answers;
- "which block has the best X" got the attention ranking;
- any question naming a block was answered;
- fuzzy kendra swaps; "madhale" matched Madha;
- schools with no teacher were left out of "PTR > 30";
- learning figures had no coverage note;
- "0.0 points lower";
- unrelated pointer notes;
- English examples in the Marathi help;
- "reasons" claimed for unexplained kendras;
- trust counts had no source.

Regression tests for these are in `tests/test_answers.py`, in the section "regressions from the adversarial
review", and in `tests/test_voice.py`.

Standing automated guardrail checks: prompt injection (`python -m kaaran.eval.guardrails`), invented numbers
(`python -m kaaran.eval.brief`, 0 so far), the 25-question intent eval, and the block-lens scorecard (19/19 on 6
seeds).

---

## Planned field testing (pilot)

**Goal.** Check with real users that Kaaran's answers are understood, trusted and acted on, and that the
rubric's actions and owners are right. Based on docs/06 §7 and the pilot metrics in docs/01 §7.

**Participants (first round).**
- The team's government primary school teacher: a 45-minute structured review of one printed brief (docs/06 §7).
- 2-3 teachers or head teachers: a 20-minute call with a printed brief.
- 2-3 BEOs or Kendra Pramukhs, and 1 DEO if possible. We will ask the mentor (CSF) for introductions.

**Setup.**
- The synthetic demo first (clearly marked SYNTHETIC), on the participant's own phone: web link or the WhatsApp
  simulator, or real WhatsApp if their number is registered.
- No real school data unless the district authorises it.
- Verbal consent. Notes are anonymised (role and block only). Audio is recorded only with permission.

**Session protocol (30 minutes).**
1. **Context (3 min).** "What data do you look at before a review meeting? What do you do when results fall?"
2. **Free use (7 min, think-aloud).** "Ask Kaaran what you would ask a data assistant." The observer notes the
   wording, the language (Marathi / English / mixed), typed or voice, and where they hesitate.
3. **Set tasks (10 min).** Use your block, or Pandharpur in the demo:
   - which kendras need attention;
   - why a kendra fell;
   - how many single-teacher schools there are;
   - which attendance records look unreliable;
   - open the source of one number;
   - download the PDF.

   For each task, record success (yes / with help / no) and the time.
4. **Brief review (5 min), from docs/06 §7.**
   - Part A: "Is this what you would want to know first?"
   - Part B: "Does this explanation make sense? What else would you check?"
   - Part C: "Would you do this? Who really owns it? By when?"
5. **Close (5 min).** "What would make you stop using this? What would make you use it every week? Is the
   Marathi natural?"

**What we record per session:**
- the questions asked, verbatim;
- task success and time;
- answers they did not trust, and why;
- actions they would take or reject;
- language corrections.

Each finding becomes a row in this file with the change made and a regression test, as in round 2.

**Pilot measures** (docs/01 §7):
- time from new data to a usable brief;
- trust flags confirmed on a field visit;
- recommended actions judged "doable and relevant";
- actions completed and re-checked the next month;
- weekly unprompted use.
