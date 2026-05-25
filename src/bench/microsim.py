"""
Microsimulation bench for the rule-based signal optimizer.

Compares the existing SignalOptimizer's queue-balancing strategy
against a fixed-time baseline on a small corridor and reports the
measured Δ-throughput and Δ-avg-wait. Designed to be defensible
rather than dramatic — the corridor and arrival model are small,
the parameters are explicit, and results carry trial counts and
seeds so anyone can reproduce.

Model
-----
- N intersections in a linear E-W corridor.
- Vehicles arrive at intersection 0 (eastbound) as a Poisson process.
- Each intersection has an N-S and E-W queue; only one direction is
  green at a time. The E-W queue drains at the saturation flow rate
  during green phase; the N-S queue is fed at a fixed cross-street
  arrival rate (a single independent Poisson stream per intersection).
- Vehicles that depart intersection i join intersection i+1's E-W
  queue after a constant link travel time.
- Two timing strategies are evaluated:
    * "fixed"   — symmetric 45 s NS / 45 s EW + 5 s yellow + 2 s all-red
                  cycle, same for every intersection.
    * "adaptive" — every 30 s of sim time, the manager re-computes the
                   green split per intersection using the same
                   queue-balancing heuristic that SignalOptimizer uses
                   (longer green for the heavier direction, clamped to
                   [25, 70] s, cycle ≤ 180 s).

Metrics
-------
- throughput_per_min : vehicles cleared at intersection N-1 per minute,
                      averaged across trials.
- avg_wait_seconds   : per-vehicle wait time, averaged across trials.
- max_queue          : peak E-W queue length across the corridor.

Usage
-----
    python -m src.bench.microsim
    # → writes data/bench_results.json
"""

from __future__ import annotations

import json
import math
import random
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_PATH = ROOT / "data" / "bench_results.json"
SWEEP_PATH = ROOT / "data" / "bench_sweep.json"

# Parameter sweep — same model, varying peak arrival rate
SWEEP_RATES = [0.20, 0.30, 0.40, 0.50, 0.60]
SWEEP_TRIALS = 25
SWEEP_SIM_SECONDS = 1200

# ---------- Default parameters (committed so results are reproducible) ----------

DEFAULTS = {
    "corridor_intersections": 5,          # 5 signals in a row
    "sim_seconds": 1800,                  # 30 min of simulated time per trial
    "trials": 40,                         # 40 trials per strategy (~1600 vehicle-minutes each)
    "tick_seconds": 1.0,                  # 1 s simulation step
    "ew_arrival_rate_peak": 0.40,         # vehicles / s arriving at corridor entry (peak)
    "ns_arrival_rate": 0.06,              # vehicles / s on each cross street
    "saturation_flow_rate": 0.50,         # vehicles / s discharged per lane during green
    "link_travel_seconds": 8.0,           # downstream travel time between signals
    "warmup_seconds": 120.0,              # warmup time excluded from metrics
    "fixed_timing": {
        "ew_green": 45,
        "ns_green": 45,
        "yellow":   5,
        "all_red":  2,
    },
    "adaptive": {
        "recompute_interval_s": 30.0,
        "min_green": 25,
        "max_green": 70,
        "yellow": 5,
        "all_red": 2,
    },
    "seed_base": 20260524,
}

# ---------- Signal state machine ----------

PHASES = ("EW_GREEN", "EW_YELLOW", "ALL_RED_1", "NS_GREEN", "NS_YELLOW", "ALL_RED_2")


@dataclass
class SignalState:
    """One intersection's signal cycle."""
    ew_green: int
    ns_green: int
    yellow: int
    all_red: int
    phase_idx: int = 0
    phase_elapsed: float = 0.0

    def durations(self) -> Tuple[int, int, int, int, int, int]:
        return (self.ew_green, self.yellow, self.all_red,
                self.ns_green, self.yellow, self.all_red)

    def cycle_length(self) -> int:
        return sum(self.durations())

    def tick(self, dt: float):
        self.phase_elapsed += dt
        durations = self.durations()
        if self.phase_elapsed >= durations[self.phase_idx]:
            self.phase_elapsed = 0.0
            self.phase_idx = (self.phase_idx + 1) % len(PHASES)

    @property
    def ew_green_now(self) -> bool:
        return PHASES[self.phase_idx] == "EW_GREEN"

    @property
    def ns_green_now(self) -> bool:
        return PHASES[self.phase_idx] == "NS_GREEN"


