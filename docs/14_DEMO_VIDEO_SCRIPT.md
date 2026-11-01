# 14 · Demo video script: hands-on product walkthrough (2:38)

> This is the script to record. It replaces docs/12_VIDEO_SCRIPT.md, which is kept for history.
> **Format:** a screen demo with no story and no recap of the problem. Part 1 is the website (about 1:49), Part 2 is the
> phone WhatsApp recording (about 0:42), and a 7-second close. **Runtime is 2:38: 275 spoken words (2:02 at 135 words
> per minute) plus 18 clicks or cuts at about 2 seconds each (0:36).** That leaves 22 seconds of buffer before 3:00.
> **Verified 2026-11-01** on the live site https://kaaran-vk5o.onrender.com: every label, figure and reply quoted below was
> taken from the live pages or from `POST /api/ask` and `POST /api/whatsapp/simulate`. The WhatsApp sequence in Part 2 was
> run end to end in the simulator, with the voice note typed instead of spoken.
> Every Pandharpur, Madha and Malshiras figure is **SYNTHETIC** demo data. Only the Real data page shows real data.

---

## Recording set-up

**Links.** Hash links only work when a page loads, so open each one in a new tab or press F5 after pasting it.

| Purpose | URL |
|---|---|
| Wake the server (2 min before recording) | https://kaaran-vk5o.onrender.com/healthz (wait for `{"ok":true,...}`) |
| **Start of take** (English UI, DEO selected, so you can click BEO on camera) | https://kaaran-vk5o.onrender.com/#role=deo&lang=en |
| Jump: BEO home, Pandharpur | https://kaaran-vk5o.onrender.com/#role=beo&block=BPandharpur&lang=en |
| Jump: DEO home | https://kaaran-vk5o.onrender.com/#role=deo&lang=en |
| Jump: Pandharpur alert opened (cards + toolbar) | https://kaaran-vk5o.onrender.com/#role=deo&lang=en&open=BPandharpur |
| Jump: Madha question | https://kaaran-vk5o.onrender.com/#lang=en&q=Which%20of%20madha%20attendance%20records%20look%20unreliable%3F |
| Real data page | https://kaaran-vk5o.onrender.com/real |
| Backup: WhatsApp simulator | https://kaaran-vk5o.onrender.com/whatsapp |

**Checklist**
- [ ] Open `/healthz` 2 minutes before you start. After an idle period the first load can take up to a minute.
- [ ] Do one dry run of the whole web part. This warms the answer cache, so the questions come back fast on the real take.
- [ ] Clear the browser history so the address bar shows no suggestions. Close other tabs. Hide the bookmarks bar.
- [ ] Set browser zoom to 110%. Record at 1920x1080 (or 1280x720). Turn cursor highlighting on in the recorder.
- [ ] Check that the yellow SYNTHETIC banner is visible at the top.
- [ ] Phone: use the number registered on the Kaaran WhatsApp test number. Keep each voice note under 30 seconds. Speak Marathi slowly and clearly in a quiet room. Turn on Do Not Disturb.
- [ ] Phone: start from an empty chat or a clean scroll position. Mute the notification sound and keep the reply audio audible.

---

## The script

Each step lists: **Time · Screen · Do · Say · Highlight · Then.** The Say lines are the only spoken narration.
Scroll while you speak; the times already include about 2 seconds for each click.

### PART 1 · WEBSITE (0:00-1:49)

**Step 1 · 0:00-0:09 · Pick the role**
- **Screen:** home page, English UI, start-of-take link.
- **Do:** in the `I am:` bar, click `Block Education Officer (BEO)`. In the dropdown that appears, choose `Pandharpur`.
- **Say:** "This is Kaaran. No login. I pick my role: BEO, Pandharpur."
- **Highlight:** the `I am:` bar and the block dropdown.
- **Then:** the page shows "Pandharpur block: my kendras". Scroll down a little.

