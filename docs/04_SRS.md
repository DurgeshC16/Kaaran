# 04 · Software Requirements Specification (SRS), Kaaran v2

> Structure loosely follows IEEE 830. "Must / Should / Could" = priority for the hackathon build
> (deadline 1 Nov 2026). Status: ✅ built · 🟡 partly built · ⏳ planned.

---

## 1. Introduction

**Purpose.** Define what Kaaran v2 must do so that a block or district education officer gets a trusted,
actionable, Marathi-first brief from the data their office already has, without having to ask first.

**Scope.** Data intake (files and connectors), trust checks, insight engine (risk, diagnosis, positive
deviance), decision rubric (actions), language layer (intent, writing, verification), channels (WhatsApp,
web, PDF, voice), proactive alerts, review-meeting (बैठक) pack, action follow-up.
Out of scope: OCR of handwritten registers, student-level tracking, teacher evaluation, any ranking of
individuals.

**Definitions.** BEO: Block Education Officer (गट शिक्षणाधिकारी). DEO: District Education Officer.
Kendra Pramukh (केंद्रप्रमुख): cluster head. Cluster (केंद्र): 10-20 schools. PTR: pupil-teacher ratio.
Evidence pack: the JSON contract between engines and the language layer (EVIDENCE_SCHEMA.md).
Rubric: the decision table in doc 06. Baithak: monthly review meeting.

## 2. Overall description

### 2.1 Users

| User | Goal | Constraints |
|---|---|---|
| **BEO** (primary) | Know which clusters/schools need attention, why, and what to assign in the next review | Low time; basic Android phone; Marathi; patchy network; not a data analyst |
| **DEO** | Compare blocks; see which blocks need support; follow up on actions | Same; oversees 10-15 BEOs |
| **Kendra Pramukh** | Receive assigned actions for their cluster; report completion | Mostly WhatsApp |
| **District MIS / data officer** | Upload or connect data; fix flagged records | Has the files; technical but not pedagogical |
| **State / SCERT** (later) | Maintain the decision rubric and thresholds; see state-wide patterns | Needs auditability |

### 2.2 Operating environment
WhatsApp (Cloud API), any modern browser, PDF readers on low-end phones. Server: Linux or Windows,
Python 3.11. Works offline-first for analysis (no LLM needed for numbers or actions).

### 2.3 Design constraints (non-negotiable rules)
1. The LLM never produces numbers, labels or actions. 2. Labels come from deterministic rules.
3. "Associated with", not "caused by", unless STRONG criteria pass. 4. Trust checks before analysis;
unreliable data is reported, never dropped silently. 5. Only aggregates go to an external LLM.
6. Marathi first, English second. 7. Synthetic data always marked SYNTHETIC. 8. No secrets or real data
in the repository.

## 3. Use cases

| ID | Use case | Actor | Trigger | Outcome |
|---|---|---|---|---|
| UC-1 | **Proactive alert** | System → BEO | New assessment round or monthly attendance arrives | WhatsApp message: "N clusters need attention" + link; brief on tap |
| UC-2 | Ask a question | BEO / DEO | Text or voice question | Clarify / refuse / brief |
| UC-3 | Read the three-part brief | BEO | UC-1 or UC-2 | A: what needs attention · B: why · C: what to do; PDF + voice summary |
| UC-4 | Drill down | BEO | Click a number or a school count | Source (file, sheet/page, row, calculation) or school list |
| UC-5 | Baithak pack | BEO | Two days before the monthly review (scheduled) or on request | Cluster-wise agenda with assigned actions, owners, last month's follow-up |
| UC-6 | Assign and track an action | BEO → Kendra Pramukh | BEO confirms a recommended action | Action forwarded; status tracked; metric re-checked next month |
| UC-7 | Upload data | MIS officer / BEO | Files from state systems | Mapped (AI proposer + validation), ingested with provenance, trust-checked |
| UC-8 | District view | DEO | Alert or question | Blocks needing support, twin blocks, actions open per block |

## 4. Functional requirements

