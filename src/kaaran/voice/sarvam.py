"""Sarvam AI speech: Marathi speech-to-text (Saaras) in, voice summary text-to-speech (Bulbul) out.

Verified against docs.sarvam.ai and a live round trip on 2026-10-28:
- STT  POST https://api.sarvam.ai/speech-to-text  multipart: file, model, mode, language_code, keyterms (JSON list).
       Accepts OGG/Opus (WhatsApp voice notes), WebM (browser recordings), MP3, WAV. Max 30 s per request.
       Response: {"request_id", "transcript", "language_code", "language_probability"?}.
- TTS  POST https://api.sarvam.ai/text-to-speech  JSON: text, language_code, model, speaker, pace, speech_sample_rate,
       output_audio_codec. Response: {"request_id", "audios": [base64]}. Max 2500 characters (v3 / v4-flash).
- Auth header "api-subscription-key". Model and speaker names come from settings (never hard-coded in code paths).
Devanagari digits are converted to ASCII before TTS (their reading is undocumented). Synthesised audio is cached on
disk by a hash of (model, speaker, language, text): each brief's voice note is generated once.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from ..llm.client import ROOT, setting

BASE_URL = "https://api.sarvam.ai"
MAX_STT_BYTES = 4_000_000  # about 30 s of compressed audio; the sync API rejects longer clips anyway
MAX_TTS_CHARS = 2500
MAX_KEYTERMS = 50
STT_INR_PER_REQUEST = 0.25  # worst case: 30 s at about 0.49 INR per minute
TTS_INR_PER_1000_CHARS = 1.0  # bulbul:v4-flash pay-as-you-go
MIME_EXT = {"audio/ogg": "ogg", "audio/opus": "opus", "audio/webm": "webm", "video/webm": "webm", "audio/mpeg": "mp3",
            "audio/mp3": "mp3", "audio/wav": "wav", "audio/x-wav": "wav", "audio/wave": "wav", "audio/mp4": "m4a",
            "audio/x-m4a": "m4a", "audio/aac": "aac", "audio/amr": "amr", "audio/flac": "flac"}
LANG_CODE = {"mr": "mr-IN", "en": "en-IN"}
DEVANAGARI_TO_ASCII = str.maketrans("०१२३४५६७८९", "0123456789")


class VoiceUnavailable(RuntimeError):
    """No key, unsupported audio, too long, or the API failed: callers fall back to text.

    `reason` is one of: off, unsupported, too_long, no_speech, cap, service (shown to officers as a fixed phrase).
    """

    def __init__(self, message: str, reason: str = "service"):
        super().__init__(message)
        self.reason = reason


@dataclass
class Transcript:
    text: str
    language_code: str | None
    request_id: str | None
    seconds: float


def base_mime(mime: str | None) -> str:
    return (mime or "").split(";")[0].strip().lower()


class SarvamClient:
    def __init__(self, api_key: str | None = None, http: httpx.Client | None = None, cache_dir: str | Path | None = None,
                 usage_log: str | Path | None = None):
        self.api_key = api_key if api_key is not None else setting("SARVAM_API_KEY")
        self.http = http or httpx.Client(timeout=60)
        self.cache_dir = Path(cache_dir or setting("KAARAN_VOICE_CACHE") or ROOT / "data" / "voice_cache")
        self.usage_log = Path(usage_log or setting("KAARAN_VOICE_USAGE_LOG") or ROOT / "data" / "voice_usage.jsonl")
        self.max_inr = float(setting("KAARAN_MAX_VOICE_INR", "100"))  # per-process cap, like KAARAN_MAX_LIVE_USD
        self.spent_inr = 0.0

    def _charge(self, inr: float) -> None:
        if self.spent_inr + inr > self.max_inr:
            raise VoiceUnavailable(f"voice spend cap reached ({self.spent_inr:.2f} of {self.max_inr:.2f} INR)", "cap")
        self.spent_inr += inr

    @property
    def configured(self) -> bool:
        """A key is set and voice is not switched off (KAARAN_VOICE=off, e.g. in tests)."""
        return bool(self.api_key) and (setting("KAARAN_VOICE") or "on").lower() != "off"

    def status(self) -> dict:
        return {"configured": self.configured, "stt_model": setting("KAARAN_STT_MODEL"), "tts_model": setting("KAARAN_TTS_MODEL"),
                "provider": "Sarvam AI", "spent_inr": round(self.spent_inr, 2), "cap_inr": self.max_inr}

    def _headers(self) -> dict:
        if not self.configured:
            raise VoiceUnavailable("voice is off or SARVAM_API_KEY is not set", "off")
        return {"api-subscription-key": self.api_key}

    def _log(self, rec: dict) -> None:
        try:
            self.usage_log.parent.mkdir(parents=True, exist_ok=True)
            with self.usage_log.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **rec}, ensure_ascii=False) + "\n")
        except OSError:
            pass

    @staticmethod
    def _error(r: httpx.Response, what: str) -> VoiceUnavailable:
        try:
            err = r.json().get("error", {})
        except ValueError:
            err = {}
        msg = str(err.get("message", "")).lower()
        reason = "too_long" if ("duration" in msg or "too long" in msg or "length" in msg) else "service"
        return VoiceUnavailable(f"{what} HTTP {r.status_code}: {err.get('code', '')} {err.get('message', r.text[:200])}".strip(), reason)

    # ---------- speech to text ----------
    def stt(self, audio: bytes, mime: str, keyterms: list[str] | None = None, language: str | None = "mr") -> Transcript:
        headers = self._headers()
        kind = base_mime(mime)
        if kind not in MIME_EXT:
            raise VoiceUnavailable(f"unsupported audio type {mime!r}", "unsupported")
        if not audio:
            raise VoiceUnavailable("empty audio", "no_speech")
        if len(audio) > MAX_STT_BYTES:
            raise VoiceUnavailable("audio too long (the limit is about 30 seconds)", "too_long")
        model = setting("KAARAN_STT_MODEL")
        if not model:
            raise VoiceUnavailable("KAARAN_STT_MODEL is not set")
        data = {"model": model, "mode": "transcribe", "language_code": LANG_CODE.get(language or "", "unknown")}
        terms = [t[:64] for t in dict.fromkeys(keyterms or []) if t][:MAX_KEYTERMS]
        if terms:
            data["keyterms"] = json.dumps(terms, ensure_ascii=False)
        self._charge(STT_INR_PER_REQUEST)
        t0 = time.monotonic()
        try:
            r = self.http.post(f"{BASE_URL}/speech-to-text", headers=headers, data=data,
                               files={"file": (f"audio.{MIME_EXT[kind]}", audio, kind)})
        except httpx.HTTPError as e:
            raise VoiceUnavailable(f"speech-to-text failed: {type(e).__name__}") from e
        secs = round(time.monotonic() - t0, 2)
        if r.status_code != 200:
            self._log({"kind": "stt", "status": r.status_code, "seconds": secs})
            raise self._error(r, "speech-to-text")
        try:
            body = r.json()
        except ValueError as e:
            raise VoiceUnavailable("speech-to-text returned an unreadable response") from e
        text = " ".join(str(body.get("transcript") or "").split())
        self._log({"kind": "stt", "status": 200, "model": model, "bytes": len(audio), "seconds": secs,
                   "request_id": body.get("request_id"), "language_code": body.get("language_code")})
        if not text:
            raise VoiceUnavailable("no speech recognised", "no_speech")
        return Transcript(text, body.get("language_code"), body.get("request_id"), secs)

    # ---------- text to speech ----------
    def tts(self, text: str, lang: str = "mr") -> Path:
        """MP3 of `text` (cached). Raises VoiceUnavailable on any problem."""
        model = setting("KAARAN_TTS_MODEL")
        speaker = setting(f"KAARAN_TTS_SPEAKER_{lang.upper()}")
        if not model or not speaker:
            raise VoiceUnavailable(f"KAARAN_TTS_MODEL / KAARAN_TTS_SPEAKER_{lang.upper()} not set")
        text = " ".join(text.translate(DEVANAGARI_TO_ASCII).split())
        if not text:
            raise VoiceUnavailable("nothing to say")
        if len(text) > MAX_TTS_CHARS:
            raise VoiceUnavailable(f"text too long for one request ({len(text)} > {MAX_TTS_CHARS} characters)")
        key = hashlib.sha256(json.dumps([model, speaker, lang, text], ensure_ascii=False).encode()).hexdigest()
        out = self.cache_dir / f"{key}.mp3"
        headers = self._headers() | {"Content-Type": "application/json"}  # voice off means off, even for cached audio
        if out.exists() and out.stat().st_size > 0:
            return out
        self._charge(len(text) / 1000 * TTS_INR_PER_1000_CHARS)
        body = {"text": text, "language_code": LANG_CODE.get(lang, "mr-IN"), "model": model, "speaker": speaker,
                "pace": float(setting("KAARAN_TTS_PACE", "1.0")), "speech_sample_rate": 24000, "output_audio_codec": "mp3"}
        t0 = time.monotonic()
        try:
            r = self.http.post(f"{BASE_URL}/text-to-speech", headers=headers, json=body)
        except httpx.HTTPError as e:
            raise VoiceUnavailable(f"text-to-speech failed: {type(e).__name__}") from e
        secs = round(time.monotonic() - t0, 2)
        if r.status_code != 200:
            self._log({"kind": "tts", "status": r.status_code, "seconds": secs})
            raise self._error(r, "text-to-speech")
        try:
            data = r.json()
            audio = base64.b64decode("".join(data.get("audios") or []))
        except (ValueError, TypeError) as e:
            raise VoiceUnavailable("text-to-speech returned unreadable audio") from e
        if not audio:
            raise VoiceUnavailable("text-to-speech returned no audio")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")  # no clash between concurrent writers
        tmp.write_bytes(audio)
        tmp.replace(out)
        self._log({"kind": "tts", "status": 200, "model": model, "speaker": speaker, "chars": len(text), "seconds": secs,
                   "request_id": data.get("request_id"), "est_cost_inr": round(len(text) / 1000 * 1.0, 3)})
        return out


_client: SarvamClient | None = None


def get_voice() -> SarvamClient:
    global _client
    if _client is None:
        _client = SarvamClient()
    return _client


def reset_voice(client: SarvamClient | None = None) -> None:
    global _client
    _client = client
