"""``<attention tokens="a,fluffy,blue,creature" weights="…">``: who attends to whom in a row of
words; the plan's ``attention`` kind.

Drawn the way 3Blue1Brown draws an attention pattern: the words in a row across the top are the
queries, the same words down the left are the keys, and each cell holds a dot sized by how much
that column's word attends to that row's word. ``weights`` is given one group per query word (its
column), so a softmaxed group sums to 1. ``view="words"`` shows the sentence instead, with
arrows arcing from the attended words into the ``focus`` word, and short vectors under the words;
the same words stay in place between views, so one picture morphs through the whole mechanism.
This module is pure Python: the attribute parsing shared with the mobject, and the plan checks."""

from __future__ import annotations

import re

from ...match import as_num, fmt_list, same_values, split_list, squash
from ...tree import BeatError
from .. import Display

MAX_TOKENS = 10        # beyond this the words and cells are unreadably small
SUM_TOL = 0.02         # a softmaxed column sums to 1 within rounding (0.33 + 0.33 + 0.33)
VIEWS = ("grid", "words", "both")
NEG_INF = {"-inf", "−inf", "-∞", "−∞"}


def tokens_of(raw: str) -> list[str]:
    return [t for t in split_list(raw) if t] if raw.strip() else []


def groups_of(raw: str) -> list[list[str]]:
    """``"0.1,0.9;1,0"`` -> one list per group (a query's weights, a token's vector)."""
    if not raw.strip():
        return []
    sep = "|" if "|" in raw else ","
    return [[c.strip() for c in g.split(sep)] if g.strip() else [] for g in raw.split(";")]


def cell_num(text: str) -> float | None:
    """A weight as a number; "" (not computed yet) is None, a masked "-inf" is -inf."""
    t = text.strip().lower()
    if t in NEG_INF:
        return float("-inf")
    return as_num(t) if t else None


def token_index(spec: str, tokens: list[str], what: str) -> int | None:
    """``focus="creature"`` or ``focus="3"`` -> its position; a repeated word needs its index."""
    spec = spec.strip()
    if not spec:
        return None
    hits = [i for i, t in enumerate(tokens) if squash(t) == squash(spec)]
    if len(hits) == 1:
        return hits[0]
    if spec.isdigit() and int(spec) < len(tokens):
        return int(spec)
    if hits:
        raise BeatError(f'{what}="{spec}": that word appears {len(hits)} times; give its position '
                        f'(0..{len(tokens) - 1}) instead')
    raise BeatError(f'{what}="{spec}" is not one of the tokens ({", ".join(tokens)})')


def truthy(v) -> bool:
    return str(v).strip().lower() in ("true", "yes", "1", "on")


def masked(key: int, query: int, mask: str) -> bool:
    """A causal mask: a word sees only itself and the words before it."""
    return mask == "causal" and key > query


def weight_problems(tokens: list[str], weights: list[list], softmax: bool, mask: str) -> list[str]:
    """Shape (one group of len(tokens) per query, or no group yet), numbers, and with ``softmax``
    columns that sum to 1 with masked cells at 0. Shared by the plan check and the renderer."""
    n = len(tokens)
    if len(weights) != n:
        return [f"weights has {len(weights)} groups for {n} tokens: give one group per query word "
                f"(its weights over all {n} words, in token order), {n} groups of {n}"]
    problems = []
    for q, col in enumerate(weights):
        if not col or all(str(c).strip() == "" for c in col):
            continue                                   # this query's weights are not computed yet
        if len(col) != n:
            problems.append(f'weights for "{tokens[q]}" has {len(col)} numbers for {n} words')
            continue
        nums = [cell_num(str(c)) if not isinstance(c, (int, float)) else float(c) for c in col]
        bad = [c for c, v in zip(col, nums) if v is None and str(c).strip()]
        if bad:
            problems.append(f'weights for "{tokens[q]}": {bad[:3]} are not numbers')
            continue
        if not softmax or None in nums:
            continue
        hidden = [tokens[k] for k, v in enumerate(nums) if masked(k, q, mask) and v != 0]
        if hidden:
            problems.append(f'weights for "{tokens[q]}": with mask causal the later words {hidden} '
                            f"must have weight 0 after softmax")
        if any(v < 0 or v > 1 for v in nums):
            problems.append(f'weights for "{tokens[q]}": softmax weights lie between 0 and 1')
        elif abs(sum(nums) - 1) > SUM_TOL:
            problems.append(f'weights for "{tokens[q]}" sum to {sum(nums):.3g}; after softmax each query\'s '
                            f"weights sum to 1")
    return problems


