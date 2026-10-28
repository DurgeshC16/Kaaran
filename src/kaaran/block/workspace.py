"""Block-lens dataset workspace for the demo service: same interface as the taluka Workspace (prepare, talukas,
years, pack, brief, pdf, examples, summarize, fragment, print_html) plus the proactive district scan, alerts and
the baithak (review meeting) pack.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pandas as pd

from ..brief import Brief
from ..brief import texts as X
from ..brief.html import fill_html
from ..brief.pdf import html_to_pdf
from ..brief.render import fill
from ..brief.texts_block import BLOCK_HEADINGS, BLOCK_SECTIONS, BLOCK_TITLE
from ..evidence import format_number
from ..llm import intent
from . import answers as AN
from .brief import block_fragment, block_print_document, write_block_brief
from .ingest import ingest_block
from .insights import analyze_block
from .pack import _assemble
from .rubric import pick_actions
from .trust import run_block_trust

POINTER = ("तुमच्या प्रश्नाचे उत्तर अहवालाच्या '{heading}' भागात आहे.", "The answer to your question is in the '{heading}' part.")
SECTION_FOR = {"why_change": "why", "trend": "attention", "twin": "why", "data_quality": "attention", "compare_talukas": "attention"}
ALERT = ("🔔 नवीन मूल्यमापन निकाल आले ({period}). {block} तालुक्यात {n_risk} {clusters} तातडीने लक्ष देण्याची गरज आहे{data}. "
         "कारणे आणि कृतीसाठी 'अहवाल' लिहा.",
         "🔔 New assessment results are in ({period}). In {block}, {n_risk} {clusters} attention now{data}. "
         "Reply 'report' for the reasons and actions.")
CLUSTER_WORD = (("केंद्राला", "केंद्रांना"), ("cluster needs", "clusters need"))
ALERT_DATA = ("; {n_data} केंद्रातील हजेरीच्या नोंदी तपासायला हव्यात", "; records in {n_data} cluster need checking")
ACTIONS_NOTE = ("काय करावे: अहवालाच्या '{heading}' भागात प्रत्येक कृती, जबाबदार अधिकारी आणि वेळ दिली आहे.",
                "What to do: the '{heading}' part lists each action with its owner and timing.")
MOVED = ("{c} केंद्र {b} तालुक्यात आहे, म्हणून {b} तालुक्याचा अहवाल दाखवला आहे.", "{c} is in {b} block, so {b}'s brief is shown.")
DATA_METRICS = {"schools", "teachers", "ptr", "attendance", "learning", "visits"}  # figures a question can ask for
ALSO_NAMED = ("हा अहवाल {a} तालुक्याचा आहे. {b} साठी वेगळा प्रश्न विचारा.", "This brief is about {a}. Ask a separate question about {b}.")


def _num(value: int, lang: str) -> str:
    return format_number(value, "count", 0)["mr" if lang == "mr" else "en"]


INTENT_SCOPE = ("The analyst also works inside a taluka: which clusters (kendras, केंद्र) or groups of schools need "
                "attention, why, and what the officer should do. Such questions are in scope (status ok) when the "
                "taluka is clear; use question_type \"trend\" for \"which clusters need attention\".")


class BlockWorkspace:
    kind = "block"
    intent_scope = INTENT_SCOPE

    def __init__(self, spec, root: Path):
        self.spec = spec
        folder = Path(spec.folder)
        self.folder = folder if folder.is_absolute() else root / folder
        self._lock = threading.RLock()
        self._key_locks: dict[str, threading.Lock] = {}
        self.ingest = None
        self.trust = None
        self.packs: dict[str, dict] = {}
        self.briefs: dict[str, Brief] = {}
        self.alerts: list[dict] = []
        self.block_names: dict[str, str] = {}
        self._facts: dict[str, dict] = {}

    # ---- preparation and scan ----
    def prepare(self) -> BlockWorkspace:
        with self._lock:
            if self.ingest is None:
                raw = self.folder / "raw"
                if not raw.is_dir():
                    from ..synth3.generate import generate

                    generate(seed=self.spec.seed, out=self.folder, names=self.spec.names)
                ing = ingest_block(raw)
                trust = run_block_trust(ing.tables)
                packs = {}
                for name in sorted(ing.tables["schools"]["block"].unique()):
                    an = analyze_block(ing.tables, trust, name)
                    per, brief_actions, log = pick_actions(an, ing.tables)
                    pack = _assemble(ing, trust, an, per, brief_actions, log)
                    packs[pack["scope"]["focus"]] = pack
                self.packs = packs
                self.block_names = {eid: p["entities"][eid]["name_en"] for eid, p in packs.items()}
                self.ingest, self.trust = ing, trust
                self.alerts = self.scan()
        return self

    @property
    def analyses(self) -> dict[str, dict]:  # interface used by Service.resolve_brief
        return self.prepare().packs

    def scan(self) -> list[dict]:
        """Proactive district scan: one alert per block with clusters needing attention (no LLM involved)."""
        out = []
        for eid, pack in self.packs.items():
            s = pack["summary"]
            n_risk = sum(1 for v in s.values() if v["status"] == "AT_RISK")
            n_data = sum(1 for v in s.values() if v["status"] == "DATA")
            n_ins = sum(1 for v in s.values() if v["status"] == "INSUFFICIENT")
            weight = sum(v["weight"] for v in s.values())
            if not (n_risk or n_data):
                continue
            ent = pack["entities"][eid]
            period = pack["scope"]["comparison"]["current"]
            text = {}
            for i, lang in enumerate(("mr", "en")):
                block = (ent.get("name_mr") or ent["name_en"]) if lang == "mr" else ent["name_en"]
                data = ALERT_DATA[i].format(n_data=_num(n_data, lang)) if n_data else ""
                p = period.translate(str.maketrans("0123456789", "०१२३४५६७८९")) if lang == "mr" else period
                word = CLUSTER_WORD[i][0 if n_risk == 1 else 1]
                text[lang] = ALERT[i].format(period=p, block=block, n_risk=_num(n_risk, lang), clusters=word, data=data)
            out.append({"block": eid, "name": ent["name_en"], "name_mr": ent.get("name_mr"), "at_risk": n_risk, "data": n_data,
                        "insufficient": n_ins, "weight": weight, "text": text, "period": period})
        return sorted(out, key=lambda a: (-a["at_risk"], -a["weight"], a["name"]))

    # ---- interface shared with the taluka workspace ----
    @property
    def talukas(self) -> pd.DataFrame:
        self.prepare()
        rows = [{"taluka_id": eid, "taluka": p["entities"][eid]["name_en"], "taluka_mr": p["entities"][eid].get("name_mr")}
                for eid, p in self.packs.items()]
        return pd.DataFrame(rows)

    @property
    def years(self) -> list[str]:
        w = next(iter(self.prepare().packs.values()))["scope"]["comparison"]
        return [w["previous"], w["current"]]

    def pack(self, focus: str) -> dict:
        return self.prepare().packs[focus]

    def _key_lock(self, key: str) -> threading.Lock:
        with self._lock:
            return self._key_locks.setdefault(key, threading.Lock())

    # ---- direct answers (facts computed by code; see block/answers.py) ----
    def facts(self, focus: str) -> dict:
        if focus not in self._facts:
            with self._key_lock("facts:" + focus):
                if focus not in self._facts:
                    self._facts[focus] = AN.build_facts(self.prepare().ingest.tables, self.trust, self.pack(focus))
        return self._facts[focus]

    def answer_pack(self, focus: str, extra: tuple | list = ()) -> dict:
        """The evidence pack plus the direct-answer facts of this block (and of compared blocks), for filling and
        the click-to-source drill-down."""
        pack = self.pack(focus)
        out = pack | {"numbers": dict(pack["numbers"]), "periods": dict(pack["periods"]), "entities": dict(pack["entities"])}
        for b in dict.fromkeys([focus, *extra]):
            f = self.facts(b)
            out["numbers"] |= f["numbers"]
            out["periods"] |= f["periods"]
            out["entities"] = f["entities"] | {b: self.packs[b]["entities"][b]} | out["entities"]
        return out

    def fact_block(self, nid: str) -> str | None:
        """Block that owns a direct-answer fact id (n.fact.<block or C+cluster>.<name>), for the drill-down."""
        parts = nid.split(".")
        if len(parts) < 4 or parts[:2] != ["n", "fact"]:
            return None
        eid = parts[2]
        if eid in self.prepare().packs:
            return eid
        cl = self.ingest.tables["clusters"].set_index("cluster_id")
        if eid.startswith("C") and eid[1:] in cl.index:
            block = cl.loc[eid[1:], "block"]
            return next((b for b, p in self.packs.items() if p["entities"][b]["name_en"] == block), None)
        return None

    def _names(self) -> dict[str, list[str]]:
        return {eid: [p["entities"][eid]["name_en"], p["entities"][eid].get("name_mr") or ""] for eid, p in self.packs.items()}

    def _block_of(self, cluster_id: str) -> str | None:
        block = self.ingest.tables["clusters"].set_index("cluster_id").loc[cluster_id, "block"]
        return next((b for b, p in self.packs.items() if p["entities"][b]["name_en"] == block), None)

    def resolve(self, question: str, plan: dict) -> dict:
        """Block-lens plan fixes by code, on top of the parsed plan:
        - a named kendra opens its block (a kendra named with the wrong block opens the kendra's block, with a note);
        - "which block needs most attention" opens the top alert; "which block has the lowest PTR" ranks blocks by it;
        - a data question naming a block is never refused as out of scope; a second named block is answered alongside.
        People / personal-data refusals and off-topic refusals are never overridden."""
        self.prepare()
        if plan["status"] == "refuse" and plan.get("reason") != "out_of_scope":
            return plan
        q = AN.normalise(question)
        if plan["status"] == "refuse" and any(w in q for w in intent.OFF_TOPIC):
            return plan
        gaz = intent.gazetteer(self.talukas)
        places = intent.places_in(question, gaz)
        metrics = AN.metrics_asked(question)
        data_metrics = [m for m in metrics if m in DATA_METRICS]
        names = self._names()
        all_names = [n for ns in names.values() for n in ns]
        clusters = self.ingest.tables["clusters"]
        if places:
            if plan["status"] != "ok":
                if not (data_metrics or intent.is_bare_place(question, gaz)):
                    return plan
                plan = plan | {"status": "ok", "taluka_id": places[0], "reason": None, "question_type": "other"}
            cid = AN.cluster_named(question, clusters, names[plan["taluka_id"]][0], all_names)
            moved = None
            if cid is None:  # a kendra of another block named together with this block: open the kendra's block
                other = AN.cluster_named(question, clusters, None, all_names)
                if other is not None and self._block_of(other) not in (None, plan["taluka_id"]) and plan["taluka_id"] in places:
                    moved, cid = plan["taluka_id"], other
                    plan = plan | {"taluka_id": self._block_of(other)}
            others = [] if moved else [p for p in [plan.get("compare_with"), *places] if p and p != plan["taluka_id"]]
            return plan | {"cluster": cid, "also_named": list(dict.fromkeys(others))[:1], "cluster_moved_from": moved}
        cid = AN.cluster_named(question, clusters, None, all_names)
        if cid is not None and self._block_of(cid):
            return plan | {"status": "ok", "taluka_id": self._block_of(cid), "reason": None,
                           "question_type": plan.get("question_type") if plan["status"] == "ok" else "trend", "cluster": cid}
        sup = AN.superlative(question)
        metric = data_metrics[0] if data_metrics else ("learning" if sup in ("good", "bad") else None)
        order = AN.rank_order(metric, sup) if (sup and metric and not ("attention_rank" in metrics and not data_metrics)) else None
        if order:
            ranked = self._rank_blocks(*order)
            if ranked:
                return plan | {"status": "ok", "taluka_id": ranked[0][0], "reason": None, "question_type": "other",
                               "metric_rank": {"fact": order[0], "order": order[1], "blocks": [b for b, _ in ranked]}}
        if "attention_rank" in metrics and self.alerts:
            return plan | {"status": "ok", "taluka_id": self.alerts[0]["block"], "reason": None, "question_type": "trend", "rank": True}
        if plan["status"] == "refuse" and data_metrics:
            return plan | {"status": "clarify", "reason": "missing_place"}  # a data question without a place
        return plan

    def _rank_blocks(self, fact: str, order: str, top: int = 3) -> list[tuple[str, str]]:
        """[(block id, number id)] of the top blocks by a direct-answer fact (ties broken by name)."""
        rows = []
        for b in self.packs:
            f = self.facts(b)
            if fact in f["ids"][b]:
                rows.append((f["facts"][b][fact][0], self.packs[b]["entities"][b]["name_en"], b, f["ids"][b][fact]))
        rows.sort(key=lambda r: ((-r[0] if order == "desc" else r[0]), r[1]))
        return [(b, nid) for _v, _n, b, nid in rows[:top]]

    def direct_answer(self, focus: str, question: str, plan: dict) -> dict:
        empty = {"scope": focus, "cluster": None, "metrics": [], "lines": [], "rank": [], "also_named": [], "extra": [],
                 "why": False, "moved_from": None}
        if not question:
            return empty
        try:
            return self._direct_answer(focus, question, plan)
        except (KeyError, ValueError, TypeError, ArithmeticError):  # a figure that cannot be computed never blocks the brief
            return empty | {"error": True}

    def _direct_answer(self, focus: str, question: str, plan: dict) -> dict:
        others = [b for b in plan.get("also_named") or [] if b in self.packs and b != focus]
        metrics = AN.metrics_asked(question)
        mr = plan.get("metric_rank")
        if mr:
            ids = [(b, self.facts(b)["ids"][b][mr["fact"]]) for b in mr["blocks"]]
            ans = {"scope": focus, "cluster": None, "metrics": metrics, "lines": [AN.rank_line(mr["fact"], mr["order"], ids)],
                   "extra": [b for b in mr["blocks"] if b != focus]}
        else:
            if others and not plan.get("cluster") and not [m for m in metrics if m in DATA_METRICS]:
                metrics = metrics + ["learning"]  # "compare A and B" without a metric: compare results
            ans = AN.direct_answer(question, self.facts(focus), self.pack(focus), plan.get("cluster"), metrics)
            extra = []
            if others and not plan.get("cluster"):  # the same figures for the other named block, side by side
                for b in others:
                    more = AN.direct_answer(question, self.facts(b), self.pack(b), None, metrics)["lines"]
                    if more:
                        ans["lines"] += more
                        extra.append(b)
            ans["extra"] = extra
        ans["rank"] = [{"block": a["block"], "at_risk": a["at_risk"]} for a in self.alerts[:3]] if plan.get("rank") else []
        ans["also_named"] = others
        ans["why"] = AN.asks_why(question)
        ans["moved_from"] = plan.get("cluster_moved_from")
        return ans

    def _answer_texts(self, focus: str, ans: dict, lang: str, html: bool) -> list[str]:
        i = 0 if lang == "mr" else 1
        out = []
        if ans.get("rank"):
            items = ", ".join(AN.RANK_ITEM[i][0 if r["at_risk"] == 1 else 1].format(name=self._block_label(r["block"], lang),
                                                                                    n=_num(r["at_risk"], lang))
                              for r in ans["rank"])
            text = AN.RANK_LINE[i].format(items=items)
            out.append(_esc(text) if html else text)
        if ans.get("lines"):
            ap = self.answer_pack(focus, ans.get("extra", []))
            out += [(fill_html if html else fill)(ln[lang], ap, lang) for ln in ans["lines"]]
        return out

    def _block_label(self, eid: str, lang: str) -> str:
        ent = self.packs[eid]["entities"][eid]
        return (ent.get("name_mr") or ent["name_en"]) if lang == "mr" else ent["name_en"]

    def answer_html(self, focus: str, plan: dict, lang: str) -> str:
        ans = plan.get("answer") or {}
        texts = self._answer_texts(focus, ans, lang, html=True)
        if not texts:
            return ""
        i = 0 if lang == "mr" else 1
        body = "".join(f"<p>{t}</p>" for t in texts)
        return f'<section class="direct-answer"><h3>{_esc(AN.ANSWER_HEADING[i])}</h3>{body}</section>'

    def brief(self, focus: str) -> Brief:
        if focus not in self.briefs:
            with self._key_lock("brief:" + focus):
                if focus not in self.briefs:
                    self.briefs[focus] = write_block_brief(self.pack(focus))
        return self.briefs[focus]

    def print_html(self, focus: str, lang: str) -> str:
        b = self.brief(focus)
        return block_print_document(self.pack(focus), b.prose, lang, b.sources)

    def pdf(self, focus: str, lang: str) -> Path:
        doc = self.print_html(focus, lang)
        out = self.folder / "briefs" / f"block_{focus}_{lang}.pdf"
        stamp = out.with_suffix(".html")
        with self._key_lock(f"pdf:{focus}:{lang}"):
            if not (out.exists() and stamp.exists() and stamp.read_text(encoding="utf-8") == doc):
                html_to_pdf(doc, out)
                stamp.write_text(doc, encoding="utf-8")
        return out

    def fragment(self, focus: str, lang: str) -> str:
        b = self.brief(focus)
        return block_fragment(self.pack(focus), b.prose, lang, b.sources)

    def examples(self) -> list[dict]:
        self.prepare()
        top = self.alerts[0]["block"] if self.alerts else next(iter(self.packs))
        ent = self.packs[top]["entities"][top]
        mr, en = ent.get("name_mr") or ent["name_en"], ent["name_en"]
        return [
            {"lang": "mr", "text": f"{mr} तालुक्यात कोणत्या केंद्रांकडे लक्ष द्यावे?"},
            {"lang": "en", "text": f"Which clusters in {en} need attention?"},
            {"lang": "mr-Latn", "text": f"{en.lower()} talukyat konte kendra mage aahe?"},
            {"lang": "mr", "text": f"{mr} तालुक्यातील हजेरीची आकडेवारी विश्वासार्ह आहे का?"},
            {"lang": "en", "text": f"Which similar block did better than {en}?"},
            {"lang": "mr", "text": "निकाल का घसरला?"},
            {"lang": "mr", "text": f"{mr} मधील सर्वात वाईट शिक्षकांची नावे द्या"},
        ]

    def summarize(self, pack: dict, b: Brief, plan: dict, lang: str) -> dict:
        """Short three-part answer: A (all), B (main lines), C (brief actions), plus a pointer note."""
        i = 0 if lang == "mr" else 1
        findings = {f["id"]: f for f in pack["findings"]}
        items = []
        focus_id = pack["scope"]["focus"]
        ans = plan.get("answer") or {}
        for text in self._answer_texts(focus_id, ans, lang, html=False):
            items.append({"section": "answer", "heading": AN.ANSWER_HEADING[i], "badge": "", "text": text, "owner": "",
                          "type": "FACT", "label": ""})
        for o in pack["outline"]:
            if o["section"] not in BLOCK_SECTIONS:
                continue
            for fid in o["finding_ids"]:
                f = findings[fid]
                owner = ""
                if f["type"] == "ACTION":
                    when = X.HORIZONS.get(f["action"].get("horizon"), ("", ""))[i]
                    owner = X.ACTORS[f["action"]["actor_role"]][i] + (f", {when}" if when else "")
                items.append({"section": o["section"], "heading": BLOCK_HEADINGS[o["section"]][i],
                              "badge": X.BADGES[(f["type"], f["label"])][i], "text": fill(b.prose[fid][lang], pack, lang),
                              "owner": owner, "type": f["type"], "label": f["label"]})
        notes = []
        sec = SECTION_FOR.get(plan.get("question_type"))
        if "actions" in ans.get("metrics", []):
            notes.append(ACTIONS_NOTE[i].format(heading=BLOCK_HEADINGS["action"][i]))
        elif sec and (ans.get("why") or (not ans.get("lines") and plan.get("question_type") != "why_change")):
            notes.append(POINTER[i].format(heading=BLOCK_HEADINGS[sec][i]))
        if ans.get("moved_from") in self.packs and plan.get("cluster"):
            cl = self.facts(focus_id)["entities"].get(f"C{plan['cluster']}", {})
            cname = (cl.get("name_mr") or cl.get("name_en", "")) if lang == "mr" else cl.get("name_en", "")
            notes.append(MOVED[i].format(c=cname, b=self._block_label(focus_id, lang)))
        for other in ans.get("also_named", []):
            if other in self.packs:
                notes.append(ALSO_NAMED[i].format(a=self._block_label(focus_id, lang), b=self._block_label(other, lang)))
        focus = pack["entities"][pack["scope"]["focus"]]
        name = (focus.get("name_mr") or focus["name_en"]) if lang == "mr" else focus["name_en"]
        return {"title": f"{BLOCK_TITLE[i]}: {name}", "banner": X.BANNER[i] if pack.get("synthetic") else "",
                "items": items, "notes": notes}

    # ---- baithak (review meeting) pack and action tracker ----
    def _tracker_path(self) -> Path:
        return self.folder / "actions.json"

    def tracker(self) -> dict:
        p = self._tracker_path()
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    def set_action(self, focus: str, action_finding: str, status: str) -> dict:
        if status not in ("confirmed", "done", "open"):
            raise ValueError("status must be open, confirmed or done")
        pack = self.pack(focus)
        if action_finding not in {f["id"] for f in pack["findings"] if f["type"] == "ACTION"}:
            raise KeyError(f"unknown action {action_finding!r}")
        with self._lock:
            data = self.tracker()
            data[f"{focus}:{action_finding}"] = {"status": status, "at": time.strftime("%Y-%m-%d %H:%M")}
            self._tracker_path().parent.mkdir(parents=True, exist_ok=True)
            self._tracker_path().write_text(json.dumps(data, indent=1), encoding="utf-8")
        return data[f"{focus}:{action_finding}"]

    def baithak(self, focus: str, lang: str) -> dict:
        """Every rubric action for the block (brief + appendix), grouped by owner, with its evidence and status."""
        i = 0 if lang == "mr" else 1
        pack, b = self.pack(focus), self.brief(focus)
        findings = {f["id"]: f for f in pack["findings"]}
        status = self.tracker()
        groups: dict[str, list] = {}
        for f in pack["findings"]:
            if f["type"] != "ACTION":
                continue
            act = f["action"]
            evidence = [fill(b.prose[x][lang], pack, lang) for x in _evidence_ids(pack, f)]
            entry = {"id": f["id"], "text": fill(b.prose[f["id"]][lang], pack, lang),
                     "when": X.HORIZONS.get(act.get("horizon"), ("", ""))[i], "rubric_id": act["rubric_id"],
                     "follow_up": act["follow_up"], "evidence": evidence,
                     "status": status.get(f"{focus}:{f['id']}", {}).get("status", "open"),
                     "cluster": pack["entities"].get(f["params"].get("cluster", {}).get("entity", ""), {}).get("name_en"),
                     "funding": _funding_text(act.get("funded_under"), lang)}
            groups.setdefault(X.ACTORS[act["actor_role"]][i], []).append(entry)
        title = ("बैठक पॅक: " if lang == "mr" else "Review meeting pack: ") + pack["entities"][focus]["name_en"]
        return {"title": title, "banner": X.BANNER[i] if pack.get("synthetic") else "", "groups": groups}


def _funding_text(f: dict | None, lang: str) -> str:
    """Citation of the budget line that can pay for an action (never a figure)."""
    if not f:
        return ""
    if lang == "mr":
        mr_digits = str.maketrans("0123456789", "०१२३४५६७८९")
        # the budget code stays exactly as printed in the PAB (e.g. C476); year and page in Devanagari digits
        return f"निधी: समग्र शिक्षा PAB {'2026-27'.translate(mr_digits)} ({f['code']}, पान {str(f['page']).translate(mr_digits)}): {f['mr']}"
    return f"Funded under: {f['source']} ({f['code']}, p.{f['page']}): {f['component']} - {f['item']}"


def _evidence_ids(pack: dict, action: dict) -> list[str]:
    """Findings an action rests on: the cluster's risk/data and diagnosis findings."""
    cl = action["params"].get("cluster", {}).get("entity")
    if not cl:
        return [f["id"] for f in pack["findings"] if f["id"] == "F.twin"]
    out = []
    for f in pack["findings"]:
        if f["type"] in ("RISK", "DATA", "CAUSE") and f["params"].get("cluster", {}).get("entity") == cl:
            out.append(f["id"])
    return out[:3]


def _esc(text: str) -> str:
    import html

    return html.escape(text)