# ---------- Corridor model ----------

@dataclass
class Vehicle:
    """A single eastbound vehicle traversing the corridor."""
    entered_at: float                # sim time entering intersection 0
    waits: List[float] = field(default_factory=list)
    cleared_at: float | None = None  # sim time clearing the corridor

    @property
    def total_wait(self) -> float:
        return sum(self.waits)


@dataclass
class CorridorState:
    ew_queues: List[List[Vehicle]] = field(default_factory=list)  # per intersection, vehicles waiting in E-W queue
    ns_queues: List[int] = field(default_factory=list)            # cross-street queue counts (we only model EW vehicles individually)
    in_transit: List[List[Tuple[float, Vehicle]]] = field(default_factory=list)  # link i → i+1: list of (arrival_time, vehicle)
    cleared: List[Vehicle] = field(default_factory=list)


def _new_corridor(n: int) -> CorridorState:
    return CorridorState(
        ew_queues=[[] for _ in range(n)],
        ns_queues=[0] * n,
        in_transit=[[] for _ in range(n)],  # in_transit[i] are vehicles heading from i to i+1
    )


# ---------- Simulation ----------

def simulate_trial(strategy: str, params: dict, seed: int) -> Dict[str, float]:
    """Run one trial; return per-trial metrics."""
    rng = random.Random(seed)
    n = params["corridor_intersections"]
    dt = params["tick_seconds"]
    warmup = params["warmup_seconds"]

    # Initialize signals
    if strategy == "fixed":
        ft = params["fixed_timing"]
        signals = [
            SignalState(ft["ew_green"], ft["ns_green"], ft["yellow"], ft["all_red"])
            for _ in range(n)
        ]
        recompute_interval = math.inf
    elif strategy == "adaptive":
        ac = params["adaptive"]
        # Start with the same baseline; will be re-tuned every recompute_interval_s.
        ft = params["fixed_timing"]
        signals = [
            SignalState(ft["ew_green"], ft["ns_green"], ac["yellow"], ac["all_red"])
            for _ in range(n)
        ]
        recompute_interval = ac["recompute_interval_s"]
    else:
        raise ValueError(f"unknown strategy: {strategy!r}")

    corridor = _new_corridor(n)

    # Pre-compute Poisson arrivals as per-tick probabilities
    p_ew_entry = params["ew_arrival_rate_peak"] * dt    # arrival at intersection 0
    p_ns       = params["ns_arrival_rate"] * dt         # cross-street arrival per intersection
    p_discharge = params["saturation_flow_rate"] * dt   # discharge per intersection during green
    link_travel = params["link_travel_seconds"]
    sim_seconds = params["sim_seconds"]

    t = 0.0
    last_recompute = 0.0

    while t < sim_seconds:
        # 1) E-W arrivals into intersection 0
        if rng.random() < p_ew_entry:
            corridor.ew_queues[0].append(Vehicle(entered_at=t))

        # 2) N-S arrivals at each intersection (counted only)
        for i in range(n):
            if rng.random() < p_ns:
                corridor.ns_queues[i] += 1

        # 3) Land in-transit vehicles into the next intersection's E-W queue
        for i in range(n - 1):
            still_in_transit = []
            for arrival_t, veh in corridor.in_transit[i]:
                if arrival_t <= t:
                    corridor.ew_queues[i + 1].append(veh)
                    # mark wait start
                    veh._wait_start = t  # type: ignore[attr-defined]
                else:
                    still_in_transit.append((arrival_t, veh))
            corridor.in_transit[i] = still_in_transit

        # 4) Discharge from each intersection during its green phase
        for i, sig in enumerate(signals):
            sig.tick(dt)
            if sig.ew_green_now and corridor.ew_queues[i] and rng.random() < p_discharge:
                veh = corridor.ew_queues[i].pop(0)
                # Record wait at this intersection (entered_at for i==0; _wait_start for downstream)
                wait_start = getattr(veh, "_wait_start", veh.entered_at)
                veh.waits.append(max(0.0, t - wait_start))
                if i == n - 1:
                    veh.cleared_at = t
                    corridor.cleared.append(veh)
                else:
                    corridor.in_transit[i].append((t + link_travel, veh))
            if sig.ns_green_now and corridor.ns_queues[i] > 0 and rng.random() < p_discharge:
                corridor.ns_queues[i] -= 1

        # 5) Adaptive recompute
        if strategy == "adaptive" and (t - last_recompute) >= recompute_interval:
            last_recompute = t
            ac = params["adaptive"]
            for i, sig in enumerate(signals):
                ew_q = len(corridor.ew_queues[i])
                ns_q = corridor.ns_queues[i]
                total = ew_q + ns_q
                if total == 0:
                    continue
                ew_share = ew_q / total
                # Heuristic: total green budget = 90 s, split by share, clamped.
                ew_green = int(max(ac["min_green"], min(ac["max_green"], round(90 * (0.4 + 0.6 * ew_share)))))
                ns_green = int(max(ac["min_green"], min(ac["max_green"], 90 - ew_green + ac["min_green"])))
                # Apply
                sig.ew_green = ew_green
                sig.ns_green = ns_green

        t += dt

    # ---------- Metrics (warmup excluded) ----------
    cleared_post_warmup = [v for v in corridor.cleared if v.cleared_at is not None and v.cleared_at >= warmup]
    sim_post_warmup_minutes = max(1e-9, (sim_seconds - warmup) / 60.0)
    throughput_per_min = len(cleared_post_warmup) / sim_post_warmup_minutes
    waits = [v.total_wait for v in cleared_post_warmup]
    avg_wait = statistics.fmean(waits) if waits else 0.0
    # Sample max E-W queue across all intersections at end-of-sim
    max_queue = max((len(q) for q in corridor.ew_queues), default=0)

    return {
        "throughput_per_min": throughput_per_min,
        "avg_wait_seconds": avg_wait,
        "max_queue": float(max_queue),
        "cleared_vehicles": float(len(cleared_post_warmup)),
    }


