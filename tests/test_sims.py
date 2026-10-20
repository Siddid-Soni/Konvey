"""Simulations (konvey.stage.sims, the <sim> display): seeded, consistent across beats."""

import importlib.util

import numpy as np
import pytest

from konvey.stage import sims
from konvey.stage.parse import BeatError, parse_beats, prepare_beats

manim = pytest.mark.skipif(importlib.util.find_spec("manimlib") is None, reason="needs manimgl")


def test_drop_is_seeded_and_later_beats_only_add_balls():
    a, b = sims.drop_runs(9, 50, seed=3), sims.drop_runs(9, 200, seed=3)
    assert b[:50] == a and all(r.bin == sum(r.moves) for r in b)
    assert sum(sims.bin_counts(9, 200, seed=3)) == 200
    assert sims.drop_runs(9, 50, seed=4) != a


def test_drop_and_trials_attribute_errors_say_what_to_write():
    with pytest.raises(BeatError, match="between 1 and"):
        sims.drop_spec({"rows": "40"}, "<sim>")
    with pytest.raises(BeatError, match="needs cases"):
        sims.trials_spec({}, "<sim>")
    with pytest.raises(BeatError, match="case numbers"):
        sims.trials_spec({"cases": "H; T", "hits": "2"}, "<sim>")


def test_each_beat_starts_where_the_last_one_ended():
    beats = parse_beats('<beats>' + "".join(
        f'<beat><sim id="g" rule="drop" rows="4" balls="{n}"></sim></beat>' for n in (0, 1, 30, 30)) + '</beats>')
    prepare_beats(beats, strict=False)
    assert [b.leaves()["g"].attrs["_start"] for b in beats] == ["0", "0", "1", "30"]
    assert {b.leaves()["g"].attrs["_most"] for b in beats} == {"30"}


@manim
def test_drop_balls_rest_in_their_bins_and_hide_until_dropped():
    from konvey.stage.displays.sim.mobject import DropBlock
    from konvey.stage.theme import use

    use("editorial", "")
    beat = parse_beats('<beats><beat><sim id="g" rule="drop" rows="6" balls="120" seed="2"></sim></beat></beats>')[0]
    n = beat.leaves()["g"]
    n.attrs["_start"] = "20"
    g = DropBlock(n)
    assert len(g.balls) == 120
    assert all(b.get_fill_opacity() == 0 for b in g.balls[20:]) and g.balls[0].get_fill_opacity() > 0
    for i, run in enumerate(g.runs):   # every ball lies inside its own bin
        assert abs(g.slot[i][0] - g.bin_x[run.bin]) <= g.dx / 2
    assert g.part("bin3") is g.bin_boxes[3]


def test_blocks_count_the_digits_of_pi():
    from konvey.stage.models import timeline

    assert [timeline("blocks", {"mass": str(m)}, "x").info["total"] for m in (1, 100, 10000)] == [3, 31, 314]
    tl = timeline("blocks", {"mass": "100"}, "x")
    p = [tl.state(t) for t in np.linspace(0, tl.end, 50)]
    radius = tl.info["radius"]
    assert all(abs(np.hypot(s["p1"], s["p2"]) - radius) < 1e-9 for s in p)   # energy is kept


def test_spread_is_seeded_and_distancing_lowers_the_peak():
    from konvey.stage.models import timeline

    a = timeline("spread", {"people": "150"}, "x").info["counts"]
    b = timeline("spread", {"people": "150"}, "x").info["counts"]
    c = timeline("spread", {"people": "150", "distancing": "0.5"}, "x").info["counts"]
    assert (a == b).all() and a.sum(1).min() == 150
    assert c[:, 1].max() < a[:, 1].max()


def test_pendulum_spirals_into_rest_and_views_share_the_clock():
    from konvey.stage.models import timeline

    tl = timeline("pendulum", {"angle": "60", "damping": "0.4", "seconds": "30"}, "x")
    assert abs(tl.state(0)["theta"] - np.radians(60)) < 1e-9 and abs(tl.state(30)["theta"]) < 0.05
    beats = parse_beats('<beats>' + "".join(
        f'<beat><sim id="p" rule="pendulum" t="{t}"></sim><simview id="v" sim="p"></simview></beat>' for t in (0, 5, 9))
        + '</beats>')
    prepare_beats(beats, strict=False)
    got = [(b.leaves()["v"].attrs["_t0"], b.leaves()["v"].attrs["_t1"]) for b in beats]
    assert got == [("0.0", "0.0"), ("0.0", "5.0"), ("5.0", "9.0")]
    with pytest.raises(BeatError, match="name a model"):
        prepare_beats(parse_beats('<beats><beat><simview id="v" sim="nope"></simview></beat></beats>'), strict=False)
