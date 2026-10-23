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
