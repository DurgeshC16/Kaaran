"""Evidence pack contract: the committed sample validates, formats consistently and projects safely for the LLM."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from kaaran import evidence as E

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "samples" / "evidence_pandharpur.json"


@pytest.fixture(scope="module")
def sample() -> dict:
    return E.load(SAMPLE)


def test_sample_is_valid_synthetic_and_illustrative(sample):
    assert E.validate(sample) == []
    assert sample["synthetic"] is True and "SYNTHETIC" in sample["marker"]
    assert sample["illustrative"] is True
    assert all(s["synthetic"] for s in sample["sources"])


def test_sample_covers_the_six_brief_sections(sample):
    sections = {o["section"]: o["finding_ids"] for o in sample["outline"]}
    for s in ("trend", "election_check", "main_cause", "twin", "data_warning", "action"):
        assert sections.get(s), s
    findings = {f["id"]: f for f in sample["findings"]}
    assert findings[sections["main_cause"][0]]["hypothesis"] == "vacancy"
    assert {f["label"] for f in sample["findings"]} >= {"STRONG", "WEAK", "LEARN_FROM", "RED_FLAG", "ACTION", "RULED_OUT", "CLEARED"}


def test_display_strings_come_from_the_one_formatter(sample):
    assert E.finalize(sample) == sample


def test_every_number_is_traceable(sample):
    for nid, n in sample["numbers"].items():
        assert n["provenance"] or n.get("derivation", {}).get("inputs"), nid


def test_llm_view_holds_aggregates_only(sample):
    view = E.llm_view(sample)
    assert E.contains_identifiers(view) == []
    assert all(e["kind"] != "school" for e in view["entities"].values())
    assert all("members" not in s and s["size"] > 0 for s in view["entity_sets"].values())
    school_names = {e["name_en"] for e in sample["entities"].values() if e["kind"] == "school"}
    text = str(view)
    assert not any(name in text for name in school_names)
    for n in view["numbers"].values():
        for p in n["provenance"]:
            assert "rows" not in p and "sr_no" not in p and "where" not in p


def test_format_number_rules():
    assert E.format_number(2.25, "score", 1) == {"en": "2.3", "mr": "२.३"}  # half up, not banker's
    assert E.format_number(-3.31, "score_change", 1)["en"] == "3.3"  # magnitude; direction is separate
    assert E.format_number(1234567, "count", 0) == {"en": "12,34,567", "mr": "१२,३४,५६७"}  # Indian grouping
    assert E.format_number(66.54, "pct", 1)["en"] == "66.5%"
    assert E.format_number(-3.7, "t_stat", 2)["en"] == "-3.70"


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda p: p["findings"][0].update(label="LEARN_FROM"), "not allowed for TREND"),
        (lambda p: p["findings"][0].update(template_key="trend.made_up"), "unknown template_key"),
        (lambda p: p["findings"][0]["params"].pop("rank_to"), "params missing"),
        (lambda p: p["findings"][1].pop("hypothesis"), "CAUSE needs hypothesis"),
        (lambda p: p["numbers"]["n.count.schools.T08"].update(provenance=[], derivation={}), "needs provenance"),
        (lambda p: p["numbers"]["n.count.schools.T08"].update(value=141), "display missing or stale"),
        (lambda p: p["numbers"]["n.count.schools.T08"]["provenance"][0]["where"].update(block="08"), "not in view"),
        (lambda p: p["numbers"]["n.count.schools.T08"].pop("of"), "count needs 'of'"),
        (lambda p: p["sources"][0].update(synthetic=False) or [s.update(synthetic=False) for s in p["sources"]], "pack.synthetic"),
        (lambda p: p["outline"].append({"section": "summary", "finding_ids": []}), "unknown section"),
    ],
)
def test_validator_catches_contract_breaks(sample, mutate, expected):
    broken = copy.deepcopy(sample)
    mutate(broken)
    problems = E.validate(broken)
    assert any(expected in msg for msg in problems), problems


def test_registries_are_documented():
    schema_doc = (ROOT / "docs" / "EVIDENCE_SCHEMA.md").read_text(encoding="utf-8")
    rules_doc = (ROOT / "docs" / "CONFIDENCE_RULES.md").read_text(encoding="utf-8")
    for key in E.TEMPLATE_KEYS:
        assert key in schema_doc, key
    for rule in E.RULE_IDS:
        assert rule in rules_doc, rule
