"""Agent 3 genre examples (spec §4.4) and the never-the-same-topic rule (§2.4)."""

import importlib.util
import re
from pathlib import Path

import pytest

from konvey.schemas import Scene
from konvey.stage.check import check_runtime
from konvey.stage.examples import (EXAMPLES_DIR, examples_block, load_examples, mentions, overlaps,
                                   select)

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

REPO = Path(__file__).resolve().parent.parent
HAS_MANIM = importlib.util.find_spec("manimlib") is not None
HAS_CHROMIUM = importlib.util.find_spec("playwright") is not None and Path("/usr/bin/chromium").exists()
TOPICS = tomllib.loads((REPO / "topics.toml").read_text())["topic"]
# Shipped prompt sets and earlier eval topics: examples must not be about these either.
EARLIER = ["neural network", "perceptron", "multilayer", "central limit", "galton", "wordle",
           "bayes", "medical test", "gradient descent", "convolution", "dice", "cube"]


def scene(*kinds: str) -> Scene:
    return Scene.model_validate({
        "id": "S1", "purpose": "hook", "duration_sec": 10, "vo_script": ["x."],
        "beats": [{"vo_line": "x.", "objects": [{"id": f"o{i}", "kind": k, "data": {}} for i, k in enumerate(kinds)],
                   "animation": {"type": "FadeIn", "code_hint": "", "run_time": 1}}]})


def test_library_genres_have_front_matter():
    ex = load_examples()
    assert sorted({e.genre for e in ex}) == ["cells", "chart", "clustering", "collection", "constructions", "diagram", "drawing-memory",
                                             "drawing-queue", "drawing-stack", "drawing-timeline", "equation",
                                             "linear-maps", "named-grid", "network", "number-lines", "places", "places-jump", "plot", "shots",
                                             "simulation", "vector", "vectors3d", "world3d", "world3d-cut",
                                             "world3d-flow", "world3d-hull", "world3d-waves"]
    assert all(e.kinds and e.topic_keywords and "```html" in e.body for e in ex)


def test_selector_scores_genres_by_planned_kinds():
    pick = lambda *k: [e.genre for e in select(scene(*k), "")]  # noqa: E731
    assert pick("solid", "tex")[0] == "world3d"
    assert pick("chart") == ["chart"]
    assert pick("array", "tex") == ["cells", "equation"]
    assert pick("text") == ["diagram"]
    assert pick() == ["diagram"]                      # nothing to score: fallback genre
    assert len(select(scene("solid", "chart", "array", "tex"), "")) == 2


def test_guard_drops_same_topic_examples_and_falls_back():
    ex = select(scene("chart"), "Why does my coffee cool slower over time?")
    assert all(e.genre != "chart" for e in ex)        # the chart example is about cooling coffee
    assert ex                                         # ... so the next-closest genre is used
    assert mentions("Two cones and a cylinder", "cone") and not mentions("scones", "cone")
    assert mentions("an odd number of ones", "odd numbers")


def test_fits_words_pick_the_drawing_that_suits_the_request():
    """All drawing examples share one kind; the request's domain words choose between them,
    and they never lift an example whose kinds the scene does not plan."""
    pick = lambda ctx, *k: [e.name for e in select(scene(*k), ctx)]  # noqa: E731
    api = "Explain how a web API works: a client sends an HTTP request to a server's endpoint."
    assert pick(api, "places")[0] == "places"
    assert pick("Money moves between three bank accounts", "places")[0] == "places-jump"
    assert pick("How an operating system scheduler shares one CPU between processes over time",
                "drawing")[0] == "drawing-timeline"
    assert pick("Threads hand jobs to workers through a queue", "drawing")[0] == "drawing-queue"
    assert pick("How the memory unit turns an address into a physical location", "drawing")[0] == "drawing-memory"
    assert len(pick("Threads hand jobs to workers through a queue at a fixed time", "drawing")) == 2   # two drawing genres
    assert pick(api, "chart") == ["chart"]                    # fits alone never outranks kinds


def test_guard_falls_back_within_the_genre_first():
    """Dropping one 3D example for its topic still leaves a 3D example."""
    picked = select(scene("solid"), "the shadow cone of a planet")
    assert picked[0].genre == "world3d" and picked[0].name == "world3d-box"


