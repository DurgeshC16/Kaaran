"""FastAPI app: web demo, brief downloads and evidence drill-down, WhatsApp webhook and a local WhatsApp simulator.

Run: python -m kaaran.api  (http://127.0.0.1:8000 ; simulator at /whatsapp)
"""

from __future__ import annotations

import json
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from ..brief.pdf import PdfUnavailable, find_browser
from ..llm.client import get_client
from ..service import LANGS, MAX_QUESTION_CHARS, Service, get_service, number_detail, set_detail
from ..whatsapp import Bot, Gateway, simulate, simulate_alert, simulate_voice, valid_signature, verify_challenge
from starlette.concurrency import run_in_threadpool

MAX_AUDIO_BYTES = 4_500_000  # about 30 s of compressed speech (the sync STT limit)

STATIC = Path(__file__).resolve().parent / "static"


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS * 2)
    dataset: str | None = None


class OpenIn(BaseModel):
    dataset: str | None = None
    focus: str = Field(min_length=1, max_length=60)


class ActionIn(BaseModel):
    action: str = Field(min_length=1, max_length=80)
    status: str = Field(pattern="^(open|confirmed|done)$")


class SimIn(BaseModel):
    sender: str = Field(default="demo-officer", min_length=1, max_length=40)
    text: str = Field(default="", max_length=MAX_QUESTION_CHARS * 2)


def _lang(lang: str) -> str:
    if lang not in LANGS:
        raise HTTPException(400, f"lang must be one of {LANGS}")
    return lang


