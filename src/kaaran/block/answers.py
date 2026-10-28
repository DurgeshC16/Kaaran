"""Direct answers (block lens): the officer's actual question answered first, computed by code, then the brief.

"How many schools in Pandharpur?", "What is the attendance in Sangola?", "PTR in Karmala?", "Which block needs the most
attention?", "What about Bhalwad Khurd kendra?". Every figure is computed here from the canonical tables (trusted data
only where trust matters), registered in the evidence pack with provenance (so it is clickable in the web brief), and
phrased by fixed Marathi/English templates with placeholders. No LLM writes these sentences.
"""

from __future__ import annotations

import difflib
import re
import unicodedata

import pandas as pd

from .. import evidence as E
from .trust import BlockTrust

ATT_LOW = 75.0
PTR_NORM = 30.0

# metric -> words that ask for it (normalised question text; Marathi, English, transliterated)
METRIC_WORDS = {
    "schools": ["how many schools", "number of schools", "school count", "total schools", "schools in", "किती शाळा",
                "शाळांची संख्या", "शाळा किती", "एकूण शाळा", "kiti shala", "shala kiti", "shalanchi sankhya"],
    "teachers": ["teacher", "शिक्षक", "shikshak", "staff", "vacanc", "रिक्त", "vacant", "sanctioned", "posts", "मंजूर", "पदे"],
    "ptr": ["ptr", "pupil teacher", "pupil-teacher", "student teacher ratio", "विद्यार्थी शिक्षक", "विद्यार्थी-शिक्षक"],
    "attendance": ["attendance", "हजेरी", "उपस्थिती", "hajeri", "absent", "गैरहजर"],
    "learning": ["result", "score", "learning", "निकाल", "गुण", "maths", "math", "गणित", "ganit", "language", "भाषा", "reading",
                 "वाचन", "nikal"],
    "visits": ["visit", "भेट", "kendra pramukh", "केंद्रप्रमुख", "crc", "mentor"],
    "data_quality": ["data", "आकडेवारी", "reliable", "विश्वास", "record", "नोंद", "fake", "बनावट"],
    "actions": ["what should i do", "what to do", "काय करावे", "काय करू", "action", "कृती", "kay karave", "next step"],
    # only real "where should I look first" words; "which block has the best X" is a ranking by X (see superlative())
    "attention_rank": ["most attention", "need attention", "needs attention", "attention first", "worst block", "worst taluka",
                       "सर्वात जास्त लक्ष", "जास्त लक्ष", "लक्ष द्यावे", "लक्ष देण्याची", "मागे आहे", "mage aahe", "sarvat jast laksh"],
}
SCHOOL_WORDS = ("school", "शाळा", "shala")
COUNT_WORDS = ("how many", "kiti", "किती", "number", "total", "sankhya", "संख्या", "count", "एकूण")
SUFFIX_STARTS = {"budruk": "budr", "khurd": "khur"}  # village suffixes (बुद्रुक / खुर्द romanise to budruk / khurd)
CLUSTER_MATCH = 0.88  # minimum similarity for a kendra name
CLUSTER_MARGIN = 0.03  # a runner-up this close means the question is ambiguous


def normalise(text: str) -> str:
    t = unicodedata.normalize("NFC", text.lower())
    return " ".join(re.sub(r"[^\wऀ-ॿ -]", " ", t).split())


def metrics_asked(question: str) -> list[str]:
    q = normalise(question).replace("गुणवत्ता", "quality")  # "गुण" (marks) must not fire on "गुणवत्ता" (quality)
    found = [m for m, words in METRIC_WORDS.items() if any(w in q for w in words)]
    if "schools" not in found and any(w in q for w in SCHOOL_WORDS) and any(w in q for w in COUNT_WORDS):
        found.insert(0, "schools")  # "pandharpur madhil shala kiti aahet"
    return found


# ---------- Devanagari -> rough Latin, to match place names heard by speech-to-text against Latin names ----------
_DEV = {"अ": "a", "आ": "a", "इ": "i", "ई": "i", "उ": "u", "ऊ": "u", "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "ऋ": "ru",
        "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
        "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
        "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r", "ल": "l", "ळ": "l", "व": "w",
        "श": "sh", "ष": "sh", "स": "s", "ह": "h", "ा": "a", "ि": "i", "ी": "i", "ु": "u", "ू": "u", "े": "e", "ै": "ai",
        "ो": "o", "ौ": "au", "ृ": "ru", "ं": "n", "ँ": "n", "ः": "h", "्": "", "़": ""}
