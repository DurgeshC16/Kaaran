"""Deploy Kaaran to a Hugging Face Docker Space (docs/DEPLOY.md).

    .venv\\Scripts\\python scripts\\deploy_hf.py              # create/update the Space, set secrets, push the committed code
    .venv\\Scripts\\python scripts\\deploy_hf.py --secrets-only

Reads HF_TOKEN and HF_USER (and the app secrets) from .env / the environment. Pushes only the committed app files
(src, llm_cache, pyproject, README, Dockerfile, .env.example: no .env, no data, no docs), with a Space README front matter. Secrets go to the Space's
secret store through the Hub API, never into git. No extra dependencies (httpx is already installed).
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
HUB = "https://huggingface.co"
SPACE_NAME = "kaaran"
SECRETS = ["ANTHROPIC_API_KEY", "SARVAM_API_KEY", "WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_APP_SECRET",
           "WHATSAPP_VERIFY_TOKEN"]
VARIABLES = {"KAARAN_LLM_MODE": "live", "KAARAN_MAX_LIVE_USD": "10", "KAARAN_MAX_VOICE_INR": "500", "KAARAN_DEMO_DATASET": "blocks",
             "KAARAN_MODEL_MAIN": None, "KAARAN_MODEL_LIGHT": None}  # None = copy from .env
FRONT_MATTER = """---
title: Kaaran - data analyst for education officers
emoji: 📊
colorFrom: blue
colorTo: green
sdk: docker
app_port: 8000
pinned: true
short_description: Marathi-first AI data analyst for BEOs and DEOs (synthetic demo)
---

"""


def load_env() -> dict[str, str]:
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env | {k: v for k, v in os.environ.items() if k in env or k.startswith(("HF_", "KAARAN_", "WHATSAPP_")) or k in SECRETS}


def hub(token: str) -> httpx.Client:
    return httpx.Client(base_url=HUB, headers={"Authorization": f"Bearer {token}"}, timeout=60)


def ensure_space(c: httpx.Client, user: str) -> str:
    repo = f"{user}/{SPACE_NAME}"
    r = c.get(f"/api/spaces/{repo}")
    if r.status_code == 200:
        return repo
    r = c.post("/api/repos/create", json={"type": "space", "name": SPACE_NAME, "sdk": "docker", "private": False})
    if r.status_code not in (200, 201, 409):
        sys.exit(f"could not create the Space: HTTP {r.status_code} {r.text[:300]}")
    return repo


def set_secrets(c: httpx.Client, repo: str, env: dict[str, str]) -> None:
    for k in SECRETS:
        if env.get(k):
            r = c.post(f"/api/spaces/{repo}/secrets", json={"key": k, "value": env[k]})
            print(f"secret {k}: {'set' if r.status_code < 300 else f'HTTP {r.status_code}'}")
        else:
            print(f"secret {k}: not in .env (skipped)")
    for k, v in VARIABLES.items():
        v = v if v is not None else env.get(k)
        if v:
            r = c.post(f"/api/spaces/{repo}/variables", json={"key": k, "value": v})
            print(f"variable {k}={v}: {'set' if r.status_code < 300 else f'HTTP {r.status_code}'}")


SHIP = ["src", "llm_cache", "pyproject.toml", "README.md", "Dockerfile", ".env.example", ".dockerignore"]  # what the Space needs


def push(repo: str, user: str, token: str) -> None:
    """Clone the Space repo, replace its files with the committed app files, commit and push (no force-push)."""
    if subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, capture_output=True, text=True).stdout.strip():
        print("note: uncommitted changes are NOT deployed (only committed files from HEAD)")
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    tmp = Path(tempfile.mkdtemp(prefix="kaaran_space_"))
    url = f"https://{user}:{token}@huggingface.co/spaces/{repo}"
    try:
        r = subprocess.run(["git", "clone", "-q", url, str(tmp / "space")], capture_output=True, text=True)
        if r.returncode:
            sys.exit("clone failed: " + r.stderr.replace(token, "***")[-400:])
        space = tmp / "space"
        for child in space.iterdir():
            if child.name not in (".git", ".gitattributes"):
                shutil.rmtree(child) if child.is_dir() else child.unlink()
        data = subprocess.run(["git", "archive", "--format=tar", "HEAD", "--", *SHIP], cwd=ROOT, capture_output=True, check=True).stdout
        with tarfile.open(fileobj=io.BytesIO(data)) as tar:
            tar.extractall(space, filter="data")
        for bad in (".env", "data", "docs"):
            if (space / bad).exists():
                sys.exit(f"refusing to deploy: {bad} is in the archive")
        readme = space / "README.md"
        readme.write_text(FRONT_MATTER + readme.read_text(encoding="utf-8"), encoding="utf-8")
        run = lambda *a: subprocess.run(["git", *a], cwd=space, check=True, capture_output=True, text=True)  # noqa: E731
        run("config", "user.email", "deploy@kaaran.local")
        run("config", "user.name", "kaaran-deploy")
        run("add", "-A")
        if not subprocess.run(["git", "status", "--porcelain"], cwd=space, capture_output=True, text=True).stdout.strip():
            print("Space already up to date")
            return
        run("commit", "-q", "-m", f"deploy {head}")
        r = subprocess.run(["git", "push", "-q", "origin", "HEAD"], cwd=space, capture_output=True, text=True)
        if r.returncode:
            sys.exit("push failed: " + r.stderr.replace(token, "***")[-600:])
        print(f"pushed {head} -> https://huggingface.co/spaces/{repo}  (app: https://{user.lower()}-{SPACE_NAME}.hf.space)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--secrets-only", action="store_true")
    args = p.parse_args(argv)
    env = load_env()
    token, user = env.get("HF_TOKEN"), env.get("HF_USER")
    if not token or not user:
        sys.exit("HF_TOKEN and HF_USER must be set in .env (docs/DEPLOY.md)")
    with hub(token) as c:
        who = c.get("/api/whoami-v2")
        if who.status_code != 200:
            sys.exit(f"HF token rejected: HTTP {who.status_code}")
        repo = ensure_space(c, user)
        set_secrets(c, repo, env)
    if not args.secrets_only:
        push(repo, user, token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
