"""Brief-level eval: Marathi/English briefs over several seeds.

Per seed: verifier pass rate (findings whose LLM text passed on the first attempt; and the shipped brief),
findings that fell back to templates, invented numbers (every figure in the rendered Markdown must equal a
value code filled in: number displays, set sizes, period texts), cost and latency (recorded per call).

CLI: python -m kaaran.eval.brief --seed 42 --seed 7 ... [--names fictional] [--samples data/samples]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

from ..analyze import analyze
from ..brief import write_brief
from ..brief.render import period_text
from ..evidence import format_number

NUMBER = re.compile(r"[0-9०-९][0-9०-९.,%\-]*")


def allowed_figures(pack: dict) -> set[str]:
    allowed = set()
    for n in pack["numbers"].values():
        allowed |= {n["display"]["en"], n["display"]["mr"]}
    for s in pack["entity_sets"].values():
        size = len(s["members"])
        allowed |= set(format_number(size, "count", 0).values())
    for per in pack["periods"].values():
        allowed |= {period_text(per, "mr"), period_text(per, "en")}
    return allowed


def invented_numbers(markdown: str, pack: dict) -> list[str]:
    """Figures in the rendered brief that code did not fill in."""
    allowed = allowed_figures(pack)
    out = []
    for tok in NUMBER.findall(markdown):
        tok = tok.rstrip(".,-")
        if tok and not any(tok in a for a in allowed):
            out.append(tok)
    return out


def evaluate_folder(folder: str | Path) -> tuple[dict, object]:
    folder = Path(folder)
    truth = json.loads((folder / "ground_truth.json").read_text(encoding="utf-8"))
    focus = next(t for t in truth["truths"] if t["id"] == "T1")["entities"]["talukas"][0]
    pack = analyze(folder / "raw", focus).pack
    brief = write_brief(pack)
    n = len(brief.sources)
    first = sum(1 for s in brief.sources.values() if s == "llm")
    card = {
        "seed": truth["seed"], "names": truth["taluka_name_set"], "findings": n,
        "llm_first_attempt": first, "llm_after_retry": sum(1 for s in brief.sources.values() if s == "llm_retry"),
        "template_fallback": sum(1 for s in brief.sources.values() if s == "template"),
        "first_pass_rate": first / n if n else 0.0,
        "shipped_passed": brief.info["verification"]["passed"],
        "invented_numbers": invented_numbers(brief.markdown["mr"], pack) + invented_numbers(brief.markdown["en"], pack),
        "llm_available": brief.info["llm_available"], "calls": len(brief.info["calls"]),
        "cost_usd": round(brief.info["cost_usd"], 4), "latency_s": round(brief.info["latency_s"], 1),
    }
    return card, brief


def evaluate_seed(seed: int, names: str = "solapur", samples: Path | None = None) -> dict:
    from ..synth.generate import generate

    with tempfile.TemporaryDirectory() as d:
        generate(seed=seed, out=d, names=names)
        card, brief = evaluate_folder(d)
    if samples is not None:
        samples.mkdir(parents=True, exist_ok=True)
        tag = f"seed{seed}" + ("" if names == "solapur" else f"_{names}")
        (samples / f"brief_{tag}_mr.md").write_text(brief.markdown["mr"], encoding="utf-8")
        (samples / f"brief_{tag}_en.md").write_text(brief.markdown["en"], encoding="utf-8")
    return card


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m kaaran.eval.brief")
    p.add_argument("--seed", type=int, action="append", required=True)
    p.add_argument("--names", default="solapur", choices=["solapur", "fictional"])
    p.add_argument("--samples", help="also save the Markdown briefs here")
    p.add_argument("--json")
    args = p.parse_args(argv)
    cards = [evaluate_seed(s, args.names, Path(args.samples) if args.samples else None) for s in args.seed]
    print("seed  names      findings  llm 1st  retry  template  first-pass  shipped  invented  cost $   latency s")
    for c in cards:
        print(f"{c['seed']:<5} {c['names']:<10} {c['findings']:<9} {c['llm_first_attempt']:<8} {c['llm_after_retry']:<6} "
              f"{c['template_fallback']:<9} {c['first_pass_rate']:<11.0%} {str(c['shipped_passed']):<8} {len(c['invented_numbers']):<9} "
              f"{c['cost_usd']:<8} {c['latency_s']}")
    if args.json:
        Path(args.json).write_text(json.dumps(cards, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
