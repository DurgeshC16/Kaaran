"""Direct answers (block lens): the officer's actual question answered first, by code, with click-to-source figures.

Facts are checked against the generator's clean tables (an independent path from the ingested raw files)."""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from kaaran.api import create_app
from kaaran.block.answers import find_cluster, is_greeting, metrics_asked, romanise


def answer_lines(a, lang="en"):
    return [it["text"] for it in a.summary[lang]["items"] if it["section"] == "answer"]


def test_metric_words_and_greetings():
    assert metrics_asked("How many schools are in Pandharpur?") == ["schools"]
    assert metrics_asked("पंढरपूर मध्ये किती शाळा आहेत?") == ["schools"]
    assert "ptr" in metrics_asked("What is PTR in Karmala?") and "attendance" in metrics_asked("सांगोला हजेरी")
    assert "attention_rank" in metrics_asked("Which block needs most attention?")
    assert "ptr" not in metrics_asked("उपस्थितीचे प्रमाण किती?") and "learning" not in metrics_asked("डेटाची गुणवत्ता")
    assert is_greeting("hello") and is_greeting("नमस्कार") and is_greeting("what can you do?")
    assert not is_greeting("which schools in Pandharpur need help with maths results this year")


def test_cluster_found_in_any_spelling(block_service):
    clusters = block_service.workspace().prepare().ingest.tables["clusters"]
    for q in ("What about Bhalwad Khurd kendra?", "भाळवड खुर्द केंद्राची हजेरी", "bhalwad khurd kendra madhe kay zale"):
        assert find_cluster(q, clusters, "Pandharpur") == "08K03", q
    assert find_cluster("Why did maths fall in Pandharpur?", clusters, "Pandharpur") is None
    assert romanise("पंढरपूर").startswith("pandh")
    twins = pd.concat([clusters, clusters[clusters["cluster_id"] == "08K03"].assign(cluster_id="99K01", block="Elsewhere")])
    assert find_cluster("What about Bhalwad Khurd kendra?", twins) is None  # same name in two blocks: never guess
    assert find_cluster("What about Bhalwad Khurd kendra?", twins, "Pandharpur") == "08K03"


def test_facts_match_the_clean_tables(block_service, block_service_folder):
    ws = block_service.workspace().prepare()
    f = ws.facts("BPandharpur")["facts"]["BPandharpur"]
    clean = {k: pd.read_parquet(block_service_folder / "clean" / f"{k}.parquet") for k in ("schools", "posts", "enrolment", "clusters")}
    codes = set(clean["schools"].loc[clean["schools"]["block_key"] == "pandharpur", "udise_code"])
    assert f["schools"][0] == len(codes) and f["clusters"][0] == clean["clusters"]["block_key"].eq("pandharpur").sum()
    posts = clean["posts"][clean["posts"]["udise_code"].isin(codes)]
    last = posts[posts["month"] == posts["month"].max()]
    assert f["working_teachers"][0] == last["working"].sum() and f["sanctioned_posts"][0] == last["sanctioned"].sum()
    assert f["vacant_posts"][0] == (last["sanctioned"] - last["working"]).clip(lower=0).sum()
    enr = clean["enrolment"][clean["enrolment"]["udise_code"].isin(codes)]
    enr = enr[enr["academic_year"] == enr["academic_year"].max()]
    assert f["ptr"][0] == pytest.approx((enr["boys"] + enr["girls"]).sum() / last["working"].sum(), rel=1e-6)
    assert all(p["kind"] in ("query", "constant") for v in f.values() if isinstance(v, tuple) and len(v) == 4 for p in v[3])


def test_factual_question_gets_a_direct_answer_with_sources(block_service):
    a = block_service.ask("How many schools are in Pandharpur?")
    n = block_service.workspace().facts("BPandharpur")["facts"]["BPandharpur"]["schools"][0]
    assert a.status == "ok" and a.focus == "BPandharpur"
    assert answer_lines(a)[0].startswith(f"Pandharpur has {n} schools")
    assert a.summary["en"]["items"][0]["section"] == "answer"  # the answer comes before the brief
    assert 'data-n="n.fact.BPandharpur.schools"' in a.html["en"] and "answer-card" in a.html["en"]
    mr = block_service.ask("पंढरपूर मध्ये किती शाळा आहेत?")
    assert answer_lines(mr, "mr")[0].startswith("पंढरपूरमध्ये") and str(n) not in answer_lines(mr, "mr")[0]  # Devanagari digits
    client = TestClient(create_app(block_service))
    d = client.get(f"/api/briefs/{a.brief_id}/number", params={"id": "n.fact.BPandharpur.schools"}).json()
    assert d["provenance"][0]["file"].endswith(".csv") and d["entity"]["en"] == "Pandharpur"


