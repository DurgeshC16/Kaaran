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
    "clusters": ["how many clusters", "how many kendra", "number of clusters", "number of kendra", "किती केंद्र", "केंद्रे किती",
                 "केंद्र किती", "kiti kendra", "kendra kiti", "kendre kiti"],
    "single_teacher": ["single teacher", "single-teacher", "one teacher school", "one-teacher", "एकशिक्षकी", "एक शिक्षकी",
                       "एक शिक्षक", "ek shikshaki", "ek shikshak", "ekshikshaki"],
    "vacancies": ["vacan", "रिक्त", "shortage", "short of teacher", "कमी शिक्षक", "शिक्षक कमी", "शिक्षक किती कमी", "shikshak kami",
                  "shikshak kiti kami", "kami shikshak", "sanctioned", "मंजूर"],
    "pupils": ["how many students", "how many pupils", "number of students", "number of pupils", "enrolment", "enrollment",
               "किती विद्यार्थी", "विद्यार्थी किती", "विद्यार्थी संख्या", "पटसंख्या", "kiti vidyarthi", "vidyarthi kiti", "pat sankhya",
               "students", "pupils", "विद्यार्थी"],
    "teachers": ["teacher", "शिक्षक", "shikshak", "staff", "posts", "पदे"],
    "ptr": ["ptr", "pupil teacher", "pupil-teacher", "student teacher ratio", "विद्यार्थी शिक्षक", "विद्यार्थी-शिक्षक"],
    "attendance": ["attendance", "हजेरी", "उपस्थिती", "hajeri", "absent", "गैरहजर"],
    "learning": ["result", "score", "learning", "निकाल", "गुण", "maths", "math", "गणित", "ganit", "language", "भाषा", "reading",
                 "वाचन", "nikal"],
    "visits": ["visit", "भेट", "kendra pramukh", "केंद्रप्रमुख", "crc", "mentor"],
    "data_quality": ["data", "आकडेवारी", "reliable", "विश्वास", "record", "नोंद", "fake", "बनावट", "nond", "avishwas", "vishwas",
                     "aakdevari", "akdevari", "khoti", "खोटी"],
    "actions": ["what should i do", "what to do", "काय करावे", "काय करू", "action", "कृती", "kay karave", "next step"],
    # only real "where should I look first" words; "which block has the best X" is a ranking by X (see superlative())
    "attention_rank": ["most attention", "need attention", "needs attention", "need more attention", "needs more attention",
                       "more attention", "attention first", "worst block", "worst taluka", "जास्त लक्ष देण्याची",
                       "सर्वात जास्त लक्ष", "जास्त लक्ष", "लक्ष द्यावे", "लक्ष देण्याची", "मागे आहे", "mage aahe", "mage ahe", "sarvat jast laksh",
                       "मागे पडला", "mage padla", "behind", "lagging"],
}
SCHOOL_WORDS = ("school", "schol", "shcool", "शाळा", "shala", "shaala", "shaal")
COUNT_WORDS = ("how many", "kiti", "kti", "किती", "number", "total", "sankhya", "संख्या", "count", "एकूण")
SUFFIX_STARTS = {"budruk": "budr", "khurd": "khur"}  # village suffixes (बुद्रुक / खुर्द romanise to budruk / khurd)
CLUSTER_MATCH = 0.88  # minimum similarity for a kendra name
CLUSTER_MARGIN = 0.03  # a runner-up this close means the question is ambiguous


def normalise(text: str) -> str:
    t = unicodedata.normalize("NFC", text.lower())
    return " ".join(re.sub(r"[^\wऀ-ॿ -]", " ", t).split())