_CONSONANTS = set("कखगघङचछजझञटठडढणतथदधनपफबभमयरलळवशषसह")
_SIGNS = set("ािीुूेैोौृ्ंँः")


def romanise(text: str) -> str:
    """Very rough Devanagari -> Latin (adds the inherent 'a' after consonants), enough for fuzzy name matching."""
    out = []
    chars = list(unicodedata.normalize("NFC", text))
    for i, ch in enumerate(chars):
        out.append(_DEV.get(ch, ch))
        nxt = chars[i + 1] if i + 1 < len(chars) else ""
        if ch in _CONSONANTS and (nxt in _CONSONANTS or nxt in "ंँः"):  # inherent vowel: "पं" -> "pan", "कर" -> "kar"
            out.append("a")
    return "".join(out).lower()


def _simple(s: str) -> str:
    s = romanise(s) if re.search(r"[ऀ-ॿ]", s) else s.lower()
    s = s.replace("w", "v").replace("oo", "u").replace("ee", "i")
    return re.sub(r"[^a-z]", "", s)


def find_cluster(question: str, clusters: pd.DataFrame, block: str | None = None) -> str | None:
    """Cluster id named in the question (Latin or Devanagari spelling), or None when no kendra (or more than one) fits.

    The full village name is compared with the same number of question words; the village stem without
    Budruk/Khurd also counts (slightly lower) unless the officer said the other suffix. Close calls return None.
    """
    tokens = [_simple(t) for t in normalise(question).split()]
    said = {s for s, starts in SUFFIX_STARTS.items() if any(t.startswith(starts) for t in tokens)}
    cands = clusters if block is None else clusters[clusters["block"] == block]
    best_by: dict[str, float] = {}
    for r in cands.itertuples(index=False):
        words = str(r.cluster_name).replace(" Kendra", "").split()
        full = _simple(" ".join(words))
        suffix = words[-1].lower() if len(words) > 1 and words[-1].lower() in SUFFIX_STARTS else None
        stem = _simple(" ".join(words[:-1])) if suffix else full
        use_stem = suffix is not None and not (said - {suffix})
        score = 0.0
        for i in range(len(tokens)):
            chunk = "".join(tokens[i:i + len(words)])
            if chunk:
                score = max(score, difflib.SequenceMatcher(None, full, chunk).ratio())
            if use_stem and tokens[i]:
                score = max(score, difflib.SequenceMatcher(None, stem, tokens[i]).ratio() - 0.02)
        best_by[r.cluster_id] = score
    ranked = sorted(best_by.items(), key=lambda kv: -kv[1])
    if not ranked or ranked[0][1] < CLUSTER_MATCH:
        return None
    if len(ranked) > 1 and ranked[1][1] >= CLUSTER_MATCH and ranked[0][1] - ranked[1][1] < CLUSTER_MARGIN:
        return None  # two kendras fit about equally well: the officer must say which, never a guess
    return ranked[0][0]


# ---------- facts ----------

def _q(view: str, where: dict, rows: pd.DataFrame | None, file_id: dict, files: list[str] | None = None) -> list[dict]:
    """Query provenance, one entry per source file. Rows without src_file (or no rows) cite the view's own files."""
    n_rows = 0 if rows is None else int(len(rows))
    if rows is not None and n_rows and "src_file" in rows:
        groups = [(f, int(len(g))) for f, g in rows.groupby("src_file")]
    else:
        groups = [(f, n_rows) for f in (files or [])]
    out = []
    for f, n in groups:
        entry = {"kind": "query", "view": view, "where": where, "n_rows": n}
        if f in file_id:
            entry["source"] = file_id[f]
        out.append(entry)
    return out or [{"kind": "query", "view": view, "where": where, "n_rows": n_rows}]


def view_files(tables: dict) -> dict[str, list[str]]:
    """Source files behind each canonical table (for empty results and for tables built without src_file)."""
    out = {k: sorted(t["src_file"].dropna().astype(str).unique()) for k, t in tables.items() if "src_file" in t}
    years = sorted(tables["udise_year"]["academic_year"].dropna().unique()) if "udise_year" in tables else []
    out["udise_year"] = [f"udise_{years[-1]}_enr1.csv"] if years else []  # enrolment of the latest year
    return out


