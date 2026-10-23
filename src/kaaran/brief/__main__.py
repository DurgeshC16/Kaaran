"""CLI: python -m kaaran.brief data/synthetic/demo/raw --focus Pandharpur --out-dir out [--no-llm]"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .. import evidence as E
from ..analyze import analyze
from .writer import write_brief


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m kaaran.brief", description="Raw files -> Marathi + English Evidence Brief.")
    p.add_argument("raw_dir")
    p.add_argument("--focus", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--no-llm", action="store_true", help="fixed templates only (what happens when the API is unavailable)")
    args = p.parse_args(argv)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pack = analyze(args.raw_dir, args.focus).pack
    brief = write_brief(pack, use_llm=not args.no_llm)
    E.dump(pack, out / "evidence.json")
    (out / "brief_mr.md").write_text(brief.markdown["mr"], encoding="utf-8")
    (out / "brief_en.md").write_text(brief.markdown["en"], encoding="utf-8")
    (out / "brief.json").write_text(json.dumps({"prose": brief.prose, "sources": brief.sources, "info": brief.info},
                                               ensure_ascii=False, indent=1), encoding="utf-8")
    llm = sum(v.startswith("llm") for v in brief.sources.values())
    print(f"brief written to {out} ({llm} of {len(brief.sources)} findings worded by the LLM; cost ${brief.info['cost_usd']:.4f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
