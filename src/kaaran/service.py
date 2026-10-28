"""Demo service: an officer's text question -> a Marathi-first answer (short reply + one-page brief).

Shared by the web demo and the WhatsApp bot. Per dataset, raw files are ingested and trust-checked once and every
taluka's evidence pack is built up front (a few seconds); briefs are written on first request and cached in memory.
All replies are built by code from the pack and the verified brief prose: no figure comes from the LLM.
"""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .analyze import Analysis, analyze_tables
from .brief import Brief, write_brief
from .brief import texts as X
from .brief.html import brief_fragment, print_document
from .brief.pdf import html_to_pdf
from .brief.render import fill
from .ingest import IngestResult, ingest
from .llm import intent
from .block.answers import is_greeting
from .llm.client import setting
from .synth.generate import generate
from .trust import TrustResult, run_trust

ROOT = Path(__file__).resolve().parents[2]
MAX_QUESTION_CHARS = 500
LANGS = ("mr", "en")


@dataclass(frozen=True)
class DatasetSpec:
    id: str
    seed: int
    names: str
    folder: str  # absolute, or relative to the repository root; generated here if raw/ is missing
    label_mr: str
    label_en: str
    kind: str = "taluka"  # taluka (v1, taluka lens) | block (v2, cluster lens)


DATASETS = {
    "blocks": DatasetSpec("blocks", 42, "solapur", "data/synthetic/block_demo",
                          "सोलापूर जिल्हा - केंद्रनिहाय (कृत्रिम डेमो डेटा)", "Solapur district - cluster lens (synthetic demo data)", "block"),
    "blocks_fictional": DatasetSpec("blocks_fictional", 7, "fictional", "data/synthetic/block_demo_fictional",
                                    "काल्पनिक जिल्हा - केंद्रनिहाय (कृत्रिम डेमो डेटा)", "Fictional district - cluster lens (synthetic demo data)", "block"),
    "solapur": DatasetSpec("solapur", 42, "solapur", "data/synthetic/demo",
                           "सोलापूर जिल्हा (कृत्रिम डेमो डेटा)", "Solapur district (synthetic demo data)"),
    "fictional": DatasetSpec("fictional", 7, "fictional", "data/synthetic/demo_fictional",
                             "काल्पनिक जिल्हा (कृत्रिम डेमो डेटा)", "Fictional district (synthetic demo data)"),
}

# ---------- fixed reply texts (Marathi first, English second) ----------

CLARIFY = {
    "unknown_place": ("हे ठिकाण या जिल्ह्याच्या डेटामध्ये सापडले नाही. कृपया यापैकी एका तालुक्याचे नाव लिहा:",
                      "I could not find that place in this district's data. Please name one of these talukas:"),
    "ambiguous_place": ("प्रश्नातील तालुका स्पष्ट नाही. कृपया एकाच तालुक्याचे नाव लिहा:",
                        "The taluka in your question is not clear. Please name one taluka:"),
    "missing_place": ("कोणत्या तालुक्याबद्दल विचारत आहात? कृपया तालुक्याचे नाव लिहा:",
                      "Which taluka are you asking about? Please name one of these talukas:"),
    "unsupported_subject": ("सध्याच्या डेटामध्ये फक्त गणिताचे निकाल आहेत. कृपया गणिताबद्दल विचारा. तालुके:",
                            "The data only has maths results. Please ask about maths. Talukas:"),
}
REFUSE = {
    "individual_people": ("मी वैयक्तिक शिक्षक किंवा विद्यार्थ्यांबद्दल माहिती देत नाही. कृपया तालुका पातळीवरील प्रश्न विचारा.",
                          "I don't answer questions about individual teachers or students. Please ask about a taluka."),
    "personal_data": ("वैयक्तिक माहिती (नावे, फोन नंबर, ओळख क्रमांक) दिली जात नाही.",
                      "I don't share personal data (names, phone numbers, identifiers)."),
    "out_of_scope": ("हा प्रश्न या शिक्षण डेटाच्या बाहेरचा आहे. मी तालुका व केंद्रांचे निकाल, हजेरी, शिक्षक, भेटी आणि डेटाच्या गुणवत्तेबद्दल उत्तर देतो.",
                     "That is outside this education data. I answer about talukas and clusters: results, attendance, teachers, visits and data quality."),
}
ANSWER_SECTION = {"why_change": "main_cause", "trend": "trend", "twin": "twin", "data_quality": "data_warning",
                  "compare_talukas": "trend"}