def metrics_asked(question: str) -> list[str]:
    q = normalise(question).replace("गुणवत्ता", "quality")  # "गुण" (marks) must not fire on "गुणवत्ता" (quality)
    found = [m for m, words in METRIC_WORDS.items() if any(w in q for w in words)]
    if "single_teacher" in found and "schools" in found and not any(w in q for w in ("how many schools are", "शाळा आहेत")):
        found.remove("schools")  # "how many single-teacher schools" asks for one figure
    if ("single_teacher" in found or "vacancies" in found or "ptr" in found) and "teachers" in found:
        found.remove("teachers")  # the specific figure, not the whole staffing line ("pupil teacher ratio" is PTR)
    if "ptr" in found and "pupils" in found:
        found.remove("pupils")  # "विद्यार्थी-शिक्षक प्रमाण" is the ratio, not a pupil count
    if not ({"schools", "clusters", "single_teacher", "pupils"} & set(found)) and any(w in q for w in SCHOOL_WORDS) \
            and any(w in q for w in COUNT_WORDS):
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
        score = -0.1 if said and suffix not in said else 0.0  # "Longaon Khurd" must not pick plain "Longaon"
        for i in range(len(tokens)):
            chunk = "".join(tokens[i:i + len(words)])
            penalty = 0.1 if said and suffix not in said else 0.0
            if chunk:
                score = max(score, difflib.SequenceMatcher(None, full, chunk).ratio() - penalty)
            if use_stem and tokens[i]:
                score = max(score, difflib.SequenceMatcher(None, stem, tokens[i]).ratio() - 0.05)  # exact full names win
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
        sur = (pm["working"] - pm["sanctioned"]).clip(lower=0)
        out["surplus_teachers"] = (int(sur.sum()), "count", 0, q("posts", where_m | {"surplus_over": 0}, pm[sur > 0]))
        out["schools_with_surplus"] = (int((sur > 0).sum()), "count", 0, q("posts", where_m | {"surplus_over": 0}, pm[sur > 0]))
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
        out["pupils"] = (int(yc["enrol_total"].fillna(0).sum()), "count", 0, q("udise_year", where_y, yc))
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
        prev3 = [f"{int(m[:4]) - 1}{m[4:]}" for m in last3]  # the same months one year earlier
        p3 = att[att["month"].isin(prev3) & att["attendance_pct"].notna()]
        if len(p3):
            out["attendance_prev_pct"] = (float(p3["attendance_pct"].astype(float).mean()), "pct", 1,
                                          q("attendance", scope | {"months": prev3, "trusted_only": True}, p3))
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
        p0, p1 = f"{w['previous'][:4]}-06", f"{w['current'][:4]}-06"
        kp_prev = kp[(kp["date"].astype(str).str[:7] >= p0) & (kp["date"].astype(str).str[:7] < p1)]
        months_prev = tables["attendance"].loc[tables["attendance"]["academic_year"] == w["previous"], "month"].nunique() or 10
        out["kp_visits_prev"] = (len(kp_prev) / (len(sc) * months_prev), "index", 1,
                                 q("visits", scope | {"visitor_role": "Kendra Pramukh", "academic_year": w["previous"]}, kp_prev))
        prev_month = f"{int(last_month[:4]) - 1}{last_month[4:]}"
        pp = posts[(posts["month"] == prev_month) & posts["udise_code"].isin(scope_codes) & posts["working"].notna()]
        if len(pp):
            out["working_prev"] = (int(pp["working"].sum()), "count", 0, q("posts", scope | {"month": prev_month}, pp))
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
    "clusters": ("{{e:P}} मध्ये {{n:clusters}} केंद्रे आहेत ({{n:schools}} शाळा).",
                 "{{e:P}} has {{n:clusters}} clusters (kendras) with {{n:schools}} schools."),
    "single_teacher": ("{{e:P}} मधील एकशिक्षकी शाळा: एकूण {{n:schools}} पैकी {{n:single_teacher_schools}}.",
                       "Single-teacher schools in {{e:P}}: {{n:single_teacher_schools}} of {{n:schools}}."),
    "vacancies": ("{{e:P}} मधील रिक्त शिक्षक पदे: {{n:vacant_posts}} (शाळा: {{n:schools_with_vacancy}}); मंजूर {{n:sanctioned_posts}}, "
                  "कार्यरत {{n:working_teachers}}.",
                  "Vacant teacher posts in {{e:P}}: {{n:vacant_posts}} (schools affected: {{n:schools_with_vacancy}}); "
                  "{{n:working_teachers}} working against {{n:sanctioned_posts}} sanctioned."),
    "pupils": ("{{e:P}} मध्ये {{n:pupils}} विद्यार्थी आहेत (इयत्ता १ ते ८, {{n:schools}} शाळा).",
               "{{e:P}} has {{n:pupils}} pupils in classes 1 to 8 across {{n:schools}} schools."),
    "schools_district": ("{{e:P}} मध्ये {{n:schools}} शाळा आहेत: {{n:blocks}} तालुके, {{n:clusters}} केंद्रे.",
                         "{{e:P}} has {{n:schools}} schools in {{n:blocks}} blocks and {{n:clusters}} clusters."),
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
    "data_quality": ("{{e:P}}: संशयास्पद हजेरी नोंदी असलेल्या शाळा {{n:flagged_schools}}; अपूर्ण माहिती असलेल्या शाळा {{n:insufficient_schools}}.",
                     "{{e:P}}: schools with unreliable attendance records: {{n:flagged_schools}}; schools with incomplete data: "
                     "{{n:insufficient_schools}}."),
}
# appended (before the final full stop) only when the condition holds
SURPLUS_NOTE = (" मंजुरीपेक्षा जास्त शिक्षक: {{n:surplus_teachers}} ({{n:schools_with_surplus}} शाळा) - पुनर्नियुक्तीची संधी.",
                " Teachers above sanction: {{n:surplus_teachers}} (in {{n:schools_with_surplus}} schools) - a redeployment option.")
