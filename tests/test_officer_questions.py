"""User testing round 2 (2026-10-29): the officer questions that gave long or wrong answers, now regression tests.
Each test names the question number from docs/USER_TESTING.md."""

from __future__ import annotations

from fastapi.testclient import TestClient

from kaaran.api import create_app
from kaaran.whatsapp import REPORT_HINT, Bot, simulate


def lines(a, lang="en"):
    return [it["text"] for it in a.summary[lang]["items"] if it["section"] == "answer"]


def test_q1_ranking_shows_only_the_ranking(block_service):
    a = block_service.ask("Which block has the best maths results?")
    assert a.summary["en"]["mode"] == "rank" and lines(a)[0].startswith("Highest maths results: Malshiras")
    assert "kcard" not in a.html["en"] and '<details class="full-evidence">' in a.html["en"]  # A/B/C only behind the button


def test_q2_why_it_improved_is_explained(block_service):
    a = block_service.ask("Malshiras cha nikal changla ka aala?")
    text = " ".join(lines(a))
    assert a.summary["en"]["mode"] == "why_up" and "rose" in text and "Largest rises" in text
    assert "associated with" in text or "no clear reason" in text  # never causal wording


def test_q4_q10_counts_are_one_line(block_service):
    for q, start in (("पंढरपूर मध्ये किती शाळा आहेत?", "पंढरपूरमध्ये"), ("Pandharpur madhe kiti shala ahet", "पंढरपूरमध्ये"),
                     ("पंढरपूर मध्ये किती केंद्रे आहेत?", "पंढरपूरमध्ये")):
        a = block_service.ask(q)
        assert a.summary["mr"]["mode"] == "fact" and len(lines(a, "mr")) == 1 and lines(a, "mr")[0].startswith(start), q
    assert "12 clusters (kendras)" in lines(block_service.ask("पंढरपूर मध्ये किती केंद्रे आहेत?"))[0]


def test_q5_district_questions_get_district_figures(block_service):
    a = block_service.ask("how many schools are there in solapur")
    assert a.status == "ok" and lines(a)[0].startswith("Solapur district has") and "11 blocks" in lines(a)[0]
    assert "सोलापूर जिल्ह्यात" in lines(a, "mr")[0]


def test_q9_single_teacher_schools_one_figure(block_service):
    a = block_service.ask("How many single-teacher schools are in Sangola?")
    assert lines(a) == [lines(a)[0]] and lines(a)[0].startswith("Single-teacher schools in Sangola:")
    assert "Source:" in a.html["en"] and "teacher_posts.xlsx" in a.html["en"]


def test_q11_unreliable_records_name_the_kendra(block_service):
    a = block_service.ask("Which of madha attendance records look unreliable?")
    text = " ".join(lines(a))
    assert a.summary["en"]["mode"] == "dq" and "Kendras with suspicious records" in text and "registers in person" in text


def test_q12_three_questions_three_answers(block_service):
    a = block_service.ask("pandharpoor madhe kiti shala ahet, karmala PTR kiti, mohol la shikshak kiti kami.")
    got = lines(a)
    assert len(got) == 3 and got[0].startswith("Pandharpur has") and got[1].startswith("Karmala: pupil-teacher ratio")
    assert got[2].startswith("Vacant teacher posts in Mohol")


def test_q8_attention_gets_kendra_cards(block_service):
    a = block_service.ask("Which block needs most attention?")
    assert a.summary["en"]["mode"] == "cards" and a.html["en"].count('class="kcard ') >= 3
    assert lines(a)[0].startswith("Most attention needed: Pandharpur")


def test_voice_followup_completes_the_question(block_service):
    first = block_service.ask("which block need more attention")
    assert first.status == "ok" and first.focus == "BPandharpur"  # "need more attention" is understood now
    clar = block_service.ask("which taluka has fewest teachers vacancy")
    follow = block_service.ask("In the solapur district", context="Which block has the highest PTR?")
    assert follow.status == "ok" and follow.info["followup_of"] == "Which block has the highest PTR?"
    assert lines(follow)[0].startswith("Highest pupil-teacher ratio")
    assert clar.status in ("ok", "clarify")


def test_reply_language_follows_the_question(block_service):
    assert block_service.ask("How many schools are in Pandharpur?").info["reply_lang"] == "en"
    assert block_service.ask("पंढरपूर मध्ये किती शाळा आहेत?").info["reply_lang"] == "mr"
    assert block_service.ask("Pandharpur madhe kiti shala ahet").info["reply_lang"] == "mr"