POINTER = ("तुमच्या प्रश्नाचे उत्तर अहवालाच्या '{heading}' विभागात आहे.", "The answer to your question is in the '{heading}' section.")
NO_CAUSE = ("तपासलेल्या कोणत्याही कारणाने पुराव्याचे निकष पूर्ण केले नाहीत; तपासलेली कारणे परिशिष्टात आहेत.",
            "None of the causes checked met the evidence rules; the causes checked are listed in the appendix.")
COMPARE = ("हा अहवाल {a} तालुक्याचा आहे. {b} तालुक्यासाठी वेगळा प्रश्न विचारा.",
           "This brief is about {a}. Ask a separate question about {b}.")
HELP_REPLY = {
    "block": ("नमस्कार! मी कारण, शिक्षण डेटा विश्लेषक (डेमो: कृत्रिम डेटा). एका तालुक्याबद्दल किंवा केंद्राबद्दल विचारा, उदा.:",
              "Hello! I am Kaaran, an education data analyst (demo: synthetic data). Ask about one block or cluster, for example:"),
    "taluka": ("नमस्कार! मी कारण, शिक्षण डेटा विश्लेषक (डेमो: कृत्रिम डेटा). एका तालुक्याबद्दल विचारा, उदा.:",
               "Hello! I am Kaaran, an education data analyst (demo: synthetic data). Ask about one taluka, for example:"),
}
YEARS_NOTE = ("विश्लेषण उपलब्ध पूर्ण कालावधीचे आहे.", "The analysis covers the full period in the data.")


@dataclass
class Answer:
    status: str  # ok | clarify | refuse
    dataset: str
    question: str
    plan: dict
    reply: dict[str, str]  # short plain-text reply per language
    focus: str | None = None
    focus_name: dict[str, str] = field(default_factory=dict)
    brief_id: str | None = None
    summary: dict = field(default_factory=dict)  # lang -> {title, banner, items[], notes[]} (ok only)
    html: dict[str, str] = field(default_factory=dict)  # lang -> interactive brief fragment (ok only)
    info: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def taluka_name(entity: dict, lang: str) -> str:
    return (entity.get("name_mr") or entity["name_en"]) if lang == "mr" else entity["name_en"]