def test_ptr_attendance_teachers_and_rule_fallback(block_service):
    for q, words in (("What is PTR in Karmala?", "pupil-teacher ratio"), ("What is the attendance in Sangola?", "average attendance"),
                     ("How many teacher posts are vacant in Mohol?", "Vacant teacher posts in Mohol"),
                     ("Kendra Pramukh visits in Pandharpur", "Kendra Pramukh visits per school")):
        a = block_service.ask(q)
        assert a.status == "ok" and any(words in t for t in answer_lines(a)), q
    a = block_service.ask("What should I do about Pandharpur?")
    assert a.status == "ok" and any("What to do" in n for n in a.summary["en"]["notes"])


def test_cluster_question_opens_its_block(block_service):
    a = block_service.ask("What about Bhalwad Khurd kendra?")
    assert a.status == "ok" and a.focus == "BPandharpur" and a.plan["cluster"] == "08K03"
    lines = answer_lines(a)
    assert lines[0] == "Bhalwad Khurd Kendra needs attention now; the reasons and actions are below."
    assert a.summary["en"]["mode"] == "cluster" and 'kcard' in a.html["en"]  # that kendra's card follows
    assert any("schools" in t for t in lines) and any("maths" in t for t in lines)
    assert "Kendra Kendra" not in " ".join(lines)
    client = TestClient(create_app(block_service))
    assert client.get(f"/api/briefs/{a.brief_id}/number", params={"id": "n.fact.C08K03.schools"}).status_code == 200


def test_which_block_needs_attention_and_comparisons(block_service):
    a = block_service.ask("Which block needs most attention?")
    top = block_service.alerts()[0]
    assert a.status == "ok" and a.focus == top["block"] and answer_lines(a)[0].startswith("Most attention needed: Pandharpur")
    c = block_service.ask("Compare Pandharpur and Sangola maths results")
    lines = answer_lines(c)
    assert c.focus == "BPandharpur" and lines[0].startswith("Pandharpur: maths") and lines[1].startswith("Sangola: maths")
    assert c.summary["en"]["mode"] == "fact" and "kcard" not in c.html["en"]  # figures only, the brief behind a button
    client = TestClient(create_app(block_service))  # the compared block's figure is clickable too
    assert client.get(f"/api/briefs/{c.brief_id}/number", params={"id": "n.fact.BSangola.maths_pct"}).status_code == 200


def test_greeting_and_refusals(block_service):
    h = block_service.ask("hello")
    assert h.status == "clarify" and h.plan["reason"] == "help" and "Kaaran" in h.reply["en"]
    assert block_service.ask("What is the weather in Pandharpur?").status == "refuse"
    assert block_service.ask("Give me the names of the worst teachers in Pandharpur").plan["reason"] == "individual_people"


def test_whatsapp_reply_starts_with_the_answer(block_service):
    from kaaran.service import as_text

    a = block_service.ask("What is PTR in Karmala?")
    text = as_text(a.summary["en"])
    assert text.index("Direct answer") < text.index("pupil-teacher ratio") and "What needs attention" not in text


# ---------- regressions from the adversarial review ----------

def test_every_fact_cites_its_own_files(block_service):
    ws = block_service.workspace().prepare()
    files = {s["id"]: s["file"] for s in ws.pack("BKarmala")["sources"]}
    expected = {"posts": "teacher_posts", "attendance": "student_attendance", "assessment": "fln_assessment", "visits": "visit_log",
                "schools": "prof1", "udise_year": "enr1"}
    for nid, n in ws.facts("BKarmala")["numbers"].items():
        for p in n["provenance"]:
            if p["kind"] == "query":
                assert "source" in p and expected[p["view"]] in files[p["source"]], (nid, p)
    ptr = ws.facts("BKarmala")["numbers"]["n.fact.BKarmala.schools_ptr_over_30"]["provenance"]
    assert {p["view"] for p in ptr} == {"udise_year", "posts"}
    client = TestClient(create_app(block_service))
    ev = client.get("/api/briefs/blocks.BKarmala/evidence").json()
    assert "n.fact.BKarmala.ptr" in ev["numbers"]  # the evidence download includes the direct-answer figures


def test_blank_cells_never_break_the_answer(block_service):
    from kaaran.block.answers import build_facts

    ws = block_service.workspace().prepare()
    t = dict(ws.ingest.tables)
    codes = set(t["schools"].loc[t["schools"]["cluster_id"] == "08K01", "udise_code"])
    att = t["attendance"].copy()
    att["attendance_pct"] = att["attendance_pct"].astype("Float64")
    att.loc[att["udise_code"].isin(codes), "attendance_pct"] = pd.NA
    ass = t["assessment"].copy()
    ass["pct"] = ass["pct"].astype("Float64")
    ass.loc[ass["udise_code"].isin(codes), "pct"] = pd.NA
    t["attendance"], t["assessment"] = att, ass
    bundle = build_facts(t, ws.trust, ws.pack("BPandharpur"))  # no crash
    assert "attendance_pct" not in bundle["ids"]["C08K01"] and "maths_pct" not in bundle["ids"]["C08K01"]
    assert "attendance_pct" in bundle["ids"]["BPandharpur"]


