"""``<places>``: places that hold things, and things moving between them; the plan's ``places`` kind
(the old name ``system`` still reads).

Pure Python: how a system's attributes and planned state are read, the checks on the plan and on
the beat HTML, and the pipeline step that copies the planned state into Agent 3's tag. The
drawing and its motion (packets running along the wires) are in ``mobject.py``.
"""

from __future__ import annotations

import re
from typing import Any

from ...match import attr_src, attrs_of, squash
from ...tree import BeatError, Node
from .. import Display

PLACE_KINDS = ("places", "system")   # "system": the old name, in saved plans


def _state_text(v: Any) -> str:
    return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)


def _own_lines(text: str, lines: list[str]) -> list[str]:
    """A card's lines minus any that only repeat its header (weak models write {"text": "SYN",
    "lines": ["SYN"]}); dropped quietly rather than sent back for a repair."""
    key = "".join(text.split()).lower()
    return [x for x in lines if x.strip() and "".join(x.split()).lower() != key]


def system_state(data: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]], dict[str, list[str]]]:
    """A ``system`` object's planned state: ``parts`` (tiers left to right), ``items`` (things of
    their own, each ``{"id", "in": part, "from"?: sender part, "text", "lines"?}``) and ``holds``
    (``{part: [plain contents]}``). Missing or malformed fields read as empty."""
    parts = []   # tiers left to right; a tier of several parts is written "a|b|c"
    for p in data.get("parts", []) if isinstance(data.get("parts"), list) else []:
        p = "|".join(str(x).strip() for x in p) if isinstance(p, (list, tuple)) else str(p).strip()
        if p:
            parts.append(p)
    items = []
    for it in data.get("items", []) if isinstance(data.get("items"), list) else []:
        if isinstance(it, dict):
            lines = it.get("lines") if isinstance(it.get("lines"), list) else []
            text = _state_text(it.get("text", ""))
            items.append({"id": str(it.get("id", "")), "in": str(it.get("in", "") or ""),
                          "from": str(it.get("from", "") or ""), "on": str(it.get("on", "") or ""),
                          "text": text, "lines": _own_lines(text, [_state_text(x) for x in lines])})
    holds: dict[str, list[str]] = {}
    if isinstance(data.get("holds"), dict):
        for k, v in data["holds"].items():
            vals = v if isinstance(v, list) else [v]
            holds[str(k)] = [_state_text(x) for x in vals if x is not None and str(x).strip()]
    return parts, items, holds


def system_tiers(parts) -> list[list[str]]:
    """``"client,balancer,a|b|c"`` (or ``["client", "balancer", ["a", "b", "c"]]``) -> tiers left to
    right; a tier of several parts is drawn as a column (a fan-out)."""
    if isinstance(parts, str):
        raw = [t for t in parts.split(",")]
    else:
        raw = ["|".join(str(x) for x in t) if isinstance(t, (list, tuple)) else str(t) for t in parts]
    tiers = [[p.strip() for p in t.split("|") if p.strip()] for t in raw]
    return [t for t in tiers if t]


def system_holds(raw: str, parts: list[str], where: str) -> dict[str, list[str]]:
    """``"store:1|5|8; server:id 5"`` -> {part: [items]} (part names as written in ``parts``)."""
    by_key = {p.lower(): p for p in parts}
    out: dict[str, list[str]] = {}
    for chunk in (c.strip() for c in raw.split(";") if c.strip()):
        name, sep, items = chunk.partition(":")
        if not sep or name.strip().lower() not in by_key:
            raise BeatError(f'{where} "{chunk}": write part:item|item with a part from parts="{",".join(parts)}"')
        out.setdefault(by_key[name.strip().lower()], []).extend(i.strip() for i in items.split("|") if i.strip())
    return out