class Workspace:
    """One dataset: ingest + trust once, all evidence packs up front, briefs and PDFs on demand."""

    kind = "taluka"

    def __init__(self, spec: DatasetSpec, root: Path = ROOT):
        self.spec = spec
        folder = Path(spec.folder)
        self.folder = folder if folder.is_absolute() else root / folder
        self._lock = threading.RLock()
        self._key_locks: dict[str, threading.Lock] = {}
        self.ingest: IngestResult | None = None
        self.trust: TrustResult | None = None
        self.analyses: dict[str, Analysis] = {}
        self.briefs: dict[str, Brief] = {}

    def prepare(self) -> Workspace:
        with self._lock:
            if self.ingest is None:
                raw = self.folder / "raw"
                if not raw.is_dir():
                    generate(seed=self.spec.seed, out=self.folder, names=self.spec.names)
                ing = ingest(raw)
                trust = run_trust(ing.tables, ing.report)
                self.analyses = {tid: analyze_tables(ing, trust, tid) for tid in sorted(ing.tables["talukas"]["taluka_id"])}
                self.ingest, self.trust = ing, trust
        return self

    @property
    def talukas(self):
        return self.prepare().ingest.tables["talukas"]

    @property
    def years(self) -> list[str]:
        return sorted(set(self.prepare().ingest.tables["scores"]["academic_year"]))

    def pack(self, focus: str) -> dict:
        return self.prepare().analyses[focus].pack

    def _key_lock(self, key: str) -> threading.Lock:
        with self._lock:
            return self._key_locks.setdefault(key, threading.Lock())

    def brief(self, focus: str) -> Brief:
        if focus not in self.briefs:
            with self._key_lock("brief:" + focus):
                if focus not in self.briefs:
                    self.briefs[focus] = write_brief(self.pack(focus))
        return self.briefs[focus]

    def print_html(self, focus: str, lang: str) -> str:
        b = self.brief(focus)
        return print_document(self.pack(focus), b.prose, lang, b.sources)

    def fragment(self, focus: str, lang: str) -> str:
        b = self.brief(focus)
        return brief_fragment(self.pack(focus), b.prose, lang, b.sources)

    def summarize(self, pack: dict, b: Brief, plan: dict, lang: str) -> dict:
        return summarize(pack, b, plan, lang, self)

    def pdf(self, focus: str, lang: str) -> Path:
        """One-page PDF of the brief (cached on disk next to the dataset; regenerated when the wording changes)."""
        doc = self.print_html(focus, lang)
        out = self.folder / "briefs" / f"brief_{focus}_{lang}.pdf"
        stamp = out.with_suffix(".html")
        with self._key_lock(f"pdf:{focus}:{lang}"):
            if not (out.exists() and stamp.exists() and stamp.read_text(encoding="utf-8") == doc):
                html_to_pdf(doc, out)
                stamp.write_text(doc, encoding="utf-8")
        return out

    def examples(self) -> list[dict]:
        """Example questions built from the gazetteer and the packs (never from the answer key)."""
        packs = {tid: a.pack for tid, a in self.prepare().analyses.items()}
        ents = {tid: p["entities"][tid] for tid, p in packs.items()}

        def first(pred):
            return next((tid for tid in sorted(packs) if pred(packs[tid], tid)), sorted(packs)[0])

        decline = first(lambda p, t: any(f["type"] == "TREND" and f["template_key"].startswith("trend.decline")
                                         for f in p["findings"]))
        flagged = first(lambda p, t: any(f["type"] == "DATA" and f["label"] == "RED_FLAG"
                                         and f["params"]["taluka"]["entity"] == t for f in p["findings"]))
        mr, en = taluka_name(ents[decline], "mr"), taluka_name(ents[decline], "en")
        fmr = taluka_name(ents[flagged], "mr")
        return [
            {"lang": "mr", "text": f"{mr} तालुक्याचा गणिताचा निकाल का घसरला?"},
            {"lang": "en", "text": f"Why did maths scores fall in {en}?"},
            {"lang": "mr-Latn", "text": f"{en.lower()} cha ganit nikal ka ghasarla?"},
            {"lang": "mr", "text": f"{fmr} तालुक्यातील हजेरीची आकडेवारी विश्वासार्ह आहे का?"},
            {"lang": "en", "text": f"Which similar taluka did better than {en}?"},
            {"lang": "mr", "text": "निकाल का घसरला?"},
            {"lang": "mr", "text": f"{mr} मधील सर्वात वाईट शिक्षकांची नावे द्या"},
        ]


