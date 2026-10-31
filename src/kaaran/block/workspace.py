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
from ..brief.texts_block import BLOCK_TITLE
from ..evidence import format_number
from ..llm import intent
from . import answers as AN
from . import view as V
from .brief import block_fragment, block_print_document, write_block_brief
from .ingest import ingest_block
from .insights import analyze_block
from .pack import _assemble
from .rubric import pick_actions
from .trust import run_block_trust

ALERT = ("🔔 नवीन मूल्यमापन निकाल आले ({period}). {block} तालुक्यात {n_risk} {clusters} तातडीने लक्ष देण्याची गरज आहे{data}. "
         "कारणे आणि कृतीसाठी 'अहवाल' लिहा.",
         "🔔 New assessment results are in ({period}). In {block}, {n_risk} {clusters} attention now{data}. "
         "Reply 'report' for the reasons and actions.")
CLUSTER_WORD = (("केंद्राला", "केंद्रांना"), ("cluster needs", "clusters need"))
ALERT_DATA = ("; {n_data} केंद्रातील हजेरीच्या नोंदी तपासायला हव्यात", "; records in {n_data} cluster need checking")
ACTIONS_NOTE = ("काय करावे: अहवालाच्या '{heading}' भागात प्रत्येक कृती, जबाबदार अधिकारी आणि वेळ दिली आहे.",
                "What to do: the '{heading}' part lists each action with its owner and timing.")
MOVED = ("{c} केंद्र {b} तालुक्यात आहे, म्हणून {b} तालुक्याचा अहवाल दाखवला आहे.", "{c} is in {b} block, so {b}'s brief is shown.")
DATA_METRICS = {"schools", "clusters", "teachers", "single_teacher", "vacancies", "pupils", "ptr", "attendance", "learning",
                "visits"}  # figures a question can ask for
DQ_BLOCKS = ("संशयास्पद हजेरी नोंदी असलेले तालुके (शाळा): {items}.", "Blocks with suspicious attendance records (schools): {items}.")
EVIDENCE_TOP = ("📄 सर्वाधिक लक्ष हवा असलेल्या तालुक्याचा ({name}) पूर्ण पुरावा अहवाल", "📄 Full evidence brief of the top-priority block ({name})")
DQ_LINES = {
    "flagged": ("संशयास्पद नोंदी असलेली केंद्रे (शाळा): {items}. सलग ३ किंवा अधिक महिने १००% हजेरी नोंदवली आहे; तपासणी होईपर्यंत "
                "ही हजेरी विश्लेषणात वापरलेली नाही. केंद्रप्रमुखांनी या आठवड्यात हजेरी रजिस्टर प्रत्यक्ष तपासावे.",
                "Kendras with suspicious records (schools): {items}. They reported 100% attendance for 3 or more months in a row; "
                "this attendance is not used in the analysis until checked. The Kendra Pramukh should check the registers in person this week."),
    "missing": ("अपूर्ण माहिती असलेली केंद्रे (शाळा): {items}. हजेरीचे महिने किंवा मूल्यमापन फेरी नाही; ही माहिती पूर्ण करून घ्यावी.",
                "Kendras with incomplete data (schools): {items}. Attendance months or an assessment round are missing; get them completed."),
}
ALSO_NAMED = ("हा अहवाल {a} तालुक्याचा आहे. {b} साठी वेगळा प्रश्न विचारा.", "This brief is about {a}. Ask a separate question about {b}.")


def _num(value: int, lang: str) -> str:
    return format_number(value, "count", 0)["mr" if lang == "mr" else "en"]