ZERO_TEACHER_NOTE = (" शिक्षक नसलेल्या शाळा: {{n:zero_teacher_schools}}.", " Schools with no teacher: {{n:zero_teacher_schools}}.")
COVERAGE_NOTE = (" ({{n:schools}} पैकी {{n:schools_learning}} शाळांच्या पूर्ण नोंदी)", " (complete records: {{n:schools_learning}} of {{n:schools}} schools)")
ANSWER_HEADING = ("थेट उत्तर", "Direct answer")
RANK_LINE = ("सर्वात जास्त लक्ष देण्याची गरज: {items}. पहिल्या तालुक्यातील केंद्रे खाली आहेत.",
             "Most attention needed: {items}. The first block's clusters are below.")
RANK_LINE_SHORT = ("सर्वात जास्त लक्ष देण्याची गरज: {items}.", "Most attention needed: {items}.")
RANK_ITEM = (("{name} ({n} केंद्र)", "{name} ({n} केंद्रे)"), ("{name} ({n} cluster)", "{name} ({n} clusters)"))
RANK_BY_LINE = ("{label}: {items}.", "{label}: {items}.")


def answer_lines(metrics: list[str], fact_ids: dict, scope_entity: str, is_cluster: bool, facts: dict,
                 period_ids: dict | None = None) -> list[dict]:
    """Template sentences (with placeholders) for the asked metrics; facts that could not be computed are skipped."""
    lines = []
    value = lambda name: facts[name][0] if name in fact_ids else None  # noqa: E731
    for m in dict.fromkeys(metrics):
        key = m
        if m == "schools" and is_cluster:
            key = "schools_cluster"
        elif m == "schools" and "blocks" in fact_ids:
            key = "schools_district"
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
        if key in ("teachers", "vacancies") and (value("surplus_teachers") or 0) > 0:
            mr, en = mr + SURPLUS_NOTE[0], en + SURPLUS_NOTE[1]
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
            mr = mr.replace("{{e:P}} मध्ये", "{{e:P}} केंद्रात").replace("{{e:P}} मधील", "{{e:P}} केंद्रातील")
        elif "blocks" in fact_ids:  # the district: "सोलापूर जिल्ह्यात"
            mr = mr.replace("{{e:P}} मध्ये", "{{e:P}} जिल्ह्यात").replace("{{e:P}} मधील", "{{e:P}} जिल्ह्यातील").replace("{{e:P}}:", "{{e:P}} जिल्हा:")
        lines.append({"metric": m, "mr": sub(mr).replace("{{e:P}}", "{{e:" + scope_entity + "}}"),
                      "en": sub(en).replace("{{e:P}}", "{{e:" + scope_entity + "}}"),
                      "facts": [fact_ids[n] for n in sorted(needed)]})
    return lines


# ---------- ranking blocks by an asked figure ("which block has the lowest PTR?") ----------

# metric -> (fact, +1 if higher is better, -1 if lower is better, 0 if neither)
RANK_FACT = {"single_teacher": ("single_teacher_schools", -1), "vacancies": ("vacant_posts", -1), "pupils": ("pupils", 0),
             "clusters": ("clusters", 0), "learning": ("maths_pct", 1), "attendance": ("attendance_pct", 1), "visits": ("kp_visits_per_school_month", 1),
             "ptr": ("ptr", -1), "teachers": ("vacant_posts", -1), "schools": ("schools", 0), "data_quality": ("flagged_schools", -1)}
