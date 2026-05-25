"""
Tests for the corridor microsim bench.

Runs as plain pytest (`pytest tests/test_microsim.py`) — uses no
external mocking. The microsim itself is fast (~1 s for the default
40 trials × 2 strategies × 1800 s sim), so these are full-fidelity
sanity tests, not unit tests on internals.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.bench.microsim import DEFAULTS, RESULTS_PATH, run, run_sweep, simulate_trial


# Smaller params for fast tests
QUICK = {**DEFAULTS, "trials": 4, "sim_seconds": 300, "warmup_seconds": 30}


def test_committed_results_file_is_valid_json():
    """The committed data/bench_results.json must be parseable + well-shaped."""
    raw = json.loads(RESULTS_PATH.read_text())
    assert raw["params"]["corridor_intersections"] >= 2
    assert raw["params"]["trials"] >= 10
    for strategy in ("fixed", "adaptive"):
        metrics = raw["summary"][strategy]
        for k in ("throughput_per_min", "avg_wait_seconds"):
            assert k in metrics, f"{strategy}.{k} missing"
            assert metrics[k]["n"] >= 10
            assert metrics[k]["stdev"] >= 0.0


def test_committed_results_show_meaningful_delta():
    """At peak arrival rate the adaptive strategy should beat fixed-time.

    This catches regressions in the optimizer or bench harness — if
    someone refactors the heuristic and accidentally inverts a sign,
    the committed delta should still be positive.
    """
    raw = json.loads(RESULTS_PATH.read_text())
    tp_delta = raw["delta"]["throughput_per_min"]["pct_delta"]
    assert tp_delta > 5.0, f"adaptive throughput Δ shrank to {tp_delta:.2f}%; expected >5% at peak"


def test_microsim_is_reproducible():
    """Same seeds + params → identical metrics."""
    r1 = run(QUICK)
    r2 = run(QUICK)
    assert r1["delta"]["throughput_per_min"]["pct_delta"] == r2["delta"]["throughput_per_min"]["pct_delta"]
    assert r1["summary"]["fixed"]["throughput_per_min"]["mean"] == r2["summary"]["fixed"]["throughput_per_min"]["mean"]


def test_single_trial_produces_finite_metrics():
    """A single trial under either strategy returns finite, non-negative metrics."""
    for strategy in ("fixed", "adaptive"):
        m = simulate_trial(strategy, QUICK, seed=123)
        assert m["throughput_per_min"] >= 0.0
        assert m["avg_wait_seconds"] >= 0.0
        assert m["max_queue"] >= 0.0


def test_no_traffic_means_no_throughput():
    """Pin a degenerate config — zero arrivals → zero clearances + ~0 throughput."""
    quiet = {**QUICK, "ew_arrival_rate_peak": 0.0, "ns_arrival_rate": 0.0}
    m = simulate_trial("fixed", quiet, seed=7)
    assert m["throughput_per_min"] == pytest.approx(0.0, abs=0.1)
    assert m["cleared_vehicles"] == pytest.approx(0.0, abs=1.0)


def test_sweep_returns_a_point_per_rate():
    sweep = run_sweep(rates=[0.20, 0.40], trials=3, sim_seconds=300)
    assert len(sweep["points"]) == 2
    for pt in sweep["points"]:
        assert "throughput_pct_delta" in pt
        assert "wait_pct_delta" in pt
        assert pt["arrival_rate"] in (0.20, 0.40)
