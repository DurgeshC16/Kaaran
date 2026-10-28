"""Real public data: UDISE+ school-level microdata (pseudocode IDs) -> validated, aggregate-only block snapshot.

Input-side signals Kaaran can compute from real public data today (outcomes and monthly operations need state
logins, see docs/02):
- teacher availability: schools with one teacher or none, pupil-teacher ratio (PTR) above the RTE primary norm of 30;
- academic support: schools that reported no cluster (CRC) visit in the previous year;
- non-teaching assignments: teachers reported as involved in non-teaching work.
Every figure carries provenance (file, filter, rows). Only aggregates leave this module (no pseudocodes).
UDISE+ values are self-reported by schools; the report says "reported", never "proven".
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

FILES = ("prof1", "prof2", "tch", "enr1")
REQUIRED = {
    "prof1": {"pseudocode", "district", "block", "managment", "school_category", "lowclass", "highclass", "rural_urban"},
    "prof2": {"pseudocode", "crc_coordinator", "block_level_officers", "acad_inspections"},
    "tch": {"pseudocode", "total_tch", "contract", "teacher_involve_non_training_assignment"},
    "enr1": {"pseudocode", "item_group", "item_id"},
}
LOCAL_BODY = 3  # UDISE+ management code for local body (ZP) schools; cross-checked against AIKosh labels
ELEMENTARY = (1, 2)  # school_category: primary only, primary with upper primary
RTE_PTR = 30
ENROL_COLS = [f"c{i}_{s}" for i in range(1, 9) for s in "bg"]


class RealDataError(ValueError):
    pass


@dataclass
class Snapshot:
    district: str
    year: str
    blocks: pd.DataFrame
    totals: dict
    checks: list = field(default_factory=list)
    provenance: dict = field(default_factory=dict)
    cross_check: pd.DataFrame | None = None

    def to_dict(self) -> dict:
        return {"kind": "REAL_PUBLIC_DATA", "source": "UDISE+ school-level microdata (pseudocode IDs)",
                "district": self.district, "year": self.year, "filter": "local-body (ZP) elementary schools",
                "note": "Self-reported by schools to UDISE+; aggregates only; no school identifiers.",
                "totals": self.totals, "blocks": self.blocks.reset_index().to_dict("records"), "checks": self.checks,
                "provenance": self.provenance,
                "cross_check_2019_20": None if self.cross_check is None else self.cross_check.reset_index().to_dict("records")}


def load_microdata(folder: str | Path) -> dict[str, pd.DataFrame]:
    folder = Path(folder)
    out = {}
    for kind in FILES:
        found = sorted(folder.glob(f"*_{kind}.csv"))
        if len(found) != 1:
            raise RealDataError(f"expected one *_{kind}.csv in {folder}, found {len(found)}")
        df = pd.read_csv(found[0])
        missing = REQUIRED[kind] - set(df.columns)
        if missing:
            raise RealDataError(f"{found[0].name}: missing columns {sorted(missing)}")
        df.attrs["file"] = found[0].name
        out[kind] = df
    return out


def validate(t: dict[str, pd.DataFrame]) -> list[dict]:
    """Structural checks before any figure is reported (rule 4: trust before analysis)."""
    checks = []

    def add(cid, ok, detail):
        checks.append({"id": cid, "ok": bool(ok), "detail": detail})

    p1 = t["prof1"]
    for kind in ("prof1", "prof2", "tch"):
        add(f"unique_ids_{kind}", t[kind]["pseudocode"].is_unique, f"{len(t[kind])} rows")
    ids = set(p1["pseudocode"])
    for kind in ("prof2", "tch"):
        other = set(t[kind]["pseudocode"])
        add(f"same_schools_{kind}", other == ids, f"{len(ids ^ other)} ids differ from prof1")
    enr_ids = set(t["enr1"]["pseudocode"])
    add("enrolment_ids_known", enr_ids <= ids, f"{len(enr_ids - ids)} enrolment ids not in prof1")
    add("single_district", p1["district"].nunique() == 1, ", ".join(map(str, p1["district"].unique()[:3])))
    add("class_range", bool((p1["highclass"] >= p1["lowclass"]).all()), f"{int((p1['highclass'] < p1['lowclass']).sum())} bad rows")
    tch = t["tch"]["total_tch"]
    add("teachers_non_negative", bool((tch >= 0).all()), f"min {tch.min()}, max {tch.max()}")
    crc = t["prof2"]["crc_coordinator"]
    add("crc_visits_plausible", bool(crc.between(0, 120).all()), f"max {crc.max()} visits in a year")
    return checks


def enrolment(enr1: pd.DataFrame) -> pd.Series:
    """Classes 1-8 enrolment per school (item_group 1 = social category rows, which sum to the total)."""
    e = enr1[enr1["item_group"] == 1]
    return e.groupby("pseudocode")[ENROL_COLS].sum().sum(axis=1).rename("enrol_1_8")


def snapshot(t: dict[str, pd.DataFrame], year: str = "2024-25", management: int = LOCAL_BODY,
             categories: tuple = ELEMENTARY) -> Snapshot:
    checks = validate(t)
    bad = [c for c in checks if not c["ok"]]
    if bad:
        raise RealDataError(f"real data failed checks: {bad}")
    p1, p2, tc = t["prof1"], t["prof2"], t["tch"]
    df = (p1[["pseudocode", "district", "block", "managment", "school_category"]]
          .merge(tc[["pseudocode", "total_tch", "contract", "teacher_involve_non_training_assignment"]], on="pseudocode")
          .merge(p2[["pseudocode", "crc_coordinator"]], on="pseudocode")
          .merge(enrolment(t["enr1"]), on="pseudocode", how="left"))
    sel = df[(df["managment"] == management) & df["school_category"].isin(categories)].copy()
    sel["ptr"] = sel["enrol_1_8"] / sel["total_tch"].where(sel["total_tch"] > 0)
    g = sel.groupby("block").agg(
        schools=("pseudocode", "size"), teachers=("total_tch", "sum"), pupils=("enrol_1_8", "sum"),
        zero_teacher=("total_tch", lambda s: int((s == 0).sum())), single_teacher=("total_tch", lambda s: int((s == 1).sum())),
        ptr_over_30=("ptr", lambda s: int((s > RTE_PTR).sum())), no_crc_visit=("crc_coordinator", lambda s: int((s == 0).sum())),
        median_crc_visits=("crc_coordinator", "median"), contract_teachers=("contract", "sum"),
        non_teaching_teachers=("teacher_involve_non_training_assignment", "sum"))
    g["ptr"] = (g["pupils"] / g["teachers"]).round(1)
    g["pct_no_crc_visit"] = (100 * g["no_crc_visit"] / g["schools"]).round(1)
    g["pct_teachers_non_teaching"] = (100 * g["non_teaching_teachers"] / g["teachers"]).round(1)
    for c in ("pupils",):
        g[c] = g[c].fillna(0).astype(int)
    totals = {k: int(g[k].sum()) for k in ("schools", "teachers", "pupils", "zero_teacher", "single_teacher", "ptr_over_30",
                                           "no_crc_visit", "non_teaching_teachers")}
    totals["ptr"] = round(totals["pupils"] / totals["teachers"], 1) if totals["teachers"] else None
    filt = {"managment": management, "school_category": list(categories)}
    prov = {
        "schools": {"file": p1.attrs.get("file"), "filter": filt, "n_rows": int(len(sel))},
        "teachers": {"file": tc.attrs.get("file"), "column": "total_tch", "filter": filt},
        "pupils": {"file": t["enr1"].attrs.get("file"), "columns": "c1..c8 boys+girls, item_group 1", "filter": filt},
        "crc_visits": {"file": p2.attrs.get("file"), "column": "crc_coordinator (visits in the previous year)", "filter": filt},
        "non_teaching": {"file": tc.attrs.get("file"), "column": "teacher_involve_non_training_assignment", "filter": filt},
    }
    return Snapshot(district=str(p1["district"].iloc[0]), year=year, blocks=g, totals=totals, checks=checks, provenance=prov)


def cross_check_aikosh(snap: Snapshot, aikosh_csv: str | Path) -> pd.DataFrame:
    """Local-body teachers per block: UDISE+ 2019-20 (AIKosh tables) vs this snapshot. A plausibility check only."""
    a = pd.read_csv(aikosh_csv)
    # The 2019-20 tables use their own management ids (e.g. 16-18 for "Local body"), so the code itself cannot be
    # compared; instead the local-body teacher totals per block must be of the same size (validates code 3 = local body).
    lb = a[a["School_Management_Name"].str.strip().str.lower() == "local body"]
    then = lb.groupby("Block_Name")["Total_Teacher"].sum()
    now = snap.blocks["teachers"]
    out = pd.DataFrame({"teachers_2019_20": then, "teachers_now": now}).dropna()
    out["ratio"] = (out["teachers_now"] / out["teachers_2019_20"]).round(2)
    ok = len(out) == len(now) and bool(out["ratio"].between(0.7, 1.3).all())
    snap.checks.append({"id": "local_body_mapping_vs_2019_20", "ok": ok,
                        "detail": f"{len(out)} blocks matched; teacher ratio now/2019-20 between {out['ratio'].min()} and {out['ratio'].max()}"})
    snap.cross_check = out
    return out


def write_report(snap: Snapshot, out_dir: str | Path, benchmarks: dict | None = None,
                 rationalisation: pd.DataFrame | None = None) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data = snap.to_dict()
    if benchmarks:
        data["benchmarks"] = benchmarks
    if rationalisation is not None and len(rationalisation):
        tot = rationalisation.sum(numeric_only=True)
        data["rationalisation"] = {"rule": "RTE norm for primary-only local-body schools: at least 2 teachers and one per 30 pupils",
                                   "blocks": rationalisation.reset_index().to_dict("records"),
                                   "totals": {k: int(v) for k, v in tot.items()}}
    j = out_dir / "real_snapshot.json"
    j.write_text(json.dumps(data, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    m = out_dir / "real_snapshot.md"
    lines = [f"# REAL PUBLIC DATA: {snap.district} district, UDISE+ {snap.year}",
             "", "Local-body (ZP) elementary schools. Values are self-reported to UDISE+; aggregates only.", "",
             "| Block | Schools | Teachers | PTR | One teacher | No teacher | PTR > 30 | No CRC visit (prev. yr) | Teachers on non-teaching work |",
             "|---|---|---|---|---|---|---|---|---|"]
    for b, r in snap.blocks.sort_values("schools", ascending=False).iterrows():
        n = {k: int(r[k]) for k in ("schools", "teachers", "single_teacher", "zero_teacher", "ptr_over_30", "no_crc_visit",
                                    "non_teaching_teachers")}
        lines.append(f"| {b} | {n['schools']} | {n['teachers']} | {r.ptr} | {n['single_teacher']} | {n['zero_teacher']} | "
                     f"{n['ptr_over_30']} | {n['no_crc_visit']} ({r.pct_no_crc_visit}%) | {n['non_teaching_teachers']} "
                     f"({r.pct_teachers_non_teaching}%) |")
    t = snap.totals
    lines += ["", f"District: {t['schools']} schools, {t['teachers']} teachers, PTR {t['ptr']}, {t['single_teacher']} single-teacher schools, "
              f"{t['no_crc_visit']} schools reporting no CRC visit.", "", "## Checks", ""]
    lines += [f"- {'OK' if c['ok'] else 'FAIL'} `{c['id']}`: {c['detail']}" for c in snap.checks]
    if snap.cross_check is not None:
        lines += ["", "## Cross-check: local-body teachers, UDISE+ 2019-20 (AIKosh) vs now", "",
                  "| Block | 2019-20 | Now | Ratio |", "|---|---|---|---|"]
        lines += [f"| {b} | {int(r.teachers_2019_20)} | {int(r.teachers_now)} | {r.ratio} |" for b, r in snap.cross_check.iterrows()]
    if benchmarks:
        lines += ["", "## PARAKH Rashtriya Sarvekshan 2024, grade 3 (district / Maharashtra / India)", ""]
        for d, v in benchmarks.get("districts", {}).items():
            lines.append(f"- {d}: maths {v['maths']}%, language {v['language']}% (page {v['page']}, verified on the rendered page)")
        st = benchmarks.get("state", {})
        if st:
            lines.append(f"- Maharashtra: maths {st['maths']}%, language {st['language']}%; India: maths {benchmarks['india']['maths']}%, language {benchmarks['india']['language']}%")
    if rationalisation is not None and len(rationalisation):
        from .inputs import rationalisation_markdown

        lines += ["", rationalisation_markdown(rationalisation, snap.district, snap.year).rstrip()]
    m.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return j, m
