"""Phase 6.1: cluster lens in the demo service, web API and WhatsApp bot (alerts, open from alert, baithak pack)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from kaaran.api import create_app
from kaaran.service import DatasetSpec, Service
from kaaran.whatsapp import Bot, CloudConfig, Gateway, simulate, simulate_alert


@pytest.fixture(scope="session")
def block_service(tmp_path_factory, block_folder):
    import shutil

    folder = tmp_path_factory.mktemp("blocksvc") / "data"
    shutil.copytree(block_folder, folder)  # actions.json is written next to the data: keep tests off the shared folder
    spec = DatasetSpec("blocks", 42, "solapur", str(folder), "डेमो", "Demo", "block")
    return Service({"blocks": spec}, default="blocks")


@pytest.fixture(scope="session")
def block_folder(tmp_path_factory):
    from kaaran.synth3.generate import generate

    out = tmp_path_factory.mktemp("block42svc")
    generate(42, out)
    return out


def test_scan_alerts_lead_with_the_focus_block(block_service):
    alerts = block_service.alerts()
    top = alerts[0]
    assert top["name"] == "Pandharpur" and top["at_risk"] == 3 and top["data"] == 1
    assert "केंद्रांना" in top["text"]["mr"] and "clusters need" in top["text"]["en"]
    assert all(a["at_risk"] or a["data"] for a in alerts)


def test_question_and_alert_open_the_same_brief(block_service):
    a = block_service.ask("पंढरपूर तालुक्यात कोणत्या केंद्रांकडे लक्ष द्यावे?")
    assert a.status == "ok" and a.brief_id == "blocks.BPandharpur" and a.info["verified"]
    assert a.summary["mr"]["notes"] and "लक्ष देण्याची गरज" in a.summary["mr"]["notes"][0]
    o = block_service.open_block(None, "BPandharpur")
    assert o.status == "ok" and o.info["intent_source"] == "alert" and o.html["en"] == a.html["en"]
    assert {it["section"] for it in a.summary["en"]["items"]} == {"attention", "why", "action"}
    with pytest.raises(KeyError):
        block_service.open_block(None, "BNowhere")


def test_baithak_pack_and_tracker(block_service):
    ws = block_service.workspace()
    pack = ws.baithak("BPandharpur", "en")
    acts = [x for group in pack["groups"].values() for x in group]
    assert len(acts) == 10 and {x["status"] for x in acts} == {"open"}
    assert any(x["evidence"] for x in acts) and all(x["follow_up"] for x in acts)
    ws.set_action("BPandharpur", acts[0]["id"], "confirmed")
    again = [x for g in ws.baithak("BPandharpur", "en")["groups"].values() for x in g]
    assert next(x for x in again if x["id"] == acts[0]["id"])["status"] == "confirmed"
    with pytest.raises(KeyError):
        ws.set_action("BPandharpur", "F.nope", "done")


def test_whatsapp_alert_then_report(block_service, monkeypatch, tmp_path):
    from kaaran.block.workspace import BlockWorkspace

    stub = tmp_path / "b.pdf"
    stub.write_bytes(b"%PDF-1.4 stub")
    monkeypatch.setattr(BlockWorkspace, "pdf", lambda self, focus, lang: stub)
    bot = Bot(block_service)
    alert = simulate_alert(bot, "o1")
    assert len(alert) == 1 and alert[0].text.startswith("🔔")
    replies = simulate(bot, "o1", "अहवाल")
    assert replies[-1].kind == "document" and replies[-1].brief_id == "blocks.BPandharpur"
    assert any("काय करावे" in r.text for r in replies if r.kind == "text")


def test_api_block_endpoints(block_service):
    app = create_app(block_service, Gateway(block_service, CloudConfig(None, None, None, None)), warm=False)
    with TestClient(app) as c:
        assert c.get("/api/datasets").json()[0]["kind"] == "block"
        alerts = c.get("/api/datasets/blocks/alerts").json()
        o = c.post("/api/open", json={"focus": alerts[0]["block"]}).json()
        assert o["status"] == "ok"
        bid = o["brief_id"]
        assert c.get(f"/api/briefs/{bid}/baithak").status_code == 200
        first = next(iter(c.get(f"/api/briefs/{bid}/baithak", params={"lang": "en"}).json()["groups"].values()))[0]
        assert c.post(f"/api/briefs/{bid}/actions", json={"action": first["id"], "status": "done"}).json()["status"] == "done"
        assert c.post(f"/api/briefs/{bid}/actions", json={"action": first["id"], "status": "maybe"}).status_code == 422
        assert "C · What to do" in c.get(f"/api/briefs/{bid}/print", params={"lang": "en"}).text
        assert c.post("/api/open", json={"focus": "BNowhere"}).status_code == 404
        assert c.post("/api/whatsapp/simulate_alert", json={"sender": "x"}).json()["replies"][0]["text"].startswith("🔔")
