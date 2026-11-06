# Konvey — 3-Agent Explainer-Video Pipeline (3b1b style)

Generate 3Blue1Brown-style explainer videos from a text prompt with three agents:
**Knowledge Discovery → Planning → Stage Director.** Agent 3 writes beat HTML; `konvey.stage`
lays it out with Chromium and draws and animates it with manimgl.

```text
USER_PROMPT
    │  prompts/agent1-knowledge-discovery/ + prompts/shared/agent1-*.md  (calc / run_python tools)
    ▼
KNOWLEDGE_PACK (JSON: topic, core_claim, key_concepts, mechanism_steps, worked_examples,
                walkthrough, triples)
    │  prompts/agent2-stage/plan.md
    ▼
SCENE PLAN (JSON: 3 scenes S1->S2->S3, beats with vo_line, teaches, walkthrough_step,
            objects {id, kind, data, source})
    │  split S1, S2, S3 ──► prompts/agent3-stage/reference.md (+ worked examples per scene) x3
    ▼
beat HTML per scene ──► konvey.stage (Chromium layout → manimgl) ──► video.mp4
```

Working on the code (or an agent doing so)? Start with [AGENTS.md](AGENTS.md): setup, commands, and
what lives where.

## Use from a coding harness (MCP)

Konvey also runs as an MCP server plus an Agent Skill for Claude Code, opencode and Cursor.
The harness model researches the topic, writes the script and beats; Konvey supplies the
reference, checks, preview stills and render. v1 is silent.

```bash
uv sync --group mcp --group render --group layout
uv run --group mcp --group render --group layout konvey-mcp --help
```

See [docs/konvey-mcp.md](docs/konvey-mcp.md) for the server config, the skill install, and the
tool reference.

## 1. Agents

| # | Agent | In → Out | Decides | Must not do |
|---|-------|----------|---------|-------------|
| 1 | Knowledge Discovery | `USER_PROMPT → KNOWLEDGE_PACK.json` | claims, steps, worked examples with real values (computed by tool calls), one walkthrough step by step, triples (`is-a/part-of/causes/stores/transforms/contrasts-with/example-of`) | visuals, code |
| 2 | Planning | `KNOWLEDGE_PACK → 3-scene plan` | VO script, objects with the data they show, which concept each beat teaches, one beat per walkthrough step | layout, animation, code |
| 3 | Stage Director | `SCENE_SPEC (1 scene) → <beats>` HTML | which displays show each beat and how they change (`konvey/stage/displays/`) | re-plan, invent data |

## 2. Run order

```text
1. Agent 1 → validate JSON (strict parse, allowed relations, worked examples, walkthrough).
2. Agent 2 → check: 3 scenes, precedes S1->S2->S3, durations sum to target, grounding
   (numbers from the knowledge pack, every concept taught, walkthrough shown in order).
3. Split S1/S2/S3 → Agent 3 x3 in parallel → static check of the beats, then (with manimgl +
   Chromium) laid out and played headless, each scene continuing from the one before.
4. --render: each scene rendered with manimgl and joined into <out-dir>/video.mp4.
```

Rejections are fed back for `--repair-rounds` (default 2, CoT after the first); still-failing
scenes are kept with `agent3-Sx.problems.txt`; all feedback goes to `repair-log.txt`; every
model request's tokens and price go to `cost.json`.

Put credentials in `.env`:

```bash
# OpenCode (used automatically when OPENCODE_API_KEY is set) — key from https://opencode.ai/auth
OPENCODE_API_KEY="..."
KONVEY_PROVIDER=opencode-go                   # or opencode (Zen), or minimax
OPENCODE_MODEL_ID=muse-spark-1.3-contributor  # Go default; Zen default glm-5.3
# also works: gemini-* or any /chat/completions model (glm-*, kimi-*, deepseek-*, qwen3.8-max, minimax-m3 on Zen)
```

```bash
uv run --group render --group layout run_konvey.py --prompt "Where do facts live in an LLM?" \
    --render --out-dir out/facts
uv run --group render --group layout run_konvey.py --prompt "..." --provider opencode-go --model-id kimi-k3
uv run --group render --group layout scripts/topics.py           # every topic in topics.toml
uv run --group render python -m konvey.render out/facts           # re-render existing beats
```

Flags: `--theme` (editorial, classic), `--no-grounding`, `--no-probe`, `--mode`, `--duration`.

`muse-spark-1.3-contributor` (and `gemini-4-argon-contributor`) are "contributor" models: Meta / Google may train on your prompts and completions. Supported OpenCode wire formats: `/chat/completions`, `/responses` (muse-*, gpt-*, grok-*) and Google (gemini-*); Claude models use `/messages`, which this adapter can't call. MiniMax direct still works: set `MINIMAX_API_KEY` and `KONVEY_MODEL_ID`.

Experimental fewer-agent variants (Researcher → 3 directors, or one Solo call):
`run_konvey_lean.py --agents {1,2}` (`konvey/lean.py`, `prompts/lean/`).

## 3. Prompt library

See `prompts/README.md`.

## 4. Sources

- Captions: `https://github.com/3b1b/captions`
- Code: `https://github.com/3b1b/videos` (how a 3b1b visual is built)
- Pipeline shape: `https://arxiv.org/abs/2509.04481` (Prompt_1/Prompt_2, triples, Alg 1/2/3, precedes KG)
- Manim API: `https://3b1b.github.io/manim/` + `https://github.com/3b1b/manim`
