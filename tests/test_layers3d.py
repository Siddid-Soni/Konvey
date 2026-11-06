"""Layered 3D pictures: a stack of layers data flows through, a block of cells (konvey.stage.layers3d)."""

import importlib.util

import numpy as np
import pytest

from konvey.stage.parse import BeatError, parse_beats

pytestmark = pytest.mark.skipif(importlib.util.find_spec("manimlib") is None, reason="needs manimgl")


def world(*beats):
    from konvey.stage.field import FieldWorld

    bs = parse_beats("<beats>" + "".join(f"<beat><world>{b}</world></beat>" for b in beats) + "</beats>")
    fw = FieldWorld(bs)
    states, prev = [], None
    for b in bs:
        prev = fw.state_from(b.world, prev)
        states.append(prev)
    return fw, states


def test_layers_expand_repeats_and_patterns():
    from konvey.stage.layers3d import expand_layers

    assert expand_layers("in*2, (a, b*2)*2, out") == ["in", "in", "a", "b", "b", "a", "b", "b", "out"]
    with pytest.raises(BeatError, match="name"):
        expand_layers("a, (b")


def test_stack_lights_layers_by_index_or_kind_and_links_fade_in():
    L = 'layers="read, (mix, think*2)*2"'
    fw, (a, b) = world(f'<stack3d id="s" {L} highlight="mix"></stack3d>',
                       f'<stack3d id="s" {L} dim="0-2" links="0>3-6:copy"></stack3d>')
    assert list(np.flatnonzero(a["s"]["lit"])) == [1, 4]
    assert list(np.flatnonzero(b["s"]["dim"])) == [0, 1, 2]
    assert a["s"]["links"].tolist() == [0.0] and b["s"]["links"].tolist() == [1.0]
    with pytest.raises(BeatError, match="not a layer index"):
        world(f'<stack3d id="s" {L} highlight="nope"></stack3d>')
    with pytest.raises(BeatError, match="same layers"):
        world('<stack3d id="s" layers="a*2"></stack3d>', '<stack3d id="s" layers="a*3"></stack3d>')


def test_stack_sheet_runs_through_the_layers_during_the_line():
    fw, (a, b) = world('<stack3d id="s" layers="a*4" tokens="x,y" at="-1"></stack3d>',
                       '<stack3d id="s" layers="a*4" tokens="x,y" at="3"></stack3d>')
    assert (b["s"]["at"], b["s"]["at1"]) == (-1, 3)      # LIVE: from where it was to the target
    s = fw.actors["s"]
    assert s.sheet_x(-1) < s.xs[0] < s.xs[-1] < s.sheet_x(4)
    groups = world('<stack3d id="s" layers="a*4" groups="one:0-1; two:2-3"></stack3d>')[0].actors["s"]
    assert groups.xs[2] - groups.xs[1] > groups.xs[1] - groups.xs[0]   # a wider gap between groups


def test_grid_merge_shortens_the_block_and_hides_the_merged_lines():
    fw, (a, b) = world('<grid3d id="g" shape="2,8,3"></grid3d>', '<grid3d id="g" shape="2,8,3" merge="1,4,1"></grid3d>')
    g = fw.actors["g"]
    ya = np.ptp([p[1] for p in g.extent(a["g"])])
    yb = np.ptp([p[1] for p in g.extent(b["g"])])
    assert yb == pytest.approx(ya / 4)
    assert b["g"]["vis1"].tolist() == [1, 0, 0, 0, 1, 0, 0, 0, 1]
    with pytest.raises(BeatError, match="divide"):
        world('<grid3d id="g" shape="2,6,3" merge="1,2,1"></grid3d>', '<grid3d id="g" shape="2,6,3" merge="1,3,1"></grid3d>')


def test_grid_slices_pull_apart_and_take_paint():
    fw, (a,) = world('<grid3d id="g" shape="4,2,2" slices="x" gap="1" paint="1:accent" highlight="3"></grid3d>')
    g = fw.actors["g"]
    boxes, _ = g._boxes(a["g"])
    assert len(boxes) == 4 and boxes[1][0][0] - boxes[0][1][0] == pytest.approx(g.cell)
    assert a["g"]["lit"].tolist() == [0, 0, 0, 1]
    assert not np.allclose(a["g"]["rgb"][1], a["g"]["rgb"][0])
    with pytest.raises(BeatError, match="needs slices"):
        world('<grid3d id="g" shape="4,2,2" paint="1:c2"></grid3d>')
