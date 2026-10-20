"""Compute tools for Agent 1, so the numbers in a video are calculated, not recalled.

- ``calc``: one arithmetic expression, parsed (never eval'd) like the renderer's ``fn``.
- ``run_python``: a short restricted Python program for traces and simulations (an algorithm
  run step by step, a recurrence, a population over time). It runs in a separate interpreter
  with no imports, no files, no dunder access, a whitelist of builtins and CPU/memory/time
  limits. ``math`` functions are provided as ``math``.

Every call is recorded in ``ComputeLog`` so a run can show where its numbers came from.
"""

from __future__ import annotations

import ast
import json
import math
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field

TIMEOUT_S = 5
MAX_OUTPUT = 6000

_ALLOWED_BUILTINS = (
    "abs all any bool dict divmod enumerate filter float int isinstance len list map max min "
    "pow print range reversed round set sorted str sum tuple zip True False None"
).split()
_FORBIDDEN_NAMES = {"eval", "exec", "compile", "open", "input", "globals", "locals", "vars",
                    "getattr", "setattr", "delattr", "breakpoint", "help", "memoryview", "type",
                    "object", "super", "classmethod", "staticmethod", "property"}


def check_code(code: str) -> list[str]:
    """Static gate: returns problems (empty = allowed)."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"syntax error line {e.lineno}: {e.msg}"]
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            problems.append("no imports (math is already available as `math`)")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            problems.append(f"attribute {node.attr!r} is not allowed")
        elif isinstance(node, ast.Name) and (node.id in _FORBIDDEN_NAMES or node.id.startswith("__")):
            problems.append(f"name {node.id!r} is not allowed")
        elif isinstance(node, (ast.Global, ast.Nonlocal, ast.AsyncFunctionDef, ast.Await,
                               ast.ClassDef, ast.With, ast.AsyncWith)):
            problems.append(f"{type(node).__name__} is not allowed")
    return sorted(set(problems))


# Runs in a fresh `python -I` process: rlimits, then exec with a stripped builtins dict.
_RUNNER = textwrap.dedent("""
    import json, math, resource, sys
    resource.setrlimit(resource.RLIMIT_CPU, (4, 4))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 512 * 2**20))
    resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))
    import builtins
    safe = {k: getattr(builtins, k) for k in json.loads(sys.argv[1])}
    m = type(sys)("math")
    for k in dir(math):
        if not k.startswith("_"):
            setattr(m, k, getattr(math, k))
    code = sys.stdin.read()
    exec(compile(code, "<run_python>", "exec"), {"__builtins__": safe, "math": m})
""")


@dataclass
class ComputeLog:
    calls: list = field(default_factory=list)

    def record(self, tool: str, arg: str, result: str) -> str:
        self.calls.append({"tool": tool, "input": arg, "output": result})
        return result


def calc(expression: str) -> str:
    """Evaluate one arithmetic expression exactly and return the number.

    Allowed: numbers, + - * / ^ (or **), // and % , parentheses, pi, e, and
    sin cos tan exp log log2 log10 sqrt abs floor ceil round arctan.
    Example: calc("log2(1048576)") -> "20.0"

    Args:
        expression: the arithmetic expression, e.g. "1000 * 1.05^3".
    """
    try:
        return repr(_eval_expr(expression))
    except Exception as e:  # report, never raise into the agent loop
        return f"ERROR: {e}"


_FUNCS = {"sin": math.sin, "cos": math.cos, "tan": math.tan, "exp": math.exp, "log": math.log,
          "log2": math.log2, "log10": math.log10, "sqrt": math.sqrt, "abs": abs,
          "floor": math.floor, "ceil": math.ceil, "round": round, "arctan": math.atan}
_OPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b, ast.Pow: lambda a, b: a ** b,
        ast.FloorDiv: lambda a, b: a // b, ast.Mod: lambda a, b: a % b}


def _eval_expr(expr: str):
    tree = ast.parse(expr.replace("^", "**"), mode="eval")

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.Name) and n.id in ("pi", "e"):
            return math.pi if n.id == "pi" else math.e
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            left, right = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and abs(right) > 1000:
                raise ValueError("exponent too large")
            return _OPS[type(n.op)](left, right)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUNCS
                and not n.keywords and 1 <= len(n.args) <= 2):
            return _FUNCS[n.func.id](*(ev(a) for a in n.args))
        raise ValueError(f"{ast.unparse(n)!r} is not allowed in calc; use run_python for programs")

    return ev(tree)


def run_python(code: str) -> str:
    """Run a short Python program and return what it prints.

    Use it to trace an algorithm step by step, run a recurrence or simulation, or build a
    table of values. print() every value you will use. No imports: `math` is already there.
    Builtins: range len min max sum abs round sorted enumerate zip list dict set tuple int
    float str bool print map filter any all divmod pow reversed isinstance. 5 s limit.

    Args:
        code: the program, e.g. "a, b = 48, 18\\nwhile b:\\n    a, b = b, a % b\\n    print(a, b)".
    """
    problems = check_code(code)
    if problems:
        return "REJECTED: " + "; ".join(problems)
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-c", _RUNNER, json.dumps(_ALLOWED_BUILTINS)],
            input=code, capture_output=True, text=True, timeout=TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return f"ERROR: timed out after {TIMEOUT_S} s"
    out = proc.stdout
    if proc.returncode != 0:
        err = proc.stderr.strip().splitlines()
        if proc.returncode < 0:  # killed by the CPU/memory rlimit
            out += "\nERROR: stopped at the CPU limit (4 s); make the program smaller"
        else:
            out += "\nERROR: " + (err[-1] if err else f"exit code {proc.returncode}")
    if len(out) > MAX_OUTPUT:
        out = out[:MAX_OUTPUT] + f"\n... (output cut at {MAX_OUTPUT} chars; print less)"
    return out or "(no output: print the values you need)"


def make_tools(log: ComputeLog | None = None) -> list:
    """The tools as plain functions for an Agno Agent, recording each call in ``log``."""
    if log is None:
        return [calc, run_python]

    def calc_logged(expression: str) -> str:
        return log.record("calc", expression, calc(expression))

    def run_python_logged(code: str) -> str:
        return log.record("run_python", code, run_python(code))

    for wrapped, orig in ((calc_logged, calc), (run_python_logged, run_python)):
        wrapped.__name__, wrapped.__doc__ = orig.__name__, orig.__doc__
    return [calc_logged, run_python_logged]
