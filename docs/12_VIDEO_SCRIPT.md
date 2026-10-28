# 12 · Three-minute demo video: script and shot list

> Judges may stop at 3:00. Record at 1080p, browser zoom 110%, Marathi UI. Say "synthetic demo data" once early.
> Prepare: server running (`python -m kaaran.api`), `/whatsapp` open in a second tab, `/real` built.

| Time | Screen | Voice-over (English; add Marathi subtitles if time allows) |
|---|---|---|
| 0:00-0:15 | Title slide → a BEO's WhatsApp | "A block officer in Maharashtra looks after 300 schools. When results fall, she has data in five portals and a review meeting on Monday. Kaaran is her data analyst." |
| 0:15-0:35 | `/whatsapp`: press **🔔 Send alert** | "Nobody asked. New assessment results arrived, Kaaran scanned all 11 blocks, and sent this alert: three clusters in Pandharpur need attention, one has records to check. (Synthetic demo data in real government formats.)" |
| 0:35-0:55 | Send a **Marathi voice note** ("पंढरपूर मध्ये कोणत्या केंद्रांकडे लक्ष द्यावे?") → transcript → summary, PDF, voice reply | "She replies with her voice. Kaaran understands Marathi, answers in Marathi, with a one-page PDF and a one-minute voice summary." Play 5 s of the voice reply. |
| 0:55-1:30 | Web brief: A / B / C | "Three parts: what needs attention, why, what to do. The three clusters fall for three different reasons: fewer Kendra Pramukh visits, teachers lost to transfers, seasonal migration. Election duty is checked and ruled out. One school improved despite losing a teacher: learn from it." |
| 1:30-1:50 | Click a number → source drawer; click a school count → list | "Every number is computed by code, never by the AI, and shows its file, filter and rows. School names stay on the server." |
| 1:50-2:10 | **📋 बैठक पॅक**: actions by owner, funding line, confirm | "Actions come from a decision rubric that checks constraints first: redeploy only because two schools have surplus teachers. Each action has an owner, a deadline, a follow-up check, and the Samagra Shiksha budget line that already pays for it." |
| 2:10-2:30 | `/real` page | "And on real public data: UDISE+ 2024-25 for Solapur: 99 single-teacher schools, 789 schools with no cluster visit last year." |
| 2:30-2:50 | Guardrails slide + scorecard output | "Guardrails: the AI cannot write numbers, a verifier checks every sentence, unreliable data is flagged before analysis. On planted test districts Kaaran finds every problem and invents zero numbers." |
| 2:50-3:00 | Roadmap slide | "Next: a one-block pilot with a Zilla Parishad. Kaaran: from data to action." |

Checklist before recording: SYNTHETIC banner visible; no real school names on screen; voice reply audible; no API keys visible in terminals.