def compute_facts(tables: dict, trust: BlockTrust, scope_codes: set, scope: dict, file_id: dict,
                  files: dict[str, list[str]] | None = None) -> dict:
    """Facts for a set of schools (a block or a cluster): {name: (value, unit, decimals, provenance)}.

    A fact whose inputs are missing (no rows, or only blank cells) is left out, never shown as 0 or NaN.
    """
    files = files if files is not None else view_files(tables)
    q = lambda view, where, rows: _q(view, where, rows, file_id, files.get(view))  # noqa: E731
    w = trust.comparison
    out = {}
    s = tables["schools"]
    sc = s[s["udise_code"].isin(scope_codes)]
    out["schools"] = (len(sc), "count", 0, q("schools", scope, sc))
    out["clusters"] = (sc["cluster_id"].nunique(), "count", 0, q("schools", scope | {"distinct": "cluster_id"}, sc))
    posts = tables["posts"]
    last_month = posts["month"].max()
    pm = posts[(posts["month"] == last_month) & posts["udise_code"].isin(scope_codes)]
    pm = pm[pm["working"].notna() & pm["sanctioned"].notna()]
    where_m = scope | {"month": last_month}
    if len(pm):
        out["working_teachers"] = (int(pm["working"].sum()), "count", 0, q("posts", where_m, pm))
        out["sanctioned_posts"] = (int(pm["sanctioned"].sum()), "count", 0, q("posts", where_m, pm))
        vac = (pm["sanctioned"] - pm["working"]).clip(lower=0)
        out["vacant_posts"] = (int(vac.sum()), "count", 0, q("posts", where_m, pm))
        out["schools_with_vacancy"] = (int((vac > 0).sum()), "count", 0, q("posts", where_m | {"vacant_over": 0}, pm[vac > 0]))
        one = pm[pm["working"] == 1]
        out["single_teacher_schools"] = (len(one), "count", 0, q("posts", where_m | {"working": 1}, one))
    y = tables["udise_year"]
    year = y["academic_year"].max()
    yc = y[(y["academic_year"] == year) & y["udise_code"].isin(scope_codes)]
    wk = pm.set_index("udise_code")["working"].astype(float)
    en = yc.set_index("udise_code")["enrol_total"].astype(float).reindex(wk.index) if "enrol_total" in yc else pd.Series(dtype=float)
    where_y = scope | {"academic_year": year}
    if len(wk) and en.notna().any():
        zero = (wk == 0) & (en > 0)
        out["zero_teacher_schools"] = (int(zero.sum()), "count", 0, q("posts", where_m | {"working": 0}, pm[pm["udise_code"].isin(wk.index[zero])]))
        if wk.sum() > 0:
            out["ptr"] = (float(en.sum()) / float(wk.sum()), "index", 1, q("udise_year", where_y, yc) + q("posts", where_m, pm))
            over = ((en / wk.where(wk > 0)) > PTR_NORM) | zero  # a school with pupils and no teacher is over any norm
            out["schools_ptr_over_30"] = (int(over.sum()), "count", 0,
                                          q("udise_year", where_y | {"ptr_over": PTR_NORM}, yc) + q("posts", where_m, pm))
    att = tables["attendance"]
    att = att[att["udise_code"].isin(scope_codes - trust.excluded_attendance)]
    last3 = sorted(att["month"].dropna().unique())[-3:]
    a3 = att[att["month"].isin(last3) & att["attendance_pct"].notna()]
    if len(a3):
        where_a = scope | {"months": last3, "trusted_only": True}
        vals = a3["attendance_pct"].astype(float)
        out["attendance_pct"] = (float(vals.mean()), "pct", 1, q("attendance", where_a, a3))
        low = vals.groupby(a3["udise_code"]).mean()
        out["schools_low_attendance"] = (int((low < ATT_LOW).sum()), "count", 0, q("attendance", where_a | {"below": ATT_LOW}, a3))
        out["_att_period"] = (last3[0], last3[-1])
    a = tables["assessment"]
    a = a[a["udise_code"].isin(scope_codes - trust.insufficient) & a["round"].isin(w["rounds"]) & a["pct"].notna()]
    for subj, prefix in (("maths", "M"), ("language", "L")):
        cur = a[(a["academic_year"] == w["current"]) & a["competency"].str.startswith(prefix)]
        prev = a[(a["academic_year"] == w["previous"]) & a["competency"].str.startswith(prefix)]
        if len(cur) and len(prev):
            where_l = scope | {"subject": subj, "round": w["rounds"]}
            c, p = float(cur["pct"].astype(float).mean()), float(prev["pct"].astype(float).mean())
            out[f"{subj}_pct"] = (c, "pct", 1, q("assessment", where_l | {"academic_year": w["current"]}, cur))
            out[f"{subj}_change"] = (c - p, "pct_point_change", 1,
                                     q("assessment", where_l | {"academic_year": [w["previous"], w["current"]]}, pd.concat([prev, cur])))
            if subj == "maths":  # schools behind the learning figures (INSUFFICIENT schools are left out, and said so)
                out["schools_learning"] = (int(cur["udise_code"].nunique()), "count", 0,
                                           q("assessment", where_l | {"academic_year": w["current"], "distinct": "udise_code"}, cur))
    v = tables["visits"]
    kp = v[v["udise_code"].isin(scope_codes) & v["visitor_role"].astype(str).str.lower().str.contains("kendra")]
    months_cur = tables["attendance"].loc[tables["attendance"]["academic_year"] == w["current"], "month"].nunique() or 10
    kp_cur = kp[kp["date"].astype(str).str[:7] >= f"{w['current'][:4]}-06"]
    if len(sc):
        out["kp_visits_per_school_month"] = (len(kp_cur) / (len(sc) * months_cur), "index", 1,
                                             q("visits", scope | {"visitor_role": "Kendra Pramukh", "academic_year": w["current"]}, kp_cur))
    out["ptr_norm"] = (PTR_NORM, "count", 0, [{"kind": "constant", "rule_id": "RTE", "name": "RTE primary pupil-teacher norm"}])
    out["att_low"] = (ATT_LOW, "pct", 0, [{"kind": "constant", "rule_id": "RISK-ATTENDANCE", "name": "ATT_LOW"}])
    fl = trust.school_flags
    fl = fl[fl["udise_code"].isin(scope_codes)]
    red = set(fl.loc[fl["label"] == "RED_FLAG", "udise_code"])
    ins = set(fl.loc[fl["label"] == "INSUFFICIENT", "udise_code"])
    rule = lambda rid, name: [{"kind": "constant", "rule_id": rid, "name": name}]  # noqa: E731
    att_all, ass_all = tables["attendance"], tables["assessment"]
    out["flagged_schools"] = (len(red), "count", 0, rule("TRUST-FLAT", "attendance >= 99.95% for 3+ months in a row")
                              + q("attendance", scope | {"trust_rule": "TRUST-FLAT"}, att_all[att_all["udise_code"].isin(red)]))
    out["insufficient_schools"] = (len(ins), "count", 0, rule("TRUST-MISSING", "attendance months or an assessment round missing")
                                   + q("assessment", scope | {"trust_rule": "TRUST-MISSING"}, ass_all[ass_all["udise_code"].isin(ins)]))
    return out


