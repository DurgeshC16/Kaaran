"""Voice (Sarvam AI) with a mocked HTTP transport: speech-to-text, text-to-speech, the spoken script, the service,
the API and the WhatsApp voice-note flow. Tests never call Sarvam or Meta."""

from __future__ import annotations

import base64
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from kaaran.voice.sarvam import SarvamClient, VoiceUnavailable
from kaaran.voice.script import MAX_CHARS, spoken_summary

MP3 = b"\xff\xf3\xc4\xc4" + b"\x00" * 64  # MP3 frame header + padding


class FakeSarvam:
    """Records requests; answers like the real API."""

    def __init__(self, transcript="पंढरपूर तालुक्यात कोणत्या केंद्रांकडे लक्ष द्यावे?", fail=None):
        self.requests, self.transcript, self.fail = [], transcript, fail

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail:
            return httpx.Response(self.fail, json={"error": {"code": "invalid_api_key_error", "message": "bad key"}})
        if request.url.path == "/speech-to-text":
            return httpx.Response(200, json={"request_id": "r1", "transcript": self.transcript, "language_code": "mr-IN"})
        if request.url.path == "/text-to-speech":
            return httpx.Response(200, json={"request_id": "r2", "audios": [base64.b64encode(MP3).decode()]})
        return httpx.Response(404)


@pytest.fixture
def fake(monkeypatch, tmp_path):
    monkeypatch.setenv("KAARAN_VOICE", "on")
    for k, v in {"KAARAN_STT_MODEL": "saaras:v4", "KAARAN_TTS_MODEL": "bulbul:v4-flash",
                 "KAARAN_TTS_SPEAKER_MR": "ritu_mr_narration", "KAARAN_TTS_SPEAKER_EN": "ritu_en_edtech"}.items():
        monkeypatch.setenv(k, v)
    handler = FakeSarvam()
    client = SarvamClient(api_key="test-key", http=httpx.Client(transport=httpx.MockTransport(handler)),
                          cache_dir=tmp_path / "vc", usage_log=tmp_path / "usage.jsonl")
    return client, handler


def test_stt_request_shape(fake):
    client, h = fake
    tr = client.stt(b"OggS-fake", "audio/ogg; codecs=opus", keyterms=["पंढरपूर", "Pandharpur", "पंढरपूर"])
    assert tr.text.startswith("पंढरपूर") and tr.language_code == "mr-IN"
    req = h.requests[0]
    assert req.url == "https://api.sarvam.ai/speech-to-text" and req.headers["api-subscription-key"] == "test-key"
    body = req.content
    assert b'name="model"' in body and b"saaras:v4" in body and b"mr-IN" in body and b'name="mode"' in body
    assert b'filename="audio.ogg"' in body
    terms = json.dumps(["पंढरपूर", "Pandharpur"], ensure_ascii=False).encode()  # de-duplicated, order kept
    assert terms in body


def test_stt_refuses_bad_input(fake):
    client, _ = fake
    with pytest.raises(VoiceUnavailable, match="unsupported"):
        client.stt(b"x", "text/plain")
    with pytest.raises(VoiceUnavailable, match="too long"):
        client.stt(b"x" * 4_000_001, "audio/webm")
    with pytest.raises(VoiceUnavailable, match="empty"):
        client.stt(b"", "audio/webm")


def test_api_errors_become_voice_unavailable(monkeypatch, tmp_path):
    monkeypatch.setenv("KAARAN_VOICE", "on")
    c = SarvamClient(api_key="k", http=httpx.Client(transport=httpx.MockTransport(FakeSarvam(fail=403))), cache_dir=tmp_path)
    with pytest.raises(VoiceUnavailable, match="403.*invalid_api_key_error"):
        c.stt(b"x", "audio/webm")
    with pytest.raises(VoiceUnavailable, match="403"):
        c.tts("नमस्कार", "mr")


def test_voice_off_switch(monkeypatch, tmp_path):
    c = SarvamClient(api_key="k", cache_dir=tmp_path)
    monkeypatch.setenv("KAARAN_VOICE", "off")
    assert not c.configured
    with pytest.raises(VoiceUnavailable, match="off"):
        c.stt(b"x", "audio/webm")
    monkeypatch.setenv("KAARAN_VOICE", "on")
    assert c.configured and not SarvamClient(api_key="", cache_dir=tmp_path).configured


