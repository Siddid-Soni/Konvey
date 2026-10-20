"""``<collection>``: members sorted into groups, written as nested lists; the renderer lays them out.

    <collection id="people" look="units">
      <li count="40" color="c3">left-handed
        <li count="30" mark>plays chess</li>
        <li count="10">does not</li>
      </li>
      <li count="960">right-handed</li>
    </collection>

    <collection id="hand" look="row"><li>7♥</li><li>K♠</li><li>2♦</li></collection>

A group is an ``<li>`` with ``count="N"`` (N identical units) or with ``<li>`` inside it; an
``<li>`` with only text is one listed member (a chip showing that text). ``look`` picks the
picture (``units``: one packed block; ``bins``: a pile per group; ``row``: one line in order;
``stacks``: a post per group with its members piled on it), ``shape`` the unit (dot, square,
ball, chip, slab) or ``icon`` the line icon each member is drawn as (a sock, a person, a coin). Members keep their identity between beats: listed
ones by their text, counted ones by their group (``from="right-handed > plays chess"`` to regroup),
so a split, a merge, a draw or a change of look moves the same members.
"""

from __future__ import annotations

from .. import Display

LOOKS = ("units", "bins", "row", "stacks")
SHAPES = ("dot", "square", "ball", "chip", "slab", "icon")
PILES = ("bins", "stacks")   # may start empty: the piles things will be sorted into
MAX_MEMBERS = 2000


def _group_problems(g, where: str) -> tuple[list[str], int]:
    if not isinstance(g, dict) or not str(g.get("name", "")).strip():
        return [f"{where}: each group is {{\"name\": …, \"count\": N}} or {{\"name\": …, \"members\": [...]}}"], 0
    name = g["name"]
    problems, total = [], 0
    kids = g.get("groups") or []
    members = g.get("members") or []
    if not isinstance(kids, list) or not isinstance(members, list):
        return [f"{where} '{name}': groups and members are lists"], 0
    for k in kids:
        p, n = _group_problems(k, f"{where} '{name}'")
        problems += p
        total += n
    total += len(members)
    if "count" in g:
        count = g["count"]
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            return problems + [f"{where} '{name}': count {count!r} must be a whole number"], 0
        if members:
            problems.append(f"{where} '{name}': give a count or listed members, not both")
        elif kids and total != count:
            problems.append(f"{where} '{name}': count {count} but its groups add up to {total}")
        total = count
    elif not kids and not members:
        problems.append(f"{where} '{name}': needs a count, members or groups")
    return problems, total


def _named(n) -> bool:
    """A top-level group with a name (or named sub-groups): the block shows a legend."""
    return any((c.text or any(k.tag == "li" for k in c.children)) and ("count" in c.attrs or c.children)
               for c in n.children if c.tag == "li")


def _legend_room(beats: list, strict: bool = True) -> None:
    """A collection whose legend shows in any beat (a named group, not in ``bins``, which names its
    piles underneath) keeps room for it in every beat, so its block does not reflow (and its
    members jump) when a split first names them."""
    nodes = [n for b in beats for n in b.leaves().values() if n.tag == "collection" and n.id]
    named = {n.id for n in nodes if _named(n) and n.attrs.get("look", "units").strip() not in ("bins", "stacks")
             and n.attrs.get("legend") != "none"}
    for n in nodes:
        if n.id in named:
            n.attrs["_legend"] = "1"


def _check_object(d: dict) -> list[str]:
    groups, members = d.get("groups") or [], d.get("members") or []
    if not isinstance(groups, list) or not isinstance(members, list) or not (groups or members):
        return ["collection data needs 'groups' (and/or loose 'members') as lists"]
    problems, total = [], len(members)
    for g in groups:
        p, n = _group_problems(g, "collection")
        problems += p
        total += n
    if d.get("look", "units") not in LOOKS:
        problems.append(f"collection look {d.get('look')!r}: use one of {', '.join(LOOKS)}")
    if d.get("shape", "dot") not in SHAPES:
        problems.append(f"collection shape {d.get('shape')!r}: use one of {', '.join(SHAPES)}")
    if d.get("icon"):
        from ... import icons
        if not icons.exists(str(d["icon"])):
            near = icons.suggest(str(d["icon"]))
            problems.append(f"collection icon {d['icon']!r} is not in the icon set"
                            + (f"; close: {', '.join(near)}" if near else "; leave it out (dots)"))
    least = 0 if d.get("look", "units") in PILES else 1
    if not problems and not least <= total <= MAX_MEMBERS:
        problems.append(f"collection has {total} members; draw 1 to {MAX_MEMBERS} (scale the population down)")
    return problems


DISPLAY = Display(tag="collection", order=75, children=frozenset({"li"}), nested=True, steady=True,
                  grow=True, shrink=0.5, min_size=22, kind="collection", prepare=_legend_room,
                  check_object=_check_object)