RANK_LABEL = {
    "maths_pct": (("गणिताचा सर्वाधिक सरासरी निकाल", "Highest maths results"), ("गणिताचा सर्वात कमी सरासरी निकाल", "Lowest maths results")),
    "attendance_pct": (("सर्वाधिक हजेरी", "Highest attendance"), ("सर्वात कमी हजेरी", "Lowest attendance")),
    "kp_visits_per_school_month": (("केंद्रप्रमुखांच्या सर्वाधिक भेटी (दर शाळा, दरमहा)", "Most Kendra Pramukh visits (per school per month)"),
                                   ("केंद्रप्रमुखांच्या सर्वात कमी भेटी (दर शाळा, दरमहा)", "Fewest Kendra Pramukh visits (per school per month)")),
    "ptr": (("सर्वाधिक विद्यार्थी-शिक्षक प्रमाण", "Highest pupil-teacher ratio"), ("सर्वात कमी विद्यार्थी-शिक्षक प्रमाण", "Lowest pupil-teacher ratio")),
    "vacant_posts": (("सर्वाधिक रिक्त पदे", "Most vacant posts"), ("सर्वात कमी रिक्त पदे", "Fewest vacant posts")),
    "schools": (("सर्वाधिक शाळा", "Most schools"), ("सर्वात कमी शाळा", "Fewest schools")),
    "single_teacher_schools": (("सर्वाधिक एकशिक्षकी शाळा", "Most single-teacher schools"), ("सर्वात कमी एकशिक्षकी शाळा", "Fewest single-teacher schools")),
    "pupils": (("सर्वाधिक विद्यार्थी", "Most pupils"), ("सर्वात कमी विद्यार्थी", "Fewest pupils")),
    "working_teachers": (("सर्वाधिक कार्यरत शिक्षक", "Most working teachers"), ("सर्वात कमी कार्यरत शिक्षक", "Fewest working teachers")),
    "clusters": (("सर्वाधिक केंद्रे", "Most clusters"), ("सर्वात कमी केंद्रे", "Fewest clusters")),
    "flagged_schools": (("संशयास्पद हजेरी नोंदी असलेल्या सर्वाधिक शाळा", "Most schools with unreliable attendance records"),
                        ("संशयास्पद हजेरी नोंदी असलेल्या सर्वात कमी शाळा", "Fewest schools with unreliable attendance records")),
}
SUPERLATIVE = {
    "high": ["highest", "most ", "maximum", "top ", "सर्वाधिक", "सर्वात जास्त", "sarvat jast", "jast"],
    "low": ["lowest", "least", "minimum", "fewest", "सर्वात कमी", "sarvat kami"],
    "good": ["best", "better", "doing well", "चांगला", "चांगली", "चांगले", "चांगल्या", "changla", "changli", "changle", "उत्तम"],
    "bad": ["worst", "wrost", "worse", "poorest", "weakest", "वाईट", "खराब", "kharab", "vait"],
}


def superlative(question: str) -> str | None:
    """high | low | good | bad when the question asks for a ranking ("which block has the best ..."), else None."""
    q = normalise(question) + " "
    found = [k for k, words in SUPERLATIVE.items() if any(w in q for w in words)]
    return found[0] if len(found) == 1 else None


def rank_order(metric: str, sup: str) -> tuple[str, str] | None:
    """(fact, 'desc' | 'asc') for a metric and a superlative, or None when the ranking would be meaningless."""
    if metric == "teachers" and sup in ("high", "low"):  # "most / fewest teachers" = working teachers, never vacancies
        return "working_teachers", "desc" if sup == "high" else "asc"
    if metric not in RANK_FACT:
        return None
    fact, better = RANK_FACT[metric]
    if sup in ("high", "low"):
        return fact, "desc" if sup == "high" else "asc"
    if better == 0:
        return None
    up = (sup == "good") == (better > 0)
    return fact, "desc" if up else "asc"


TIED = (" (समान आकडे बरोबरीत आहेत)", " (equal figures are tied)")


def rank_line(fact: str, order: str, ranked: list[tuple[str, str]], tied: bool = False) -> dict:
    """One line ranking the top blocks (or kendras) by a fact; ranked = [(entity id, number id), ...] (placeholders only)."""
    label = RANK_LABEL[fact][0 if order == "desc" else 1]
    items = ", ".join("{{e:" + b + "}} {{n:" + nid + "}}" for b, nid in ranked)
    mr, en = RANK_BY_LINE[0].format(label=label[0], items=items), RANK_BY_LINE[1].format(label=label[1], items=items)
    if tied:
        mr, en = mr[:-1] + TIED[0] + ".", en[:-1] + TIED[1] + "."
    return {"metric": "rank_by", "mr": mr, "en": en, "facts": [nid for _b, nid in ranked]}


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
    tokens = q.split()
    # "का" / "ka" before a verb asks why ("निकाल का घसरला", "changla ka aala"); at the end it is a yes/no particle
    return any(w in q for w in WHY_WORDS) or any(t in ("का", "ka") and i < len(tokens) - 1 for i, t in enumerate(tokens))


