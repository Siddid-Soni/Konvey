# Example 04 — CLT Galton Board (probability)

> Different video from transformers examples: probability, not ML.
> Sources:
> - VO: `3b1b/captions/2023/clt/english/transcript.txt` — opens `This is a Galton board... chaotic single event, precise distribution of many events... normal/bell/Gaussian... crown jewel central limit theorem... idealized 50-50 ±1 hops, 5 rows, sum = position... ghosts assumption... Pascal's triangle...`
> - Code: `3b1b/videos/_2023/clt/galton_board.py:GaltonBoard` — `get_pegs/get_buckets`, `LaggedStartMap(Write, buckets/pegs)`, `drop_n_balls(25)`, `random_trajectory + falling_anim + pm_arrows (±1)`, `show_corner_sum`, `Integer(s, include_sign=True).next_to(bucket, DOWN)`, `FadeOut(balls, lag_ratio=0.05)`
> - Prompts: Agent1 few-shot -> Agent2 few-shot -> Agent3 few-shot

## Files

- `agent1-output.json`, `agent2-output.json`, `agent3-S1.py` (board setup + single-ball ±1 walk), `agent3-S2.py` (many-ball histogram -> bell)
