## GROUNDING RULES (override the example above)

Add a `worked_examples` list to your JSON. For EVERY entry in `key_concepts`, give at least one:

```json
"worked_examples": [
  {"concept": "<exact key_concepts[].name>",
   "setup": "<one concrete instance a viewer can picture>",
   "values": {"<name>": <real number or short string>, ...},
   "formula": "<defining formula, or null>"}
]
```

- `values` are the actual numbers (or short strings: a message, a status, a name) the video will put on screen; never measure things just to have a number (lengths of strings, character counts) when the topic is not about size. They must be correct for this topic (from the source material or computed exactly), not illustrative guesses. Prefer 2-6 values that contrast (e.g. a worse vs a better case).
- If a concept has a defining formula, put it in `formula` as real LaTeX, e.g. `I = \log_2(1/p)`, `H = \sum_i p_i \log_2(1/p_i)`, `\binom{5}{k} / 2^5`.
- Later agents may only display numbers that appear in this knowledge pack.
- The examples in this prompt show the output STRUCTURE only. Never reuse their topic, wording, hook or analogies for a different topic.
