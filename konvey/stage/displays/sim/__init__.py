"""``<sim rule="drop|trials">``: a seeded simulation that runs while the line is spoken.

A beat says how far the simulation has got by its end (``balls="40"``, ``shown="8"``); what was
added since the previous beat plays during this beat's hold (``live``), the rest stands still.
Rules and their numbers: ``konvey.stage.sims``."""

from __future__ import annotations

from .. import Display
from ...sims import RULES, drop_spec, trials_spec
from ...tree import BeatError

def _prepare(beats, strict: bool) -> None:
    _prepare_models(beats)
    _prepare_rules(beats)


def _model_t(n, where: str) -> float:
    from ...models import timeline

    raw = n.attrs.get("t", "0").strip()
    if raw == "end":
        return timeline(n.attrs["rule"].strip(), n.attrs, where).end
    try:
        return float(raw)
    except ValueError:
        raise BeatError(f'{where} t="{raw}": model time reached by the end of this beat (a number, or "end")') from None


def _prepare_models(beats) -> None:
    """A model <sim> learns the model time the previous beat reached (``_t0``) and its own
    (``_t1``); a <simview sim="id"> copies its model's attributes (``_model``), so both compute
    the same timeline and play the same stretch of time. (``sim=``, not ``of=``: of= means "sits
    beside that part" everywhere else; a view is a picture of its own.)"""
    import json

    from ...models import MODELS

    last: dict[str, float] = {}
    furthest: dict[str, float] = {}   # the most model time any beat reaches, per sim id
    for b in beats:
        for n in b.leaves().values():
            if n.tag == "sim" and n.attrs.get("rule", "").strip() in MODELS:
                furthest[n.id] = max(furthest.get(n.id, 0.0), _model_t(n, f"beat {b.index} <sim id={n.id}>"))
    for b in beats:
        sims = {n.id: n for n in b.leaves().values() if n.tag == "sim" and n.attrs.get("rule", "").strip() in MODELS}
        for i, n in sims.items():
            t1 = _model_t(n, f"beat {b.index} <sim id={i}>")
            n.attrs["_t0"], n.attrs["_t1"] = repr(min(last.get(i, 0.0), t1)), repr(t1)
            n.attrs["_tmax"] = repr(furthest.get(i, t1))   # how far the scene takes it (sizing)
        for gone in set(last) - set(sims):
            last.pop(gone)
        last.update({i: float(n.attrs["_t1"]) for i, n in sims.items()})
        for v in (n for n in b.leaves().values() if n.tag == "simview"):
            ref = v.attrs.get("sim", "").strip().lstrip("#")
            if ref not in sims:
                raise BeatError(f'beat {b.index} <simview id={v.id} sim="{ref}">: name a model <sim> of this '
                                f'beat ({", ".join(sorted(sims)) or "there is none"})')
            m = sims[ref]
            v.attrs["_model"] = json.dumps({k: x for k, x in m.attrs.items() if not k.startswith("_")})
            v.attrs["_t0"], v.attrs["_t1"] = m.attrs["_t0"], m.attrs["_t1"]
            v.attrs["_tmax"] = repr(furthest.get(ref, float(m.attrs["_t1"])))   # a graph's time axis


def _prepare_rules(beats) -> None:
    """Each <sim> learns where the previous beat left it (``_start``) and the most it shows in the
    scene (``_most``: balls keep one size while the piles grow)."""
    last: dict[str, int] = {}
    most: dict[str, int] = {}
    progress: dict[int, int] = {}   # id(node) -> how far it has got by the end of its beat
    from ...models import MODELS

    for b in beats:
        for n in b.leaves().values():
            if n.tag != "sim":
                continue
            rule = n.attrs.get("rule", "").strip()
            where = f"beat {b.index} <sim id={n.id}>"
            if rule in MODELS:
                continue
            if rule not in RULES:
                raise BeatError(f'{where} rule="{rule}": use one of {", ".join((*RULES, *MODELS))}')
            spec = drop_spec(n.attrs, where) if rule == "drop" else trials_spec(n.attrs, where)
            progress[id(n)] = spec.balls if rule == "drop" else spec.shown
            most[n.id] = max(most.get(n.id, 0), progress[id(n)])
    for b in beats:
        seen = set()
        for n in b.leaves().values():
            if n.tag != "sim" or id(n) not in progress:
                continue
            count = progress[id(n)]
            n.attrs["_start"] = str(min(last.get(n.id, 0), count))
            n.attrs["_most"] = str(most[n.id])
            last[n.id] = count
            seen.add(n.id)
        for gone in set(last) - seen:   # a sim that leaves and comes back starts over
            last.pop(gone)


DISPLAY = Display(tag="sim", order=150, shrink=0.6, grow=True, steady=True, prepare=_prepare,
                  kind="simulation", needs=("rule",))
