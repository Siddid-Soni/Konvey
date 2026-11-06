"""Progressive docs: guide sections, display catalog, examples, simulations."""

from __future__ import annotations

import json

import pytest

from konvey.mcp import docs
from konvey.stage import displays


def test_guide_index_lists_the_sections_a_director_needs():
    text = docs.guide()
    for name in ("workflow", "beats", "shots", "camera", "parts", "overlay", "world",
                 "rules", "themes", "sims", "marks", "checks", "review"):
        assert f"`{name}`" in text


def test_every_guide_section_is_non_empty_and_not_an_error():
    for name in ("workflow", "beats", "shots", "camera", "parts", "overlay", "world",
                 "rules", "themes", "sims", "marks", "checks", "review"):
        text = docs.guide(name)
        assert not text.startswith("ERROR"), name
        assert len(text) > 200, name


def test_guide_sections_do_not_repeat_their_heading():
    text = docs.guide("workflow")
    assert text.startswith("# Workflow\n")
    assert text.count("# Workflow") == 1
    assert "konvey_new_run" in text


def test_all_includes_the_filled_display_reference():
    text = docs.guide("all")
    assert "| tag | draws | attributes |" in text
    assert "<beats> holds a sequence" in text or "<beats>" in text
    assert len(text) > 30000


def test_unknown_section_names_the_available_ones():
    text = docs.guide("not-a-section")
    assert text.startswith("ERROR:")
    assert "workflow" in text


def test_display_catalog_has_every_display():
    result = docs.display_catalog()
    assert result["count"] == len(displays.all_displays())
    tags = {d["tag"] for d in result["displays"]}
    assert {"plot", "tex", "places", "graph", "sim"} <= tags


def test_one_display_returns_its_attributes_and_docs():
    result = docs.display_catalog(tag="plot")
    display = result["display"]
    assert display["tag"] == "plot"
    assert "fn=" in display["docs"]
    assert display["attributes"]
    assert display["examples"]


def test_display_kind_accepts_the_tag_and_the_plan_kind():
    assert [d["tag"] for d in docs.display_catalog(kind="sim")["displays"]] == ["sim"]
    assert [d["tag"] for d in docs.display_catalog(kind="simulation")["displays"]] == ["sim"]
    assert [d["tag"] for d in docs.display_catalog(kind="plot")["displays"]] == ["plot"]


def test_unknown_display_and_kind_are_errors():
    with pytest.raises(ValueError):
        docs.display_catalog(tag="not-a-display")
    with pytest.raises(ValueError):
        docs.display_catalog(kind="not-a-kind")


def test_example_index_and_one_example():
    index = docs.example()
    assert index["count"] >= 20
    chosen = docs.example(kind="plot")
    assert chosen["ok"] is True
    assert "plot" in chosen["kinds"]
    assert "<beats>" in chosen["body"]
    assert chosen["note"].startswith("Copy the structure")


def test_example_name_accepts_the_md_suffix():
    assert docs.example(name="plot")["name"] == "plot"
    assert docs.example(name="plot.md")["name"] == "plot"
    missing = docs.example(name="not-an-example")
    assert missing["ok"] is False
    assert "available" in missing


def test_simulation_rules_and_exact_values():
    text = docs.simulate()
    assert "blocks" in text and "pendulum" in text and "settings" in text
    values = json.loads(docs.simulate("blocks", '{"mass": 100}', "end"))
    assert values["end"]["end"] > 0
    assert "ERROR" in docs.simulate("not-a-rule", "{}")
