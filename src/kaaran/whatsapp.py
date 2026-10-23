"""WhatsApp bot: the same question flow over the WhatsApp Business Cloud API (typed question in; summary + PDF out).

- `Bot.handle` is transport-independent and shared by the real webhook and the local simulator.
- Cloud API (Graph v26.0 by default): POST /{phone_number_id}/messages sends text and documents,
  POST /{phone_number_id}/media uploads the PDF brief.
- Webhook POSTs are accepted only with a valid X-Hub-Signature-256 (HMAC-SHA256 of the raw body, keyed with the
  app secret). Message ids are de-duplicated because Meta retries deliveries.
- Phone numbers are kept in memory only and masked in the event log.
"""

from __future__ import annotations

import hashlib
import hmac
import threading
import time
import unicodedata
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

from .brief.pdf import PdfUnavailable
from .llm.client import setting
from .service import LANGS, Service, as_text

GRAPH = "https://graph.facebook.com"
TEXT_LIMIT = 4096
CAPTION_LIMIT = 1024
MEDIA_TTL_S = 25 * 24 * 3600  # Meta keeps uploaded media for 30 days

ACK = ("⏳ प्रश्न मिळाला. पुरावे तपासत आहे, थोडा वेळ लागेल...", "⏳ Got your question. Checking the evidence, this takes a moment...")
PDF_CAPTION = ("{title} - एक पानी अहवाल. कृत्रिम (SYNTHETIC) डेमो डेटा.", "{title} - one-page brief. SYNTHETIC demo data.")
PDF_MISSING = ("PDF सध्या तयार करता आला नाही; वरील सारांश पाहा.", "Could not make the PDF right now; see the summary above.")
UNSUPPORTED = ("सध्या फक्त टाइप केलेले प्रश्न समजतात (व्हॉइस नोट नंतर येईल).", "For now I understand typed questions only (voice notes come later).")
LANG_SET = ("ठीक आहे, आता उत्तरे मराठीत येतील.", "OK, replies will now be in English.")
ERROR = ("माफ करा, काहीतरी चुकले. कृपया पुन्हा प्रयत्न करा.", "Sorry, something went wrong. Please try again.")
HELP = (
    "नमस्कार! मी *कारण* - शिक्षण डेटा विश्लेषक (डेमो: कृत्रिम डेटा).\nएका तालुक्याबद्दल प्रश्न टाइप करा, उदा.:\n{examples}\n\n"
    "उत्तर: छोटा सारांश + एक पानी PDF अहवाल. इंग्रजीसाठी 'english' लिहा.",
    "Hello! I am *Kaaran*, an education data analyst (demo: synthetic data).\nType a question about one taluka, e.g.:\n{examples}\n\n"
    "You get a short summary + a one-page PDF brief. Type 'marathi' for Marathi.",
)
HELP_WORDS = {"", "hi", "hello", "help", "start", "menu", "नमस्कार", "नमस्ते", "मदत", "हाय"}
LANG_WORDS = {"en": {"english", "en", "इंग्रजी", "इंग्लिश"}, "mr": {"marathi", "mr", "मराठी"}}


@dataclass
class Reply:
    kind: str  # text | document
    text: str = ""  # message body, or the document caption
    path: Path | None = None
    filename: str = ""
    brief_id: str = ""
    lang: str = "mr"


def split_text(text: str, limit: int = TEXT_LIMIT) -> list[str]:
    """Split on blank lines (then lines, then hard) so each part fits one WhatsApp message."""
    parts, cur = [], ""
    for block in text.split("\n\n"):
        piece = block if not cur else cur + "\n\n" + block
        if len(piece) <= limit:
            cur = piece
            continue
        if cur:
            parts.append(cur)
        while len(block) > limit:
            cut = block.rfind("\n", 0, limit)
            cut = cut if cut > 0 else limit
            parts.append(block[:cut])
            block = block[cut:].lstrip("\n")
        cur = block
    if cur:
        parts.append(cur)
    return parts


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip().strip("!.?।").lower()


