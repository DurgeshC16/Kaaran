"""Cause tester (no LLM): trend, election duty, teacher vacancy, infrastructure, attendance."""

from __future__ import annotations

from ..evidence import Builder
from .data import analysis_attendance, analysis_scores
from .hypotheses import attendance, election, infrastructure, vacancy
from .trend import analyse_trend


def resolve_taluka(tables: dict, name: str) -> str:
    t = tables["talukas"]
    for col in ("taluka_id", "taluka", "taluka_mr"):
        hit = t[t[col].astype(str).str.casefold() == str(name).strip().casefold()]
        if len(hit):
            return hit["taluka_id"].iloc[0]
    raise ValueError(f"unknown taluka {name!r}; known: {sorted(t['taluka'])}")


def run_causes(tables: dict, trust, focus: str, builder: Builder | None = None) -> tuple[Builder, dict]:
    """Findings for one focus taluka. A taluka marked INSUFFICIENT by trust caps its findings at INSUFFICIENT."""
    b = builder or Builder(tables)
    b.taluka(focus)
    insufficient = focus in set(trust.report.get("insufficient_talukas", []))
    sc = analysis_scores(tables, trust)
    att = analysis_attendance(tables, trust)
    trend = analyse_trend(b, sc, focus, insufficient)
    vac, vac_info = vacancy(b, tables, sc, focus, insufficient)
    # Correlational hypotheses are tested on schools not exposed to a STRONG school-level cause, so the main
    # cause's large effects cannot create or hide a secondary correlation (docs/CONFIDENCE_RULES.md).
    exclude = frozenset(vac_info["schools"]) if vac is not None and vac["label"] == "STRONG" else frozenset()
    results = {"trend": trend, "election": election(b, tables, sc, focus, insufficient), "vacancy": vac,
               "infrastructure": infrastructure(b, tables, sc, focus, insufficient, exclude),
               "attendance": attendance(b, tables, sc, att, focus, insufficient, exclude), "vacancy_info": vac_info}
    return b, results
