"""``<graph nodes="A:0,0;B:2,1" edges="A-B:7">``: nodes joined by edges; the plan's ``graph`` kind.

Besides a weight, an edge can carry a second number (``edge-values``, e.g. a gradient flowing
back), ``weighted`` draws edges thick or thin by weight, and ``flow="A>B>C"`` sends a packet
along the edges into the beat (a forward pass, or gradients flowing back)."""

from __future__ import annotations

from ...match import as_num, squash
from .. import Display


def _graph_names(raw: str) -> list[str]:
    """``"A:0,0;B:2,1"`` or ``"A,B,C"`` (``"a,b|x,y"``: two lines) -> node names."""
    raw = raw.replace("|", ",")
    parts = raw.split(";") if ";" in raw or ":" in raw else raw.split(",")
    return [p.partition(":")[0].strip() for p in parts if p.strip()]


def edge_pair(key: str) -> frozenset[str] | None:
    """``"A-B"`` / ``"A>B"`` / ``"B<A"`` -> {A, B} (an edge named either way round)."""
    for sep in (">", "<", "-"):
        a, s, b = key.partition(sep)
        if s and a.strip() and b.strip():
            return frozenset((a.strip(), b.strip()))
    return None


def _plan_edges(d: dict) -> set[frozenset[str]] | None:
    edges = d.get("edges")
    if not isinstance(edges, list):
        return None
    out = set()
    for e in edges:
        if isinstance(e, (list, tuple)) and len(e) >= 2:
            out.add(frozenset((str(e[0]), str(e[1]))))
        elif isinstance(e, str) and edge_pair(e.partition(":")[0]):
            out.add(edge_pair(e.partition(":")[0]))
    return out


def _routes(flow) -> list[list[str]] | None:
    """A planned ``flow``: one route ``["A", "B", "C"]`` or several ``[["A", "B"], ["A", "C"]]``."""
    if not isinstance(flow, list) or not flow:
        return None
    routes = flow if all(isinstance(r, list) for r in flow) else [flow]
    if not all(len(r) >= 2 and all(isinstance(x, str) for x in r) for r in routes):
        return None
    return routes


def _check_object(d: dict) -> list[str]:
    problems = []
    edges = _plan_edges(d)
    ev = d.get("edge_values")
    if ev is not None:
        if not isinstance(ev, dict):
            problems.append('graph edge_values must be {"A-B": value, …}')
        else:
            for k in ev:
                pair = edge_pair(str(k))
                if pair is None:
                    problems.append(f'graph edge_values key {k!r}: name the edge "A-B"')
                elif edges is not None and pair not in edges:
                    problems.append(f"graph edge_values {k!r}: there is no edge between those nodes")
    if "flow" in d:
        routes = _routes(d["flow"])
        if routes is None:
            problems.append('graph flow: a route of node names ["A", "B", "C"] (or a list of routes)')
        elif edges is not None:
            for r in routes:
                missing = [f"{a}-{b}" for a, b in zip(r, r[1:]) if frozenset((a, b)) not in edges]
                if missing:
                    problems.append(f"graph flow {r}: no edge for {missing} (a flow runs along edges)")
    lay = d.get("layout")
    if lay not in (None, "line", "two-lines"):
        problems.append('graph layout: "line" (one row, edges arcing above) or "two-lines" (two rows, edges '
                        'between them); leave it out to place the nodes yourself')
    elif lay == "two-lines" and not (isinstance(d.get("lines"), list) and len(d["lines"]) == 2):
        problems.append('graph layout "two-lines" needs "lines": [[top names], [bottom names]]')
    if d.get("weighted") and isinstance(d.get("edges"), list):
        bad = [e for e in d["edges"] if not (isinstance(e, (list, tuple)) and len(e) >= 3 and as_num(e[2]) is not None)]
        if bad:
            problems.append(f"graph weighted: every edge needs a number weight [a, b, w]; not {bad[:3]}")
    return problems


def _pairs(raw: str) -> dict[frozenset[str], str]:
    out = {}
    for part in (p.strip() for p in raw.split(";") if p.strip()):
        key, _, v = part.partition(":")
        pair = edge_pair(key)
        if pair:
            out[pair] = v.strip()
    return out


def _check_drawn(where: str, obj, leaves) -> list[str]:
    graphs = [n for n in leaves if n.tag == "graph"]
    problems = []
    if isinstance(obj.data.get("nodes"), list):
        drawn = {squash(name) for n in graphs for name in _graph_names(n.attrs.get("nodes", ""))}
        missing = [str(x) for x in obj.data["nodes"] if squash(x) not in drawn]
        if missing:
            problems.append(f'{where}: needs <graph nodes="…"> with every planned node; missing {missing}')
    ev = obj.data.get("edge_values")
    if isinstance(ev, dict):
        drawn = [_pairs(n.attrs.get("edge-values", "")) for n in graphs]
        for k, v in ev.items():
            pair = edge_pair(str(k))
            if pair and not any(squash(d.get(pair, "")) == squash(v) for d in drawn):
                problems.append(f'{where}: needs <graph edge-values="{k}:{v}"> (the planned edge value)')
    routes = _routes(obj.data.get("flow"))
    if routes:
        drawn = {squash(r) for n in graphs for r in n.attrs.get("flow", "").split(";")}
        for r in routes:
            if squash(">".join(r)) not in drawn:
                problems.append(f'{where}: needs <graph flow="{">".join(r)}"> (the planned flow)')
    return problems


def _check_layout_drawn(where: str, obj, leaves) -> list[str]:
    d = obj.data
    if not d.get("layout"):
        return []
    graphs = [n for n in leaves if n.tag == "graph"]
    if not any(n.attrs.get("layout", "").strip().lower() == d["layout"] for n in graphs):
        return [f'{where}: needs <graph layout="{d["layout"]}">']
    if d["layout"] == "two-lines" and isinstance(d.get("lines"), list):
        want = "|".join(",".join(map(str, g)) for g in d["lines"])
        if not any(squash(n.attrs.get("nodes", "")) == squash(want) for n in graphs):
            return [f'{where}: needs <graph nodes="{want}"> (the top line, "|", the bottom line)']
    return []


DISPLAY = Display(tag="graph", order=80, steady=True, grow=True, kind="graph", needs=("nodes", "edges"),
                  check_object=_check_object,
                  check_drawn=lambda w, o, l: _check_drawn(w, o, l) + _check_layout_drawn(w, o, l))
