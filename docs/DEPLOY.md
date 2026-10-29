# Deploying Kaaran (Render free plan + Meta WhatsApp Cloud API)

This guide puts the demo on a public link on **Render's free plan** (`https://kaaran.onrender.com`, or the URL
Render gives your service), connects the real WhatsApp test number, and freezes the submitted version. For running
locally and the demo script, see [DEMO.md](DEMO.md).

> Hugging Face Spaces (sections 1-2) now need a paid PRO subscription for Docker Spaces (HTTP 402 since Oct 2026),
> so the submitted demo runs on Render. The Hugging Face path is kept for teams that have PRO.

## Render free plan (the deployed demo)

The free plan gives 512 MB RAM and 0.1 CPU, and the service sleeps after 15 minutes without visits. Kaaran is
prepared for this (tested locally with `docker run --memory=512m --cpus=0.1`):
- the image **pre-builds** the main dataset at build time (`python -m kaaran.warm`): packs, briefs, all 22 one-page
  PDFs and a prepared-state cache (`prepared.pkl`, keyed on the raw files and the code);
- `KAARAN_DATASETS=blocks` loads only the main demo dataset (about 210 MB in use);
- measured under those limits: up in about 13 s, first answer about 16 s, then answers, home pages and PDFs in under
  a second.

Steps (about 10 minutes):
1. Sign up at https://render.com with GitHub (free, no card). When asked, allow Render's GitHub app to access the
   `DurgeshC16/Kaaran` repository (it is private).
2. Dashboard → **New → Blueprint** → pick `DurgeshC16/Kaaran`. Render reads `render.yaml` (web service `kaaran`,
   Docker, free plan, Singapore, health check `/healthz`, auto-deploy off so the evaluated version stays frozen).
3. Render asks for the secret values (they are stored by Render, never in git). Copy them from your local `.env`:
   `ANTHROPIC_API_KEY`, `SARVAM_API_KEY`, `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET`,
   `WHATSAPP_VERIFY_TOKEN`. Leave one empty if you do not have it yet (WhatsApp sending then stays off); add it later
   under the service's **Environment** tab and click **Save, rebuild and deploy**.
4. Click **Apply**. The first build takes about 10 minutes (Chromium, fonts, data, PDFs). The URL appears at the top
   of the service page.
5. **Keep it awake (recommended):** create a free monitor at https://uptimerobot.com (HTTP, every 5 minutes) on
   `https://<your-service>.onrender.com/healthz`. One always-on free service fits in Render's 750 free hours a month,
   and judges then never wait for a cold start.
6. Run the checks: `.venv\Scripts\python scripts\check_webhook.py https://<your-service>.onrender.com` (section 4)
   and the smoke tests (section 5).
7. **Real-data page (`/real`):** the aggregate Solapur snapshot (block totals from public UDISE+, no school
   identifiers) is never in git. Upload it as a Render **Secret File**: service → **Environment → Secret Files → Add**,
   file name `real_snapshot.json`, contents = your local `data/real/reports/real_snapshot.json`. Render mounts it at
   `/etc/secrets/real_snapshot.json`, where the app looks for it. Save and redeploy, then open `/real`.


What the image already does (`Dockerfile`):
- Python 3.11-slim, with Chromium and Noto fonts so the Marathi PDF is shaped correctly.
- Runs as a non-root user with uid 1000 (as Hugging Face Spaces expect); `/app` belongs to that user, so the app
  can write generated data, PDFs, caches and `actions.json`.
- `KAARAN_HOST=0.0.0.0`, `PORT=8000`, `KAARAN_BROWSER=/usr/bin/chromium`, `KAARAN_BROWSER_NO_SANDBOX=1`.
- `KAARAN_LLM_MODE=replay` by default.
- It copies `src/`, `llm_cache/` (recorded Claude responses), `pyproject.toml`, `README.md` and `.env.example`.
- `.dockerignore` keeps `.env`, `data/` (including `data/real/`), `docs/source/`, `.git/` and `.venv/` out of the
  image.
- The four SYNTHETIC demo datasets are generated **at build time** (deterministic, no LLM). On start, the server
  prepares ingest, trust checks and packs in the background, default dataset first.
- A `HEALTHCHECK` calls `/healthz` every 60 s.

---

## 0. Before you start

- [ ] Full test suite green: `.venv\Scripts\python -m pytest -q`.
- [ ] Everything you want deployed is **committed**. The deploy script ships only committed files from `HEAD`.
- [ ] `git status` shows no `.env`, `data/real/` or `docs/source/` files.
- [ ] Docker runs locally: `docker build -t kaaran .`, then `docker run -p 8000:8000 kaaran`, then open
      http://127.0.0.1:8000.