# ---------- the block's facts bundle (kept outside the evidence pack, so recorded brief prompts stay unchanged) ----------

DQ_WORDS = ("reliable", "unreliable", "विश्वास", "fake", "बनावट", "संशय", "suspicious", "trust", "vishwas", "avishwas", "khari",
            "खरी", "nond", "नोंद", "khoti", "खोटी")
CLUSTER_WORDS = ("kendra", "केंद्र", "cluster", "kendr")
CLUSTER_STATUS = {
    "AT_RISK": ("{{e:P}} केंद्राकडे तातडीने लक्ष देण्याची गरज आहे; कारणे आणि कृती खाली दिली आहेत.",
                "{{e:P}} needs attention now; the reasons and actions are below."),
    "AT_RISK_UNEXPLAINED": ("{{e:P}} केंद्राकडे तातडीने लक्ष देण्याची गरज आहे; घसरणीचे स्पष्ट कारण सापडले नाही. काय तपासले आणि कृती खाली दिली आहेत.",
                            "{{e:P}} needs attention now; no clear cause was found. What was checked and the actions are below."),
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
                  metrics: list[str] | None = None, keep_status: bool = False) -> dict:
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
        if asked and not keep_status:  # a figure was asked: the status in one clause (no kendra card follows)
            mr, en = mr.split(";")[0].rstrip(".") + ".", en.split(";")[0].rstrip(".") + "."
        lines.append({"metric": "status", "mr": mr.replace("{{e:P}}", "{{e:" + eid + "}}"), "en": en.replace("{{e:P}}", "{{e:" + eid + "}}")})
        if not asked:  # overview; an incomplete kendra gets no learning figures (it "cannot be judged yet")
            asked = [m for m in CLUSTER_OVERVIEW if not (status == "INSUFFICIENT" and m == "learning")]
    lines += answer_lines(asked, bundle["ids"][eid], eid, eid != focus, bundle["facts"][eid], bundle["period_ids"].get(eid))
    return {"scope": eid, "cluster": cluster_id if eid != focus else None, "metrics": metrics, "lines": lines}


# ---------- "why did it improve?" (rule-based, associated-with wording only) ----------

IMPROVE_WORDS = ["improve", "improved", "rose", "rise", "increase", "better", "went up", "go up", "gone up", "goes up", "चांगला", "चांगले", "चांगली", "changla",
                 "changle", "सुधार", "sudhar", "वाढ", "vadh", "प्रगती", "pragati", "उंचाव"]
DECLINE_WORDS = ["fall", "fell", "drop", "decline", "down", "घसर", "ghasar", "कमी झा", "kami zal", "worse", "खाल"]
WHY_UP = {
    "headline": ("{{e:P}} मध्ये गणिताचा निकाल या वर्षी {{n:maths_change}} गुणांनी वाढून {{n:maths_pct}} झाला.",
                 "{{e:P}}: maths rose {{n:maths_change}} points this year, to {{n:maths_pct}}."),
    "top": ("सर्वात जास्त वाढ: {items}.", "Largest rises: {items}."),
    "kp": ("याच काळात केंद्रप्रमुखांच्या भेटी दर शाळेला दरमहा {{n:kp_visits_prev}} वरून {{n:kp_visits_per_school_month}} झाल्या.",
           "Over the same period Kendra Pramukh visits went from {{n:kp_visits_prev}} to {{n:kp_visits_per_school_month}} per school per month."),
    "att": ("हजेरी {{n:attendance_prev_pct}} वरून {{n:attendance_pct}} झाली (विश्वासार्ह नोंदी).",
            "Attendance went from {{n:attendance_prev_pct}} to {{n:attendance_pct}} (trusted records)."),
    "staff": ("कार्यरत शिक्षक {{n:working_prev}} वरून {{n:working_teachers}} झाले.",
              "Working teachers went from {{n:working_prev}} to {{n:working_teachers}}."),
    "assoc": ("हे बदल वाढीशी संबंधित दिसतात; यांमुळेच वाढ झाली असे हा डेटा सिद्ध करत नाही.",
              "These changes are associated with the rise; the data does not prove they caused it."),
    "none": ("शिक्षक संख्या, हजेरी आणि केंद्रप्रमुखांच्या भेटी जवळपास तशाच राहिल्या, त्यामुळे डेटा वाढीचे स्पष्ट कारण दाखवत नाही. "
             "सर्वात जास्त वाढलेल्या केंद्रांमध्ये काय वेगळे केले ते प्रत्यक्ष विचारून घ्यावे.",
             "Teacher numbers, attendance and Kendra Pramukh visits stayed about the same, so the data shows no clear reason. "
             "Ask the clusters that rose most what they did differently."),
    "none_fell": ("वरील बदल वाढीचे कारण दाखवत नाहीत; डेटामध्ये निकालासोबत वाढलेला घटक नाही. सर्वात जास्त वाढलेल्या केंद्रांमध्ये काय वेगळे केले ते प्रत्यक्ष विचारून घ्यावे.",
                  "These changes do not explain the rise: no input in the data rose with the results. Ask the clusters that rose most what they did differently."),
    "not_up": ("{{e:P}} मध्ये गणिताचा निकाल या वर्षी वाढलेला नाही.", "{{e:P}}: maths did not rise this year."),
}
KP_MOVE, ATT_MOVE, STAFF_MOVE = 0.2, 1.0, 0.02  # smallest changes worth mentioning (visits/school/month; points; share)


