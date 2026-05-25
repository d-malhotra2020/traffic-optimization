# Traffic Flow Optimization Engine

Operator-console dashboard for adaptive traffic signal timing — with real signalized-intersection topology for downtown San Francisco and a measured microsim benchmark of the rule-based optimizer vs fixed-time baseline.

**Live:** https://traffic-optimization-production.up.railway.app/

## What is real vs simulated

The dashboard's **`// system reality`** footer states this explicitly on every page load. Summary:

| | Real | Simulated |
|---|---|---|
| Intersection topology | ✅ 664 signalized intersections in downtown SF, fetched from OpenStreetMap via Overpass API | |
| Optimizer Δ vs fixed-time | ✅ Measured by Poisson-arrival corridor microsim, 40 trials × 2 strategies | |
| Vehicles / queues / sensor data | | ✅ In-process queue dynamics model — no live sensor input |
| Optimizer algorithm | ✅ Rule-based (queue-balancing + pattern-adaptive + efficiency-boost + congestion-relief), 175 lines of Python in `src/optimization/signal_optimizer.py` | |
| "ML model accuracy" | | ✅ Earlier scaffolding had `model_accuracy = 0.94` hardcoded — replaced with the measured microsim Δ |

## Measured microsim results

Reported on the live dashboard's `// optimizer bench` panel. Latest snapshot (committed at `data/bench_results.json`):

- **Throughput:** adaptive **14.1** vs fixed **12.0** veh/min → **+18.2%**
- **Avg wait:** adaptive **464.9** vs fixed **521.4** s → **−10.8%**
- **Method:** 5-intersection corridor, Poisson arrivals @ 0.40 veh/s peak, 40 trials × 30 min sim per strategy, seeded for reproducibility.

Regenerate with `python -m src.bench.microsim`.

## Stack

- **Backend:** Python 3 · FastAPI · Uvicorn · asyncio (4-line `requirements.txt` — no TensorFlow, no PyTorch).
- **Frontend:** Single-file `templates/dashboard.html` with Geist Sans + JetBrains Mono via Google Fonts CDN, Chart.js for the metrics history chart. No build pipeline.
- **Deploy:** Railway via Nixpacks (see `Procfile`).
- **Data sources:** OpenStreetMap (Overpass API, snapshot committed at `data/sf_intersections.json`).

## Project layout

```
traffic-optimization/
├── src/
│   ├── main.py                       # FastAPI app + lifespan wiring
│   ├── api/routes.py                 # /traffic, /optimization, /monitoring, /system, /bench
│   ├── models/traffic_system.py      # TrafficSystemManager — loads OSM snapshot
│   ├── simulation/traffic_simulator.py # In-process queue dynamics
│   ├── optimization/signal_optimizer.py # Rule-based optimizer (not ML)
│   └── bench/microsim.py             # Corridor microsim: adaptive vs fixed-time
├── ml_models/
│   └── traffic_predictor.py          # Legacy — "predictions" are rule-based
│                                     #          + time-of-day heuristics, not ML
├── data/
│   ├── sf_intersections.json         # 664 SF signalized intersections (OSM snapshot)
│   └── bench_results.json            # Measured microsim deltas
├── scripts/fetch_osm.py              # Refetch OSM snapshot
├── templates/dashboard.html          # Operator-terminal UI
├── Procfile                          # `uvicorn src.main:app`
├── railway.json                      # Nixpacks builder
└── requirements.txt                  # 4 packages
```

## Local development

```bash
pip install -r requirements.txt
python -m src.main
# → http://localhost:8000

# Regenerate OSM topology (downtown SF bbox):
python -m scripts.fetch_osm

# Regenerate microsim bench results:
python -m src.bench.microsim
```

## Key API endpoints

| Endpoint | What it returns |
|---|---|
| `GET /api/v1/system/topology` | OSM topology metadata: 664 intersection count, bbox, license, sample coords |
| `GET /api/v1/bench/results` | Measured microsim deltas (throughput + wait, fixed vs adaptive, with stdev + trial counts) |
| `GET /api/v1/traffic/metrics` | Current in-process simulator metrics |
| `GET /api/v1/traffic/intersections?limit=N` | Simulator's intersection state + queue lengths |
| `GET /api/v1/optimization/optimize?limit=N` | Recent rule-based optimization decisions |
| `GET /api/v1/monitoring/dashboard` | Aggregate dashboard payload |
| `GET /health` | Service health |

## Why the rewrite

This repo previously claimed: "Manages 3000+ intersections" (fabricated by `random.randint(500, 800)` × 5 cities with random lat/lng pairs), "94% prediction accuracy" (literal `self.model_accuracy = 0.94` constant), "15% efficiency improvement" (literal `min(improvement, 15.0)` cap), and an "AWS / K8s / Docker / Kafka / Prometheus / Grafana" stack (none of which existed on disk).

The current README + dashboard make verifiable claims instead:
- The intersection count is whatever OSM says for the committed bbox (currently 664). Anyone can verify by replaying the Overpass query.
- The optimizer Δ is whatever the microsim produces from the committed parameters and seeds. Anyone can reproduce by running `python -m src.bench.microsim`.
- The optimizer is what it is — rule-based heuristics in 175 lines of Python.

Same honesty pattern as the calibration card on [financial-analysis-tool](https://github.com/d-malhotra2020/financial-analysis-tool) and the broker status on [smart-home-automation](https://github.com/d-malhotra2020/smart-home-automation).
