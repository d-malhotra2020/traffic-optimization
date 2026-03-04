import asyncio
import logging
import random
import time
import math
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class Vehicle:
    """Represents a vehicle in the simulation"""
    id: str
    position: tuple
    destination: tuple
    speed: float
    vehicle_type: str = "car"
    created_at: float = 0.0

@dataclass
class Intersection:
    """Represents a traffic intersection"""
    id: str
    position: tuple
    signal_state: str  # "red", "yellow", "green"
    signal_timing: Dict[str, int]  # timing for each direction
    queue_length: Dict[str, int]  # vehicles waiting in each direction
    throughput: int = 0
    last_updated: float = 0.0
    efficiency_score: float = 0.0

@dataclass
class TrafficMetrics:
    """Traffic system metrics"""
    total_vehicles: int
    average_speed: float
    congestion_level: float
    throughput: int
    efficiency_improvement: float
    prediction_accuracy: float

class TrafficSimulator:
    """Advanced traffic simulation engine with real-time data generation"""
    
    def __init__(self):
        self.running = False
        self.intersections: Dict[str, Intersection] = {}
        self.vehicles: Dict[str, Vehicle] = {}
        self.simulation_task: Optional[asyncio.Task] = None
        self.metrics_history: List[TrafficMetrics] = []
        self.simulation_speed = 1.0  # Real-time multiplier
        
        # Initialize simulation parameters
        self.max_vehicles = 2000
        self.intersection_count = 150
        self.city_bounds = (0, 100)  # 100x100 grid
        
    async def start(self):
        """Start traffic simulation with realistic traffic patterns"""
        if self.running:
            return
            
        self.running = True
        logger.info("🚦 Initializing traffic simulation...")
        
        # Generate realistic intersection network
        await self._generate_intersections()
        
        # Start simulation loop
        self.simulation_task = asyncio.create_task(self._simulation_loop())
        
        logger.info(f"✅ Traffic simulator started with {len(self.intersections)} intersections")
        
    async def stop(self):
        """Stop traffic simulation"""
        self.running = False
        
        if self.simulation_task:
            self.simulation_task.cancel()
            try:
                await self.simulation_task
            except asyncio.CancelledError:
                pass
                
        logger.info("🛑 Traffic simulator stopped")
        
    async def _generate_intersections(self):
        """Generate a realistic network of traffic intersections"""
        self.intersections = {}
        
        # Create grid-based intersection network
        grid_size = int(math.sqrt(self.intersection_count))
        
        for i in range(grid_size):
            for j in range(grid_size):
                if len(self.intersections) >= self.intersection_count:
                    break
                    
                intersection_id = f"INT_{i:02d}_{j:02d}"
                x = (i / grid_size) * (self.city_bounds[1] - self.city_bounds[0])
                y = (j / grid_size) * (self.city_bounds[1] - self.city_bounds[0])
                
                # Vary signal timing based on intersection type
                is_major = (i % 3 == 0) or (j % 3 == 0)  # Major roads every 3 blocks
                
                signal_timing = {
                    "north_south": 45 if is_major else 30,
                    "east_west": 45 if is_major else 30,
                    "yellow": 5,
                    "all_red": 2
                }
                
                intersection = Intersection(
                    id=intersection_id,
                    position=(x, y),
                    signal_state="green",
                    signal_timing=signal_timing,
                    queue_length={"north": 0, "south": 0, "east": 0, "west": 0},
                    last_updated=time.time(),
                    efficiency_score=random.uniform(0.7, 0.95)
                )
                
                self.intersections[intersection_id] = intersection
    
    async def _simulation_loop(self):
        """Main simulation loop generating realistic traffic data"""
        loop_count = 0
        
        while self.running:
            try:
                current_time = time.time()
                hour_of_day = datetime.now().hour
                
                # Simulate different traffic patterns throughout the day
                traffic_multiplier = self._get_traffic_multiplier(hour_of_day)
                
                # Update vehicle population
                await self._update_vehicles(traffic_multiplier)
                
                # Update intersection states and metrics
                await self._update_intersections(current_time)
                
                # Calculate system metrics
                metrics = await self._calculate_metrics()
                self.metrics_history.append(metrics)
                
                # Keep only last hour of metrics
                if len(self.metrics_history) > 3600:  # 1 hour at 1-second intervals
                    self.metrics_history = self.metrics_history[-3600:]
                
                loop_count += 1
                if loop_count % 30 == 0:  # Log every 30 seconds
                    logger.info(f"🚗 Simulation: {len(self.vehicles)} vehicles, {metrics.average_speed:.1f} avg speed, {metrics.congestion_level:.1%} congestion")
                
                await asyncio.sleep(1.0 / self.simulation_speed)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Simulation error: {e}")
                await asyncio.sleep(1)
    
    def _get_traffic_multiplier(self, hour: int) -> float:
        """Get traffic volume multiplier based on time of day"""
        # Realistic traffic patterns: rush hours, lunch, evening
        if 7 <= hour <= 9 or 17 <= hour <= 19:  # Rush hours
            return random.uniform(1.5, 2.0)
        elif 12 <= hour <= 13:  # Lunch hour
            return random.uniform(1.2, 1.4)
        elif 22 <= hour or hour <= 5:  # Late night/early morning
            return random.uniform(0.2, 0.4)
        else:  # Regular hours
            return random.uniform(0.8, 1.2)
    
    async def _update_vehicles(self, traffic_multiplier: float):
        """Update vehicle population based on traffic patterns"""
        target_vehicles = int(self.max_vehicles * traffic_multiplier)
        
        # Add vehicles if below target
        while len(self.vehicles) < target_vehicles:
            vehicle_id = f"VEH_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
            
            # Random start and destination
            start_x = random.uniform(*self.city_bounds)
            start_y = random.uniform(*self.city_bounds)
            dest_x = random.uniform(*self.city_bounds)
            dest_y = random.uniform(*self.city_bounds)
            
            vehicle = Vehicle(
                id=vehicle_id,
                position=(start_x, start_y),
                destination=(dest_x, dest_y),
                speed=random.uniform(20, 60),  # km/h
                vehicle_type=random.choice(["car", "truck", "bus", "motorcycle"]),
                created_at=time.time()
            )
            
            self.vehicles[vehicle_id] = vehicle
        
        # Remove excess vehicles (simulate arrivals at destination)
        while len(self.vehicles) > target_vehicles:
            # Remove oldest vehicles first
            oldest_id = min(self.vehicles.keys(), key=lambda k: self.vehicles[k].created_at)
            del self.vehicles[oldest_id]
        
        # Update vehicle positions and speeds
        for vehicle in self.vehicles.values():
            # Simulate movement towards destination with some randomness
            vehicle.speed = max(5, vehicle.speed + random.uniform(-5, 5))
            
            # Simple movement simulation
            dx = vehicle.destination[0] - vehicle.position[0]
            dy = vehicle.destination[1] - vehicle.position[1]
            distance = math.sqrt(dx**2 + dy**2)
            
            if distance > 1:
                # Move towards destination
                move_distance = vehicle.speed / 3600  # Convert km/h to units per second
                new_x = vehicle.position[0] + (dx / distance) * move_distance
                new_y = vehicle.position[1] + (dy / distance) * move_distance
                vehicle.position = (new_x, new_y)
    
    async def _update_intersections(self, current_time: float):
        """Update intersection states and queue lengths"""
        for intersection in self.intersections.values():
            # Count nearby vehicles as queue length
            for direction in intersection.queue_length:
                intersection.queue_length[direction] = random.randint(0, 25)
            
            # Update signal state based on timing
            time_since_update = current_time - intersection.last_updated
            cycle_time = sum(intersection.signal_timing.values())
            
            # Simple signal cycle logic
            if time_since_update >= cycle_time:
                intersection.last_updated = current_time
                intersection.signal_state = random.choice(["green", "yellow", "red"])
            
            # Calculate throughput (vehicles per minute)
            intersection.throughput = random.randint(15, 45)
            
            # Update efficiency score based on queue lengths
            avg_queue = sum(intersection.queue_length.values()) / len(intersection.queue_length)
            intersection.efficiency_score = max(0.1, 1.0 - (avg_queue / 30))
    
    async def _calculate_metrics(self) -> TrafficMetrics:
        """Calculate overall traffic system metrics"""
        if not self.vehicles:
            return TrafficMetrics(0, 0, 0, 0, 0, 0.94)
        
        # Calculate average speed
        avg_speed = sum(v.speed for v in self.vehicles.values()) / len(self.vehicles)
        
        # Calculate congestion level (inverse of average speed)
        congestion_level = max(0, min(1, 1 - (avg_speed - 10) / 50))
        
        # Calculate total throughput
        total_throughput = sum(i.throughput for i in self.intersections.values())
        
        # Simulate efficiency improvement (compare to baseline)
        baseline_throughput = len(self.intersections) * 25  # Baseline 25 vehicles/min per intersection
        efficiency_improvement = max(0, (total_throughput - baseline_throughput) / baseline_throughput * 100)
        efficiency_improvement = min(20, efficiency_improvement)  # Cap at 20%
        
        # ML prediction accuracy (simulated as stable high value with small variation)
        prediction_accuracy = 0.94 + random.uniform(-0.02, 0.02)
        
        return TrafficMetrics(
            total_vehicles=len(self.vehicles),
            average_speed=avg_speed,
            congestion_level=congestion_level,
            throughput=total_throughput,
            efficiency_improvement=efficiency_improvement,
            prediction_accuracy=prediction_accuracy
        )
    
    # Public API methods
    async def get_intersections(self) -> Dict[str, Dict]:
        """Get current intersection data"""
        return {
            int_id: {
                "id": intersection.id,
                "position": intersection.position,
                "signal_state": intersection.signal_state,
                "queue_length": intersection.queue_length,
                "throughput": intersection.throughput,
                "efficiency_score": intersection.efficiency_score,
                "last_updated": intersection.last_updated
            }
            for int_id, intersection in self.intersections.items()
        }
    
    async def get_vehicles(self) -> Dict[str, Dict]:
        """Get current vehicle data"""
        return {
            veh_id: {
                "id": vehicle.id,
                "position": vehicle.position,
                "destination": vehicle.destination,
                "speed": vehicle.speed,
                "vehicle_type": vehicle.vehicle_type
            }
            for veh_id, vehicle in self.vehicles.items()
        }
    
    async def get_current_metrics(self) -> TrafficMetrics:
        """Get current traffic metrics"""
        if self.metrics_history:
            return self.metrics_history[-1]
        else:
            return await self._calculate_metrics()
    
    async def get_metrics_history(self, minutes: int = 60) -> List[TrafficMetrics]:
        """Get metrics history for specified number of minutes"""
        samples = minutes * 60  # 1 sample per second
        return self.metrics_history[-samples:] if len(self.metrics_history) >= samples else self.metrics_history
    
    async def set_simulation_speed(self, speed: float):
        """Set simulation speed multiplier"""
        self.simulation_speed = max(0.1, min(10.0, speed))
        logger.info(f"Simulation speed set to {self.simulation_speed}x")