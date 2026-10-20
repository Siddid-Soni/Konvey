| `attention` | which words attend to which: a row of words with the attention pattern under it (queries across the top, keys down the left, a dot per pair sized by its weight), or the sentence with arrows from the attended words into one word | `tokens="a,fluffy,blue,creature"` (2–10 words; `\|` between them if one has a comma), `weights="1,0,0,0;0.4,0.6,0,0;…"` (one group per query word, in token order: that word's weight on every word; `""` in a group not computed yet), `softmax="true"` (weights are normalised: each group sums to 1), `mask="causal"` (a word sees only itself and earlier words), `focus="creature"` (one query word: its column framed, the rest dimmed; arrows go into it), `focus-key="fluffy"` (one key row), `view="grid"` (default) / `"words"` (the sentence with arrows and vectors) / `"both"` (grid with arrows over the words), `numbers="true"` (weights written in the cells instead of dots), `vectors="0.9,-0.4,0.2;…"` (one short column per token, 2–6 numbers, shown in `view="words"`), `qk="true"` (each word's query Q and key K), `size` |

**Telling the attention story** (`<attention>`): keep one id and the same `tokens` for the
whole scene and change only the other attributes, beat by beat. The renderer lays everything out
(never place words or dots yourself) and keeps the words still while the picture changes under
them. Each change plays as the mechanism: `view="words"` → grid: the key labels fly from the words
to the left and the dots grow row by row; raw scores → `softmax="true"`: a frame sweeps the
columns and each column's dots resize to weights; adding `mask="causal"`: the cells of later
words are struck one by one; a new `focus` slides the frame; `view="words"` (or `"both"`) with a
`focus` and its weights grows arrows from the attended words into the focus word (thick = more
weight, the weight beside each arrow when `softmax`); then changing the focus word's `vectors`
sends a value along each arrow into it before its numbers change. Weights are per query word:
group 3 is what word 3 looks at, drawn as column 3. A word's weights after softmax sum to 1, and
with `mask="causal"` the later words get 0. Use `numbers="true"` for the beats where the
narration reads values, dots for the pattern.