**Step 2 · 0:09-0:18 · The block at a glance, and the alerts**
- **Screen:** BEO home. Tiles: Schools 140 · Kendras 12 · Teachers working 558 · Vacant posts 7 · Pupil-teacher ratio 26.5 · Attendance (3 months) 88.0% · Maths result 59.4% "▼ 2.0 vs last year". Below them is the section "Kendras that need attention".
- **Do:** move the cursor across the tiles, then scroll to "Kendras that need attention". Let the badges show: three `Needs attention now`, one `Red flag`, one `Not enough data`.
- **Say:** "My block: 140 schools, maths down two points. Below are alerts. Code checks every kendra and raises them on its own."
- **Highlight:** the "▼ 2.0 vs last year" line, then the coloured badges on the cards.
- **Then:** stop on the first card, Bhalwad Khurd Kendra.

**Step 3 · 0:18-0:31 · Read one alert: what, why, what to do**
- **Screen:** the Bhalwad Khurd Kendra card.
- **Do:** point at each of the three parts in turn.
  - What happened: "…maths results fell 11.6 points more than other schools in the block (2024-25 to 2025-26)."
  - Why: `Strong evidence` "…Kendra Pramukh visits fell from 1.3 to 0.1 per school per month."
  - What to do: "…visit classrooms in all 12 schools of Bhalwad Khurd Kendra every week." with "— Kendra Pramukh (cluster head), this week".
- **Say:** "Each alert says what happened: maths fell 11.6 points more. Why: cluster head visits almost stopped. Strong evidence, by fixed rules. Then what to do, who, by when."
- **Highlight:** the green `Strong evidence` label, then the owner and timing line.
- **Then:** scroll back to the top, to the `I am:` bar.

**Step 4 · 0:31-0:40 · The district view**
- **Screen:** role bar, then the DEO home.
- **Do:** click `District Education Officer (DEO)`. Scroll past the tiles. The section "Blocks that need attention (results 2025-26)" shows "Pandharpur: 3 kendras need attention now; check records in 1", then Karmala, Madha, Mangalvedha and Akkalkot. Click `Open` on the Pandharpur card.
- **Say:** "The district officer sees alerts for all eleven blocks. I open Pandharpur."
- **Highlight:** the Pandharpur alert line and the `Open` button.
- **Then:** the alert page opens with "Question: 🔔 Pandharpur" and the same kendra cards.

**Step 5 · 0:40-0:51 · Click a number to see its source**
- **Screen:** the opened Pandharpur alert, Bhalwad Khurd card.
- **Do:** click the blue **11.6**. A drawer opens on the right showing "Source · 11.6 · Computed as: mean_rel_change", "File: fln_assessment_2024-25.xlsx · Table: assessment · Filter … · Rows matched: 120", the same for 2025-26, and the amber line "Synthetic data: the source files were generated for the demo." Press Esc.
- **Say:** "Every blue number opens its source: file, filter, 120 rows. Code makes the numbers, not AI."
- **Highlight:** the File line and "Rows matched: 120".
- **Then:** scroll to the toolbar below the cards.

**Step 6 · 0:51-1:00 · Review meeting pack**
- **Screen:** toolbar with `📄 Show the full evidence brief (source of every figure)`, `⬇ PDF Marathi`, `⬇ PDF English`, `📋 Review meeting pack`, `🔊 Listen`.
- **Do:** click `📋 Review meeting pack`. The drawer "Review meeting pack: Pandharpur" shows actions grouped under Kendra Pramukh (cluster head), Block Education Officer (BEO) and District Education Officer (DEO). Most actions have a "💰 Funded under: Samagra Shiksha PAB 2026-27, Maharashtra (C476, p.57) …" line. Scroll once through it, then press Esc.
- **Say:** "The meeting pack lists actions by owner, with the scheme that pays."
- **Highlight:** the owner headings and one 💰 line.
- **Then:** scroll up to "Ask your question".

