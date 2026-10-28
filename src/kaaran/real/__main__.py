"""python -m kaaran.real --udise data/real/udise_2425 [--aikosh <csv>] [--benchmarks <json>] [--pab <csv>] [--out data/real/reports]

Builds the aggregate-only snapshot of REAL public data. Outputs stay in data/real/ (git-ignored).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .udise import cross_check_aikosh, load_microdata, snapshot, write_report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m kaaran.real")
    p.add_argument("--udise", default="data/real/udise_2425")
    p.add_argument("--aikosh", default=None)
    p.add_argument("--benchmarks", default=None)
    p.add_argument("--year", default="2024-25")
    p.add_argument("--pab", default=None, help="PAB line-item CSV: verify the rubric's funded_under citations")
    p.add_argument("--out", default="data/real/reports")
    args = p.parse_args(argv)
    tables = load_microdata(args.udise)
    snap = snapshot(tables, args.year)
    if args.pab and Path(args.pab).exists():
        from .pab import verify_pab

        snap.checks.extend(verify_pab(args.pab))
    if args.aikosh and Path(args.aikosh).exists():
        cross_check_aikosh(snap, args.aikosh)
    bench = json.loads(Path(args.benchmarks).read_text(encoding="utf-8")) if args.benchmarks and Path(args.benchmarks).exists() else None
    from .inputs import rationalisation

    j, m = write_report(snap, args.out, bench, rationalisation(tables))
    failed = [c for c in snap.checks if not c["ok"]]
    print(f"REAL snapshot: {snap.district} {snap.year}: {snap.totals['schools']} schools in {len(snap.blocks)} blocks -> {j}, {m}")
    print(f"checks: {len(snap.checks) - len(failed)}/{len(snap.checks)} passed" + (f" FAILED: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
