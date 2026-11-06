"""Progressive documentation and reference data for the Konvey MCP engine.

The skill carries the workflow and the hard rules. Everything that is only needed while
writing a particular scene is served on demand from here:

- ``guide(section)`` — the Director reference (filled with the live display table), plus
  the MCP workflow / review / checks sections.
- ``display_catalog(tag, kind)`` — every overlay tag with its summary and attributes.
- ``example(name, kind, genre)`` — one worked scene to copy the structure from.
- ``simulate(rule, settings, times)`` — the exact numbers a simulation will play.

The content is read from the repo's prompts and display docs, so it cannot drift from what
the Director actually gets.
"""

from __future__ import annotations

import functools
import re

from ..stage import displays, theme as themes
from ..stage.examples import load_examples
from ..story_sim import RULES, simulate as run_simulation
from .runs import REPO_ROOT

REFERENCE = REPO_ROOT / "prompts" / "agent3-stage" / "reference.md"
DISPLAY_DIR = REPO_ROOT / "konvey" / "stage" / "displays"

ALIASES = {"overlay": "overlay-tags", "world": "world-actors"}


# --- the reference document -----------------------------------------------------------

@functools.lru_cache(maxsize=1)
def _reference() -> str:
    return displays.fill_agent3(REFERENCE.read_text(encoding="utf-8"))


def _slug(title: str) -> str:
    title = re.sub(r"\s*\(.*\)\s*$", "", title)
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


@functools.lru_cache(maxsize=1)
def _sections() -> dict[str, tuple[str, str]]:
    parts = re.split(r"(?m)^## ", _reference())
    out = {}
    for part in parts[1:]:
        title, _, body = part.partition("\n")
        out[_slug(title)] = (title.strip(), body.strip())
    return out


def _slice(text: str, start: str, end: str) -> str:
    i = text.find(start)
    if i < 0:
        return text
    j = text.find(end, i + len(start))
    return text[i:j if j > 0 else len(text)].strip()


# --- authored sections -----------------------------------------------------------------

WORKFLOW = """# Workflow: topic -> silent explainer video

You do the thinking; Konvey does the layout, checks and render. Do not write Python.

1. `konvey_new_run(topic, duration=90)` creates `.konvey/runs/<id>/` with `run.json`,
   `plan.md` (optional) and `S1.html` … `S3.html`. Ask the user for a different duration or
   theme only when it matters; the default is a 90 s, three-scene, silent video.
2. Research the topic with your own tools. Compute every number the viewer will hear or see.
   For a simulation, use `konvey_simulate` so the number is exactly what the engine plays.
3. Write `plan.md`: three acts, 8–12 beats each, one idea per beat, one spoken line per beat
   (`vo`), and one picture that evolves across the scene. Act 1 opens on a concrete case;
   Act 2 takes the idea into the topic; Act 3 pays it off.
4. Fetch only what the current scene needs: `konvey_guide("beats")`, `konvey_guide("shots")`,
   `konvey_displays(kind=…)`, `konvey_example(kind=…)`. Copy an example's structure, never
   its topic, numbers or wording.
5. Write `S1.html` … `S3.html` as `<beats>…</beats>`: one `<beat vo="…">` per line, each a
   full snapshot of the screen at the end of that line. Reuse an element's `id` to change it
   in place; a new `id` enters, a missing `id` exits. Use `shot="…"` so the engine composes
   the screen.
6. `konvey_check(run_id)`: fix every static problem and every runtime problem it names.
   Then `konvey_preview(run_id)`: look at `preview/sheet.png` and the per-beat stills.
7. Compare every still with its `vo` line. If the picture does not show what the line says,
   or the eye has no single place to go, fix that beat and repeat check -> preview. Do not
   render until the sheet tells the story on its own.
8. `konvey_render(run_id)`: render in the background, poll `konvey_status(run_id)`, then give
   the user `<run>/video.mp4` (and the sheet if they want to review it first).

Hard rules:
- Every beat has a non-empty `vo`. Aim for 20 words or fewer.
- 8–12 beats per scene, 3 scenes. One dominant picture, not a wall of cards.
- Compute or simulate every number. Never invent one.
- Colours are theme roles (`ink`, `muted`, `accent`, `c1`…`c5`), never hex.
- Silent v1: no subtitles; the `vo` is for timing and future narration.
- The beat HTML is data, not code. Do not write Python or shell into the scene files.
"""

REVIEW = """# Reviewing the preview

`konvey_preview` plays every scene with the engine's own layout and animations, saves the
frame at the end of each beat, and writes `preview/sheet.png` plus `preview/index.json`.

1. Open the sheet first. It should read as a storyboard: each tile is a different state of the
   same picture, and the VO under each tile should be answered by what is on screen.
2. Open an individual `S1-beat-03.png` when a tile is hard to judge. Check: is the thing the
   line names the largest, brightest thing? Is anything overlapping, clipped, or too small to
   read? Is there one focal point?
3. Fix the named beat in the HTML. Change one thing at a time; keep the `id` so the engine
   morphs in place instead of cutting.
4. Re-run `konvey_check` (static first; runtime when the change is structural) and then
   `konvey_preview`. Do not re-render the video for every small fix.
5. Render only when the sheet makes sense without the voice. A good video needs no subtitle.

The preview is the same scene code the video uses, so a still that looks wrong will look
wrong in the render. Do not assume the render will fix it.
"""

CHECKS = """# Checks and how to fix them

`konvey_check` runs three layers:

**Static** (`check_static`): the beats parse; every leaf has an id; font sizes are above the
display's floor; colours are theme names, not hex; letterbox opens only at the start of S1
and closes only at the end of S3; points that belong on a plot are drawn on the plot; each
display's own scene rules pass.

**MCP rules**: every beat has a non-empty `vo`; a scene has 3–15 beats; the estimated
duration is near the run's target; no `TODO`/`FIXME` placeholders; every scene file exists.

**Runtime** (`check_runtime`): Chromium lays the scene out, manimgl plays it with animations
skipped, and the frame audit measures what the viewer sees. It catches overflow, elements
that cannot shrink, LaTeX errors, bad attributes, a world body over a label, too many text
items, and a note whose arrow reaches nothing.

Common fixes:
- Something sticks out -> show less, use a smaller picture, or put it in its own beat.
- Text too small -> cut words or move the detail to another beat; never shrink below the
  display's minimum.
- Two things overlap -> give the beat a `shot`, or split the screen with `row`/`col` and
  `grow`; do not hand-place absolute coordinates.
- A world body covers a label -> move the label or use `camera focus` on the 3D box.
- The beat is crowded -> one picture per beat; carry the rest to the next line.
- A simulation number is wrong -> use `konvey_simulate` with the same rule/settings and copy
  its values; the engine will play exactly those.
"""

THEMES = """# Themes and colours

Available themes: {themes}. The run's theme and highlight are chosen in `konvey_new_run` and
recorded in `run.json`; `konvey_render` uses them.

Colour roles: `ink` (text), `muted` (secondary), `accent` (the one thing to look at),
`c1`…`c5` (series and multiple objects, in order), `dark` (a near-black shape). Never write a
hex colour; the engine rejects it in the checks. A highlight (`highlight`, `mark`, a `path`)
lights the shape's own outline in the run's highlight colour; `lit-color="c2"` on a display
uses a different outline only when two highlighted things must be told apart.

The background, fonts and palettes come from the theme. Do not try to set them per beat.
"""


def _sims_section() -> str:
    doc = run_simulation.__doc__ or ""
    sim_doc = _display_doc("sim")
    return ("# Simulations\n\n"
            "The engine's `<sim>` runs exact, seeded models. Use `konvey_simulate` for every\n"
            "number the narration or the picture reads off a simulation; do not compute it\n"
            "another way. `simview` shows another view of the same run (its phase plane or its\n"
            "numbers over time).\n\n"
            f"Rules: {', '.join(RULES)}\n\n"
            f"```text\n{doc.strip()}\n```\n\n"
            + (f"## `<sim>`\n\n{sim_doc}\n" if sim_doc else ""))


def _marks_section() -> str:
    tags = ("dots", "path", "arc", "angle", "brace", "note", "ring", "arrow")
    rows = []
    for tag in tags:
        d = displays.get(tag)
        if d is None:
            continue
        summary, attrs = _row(_display_doc(tag))
        rows.append(f"- **`{tag}`** — {summary}\n  Attributes: {attrs}")
    return ("# Marks on a picture\n\n"
            "Marks sit on the thing they mark (`on=`, `of=`, `to=`) and take no room in the\n"
            "layout. Use them instead of drawing arrows or labels yourself.\n\n"
            + "\n".join(rows))


def _beats_section() -> str:
    sections = _sections()
    return ("# Beats and the scene model\n\n"
            + sections.get("how-it-works", ("", ""))[1]
            + "\n\n" + sections.get("rules", ("", ""))[1])


def guide(section: str | None = None) -> str:
    """Return the guide index, or one section of it."""
    sections = _sections()
    authored = {
        "workflow": ("Workflow", WORKFLOW),
        "review": ("Preview review", REVIEW),
        "checks": ("Checks", CHECKS),
        "themes": ("Themes", THEMES.format(themes=", ".join(themes.THEMES))),
        "sims": ("Simulations", _sims_section()),
        "marks": ("Marks", _marks_section()),
        "beats": ("Beats", _beats_section()),
        "displays": ("Displays", sections.get("overlay-tags", ("", ""))[1]),
    }
    engine = {name: (title, body) for name, (title, body) in sections.items()}
    if "the-stage" in engine:
        stage = engine["the-stage"][1]
        engine["shots"] = ("Shots", _slice(stage, "**Shots:", "**The 2D camera**"))
        engine["camera"] = ("The 2D camera", _slice(stage, "**The 2D camera**", "**Parts**"))
        engine["parts"] = ("Parts", _slice(stage, "**Parts**", "**An equation built"))
    all_sections = {**authored, **engine}
    if "overlay-tags" in engine:
        all_sections["overlay"] = engine["overlay-tags"]
    if "world-actors" in engine:
        all_sections["world"] = engine["world-actors"]

    if section is None:
        lines = ["# Konvey guide", "",
                 "Fetch one section when you need it; the skill carries the workflow and the hard rules.", ""]
        for name, (title, body) in all_sections.items():
            if name in {"overlay-tags", "world-actors"}:
                continue
            first = next((line.strip(" #") for line in body.splitlines() if line.strip()), "")
            short = re.sub(r"\s*\(.*\)\s*$", "", title)
            if not first.lower().startswith(short.lower()):
                first = f"{short}: {first}"
            lines.append(f"- **`{name}`** — {first[:140]}")
        lines += ["", "Use `konvey_guide(\"all\")` for the whole Director reference."]
        return "\n".join(lines)

    key = _slug(section)
    key = ALIASES.get(key, key)
    if key == "all":
        return "\n\n".join([WORKFLOW, REVIEW, CHECKS, _reference()])
    if key not in all_sections:
        return (f"ERROR: unknown guide section {section!r}. Available: "
                + ", ".join(sorted(all_sections)))
    title, body = all_sections[key]
    body = re.sub(r"^#\s+[^\n]*\n+", "", body).strip() if body.startswith("#") else body
    return f"# {title}\n\n{body}"


# --- displays --------------------------------------------------------------------------

