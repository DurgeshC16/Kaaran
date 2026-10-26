# 03 · Literature survey: what exists, what the evidence says, and where Kaaran is different

> Scope: (1) how education systems use data, in India and abroad; (2) what research says about why data
> rarely becomes action; (3) AI and LLM approaches to data analysis and their failure modes; (4) the
> methods Kaaran borrows; (5) Indian-language speech. Section 7 states the novelty claim.
>
> Citation note: entries were checked for author, title and venue on 2026-10-27. Check page numbers and
> exact quotes against the original before putting a citation on a slide.

---

## 1. Education data systems in India

| System | What it gives | Limitation for a block officer |
|---|---|---|
| **UDISE+** (Ministry of Education) | Yearly census of schools: infrastructure, enrolment, teachers. School-level microdata (pseudo IDs) on registration. | Yearly; self-reported and hard to verify; describes inputs, not learning; used mostly for compliance. |
| **NAS 2017 / 2021** (NCERT) | Learning levels for grades 3, 5, 8, 10, reported by district. | Sample-based, district level, every few years; little follow-up action. |
| **Foundational Learning Study 2022** (NCERT) | Grade 3 FLN baseline for NIPUN Bharat; state and low-performing-district reports. | One-off baseline; state/district level. |
| **PARAKH Rashtriya Sarvekshan 2024** (NCERT) | Competency-based results for grades 3, 6, 9 for 782 districts; district report cards disseminated in district workshops (2025). | District as the unit; e.g. Solapur's grade-3 sample is 40 schools. Says *where the district stands*, not *which school or why*. |
| **PGI-D** (district Performance Grading Index) | Composite district grade. | Ranking, not diagnosis. |
| **State MIS / Vidya Samiksha Kendras** (e.g. Gujarat's Command and Control Centre; Maharashtra's systems) | Near-real-time attendance, assessments, teacher data; dashboards for officials; Gujarat plans school visits based on data indicators. | Dashboards show *what*; the officer still has to work out *why* and *what to do*. Most officers do not open them unprompted (mentor review). |
| **ASER** (ASER Centre) | Independent household survey of reading and arithmetic, rural districts. | Rural, district-level, every two years. |

The challenge's own background note (*Using Data to Improve Teaching and Learning in India*, Education for
All in India, 2024) lists the same structural problems: data collection separated from use (MIS officers
collect, nobody analyses), many disconnected portals, poor record quality, low data literacy, and no
follow-up after surveys. It recommends starting small, focusing on learning, ensuring data quality and
closing the feedback loop. **Kaaran is built around exactly these four.**

## 2. What research says about data and action

1. **Assessments and plans alone do not change learning.** Muralidharan & Singh (2020), *Improving Public
   Sector Management at Scale? Experimental Evidence on School Governance in India* (NBER WP 28129;
   RISE WP 20/056), evaluated Madhya Pradesh's school quality assessment programme in 1,774 randomly
   selected schools. Assessments were completed and ratings were informative, yet there was **no effect on
   school functioning or learning**; officials described the main effect as more paperwork. The programme
   was nevertheless scaled to over 600,000 schools.
   → *Implication for Kaaran:* a report is not an intervention. Actions must be specific, owned, checked
   next month and discussed in the review meeting. Hence the decision rubric, the baithak pack and the
   follow-up re-check.
2. **Administrative data is often inflated.** Singh (2020), *Myths of Official Measurement: Auditing and
   Improving Administrative Data in Developing Countries* (RISE WP 20/042), found reported achievement in
   Madhya Pradesh severely inflated, most of all for low performers, and that teacher-proctored paper tests
   exaggerate achievement (Andhra Pradesh experiment). Follow-ups: Berg & Singh (2024, *Journal of Public
   Economics*) and Singh (2024, *Economic Journal*, digital testing at scale).
   → *Implication:* trust checks must run **before** any conclusion, and implausible combinations (high
   attendance with low learning, reverting spikes) are findings in their own right.
