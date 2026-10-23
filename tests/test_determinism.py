"""Same seed -> byte-identical files; different seed -> different data."""

from __future__ import annotations

import json
import os
import subprocess
import sys

from kaaran.synth.generate import generate


def file_hashes(out) -> dict[str, str]:
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    return {rel: entry["sha256"] for rel, entry in manifest["files"].items()}


def test_same_seed_gives_identical_hashes(demo_dir, tmp_path):
    seed = json.loads((demo_dir / "manifest.json").read_text(encoding="utf-8"))["seed"]
    # Fresh process with a different hash seed, so set/dict ordering cannot leak into the output.
    env = {**os.environ, "PYTHONHASHSEED": "12345"}
    subprocess.run(
        [sys.executable, "-m", "kaaran.synth", "--seed", str(seed), "--out", str(tmp_path)],
        check=True, env=env, capture_output=True,
    )
    first, second = file_hashes(demo_dir), file_hashes(tmp_path)
    assert len(first) == 13  # 6 clean tables, 6 raw files, ground truth
    assert first == second
    assert (demo_dir / "manifest.json").read_bytes() == (tmp_path / "manifest.json").read_bytes()


def test_different_seed_gives_different_data(demo_dir, tmp_path):
    seed = json.loads((demo_dir / "manifest.json").read_text(encoding="utf-8"))["seed"]
    generate(seed=seed + 1, out=tmp_path, raw=False)
    first, other = file_hashes(demo_dir), file_hashes(tmp_path)
    random_tables = ["schools", "scores", "attendance", "teacher_posts", "election_duty"]
    for key in random_tables:
        rel = f"clean/{key}.parquet"
        assert first[rel] != other[rel], rel
    assert first["clean/talukas.parquet"] == other["clean/talukas.parquet"]  # fixed by config, not by seed
    assert first["ground_truth.json"] != other["ground_truth.json"]