**Step 7 · 1:00-1:22 · Ask two questions: Marathi, then English**
- **Screen:** the ask panel and its `Try asking:` chips. Each answer appears just below the panel, so make a small scroll after each one.
- **Do (a), Marathi:** click the chip `Malshiras cha nikal changla ka aala?`. The whole page switches to Marathi: "माळशिरसमध्ये गणिताचा निकाल या वर्षी २.७ गुणांनी वाढून ६५.२% झाला." / "सर्वात जास्त वाढ: Longaon Khurd (+५.०), Malner Budruk (+४.३)." Then: "शिक्षक संख्या, हजेरी आणि केंद्रप्रमुखांच्या भेटी जवळपास तशाच राहिल्या, त्यामुळे डेटा वाढीचे स्पष्ट कारण दाखवत नाही."
- **Say (a):** "Now Marathi: why did Malshiras improve? It answers in Marathi, and honestly says the data shows no clear reason."
- **Do (b), English, trust check:** scroll up and click the chip `Which of madha attendance records look unreliable?`. The page switches back to English: "Madha: schools with unreliable attendance records: 1; schools with incomplete data: 0." and "Dhokkheda Budruk Kendra (1). They reported 100% attendance for 3 or more months in a row; this attendance is not used in the analysis until checked. The Kendra Pramukh should check the registers in person this week."
- **Say (b):** "In English: which Madha attendance records look unreliable? One kendra reported 100% for months, so that data is held back."
- **Highlight:** (a) the Marathi headline and the "स्पष्ट कारण दाखवत नाही" sentence; (b) "not used in the analysis until checked".
- **Then:** scroll to the top and point at the yellow banner.

**Step 8 · 1:22-1:49 · Synthetic data, then real data**
- **Screen:** the yellow banner "⚠️ SYNTHETIC demo data - the figures here are not real and the findings are not real." Then the header link `Real data`, which opens `/real`.
- **Do (1:22-1:34):** point at the banner while you speak.
- **Say (on the banner):** "Why synthetic? School results and attendance are not public. So we built a district in real government formats, with known problems, and marked it SYNTHETIC everywhere."
- **Do (1:34-1:49):** click `Real data`. On `/real`, show the line "SOLAPUR · UDISE+ 2024-25" and the totals "2900 schools · 9534 teachers · PTR 20.1 · 99 single-teacher schools · 789 schools reported no CRC visit last year". Scroll past the block table to "PARAKH Rashtriya Sarvekshan 2024 · grade 3" (Solapur 75 maths / 79 language). Stop on "Teacher rationalisation potential": "213 posts needed in 196 schools · 89 could be covered by moving teachers inside the same block (rubric A1)…".
- **Say (on /real):** "The Real data tab is real public data: UDISE+ 2024-25, Solapur. 2,900 schools, 789 with no cluster visit, PARAKH scores, and 89 teacher gaps we can fill by moving teachers."
- **Highlight:** "SOLAPUR · UDISE+ 2024-25", "789 schools reported no CRC visit", the PARAKH Solapur row, and "89 could be covered by moving teachers".
- **Then:** cut to the phone recording.

### PART 2 · WHATSAPP (1:49-2:31)

Record these four messages in this order (the order matters, see note 4). Replies take a few seconds, so cut the waiting in the edit. Long replies may start with "⏳ Got your question. Checking the evidence…"; you can cut that too.

**Step 9 · 1:49-1:53 · Transition**
- **Screen:** phone, WhatsApp chat with Kaaran.
- **Say:** "Now the same analyst on WhatsApp."

**Step 10 · 1:53-2:03 · English text, with PDF and voice summary**
- **Type:** `Which block needs most attention?`
- **Reply:** "*Cluster Evidence Brief: Pandharpur*", then "⚠️ SYNTHETIC demo data - not real figures and not a real finding.", then "*Direct answer*" and "Most attention needed: Pandharpur (3 clusters), Karmala (1 cluster), Madha (1 cluster). The first block's clusters are below." and the kendra cards. After the text come the document `Kaaran_Pandharpur_en.pdf` ("one-page brief. SYNTHETIC demo data.") and the audio `Kaaran_Pandharpur_en.mp3` ("🔊 … one-minute voice summary").
- **Say:** "I type in English. I get the kendra cards, a one-page PDF, and a one-minute voice summary."
- **Highlight:** the "Most attention needed" line, the PDF bubble, the audio bubble.