TWIN_WORDS = ["similar", "twin", "than", "सारख", "समान", "जुळा", "पेक्षा", "sarkha", "sarakha", "peksha"]


def asks_twin(question: str) -> bool:
    """"Which similar block did better than X?" / "X सारखा कोणता तालुका" (the learn-from comparison, not why X improved)."""
    q = normalise(question)
    return any(w in q for w in TWIN_WORDS)


def asks_improvement(question: str) -> bool:
    q = normalise(question)
    return any(w in q for w in IMPROVE_WORDS) and not any(w in q for w in DECLINE_WORDS) and not asks_twin(question)


def improvement_lines(bundle: dict, focus: str) -> list[dict]:
    """Why a block's results rose: the rise, the kendras that rose most, and the inputs that moved with it."""
    f, ids = bundle["facts"][focus], bundle["ids"][focus]
    val = lambda name: f[name][0] if name in ids else None  # noqa: E731

    def line(key: str, extra: dict | None = None, facts: list[str] | None = None) -> dict:
        mr, en = WHY_UP[key]
        sub_ = lambda t: re.sub(r"\{\{n:([a-z_0-9]+)\}\}", lambda x: "{{n:" + ids[x.group(1)] + "}}", t).replace("{{e:P}}", "{{e:" + focus + "}}")  # noqa: E731
        mr, en = sub_(mr), sub_(en)
        if extra:
            mr, en = mr.format(**{k: v[0] for k, v in extra.items()}), en.format(**{k: v[1] for k, v in extra.items()})
        return {"metric": "why_up", "mr": mr, "en": en, "facts": facts or [ids[n] for n in re.findall(r"\{\{n:([a-z_0-9]+)\}\}", WHY_UP[key][1]) if n in ids]}

    change = val("maths_change")
    if change is None:
        return []
    if round(change, 1) <= 0:  # say so, with the actual figure
        return [line("not_up")] + answer_lines(["learning"], ids, focus, False, f)
    out = [line("headline")]
    rises = sorted(((bundle["facts"][c]["maths_change"][0], c) for c in bundle["ids"] if c != focus and c.startswith("C")
                    and "maths_change" in bundle["ids"][c]), reverse=True)
    top = [(v, c) for v, c in rises if round(v, 1) > 0][:2]
    if top:
        items = ", ".join("{{e:" + c + "}} (+{{n:" + bundle["ids"][c]["maths_change"] + "}})" for _v, c in top)
        out.append(line("top", {"items": (items, items)}, [bundle["ids"][c]["maths_change"] for _v, c in top]))
    rose, fell = [], []
    for key, prev, cur, step, rel in (("kp", "kp_visits_prev", "kp_visits_per_school_month", KP_MOVE, False),
                                       ("att", "attendance_prev_pct", "attendance_pct", ATT_MOVE, False),
                                       ("staff", "working_prev", "working_teachers", STAFF_MOVE, True)):
        if val(prev) is None or val(cur) is None:
            continue
        d = (val(cur) - val(prev)) / val(prev) if rel and val(prev) else val(cur) - val(prev)
        if d >= step:
            rose.append(line(key))
        elif d <= -step:
            fell.append(line(key))
    if rose:
        out += rose + fell + [line("assoc")]
    elif fell:
        out += fell + [line("none_fell")]
    else:
        out.append(line("none"))
    return out


# ---------- district scope ----------

