"""Evidence pack contract: the engines' only output; the Brief Writer and UI read nothing else.

See docs/EVIDENCE_SCHEMA.md. A pack holds structured numbers with provenance, entities, sets,
periods and wording template keys; never prose.

- `validate(pack)` returns a list of problems (empty = valid).
- `finalize(pack)` fills every number's `display` strings and `direction` (one formatter for all).
- `llm_view(pack)` is the only projection that may be sent to an LLM (CLAUDE.md rule 5).
"""

from __future__ import annotations

import copy
import json
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

SCHEMA_VERSION = "1.0"
TEMPLATE_REGISTRY_VERSION = "2"

FINDING_TYPES = ("TREND", "CAUSE", "TWIN", "DATA", "ACTION")
LABELS = ("STRONG", "WEAK", "INSUFFICIENT", "RED_FLAG", "LEARN_FROM", "ACTION", "RULED_OUT", "CLEARED")
LABELS_BY_TYPE = {
    "TREND": ("STRONG", "WEAK", "INSUFFICIENT"),
    "CAUSE": ("STRONG", "WEAK", "RULED_OUT", "INSUFFICIENT"),
    "TWIN": ("LEARN_FROM", "INSUFFICIENT"),
    "DATA": ("RED_FLAG", "INSUFFICIENT", "CLEARED"),
    "ACTION": ("ACTION",),
}
HYPOTHESES = ("vacancy", "election", "infrastructure", "attendance")
OUTLINE_SECTIONS = ("trend", "election_check", "main_cause", "twin", "data_warning", "action", "appendix")
ACTOR_ROLES = ("DEO", "BEO", "KENDRA_PRAMUKH")
ENTITY_KINDS = ("district", "taluka", "cluster", "school")
SOURCE_KINDS = ("xlsx", "csv", "pdf")
PERIOD_KINDS = ("academic_year", "year_range", "month", "month_range")
PARAM_KINDS = ("number", "entity", "set", "period", "text_key")

UNITS = ("score", "score_change", "pct", "pct_point_change", "count", "rank", "t_stat", "corr", "months", "index")
CHANGE_UNITS = ("score_change", "pct_point_change")
COUNT_OF = ("schools", "talukas", "months", "years", "teachers", "students", "rows")

# Canonical DuckDB views (built in Stage 2). Columns mirror the clean truth tables plus ids;
# every view also carries src_id, src_sheet, src_page, src_section, src_row.
CANONICAL_VIEWS = {
    "talukas": ("taluka_id", "block_code", "taluka", "taluka_mr", "n_schools", "poverty_index"),
    "schools": ("udise_code", "short_code", "school_name", "village", "taluka_id", "cluster_code", "cluster",
                "enrol_std1", "enrol_std2", "enrol_std3", "enrol_std4", "enrol_std5", "enrol_total",
                "toilets", "library", "drinking_water", "classrooms"),
    "scores": ("udise_code", "taluka_id", "academic_year", "std", "subject", "mean_score", "students_appeared"),
    "attendance": ("udise_code", "taluka_id", "academic_year", "month", "enrolled", "present_avg", "attendance_pct"),
    "teacher_posts": ("udise_code", "taluka_id", "academic_year", "subject", "sanctioned", "working"),
    "election_duty": ("taluka_id", "academic_year", "month", "deployed_pct"),
}

# Rule ids; each must be described in docs/CONFIDENCE_RULES.md.
RULE_IDS = (
    "TREND-STRONG", "TREND-WEAK", "TREND-INSUFFICIENT",
    "CAUSE-SCHOOL-EXPOSURE", "CAUSE-ELECTION", "CAUSE-CORRELATION", "CAUSE-RULED-OUT", "CAUSE-INSUFFICIENT",
    "TWIN-LEARN-FROM", "TWIN-NONE",
    "TRUST-FLAT-SCHOOL", "TRUST-FLAT-TALUKA", "TRUST-JUMP-ATTENDANCE", "TRUST-SPIKE-SCORE",
    "TRUST-MISSING-SCHOOL", "TRUST-INSUFFICIENT-TALUKA", "TRUST-DUPLICATE-CONFLICT", "TRUST-CLEARED",
    "ACTION-CATALOG",
)

