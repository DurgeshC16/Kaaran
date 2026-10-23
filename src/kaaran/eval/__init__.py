"""Eval harness: run the deterministic engines on the RAW files and score them against ground_truth.json.

This is the only code (besides tests) that reads the answer key. Scorecard:
- truths recovered (x/8), wrong verdicts, missing findings
- false flags: flagged schools outside the planted T5/T6 sets, and any T8 school flagged
- invented numbers: numbers with neither provenance nor derivation inputs
- provenance mismatches: query provenance whose row count or value does not re-compute on the canonical tables
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd

from ..analyze import analyze
from ..causes import resolve_taluka


def _rows(tables: dict, prov: dict) -> pd.DataFrame:
    df = tables[prov["view"]]
    mask = pd.Series(True, index=df.index)
    for field, value in prov["where"].items():
        mask &= df[field].isin(value) if isinstance(value, list) else (df[field] == value)
    return df[mask]


def check_numbers(pack: dict, tables: dict) -> dict:
    invented, mismatches, checked = [], [], 0
    for nid, n in pack["numbers"].items():
        prov = n.get("provenance", [])
        if not prov and not n.get("derivation", {}).get("inputs"):
            invented.append(nid)
        op = n.get("derivation", {}).get("op")
        for p in prov:
            if p["kind"] != "query":
                continue
            checked += 1
            rows = _rows(tables, p)
            if len(rows) != p["n_rows"]:
                mismatches.append(f"{nid}: {p['view']} n_rows {p['n_rows']} != {len(rows)}")
                continue
            if op == "mean" and p["view"] == "scores" and len(prov) == 1:
                if round(float(rows["mean_score"].mean()), n["decimals"]) != n["value"]:
                    mismatches.append(f"{nid}: mean does not recompute")
            if op == "count" and p["view"] in ("schools", "teacher_posts") and len(prov) == 1:
                if rows["udise_code"].nunique() != n["value"]:
                    mismatches.append(f"{nid}: count does not recompute")
            if op == "rank_desc" and p["view"] == "scores":
                ranks = rows.groupby("taluka_id")["mean_score"].mean().rank(ascending=False, method="min")
                if int(ranks[n["entity"]]) != n["value"]:
                    mismatches.append(f"{nid}: rank does not recompute")
    return {"invented": invented, "mismatches": mismatches, "queries_checked": checked}


def score(pack: dict, analysis, truth: dict) -> dict:
    tables = analysis.ingest.tables
    T = {t["id"]: t for t in truth["truths"]}
    findings = pack["findings"]

    def tid(name):
        return resolve_taluka(tables, name)

    def members(sid):
        return {m[1:] for m in pack["entity_sets"][sid]["members"]}

    def find(pred):
        return next((f for f in findings if pred(f)), None)

    results = {}
    focus = tid(T["T1"]["entities"]["talukas"][0])
    f = find(lambda f: f["type"] == "TREND" and f["params"]["taluka"]["entity"] == focus)
    results["T1"] = (f, f is not None and f["label"] == "STRONG" and f["template_key"] == "trend.decline_rank")
    f = find(lambda f: f["type"] == "CAUSE" and f.get("hypothesis") == "election")
    results["T2"] = (f, f is not None and f["label"] == "WEAK")
    f = find(lambda f: f["type"] == "CAUSE" and f.get("hypothesis") == "vacancy")
    results["T3"] = (f, f is not None and f["label"] == "STRONG"
                     and members(f["params"]["schools"]["set"]) == set(T["T3"]["entities"]["schools"]))
    f = find(lambda f: f["type"] == "TWIN")
    results["T4"] = (f, f is not None and f["label"] == "LEARN_FROM"
                     and f["params"]["twin"]["entity"] == tid(T["T4"]["entities"]["talukas"][0]))
    t5_taluka = tid(T["T5"]["entities"]["talukas"][0])
    f = find(lambda f: f["rule_id"] == "TRUST-FLAT-TALUKA" and f["params"]["taluka"]["entity"] == t5_taluka)
    all_t5 = set(T["T5"]["entities"]["schools"]) | set(T["T5"]["entities"]["scattered_schools"])
    flags = analysis.trust.flags
    flat_flagged = set(flags.loc[flags["rule_id"] == "TRUST-FLAT-SCHOOL", "entity_id"])
    results["T5"] = (f, f is not None and f["label"] == "RED_FLAG"
                     and members(f["params"]["schools"]["set"]) == set(T["T5"]["entities"]["schools"]) and all_t5 <= flat_flagged)
    t6_taluka = tid(T["T6"]["entities"]["talukas"][0])
    f = find(lambda f: f["rule_id"] == "TRUST-INSUFFICIENT-TALUKA" and f["params"]["taluka"]["entity"] == t6_taluka)
    results["T6"] = (f, f is not None and f["label"] == "INSUFFICIENT")
    f = find(lambda f: f["type"] == "CAUSE" and f.get("hypothesis") == "infrastructure")
    results["T7"] = (f, f is not None and f["label"] == "RULED_OUT")
    honest = set(T["T8"]["entities"]["schools"])
    flagged = analysis.trust.flagged_schools()
    flag_sets = [members(f["params"]["schools"]["set"]) for f in findings
                 if f["label"] in ("RED_FLAG", "INSUFFICIENT") and "schools" in f["params"]]
    in_flag_sets = set().union(*flag_sets) if flag_sets else set()
    results["T8"] = (None, not (honest & (flagged | in_flag_sets)))

    expected = {"T1": "STRONG", "T2": "WEAK", "T3": "STRONG", "T4": "LEARN_FROM", "T5": "RED_FLAG", "T6": "INSUFFICIENT",
                "T7": "RULED_OUT", "T8": "not flagged"}
    planted_flagged = all_t5 | set(T["T6"]["entities"]["schools"])
    numbers = check_numbers(pack, tables)
    rows = []
    for k in sorted(results):
        f, ok = results[k]
        if k == "T8":
            got = "not flagged" if ok else "flagged"
        else:
            got = f["label"] if f else "missing"
        rows.append({"truth": k, "expected": expected[k], "got": got, "recovered": bool(ok)})
    return {
        "recovered": sum(r["recovered"] for r in rows),
        "total": len(rows),
        "truths": rows,
        "wrong_verdicts": [r["truth"] for r in rows if not r["recovered"] and r["got"] != "missing"],
        "missing_findings": [r["truth"] for r in rows if r["got"] == "missing"],
        "false_flags": sorted(flagged - planted_flagged),
        "t8_flagged": sorted(honest & flagged),
        "invented_numbers": numbers["invented"],
        "provenance_mismatches": numbers["mismatches"],
        "queries_checked": numbers["queries_checked"],
        "numbers": len(pack["numbers"]),
    }


def evaluate_folder(folder: str | Path, proposer: str = "rule") -> tuple[dict, object]:
    folder = Path(folder)
    truth = json.loads((folder / "ground_truth.json").read_text(encoding="utf-8"))
    focus = next(t for t in truth["truths"] if t["id"] == "T1")["entities"]["talukas"][0]
    analysis = analyze(folder / "raw", focus, proposer=proposer)
    card = score(analysis.pack, analysis, truth)
    card["seed"] = truth["seed"]
    card["names"] = truth["taluka_name_set"]
    card["layout"] = truth.get("layout", {}).get("name", "default")
    card["mapping_proposer"] = analysis.ingest.report.get("mapping_proposer", {}).get("source")
    return card, analysis


def evaluate_seed(seed: int, names: str = "solapur", layout: str = "default", proposer: str = "rule") -> dict:
    from ..synth.generate import generate

    with tempfile.TemporaryDirectory() as d:
        generate(seed=seed, out=d, names=names, layout=layout)
        card, _ = evaluate_folder(d, proposer)
    return card


def format_scorecard(card: dict) -> str:
    lines = [f"Kaaran eval (SYNTHETIC data, seed {card['seed']}, names {card['names']}, layout {card.get('layout', 'default')}, "
             f"mapping {card.get('mapping_proposer') or 'rule'})",
             f"  truths recovered: {card['recovered']}/{card['total']}"]
    for r in card["truths"]:
        lines.append(f"    {r['truth']}: expected {r['expected']:<12} got {r['got']:<12} {'OK' if r['recovered'] else 'FAIL'}")
    lines += [
        f"  wrong verdicts: {len(card['wrong_verdicts'])} {card['wrong_verdicts'] or ''}".rstrip(),
        f"  missing findings: {len(card['missing_findings'])} {card['missing_findings'] or ''}".rstrip(),
        f"  false flags: {len(card['false_flags'])} (T8 honest schools flagged: {len(card['t8_flagged'])})",
        f"  invented numbers (no provenance): {len(card['invented_numbers'])} of {card['numbers']}",
        f"  provenance mismatches: {len(card['provenance_mismatches'])} of {card['queries_checked']} queries re-run",
    ]
    return "\n".join(lines)
