"""CLI: python -m kaaran.trust --db data/synthetic/demo/kaaran.duckdb"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb

from .run import as_pack, run_trust

TABLES = ("talukas", "schools", "scores", "attendance", "teacher_posts", "election_duty")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m kaaran.trust", description="Run trust checks on an ingested DuckDB (no LLM).")
    p.add_argument("--db", required=True)
    args = p.parse_args(argv)
    db = Path(args.db)
    con = duckdb.connect(str(db))
    try:
        tables = {t: con.execute(f"SELECT * FROM {t}").df() for t in TABLES}
        report_path = db.with_name("ingest_report.json")
        ingest_report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {
            "sources": con.execute("SELECT * FROM sources").df().to_dict("records")}
        result = run_trust(tables, ingest_report)
        for name, df in (("trust_flags", result.flags), ("trust_missing", result.missing), ("trust_annotations", result.annotations)):
            con.register("_frame", df)
            con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM _frame")
            con.unregister("_frame")
    finally:
        con.close()
    out = db.with_name("trust_report.json")
    out.write_text(json.dumps(result.report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    db.with_name("trust_evidence.json").write_text(
        json.dumps(as_pack(result.fragment, ingest_report), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    names = dict(zip(tables["talukas"]["taluka_id"], tables["talukas"]["taluka"]))
    print("Trust checks (SYNTHETIC data)" if ingest_report.get("synthetic", True) else "Trust checks")
    print(f"  flagged schools: {result.report['flagged_schools']}  by rule: {result.report['flags_by_rule']}")
    print(f"  RED_FLAG talukas: {[names[t] for t in result.report['red_flag_talukas']]}")
    print(f"  INSUFFICIENT talukas: {[names[t] for t in result.report['insufficient_talukas']]}")
    print(f"  cleared low-attendance schools: {result.report['cleared_schools']}")
    print(f"  report: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
