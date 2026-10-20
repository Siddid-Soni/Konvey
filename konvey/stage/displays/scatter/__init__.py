"""``<scatter points="1,1; 2,1; 8,8" groups="0,0,1" centroids="1,1; 8,8">``: data points on a
plane, coloured by group, with centres and fitted lines; the plan's ``scatter`` kind."""

from __future__ import annotations

import json
import re

from ...match import as_num, fmt_list, same_values, squash
from .. import Display


def pairs(raw: str) -> list[tuple[float, float]]:
    """``"1,1; 2,1.5"`` (or JSON ``[[1,1],[2,1.5]]``) -> [(1, 1), (2, 1.5)]; ValueError names the bad one."""
    raw = raw.strip()
    items = json.loads(raw) if raw.startswith("[") else [p.split(",") for p in raw.split(";") if p.strip()]
    out = []
    for it in items:
        xy = [as_num(v) for v in it] if isinstance(it, (list, tuple)) else [None]
        if len(xy) != 2 or None in xy:
            raise ValueError(f'"{it if isinstance(it, str) else ",".join(map(str, it))}" is not a point x,y')
        out.append((xy[0], xy[1]))
    return out


_VERTICAL = re.compile(r"^x\s*=\s*(.+)$")


def parse_line(spec) -> tuple[str, float, float]:
    """A line: ``"a,b"`` / ``[a, b]`` is y = a·x + b, ``"x=4"`` a vertical line (a boundary)."""
    if isinstance(spec, (list, tuple)) and len(spec) == 2 and None not in map(as_num, spec):
        return ("ab", as_num(spec[0]), as_num(spec[1]))
    s = str(spec).strip()
    m = _VERTICAL.match(s)
    if m and as_num(m.group(1)) is not None:
        return ("x", as_num(m.group(1)), 0.0)
    ab = [as_num(v) for v in s.split(",")]
    if len(ab) == 2 and None not in ab:
        return ("ab", ab[0], ab[1])
    raise ValueError(f'line "{s}": use "a,b" for y = a·x + b, or "x=4" for a vertical line')


def _flat(points) -> list:
    return [v for p in points for v in p]


def _check_object(d: dict) -> list[str]:
    try:
        pts = pairs(json.dumps(d.get("points", [])))
        cents = pairs(json.dumps(d.get("centroids") or []))
    except (ValueError, TypeError) as e:
        return [f"scatter data['points'] / ['centroids'] must be [[x, y], …] numbers: {e}"]
    if not pts:
        return ["scatter data['points'] must list at least one [x, y]"]
    problems = []
    groups = d.get("groups")
    if groups is not None:
        if not (isinstance(groups, list) and all(isinstance(g, int) and not isinstance(g, bool) and g >= 0
                                                for g in groups)):
            problems.append("scatter data['groups'] must be whole numbers >= 0, one per point")
        elif len(groups) != len(pts):
            problems.append(f"scatter data['groups'] has {len(groups)} entries for {len(pts)} points")
        elif cents and max(groups) >= len(cents):
            problems.append(f"scatter group {max(groups)} has no centroid (centroids are numbered "
                            f"0..{len(cents) - 1})")
    for line in d.get("lines") or []:
        try:
            parse_line(line)
        except ValueError as e:
            problems.append(f"scatter data['lines']: {e}")
    hot = d.get("highlight") or []
    if not (isinstance(hot, list) and all(isinstance(i, int) and 0 <= i < len(pts) for i in hot)):
        problems.append(f"scatter data['highlight'] must be point indices 0..{len(pts) - 1}")
    if d.get("links") and not (groups and cents):
        problems.append("scatter data['links'] needs 'groups' and 'centroids' (a link joins a point to its centroid)")
    return problems


OFF = {"off", "none", "false", "no", "0"}   # links="off": no links


def _check_drawn(where: str, obj, leaves) -> list[str]:
    d = obj.data
    drawn = [n for n in leaves if n.tag == "scatter"]
    for key in ("points", "centroids", "groups"):
        want = d.get(key)
        if not isinstance(want, list) or not want:
            continue
        flat = want if key == "groups" else _flat(want)
        if not any(same_values(flat, n.attrs.get(key, "")) for n in drawn):
            shown = fmt_list(want) if key == "groups" else "; ".join(fmt_list(p) for p in want)
            return [f'{where}: needs <scatter {key}="{shown}"> (the planned {key}, in order)']
    if d.get("lines"):
        try:
            want = [parse_line(x) for x in d["lines"]]
        except ValueError:
            return []
        for n in drawn:
            try:
                got = [parse_line(s) for s in n.attrs.get("lines", "").split(";") if s.strip()]
            except ValueError:
                continue
            if len(got) == len(want) and all(a[0] == b[0] and abs(a[1] - b[1]) < 1e-6 and abs(a[2] - b[2]) < 1e-6
                                             for a, b in zip(want, got)):
                return []
        lines = "; ".join(f"x={a:g}" if k == "x" else f"{a:g},{b:g}" for k, a, b in want)
        return [f'{where}: needs <scatter lines="{lines}"> (each planned line, a,b for y = a·x + b)']
    if d.get("links") and not any(squash(n.attrs.get("links", "off")) not in OFF for n in drawn):
        return [f'{where}: needs <scatter links="on"> (each point joined to its centroid)']
    return []


DISPLAY = Display(tag="scatter", order=55, steady=True, grow=True, enter="create", kind="scatter",
                  needs=("points",), check_object=_check_object, check_drawn=_check_drawn)