DISTRICT_WORDS = ["district", "जिल्हा", "जिल्ह्यात", "जिल्ह्याचा", "जिल्ह्यातील", "jilha", "jilhyat", "zilla", "zila", "whole"]


def district_named(question: str, district_names: list[str]) -> bool:
    q = normalise(question)
    return any(w in q for w in DISTRICT_WORDS) or any(re.search(r"(?<![\wऀ-ॿ])" + re.escape(normalise(n)), q)
                                                      for n in district_names if n)


def build_district(tables: dict, trust: BlockTrust, packs: dict, entity: dict) -> dict:
    """District-wide facts (all blocks), as a bundle like build_facts (entity id = entity['id'])."""
    any_pack = next(iter(packs.values()))
    file_id = {s["file"]: s["id"] for s in any_pack["sources"]}
    files = view_files(tables)
    eid = entity["id"]
    codes = set(tables["schools"]["udise_code"])
    facts = compute_facts(tables, trust, codes, {"district": entity["name_en"]}, file_id, files)
    facts["blocks"] = (tables["schools"]["block"].nunique(), "count", 0, _q("schools", {"distinct": "block"}, tables["schools"], file_id))
    out = {"numbers": {}, "periods": {}, "entities": {eid: {k: v for k, v in entity.items() if k != "id"}}, "ids": {}, "facts": {},
           "period_ids": {}}
    ids = register_facts(out, facts, eid)
    for nid in ids.values():
        out["numbers"][nid]["entity"] = eid
    out["ids"][eid], out["facts"][eid] = ids, facts
    if "_att_period" in facts:
        pid = f"p.fact.{eid}.att"
        out["periods"][pid] = {"kind": "month_range", "from": facts["_att_period"][0], "to": facts["_att_period"][1]}
        out["period_ids"][eid] = {"att": pid}
    return out


# ---------- several questions in one message ----------

SPLIT = re.compile(r"[,;?।\n]+|\s+(?:and|आणि|ani|also|तसेच)\s+")


def segments(question: str) -> list[str]:
    """Parts of a message that each look like their own question ("X madhe shala kiti, Y PTR kiti")."""
    parts = [p.strip() for p in SPLIT.split(question) if p and p.strip()]
    return parts if len(parts) > 1 else [question]


# ---------- reply language ----------

MR_LATIN = {"kiti", "ahe", "aahe", "ahet", "aahet", "madhe", "madhye", "madhil", "cha", "chi", "che", "kay", "ka", "la", "shala",
            "shikshak", "nikal", "hajeri", "kontya", "konta", "konti", "mage", "kasa", "kase", "kashi", "zala", "zali", "aala",
            "changla", "kami", "jast", "talukyat", "talukyatil", "sanga", "vishwasarha", "aakdevari", "ghasarla", "karave"}
EN_WORDS = {"what", "how", "which", "why", "is", "are", "the", "in", "of", "many", "does", "do", "did", "has", "have", "show",
            "tell", "me", "about", "need", "needs", "most", "best", "lowest", "highest", "give", "list", "should", "i", "there",
            "attendance", "schools", "school", "teachers", "teacher", "results", "result", "maths", "vacant", "posts", "students",
            "report", "data", "reliable", "visits", "compare", "district", "block", "cluster", "ratio", "improve", "fall",
            "hello", "hi", "hey", "help", "thanks", "thank", "you", "please"}