def system_place(raw_in: str, raw_on: str, parts, where: str) -> tuple[str, str]:
    """An item's place: ("in", part) or ("on", "a-b") for the wire between parts in neighbouring
    tiers. ``parts`` is a flat list or tiers (see system_tiers)."""
    tiers = system_tiers(parts)
    tier_of = {p.lower(): (k, p) for k, t in enumerate(tiers) for p in t}
    flat = [p for t in tiers for p in t]
    if bool(raw_in.strip()) == bool(raw_on.strip()):
        raise BeatError(f'{where} needs in="<part>" (inside a part) or on="<part>-<part>" (on the wire '
                        "between two neighbours), one of them")
    if raw_in.strip():
        if raw_in.strip().lower() not in tier_of:
            raise BeatError(f'{where} in="{raw_in}" is not one of parts {flat}')
        return "in", tier_of[raw_in.strip().lower()][1]
    a, _, b = raw_on.partition("-")
    ta, tb = tier_of.get(a.strip().lower()), tier_of.get(b.strip().lower())
    if ta is None or tb is None or abs(ta[0] - tb[0]) != 1:
        example = f"{tiers[0][0]}-{tiers[1][0]}" if len(tiers) > 1 else "a-b"
        raise BeatError(f'{where} on="{raw_on}": name two neighbouring parts joined by a wire, like on="{example}"')
    return "on", f"{ta[1]}-{tb[1]}"


SYSTEM_LOOK = ("shapes", "wires", "layout", "links", "w", "h")
LAYOUTS = ("", "row", "ring", "column", "grid")
FREE_LAYOUTS = ("column", "grid")      # parts placed one per cell, not in tiers


def links_of(data: dict) -> str:
    """A plan's ``links``: "none" (no wires: things hop from place to place), a list of pairs
    [["a", "b"], …] (only these wires), or "" (the layout's own wiring)."""
    v = data.get("links") if isinstance(data, dict) else None
    if isinstance(v, str):
        return v.strip().lower() if v.strip().lower() == "none" else v.strip()
    if isinstance(v, list):
        return ";".join(f"{a}-{b}" for a, b in (x for x in v if isinstance(x, (list, tuple)) and len(x) == 2))
    return ""


def link_pairs(raw: str, parts: list[str], where: str) -> list[tuple[str, str]] | None:
    """``links="a-b;b-c"`` -> pairs, ``"none"`` -> [], ``""`` -> None (the layout's own wiring)."""
    raw = raw.strip()
    if not raw:
        return None
    if raw.lower() == "none":
        return []
    by_key = {p.lower(): p for p in parts}
    out = []
    for chunk in (c.strip() for c in raw.split(";") if c.strip()):
        a, sep, b = chunk.partition("-")
        if not sep or a.strip().lower() not in by_key or b.strip().lower() not in by_key or a.strip().lower() == b.strip().lower():
            raise BeatError(f'{where} links="{chunk}": write a-b with two different parts from '
                            f'parts="{",".join(parts)}" ("a-b;b-c"), or links="none"')
        out.append((by_key[a.strip().lower()], by_key[b.strip().lower()]))
    return out


def carry_system_look(beats: list, strict: bool = True) -> None:
    """A system keeps its look (part shapes, wire labels, size) from its first beat on: a beat
    that leaves one out inherits it, so the queue is not a box in one beat and a cylinder in the
    next; its size is always the first beat's; with ``strict`` (checking) a beat that writes
    other shapes or wire labels is an error (it would flicker)."""
    norm = lambda v: "".join((v or "").split()).lower()  # noqa: E731
    _reserve_room(beats)
    look: dict[str, dict[str, str | None]] = {}
    for b in beats:
        for n in b.leaves().values():
            if n.tag != "places" or not n.id:
                continue
            prev = look.get(n.id)
            if prev is not None:
                for a in SYSTEM_LOOK:
                    if a in ("w", "h"):            # its size: the first one simply wins, never an error
                        if prev[a] is None:
                            n.attrs.pop(a, None)
                        else:
                            n.attrs[a] = prev[a]
                    elif a not in n.attrs:
                        if prev[a] is not None:
                            n.attrs[a] = prev[a]
                    elif strict and norm(n.attrs[a]) != norm(prev[a]):
                        was = f'{a}="{prev[a]}"' if prev[a] is not None else f"no {a}"
                        raise BeatError(f'beat {b.index} <places id={n.id}> {a}="{n.attrs[a]}": it was drawn with '
                                        f"{was} before (earlier in this scene, or at the end of the previous one). "
                                        f"The places keep their look: write the same {a} in every beat, or leave it out")
            look[n.id] = {a: n.attrs.get(a) for a in SYSTEM_LOOK}