def test_tts_request_digits_and_cache(fake):
    client, h = fake
    p = client.tts("घट ११.६ गुण, ७५% शाळा", "mr")
    assert p.read_bytes() == MP3 and p.suffix == ".mp3"
    sent = json.loads(h.requests[0].content)
    assert sent["text"] == "घट 11.6 गुण, 75% शाळा"  # Devanagari digits converted for the TTS engine
    assert sent["language_code"] == "mr-IN" and sent["model"] == "bulbul:v4-flash"
    assert sent["speaker"] == "ritu_mr_narration" and sent["output_audio_codec"] == "mp3"
    assert "pitch" not in sent and "loudness" not in sent  # not supported by v3 / v4-flash
    assert client.tts("घट ११.६ गुण, ७५% शाळा", "mr") == p and len(h.requests) == 1  # cached
    client.tts("Drop of 11.6 points", "en")
    assert json.loads(h.requests[1].content)["speaker"] == "ritu_en_edtech"
    with pytest.raises(VoiceUnavailable, match="too long"):
        client.tts("अ" * 2501, "mr")


def test_spoken_summary_keeps_every_part(demo_service):
    a = demo_service.ask("पंढरपूर तालुक्याचा गणिताचा निकाल का घसरला?")
    for lang in ("mr", "en"):
        s = spoken_summary(a.summary[lang], lang)
        assert len(s) <= MAX_CHARS[lang] + 200 and "(" not in s and "*" not in s
    en = spoken_summary(a.summary["en"], "en")  # taluka lens: trend, cause with its label, warning and action
    assert all(h in en for h in ("Trend.", "Probable main cause.", "Data warning.", "Suggested action."))
    assert "evidence:" in en.lower() or "cause:" in en.lower()  # the rule-based badge is spoken
    mr = spoken_summary(a.summary["mr"], "mr")
    assert all(h in mr for h in ("कल.", "संभाव्य मुख्य कारण.", "डेटा इशारा.", "सुचवलेली कृती."))
    summary = {"title": "T", "banner": "B", "notes": [], "items": [
        {"section": "attention", "text": "A1 (2024-25 ते 2025-26) 75%"}, {"section": "why", "text": "B1"},
        {"section": "action", "text": "C1"}] + [{"section": "attention", "text": "x" * 400}] * 3}
    s = spoken_summary(summary, "en")
    assert "What to do. C1." in s and "75 percent" in s and "2024-25" not in s


def test_service_ask_voice_and_summary(fake, demo_service):
    client, h = fake
    demo_service._voice = client
    try:
        a = demo_service.ask_voice(b"webm-bytes", "audio/webm;codecs=opus")
        assert a.status == "ok" and a.info["transcript"].startswith("पंढरपूर") and a.info["input"] == "voice"
        sent = h.requests[0].content
        assert "पंढरपूर".encode() in sent  # gazetteer names sent as keyterms
        mp3 = demo_service.voice_summary(a.brief_id, "mr")
        tts_text = json.loads(h.requests[-1].content)["text"]
        assert mp3.exists() and "SYNTHETIC" not in tts_text and "कृत्रिम" in tts_text  # spoken synthetic notice
    finally:
        demo_service._voice = None


def test_api_voice_endpoints(fake, demo_service):
    from kaaran.api import create_app
    from kaaran.whatsapp import CloudConfig, Gateway

    client, _ = fake
    demo_service._voice = client
    try:
        app = create_app(demo_service, Gateway(demo_service, CloudConfig(None, None, None, None)), warm=False)
        with TestClient(app) as c:
            assert c.get("/api/voice/status").json()["configured"] is True
            r = c.post("/api/voice/ask?lang=mr", content=b"webm", headers={"Content-Type": "audio/webm;codecs=opus"})
            assert r.status_code == 200 and r.json()["info"]["transcript"]
            assert c.post("/api/voice/ask", content=b"x", headers={"Content-Type": "text/plain"}).status_code == 415
            assert c.post("/api/voice/ask", content=b"", headers={"Content-Type": "audio/webm"}).status_code == 400
            big = c.post("/api/voice/ask", content=b"x" * 4_600_000, headers={"Content-Type": "audio/webm"})
            assert big.status_code == 413
            v = c.get(f"/api/briefs/{r.json()['brief_id']}/voice?lang=mr")
            assert v.status_code == 200 and v.headers["content-type"] == "audio/mpeg" and v.content == MP3
    finally:
        demo_service._voice = None


def test_api_voice_unavailable_is_503(demo_service):
    from kaaran.api import create_app
    from kaaran.whatsapp import CloudConfig, Gateway

    app = create_app(demo_service, Gateway(demo_service, CloudConfig(None, None, None, None)), warm=False)
    with TestClient(app) as c:  # voice is off in tests
        assert c.get("/api/voice/status").json()["configured"] is False
        assert c.post("/api/voice/ask", content=b"x", headers={"Content-Type": "audio/webm"}).status_code == 503
        a = c.post("/api/ask", json={"question": "Why did maths scores fall in Pandharpur?"}).json()
        assert c.get(f"/api/briefs/{a['brief_id']}/voice").status_code == 503