def register_facts(pack: dict, facts: dict, prefix: str) -> dict:
    """Add facts to (a copy of) the pack's number registry; returns {fact name: number id}. Blank values are skipped."""
    ids = {}
    for name, val in facts.items():
        if name.startswith("_"):
            continue
        value, unit, dec, prov = val
        if value is None or pd.isna(value):
            continue
        value = float(value)
        nid = f"n.fact.{prefix}.{name}"
        n = {"value": round(value, 4), "unit": unit, "decimals": dec, "provenance": prov,
             "derivation": {"op": "fact", "inputs": []}, "display": E.format_number(value, unit, dec)}
        if unit in E.CHANGE_UNITS:
            shown = round(abs(value), dec)
            n["direction"] = "flat" if shown == 0 else "down" if value < 0 else "up"
        pack["numbers"][nid] = n
        ids[name] = nid
    return ids


# ---------- direct-answer sentences (placeholders only; code fills every figure and name) ----------

ANSWER_TEMPLATES = {
    "schools": ("{{e:P}} मध्ये {{n:schools}} शाळा आहेत ({{n:clusters}} केंद्रे).",
                "{{e:P}} has {{n:schools}} schools in {{n:clusters}} clusters."),
    "schools_cluster": ("{{e:P}} केंद्रात {{n:schools}} शाळा आहेत.", "{{e:P}} has {{n:schools}} schools."),
    "teachers": ("{{e:P}} मध्ये {{n:working_teachers}} शिक्षक कार्यरत आहेत; मंजूर पदे {{n:sanctioned_posts}}, रिक्त पदे {{n:vacant_posts}} "
                 "({{n:schools_with_vacancy}} शाळांमध्ये). एकच शिक्षक असलेल्या शाळा: {{n:single_teacher_schools}}.",
                 "{{e:P}}: {{n:working_teachers}} teachers working against {{n:sanctioned_posts}} sanctioned posts; {{n:vacant_posts}} posts "
                 "vacant in {{n:schools_with_vacancy}} schools. Single-teacher schools: {{n:single_teacher_schools}}."),
    "ptr": ("{{e:P}} मध्ये विद्यार्थी-शिक्षक प्रमाण {{n:ptr}} आहे; {{n:schools_ptr_over_30}} शाळांमध्ये ते {{n:ptr_norm}} पेक्षा जास्त आहे.",
            "{{e:P}}: pupil-teacher ratio {{n:ptr}}; {{n:schools_ptr_over_30}} schools are above {{n:ptr_norm}}."),
    "attendance": ("{{e:P}} मध्ये {{p:att}} या काळात सरासरी हजेरी {{n:attendance_pct}} होती (विश्वासार्ह नोंदी); "
                   "{{n:schools_low_attendance}} शाळांमध्ये ती {{n:att_low}} पेक्षा कमी आहे.",
                   "{{e:P}}: average attendance {{n:attendance_pct}} in {{p:att}} (trusted records only); "
                   "{{n:schools_low_attendance}} schools are below {{n:att_low}}."),
    "learning_down": ("{{e:P}} मध्ये गणिताचा सरासरी निकाल {{n:maths_pct}} आहे, मागील वर्षापेक्षा {{n:maths_change}} गुणांनी कमी; "
                      "भाषा {{n:language_pct}}.",
                      "{{e:P}}: maths {{n:maths_pct}} on average, {{n:maths_change}} points lower than last year; language {{n:language_pct}}."),
    "learning_up": ("{{e:P}} मध्ये गणिताचा सरासरी निकाल {{n:maths_pct}} आहे, मागील वर्षापेक्षा {{n:maths_change}} गुणांनी जास्त; "
                    "भाषा {{n:language_pct}}.",
                    "{{e:P}}: maths {{n:maths_pct}} on average, {{n:maths_change}} points higher than last year; language {{n:language_pct}}."),
    "learning_flat": ("{{e:P}} मध्ये गणिताचा सरासरी निकाल {{n:maths_pct}} आहे, मागील वर्षाइतकाच; भाषा {{n:language_pct}}.",
                      "{{e:P}}: maths {{n:maths_pct}} on average, about the same as last year; language {{n:language_pct}}."),
    "visits": ("{{e:P}} मध्ये या वर्षी केंद्रप्रमुखांच्या भेटी दर शाळेला दरमहा {{n:kp_visits_per_school_month}} आहेत.",
               "{{e:P}}: {{n:kp_visits_per_school_month}} Kendra Pramukh visits per school per month this year."),
    "data_quality": ("{{e:P}} मध्ये {{n:flagged_schools}} शाळांच्या हजेरीच्या नोंदी संशयास्पद आहेत आणि {{n:insufficient_schools}} शाळांची माहिती अपूर्ण आहे.",
                     "{{e:P}}: attendance records of {{n:flagged_schools}} schools look unreliable and data is incomplete for "
                     "{{n:insufficient_schools}} schools."),
}
# appended (before the final full stop) only when the condition holds
ZERO_TEACHER_NOTE = (" शिक्षक नसलेल्या शाळा: {{n:zero_teacher_schools}}.", " Schools with no teacher: {{n:zero_teacher_schools}}.")
COVERAGE_NOTE = (" ({{n:schools}} पैकी {{n:schools_learning}} शाळांच्या पूर्ण नोंदी)", " (complete records: {{n:schools_learning}} of {{n:schools}} schools)")
ANSWER_HEADING = ("थेट उत्तर", "Direct answer")
RANK_LINE = ("सर्वात जास्त लक्ष देण्याची गरज: {items}. पहिल्या तालुक्याचा अहवाल खाली आहे.",
             "Most attention needed: {items}. The first block's brief is below.")