# Wording templates: key -> required params. The Brief Writer owns the Marathi/English sentences.
TEMPLATE_KEYS = {
    "trend.decline_rank": {"taluka", "period", "score_from", "score_to", "change", "rank_from", "rank_to"},
    "trend.rise_rank": {"taluka", "period", "score_from", "score_to", "change", "rank_from", "rank_to"},
    "trend.no_clear_change": {"taluka", "period", "change"},
    "cause.election.similar_blocks_no_drop": {"taluka", "period", "focus_change", "similar", "n_similar_no_drop"},
    "cause.vacancy.concentrated": {"taluka", "subject", "schools", "since", "group_change", "others_change", "share_of_decline"},
    "cause.infra.no_link": {"taluka", "r", "lowest_infra_taluka", "lowest_infra_change"},
    "cause.attendance.no_link": {"taluka", "r"},
    "twin.learn_from": {"twin", "focus", "twin_change", "twin_rank_from", "twin_rank_to", "n_schools_twin", "n_schools_focus"},
    "data.flat_attendance": {"taluka", "schools", "months", "n_months", "share", "rest_share"},
    "data.insufficient": {"taluka", "schools", "share"},
    "data.cleared_low_attendance": {"taluka", "schools"},
    "action.redeploy_teachers": {"taluka", "subject", "schools"},
    "action.exposure_visit": {"twin", "focus"},
    "action.verify_registers": {"taluka", "schools"},
    "action.collect_missing_data": {"taluka", "schools"},
    # v2: association wording (WEAK), "no link" wording (RULED_OUT) and an inconclusive key (INSUFFICIENT).
    # Only cause.vacancy.concentrated is causal in tone, and it is used only when the STRONG criteria pass.
    "trend.decline_weak": {"taluka", "period", "score_from", "score_to", "change", "rank_from", "rank_to"},
    "cause.vacancy.associated": {"taluka", "subject", "schools", "group_change", "others_change"},
    "cause.vacancy.no_link": {"taluka", "subject", "group_change", "others_change"},
    "cause.election.associated": {"taluka", "period", "focus_change", "similar", "n_similar_no_drop"},
    "cause.election.no_link": {"taluka", "period", "focus_change"},
    "cause.infra.associated": {"taluka", "r"},
    "cause.attendance.associated": {"taluka", "r"},
    "cause.inconclusive": {"taluka", "hypothesis"},
    "twin.none_found": {"focus"},
}
CAUSAL_TEMPLATE_KEYS = {"cause.vacancy.concentrated"}  # only with a STRONG label
CAVEAT_KEYS = {
    "caveat.synthetic_data": set(),
    "caveat.associated_not_caused": set(),
    "caveat.concentrated_in_few_schools": {"schools"},
    "caveat.poverty_not_available": set(),
    "caveat.static_infra_snapshot": set(),
    "caveat.small_sample": set(),
    "caveat.flagged_data_excluded": {"schools"},
}
TEXT_KEYS = {"subject.maths", "subject.language", "question.why_decline",
             "hypothesis.vacancy", "hypothesis.election", "hypothesis.infrastructure", "hypothesis.attendance"}
DERIVATION_OPS = ("mean", "sum", "count", "count_distinct", "diff", "ratio", "pct", "share_of_decline", "rank_desc",
                  "paired_t", "corr", "max_run", "set_size", "mean_change", "count_where")

MR_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")


def label_badge_key(finding_type: str, label: str) -> str:
    """Badge text key; the Marathi wording may differ per type (e.g. WEAK cause vs WEAK trend)."""
    return f"label.{finding_type}.{label}"


# ---------- formatting ----------


def _group_indian(int_part: str) -> str:
    if len(int_part) <= 3:
        return int_part
    head, tail = int_part[:-3], int_part[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups + [tail])


