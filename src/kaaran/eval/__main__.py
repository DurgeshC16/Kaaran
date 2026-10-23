"""CLI: python -m kaaran.eval --seed 42 [--seed 7 ...] [--names fictional] [--json out.json]"""

from __future__ import annotations

import argparse
import json
import sys

from . import evaluate_seed, format_scorecard


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m kaaran.eval", description="Score the engines against the answer key (no LLM).")
    p.add_argument("--seed", type=int, action="append", required=True, help="repeatable")
    p.add_argument("--names", default="solapur", choices=["solapur", "fictional"])
    p.add_argument("--layout", default="default", choices=["default", "variant_b"])
    p.add_argument("--proposer", default="rule", choices=["rule", "llm"])
    p.add_argument("--json", help="write the scorecards as JSON")
    args = p.parse_args(argv)
    cards = [evaluate_seed(s, args.names, args.layout, args.proposer) for s in args.seed]
    print("\n\n".join(format_scorecard(c) for c in cards))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(cards, fh, ensure_ascii=False, indent=1)
    return 0 if all(c["recovered"] == c["total"] for c in cards) else 1


if __name__ == "__main__":
    sys.exit(main())