RANK_ITEM = (("{name} ({n} केंद्र)", "{name} ({n} केंद्रे)"), ("{name} ({n} cluster)", "{name} ({n} clusters)"))
RANK_BY_LINE = ("{label}: {items}. पहिल्या तालुक्याचा अहवाल खाली आहे.", "{label}: {items}. The first block's brief is below.")


def answer_lines(metrics: list[str], fact_ids: dict, scope_entity: str, is_cluster: bool, facts: dict,
                 period_ids: dict | None = None) -> list[dict]:
    """Template sentences (with placeholders) for the asked metrics; facts that could not be computed are skipped."""
    lines = []
    value = lambda name: facts[name][0] if name in fact_ids else None  # noqa: E731
    for m in dict.fromkeys(metrics):
        key = m
        if m == "schools" and is_cluster:
            key = "schools_cluster"
        if m == "learning":
            change = value("maths_change")
            if change is None:
                continue
            key = "learning_flat" if round(abs(change), 1) == 0 else "learning_down" if change < 0 else "learning_up"
        if key not in ANSWER_TEMPLATES:
            continue
        mr, en = ANSWER_TEMPLATES[key]
        if key == "teachers" and (value("zero_teacher_schools") or 0) > 0:
            mr, en = mr + ZERO_TEACHER_NOTE[0], en + ZERO_TEACHER_NOTE[1]
        if key.startswith("learning") and value("schools_learning") is not None and value("schools_learning") < (value("schools") or 0):
            mr, en = mr[:-1] + COVERAGE_NOTE[0] + ".", en[:-1] + COVERAGE_NOTE[1] + "."  # INSUFFICIENT schools left out: say so
        needed = set(re.findall(r"\{\{n:([a-z_0-9]+)\}\}", mr + en))
        periods = set(re.findall(r"\{\{p:([a-z_]+)\}\}", mr + en))
        if not needed <= set(fact_ids) or not periods <= set(period_ids or {}):
            continue
        for name in periods:
            mr = mr.replace("{{p:" + name + "}}", "{{p:" + period_ids[name] + "}}")
            en = en.replace("{{p:" + name + "}}", "{{p:" + period_ids[name] + "}}")
        sub = lambda t: re.sub(r"\{\{n:([a-z_0-9]+)\}\}", lambda x: "{{n:" + fact_ids[x.group(1)] + "}}", t)  # noqa: E731
        if is_cluster:  # "<village> मध्ये" reads badly for a kendra: "<village> केंद्रात"
            mr = mr.replace("{{e:P}} मध्ये", "{{e:P}} केंद्रात")
        lines.append({"metric": m, "mr": sub(mr).replace("{{e:P}}", "{{e:" + scope_entity + "}}"),
                      "en": sub(en).replace("{{e:P}}", "{{e:" + scope_entity + "}}")})
    return lines