3. **Teachers present is necessary, not sufficient.** Kremer, Chaudhury, Rogers, Muralidharan & Hammer
   (2005), *Teacher Absence in India: A Snapshot* (JEEA), found about a quarter of teachers absent on any
   given day. Duflo, Dupas & Kremer (2015, *Journal of Public Economics*) found that extra contract teachers
   in Kenya improved learning only where accountability and governance worked.
   → *Implication:* "PTR is fine" must lead to a different action (support, accountability) than "teachers
   are missing" (redeploy). This is the mentor's cluster A vs cluster B example, encoded in the rubric.
4. **Targeted instruction and coaching work at scale when data drives them.** Banerjee et al. (2017),
   *From Proof of Concept to Scalable Policies* (*Journal of Economic Perspectives*), on Teaching at the
   Right Level; Piper, Destefano, Kinyanjui & Ong'ele (2018), *Scaling up successfully: Lessons from
   Kenya's Tusome national literacy program* (*Journal of Educational Change*): coaches use classroom data
   for immediate feedback.
   → *Implication:* actions should point to **competencies** and **coaching visits**, not generic training.
5. **Composite indicators and accountability abroad.** Brazil's IDEB (Bruns, Evans & Luque, 2012, World
   Bank), Chile's SEP, Vietnam's balanced scorecard: data tied to targeted support and follow-up.
   World Bank (2018), *World Development Report: Learning to Realize Education's Promise*: measure
   learning, act on it, align actors.
6. **Positive deviance.** Pascale, Sternin & Sternin (2010), *The Power of Positive Deviance*: solutions
   often already exist in peers that succeed under the same constraints.
   → *Implication:* the twin block and positive-deviant school ("multigrade, vacancy, still improving")
   make actions local and credible.

## 3. AI and LLM approaches to data analysis