def _reserve_room(beats: list) -> None:
    """Tell every beat's <system> the most slots and items each part holds in any of these beats
    (``_room="web1:1/1; …"``), so a part is laid out once for the whole scene and a slot does not
    halve in width when a request arrives beside it."""
    most: dict[str, dict[str, list[int]]] = {}
    nodes: dict[str, list[Node]] = {}
    for b in beats:
        for n in b.leaves().values():
            if n.tag != "places" or not n.id:
                continue
            flat = [p for t in system_tiers(n.attrs.get("parts", "")) for p in t]
            try:
                holds = system_holds(n.attrs.get("holds", ""), flat, "holds=")
            except BeatError:
                holds = {}
            m = most.setdefault(n.id, {})
            for p in flat:
                ins = sum(1 for c in n.children if c.attrs.get("in", "").strip().lower() == p.lower())
                cur = m.setdefault(p, [0, 0])
                cur[0], cur[1] = max(cur[0], len(holds.get(p, []))), max(cur[1], ins)
            nodes.setdefault(n.id, []).append(n)
    for sid, ns in nodes.items():
        room = "; ".join(f"{p}:{s_}/{i}" for p, (s_, i) in most[sid].items() if s_ or i)
        for n in ns:
            n.attrs["_room"] = room


SYSTEM_MAX_PARTS = 5


def _check_object(d: dict) -> list[str]:
    """parts / items / holds: a system's state in one beat (see system_state)."""
    if "parts" not in d:
        return []
    problems = []
    free = str(d.get("layout", "") or "").strip().lower() in FREE_LAYOUTS
    if free and not (isinstance(d["parts"], list) and 2 <= len(d["parts"]) <= 9
                     and all(isinstance(p, (str, int, float)) for p in d["parts"])):
        problems.append("places with layout 'column' or 'grid' list 2 to 9 parts, one name each "
                        "(no nested lists): ['A', 'B', 'C']")
    elif not free and not (isinstance(d["parts"], list) and 2 <= len(d["parts"]) <= SYSTEM_MAX_PARTS):
        problems.append(f"places data['parts'] must list 2 to {SYSTEM_MAX_PARTS} tiers left to right, e.g. "
                        "['client', 'server', 'store'], or ['client', 'balancer', ['a', 'b', 'c']] for a fan-out")
    if "items" in d and not (isinstance(d["items"], list) and all(isinstance(i, dict) for i in d["items"])):
        problems.append('places data[\'items\'] must be a list of {"id", "in": "<part>" or "on": "<a>-<b>", '
                        '"text", "lines"?: [...]}')
    if "token" in d:
        problems.append('places has no \'token\': a thing that moves is an item {"id": "req", "in": "client", '
                        '"text": "GET /items/5"}; keep its id and change "in"/"on" to move it')
    if "holds" in d and not isinstance(d["holds"], dict):
        problems.append('places data[\'holds\'] must be {"<part>": ["<item>", ...]}')
    if problems:
        return problems
    parts, items, holds = system_state(d)
    flat = [p for t in system_tiers(parts) for p in t]
    layout = str(d.get("layout", "") or "").strip().lower()
    if layout not in LAYOUTS:
        problems.append(f"places 'layout' {d.get('layout')!r}: use \"ring\" (peers on a circle), \"column\" "
                        "(top to bottom), \"grid\" (rows of places) or leave it out (left to right)")
    try:
        link_pairs(links_of(d), flat, "places")
    except BeatError as e:
        problems.append(str(e))
    if layout == "ring":
        groups = [t for t in system_tiers(parts) if len(t) > 1]
        if len(groups) != 1 or not 3 <= len(groups[0]) <= 8 or len(system_tiers(parts)) > 3:
            problems.append("places layout 'ring' needs one group of 3 to 8 peers in parts, e.g. "
                            "['client', ['s1', 's2', 's3', 's4', 's5']] (a part before or after the group sits "
                            "beside the ring)")
    elif layout not in FREE_LAYOUTS and (len(flat) > 8 or any(len(t) > 4 for t in system_tiers(parts))):
        problems.append("places: at most 8 parts, at most 4 in one tier")
    names = {p.strip().lower() for p in flat}
    ids = [it["id"] for it in items]
    if any(not i for i in ids) or len(set(ids)) != len(ids):
        problems.append(f"places items need distinct ids (got {ids}); an item keeps its id in every beat")
    for it in items:
        where = f"places item {it['id']!r}"
        if it["on"]:
            problems.append(f'{where}: items always rest inside a part ("in"); a message travels by itself '
                            'when its "in" changes from one beat to the next, and a new one sent in this beat '
                            'is {"in": "<receiver>", "from": "<sender>"}')
            continue
        try:
            system_place(it["in"], "", parts, where)
            if it["from"]:
                if system_place(it["from"], "", parts, where)[1].lower() == it["in"].strip().lower():
                    problems.append(f'{where}: "from" names the part it is in; "from" is the sender')
        except BeatError as e:
            problems.append(str(e).replace("needs in=", "needs \"in\": ").replace('in="', '"in": "'))
        if not it["text"].strip():
            problems.append(f"{where} needs a 'text'")
        for t in [it["text"], *it["lines"]]:
            if len(t) > 28:
                problems.append(f"{where}: {t!r} is too long to read on it (at most 28 characters); shorten it "
                                "or split it into 'lines'")
        if len(it["lines"]) > 4:
            problems.append(f"{where}: at most 4 lines")
        problems += _separator_problems(where, [it["text"], *it["lines"]])
    for part, vals in holds.items():
        if part.strip().lower() not in names:
            problems.append(f"places holds {part!r}, which is not one of parts {flat}")
        for v in vals:
            if len(v) > 32:
                problems.append(f"places holds {part!r}: {v!r} is too long for a slot (at most 32 characters); "
                                "keep the value short (\"203.0.113.7\") and let the part's name or the narration "
                                "say what it is, or make it an item with lines")
        problems += _separator_problems(f"places holds {part!r}", vals)
    return problems