# ---------- ranking blocks by an asked figure ("which block has the lowest PTR?") ----------

# metric -> (fact, +1 if higher is better, -1 if lower is better, 0 if neither)
RANK_FACT = {"learning": ("maths_pct", 1), "attendance": ("attendance_pct", 1), "visits": ("kp_visits_per_school_month", 1),
             "ptr": ("ptr", -1), "teachers": ("vacant_posts", -1), "schools": ("schools", 0), "data_quality": ("flagged_schools", -1)}
RANK_LABEL = {
    "maths_pct": (("गणिताचा सर्वाधिक सरासरी निकाल", "Highest maths results"), ("गणिताचा सर्वात कमी सरासरी निकाल", "Lowest maths results")),
    "attendance_pct": (("सर्वाधिक हजेरी", "Highest attendance"), ("सर्वात कमी हजेरी", "Lowest attendance")),
    "kp_visits_per_school_month": (("केंद्रप्रमुखांच्या सर्वाधिक भेटी (दर शाळा, दरमहा)", "Most Kendra Pramukh visits (per school per month)"),
                                   ("केंद्रप्रमुखांच्या सर्वात कमी भेटी (दर शाळा, दरमहा)", "Fewest Kendra Pramukh visits (per school per month)")),
    "ptr": (("सर्वाधिक विद्यार्थी-शिक्षक प्रमाण", "Highest pupil-teacher ratio"), ("सर्वात कमी विद्यार्थी-शिक्षक प्रमाण", "Lowest pupil-teacher ratio")),
    "vacant_posts": (("सर्वाधिक रिक्त पदे", "Most vacant posts"), ("सर्वात कमी रिक्त पदे", "Fewest vacant posts")),
    "schools": (("सर्वाधिक शाळा", "Most schools"), ("सर्वात कमी शाळा", "Fewest schools")),
    "flagged_schools": (("संशयास्पद हजेरी नोंदी असलेल्या सर्वाधिक शाळा", "Most schools with unreliable attendance records"),
                        ("संशयास्पद हजेरी नोंदी असलेल्या सर्वात कमी शाळा", "Fewest schools with unreliable attendance records")),
}
SUPERLATIVE = {
    "high": ["highest", "most ", "maximum", "top ", "सर्वाधिक", "सर्वात जास्त", "sarvat jast", "jast"],
    "low": ["lowest", "least", "minimum", "fewest", "सर्वात कमी", "sarvat kami"],
    "good": ["best", "better", "doing well", "चांगला", "चांगली", "चांगले", "चांगल्या", "changla", "changli", "उत्तम"],
    "bad": ["worst", "poorest", "weakest", "वाईट", "खराब", "kharab", "vait"],
}


