# Konvey — 3-Agent Explainer-Video Pipeline (manimgl / 3b1b style)

Generate 3Blue1Brown-style explainer videos from a text prompt with three agents:
**Knowledge Discovery → Planning + Scene Generation → Manim Coding.**

```text
USER_PROMPT
    │  prompts/sets/<set>/agent1.md  (or prompts/agent1-knowledge-discovery/)
    ▼
KNOWLEDGE_PACK (JSON: topic, core_claim, key_concepts, mechanism_steps,
                misconceptions, analogies, narration_beats, triples)
    │  prompts/sets/<set>/agent2.md  (decides layout + animation)
    ▼
SCENE PLAN (JSON: 3 scenes S1->S2->S3, beats with vo_line, objects,
            layout[], spatial_predicates, animation{code_hint, run_time})
    │  split S1, S2, S3 ──► prompts/sets/<set>/agent3.md x3 in parallel
    ▼
manimgl code (SingleScene.construct per scene) ──► manimgl file.py SingleScene
```

## 1. Agents

| # | Agent | In → Out | Decides | Must not do |
|---|-------|----------|---------|-------------|
| 1 | Knowledge Discovery | `USER_PROMPT → KNOWLEDGE_PACK.json` | claims, steps, analogies, triples (`is-a/part-of/causes/stores/transforms/contrasts-with/example-of`) | visuals, code |
| 2 | Planning + Scene Generation | `KNOWLEDGE_PACK → 3-scene plan` | VO script, objects (verbatim reuse), `layout[]`, `spatial_predicates` (above/below/at left of/at right of/on top of), `animation` (from `manim-reference/animations.md`) | write full python |
| 3 | Manim Coding | `SCENE_SPEC (1 scene) → .py` | implements beats verbatim: `from manim_imports_ext import *`, `InteractiveScene.construct`, `# VO:` comments, `self.wait()` per beat | re-plan animation, new assets |

## 2. Run order

```text
1. Pick a set closest to your video (see §4) or generic prompts/ (few-shot default, CoT on failure, zero-shot baseline).
2. Agent1 → validate JSON (strict parse, allowed relations only).
3. Agent2 → check: 3 scenes, precedes S1->S2->S3, durations sum to target, every predicate compiles to a layout op.
4. Split S1/S2/S3 → Agent3 x3 in parallel → py_compile + forbid ImageMobject/external/torch.
5. Render: manimgl agent3-S1.py SingleScene  (repeat S2, S3).
```

Minimal commands:

```bash
# validate outputs
python3 -c "import json,glob; [json.load(open(f)) for f in glob.glob('examples/*/agent*.json')]; print('JSON OK')"
python3 -m py_compile examples/<example>/agent3-*.py
# render one scene (requires manimgl + repo on path)
manimgl examples/example-01-mlp-facts/agent3-S1.py SingleScene
```

## 3. Prompt library

Generic (style-first) prompts:

```text
prompts/agent1-knowledge-discovery/{zero-shot,few-shot,cot}.md
prompts/agent2-planning-scene-generation/{zero-shot,few-shot,cot}.md
prompts/agent3-manim-coding/{zero-shot,few-shot,cot}.md
```

Per-video sets — each set = 3 prompts for the SAME video (preferred entry point):

```text
prompts/sets/set-01-mlp-facts/{agent1,agent2,agent3}.md          # ML mechanism (Jordan puzzle + mlp.py)
prompts/sets/set-02-clt-galton-board/{agent1,agent2,agent3}.md   # probability (Galton board + galton_board.py)
prompts/sets/set-03-shadows-cube/{agent1,agent2,agent3}.md       # geometry (Alice-vs-Bob cube + shadows.py)
```

Animation/layout authority:

```text
manim-reference/animations.md      # from manimlib/animation/*.py (docs site is thin)
manim-reference/spatial-layout.md  # paper predicates → next_to/to_edge/arrange/target
```

## 4. Which set to pick

