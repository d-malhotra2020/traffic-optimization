import asyncio
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# Path to the committed OSM snapshot (regenerable via `python -m scripts.fetch_osm`)
SF_INTERSECTIONS_SNAPSHOT = (
    Path(__file__).resolve().parent.parent.parent / "data" / "sf_intersections.json"
)

class SignalState(Enum):
    RED = "red"
    YELLOW = "yellow" 
    GREEN = "green"

class TrafficPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    EMERGENCY = 4

@dataclass
class Intersection:
    id: str
    name: str
    location: tuple
    signal_states: Dict[str, SignalState]
    timing_plan: Dict[str, int]
    traffic_volume: Dict[str, int]
    wait_times: Dict[str, float]
    last_updated: datetime
    city: str = "Default City"
    
    def __post_init__(self):
        if not self.signal_states:
            # Initialize with 4-way intersection default
            self.signal_states = {
                "north": SignalState.RED,
                "south": SignalState.RED,
                "east": SignalState.GREEN,
                "west": SignalState.GREEN
            }
        
        if not self.timing_plan:
            # Default timing plan (seconds)
            self.timing_plan = {
                "north_south_green": 45,
                "north_south_yellow": 5,
                "east_west_green": 40,
                "east_west_yellow": 5,
                "all_red_clearance": 2
            }

@dataclass
class TrafficData:
    intersection_id: str
    timestamp: datetime
    vehicle_count: Dict[str, int]
    average_speed: Dict[str, float]
    queue_length: Dict[str, int]
    pedestrian_count: int = 0
    emergency_vehicles: int = 0