def superlative(question: str) -> str | None:
    """high | low | good | bad when the question asks for a ranking ("which block has the best ..."), else None."""
    q = normalise(question) + " "
    found = [k for k, words in SUPERLATIVE.items() if any(w in q for w in words)]
    return found[0] if len(found) == 1 else None


def rank_order(metric: str, sup: str) -> tuple[str, str] | None:
    """(fact, 'desc' | 'asc') for a metric and a superlative, or None when the ranking would be meaningless."""
    if metric not in RANK_FACT:
        return None
    fact, better = RANK_FACT[metric]
    if sup in ("high", "low"):
        return fact, "desc" if sup == "high" else "asc"
    if better == 0:
        return None
    up = (sup == "good") == (better > 0)
    return fact, "desc" if up else "asc"


def rank_line(fact: str, order: str, ranked: list[tuple[str, str]]) -> dict:
    """One line ranking the top blocks by a fact; ranked = [(block entity id, number id), ...] (placeholders only)."""
    label = RANK_LABEL[fact][0 if order == "desc" else 1]
    items = ", ".join("{{e:" + b + "}} {{n:" + nid + "}}" for b, nid in ranked)
    return {"metric": "rank_by", "mr": RANK_BY_LINE[0].format(label=label[0], items=items),
            "en": RANK_BY_LINE[1].format(label=label[1], items=items)}


# ---------- greeting / help ----------

GREETING_TOKENS = {"hi", "hello", "hey", "help", "start", "menu", "namaskar", "namaste", "madat", "नमस्कार", "नमस्ते", "मदत", "हाय"}
GREETING_PHRASES = ["what can you do", "who are you", "how to use", "तुम्ही काय करू शकता", "तू काय करू शकतोस", "कसे वापरायचे"]
WHY_WORDS = ["why", "reason", "cause", "कशामुळे", "कारण", "का घसर", "का कमी", "का वाढ", "का खाल", "ka ghasar", "ka kami", "karan",
             "घसर", "ghasar", "fall", "fell", "drop", "decline"]


def is_greeting(question: str) -> bool:
    """A greeting or a request for help (used only when no place or topic was understood)."""
    q = normalise(question)
    tokens = q.split()
    return not tokens or (len(tokens) <= 4 and bool(set(tokens) & GREETING_TOKENS)) or any(p in q for p in GREETING_PHRASES)


def asks_why(question: str) -> bool:
    q = normalise(question)
    return any(w in q for w in WHY_WORDS)


# ---------- the block's facts bundle (kept outside the evidence pack, so recorded brief prompts stay unchanged) ----------

CLUSTER_WORDS = ("kendra", "केंद्र", "cluster", "kendr")
CLUSTER_STATUS = {
    "AT_RISK": ("{{e:P}} केंद्राकडे तातडीने लक्ष देण्याची गरज आहे; कारणे आणि कृती खालील अहवालात आहेत.",
                "{{e:P}} needs attention now; the reasons and actions are in the brief below."),
    "AT_RISK_UNEXPLAINED": ("{{e:P}} केंद्राकडे तातडीने लक्ष देण्याची गरज आहे; घसरणीचे स्पष्ट कारण सापडले नाही. काय तपासले आणि कृती खालील अहवालात आहेत.",
                            "{{e:P}} needs attention now; no clear cause was found. What was checked and the actions are in the brief below."),
    "DATA": ("{{e:P}} केंद्रातील हजेरीच्या नोंदी विश्वासार्ह दिसत नाहीत; आधी त्या तपासाव्यात.",
             "Attendance records in {{e:P}} look unreliable; check them first."),
    "INSUFFICIENT": ("{{e:P}} केंद्राची माहिती अपूर्ण आहे, त्यामुळे अजून निष्कर्ष काढता येत नाही.",
                     "Data for {{e:P}} is incomplete, so it cannot be judged yet."),
    "OK": ("{{e:P}} केंद्र सध्या तातडीच्या यादीत नाही.", "{{e:P}} is not among the clusters needing attention now."),
}
CLUSTER_OVERVIEW = ["schools", "learning", "attendance", "visits"]  # a kendra named without a metric


