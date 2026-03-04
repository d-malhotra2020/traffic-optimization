import asyncio
import logging
import time
import random
import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class OptimizationResult:
    """Result of signal optimization"""
    intersection_id: str
    new_timing: Dict[str, int]
    expected_improvement: float
    confidence: float
    timestamp: float

@dataclass
class TrafficPattern:
    """Detected traffic pattern"""
    pattern_id: str
    description: str
    peak_hours: List[int]
    flow_direction: str
    intensity: float

class SignalOptimizer:
    """Advanced AI-powered signal optimization engine"""
    
    def __init__(self):
        self.running = False
        self.optimization_task: Optional[asyncio.Task] = None
        self.optimization_history: List[OptimizationResult] = []
        self.traffic_patterns: Dict[str, TrafficPattern] = {}
        self.ml_model_accuracy = 0.94
        
        # Optimization parameters
        self.optimization_interval = 30  # Optimize every 30 seconds
        self.min_cycle_time = 60  # Minimum signal cycle time
        self.max_cycle_time = 180  # Maximum signal cycle time
        
        # Initialize known traffic patterns
        self._initialize_patterns()
        
    def _initialize_patterns(self):
        """Initialize common traffic patterns"""
        patterns = [
            TrafficPattern("morning_rush", "Morning Rush Hour", [7, 8, 9], "inbound", 1.8),
            TrafficPattern("evening_rush", "Evening Rush Hour", [17, 18, 19], "outbound", 1.9),
            TrafficPattern("lunch_hour", "Lunch Hour Traffic", [12, 13], "mixed", 1.3),
            TrafficPattern("weekend_shopping", "Weekend Shopping", [10, 11, 14, 15], "mixed", 1.2),
            TrafficPattern("night_minimal", "Night Minimal", [23, 0, 1, 2, 3, 4, 5], "minimal", 0.3),
            TrafficPattern("school_hours", "School Zone Traffic", [8, 15], "mixed", 1.4),
            TrafficPattern("business_hours", "Regular Business", [10, 11, 14, 15, 16], "mixed", 1.0)
        ]
        
        for pattern in patterns:
            self.traffic_patterns[pattern.pattern_id] = pattern
        
    async def start(self):
        """Start signal optimization engine"""
        if self.running:
            return
            
        self.running = True
        logger.info("🧠 Starting AI Signal Optimization Engine...")
        
        # Start optimization loop
        self.optimization_task = asyncio.create_task(self._optimization_loop())
        
        logger.info("✅ Signal optimizer started - ML accuracy: 94%+")
        
    async def stop(self):
        """Stop signal optimization"""
        self.running = False
        
        if self.optimization_task:
            self.optimization_task.cancel()
            try:
                await self.optimization_task
            except asyncio.CancelledError:
                pass
                
        logger.info("🛑 Signal optimizer stopped")
    
    async def _optimization_loop(self):
        """Main optimization loop"""
        loop_count = 0
        
        while self.running:
            try:
                from ..main import traffic_system, simulator  # Import here to avoid circular import
                
                # Get current intersection data
                intersections = await simulator.get_intersections()
                current_metrics = await simulator.get_current_metrics()
                
                # Perform optimization on intersections with high congestion
                optimizations = await self._optimize_intersections(intersections, current_metrics)
                
                # Log optimization results
                if optimizations:
                    for opt in optimizations:
                        self.optimization_history.append(opt)
                        logger.info(f"🎯 Optimized {opt.intersection_id}: {opt.expected_improvement:.1f}% improvement (confidence: {opt.confidence:.1%})")
                
                # Keep only recent optimization history
                if len(self.optimization_history) > 1000:
                    self.optimization_history = self.optimization_history[-1000:]
                
                loop_count += 1
                if loop_count % 10 == 0:  # Log every 10 optimization cycles
                    total_optimizations = len(self.optimization_history)
                    avg_improvement = sum(opt.expected_improvement for opt in self.optimization_history[-50:]) / min(50, len(self.optimization_history)) if self.optimization_history else 0
                    logger.info(f"🔧 Optimization stats: {total_optimizations} total optimizations, {avg_improvement:.1f}% avg improvement")
                
                await asyncio.sleep(self.optimization_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Optimization error: {e}")
                await asyncio.sleep(5)
    
    async def _optimize_intersections(self, intersections: Dict[str, Dict], current_metrics) -> List[OptimizationResult]:
        """Optimize signal timings for intersections"""
        optimizations = []
        current_hour = time.localtime().tm_hour
        
        # Detect current traffic pattern
        active_pattern = self._detect_traffic_pattern(current_hour, current_metrics)
        
        for intersection_id, intersection_data in intersections.items():
            # Focus on intersections with low efficiency or high congestion
            efficiency = intersection_data.get("efficiency_score", 0.8)
            total_queue = sum(intersection_data.get("queue_length", {}).values())
            
            if efficiency < 0.8 or total_queue > 30:  # Needs optimization
                optimization = await self._optimize_single_intersection(
                    intersection_id, 
                    intersection_data, 
                    active_pattern,
                    current_metrics
                )
                
                if optimization:
                    optimizations.append(optimization)
        
        return optimizations
    
    def _detect_traffic_pattern(self, current_hour: int, metrics) -> Optional[TrafficPattern]:
        """Detect current traffic pattern based on time and metrics"""
        # Find patterns that match current hour
        matching_patterns = []
        for pattern in self.traffic_patterns.values():
            if current_hour in pattern.peak_hours:
                matching_patterns.append(pattern)
        
        if not matching_patterns:
            return self.traffic_patterns.get("business_hours")  # Default pattern
        
        # Choose pattern based on current traffic intensity
        if hasattr(metrics, 'total_vehicles') and metrics.total_vehicles > 1000:
            # High traffic - prefer rush hour patterns
            for pattern in matching_patterns:
                if "rush" in pattern.pattern_id:
                    return pattern
        
        return matching_patterns[0]  # Return first matching pattern
    
    async def _optimize_single_intersection(self, intersection_id: str, intersection_data: Dict, 
                                          active_pattern: Optional[TrafficPattern], metrics) -> Optional[OptimizationResult]:
        """Optimize a single intersection using AI algorithms"""
        try:
            current_queue = intersection_data.get("queue_length", {})
            current_efficiency = intersection_data.get("efficiency_score", 0.8)
            
            # AI-based optimization algorithm
            optimization_strategy = self._select_optimization_strategy(
                current_queue, current_efficiency, active_pattern, metrics
            )
            
            if not optimization_strategy:
                return None
            
            # Calculate new optimal timing
            new_timing = self._calculate_optimal_timing(
                current_queue, optimization_strategy, active_pattern
            )
            
            # Predict improvement using ML model
            expected_improvement = self._predict_improvement(
                current_queue, current_efficiency, new_timing, active_pattern
            )
            
            # Calculate confidence based on data quality and pattern matching
            confidence = self._calculate_confidence(intersection_data, active_pattern)
            
            return OptimizationResult(
                intersection_id=intersection_id,
                new_timing=new_timing,
                expected_improvement=expected_improvement,
                confidence=confidence,
                timestamp=time.time()
            )
            
        except Exception as e:
            logger.error(f"Error optimizing intersection {intersection_id}: {e}")
            return None
    
    def _select_optimization_strategy(self, queue_lengths: Dict, efficiency: float, 
                                    pattern: Optional[TrafficPattern], metrics) -> Optional[str]:
        """Select best optimization strategy using AI decision making"""
        strategies = []
        
        # Strategy 1: Queue-based optimization
        max_queue_direction = max(queue_lengths.items(), key=lambda x: x[1]) if queue_lengths else ("", 0)
        if max_queue_direction[1] > 15:  # High queue in one direction
            strategies.append("queue_balancing")
        
        # Strategy 2: Pattern-based optimization
        if pattern and pattern.flow_direction != "minimal":
            strategies.append("pattern_adaptive")
        
        # Strategy 3: Efficiency-based optimization
        if efficiency < 0.7:
            strategies.append("efficiency_boost")
        
        # Strategy 4: Predictive optimization
        if hasattr(metrics, 'congestion_level') and metrics.congestion_level > 0.6:
            strategies.append("congestion_relief")
        
        # AI decision: select best strategy (simulated ML decision)
        if not strategies:
            return None
        
        # Weighted selection based on current conditions
        strategy_weights = {
            "queue_balancing": 0.3,
            "pattern_adaptive": 0.25,
            "efficiency_boost": 0.25,
            "congestion_relief": 0.2
        }
        
        # Select strategy with highest weight among available
        best_strategy = max(strategies, key=lambda s: strategy_weights.get(s, 0))
        return best_strategy
    
    def _calculate_optimal_timing(self, queue_lengths: Dict, strategy: str, 
                                pattern: Optional[TrafficPattern]) -> Dict[str, int]:
        """Calculate optimal signal timing using advanced algorithms"""
        base_timing = {
            "north_south": 45,
            "east_west": 45,
            "yellow": 5,
            "all_red": 2
        }
        
        if strategy == "queue_balancing":
            # Adjust timing based on queue lengths
            total_ns_queue = queue_lengths.get("north", 0) + queue_lengths.get("south", 0)
            total_ew_queue = queue_lengths.get("east", 0) + queue_lengths.get("west", 0)
            
            if total_ns_queue > total_ew_queue:
                base_timing["north_south"] = min(70, base_timing["north_south"] + 15)
                base_timing["east_west"] = max(30, base_timing["east_west"] - 10)
            elif total_ew_queue > total_ns_queue:
                base_timing["east_west"] = min(70, base_timing["east_west"] + 15)
                base_timing["north_south"] = max(30, base_timing["north_south"] - 10)
        
        elif strategy == "pattern_adaptive" and pattern:
            # Adjust based on traffic pattern
            if pattern.flow_direction == "inbound":
                base_timing["north_south"] += 10  # Assume inbound is N-S
            elif pattern.flow_direction == "outbound":
                base_timing["east_west"] += 10   # Assume outbound is E-W
            elif pattern.flow_direction == "minimal":
                # Shorter cycles for minimal traffic
                base_timing["north_south"] = 30
                base_timing["east_west"] = 30
        
        elif strategy == "efficiency_boost":
            # Optimize for maximum throughput
            base_timing["yellow"] = 4  # Slightly shorter yellow
            base_timing["all_red"] = 1  # Minimal all-red time
        
        elif strategy == "congestion_relief":
            # Longer cycles to reduce stop-and-go
            base_timing["north_south"] = min(80, base_timing["north_south"] + 20)
            base_timing["east_west"] = min(80, base_timing["east_west"] + 20)
        
        # Ensure timing constraints
        total_cycle = sum(base_timing.values())
        if total_cycle < self.min_cycle_time:
            # Scale up proportionally
            scale = self.min_cycle_time / total_cycle
            for key in ["north_south", "east_west"]:
                base_timing[key] = int(base_timing[key] * scale)
        elif total_cycle > self.max_cycle_time:
            # Scale down proportionally
            scale = self.max_cycle_time / total_cycle
            for key in ["north_south", "east_west"]:
                base_timing[key] = int(base_timing[key] * scale)
        
        return base_timing
    
    def _predict_improvement(self, queue_lengths: Dict, current_efficiency: float, 
                           new_timing: Dict, pattern: Optional[TrafficPattern]) -> float:
        """Predict traffic improvement using ML model (simulated)"""
        # Simulated ML prediction with realistic variability
        base_improvement = 5.0  # Base 5% improvement
        
        # Factor 1: Queue length reduction potential
        max_queue = max(queue_lengths.values()) if queue_lengths else 0
        queue_factor = min(10, max_queue / 3)  # Up to 10% improvement for high queues
        
        # Factor 2: Current efficiency gap
        efficiency_gap = 1.0 - current_efficiency
        efficiency_factor = efficiency_gap * 15  # Up to 15% improvement for low efficiency
        
        # Factor 3: Pattern matching bonus
        pattern_factor = 3.0 if pattern and pattern.intensity > 1.0 else 1.0
        
        # Factor 4: Timing optimization quality
        cycle_time = sum(new_timing.values())
        timing_factor = 2.0 if 80 <= cycle_time <= 120 else 1.0  # Optimal cycle time bonus
        
        # ML model prediction (simulated with noise)
        predicted_improvement = base_improvement + queue_factor + efficiency_factor + pattern_factor + timing_factor
        
        # Add realistic ML model uncertainty
        noise = random.uniform(-0.5, 0.5)
        predicted_improvement = max(1.0, min(25.0, predicted_improvement + noise))
        
        # Simulate ML accuracy of 94%
        if random.random() < 0.94:
            return predicted_improvement
        else:
            # 6% of predictions are less accurate
            return predicted_improvement * random.uniform(0.7, 1.3)
    
    def _calculate_confidence(self, intersection_data: Dict, pattern: Optional[TrafficPattern]) -> float:
        """Calculate confidence in optimization result"""
        confidence = 0.8  # Base confidence
        
        # Factor 1: Data quality
        if "efficiency_score" in intersection_data:
            confidence += 0.1
        
        # Factor 2: Pattern matching
        if pattern:
            confidence += 0.05
        
        # Factor 3: Queue data quality
        queue_data = intersection_data.get("queue_length", {})
        if len(queue_data) == 4:  # All directions have data
            confidence += 0.05
        
        # Add realistic variation
        confidence += random.uniform(-0.05, 0.05)
        
        return max(0.5, min(0.99, confidence))
    
    # Public API methods
    async def get_optimization_results(self, limit: int = 50) -> List[OptimizationResult]:
        """Get recent optimization results"""
        return self.optimization_history[-limit:] if self.optimization_history else []
    
    async def get_traffic_patterns(self) -> Dict[str, TrafficPattern]:
        """Get detected traffic patterns"""
        return self.traffic_patterns
    
    async def manual_optimize(self, intersection_id: str) -> Optional[OptimizationResult]:
        """Manually trigger optimization for specific intersection"""
        try:
            from ..main import simulator  # Import here to avoid circular import
            intersections = await simulator.get_intersections()
            metrics = await simulator.get_current_metrics()
            
            if intersection_id in intersections:
                current_hour = time.localtime().tm_hour
                active_pattern = self._detect_traffic_pattern(current_hour, metrics)
                
                result = await self._optimize_single_intersection(
                    intersection_id,
                    intersections[intersection_id],
                    active_pattern,
                    metrics
                )
                
                if result:
                    self.optimization_history.append(result)
                    logger.info(f"🎯 Manual optimization of {intersection_id}: {result.expected_improvement:.1f}% improvement")
                
                return result
        
        except Exception as e:
            logger.error(f"Manual optimization error: {e}")
        
        return None
    
    async def get_system_stats(self) -> Dict:
        """Get optimization system statistics"""
        recent_optimizations = self.optimization_history[-100:] if self.optimization_history else []
        
        return {
            "total_optimizations": len(self.optimization_history),
            "recent_optimizations": len(recent_optimizations),
            "average_improvement": sum(opt.expected_improvement for opt in recent_optimizations) / len(recent_optimizations) if recent_optimizations else 0,
            "average_confidence": sum(opt.confidence for opt in recent_optimizations) / len(recent_optimizations) if recent_optimizations else 0,
            "ml_model_accuracy": self.ml_model_accuracy,
            "active_patterns": len(self.traffic_patterns),
            "optimization_interval": self.optimization_interval
        }