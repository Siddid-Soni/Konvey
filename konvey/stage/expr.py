"""Arithmetic expressions from beat attributes (``fn=``), parsed and never eval'd (pure Python)."""

from __future__ import annotations

import ast
import operator

import numpy as np

from .tree import BeatError

# Plot functions are parsed, never eval'd: numbers, x, + - * / ** and these calls.
_FUNCS = {k: getattr(np, k) for k in ("sin", "cos", "tan", "exp", "log", "sqrt", "abs", "arctan",
                                      "sinh", "cosh", "tanh", "floor", "ceil", "sign")}
_CONSTS = {"pi": np.pi, "e": np.e}
_BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.Pow: operator.pow}


def parse_fn(expr: str):
    """``"exp(-x**2/2)/sqrt(2*pi)"`` -> callable of x, or BeatError."""
    return parse_expr(expr, ("x",))


def parse_expr(expr: str, names: tuple[str, ...]):
    """Arithmetic expression in ``names`` -> callable(*values). Parsed, never eval'd."""
    try:
        tree = ast.parse(expr.replace("^", "**"), mode="eval")
    except SyntaxError as e:
        raise BeatError(f"fn={expr!r} is not a valid expression: {e.msg}") from e

    def ev(n, env):
        if isinstance(n, ast.Expression):
            return ev(n.body, env)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.Name) and n.id in env:
            return env[n.id]
        if isinstance(n, ast.BinOp) and type(n.op) in _BINOPS:
            return _BINOPS[type(n.op)](ev(n.left, env), ev(n.right, env))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = ev(n.operand, env)
            return -v if isinstance(n.op, ast.USub) else v
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUNCS
                and len(n.args) == 1 and not n.keywords):
            return _FUNCS[n.func.id](ev(n.args[0], env))
        raise BeatError(f"fn={expr!r}: only {', '.join(names)}, numbers, pi, e, + - * / ** and "
                        f"{', '.join(sorted(_FUNCS))}(...) are allowed")

    ev(tree, {**_CONSTS, **{k: 0.5 for k in names}})  # surface errors now, not mid-render
    return lambda *vals: ev(tree, {**_CONSTS, **dict(zip(names, vals))})