## 1. Deploy with the script (recommended)

`scripts/deploy_hf.py` creates the Space (Docker SDK, public) if it does not exist, sets the secrets and variables
through the Hub API, and pushes the app. It uses only `httpx` (already installed) and never force-pushes.

1. Create a Hugging Face access token with **write** permission (*Settings → Access Tokens*).
2. Add to your local `.env` (never committed): `HF_TOKEN=<the token>` and `HF_USER=<your Hugging Face user>`, plus
   any app keys you want on the Space (`ANTHROPIC_API_KEY`, `SARVAM_API_KEY`, `WHATSAPP_*`).
3. Commit your work, then run:
   ```bat
   .venv\Scripts\python scripts\deploy_hf.py                 :: create/update the Space, set secrets, push HEAD
   .venv\Scripts\python scripts\deploy_hf.py --secrets-only  :: only update secrets and variables
   ```

What it does:
- **Ships only committed files from `HEAD`**: `src`, `llm_cache`, `pyproject.toml`, `README.md`, `Dockerfile`,
  `.env.example`, `.dockerignore`. It refuses to deploy if `.env`, `data` or `docs` appear in the archive.
  Uncommitted changes are not deployed (it prints a note).
- Adds the Space front matter (`sdk: docker`, `app_port: 8000`) to the deployed copy of `README.md` only; the
  GitHub README stays clean.
- **Secrets** (copied from `.env` if present, skipped otherwise): `ANTHROPIC_API_KEY`, `SARVAM_API_KEY`,
  `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN`.
- **Variables:** `KAARAN_LLM_MODE=live`, `KAARAN_MAX_LIVE_USD=10`, `KAARAN_MAX_VOICE_INR=500`,
  `KAARAN_DEMO_DATASET=blocks`, and `KAARAN_MODEL_MAIN` / `KAARAN_MODEL_LIGHT` copied from `.env` if set.
  To change a cap, edit `VARIABLES` in the script or change it in the Space settings afterwards.
- Prints the app URL: `https://<hf_user>-kaaran.hf.space`.

The build log is in the Space's **Logs** tab. The first build installs Chromium and generates the synthetic data,
so it takes a few minutes. When the log shows `Kaaran demo: http://0.0.0.0:8000/` and Uvicorn is running, the
Space is up.

## 2. Manual alternative (no script)

