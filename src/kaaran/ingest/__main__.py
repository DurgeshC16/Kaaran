"""CLI: python -m kaaran.ingest data/synthetic/demo/raw --db data/synthetic/demo/kaaran.duckdb"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .mapping import propose
from .pipeline import IngestError, ingest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m kaaran.ingest", description="Ingest raw files into DuckDB (no LLM).")
    p.add_argument("raw_dir")
    p.add_argument("--db", help="DuckDB file to write (default: <raw_dir>/../kaaran.duckdb)")
    p.add_argument("--mapping", help="mapping JSON to apply (default: rule-based proposal)")
    p.add_argument("--write-mapping", help="write the rule-based mapping proposal to this file and exit")
    args = p.parse_args(argv)
    raw = Path(args.raw_dir)
    if args.write_mapping:
        Path(args.write_mapping).write_text(json.dumps(propose(raw), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"mapping proposal written to {args.write_mapping}")
        return 0
    mapping = json.loads(Path(args.mapping).read_text(encoding="utf-8")) if args.mapping else None
    db = Path(args.db) if args.db else raw.parent / "kaaran.duckdb"
    try:
        result = ingest(raw, db, mapping)
    except IngestError as e:
        print("mapping invalid:", json.dumps(e.errors, ensure_ascii=False, indent=1))
        return 2
    report_path = db.with_name("ingest_report.json")
    report_path.write_text(json.dumps(result.report, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print(f"{'SYNTHETIC ' if result.report['synthetic'] else ''}data ingested into {db}")
    for name, n in result.report["tables"].items():
        print(f"  {name:14s} {n:>7,d} rows")
    print(f"  fixes applied: {len(result.report['fixes'])} kinds; unresolved rows: {result.report['unresolved_rows']}")
    print(f"  report: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