def detect_lang(text: str, default: str = "mr") -> str:
    """Language of an officer's message: Devanagari -> mr; Marathi typed in Latin letters -> mr; English -> en."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return default
    if sum(1 for c in letters if "\u0900" <= c <= "\u097f") / len(letters) > 0.3:
        return "mr"
    tokens = set(normalise(text).split())
    mr, en = len(tokens & MR_LATIN), len(tokens & EN_WORDS)
    if mr > en:
        return "mr"
    if en:
        return "en"
    if len(tokens) >= 3 and not mr:  # a Latin-script sentence with no Marathi words is English
        return "en"
    return default


# ---------- safety and scope guards (checked by code before any analysis or AI call) ----------

WELLBEING_WORDS = ["kill myself", "killing myself", "suicide", "end my life", "want to die", "self harm", "self-harm",
                   "no reason to live", "आत्महत्या", "जगायचं नाही", "जगायचे नाही", "मरायचं आहे", "मरायचे आहे", "jagaycha nahi",
                   "jagayche nahi", "atmahatya", "marayche aahe"]
ABUSE_WORDS = ["stupid", "idiot", "useless bot", "nonsense", "shut up", "fuck", "bastard", "मूर्ख", "नालायक", "गाढव",
               "बावळट", "murkh", "nalayak", "gadhav", "bavlat"]
GROUP_WORDS = ["caste", "religion", "dalit", "maratha", "muslim", "hindu", "christian", "buddhist", "brahmin",
               "धर्म", "दलित", "मराठा", "मुस्लिम", "मुसलमान", "हिंदू", "ख्रिश्चन", "बौद्ध", "ब्राह्मण", "dharma"]
GROUP_TOKENS = {"sc", "st", "obc", "nt", "vjnt", "jain", "jaat", "जात", "जाती", "जातीनुसार", "जातीचे", "जातीच्या"}  # whole words
# ("जात" alone is a caste; inside "जाते" / "जातात" it is an everyday verb)
# other districts and big cities of Maharashtra: the demo data covers one district only
OTHER_PLACES = ["pune", "mumbai", "nagpur", "kolhapur", "nashik", "satara", "sangli", "aurangabad", "chhatrapati sambhajinagar",
                "thane", "latur", "osmanabad", "dharashiv", "ahmednagar", "ahilyanagar", "beed", "jalgaon", "nanded", "amravati",
                "akola", "ratnagiri", "sindhudurg", "raigad", "palghar", "dhule", "nandurbar", "parbhani", "hingoli", "jalna",
                "buldhana", "washim", "yavatmal", "wardha", "chandrapur", "gadchiroli", "gondia", "bhandara", "delhi", "bangalore",
                "पुणे", "मुंबई", "नागपूर", "कोल्हापूर", "नाशिक", "सातारा", "सांगली", "औरंगाबाद", "ठाणे", "लातूर", "उस्मानाबाद",
                "अहमदनगर", "बीड", "जळगाव", "नांदेड", "अमरावती", "अकोला", "रत्नागिरी"]
GENERIC_BEFORE_KENDRA = {"which", "wich", "whch", "witch", "the", "this", "that", "all", "each", "every", "my", "our", "any", "a", "of", "in", "konte",
                         "kontya", "konta", "कोणत्या", "कोणते", "कोणता", "सर्व", "प्रत्येक", "या", "त्या", "माझ्या", "best", "worst",
                         "lowest", "highest", "need", "needs", "sarvat", "सर्वात", "किती", "kiti", "kti", "how", "many", "एकूण",
                         "total", "number", "no", "मधील", "madhil", "madhe", "मध्ये", "आणि", "and", "ani", "chya", "च्या", "ki"}


def guard(question: str) -> str | None:
    """wellbeing | abuse | sensitive_group | None: questions answered by a fixed reply, before any analysis."""
    q = normalise(question)
    if any(w in q for w in WELLBEING_WORDS):
        return "wellbeing"
    if any(w in q for w in GROUP_WORDS) or set(q.split()) & GROUP_TOKENS:
        return "sensitive_group"
    if any(w in q for w in ABUSE_WORDS):
        return "abuse"
    return None


def other_place(question: str) -> str | None:
    """A place outside this district named in the question ("schools in Pune")."""
    q = normalise(question)
    for p in OTHER_PLACES:
        if re.search(r"(?<![\wऀ-ॿ])" + re.escape(p), q):
            return p
    return None


def named_kendra_word(question: str, known: list[str]) -> str | None:
    """The word right before "kendra/केंद्र/cluster" when it looks like a kendra name ("Zzyzx kendra"), else None."""
    tokens = normalise(question).split()
    known_s = {_simple(k) for k in known if k}
    for i, t in enumerate(tokens):
        if i and any(t.startswith(w) for w in ("kendra", "केंद्र", "cluster")):
            prev = tokens[i - 1]
            if prev not in GENERIC_BEFORE_KENDRA and _simple(prev) not in known_s and not prev.isdigit():
                return prev
    return None


YEAR_NOTE = ("माहिती {first} ते {last} या वर्षांची आहे; वरील आकडे सर्वात अलीकडच्या वर्षाचे आहेत. कारण भविष्याचा अंदाज देत नाही.",
             "The data covers {first} to {last}; the figures above are for the latest year. Kaaran does not forecast.")


def years_outside(question: str, first: str, last: str) -> bool:
    """A year named in the question outside the data's academic years (e.g. 2015, 2030)."""
    lo, hi = int(first[:4]), int(last[:4]) + 1
    years = [int(y) for y in re.findall(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)", question)]
    return any(y < lo or y > hi for y in years)