# ---------- WhatsApp voice notes ----------

def test_whatsapp_voice_note_flow(fake, demo_service, monkeypatch, tmp_path):
    from kaaran.service import Workspace
    from kaaran.whatsapp import HEARD, Bot, simulate_voice

    client, _ = fake
    stub = tmp_path / "b.pdf"
    stub.write_bytes(b"%PDF-1.4 stub")
    monkeypatch.setattr(Workspace, "pdf", lambda self, focus, lang: stub)
    demo_service._voice = client
    try:
        replies = simulate_voice(Bot(demo_service), "v1", b"OggS", "audio/ogg; codecs=opus")
        kinds = [r.kind for r in replies]
        assert replies[0].text == HEARD[0].format(text=client.stt(b"x", "audio/ogg").text)
        assert kinds[-2:] == ["document", "audio"] and replies[-1].path.read_bytes() == MP3
    finally:
        demo_service._voice = None


def test_whatsapp_voice_failure_message(monkeypatch, tmp_path, demo_service):
    from kaaran.whatsapp import Bot, simulate_voice

    monkeypatch.setenv("KAARAN_VOICE", "on")
    bad = SarvamClient(api_key="k", http=httpx.Client(transport=httpx.MockTransport(FakeSarvam(fail=500))), cache_dir=tmp_path)
    demo_service._voice = bad
    try:
        replies = simulate_voice(Bot(demo_service), "v2", b"OggS", "audio/ogg")
        assert len(replies) == 1 and "आवाज समजला नाही" in replies[0].text
    finally:
        demo_service._voice = None


def test_incoming_audio_payload_and_download():
    from kaaran.whatsapp import CloudAPI, CloudConfig, Reply, incoming_messages

    payload = {"object": "whatsapp_business_account", "entry": [{"changes": [{"field": "messages", "value": {
        "metadata": {"phone_number_id": "PNID"},
        "messages": [{"from": "9198", "id": "wamid.A", "type": "audio",
                      "audio": {"id": "MEDIA9", "mime_type": "audio/ogg; codecs=opus", "voice": True}}]}}]}]}
    msg = incoming_messages(payload)[0]
    assert msg["media_id"] == "MEDIA9" and msg["mime_type"].startswith("audio/ogg") and msg["text"] == ""
    seen = []

    def handler(request: httpx.Request):
        seen.append(request)
        if request.url.path.endswith("/MEDIA9"):
            return httpx.Response(200, json={"url": "https://lookaside.example/media/abc", "mime_type": "audio/ogg; codecs=opus",
                                             "file_size": "1234", "id": "MEDIA9"})
        if request.url.host == "lookaside.example":
            return httpx.Response(200, content=b"OggS-audio", headers={"content-type": "audio/ogg"})
        if request.url.path.endswith("/media"):
            return httpx.Response(200, json={"id": "UP1"})
        return httpx.Response(200, json={"messages": [{"id": "wamid.out"}]})

    api = CloudAPI(CloudConfig("TOKEN", "PNID", None, None, "v26.0"), http=httpx.Client(transport=httpx.MockTransport(handler)))
    data, mime = api.download_media("MEDIA9")
    assert data == b"OggS-audio" and mime.startswith("audio/ogg")
    assert all(r.headers["authorization"] == "Bearer TOKEN" for r in seen)
    assert seen[0].url.params["phone_number_id"] == "PNID"


def test_cloud_api_sends_mp3_audio(tmp_path):
    from kaaran.whatsapp import CloudAPI, CloudConfig, Reply

    seen = []

    def handler(request: httpx.Request):
        seen.append(request)
        if request.url.path.endswith("/media"):
            return httpx.Response(200, json={"id": "AUD1"})
        return httpx.Response(200, json={"messages": [{"id": "wamid.out"}]})

    mp3 = tmp_path / "v.mp3"
    mp3.write_bytes(MP3)
    api = CloudAPI(CloudConfig("TOKEN", "PNID", None, None, "v26.0"), http=httpx.Client(transport=httpx.MockTransport(handler)))
    api.deliver("9198", Reply("audio", "caption", mp3, "v.mp3"))
    upload, send = seen
    assert b'name="type"' in upload.content and b"audio/mpeg" in upload.content
    assert json.loads(send.content)["audio"] == {"id": "AUD1"} and json.loads(send.content)["type"] == "audio"


