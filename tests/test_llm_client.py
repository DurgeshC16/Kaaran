"""LLM wrapper: cache/replay, modes, usage log, spend cap, refusals. No network unless --live."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from kaaran.llm import LLMClient, LLMUnavailable, cost_usd
from kaaran.llm import client as C


class FakeAPI:
    """Mimics client.beta.messages.create; records the kwargs it was called with."""

    def __init__(self, text='{"ok": true}', stop="end_turn", usage=(100, 20), model=None):
        self.calls = []
        self.text, self.stop, self.usage, self.model = text, stop, usage, model
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.text)], stop_reason=self.stop, stop_details=None,
            model=self.model or kwargs["model"], _request_id="req_test",
            usage=SimpleNamespace(input_tokens=self.usage[0], output_tokens=self.usage[1],
                                  cache_read_input_tokens=0, cache_creation_input_tokens=0))


SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False}


@pytest.fixture
def models(monkeypatch):
    monkeypatch.setenv("KAARAN_MODEL_MAIN", "claude-sonnet-5-5")
    monkeypatch.setenv("KAARAN_MODEL_LIGHT", "claude-haiku-5-5")


def make(tmp_path, mode="live", api=None, cap=15.0):
    return LLMClient(mode=mode, cache_dir=tmp_path / "cache", usage_log=tmp_path / "usage.jsonl", max_live_usd=cap, api=api)


def test_live_call_records_then_replays_without_api(tmp_path, models):
    api = FakeAPI()
    live = make(tmp_path, "live", api)
    r = live.call(role="test", tier="main", system="sys", user="hello", schema=SCHEMA)
    assert r.data == {"ok": True} and not r.cached and r.cost_usd == cost_usd("claude-sonnet-5-5", {"input_tokens": 100, "output_tokens": 20})
    kwargs = api.calls[0]
    assert kwargs["output_config"]["format"]["type"] == "json_schema" and kwargs["fallbacks"] == "default"
    assert "temperature" not in kwargs
    replay = make(tmp_path, "replay", api=None)
    r2 = replay.call(role="test", tier="main", system="sys", user="hello", schema=SCHEMA)
    assert r2.cached and r2.data == {"ok": True} and r2.cost_usd == r.cost_usd  # recorded cost kept for reporting
    log = [json.loads(line) for line in (tmp_path / "usage.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [x["cached"] for x in log] == [False, True]


def test_light_tier_has_no_server_fallback(tmp_path, models):
    api = FakeAPI()
    make(tmp_path, "live", api).call(role="t", tier="light", system="s", user="u")
    assert "fallbacks" not in api.calls[0] and api.calls[0]["model"] == "claude-haiku-5-5"


def test_replay_miss_and_off_mode_raise(tmp_path, models):
    with pytest.raises(LLMUnavailable, match="no recorded response"):
        make(tmp_path, "replay").call(role="t", tier="main", system="s", user="new prompt")
    with pytest.raises(LLMUnavailable):
        make(tmp_path, "off").call(role="t", tier="main", system="s", user="x")


def test_cache_key_changes_with_any_input(tmp_path, models):
    api = FakeAPI()
    c = make(tmp_path, "live", api)
    c.call(role="t", tier="main", system="s", user="a")
    c.call(role="t", tier="main", system="s", user="a")  # cache hit, no second API call
    c.call(role="t", tier="main", system="s", user="b")
    c.call(role="t", tier="main", system="s2", user="a")
    c.call(role="t", tier="light", system="s", user="a")
    assert len(api.calls) == 4


def test_spend_cap_refuses_live_calls(tmp_path, models):
    api = FakeAPI(usage=(1000, 100_000))  # 100k output tokens on Sonnet = $1.00
    c = make(tmp_path, "live", api, cap=1.5)
    c.call(role="t", tier="main", system="s", user="one", max_tokens=1000)
    assert c.live_spend == pytest.approx(1.002)
    with pytest.raises(LLMUnavailable, match="cap"):
        c.call(role="t", tier="main", system="s", user="two", max_tokens=100_000)


def test_refusal_and_bad_json_are_unavailable(tmp_path, models):
    with pytest.raises(LLMUnavailable, match="refused"):
        make(tmp_path, "live", FakeAPI(stop="refusal")).call(role="t", tier="main", system="s", user="u")
    with pytest.raises(LLMUnavailable, match="valid JSON"):
        make(tmp_path / "b", "live", FakeAPI(text="not json")).call(role="t", tier="main", system="s", user="u", schema=SCHEMA)


def test_unknown_model_is_priced_at_the_top_rate():
    assert cost_usd("claude-new-model", {"input_tokens": 1_000_000}) == C.UNKNOWN_MODEL_PRICE[0]
    assert cost_usd("claude-haiku-5-5", {"input_tokens": 1_000_000, "output_tokens": 1_000_000}) == pytest.approx(0.60)


def test_settings_prefer_environment_over_files(monkeypatch):
    monkeypatch.setenv("KAARAN_MODEL_MAIN", "from-env")
    assert C.setting("KAARAN_MODEL_MAIN") == "from-env"
    monkeypatch.delenv("KAARAN_MODEL_MAIN")
    assert C.setting("KAARAN_MODEL_MAIN") == C._read_env_file(C.ROOT / ".env.example")["KAARAN_MODEL_MAIN"]


@pytest.mark.live
@pytest.mark.parametrize("tier", ["light", "main"])
def test_live_auth_and_model_ids(tier, tmp_path):
    """One tiny call per tier: proves auth, both model ids and structured output (run with --live)."""
    c = LLMClient(mode="live", cache_dir=tmp_path / "cache")
    r = c.call(role="auth_check", tier=tier, system="Answer with the requested JSON only.",
               user='Return {"ok": true}.', schema=SCHEMA, max_tokens=200)
    assert r.data == {"ok": True} and r.model.startswith(c.model(tier)) and r.cost_usd < 0.01
