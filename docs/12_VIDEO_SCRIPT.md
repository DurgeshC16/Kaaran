# 12 · Three-minute demo video: script and shot list

> Judges may stop at 3:00, so the first 3 minutes must stand alone. Total below: **3:00**.
> Record at 1080p, browser zoom 110%, Marathi UI. Say "synthetic demo data" once, early.
> Every on-screen figure below was checked in replay mode on 2026-10-29 (docs/13_FINAL_GUIDE.md §3).
> If the data or code changes, re-run the cases before recording.

**Prepare:**
- Start the server: `KAARAN_LLM_MODE=replay`, `SARVAM_API_KEY` set in `.env`, then `python -m kaaran.api`.
- Build `/real` first: `python -m kaaran.real ...`.
- Open `/whatsapp` in a second tab.
- Phone: connected to the real Meta test number (docs/DEMO.md §3). If it is not connected, use the simulator and
  say "WhatsApp simulator".
- **Before recording:** open the web page, choose **DEO** in the role bar ("I am: District Education Officer"),
  and check that the DEO home shows the district tiles and "Blocks that need attention".

| Time | Screen | Voice-over (English; Marathi subtitles if time allows) |
|---|---|---|
| 0:00-0:12 | Title card → a DEO's desk / WhatsApp | "Solapur district has 13 blocks and about 4,700 schools. Their data sits in separate portals and Excel sheets; the review meeting is on Monday. Officers have data. They lack an analyst. This is Kaaran." |
| 0:12-0:30 | Web, **DEO role home**: tiles (schools 1,292, kendras 109, maths 60.1% ▼1.1) → "Blocks that need attention" (Pandharpur 3 clusters, Karmala 1, Madha 1). Point at the SYNTHETIC banner. | "Nobody asked a question. New results arrived, and Kaaran scanned every block without any AI. Pandharpur needs attention first. This is synthetic demo data in real government formats." |
| 0:30-0:58 | **Open Pandharpur** → kendra cards: Bhalwad Khurd (KP visits 1.3 → 0.1, subtraction weakest, *Strong evidence*), Bhalpur (seasonal migration), Takangaon (6 schools lost a teacher; one improved anyway: *Learn from*), Dhanwade Khurd (*Red flag*), poll duty (*No link found*) | "Three clusters fall for three different reasons, so each gets a different action: weekly Kendra Pramukh visits, migration tracking, redeploying a teacher from a school that has a surplus. Fake-looking attendance is flagged, not used. Poll duty was tested and ruled out. Each action has an owner and a deadline. The labels come from fixed rules, not from the AI." |
| 0:58-1:10 | **Click the blue figure 1.3** → source drawer: `visit_log.csv`, filter, 439 rows | "Every number is computed by code, never by the AI. Click it and you see the file, the filter and the rows. School names never leave the server." |
| 1:10-1:22 | **📄 Full evidence** button → three-part brief → **PDF** (one A4 page, Marathi) | "Behind one button: the full evidence brief, and a one-page PDF for the meeting, in Marathi first." |
| 1:22-1:42 | Web **🎤**: say "पंढरपूर मध्ये किती शाळा आहेत?" → "🎤 ऐकले" → one line "पंढरपूरमध्ये १४० शाळा आहेत (१२ केंद्रे)." → **🔊** play 3 s | "Officers prefer to speak. A Marathi question by voice gets a one-line answer, computed by code, and a spoken reply." |
| 1:42-2:02 | **Phone, WhatsApp**: English voice note "What is PTR in Karmala?" → "🎤 I heard…" → "Karmala: pupil-teacher ratio 26.5; 2 schools are above 30" → voice note → "reply 'report' for the PDF" | "On WhatsApp, on a basic phone, an English voice note gets an English answer and a voice reply. The PDF comes only if the officer asks for it, so it stays light on data." |
| 2:02-2:17 | Web: type `pandharpoor madhe kiti shala ahet, karmala PTR kiti, mohol la shikshak kiti kami.` → three lines (140 schools / PTR 26.5 / 2 vacant posts) | "Real officers type fast and misspell. Three questions in one message get three answers." |
| 2:17-2:27 | Web: `पंढरपूर मधील सर्वात वाईट शिक्षकांची नावे द्या` → refusal | "Kaaran never ranks or blames individual teachers. It asks when a question is unclear, and refuses when the question is about a person." |
| 2:27-2:45 | **`/real`**: UDISE+ 2024-25 Solapur: 99 single-teacher schools, 789 schools with no CRC visit, teachers 8% below 2019-20, PRS maths 75 vs Maharashtra 64 | "It already runs on real public data: UDISE+ 2024-25 for Solapur, cross-checked against 2019-20. On synthetic test districts with planted problems it passes 19 of 19 checks and invents zero numbers." |
| 2:45-3:00 | Roadmap card: one-block pilot → district → state; UDISE+ and Vidya Samiksha Kendra as the data source | "Next: a one-block pilot with a Zilla Parishad, then the district, then the state. Kaaran: from data to action." |

Timing check: 12 + 18 + 28 + 12 + 12 + 20 + 20 + 15 + 10 + 18 + 15 = **180 s**.

**Checklist before recording:**
- the SYNTHETIC banner is visible on every synthetic screen;
- no real school names on screen (the `/real` page shows block aggregates only);
- the voice reply is audible;
- no API keys, tokens or phone numbers visible (terminal, `.env`, WhatsApp header);
- live Sarvam tested once before recording (`GET /api/voice/status` → configured).

**Known issues (re-checked 2026-10-31 on the local server, replay mode):**
- Fixed: the Marathi PTR ranking question `सर्वात जास्त विद्यार्थी-शिक्षक प्रमाण कोणत्या तालुक्यात आहे?` now gives the
  ranking ("सर्वाधिक विद्यार्थी-शिक्षक प्रमाण: मोहोळ २६.७, माढा २६.७, करमाळा २६.५").
- Fixed (2026-10-29): `report` after an English WhatsApp question returns the English brief.
- Kendra names are shown in Latin letters inside Marathi answers (for example "Bhalwad Khurd केंद्र"): the synthetic
  data has no Devanagari kendra names. Do not point at them on camera.