# --- the plan --------------------------------------------------------------------------------
def _plan_weights(d: dict) -> list[list] | None:
    w = d.get("weights")
    if isinstance(w, list) and all(isinstance(g, list) for g in w):
        return [["" if v is None else v for v in g] for g in w]
    return None


def _check_object(d: dict) -> list[str]:
    toks = d.get("tokens")
    if not (isinstance(toks, list) and toks and all(isinstance(t, (str, int, float)) for t in toks)):
        return ['attention tokens must be a list of words ["a", "fluffy", "blue", "creature"]']
    toks = [str(t) for t in toks]
    problems = []
    if not 2 <= len(toks) <= MAX_TOKENS:
        problems.append(f"attention has {len(toks)} tokens; use 2 to {MAX_TOKENS} (a short phrase)")
    mask = str(d.get("mask") or "none").lower()
    if mask not in ("none", "causal"):
        problems.append(f'attention mask {d.get("mask")!r}: use "causal" or leave it out')
    if "weights" in d:
        w = _plan_weights(d)
        if w is None:
            problems.append("attention weights: a list with one list per query word (its weights over "
                            "every word), e.g. [[1, 0], [0.3, 0.7]]")
        else:
            problems += [f"attention {p}" for p in weight_problems(toks, w, bool(d.get("softmax")), mask)]
    view = d.get("view", "grid")
    if view not in VIEWS:
        problems.append(f"attention view {view!r}: use one of {', '.join(VIEWS)}")
    for key in ("focus", "focus_key"):
        if key in d and squash(d[key]) not in {squash(t) for t in toks} and not (
                isinstance(d[key], int) and 0 <= d[key] < len(toks)):
            problems.append(f"attention {key} {d[key]!r} is not one of the tokens")
    vecs = d.get("vectors")
    if vecs is not None:
        if isinstance(vecs, dict):
            vecs = [vecs.get(t, []) for t in toks]
        if not (isinstance(vecs, list) and len(vecs) == len(toks) and all(isinstance(v, list) for v in vecs)):
            problems.append("attention vectors: one short list of numbers per token (or {word: [numbers]})")
        elif any(len(v) > 6 for v in vecs):
            problems.append("attention vectors: at most 6 numbers each (a column under the word)")
    return problems


def _vector_list(d: dict, toks: list[str]) -> list[list] | None:
    vecs = d.get("vectors")
    if isinstance(vecs, dict):
        vecs = [vecs.get(t, []) for t in toks]
    return vecs if isinstance(vecs, list) and all(isinstance(v, list) for v in vecs) else None


