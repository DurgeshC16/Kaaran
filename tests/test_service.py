"""Phase 4: the demo service (question -> clarify | refuse | brief), its summary text and the HTML/PDF brief."""

from __future__ import annotations

import re

import pytest

from kaaran.brief import texts as X
from kaaran.brief.html import brief_fragment, print_document
from kaaran.brief.pdf import find_browser, html_to_pdf
from kaaran.brief.render import PLACEHOLDER, render_markdown
from kaaran.eval.brief import invented_numbers
from kaaran.service import DatasetSpec, Service, as_text, number_detail, set_detail

PANDHARPUR_MR = "पंढरपूर तालुक्याचा गणिताचा निकाल का घसरला?"


def test_question_to_verified_brief(demo_service):
    a = demo_service.ask(PANDHARPUR_MR)
    assert a.status == "ok" and a.focus == "T08" and a.brief_id == "demo.T08"
    assert a.info["verified"] is True and a.info["wording"] == ["llm"]  # recorded AI wording, all checks passed
    pack = demo_service.workspace().pack("T08")
    for lang in ("mr", "en"):
        text = a.reply[lang]
        assert X.BANNER[0 if lang == "mr" else 1] in text  # SYNTHETIC marker in every reply
        assert invented_numbers(text, pack) == []  # every figure was filled in by code
        assert "{{" not in text and "{{" not in a.html[lang]
    headings = [it["section"] for it in a.summary["mr"]["items"]]
    assert headings[0] == "trend" and "main_cause" in headings and headings.count("data_warning") == 1
    assert a.summary["mr"]["notes"] == [f"तुमच्या प्रश्नाचे उत्तर अहवालाच्या '{X.SECTION_HEADINGS['main_cause'][0]}' विभागात आहे."]


def test_examples_are_answerable(demo_service):
    examples = demo_service.workspace().examples()
    statuses = [demo_service.ask(e["text"]).status for e in examples]
    assert statuses == ["ok"] * 5 + ["clarify", "refuse"]


def test_clarify_and_refuse_never_build_a_brief(demo_service):
    c = demo_service.ask("Why did maths scores fall in Mumbai?")
    assert c.status == "clarify" and c.brief_id is None and not c.html
    assert "पंढरपूर" in c.reply["mr"] and "Pandharpur" in c.reply["en"]  # offers the gazetteer
    r = demo_service.ask("Give me the phone number of the Pandharpur BEO")
    assert r.status == "refuse" and r.plan["reason"] == "personal_data" and r.brief_id is None


@pytest.mark.parametrize("question, section", [
    ("Is the attendance data of Pandharpur reliable?", "data_warning"),
    ("Which similar taluka did better than Pandharpur?", "twin"),
    ("पंढरपूर हजेरी आणि निकाल यांचा संबंध आहे का?", "appendix"),  # attendance -> the section holding that finding
])
def test_pointer_to_the_answering_section(demo_service, question, section):
    a = demo_service.ask(question)
    assert a.status == "ok"
    assert any(X.SECTION_HEADINGS[section][1] in n for n in a.summary["en"]["notes"]), a.summary["en"]["notes"]


def test_no_cause_note_when_no_main_cause(demo_service):
    ws = demo_service.workspace()
    no_cause = next(t for t, an in sorted(ws.prepare().analyses.items())
                    if "main_cause" not in {o["section"] for o in an.pack["outline"]})
    name = ws.pack(no_cause)["entities"][no_cause]["name_en"]
    a = demo_service.ask(f"Why did maths scores fall in {name}?")
    assert a.focus == no_cause and any("None of the causes" in n for n in a.summary["en"]["notes"])


def test_brief_is_cached_and_progress_reported_once(demo_service):
    calls = []
    ws = demo_service.workspace()
    ws.briefs.pop("T02", None)
    demo_service.ask("Why did maths fall in Barshi?", on_progress=lambda: calls.append(1))
    first = ws.briefs["T02"]
    demo_service.ask("How is Barshi doing in maths?", on_progress=lambda: calls.append(1))
    assert calls == [1] and ws.briefs["T02"] is first


