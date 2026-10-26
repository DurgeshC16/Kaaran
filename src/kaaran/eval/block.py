"""Scorecard for the block lens (v3) against truth3.json: risks, diagnoses, data checks, positive deviance, twin,
and (when a pack is given) the rubric's actions. The only engine-side reader of truth3.json besides tests.

CLI: python -m kaaran.eval.block --seed 42 [--seed 7 ...] [--names fictional]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from ..block.ingest import ingest_block
from ..block.insights import analyze_block
from ..block.trust import run_block_trust


def score(folder: str | Path, actions: dict | None = None) -> dict:
    folder = Path(folder)
    truth = json.loads((folder / "truth3.json").read_text(encoding="utf-8"))
    ing = ingest_block(folder / "raw")
    trust = run_block_trust(ing.tables)
    focus = ing.tables["schools"].loc[ing.tables["schools"]["udise_code"].str[4:6] == "08", "block"].iloc[0]
    an = analyze_block(ing.tables, trust, focus)
    sc = {s["kind"]: s for s in truth["scenarios"]}
    flagged = {cid for cid, r in an.clusters.items() if r.status in ("AT_RISK", "DATA")}
    checks = {}

    def check(name, ok, detail=""):
        checks[name] = {"ok": bool(ok), "detail": detail}

    expected = set(truth["at_risk_clusters"])
    check("risk_recall", expected <= flagged, f"missed {sorted(expected - flagged)}")
    check("never_at_risk", not (flagged & set(truth["never_at_risk"])), f"wrongly flagged {sorted(flagged & set(truth['never_at_risk']))}")
    extra = sorted(flagged - expected - set(truth["never_at_risk"]))
    for kind, diag in (("support_gap", "D2"), ("staffing_gap", "D1"), ("data_problem", "D6"), ("seasonal_migration", "D4")):
        res = an.clusters[sc[kind]["cluster"]]
        st = res.checks.get(diag).status if diag in res.checks else None
        check(f"{kind}_diagnosis", st in ("STRONG", "WEAK"), f"{diag}={st}")
    s1 = an.clusters[sc["support_gap"]["cluster"]]
    reported = {c["competency"] for c in s1.competencies}
    check("competencies_subset", reported <= set(sc["support_gap"]["weak_competencies"]),
          f"reported {sorted(reported)} planted {sc['support_gap']['weak_competencies']}")
    check("duty_ruled_out", an.duty is not None and an.duty.status == "RULED_OUT", an.duty.status if an.duty else "none")
    check("insufficient_cluster", an.clusters[sc["insufficient_data"]["cluster"]].status == "INSUFFICIENT", "")
    honest = set(sc["honest_low_attendance"]["schools"])
    check("honest_not_flagged", not (honest & set(trust.school_flags["udise_code"])), "")
    flat = set(trust.school_flags.loc[trust.school_flags["rule"] == "TRUST-FLAT", "udise_code"])
    check("flat_found", set(sc["data_problem"]["schools"]) <= flat, "")
    pds = {p["udise_code"] for p in an.positive_deviants}
    check("positive_deviant", set(sc["positive_deviant"]["schools"]) <= pds, f"found {sorted(pds)}")
    check("surplus_found", set(sc["surplus_schools"]["schools"]) <= {s["udise_code"] for s in an.surplus}, "")
    from ..synth.config import NAME_SETS

    tw = sc["twin_block"]
    names = {k: v[0] for k, v in NAME_SETS[truth["names"]].items()}
    check("twin_block", an.twin["twin"] == names[tw["twin"]] and an.twin["decoy"] == names[tw["decoy"]],
          f"twin={an.twin['twin']} decoy={an.twin['decoy']}")
    if actions is not None:
        for kind in ("support_gap", "staffing_gap", "data_problem", "seasonal_migration", "insufficient_data"):
            s = sc[kind]
            got = actions.get(s["cluster"], [])
            check(f"{kind}_actions", got == s["expected_actions"], f"got {got} expected {s['expected_actions']}")
    return {"seed": truth["seed"], "names": truth["names"], "passed": sum(c["ok"] for c in checks.values()),
            "total": len(checks), "extra_flagged": extra, "checks": checks}


def score_seed(seed: int, names: str = "solapur", with_actions: bool = True) -> dict:
    from ..synth3.generate import generate

    with tempfile.TemporaryDirectory() as d:
        generate(seed, Path(d), names)
        acts = None
        if with_actions:
            from ..block.pack import build_block_pack

            pack = build_block_pack(Path(d) / "raw", "Pandharpur" if names == "solapur" else None)
            acts = pack["_actions_by_cluster"]
        return score(d, acts)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m kaaran.eval.block")
    p.add_argument("--seed", type=int, action="append")
    p.add_argument("--names", default="solapur")
    p.add_argument("--no-actions", action="store_true")
    args = p.parse_args(argv)
    ok = True
    for seed in args.seed or [42]:
        card = score_seed(seed, args.names, not args.no_actions)
        ok &= card["passed"] == card["total"]
        print(f"seed {seed}: {card['passed']}/{card['total']}  extra flagged: {card['extra_flagged']}")
        for name, c in card["checks"].items():
            if not c["ok"]:
                print(f"   FAIL {name}: {c['detail']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
