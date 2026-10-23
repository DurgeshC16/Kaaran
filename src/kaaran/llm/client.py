"""Thin, guarded wrapper around the Anthropic SDK.

- Model ids come from env (KAARAN_MODEL_MAIN / KAARAN_MODEL_LIGHT), then .env, then .env.example defaults.
- Modes (KAARAN_LLM_MODE): `live` calls the API (and records), `replay` answers only from the disk cache,
  `off` never answers. Callers catch LLMUnavailable and fall back to their deterministic baseline.
- Disk cache keyed by a hash of (model, system, user, schema, parameters): tests, evals and demos replay
  recorded responses at no cost. Each entry keeps the usage, cost and latency measured when it was recorded.
- Usage log (JSONL) with tokens, estimated cost and latency per call; a hard per-process spend cap
  (KAARAN_MAX_LIVE_USD, default 15) refuses further live calls.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CACHE_VERSION = 1
DEFAULT_MAX_LIVE_USD = 15.0
TIERS = {"main": "KAARAN_MODEL_MAIN", "light": "KAARAN_MODEL_LIGHT"}
# USD per million tokens (input, output). Cache reads 0.1x input, cache writes 1.25x input.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-fable-5-1": (10.00, 50.00),
}
UNKNOWN_MODEL_PRICE = (10.00, 50.00)  # charge unknown models at the top price: cost is never under-counted
FALLBACK_MODELS = {"claude-sonnet-5-5", "claude-opus-5-5"}  # server-side refusal fallback ("default" mode)
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMUnavailable(Exception):
    """No answer: mode off, replay miss, spend cap, refusal, missing config or API failure."""


@dataclass
class LLMResult:
    text: str
    data: dict | list | None
    model: str
    cached: bool
    usage: dict
    cost_usd: float
    latency_s: float
    stop_reason: str
    key: str
    extra: dict = field(default_factory=dict)


def _read_env_file(path: Path) -> dict[str, str]:
    out = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def setting(name: str, default: str | None = None) -> str | None:
    """Environment first, then .env, then .env.example (defaults only; secrets never live there)."""
    if os.environ.get(name):
        return os.environ[name]
    for f in (ROOT / ".env", ROOT / ".env.example"):
        v = _read_env_file(f).get(name)
        if v:
            return v
    return default


def cost_usd(model: str, usage: dict) -> float:
    pin, pout = PRICES.get(model, UNKNOWN_MODEL_PRICE)
    inp = usage.get("input_tokens", 0) or 0
    read = usage.get("cache_read_input_tokens", 0) or 0
    write = usage.get("cache_creation_input_tokens", 0) or 0
    out = usage.get("output_tokens", 0) or 0
    return round((inp * pin + read * pin * 0.1 + write * pin * 1.25 + out * pout) / 1_000_000, 6)


class LLMClient:
    def __init__(self, mode: str | None = None, cache_dir: str | Path | None = None, usage_log: str | Path | None = None,
                 max_live_usd: float | None = None, api=None):
        self.mode = (mode or setting("KAARAN_LLM_MODE", "replay")).lower()
        if self.mode not in ("live", "replay", "off"):
            raise ValueError(f"KAARAN_LLM_MODE must be live, replay or off, not {self.mode!r}")
        self.cache_dir = Path(cache_dir or setting("KAARAN_LLM_CACHE") or ROOT / "llm_cache")
        self.usage_log = Path(usage_log or setting("KAARAN_LLM_USAGE_LOG") or ROOT / "data" / "llm_usage.jsonl")
        self.max_live_usd = float(max_live_usd if max_live_usd is not None else setting("KAARAN_MAX_LIVE_USD", str(DEFAULT_MAX_LIVE_USD)))
        self.live_spend = 0.0
        self._api = api

    # ---- helpers
    def model(self, tier: str) -> str:
        name = setting(TIERS[tier])
        if not name:
            raise LLMUnavailable(f"{TIERS[tier]} is not set")
        return name

    def _api_client(self):
        if self._api is None:
            import anthropic

            if not setting("ANTHROPIC_API_KEY"):
                raise LLMUnavailable("ANTHROPIC_API_KEY is not set")
            self._api = anthropic.Anthropic(api_key=setting("ANTHROPIC_API_KEY"), timeout=120.0, max_retries=3)
        return self._api

    @staticmethod
    def cache_key(payload: dict) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

    def _log(self, rec: dict) -> None:
        self.usage_log.parent.mkdir(parents=True, exist_ok=True)
        with self.usage_log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ---- the one entry point
    def call(self, *, role: str, tier: str, system: str, user: str, schema: dict | None = None,
             max_tokens: int = 8000, effort: str = "low") -> LLMResult:
        model = self.model(tier)
        payload = {"v": CACHE_VERSION, "model": model, "system": system, "user": user, "schema": schema,
                   "max_tokens": max_tokens, "effort": effort}
        key = self.cache_key(payload)
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            entry = json.loads(path.read_text(encoding="utf-8"))
            res = LLMResult(text=entry["text"], data=entry.get("data"), model=entry["model"], cached=True, usage=entry["usage"],
                            cost_usd=entry["cost_usd"], latency_s=entry["latency_s"], stop_reason=entry["stop_reason"], key=key)
            self._log({"role": role, "model": res.model, "cached": True, "key": key, "recorded_cost_usd": res.cost_usd,
                       "recorded_latency_s": res.latency_s, "usage": res.usage, "at": _now()})
            return res
        if self.mode != "live":
            raise LLMUnavailable(f"no recorded response ({self.mode} mode) for {role}")
        if self.live_spend >= self.max_live_usd:
            raise LLMUnavailable(f"live spend cap reached (${self.live_spend:.2f} of ${self.max_live_usd:.2f})")
        worst = cost_usd(model, {"input_tokens": (len(system) + len(user)) // 2, "output_tokens": max_tokens})
        if self.live_spend + worst > self.max_live_usd:
            raise LLMUnavailable(f"call could exceed the live spend cap (worst case ${worst:.2f})")

        output_config: dict = {"effort": effort}
        if schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        kwargs = dict(model=model, max_tokens=max_tokens, system=system,
                      messages=[{"role": "user", "content": user}], output_config=output_config)
        if model in FALLBACK_MODELS:
            kwargs |= {"betas": [FALLBACK_BETA], "fallbacks": "default"}
        api = self._api_client()
        t0 = time.perf_counter()
        try:
            resp = api.beta.messages.create(**kwargs)
        except Exception as e:  # SDK already retried 408/409/429/5xx and connection errors
            self._log({"role": role, "model": model, "cached": False, "error": type(e).__name__, "at": _now()})
            raise LLMUnavailable(f"API call failed: {type(e).__name__}: {e}") from e
        latency = round(time.perf_counter() - t0, 3)
        u = resp.usage
        usage = {k: getattr(u, k, 0) or 0 for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")}
        served = getattr(resp, "model", model) or model
        cost = cost_usd(served, usage)
        self.live_spend += cost
        stop = resp.stop_reason or ""
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        self._log({"role": role, "model": served, "cached": False, "key": key, "cost_usd": cost, "latency_s": latency,
                   "usage": usage, "stop_reason": stop, "request_id": getattr(resp, "_request_id", None), "at": _now()})
        if stop == "refusal":
            raise LLMUnavailable(f"model refused ({getattr(getattr(resp, 'stop_details', None), 'category', None)})")
        data = None
        if schema is not None:
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                raise LLMUnavailable(f"response was not valid JSON (stop_reason {stop})") from e
        entry = {"key": key, "request": payload, "text": text, "data": data, "model": served, "usage": usage,
                 "cost_usd": cost, "latency_s": latency, "stop_reason": stop, "recorded_at": _now(), "synthetic_inputs": True}
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(entry, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return LLMResult(text=text, data=data, model=served, cached=False, usage=usage, cost_usd=cost, latency_s=latency,
                         stop_reason=stop, key=key)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_DEFAULT: LLMClient | None = None


def get_client() -> LLMClient:
    """Process-wide client, so the spend cap is per process (session)."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = LLMClient()
    return _DEFAULT


def reset_client(client: LLMClient | None = None) -> None:
    global _DEFAULT
    _DEFAULT = client
