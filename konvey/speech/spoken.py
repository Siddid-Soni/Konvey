"""Narration text as a voice reads it: numbers, fractions and symbols spelled out.

The caption keeps "6/9"; the TTS gets "six ninths". Bracketed stage directions pass through.
"""

from __future__ import annotations

import re

ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
        "fifteen sixteen seventeen eighteen nineteen").split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
SCALES = [(10**9, "billion"), (10**6, "million"), (1000, "thousand"), (100, "hundred")]
ORD = {"one": "first", "two": "second", "three": "third", "five": "fifth", "eight": "eighth",
       "nine": "ninth", "twelve": "twelfth"}
DENOM = {2: ("half", "halves"), 4: ("quarter", "quarters")}


def words(n: int) -> str:
    if n < 0:
        return "minus " + words(-n)
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else "-" + ONES[n % 10])
    for size, name in SCALES:
        if n >= size:
            head, rest = divmod(n, size)
            tail = "" if rest == 0 else " " + words(rest)
            return f"{words(head)} {name}{tail}"
    return str(n)


def ordinal(n: int) -> str:
    w = words(n)
    last = re.split(r"([ -])", w)
    end = last[-1]
    if end in ORD:
        last[-1] = ORD[end]
    elif end.endswith("y"):
        last[-1] = end[:-1] + "ieth"
    else:
        last[-1] = end + "th"
    return "".join(last)


def short(n: int) -> str:
    """How people say a three-digit number in a ratio: 364 -> "three sixty-four", 305 -> "three oh five"."""
    if 100 <= n <= 999 and n % 100:
        head, rest = divmod(n, 100)
        return f"{ONES[head]} {'oh ' + ONES[rest] if rest < 10 else words(rest)}"
    return words(n)


def fraction(a: int, b: int) -> str:
    if 2 <= b <= 12 and 0 < a <= 12:
        one, many = DENOM.get(b, (ordinal(b), ordinal(b) + "s"))
        return f"{words(a)} {one if a == 1 else many}"
    return f"{short(a)} out of {short(b)}"


def _num(m: re.Match) -> str:
    s = m.group(0).replace(",", "")
    if "." in s:
        s = s.rstrip("0").rstrip(".")   # 73.0 -> seventy-three, 1.50 -> one point five
    if "." in s:
        whole, frac = s.split(".")
        return f"{words(int(whole or 0))} point {' '.join(ONES[int(d)] for d in frac)}"
    return words(int(s))


NUM = r"\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?"
HEDGE = re.compile(r"(?:about|around|roughly|nearly|almost|just over|just under|over|under)\s*$", re.I)


def _percent(m: re.Match) -> str:
    """50.7% -> "about fifty-one percent"; under ten keeps one decimal (1.6 percent)."""
    v = float(m[1].replace(",", ""))
    r = round(v) if v >= 10 else round(v, 1)
    hedge = "" if r == v or HEDGE.search(m.string[:m.start()]) else "about "
    return f"{hedge}{r:g} percent"


def _decimal(m: re.Match) -> str:
    """0.042731 -> 0.043: two significant digits are enough to hear."""
    v = float(m[0])
    return f"{float(f'{v:.2g}'):g}" if len(m[0].split(".")[1]) > 3 else m[0]
RULES = [
    (re.compile(r"\b(\d+)\s*/\s*(\d+)\b"), lambda m: fraction(int(m[1]), int(m[2]))),
    (re.compile(r"\b(\d{3}) over (\d{3})\b"), lambda m: f"{short(int(m[1]))} over {short(int(m[2]))}"),
    (re.compile(rf"({NUM})\s*(?:%|percent\b)"), _percent),
    (re.compile(r"\b\d+\.\d{4,}\b"), _decimal),
    (re.compile(rf"(?<![\w.])-({NUM})"), lambda m: "minus " + m[1]),
    (re.compile(r"\b(\d+)(?:st|nd|rd|th)\b"), lambda m: ordinal(int(m[1]))),
    (re.compile(r"(\d)\s*[x×]\s*(\d)"), lambda m: f"{m[1]} by {m[2]}"),
    (re.compile(r"\^\s*2\b"), lambda m: " squared"),
    (re.compile(r"\^\s*3\b"), lambda m: " cubed"),
    (re.compile(r"\^\s*\(?([\w-]+)\)?"), lambda m: f" to the power of {m[1]}"),
    (re.compile(r"\b([a-zA-Z])\s*/\s*([a-zA-Z0-9])\b"), lambda m: f"{m[1]} over {m[2]}"),
    (re.compile(r"\b(\d{1,2}):(\d{2})\b"), lambda m: f"{m[1]} {m[2]}"),         # 3:30 -> three thirty
    (re.compile(r"\s*[:;](?=\s|$)"), lambda m: ","),               # "Add them up: nine..." reads as a pause
    (re.compile(r"\s*=\s*"), lambda m: " equals "),
    (re.compile(r"\s*≈\s*"), lambda m: " is about "),
    (re.compile(r"\s*\+\s*"), lambda m: " plus "),
    (re.compile(r"\s*[×*]\s*"), lambda m: " times "),
    (re.compile(r"\s*≤\s*"), lambda m: " at most "),
    (re.compile(r"\s*≥\s*"), lambda m: " at least "),
    (re.compile(r"\s*<\s*"), lambda m: " less than "),
    (re.compile(r"\s*>\s*"), lambda m: " greater than "),
    (re.compile(r"\s*(?:→|->)\s*"), lambda m: " to "),
    (re.compile(r"\s*&\s*"), lambda m: " and "),
    (re.compile(r"(?<=\d)\s*-\s*(?=\d)"), lambda m: " to "),       # ranges "3-5"
    (re.compile(r"(?<=\w)\s+-\s+(?=\w)"), lambda m: " minus "),    # "n - 1"
    (re.compile(NUM), _num),
]


def spoken(text: str) -> str:
    for pat, fn in RULES:
        text = pat.sub(fn, text)
    text = re.sub(r"\s+", " ", text).strip()
    # "...the rest. 77 percent" was spelled "...the rest. seventy-seven percent": capitalise again
    return re.sub(r"(^|(?<!\.\.)[.!?]\s+)([a-z])", lambda m: m[1] + m[2].upper(), text)


if __name__ == "__main__":
    for t in ["Of the 9 tiles, 6 are blue: 6/9, which is 2/3.",
              "With 100 tiles, 99/100 are blue.", "It drops 33% to 0.67 by the 3rd day.",
              "Multiply by 728 over 731. About 50.7 percent, then 1.6%, p = 0.042731, 117 pairs.",
              "77% of the tiles. 3 rows, 2 columns.",
              "A 3x3 grid, n^2 cells, 1,024 steps, n - 1 swaps, x = 2.5, steps 3-5, -4 degrees."]:
        print(spoken(t))
