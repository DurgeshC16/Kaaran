"""Check the deployed WhatsApp webhook before clicking "Verify and save" in Meta (docs/DEPLOY.md). Prints no secrets.

    .venv\\Scripts\\python scripts\\check_webhook.py https://durgeshc16-kaaran.hf.space

Checks: the server is up (/healthz), the WhatsApp settings are loaded (/api/whatsapp/status), Meta's GET handshake
echoes the challenge with WHATSAPP_VERIFY_TOKEN from .env (and refuses a wrong token), and a POST signed with
WHATSAPP_APP_SECRET is accepted while an unsigned one is refused. The test POST carries only a delivery status, so the
bot sends nothing to anyone.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def env() -> dict[str, str]:
    out = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k, v = s.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def main(base: str) -> int:
    e = env()
    for k in ("WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_APP_SECRET", "WHATSAPP_VERIFY_TOKEN"):
        if not e.get(k) or e[k].lower().startswith(("your", "<", "xxx")):
            print(f"WARN {k} in .env is empty or still a placeholder")
    base = base.rstrip("/")
    url = f"{base}/whatsapp/webhook"
    results = []
    with httpx.Client(timeout=60, follow_redirects=True) as c:
        h = c.get(f"{base}/healthz")
        results.append(("server up (/healthz)", h.status_code == 200))
        st = c.get(f"{base}/api/whatsapp/status").json() if h.status_code == 200 else {}
        cfg = st.get("config", st)
        results.append(("verify token loaded on the server", bool(cfg.get("verify_token"))))
        results.append(("app secret loaded on the server", bool(cfg.get("app_secret"))))
        results.append(("send settings (token + phone number id) loaded", bool(cfg.get("send"))))
        challenge = str(secrets.randbelow(10**9))
        ok = c.get(url, params={"hub.mode": "subscribe", "hub.verify_token": e.get("WHATSAPP_VERIFY_TOKEN", ""), "hub.challenge": challenge})
        results.append(("GET handshake echoes the challenge", ok.status_code == 200 and ok.text.strip() == challenge))
        bad = c.get(url, params={"hub.mode": "subscribe", "hub.verify_token": "wrong-token", "hub.challenge": challenge})
        results.append(("GET with a wrong token is refused (403)", bad.status_code == 403))
        body = json.dumps({"object": "whatsapp_business_account", "entry": [{"changes": [{"field": "messages", "value": {
            "statuses": [{"id": "check", "status": "delivered"}]}}]}]}).encode()
        secret = e.get("WHATSAPP_APP_SECRET", "")
        sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        signed = c.post(url, content=body, headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig})
        results.append(("signed POST accepted (app secret matches)", signed.status_code == 200))
        unsigned = c.post(url, content=body, headers={"Content-Type": "application/json"})
        results.append(("unsigned POST refused (403)", unsigned.status_code == 403))
    for name, passed in results:
        print(("PASS " if passed else "FAIL ") + name)
    print(f"\nCallback URL for Meta: {url}")
    return 0 if all(passed for _name, passed in results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"))
