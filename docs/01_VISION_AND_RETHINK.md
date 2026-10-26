# 01 · Vision, problem and the rethink (v2)

> Status: written 2026-10-27, after the mentor review with Rupala (Central Square Foundation, 24 Oct 2026).
> This file explains **why** Kaaran exists, **what changed** after the review and **what we will not do**.
> The other docs explain how: data (02), related work (03), requirements (04), architecture (05),
> decision rubrics (06), plan (07), data downloads (08).

---

## 1. The problem in one paragraph

A Block Education Officer (BEO) in Maharashtra is responsible for 150-300 schools spread over 10-20 clusters
(kendras), each run by a Kendra Pramukh. Every month data arrives: attendance from the state system, teacher
posts, assessment rounds, UDISE+ once a year. When results fall, the officer has to answer three questions:
**where is the problem, why is it happening, and what should I do on Monday?** Today the data sits in
separate portals and Excel sheets. Nobody joins it, nobody checks whether it can be trusted, and the monthly
review meeting (बैठक) ends with generic instructions ("improve attendance", "conduct training"). Studies of
Indian school governance show that this pattern produces plans on paper and no change in learning (see 03).

**The gap is not data. The gap is the step from data to a specific, trusted, doable action.**

## 2. What Kaaran is (one line)

**Kaaran (कारण, "reason") is an AI data analyst for block and district education officers. It reads the
data they already have, checks it can be trusted, finds which schools and clusters need attention and why,
and recommends specific actions within the officer's powers, in Marathi, on WhatsApp and the web.**

## 3. What the mentor review told us (and what we accept)

| # | Mentor point (24 Oct) | Our reading | Decision |
|---|---|---|---|
| 1 | 60-70% of officers will never ask a bot a question. A tool that waits for questions does not scale. | Questions are a feature, not the trigger. | **Kaaran becomes proactive**: when new data arrives it scans every block and sends the officer an alert ("3 clusters need attention, tap to see why"). Questions still work. |
| 2 | Do not try to solve for every dataset. Build a **data availability matrix**: which data can the model handle accurately? | Our v1 covered scores, attendance, teacher posts, election duty, infrastructure and poverty, with equal weight. | **Scope = 4 core domains**: teacher availability (incl. PTR), student attendance, enrolment, learning assessment. Plus two support signals that drive actions: academic support visits and non-teaching duty. Infrastructure and poverty become context only. See 02. |
| 3 | Public data is aggregated (UDISE+ reports, NAS) and not very useful; school-level data needs logins. Synthetic data in real formats is a valid approach. | We found UDISE+ 2024-25 **school-level microdata** (pseudo IDs) is shared on registration. Assessment and attendance are not public. | **Hybrid data**: real UDISE+ microdata format (and real files for the pilot block when downloaded), real district benchmarks (PRS 2024, FLS 2022, NAS 2021), synthetic assessment / attendance / visits **in the formats state systems export**. Every synthetic file keeps the SYNTHETIC marker. |
| 4 | The six-part brief is too much. Use three parts: **what needs attention → why it may be happening → what to do.** Lead with at-risk flags. | Our labels (STRONG / WEAK / LEARN_FROM / RULED_OUT…) are correct but heavy for an officer. | **New brief: A / B / C.** Labels stay in code and in the appendix; the officer sees plain words ("strong evidence", "possible", "cannot tell"). Twin block and data trust move into part B. |
| 5 | **Actions are the weakest part of every product.** An LLM gives generic advice ("train teachers"). Actions need a **decision rubric** that checks constraints first (PTR, mentor visits, training, attendance). Two clusters with the same fall can need opposite actions. | Our v1 had a fixed 4-item action catalog. Correct in spirit (code, not LLM), too thin. | **Decision Rubric engine** (doc 06): situation + constraints → diagnosis → action, owner, deadline, follow-up metric. Written as data (JSON), reviewed with real teachers and officers. The LLM never chooses an action. |
| 6 | Insights should be things the naked eye misses: "two clusters fail for different reasons". | v1 compared talukas inside a district. The BEO's unit is the cluster and the school. | **Block lens**: diagnose **per cluster** inside a block (and per block for the DEO). Show the positive deviants ("this multigrade school does well despite a vacancy"). |
| 7 | The बैठक (monthly review) is where accountability happens. | v1 mentioned action forwarding as a stretch goal. | **Baithak pack**: cluster-wise agenda with assigned actions, and next month's re-check of whether the numbers moved. This closes the loop (challenge sub-problem 3). |
| 8 | OCR of handwritten registers is a teacher-level problem, not ours. | Agreed. | Out of scope. |
| 9 | Voice: Bhashini underperforms; check the Bodhan stack. Ask the technical mentor about cost at scale. | Bodhan AI (IIT Madras + AI4Bharat) released open ASR/TTS models in Sept 2026. AI4Bharat IndicConformer Marathi (120M, MIT) exists. | Voice through a pluggable speech layer (doc 05). Hosted API for the demo, self-hosted open model for the pilot. |

