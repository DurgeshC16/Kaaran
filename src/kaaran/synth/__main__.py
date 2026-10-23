"""CLI: python -m kaaran.synth --seed 42 --out data/synthetic/demo"""

from __future__ import annotations

import argparse
import sys

from . import config as C
from .generate import generate


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m kaaran.synth", description="Generate the SYNTHETIC demo district.")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", default="data/synthetic/demo")
    p.add_argument("--names", choices=sorted(C.NAME_SETS), default=C.TALUKA_NAMES, help="taluka name set")
    p.add_argument("--clean-only", action="store_true", help="skip the messy raw files")
    args = p.parse_args(argv)
    result = generate(seed=args.seed, out=args.out, names=args.names, raw=not args.clean_only)
    print(f"SYNTHETIC data written to {result['out']} (seed {args.seed}, names {args.names})")
    for name, n in result["rows"].items():
        print(f"  {name:28s} {n:>7,d} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
