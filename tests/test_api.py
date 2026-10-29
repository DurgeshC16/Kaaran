"""Phase 4: FastAPI app (web demo endpoints, WhatsApp webhook and simulator) through the TestClient."""

from __future__ import annotations

import hashlib
import hmac
import json
import re

import pytest
from fastapi.testclient import TestClient

from kaaran.api import create_app
from kaaran.brief.pdf import find_browser
from kaaran.whatsapp import CloudConfig, Gateway

from test_whatsapp import FakeAPI, payload

CFG = CloudConfig("TOKEN", "PNID", "verify-me", "app-secret", "v26.0")


@pytest.fixture
def client(demo_service):
    api = FakeAPI()
    app = create_app(demo_service, Gateway(demo_service, CFG, api), warm=False)
    with TestClient(app) as c:
        c.fake_api = api
        yield c


def test_pages_and_health(client):
    for path in ("/", "/whatsapp"):
        r = client.get(path)
        assert r.status_code == 200 and "text/html" in r.headers["content-type"] and "SYNTHETIC" in r.text
    h = client.get("/healthz").json()
    assert h["ok"] and h["llm_mode"] == "replay" and h["default_dataset"] == "demo"
    assert h["whatsapp"] == {"send": True, "verify_token": True, "app_secret": True, "graph_version": "v26.0"}


def test_datasets_and_examples(client):
    ex = client.get("/api/datasets/demo/examples").json()
    assert len(ex) == 7
    ds = client.get("/api/datasets").json()
    assert ds[0]["id"] == "demo" and ds[0]["default"] and ds[0]["examples"] == ex
    assert client.get("/api/datasets/nope/examples").status_code == 404


def test_ask_and_drill_down(client):
    a = client.post("/api/ask", json={"question": "Why did maths scores fall in Pandharpur?"}).json()
    assert a["status"] == "ok" and a["brief_id"] == "demo.T08" and a["info"]["verified"]
    nums = re.findall(r'data-n="([^"]+)"', a["html"]["mr"])
    sets = re.findall(r'data-s="([^"]+)"', a["html"]["mr"])
    assert nums and sets
    n = client.get("/api/briefs/demo.T08/number", params={"id": nums[0]}).json()
    assert n["display"]["mr"] and n["provenance"]
    s = client.get("/api/briefs/demo.T08/set", params={"id": sets[0]}).json()
    assert s["size"] == len(s["members"]) > 0
    ev = client.get("/api/briefs/demo.T08/evidence")
    assert ev.status_code == 200 and ev.json()["synthetic"] is True and "attachment" in ev.headers["content-disposition"]
    pr = client.get("/api/briefs/demo.T08/print", params={"lang": "en"})
    assert pr.status_code == 200 and "Evidence Brief" in pr.text


def test_ask_errors(client):
    assert client.post("/api/ask", json={"question": ""}).status_code == 422
    assert client.post("/api/ask", json={"question": "x", "dataset": "zzz"}).status_code == 404
    assert client.get("/api/briefs/demo.T99/evidence").status_code == 404
    assert client.get("/api/briefs/zzz.T08/evidence").status_code == 404
    assert client.get("/api/briefs/demo.T08/number", params={"id": "n.nope"}).status_code == 404
    assert client.get("/api/briefs/demo.T08/set", params={"id": "set.nope"}).status_code == 404
    assert client.get("/api/briefs/demo.T08/pdf", params={"lang": "fr"}).status_code == 400
    r = client.post("/api/ask", json={"question": "Name the worst teachers in Pandharpur"}).json()
    assert r["status"] == "refuse" and r["brief_id"] is None


def test_webhook_verification(client):
    ok = client.get("/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "777"})
    assert ok.status_code == 200 and ok.text == "777"
    bad = client.get("/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "777"})
    assert bad.status_code == 403


def test_webhook_requires_signature_and_dedupes(client, monkeypatch, tmp_path):
    from kaaran.service import Workspace

    stub = tmp_path / "b.pdf"
    stub.write_bytes(b"%PDF-1.4 stub")
    monkeypatch.setattr(Workspace, "pdf", lambda self, focus, lang: stub)
    raw = json.dumps(payload(mid="wamid.api1"), ensure_ascii=False).encode("utf-8")
    sig = "sha256=" + hmac.new(b"app-secret", raw, hashlib.sha256).hexdigest()
    headers = {"Content-Type": "application/json"}
    assert client.post("/whatsapp/webhook", content=raw, headers=headers).status_code == 403
    assert client.post("/whatsapp/webhook", content=raw, headers=headers | {"X-Hub-Signature-256": "sha256=00"}).status_code == 403
    assert client.post("/whatsapp/webhook", content=raw, headers=headers | {"X-Hub-Signature-256": sig}).json() == {"ok": True}
    sent = list(client.fake_api.sent)
    assert [r.kind for _, r in sent][-1] == "document"  # background task ran after the response
    client.post("/whatsapp/webhook", content=raw, headers=headers | {"X-Hub-Signature-256": sig})
    assert client.fake_api.sent == sent  # retry of the same message id: nothing sent again
    events = client.get("/api/whatsapp/status").json()["events"]
    assert any(e.get("status") == "rejected" for e in events)
    bad_json = b"not json"
    bad_sig = "sha256=" + hmac.new(b"app-secret", bad_json, hashlib.sha256).hexdigest()
    assert client.post("/whatsapp/webhook", content=bad_json, headers=headers | {"X-Hub-Signature-256": bad_sig}).status_code == 400


def test_simulator(client, monkeypatch, tmp_path):
    from kaaran.service import Workspace

    stub = tmp_path / "b.pdf"
    stub.write_bytes(b"%PDF-1.4 stub")
    monkeypatch.setattr(Workspace, "pdf", lambda self, focus, lang: stub)
    hi = client.post("/api/whatsapp/simulate", json={"sender": "t", "text": "hi"}).json()["replies"]
    assert len(hi) == 1 and "Kaaran" in hi[0]["text"]  # an English greeting gets the English help
    r = client.post("/api/whatsapp/simulate", json={"sender": "t", "text": "पंढरपूरचा गणिताचा निकाल का घसरला?"}).json()["replies"]
    assert r[-1]["kind"] == "document" and r[-1]["url"] == "/api/briefs/demo.T08/pdf?lang=mr"
    assert client.fake_api.sent == []  # the simulator never calls the Cloud API


@pytest.mark.slow
def test_pdf_download(client):
    if find_browser() is None:
        pytest.skip("no Edge/Chrome/Chromium for PDF")
    client.post("/api/ask", json={"question": "Why did maths scores fall in Pandharpur?"})
    r = client.get("/api/briefs/demo.T08/pdf", params={"lang": "mr"})
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")
    assert "Kaaran_Pandharpur_mr.pdf" in r.headers["content-disposition"]