def create_app(service: Service | None = None, gateway: Gateway | None = None, warm: bool = True) -> FastAPI:
    svc = service or get_service()
    gw = gateway or Gateway(svc)
    sim_bot = Bot(svc)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if warm:  # ingest + trust + packs in the background (default dataset first); questions are then fast
            def prepare_all():
                for key in [svc.default] + [k for k in svc.datasets if k != svc.default]:
                    svc.workspace(key).prepare()

            threading.Thread(target=prepare_all, daemon=True).start()
        yield

    app = FastAPI(title="Kaaran demo", version="0.4.0", lifespan=lifespan)
    app.state.service, app.state.gateway = svc, gw

    # ---------- pages ----------

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html", media_type="text/html; charset=utf-8")

    @app.get("/real", response_class=HTMLResponse, include_in_schema=False)
    def real_page():
        return FileResponse(STATIC / "real.html", media_type="text/html; charset=utf-8")

    @app.get("/api/real/snapshot")
    def real_snapshot():
        """Aggregate-only snapshot of REAL public data, if built on this machine (data/real/ is never committed)."""
        from ..service import ROOT

        path = ROOT / "data" / "real" / "reports" / "real_snapshot.json"
        if not path.exists():
            raise HTTPException(404, "no real-data snapshot here; run python -m kaaran.real (docs/10_TESTING_GUIDE.md)")
        return JSONResponse(json.loads(path.read_text(encoding="utf-8")))

    @app.get("/whatsapp", response_class=HTMLResponse, include_in_schema=False)
    def whatsapp_page():
        return FileResponse(STATIC / "whatsapp.html", media_type="text/html; charset=utf-8")

    @app.get("/healthz")
    def healthz():
        client = get_client()
        return {"ok": True, "llm_mode": client.mode, "pdf_browser": bool(find_browser()),
                "whatsapp": gw.cfg.status(), "default_dataset": svc.default}

    # ---------- web API ----------

    @app.get("/api/datasets")
    def datasets():
        out = []
        for key, spec in svc.datasets.items():
            ws = svc.workspace(key)
            item = {"id": key, "label": {"mr": spec.label_mr, "en": spec.label_en}, "default": key == svc.default,
                    "ready": ws.ingest is not None, "kind": spec.kind}
            if ws.ingest is not None:
                item["examples"] = ws.examples()
            out.append(item)
        return out

    @app.get("/api/datasets/{dataset}/examples")
    def examples(dataset: str):
        try:
            return svc.workspace(dataset).examples()
        except KeyError as e:
            raise HTTPException(404, str(e)) from e

    @app.post("/api/ask")
    def ask(body: AskIn):
        if body.dataset is not None and body.dataset not in svc.datasets:
            raise HTTPException(404, f"unknown dataset {body.dataset!r}")
        return svc.ask(body.question, body.dataset).to_dict()

    @app.get("/api/datasets/{dataset}/alerts")
    def alerts(dataset: str):
        """Proactive district scan: blocks with clusters that need attention (computed when data arrives, no LLM)."""
        try:
            return svc.alerts(dataset)
        except KeyError as e:
            raise HTTPException(404, str(e)) from e

    @app.post("/api/open")
    def open_block(body: OpenIn):
        try:
            return svc.open_block(body.dataset, body.focus).to_dict()
        except KeyError as e:
            raise HTTPException(404, str(e)) from e

    def _brief(brief_id: str):
        try:
            return svc.resolve_brief(brief_id)
        except KeyError as e:
            raise HTTPException(404, str(e)) from e

    @app.get("/api/briefs/{brief_id}/pdf")
    def brief_pdf(brief_id: str, lang: str = "mr"):
        ws, focus = _brief(brief_id)
        try:
            path = ws.pdf(focus, _lang(lang))
        except PdfUnavailable as e:
            raise HTTPException(503, f"PDF unavailable: {e}") from e
        name = ws.pack(focus)["entities"][focus]["name_en"].replace(" ", "_")
        return FileResponse(path, media_type="application/pdf", filename=f"Kaaran_{name}_{lang}.pdf")

    # ---------- voice (Sarvam AI) ----------

    async def _audio_body(request: Request) -> tuple[bytes, str]:
        mime = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
        if not mime.startswith(("audio/", "video/webm")):
            raise HTTPException(415, "send the recording as the raw request body with an audio/* Content-Type")
        body = await request.body()
        if not body:
            raise HTTPException(400, "empty audio")
        if len(body) > MAX_AUDIO_BYTES:
            raise HTTPException(413, "recording too long: keep it under 30 seconds")
        return body, request.headers.get("content-type")

    @app.get("/api/voice/status")
    def voice_status():
        return svc.voice.status()

    @app.post("/api/voice/ask")
    async def voice_ask(request: Request, dataset: str | None = None, lang: str = "mr"):
        """A spoken question (raw audio body) -> transcript -> the normal answer (with info.transcript)."""
        from ..voice.sarvam import VoiceUnavailable

        dataset = dataset or None
        if dataset is not None and dataset not in svc.datasets:
            raise HTTPException(404, f"unknown dataset {dataset!r}")
        audio, mime = await _audio_body(request)
        try:
            answer = await run_in_threadpool(svc.ask_voice, audio, mime, dataset, _lang(lang))
        except VoiceUnavailable as e:
            raise HTTPException(503, f"voice unavailable: {e}") from e
        return answer.to_dict()

    @app.get("/api/briefs/{brief_id}/voice")
    def brief_voice(brief_id: str, lang: str = "mr"):
        """One-minute spoken summary (MP3, generated once and cached)."""
        from ..voice.sarvam import VoiceUnavailable

        _brief(brief_id)
        try:
            path = svc.voice_summary(brief_id, _lang(lang))
        except VoiceUnavailable as e:
            raise HTTPException(503, f"voice unavailable: {e}") from e
        return FileResponse(path, media_type="audio/mpeg", filename=f"Kaaran_{brief_id.replace('.', '_')}_{lang}.mp3")

    @app.get("/api/briefs/{brief_id}/print", response_class=HTMLResponse)
    def brief_print(brief_id: str, lang: str = "mr"):
        """The exact HTML the PDF is printed from (fallback when no browser is available for PDF)."""
        ws, focus = _brief(brief_id)
        return HTMLResponse(ws.print_html(focus, _lang(lang)))

    @app.get("/api/briefs/{brief_id}/baithak")
    def brief_baithak(brief_id: str, lang: str = "mr"):
        """Review-meeting pack: every rubric action grouped by owner, with its evidence and tracked status."""
        ws, focus = _brief(brief_id)
        if getattr(ws, "kind", "taluka") != "block":
            raise HTTPException(404, "baithak pack is available for the cluster lens only")
        return ws.baithak(focus, _lang(lang))

    @app.post("/api/briefs/{brief_id}/actions")
    def brief_action(brief_id: str, body: ActionIn):
        ws, focus = _brief(brief_id)
        if getattr(ws, "kind", "taluka") != "block":
            raise HTTPException(404, "action tracking is available for the cluster lens only")
        try:
            return ws.set_action(focus, body.action, body.status)
        except KeyError as e:
            raise HTTPException(404, str(e)) from e

    @app.get("/api/briefs/{brief_id}/evidence")
    def brief_evidence(brief_id: str):
        ws, focus = _brief(brief_id)
        name = ws.pack(focus)["entities"][focus]["name_en"].replace(" ", "_")
        return JSONResponse(ws.pack(focus), headers={"Content-Disposition": f'attachment; filename="evidence_{name}.json"'})

    @app.get("/api/briefs/{brief_id}/number")
    def brief_number(brief_id: str, id: str = Query(min_length=1, max_length=200)):
        ws, focus = _brief(brief_id)
        pack = ws.pack(focus)
        if id not in pack["numbers"]:
            raise HTTPException(404, f"unknown number {id!r}")
        return number_detail(pack, id)

    @app.get("/api/briefs/{brief_id}/set")
    def brief_set(brief_id: str, id: str = Query(min_length=1, max_length=200)):
        ws, focus = _brief(brief_id)
        pack = ws.pack(focus)
        if id not in pack["entity_sets"]:
            raise HTTPException(404, f"unknown set {id!r}")
        return set_detail(pack, id)

    # ---------- WhatsApp: real webhook ----------

    @app.get("/whatsapp/webhook", response_class=PlainTextResponse)
    def webhook_verify(mode: str | None = Query(None, alias="hub.mode"), token: str | None = Query(None, alias="hub.verify_token"),
                       challenge: str | None = Query(None, alias="hub.challenge")):
        echoed = verify_challenge(mode, token, challenge, gw.cfg.verify_token)
        if echoed is None:
            raise HTTPException(403, "verification failed")
        return PlainTextResponse(echoed)

    @app.post("/whatsapp/webhook")
    async def webhook_receive(request: Request, background: BackgroundTasks):
        raw = await request.body()
        if not valid_signature(raw, request.headers.get("x-hub-signature-256"), gw.cfg.app_secret):
            gw.log(dir="in", status="rejected", error="bad or missing X-Hub-Signature-256 (is WHATSAPP_APP_SECRET set?)")
            raise HTTPException(403, "invalid signature")
        try:
            payload = json.loads(raw)
        except ValueError as e:
            raise HTTPException(400, "body is not JSON") from e
        for msg in gw.accept(payload):
            background.add_task(gw.process, msg)
        return {"ok": True}

    @app.get("/api/whatsapp/status")
    def whatsapp_status():
        return {"config": gw.cfg.status(), "events": list(gw.events)}

    # ---------- WhatsApp: local simulator (same bot logic, nothing leaves the machine) ----------

    @app.post("/api/whatsapp/simulate_alert")
    def whatsapp_simulate_alert(body: SimIn):
        """Simulate 'new data arrived': the bot pushes the most urgent block alert to this simulated phone."""
        return {"replies": [{"kind": r.kind, "text": r.text, "lang": r.lang} for r in simulate_alert(sim_bot, "sim:" + body.sender)]}

    @app.post("/api/whatsapp/simulate")
    def whatsapp_simulate(body: SimIn):
        out = []
        for r in simulate(sim_bot, "sim:" + body.sender, body.text):
            out.append(_sim_item(r))
        return {"replies": out}

    def _sim_item(r) -> dict:
        item = {"kind": r.kind, "text": r.text, "lang": r.lang}
        if r.kind == "document":
            item |= {"filename": r.filename, "url": f"/api/briefs/{r.brief_id}/pdf?lang={r.lang}"}
        if r.kind == "audio":
            item |= {"filename": r.filename, "url": f"/api/briefs/{r.brief_id}/voice?lang={r.lang}"}
        return item

    @app.post("/api/whatsapp/simulate_voice")
    async def whatsapp_simulate_voice(request: Request, sender: str = Query("demo-officer", min_length=1, max_length=40)):
        """Simulated WhatsApp voice note: same bot and speech-to-text path as the real webhook."""
        audio, mime = await _audio_body(request)
        replies = await run_in_threadpool(simulate_voice, sim_bot, "sim:" + sender, audio, mime)
        return {"replies": [_sim_item(r) for r in replies]}

    return app
