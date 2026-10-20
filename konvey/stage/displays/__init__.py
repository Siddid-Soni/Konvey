"""Display types: one folder per overlay tag (``<array>``, ``<system>``, ``<graph>``, ...).

A display is self-contained; adding one is adding a folder (see ``README.md`` here):

- ``<name>/__init__.py``: ``DISPLAY = Display(...)`` — the tag, how it parses and lays out, the
  plan object kind it draws and its checks. Pure Python (no manimgl): the planner, the static
  checker and the parser load it.
- ``<name>/mobject.py``: ``build(node, world) -> Mobject`` at natural size, plus optional motion
  hooks (manimgl; loaded only when rendering):

  ``morph(old, new, sources)``   same id, new content: animate old into new (None = default)
  ``sources(new, old)``          [(value, live mobject)] numbers the picture points at, which a
                                 changing label takes from there (motion.picture_sources)
  ``enter(node, mob, run_time)`` / ``exit(node, mob)``   override the named enter/exit animations
  ``move(old, new)``             same content, new place (default Transform)
  ``emphasis_target(kind, mob)`` what ``emphasize=`` acts on (default the whole mobject)
  ``live(node, mob, hold)``      an Animation played during the beat's hold (a simulation that
                                 keeps running while the line is spoken), or None

- ``<name>/agent3.md``: Agent 3's docs. The first paragraph is its row in the tag table of
  ``prompts/agent3-stage/reference.md``; anything after a blank line is a section after the table.
- ``<name>/plan.md`` (optional): Agent 2's row in the object-kinds table of
  ``prompts/agent2-stage/plan.md``.

Named enter/exit/emphasis animations shared by every display live in ``konvey/stage/animations.py``.
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Display:
    tag: str
    order: int = 1000              # place in Agent 3's tag table (and among plan rows placed by default)
    # --- parsing / layout -----------------------------------------------------------
    raw: bool = False              # inner text kept verbatim (LaTeX)
    aliases: tuple[str, ...] = ()  # old tag / kind names still read as this display (saved runs)
    children: frozenset[str] = frozenset()   # child tags allowed inside it (``<item>`` in a system)
    nested: bool = False           # children nest (``<li>`` in ``<li>``) and keep their text
    shrink: float | None = 0.6     # may scale down to this fraction to fit the page; None: never
    steady: bool = False           # one scale and one place for the whole scene (no jumping)
    grow: bool | float = False     # alone in its container, it scales up into the spare room (a plot);
                                   # a number: how far past its natural size (default GROW_MAX)
    min_size: int | None = None    # smallest readable ``size=``
    enter: str | None = None       # default enter animation (see animations.ENTERS)
    prepare: Callable[[list, bool], None] | None = None   # (beats, strict): scene-wide normalising
    adopt: Callable[[Any, Any], None] | None = None       # (prev scene's last beat, first beat)
    # --- the plan (Agent 2) -------------------------------------------------------------
    kind: str | None = None        # the plan object kind it draws
    needs: tuple[str, ...] = ()    # data keys an object of that kind must have
    picture: bool = True           # counts as a beat's visual (text-like readouts do not)
    check_object: Callable[[dict], list[str]] | None = None          # one object's data
    check_plan: Callable[[Any], list[str]] | None = None             # rules across beats
    # --- the beat HTML (Agent 3) --------------------------------------------------------
    check_drawn: Callable[[str, Any, list], list[str]] | None = None  # (where, obj, leaves): data verbatim
    check_scene: Callable[[Any, list], list[str]] | None = None       # (scene, beats)
    apply_plan: Callable[[str, Any], str] | None = None              # (beat body html, obj) -> html
    package: str = field(default="", compare=False)                  # filled in by discovery


_REGISTRY: dict[str, Display] = {}


def _discover() -> None:
    for info in sorted(pkgutil.iter_modules([str(HERE)]), key=lambda m: m.name):
        if not info.ispkg or info.name.startswith("_"):
            continue
        mod = importlib.import_module(f"{__name__}.{info.name}")
        d = getattr(mod, "DISPLAY", None)
        if not isinstance(d, Display):
            raise TypeError(f"{mod.__name__} has no DISPLAY = Display(...)")
        if d.tag in _REGISTRY:
            raise ValueError(f"two displays draw <{d.tag}>: {_REGISTRY[d.tag].package} and {mod.__name__}")
        _REGISTRY[d.tag] = replace(d, package=mod.__name__)


def all_displays() -> list[Display]:
    return sorted(_REGISTRY.values(), key=lambda d: (d.order, d.tag))


def aliases() -> dict[str, str]:
    """Old tag (and kind) name -> the display's tag now."""
    return {a: d.tag for d in _REGISTRY.values() for a in d.aliases}


