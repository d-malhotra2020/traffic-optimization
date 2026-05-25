"""
Heuristic traffic estimators.

This module is named ml_models for historical reasons — earlier
scaffolding pitched it as "TensorFlow / Random Forest / LSTM
ensemble" with hardcoded 94 %% "model accuracy" and a fake
"last_trained" timestamp. There was never an actual model.

What's actually here:
- Time-of-day multipliers (rush hour, lunch, night).
- Queue-share splits (longer green for the heavier direction).
- Hardcoded pattern descriptors (named "Morning Rush" etc.).
- A small amount of bounded random noise to make demo values vary.

These are heuristic estimators, not predictions from a trained model.
The dashboard reports a measured Δ from src/bench/microsim.py, which
benchmarks the optimizer's rule-based timing against a fixed-time
baseline — that's the real story.

Class/method names are preserved so existing route callers keep
working. New code should treat anything in this module as heuristics.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Module-level honesty marker (read by /api/v1/monitoring/dashboard)
ESTIMATOR_KIND = "heuristic"


@dataclass
class PredictionResult:
    """A single heuristic estimate.

    The `confidence` field is a coarse data-quality score (0.5..0.99),
    not a calibrated probability. The legacy `model_version` and
    `accuracy` fields have been dropped — there is no model.
    """
    prediction_type: str
    confidence: float
    prediction_value: float
    timestamp: float
    kind: str = ESTIMATOR_KIND


@dataclass
class ModelMetrics:
    """Estimator metadata — intentionally sparse.

    Kept for backward compat with routes.py callers. The hardcoded
    accuracy / precision / recall / f1_score / training_samples /
    last_trained fields were removed — they were fabricated.
    """
    kind: str = ESTIMATOR_KIND
    description: str = "time-of-day + queue-share heuristics"


class TrafficVolumeEstimator:
    """Estimates future traffic volume from time-of-day patterns + current state."""

    def __init__(self):
        self.metrics = ModelMetrics()

    async def predict_traffic_volume(
        self, intersection_id: str, current_data: Dict, forecast_minutes: int = 30
    ) -> PredictionResult:
        """Estimate volume {forecast_minutes} ahead from time-of-day shape.

        Method: current volume × weekday/weekend factor × hour-of-day
        rush-hour multiplier, with small bounded noise. Not a model.
        """
        try:
            current_volume = sum(current_data.get("traffic_volume", {}).values())
            now = datetime.now()
            weekday_factor = 1.0 if now.weekday() < 5 else 0.7
            time_factor = self._time_factor(now.hour)

            estimate = current_volume * weekday_factor * time_factor
            noise = random.uniform(-0.05, 0.05)
            estimate = max(0.0, estimate * (1.0 + noise))

            return PredictionResult(
                prediction_type="traffic_volume",
                confidence=self._data_quality(current_data, now.hour),
                prediction_value=estimate,
                timestamp=time.time(),
            )
        except Exception as exc:
            logger.error("Traffic volume estimate failed: %s", exc)
            return PredictionResult("traffic_volume", 0.5, 0.0, time.time())

    async def predict_congestion_level(self, intersection_data: Dict) -> PredictionResult:
        """Estimate congestion (0..1) from queues + volumes + time-of-day."""
        try:
            queues = intersection_data.get("queue_length", {})
            volumes = intersection_data.get("traffic_volume", {})

            queue_factor = min(1.0, sum(queues.values()) / 80.0)
            volume_factor = min(1.0, sum(volumes.values()) / 300.0)
            time_factor = 0.8 if self._is_rush_hour() else 0.4

            score = queue_factor * 0.4 + volume_factor * 0.3 + time_factor * 0.3
            score = max(0.0, min(1.0, score + random.uniform(-0.05, 0.05)))

            return PredictionResult(
                prediction_type="congestion_level",
                confidence=self._data_quality(intersection_data),
                prediction_value=score,
                timestamp=time.time(),
            )
        except Exception as exc:
            logger.error("Congestion estimate failed: %s", exc)
            return PredictionResult("congestion_level", 0.5, 0.5, time.time())

    async def predict_optimal_timing(self, intersection_data: Dict) -> PredictionResult:
        """Estimate ideal NS green time (seconds) from queue share."""
        try:
            queues = intersection_data.get("queue_length", {})
            ns_q = queues.get("north", 0) + queues.get("south", 0)
            ew_q = queues.get("east", 0) + queues.get("west", 0)
            total = ns_q + ew_q
            if total == 0:
                return PredictionResult("optimal_timing", 0.7, 45.0, time.time())

            ns_ratio = ns_q / total
            base_cycle = 90.0
            ns_time = base_cycle * 0.5 * (0.5 + ns_ratio)
            ns_time = max(25.0, min(70.0, ns_time))

            return PredictionResult(
                prediction_type="optimal_timing",
                confidence=self._data_quality(intersection_data),
                prediction_value=ns_time,
                timestamp=time.time(),
            )
        except Exception as exc:
            logger.error("Optimal-timing estimate failed: %s", exc)
            return PredictionResult("optimal_timing", 0.6, 45.0, time.time())

    async def get_model_metrics(self) -> ModelMetrics:
        return self.metrics

    # ---- internals ----

    @staticmethod
    def _time_factor(hour: int) -> float:
        if 7 <= hour <= 9 or 17 <= hour <= 19:
            return 1.6
        if 12 <= hour <= 13:
            return 1.2
        if 22 <= hour or hour <= 5:
            return 0.3
        return 1.0

    @staticmethod
    def _is_rush_hour() -> bool:
        h = datetime.now().hour
        return 7 <= h <= 9 or 17 <= h <= 19

    @staticmethod
    def _data_quality(data: Dict, hour: Optional[int] = None) -> float:
        score = 0.85
        if "queue_length" in data:
            score *= 1.0
        if "traffic_volume" in data:
            score *= 1.0
        if hour is not None:
            score *= 1.05 if 6 <= hour <= 22 else 0.95
        return max(0.5, min(0.99, score + random.uniform(-0.03, 0.03)))


class CongestionEstimator:
    """Picks the worst-queue intersections as predicted hotspots."""

    kind = ESTIMATOR_KIND
    description = "queue-rank heuristic"

    async def predict_congestion_hotspots(self, city_data: Dict) -> List[Dict]:
        """Return up to 10 intersections with the longest queues."""
        ranked = sorted(
            city_data.items(),
            key=lambda kv: sum((kv[1].get("queue_length") or {}).values()),
            reverse=True,
        )
        hotspots = []
        for intersection_id, data in ranked[:10]:
            total_q = sum((data.get("queue_length") or {}).values())
            if total_q <= 0:
                break
            severity = "severe" if total_q > 60 else "high" if total_q > 30 else "moderate"
            hotspots.append({
                "intersection_id": intersection_id,
                "total_queue": total_q,
                "severity": severity,
            })
        return hotspots


class PatternRecognizer:
    """Static catalog of named traffic patterns keyed by hour-of-day."""

    kind = ESTIMATOR_KIND
    description = "time-of-day pattern catalog"

    def __init__(self):
        self.pattern_library: List[Dict] = [
            {"name": "Morning Rush", "hours": [7, 8, 9], "direction_bias": "inbound", "intensity_multiplier": 1.8},
            {"name": "Evening Rush", "hours": [17, 18, 19], "direction_bias": "outbound", "intensity_multiplier": 1.9},
            {"name": "Lunch Hour", "hours": [12, 13], "direction_bias": "mixed", "intensity_multiplier": 1.3},
            {"name": "Weekend Shopping", "hours": [10, 11, 14, 15, 16], "direction_bias": "commercial", "intensity_multiplier": 1.4},
        ]

    async def detect_current_pattern(self, _traffic_data: Dict) -> Optional[Dict]:
        hour = datetime.now().hour
        for pattern in self.pattern_library:
            if hour in pattern["hours"]:
                return dict(pattern)
        return None


# Global singletons — names preserved for legacy callers in routes.py.
# These are heuristic estimators, not models.
traffic_flow_predictor = TrafficVolumeEstimator()
congestion_predictor = CongestionEstimator()
pattern_recognition = PatternRecognizer()
