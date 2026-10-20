"""3D world actors: parametric surfaces, traced trajectories, slices (konvey.stage.actors3d)."""

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


def test_parametric_morphs_between_its_shapes():
    band = 'x="2*cos(u)" y="2*sin(u)" z="0.6*v"'
    flat = 'x="2*cos(u)" y="2*sin(u)" z="0"'
    fw, (a, b) = world(f'<parametric id="m" {band}></parametric>', f'<parametric id="m" {flat}></parametric>')
    p = fw.actors["m"]
    assert p.extent(a["m"])[1][2] == pytest.approx(0.6, abs=1e-6) and p.extent(b["m"])[1][2] == pytest.approx(0, abs=1e-6)
    half = fw.lerp(a, b, 0.5)["m"]
    assert p.extent(half)[1][2] == pytest.approx(0.3, abs=1e-6)
    with pytest.raises(BeatError, match="needs x="):
        world('<parametric id="m" x="u"></parametric>')


def test_trajectory_continues_from_the_last_beat_and_starts_split():
    fw, (a, b) = world('<trajectory id="l" system="lorenz" count="3" t="2"></trajectory>',
                       '<trajectory id="l" system="lorenz" count="3" t="25"></trajectory>')
    assert (a["l"]["t"], a["l"]["t1"]) == (0.0, 2.0) and (b["l"]["t"], b["l"]["t1"]) == (2.0, 25.0)
    paths = fw.actors["l"].paths
    assert paths.shape[0] == 3 and np.linalg.norm(paths[0, 0] - paths[1, 0]) < 1e-2
    assert np.linalg.norm(paths[0, -1] - paths[1, -1]) > 0.5     # a hair apart, then far apart
    with pytest.raises(BeatError, match="system="):
        world('<trajectory id="l" t="1"></trajectory>')


def test_slice_area_is_the_integral_along_the_cut():
    fw, (a,) = world('<surface id="s" fn="1" x="-1,1" y="-1,1"></surface><slice id="c" of="s" dir="1,0" at="0.5"></slice>')
    fw.apply(a)
    assert fw.values["c.area"] == pytest.approx(2.0, rel=1e-3)   # f = 1 along a cut 2 long
    fw2, (b,) = world('<surface id="s" fn="1" x="-1,1" y="-1,1"></surface><slice id="c" of="nope"></slice>')
    with pytest.raises(BeatError, match="must name a <surface"):
        fw2.apply(b)