def _display_doc(tag: str) -> str:
    d = displays.get(tag)
    if d is None:
        return ""
    path = DISPLAY_DIR / d.package.rsplit(".", 1)[-1] / "agent3.md"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _row(doc: str) -> tuple[str, str]:
    """Summary and attributes from the first (table-row) line of an ``agent3.md``."""
    if not doc:
        return "", ""
    row = doc.splitlines()[0].strip()
    cells = [c.strip() for c in re.split(r"(?<!\\)\|", row.strip("|"))]
    summary = cells[1] if len(cells) > 1 else ""
    attrs = cells[2] if len(cells) > 2 else ""
    return summary, attrs


@functools.lru_cache(maxsize=1)
def _examples():
    return tuple(load_examples())


def _example_names(kind: str | None) -> list[str]:
    if not kind:
        return []
    return [ex.name for ex in _examples() if kind in ex.kinds][:3]


def _compact(d) -> dict:
    summary, _ = _row(_display_doc(d.tag))
    if len(summary) > 180:
        summary = summary[:177].rstrip() + "…"
    return {
        "tag": d.tag,
        "kind": d.kind,
        "summary": summary,
        "min_size": d.min_size,
        "aliases": list(d.aliases),
        "examples": _example_names(d.kind or d.tag),
    }


def display_catalog(tag: str | None = None, kind: str | None = None) -> dict:
    """A compact catalog, one display's full docs, or every display of a plan kind."""
    if tag:
        d = displays.get(tag)
        if d is None:
            raise ValueError(f"unknown display {tag!r}; tags: "
                             + ", ".join(sorted(x.tag for x in displays.all_displays())))
        doc = _display_doc(d.tag)
        summary, attrs = _row(doc)
        return {"ok": True, "display": {
            "tag": d.tag, "kind": d.kind, "summary": summary, "attributes": attrs,
            "min_size": d.min_size, "aliases": list(d.aliases),
            "children": sorted(d.children), "plan_needs": list(d.needs),
            "examples": _example_names(d.kind or d.tag), "docs": doc,
        }}
    if kind:
        found = [d for d in displays.all_displays()
                 if d.kind == kind or kind in d.aliases or d.tag == kind]
        if not found:
            raise ValueError(f"no display draws plan kind {kind!r}")
        return {"ok": True, "kind": kind, "displays": [_compact(d) for d in found]}
    return {"ok": True, "count": len(displays.all_displays()),
            "displays": [_compact(d) for d in displays.all_displays()]}


# --- examples --------------------------------------------------------------------------

def example(name: str | None = None, kind: str | None = None,
            genre: str | None = None) -> dict:
    """The example index, or one worked scene from the Director's examples."""
    examples = list(_examples())
    if name is None and kind is None and genre is None:
        return {"ok": True, "count": len(examples), "examples": [
            {"name": ex.name, "genre": ex.genre, "kinds": sorted(ex.kinds),
             "fits": list(ex.fits)}
            for ex in examples
        ]}
    if name:
        wanted = name[:-3] if name.endswith(".md") else name
        matches = [ex for ex in examples if ex.name == wanted]
    else:
        matches = [ex for ex in examples
                   if (kind is None or kind in ex.kinds)
                   and (genre is None or ex.genre.lower() == genre.lower())]
    if not matches:
        return {"ok": False, "error": "no matching example",
                "available": [ex.name for ex in examples]}
    chosen = matches[0]
    return {
        "ok": True,
        "name": chosen.name, "genre": chosen.genre, "kinds": sorted(chosen.kinds),
        "body": chosen.body,
        "note": "Copy the structure and the display choices, never the topic, numbers or wording.",
        "alternatives": [ex.name for ex in matches[1:]],
    }


# --- simulations ------------------------------------------------------------------------

def simulate(rule: str | None = None, settings: str = "{}", times: str = "end") -> str:
    """The simulation rules and their settings, or one run's exact values."""
    if not rule:
        doc = run_simulation.__doc__ or ""
        return ("Simulation rules: " + ", ".join(RULES) + "\n\n" + doc.strip())
    return run_simulation(rule, settings, times)
