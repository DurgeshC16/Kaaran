# 06 · Decision rubrics: from "what is wrong" to "what to do on Monday"

> The mentor's core point: *actions are where every product is weak; an LLM gives generic advice; build a
> decision matrix that checks constraints before recommending an action.* This file is that matrix.
> It will live in code as versioned data (`src/kaaran/block/rubric_v1.json`). Thresholds marked † are starting
> values to be validated in user interviews (section 7) and are published so reviewers can challenge them.

---

## 1. The three questions and where each answer comes from

| Brief part | Officer's question | Produced by | LLM role |
|---|---|---|---|
| **A · लक्ष देण्याची गरज (What needs attention)** | Which clusters and schools, how bad, how sure? | Risk scanner (§2) + trust engine | wording only |
| **B · असे का होत असावे (Why it may be happening)** | What does the data say is different about them? | Differential diagnosis (§3), competency focus, positive deviance, data-trust findings | wording only |
| **C · काय करावे (What to do)** | What exactly, by whom, by when, and how will we know? | Decision rubric (§4) | wording only |

Evidence strength shown to officers in plain words: **ठाम पुरावा (strong evidence)** = STRONG rule passed;
**शक्यता (possible)** = WEAK; **सांगता येत नाही (cannot tell)** = INSUFFICIENT. Rule ids stay in the appendix.

## 2. Risk scanner (part A)

Unit = cluster inside a block (and school inside a cluster). Computed on **trusted** data only.

| Rule | Condition | Risk weight |
|---|---|---|
| RISK-LEVEL | cluster's latest assessment % (grade 3 maths or language, all competencies) is in the bottom quartile of the block **and** ≥ 5 points† below the block median | 2 |
| RISK-DROP | cluster fell ≥ 5 points† between the last two rounds (school-level paired comparison, t ≤ −2) | 3 |
| RISK-COMPETENCY | ≥ 2 foundational competencies below 50%† correct | 1 |
| RISK-ATTENDANCE | trusted student attendance < 75%† in ≥ 2 of the last 3 months | 1 |
| RISK-DATA | ≥ 20% of the cluster's schools red-flagged (records cannot be trusted) | 2 (separate "data" alert) |

A cluster is **at risk** when its weight ≥ 3; an alert is sent when ≥ 1 cluster is at risk or a RISK-DATA
flag is new. Schools are listed under their cluster, ordered by drop. **Never ranked by teacher.**

## 3. Differential diagnosis (part B)

For each at-risk cluster, every check runs. Each check produces PASS (pattern present), FAIL (not present),
or CANNOT_TELL (not enough data). A check passes as **STRONG** only with effect + share + comparison +
timing (the Hill-style criteria already in CONFIDENCE_RULES.md); otherwise **WEAK**.

| Check | Pattern looked for | Indicators |
|---|---|---|
| D1 Staffing gap | working teachers < sanctioned, PTR > 30† (RTE primary norm), single-teacher or multigrade schools concentrated in the drop | `teacher_posts`, `teachers_year`, `enrolment` |
| D2 Support gap | PTR ≤ 30, no vacancy, attendance fine, but CRC/Kendra Pramukh visits < 1 per school per month† and/or no teacher training in 12 months† | `support_visits`, `training`, `teacher_posts` |
| D3 Student absence | trusted attendance low and falling in the same schools that dropped (exposed vs unexposed comparison) | `attendance` |
| D4 Seasonal migration | attendance falls Nov-Mar† in specific villages, recovers Jun-Jul; enrolment drops mid-year | `attendance` by month, `enrolment` |
| D5 Non-teaching duty | duty days high in the months before the assessment; comparable clusters with the same duty did not drop | `teacher_posts.duty_days`, election dates |
| D6 Data problem | the "drop" or "rise" sits in flagged schools (flat attendance with low learning, reverting assessment spikes) | trust findings |
| D7 Competency-specific | the fall is concentrated in 1-2 competencies (e.g. place value, subtraction with borrowing) | `assessment` by competency |
| D8 No clear pattern | none of D1-D7 passes | — |

**Positive deviance (also part B):** schools in the same block with the same constraint (e.g. multigrade,
vacancy, PTR > 30) that **improved** ≥ 5 points†. Shown as "learn from" with the constraint they share.
**Twin block** (DEO view): most similar block on enrolment, school count, poverty and duty exposure that
improved (rule in CONFIDENCE_RULES.md).

## 4. Action rubric (part C)

Each row: **when** (diagnosis + constraint checks) → **action** → **owner** (within powers) → **when by** →
**follow-up metric** (re-checked next month). An action is only proposed if all its constraint checks pass;
otherwise the next row applies. The officer confirms before anything is forwarded.

