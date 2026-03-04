"""
Traffic Prediction ML Models
Simulates advanced ML models for traffic pattern prediction and optimization
"""

import random
import logging
import time
import asyncio
import math
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PredictionResult:
    """ML model prediction result"""
    prediction_type: str
    confidence: float
    prediction_value: float
    timestamp: float
    model_version: str = "v2.1.4"
    accuracy: float = 0.94

@dataclass
class ModelMetrics:
    """ML model performance metrics"""
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    training_samples: int
    last_trained: datetime

class TrafficFlowPredictor:
    """Advanced ML model for traffic flow prediction"""
    
    def __init__(self):
        self.model_accuracy = 0.94
        self.model_version = "v2.1.4"
        self.training_data_size = 2_500_000  # 2.5M training samples
        self.last_prediction_time = 0
        
        # Simulate model characteristics
        self.metrics = ModelMetrics(
            accuracy=0.942,
            precision=0.938,
            recall=0.945,
            f1_score=0.941,
            training_samples=self.training_data_size,
            last_trained=datetime.now() - timedelta(days=7)
        )
        
        logger.info(f"🤖 TrafficFlowPredictor initialized - Accuracy: {self.model_accuracy:.1%}")
    
    async def predict_traffic_volume(self, intersection_id: str, current_data: Dict, 
                                   forecast_minutes: int = 30) -> PredictionResult:
        """Predict traffic volume for next N minutes"""
        try:
            # Simulate TensorFlow/PyTorch model inference
            current_volume = sum(current_data.get('traffic_volume', {}).values())
            hour_of_day = datetime.now().hour
            day_of_week = datetime.now().weekday()
            
            # Time-based traffic patterns
            weekday_multiplier = 1.0 if day_of_week < 5 else 0.7  # Weekday vs weekend
            
            # Hour-based patterns
            if 7 <= hour_of_day <= 9 or 17 <= hour_of_day <= 19:  # Rush hours
                time_multiplier = 1.6
            elif 12 <= hour_of_day <= 13:  # Lunch
                time_multiplier = 1.2
            elif 22 <= hour_of_day or hour_of_day <= 5:  # Night
                time_multiplier = 0.3
            else:
                time_multiplier = 1.0
            
            # Predict volume with ML-like calculation
            base_prediction = current_volume * weekday_multiplier * time_multiplier
            
            # Add trend factor (simulate ML learning)
            trend_factor = 1.0 + random.uniform(-0.1, 0.1)
            predicted_volume = base_prediction * trend_factor
            
            # Add realistic ML model uncertainty
            if random.random() < self.model_accuracy:
                # Accurate prediction
                noise = random.uniform(-0.05, 0.05)
            else:
                # Less accurate prediction (6% of cases)
                noise = random.uniform(-0.2, 0.2)
            
            predicted_volume = max(0, predicted_volume * (1 + noise))
            
            # Calculate confidence based on data quality
            confidence = self._calculate_prediction_confidence(current_data, hour_of_day)
            
            return PredictionResult(
                prediction_type="traffic_volume",
                confidence=confidence,
                prediction_value=predicted_volume,
                timestamp=time.time(),
                model_version=self.model_version,
                accuracy=self.model_accuracy
            )
            
        except Exception as e:
            logger.error(f"Traffic volume prediction error: {e}")
            return PredictionResult("traffic_volume", 0.5, 0, time.time())
    
    async def predict_congestion_level(self, intersection_data: Dict) -> PredictionResult:
        """Predict congestion level (0-1 scale)"""
        try:
            queue_lengths = intersection_data.get('queue_length', {})
            traffic_volume = intersection_data.get('traffic_volume', {})
            
            # Calculate current congestion indicators
            total_queue = sum(queue_lengths.values()) if queue_lengths else 0
            total_volume = sum(traffic_volume.values()) if traffic_volume else 0
            
            # ML-based congestion prediction
            queue_factor = min(1.0, total_queue / 80)  # Normalize queue length
            volume_factor = min(1.0, total_volume / 300)  # Normalize volume
            
            # Time-based congestion patterns
            hour = datetime.now().hour
            time_factor = 0.8 if 7 <= hour <= 9 or 17 <= hour <= 19 else 0.4
            
            # Simulate deep learning prediction
            congestion_score = (queue_factor * 0.4 + volume_factor * 0.3 + time_factor * 0.3)
            
            # Add model uncertainty
            noise = random.uniform(-0.05, 0.05) if random.random() < 0.94 else random.uniform(-0.15, 0.15)
            congestion_score = max(0, min(1, congestion_score + noise))
            
            confidence = self._calculate_prediction_confidence(intersection_data)
            
            return PredictionResult(
                prediction_type="congestion_level",
                confidence=confidence,
                prediction_value=congestion_score,
                timestamp=time.time()
            )
            
        except Exception as e:
            logger.error(f"Congestion prediction error: {e}")
            return PredictionResult("congestion_level", 0.5, 0.5, time.time())
    
    async def predict_optimal_timing(self, intersection_data: Dict) -> PredictionResult:
        """Predict optimal signal timing"""
        try:
            queue_lengths = intersection_data.get('queue_length', {})
            
            # Calculate imbalance in traffic directions
            ns_queue = queue_lengths.get('north', 0) + queue_lengths.get('south', 0)
            ew_queue = queue_lengths.get('east', 0) + queue_lengths.get('west', 0)
            
            total_queue = ns_queue + ew_queue
            if total_queue == 0:
                return PredictionResult("optimal_timing", 0.7, 45, time.time())
            
            # ML algorithm to determine optimal green time
            ns_ratio = ns_queue / total_queue
            ew_ratio = ew_queue / total_queue
            
            # Base cycle time
            base_cycle = 90
            
            # Allocate time based on traffic demand (ML optimization)
            optimal_ns_time = int(base_cycle * 0.5 * (0.5 + ns_ratio))
            optimal_ns_time = max(25, min(70, optimal_ns_time))
            
            # Add ML model sophistication
            hour_factor = 1.1 if 7 <= datetime.now().hour <= 19 else 0.9
            optimal_ns_time = int(optimal_ns_time * hour_factor)
            
            confidence = self._calculate_prediction_confidence(intersection_data)
            
            return PredictionResult(
                prediction_type="optimal_timing",
                confidence=confidence,
                prediction_value=optimal_ns_time,
                timestamp=time.time()
            )
            
        except Exception as e:
            logger.error(f"Optimal timing prediction error: {e}")
            return PredictionResult("optimal_timing", 0.6, 45, time.time())
    
    def _calculate_prediction_confidence(self, data: Dict, hour: int = None) -> float:
        """Calculate confidence in prediction based on data quality"""
        confidence = 0.85  # Base confidence
        
        # Data completeness factor
        required_fields = ['queue_length', 'traffic_volume']
        present_fields = sum(1 for field in required_fields if field in data)
        completeness = present_fields / len(required_fields)
        confidence *= completeness
        
        # Time factor (more confident during normal hours)
        if hour is not None:
            if 6 <= hour <= 22:
                confidence *= 1.1
            else:
                confidence *= 0.9
        
        # Add realistic variation
        confidence += random.uniform(-0.05, 0.05)
        
        return max(0.5, min(0.99, confidence))
    
    async def get_model_metrics(self) -> ModelMetrics:
        """Get current model performance metrics"""
        return self.metrics
    
    async def retrain_model(self, new_data_samples: int = 50000) -> bool:
        """Simulate model retraining with new data"""
        logger.info(f"🔄 Retraining ML model with {new_data_samples} new samples...")
        
        # Simulate training time
        await asyncio.sleep(2)
        
        # Update metrics (simulate improved performance)
        self.metrics.training_samples += new_data_samples
        self.metrics.last_trained = datetime.now()
        
        # Slight accuracy improvement with more data
        accuracy_improvement = min(0.005, new_data_samples / 10_000_000)
        self.metrics.accuracy = min(0.99, self.metrics.accuracy + accuracy_improvement)
        self.model_accuracy = self.metrics.accuracy
        
        logger.info(f"✅ Model retrained - New accuracy: {self.model_accuracy:.1%}")
        return True


class CongestionPredictor:
    """Specialized ML model for congestion prediction"""
    
    def __init__(self):
        self.model_accuracy = 0.91
        self.model_type = "Ensemble (Random Forest + LSTM)"
        
    async def predict_congestion_hotspots(self, city_data: Dict) -> List[Dict]:
        """Predict traffic congestion hotspots"""
        hotspots = []
        
        # Simulate ML identification of congestion patterns
        high_traffic_intersections = [
            int_id for int_id, data in city_data.items()
            if sum(data.get('queue_length', {}).values()) > 20
        ]
        
        for intersection_id in random.sample(high_traffic_intersections, 
                                           min(10, len(high_traffic_intersections))):
            hotspot = {
                "intersection_id": intersection_id,
                "predicted_congestion": random.uniform(0.7, 0.95),
                "confidence": random.uniform(0.85, 0.95),
                "estimated_duration": random.randint(15, 45),  # minutes
                "severity": random.choice(["moderate", "high", "severe"])
            }
            hotspots.append(hotspot)
        
        return sorted(hotspots, key=lambda x: x["predicted_congestion"], reverse=True)


class PatternRecognitionModel:
    """ML model for detecting traffic patterns"""
    
    def __init__(self):
        self.model_accuracy = 0.96
        self.pattern_library = self._initialize_patterns()
    
    def _initialize_patterns(self) -> List[Dict]:
        """Initialize known traffic patterns"""
        return [
            {
                "name": "Morning Rush",
                "hours": [7, 8, 9],
                "direction_bias": "inbound",
                "intensity_multiplier": 1.8,
                "confidence": 0.95
            },
            {
                "name": "Evening Rush", 
                "hours": [17, 18, 19],
                "direction_bias": "outbound",
                "intensity_multiplier": 1.9,
                "confidence": 0.94
            },
            {
                "name": "Lunch Hour",
                "hours": [12, 13],
                "direction_bias": "mixed",
                "intensity_multiplier": 1.3,
                "confidence": 0.88
            },
            {
                "name": "Weekend Shopping",
                "hours": [10, 11, 14, 15, 16],
                "direction_bias": "commercial_districts",
                "intensity_multiplier": 1.4,
                "confidence": 0.86
            }
        ]
    
    async def detect_current_pattern(self, traffic_data: Dict) -> Optional[Dict]:
        """Detect current traffic pattern using ML"""
        current_hour = datetime.now().hour
        
        # Find matching patterns
        matching_patterns = [
            pattern for pattern in self.pattern_library
            if current_hour in pattern["hours"]
        ]
        
        if not matching_patterns:
            return None
        
        # Select best match based on current traffic intensity
        total_volume = sum(
            sum(intersection_data.get('traffic_volume', {}).values())
            for intersection_data in traffic_data.values()
        )
        
        normalized_volume = total_volume / len(traffic_data) if traffic_data else 0
        
        # ML pattern matching
        best_pattern = None
        best_score = 0
        
        for pattern in matching_patterns:
            # Calculate pattern match score
            expected_volume = pattern["intensity_multiplier"] * 50  # Base expected volume
            volume_match = 1 - abs(normalized_volume - expected_volume) / expected_volume
            time_match = 1.0  # Already filtered by hour
            
            pattern_score = (volume_match * 0.6 + time_match * 0.4) * pattern["confidence"]
            
            if pattern_score > best_score:
                best_score = pattern_score
                best_pattern = pattern.copy()
                best_pattern["match_score"] = pattern_score
        
        return best_pattern


# Global ML model instances
traffic_flow_predictor = TrafficFlowPredictor()
congestion_predictor = CongestionPredictor()
pattern_recognition = PatternRecognitionModel()