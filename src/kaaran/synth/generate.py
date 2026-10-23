"""Orchestrates generation: clean truth tables -> self-check -> files."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from . import SYNTHETIC_MARKER
from . import config as C
from . import ground_truth
from .entities import build_schools, build_talukas
from .plant import Planted, draw_school_effects, select
from .tables import (
    build_attendance,
    build_election_duty,
    build_scores,
    build_teacher_posts,
    enforce_infra_independence,
    focus_infra_r,
)

CLEAN_TABLES = ("talukas", "schools", "scores", "attendance", "teacher_posts", "election_duty")


def build_clean(seed: int, names: str) -> tuple[dict[str, pd.DataFrame], Planted]:
    talukas = build_talukas(names)
    schools = build_schools(seed, names)
    effects = draw_school_effects(schools, seed)
    planted = select(schools, effects, seed)
    scores = build_scores(schools, effects, planted, seed)
    schools = enforce_infra_independence(schools, scores, seed)
    clean = {
        "talukas": talukas,
        "schools": schools.drop(columns="infra_quality"),
        "scores": scores,
        "attendance": build_attendance(schools, planted, seed),
        "teacher_posts": build_teacher_posts(schools, planted, seed),
        "election_duty": build_election_duty(talukas, seed),
    }
    self_check(clean, planted)
    return clean, planted


def self_check(clean: dict[str, pd.DataFrame], planted: Planted) -> None:
    """Fail loudly if the generated tables miss the planted targets (tests re-verify independently)."""
    problems = []
    s = clean["scores"].merge(clean["schools"][["udise_code", "taluka_key"]], on="udise_code")
    means = s.groupby(["taluka_key", "academic_year"])["mean_score"].mean()
    for t in C.TALUKAS:
        for y, target in zip(C.YEARS, t.scores):
            if abs(means[(t.key, y)] - target) > 0.05:
                problems.append(f"{t.key} {y}: mean {means[(t.key, y)]:.3f} vs target {target:.3f}")
    vac = s[s["udise_code"].isin(planted.vacancy_focus)].groupby("academic_year")["mean_score"].mean()
    drop = vac[C.YEARS[0]] - vac[C.YEARS[-1]]
    if not 20 <= drop <= 30:
        problems.append(f"vacancy group drop {drop:.2f} outside 20-30")
    r = focus_infra_r(clean["schools"], clean["scores"])
    if abs(r) >= 0.1:
        problems.append(f"focus infra/change r = {r:.3f}")
    if problems:
        raise AssertionError("planted targets missed:\n" + "\n".join(problems))


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    table = pa.Table.from_pandas(df, preserve_index=False)
    meta = dict(table.schema.metadata or {})
    meta[b"synthetic"] = b"true"
    meta[b"marker"] = SYNTHETIC_MARKER.encode()
    pq.write_table(table.replace_schema_metadata(meta), path)


def write_json(obj: dict, path: Path) -> None:
    text = json.dumps(ground_truth.to_jsonable(obj), ensure_ascii=False, indent=2) + "\n"
    path.write_bytes(text.encode("utf-8"))


def generate(seed: int = 42, out: str | Path = "data/synthetic/demo", names: str = C.TALUKA_NAMES) -> dict:
    out = Path(out)
    clean, planted = build_clean(seed, names)
    clean_dir = out / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)
    for key in CLEAN_TABLES:
        write_parquet(clean[key], clean_dir / f"{key}.parquet")
    truth = ground_truth.build(seed, names, clean, planted)
    write_json(truth, out / "ground_truth.json")
    return {"out": str(out), "rows": {k: len(v) for k, v in clean.items()}}