def _separator_problems(where: str, texts: list[str]) -> list[str]:
    """A "|" or ";" separates lines and parts in the drawn tag (lines="a|b", holds="p:a|b; q:c"), so
    a planned text holding one could never be drawn or matched: it is rejected up front."""
    return [f"{where}: {t!r} has {'|' if '|' in t else ';'!r}, which the drawing uses to separate lines "
            f"and parts; write {_SEP_RE.sub(' · ', t)!r} or split it into two lines"
            for t in texts if _SEP_RE.search(t)]


_SEP_RE = re.compile(r"\s*[|;]\s*")


def _check_plan(plan) -> list[str]:
    """A ``system`` tells its story through state: once shown it stays, and every beat moves an item,
    changes what a part holds, or changes another picture; and what the drawing carries is not
    repeated as a separate text object (it would be printed twice, away from the picture)."""
    from ....validators import _picture_states

    errors = []
    for scene in plan.scenes:
        prev = None
        seen_system: str | None = None
        last_place: dict[tuple[str, str], str] = {}     # (system id, item id) -> part
        for b, beat in enumerate(scene.beats):
            tag = f"Scene {scene.id} beat {b}"
            objs = [o for o in beat.objects if not isinstance(o, str)]
            systems = [o.id for o in objs if o.kind in PLACE_KINDS]
            if seen_system and seen_system not in systems:
                errors.append(f"{tag}: the places {seen_system!r} left the screen. Once they are shown, keep them "
                              "in every later beat of the scene: numbers about its parts (load, counts, time "
                              "left) go into those parts' holds or items, and a chart or formula may sit under it")
            seen_system = seen_system or (systems[0] if systems else None)
            for o in objs:
                if o.kind not in PLACE_KINDS:
                    continue
                parts, items, _ = system_state(o.data)
                tier = {p.lower(): k for k, t in enumerate(system_tiers(parts)) for p in t}
                if _layout(o.data) in ("ring", *FREE_LAYOUTS) or links_of(o.data):
                    tier = {}            # peers on a ring, or places linked as drawn, pass things directly
                for it in items:
                    key, here = (o.id, it["id"]), it["in"].strip().lower()
                    there = last_place.get(key)
                    if there and there != here and tier.get(there) is not None and tier.get(there) == tier.get(here):
                        errors.append(f"{tag}: item {it['id']!r} moves from {there!r} to {here!r}, two parts side by "
                                      "side (one column). A request handled by one server stays there (or is "
                                      "counted in its holds and dropped); the next request is a NEW item with its "
                                      'own id, sent from where it really comes from: {"id": "req2", "in": "<server>", '
                                      '"from": "<client or balancer>"}')
                    last_place[key] = here
            stated = []
            for o in objs:
                if o.kind in PLACE_KINDS:
                    _, items, holds = system_state(o.data)
                    stated += [x for it in items for x in (it["text"], *it["lines"])]
                    stated += [t for v in holds.values() for t in v]
            shown = {"".join(t.split()).lower() for t in stated if t.strip()}
            for o in objs:
                if o.kind == "text" and "".join(str(o.data.get("text", "")).split()).lower() in shown:
                    errors.append(f"{tag}: text {o.data.get('text')!r} repeats what the places' items/holds "
                                  "already show; drop the text object")
            now = _picture_states(beat)
            has_parts = any(o.kind in PLACE_KINDS for o in objs)
            if prev is not None and has_parts and now == prev:
                # a filler beat is a weakness, not worth a failed run: noted, never rejected
                print(f"note: {tag}: the places look the same as in beat {b - 1}", flush=True)
            prev = now
    return errors


