"""Run every trust rule over the canonical tables -> flags, missing-data lists, annotations, DATA findings.

Only RED_FLAG / INSUFFICIENT labels count as a school being "flagged". Ingest fixes (dedup, name-matched
links, normalisation) never do. Persisting score jumps are annotations for the cause tester, not flags.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pandas as pd

from .. import evidence as E
from . import rules as R

FLAG_COLUMNS = ["entity_kind", "entity_id", "taluka_id", "rule_id", "label", "metric", "period_from", "period_to",
                "value", "threshold", "detail", "provenance"]


@dataclass
class TrustResult:
    flags: pd.DataFrame
    missing: pd.DataFrame
    school_missing: pd.DataFrame
    annotations: pd.DataFrame
    cleared: list[str]
    talukas: pd.DataFrame
    fragment: dict
    report: dict = field(default_factory=dict)

    def flagged_schools(self) -> set[str]:
        f = self.flags
        return set(f.loc[(f["entity_kind"] == "school") & f["label"].isin(["RED_FLAG", "INSUFFICIENT"]), "entity_id"])


def _prov(rows: pd.DataFrame) -> str:
    cols = ["src_id", "src_sheet", "src_page", "src_section", "src_row"]
    recs = [{k: (None if pd.isna(v) else (int(v) if k in ("src_page", "src_row") else v)) for k, v in r.items()}
            for r in rows[cols].to_dict("records")]
    return json.dumps(recs, ensure_ascii=False)


def run_trust(tables: dict[str, pd.DataFrame], ingest_report: dict | None = None) -> TrustResult:
    schools, att, scores, talukas = tables["schools"], tables["attendance"], tables["scores"], tables["talukas"]
    taluka_of = schools.set_index("udise_code")["taluka_id"]
    flags = []

    def flag(kind, eid, tid, rule, label, metric, pfrom, pto, value, threshold, detail, prov="[]"):
        flags.append(dict(zip(FLAG_COLUMNS, [kind, eid, tid, rule, label, metric, pfrom, pto, value, threshold, detail, prov])))

    runs = R.flat_runs(att)
    for r in runs.itertuples(index=False):
        flag("school", r.udise_code, taluka_of[r.udise_code], "TRUST-FLAT-SCHOOL", "RED_FLAG", "attendance", r.first_month,
             r.last_month, r.n_months, R.FLAT_RUN_MIN_MONTHS, f"{r.n_months} consecutive months at 100%", _prov(r.src_rows))
    jumps = R.attendance_jumps(att)
    for r in jumps.itertuples(index=False):
        rows = att[(att["udise_code"] == r.udise_code) & att["month"].isin([r.from_month, r.to_month])]
        flag("school", r.udise_code, taluka_of[r.udise_code], "TRUST-JUMP-ATTENDANCE", "RED_FLAG", "attendance", r.from_month,
             r.to_month, r.change_pp, R.JUMP_MIN_PP, f"swing {r.change_pp:+.1f} pp (z {r.z:+.1f} vs own history)", _prov(rows))
    sj = R.score_jumps(scores)
    annotations = []
    for r in sj.itertuples(index=False):
        rows = scores[(scores["udise_code"] == r.udise_code) & scores["academic_year"].isin([r.prev_year, r.academic_year])]
        if r.status == "spike":
            flag("school", r.udise_code, taluka_of[r.udise_code], "TRUST-SPIKE-SCORE", "RED_FLAG", "scores", r.prev_year,
                 r.academic_year, round(r.delta, 2), R.SCORE_JUMP_MIN, f"one-year spike {r.delta:+.1f} (z {r.z:+.1f}), reverts", _prov(rows))
        else:
            annotations.append({"udise_code": r.udise_code, "taluka_id": taluka_of[r.udise_code], "metric": "scores",
                                "from_year": r.prev_year, "to_year": r.academic_year, "delta": round(r.delta, 2),
                                "z": round(r.z, 2), "status": r.status})
    school_missing, missing = R.missing_data(schools, att, scores)
    insufficient = school_missing[(school_missing["months_missing"] >= R.MISSING_MONTHS_MIN)
                                  | (school_missing["years_missing"] >= R.MISSING_YEARS_MIN)]
    for r in insufficient.itertuples(index=False):
        flag("school", r.udise_code, r.taluka_id, "TRUST-MISSING-SCHOOL", "INSUFFICIENT", "data", None, None,
             int(max(r.months_missing, r.years_missing)), None,
             f"{r.months_missing} of {r.months_expected} months, {r.years_missing} of {r.years_expected} score years missing")

    # Taluka level.
    flat_schools = set(runs["udise_code"])
    n_by_taluka = schools.groupby("taluka_id").size()
    summary = []
    for tid, n in n_by_taluka.items():
        members = set(schools.loc[schools["taluka_id"] == tid, "udise_code"])
        n_flat = len(members & flat_schools)
        rest_n = len(flat_schools) - n_flat
        rest_share = rest_n / max(len(schools) - n, 1)
        n_ins = int((insufficient["taluka_id"] == tid).sum())
        summary.append({"taluka_id": tid, "n_schools": int(n), "n_flat": n_flat, "flat_share": n_flat / n,
                        "rest_flat_share": rest_share, "n_insufficient": n_ins, "insufficient_share": n_ins / n})
    summary = pd.DataFrame(summary)
    summary["flat_red_flag"] = (summary["n_flat"] >= R.TALUKA_FLAT_MIN_SCHOOLS) & (
        summary["flat_share"] >= R.TALUKA_FLAT_RATIO_MIN * summary["rest_flat_share"])
    summary["insufficient"] = summary["insufficient_share"] >= R.TALUKA_INSUFFICIENT_SHARE
    for r in summary.itertuples(index=False):
        if r.flat_red_flag:
            flag("taluka", r.taluka_id, r.taluka_id, "TRUST-FLAT-TALUKA", "RED_FLAG", "attendance", None, None,
                 round(r.flat_share, 4), R.TALUKA_FLAT_RATIO_MIN, f"{r.n_flat} of {r.n_schools} schools flat vs {r.rest_flat_share:.1%} elsewhere")
        if r.insufficient:
            flag("taluka", r.taluka_id, r.taluka_id, "TRUST-INSUFFICIENT-TALUKA", "INSUFFICIENT", "data", None, None,
                 round(r.insufficient_share, 4), R.TALUKA_INSUFFICIENT_SHARE, f"{r.n_insufficient} of {r.n_schools} schools lack usable data")
    flags_df = pd.DataFrame(flags, columns=FLAG_COLUMNS)
    result = TrustResult(flags=flags_df, missing=missing, school_missing=school_missing,
                         annotations=pd.DataFrame(annotations, columns=["udise_code", "taluka_id", "metric", "from_year", "to_year",
                                                                        "delta", "z", "status"]),
                         cleared=[], talukas=summary, fragment={})
    result.cleared = R.cleared(att, result.flagged_schools())
    result.fragment = evidence_fragment(tables, result, runs)
    fixes = (ingest_report or {}).get("fixes", [])
    result.report = {
        "flags_by_rule": flags_df.groupby("rule_id").size().to_dict() if len(flags_df) else {},
        "flagged_schools": len(result.flagged_schools()),
        "red_flag_talukas": sorted(summary.loc[summary["flat_red_flag"], "taluka_id"]),
        "insufficient_talukas": sorted(summary.loc[summary["insufficient"], "taluka_id"]),
        "cleared_schools": len(result.cleared),
        "missing_school_months": int(len(missing)),
        "score_jump_annotations": int(len(result.annotations)),
        "exact_duplicates_removed_at_ingest": sum(f["count"] for f in fixes if f["kind"] == "exact_duplicates_removed"),
        "conflicting_duplicates": sum(f["count"] for f in fixes if f["kind"] == "conflicting_duplicates"),
        "unresolved_rows_at_ingest": (ingest_report or {}).get("unresolved_rows", 0),
    }
    return result


# ---------- evidence fragment (DATA findings) ----------


def evidence_fragment(tables: dict[str, pd.DataFrame], res: TrustResult, runs: pd.DataFrame) -> dict:
    schools, att, talukas = tables["schools"], tables["attendance"], tables["talukas"]
    src = {"attendance": att["src_id"].iloc[0], "schools": schools["src_id"].iloc[0]}
    entities, sets, periods, numbers, findings = {}, {}, {}, {}, []
    for t in talukas.itertuples(index=False):
        entities[t.taluka_id] = {"kind": "taluka", "code": t.block_code, "name_en": t.taluka, **({"name_mr": t.taluka_mr} if t.taluka_mr else {})}
    names = schools.set_index("udise_code")

    def school_set(sid, rule, codes):
        for c in codes:
            entities[f"S{c}"] = {"kind": "school", "code": c, "name_en": names.at[c, "school_name"], "taluka": names.at[c, "taluka_id"]}
        sets[sid] = {"kind": "school", "rule_id": rule, "members": [f"S{c}" for c in sorted(codes)]}

    def count_schools(tid):
        nid = f"n.count.schools.{tid}"
        n = int((schools["taluka_id"] == tid).sum())
        numbers[nid] = {"value": n, "unit": "count", "of": "schools", "decimals": 0, "entity": tid,
                        "derivation": {"op": "count", "inputs": []},
                        "provenance": [{"kind": "query", "source": src["schools"], "view": "schools", "where": {"taluka_id": tid}, "n_rows": n}]}
        return nid

    summary = res.talukas.set_index("taluka_id")
    for tid, r in summary[summary["flat_red_flag"]].iterrows():
        codes = sorted(set(runs["udise_code"]) & set(schools.loc[schools["taluka_id"] == tid, "udise_code"]))
        tr = runs[runs["udise_code"].isin(codes)]
        first, last = tr["first_month"].mode().iloc[0], tr["last_month"].mode().iloc[0]
        pid = f"p.{first}_{last}"
        periods[pid] = {"kind": "month_range", "from": first, "to": last}
        school_set(f"set.flat_attendance.{tid}", "TRUST-FLAT-TALUKA", codes)
        n_rows = int(((att["taluka_id"] == tid) & (att["attendance_pct"] >= R.FLAT_VALUE_MIN)).sum())
        q = {"kind": "query", "source": src["attendance"], "view": "attendance", "where": {"taluka_id": tid, "attendance_pct": 100.0}, "n_rows": n_rows}
        n_sch = count_schools(tid)
        numbers[f"n.count.months.flat_run.{tid}"] = {"value": int(tr["n_months"].mode().iloc[0]), "unit": "months", "decimals": 0,
                                                     "entity": tid, "derivation": {"op": "max_run", "inputs": []}, "provenance": [q]}
        numbers[f"n.pct.flat_share.{tid}"] = {"value": round(100 * r["flat_share"], 1), "unit": "pct", "decimals": 1, "entity": tid,
                                              "derivation": {"op": "pct", "inputs": [n_sch]}, "provenance": [q]}
        others = [t for t in summary.index if t != tid]
        rest_rows = int((att["taluka_id"].isin(others) & (att["attendance_pct"] >= R.FLAT_VALUE_MIN)).sum())
        numbers[f"n.pct.flat_share.rest.{tid}"] = {
            "value": round(100 * r["rest_flat_share"], 1), "unit": "pct", "decimals": 1, "derivation": {"op": "pct", "inputs": []},
            "provenance": [{"kind": "query", "source": src["attendance"], "view": "attendance",
                            "where": {"taluka_id": others, "attendance_pct": 100.0}, "n_rows": max(rest_rows, 1)}]}
        findings.append({"id": f"F.data.flat.{tid}", "type": "DATA", "label": "RED_FLAG", "rule_id": "TRUST-FLAT-TALUKA",
                         "template_key": "data.flat_attendance",
                         "params": {"taluka": {"entity": tid}, "schools": {"set": f"set.flat_attendance.{tid}"}, "months": {"period": pid},
                                    "n_months": {"number": f"n.count.months.flat_run.{tid}"}, "share": {"number": f"n.pct.flat_share.{tid}"},
                                    "rest_share": {"number": f"n.pct.flat_share.rest.{tid}"}},
                         "criteria": [{"id": "flat_run_min_months", "threshold": R.FLAT_RUN_MIN_MONTHS, "passed": True},
                                      {"id": "taluka_min_flat_schools", "threshold": R.TALUKA_FLAT_MIN_SCHOOLS, "passed": True},
                                      {"id": "share_vs_rest_min_ratio", "threshold": R.TALUKA_FLAT_RATIO_MIN, "passed": True}],
                         "sample": {"n_schools": int(r["n_schools"])},
                         "caveats": [{"template_key": "caveat.flagged_data_excluded", "params": {"schools": {"set": f"set.flat_attendance.{tid}"}}}],
                         "related": []})
    flagged_missing = res.flags[res.flags["rule_id"] == "TRUST-MISSING-SCHOOL"]
    for tid, r in summary[summary["insufficient"]].iterrows():
        codes = sorted(flagged_missing.loc[flagged_missing["taluka_id"] == tid, "entity_id"])
        school_set(f"set.insufficient.{tid}", "TRUST-MISSING-SCHOOL", codes)
        n_sch = count_schools(tid)
        numbers[f"n.pct.insufficient_share.{tid}"] = {"value": round(100 * r["insufficient_share"], 1), "unit": "pct", "decimals": 1,
                                                      "entity": tid, "derivation": {"op": "pct", "inputs": [n_sch]},
                                                      "provenance": [{"kind": "constant", "rule_id": "TRUST-MISSING-SCHOOL", "name": "MISSING_MONTHS_MIN"}]}
        findings.append({"id": f"F.data.insufficient.{tid}", "type": "DATA", "label": "INSUFFICIENT", "rule_id": "TRUST-INSUFFICIENT-TALUKA",
                         "template_key": "data.insufficient",
                         "params": {"taluka": {"entity": tid}, "schools": {"set": f"set.insufficient.{tid}"},
                                    "share": {"number": f"n.pct.insufficient_share.{tid}"}},
                         "criteria": [{"id": "taluka_insufficient_share_min", "threshold": R.TALUKA_INSUFFICIENT_SHARE, "passed": True}],
                         "sample": {"n_schools": int(r["n_schools"])}, "caveats": [], "related": []})
    cleared_by_taluka = pd.Series(res.cleared, dtype=object).map(names["taluka_id"]) if res.cleared else pd.Series(dtype=object)
    for tid in sorted(set(cleared_by_taluka)):
        codes = [c for c, t in zip(res.cleared, cleared_by_taluka) if t == tid]
        school_set(f"set.cleared.{tid}", "TRUST-CLEARED", codes)
        findings.append({"id": f"F.data.cleared.{tid}", "type": "DATA", "label": "CLEARED", "rule_id": "TRUST-CLEARED",
                         "template_key": "data.cleared_low_attendance",
                         "params": {"taluka": {"entity": tid}, "schools": {"set": f"set.cleared.{tid}"}},
                         "criteria": [{"id": "district_bottom_share", "threshold": R.CLEARED_SHARE, "passed": True},
                                      {"id": "no_trust_flag", "passed": True}],
                         "sample": {"n_schools": int(summary.at[tid, "n_schools"])}, "caveats": [], "related": []})
    return {"entities": entities, "entity_sets": sets, "periods": periods, "numbers": numbers, "findings": findings}


def as_pack(fragment: dict, ingest_report: dict, focus: str | None = None) -> dict:
    """Wrap a trust fragment into a valid (DATA-only) evidence pack; the 2B pipeline adds the other findings."""
    sources = [{k: s[k] for k in ("id", "file", "kind", "sha256", "synthetic", "marker_at")} for s in ingest_report["sources"]]
    synthetic = any(s["synthetic"] for s in sources)
    pack = {
        "schema_version": E.SCHEMA_VERSION, "template_registry_version": E.TEMPLATE_REGISTRY_VERSION,
        "engine_version": "0.1.0", "mapping_sha256": ingest_report.get("mapping_sha256"),
        "synthetic": synthetic, "marker": "SYNTHETIC DEMO DATA - NOT REAL" if synthetic else "",
        "scope": {"focus": focus} if focus else {},
        "sources": sources, **fragment,
        "outline": [{"section": "data_warning", "finding_ids": [f["id"] for f in fragment["findings"]]}],
    }
    return E.finalize(pack)
