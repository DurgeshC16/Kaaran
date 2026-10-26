"""v3 generator entry point: world -> raw files (real formats) + clean parquet + truth3.json + manifest.

CLI: python -m kaaran.synth3 --seed 42 --out data/synthetic/block_demo [--names fictional]
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..synth import config as V2
from . import SYNTHETIC_MARKER
from .truth import build_truth
from .world import build_world
from .writers import write_raw


def generate(seed: int = 42, out: str | Path = "data/synthetic/block_demo", names: str = V2.TALUKA_NAMES) -> dict:
    out = Path(out)
    world = build_world(seed, names)
    messy = write_raw(world, out / "raw")
    clean = out / "clean"
    clean.mkdir(parents=True, exist_ok=True)
    for name, frame in world.tables().items():
        frame.to_parquet(clean / f"{name}.parquet", index=False)
    truth = build_truth(world, messy)
    (out / "truth3.json").write_text(json.dumps(truth, ensure_ascii=False, indent=1), encoding="utf-8")
    files = sorted(p for p in (out / "raw").iterdir())
    manifest = {"marker": SYNTHETIC_MARKER, "generator": "kaaran.synth3", "seed": seed, "names": names,
                "raw_files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest
