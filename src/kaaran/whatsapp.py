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
from .block.answers import ANSWER_HEADING, detect_lang
from .brief.texts_block import BLOCK_TITLE
from .service import LANGS, Service, as_text

GRAPH = "https://graph.facebook.com"
TEXT_LIMIT = 4096
CAPTION_LIMIT = 1024
MEDIA_TTL_S = 25 * 24 * 3600  # Meta keeps uploaded media for 30 days

ACK = ("⏳ प्रश्न मिळाला. पुरावे तपासत आहे, थोडा वेळ लागेल...", "⏳ Got your question. Checking the evidence, this takes a moment...")
PDF_CAPTION = ("{title} - एक पानी अहवाल. कृत्रिम (SYNTHETIC) डेमो डेटा.", "{title} - one-page brief. SYNTHETIC demo data.")
PDF_MISSING = ("PDF सध्या तयार करता आला नाही; वरील सारांश पाहा.", "Could not make the PDF right now; see the summary above.")
UNSUPPORTED = ("हा संदेश वाचता आला नाही. कृपया प्रश्न टाइप करा किंवा व्हॉइस नोट पाठवा.", "I could not read this message. Please type your question or send a voice note.")
VOICE_FAILED = ("आवाज समजला नाही ({why}). कृपया पुन्हा बोला (३० सेकंदांपेक्षा कमी) किंवा प्रश्न टाइप करा.",
                "I could not understand the voice note ({why}). Please try again (under 30 seconds) or type the question.")
HEARD = ("🎤 ऐकले: \"{text}\"", "🎤 I heard: \"{text}\"")
VOICE_OFF = ("सध्या व्हॉइस नोट समजण्याची सोय सुरू नाही. कृपया प्रश्न टाइप करा.", "Voice notes are not available right now. Please type your question.")
VOICE_REASON = {
    "too_long": ("व्हॉइस नोट खूप मोठी आहे", "the voice note is too long"),
    "no_speech": ("आवाज स्पष्ट ऐकू आला नाही", "no clear speech was heard"),
    "unsupported": ("हा ऑडिओ प्रकार चालत नाही", "this audio type is not supported"),
    "download": ("व्हॉइस नोट डाउनलोड झाली नाही", "the voice note could not be downloaded"),
    "cap": ("आजची आवाज-सेवेची मर्यादा संपली", "today's voice limit is used up"),
    "service": ("आवाज-सेवा सध्या उपलब्ध नाही", "the voice service is unavailable"),
    "off": ("आवाज-सेवा बंद आहे", "voice is switched off"),
}
VOICE_CAPTION = ("🔊 {title}: एका मिनिटाचा आवाज-सारांश", "🔊 {title}: one-minute voice summary")
LANG_SET = ("ठीक आहे, आता उत्तरे मराठीत येतील.", "OK, replies will now be in English.")
ERROR = ("माफ करा, काहीतरी चुकले. कृपया पुन्हा प्रयत्न करा.", "Sorry, something went wrong. Please try again.")
HELP = (
    "नमस्कार! मी *कारण* - शिक्षण डेटा विश्लेषक (डेमो: कृत्रिम डेटा).\nतालुका किंवा केंद्राबद्दल प्रश्न टाइप करा किंवा 🎤 व्हॉइस नोट पाठवा, उदा.:\n{examples}\n\n"
    "उत्तर: थेट उत्तर + आवाज-सारांश; 'अहवाल' लिहिल्यास एक पानी PDF. मी तुमच्याच भाषेत उत्तर देतो.",
    "Hello! I am *Kaaran*, an education data analyst (demo: synthetic data).\nType or 🎤 speak a question about a block or cluster, e.g.:\n{examples}\n\n"
    "You get a direct answer + a voice summary; reply 'report' for the one-page PDF. I reply in the language you use.",
)
HELP_WORDS = {"", "hi", "hello", "help", "start", "menu", "नमस्कार", "नमस्ते", "मदत", "हाय"}
LANG_WORDS = {"en": {"english", "en", "इंग्रजी", "इंग्लिश"}, "mr": {"marathi", "mr", "मराठी"}}
REPORT_WORDS = {"अहवाल", "report", "हो", "होय", "yes", "ho", "ahwal", "ahaval"}
REPORT_HINT = ("📄 पूर्ण पुरावा अहवाल (PDF, प्रत्येक आकड्याचा स्रोत) हवा असल्यास 'अहवाल' लिहा.",
               "📄 For the full evidence brief (PDF, source of every figure), reply 'report'.")