def _layout(data: dict) -> str:
    return str(data.get("layout", "") or "").strip().lower() if isinstance(data, dict) else ""


def _apply_plan(body: str, obj) -> str:
    tags = list(re.finditer(r"<(?:system|places)\b([^>]*?)(/>|>(.*?)</(?:system|places)>)", body, re.S))
    tag = next((t for t in tags if attrs_of(t.group(1)).get("id") == obj.id), tags[0] if len(tags) == 1 else None)
    if tag is None:
        return body
    parts, items, holds = system_state(obj.data)
    attrs = attrs_of(tag.group(1))
    attrs["parts"] = ",".join(parts)
    if _layout(obj.data) not in ("", "row"):
        attrs["layout"] = _layout(obj.data)
    else:
        attrs.pop("layout", None)
    if links_of(obj.data):
        attrs["links"] = links_of(obj.data)
    else:
        attrs.pop("links", None)
    held = "; ".join(f'{p}:{"|".join(v)}' for p, v in holds.items() if v)
    if held:
        attrs["holds"] = held
    else:
        attrs.pop("holds", None)
    if attrs.get("highlight"):                   # keep only highlights of what is still there
        keep = []
        flat = {p.lower() for t in system_tiers(parts) for p in t}
        for chunk in (c.strip() for c in attrs["highlight"].split(";") if c.strip()):
            part, sep, rest = chunk.partition(":")
            if not sep and part.strip().lower() in flat:
                keep.append(chunk)
            elif sep:
                vals = [v for v in rest.split("|") if v.strip() in holds.get(part.strip(), [])]
                if vals:
                    keep.append(f"{part.strip()}:{'|'.join(vals)}")
        if keep:
            attrs["highlight"] = "; ".join(keep)
        else:
            attrs.pop("highlight")
    old = {attrs_of(c.group(1)).get("id"): attrs_of(c.group(1))
           for c in re.finditer(r"<item\b([^>]*?)/?>", tag.group(3) or "")}
    kids = []
    for it in items:
        a = {k: v for k, v in old.get(it["id"], {}).items() if k in ("style", "color")}
        a = {"id": it["id"], "in": it["in"], **({"from": it["from"]} if it["from"] else {}), "text": it["text"],
             **({"lines": "|".join(it["lines"])} if it["lines"] else {}), **a}
        kids.append(f"<item {attr_src(a)}></item>")
    new = f"<places {attr_src(attrs)}>{''.join(kids)}</places>"
    return body[:tag.start()] + new + body[tag.end():]


def _system_tag(obj_id: str, parts: list[str], items: list[dict], holds: dict, layout: str = "",
                links: str = "") -> str:
    attrs = [f'id="{obj_id}"', f'parts="{",".join(parts)}"'] + ([f'layout="{layout}"'] if layout not in ("", "row") else []) \
        + ([f'links="{links}"'] if links else [])
    if any(holds.values()):
        attrs.append('holds="' + "; ".join(f'{p}:{"|".join(v)}' for p, v in holds.items() if v) + '"')
    kids = []
    for it in items:
        where = f'in="{it["in"]}"' + (f' from="{it["from"]}"' if it["from"] else "")
        lines = f' lines="{"|".join(it["lines"])}" style="card"' if it["lines"] else ""
        kids.append(f'<item id="{it["id"]}" {where} text="{it["text"]}"{lines}></item>')
    return f"<places {' '.join(attrs)}>{''.join(kids)}</places>"