def run(params: dict = DEFAULTS) -> dict:
    """Run trials for both strategies and produce a results dict."""
    trials = params["trials"]
    out: Dict[str, Dict[str, List[float]]] = {"fixed": {}, "adaptive": {}}
    for strategy in ("fixed", "adaptive"):
        per_trial: List[Dict[str, float]] = []
        for trial in range(trials):
            seed = params["seed_base"] + (1_000_000 if strategy == "adaptive" else 0) + trial
            per_trial.append(simulate_trial(strategy, params, seed))
        out[strategy] = {
            k: [t[k] for t in per_trial]
            for k in per_trial[0].keys()
        }

    summary = {}
    for strategy, series in out.items():
        summary[strategy] = {
            k: {
                "mean":    statistics.fmean(v),
                "stdev":   statistics.pstdev(v) if len(v) > 1 else 0.0,
                "n":       len(v),
            }
            for k, v in series.items()
        }

    # Δ (adaptive vs fixed)
    delta = {}
    for k in ("throughput_per_min", "avg_wait_seconds", "max_queue"):
        f_mean = summary["fixed"][k]["mean"]
        a_mean = summary["adaptive"][k]["mean"]
        delta[k] = {
            "fixed_mean":    f_mean,
            "adaptive_mean": a_mean,
            "abs_delta":     a_mean - f_mean,
            "pct_delta":     ((a_mean - f_mean) / f_mean * 100.0) if f_mean else 0.0,
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "params": params,
        "summary": summary,
        "delta": delta,
        "interpretation": _interpret(delta),
    }


