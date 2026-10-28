"""Verify the rubric's budget citations (funded_under) against a real Samagra Shiksha PAB line-item file.

The PAB CSV stays in data/real/ (never committed). The rubric only cites codes, items and pages; this check
proves each cited line exists on the cited page, so an officer can trust "this action is already funded".
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..block.rubric import load_rubric


def verify_pab(pab_csv: str | Path, rubric: dict | None = None) -> list[dict]:
    rubric = rubric or load_rubric()
    pab = pd.read_csv(pab_csv, comment="#")
    for col in ("Code", "Page", "Sub Activity", "Sub Component"):
        if col not in pab.columns:
            return [{"id": "pab_columns", "ok": False, "detail": f"missing column {col}"}]
    pab["Code"] = pab["Code"].astype(str).str.strip()
    checks = []
    if "State" in pab.columns:  # the rubric cites Maharashtra; other states' rows must not "verify" it
        pab = pab[pab["State"].astype(str).str.strip().str.casefold() == "maharashtra"]
    if pab.empty:
        return [{"id": "pab_state", "ok": False, "detail": "no Maharashtra rows in the PAB file"}]
    for row in rubric["actions"] + rubric["brief_level"]:
        f = row.get("funded_under")
        if not f:
            continue
        hit = pab[pab["Code"] == f["code"]]
        pages = sorted({int(p) for p in pd.to_numeric(hit["Page"], errors="coerce").dropna()})
        ok = len(hit) > 0 and int(f["page"]) in pages
        detail = (f"{f['code']} p.{f['page']}: " + (hit["Sub Activity"].iloc[0] if len(hit) else "not found")
                  + ("" if ok else f" (pages in file: {pages})"))
        checks.append({"id": f"pab_{row['id']}_{f['code']}", "ok": bool(ok), "detail": detail})
    return checks
