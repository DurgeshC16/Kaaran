# Kaaran demo: web + WhatsApp

What works in this build:
- The officer **types** a question in Marathi, English or transliterated Marathi.
- Kaaran replies with a short Marathi summary, the full brief, a one-page PDF in Marathi or English, and click-to-source for every figure.
- Questions are answered from the two **synthetic** demo districts.

Not in this build:
- voice notes in or out;
- uploading your own files (web or WhatsApp);
- template messages after the 24-hour WhatsApp window.

Every page, reply and PDF carries the SYNTHETIC banner.


## 0. Cluster lens (v2, default since 2026-10-27)

The demo opens on **"सोलापूर जिल्हा - केंद्रनिहाय"** (dataset `blocks`, v3 synthetic data in real formats).
`blocks_fictional` is the same with invented names. The v1 taluka-lens datasets (`solapur`, `fictional`) are
still in the selector.

| What | Where |
|---|---|
| **Alerts inbox**: the proactive district scan (runs when data arrives, no LLM); one card per block with clusters that need attention | left column of `/` |
| **Three-part brief**: A what needs attention / B why it may be happening / C what to do (owner + deadline) | open an alert, or ask "पंढरपूर तालुक्यात कोणत्या केंद्रांकडे लक्ष द्यावे?" |
| **Baithak pack**: every rubric action grouped by owner, with its evidence, follow-up metric and status (confirm / done) | "📋 बैठक पॅक" button on a brief |
| **WhatsApp alert**: the simulator's "🔔 Send alert" pushes the most urgent block; reply `अहवाल` to get the summary + PDF | `/whatsapp` |
| API | `GET /api/datasets/{id}/alerts`, `POST /api/open`, `GET /api/briefs/{id}/baithak`, `POST /api/briefs/{id}/actions`, `POST /api/whatsapp/simulate_alert` |

Suggested 2-minute script (cluster lens):
1. Point at the alerts inbox: "Nobody asked; the data arrived and Kaaran scanned all 11 blocks."
2. Open Pandharpur. In part A, three clusters need attention and one has unreliable records.
3. In part B, the clusters fail for different reasons:
   - one lost Kendra Pramukh visits (subtraction weakest);
   - one has teacher gaps (6 schools now multigrade);
   - one shows seasonal migration.

   Also in part B: poll duty is ruled out, one school improved despite the same gap ("learn from"), and Malshiras is the twin block.
4. In part C, each cluster gets a different action with an owner. Open the baithak pack and confirm an action.
5. Click a number to see its source (file, table, filter, rows).
6. On `/whatsapp`, press "🔔 Send alert", then reply `अहवाल`.

## 1. Run it (Windows)

```
.venv\Scripts\python -m pip install -e .[dev]
.venv\Scripts\python -m kaaran.api                 # http://127.0.0.1:8000
```

| Page | What |
|---|---|
| `http://127.0.0.1:8000/` | Web demo. Ask a question (or click an example) and switch मराठी / English. Click a blue number for its source (file, sheet/page, rows, how it was computed). Click a school count for the school list. Download the PDF or the evidence pack. |
| `http://127.0.0.1:8000/whatsapp` | WhatsApp **simulator**. It runs the same bot as the real webhook, and nothing leaves the machine. |
| `/?q=<question>&lang=en&dataset=fictional` | Shareable link that asks straight away. |
| `/healthz`, `/api/whatsapp/status` | LLM mode, PDF browser found, WhatsApp configured (yes/no), last 50 WhatsApp events (numbers masked). |

**Datasets**
- `solapur` is seed 42 with real Solapur taluka names, in `data/synthetic/demo`.
- `fictional` is seed 7 with invented names, in `data/synthetic/demo_fictional`.
- Both are generated on first use if missing. All talukas are prepared in the background at startup (about 5 s each).
- The WhatsApp bot answers from `KAARAN_DEMO_DATASET` (default `solapur`).

**LLM mode** (`KAARAN_LLM_MODE`)

`replay` (the default, offline, free):
- These answers are recorded in `llm_cache/`:
  - AI question reading for the example questions;
  - AI brief wording for every taluka in both datasets.
