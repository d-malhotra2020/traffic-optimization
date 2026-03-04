from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict
import asyncio
import logging
from datetime import datetime, timedelta

from ..simulation.traffic_simulator import TrafficMetrics

logger = logging.getLogger(__name__)

traffic_router = APIRouter()
optimization_router = APIRouter()
monitoring_router = APIRouter()

# Traffic Management Endpoints

@traffic_router.get("/intersections")
async def get_intersections(
    limit: int = Query(50, description="Maximum number of intersections to return"),
    city: Optional[str] = Query(None, description="Filter by city name")
):
    """Get traffic intersection data with real-time information"""
    try:
        from ..main import simulator, traffic_system
        
        # Get intersection data from simulator
        intersections = await simulator.get_intersections()
        
        # Filter by city if specified
        if city:
            # Get intersections from traffic system filtered by city
            city_intersections = await traffic_system.get_intersections_by_city(city)
            city_intersection_ids = {i.id for i in city_intersections}
            intersections = {
                k: v for k, v in intersections.items() 
                if k in city_intersection_ids
            }
        
        # Limit results
        intersection_items = list(intersections.items())[:limit]
        limited_intersections = dict(intersection_items)
        
        return {
            "total_intersections": len(intersections),
            "returned_count": len(limited_intersections),
            "intersections": limited_intersections,
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting intersections: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve intersection data")

@traffic_router.get("/intersections/{intersection_id}")
async def get_intersection_detail(intersection_id: str):
    """Get detailed information about a specific intersection"""
    try:
        from ..main import simulator, traffic_system
        
        intersections = await simulator.get_intersections()
        
        if intersection_id not in intersections:
            raise HTTPException(status_code=404, detail="Intersection not found")
        
        intersection_data = intersections[intersection_id]
        
        # Get traffic predictions
        from ...ml_models import traffic_flow_predictor
        
        volume_prediction = await traffic_flow_predictor.predict_traffic_volume(
            intersection_id, intersection_data
        )
        congestion_prediction = await traffic_flow_predictor.predict_congestion_level(
            intersection_data
        )
        timing_prediction = await traffic_flow_predictor.predict_optimal_timing(
            intersection_data
        )
        
        return {
            "intersection": intersection_data,
            "predictions": {
                "traffic_volume": {
                    "value": volume_prediction.prediction_value,
                    "confidence": volume_prediction.confidence,
                    "for_next_minutes": 30
                },
                "congestion_level": {
                    "value": congestion_prediction.prediction_value,
                    "confidence": congestion_prediction.confidence,
                    "severity": "high" if congestion_prediction.prediction_value > 0.7 else "moderate" if congestion_prediction.prediction_value > 0.4 else "low"
                },
                "optimal_timing": {
                    "recommended_green_time": timing_prediction.prediction_value,
                    "confidence": timing_prediction.confidence
                }
            },
            "last_updated": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting intersection detail: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve intersection details")

@traffic_router.get("/vehicles")
async def get_vehicles(limit: int = Query(100, description="Maximum number of vehicles to return")):
    """Get current vehicle positions and data"""
    try:
        from ..main import simulator
        
        vehicles = await simulator.get_vehicles()
        
        # Limit results
        vehicle_items = list(vehicles.items())[:limit]
        limited_vehicles = dict(vehicle_items)
        
        return {
            "total_vehicles": len(vehicles),
            "returned_count": len(limited_vehicles),
            "vehicles": limited_vehicles,
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting vehicles: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve vehicle data")

@traffic_router.get("/metrics")
async def get_traffic_metrics():
    """Get current traffic system metrics"""
    try:
        from ..main import simulator
        
        metrics = await simulator.get_current_metrics()
        
        return {
            "current_metrics": {
                "total_vehicles": metrics.total_vehicles,
                "average_speed": round(metrics.average_speed, 2),
                "congestion_level": round(metrics.congestion_level, 3),
                "throughput": metrics.throughput,
                "efficiency_improvement": round(metrics.efficiency_improvement, 2),
                "prediction_accuracy": round(metrics.prediction_accuracy, 3)
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting traffic metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve traffic metrics")

@traffic_router.get("/patterns")
async def get_traffic_patterns():
    """Get detected traffic patterns"""
    try:
        from ..main import simulator
        
        # Get current traffic data
        intersections = await simulator.get_intersections()
        
        # Detect current pattern
        from ...ml_models import pattern_recognition
        current_pattern = await pattern_recognition.detect_current_pattern(intersections)
        
        # Get all known patterns
        all_patterns = pattern_recognition.pattern_library
        
        return {
            "current_pattern": current_pattern,
            "all_patterns": all_patterns,
            "pattern_count": len(all_patterns),
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting traffic patterns: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve traffic patterns")

@traffic_router.post("/simulate")
async def simulate_scenario(
    duration_minutes: int = Query(10, description="Simulation duration in minutes"),
    traffic_multiplier: float = Query(1.0, description="Traffic volume multiplier")
):
    """Run traffic simulation scenario"""
    try:
        from ..main import simulator
        
        # Adjust simulation parameters
        original_speed = simulator.simulation_speed
        await simulator.set_simulation_speed(5.0)  # 5x speed for scenario
        
        # Run simulation for specified duration
        await asyncio.sleep(duration_minutes * 60 / 5.0)  # Account for 5x speed
        
        # Reset to original speed
        await simulator.set_simulation_speed(original_speed)
        
        # Get final metrics
        final_metrics = await simulator.get_current_metrics()
        
        return {
            "simulation_completed": True,
            "duration_minutes": duration_minutes,
            "traffic_multiplier": traffic_multiplier,
            "final_metrics": {
                "total_vehicles": final_metrics.total_vehicles,
                "average_speed": round(final_metrics.average_speed, 2),
                "congestion_level": round(final_metrics.congestion_level, 3),
                "efficiency_improvement": round(final_metrics.efficiency_improvement, 2)
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error running simulation: {e}")
        raise HTTPException(status_code=500, detail="Failed to run simulation scenario")

# Optimization Endpoints

@optimization_router.get("/optimize")
async def get_optimization_results(
    limit: int = Query(50, description="Maximum number of results to return")
):
    """Get recent traffic optimization results"""
    try:
        from ..main import optimizer
        
        results = await optimizer.get_optimization_results(limit)
        
        # Convert results to dict format
        optimization_data = []
        for result in results:
            optimization_data.append({
                "intersection_id": result.intersection_id,
                "new_timing": result.new_timing,
                "expected_improvement": round(result.expected_improvement, 2),
                "confidence": round(result.confidence, 3),
                "timestamp": result.timestamp,
                "time_ago_seconds": int(datetime.now().timestamp() - result.timestamp)
            })
        
        return {
            "optimization_results": optimization_data,
            "result_count": len(optimization_data),
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting optimization results: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve optimization results")

@optimization_router.post("/optimize/{intersection_id}")
async def manual_optimize_intersection(intersection_id: str):
    """Manually trigger optimization for a specific intersection"""
    try:
        from ..main import optimizer
        
        result = await optimizer.manual_optimize(intersection_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Intersection not found or optimization failed")
        
        return {
            "optimization_result": {
                "intersection_id": result.intersection_id,
                "new_timing": result.new_timing,
                "expected_improvement": round(result.expected_improvement, 2),
                "confidence": round(result.confidence, 3),
                "timestamp": result.timestamp
            },
            "message": f"Optimization completed for intersection {intersection_id}",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in manual optimization: {e}")
        raise HTTPException(status_code=500, detail="Failed to optimize intersection")

@optimization_router.get("/patterns")
async def get_optimization_patterns():
    """Get traffic patterns used for optimization"""
    try:
        from ..main import optimizer
        
        patterns = await optimizer.get_traffic_patterns()
        
        pattern_data = {}
        for pattern_id, pattern in patterns.items():
            pattern_data[pattern_id] = {
                "description": pattern.description,
                "peak_hours": pattern.peak_hours,
                "flow_direction": pattern.flow_direction,
                "intensity": pattern.intensity
            }
        
        return {
            "traffic_patterns": pattern_data,
            "pattern_count": len(pattern_data),
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting optimization patterns: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve optimization patterns")

@optimization_router.get("/stats")
async def get_optimization_stats():
    """Get optimization system statistics"""
    try:
        from ..main import optimizer
        
        stats = await optimizer.get_system_stats()
        
        return {
            "optimization_stats": stats,
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting optimization stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve optimization statistics")

@optimization_router.get("/hotspots")
async def get_congestion_hotspots():
    """Get predicted traffic congestion hotspots"""
    try:
        from ..main import simulator
        
        intersections = await simulator.get_intersections()
        from ...ml_models import congestion_predictor
        hotspots = await congestion_predictor.predict_congestion_hotspots(intersections)
        
        return {
            "congestion_hotspots": hotspots,
            "hotspot_count": len(hotspots),
            "prediction_accuracy": congestion_predictor.model_accuracy,
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting congestion hotspots: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve congestion hotspots")

# Monitoring Endpoints

@monitoring_router.get("/dashboard")
async def get_monitoring_dashboard():
    """Get comprehensive monitoring dashboard data"""
    try:
        from ..main import simulator, optimizer, traffic_system
        
        # Get current metrics
        current_metrics = await simulator.get_current_metrics()
        system_metrics = await traffic_system.get_system_metrics()
        optimization_stats = await optimizer.get_system_stats()
        
        # Get recent data
        intersections = await simulator.get_intersections()
        vehicles = await simulator.get_vehicles()
        
        # ML model metrics
        from ...ml_models import traffic_flow_predictor, congestion_predictor, pattern_recognition
        model_metrics = await traffic_flow_predictor.get_model_metrics()
        
        dashboard_data = {
            "system_overview": {
                "total_intersections": len(intersections),
                "total_vehicles": len(vehicles),
                "cities_served": system_metrics.get("cities_served", 5),
                "system_uptime": system_metrics.get("system_uptime", 0),
                "last_updated": datetime.now().isoformat()
            },
            "performance_metrics": {
                "average_speed": round(current_metrics.average_speed, 2),
                "congestion_level": round(current_metrics.congestion_level, 3),
                "throughput": current_metrics.throughput,
                "efficiency_improvement": round(current_metrics.efficiency_improvement, 2),
                "prediction_accuracy": round(current_metrics.prediction_accuracy, 3)
            },
            "optimization_status": {
                "total_optimizations": optimization_stats.get("total_optimizations", 0),
                "average_improvement": round(optimization_stats.get("average_improvement", 0), 2),
                "average_confidence": round(optimization_stats.get("average_confidence", 0), 3),
                "ml_model_accuracy": optimization_stats.get("ml_model_accuracy", 0.94)
            },
            "ml_models": {
                "traffic_predictor": {
                    "accuracy": round(model_metrics.accuracy, 3),
                    "training_samples": model_metrics.training_samples,
                    "last_trained": model_metrics.last_trained.isoformat()
                },
                "congestion_predictor": {
                    "accuracy": congestion_predictor.model_accuracy,
                    "model_type": congestion_predictor.model_type
                },
                "pattern_recognition": {
                    "accuracy": pattern_recognition.model_accuracy,
                    "known_patterns": len(pattern_recognition.pattern_library)
                }
            }
        }
        
        return dashboard_data
        
    except Exception as e:
        logger.error(f"Error getting monitoring dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve dashboard data")

@monitoring_router.get("/health")
async def get_system_health():
    """Get detailed system health status"""
    try:
        from ..main import traffic_system, simulator, optimizer
        
        # Get health status from all components
        system_health = await traffic_system.health_check()
        
        # Additional component checks
        simulator_running = simulator.running
        optimizer_running = optimizer.running
        
        health_status = {
            "overall_status": "healthy" if system_health["all_systems_operational"] else "degraded",
            "components": {
                **system_health["components"],
                "simulator": simulator_running,
                "optimizer": optimizer_running
            },
            "uptime_seconds": system_health["uptime_seconds"],
            "timestamp": datetime.now().isoformat()
        }
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system health")

@monitoring_router.get("/metrics/history")
async def get_metrics_history(minutes: int = Query(60, description="Minutes of history to retrieve")):
    """Get historical performance metrics"""
    try:
        from ..main import simulator
        
        history = await simulator.get_metrics_history(minutes)
        
        # Convert to serializable format
        metrics_data = []
        for i, metrics in enumerate(history):
            metrics_data.append({
                "timestamp": datetime.now().timestamp() - (len(history) - i - 1),
                "total_vehicles": metrics.total_vehicles,
                "average_speed": round(metrics.average_speed, 2),
                "congestion_level": round(metrics.congestion_level, 3),
                "throughput": metrics.throughput,
                "efficiency_improvement": round(metrics.efficiency_improvement, 2)
            })
        
        return {
            "metrics_history": metrics_data,
            "data_points": len(metrics_data),
            "time_span_minutes": minutes,
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting metrics history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics history")

@monitoring_router.get("/alerts")
async def get_system_alerts():
    """Get current system alerts and warnings"""
    try:
        from ..main import simulator
        
        # Get current metrics to check for alert conditions
        current_metrics = await simulator.get_current_metrics()
        intersections = await simulator.get_intersections()
        
        alerts = []
        
        # Check for high congestion
        if current_metrics.congestion_level > 0.8:
            alerts.append({
                "type": "high_congestion",
                "severity": "warning",
                "message": f"System congestion at {current_metrics.congestion_level:.1%}",
                "timestamp": datetime.now().isoformat()
            })
        
        # Check for low efficiency
        if current_metrics.efficiency_improvement < 5.0:
            alerts.append({
                "type": "low_efficiency",
                "severity": "info", 
                "message": f"Efficiency improvement below target: {current_metrics.efficiency_improvement:.1f}%",
                "timestamp": datetime.now().isoformat()
            })
        
        # Check for intersections with high queues
        high_queue_intersections = [
            int_id for int_id, data in intersections.items()
            if sum(data.get("queue_length", {}).values()) > 50
        ]
        
        if high_queue_intersections:
            alerts.append({
                "type": "high_queue_intersections",
                "severity": "warning",
                "message": f"{len(high_queue_intersections)} intersections with high queue lengths",
                "affected_intersections": high_queue_intersections[:5],  # Show first 5
                "timestamp": datetime.now().isoformat()
            })
        
        return {
            "alerts": alerts,
            "alert_count": len(alerts),
            "last_checked": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting system alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system alerts")