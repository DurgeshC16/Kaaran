"""Shared fixtures. Data is generated once per test session into a temp folder.

Tests read the generated files with plain pandas/pyarrow; they never call Kaaran engines.
Set KAARAN_TEST_SEED to run the suite against another seed (default 42).
"""

from __future__ import annotations

import json
import os

import pandas as pd
import pytest

from kaaran.synth.generate import CLEAN_TABLES, generate

YEARS = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]
FIRST, LAST = YEARS[0], YEARS[-1]
SCHOOL_MONTHS = [6, 7, 8, 9, 10, 11, 12, 1, 2, 3]


def all_months() -> list[str]:
    """Every school month of the panel in order, as 'YYYY-MM'."""
    out = []
    for y in YEARS:
        start = int(y[:4])
        out += [f"{start if m >= 6 else start + 1}-{m:02d}" for m in SCHOOL_MONTHS]
    return out


@pytest.fixture(scope="session")
def demo_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("demo")
    generate(seed=int(os.environ.get("KAARAN_TEST_SEED", "42")), out=out)
    return out


@pytest.fixture(scope="session")
def clean(demo_dir) -> dict[str, pd.DataFrame]:
    return {k: pd.read_parquet(demo_dir / "clean" / f"{k}.parquet") for k in CLEAN_TABLES}


@pytest.fixture(scope="session")
def gt(demo_dir) -> dict:
    return json.loads((demo_dir / "ground_truth.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def truths(gt) -> dict[str, dict]:
    return {t["id"]: t for t in gt["truths"]}


@pytest.fixture(scope="session")
def scores(clean) -> pd.DataFrame:
    """School scores with taluka name attached."""
    return clean["scores"].merge(clean["schools"][["udise_code", "taluka"]], on="udise_code")


@pytest.fixture(scope="session")
def taluka_scores(scores) -> pd.DataFrame:
    """Taluka x year table: unweighted mean of school means (the spec's metric)."""
    return scores.groupby(["taluka", "academic_year"])["mean_score"].mean().unstack()


@pytest.fixture(scope="session")
def school_wide(scores) -> pd.DataFrame:
    return scores.pivot(index="udise_code", columns="academic_year", values="mean_score")


# ---------- multi-seed datasets and ingest results (shared by ingest and trust tests) ----------
# Seed 42 runs in the fast suite; the extra seeds (one with the fictional name set) are marked slow.
EXTRA_SEEDS = [(7, "fictional"), (2026, "solapur")]


@pytest.fixture(scope="session")
def dataset(tmp_path_factory, demo_dir):
    """Factory: (seed, names) -> generated data folder (raw/, clean/, ground_truth.json)."""
    cache = {}

    def get(seed: int = 42, names: str = "solapur"):
        if (seed, names) == (int(os.environ.get("KAARAN_TEST_SEED", "42")), "solapur"):
            return demo_dir
        if (seed, names) not in cache:
            out = tmp_path_factory.mktemp(f"data_{seed}_{names}")
            generate(seed=seed, out=out, names=names)
            cache[(seed, names)] = out
        return cache[(seed, names)]

    return get


@pytest.fixture(scope="session")
def ingested(dataset, tmp_path_factory):
    """Factory: (seed, names) -> (data folder, IngestResult) with the DuckDB file written."""
    from kaaran.ingest import ingest

    cache = {}

    def get(seed: int = 42, names: str = "solapur"):
        if (seed, names) not in cache:
            folder = dataset(seed, names)
            db = tmp_path_factory.mktemp(f"db_{seed}_{names}") / "kaaran.duckdb"
            cache[(seed, names)] = (folder, ingest(folder / "raw", db))
        return cache[(seed, names)]

    return get


def load_clean(folder) -> dict[str, pd.DataFrame]:
    return {k: pd.read_parquet(folder / "clean" / f"{k}.parquet") for k in CLEAN_TABLES}


def load_truth(folder) -> dict:
    return json.loads((folder / "ground_truth.json").read_text(encoding="utf-8"))


# ---------- LLM: tests never call the API unless run with --live ----------


def pytest_addoption(parser):
    parser.addoption("--live", action="store_true", default=False, help="run tests that call the Anthropic API (costs money)")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--live"):
        return
    skip = pytest.mark.skip(reason="calls the Anthropic API; run with --live")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _llm_replay_mode(request, monkeypatch, tmp_path):
    """Default: replay recorded responses only (no network); usage goes to a throwaway log."""
    from kaaran.llm import reset_client

    live = request.config.getoption("--live") and "live" in request.keywords
    monkeypatch.setenv("KAARAN_LLM_MODE", "live" if live else "replay")
    if not live:
        monkeypatch.setenv("KAARAN_LLM_USAGE_LOG", str(tmp_path / "llm_usage.jsonl"))
    reset_client(None)
    yield
    reset_client(None)


# ---------- demo service (web + WhatsApp) over the session's seed-42 data ----------


@pytest.fixture(scope="session")
def demo_service(demo_dir):
    """Service over the generated seed-42 folder (PDFs and caches go to the temp folder, never the repo)."""
    from kaaran.service import DatasetSpec, Service

    spec = DatasetSpec("demo", 42, "solapur", str(demo_dir), "डेमो", "Demo")
    return Service({"demo": spec}, default="demo")


@pytest.fixture(scope="session")
def block_service_folder(tmp_path_factory):
    from kaaran.synth3.generate import generate

    out = tmp_path_factory.mktemp("block42svc")
    generate(42, out)
    return out


@pytest.fixture(scope="session")
def block_service(tmp_path_factory, block_service_folder):
    """Block-lens Service over seed-42 v3 data (a copy: actions.json is written next to the data)."""
    import shutil

    from kaaran.service import DatasetSpec, Service

    folder = tmp_path_factory.mktemp("blocksvc") / "data"
    shutil.copytree(block_service_folder, folder)
    spec = DatasetSpec("blocks", 42, "solapur", str(folder), "डेमो", "Demo", "block")
    return Service({"blocks": spec}, default="blocks")


@pytest.fixture(autouse=True)
def _voice_off(monkeypatch, tmp_path):
    """Tests never call Sarvam: voice is off unless a test injects a fake client."""
    from kaaran.voice.sarvam import reset_voice

    monkeypatch.setenv("KAARAN_VOICE", "off")
    monkeypatch.setenv("KAARAN_VOICE_CACHE", str(tmp_path / "voice_cache"))
    monkeypatch.setenv("KAARAN_VOICE_USAGE_LOG", str(tmp_path / "voice_usage.jsonl"))
    reset_voice(None)
    yield
    reset_voice(None)