### 4.1 Data intake
| ID | Requirement | Priority | Status |
|---|---|---|---|
| FR-1 | Read xlsx, csv and text-based PDF exports, including messy headers, merged title rows, Marathi/English/transliterated column names | Must | ✅ |
| FR-2 | Map columns to the canonical model with a rule baseline and an AI proposer; validate every mapping; fall back to rules | Must | ✅ |
| FR-3 | Read **UDISE+ microdata format** (`prof1, prof2, tch, enr1, fac`) | Must | ⏳ |
| FR-4 | Support the **block → cluster → school** hierarchy (kendra list) | Must | ⏳ |
| FR-5 | Read competency-wise assessment exports (school × round × grade × competency) | Must | ⏳ |
| FR-6 | Read monthly teacher-post, attendance, support-visit and training exports | Must | 🟡 (posts, attendance ✅; visits, training ⏳) |
| FR-7 | Keep provenance (file, sheet/page, row) on every canonical row | Must | ✅ |
| FR-8 | Officer upload through the web (and later WhatsApp media) | Should | ⏳ |
| FR-9 | Load real district benchmarks (PRS 2024, FLS 2022, NAS 2021) with a "benchmark only" flag | Should | ⏳ |

### 4.2 Trust engine
| ID | Requirement | Priority | Status |
|---|---|---|---|
| FR-10 | Flag flat attendance runs, deseasonalised jumps, reverting score spikes, missing data, contradictory duplicates | Must | ✅ |
| FR-11 | Clear honest low-attendance schools explicitly (protect honest teachers) | Must | ✅ |
| FR-12 | Flag impossible combinations (very high attendance with very low learning), PTR anomalies, reverting assessment spikes | Must | ⏳ |
| FR-13 | Mark outdated sources; outdated data cannot trigger alerts | Should | ⏳ |
| FR-14 | Cap conclusions for units with too much missing data at "cannot tell" | Must | ✅ |

### 4.3 Insight engine
| ID | Requirement | Priority | Status |
|---|---|---|---|
| FR-20 | **Risk scanner**: score every cluster and school in a block on level, change and trust; select at-risk units with fixed thresholds | Must | ⏳ |
| FR-21 | **Differential diagnosis per at-risk cluster**: run the rubric checks (staffing, PTR, attendance, support visits, training, non-teaching duty, migration pattern, data trust) and label each with evidence strength | Must | ⏳ (taluka-level version ✅) |
| FR-22 | Competency focus: name the weakest competencies in each at-risk cluster | Must | ⏳ |
| FR-23 | **Positive deviance**: find schools/clusters that improved under the same constraints; twin block for the DEO view | Must | 🟡 (twin taluka ✅) |
| FR-24 | Election / non-teaching-duty check: rule out district-wide events as the cause when comparable units without the drop exist | Should | ✅ |
| FR-25 | Every finding carries rule id, criteria, thresholds, pass/fail and provenance for each number | Must | ✅ |

### 4.4 Decision rubric (actions)
| ID | Requirement | Priority | Status |
|---|---|---|---|
| FR-30 | Actions come only from the rubric table (doc 06): diagnosis + constraint checks → action, owner, deadline, follow-up metric | Must | ⏳ (4-item catalog ✅) |
| FR-31 | Constraint checks before an action (e.g. redeploy only if a surplus school exists in the block) | Must | ⏳ |
| FR-32 | Every action is within the named officer's powers and cites the finding it is based on | Must | ✅ |
| FR-33 | Rubric stored as versioned data (JSON), reviewable without code changes | Must | ⏳ |

### 4.5 Language layer
| ID | Requirement | Priority | Status |
|---|---|---|---|
| FR-40 | Intent parser: question → validated plan; clarify instead of guessing; refuse individual/personal requests | Must | ✅ |
| FR-41 | Writer: Marathi + English prose with placeholders; code fills numbers, names, periods | Must | ✅ |
| FR-42 | Verifier: no invented digits, no causal words unless STRONG, no school names, all sections present; retry once, then templates | Must | ✅ |
| FR-43 | **Three-part brief** (A attention / B why / C what to do) + appendix; one page | Must | ⏳ (6-section ✅) |
| FR-44 | Voice: Marathi speech-to-text in; one-minute Marathi voice summary out (numbers read from code-formatted words) | Should | ⏳ |
| FR-45 | Confirm before analysing when the place, a school name, a number or a period was heard with low confidence | Should | 🟡 (place for text ✅) |

