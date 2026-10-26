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
from ..brief.pdf import html_to_pdf
from ..brief.render import fill
from ..brief.texts_block import BLOCK_HEADINGS, BLOCK_SECTIONS, BLOCK_TITLE
from ..evidence import format_number
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
                              "owner": owner})
        notes = []
        sec = SECTION_FOR.get(plan.get("question_type"))
        if sec:
            notes.append(POINTER[i].format(heading=BLOCK_HEADINGS[sec][i]))
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
                     "cluster": pack["entities"].get(f["params"].get("cluster", {}).get("entity", ""), {}).get("name_en")}
            groups.setdefault(X.ACTORS[act["actor_role"]][i], []).append(entry)
        title = ("बैठक पॅक: " if lang == "mr" else "Review meeting pack: ") + pack["entities"][focus]["name_en"]
        return {"title": title, "banner": X.BANNER[i] if pack.get("synthetic") else "", "groups": groups}


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