def test_whatsapp_bold_format_and_grouped_actions(demo_service):
    a = demo_service.ask(PANDHARPUR_MR)
    text = as_text(a.summary["mr"], bold="*")
    assert text.startswith("*पुरावा अहवाल: पंढरपूर*")
    assert text.count(f"*{X.SECTION_HEADINGS['action'][0]}*") == 1  # one heading for all actions
    assert len(text) < 4096


def test_number_and_set_drill_down(demo_service):
    pack = demo_service.workspace().pack("T08")
    d = number_detail(pack, "n.count.schools.T08")
    files = {s["id"]: s["file"] for s in pack["sources"]}
    assert d["display"]["mr"] == "१४०" and d["provenance"][0]["file"] == files[d["provenance"][0]["source"]]
    schools = next(s for s, v in pack["entity_sets"].items() if v["kind"] == "school")
    sd = set_detail(pack, schools)
    assert sd["size"] == len(pack["entity_sets"][schools]["members"]) and sd["members"][0]["taluka"]["en"]
    talukas = [s for s, v in pack["entity_sets"].items() if v["kind"] == "taluka"]
    for s in talukas:
        assert all(m["taluka"] is None and m["name"]["mr"] for m in set_detail(pack, s)["members"])


def test_html_brief_escapes_prose_and_links_every_number(demo_service):
    ws = demo_service.workspace()
    pack, b = ws.pack("T08"), ws.brief("T08")
    prose = {k: dict(v) for k, v in b.prose.items()}
    prose["F.trend"]["en"] += " <script>alert(1)</script>"
    html = brief_fragment(pack, prose, "en", b.sources)
    assert "<script>" not in html and "&lt;script&gt;" in html
    refs = {m.group(2) for v in b.prose.values() for m in PLACEHOLDER.finditer(v["mr"]) if m.group(1) == "n"}
    assert refs <= set(re.findall(r'data-n="([^"]+)"', brief_fragment(pack, b.prose, "mr", b.sources)))
    doc = print_document(pack, b.prose, "mr", b.sources)
    assert 'class="num"' not in doc and X.BANNER[0] in doc  # print version: no click targets, banner kept


def test_markdown_question_line_only_for_a_decline(demo_service):
    ws = demo_service.workspace()
    for tid, an in ws.prepare().analyses.items():
        trend = next(f for f in an.pack["findings"] if f["type"] == "TREND")
        md = render_markdown(an.pack, {f["id"]: {"mr": "x", "en": "x"} for f in an.pack["findings"]}, "mr")
        assert ("**प्रश्न:**" in md) == trend["template_key"].startswith("trend.decline"), tid


@pytest.mark.slow
def test_pdf_is_one_page_per_language(demo_service):
    if find_browser() is None:
        pytest.skip("no Edge/Chrome/Chromium for PDF")
    import pypdfium2 as pdfium

    ws = demo_service.workspace()
    for lang in ("mr", "en"):
        path = ws.pdf("T08", lang)
        doc = pdfium.PdfDocument(str(path))
        assert len(doc) == 1
        assert "SYNTHETIC" in doc[0].get_textpage().get_text_range()
        doc.close()
        assert ws.pdf("T08", lang) == path  # cached: same file, not regenerated


@pytest.mark.slow
def test_missing_dataset_is_generated(tmp_path):
    svc = Service({"x": DatasetSpec("x", 7, "fictional", str(tmp_path / "x"), "x", "x")})
    ws = svc.workspace().prepare()
    assert (tmp_path / "x" / "raw").is_dir() and len(ws.analyses) == len(ws.talukas)
    assert svc.ask(ws.examples()[1]["text"]).status == "ok"


def test_html_to_pdf_without_browser(monkeypatch, tmp_path):
    from kaaran.brief import pdf as P

    monkeypatch.setattr(P, "find_browser", lambda: None)
    with pytest.raises(P.PdfUnavailable):
        html_to_pdf("<p>x</p>", tmp_path / "x.pdf")