class Service:
    def __init__(self, datasets: dict[str, DatasetSpec] | None = None, root: Path = ROOT, default: str | None = None,
                 voice=None):
        self.datasets = datasets or DATASETS
        if default is None:  # KAARAN_DEMO_DATASET names a dataset of the built-in registry
            default = (setting("KAARAN_DEMO_DATASET") if datasets is None else None) or next(iter(self.datasets))
        self.default = default
        if self.default not in self.datasets:
            raise ValueError(f"unknown default dataset {self.default!r}")
        self.workspaces = {k: _workspace_for(spec, root) for k, spec in self.datasets.items()}
        self._voice = voice  # SarvamClient; created lazily from settings when None

    # ---------- voice (Sarvam AI) ----------

    @property
    def voice(self):
        if self._voice is None:
            from .voice.sarvam import get_voice

            self._voice = get_voice()
        return self._voice

    def keyterms(self, dataset: str | None = None) -> list[str]:
        """Place names that bias speech recognition (Sarvam keyterms; at most 50)."""
        t = self.workspace(dataset).talukas
        names = [str(n) for col in ("taluka_mr", "taluka") if col in t for n in t[col] if isinstance(n, str) and n]
        return list(dict.fromkeys(names))[:50]

    def ask_voice(self, audio: bytes, mime: str, dataset: str | None = None, lang: str = "mr", on_progress=None) -> Answer:
        """Speech -> text (Sarvam) -> the normal question flow. Raises VoiceUnavailable when speech cannot be used."""
        tr = self.voice.stt(audio, mime, self.keyterms(dataset), language="mr" if lang == "mr" else None)
        answer = self.ask(tr.text, dataset, on_progress=on_progress)
        answer.info |= {"transcript": tr.text, "stt_language": tr.language_code, "stt_seconds": tr.seconds, "input": "voice"}
        return answer

    def voice_summary(self, brief_id: str, lang: str = "mr") -> Path:
        """One-minute spoken summary (MP3, cached) of a brief, built by code from the verified summary."""
        from .voice.script import spoken_summary

        ws, focus = self.resolve_brief(brief_id)
        plan = {"status": "ok", "taluka_id": focus, "question_type": None}
        summary = ws.summarize(ws.pack(focus), ws.brief(focus), plan, lang)
        return self.voice.tts(spoken_summary(summary, lang), lang)

    def workspace(self, dataset: str | None = None) -> Workspace:
        key = dataset or self.default
        if key not in self.workspaces:
            raise KeyError(f"unknown dataset {key!r}")
        return self.workspaces[key]

    # ---------- briefs by id ("<dataset>.<taluka_id>") ----------

    @staticmethod
    def brief_id(dataset: str, focus: str) -> str:
        return f"{dataset}.{focus}"

    def resolve_brief(self, brief_id: str) -> tuple[Workspace, str]:
        """(workspace, focus) for a brief id; KeyError for an unknown dataset or taluka."""
        dataset, _, focus = brief_id.partition(".")
        ws = self.workspace(dataset)
        if focus not in ws.prepare().analyses:
            raise KeyError(f"unknown brief {brief_id!r}")
        return ws, focus

    # ---------- the question flow ----------

    def ask(self, question: str, dataset: str | None = None, on_progress=None) -> Answer:
        """Intent -> (clarify | refuse | brief). `on_progress()` is called before a brief that is not cached yet."""
        t0 = time.monotonic()
        key = dataset or self.default
        ws = self.workspace(key)
        question = " ".join(question.split())[:MAX_QUESTION_CHARS]
        plan = intent.parse(question, ws.talukas, ws.years, tier="light", scope_note=getattr(ws, "intent_scope", ""))
        info = {"intent_source": plan.get("source"), "intent_cost_usd": plan.get("cost_usd", 0.0)}
        if getattr(ws, "kind", "taluka") == "block":  # deterministic fixes on top of the parsed plan (block/answers.py)
            plan = ws.resolve(question, plan)
        if plan["status"] != "ok" and plan.get("reason") not in ("individual_people", "personal_data") and is_greeting(question):
            # examples in the officer's language; never the refused one, never the one without a place
            ex = [e for e in ws.examples() if "नावे" not in e["text"] and "names" not in e["text"] and len(e["text"].split()) > 3]
            lens = getattr(ws, "kind", "taluka")
            reply = {lang: HELP_REPLY[lens][i] + "\n" + "\n".join(f"• {e['text']}" for e in [e for e in ex if e["lang"] == lang][:3])
                     for i, lang in enumerate(LANGS)}
            return Answer("clarify", key, question, plan | {"reason": "help"}, reply,
                          info=info | {"seconds": round(time.monotonic() - t0, 2)})
        names = {lang: ", ".join(taluka_names(ws, lang)) for lang in LANGS}
        if plan["status"] == "refuse":
            reply = {lang: REFUSE.get(plan["reason"], REFUSE["out_of_scope"])[i] for i, lang in enumerate(LANGS)}
            return Answer("refuse", key, question, plan, reply, info=info | {"seconds": round(time.monotonic() - t0, 2)})
        if plan["status"] != "ok":
            reply = {lang: f"{CLARIFY.get(plan['reason'], CLARIFY['missing_place'])[i]} {names[lang]}." for i, lang in enumerate(LANGS)}
            return Answer("clarify", key, question, plan, reply, info=info | {"seconds": round(time.monotonic() - t0, 2)})

        return self._answer(key, ws, question, plan, info, t0, on_progress)

    def open_block(self, dataset: str | None, focus: str, on_progress=None) -> Answer:
        """Open a brief directly (from an alert), without a question."""
        t0 = time.monotonic()
        key = dataset or self.default
        ws = self.workspace(key)
        if focus not in ws.prepare().analyses:
            raise KeyError(f"unknown block {focus!r}")
        plan = {"status": "ok", "taluka_id": focus, "question_type": "other", "metric": "score", "source": "alert"}
        return self._answer(key, ws, "", plan, {"intent_source": "alert", "intent_cost_usd": 0.0}, t0, on_progress)

    def alerts(self, dataset: str | None = None) -> list[dict]:
        ws = self.workspace(dataset)
        return list(ws.prepare().alerts) if getattr(ws, "kind", "taluka") == "block" else []

    def _answer(self, key, ws, question, plan, info, t0, on_progress) -> Answer:
        focus = plan["taluka_id"]
        if focus not in ws.briefs and on_progress is not None:
            on_progress()
        pack, b = ws.pack(focus), ws.brief(focus)
        if hasattr(ws, "direct_answer"):
            plan = plan | {"answer": ws.direct_answer(focus, question, plan)}
        summary = {lang: ws.summarize(pack, b, plan, lang) for lang in LANGS}
        wording = sorted(set(b.sources.values()))
        info |= {"brief_cost_usd": round(b.info.get("cost_usd", 0.0), 4), "wording": wording,
                 "llm_available": b.info.get("llm_available"), "verified": b.info.get("verification", {}).get("passed"),
                 "seconds": round(time.monotonic() - t0, 2)}
        ent = pack["entities"][focus]
        return Answer(
            "ok", key, question, plan,
            reply={lang: as_text(summary[lang]) for lang in LANGS},
            focus=focus, focus_name={lang: taluka_name(ent, lang) for lang in LANGS},
            brief_id=self.brief_id(key, focus), summary=summary,
            html={lang: (ws.answer_html(focus, plan, lang) if hasattr(ws, "answer_html") else "") + ws.fragment(focus, lang)
                  for lang in LANGS}, info=info,
        )


