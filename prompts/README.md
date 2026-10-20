# Konvey — Prompt Library

- **Agent 1 — Knowledge Discovery:** `USER_PROMPT -> KNOWLEDGE_PACK (JSON)`
- **Agent 2 — Planning:** `KNOWLEDGE_PACK -> 3-scene plan (beats with the objects and data they show)`
- **Agent 3 — Stage Director:** `SCENE_SPEC (1 scene) -> <beats> HTML` for `konvey.stage`

## Layout

```text
prompts/agent1-knowledge-discovery/{zero-shot,few-shot,cot}.md  # few-shot default, CoT on repair
prompts/shared/agent1-grounding.md     # worked examples, real values (dropped by --no-grounding)
prompts/shared/agent1-stage.md         # what the stage can draw: what data to gather
prompts/agent2-stage/plan.md           # topic-free planner; {{plan_kinds}} filled from each display
prompts/agent2-stage/plan-narration.md # narration-mode planner (spikes/speech)
prompts/agent3-stage/reference.md      # tag reference; {{display_tags}} filled from each display
prompts/agent3-stage/examples/*.md     # worked scenes by genre, picked per scene (konvey.stage.examples)
prompts/lean/{researcher,solo}.md      # fewer-agent variants (run_konvey_lean.py)
```

## Run order

```text
Agent1 (few-shot, CoT on failure) -> validate JSON -> Agent2 -> validate plan -> split S1,S2,S3
    -> Agent3 x3 in parallel -> check beats (static, then laid out + played headless) -> render
```
