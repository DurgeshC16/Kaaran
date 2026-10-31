"""Connect Meta's WhatsApp Business Account (WABA) to the Kaaran app so real messages reach the webhook.

    .venv\\Scripts\\python scripts\\whatsapp_setup.py              # check only
    .venv\\Scripts\\python scripts\\whatsapp_setup.py --subscribe  # also subscribe the WABA to the app

Why: Meta delivers incoming messages to an app's webhook only when (1) the app has a webhook with the `messages`
field and (2) the WABA that owns the phone number is subscribed to the app (POST /{waba-id}/subscribed_apps).
Sending works without (2), so the bot can send but never hears anything. Reads WHATSAPP_TOKEN, WHATSAPP_APP_SECRET,
WHATSAPP_PHONE_NUMBER_ID and WHATSAPP_WABA_ID (the "WhatsApp Business Account ID" on the API Setup page) from .env.
Prints no secrets.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
G = "https://graph.facebook.com/v26.0"


def env() -> dict[str, str]:
    out = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k, v = s.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--subscribe", action="store_true", help="subscribe the WABA to the app (safe to repeat)")
    p.add_argument("--waba", help="WhatsApp Business Account ID (else WHATSAPP_WABA_ID from .env)")
    args = p.parse_args(argv)
    e = env()
    tok, sec, pid = e.get("WHATSAPP_TOKEN", ""), e.get("WHATSAPP_APP_SECRET", ""), e.get("WHATSAPP_PHONE_NUMBER_ID", "")
    waba = (args.waba or e.get("WHATSAPP_WABA_ID", "")).strip()
    ok = True
    with httpx.Client(timeout=30) as c:
        d = c.get(f"{G}/debug_token", params={"input_token": tok, "access_token": tok}).json().get("data", {})
        app = d.get("app_id")
        print(f"token: valid={d.get('is_valid')} type={d.get('type')}")
        subs = c.get(f"{G}/{app}/subscriptions", params={"access_token": f"{app}|{sec}"}).json().get("data", [])
        hook = next((s for s in subs if s.get("object") == "whatsapp_business_account"), None)
        fields = [f.get("name") for f in (hook or {}).get("fields", [])]
        print(f"app webhook: {'active' if hook and hook.get('active') else 'MISSING'} url={(hook or {}).get('callback_url')} "
              f"messages_field={'messages' in fields}")
        ok &= bool(hook and hook.get("active") and "messages" in fields)
        if not waba:
            print("WABA id: not set. Copy 'WhatsApp Business Account ID' from Meta > your app > WhatsApp > API Setup and add "
                  "WHATSAPP_WABA_ID=<id> to .env (it is an id, not a secret), or pass --waba <id>.")
            return 1
        nums = c.get(f"{G}/{waba}/phone_numbers", params={"access_token": tok}).json()
        if "error" in nums:
            print("WABA phone numbers: ERROR", nums["error"].get("message", "")[:160])
            return 1
        ids = [n.get("id") for n in nums.get("data", [])]
        print(f"WABA phone numbers: {[(n.get('id'), n.get('verified_name')) for n in nums.get('data', [])]}; "
              f".env phone number id {'is' if pid in ids else 'is NOT'} one of them")
        ok &= pid in ids
        if args.subscribe:
            r = c.post(f"{G}/{waba}/subscribed_apps", params={"access_token": tok}).json()
            print("subscribe WABA to the app:", "done" if r.get("success") else r.get("error", {}).get("message", r))
        apps = c.get(f"{G}/{waba}/subscribed_apps", params={"access_token": tok}).json()
        names = [(a.get("whatsapp_business_api_data") or {}).get("id") for a in apps.get("data", [])]
        sub_ok = app in names
        print(f"WABA subscribed apps: {len(names)}; this app subscribed: {sub_ok}")
        ok &= sub_ok
    print("\nREADY: messages to the number will reach the webhook." if ok else
          "\nNOT READY: fix the items above" + ("" if args.subscribe else " (try --subscribe)") + ".")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