**Step 11 · 2:03-2:14 · Marathi voice note**
- **Speak (hold the mic, under 30 s):** "पंढरपूर मध्ये किती शाळा आहेत?" (Pandharpur madhye kiti shala aahet?)
- **Reply:** `🎤 ऐकले: "<what it heard>"`, then "*थेट उत्तर: पंढरपूर*", the Marathi SYNTHETIC line, "पंढरपूरमध्ये १४० शाळा आहेत (१२ केंद्रे).", then "📄 पूर्ण पुरावा अहवाल (PDF, प्रत्येक आकड्याचा स्रोत) हवा असल्यास 'अहवाल' लिहा.", then the audio `Kaaran_Pandharpur_mr.mp3`.
- **Say:** "Now a voice note in Marathi. It shows what it heard, answers in Marathi, 140 schools, and sends audio back."
- **Highlight:** the "🎤 ऐकले" line, then the Marathi answer, then the audio bubble.

**Step 12 · 2:14-2:24 · Marathi text: the full report**
- **Type:** `अहवाल`
- **Reply:** "*केंद्रनिहाय पुरावा अहवाल: पंढरपूर*" with the Marathi kendra cards ("[तातडीने लक्ष द्या] Bhalwad Khurd केंद्रातील १२ शाळांमध्ये…"), then `Kaaran_Pandharpur_mr.pdf` and `Kaaran_Pandharpur_mr.mp3`.
- **Say:** "I type 'report' in Marathi, and get the full Marathi brief as a PDF."
- **Highlight:** tap the PDF bubble for one second so the Marathi one-pager shows.

**Step 13 · 2:24-2:31 · English follow-up**
- **Type:** `and PTR?`
- **Reply:** "*Direct answer: Pandharpur*", the SYNTHETIC line, "Pandharpur: pupil-teacher ratio 26.5; 7 schools are above 30.", then "📄 For the full evidence brief (PDF, source of every figure), reply 'report'." and an English audio file.
- **Say:** "A follow-up in English. It remembers Pandharpur: 26.5 pupils per teacher."
- **Highlight:** "26.5; 7 schools are above 30".
- **Then:** cut to the close card.

### CLOSE (2:31-2:38)
- **Screen:** the BEO home (Pandharpur) or a title card, "Kaaran (कारण) · https://kaaran-vk5o.onrender.com".
- **Say:** "Kaaran: numbers from code, answers in your language. Try the link below."

---

## Notes for the recorder (what the demo does and does not do)
1. **No login.** The officer picks DEO or BEO (and a block) in the `I am:` bar, and the device remembers the choice. The narration says this plainly.
2. **Alerts come from code, not from public datasets.** Code computes the alerts from the demo district's data, which is synthetic but in the real government formats. The Real data page is a separate snapshot of real public files and does not drive the alerts. Do not say "alerts from public data".
3. **No automatic alerts reach the phone.** Real proactive WhatsApp alerts to a phone are not implemented. The only push alert is the `🔔 इशारा पाठवा / Send alert` button in the web simulator (`/whatsapp`). It posts "🔔 नवीन मूल्यमापन निकाल आले (२०२५-२६). पंढरपूर तालुक्यात ३ केंद्रांना तातडीने लक्ष देण्याची गरज आहे; …", and replying `अहवाल` returns the Marathi brief, PDF and MP3. If you want to show it, use a 6-second simulator clip in place of Step 10 and say "In the simulator, I push the alert Kaaran raises when new data arrives." Never claim the phone receives alerts on its own.
4. **WhatsApp order matters.** `अहवाल` returns the brief in the language of the previous answer, so it must follow the Marathi voice note. `and PTR?` works because the bot remembers the last block. If you already have a phone recording with different messages, keep it as long as it shows English text, Marathi text and a voice note, then take the narration from the table below.
5. **The reply audio is an MP3 audio message**, not a green voice-note bubble. Say "audio" or "voice summary", not "voice note", for the reply.
6. **Don't read numbers from two different views together.** The Malshiras "Learn from" line in the full brief says "+2.5 / −2.1", while the tiles show +2.7 / −2.0. This script never shows them side by side. Also don't compare real Pandharpur (352 ZP schools on /real) with the synthetic Pandharpur (140).
7. **The `/real` banner contains the word "(pseudocode)".** Don't zoom on the banner. Zoom on the "SOLAPUR · UDISE+ 2024-25" line instead.
8. **The Marathi question switches the whole web page to Marathi.** The next English question (Madha) switches it back, so Step 8 starts on the English banner and the English `Real data` link.
9. **Optional extras, only if a take runs short** (each adds about 6 seconds):
   - Step 6: click `Confirm` on an action that shows `open`; it changes to `confirmed`. A confirmed status stays saved on the server, so pick a still-`open` action in the dry run. Say "I confirm one."
   - Step 7: type `Give me the names of the worst teachers in Pandharpur` and click `Ask`. The reply is "I don't answer questions about individual teachers or students. Please ask about a block (taluka) or kendra." Say "Names of the worst teachers? It refuses."