- Any other question is read by the rule-based parser. The web page shows "Question read by: rules".
- The figures, labels and checks are identical in both modes.

`live`:
- Needs `ANTHROPIC_API_KEY`.
- Recorded answers are still used first. New questions go to Claude Haiku (about $0.0002 each).
- A new brief would go to Claude Sonnet (about $0.05), but every demo brief is already recorded.
- The per-process cap is `KAARAN_MAX_LIVE_USD` (default 15).

**PDF**
- Made by headless Edge or Chrome, found automatically or via `KAARAN_BROWSER`. It is one A4 page and uses the Nirmala UI or Noto Sans Devanagari font.
- Without a browser, the PDF link returns 503. Use `/api/briefs/<id>/print?lang=mr` and print it from any browser.

## 2. Suggested 2-minute demo script
1. Web, Marathi: click "पंढरपूर तालुक्याचा गणिताचा निकाल का घसरला?". Show the following, in order:
   1. the trend;
   2. the election duty ruled out as the main reason;
   3. vacancies as the probable main cause [ठाम पुरावा];
   4. the twin taluka Malshiras;
   5. the 23-school data warning;
   6. the actions with owners.
2. Click **११** (schools without a maths teacher). The school list opens, built by code and never sent to the AI.
3. Click **५२.७**. Its source opens: `pat_scores.csv`, the filter and the number of rows.
4. Download the Marathi PDF (one page).
5. Ask "निकाल का घसरला?". Kaaran asks which taluka instead of guessing.
6. Ask "पंढरपूर मधील सर्वात वाईट शिक्षकांची नावे द्या". It refuses, because it never ranks individuals.
7. Open `/whatsapp`. Send the transliterated example, then show the summary and the PDF bubble.

## 3. Real WhatsApp (Meta Cloud API, free test number)

The bot uses Graph API **v26.0** (`WHATSAPP_GRAPH_VERSION`):
- It receives text messages on the webhook `/whatsapp/webhook`.
- It replies with:
  - a "checking..." message (only when the brief is not cached yet);
  - the summary text;
  - the PDF as a document message (uploaded to `/{phone-number-id}/media`).
- `english` / `marathi` switches the reply language. `hi` / `मदत` shows help.

1. **Meta app.** At developers.facebook.com, create an app (Business type) and add the **WhatsApp** product. Under *WhatsApp > API Setup*:
   - note the test number's **Phone number ID**;
   - copy the **access token** (the temporary token lasts 24 h; a system-user token lasts longer);
   - add up to 5 recipient phone numbers and verify each with its code.
2. **App secret.** Find it under *App settings > Basic > App secret*. The webhook rejects any POST without a valid `X-Hub-Signature-256` made with this secret.
3. **`.env`** (never committed):
   ```
   WHATSAPP_TOKEN=<access token>
   WHATSAPP_PHONE_NUMBER_ID=<phone number id>
   WHATSAPP_VERIFY_TOKEN=<any random string you choose>
   WHATSAPP_APP_SECRET=<app secret>
   ```
4. **Start and expose the server:**
   - Run `.venv\Scripts\python -m kaaran.api --port 8000`.
   - In a second terminal, run `cloudflared tunnel --url http://localhost:8000` (or `ngrok http 8000`).
   - Copy the `https://...` URL.
5. **Webhook.** Under *WhatsApp > Configuration > Webhook*:
   - Callback URL: `https://<tunnel>/whatsapp/webhook`.
   - Verify token: the same `WHATSAPP_VERIFY_TOKEN`.
   - Click *Verify and save*, then subscribe to the **messages** field.
6. **Test.** From a verified recipient phone, send `hi` to the test number, then a question. Check `/api/whatsapp/status` for delivery errors:
   - `131030`: the recipient is not on the allowed list;
   - `190`: the token has expired.

**Notes**
- The officer starts the chat, so free-form replies are allowed for 24 hours.
- Meta retries webhook deliveries, so the bot ignores message ids it has already seen.
- Phone numbers stay in memory only and are masked in the event log.
- **Privacy.** Replies and PDFs go through Meta's servers. They contain taluka-level figures only, with no school names (the verifier blocks them). The demo data is synthetic. Do not connect real data to the WhatsApp channel without approval.