def _check_drawn(where: str, obj, leaves) -> list[str]:
    d = obj.data
    toks = [str(t) for t in d.get("tokens") or []]
    mine = [n for n in leaves if n.tag == "attention"]
    if not toks or not mine:
        return [f'{where}: needs <attention tokens="{",".join(toks)}"> (the planned words)'] if toks else []
    same = [n for n in mine if [squash(t) for t in tokens_of(n.attrs.get("tokens", ""))] == [squash(t) for t in toks]]
    if not same:
        return [f'{where}: needs <attention tokens="{fmt_list(toks)}"> (the planned words, in order)']
    problems = []
    w = _plan_weights(d)
    if w is not None:
        want = ";".join(fmt_list(g) for g in w)
        flat = [v for g in w for v in g]
        if not any(same_values(flat, n.attrs.get("weights", "")) and len(groups_of(n.attrs.get("weights", ""))) == len(w)
                   for n in same):
            problems.append(f'{where}: needs <attention weights="{want}"> (the planned weights, one group per '
                            f"query word)")
    for key, attr in (("softmax", "softmax"), ("numbers", "numbers"), ("qk", "qk")):
        if d.get(key) and not any(truthy(n.attrs.get(attr, "")) for n in same):
            problems.append(f'{where}: needs <attention {attr}="true">')
    if str(d.get("mask") or "").lower() == "causal" and not any(n.attrs.get("mask", "").strip().lower() == "causal"
                                                                for n in same):
        problems.append(f'{where}: needs <attention mask="causal">')
    for key, attr in (("focus", "focus"), ("focus_key", "focus-key"), ("view", "view")):
        if key in d and not any(squash(n.attrs.get(attr, "grid" if key == "view" else "")) == squash(d[key])
                                for n in same):
            problems.append(f'{where}: needs <attention {attr}="{d[key]}">')
    vecs = _vector_list(d, toks)
    if vecs is not None:
        flat = [v for g in vecs for v in g]
        if not any(same_values(flat, n.attrs.get("vectors", "")) for n in same):
            want = ";".join(fmt_list(g) for g in vecs)
            problems.append(f'{where}: needs <attention vectors="{want}"> (one group per token)')
    return problems


# --- one picture for the scene ---------------------------------------------------------------
def _view(n) -> str:
    v = n.attrs.get("view", "").strip().lower()
    if v:
        return v
    return "grid" if n.attrs.get("weights", "").strip() else "words"


def _arrows(n) -> bool:
    return _view(n) in ("words", "both") and bool(n.attrs.get("focus", "").strip()) \
        and bool(n.attrs.get("weights", "").strip())


def _reserve_room(beats: list, strict: bool = True) -> None:
    """Every beat of one ``<attention id>`` is laid out on one canvas: the room for the grid, the
    key column, the arcs and the vectors that any beat of the scene shows is kept in all of them
    (``_room``), so the words never move while the picture changes under them. Raw scores share
    one scale (``_scale``), so a dot keeps its size until its own number changes."""
    nodes: dict[str, list] = {}
    for b in beats:
        for n in b.leaves().values():
            if n.tag == "attention" and n.id:
                nodes.setdefault(n.id, []).append(n)
    for ns in nodes.values():
        grid = any(_view(n) in ("grid", "both") for n in ns)
        arcs = any(_arrows(n) for n in ns)
        qk = any(truthy(n.attrs.get("qk", "")) for n in ns)
        vec = max((len(g) for n in ns if _view(n) == "words" for g in groups_of(n.attrs.get("vectors", ""))),
                  default=0)
        rows = max((len(tokens_of(n.attrs.get("tokens", ""))) for n in ns), default=0)
        raw = [abs(v) for n in ns if not truthy(n.attrs.get("softmax", ""))
               for g in groups_of(n.attrs.get("weights", "")) for v in map(cell_num, g)
               if v is not None and v != float("-inf")]
        room = f"grid={int(grid)};arcs={int(arcs)};qk={int(qk)};vec={vec};rows={rows}"
        for n in ns:
            n.attrs["_room"] = room
            n.attrs["_scale"] = f"{max(raw, default=1.0) or 1.0:g}"


ROOM_RE = re.compile(r"(\w+)=(\d+)")


def room_of(raw: str) -> dict[str, int]:
    return {k: int(v) for k, v in ROOM_RE.findall(raw)}


DISPLAY = Display(tag="attention", order=82, steady=True, grow=True, shrink=0.5, min_size=22,
                  kind="attention", needs=("tokens",), prepare=_reserve_room,
                  check_object=_check_object, check_drawn=_check_drawn)