**What we keep from v1 (the mentor called these strong):** trust checks before conclusions ("data fidelity
check"), the twin comparison, evidence with sources for every number, the LLM never producing numbers.

## 4. Are we on the right track? (honest check)

| Question | Answer |
|---|---|
| Is the problem real and the user right? | Yes. The mentor confirmed it is "an implementation challenge" she sees in Haryana. Our team includes a government primary teacher (Khadki, Pune). |
| Is the core design right? | Yes for the evidence engine (code computes, LLM writes, verifier checks). **No** for the trigger (wait for questions), the unit (taluka vs cluster), the brief (6 parts) and the actions (thin catalog). v2 fixes these four. |
| Is the data plan right? | Partly. v1 synthetic data was realistic in shape but used our own column names. v2 uses the real UDISE+ microdata columns and state-style exports, and runs one real public dataset end to end. |
| What would make us lose? | A "dashboard + chatbot" impression; generic actions; no proof of user testing; nothing running on real data. The plan in 07 addresses each. |

## 5. Vision (where this goes)

1. **Hackathon (by 1 Nov 2026):** one district, block lens, proactive alert, three-part Marathi brief with
   rubric-based actions, baithak pack, WhatsApp + web, voice in/out, one real public dataset processed,
   user tests with teachers and officers.
2. **Pilot (Dec 2026 - Mar 2027):** one block in Solapur with authorised exports from the state systems,
   weekly alerts, monthly baithak packs, action tracking. Measure: time to answer, flags confirmed in the
   field, actions completed, learning change in the next assessment round.
3. **State scale:** connect to the state MIS / Vidya Samiksha Kendra as a data source, so alerts start from
   the system, not from uploads. Every block officer in the state gets a monthly brief. The decision rubric
   becomes a shared, versioned state asset that SCERT and district teams improve over time.

## 6. What Kaaran will not do

- Rank, blame or name individual teachers or students.
- Claim a cause is proven. Even the strongest finding says "probable".
- Let the LLM produce a number, a label or an action.
- Act on data that failed trust checks (it reports it instead).
- Replace the officer's judgement. Actions are recommendations; the officer confirms before anything is
  forwarded.
- Send school names or identifiable data to an external LLM.

## 7. How we will know it works

| Metric | Target in the pilot |
|---|---|
| Time from new data to a usable brief | < 5 minutes (today: days to never) |
| Numbers in briefs without a source | 0 (verified by code on every brief) |
| Trust flags confirmed on a field visit | ≥ 50% of flagged registers show a real problem |
| Recommended actions accepted by officers | ≥ 60% judged "doable and relevant" in review |
| Actions completed and re-checked next month | tracked for 100% of assigned actions |
| Officer use without prompting | weekly, for 3 months |