def _workspace_for(spec: DatasetSpec, root: Path):
    if spec.kind == "block":
        from .block.workspace import BlockWorkspace

        return BlockWorkspace(spec, root)
    return Workspace(spec, root)


def taluka_names(ws: Workspace, lang: str) -> list[str]:
    t = ws.talukas.sort_values("taluka_id")
    col = "taluka_mr" if lang == "mr" else "taluka"
    return [str(r[col]) if isinstance(r[col], str) and r[col] else str(r["taluka"]) for _, r in t.iterrows()]


def summarize(pack: dict, b: Brief, plan: dict, lang: str, ws: Workspace | None = None) -> dict:
    """Short answer from the verified brief: one line per section (first data warning only) plus pointer notes."""
    i = LANGS.index(lang)
    findings = {f["id"]: f for f in pack["findings"]}
    outline = {o["section"]: o["finding_ids"] for o in pack["outline"]}
    focus = pack["scope"]["focus"]
    items = []
    for name in X.REQUIRED_SECTIONS:
        ids = outline.get(name, [])
        if name == "data_warning":
            ids = ids[:1]
        for fid in ids:
            f = findings[fid]
            text = fill(b.prose[fid][lang], pack, lang)
            owner = ""
            if f["type"] == "ACTION":
                when = X.HORIZONS.get(f["action"].get("horizon"), ("", ""))[i]
                owner = X.ACTORS[f["action"]["actor_role"]][i] + (f", {when}" if when else "")
            items.append({"section": name, "heading": X.SECTION_HEADINGS[name][i],
                          "badge": X.BADGES[(f["type"], f["label"])][i], "text": text, "owner": owner,
                          "type": f["type"], "label": f["label"]})
    notes = []
    if plan.get("metric") == "attendance" and plan.get("question_type") != "data_quality":
        sec = next((o["section"] for o in pack["outline"] for fid in o["finding_ids"]
                    if findings[fid].get("hypothesis") == "attendance"), None)
        if sec:
            notes.append(POINTER[i].format(heading=X.SECTION_HEADINGS[sec][i]))
    else:
        sec = ANSWER_SECTION.get(plan.get("question_type"))
        if sec == "main_cause" and sec not in outline:
            notes.append(NO_CAUSE[i])
        elif sec in outline:
            notes.append(POINTER[i].format(heading=X.SECTION_HEADINGS[sec][i]))
    other = plan.get("compare_with")
    if other and other != focus and ws is not None and other in ws.analyses:
        a = taluka_name(pack["entities"][focus], lang)
        notes.append(COMPARE[i].format(a=a, b=taluka_name(ws.pack(other)["entities"][other], lang)))
    if plan.get("year_from") or plan.get("year_to"):
        notes.append(YEARS_NOTE[i])
    title = f"{X.TITLE[i]}: {taluka_name(pack['entities'][focus], lang)}"
    return {"title": title, "banner": X.BANNER[i] if pack.get("synthetic") else "", "items": items, "notes": notes}


