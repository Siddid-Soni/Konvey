"""Tests for the executed layout check (konvey.layout_probe) and the
Agent 3 measure-and-repair loop. Probe tests need manimgl and are skipped
without it; the plan-naming check runs everywhere."""

import json
from pathlib import Path

import pytest

from konvey.layout_probe import manimgl_available, probe_scene
from konvey.pipeline import run_coding, run_dry_run
from konvey.schemas import LAYOUT_OPS, ScenePlan
from konvey.validators import check_plan_naming, validate_scene_plan

ROOT = Path(__file__).resolve().parent.parent
FIX = Path(__file__).resolve().parent / "fixtures"
EXAMPLES = ROOT / "examples"

needs_manim = pytest.mark.skipif(not manimgl_available(), reason="manimgl not installed")


def _kinds(report):
    return {i.kind for i in report.issues}


@needs_manim
def test_probe_flags_overlaps_and_off_frame():
    rep = probe_scene(FIX / "layout_bad.py")
    assert not rep.skipped, rep.skip_reason
    assert {"text_overlap", "text_on_drawing", "off_frame"} <= _kinds(rep)
    off = next(i for i in rep.issues if i.kind == "off_frame")
    assert off.objects == ["note"] and "right by" in off.detail
    assert off.vo == "Now a formula."
    assert not rep.ok


@needs_manim
def test_probe_passes_region_layout():
    rep = probe_scene(FIX / "layout_good.py")
    assert not rep.skipped, rep.skip_reason
    assert rep.issues == []


@needs_manim
def test_probe_catches_unarranged_vgroup_in_example05():
    rep = probe_scene(EXAMPLES / "example-05-discrete-convolution-dice" / "agent3-S2.py")
    stacked = [i for i in rep.errors if i.kind == "text_overlap"]
    assert len(stacked) == 1, "pairwise sibling overlaps should collapse into one finding"
    assert "low_row" in stacked[0].detail and "arrange" in stacked[0].detail


@needs_manim
def test_probe_reports_runtime_errors_ast_parse_misses():
    rep = probe_scene("from manim_imports_ext import *\n"
                      "class SingleScene(InteractiveScene):\n"
                      "    def construct(self):\n"
                      "        # VO: \"x\"\n"
                      "        self.play(Write(Txet('hi')))\n"
                      "        self.wait()\n")
    assert [i.kind for i in rep.errors] == ["runtime_error"]
    assert "Txet" in rep.errors[0].detail and rep.errors[0].line == 5


@needs_manim
def test_feedback_is_actionable():
    fb = probe_scene(FIX / "layout_bad.py").as_feedback()
    assert fb.startswith("LAYOUT CHECK FAILED")
    assert "note" in fb and "FadeOut" in fb


class _FakeCoder:
    """Returns each scripted reply in turn and records prompts."""

    def __init__(self, replies):
        self.replies, self.prompts = list(replies), []

    def run(self, prompt):
        self.prompts.append(prompt)
        return type("R", (), {"content": self.replies.pop(0)})()


def _scene():
    plan = validate_scene_plan(json.loads(
        (EXAMPLES / "example-04-clt-galton-board" / "agent2-output.json").read_text()))
    return plan.scenes[0]


@needs_manim
def test_repair_loop_sends_report_and_keeps_fixed_code():
    bad, good = (FIX / "layout_bad.py").read_text(), (FIX / "layout_good.py").read_text()
    coder = _FakeCoder([bad, good])
    coded = run_coding(_scene(), coder, layout_check=True, max_repairs=2)
    assert len(coder.prompts) == 2
    assert "LAYOUT CHECK FAILED" in coder.prompts[1] and "previous code" in coder.prompts[1]
    assert coded.code.strip() == good.strip() and coded.layout_issues == []


@needs_manim
def test_repair_loop_never_returns_a_worse_candidate():
    bad, good = (FIX / "layout_bad.py").read_text(), (FIX / "layout_good.py").read_text()
    # same issues as `bad` plus one more off-frame object
    worse = bad.replace("self.play(Write(formula), FadeIn(note))",
                        "self.play(Write(formula), FadeIn(note))\n        self.add(Text('oops').shift(10 * RIGHT))")
    coder = _FakeCoder([bad, worse])
    coded = run_coding(_scene(), coder, layout_check=True, max_repairs=1)
    assert coded.code.strip() == bad.strip()
    assert coded.layout_issues  # remaining issues are surfaced, not hidden


def test_layout_check_off_is_single_call():
    coder = _FakeCoder([(FIX / "layout_bad.py").read_text()])
    coded = run_coding(_scene(), coder, layout_check=False)
    assert len(coder.prompts) == 1 and coded.layout_issues == []


@needs_manim
def test_dry_run_writes_layout_report(tmp_path):
    res = run_dry_run(EXAMPLES / "example-05-discrete-convolution-dice", tmp_path, layout_check=True)
    s2 = next(s for s in res.scenes if s.scene_id == "S2")
    assert any(i["kind"] == "text_overlap" for i in s2.layout_issues)
    assert json.loads((tmp_path / "layout-report.json").read_text())["S2"]


def test_plan_naming_flags_mismatched_identifiers():
    plan = ScenePlan.model_validate(json.loads(
        (EXAMPLES / "example-04-clt-galton-board" / "agent2-output.json").read_text()))
    warnings = check_plan_naming(plan)
    assert any("many_balls" in w for w in warnings)


def test_region_ops_are_allowed_layout_ops():
    assert {"place", "set_max_width", "set_max_height"} <= set(LAYOUT_OPS)