def _check_scene(scene, beats) -> list[str]:
    """A planned ``system`` is drawn as a ``<system>`` in the beat with that vo, with exactly the
    planned parts, held items and items (id, place, text, lines). How it looks (style, colour,
    shapes, wire labels, notes, highlight) is Agent 3's choice."""
    by_vo = {squash(b.attrs.get("vo", "")): b for b in beats}
    problems: list[str] = []
    for i, beat in enumerate(scene.beats):
        html_beat = by_vo.get(squash(beat.vo_line))
        if html_beat is None:
            continue
        for obj in beat.objects:
            if isinstance(obj, str) or obj.kind not in PLACE_KINDS:
                continue
            parts, items, holds = system_state(obj.data)
            want = _system_tag(obj.id, parts, items, holds, _layout(obj.data), links_of(obj.data))
            drawn = [n for n in html_beat.leaves().values() if n.tag == "places"]
            node = next((n for n in drawn if n.id == obj.id), drawn[0] if len(drawn) == 1 else None)
            tag = f"plan beat {i} places {obj.id!r}"
            if node is None:
                problems.append(f"{tag}: draw it as {want} (add style/colour/shapes as you like)")
                continue
            got_parts = [p.strip() for p in node.attrs.get("parts", "").split(",") if p.strip()]
            wrong = []
            if [squash(p) for p in got_parts] != [squash(p) for p in parts]:
                wrong.append(f'parts="{",".join(got_parts)}"')
            lay = lambda v: "" if v in ("", "row") else v  # noqa: E731
            if lay(node.attrs.get("layout", "").strip().lower()) != lay(_layout(obj.data)):
                wrong.append(f'layout="{node.attrs.get("layout", "")}"')
            if squash(node.attrs.get("links", "")) != squash(links_of(obj.data)):
                wrong.append(f'links="{node.attrs.get("links", "")}"')
            try:
                got_holds = system_holds(node.attrs.get("holds", ""),
                                         [p for t in system_tiers(got_parts) for p in t], "holds=")
            except BeatError:
                got_holds = {}
            norm = lambda hs: {squash(p): [squash(x) for x in v] for p, v in hs.items() if v}  # noqa: E731

            def key(it_id, where_in, sender, text, lines):
                own = tuple(squash(x) for x in lines if squash(x) != squash(text))   # a repeated header is dropped
                return (it_id, squash(where_in), squash(sender), squash(text), own)
            want_items = sorted(key(it["id"], it["in"], it["from"], it["text"], it["lines"]) for it in items)
            got_items = sorted(key(c.id or "", c.attrs.get("in", ""), c.attrs.get("from", ""), c.attrs.get("text", ""),
                                   [x.strip() for x in c.attrs.get("lines", "").split("|") if x.strip()])
                               for c in node.children)
            if norm(got_holds) != norm(holds):
                wrong.append(f'holds="{node.attrs.get("holds", "")}"')
            if want_items != got_items:
                wrong.append("items " + ", ".join(f'<item id="{c.id}" in="{c.attrs.get("in", "")}" '
                                                  f'from="{c.attrs.get("from", "")}" text="{c.attrs.get("text", "")}">'
                                                  for c in node.children) if node.children else "no items")
            if wrong:
                problems.append(f"{tag}: drawn with {'; '.join(wrong)}; the plan's state for this beat is "
                                f"{want} (keep these ids, places and texts; style, colour, shapes, wires, notes "
                                "and highlight are yours)")
    return problems


def _adopt(prev, first) -> None:
    """One system on each side of a scene cut, same parts, different ids: the same system."""
    olds = [n for n in prev.leaves().values() if n.tag == "places"]
    news = [n for n in first.leaves().values() if n.tag == "places"]
    if len(olds) == 1 and len(news) == 1 and olds[0].id != news[0].id and \
            "".join(olds[0].attrs.get("parts", "").split()) == "".join(news[0].attrs.get("parts", "").split()):
        olds[0].attrs["id"] = news[0].id


DISPLAY = Display(tag="places", order=110, aliases=("system",), children=frozenset({"item"}), steady=True,
                  prepare=carry_system_look, adopt=_adopt, kind="places", needs=("parts",),
                  check_object=_check_object, check_plan=_check_plan, check_scene=_check_scene,
                  apply_plan=_apply_plan)
