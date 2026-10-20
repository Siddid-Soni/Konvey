"""``<tex>``: LaTeX math; the plan's ``tex`` kind."""

from __future__ import annotations

import re

from ...match import squash
from .. import Display

# Valid LaTeX that manimgl 1.7.2's Tex cannot typeset, and an equivalent it can.
_TEX_FIXES = ((re.compile(r"\\\|"), r"\\Vert "),
              # \; and \: break any formula that also has \text{} (same spacing via \mskip)
              (re.compile(r"\\;"), r"\\mskip 5mu "), (re.compile(r"\\:"), r"\\mskip 4mu "),
              # these expand to \; internally, so they break next to \text{} the same way
              (re.compile(r"\\iff(?![A-Za-z])"), r"\\mskip 5mu\\Longleftrightarrow\\mskip 5mu "),
              (re.compile(r"\\implies(?![A-Za-z])"), r"\\mskip 5mu\\Longrightarrow\\mskip 5mu "),
              (re.compile(r"\\impliedby(?![A-Za-z])"), r"\\mskip 5mu\\Longleftarrow\\mskip 5mu "))


def tex_safe(tex: str) -> str:
    """Rewrite valid LaTeX that manimgl cannot typeset (``\\|``, ``\;``, ``\\:``) into equivalents."""
    for pat, rep in _TEX_FIXES:
        tex = pat.sub(rep, tex)
    return tex


_TEX_GROUP_RE = re.compile(r"\\(?:text|mathrm|operatorname|textbf|mathit|begin|end)\{[^}]*\}")
_TEX_CMD_RE = re.compile(r"\\[A-Za-z]+")
_TEX_WORD_RE = re.compile(r"[A-Za-z]{3,}|[A-Za-z]+\d")


def bare_tex_words(tex: str) -> list[str]:
    """Plain words in math mode ('with', 'log2', 'rights') that LaTeX would
    italicise as letter products; \\text{} / \\mathrm{} / commands are fine."""
    stripped = _TEX_CMD_RE.sub(" ", _TEX_GROUP_RE.sub(" ", tex))
    stripped = re.sub(r"[_^]\{[^{}]*\}", " ", stripped)  # A_{face}, e^{rate}
    return sorted(set(_TEX_WORD_RE.findall(stripped)))


def _check_object(d: dict) -> list[str]:
    words = bare_tex_words(d["tex"]) if isinstance(d.get("tex"), str) else []
    if words:
        return [f"tex {d['tex']!r} has plain words {words}; write LaTeX (\\log_2, \\sum_i, x_1, "
                "\\mathrm{Var}, \\text{with})"]
    return []


def _check_drawn(where: str, obj, leaves) -> list[str]:
    tex = obj.data.get("tex")
    blob = "\n".join({squash(n.text) for n in leaves if n.tag != "bars"})
    if tex and squash(tex) not in blob:
        return [f"{where}: <tex> {tex!r} not drawn verbatim"]
    return []


DISPLAY = Display(tag="tex", order=10, raw=True, shrink=0.7, min_size=30, enter="write",
                  kind="tex", needs=("tex",), picture=False,
                  check_object=_check_object, check_drawn=_check_drawn)