def test_gateway_downloads_and_answers_voice_note(fake, demo_service, monkeypatch, tmp_path):
    from kaaran.service import Workspace
    from kaaran.whatsapp import CloudConfig, Gateway

    client, _ = fake
    stub = tmp_path / "b.pdf"
    stub.write_bytes(b"%PDF-1.4 stub")
    monkeypatch.setattr(Workspace, "pdf", lambda self, focus, lang: stub)

    class Api:
        def __init__(self):
            self.sent = []

        def download_media(self, media_id):
            assert media_id == "MEDIA9"
            return b"OggS", "audio/ogg; codecs=opus"

        def deliver(self, to, reply):
            self.sent.append(reply)

    api = Api()
    demo_service._voice = client
    try:
        gw = Gateway(demo_service, CloudConfig("T", "PNID", "v", "s"), api)
        gw.process({"id": "w1", "from": "9198", "type": "audio", "text": "", "phone_number_id": "PNID",
                    "media_id": "MEDIA9", "mime_type": "audio/ogg"})
        assert [r.kind for r in api.sent][0] == "text" and api.sent[0].text.startswith("🎤")
        assert [r.kind for r in api.sent][-2:] == ["document", "audio"]
    finally:
        demo_service._voice = None


def test_whatsapp_voice_note_when_voice_is_off(demo_service):
    from kaaran.whatsapp import VOICE_OFF, Bot, simulate_voice

    replies = simulate_voice(Bot(demo_service), "v3", b"OggS", "audio/ogg")  # conftest switches voice off
    assert [r.text for r in replies] == [VOICE_OFF[0]]


def test_voice_failure_reason_is_fixed_text(monkeypatch, tmp_path, demo_service):
    from kaaran.whatsapp import VOICE_REASON, Bot, simulate_voice

    monkeypatch.setenv("KAARAN_VOICE", "on")
    bad = SarvamClient(api_key="k", http=httpx.Client(transport=httpx.MockTransport(FakeSarvam(fail=401))), cache_dir=tmp_path)
    demo_service._voice = bad
    try:
        text = simulate_voice(Bot(demo_service), "v4", b"OggS", "audio/ogg")[0].text
        assert VOICE_REASON["service"][0] in text and "bad key" not in text and "401" not in text
    finally:
        demo_service._voice = None


def test_gateway_skips_download_when_voice_is_off(demo_service):
    from kaaran.whatsapp import VOICE_OFF, CloudConfig, Gateway

    class Api:
        def __init__(self):
            self.sent = []

        def download_media(self, media_id):
            raise AssertionError("must not download when voice is off")

        def deliver(self, to, reply):
            self.sent.append(reply)

    api = Api()
    Gateway(demo_service, CloudConfig("T", "PNID", "v", "s"), api).process(
        {"id": "w9", "from": "9198", "type": "audio", "text": "", "phone_number_id": "PNID", "media_id": "M", "mime_type": "audio/ogg"})
    assert [r.text for r in api.sent] == [VOICE_OFF[0]]


def test_voice_note_sent_even_without_pdf(fake, demo_service, monkeypatch):
    from kaaran.brief.pdf import PdfUnavailable
    from kaaran.service import Workspace
    from kaaran.whatsapp import PDF_MISSING, Bot, simulate

    def no_pdf(self, focus, lang):
        raise PdfUnavailable("no browser")

    monkeypatch.setattr(Workspace, "pdf", no_pdf)
    demo_service._voice = fake[0]
    try:
        replies = simulate(Bot(demo_service), "v5", "पंढरपूर तालुक्याचा गणिताचा निकाल का घसरला?")
        assert PDF_MISSING[0] in [r.text for r in replies] and replies[-1].kind == "audio"
    finally:
        demo_service._voice = None


def test_voice_spend_cap(fake, monkeypatch):
    client, h = fake
    client.max_inr = 0.3  # one speech-to-text request (0.25 INR) fits, a second does not
    client.stt(b"OggS", "audio/ogg")
    with pytest.raises(VoiceUnavailable) as e:
        client.stt(b"OggS", "audio/ogg")
    assert e.value.reason == "cap" and len(h.requests) == 1


def test_pab_check_only_counts_maharashtra(tmp_path):
    import pandas as pd

    from kaaran.block.rubric import load_rubric
    from kaaran.real.pab import verify_pab

    rubric = load_rubric()
    cited = [r["funded_under"] for r in rubric["actions"] + rubric["brief_level"] if r.get("funded_under")]
    rows = [{"State": "Kerala", "Code": f["code"], "Page": f["page"], "Sub Activity": "x", "Sub Component": "y"} for f in cited]
    csv = tmp_path / "pab.csv"
    pd.DataFrame(rows).to_csv(csv, index=False)
    assert [c["id"] for c in verify_pab(csv)] == ["pab_state"]  # another state's rows must not verify the rubric
    pd.DataFrame([{**r, "State": "Maharashtra"} for r in rows]).to_csv(csv, index=False)
    checks = verify_pab(csv)
    assert len(checks) == len(cited) and all(c["ok"] for c in checks)
