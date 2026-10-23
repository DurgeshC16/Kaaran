"""Intent-parser eval: accuracy on tests/fixtures/intent_questions.json, LIGHT vs MAIN vs the rule-based fallback.

Correct = status and taluka_id (and compare_with when expected) match. Reason and question type are reported
separately because they are softer judgements.

CLI: python -m kaaran.eval.intent [--tier light --tier main --tier rule]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

from ..llm.intent import gazetteer, parse, rule_plan

FIXTURE = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "intent_questions.json"


def seed42_talukas() -> tuple[pd.DataFrame, list[str]]:
    from ..synth.generate import generate

    with tempfile.TemporaryDirectory() as d:
        generate(seed=42, out=d, raw=False)
        t = pd.read_parquet(Path(d) / "clean" / "talukas.parquet")
        years = sorted(set(pd.read_parquet(Path(d) / "clean" / "scores.parquet")["academic_year"]))
    t = t.assign(taluka_id="T" + t["block_code"])[["taluka_id", "block_code", "taluka", "taluka_mr", "n_schools"]]
    return t, years


def run(tier: str, questions: list[dict] | None = None, talukas=None, years=None) -> dict:
    if talukas is None:
        talukas, years = seed42_talukas()
    questions = questions or json.loads(FIXTURE.read_text(encoding="utf-8"))["questions"]
    rows, cost, latency = [], 0.0, 0.0
    for q in questions:
        plan = rule_plan(q["q"], gazetteer(talukas), years) | {"source": "rule"} if tier == "rule" else parse(q["q"], talukas, years, tier=tier)
        ok = plan["status"] == q["status"] and (plan.get("taluka_id") == q.get("taluka_id") or q["status"] != "ok") \
            and plan.get("compare_with") == q.get("compare_with")
        reason_ok = q.get("reason") is None or plan.get("reason") == q.get("reason")
        type_ok = q.get("question_type") is None or plan.get("question_type") == q.get("question_type")
        cost += plan.get("cost_usd", 0.0)
        latency += plan.get("latency_s", 0.0)
        rows.append({"id": q["id"], "kind": q["kind"], "ok": ok, "reason_ok": reason_ok, "type_ok": type_ok,
                     "got": {k: plan.get(k) for k in ("status", "taluka_id", "compare_with", "reason", "question_type")},
                     "source": plan.get("source")})
    n = len(rows)
    return {"tier": tier, "n": n, "accuracy": sum(r["ok"] for r in rows) / n, "reason_accuracy": sum(r["reason_ok"] for r in rows) / n,
            "type_accuracy": sum(r["type_ok"] for r in rows) / n, "fallbacks": sum(r["source"] == "rule_fallback" for r in rows),
            "cost_usd": round(cost, 4), "avg_latency_s": round(latency / n, 2), "rows": rows}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m kaaran.eval.intent")
    p.add_argument("--tier", action="append", choices=["light", "main", "rule"])
    args = p.parse_args(argv)
    talukas, years = seed42_talukas()
    for tier in args.tier or ["light"]:
        r = run(tier, talukas=talukas, years=years)
        print(f"{tier:5s} accuracy {r['accuracy']:.0%}  reason {r['reason_accuracy']:.0%}  type {r['type_accuracy']:.0%}  "
              f"fallbacks {r['fallbacks']}  cost ${r['cost_usd']}  avg latency {r['avg_latency_s']}s")
        for row in r["rows"]:
            if not (row["ok"] and row["reason_ok"]):
                print(f"   MISS {row['id']} ({row['kind']}): {row['got']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