10. **Backup if the phone recording fails:** record Part 2 in the simulator at `/whatsapp` with the same messages. It runs the same bot. Use the 🎤 button for the voice note, or type it and drop "It shows what it heard" from the narration. Say "the WhatsApp simulator" on camera.

**Other verified WhatsApp messages (for an existing recording)**

| Message | First reply line | One-line narration |
|---|---|---|
| `Malshiras cha nikal changla ka aala?` | "माळशिरसमध्ये गणिताचा निकाल या वर्षी २.७ गुणांनी वाढून ६५.२% झाला." | "Marathi in English letters. It answers in Marathi and says there is no clear reason." |
| `पंढरपूर तालुक्यात कोणत्या केंद्रांकडे लक्ष द्यावे?` | "*केंद्रनिहाय पुरावा अहवाल: पंढरपूर*" with the Marathi kendra cards, PDF and MP3 | "A Marathi question gets the Marathi kendra brief." |
| `Which of Madha's attendance records look unreliable?` | "Madha: schools with unreliable attendance records: 1; schools with incomplete data: 0." | "It flags records it does not trust." |
| `Why did maths fall in Bhalwad Khurd kendra?` | "Bhalwad Khurd Kendra needs attention now; the reasons and actions are below." | "It drills down to one kendra." |
| `hi` / `नमस्कार` | "Hello! I am *Kaaran*, an education data analyst (demo: synthetic data)…" | "It greets you in your language." |

---

## Timing and word count

Time per step = spoken words at 135 words per minute + about 2 seconds per click or cut.

| # | Time | Part | Words | Clicks / cuts |
|---|---|---|---|---|
| 1 | 0:00-0:09 | Pick the role | 11 | 2 |
| 2 | 0:09-0:18 | Tiles and alerts | 21 | 0 |
| 3 | 0:18-0:31 | What / why / what to do | 28 | 0 |
| 4 | 0:31-0:40 | DEO alerts, Open | 12 | 2 |
| 5 | 0:40-0:51 | Click a number, see its source | 16 | 2 |
| 6 | 0:51-1:00 | Review meeting pack | 12 | 2 |
| 7 | 1:00-1:22 | Questions (Marathi, English) | 39 | 2 |
| 8 | 1:22-1:49 | Synthetic, then Real data | 56 | 1 |
| 9 | 1:49-1:53 | Transition to phone | 6 | 1 |
| 10 | 1:53-2:03 | WhatsApp English text | 17 | 1 |
| 11 | 2:03-2:14 | WhatsApp Marathi voice note | 20 | 1 |
| 12 | 2:14-2:24 | WhatsApp `अहवाल` | 14 | 2 |
| 13 | 2:24-2:31 | WhatsApp `and PTR?` | 11 | 1 |
| - | 2:31-2:38 | Close | 12 | 1 |
| | **2:38** | **Total** | **275** | **18** |

275 words take about 2:02 of speech. The 18 clicks and cuts add about 0:36. Total 2:38, with 22 seconds to spare before 3:00. If a take runs long, first shorten the scroll on `/real` (stop at the totals and PARAKH), then drop Step 13.