Only if the script cannot be used. Create the Space by hand (**New Space** → SDK **Docker**, blank template, free
CPU, **Public**: judges need it without a login, and Meta's webhook cannot reach a private Space). Then put only
the app files in the Space repository (the same list the script ships: `src/`, `llm_cache/`, `pyproject.toml`,
`README.md`, `Dockerfile`, `.env.example`, `.dockerignore`), and prepend this front matter to the Space's copy of
`README.md`:

```yaml
---
title: Kaaran
emoji: 📊
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8000
pinned: false
short_description: AI data analyst for education officers (synthetic demo)
---
```

- `sdk: docker` makes Hugging Face build our `Dockerfile`.
- `app_port: 8000` must match `PORT` in the Dockerfile. The default for Docker Spaces is 7860.
- Do not push the whole GitHub repository to the Space: it contains `docs/` and binary files the Space does not
  need. Then set the secrets and variables by hand (step 3).

## 3. Secrets and variables

`scripts/deploy_hf.py` sets these for you (step 1). To check or change them by hand: in the Space, **Settings →
Variables and secrets**. Both kinds reach the container as environment variables. Put keys in **Secrets**
(hidden). Plain settings can go in **Variables**. Restart the Space after changing them.

| Name | Type | Value | Why |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Secret | your Claude key | intent parsing, column mapping and brief wording for new questions |
| `KAARAN_LLM_MODE` | Variable | `live` | recorded answers first, then Claude for new wordings (default in the image: `replay`) |
| `KAARAN_MAX_LIVE_USD` | Variable | the script sets `10`; keep it within the demo budget (PROGRESS.md: demo/judging ≤ $40). The code default is `15`. | hard per-process cap on Claude spend; a restart resets the counter |
| `SARVAM_API_KEY` | Secret | your Sarvam key | speech-to-text (`saaras:v4`) and voice summary (`bulbul:v4-flash`) |
| `KAARAN_MAX_VOICE_INR` | Variable | a cap in rupees; the script sets `500` (code default `100`) | hard per-process cap on Sarvam spend |
| `WHATSAPP_TOKEN` | Secret | system-user token (step 4.4) | send replies, PDFs and MP3s |
| `WHATSAPP_PHONE_NUMBER_ID` | Secret | from *WhatsApp → API Setup* | the number Kaaran sends from |
| `WHATSAPP_APP_SECRET` | Secret | *App settings → Basic → App secret* | checks `X-Hub-Signature-256`; without it every webhook POST is rejected |
| `WHATSAPP_VERIFY_TOKEN` | Secret | any long random string you choose | Meta echoes it when you verify the webhook |
| `KAARAN_DEMO_DATASET` | Variable | `blocks` | the cluster-lens synthetic district (seed 42) opens by default |

Optional settings:
- `WHATSAPP_GRAPH_VERSION` (default `v26.0`).
- `KAARAN_VOICE_REPLY=off` stops the MP3 replies on WhatsApp.
- Leave `KAARAN_MODEL_MAIN` / `KAARAN_MODEL_LIGHT` unset to use the defaults in `.env.example`.

To deploy without keys, set no secrets at all. The demo then runs in replay mode, text only, and the WhatsApp
simulator still works.

## 4. Meta WhatsApp Cloud API

1. **Create the app.** At https://developers.facebook.com, choose *My Apps → Create app* and pick the
   **Business** type. Link it to a Meta Business portfolio (create one if needed).
2. **Add WhatsApp.** On the app dashboard, add the **WhatsApp** product. Meta creates a test WhatsApp Business
   Account and a **test phone number**.
3. **Add recipients.** In *WhatsApp → API Setup → To*, add each tester's phone number and verify it with the
   code Meta sends. The test number can message only these registered recipients (DEMO.md: up to 5).
4. **Permanent token (System User).**
   1. Open https://business.facebook.com/settings, go to *Users → System users → Add*, and create an **Admin**
      system user.
   2. Under *Assign assets*, give it the app (full control) and the WhatsApp account (full control).
   3. Click *Generate new token*, choose the app, set the expiry to **Never**, and tick
      **`whatsapp_business_messaging`** and **`whatsapp_business_management`**.
   4. Copy the token into the `WHATSAPP_TOKEN` secret.

   The temporary token on the API Setup page expires after 24 hours. Use it only for a quick test.
5. **Phone number id.** It is a long number (15-16 digits), not the phone number itself. Find it in either place:
   - developers.facebook.com → *My Apps* → your app → left menu **WhatsApp → API Setup** (in the new dashboard:
     *Use cases → Connect with customers through WhatsApp → Customize → API Setup*). In *Step 1, Send and receive
     messages*, the **From** box shows the test number and, right under it, **Phone number ID** (with a copy icon) and
     **WhatsApp Business Account ID**;
   - or business.facebook.com → **WhatsApp Manager → Phone numbers** → click the number → **Phone number ID**.

   Put it in `WHATSAPP_PHONE_NUMBER_ID` (digits only).
6. **App secret.** Copy it from *App settings → Basic → App secret* (click *Show*) into `WHATSAPP_APP_SECRET`.
7. **Redeploy** (Render: *Save, rebuild and deploy*; Hugging Face: restart the Space) so the new secrets load. `GET /api/whatsapp/status` should show `"send": true`,
   `"verify_token": true` and `"app_secret": true`.
8. **Webhook.** Open *WhatsApp → Configuration → Webhook → Edit* and enter:
   - **Callback URL:** `https://<your-service>.onrender.com/whatsapp/webhook`;
   - **Verify token:** the same value as `WHATSAPP_VERIFY_TOKEN`.

   Click **Verify and save**. Meta sends a GET with `hub.challenge`, and Kaaran echoes it only when the token
   matches.
9. **Subscribe to messages.** Under *Webhook fields*, **Subscribe** to the **`messages`** field.
10. **Test.** From a registered phone, send `hi` to the test number, then a question, then a voice note.
    - The bot replies with the short answer (and "🎤 I heard: …" for voice).
    - It sends the PDF when asked, and an MP3 voice summary if voice is configured.
    - Delivery errors appear in `GET /api/whatsapp/status` (phone numbers are masked).

## 5. Smoke tests (after every deploy)

```bash
BASE=https://<your-service>.onrender.com
curl -s $BASE/healthz                 # {"ok": true, "llm_mode": "live"|"replay", "pdf_browser": true, "whatsapp": {...}, "default_dataset": "blocks"}
curl -s $BASE/api/voice/status        # "configured": true, stt_model saaras:v4, tts_model bulbul:v4-flash
curl -s $BASE/api/whatsapp/status     # config send / verify_token / app_secret all true; recent events
curl -s -X POST $BASE/api/ask -H "Content-Type: application/json" \
     -d '{"question": "Which block needs most attention?"}'
curl -s -X POST $BASE/api/ask -H "Content-Type: application/json" \
     -d '{"question": "पंढरपूर मध्ये किती शाळा आहेत?"}'
curl -s -X POST $BASE/api/ask -H "Content-Type: application/json" \
     -d '{"question": "Which teacher in Pandharpur is absent most often?"}'
```

Expected, matching the regression tests in `tests/test_officer_questions.py` and `tests/test_answers.py`:
- "Which block needs most attention?" → status `ok`; first answer line "Most attention needed: Pandharpur (3
  clusters), Karmala (1 cluster), Madha (1 cluster)…".