def format_number(value: float, unit: str, decimals: int) -> dict[str, str]:
    """Display strings (magnitude only for change units; direction is a separate field)."""
    v = abs(value) if unit in CHANGE_UNITS else value
    q = Decimal(str(v)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    sign = "-" if q < 0 else ""
    text = f"{abs(q):.{decimals}f}"
    int_part, _, frac = text.partition(".")
    en = sign + _group_indian(int_part) + (f".{frac}" if frac else "")
    if unit == "pct":
        en += "%"
    return {"en": en, "mr": en.translate(MR_DIGITS)}


def _direction(value: float) -> str:
    return "down" if value < 0 else "up" if value > 0 else "flat"


def finalize(pack: dict) -> dict:
    """Return a copy with display strings and directions filled in by the one formatter."""
    out = copy.deepcopy(pack)
    for n in out.get("numbers", {}).values():
        n["display"] = format_number(n["value"], n["unit"], n["decimals"])
        if n["unit"] in CHANGE_UNITS:
            n["direction"] = _direction(n["value"])
    return out


def load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump(pack: dict, path: str | Path) -> None:
    Path(path).write_text(json.dumps(pack, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# ---------- LLM projection (rule 5) ----------


def llm_view(pack: dict) -> dict:
    """Aggregates only: no school entities, no set members, no per-school numbers, no raw row lists."""
    v = copy.deepcopy(pack)
    v["sources"] = [{k: s[k] for k in ("id", "file", "kind", "synthetic") if k in s} for s in v["sources"]]
    school_ids = {eid for eid, e in v["entities"].items() if e["kind"] == "school"}
    v["entities"] = {eid: e for eid, e in v["entities"].items() if eid not in school_ids}
    v["entity_sets"] = {
        sid: {"kind": s["kind"], "rule_id": s["rule_id"], "size": len(s["members"])} for sid, s in v["entity_sets"].items()
    }
    numbers = {}
    for nid, n in v["numbers"].items():
        if n.get("entity") in school_ids:
            continue
        n["provenance"] = [_summarise_provenance(p) for p in n.get("provenance", [])]
        numbers[nid] = n
    v["numbers"] = numbers
    return v


def _summarise_provenance(p: dict) -> dict:
    if p["kind"] == "cells":
        n_rows = len(p.get("rows", [])) or len(p.get("sr_no", []))
        return {k: p[k] for k in ("kind", "source", "sheet", "page", "columns") if k in p} | {"n_rows": n_rows}
    if p["kind"] == "query":
        return {k: p[k] for k in ("kind", "source", "view", "n_rows") if k in p}
    return dict(p)


# ---------- validation ----------


def _ref_ok(kind: str, value, pack: dict) -> bool:
    if kind == "number":
        return value in pack["numbers"]
    if kind == "entity":
        return value in pack["entities"]
    if kind == "set":
        return value in pack["entity_sets"]
    if kind == "period":
        return value in pack["periods"]
    return value in TEXT_KEYS


def _check_params(params: dict, required: set[str], where: str, pack: dict, p: list[str]) -> None:
    missing = required - set(params)
    if missing:
        p.append(f"{where}: params missing {sorted(missing)}")
    for name, ref in params.items():
        if not (isinstance(ref, dict) and len(ref) == 1 and next(iter(ref)) in PARAM_KINDS):
            p.append(f"{where}.params.{name}: must be {{kind: id}} with kind in {PARAM_KINDS}")
            continue
        kind, value = next(iter(ref.items()))
        if not _ref_ok(kind, value, pack):
            p.append(f"{where}.params.{name}: unknown {kind} {value!r}")


def _check_provenance(prov: dict, sources: dict, where: str, p: list[str]) -> None:
    kind = prov.get("kind")
    if kind == "constant":
        if prov.get("rule_id") not in RULE_IDS or not prov.get("name"):
            p.append(f"{where}: constant provenance needs a known rule_id and a name")
        return
    src = sources.get(prov.get("source"))
    if src is None:
        p.append(f"{where}: unknown source {prov.get('source')!r}")
        return
    if kind == "query":
        view = prov.get("view")
        if view not in CANONICAL_VIEWS:
            p.append(f"{where}: unknown view {view!r}")
            return
        bad = set(prov.get("where", {})) - set(CANONICAL_VIEWS[view])
        if bad:
            p.append(f"{where}: where-fields {sorted(bad)} not in view {view}")
        for value in prov.get("where", {}).values():
            if not isinstance(value, (str, int, float, list)):
                p.append(f"{where}: where values must be scalars or lists (equality / IN only)")
        if not (isinstance(prov.get("n_rows"), int) and prov["n_rows"] >= 1):
            p.append(f"{where}: query provenance needs n_rows >= 1")
    elif kind == "cells":
        if src["kind"] == "xlsx" and not prov.get("sheet"):
            p.append(f"{where}: xlsx cells need 'sheet'")
        if src["kind"] == "pdf":
            if not (prov.get("page") and prov.get("section") and prov.get("sr_no")):
                p.append(f"{where}: pdf cells need page, section and sr_no")
        elif not prov.get("rows"):
            p.append(f"{where}: cells need 'rows' (1-based physical rows / lines)")
        for r in prov.get("rows", []) + prov.get("sr_no", []):
            if not (isinstance(r, int) and r >= 1):
                p.append(f"{where}: row numbers must be positive integers")
                break
    else:
        p.append(f"{where}: provenance kind must be cells, query or constant")


def validate(pack: dict) -> list[str]:
    p: list[str] = []
    required = ("schema_version", "template_registry_version", "synthetic", "scope", "sources", "entities",
                "entity_sets", "periods", "numbers", "findings", "outline")
    for key in required:
        if key not in pack:
            p.append(f"missing top-level field {key!r}")
    if p:
        return p
    if pack["schema_version"] != SCHEMA_VERSION:
        p.append(f"schema_version must be {SCHEMA_VERSION}")
    sources = {s.get("id"): s for s in pack["sources"]}
    if len(sources) != len(pack["sources"]):
        p.append("duplicate source ids")
    for s in pack["sources"]:
        if s.get("kind") not in SOURCE_KINDS:
            p.append(f"source {s.get('id')}: kind must be one of {SOURCE_KINDS}")
        if not isinstance(s.get("synthetic"), bool):
            p.append(f"source {s.get('id')}: synthetic flag (bool) required")
    if pack["synthetic"] != any(s.get("synthetic") for s in pack["sources"]):
        p.append("pack.synthetic must equal any(source.synthetic)")
    if pack["synthetic"] and "SYNTHETIC" not in str(pack.get("marker", "")):
        p.append("synthetic packs need a marker containing SYNTHETIC")

    for eid, e in pack["entities"].items():
        if e.get("kind") not in ENTITY_KINDS or not e.get("name_en"):
            p.append(f"entity {eid}: needs kind in {ENTITY_KINDS} and name_en")
        for parent in ("taluka", "cluster"):
            if parent in e and e[parent] not in pack["entities"]:
                p.append(f"entity {eid}: unknown {parent} {e[parent]!r}")
    for sid, s in pack["entity_sets"].items():
        if s.get("kind") not in ENTITY_KINDS or s.get("rule_id") not in RULE_IDS:
            p.append(f"set {sid}: needs kind and a known rule_id")
        for m in s.get("members", []):
            if pack["entities"].get(m, {}).get("kind") != s.get("kind"):
                p.append(f"set {sid}: member {m!r} missing or not a {s.get('kind')}")
                break
    for pid, per in pack["periods"].items():
        if per.get("kind") not in PERIOD_KINDS or "from" not in per or "to" not in per:
            p.append(f"period {pid}: needs kind in {PERIOD_KINDS}, from and to")

    for nid, n in pack["numbers"].items():
        where = f"number {nid}"
        unit = n.get("unit")
        if unit not in UNITS:
            p.append(f"{where}: unit must be one of {UNITS}")
            continue
        if not isinstance(n.get("value"), (int, float)) or isinstance(n.get("value"), bool):
            p.append(f"{where}: value must be a number")
            continue
        if not isinstance(n.get("decimals"), int):
            p.append(f"{where}: decimals (int) required")
            continue
        if unit == "count" and n.get("of") not in COUNT_OF:
            p.append(f"{where}: count needs 'of' in {COUNT_OF}")
        if unit == "rank" and not isinstance(n.get("out_of"), int):
            p.append(f"{where}: rank needs integer 'out_of'")
        if n.get("display") != format_number(n["value"], unit, n["decimals"]):
            p.append(f"{where}: display missing or stale (run evidence.finalize)")
        if unit in CHANGE_UNITS and n.get("direction") != _direction(n["value"]):
            p.append(f"{where}: direction missing or wrong")
        if "entity" in n and n["entity"] not in pack["entities"]:
            p.append(f"{where}: unknown entity {n['entity']!r}")
        deriv = n.get("derivation", {})
        if deriv and deriv.get("op") not in DERIVATION_OPS:
            p.append(f"{where}: derivation op must be one of {DERIVATION_OPS}")
        inputs = deriv.get("inputs", [])
        for inp in inputs:
            if inp not in pack["numbers"]:
                p.append(f"{where}: derivation input {inp!r} unknown")
        if not n.get("provenance") and not inputs:
            p.append(f"{where}: needs provenance or derivation.inputs")
        for i, pr in enumerate(n.get("provenance", [])):
            _check_provenance(pr, sources, f"{where}.provenance[{i}]", p)
        # A displayed change must equal the difference of its displayed inputs (to one last-digit unit).
        if deriv.get("op") == "diff" and len(inputs) == 2 and all(i in pack["numbers"] for i in inputs):
            a, b = (pack["numbers"][i] for i in inputs)
            step = Decimal(1).scaleb(-n["decimals"])
            da = Decimal(str(a["value"])).quantize(step, rounding=ROUND_HALF_UP)
            db = Decimal(str(b["value"])).quantize(step, rounding=ROUND_HALF_UP)
            dn = Decimal(str(n["value"])).quantize(step, rounding=ROUND_HALF_UP)
            if abs((da - db) - dn) > step:
                p.append(f"{where}: displayed change differs from the difference of its displayed inputs")

    finding_ids = [f.get("id") for f in pack["findings"]]
    if len(set(finding_ids)) != len(finding_ids):
        p.append("duplicate finding ids")
    for f in pack["findings"]:
        fid = f.get("id")
        ftype = f.get("type")
        if ftype not in FINDING_TYPES:
            p.append(f"{fid}: type must be one of {FINDING_TYPES}")
            continue
        if f.get("label") not in LABELS_BY_TYPE[ftype]:
            p.append(f"{fid}: label {f.get('label')!r} not allowed for {ftype} (allowed {LABELS_BY_TYPE[ftype]})")
        if f.get("rule_id") not in RULE_IDS:
            p.append(f"{fid}: unknown rule_id {f.get('rule_id')!r}")
        key = f.get("template_key")
        if key not in TEMPLATE_KEYS:
            p.append(f"{fid}: unknown template_key {key!r}")
        else:
            _check_params(f.get("params", {}), TEMPLATE_KEYS[key], fid, pack, p)
        if key in CAUSAL_TEMPLATE_KEYS and f.get("label") != "STRONG":
            p.append(f"{fid}: causal wording {key!r} is only allowed with a STRONG label")
        if ftype == "CAUSE" and f.get("hypothesis") not in HYPOTHESES:
            p.append(f"{fid}: CAUSE needs hypothesis in {HYPOTHESES}")
        for c in f.get("criteria", []):
            if "number" in c and c["number"] not in pack["numbers"]:
                p.append(f"{fid}: criterion {c.get('id')} refers to unknown number")
        for i, cav in enumerate(f.get("caveats", [])):
            ck = cav.get("template_key")
            if ck not in CAVEAT_KEYS:
                p.append(f"{fid}: unknown caveat {ck!r}")
            else:
                _check_params(cav.get("params", {}), CAVEAT_KEYS[ck], f"{fid}.caveats[{i}]", pack, p)
        for r in f.get("related", []):
            if r not in finding_ids:
                p.append(f"{fid}: related finding {r!r} unknown")
        if ftype == "ACTION":
            act = f.get("action", {})
            if act.get("actor_role") not in ACTOR_ROLES:
                p.append(f"{fid}: action.actor_role must be one of {ACTOR_ROLES}")
            if not act.get("based_on") or any(b not in finding_ids for b in act["based_on"]):
                p.append(f"{fid}: action.based_on must list existing findings")
            if "targets" in act and act["targets"] not in pack["entity_sets"]:
                p.append(f"{fid}: action.targets must be a set id")

    for item in pack["outline"]:
        if item.get("section") not in OUTLINE_SECTIONS:
            p.append(f"outline: unknown section {item.get('section')!r}")
        for fid in item.get("finding_ids", []):
            if fid not in finding_ids:
                p.append(f"outline: unknown finding {fid!r}")
    return p


def contains_identifiers(obj) -> list[str]:
    """School-level identifiers (9-11 digit codes) found anywhere in obj; used to test llm_view."""
    text = json.dumps(obj, ensure_ascii=False)
    return re.findall(r"(?<![0-9a-f])\d{9,11}(?![0-9a-f])", text)


# ---------- builder used by the engines ----------


class Builder:
    """Accumulates entities, sets, periods, numbers and findings with deterministic ids."""

    def __init__(self, tables: dict) -> None:
        self.tables = tables
        self.entities: dict = {}
        self.entity_sets: dict = {}
        self.periods: dict = {}
        self.numbers: dict = {}
        self.findings: list = []
        t = tables["talukas"]
        self._talukas = {r.taluka_id: r for r in t.itertuples(index=False)}
        self._schools = tables["schools"].set_index("udise_code")

    def source(self, view: str) -> str:
        return str(self.tables[view]["src_id"].iloc[0])

    def taluka(self, tid: str) -> str:
        r = self._talukas[tid]
        self.entities[tid] = {"kind": "taluka", "code": r.block_code, "name_en": r.taluka,
                              **({"name_mr": r.taluka_mr} if isinstance(r.taluka_mr, str) and r.taluka_mr else {})}
        return tid

    def school_set(self, sid: str, rule_id: str, codes) -> str:
        for c in codes:
            self.entities[f"S{c}"] = {"kind": "school", "code": c, "name_en": self._schools.at[c, "school_name"],
                                      "taluka": self.taluka(self._schools.at[c, "taluka_id"])}
        self.entity_sets[sid] = {"kind": "school", "rule_id": rule_id, "members": [f"S{c}" for c in sorted(codes)]}
        return sid

    def taluka_set(self, sid: str, rule_id: str, tids) -> str:
        self.entity_sets[sid] = {"kind": "taluka", "rule_id": rule_id, "members": [self.taluka(t) for t in sorted(tids)]}
        return sid

    def period(self, kind: str, frm: str, to: str) -> str:
        pid = f"p.{frm}" if frm == to else f"p.{frm}_{to}"
        self.periods[pid] = {"kind": kind, "from": frm, "to": to}
        return pid

    def query(self, view: str, where: dict, n_rows: int) -> dict:
        return {"kind": "query", "source": self.source(view), "view": view, "where": where, "n_rows": max(int(n_rows), 1)}

    @staticmethod
    def constant(rule_id: str, name: str) -> dict:
        return {"kind": "constant", "rule_id": rule_id, "name": name}

    def number(self, nid: str, value, unit: str, decimals: int, prov=None, op=None, inputs=None, entity=None, n=None, **extra) -> str:
        d = {"value": round(float(value), decimals) if decimals else int(round(float(value))), "unit": unit, "decimals": decimals, **extra}
        if n is not None:
            d["n"] = int(n)
        if entity:
            d["entity"] = entity
        if op:
            d["derivation"] = {"op": op, "inputs": list(inputs or [])}
        d["provenance"] = list(prov or [])
        self.numbers[nid] = d
        return nid

    def finding(self, **f) -> dict:
        f.setdefault("criteria", [])
        f.setdefault("sample", {})
        f.setdefault("caveats", [])
        f.setdefault("related", [])
        self.findings.append(f)
        return f

    def fragment(self) -> dict:
        return {"entities": self.entities, "entity_sets": self.entity_sets, "periods": self.periods,
                "numbers": self.numbers, "findings": self.findings}


def merge_fragments(*fragments: dict) -> dict:
    out = {"entities": {}, "entity_sets": {}, "periods": {}, "numbers": {}, "findings": []}
    for fr in fragments:
        for k in ("entities", "entity_sets", "periods", "numbers"):
            out[k].update(fr.get(k, {}))
        out["findings"] += fr.get("findings", [])
    return out


def prune(pack: dict) -> dict:
    """Drop sets, entities, periods and numbers that no finding (or the scope) references."""
    out = copy.deepcopy(pack)
    refs = {"number": set(), "entity": set(), "set": set(), "period": set()}

    def walk_params(params):
        for ref in params.values():
            kind, value = next(iter(ref.items()))
            if kind in refs:
                refs[kind].add(value)

    for f in out["findings"]:
        walk_params(f.get("params", {}))
        for c in f.get("caveats", []):
            walk_params(c.get("params", {}))
        for c in f.get("criteria", []):
            if "number" in c:
                refs["number"].add(c["number"])
        if f.get("action", {}).get("targets"):
            refs["set"].add(f["action"]["targets"])
    stack = list(refs["number"])
    while stack:  # numbers referenced through derivations
        for inp in out["numbers"].get(stack.pop(), {}).get("derivation", {}).get("inputs", []):
            if inp not in refs["number"]:
                refs["number"].add(inp)
                stack.append(inp)
    out["numbers"] = {k: v for k, v in out["numbers"].items() if k in refs["number"]}
    out["entity_sets"] = {k: v for k, v in out["entity_sets"].items() if k in refs["set"]}
    out["periods"] = {k: v for k, v in out["periods"].items() if k in refs["period"] or k == out["scope"].get("period")}
    keep = set(refs["entity"]) | {out["scope"].get("district"), out["scope"].get("focus")}
    keep |= {m for s in out["entity_sets"].values() for m in s["members"]}
    keep |= {n["entity"] for n in out["numbers"].values() if "entity" in n}
    keep |= {out["entities"][k]["taluka"] for k in list(keep) if k in out["entities"] and "taluka" in out["entities"][k]}
    out["entities"] = {k: v for k, v in out["entities"].items() if k in keep}
    return out
