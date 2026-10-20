"""``<vector>`` (kind ``vector``): numbers in brackets, usable beside any picture."""

import importlib.util

import pytest

from konvey.stage.displays import get
from konvey.stage.parse import BeatError, parse_beats

HAS_MANIM = importlib.util.find_spec("manimlib") is not None
manim = pytest.mark.skipif(not HAS_MANIM, reason="needs manimgl (uv --group render)")


def leaf(html: str, i: str = "v"):
    return parse_beats(f"<beats><beat>{html}</beat></beats>")[0].leaves()[i]


def test_plan_checks_a_flat_short_list():
    check = get("vector").check_object
    assert check({"values": [0.9, -0.4, 0.2], "highlight": [0], "label": "\\vec{E}"}) == []
    assert "flat list" in check({"values": [[1, 2], [3, 4]]})[0]
    assert "at most 8" in check({"values": list(range(9))})[0]
    assert "highlight" in check({"values": [1, 2], "highlight": [2]})[0]
    assert "orient" in check({"values": [1, 2], "orient": "diagonal"})[0]


def test_plan_needs_the_drawn_values():
    class Obj:
        kind = "vector"
        data = {"values": [0.9, -0.4, 0.2]}
    assert get("vector").check_drawn("b0", Obj, [leaf('<vector id="v" values="0.9,-0.4,0.2"></vector>')]) == []
    assert "planned values" in get("vector").check_drawn("b0", Obj, [leaf('<vector id="v" values="1,2,3"></vector>')])[0]


@manim
def test_column_row_label_and_highlight():
    from konvey.stage.displays.vector.mobject import VectorBlock, sources

    col = VectorBlock(leaf('<vector id="v" values="0.9,-0.4,0.2" label="x" highlight="1"></vector>'))
    ys = [e.get_y() for e in col.entries]
    assert ys[0] > ys[1] > ys[2]                                    # a column, top to bottom
    left, right = col.brackets
    assert left.get_right()[0] <= col.entries.get_left()[0] and right.get_left()[0] >= col.entries.get_right()[0]
    assert col.name.get_right()[0] < left.get_left()[0]             # "x =" before the brackets
    assert [v for v, _ in sources(col, None)] == ["-0.4"]
    row = VectorBlock(leaf('<vector id="v" values="1,2,3" orient="row"></vector>'))
    xs = [e.get_x() for e in row.entries]
    assert xs[0] < xs[1] < xs[2] and abs(row.entries[0].get_y() - row.entries[2].get_y()) < 1e-6
    with pytest.raises(BeatError, match="needs values"):
        VectorBlock(leaf('<vector id="v"></vector>'))


@manim
def test_morph_keeps_unchanged_entries_and_flies_from_a_source():
    from manimlib import Text, UpdateFromAlphaFunc

    from konvey.stage.displays.vector.mobject import VectorBlock, morph

    a = VectorBlock(leaf('<vector id="v" values="1,2,3"></vector>'))
    b = VectorBlock(leaf('<vector id="v" values="1,5,3"></vector>'))
    c = VectorBlock(leaf('<vector id="v" values="1,5,3,4"></vector>'))

    def flat(anim):
        out = []
        for x in getattr(anim, "animations", [anim]):
            out += flat(x) if hasattr(x, "animations") else [x]
        return out
    plain = flat(morph(a, b))
    flights = flat(morph(a, b, {5.0: Text("5")}))
    count = lambda anims: sum(isinstance(x, UpdateFromAlphaFunc) for x in anims)   # noqa: E731
    assert count(flights) == count(plain) + 1                      # the 5 flies in from the cell showing it
    assert morph(b, c) is not None                                 # an added entry grows in
    assert count(flat(morph(a, a))) == 0                           # nothing changed: no flash
