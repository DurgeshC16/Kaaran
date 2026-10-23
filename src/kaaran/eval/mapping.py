"""Mapping-proposer eval: rule-based baseline vs LLM proposer on the default layout and the variant_b hold-out.

Gold mapping: the rule-based mapping of the DEFAULT layout of the same seed (proven by the ingest round trip),
carried over to variant_b through the layout key the generator writes (sheet renames, header rewording,
header-row shift). Scores:
- required: share of required fields mapped to the right column (or sheet name);
- all: share of all gold fields (required + optional) mapped correctly;
- tables: share of tables given the right role and header row;
- valid: the mapping passes validation + dry run; scorecard: 8/8 truths with the LLM mapping on variant_b.

CLI: python -m kaaran.eval.mapping --seed 42 --seed 7 --seed 2026 [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from ..ingest import mapping as M
from ..ingest.readers import xlsx_rows
from ..llm.mapper import check, propose_with_llm


def _expand(entries: list[dict], raw_dir: Path) -> dict[tuple, dict]:
    """(file, sheet) -> entry; '*' entries expand to every sheet of the workbook."""
    out = {}
    for e in entries:
        if e["read"]["format"] == "pdf":
            continue
        sheets = list(xlsx_rows(raw_dir / e["file"])) if e.get("sheet") == "*" else [e.get("sheet")]
        for s in sheets:
            out[(e["file"], s)] = e
    return out


def gold_mapping(default_raw: Path, layout_key: dict, target_raw: Path) -> dict[tuple, dict]:
    base = _expand(M.propose(default_raw)["entries"], default_raw)
    if layout_key.get("name", "default") == "default":
        return {k: {"role": e["role"], "header_row": e["read"]["header_row"], "fields": e["fields"]} for k, e in base.items()}
    gold = {}
    for t in layout_key["tables"]:
        e = base.get((t["file"], t["sheet_from"]))
        if e is None:
            continue
        fields = {}
        for f, spec in e["fields"].items():
            src = spec["source"]
            fields[f] = {"source": {"col": t["headers"].get(src["col"], src["col"])} if "col" in src else src}
        gold[(t["file"], t["sheet_to"])] = {"role": e["role"], "header_row": e["read"]["header_row"] + t.get("header_row_shift", 0),
                                            "fields": fields}
    return gold


def score_mapping(proposal: dict, gold: dict[tuple, dict], raw_dir: Path) -> dict:
    got = _expand(proposal["entries"], raw_dir)
    req_ok = req_n = all_ok = all_n = tab_ok = 0
    misses = []
    for key, g in gold.items():
        e = got.get(key)
        tab_ok += bool(e and e["role"] == g["role"] and e["read"]["header_row"] == g["header_row"])
        required = M.ROLES[g["role"]][0]
        for f, spec in g["fields"].items():
            ok = bool(e and e["role"] == g["role"] and f in e["fields"] and e["fields"][f]["source"] == spec["source"])
            all_n += 1
            all_ok += ok
            if f in required:
                req_n += 1
                req_ok += ok
            if not ok:
                misses.append(f"{key[0]}|{key[1]}|{f}")
    return {"required": req_ok / req_n if req_n else 0.0, "all": all_ok / all_n if all_n else 0.0,
            "tables": tab_ok / len(gold) if gold else 0.0, "misses": misses}


def evaluate_seed(seed: int, names: str = "solapur") -> list[dict]:
    from ..synth.generate import generate
    from . import evaluate_folder

    rows = []
    with tempfile.TemporaryDirectory() as d:
        default_dir, variant_dir = Path(d) / "default", Path(d) / "variant_b"
        generate(seed=seed, out=default_dir, names=names)
        generate(seed=seed, out=variant_dir, names=names, layout="variant_b")
        for layout, folder in (("default", default_dir), ("variant_b", variant_dir)):
            truth = json.loads((folder / "ground_truth.json").read_text(encoding="utf-8"))
            gold = gold_mapping(default_dir / "raw", truth["layout"], folder / "raw")
            baseline = M.propose(folder / "raw")
            rows.append({"seed": seed, "layout": layout, "proposer": "rule", "valid": not check(baseline, folder / "raw"),
                         **score_mapping(baseline, gold, folder / "raw")})
            mapping, info = propose_with_llm(folder / "raw")
            row = {"seed": seed, "layout": layout, "proposer": "llm", "source": info["source"], "valid": info["source"] != "rule_fallback",
                   "cost_usd": round(info["cost_usd"], 4), "latency_s": round(info["latency_s"], 1), **score_mapping(mapping, gold, folder / "raw")}
            if layout == "variant_b":
                card, _ = evaluate_folder(folder, proposer="llm")
                row["scorecard"] = f"{card['recovered']}/{card['total']}"
            rows.append(row)
    return rows


def format_rows(rows: list[dict]) -> str:
    lines = ["seed  layout     proposer  valid  required  all     tables  scorecard  source        cost $   latency s"]
    for r in rows:
        lines.append(f"{r['seed']:<5} {r['layout']:<10} {r['proposer']:<9} {str(r['valid']):<6} {r['required']:>7.0%}  {r['all']:>6.0%}  "
                     f"{r['tables']:>6.0%}  {r.get('scorecard', ''):<9}  {r.get('source', ''):<12}  {r.get('cost_usd', ''):<7}  {r.get('latency_s', '')}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m kaaran.eval.mapping", description="Baseline vs LLM mapping accuracy.")
    p.add_argument("--seed", type=int, action="append", required=True)
    p.add_argument("--json")
    args = p.parse_args(argv)
    rows = [r for s in args.seed for r in evaluate_seed(s)]
    print(format_rows(rows))
    if args.json:
        Path(args.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