| Id | When (diagnosis) | Constraint checks | Action | Owner | By | Follow-up metric |
|---|---|---|---|---|---|---|
| A1 | D1 staffing gap | a school in the same block has PTR < 20† (surplus) | **Redeploy / rationalise** a teacher from the named surplus school(s) to the gap school(s) | BEO proposes, DEO orders | this month | working teachers and PTR in the gap schools |
| A2 | D1 staffing gap | no surplus school in the block | **Request a guest / contract teacher** for the gap schools; escalate vacancy list | DEO | this month | posts filled |
| A3 | D1 with multigrade schools | — (always, as interim) | **Multigrade support**: Kendra Pramukh visit with multigrade lesson plans and grouping by level | Kendra Pramukh | this week | visit logged; next-round competency change |
| A4 | D2 support gap | visits < 1/school/month | **Mentoring cycle**: weekly CRC/Kendra Pramukh classroom visits to the at-risk schools for 4 weeks, focused on the weakest competencies | Kendra Pramukh, BEO reviews | start this week | visits per school-month; next-round change |
| A5 | D2 support gap | training older than 12 months† **and** competency-specific fall (D7) | **Targeted training** on the named competencies (cluster-level teacher meeting) | BEO with DIET/BRC | this month | training logged; competency change |
| A6 | D2 or D8, teachers available, PTR ≤ 30 | — | **Accountability review**: discuss the cluster in the बैठक, school-wise targets, weekly review call with HMs for 4 weeks | BEO | next बैठक | targets set; next-round change |
| A7 | D3 student absence | attendance trusted | **Attendance drive**: HM + SMC home visits for children absent > 10 days/month; SMC meeting | HM, SMC, Kendra Pramukh | this month | attendance next month |
| A8 | D4 seasonal migration | pattern repeats in ≥ 2 years or in named villages | **Migration tracking**: list migrating children, coordinate seasonal hostel / destination schooling, bridge classes on return | BEO, HM | before Nov | children tracked; attendance Nov-Mar |
| A9 | D5 non-teaching duty | duty months overlap assessment | **Plan duty rotation** / request exemption around assessment windows; no blame on schools | DEO | before next duty order | duty days in assessment months |
| A10 | D6 data problem | — (always first) | **Verify registers in person** in the flagged schools; do not act on their results until verified | Kendra Pramukh | this week | flags confirmed / cleared |
| A11 | Insufficient data | ≥ 20% schools missing | **Collect missing data**; conclusions withheld | BEO | this month | completeness |
| A12 | Positive deviant found | same constraint as the at-risk school | **Peer visit**: teachers from the at-risk school visit the positive-deviant school; document the practice | BEO | this month | visit done; practice note |
| A13 | Twin block improved (DEO) | similar profile, same duty years | **Exposure visit** to the twin block | DEO / BEO | this month | visit done |

Ordering rule (code): A10/A11 first (fix the data), then the cause-specific action with the strongest
evidence, then supporting actions; at most **3 actions per cluster and 5 per brief**.

## 5. Worked example (the mentor's case, as Kaaran will output it)

*Block with 4 clusters (A-D); grade 3 maths fell. Synthetic illustration: no real place or school.*

**A · What needs attention**
- Clusters A and B: 19 schools, maths down 8 points since the last round (strong evidence).
  The other two clusters are stable.
- 6 schools in cluster B have attendance records that look unreliable (100% for 4 months).

**B · Why it may be happening**
- Cluster A: enough teachers (PTR 18), attendance normal, but only 2 Kendra Pramukh visits in 3 months
  across 10 schools. Place value and subtraction fell most. → support gap (possible).
- Cluster B: 4 of 9 schools are short of a teacher and run multigrade classes (PTR 41) → staffing gap
  (strong evidence).
- School B-07 (cluster B): multigrade with a vacancy, yet improved 6 points → learn from it.
- Election duty in November affected all 4 clusters; the 2 stable clusters did not fall → not the main reason.

**C · What to do**
1. Cluster A: weekly Kendra Pramukh classroom visits for 4 weeks on place value and subtraction
   (Kendra Pramukh, start this week; check: visits logged, next round).
2. Cluster B: redeploy one teacher from school D-03 (PTR 14, cluster D) to the two neediest schools (BEO proposes,
   DEO orders, this month; check: PTR next month).
3. Cluster B: verify the attendance registers of the 6 flagged schools before judging them (Kendra Pramukh,
   this week).

## 6. How the rubric stays honest

- Every action cites the finding ids it is based on; the evidence pack stores the rubric version.
- An action whose constraint check fails is not shown (and the reason is logged in the appendix).
- No action targets an individual teacher. Accountability actions are at school/cluster level and run
  through the existing review meeting.
- Thresholds marked † are config; changes are versioned and visible to reviewers.
- The eval answer key includes the expected action per planted scenario; tests fail if the rubric picks a
  different one.

## 7. Validating the rubric with real people (before 30 Oct)

| Who | How | What we ask |
|---|---|---|
| Team member (government primary teacher, Khadki, Pune) | 45-min structured interview + brief review | Which actions are realistic for a school; what a Kendra Pramukh actually does in a visit; register practices |
| 2-3 teachers / HMs (team families, referrals) | 20-min call with printed brief | Is part C doable? What would you do instead? |
| 1-2 officers or ex-officers (BEO / Kendra Pramukh / DIET faculty) | 30-min call; ask Rupala (CSF) by email for a contact | Are owners and powers right? Which thresholds feel wrong? |
| Rupala (mentor, CSF) | email with the rubric table | Does the matrix capture the constraints she described? |

Interview guide (each): (1) show part A only: "Is this what you would want to know first?" (2) part B:
"Does this explanation make sense? What else would you check?" (3) part C: "Would you do this? Who really
owns it? By when?" (4) "What would make you stop using this?" Record answers and the change we made in
`docs/USER_TESTING.md` (evidence for the 35% criterion).
