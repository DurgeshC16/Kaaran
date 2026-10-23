"""End-to-end deterministic analysis (no LLM): raw files -> ingest -> trust -> causes -> twins -> evidence pack.

CLI: python -m kaaran.analyze data/synthetic/demo/raw --focus Pandharpur --out evidence.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from . import evidence as E
from .causes import resolve_taluka, run_causes
from .causes.data import analysis_scores
from .ingest import IngestResult, ingest
from .trust import TrustResult, run_trust
from .twins import find_twin

LABEL_RANK = {"STRONG": 0, "WEAK": 1, "INSUFFICIENT": 2, "RULED_OUT": 3}
SYNTHETIC_MARKER = "SYNTHETIC DEMO DATA - NOT REAL"


@dataclass
class Analysis:
    pack: dict
    ingest: IngestResult
    trust: TrustResult
    focus: str


def _actions(b: E.Builder, results: dict, twin: dict, trust_fragment: dict, focus: str) -> list[dict]:
    """ACTION-CATALOG: a fixed action per supporting finding; all within district/block officers' powers."""
    acts = []

    def add(fid, key, params, role, based_on, horizon, targets=None):
        action = {"actor_role": role, "based_on": based_on, "horizon": horizon, "within_officer_powers": True}
        if targets:
            action["targets"] = targets
        acts.append(b.finding(id=fid, type="ACTION", label="ACTION", rule_id="ACTION-CATALOG", template_key=key,
                              params=params, action=action, related=list(based_on)))

    vac = results.get("vacancy")
    if vac is not None and vac["label"] == "STRONG":
        sid = vac["params"]["schools"]["set"]
        add("F.action.redeploy", "action.redeploy_teachers",
            {"taluka": {"entity": focus}, "subject": {"text_key": "subject.maths"}, "schools": {"set": sid}},
            "DEO", [vac["id"]], "this_month", sid)
    if twin["label"] == "LEARN_FROM":
        add("F.action.exposure_visit", "action.exposure_visit", {"twin": twin["params"]["twin"], "focus": {"entity": focus}},
            "BEO", [twin["id"]], "this_month")
    for f in trust_fragment["findings"]:
        if f["params"]["taluka"]["entity"] != focus:
            continue
        sid = f["params"]["schools"]["set"]
        if f["rule_id"] == "TRUST-FLAT-TALUKA":
            add("F.action.verify_registers", "action.verify_registers", {"taluka": {"entity": focus}, "schools": {"set": sid}},
                "KENDRA_PRAMUKH", [f["id"]], "this_week", sid)
        if f["rule_id"] == "TRUST-INSUFFICIENT-TALUKA":
            add("F.action.collect_missing_data", "action.collect_missing_data", {"taluka": {"entity": focus}, "schools": {"set": sid}},
                "BEO", [f["id"]], "this_month", sid)
    return acts


def _outline(findings: list[dict], focus: str) -> list[dict]:
    """Written rule: which finding goes in which brief section (never decided by an LLM)."""
    by_id = {f["id"]: f for f in findings}
    causes = [f for f in findings if f["type"] == "CAUSE"]
    election = [f["id"] for f in causes if f.get("hypothesis") == "election"]
    candidates = [f for f in causes if f.get("hypothesis") != "election" and f["label"] in ("STRONG", "WEAK")]
    main = sorted(candidates, key=lambda f: (LABEL_RANK[f["label"]], f["id"]))[:1]
    data = [f["id"] for f in findings if f["type"] == "DATA" and f["params"]["taluka"]["entity"] == focus]
    sections = [("trend", [f["id"] for f in findings if f["type"] == "TREND"]), ("election_check", election),
                ("main_cause", [f["id"] for f in main]), ("twin", [f["id"] for f in findings if f["type"] == "TWIN"]),
                ("data_warning", data), ("action", [f["id"] for f in findings if f["type"] == "ACTION"])]
    placed = {fid for _, ids in sections for fid in ids}
    sections.append(("appendix", [fid for fid in by_id if fid not in placed]))
    return [{"section": s, "finding_ids": ids} for s, ids in sections if ids]