class Bot:
    def __init__(self, service: Service, dataset: str | None = None):
        self.service = service
        self.dataset = dataset
        self.lang: dict[str, str] = {}

    def help_text(self, lang: str) -> str:
        i = LANGS.index(lang)
        ex = [e["text"] for e in self.service.workspace(self.dataset).examples()]
        picks = [ex[0], ex[3], ex[2]] if lang == "mr" else [ex[1], ex[4], ex[2]]
        return HELP[i].format(examples="\n".join(f"• {q}" for q in picks))

    def handle(self, sender: str, kind: str, text: str, send: Callable[[Reply], None]) -> None:
        lang = self.lang.get(sender, "mr")
        i = LANGS.index(lang)
        if kind != "text":
            send(Reply("text", UNSUPPORTED[i], lang=lang))
            return
        cmd = _norm(text)
        for code, words in LANG_WORDS.items():
            if cmd in words:
                self.lang[sender] = code
                send(Reply("text", LANG_SET[LANGS.index(code)], lang=code))
                return
        if cmd in HELP_WORDS:
            send(Reply("text", self.help_text(lang), lang=lang))
            return
        answer = self.service.ask(text, self.dataset, on_progress=lambda: send(Reply("text", ACK[i], lang=lang)))
        if answer.status != "ok":
            send(Reply("text", answer.reply[lang], lang=lang))
            return
        for part in split_text(as_text(answer.summary[lang], bold="*")):
            send(Reply("text", part, lang=lang))
        ws, focus = self.service.resolve_brief(answer.brief_id)
        try:
            path = ws.pdf(focus, lang)
        except PdfUnavailable:
            send(Reply("text", PDF_MISSING[i], lang=lang))
            return
        caption = PDF_CAPTION[i].format(title=answer.summary[lang]["title"])[:CAPTION_LIMIT]
        filename = f"Kaaran_{answer.focus_name['en'].replace(' ', '_')}_{lang}.pdf"
        send(Reply("document", caption, path, filename, answer.brief_id, lang))


# ---------- Cloud API ----------

@dataclass
class CloudConfig:
    token: str | None
    phone_number_id: str | None
    verify_token: str | None
    app_secret: str | None
    graph_version: str = "v26.0"

    @classmethod
    def from_settings(cls) -> CloudConfig:
        return cls(setting("WHATSAPP_TOKEN"), setting("WHATSAPP_PHONE_NUMBER_ID"), setting("WHATSAPP_VERIFY_TOKEN"),
                   setting("WHATSAPP_APP_SECRET"), setting("WHATSAPP_GRAPH_VERSION") or "v26.0")

    @property
    def can_send(self) -> bool:
        return bool(self.token and self.phone_number_id)

    def status(self) -> dict:
        return {"send": self.can_send, "verify_token": bool(self.verify_token), "app_secret": bool(self.app_secret),
                "graph_version": self.graph_version}


class CloudAPIError(RuntimeError):
    pass


class CloudAPI:
    def __init__(self, cfg: CloudConfig, http: httpx.Client | None = None):
        self.cfg = cfg
        self.http = http or httpx.Client(timeout=60)
        self._media: dict[tuple[str, float], tuple[str, float]] = {}  # (path, mtime) -> (media id, uploaded at)

    def _post(self, path: str, **kw) -> dict:
        if not self.cfg.can_send:
            raise CloudAPIError("WHATSAPP_TOKEN / WHATSAPP_PHONE_NUMBER_ID not set")
        url = f"{GRAPH}/{self.cfg.graph_version}/{self.cfg.phone_number_id}/{path}"
        r = self.http.post(url, headers={"Authorization": f"Bearer {self.cfg.token}"}, **kw)
        try:
            data = r.json()
        except ValueError:
            data = {}
        if r.status_code >= 400:
            err = data.get("error", {}) if isinstance(data, dict) else {}
            raise CloudAPIError(f"HTTP {r.status_code}: {err.get('code')} {err.get('message', r.text[:200])}")
        return data

    def send_text(self, to: str, body: str) -> dict:
        return self._post("messages", json={"messaging_product": "whatsapp", "recipient_type": "individual", "to": to,
                                            "type": "text", "text": {"preview_url": False, "body": body}})

    def upload_pdf(self, path: Path) -> str:
        key = (str(path), path.stat().st_mtime)
        cached = self._media.get(key)
        if cached and time.time() - cached[1] < MEDIA_TTL_S:
            return cached[0]
        with open(path, "rb") as f:
            data = self._post("media", data={"messaging_product": "whatsapp", "type": "application/pdf"},
                              files={"file": (path.name, f, "application/pdf")})
        self._media[key] = (data["id"], time.time())
        return data["id"]

    def send_document(self, to: str, media_id: str, filename: str, caption: str) -> dict:
        return self._post("messages", json={"messaging_product": "whatsapp", "recipient_type": "individual", "to": to,
                                            "type": "document",
                                            "document": {"id": media_id, "filename": filename, "caption": caption}})

    def deliver(self, to: str, reply: Reply) -> None:
        if reply.kind == "document":
            self.send_document(to, self.upload_pdf(reply.path), reply.filename, reply.text)
        else:
            self.send_text(to, reply.text)


