"""Phase 4: WhatsApp bot, Cloud API client (mocked transport), webhook signature/handshake, de-duplication."""

from __future__ import annotations

import hashlib
import hmac
import json
import httpx
import pytest

from kaaran.brief.pdf import PdfUnavailable
from kaaran.service import Workspace
from kaaran.whatsapp import (ACK, ERROR, PDF_MISSING, UNSUPPORTED, VOICE_OFF, Bot, CloudAPI, CloudAPIError, CloudConfig, Gateway, Reply,
                             Seen, incoming_messages, simulate, split_text, valid_signature, verify_challenge)

CFG = CloudConfig("TOKEN", "PNID", "verify-me", "app-secret", "v26.0")


def payload(text="पंढरपूरचा गणिताचा निकाल का घसरला?", mid="wamid.1", sender="919800000001", pnid="PNID", kind="text"):
    msg = {"from": sender, "id": mid, "timestamp": "1", "type": kind}
    if kind == "text":
        msg["text"] = {"body": text}
    return {"object": "whatsapp_business_account", "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"display_phone_number": "15550000000", "phone_number_id": pnid},
        "contacts": [{"profile": {"name": "Officer"}, "wa_id": sender}], "messages": [msg]}}]}]}


@pytest.fixture
def fake_pdf(monkeypatch, tmp_path):
    """Skip the browser in fast tests: the brief PDF is a stub file."""
    path = tmp_path / "brief.pdf"
    path.write_bytes(b"%PDF-1.4 stub")
    monkeypatch.setattr(Workspace, "pdf", lambda self, focus, lang: path)
    return path


# ---------- webhook primitives ----------

def test_signature():
    raw = b'{"a":1}'
    good = "sha256=" + hmac.new(b"app-secret", raw, hashlib.sha256).hexdigest()
    assert valid_signature(raw, good, "app-secret")
    assert not valid_signature(raw + b" ", good, "app-secret")
    assert not valid_signature(raw, good, "other-secret")
    assert not valid_signature(raw, None, "app-secret") and not valid_signature(raw, good, None)  # no secret: reject


def test_verification_handshake():
    assert verify_challenge("subscribe", "verify-me", "123", "verify-me") == "123"
    assert verify_challenge("subscribe", "wrong", "123", "verify-me") is None
    assert verify_challenge("subscribe", "verify-me", "123", None) is None
    assert verify_challenge("unsubscribe", "verify-me", "123", "verify-me") is None


def test_incoming_messages_parsing():
    assert incoming_messages(payload()) == [{"id": "wamid.1", "from": "919800000001", "type": "text",
                                            "text": "पंढरपूरचा गणिताचा निकाल का घसरला?", "phone_number_id": "PNID"}]
    statuses = {"object": "whatsapp_business_account", "entry": [{"changes": [{"field": "messages", "value": {
        "statuses": [{"id": "wamid.x", "status": "delivered"}]}}]}]}
    assert incoming_messages(statuses) == []
    assert incoming_messages(payload(kind="audio"))[0]["text"] == ""
    for junk in (None, [], {"object": "page"}, {"object": "whatsapp_business_account", "entry": [None, {"changes": ["x"]}]}):
        assert incoming_messages(junk) == []


def test_seen_is_bounded():
    s = Seen(size=3)
    assert s.add("a") and not s.add("a")
    for k in "bcd":
        s.add(k)
    assert s.add("a")  # evicted, so new again


def test_split_text():
    text = "\n\n".join(f"block {i} " + "x" * 900 for i in range(10))
    parts = split_text(text, limit=2000)
    assert all(len(p) <= 2000 for p in parts) and "\n\n".join(parts) == text
    assert all(len(p) <= 100 for p in split_text("y" * 450, limit=100))


# ---------- bot ----------

def run(bot, text, sender="s1", kind="text"):
    out: list[Reply] = []
    bot.handle(sender, kind, text, out.append)
    return out


def test_bot_help_language_and_non_text(demo_service):
    bot = Bot(demo_service)
    help_mr = run(bot, "नमस्कार")
    assert len(help_mr) == 1 and "कारण" in help_mr[0].text and "पंढरपूर" in help_mr[0].text
    assert run(bot, "x", kind="audio")[0].text == VOICE_OFF[0]  # conftest switches voice off
    assert run(bot, "x", kind="image")[0].text == UNSUPPORTED[0]
    assert run(bot, "English")[0].lang == "en" and bot.lang["s1"] == "en"
    assert "Hello" in run(bot, "hi")[0].text
    assert run(bot, "मराठी")[0].lang == "mr"


def test_bot_question_gives_summary_then_pdf(demo_service, fake_pdf):
    bot = Bot(demo_service)
    demo_service.workspace().briefs.pop("T08", None)
    replies = run(bot, "पंढरपूरचा गणिताचा निकाल का घसरला?")
    assert [r.kind for r in replies] == ["text", "text", "document"]
    assert replies[0].text == ACK[0]  # brief was not cached yet
    assert replies[1].text.startswith("*पुरावा अहवाल: पंढरपूर*") and "SYNTHETIC" in replies[1].text
    doc = replies[2]
    assert doc.path == fake_pdf and doc.filename == "Kaaran_Pandharpur_mr.pdf" and len(doc.text) <= 1024
    again = run(bot, "Why did maths fall in Pandharpur?")
    assert [r.kind for r in again] == ["text", "document"]  # cached: no ack


