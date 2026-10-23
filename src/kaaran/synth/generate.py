"""Orchestrates generation: clean truth tables -> self-check -> raw files -> manifest."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import platform
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from . import GENERATOR_VERSION, SYNTHETIC_MARKER
from . import config as C
from . import ground_truth
from .entities import build_schools, build_talukas
from .messy import FILES as RAW_FILES
from .messy import write_raw
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


def config_hash() -> str:
    values = {k: v for k, v in vars(C).items() if k.isupper()}
    values["TALUKAS"] = [dataclasses.asdict(t) for t in C.TALUKAS]
    values.pop("TALUKA_BY_KEY")
    return hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def library_versions() -> dict[str, str]:
    import numpy, openpyxl, pdfplumber, reportlab  # noqa: E401

    return {
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "pandas": pd.__version__,
        "pyarrow": pa.__version__,
        "openpyxl": openpyxl.__version__,
        "reportlab": reportlab.Version,
        "pdfplumber": pdfplumber.__version__,
    }


def build_manifest(out: Path, seed: int, names: str, rows: dict[str, int], files: list[str]) -> dict:
    entries = {}
    for rel in files:
        data = (out / rel).read_bytes()
        entries[rel] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "rows": rows.get(rel)}
    return {
        "synthetic": True,
        "marker": SYNTHETIC_MARKER,
        "district": C.DISTRICT_NAME,
        "generator": "kaaran.synth",
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "taluka_name_set": names,
        "config_sha256": config_hash(),
        "library_versions": library_versions(),
        "files": entries,
    }


def generate(
    seed: int = 42, out: str | Path = "data/synthetic/demo", names: str = C.TALUKA_NAMES, raw: bool = True,
    layout: str = "default",
) -> dict:
    out = Path(out)
    clean, planted = build_clean(seed, names)
    clean_dir = out / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)
    rows, files = {}, []
    for key in CLEAN_TABLES:
        rel = f"clean/{key}.parquet"
        write_parquet(clean[key], out / rel)
        rows[rel], files = len(clean[key]), files + [rel]
    truth = ground_truth.build(seed, names, clean, planted)
    if raw:
        truth["messiness"], raw_rows, truth["layout"] = write_raw(clean, planted, out / "raw", seed, names, layout)
        for name in RAW_FILES:
            rows[f"raw/{name}"] = raw_rows[name]
            files.append(f"raw/{name}")
    write_json(truth, out / "ground_truth.json")
    files.append("ground_truth.json")
    manifest = build_manifest(out, seed, names, rows, files)
    manifest["layout"] = layout
    write_json(manifest, out / "manifest.json")
    return {"out": str(out), "rows": rows, "manifest": manifest}