- "पंढरपूर मध्ये किती शाळा आहेत?" → one line, "पंढरपूरमध्ये १४० शाळा आहेत (१२ केंद्रे)."
- "Which teacher…" → status `refuse` (no individual people).

Then by hand in a browser:
- [ ] the home page shows the SYNTHETIC banner;
- [ ] a blue number opens its source;
- [ ] the PDF downloads as one A4 page;
- [ ] `/whatsapp` (simulator): `hello`, then a question;
- [ ] if voice is on, 🎤 and 🔊 work;
- [ ] `/real` shows the green REAL PUBLIC DATA page once the aggregate snapshot is uploaded as a Render Secret File
      (Render step 7); without it the page says no snapshot is available, which is also safe.

## 6. Freeze the submitted version

1. When the smoke tests pass, tag the exact commit that is deployed:
   ```bash
   git tag -a build-submission -m "Build-stage submission (deployed to https://<HF_USER>-kaaran.hf.space)"
   git push origin build-submission
   ```
2. Put the GitHub URL, the Space URL and the tag or commit hash in the submission form.
3. **Do not push to `main` on GitHub or to the Space after the deadline** (2026-11-01, 11:59 pm). Judges must see
   the version that was submitted. Later work goes on a branch.
4. Keep the Space running (do not pause it) and keep the secrets valid until judging ends. Rotate the keys after.

## 7. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| The first page load takes long, or "Building / Starting" | **Cold start.** Free Spaces sleep after a period without visitors. The next visit restarts the container, which prepares ingest, trust checks and packs for every demo dataset in the background (the synthetic data itself was generated at build time). Wait, then reload. Open the Space yourself shortly before a judged demo. |
| Startup fails with `PermissionError` under `/app/data` | The container runs as uid 1000. The Dockerfile already creates that user and gives it `/app`; if you changed the Dockerfile, keep the `useradd -u 1000`, `chown -R user /app` and `USER user` lines. |
| The PDF link returns 503 | No headless browser was found. The image installs Chromium at `/usr/bin/chromium` (`KAARAN_BROWSER`). Check `pdf_browser` in `/healthz`. Meanwhile `/api/briefs/<id>/print?lang=mr` gives a printable page. |
| PDF is blank or the browser crashes | Chromium in containers needs `--no-sandbox`. Keep `KAARAN_BROWSER_NO_SANDBOX=1` (set in the image). |
| 🎤 / 🔊 buttons are missing | `SARVAM_API_KEY` is not set, or `KAARAN_VOICE=off`. Check `/api/voice/status`. Text still works. |
| "Question read by: rules" for new wordings | `KAARAN_LLM_MODE` is `replay`, `ANTHROPIC_API_KEY` is missing, or the spend cap was reached. The rule fallback still answers, and figures are identical in every mode. |
| Webhook "Verify and save" fails | The Space is private or asleep, the URL is not `/whatsapp/webhook`, or `WHATSAPP_VERIFY_TOKEN` differs from what you typed in Meta (restart after changing secrets). |
| Messages arrive but no reply; status shows a signature error | `WHATSAPP_APP_SECRET` is missing or wrong. Every POST must carry a valid `X-Hub-Signature-256`. |
| No webhook events at all | Check that the **messages** field is subscribed and the app is subscribed to the WhatsApp Business Account (`POST /<WABA_ID>/subscribed_apps` with the token). |
| Error `131030` | The recipient is not on the test number's list. **The test number only reaches registered recipients** (step 4.3). |
| Error `190` | The token has expired. Use the System User token (step 4.4). |
| Error `131047`, or no reply after a long gap | **24-hour customer-service window.** Free-form replies are allowed only within 24 hours of the user's last message. Outside it, Meta requires an approved template message. The officer just sends a new message to reopen the window. Proactive alerts on real WhatsApp therefore need an approved template; the simulator's "🔔 Send alert" shows the flow. |
| Voice note on real WhatsApp is not transcribed | Voice must be configured (`/api/voice/status`) and the note shorter than about 30 seconds. The bot replies with a fixed reason (never the raw API error). |
| Actions confirmed in the baithak pack disappear | Space storage is not persistent by default. `actions.json`, caches and generated data reset on restart. This is fine for the demo. |
