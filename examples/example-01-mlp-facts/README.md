# Example 01 — MLP facts (Where do facts live?)

> Sources:
> - VO style: `3b1b/captions/2024/mlp/english/transcript.txt` + `captions.srt` (`Michael Jordan plays sport of ___ -> basketball`)
> - Code idioms: `3b1b/videos/_2024/transformers/mlp.py:LastTwoChapters` (2627 lines; thumbnails `LaggedStartMap(FadeIn)`, `blocks.arrange(OUT)`, `frame.animate.reorient`, `SurroundingRectangle + Write(question) + GrowArrow`)
> - Prompts used: Agent1 few-shot -> Agent2 few-shot -> Agent3 few-shot

## Files

- `agent1-output.json` — KNOWLEDGE_PACK
- `agent2-output.json` — 3-scene plan with beats (layout + animation decided)
- `agent3-S1.py`, `agent3-S2.py`, `agent3-S3.py` — runnable manimgl per scene

## How to run

```bash
manimgl agent3-S1.py SingleScene
manimgl agent3-S2.py SingleScene
manimgl agent3-S3.py SingleScene
```