# ---------- webhook ----------

def valid_signature(raw: bytes, header: str | None, app_secret: str | None) -> bool:
    if not app_secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[len("sha256="):].strip().lower())


def verify_challenge(mode: str | None, token: str | None, challenge: str | None, verify_token: str | None) -> str | None:
    """The webhook subscription handshake: echo the challenge only for the configured verify token."""
    if mode == "subscribe" and verify_token and token and hmac.compare_digest(token, verify_token) and challenge is not None:
        return challenge
    return None


def incoming_messages(payload) -> list[dict]:
    """User messages in a webhook payload (status updates are ignored)."""
    out = []
    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        return out
    for entry in payload.get("entry") or []:
        for change in (entry.get("changes") or []) if isinstance(entry, dict) else []:
            if not isinstance(change, dict) or change.get("field") != "messages":
                continue
            value = change.get("value") or {}
            meta = value.get("metadata") or {}
            for m in value.get("messages") or []:
                if not isinstance(m, dict) or not m.get("id") or not m.get("from"):
                    continue
                text = (m.get("text") or {}).get("body", "") if m.get("type") == "text" else ""
                out.append({"id": m["id"], "from": str(m["from"]), "type": m.get("type", ""), "text": text,
                            "phone_number_id": meta.get("phone_number_id")})
    return out


class Seen:
    """Bounded, thread-safe set of processed message ids."""

    def __init__(self, size: int = 5000):
        self.size, self._ids, self._lock = size, OrderedDict(), threading.Lock()

    def add(self, key: str) -> bool:
        with self._lock:
            if key in self._ids:
                return False
            self._ids[key] = True
            while len(self._ids) > self.size:
                self._ids.popitem(last=False)
            return True


def mask(number: str) -> str:
    return "…" + number[-4:] if len(number) > 4 else "…"


class Gateway:
    """Real WhatsApp traffic: filter + de-duplicate webhook messages, run the bot, deliver replies via the Cloud API."""

    def __init__(self, service: Service, cfg: CloudConfig | None = None, api: CloudAPI | None = None, bot: Bot | None = None):
        self.cfg = cfg or CloudConfig.from_settings()
        self.api = api or CloudAPI(self.cfg)
        self.bot = bot or Bot(service)
        self.seen = Seen()
        self.events: deque = deque(maxlen=50)

    def log(self, **event) -> None:
        self.events.append({"at": time.strftime("%H:%M:%S"), **event})

    def accept(self, payload) -> list[dict]:
        new = []
        for m in incoming_messages(payload):
            if self.cfg.phone_number_id and m["phone_number_id"] and m["phone_number_id"] != self.cfg.phone_number_id:
                continue
            if self.seen.add(m["id"]):
                new.append(m)
                self.log(dir="in", who=mask(m["from"]), kind=m["type"], chars=len(m["text"]))
        return new

    def process(self, msg: dict) -> None:
        def send(reply: Reply) -> None:
            try:
                self.api.deliver(msg["from"], reply)
                self.log(dir="out", who=mask(msg["from"]), kind=reply.kind, status="sent")
            except (CloudAPIError, httpx.HTTPError, OSError) as e:
                self.log(dir="out", who=mask(msg["from"]), kind=reply.kind, status="failed", error=str(e)[:300])

        try:
            self.bot.handle(msg["from"], msg["type"], msg["text"], send)
        except Exception as e:  # never let one message kill the worker; tell the officer
            self.log(dir="bot", who=mask(msg["from"]), status="error", error=f"{type(e).__name__}: {e}"[:300])
            send(Reply("text", ERROR[LANGS.index(self.bot.lang.get(msg["from"], "mr"))]))


def simulate(bot: Bot, sender: str, text: str) -> list[Reply]:
    """Local simulator: same bot, replies collected instead of sent."""
    out: list[Reply] = []
    bot.handle(sender, "text", text, out.append)
    return out
