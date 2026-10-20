"""Generation cost: per-request pricing and the per-run cost.json."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from konvey.cost import CostLog, request_cost, track


def usage(inp=0, out=0, read=0, write=0, reasoning=0):
    return SimpleNamespace(input_tokens=inp, output_tokens=out, cache_read_tokens=read,
                           cache_write_tokens=write, reasoning_tokens=reasoning)


SAT = datetime(2026, 10, 17, 8, tzinfo=timezone.utc)      # weekend: off-peak all day
MON_PEAK = datetime(2026, 10, 19, 7, tzinfo=timezone.utc)  # weekday 06-10 UTC: peak


def test_deepseek_peak_and_cached_input_is_a_subset():
    off = request_cost("deepseek-v4.1-flash", usage(1_000_000, 1_000_000, read=500_000), SAT)
    assert off["input"] == 500_000 and off["tier"] == "off-peak"
    assert off["usd"] == pytest.approx(0.5 * 0.15 + 0.60 + 0.5 * 0.003)
    peak = request_cost("deepseek-v4.1-flash", usage(1_000_000, 1_000_000, read=500_000), MON_PEAK)
    assert peak["usd"] == pytest.approx(2 * off["usd"])


def test_haiku_tiers_and_separate_cache_tokens():
    small = request_cost("claude-haiku-5-5", usage(50_000, 1_000_000, read=10_000, write=1_000), SAT)
    assert small["input"] == 50_000 and small["tier"] == "<=100K"     # Anthropic: not a subset
    assert small["usd"] == pytest.approx((50_000 * 0.10 + 1e6 * 0.50 + 10_000 * 0.01 + 1_000 * 0.125) / 1e6)
    big = request_cost("claude-haiku-5-5", usage(150_000, 0), SAT)
    assert big["tier"] == ">100K" and big["usd"] == pytest.approx(150_000 * 0.50 / 1e6)


def test_unpriced_model_keeps_tokens():
    r = request_cost("some-new-model", usage(10, 20), SAT)
    assert r["usd"] is None and r["output"] == 20


def test_track_records_every_request_and_writes_cost_json(tmp_path):
    msgs = [SimpleNamespace(role="assistant", metrics=usage(1000, 100)),
            SimpleNamespace(role="tool", metrics=None),
            SimpleNamespace(role="assistant", metrics=usage(1200, 50, read=1000))]
    agent = SimpleNamespace(model=SimpleNamespace(id="glm-5.3-flash"),
                            run=lambda *a, **k: SimpleNamespace(messages=msgs, metrics=None))
    log = CostLog()
    log.out_dir = tmp_path
    track(agent, log, "Agent 1")
    agent.run("go")
    agent.run("again")                                 # a repair is a second run
    data = json.loads((tmp_path / "cost.json").read_text())
    assert data["total"]["requests"] == 4 and data["by_agent"]["Agent 1"]["output"] == 300
    one_run = (1000 * 0.15 + 100 * 0.50 + 200 * 0.15 + 1000 * 0.03 + 50 * 0.50) / 1e6
    assert data["total"]["usd"] == pytest.approx(2 * one_run, rel=1e-6)