### 4.6 Channels, alerts and loop
| ID | Requirement | Priority | Status |
|---|---|---|---|
| FR-50 | Web demo: question, brief, click-to-source, school lists, PDF and evidence downloads | Must | ✅ |
| FR-51 | WhatsApp: signed webhook, de-duplication, summary + PDF reply, language switch | Must | ✅ |
| FR-52 | **Proactive scan**: on new data, scan all blocks and create alerts above threshold | Must | ⏳ |
| FR-53 | Alert delivery on WhatsApp (template message outside the 24-hour window) and in a web inbox | Must | ⏳ |
| FR-54 | **Baithak pack**: cluster-wise agenda, assigned actions, last month's follow-up | Should | ⏳ |
| FR-55 | Action tracking: assign, status, next-month metric re-check | Should | ⏳ |
| FR-56 | DEO view: blocks needing support, open actions per block | Could | ⏳ |

## 5. Non-functional requirements

| ID | Category | Requirement | How we verify |
|---|---|---|---|
| NFR-1 | Accuracy | 0 numbers without provenance; 0 invented numbers in any brief | verifier on every brief; eval over 5+ seeds |
| NFR-2 | Correctness | Planted truths in synthetic data found with 0 wrong verdicts and 0 false flags on honest schools | eval scorecard (now 8/8 on 5 seeds; v3 adds new truths) |
| NFR-3 | Latency | Cached brief < 3 s; new brief < 60 s; block scan < 5 s; district scan < 60 s | timing tests |
| NFR-4 | Cost | < $0.10 per brief; < $0.001 per question; analysis and actions cost $0 (no LLM) | usage log |
| NFR-5 | Language | Marathi first; plain words; native-speaker review of templates and samples | review log in user-testing doc |
| NFR-6 | Low bandwidth | WhatsApp text summary < 4,096 chars; PDF ≤ 1 page, < 300 KB; web works without external CDNs | tests |
| NFR-7 | Privacy | Only aggregates reach the LLM; school names only in the local drill-down; phone numbers masked in logs | `llm_view` tests; verifier |
| NFR-8 | Security | Webhook HMAC check; no secrets in repo; RBAC for officers (pilot) | tests; git checks |
| NFR-9 | Graceful degradation | Without LLM: rule intent + template brief; without browser: HTML print view; without voice: text | tests in replay/off modes |
| NFR-10 | Auditability | Every brief reproducible from inputs (file hashes, rule ids, rubric version) | evidence pack fields |
| NFR-11 | Scalability | Stateless analysis per block; state of 300+ blocks scanned in minutes on one server | benchmark on synthetic state |
| NFR-12 | Portability | New state = config (column mapping, rubric thresholds, language texts), not code | config-driven tests |
| NFR-13 | Maintainability | Test suite green before every commit; each engine testable alone through the evidence-pack contract | CI-equivalent local run |

## 6. Acceptance criteria for the hackathon build

1. On the v3 synthetic district, a scan of the focus block produces an alert naming the right at-risk
   clusters (answer key) and no honest cluster.
2. The two planted failing clusters get **different** diagnoses and **different** actions
   (staffing gap → redeploy/guest teacher; support gap → mentoring cycle + weekly review).
3. The positive-deviant school is reported in part B, the twin block in the DEO view.
4. Every number in the brief opens its source; verifier passes; 0 invented numbers across 5 seeds.
5. The brief fits one page with A / B / C, in Marathi and English, and a voice summary is produced.
6. The same pipeline runs on the real UDISE+ format (real file when available) and shows the real PRS 2024
   benchmark with its source.
7. At least 3 users (teacher on the team + officers/teachers) tested it; changes made from their feedback
   are listed.

## 7. Traceability to the judging criteria

| Criterion (weight) | Requirements that score it |
|---|---|
| Efficacy & user-centricity (35%) | FR-20..23, FR-30..33, FR-43..45, FR-52..55, NFR-5, NFR-6, acceptance 7 |
| Effective AI use & technical strength (30%) | FR-2, FR-40..42, NFR-1, NFR-2, NFR-7..10, acceptance 4, 6 |
| Innovation (25%) | FR-12, FR-21, FR-23, FR-30..31, FR-52, FR-54 |
| Future roadmap (10%) | FR-3, FR-9, NFR-11, NFR-12, doc 07 pilot and state plan |