BRIEF_MODES = {"cards", "cluster", "dq", "twin"}  # answers that come with the one-page PDF
FOLLOWUP_REASONS = {"missing_place", "ambiguous_place", "unknown_place", "unknown_kendra"}
NO_ALERT = ("सध्या कोणत्याही तालुक्यात तातडीचा इशारा नाही.", "No block needs urgent attention right now.")


@dataclass
class Reply:
    kind: str  # text | document | audio
    text: str = ""  # message body, or the document caption
    path: Path | None = None
    filename: str = ""
    brief_id: str = ""
    lang: str = "mr"
    answer_id: str = ""  # the answer this reply belongs to (voice notes: its spoken version)


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
        self.lang: dict[str, str] = {}  # sender -> language chosen with 'english' / 'marathi' (default for unclear messages)
        self.offer: dict[str, str] = {}  # sender -> block whose full brief 'report' opens (last alert or last short answer)
        self.followup: dict[str, str] = {}  # sender -> question that got "which taluka?" (the next reply completes it)
        self.offer_lang: dict[str, str] = {}  # sender -> language the 'report' offer was made in
        self.last_lang: dict[str, str] = {}  # sender -> language of the last reply (default for unclear messages)

    @property
    def pending(self) -> dict[str, str]:  # older name, kept for callers
        return self.offer

    def help_text(self, lang: str) -> str:
        i = LANGS.index(lang)
        ex = [e["text"] for e in self.service.workspace(self.dataset).examples()]
        picks = [ex[0], ex[3], ex[2]] if lang == "mr" else [ex[1], ex[4], ex[2]]
        return HELP[i].format(examples="\n".join(f"• {q}" for q in picks))

    def handle(self, sender: str, kind: str, text: str, send: Callable[[Reply], None],
               audio: tuple[bytes, str] | None = None) -> None:
        lang = self.last_lang.get(sender) or self.lang.get(sender, "mr")
        i = LANGS.index(lang)
        if kind == "audio":
            from .voice.sarvam import VoiceUnavailable

            if not self.service.voice.configured:
                send(Reply("text", VOICE_OFF[i], lang=lang))
                return
            if audio is None:  # the gateway could not download it
                send(Reply("text", VOICE_FAILED[i].format(why=VOICE_REASON["download"][i]), lang=lang))
                return
            try:  # speech -> text (spoken language detected), then exactly the same path as a typed message
                tr = self.service.voice.stt(audio[0], audio[1], self.service.keyterms(self.dataset), language=None)
            except VoiceUnavailable as e:  # fixed bilingual reason; the raw API message is never shown
                send(Reply("text", VOICE_FAILED[i].format(why=VOICE_REASON.get(e.reason, VOICE_REASON["service"])[i]), lang=lang))
                return
            code = str(tr.language_code or "")
            lang = "en" if code.startswith("en") else "mr" if code.startswith("mr") else detect_lang(tr.text, lang)
            i = LANGS.index(lang)
            send(Reply("text", HEARD[i].format(text=tr.text), lang=lang))
            kind, text = "text", tr.text
        if kind != "text":
            send(Reply("text", UNSUPPORTED[i], lang=lang))
            return
        cmd = _norm(text)
        for code, words in LANG_WORDS.items():
            if cmd in words:
                self.lang[sender] = self.last_lang[sender] = code
                send(Reply("text", LANG_SET[LANGS.index(code)], lang=code))
                return
        if cmd in HELP_WORDS:
            send(Reply("text", self.help_text(detect_lang(text, lang)), lang=detect_lang(text, lang)))
            return
        ctx = self.followup.pop(sender, None)
        if kind == "text" and audio is None:
            lang = detect_lang((ctx + " " + text) if ctx else text, lang)  # reply in the language the officer wrote in
        i = LANGS.index(lang)
        ack = lambda: send(Reply("text", ACK[i], lang=lang))  # noqa: E731
        if cmd in REPORT_WORDS and sender in self.offer:
            lang = self.offer_lang.pop(sender, lang)  # the full brief comes in the language of the answer it follows
            i = LANGS.index(lang)
            answer = self.service.open_block(self.dataset, self.offer.pop(sender), on_progress=ack)
        else:
            self.offer.pop(sender, None)  # a new question replaces any older 'report' offer
            self.offer_lang.pop(sender, None)
            answer = self.service.ask(text, self.dataset, on_progress=ack, context=ctx, default_lang=lang)
            if audio is None:
                lang = answer.info.get("reply_lang", lang)
                i = LANGS.index(lang)
        if answer.status != "ok":
            if answer.status == "clarify" and answer.plan.get("reason") in FOLLOWUP_REASONS:
                self.followup[sender] = answer.question  # the next reply ("Solapur district") completes this question
            elif ctx and len(text.split()) <= 3:
                self.followup[sender] = ctx  # one unrecognised reply ("Pune") keeps the earlier question open
            self.last_lang[sender] = lang
            send(Reply("text", answer.reply[lang], lang=lang))
            return
        self.last_lang[sender] = lang
        self._deliver(answer, lang, send, sender)

    def alert(self, sender: str, send: Callable[[Reply], None]) -> None:
        """Proactive message when new data arrives: the most urgent block (the officer replies 'report' to open it)."""
        lang = self.lang.get(sender, "mr")
        alerts = self.service.alerts(self.dataset)
        if not alerts:
            send(Reply("text", NO_ALERT[LANGS.index(lang)], lang=lang))
            return
        top = alerts[0]
        self.pending[sender] = top["block"]
        self.offer_lang[sender] = lang
        send(Reply("text", top["text"][lang], lang=lang))

    def _deliver(self, answer, lang: str, send: Callable[[Reply], None], sender: str = "") -> None:
        """Short answers (a figure, a ranking, data checks, why it improved): text + voice note, and 'report' gives the
        full brief. Kendra-card answers ("what needs attention", "why did it fall", an alert): text + PDF + voice note."""
        i = LANGS.index(lang)
        for part in split_text(as_text(answer.summary[lang], bold="*")):
            send(Reply("text", part, lang=lang))
        mode = answer.summary[lang].get("mode", "cards")
        if mode not in BRIEF_MODES:
            if sender and not answer.info.get("district"):
                self.offer[sender] = answer.focus
                self.offer_lang[sender] = lang
                send(Reply("text", REPORT_HINT[i], lang=lang))
            self._voice_note(answer, lang, send)
            return
        ws, focus = self.service.resolve_brief(answer.brief_id)
        try:
            path = ws.pdf(focus, lang)
        except PdfUnavailable:
            send(Reply("text", PDF_MISSING[i], lang=lang))
            self._voice_note(answer, lang, send)  # the voice summary does not depend on the PDF
            return
        title = answer.summary[lang]["title"]
        if title.startswith(ANSWER_HEADING[i]):  # the PDF is the brief, not the short answer ("Direct answer: X")
            title = f"{BLOCK_TITLE[i]}: {answer.focus_name[lang]}"
        caption = PDF_CAPTION[i].format(title=title)[:CAPTION_LIMIT]
        filename = f"Kaaran_{answer.focus_name['en'].replace(' ', '_')}_{lang}.pdf"
        send(Reply("document", caption, path, filename, answer.brief_id, lang))
        self._voice_note(answer, lang, send)

    def _voice_note(self, answer, lang: str, send: Callable[[Reply], None]) -> None:
        """Spoken version of this answer (skipped quietly when voice is off or fails)."""
        from .voice.sarvam import VoiceUnavailable

        if not self.service.voice.configured or setting("KAARAN_VOICE_REPLY", "on") == "off":
            return
        try:
            path = self.service.voice_answer(answer, lang)
        except (VoiceUnavailable, OSError):  # the text and PDF already went out; the voice note is a bonus
            return
        i = LANGS.index(lang)
        caption = VOICE_CAPTION[i].format(title=answer.summary[lang]["title"])
        filename = f"Kaaran_{answer.focus_name['en'].replace(' ', '_')}_{lang}.mp3"
        send(Reply("audio", caption, path, filename, answer.brief_id, lang, answer.answer_id))


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
        return self.upload(path, "application/pdf")

    def upload(self, path: Path, mime: str) -> str:
        key = (str(path), path.stat().st_mtime)
        cached = self._media.get(key)
        if cached and time.time() - cached[1] < MEDIA_TTL_S:
            return cached[0]
        with open(path, "rb") as f:
            data = self._post("media", data={"messaging_product": "whatsapp", "type": mime},
                              files={"file": (path.name, f, mime)})
        self._media[key] = (data["id"], time.time())
        return data["id"]

    def send_document(self, to: str, media_id: str, filename: str, caption: str) -> dict:
        return self._post("messages", json={"messaging_product": "whatsapp", "recipient_type": "individual", "to": to,
                                            "type": "document",
                                            "document": {"id": media_id, "filename": filename, "caption": caption}})

    def send_audio(self, to: str, media_id: str) -> dict:
        # MP3 is sent as an audio message; a WhatsApp voice-note bubble would need OGG/Opus (no transcoder installed)
        return self._post("messages", json={"messaging_product": "whatsapp", "recipient_type": "individual", "to": to,
                                            "type": "audio", "audio": {"id": media_id}})

    def download_media(self, media_id: str, max_bytes: int = 16_000_000) -> tuple[bytes, str]:
        """Incoming media: GET /{media-id} for a 5-minute URL, then GET the URL with the same Bearer token."""
        if not self.cfg.can_send:
            raise CloudAPIError("WHATSAPP_TOKEN / WHATSAPP_PHONE_NUMBER_ID not set")
        auth = {"Authorization": f"Bearer {self.cfg.token}"}
        r = self.http.get(f"{GRAPH}/{self.cfg.graph_version}/{media_id}", headers=auth,
                          params={"phone_number_id": self.cfg.phone_number_id})
        if r.status_code >= 400:
            raise CloudAPIError(f"media lookup HTTP {r.status_code}")
        meta = r.json()
        if int(meta.get("file_size") or 0) > max_bytes:
            raise CloudAPIError("media too large")
        r2 = self.http.get(meta["url"], headers=auth)
        if r2.status_code >= 400:
            raise CloudAPIError(f"media download HTTP {r2.status_code}")
        return r2.content, meta.get("mime_type") or r2.headers.get("content-type", "")

    def deliver(self, to: str, reply: Reply) -> None:
        if reply.kind == "document":
            self.send_document(to, self.upload_pdf(reply.path), reply.filename, reply.text)
        elif reply.kind == "audio":
            self.send_audio(to, self.upload(reply.path, "audio/mpeg"))
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
                item = {"id": m["id"], "from": str(m["from"]), "type": m.get("type", ""), "text": text,
                        "phone_number_id": meta.get("phone_number_id")}
                audio = m.get("audio") if m.get("type") == "audio" else None
                if isinstance(audio, dict) and audio.get("id"):
                    item |= {"media_id": str(audio["id"]), "mime_type": str(audio.get("mime_type") or "audio/ogg")}
                out.append(item)
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

        audio = None
        if msg.get("type") == "audio" and msg.get("media_id") and self.bot.service.voice.configured:
            try:
                audio = self.api.download_media(msg["media_id"])
                audio = (audio[0], audio[1] or msg.get("mime_type", "audio/ogg"))
            except (CloudAPIError, httpx.HTTPError, OSError, KeyError, ValueError) as e:
                self.log(dir="in", who=mask(msg["from"]), kind="audio", status="download_failed", error=str(e)[:200])
        try:
            self.bot.handle(msg["from"], msg["type"], msg["text"], send, audio=audio)
        except Exception as e:  # never let one message kill the worker; tell the officer
            self.log(dir="bot", who=mask(msg["from"]), status="error", error=f"{type(e).__name__}: {e}"[:300])
            send(Reply("text", ERROR[LANGS.index(self.bot.lang.get(msg["from"], "mr"))]))


def simulate(bot: Bot, sender: str, text: str) -> list[Reply]:
    """Local simulator: same bot, replies collected instead of sent."""
    out: list[Reply] = []
    bot.handle(sender, "text", text, out.append)
    return out


def simulate_voice(bot: Bot, sender: str, audio: bytes, mime: str) -> list[Reply]:
    """Local simulator for a voice note: same bot, same speech-to-text path."""
    out: list[Reply] = []
    bot.handle(sender, "audio", "", out.append, audio=(audio, mime))
    return out


def simulate_alert(bot: Bot, sender: str) -> list[Reply]:
    out: list[Reply] = []
    bot.alert(sender, out.append)
    return out
