"""Price of each generation: every model request's token usage, priced from the provider's
published per-token rates, written to ``<out_dir>/cost.json`` after every request (so a run that
fails still shows what it cost).

OpenCode does not return a cost with a response, so it is computed here. Prices are the
OpenCode Go rates (https://opencode.ai/docs/go/, checked 2026-10-16), $ per 1M tokens; update
``PRICES`` when they change. A model without a price still gets its tokens recorded (usd null).

Token accounting differs by API: OpenAI-style ``input_tokens`` already include the cached ones
(cache_read is a subset), Anthropic's do not (cache read/write are reported separately).
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

PRICES_SOURCE = "https://opencode.ai/docs/go/ (2026-10-19)"


@dataclass(frozen=True)
class Price:
    input: float
    output: float
    cache_read: float = 0.0
    cache_write: float = 0.0


PRICES: dict[str, Any] = {
    # weekdays 01:00-04:00 and 06:00-10:00 UTC are peak
    "deepseek-v4.1-flash": {"off-peak": Price(0.15, 0.60, 0.003), "peak": Price(0.30, 1.20, 0.006)},
    # tier by the request's prompt size
    "claude-haiku-5-5": {"<=100K": Price(0.10, 0.50, 0.01, 0.125), ">100K": Price(0.50, 2.50, 0.05, 0.625)},
    "glm-5.3-flash": Price(0.15, 0.50, 0.03),
    "qwen3.8-flash": Price(0.15, 0.47, 0.016, 0.20),
    "mimo-v2.6-flash": Price(0.14, 0.28, 0.0028),
    # Contributor tier: prompts and completions may be used to train Meta models (not ZDR)
    "muse-spark-1.3-contributor": Price(0.10, 0.20, 0.002),
    # Zen pay-as-you-go rates (https://opencode.ai/docs/zen/) for models used outside the Go list
    "minimax-m3": Price(0.30, 1.20, 0.06),
    "MiniMax-M3": Price(0.30, 1.20, 0.06),
    # Inception direct (https://docs.inceptionlabs.ai/get-started/models, 2026-10-20):
    # launch promo, half the regular 0.20 / 0.70 / 0.02
    "mercury-3": Price(0.10, 0.35, 0.01),
}


def _deepseek_peak(at: datetime) -> bool:
    return at.weekday() < 5 and (1 <= at.hour < 4 or 6 <= at.hour < 10)


def price_of(model: str, prompt_tokens: int, at: datetime) -> tuple[Optional[Price], str]:
    """(rates, tier name) for one request; (None, "") when the model has no listed price."""
    p = PRICES.get(model)
    if p is None or isinstance(p, Price):
        return p, ""
    if model.startswith("deepseek"):
        tier = "peak" if _deepseek_peak(at) else "off-peak"
    else:
        tier = ">100K" if prompt_tokens > 100_000 else "<=100K"
    return p[tier], tier


def request_cost(model: str, m: Any, at: Optional[datetime] = None) -> dict:
    """One request's tokens (agno message metrics) and its price in $."""
    at = at or datetime.now(timezone.utc)
    inp, out = int(m.input_tokens or 0), int(m.output_tokens or 0)
    read, write = int(m.cache_read_tokens or 0), int(m.cache_write_tokens or 0)
    anthropic = model.startswith("claude")
    fresh = inp if anthropic else max(inp - read, 0)          # uncached input
    prompt = fresh + read + write
    rates, tier = price_of(model, prompt, at)
    usd = None
    if rates is not None:
        usd = (fresh * rates.input + out * rates.output + read * rates.cache_read
               + write * rates.cache_write) / 1e6
    return {"model": model, "tier": tier, "input": fresh, "cache_read": read, "cache_write": write,
            "output": out, "reasoning": int(m.reasoning_tokens or 0), "usd": usd,
            "at": at.isoformat(timespec="seconds")}


class CostLog:
    """Thread-safe list of priced requests for one run (agents run in parallel)."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.out_dir: Optional[Path] = None
        self._lock = threading.Lock()

    def record(self, agent: str, model: str, response: Any) -> None:
        # one entry per model request (a run with tool calls makes several); the run's total
        # only when per-request detail is missing
        metrics = [m.metrics for m in (getattr(response, "messages", None) or [])
                   if getattr(m, "role", "") == "assistant" and getattr(m, "metrics", None) is not None]
        if not metrics and getattr(response, "metrics", None) is not None:
            metrics = [response.metrics]
        with self._lock:
            self.requests += [{"agent": agent, **request_cost(model, m)} for m in metrics]
            self._write()

    def summary(self) -> dict:
        def add(rows):
            known = [r["usd"] for r in rows if r["usd"] is not None]
            return {"requests": len(rows), "usd": round(sum(known), 6) if known else None,
                    "unpriced_requests": sum(r["usd"] is None for r in rows),
                    **{k: sum(r[k] for r in rows) for k in ("input", "cache_read", "cache_write",
                                                            "output", "reasoning")}}
        agents = sorted({r["agent"] for r in self.requests})
        return {"total": add(self.requests),
                "by_agent": {a: add([r for r in self.requests if r["agent"] == a]) for a in agents},
                "prices": PRICES_SOURCE}

    def _write(self) -> None:
        if self.out_dir is None:
            return
        self.out_dir.mkdir(parents=True, exist_ok=True)
        (self.out_dir / "cost.json").write_text(json.dumps(
            {**self.summary(), "requests": self.requests}, indent=1) + "\n", encoding="utf-8")


def track(agent: Any, log: CostLog, label: str) -> Any:
    """Record every ``agent.run`` (repairs included) without touching the agent class."""
    if getattr(agent, "_cost_tracked", False):
        return agent
    run = agent.run
    model = getattr(getattr(agent, "model", None), "id", "") or "unknown"

    def tracked(*a, **k):
        resp = run(*a, **k)
        try:
            log.record(label, model, resp)
        except Exception:  # noqa: BLE001 - accounting must never break a run
            pass
        return resp

    agent.run = tracked
    agent._cost_tracked = True
    return agent


def fmt_usd(usd: Optional[float]) -> str:
    return "n/a" if usd is None else f"${usd:.4f}"


__all__ = ["CostLog", "PRICES", "Price", "fmt_usd", "price_of", "request_cost", "track"]