def build_facts(tables: dict, trust: BlockTrust, pack: dict) -> dict:
    """Facts for the pack's block and each of its clusters, as pack-style numbers/periods/entities plus id maps."""
    focus = pack["scope"]["focus"]
    block_name = pack["entities"][focus]["name_en"]
    file_id = {s["file"]: s["id"] for s in pack["sources"]}
    files = view_files(tables)
    schools = tables["schools"]
    in_block = schools[schools["block"] == block_name]
    clusters = tables["clusters"][tables["clusters"]["block"] == block_name]
    out = {"numbers": {}, "periods": {}, "entities": {}, "ids": {}, "facts": {}, "period_ids": {}, "clusters": clusters}
    scopes = [(focus, {"block": block_name}, set(in_block["udise_code"]))]
    for r in clusters.itertuples(index=False):
        eid = f"C{r.cluster_id}"
        village = str(r.cluster_name).replace(" Kendra", "")
        out["entities"][eid] = {"kind": "cluster", "code": r.cluster_id, "name_en": f"{village} Kendra", "name_mr": village}
        codes = set(in_block.loc[in_block["cluster_id"] == r.cluster_id, "udise_code"])
        scopes.append((eid, {"block": block_name, "cluster": r.cluster_id}, codes))
    for eid, where, codes in scopes:
        facts = compute_facts(tables, trust, codes, where, file_id, files)
        ids = register_facts(out, facts, eid)
        for nid in ids.values():
            out["numbers"][nid]["entity"] = eid
        out["ids"][eid], out["facts"][eid] = ids, facts
        if "_att_period" in facts:
            pid = f"p.fact.{eid}.att"
            out["periods"][pid] = {"kind": "month_range", "from": facts["_att_period"][0], "to": facts["_att_period"][1]}
            out["period_ids"][eid] = {"att": pid}
    return out


def cluster_named(question: str, clusters: pd.DataFrame, block: str | None, block_names: list[str]) -> str | None:
    """Cluster id named in the question. A kendra that shares its block's name needs the word kendra/केंद्र/cluster."""
    cid = find_cluster(question, clusters, block)
    if cid is None:
        return None
    village = str(clusters.set_index("cluster_id").loc[cid, "cluster_name"]).replace(" Kendra", "")
    if _simple(village) in {_simple(n) for n in block_names if n} and not any(w in normalise(question) for w in CLUSTER_WORDS):
        return None
    return cid


def direct_answer(question: str, bundle: dict, pack: dict, cluster_id: str | None = None,
                  metrics: list[str] | None = None) -> dict:
    """{scope, cluster, metrics, lines[]}: the asked figures for the block (or the named cluster), as placeholder text."""
    metrics = metrics_asked(question) if metrics is None else metrics
    focus = pack["scope"]["focus"]
    eid = f"C{cluster_id}" if cluster_id and f"C{cluster_id}" in bundle["ids"] else focus
    lines = []
    asked = [m for m in metrics if m not in ("actions", "attention_rank")]
    if eid != focus:
        summary = pack.get("summary", {}).get(cluster_id, {})
        status = summary.get("status", "OK")
        if status == "AT_RISK" and "D8" in summary.get("checks", {}):  # D8 = no tested cause held
            status = "AT_RISK_UNEXPLAINED"
        mr, en = CLUSTER_STATUS.get(status, CLUSTER_STATUS["OK"])
        lines.append({"metric": "status", "mr": mr.replace("{{e:P}}", "{{e:" + eid + "}}"), "en": en.replace("{{e:P}}", "{{e:" + eid + "}}")})
        if not asked:  # overview; an incomplete kendra gets no learning figures (it "cannot be judged yet")
            asked = [m for m in CLUSTER_OVERVIEW if not (status == "INSUFFICIENT" and m == "learning")]
    lines += answer_lines(asked, bundle["ids"][eid], eid, eid != focus, bundle["facts"][eid], bundle["period_ids"].get(eid))
    return {"scope": eid, "cluster": cluster_id if eid != focus else None, "metrics": metrics, "lines": lines}