def test_zero_teacher_school_counts_as_over_the_norm(block_service):
    from kaaran.block.answers import PTR_NORM, build_facts

    ws = block_service.workspace().prepare()
    t = dict(ws.ingest.tables)
    posts = t["posts"].copy()
    last = posts["month"] == posts["month"].max()
    y = t["udise_year"]
    enrol = y[y["academic_year"] == y["academic_year"].max()].set_index("udise_code")["enrol_total"]
    work = posts[last].set_index("udise_code")["working"]
    code = next(c for c in sorted(t["schools"].loc[t["schools"]["block"] == "Pandharpur", "udise_code"])
                if enrol.get(c, 0) > 0 and 0 < work.get(c, 0) and enrol[c] / work[c] <= PTR_NORM)  # under the norm today
    before = build_facts(t, ws.trust, ws.pack("BPandharpur"))["facts"]["BPandharpur"]
    posts.loc[last & (posts["udise_code"] == code), "working"] = 0
    t["posts"] = posts
    after = build_facts(t, ws.trust, ws.pack("BPandharpur"))["facts"]["BPandharpur"]
    assert after["zero_teacher_schools"][0] == before["zero_teacher_schools"][0] + 1
    assert after["schools_ptr_over_30"][0] == before["schools_ptr_over_30"][0] + 1  # pupils and no teacher: over any norm


def test_incomplete_kendra_and_unexplained_and_flat_wording(block_service):
    lines = answer_lines(block_service.ask("What about Malpur Khurd kendra?"))
    assert lines[0].startswith("Data for Malpur Khurd Kendra is incomplete") and not any("maths" in t for t in lines)
    asked = answer_lines(block_service.ask("maths results in Malpur Khurd kendra"))
    assert any("complete records: 7 of 11 schools" in t for t in asked)
    assert "no clear cause was found" in answer_lines(block_service.ask("What about Upwad Budruk kendra?"))[0]
    assert any("about the same as last year" in t for t in answer_lines(block_service.ask("maths results in Borpur Khurd Kendra")))


def test_rankings_by_the_asked_figure(block_service):
    a = block_service.ask("Which block has the best maths results?")
    assert a.focus == "BMalshiras" and answer_lines(a)[0].startswith("Highest maths results: Malshiras")
    p = block_service.ask("Which block has the lowest PTR?")
    assert answer_lines(p)[0].startswith("Lowest pupil-teacher ratio: South Solapur")
    m = block_service.ask("कोणत्या तालुक्यात हजेरी सर्वात कमी आहे?")
    assert answer_lines(m, "mr")[0].startswith("सर्वात कमी हजेरी: पंढरपूर")
    s = block_service.ask("सांगोल्यासारखा कोणता तालुका आहे?")  # a named block is never replaced by a ranking
    assert s.focus == "BSangola" and not s.plan.get("rank") and not s.plan.get("metric_rank")
    client = TestClient(create_app(block_service))
    nid = a.plan["answer"]["lines"][0]["en"].split("{{n:")[2].split("}}")[0]  # the second block's figure
    assert client.get(f"/api/briefs/{a.brief_id}/number", params={"id": nid}).status_code == 200


def test_kendra_matching_is_strict(block_service):
    assert block_service.ask("Gadgaon kendra attendance").plan["cluster"] == "02K09"
    moved = block_service.ask("Bhalwad Khurd kendra in Sangola")
    assert moved.focus == "BPandharpur" and any("is in Pandharpur block" in n for n in moved.summary["en"]["notes"])
    assert block_service.ask("How is Nandur Budruk kendra doing?").status == "clarify"


def test_scope_people_and_place_boundaries(block_service):
    for q in ("Best hotels in Pandharpur", "What was the cricket score in Pandharpur?", "Sangola train timings"):
        assert block_service.ask(q).status == "refuse", q
    for q in ("Give me the list of absent teachers in Pandharpur", "Which teacher in Pandharpur is absent most often?"):
        assert block_service.ask(q).plan["reason"] == "individual_people", q
    assert block_service.ask("What about Karmala?").focus == "BKarmala"
    a = block_service.ask("pandharpur madhale shala kiti?")  # "madhale" is not the Madha block
    assert a.focus == "BPandharpur" and not a.plan.get("also_named") and len(answer_lines(a)) == 1
    assert not block_service.ask("How many schools in Pandharpur?").summary["en"]["notes"]  # no pointer to an unrelated part


def test_help_is_in_the_officers_language(block_service):
    h = block_service.ask("नमस्कार")
    bullets = [l for l in h.reply["mr"].splitlines() if l.startswith("•")]
    assert bullets and all(not any(c.isascii() and c.isalpha() for c in b.replace("Pandharpur", "")) for b in bullets)