def as_text(summary: dict, bold: str = "") -> str:
    """Plain text (bold="*" gives WhatsApp formatting)."""
    lines = [f"{bold}{summary['title']}{bold}"]
    if summary["banner"]:
        lines.append(f"⚠️ {summary['banner']}")
    section = None
    for it in summary["items"]:
        if it["section"] != section:
            lines += ["", f"{bold}{it['heading']}{bold}"]
            section = it["section"]
        badge = f"[{it['badge']}] " if it.get("badge") else ""
        lines.append(("• " if it["owner"] else "") + badge + it["text"] + (f" — {it['owner']}" if it["owner"] else ""))
    if summary["notes"]:
        lines.append("")
        lines += [f"👉 {n}" for n in summary["notes"]]
    return "\n".join(lines)


def number_detail(pack: dict, nid: str, max_rows: int = 20) -> dict:
    """Where a figure comes from: derivation, inputs and provenance (file, sheet/page, rows), for the web drill-down."""
    n = pack["numbers"][nid]
    files = {s["id"]: s["file"] for s in pack["sources"]}
    prov = []
    for p in n.get("provenance", []):
        d = dict(p)
        if "source" in d:
            d["file"] = files.get(d["source"])
        for k in ("rows", "sr_no"):
            if isinstance(d.get(k), list) and len(d[k]) > max_rows:
                d[k + "_total"], d[k] = len(d[k]), d[k][:max_rows]
        prov.append(d)
    deriv = n.get("derivation", {})
    inputs = [{"id": i, "display": pack["numbers"][i]["display"]} for i in deriv.get("inputs", []) if i in pack["numbers"]]
    ent = pack["entities"].get(n.get("entity") or "")
    return {"id": nid, "display": n["display"], "unit": n.get("unit"), "of": n.get("of"),
            "entity": {lang: taluka_name(ent, lang) for lang in LANGS} if ent else None,
            "op": deriv.get("op"), "inputs": inputs, "provenance": prov, "synthetic": pack.get("synthetic", False)}


def set_detail(pack: dict, sid: str) -> dict:
    """Members of a school or taluka set (local drill-down only; school names never go to the LLM)."""
    s = pack["entity_sets"][sid]
    rows = []
    for m in s["members"]:
        e = pack["entities"].get(m, {"name_en": m})
        t = pack["entities"].get(e.get("taluka") or "")
        rows.append({"id": m, "code": e.get("code"), "name": {lang: taluka_name(e, lang) for lang in LANGS},
                     "taluka": {lang: taluka_name(t, lang) for lang in LANGS} if t else None})
    return {"id": sid, "rule_id": s.get("rule_id"), "kind": s.get("kind"), "size": len(rows), "members": rows,
            "synthetic": pack.get("synthetic", False)}


_service: Service | None = None
_service_lock = threading.Lock()


def get_service() -> Service:
    global _service
    with _service_lock:
        if _service is None:
            _service = Service()
        return _service