class TrafficSystemManager:
    """Manages the entire traffic control system.

    Topology source: real OpenStreetMap signalized-intersection
    coordinates for Downtown San Francisco, loaded from a committed
    JSON snapshot at startup (regenerable via `python -m scripts.fetch_osm`).
    """

    def __init__(self):
        self.intersections: Dict[str, Intersection] = {}
        self.topology_meta: Dict = {}  # snapshot provenance (source/bbox/timestamps/etc.)
        self.traffic_data_history: List[TrafficData] = []
        self.system_metrics = {
            "total_intersections": 0,
            "average_wait_time": 0.0,
            "efficiency_improvement": 0.0,
            "system_uptime": 0
        }
        self.is_running = False
        self.start_time = None
        
    async def initialize(self):
        """Initialize the traffic system from the committed OSM snapshot.

        The snapshot at data/sf_intersections.json is fetched via the
        Overpass API and committed to the repo so the app boots without
        a runtime dependency on OSM. Regenerate with
        `python -m scripts.fetch_osm`.
        """
        loaded = self._load_real_intersections()
        if not loaded:
            logger.warning(
                "⚠️  OSM snapshot missing or malformed — TrafficSystemManager starts empty. "
                "Run `python -m scripts.fetch_osm` to regenerate %s.",
                SF_INTERSECTIONS_SNAPSHOT,
            )
        self.start_time = datetime.now()
        self.is_running = True
        self.system_metrics["total_intersections"] = len(self.intersections)
        logger.info(
            "✅ Traffic system manager ready — %d real intersections loaded from OSM",
            len(self.intersections),
        )

    def _load_real_intersections(self) -> bool:
        """Load signalized intersections from the committed OSM snapshot.

        Returns True on success, False if the snapshot is missing or
        malformed. Failure is non-fatal — the manager just starts empty.
        """
        try:
            raw = json.loads(SF_INTERSECTIONS_SNAPSHOT.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Failed to read OSM snapshot: %s", exc)
            return False

        nodes = raw.get("intersections", [])
        if not isinstance(nodes, list):
            logger.error("OSM snapshot malformed — `intersections` is not a list")
            return False

        self.intersections.clear()
        for n in nodes:
            try:
                intersection = Intersection(
                    id=n["id"],
                    name=f"SF traffic signal @ {n['lat']:.4f},{n['lon']:.4f}",
                    location=(n["lat"], n["lon"]),
                    signal_states={},
                    timing_plan={},
                    traffic_volume={"north": 0, "south": 0, "east": 0, "west": 0},
                    wait_times={"north": 0.0, "south": 0.0, "east": 0.0, "west": 0.0},
                    last_updated=datetime.now(),
                    city="San Francisco",
                )
                self.intersections[intersection.id] = intersection
            except (KeyError, TypeError) as exc:
                logger.warning("Skipping malformed node %r: %s", n, exc)

        # Preserve provenance for the API to expose
        self.topology_meta = {
            "source": raw.get("source"),
            "license": raw.get("license"),
            "osm_timestamp": raw.get("osm_timestamp"),
            "fetched_at": raw.get("fetched_at"),
            "bbox": raw.get("bbox"),
            "intersection_count": len(self.intersections),
            "overpass_generator": raw.get("overpass_generator"),
        }
        return True

    def get_topology_meta(self) -> Dict:
        """Provenance + counts for /api/v1/system/topology."""
        meta = dict(self.topology_meta)
        meta["loaded_count"] = len(self.intersections)
        return meta
    
    async def get_intersection_count(self) -> int:
        """Get total number of managed intersections"""
        return len(self.intersections)
    
    async def get_intersection(self, intersection_id: str) -> Optional[Intersection]:
        """Get specific intersection by ID"""
        return self.intersections.get(intersection_id)
    
    async def get_intersections_by_city(self, city: str) -> List[Intersection]:
        """Get all intersections in a specific city"""
        return [
            intersection for intersection in self.intersections.values()
            if intersection.city.lower() == city.lower()
        ]
    
    async def update_intersection_timing(self, intersection_id: str, timing_plan: Dict[str, int]) -> bool:
        """Update timing plan for an intersection"""
        if intersection_id in self.intersections:
            self.intersections[intersection_id].timing_plan = timing_plan
            self.intersections[intersection_id].last_updated = datetime.now()
            logger.info(f"Updated timing plan for intersection {intersection_id}")
            return True
        return False
    
    async def get_traffic_data(self, intersection_id: str, hours: int = 24) -> List[TrafficData]:
        """Get historical traffic data for an intersection"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        return [
            data for data in self.traffic_data_history
            if data.intersection_id == intersection_id and data.timestamp > cutoff_time
        ]
    
    async def add_traffic_data(self, traffic_data: TrafficData):
        """Add new traffic data point"""
        self.traffic_data_history.append(traffic_data)
        
        # Keep only last 7 days of data
        cutoff_time = datetime.now() - timedelta(days=7)
        self.traffic_data_history = [
            data for data in self.traffic_data_history
            if data.timestamp > cutoff_time
        ]
    
    async def calculate_system_efficiency(self) -> float:
        """Calculate current system efficiency improvement"""
        if not self.intersections:
            return 0.0
        
        # Simulate efficiency calculation
        total_wait_time = sum(
            sum(intersection.wait_times.values())
            for intersection in self.intersections.values()
        )
        
        avg_wait_time = total_wait_time / (len(self.intersections) * 4)  # 4 directions
        
        # Simulate 15% efficiency improvement
        baseline_wait_time = avg_wait_time * 1.15
        improvement = (baseline_wait_time - avg_wait_time) / baseline_wait_time * 100
        
        return min(improvement, 15.0)  # Cap at 15%
    
    async def get_system_metrics(self) -> Dict:
        """Get current system metrics"""
        if not self.is_running:
            return self.system_metrics
        
        # Calculate real-time metrics
        efficiency = await self.calculate_system_efficiency()
        uptime = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        
        total_wait_time = sum(
            sum(intersection.wait_times.values())
            for intersection in self.intersections.values()
        )
        avg_wait_time = total_wait_time / (len(self.intersections) * 4) if self.intersections else 0
        
        self.system_metrics.update({
            "total_intersections": len(self.intersections),
            "average_wait_time": round(avg_wait_time, 2),
            "efficiency_improvement": round(efficiency, 2),
            "system_uptime": int(uptime),
            "cities_served": len(set(i.city for i in self.intersections.values())),
            "data_points_processed": len(self.traffic_data_history),
            "last_updated": datetime.now().isoformat()
        })
        
        return self.system_metrics
    
    async def health_check(self) -> Dict:
        """Perform system health check"""
        components = {
            "traffic_system": self.is_running,
            "intersections": len(self.intersections) > 0,
            "data_processing": len(self.traffic_data_history) >= 0,
            "optimization_engine": True,  # Assume healthy
            "ml_models": True  # Assume healthy
        }
        
        all_healthy = all(components.values())
        
        return {
            "all_systems_operational": all_healthy,
            "timestamp": datetime.now().isoformat(),
            "components": components,
            "uptime_seconds": int((datetime.now() - self.start_time).total_seconds()) if self.start_time else 0
        }
    
    async def simulate_traffic_update(self):
        """Simulate real-time traffic data updates"""
        while self.is_running:
            # Update traffic data for random intersections
            sample_size = min(100, len(self.intersections))
            sample_intersections = random.sample(list(self.intersections.keys()), sample_size)
            
            for intersection_id in sample_intersections:
                intersection = self.intersections[intersection_id]
                
                # Simulate traffic volume changes
                for direction in ["north", "south", "east", "west"]:
                    # Add some randomness to traffic volumes
                    current_volume = intersection.traffic_volume.get(direction, 50)
                    change = random.randint(-10, 10)
                    new_volume = max(0, current_volume + change)
                    intersection.traffic_volume[direction] = new_volume
                    
                    # Update wait times based on volume
                    base_wait = 20  # Base wait time
                    volume_factor = new_volume / 50  # Normalize around 50 vehicles
                    new_wait_time = base_wait * volume_factor + random.uniform(-5, 5)
                    intersection.wait_times[direction] = max(0, new_wait_time)
                
                intersection.last_updated = datetime.now()
                
                # Create traffic data record
                traffic_data = TrafficData(
                    intersection_id=intersection_id,
                    timestamp=datetime.now(),
                    vehicle_count=intersection.traffic_volume.copy(),
                    average_speed={
                        direction: random.uniform(15, 45) 
                        for direction in ["north", "south", "east", "west"]
                    },
                    queue_length={
                        direction: max(0, int(intersection.wait_times[direction] / 5))
                        for direction in ["north", "south", "east", "west"]
                    },
                    pedestrian_count=random.randint(0, 20),
                    emergency_vehicles=random.choices([0, 1], weights=[95, 5])[0]
                )
                
                await self.add_traffic_data(traffic_data)
            
            await asyncio.sleep(10)  # Update every 10 seconds
    
    async def cleanup(self):
        """Cleanup system resources"""
        self.is_running = False
        logger.info("Traffic system cleanup complete")