| Target video about… | Use set | Why |
|---|---|---|
| ML mechanism / transformer internals | set-01-mlp-facts | hook puzzle → intuition → late term; block split + collapse idioms |
| Probability experiment / distributions | set-02-clt-galton-board | chaotic-one / precise-many; pegs + ±1 arrows + histogram idioms |
| Geometry / 3D projection / optimization | set-03-shadows-cube | special-cases → general law; plane/cube/shadow-updater idioms |

## 5. Layout check (executed, not just parsed)

`ast.parse` only proves Agent 3 wrote Python. Overlaps happen on screen, so after each scene is coded the pipeline **executes it** with manimgl (animations skipped, no video, ~0.3 s/scene) and measures every visible object in screen space at each `self.wait()` beat:

| kind | severity | meaning |
|---|---|---|
| `text_overlap` | error | two text objects overlap (sibling pile-ups collapse into one finding: "did you forget `arrange()`?") |
| `text_on_drawing` | error | a label is drawn over lines/curves/shapes of another object |
| `off_frame` | error | something leaves `x ∈ [-6.96, 6.96]`, `y ∈ [-3.85, 3.85]` |
| `runtime_error` | error | the scene crashes (bad name/kwarg, `MoveToTarget` without target, …) |
| `shape_overlap` / `tiny_text` / `clutter` | warning | partial shape overlap, text < ~font_size 22, > 9 objects at once |

Failures go back to Agent 3 with the spec, its code and the measured report (object names, line, VO beat, coordinates), for up to `--layout-repairs` rounds (default 2). The best candidate is kept, so a repair never makes the scene worse; anything left lands in `out/.../layout-report.json`.

```bash
uv sync --extra layout                                   # manimgl for the check
uv run python -m konvey.layout_probe out/konvey-run/agent3-S*.py   # check any scene file
uv run run_konvey.py --dry-run-example examples/example-05-discrete-convolution-dice  # check an example
uv run run_konvey.py --prompt "..." --layout-repairs 3   # live run; --no-layout-check to disable
```

Prevention lives in `manim-reference/spatial-layout.md` (fed to Agents 2 and 3): five screen regions with a `place(mob, region)` fit-to-box helper instead of long `next_to` chains, per-beat `FadeOut` of anything the VO no longer mentions, and one identifier per object across `objects` / `spatial_predicates` / `layout[]` (mismatches are logged as `plan warning:`).

## 6. Worked examples (trace Agent1 → Agent2 → Agent3)

```text
examples/example-01-mlp-facts/                 # full S1+S2+S3 code
examples/example-02-attention-adjectives/      # adjectives→nouns arrows + ContextAnimation
examples/example-03-elara-paper-adaptation/    # arXiv:2509.04481 story → explainer mapping
examples/example-04-clt-galton-board/          # board setup + many-ball histogram
examples/example-05-discrete-convolution-dice/ # 36-grid diagonals + flip/slide + bars
examples/example-06-shadows-cube-average/      # flat projection + square→hexagon
```

Each example has `agent1-output.json`, `agent2-output.json`, `agent3-S*.py`, `README.md` with sources.

## 7. Adding a new video

1. Add transcript excerpt + code idiom to `examples/example-0N-<name>/` (copy an existing example's file names).
2. Copy nearest set in `prompts/sets/` to `set-0N-<name>/`, swap the EXAMPLE block to your transcript/code, keep schemas identical.
3. Validate JSON + py_compile, commit.

## 8. Sources

- Captions: `https://github.com/3b1b/captions` (`2024/mlp`, `2024/attention`, `2023/clt`, `2023/convolutions2`, `2021/shadows`)
- Code: `https://github.com/3b1b/videos` (`_2024/transformers/mlp.py`, `attention.py`, `_2023/clt/galton_board.py`, `_2023/convolutions2/dice.py` + `_2022/convolutions/discrete.py`, `_2021/shadows.py`)
- Pipeline shape: `https://arxiv.org/abs/2509.04481` (Prompt_1/Prompt_2, triples, Alg 1/2/3, precedes KG)
- Manim API: `https://3b1b.github.io/manim/` + `https://github.com/3b1b/manim` (`manimlib/animation`, `manimlib/mobject/mobject.py`)