def analyze(raw_dir: str | Path, focus_name: str, db_path: str | Path | None = None, mapping: dict | None = None,
            proposer: str = "rule") -> Analysis:
    ing = ingest(raw_dir, db_path, mapping, proposer)
    trust = run_trust(ing.tables, ing.report)
    focus = resolve_taluka(ing.tables, focus_name)
    b, results = run_causes(ing.tables, trust, focus)
    twin = find_twin(b, ing.tables, analysis_scores(ing.tables, trust), trust, focus)
    vac = results.get("vacancy")
    if vac is not None and vac["label"] == "STRONG" and vac["params"].get("share_of_decline"):
        results["trend"]["caveats"].append({"template_key": "caveat.concentrated_in_few_schools",
                                            "params": {"schools": vac["params"]["schools"]}})
        results["trend"]["related"].append(vac["id"])
    _actions(b, results, twin, trust.fragment, focus)
    # District-wide RED_FLAG / INSUFFICIENT findings stay (context); CLEARED lists only for the focus taluka.
    trust_fragment = dict(trust.fragment)
    trust_fragment["findings"] = [f for f in trust.fragment["findings"]
                                  if f["label"] != "CLEARED" or f["params"]["taluka"]["entity"] == focus]
    fragment = E.merge_fragments(trust_fragment, b.fragment())
    synthetic = bool(ing.report["synthetic"])
    for f in fragment["findings"]:
        if synthetic and f["type"] != "ACTION":
            f["caveats"].insert(0, {"template_key": "caveat.synthetic_data", "params": {}})
    district = "D" + str(ing.tables["schools"]["udise_code"].iloc[0])[2:4]
    fragment["entities"][district] = {"kind": "district", "code": district[1:],
                                      "name_en": "SYNTHETIC DEMO DISTRICT" if synthetic else "District"}
    years = sorted(set(ing.tables["scores"]["academic_year"]))
    period = f"p.{years[0]}_{years[-1]}"
    fragment["periods"].setdefault(period, {"kind": "year_range", "from": years[0], "to": years[-1]})
    pack = {
        "schema_version": E.SCHEMA_VERSION, "template_registry_version": E.TEMPLATE_REGISTRY_VERSION,
        "engine_version": "0.2.0", "mapping_sha256": ing.report["mapping_sha256"],
        "synthetic": synthetic, "marker": SYNTHETIC_MARKER if synthetic else "", "illustrative": False,
        "scope": {"district": district, "focus": focus, "subject": "subject.maths", "std": 3, "period": period,
                  "question": "question.why_decline"},
        "sources": [{k: s[k] for k in ("id", "file", "kind", "sha256", "synthetic", "marker_at")} for s in ing.report["sources"]],
        **fragment,
        "outline": _outline(fragment["findings"], focus),
    }
    pack = E.finalize(E.prune(pack))
    problems = E.validate(pack)
    if problems:
        raise ValueError(f"engine produced an invalid evidence pack: {problems[:5]}")
    return Analysis(pack=pack, ingest=ing, trust=trust, focus=focus)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m kaaran.analyze", description="Raw files -> evidence pack (no LLM).")
    p.add_argument("raw_dir")
    p.add_argument("--focus", required=True, help="taluka name (English or Marathi) or id")
    p.add_argument("--out", required=True)
    p.add_argument("--db", help="also write the DuckDB store here")
    p.add_argument("--proposer", choices=["rule", "llm"], default="rule", help="column-mapping proposer (llm falls back to rule)")
    args = p.parse_args(argv)
    result = analyze(args.raw_dir, args.focus, args.db, proposer=args.proposer)
    E.dump(result.pack, args.out)
    names = {k: v["name_en"] for k, v in result.pack["entities"].items()}
    findings = {f["id"]: f for f in result.pack["findings"]}
    print(f"{'SYNTHETIC ' if result.pack['synthetic'] else ''}evidence pack for {names[result.focus]} -> {args.out}")
    for sec in result.pack["outline"]:
        for fid in sec["finding_ids"]:
            f = findings[fid]
            print(f"  {sec['section']:15s} {f['type']:6s} {f['label']:12s} {f['template_key']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
