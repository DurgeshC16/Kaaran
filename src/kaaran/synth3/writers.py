"""Raw v3 files in the formats real systems export (all SYNTHETIC-marked).

- UDISE+ yearly files: the column names of the UDISE+ 2024-25 school-level microdata (prof1, prof2, tch, enr1),
  in the official-export variant keyed by `udise_sch_code` + `school_name` (public microdata uses `pseudocode`).
- BEO office: kendra (cluster) list. ZP establishment: monthly teacher posts with non-teaching duty days.
- State MIS: monthly student attendance, one sheet per month. State assessment: competency-wise results,
  one sheet per round. Visit app: support-visit log (CSV). Training register.
Messiness (recorded in the answer key): UDISE codes stored as numbers (leading zeros lost), percentages as
text with "%", exact duplicate rows, mixed date formats, Marathi/English headers, title rows above headers.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..synth import config as V2
from ..synth.rng import stream
from ..synth.writers import Sheet, write_csv, write_xlsx
from . import SYNTHETIC_MARKER
from . import config as C
from .world import World

CATEGORY_SHARES = (("General", 1, 0.45), ("SC", 2, 0.18), ("ST", 3, 0.04), ("OBC", 4, 0.33))
MONTH_SHEET = {6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec", 1: "Jan", 2: "Feb", 3: "Mar"}


def _names(w: World) -> pd.DataFrame:
    s = w.schools.merge(w.blocks[["block_key", "block"]], on="block_key").merge(
        w.clusters[["cluster_id", "cluster_name"]], on="cluster_id")
    return s


def udise_files(w: World, raw: Path, messy: list[dict]) -> None:
    s = _names(w)
    totals = w.enrolment.assign(t=lambda d: d["boys"] + d["girls"])
    for year in C.YEARS[1:]:  # UDISE+ 2024-25 and 2025-26 (as on 30 September)
        sep = V2.month_label(year, 9)
        prev = C.YEARS[C.YEARS.index(year) - 1]
        title = f"{SYNTHETIC_MARKER} | UDISE+ {year} school data (official export layout; public microdata uses pseudocode)"
        rng = stream(w.seed, f"v3.udise.{year}")
        prof1 = pd.DataFrame({
            "udise_sch_code": s["udise_code"], "school_name": s["school_name"], "state": "MAHARASHTRA",
            "district": C.DISTRICT_NAME, "block": s["block"].str.upper(), "rural_urban": s["rural_urban"],
            "lgd_vill_name": s["village"], "lgd_vill_panchayat_name": s["village"], "school_category": s["school_category"],
            "school_type": 3, "lowclass": s["lowclass"], "highclass": s["highclass"], "managment": s["management"],
            "medium_instr1": 6, "avg_instr_days": rng.integers(205, 231, len(s)),
        })
        write_csv(raw / f"udise_{year}_prof1.csv", title, prof1)
        v = w.visits.assign(y=w.visits["date"].str[:7].map(V2.academic_year_of))
        v = v[v["y"] == prev]
        counts = v.pivot_table(index="udise_code", columns="visitor_role", values="date", aggfunc="count", fill_value=0)
        acad = v[v["purpose"] == "academic"].groupby("udise_code").size()
        prof2 = pd.DataFrame({"udise_sch_code": s["udise_code"]})
        prof2["acad_inspections"] = prof2["udise_sch_code"].map(acad).fillna(0).astype(int)
        for col, role in (("crc_coordinator", "Kendra Pramukh"), ("block_level_officers", "BRC"), ("district_officers", "BEO")):
            prof2[col] = prof2["udise_sch_code"].map(counts.get(role, pd.Series(dtype=int))).fillna(0).astype(int)
        prof2["smc_exists"] = 1
        prof2["smc_smdc_meetings"] = rng.integers(4, 13, len(prof2))
        write_csv(raw / f"udise_{year}_prof2.csv", title, prof2)
        posts = w.posts[w.posts["month"] == sep].set_index("udise_code")
        duty = w.posts[w.posts["academic_year"] == prev].groupby("udise_code")["duty_days"].sum()
        total = s["udise_code"].map(posts["working"]).astype(int)
        female = np.array([int(rng.binomial(t, 0.55)) for t in total])
        contract = np.array([int(rng.binomial(t, C.CONTRACT_SHARE)) for t in total])
        involve = np.minimum(total, np.round(s["udise_code"].map(duty).fillna(0).to_numpy() / 6.0).astype(int))
        tch = pd.DataFrame({"udise_sch_code": s["udise_code"], "total_tch": total, "male": total - female, "female": female,
                            "regular": total - contract, "contract": contract, "class_taught_pr": total,
                            "teacher_involve_non_training_assignment": involve})
        write_csv(raw / f"udise_{year}_tch.csv", title, tch)
        e = totals[totals["academic_year"] == year]
        rows = []
        for code, grp in e.groupby("udise_code", sort=True):
            split = {}
            for cls, b, g in grp[["cls", "boys", "girls"]].itertuples(index=False):
                shares = [x[2] for x in CATEGORY_SHARES]
                split[cls] = (rng.multinomial(b, shares), rng.multinomial(g, shares))
            for k, (_label, item_id, _share) in enumerate(CATEGORY_SHARES):
                row = {"udise_sch_code": code, "item_group": 1, "item_id": item_id}
                for cls in range(1, 9):
                    bb, gg = split.get(cls, ((0,) * 4, (0,) * 4))
                    row[f"c{cls}_b"], row[f"c{cls}_g"] = int(bb[k]), int(gg[k])
                rows.append(row)
        write_csv(raw / f"udise_{year}_enr1.csv", title, pd.DataFrame(rows))


def kendra_list(w: World, raw: Path, messy: list[dict]) -> None:
    s = _names(w).sort_values(["block_key", "cluster_id", "udise_code"])
    frame = pd.DataFrame({"तालुका / Block": s["block"], "केंद्र / Kendra": s["cluster_name"],
                          "केंद्र कोड / Kendra code": s["cluster_id"], "UDISE कोड / UDISE code": s["udise_code"],
                          "शाळेचे नाव / School name": s["school_name"]})
    write_xlsx(raw / "kendra_list.xlsx", [Sheet("Kendra list", [SYNTHETIC_MARKER, "जिल्हा परिषद - केंद्रनिहाय शाळांची यादी (Cluster-wise school list)"],
                                                frame, text_columns=("UDISE कोड / UDISE code",))])


def teacher_posts(w: World, raw: Path, messy: list[dict]) -> None:
    s = _names(w).set_index("udise_code")
    sheets = []
    for year in C.YEARS:
        p = w.posts[w.posts["academic_year"] == year]
        frame = pd.DataFrame({"UDISE Code": p["udise_code"], "School Name": p["udise_code"].map(s["school_name"]),
                              "Month": p["month"], "मंजूर पदे / Sanctioned": p["sanctioned"], "कार्यरत / Working": p["working"],
                              "रिक्त / Vacant": (p["sanctioned"] - p["working"]).clip(lower=0),
                              "अशैक्षणिक कामाचे दिवस / Non-teaching duty days (avg per teacher)": p["duty_days"]})
        sheets.append(Sheet(year, [SYNTHETIC_MARKER, f"Teacher posts (monthly) {year}"], frame, text_columns=("UDISE Code",)))
    write_xlsx(raw / "teacher_posts.xlsx", sheets)


def attendance(w: World, raw: Path, messy: list[dict]) -> None:
    s = _names(w).set_index("udise_code")
    for year in C.YEARS:
        sheets = []
        for m in C.SCHOOL_MONTHS:
            label = V2.month_label(year, m)
            a = w.attendance[w.attendance["month"] == label]
            frame = pd.DataFrame({"UDISE Code": a["udise_code"], "School Name": a["udise_code"].map(s["school_name"]),
                                  "Kendra": a["udise_code"].map(s["cluster_name"]), "पटसंख्या / Enrolled": a["enrolled"],
                                  "उपस्थिती % / Attendance %": a["attendance_pct"]})
            sheets.append(Sheet(f"{MONTH_SHEET[m]}-{label[:4]}", [SYNTHETIC_MARKER, f"Student attendance {MONTH_SHEET[m]} {label[:4]}"],
                                frame, text_columns=("UDISE Code",)))
        write_xlsx(raw / f"student_attendance_{year}.xlsx", sheets)


def assessment(w: World, raw: Path, messy: list[dict]) -> None:
    s = _names(w).set_index("udise_code")
    rng = stream(w.seed, "v3.messy.assessment")
    comp_cols = {code: f"{code} {mr} / {en} %" for code, (_s, en, mr, _o) in C.COMPETENCIES.items()}
    for year in C.YEARS:
        sheets = []
        for rkey, en, mr, _month in C.ROUNDS:
            a = w.assessment[(w.assessment["academic_year"] == year) & (w.assessment["round"] == rkey)]
            wide = a.pivot_table(index=["udise_code", "grade", "assessed"], columns="competency", values="pct").reset_index()
            frame = pd.DataFrame({"UDISE Code": wide["udise_code"], "School Name": wide["udise_code"].map(s["school_name"]),
                                  "Grade / इयत्ता": wide["grade"], "Students assessed / मूल्यमापन झालेले विद्यार्थी": wide["assessed"]})
            for code in C.COMPETENCIES:
                frame[comp_cols[code]] = wide[code].round(1)
            text_cols = ("UDISE Code",)
            if year == "2024-25":  # leading zeros lost: codes stored as numbers
                frame["UDISE Code"] = frame["UDISE Code"].astype("int64")
                text_cols = ()
                messy.append({"file": f"fln_assessment_{year}.xlsx", "kind": "udise_leading_zero_loss"})
            if year == "2025-26" and rkey == "ML":  # percentages typed as text with a % sign
                for code in C.COMPETENCIES:
                    frame[comp_cols[code]] = frame[comp_cols[code]].map(lambda v: f"{v:.1f}%")
                messy.append({"file": f"fln_assessment_{year}.xlsx", "sheet": f"{en}", "kind": "percent_as_text"})
            dup = frame.iloc[rng.choice(len(frame), size=3, replace=False)]
            frame = pd.concat([frame, dup]).sort_values("UDISE Code", kind="stable").reset_index(drop=True)
            messy.append({"file": f"fln_assessment_{year}.xlsx", "sheet": en, "kind": "exact_duplicates", "count": 3})
            sheets.append(Sheet(f"{en} ({mr})", [SYNTHETIC_MARKER, f"FLN assessment {year} - {en} - Grade {C.GRADE}"],
                                frame, text_columns=text_cols))
        write_xlsx(raw / f"fln_assessment_{year}.xlsx", sheets)


def visit_log(w: World, raw: Path, messy: list[dict]) -> None:
    s = _names(w).set_index("udise_code")
    v = w.visits
    dates = pd.to_datetime(v["date"])
    shown = np.where(v.index % 9 == 0, dates.dt.strftime("%d/%m/%y"), dates.dt.strftime("%d-%m-%Y"))
    messy.append({"file": "visit_log.csv", "kind": "mixed_date_formats", "formats": ["%d-%m-%Y", "%d/%m/%y"]})
    frame = pd.DataFrame({"Visit date": shown, "UDISE": v["udise_code"], "School": v["udise_code"].map(s["school_name"]),
                          "Visitor": v["visitor_role"], "Purpose": v["purpose"],
                          "Classroom observed": np.where(v["classroom_observed"], "Yes", "No")})
    write_csv(raw / "visit_log.csv", f"{SYNTHETIC_MARKER} | School support visits (visit app export)", frame)


def training(w: World, raw: Path, messy: list[dict]) -> None:
    s = _names(w).set_index("udise_code")
    t = w.training
    frame = pd.DataFrame({"UDISE Code": t["udise_code"], "School Name": t["udise_code"].map(s["school_name"]),
                          "Training": t["topic"], "Start date": t["date"], "Days": t["days"],
                          "Teachers trained": t["teachers_trained"]})
    write_xlsx(raw / "teacher_training.xlsx", [Sheet("Training", [SYNTHETIC_MARKER, "Teacher training register"], frame,
                                                     text_columns=("UDISE Code",))])


def write_raw(w: World, raw: Path) -> list[dict]:
    raw.mkdir(parents=True, exist_ok=True)
    messy: list[dict] = []
    for fn in (udise_files, kendra_list, teacher_posts, attendance, assessment, visit_log, training):
        fn(w, raw, messy)
    return messy