HOME = {
    "deo_title": ("{name}: आजचे चित्र", "{name}: today's picture"),
    "beo_title": ("{name} तालुका: माझी केंद्रे", "{name} block: my kendras"),
    "schools": ("शाळा", "Schools"), "clusters": ("केंद्रे", "Kendras"), "teachers": ("कार्यरत शिक्षक", "Teachers working"),
    "vacant": ("रिक्त पदे", "Vacant posts"), "ptr": ("विद्यार्थी-शिक्षक प्रमाण", "Pupil-teacher ratio"),
    "attendance": ("हजेरी (३ महिने)", "Attendance (3 months)"), "maths": ("गणित निकाल", "Maths result"),
    "vs_last": ("मागील वर्षापेक्षा", "vs last year"), "change": ("बदल (गुण)", "Change (points)"),
    "need_attention": ("लक्ष देण्याची गरज असलेले तालुके", "Blocks that need attention"), "open": ("उघडा", "Open"),
    "all_blocks": ("सर्व तालुके एका नजरेत", "All blocks at a glance"), "block": ("तालुका", "Block"),
    "kendras_risk": ("लक्ष हवे असलेली केंद्रे", "Kendras needing attention"),
    "my_kendras": ("लक्ष देण्याची गरज असलेली केंद्रे", "Kendras that need attention"),
    "all_kendras": ("सर्व केंद्रे", "All kendras"), "kendra": ("केंद्र", "Kendra"), "state": ("स्थिती", "Status"),
    "alert": ("{block}: {n} केंद्रांना तातडीने लक्ष हवे", "{block}: {n} kendras need attention now"),
    "alert_one": ("{block}: {n} केंद्राला तातडीने लक्ष हवे", "{block}: {n} kendra needs attention now"),
    "alert_data": ("; {n} केंद्रातील नोंदी तपासा", "; check records in {n}"),
    "results": ("निकाल", "results"),
    "status": {"AT_RISK": ("तातडीने लक्ष", "Needs attention"), "DATA": ("नोंदी तपासा", "Check records"),
               "INSUFFICIENT": ("अपूर्ण माहिती", "Incomplete data"), "OK": ("ठीक", "OK")},
}
STATUS_ORDER = {"AT_RISK": 0, "DATA": 1, "INSUFFICIENT": 2, "OK": 3}

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
        self._district: dict | None = None

    # ---- preparation and scan ----
    def prepare(self) -> BlockWorkspace:
        with self._lock:
            if self.ingest is None:
                raw = self.folder / "raw"
                if not raw.is_dir():
                    from ..synth3.generate import generate

                    generate(seed=self.spec.seed, out=self.folder, names=self.spec.names)
                cached = self._load_prepared(raw)
                if cached is not None:  # built at image build time (python -m kaaran.warm): fast start on small hosts
                    ing, trust, packs, self._facts, self._district = cached
                else:
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

    # ---- prepared-state cache (only written by `python -m kaaran.warm`; keyed on the raw files and the code) ----
    def _prepared_key(self, raw: Path) -> str:
        import hashlib

        h = hashlib.sha256()
        for f in sorted(raw.rglob("*")):
            if f.is_file():
                h.update(f"{f.relative_to(raw)}:{f.stat().st_size}".encode())
        for f in sorted(Path(__file__).resolve().parents[1].rglob("*.py")):  # any code change invalidates the cache
            h.update(f.read_bytes())
        return h.hexdigest()

    def _load_prepared(self, raw: Path):
        import pickle

        path = self.folder / "prepared.pkl"
        if not path.exists():
            return None
        try:
            with path.open("rb") as fh:
                key, state = pickle.load(fh)
            return state if key == self._prepared_key(raw) else None
        except Exception:  # noqa: BLE001 - a stale or broken cache is simply rebuilt
            return None

    def save_prepared(self) -> Path:
        """Write the prepared state (ingest, trust, packs, direct-answer facts) next to the data."""
        import pickle

        self.prepare()
        self.district()
        for b in self.packs:
            self.facts(b)
        path = self.folder / "prepared.pkl"
        with path.open("wb") as fh:
            pickle.dump((self._prepared_key(self.folder / "raw"), (self.ingest, self.trust, self.packs, self._facts, self._district)),
                        fh, protocol=pickle.HIGHEST_PROTOCOL)
        return path

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

    def district_entity(self) -> dict:
        pack = next(iter(self.prepare().packs.values()))
        eid = pack["scope"]["district"]
        named = getattr(self.spec, "names", "") == "solapur"
        return {"id": eid, "kind": "district", "name_en": "Solapur district" if named else "Demo district",
                "name_mr": "सोलापूर" if named else "डेमो"}  # Marathi templates add जिल्ह्यात / जिल्हा

    def district(self) -> dict:
        if self._district is None:
            with self._key_lock("district"):
                if self._district is None:
                    self._district = AN.build_district(self.prepare().ingest.tables, self.trust, self.packs, self.district_entity())
        return self._district

    def answer_pack(self, focus: str, extra: tuple | list = ()) -> dict:
        """The evidence pack plus the direct-answer facts of this block, the district, and any compared blocks
        (for filling and for the click-to-source drill-down)."""
        pack = self.pack(focus)
        out = pack | {"numbers": dict(pack["numbers"]), "periods": dict(pack["periods"]), "entities": dict(pack["entities"])}
        d = self.district()
        out["numbers"] |= d["numbers"]
        out["periods"] |= d["periods"]
        out["entities"] = out["entities"] | d["entities"]  # the district's display name (the pack keeps a code name)
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
        - several questions in one message are answered part by part ("X shala kiti, Y PTR kiti");
        - a named kendra opens its block (a kendra named with the wrong block opens the kendra's block, with a note);
        - "which block needs most attention" opens the top alert; "which block has the lowest PTR" ranks blocks by it;
        - a question about the district (or a figure asked without any place) gets district figures;
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
        if not places and AN.other_place(question):  # "schools in Pune": never answer with this district's figures
            return plan | {"status": "clarify", "reason": "other_district", "taluka_id": None}
        kendra_names = [str(n).replace(" Kendra", "") for n in clusters["cluster_name"]] + all_names
        unknown_kendra = AN.named_kendra_word(question, [w for n in kendra_names for w in n.split()])
        segs = self._segments(question, gaz)
        if segs:
            first = next((b for sg in segs for b in sg["blocks"]), None) or next(
                (sg["ranked"][0][2] for sg in segs if sg.get("ranked")), None)
            if first:
                return plan | {"status": "ok", "taluka_id": first, "reason": None, "question_type": "other", "segments": segs,
                               "cluster": None}
        sup = AN.superlative(question)
        metric = data_metrics[0] if data_metrics else ("data_quality" if "data_quality" in metrics else
                                                        ("learning" if sup in ("good", "bad") else None))
        order = AN.rank_order(metric, sup) if (sup and metric and not ("attention_rank" in metrics and not data_metrics)) else None
        kendra_q = any(w in q for w in AN.CLUSTER_WORDS)
        if order and kendra_q:  # "which kendra (in X) has the lowest attendance?": rank the kendras, not the blocks
            items, tied = self._rank_clusters(*order, block=places[0] if places else None)
            if items:
                return plan | {"status": "ok", "taluka_id": items[0][2], "reason": None, "question_type": "other", "cluster": None,
                               "metric_rank": {"fact": order[0], "order": order[1], "items": items, "tied": tied, "level": "cluster"}}
        if places:
            if plan["status"] != "ok":
                if not (data_metrics or intent.is_bare_place(question, gaz) or AN.asks_twin(question) or len(places) > 1
                        or "data_quality" in metrics):
                    return plan
                plan = plan | {"status": "ok", "taluka_id": places[0], "reason": None, "question_type": "other"}
            cid = AN.cluster_named(question, clusters, names[plan["taluka_id"]][0], all_names)
            if cid is None and unknown_kendra and AN.cluster_named(question, clusters, None, all_names) is None:
                return plan | {"status": "clarify", "reason": "unknown_kendra", "taluka_id": None}  # "Zzyzx kendra in X"
            moved = None
            if cid is None:  # a kendra of another block named together with this block: open the kendra's block
                other = AN.cluster_named(question, clusters, None, all_names)
                if other is not None and self._block_of(other) not in (None, plan["taluka_id"]) and plan["taluka_id"] in places:
                    moved, cid = plan["taluka_id"], other
                    plan = plan | {"taluka_id": self._block_of(other)}
            others = [] if moved else [p for p in [plan.get("compare_with"), *places] if p and p != plan["taluka_id"]]
            return plan | {"cluster": cid, "also_named": list(dict.fromkeys(others))[:2], "cluster_moved_from": moved}
        cid = AN.cluster_named(question, clusters, None, all_names)
        if cid is not None and self._block_of(cid):
            return plan | {"status": "ok", "taluka_id": self._block_of(cid), "reason": None,
                           "question_type": plan.get("question_type") if plan["status"] == "ok" else "trend", "cluster": cid}
        if order:
            ranked, tied = self._rank_blocks(*order)
            if ranked:
                return plan | {"status": "ok", "taluka_id": ranked[0][0], "reason": None, "question_type": "other",
                               "metric_rank": {"fact": order[0], "order": order[1], "items": [[b, n, b] for b, n in ranked],
                                               "tied": tied, "level": "block"}}
        if "attention_rank" in metrics and self.alerts:
            return plan | {"status": "ok", "taluka_id": self.alerts[0]["block"], "reason": None, "question_type": "trend", "rank": True}
        if kendra_q and (data_metrics or AN.asks_why(question)):
            return plan | {"status": "clarify", "reason": "unknown_kendra"}  # a kendra was named but not found: never a guess
        de = self.district_entity()
        district = AN.district_named(question, [de["name_en"].replace(" district", ""), de["name_mr"]])
        # a figure asked without a place: district figures; "why" without a place still asks which taluka (never a guess)
        if (district or (data_metrics and not AN.asks_why(question))) and (plan["status"] != "ok" or district) and self.alerts \
                and plan.get("reason") != "unknown_place":  # a place was named but is not in this district: ask
            return plan | {"status": "ok", "taluka_id": self.alerts[0]["block"], "reason": None, "question_type": "other",
                           "district": True}
        if plan["status"] == "refuse" and data_metrics:
            return plan | {"status": "clarify", "reason": "missing_place"}  # a data question without a place
        return plan

    def _segments(self, question: str, gaz: list[dict]) -> list[dict]:
        """Parts of a multi-question message, each with its own blocks, figures, data check or ranking. A part without
        a block uses the previous part's block; a part with a block but no figure uses the previous part's figures.
        Only used when at least two parts ask for something."""
        parts = AN.segments(question)
        if len(parts) < 2:
            return []
        out, last, last_metrics = [], None, []
        for p in parts:
            places = intent.places_in(p, gaz)
            asked = AN.metrics_asked(p)
            metrics = [m for m in asked if m in DATA_METRICS]
            dq = "data_quality" in asked and (not metrics or any(w in AN.normalise(p) for w in AN.DQ_WORDS))
            sup = AN.superlative(p)
            if not metrics and not dq and places and last_metrics and not sup:
                metrics = last_metrics  # "Pandharpur madhe shala kiti, Sangola madhe?"
            kendra_q = any(w in AN.normalise(p) for w in AN.CLUSTER_WORDS)
            rank_metrics = metrics or (["learning"] if sup in ("good", "bad") else [])  # "which kendra is worst": results
            ranked = None
            if sup and rank_metrics and (kendra_q or not places):
                order = AN.rank_order(rank_metrics[0], sup)
                if order and kendra_q:  # "wich kendra is wrost in pandharpur": that block's kendras
                    items, tied = self._rank_clusters(*order, block=places[0] if places else None)
                    ranked = {"fact": order[0], "order": order[1], "items": items, "tied": tied}
                elif order:
                    items, tied = self._rank_blocks(*order)
                    ranked = {"fact": order[0], "order": order[1], "items": [[b, n, b] for b, n in items], "tied": tied}
            blocks = places or ([last] if last else [])
            if ranked or ((metrics or dq) and blocks):
                out.append({"blocks": [] if ranked else blocks, "metrics": metrics, "dq": dq, "text": p,
                            "ranked": ranked["items"] if ranked else None, "rank": ranked})
            last = places[-1] if places else last
            last_metrics = metrics or last_metrics
        return out if len(out) >= 2 else []

    def _rank_blocks(self, fact: str, order: str, top: int = 3) -> tuple[list[tuple[str, str]], bool]:
        """([(block id, number id)] of the top blocks by a direct-answer fact, whether others tie with the last one)."""
        rows = []
        for b in self.packs:
            f = self.facts(b)
            if fact in f["ids"][b]:
                rows.append((f["facts"][b][fact][0], self.packs[b]["entities"][b]["name_en"], b, f["ids"][b][fact]))
        rows.sort(key=lambda r: ((-r[0] if order == "desc" else r[0]), r[1]))
        shown = [round(r[0], 1) for r in rows[:top + 1]]
        tied = len(set(shown)) < len(shown)  # equal figures among the shown ones or with the next one
        return [(b, nid) for _v, _n, b, nid in rows[:top]], tied

    def _rank_clusters(self, fact: str, order: str, block: str | None = None, top: int = 3) -> tuple[list[list[str]], bool]:
        """([[kendra entity id, number id, block id]] of the top kendras by a fact, in one block or the district; ties)."""
        rows = []
        for b in ([block] if block in self.packs else list(self.packs)):
            f = self.facts(b)
            for eid, ids in f["ids"].items():
                if eid.startswith("C") and fact in ids:
                    rows.append((f["facts"][eid][fact][0], f["entities"][eid]["name_en"], eid, ids[fact], b))
        rows.sort(key=lambda r: ((-r[0] if order == "desc" else r[0]), r[1]))
        shown = [round(r[0], 1) for r in rows[:top + 1]]
        tied = len(set(shown)) < len(shown)
        return [[eid, nid, b] for _v, _n, eid, nid, b in rows[:top]], tied

    def direct_answer(self, focus: str, question: str, plan: dict) -> dict:
        empty = {"scope": focus, "cluster": None, "metrics": [], "lines": [], "rank": [], "also_named": [], "extra": [],
                 "why": False, "moved_from": None, "mode": "cards", "cards": None, "card_kinds": None}
        if not question:
            return empty
        try:
            return self._direct_answer(focus, question, plan)
        except (KeyError, ValueError, TypeError, ArithmeticError):  # a figure that cannot be computed never blocks the brief
            return empty | {"error": True}

    def _direct_answer(self, focus: str, question: str, plan: dict) -> dict:
        others = [b for b in plan.get("also_named") or [] if b in self.packs and b != focus]
        metrics = AN.metrics_asked(question)
        data_metrics = [m for m in metrics if m in DATA_METRICS]
        why, up = AN.asks_why(question), AN.asks_improvement(question)
        qn = AN.normalise(question)
        dq = "data_quality" in metrics and (not data_metrics or any(w in qn for w in AN.DQ_WORDS))
        ans = {"scope": focus, "cluster": plan.get("cluster"), "metrics": metrics, "lines": [], "extra": [], "cards": None,
               "card_kinds": None, "mode": "cards"}
        mr = plan.get("metric_rank")
        if plan.get("segments"):
            for seg in plan["segments"]:
                if seg.get("rank"):
                    r = seg["rank"]
                    ans["lines"].append(AN.rank_line(r["fact"], r["order"], [(e, n) for e, n, _b in r["items"]], r.get("tied", False)))
                    ans["extra"] += [b for _e, _n, b in r["items"] if b != focus]
                for b in seg["blocks"]:
                    if seg["metrics"]:
                        ans["lines"] += AN.direct_answer(seg["text"], self.facts(b), self.pack(b), None, seg["metrics"])["lines"]
                    if seg.get("dq"):
                        ans["lines"] += self._dq_lines(b)
                    if b != focus:
                        ans["extra"].append(b)
            ans["extra"] = list(dict.fromkeys(ans["extra"]))
            ans["mode"] = "fact"
        elif mr:
            ans["lines"] = [AN.rank_line(mr["fact"], mr["order"], [(e, n) for e, n, _b in mr["items"]], mr.get("tied", False))]
            ans["extra"] = list(dict.fromkeys(b for _e, _n, b in mr["items"] if b != focus))
            ans["mode"] = "rank"
        elif plan.get("rank"):
            ans["mode"] = "cards"  # the ranked line comes from ans["rank"]; the top block's kendra cards follow
        elif plan.get("district"):
            d = self.district()
            eid = next(iter(d["ids"]))
            asked = (["data_quality"] if dq else []) + ([m for m in data_metrics if not dq or m != "attendance"]
                                                       or ([] if dq else ["schools", "learning", "attendance"]))
            ans["lines"] = AN.answer_lines(asked, d["ids"][eid], eid, False, d["facts"][eid], d["period_ids"].get(eid))
            if dq:  # which blocks hold the suspicious records
                rows = [(b, self.facts(b)["ids"][b]["flagged_schools"]) for b in self.packs
                        if self.facts(b)["facts"][b].get("flagged_schools", (0,))[0] > 0]
                if rows:
                    items = ", ".join("{{e:" + b + "}} ({{n:" + n + "}})" for b, n in rows)
                    ans["lines"].append({"metric": "dq", "mr": DQ_BLOCKS[0].format(items=items), "en": DQ_BLOCKS[1].format(items=items),
                                         "facts": [n for _b, n in rows]})
                    ans["extra"] = [b for b, _n in rows if b != focus]
            ans["mode"] = "fact"
            if not data_metrics and not dq:
                plan = plan | {"rank": True}
        elif AN.asks_twin(question) and not data_metrics and not plan.get("cluster") and not others:
            ans["mode"], ans["cards"] = "twin", "block"  # the learn-from card (similar block that did better)
            pack, b = self.pack(focus), self.brief(focus)
            ans["lines"] = [{"metric": "twin", "mr": b.prose[f["id"]]["mr"], "en": b.prose[f["id"]]["en"], "facts": []}
                            for f in pack["findings"] if f["type"] == "TWIN" and not f.get("params", {}).get("cluster")]
        elif up and (why or not data_metrics) and set(data_metrics) <= {"learning"} and not plan.get("cluster"):
            ans["lines"] = AN.improvement_lines(self.facts(focus), focus)
            ans["mode"] = "why_up"
        elif dq:
            ans["lines"] = self._dq_lines(focus)
            ans["mode"], ans["card_kinds"] = "dq", {"DATA"}
        else:
            if others and not plan.get("cluster") and not data_metrics:
                metrics = metrics + ["learning"]  # "compare A and B" without a metric: compare results
                data_metrics = ["learning"]
            sub = AN.direct_answer(question, self.facts(focus), self.pack(focus), plan.get("cluster"), metrics, keep_status=why)
            ans["lines"] = sub["lines"]
            ans["cluster"] = sub["cluster"]
            if others and not plan.get("cluster"):  # the same figures for the other named blocks, side by side
                for b in others:
                    more = AN.direct_answer(question, self.facts(b), self.pack(b), None, metrics)["lines"]
                    if more:
                        ans["lines"] += more
                        ans["extra"].append(b)
            if sub["cluster"]:
                ans["mode"] = "cluster" if (why or not data_metrics) else "fact"  # "why did <kendra> fall": its card too
                ans["cards"] = {f"C{sub['cluster']}"}
            elif why:
                ans["mode"] = "cards"
                ans["lines"] = ans["lines"] or AN.direct_answer("", self.facts(focus), self.pack(focus), None, ["learning"])["lines"]
            elif data_metrics:
                ans["mode"] = "fact"
        ans["rank"] = [{"block": a["block"], "at_risk": a["at_risk"]} for a in self.alerts[:3]] if plan.get("rank") else []
        ans["also_named"] = others
        ans["why"] = why
        ans["moved_from"] = plan.get("cluster_moved_from")
        years = sorted(self.ingest.tables["assessment"]["academic_year"].dropna().unique())
        ans["year_note"] = [years[0], years[-1]] if years and AN.years_outside(question, years[0], years[-1]) else None
        return ans

    def _dq_lines(self, focus: str) -> list[dict]:
        """Which records look unreliable: the block count, the kendras they sit in, and what to do."""
        f = self.facts(focus)
        lines = AN.direct_answer("", f, self.pack(focus), None, ["data_quality"])["lines"]
        flagged = [(c, f["ids"][c]["flagged_schools"]) for c in f["ids"] if c.startswith("C")
                   and f["facts"][c].get("flagged_schools", (0,))[0] > 0]
        missing = [(c, f["ids"][c]["insufficient_schools"]) for c in f["ids"] if c.startswith("C")
                   and f["facts"][c].get("insufficient_schools", (0,))[0] > 0]
        for rows, key in ((flagged, "flagged"), (missing, "missing")):
            if rows:
                items = ", ".join("{{e:" + c + "}} ({{n:" + nid + "}})" for c, nid in rows)
                mr, en = DQ_LINES[key]
                lines.append({"metric": "dq", "mr": mr.format(items=items), "en": en.format(items=items), "facts": [n for _c, n in rows]})
        return lines

    def _answer_texts(self, focus: str, ans: dict, lang: str, html: bool) -> list[str]:
        i = 0 if lang == "mr" else 1
        out = []
        if ans.get("rank"):
            items = ", ".join(AN.RANK_ITEM[i][0 if r["at_risk"] == 1 else 1].format(name=self._block_label(r["block"], lang),
                                                                                    n=_num(r["at_risk"], lang))
                              for r in ans["rank"])
            text = (AN.RANK_LINE if ans.get("mode") == "cards" else AN.RANK_LINE_SHORT)[i].format(items=items)
            out.append(_esc(text) if html else text)
        if ans.get("lines"):
            ap = self.answer_pack(focus, ans.get("extra", []))
            out += [(fill_html if html else fill)(ln[lang], ap, lang) for ln in ans["lines"]]
        return out

    def _block_label(self, eid: str, lang: str) -> str:
        ent = self.packs[eid]["entities"][eid]
        return (ent.get("name_mr") or ent["name_en"]) if lang == "mr" else ent["name_en"]

    def _cards_for(self, focus: str, ans: dict) -> list[dict]:
        if ans.get("mode") not in ("cards", "cluster", "dq", "twin"):
            return []
        if ans.get("cards") == "block":
            return [c for c in V.cards(self.pack(focus)) if c["entity"] is None]
        return V.cards(self.pack(focus), only=ans.get("cards"), kinds=ans.get("card_kinds"))

    def _notes(self, focus: str, plan: dict, ans: dict, lang: str) -> list[str]:
        i = 0 if lang == "mr" else 1
        notes = []
        if "actions" in ans.get("metrics", []):
            notes.append(ACTIONS_NOTE[i].format(heading=V.HEAD["todo"][i]))
        if ans.get("moved_from") in self.packs and ans.get("cluster"):
            cl = self.facts(focus)["entities"].get(f"C{ans['cluster']}", {})
            cname = (cl.get("name_mr") or cl.get("name_en", "")) if lang == "mr" else cl.get("name_en", "")
            notes.append(MOVED[i].format(c=cname, b=self._block_label(focus, lang)))
        if ans.get("year_note"):
            first, last = ans["year_note"]
            digits = str.maketrans("0123456789", "०१२३४५६७८९") if lang == "mr" else None
            notes.append(AN.YEAR_NOTE[i].format(first=first.translate(digits) if digits else first,
                                                last=last.translate(digits) if digits else last))
        for other in ans.get("also_named", []):
            if other in self.packs and other not in ans.get("extra", []):
                notes.append(ALSO_NAMED[i].format(a=self._block_label(focus, lang), b=self._block_label(other, lang)))
        return notes

    def answer_html(self, focus: str, plan: dict, lang: str) -> str:
        """Answer card + kendra cards + the full brief behind a button (replaces the plain brief fragment)."""
        ans = plan.get("answer") or {"mode": "cards"}
        pack, b = self.pack(focus), self.brief(focus)
        texts = self._answer_texts(focus, ans, lang, html=True)
        fact_ids = [n for ln in ans.get("lines", []) for n in ln.get("facts", [])]
        ap = self.answer_pack(focus, ans.get("extra", [])) if fact_ids else pack
        files = V.sources_of(fact_ids, ap["numbers"], {s["id"]: s["file"] for s in pack["sources"]})
        cards_html = [V.card_html(c, pack, b.prose, lang) for c in self._cards_for(focus, ans)]
        i = 0 if lang == "mr" else 1
        label = EVIDENCE_TOP[i].format(name=self._block_label(focus, lang)) if plan.get("district") else None
        return V.answer_html(ans.get("mode", "cards"), texts, self._notes(focus, plan, ans, lang), files, cards_html,
                             self.fragment(focus, lang), lang, bool(pack.get("synthetic")), evidence_label=label)

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
        """Short answer for WhatsApp text and voice: the direct answer first; kendra cards only for "what needs attention
        / why" questions. The full brief stays in the PDF and behind the web button."""
        i = 0 if lang == "mr" else 1
        focus_id = pack["scope"]["focus"]
        ans = plan.get("answer") or {"mode": "cards"}
        items = [{"section": "answer", "heading": AN.ANSWER_HEADING[i], "badge": "", "text": t, "owner": "", "type": "FACT",
                  "label": ""} for t in self._answer_texts(focus_id, ans, lang, html=False)]
        findings = {f["id"]: f for f in pack["findings"]}
        for c in self._cards_for(focus_id, ans):
            ct = V.card_text(c, pack, b.prose, lang)
            sec = f"card:{c['entity'] or 'block'}"
            st = findings.get(c["status"]) if c["status"] else None
            if st:
                items.append({"section": sec, "heading": ct["name"], "badge": ct["badge"], "text": ct["what"], "owner": "",
                              "type": st["type"], "label": st["label"]})
            for fid, (badge, text) in zip(c["why"], ct["why"]):
                items.append({"section": sec, "heading": ct["name"], "badge": badge, "text": text, "owner": "",
                              "type": findings[fid]["type"], "label": findings[fid]["label"]})
            for text, owner in ct["todo"]:
                items.append({"section": sec, "heading": ct["name"], "badge": V.HEAD["todo"][i], "text": text, "owner": owner,
                              "type": "ACTION", "label": "ACTION"})
        focus = pack["entities"][focus_id]
        name = (focus.get("name_mr") or focus["name_en"]) if lang == "mr" else focus["name_en"]
        if plan.get("district"):
            de = self.district_entity()
            name = de["name_mr"] + " जिल्हा" if lang == "mr" else de["name_en"]
        title = f"{BLOCK_TITLE[i]}: {name}" if ans.get("mode") in ("cards", "cluster", "dq") else f"{AN.ANSWER_HEADING[i]}: {name}"
        return {"title": title, "banner": X.BANNER[i] if pack.get("synthetic") else "", "items": items,
                "notes": self._notes(focus_id, plan, ans, lang), "mode": ans.get("mode", "cards")}

    # ---- role home pages (DEO: district; BEO: one block) ----
    def home_html(self, role: str, lang: str, block: str | None = None) -> tuple[str, str]:
        """(html, brief id for the click-to-source drill-down). Every figure is a direct-answer fact (with provenance)."""
        self.prepare()
        i = 0 if lang == "mr" else 1
        esc = _esc
        focus = block if (role == "beo" and block in self.packs) else (self.alerts[0]["block"] if self.alerts else next(iter(self.packs)))
        ap = self.answer_pack(focus, list(self.packs) if role == "deo" else [])
        brief_id = f"{self.spec.id}.{focus}"

        def tile(label: tuple[str, str], nid: str | None, sub: str = "") -> str:
            if not nid or nid not in ap["numbers"]:
                return ""
            val = fill_html("{{n:" + nid + "}}", ap, lang)
            return f'<div class="tile"><div class="tile-label">{esc(label[i])}</div><div class="tile-value">{val}</div>' \
                   f'{f"<div class=tile-sub>{sub}</div>" if sub else ""}</div>'

        def tiles(eid: str, ids: dict) -> str:
            change = ids.get("maths_change")
            sub = ""
            if change:
                v = ap["numbers"][change]
                arrow = {"up": "▲", "down": "▼"}.get(v.get("direction"), "■")
                sub = f'{arrow} {fill_html("{{n:" + change + "}}", ap, lang)} {esc(HOME["vs_last"][i])}'
            return '<div class="tiles">' + "".join([
                tile(HOME["schools"], ids.get("schools")), tile(HOME["clusters"], ids.get("clusters")),
                tile(HOME["teachers"], ids.get("working_teachers")), tile(HOME["vacant"], ids.get("vacant_posts")),
                tile(HOME["ptr"], ids.get("ptr")), tile(HOME["attendance"], ids.get("attendance_pct")),
                tile(HOME["maths"], ids.get("maths_pct"), sub)]) + "</div>"

        parts = [f'<div class="home home-{esc(role)}" lang="{lang}" data-brief="{esc(brief_id)}">']
        if role == "deo":
            d = self.district()
            eid = next(iter(d["ids"]))
            de = self.district_entity()
            name = de["name_mr"] + " जिल्हा" if lang == "mr" else de["name_en"]
            parts.append(f'<h2 class="home-title">{esc(HOME["deo_title"][i].format(name=name))}</h2>')
            parts.append(tiles(eid, d["ids"][eid]))
            period = self.alerts[0]["period"] if self.alerts else ""
            period = period.translate(str.maketrans("0123456789", "०१२३४५६७८९")) if lang == "mr" else period
            parts.append(f'<section class="home-alerts"><h3>{esc(HOME["need_attention"][i])} '
                         f'<span class="home-period">({esc(HOME["results"][i])} {esc(period)})</span></h3>')
            for a in self.alerts:
                web = HOME["alert" if a["at_risk"] != 1 else "alert_one"][i].format(block=self._block_label(a["block"], lang), n=_num(a["at_risk"], lang)) + (
                    HOME["alert_data"][i].format(n=_num(a["data"], lang)) if a["data"] else "")
                parts.append(f'<article class="acard" data-block="{esc(a["block"])}"><div class="acard-text">{esc(web)}</div>'
                             f'<button class="btn open-block" type="button" data-block="{esc(a["block"])}">{esc(HOME["open"][i])}</button></article>')
            parts.append("</section>")
            parts.append(f'<section class="home-table"><h3>{esc(HOME["all_blocks"][i])}</h3><table class="blocks"><thead><tr>'
                         + "".join(f"<th>{esc(h[i])}</th>" for h in (HOME["block"], HOME["schools"], HOME["maths"], HOME["change"],
                                                                      HOME["attendance"], HOME["ptr"], HOME["kendras_risk"]))
                         + "</tr></thead><tbody>")
            risk = {a["block"]: a["at_risk"] for a in self.alerts}
            order = sorted(self.packs, key=lambda b: (-risk.get(b, 0), self.packs[b]["entities"][b]["name_en"]))
            for b in order:
                ids = self.facts(b)["ids"][b]
                cell = lambda k: (_arrow(ap["numbers"][ids[k]]) + fill_html("{{n:" + ids[k] + "}}", ap, lang)) if k in ids else "–"  # noqa: E731
                parts.append(f'<tr data-block="{esc(b)}" data-brief="{esc(self.spec.id)}.{esc(b)}"><td><a href="#" class="open-block" '
                             f'data-block="{esc(b)}">{esc(self._block_label(b, lang))}</a></td><td>{cell("schools")}</td>'
                             f'<td>{cell("maths_pct")}</td><td>{cell("maths_change")}</td><td>{cell("attendance_pct")}</td>'
                             f'<td>{cell("ptr")}</td><td>{_num(risk.get(b, 0), lang)}</td></tr>')
            parts.append("</tbody></table></section>")
        else:
            ids = self.facts(focus)["ids"][focus]
            parts.append(f'<h2 class="home-title">{esc(HOME["beo_title"][i].format(name=self._block_label(focus, lang)))}</h2>')
            parts.append(tiles(focus, ids))
            pack, b = self.pack(focus), self.brief(focus)
            cs = V.cards(pack)
            parts.append(f'<section class="kendra-cards"><h3 class="cards-head">{esc(HOME["my_kendras"][i])}</h3>'
                         + "".join(V.card_html(c, pack, b.prose, lang) for c in cs) + "</section>")
            summ = pack.get("summary", {})
            fx = self.facts(focus)
            rows = []
            for cid in sorted(summ, key=lambda c: (STATUS_ORDER.get(summ[c]["status"], 9), c)):
                eid = f"C{cid}"
                ent = fx["entities"].get(eid, {})
                nm = (ent.get("name_mr") or ent.get("name_en", cid)) if lang == "mr" else ent.get("name_en", cid)
                ch = fx["ids"].get(eid, {}).get("maths_change")
                chv = (_arrow(ap["numbers"][ch]) + fill_html("{{n:" + ch + "}}", ap, lang)) if ch else "–"
                st = summ[cid]["status"]
                rows.append(f'<tr><td>{esc(nm)}</td><td><span class="chip chip-{esc(st.lower())}">{esc(HOME["status"][st][i])}</span></td>'
                            f'<td>{chv}</td></tr>')
            parts.append(f'<section class="home-table"><h3>{esc(HOME["all_kendras"][i])}</h3><table class="kendras"><thead><tr>'
                         f'<th>{esc(HOME["kendra"][i])}</th><th>{esc(HOME["state"][i])}</th><th>{esc(HOME["change"][i])}</th></tr></thead>'
                         f'<tbody>{"".join(rows)}</tbody></table></section>')
        parts.append(f'<p class="home-note">{esc(X.BANNER[i])}</p></div>')
        return "".join(parts), brief_id

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
        title = ("बैठक पॅक: " if lang == "mr" else "Review meeting pack: ") + self._block_label(focus, lang)
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


def _arrow(n: dict) -> str:
    """▲ / ▼ before a change so a fall is never read as a rise (direction set by code from the sign)."""
    return {"up": "▲ ", "down": "▼ "}.get(n.get("direction"), "")