def _interpret(delta: Dict[str, Dict[str, float]]) -> str:
    tp = delta["throughput_per_min"]
    wt = delta["avg_wait_seconds"]
    parts = []
    if abs(tp["pct_delta"]) >= 1.0:
        parts.append(
            f"Throughput: {tp['adaptive_mean']:.1f} vs {tp['fixed_mean']:.1f} veh/min "
            f"({tp['pct_delta']:+.1f}%)."
        )
    else:
        parts.append(
            f"Throughput: ~unchanged ({tp['adaptive_mean']:.1f} vs {tp['fixed_mean']:.1f} veh/min, "
            f"{tp['pct_delta']:+.1f}%)."
        )
    if abs(wt["pct_delta"]) >= 1.0:
        parts.append(
            f"Avg wait: {wt['adaptive_mean']:.1f} vs {wt['fixed_mean']:.1f} s "
            f"({wt['pct_delta']:+.1f}%)."
        )
    else:
        parts.append(
            f"Avg wait: ~unchanged ({wt['adaptive_mean']:.1f} vs {wt['fixed_mean']:.1f} s, "
            f"{wt['pct_delta']:+.1f}%)."
        )
    return " ".join(parts)


def run_sweep(rates=SWEEP_RATES, trials=SWEEP_TRIALS, sim_seconds=SWEEP_SIM_SECONDS) -> dict:
    """Sweep the peak arrival rate; produce Δ throughput / wait per rate.

    Smaller trial count + sim duration than the main bench because we're
    measuring a curve, not a single point. The shape of the curve matters
    more than the exact value at any one rate.
    """
    points = []
    for rate in rates:
        params = {**DEFAULTS, "trials": trials, "sim_seconds": sim_seconds, "ew_arrival_rate_peak": rate}
        results = run(params)
        tp = results["delta"]["throughput_per_min"]
        wt = results["delta"]["avg_wait_seconds"]
        points.append({
            "arrival_rate": rate,
            "fixed_throughput": tp["fixed_mean"],
            "adaptive_throughput": tp["adaptive_mean"],
            "throughput_pct_delta": tp["pct_delta"],
            "fixed_avg_wait": wt["fixed_mean"],
            "adaptive_avg_wait": wt["adaptive_mean"],
            "wait_pct_delta": wt["pct_delta"],
        })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "params": {
            "rates": rates,
            "trials_per_point": trials,
            "sim_seconds_per_trial": sim_seconds,
            "corridor_intersections": DEFAULTS["corridor_intersections"],
            "saturation_flow_rate": DEFAULTS["saturation_flow_rate"],
            "ns_arrival_rate": DEFAULTS["ns_arrival_rate"],
        },
        "points": points,
    }


def main() -> int:
    print(f"→ Running microsim bench: {DEFAULTS['trials']} trials × 2 strategies "
          f"× {DEFAULTS['sim_seconds']}s sim time…")
    results = run(DEFAULTS)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(results, indent=2))
    print(f"✓ Wrote {RESULTS_PATH.relative_to(ROOT)}")
    print(f"  {results['interpretation']}")

    print(f"\n→ Running arrival-rate sweep: {len(SWEEP_RATES)} rates × "
          f"{SWEEP_TRIALS} trials × 2 strategies…")
    sweep = run_sweep()
    SWEEP_PATH.write_text(json.dumps(sweep, indent=2))
    print(f"✓ Wrote {SWEEP_PATH.relative_to(ROOT)}")
    for pt in sweep["points"]:
        print(f"  {pt['arrival_rate']:.2f} veh/s : "
              f"tp {pt['adaptive_throughput']:.1f} vs {pt['fixed_throughput']:.1f} "
              f"({pt['throughput_pct_delta']:+.1f}%) · "
              f"wait {pt['adaptive_avg_wait']:.0f} vs {pt['fixed_avg_wait']:.0f} "
              f"({pt['wait_pct_delta']:+.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