def get(tag: str | None) -> Display | None:
    tag = tag or ""
    return _REGISTRY.get(tag) or _REGISTRY.get(aliases().get(tag, ""))


def for_kind(kind: str | None) -> Display | None:
    return next((d for d in _REGISTRY.values() if kind and (d.kind == kind or kind in d.aliases)), None)


def tags() -> frozenset[str]:
    return frozenset(_REGISTRY)


def kinds() -> tuple[str, ...]:
    return tuple(d.kind for d in all_displays() if d.kind)


_MOBJECTS: dict[str, ModuleType] = {}


def mobject_of(tag: str | None) -> ModuleType | None:
    """The display's ``mobject`` module (imports manimgl), or None for a tag that is no display."""
    d = get(tag)
    if d is None:
        return None
    if d.tag not in _MOBJECTS:
        _MOBJECTS[d.tag] = importlib.import_module(f"{d.package}.mobject")
    return _MOBJECTS[d.tag]


def hook(tag: str | None, name: str) -> Callable | None:
    mod = mobject_of(tag)
    return getattr(mod, name, None) if mod is not None else None


# --- docs ---------------------------------------------------------------------------------------
def _doc(d: Display, name: str) -> str:
    path = HERE / d.package.rsplit(".", 1)[-1] / name
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def agent3_rows() -> str:
    return "\n".join(_doc(d, "agent3.md").split("\n\n", 1)[0] for d in all_displays() if _doc(d, "agent3.md"))


def agent3_sections() -> str:
    parts = [_doc(d, "agent3.md").split("\n\n", 1) for d in all_displays()]
    return "\n\n".join(p[1] for p in parts if len(p) == 2)


_PLAN_MARK = re.compile(r"^\{\{plan_kinds(?::([^}]*))?\}\}$", re.M)
_AGENT3_MARKS = {"{{display_tags}}": agent3_rows, "{{display_sections}}": agent3_sections}


def fill_agent3(text: str) -> str:
    """Fill ``{{display_tags}}`` / ``{{display_sections}}`` in Agent 3's reference."""
    for mark, fn in _AGENT3_MARKS.items():
        text = text.replace(mark, fn())
    return text


def fill_plan(text: str) -> str:
    """Fill ``{{plan_kinds: tex number}}`` with those displays' plan rows (by tag) and a bare
    ``{{plan_kinds}}`` with every display's row not placed yet, so a new display shows up."""
    named = {t for m in _PLAN_MARK.finditer(text) if m.group(1) for t in m.group(1).split()}

    def rows(m: re.Match) -> str:
        chosen = ([get(t) for t in m.group(1).split()] if m.group(1)
                  else [d for d in all_displays() if d.tag not in named])
        missing = [t for t, d in zip((m.group(1) or "").split(), chosen) if d is None]
        if missing:
            raise ValueError(f"plan.md names displays that do not exist: {missing}")
        return "\n".join(r for r in (_doc(d, "plan.md") for d in chosen) if r)
    return _PLAN_MARK.sub(rows, text)


_discover()