| Approach | Examples | Strength | Failure mode for our use |
|---|---|---|---|
| Chat over data (LLM reads tables) | General assistants with file upload; "Gemini/GPT over state data" (the mentor's comparison) | Easy, flexible | Invents or miscomputes numbers; generic actions; no trust checks; answers only when asked |
| LLM writes code to compute | PAL (Gao et al., 2023, ICML); Program of Thoughts (Chen et al., 2023, TMLR); Data Interpreter (Hong et al., 2024) | Numbers come from execution | The *analysis plan* is still improvised per question; not auditable as a fixed rule; hard to certify for government |
| Text-to-SQL agents | BIRD benchmark (Li et al., 2023, NeurIPS Datasets & Benchmarks) | Natural-language querying | Even strong models fail many realistic queries on messy schemas; answers "what", not "why" |
| Auto-visualisation | LIDA (Dibia, 2023, ACL demo) | Charts from data | Dashboards again; officer still interprets |
| BI dashboards with AI copilots | Commercial BI tools | Mature | Requires clean data, trained users, and someone who opens them |
| Retrieval-augmented generation | Lewis et al. (2020, NeurIPS) | Grounds text in documents | Retrieves text, not computed evidence; useful for policy documents, not for numbers |

Known LLM risks that shape our design:
- **Hallucination in data-to-text:** Wiseman, Shieber & Rush (2017, EMNLP) showed neural generators state
  wrong numbers when describing tables; Ji et al. (2023, *ACM Computing Surveys*) survey the problem.
  Delexicalised generation (e.g. Wen et al., 2015, EMNLP) writes slot placeholders that code fills.
  **Kaaran's `{{n:id}}` placeholders + verifier are a modern, checked version of this idea.**
- **Indirect prompt injection:** Greshake et al. (2023, AISec) showed instructions hidden in data can
  hijack LLM applications. **Kaaran passes file contents as quoted, masked summaries and tests an injected
  file (guardrail test).**

## 4. Methods Kaaran borrows

| Method | Source | Where in Kaaran |
|---|---|---|
| Criteria for moving from association to causation: strength, consistency, temporality, specificity, gradient | Hill (1965), *The Environment and Disease: Association or Causation?* (*Proc. R. Soc. Med.*) | STRONG requires effect size + share of decline + replication elsewhere + correct timing (CONFIDENCE_RULES.md) |
| Comparison with unexposed groups, before/after | Difference-in-differences logic (Angrist & Pischke, 2009, *Mostly Harmless Econometrics*) | exposed vs unexposed schools; pre-exposure check |
| Robust outlier detection (median / MAD) | standard robust statistics | attendance jump rule |
| Matching on covariates | nearest-neighbour matching on standardised covariates | twin block / comparable schools |
| Positive deviance | Pascale et al. (2010) | learn-from twin; positive-deviant schools |
| Decision tables / rule engines | classic expert systems; clinical decision support | decision rubric (doc 06): situation + constraints → action |
| Delexicalised NLG + verification | Wen et al. (2015); data-to-text faithfulness research | placeholders + deterministic verifier |

## 5. Indian-language speech

| Option | What it is | Notes |
|---|---|---|
| AI4Bharat **IndicConformer** (Marathi) | Open ASR, Conformer-Large, ~120M parameters, hybrid CTC/RNNT, MIT licence (AI4Bharat GitHub; AIKosh listing); 600M multilingual variant | Small enough to self-host on CPU/small GPU; needs NeMo |
| AI4Bharat **Vistaar** benchmarks / IndicWhisper | Bhogale et al. (2023, Interspeech) | Benchmark for comparing Marathi ASR |
| **IndicVoices** | Javed et al. (2024, ACL Findings) | Large natural-speech dataset incl. Marathi; useful test reference |
| **Bodhan AI** (IIT Madras + AI4Bharat, Sept 2026) | Open models for education incl. ASR (27 languages) and TTS (23 languages), open weights + hosted APIs, planned as Digital Public Goods | Recommended by the mentor; education-specific; check licence before self-hosting |
| Bhashini (Government of India) | Hosted speech/translation APIs | The mentor reports weaker quality in practice |
| OpenAI Whisper | Radford et al. (2023, ICML) | Open, multilingual; weaker on Marathi than Indic-tuned models |

Kaaran's design keeps speech **pluggable**: speech-to-text produces text, and the intent parser then
snaps place names to the fixed gazetteer and asks for confirmation when unsure, so ASR errors on names do
not silently change the analysis.

## 6. Comparison table

| Capability | Dashboards (UDISE+, PGI-D, state VSK) | Chat-with-data LLM | Text-to-SQL / code agents | Manual analysis by a "smart mentor" | **Kaaran** |
|---|---|---|---|---|---|
| Starts without a question (proactive) | partly (alerts in some states) | no | no | no | **yes: scans on data arrival, sends alert** |
| Checks data trust first | no | no | no | sometimes | **yes, rule-based, reported** |
| Explains *why* (tests causes, rules some out) | no | improvised | improvised | yes, slow | **yes, fixed tests with thresholds** |
| Different diagnosis per cluster | no | maybe | maybe | yes | **yes: differential diagnosis** |
| Actions grounded in constraints | no | generic | no | depends on person | **yes: decision rubric, owner, deadline** |
| Every number traceable to file/row | partly | no | partly | no | **yes, click to source; verified** |
| Learns from peers (positive deviance) | no | no | no | sometimes | **yes: twin block, positive-deviant schools** |
| Marathi, WhatsApp, voice | rarely | partly | no | yes | **yes** |
| Closes the loop (review meeting, re-check) | no | no | no | rarely | **yes: baithak pack + next-month re-check** |
| Works on messy files | no | partly | no | yes | **yes: AI column mapper + validation** |

## 7. Novelty claim (what is new)

Kaaran is not a dashboard and not a chatbot. Its contribution is an **evidence-to-action pipeline** that
combines, for the first time in this setting:

1. **Trust before analysis** as a first-class output: implausible records become findings and actions
   ("verify these 23 registers"), grounded in evidence that Indian administrative data is often inflated.
2. **Differential diagnosis per cluster** with fixed, published tests (Hill-style criteria), so two
   clusters with the same fall get different explanations, and causes that fail are shown as ruled out.
3. **A constraint-aware decision rubric** that maps situation + constraints to an action within a named
   officer's powers, with a follow-up metric. Actions are data (versioned JSON) that SCERT and officers
   can review, not LLM improvisation.
4. **Positive deviance built in:** a comparable block or school that improved under the same
   constraints becomes the "learn from" action.
5. **LLM used only for language** (understanding the question, mapping messy columns, writing Marathi),
   with placeholders and a deterministic verifier, giving **zero invented numbers** by construction and test.
6. **Proactive, closed loop:** alerts on data arrival, a baithak pack for the monthly review, and a
   re-check next month. This directly targets the failure mode in Muralidharan & Singh (2020).

## 8. References

- Angrist, J. D., & Pischke, J.-S. (2009). *Mostly Harmless Econometrics*. Princeton University Press.
- Banerjee, A., Banerji, R., Berry, J., Duflo, E., Kannan, H., Mukerji, S., Shotland, M., & Walton, M. (2017). From proof of concept to scalable policies: Challenges and solutions, with an application. *Journal of Economic Perspectives*, 31(4), 73-102.
- Berg, P., & Singh, A. (2024). Myths of official measurement: Limits to test-based education reforms with weak governance. *Journal of Public Economics*.
- Bhogale, K., et al. (2023). Vistaar: Diverse benchmarks and training sets for Indian language ASR. *Interspeech 2023*.
- Bruns, B., Evans, D., & Luque, J. (2012). *Achieving World-Class Education in Brazil: The Next Agenda*. World Bank.
- Chen, W., Ma, X., Wang, X., & Cohen, W. W. (2023). Program of thoughts prompting. *Transactions on Machine Learning Research*.
- Dibia, V. (2023). LIDA: A tool for automatic generation of grammar-agnostic visualizations and infographics using LLMs. *ACL 2023 System Demonstrations*.
- Duflo, E., Dupas, P., & Kremer, M. (2015). School governance, teacher incentives, and pupil-teacher ratios: Experimental evidence from Kenyan primary schools. *Journal of Public Economics*, 123, 92-110.
- Education for All in India (2024). *Using Data to Improve Teaching and Learning in India* (challenge background reading).
- Gao, L., et al. (2023). PAL: Program-aided language models. *ICML 2023*.
- Greshake, K., et al. (2023). Not what you've signed up for: Compromising real-world LLM-integrated applications with indirect prompt injection. *AISec 2023*.
- Hill, A. B. (1965). The environment and disease: Association or causation? *Proceedings of the Royal Society of Medicine*, 58(5), 295-300.
- Hong, S., et al. (2024). Data Interpreter: An LLM agent for data science. arXiv:2402.18679.
- Javed, T., et al. (2024). IndicVoices: Towards building an inclusive multilingual speech dataset for Indian languages. *Findings of ACL 2024*.
- Ji, Z., et al. (2023). Survey of hallucination in natural language generation. *ACM Computing Surveys*, 55(12).
- Kremer, M., Chaudhury, N., Rogers, F. H., Muralidharan, K., & Hammer, J. (2005). Teacher absence in India: A snapshot. *Journal of the European Economic Association*, 3(2-3), 658-667.
- Lewis, P., et al. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks. *NeurIPS 2020*.
- Li, J., et al. (2023). Can LLM already serve as a database interface? A big bench for large-scale database grounded text-to-SQLs (BIRD). *NeurIPS 2023 Datasets and Benchmarks*.
- Muralidharan, K., & Singh, A. (2020). Improving public sector management at scale? Experimental evidence on school governance in India. NBER Working Paper 28129 / RISE Working Paper 20/056.
- NCERT (2022). *Foundational Learning Study* (state and district reports). NCERT (2025). *PARAKH Rashtriya Sarvekshan 2024* district report cards.
- Pascale, R., Sternin, J., & Sternin, M. (2010). *The Power of Positive Deviance*. Harvard Business Press.
- Piper, B., Destefano, J., Kinyanjui, E. M., & Ong'ele, S. (2018). Scaling up successfully: Lessons from Kenya's Tusome national literacy program. *Journal of Educational Change*, 19(3), 293-321.
- Radford, A., et al. (2023). Robust speech recognition via large-scale weak supervision (Whisper). *ICML 2023*.
- Singh, A. (2020). Myths of official measurement: Auditing and improving administrative data in developing countries. RISE Working Paper 20/042.
- Wen, T.-H., et al. (2015). Semantically conditioned LSTM-based natural language generation for spoken dialogue systems. *EMNLP 2015*.
- Wiseman, S., Shieber, S., & Rush, A. (2017). Challenges in data-to-document generation. *EMNLP 2017*.
- World Bank (2018). *World Development Report 2018: Learning to Realize Education's Promise*.