def test_guard_never_sees_nothing_but_overlaps(monkeypatch):
    lines = []
    assert select(scene("chart"), "coffee cone cylinder cuboid caesar odd number largest number "
                                  "bfs tip to tail lifo wedge frustum cache miss bounded buffer round robin "
                                  "page table edge detector k-means eigenvector sales tax drug dose pronoun king minus man bucket sort club vote "
                                  "dye wind pond runner ladder celsius",
                  log=lines.append) == []
    assert any("reference only" in m for m in lines)


@pytest.mark.parametrize("topic", TOPICS, ids=[t["id"] for t in TOPICS])
def test_test_set_prompts_get_examples_off_their_topic(topic):
    kinds = {"T1": ("array", "tex"), "T2": ("grid", "tex"), "T3": ("chart", "tex"),
             "T4": ("solid", "field"), "T5": ("solid", "tex"), "T6": ("array", "tex"),
             "T7": ("solid", "line", "angle"), "T8": ("grid", "bars"), "T9": ("chart", "tex"),
             "T10": ("text", "tex"), "T11": ("solid", "tex"), "T12": ("graph", "text"),
             "T13": ("solid", "chart"), "T14": ("grid", "bars"), "T15": ("solid", "line"),
             "T16": ("array", "tex"), "T17": ("solid", "angle"), "T18": ("bars", "chart"),
             "T19": ("array", "graph"), "T20": ("axes", "line"), "T21": ("array", "tex"),
             "T22": ("solid", "tex"), "T23": ("chart", "tex"), "T24": ("drawing", "tex"),
             "T25": ("solid", "tex"), "T26": ("drawing", "number")}[topic["id"]]
    picked = select(scene(*kinds), topic["prompt"])
    assert picked
    for e in picked:
        assert not overlaps(e, topic["prompt"])
        assert not [k for k in topic["keywords"] if mentions(e.body, k)]


def test_no_example_mentions_a_test_or_earlier_topic():
    for path in EXAMPLES_DIR.glob("*.md"):
        text = path.read_text()
        for k in [kw for t in TOPICS for kw in t["keywords"]] + EARLIER:
            assert not mentions(text, k), f"{path.name} mentions {k!r}"


def test_no_code_or_stage_prompt_names_a_test_topic():
    """Anti-overfit (spec §4.6): fixes must be general, never about one test topic."""
    vendor = REPO / "konvey" / "speech" / "vendor"   # third-party code copied as is
    files = [*(p for p in (REPO / "konvey").rglob("*.py") if vendor not in p.parents),
             *(REPO / "prompts" / "agent3-stage").rglob("*.md"),
             *(REPO / "konvey" / "stage" / "displays").rglob("*.md"),
             *(REPO / "prompts" / "shared").glob("*-stage.md")]
    for path in files:
        text = path.read_text()
        for k in (kw for t in TOPICS for kw in t["keywords"]):
            assert not mentions(text, k), f"{path.relative_to(REPO)} names test topic keyword {k!r}"


def test_examples_block_header():
    assert examples_block([]) == ""
    assert examples_block(load_examples()[:1]).startswith("## Examples (different topics")


@pytest.mark.skipif(not (HAS_MANIM and HAS_CHROMIUM), reason="needs manimgl + Chromium")
@pytest.mark.parametrize("example", load_examples(), ids=lambda e: e.name)
def test_every_example_passes_the_runtime_check(example, tmp_path):
    (html,) = re.findall(r"```html\n(.*?)```", example.body, re.S)
    assert check_runtime(html, tmp_path, "S2") == []


def test_run_staging_sends_examples_before_the_scene():
    from konvey.pipeline import run_staging

    seen = []

    class Agent:
        def run(self, prompt):
            seen.append(prompt)
            return type("R", (), {"content": '<beats><beat vo="x."><h2 id="t">T</h2></beat></beats>'})()

    block = examples_block(select(scene("chart"), "anything"))
    run_staging(scene("chart"), Agent(), examples=block)
    assert seen[0].index("## Examples (different topics") < seen[0].index("Input SCENE_SPEC")
