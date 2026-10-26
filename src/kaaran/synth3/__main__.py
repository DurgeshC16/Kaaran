"""python -m kaaran.synth3 --seed 42 --out data/synthetic/block_demo [--names fictional]"""

from __future__ import annotations

import argparse
import sys

from .generate import generate


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m kaaran.synth3", description="v3 synthetic district (block lens, real formats).")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", default="data/synthetic/block_demo")
    p.add_argument("--names", choices=["solapur", "fictional"], default="solapur")
    args = p.parse_args(argv)
    manifest = generate(args.seed, args.out, args.names)
    print(f"SYNTHETIC v3 district (seed {args.seed}) -> {args.out}: {len(manifest['raw_files'])} raw files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
