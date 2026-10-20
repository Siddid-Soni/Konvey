"""Simulations for the story agents (v7): the Explorer computes with the rules the video plays.

The stage's ``<sim>`` runs seeded, exact models (``konvey.stage.models``, ``konvey.stage.sims``).
When a finding is read off a simulation, the Explorer gets its numbers from the same code, so
the number narrated is the number the engine shows. A finding computed this way stores its run
(``Finding.sim``); :func:`sim_problem` reruns it and compares.
"""

from __future__ import annotations

import json
import math

from .stage.models import MODELS, timeline
from .stage.sims import bin_counts, drop_spec
from .stage.tree import BeatError

RULES = ("drop", *MODELS)  # trials is a montage of cases the Explorer writes out, not a model
TOL = 0.005  # relative, for real-valued channels


def values(rule: str, settings: dict, t="end") -> dict:
    """The run's numbers by model time ``t`` (``"end"``: when it stops): every channel, plus
    ``total`` for blocks (all collisions), ``end`` (model time it stops) and, for drop, ``binK``."""
    where = f"simulate({rule})"
    settings = {k: v for k, v in (settings or {}).items()}
    if rule == "drop":
        d = drop_spec(settings, where)
        counts = bin_counts(d.rows, d.balls, d.seed, d.p)
        return {"balls": d.balls, **{f"bin{k}": n for k, n in enumerate(counts)}}
    if rule not in MODELS:
        raise BeatError(f'{where}: the rules are {", ".join(RULES)}')
    tl = timeline(rule, settings, where)
    at = tl.end if t in ("end", None, "") else float(t)
    out = {k: (round(v, 6) if isinstance(v, float) else v) for k, v in tl.state(at).items()
           if isinstance(v, (int, float))}
    out["end"] = round(tl.end, 4)
    if "total" in tl.info:
        out["total"] = tl.info["total"]
    return out


def simulate(rule: str, settings: str, times: str = "end") -> str:
    """Run one of the video's simulations, exactly as the video will play it, and return its numbers.

    Use it for every number the video will show happening in a simulation, so the narration
    matches the screen. Rules and their settings (all optional, defaults in brackets):
    - blocks: mass (big/small) [100], v (big block's speed) [1], x1 [3], x2 [6]. Gives clacks
      (collisions so far), total (all collisions), v1 v2 (speeds), p1 p2 (√m·v), x1 x2.
    - drop: rows [8], balls, p (chance of right) [0.5], seed [1]. A Galton board; gives bin0, bin1, …
    - spread: people [100], radius [0.05], p (per day) [0.4], sick-days [5], distancing [0],
      days [40], seed [1]. Time in days; gives healthy, sick, recovered.
    - pendulum: angle (degrees) [60], damping [0.3], length [2], g [9.8], seconds [20]. Gives
      theta (radians), omega.
    - circles: shape (TeX outline) or curve "x(u); y(u)", terms [20], period [10]. Gives turns, x, y.
    - line: start (step|spike|expression in x), equation (heat|wave), rate, speed, ends
      (sealed|fixed), seconds. Gives left, middle, right, spread.
    - walk: walkers [400], pace (steps a second) [4], step ["-1,1"], p, seconds [30], seed [1].
      Gives steps, spread, far, mean.

    Args:
        rule: one of the rules above, e.g. "blocks".
        settings: JSON object of its settings, e.g. '{"mass": 10000, "v": 1}'.
        times: model times to report, comma separated, or "end", e.g. "1, 2.5, end".
    """
    try:
        s = json.loads(settings) if settings.strip() else {}
        if not isinstance(s, dict):
            return 'ERROR: settings must be a JSON object, e.g. {"mass": 100}'
        out = {}
        for t in [x.strip() for x in str(times).split(",") if x.strip()] or ["end"]:
            out[t] = values(rule, s, t)
        return json.dumps(out)
    except (BeatError, ValueError, TypeError) as e:
        return f"ERROR: {e}"


def sim_problem(fid: str, sim: dict) -> str | None:
    """None when the finding's stored run gives the values it claims; else what differs."""
    try:
        got = values(str(sim.get("rule", "")), sim.get("settings") or {}, sim.get("t", "end"))
    except (BeatError, ValueError, TypeError) as e:
        return f"finding {fid}: its sim does not run: {e}"
    claimed = sim.get("values") or {}
    if not claimed:
        return f"finding {fid}: its sim gives no `values` (the channels the claim reads, e.g. {{\"clacks\": 31}})"
    bad = []
    for k, v in claimed.items():
        if k not in got:
            bad.append(f"{k} is not a value of rule {sim.get('rule')} (it has {', '.join(got)})")
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            bad.append(f"{k}={v!r} is not a number")
            continue
        g = float(got[k])
        if not math.isclose(v, g, rel_tol=TOL, abs_tol=1e-9 if g == int(g) and v == int(v) else 1e-6):
            bad.append(f"{k}: claimed {v:g}, the simulation gives {g:g}")
    return f"finding {fid}: {'; '.join(bad)}" if bad else None