def test_bot_clarify_refuse_and_pdf_failure(demo_service, monkeypatch):
    bot = Bot(demo_service)
    assert [r.kind for r in run(bot, "निकाल का घसरला?")] == ["text"]
    assert "शिक्षक" in run(bot, "पंढरपूर मधील सर्वात वाईट शिक्षकांची नावे द्या")[0].text

    def no_pdf(self, focus, lang):
        raise PdfUnavailable("no browser")

    monkeypatch.setattr(Workspace, "pdf", no_pdf)
    replies = run(bot, "Why did maths fall in Pandharpur?")
    assert replies[-1].kind == "text" and replies[-1].text == PDF_MISSING[0]


def test_simulate_uses_the_same_bot(demo_service, fake_pdf):
    replies = simulate(Bot(demo_service), "sim", "Why did maths fall in Pandharpur?")
    assert replies[-1].kind == "document" and replies[-1].brief_id == "demo.T08"


# ---------- Cloud API client (mocked HTTP) ----------

def mock_api(handler):
    return CloudAPI(CFG, http=httpx.Client(transport=httpx.MockTransport(handler)))


def test_cloud_api_requests(tmp_path):
    seen = []

    def handler(request: httpx.Request):
        seen.append(request)
        if request.url.path.endswith("/media"):
            return httpx.Response(200, json={"id": "MEDIA1"})
        return httpx.Response(200, json={"messages": [{"id": "wamid.out"}]})

    api = mock_api(handler)
    api.send_text("9198", "नमस्कार")
    pdf = tmp_path / "b.pdf"
    pdf.write_bytes(b"%PDF-1.4 x")
    api.deliver("9198", Reply("document", "caption", pdf, "Kaaran_X_mr.pdf"))
    api.deliver("9198", Reply("document", "caption", pdf, "Kaaran_X_mr.pdf"))  # media id reused, no 2nd upload
    paths = [r.url.path for r in seen]
    assert paths == ["/v26.0/PNID/messages", "/v26.0/PNID/media", "/v26.0/PNID/messages", "/v26.0/PNID/messages"]
    assert all(r.headers["authorization"] == "Bearer TOKEN" for r in seen)
    text = json.loads(seen[0].content)
    assert text == {"messaging_product": "whatsapp", "recipient_type": "individual", "to": "9198", "type": "text",
                    "text": {"preview_url": False, "body": "नमस्कार"}}
    upload = seen[1]
    assert upload.headers["content-type"].startswith("multipart/form-data")
    body = upload.content
    assert b'name="messaging_product"' in body and b"whatsapp" in body and b'name="type"' in body
    assert b'name="file"; filename="b.pdf"' in body and b"application/pdf" in body
    doc = json.loads(seen[2].content)
    assert doc["type"] == "document" and doc["document"] == {"id": "MEDIA1", "filename": "Kaaran_X_mr.pdf", "caption": "caption"}


def test_cloud_api_errors():
    api = mock_api(lambda r: httpx.Response(400, json={"error": {"code": 131030, "message": "Recipient not in allowed list"}}))
    with pytest.raises(CloudAPIError, match="131030"):
        api.send_text("9198", "x")
    with pytest.raises(CloudAPIError, match="not set"):
        CloudAPI(CloudConfig(None, None, None, None)).send_text("9198", "x")


# ---------- gateway ----------

class FakeAPI:
    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    def deliver(self, to, reply):
        if self.fail:
            raise CloudAPIError("HTTP 401")
        self.sent.append((to, reply))


def test_gateway_dedupes_filters_and_delivers(demo_service, fake_pdf):
    api = FakeAPI()
    gw = Gateway(demo_service, CFG, api)
    msgs = gw.accept(payload())
    assert len(msgs) == 1 and gw.accept(payload()) == []  # Meta retry: same id ignored
    assert gw.accept(payload(mid="wamid.2", pnid="OTHER")) == []  # another business number
    gw.process(msgs[0])
    assert [r.kind for _, r in api.sent][-2:] == ["text", "document"] and api.sent[0][0] == "919800000001"
    assert all("919800000001" not in json.dumps(e) for e in gw.events)  # numbers are masked in the log


def test_gateway_survives_failures(demo_service, monkeypatch):
    gw = Gateway(demo_service, CFG, FakeAPI(fail=True))
    gw.process(gw.accept(payload(text="hi", mid="wamid.f1"))[0])
    assert gw.events[-1]["status"] == "failed" and "401" in gw.events[-1]["error"]

    api = FakeAPI()
    gw = Gateway(demo_service, CFG, api)
    monkeypatch.setattr(gw.bot.service, "ask", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    gw.process(gw.accept(payload(mid="wamid.f2"))[0])
    assert api.sent[-1][1].text == ERROR[0] and any(e.get("status") == "error" for e in gw.events)