def test_whatsapp_english_question_gets_english_short_answer(block_service):
    replies = simulate(Bot(block_service), "w-en", "What is PTR in Karmala?")
    assert all(r.lang == "en" for r in replies) and any("pupil-teacher ratio" in r.text for r in replies)
    assert replies[-1].text == REPORT_HINT[1] and not any(r.kind == "document" for r in replies)  # short answer, PDF on request


def test_whatsapp_followup_after_clarify(block_service):
    bot = Bot(block_service)
    first = simulate(bot, "w-f", "निकाल का घसरला?")
    assert len(first) == 1 and "w-f" in bot.followup
    second = simulate(bot, "w-f", "पंढरपूर")
    assert any(r.kind == "document" for r in second) and "w-f" not in bot.followup


def test_role_home_pages(block_service):
    c = TestClient(create_app(block_service, warm=False))
    deo = c.get("/api/home", params={"role": "deo"}).json()
    assert "tile" in deo["html"]["mr"] and "acard" in deo["html"]["en"] and "Pandharpur" in deo["html"]["en"]
    beo = c.get("/api/home", params={"role": "beo", "block": "BPandharpur"}).json()
    assert "kcard" in beo["html"]["en"] and beo["brief_id"] == "blocks.BPandharpur"
    nid = deo["html"]["en"].split('data-n="')[1].split('"')[0]
    assert c.get(f"/api/briefs/{deo['brief_id']}/number", params={"id": nid}).status_code == 200


# ---------- regressions from the second adversarial review (answer engine v2) ----------

def test_new_complete_question_is_not_glued_to_an_old_one(block_service):
    a = block_service.ask("How many schools in Sangola?", context="Is the data reliable?")
    assert a.summary["en"]["mode"] == "fact" and lines(a)[0].startswith("Sangola has") and "followup_of" not in a.info


def test_rankings_use_the_asked_figure(block_service):
    assert lines(block_service.ask("Which block has the highest pupil teacher ratio?"))[0].startswith("Highest pupil-teacher ratio")
    assert lines(block_service.ask("Which block has the fewest teachers?"))[0].startswith("Fewest working teachers")
    assert lines(block_service.ask("Which block has the worst data quality?"))[0].startswith("Most schools with unreliable")
    k = block_service.ask("Which cluster has the lowest attendance?")
    assert lines(k)[0].startswith("Lowest attendance: Bhalpur Kendra")  # kendras ranked, not blocks
    m = block_service.ask("सर्वात जास्त विद्यार्थी-शिक्षक प्रमाण कोणत्या तालुक्यात आहे?")
    assert m.status == "ok" and m.summary["en"]["mode"] == "rank"  # not refused as a question about people


def test_kendra_why_gets_its_card_and_attendance_improvement_is_not_maths(block_service):
    a = block_service.ask("Why did maths fall in Bhalwad Khurd?")
    assert a.summary["en"]["mode"] == "cluster" and "kcard" in a.html["en"] and "reasons and actions are below" in lines(a)[0]
    b = block_service.ask("Why did attendance improve in Pandharpur?")
    assert b.summary["en"]["mode"] != "why_up" and "attendance" in lines(b)[0]


def test_vacancies_show_teachers_above_sanction(block_service):
    t = lines(block_service.ask("How many vacant posts in Pandharpur?"))[0]
    assert "Vacant teacher posts in Pandharpur: 7" in t and "Teachers above sanction: 4" in t


def test_unknown_kendra_is_never_guessed(block_service):
    a = block_service.ask("Xyzabad kendra attendance")
    assert a.status == "clarify" and a.plan["reason"] == "unknown_kendra"


def test_whatsapp_report_opens_the_latest_answer(block_service, monkeypatch, tmp_path):
    from kaaran.block.workspace import BlockWorkspace
    from kaaran.whatsapp import simulate_alert

    stub = tmp_path / "b.pdf"
    stub.write_bytes(b"%PDF-1.4 stub")
    monkeypatch.setattr(BlockWorkspace, "pdf", lambda self, focus, lang: stub)
    bot = Bot(block_service)
    simulate_alert(bot, "w-r")  # offers Pandharpur
    simulate(bot, "w-r", "How many schools are in Mohol?")  # now offers Mohol
    replies = simulate(bot, "w-r", "report")
    assert replies[-1].kind == "document" and replies[-1].brief_id == "blocks.BMohol"
