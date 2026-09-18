# Example 05 — Discrete convolution with dice (probability + signals)

> Different video: discrete convolution, not transformers/probability-preview.
> Sources:
> - VO: `3b1b/captions/2023/convolutions2/english/transcript.txt` (quiz: sum of two normals; warmup weighted dice blue/red; `flip second row, slide offsets, pairwise products summed`) + `2022/convolutions` discrete focus (dice grid diagonals, `a1,a2... b1,b2...`, 36 pairs, `convolution = flipped sliding dot-products`)
> - Code: `3b1b/videos/_2023/convolutions2/dice.py:SumAlongDiagonal` + `get_bar_group/dist_to_bars`, `die_sum_labels`, `rotate_sum_label` + `3b1b/videos/_2022/convolutions/discrete.py:get_die_faces/get_aligned_pairs/get_pair_rects/get_row_shift` — `SurroundingRectangle(pair)`, `low_row.animate.shift(x*RIGHT)`, `dist_to_bars + DecimalNumber.next_to(bar, UP)`
> - Prompts: Agent1 CoT -> Agent2 CoT -> Agent3 CoT

## Files

- `agent1-output.json`, `agent2-output.json`, `agent3-S1.py` (dice grid diagonals), `agent3-S2.py` (flip + slide + bars)
