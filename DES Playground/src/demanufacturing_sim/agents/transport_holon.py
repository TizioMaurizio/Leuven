"""
TransportHolon: Autonomous agent representing AGV/conveyor transport.

Represents material handling equipment that moves items between stations:
- AGVs (Automated Guided Vehicles)
- Conveyors
- Mobile robots

Features:
- Travel time calculation based on distance
- Capacity constraints
- Congestion awareness
- Path planning integration
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum, auto
import random
import math


class TransportType(Enum):
    """Types of transport resources."""
    AGV = auto()
    CONVEYOR = auto()
    MOBILE_ROBOT = auto()
    MANUAL = auto()  # Human operator


class TransportState(Enum):
    """State of transport holon."""
    IDLE = auto()
    MOVING_TO_PICKUP = auto()
    PICKING_UP = auto()
    MOVING_TO_DROPOFF = auto()
    DROPPING_OFF = auto()
    BLOCKED = auto()
    MAINTENANCE = auto()


@dataclass
class TransportTask:
    """A transport task/request."""
    task_id: str
    product_holon_id: str
    pickup_location: str
    dropoff_location: str
    priority: float = 1.0
    timestamp: float = 0.0
    deadline: Optional[float] = None


@dataclass
class Location:
    """A location in the factory."""
    id: str
    name: str
    x: float
    y: float
    location_type: str  # station, buffer, gate, dock
    
    def distance_to(self, other: "Location") -> float:
        """Calculate Euclidean distance to another location."""
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)


@dataclass
class TransportHolon:
    """
    Holon representing an autonomous transport unit (AGV/conveyor).
    
    Attributes:
        id: Unique transport identifier
        transport_type: Type of transport
        state: Current transport state
        position: Current (x, y) position
        speed: Movement speed (distance units per minute)
        capacity: Number of items that can be carried
    """
    id: str
    transport_type: TransportType = TransportType.AGV
    
    # State
    state: TransportState = TransportState.IDLE
    current_task: Optional[TransportTask] = None
    
    # Position and movement
    position: Tuple[float, float] = (0.0, 0.0)
    target_position: Optional[Tuple[float, float]] = None
    home_position: Tuple[float, float] = (0.0, 0.0)
    speed: float = 10.0  # Distance units per minute
    
    # Capacity
    capacity: int = 1
    carried_items: List[str] = field(default_factory=list)  # Product holon IDs
    
    # Task queue
    task_queue: List[TransportTask] = field(default_factory=list)
    max_queue: int = 5
    
    # Statistics
    total_trips: int = 0
    total_distance: float = 0.0
    total_items_moved: int = 0
    idle_time: float = 0.0
    busy_time: float = 0.0
    blocked_time: float = 0.0
    last_state_change: float = 0.0
    
    # Health
    battery_level: float = 1.0  # For AGVs
    health_percentage: float = 1.0
    is_operational: bool = True
    
    # Path planning
    current_path: List[Tuple[float, float]] = field(default_factory=list)
    blocked_locations: List[str] = field(default_factory=list)
    
    # Known locations (reference to factory layout)
    _locations: Dict[str, Location] = field(default_factory=dict)
    
    @property
    def is_available(self) -> bool:
        """Check if transport is available for new tasks."""
        return (
            self.is_operational and
            self.state in (TransportState.IDLE,) and
            len(self.task_queue) < self.max_queue and
            len(self.carried_items) < self.capacity and
            self.battery_level > 0.1
        )
    
    @property
    def is_loaded(self) -> bool:
        """Check if carrying any items."""
        return len(self.carried_items) > 0
    
    @property
    def utilization(self) -> float:
        """Calculate utilization rate."""
        total = self.busy_time + self.idle_time + self.blocked_time
        return self.busy_time / total if total > 0 else 0.0
    
    def set_locations(self, locations: Dict[str, Location]) -> None:
        """Set the location reference map."""
        self._locations = locations
    
    def get_location(self, location_id: str) -> Optional[Location]:
        """Get a location by ID."""
        return self._locations.get(location_id)
    
    def distance_to(self, location_id: str) -> float:
        """Calculate distance to a location."""
        loc = self.get_location(location_id)
        if not loc:
            return float('inf')
        return math.sqrt(
            (self.position[0] - loc.x)**2 + 
            (self.position[1] - loc.y)**2
        )
    
    def estimate_travel_time(self, from_loc: str, to_loc: str) -> float:
        """Estimate travel time between two locations."""
        loc_from = self.get_location(from_loc)
        loc_to = self.get_location(to_loc)
        
        if not loc_from or not loc_to:
            return float('inf')
        
        distance = loc_from.distance_to(loc_to)
        
        # Add congestion factor (simple model)
        congestion_factor = 1.0 + len(self.blocked_locations) * 0.1
        
        return (distance / self.speed) * congestion_factor
    
    def estimate_task_time(self, task: TransportTask) -> float:
        """Estimate total time to complete a task."""
        # Time to reach pickup
        pickup_loc = self.get_location(task.pickup_location)
        if pickup_loc:
            to_pickup = math.sqrt(
                (self.position[0] - pickup_loc.x)**2 +
                (self.position[1] - pickup_loc.y)**2
            ) / self.speed
        else:
            to_pickup = 5.0  # Default estimate
        
        # Time between pickup and dropoff
        transit = self.estimate_travel_time(task.pickup_location, task.dropoff_location)
        
        # Loading/unloading time
        handling = 1.0  # 1 minute per operation
        
        return to_pickup + transit + handling * 2
    
    def request_transport(self, task: TransportTask) -> Dict[str, Any]:
        """
        Handle a transport request.
        
        Args:
            task: Transport task request
        
        Returns:
            Response dict with acceptance status and estimates
        """
        if not self.is_available and not (
            self.state == TransportState.IDLE and 
            len(self.task_queue) < self.max_queue
        ):
            return {
                "accepted": False,
                "transport_id": self.id,
                "reason": "not_available",
                "state": self.state.name
            }
        
        # Check if we can reach the pickup location
        if task.pickup_location in self.blocked_locations:
            return {
                "accepted": False,
                "transport_id": self.id,
                "reason": "pickup_blocked"
            }
        
        estimated_time = self.estimate_task_time(task)
        
        # Check deadline feasibility
        if task.deadline:
            if estimated_time > task.deadline - task.timestamp:
                return {
                    "accepted": False,
                    "transport_id": self.id,
                    "reason": "cannot_meet_deadline",
                    "estimated_time": estimated_time
                }
        
        # Accept the task
        self.task_queue.append(task)
        
        return {
            "accepted": True,
            "transport_id": self.id,
            "estimated_time": estimated_time,
            "queue_position": len(self.task_queue)
        }
    
    def start_next_task(self, current_time: float) -> Optional[TransportTask]:
        """Start the next task in queue."""
        if self.current_task or not self.task_queue:
            return None
        
        if not self.is_operational:
            return None
        
        self.current_task = self.task_queue.pop(0)
        self.state = TransportState.MOVING_TO_PICKUP
        self._update_time_tracking(current_time, "busy")
        
        # Set target position
        pickup_loc = self.get_location(self.current_task.pickup_location)
        if pickup_loc:
            self.target_position = (pickup_loc.x, pickup_loc.y)
        
        return self.current_task
    
    def update_position(self, delta_time: float, current_time: float) -> bool:
        """
        Update position based on movement.
        
        Args:
            delta_time: Time elapsed
            current_time: Current simulation time
        
        Returns:
            True if reached target
        """
        if not self.target_position:
            return True
        
        dx = self.target_position[0] - self.position[0]
        dy = self.target_position[1] - self.position[1]
        distance = math.sqrt(dx**2 + dy**2)
        
        if distance < 0.1:
            # Reached target
            self.position = self.target_position
            self.target_position = None
            return True
        
        # Move towards target
        move_distance = self.speed * delta_time * self.health_percentage
        if move_distance >= distance:
            self.position = self.target_position
            self.target_position = None
            self.total_distance += distance
            return True
        
        # Partial movement
        ratio = move_distance / distance
        self.position = (
            self.position[0] + dx * ratio,
            self.position[1] + dy * ratio
        )
        self.total_distance += move_distance
        
        # Drain battery (for AGVs)
        if self.transport_type == TransportType.AGV:
            self.battery_level -= 0.0001 * move_distance
            self.battery_level = max(0.0, self.battery_level)
        
        return False
    
    def arrive_at_pickup(self, current_time: float) -> None:
        """Handle arrival at pickup location."""
        self.state = TransportState.PICKING_UP
        # Actual pickup handled by SimPy process
    
    def complete_pickup(self, product_id: str, current_time: float) -> None:
        """Complete picking up an item."""
        self.carried_items.append(product_id)
        
        # Set target to dropoff
        if self.current_task:
            dropoff_loc = self.get_location(self.current_task.dropoff_location)
            if dropoff_loc:
                self.target_position = (dropoff_loc.x, dropoff_loc.y)
        
        self.state = TransportState.MOVING_TO_DROPOFF
    
    def arrive_at_dropoff(self, current_time: float) -> None:
        """Handle arrival at dropoff location."""
        self.state = TransportState.DROPPING_OFF
    
    def complete_dropoff(self, current_time: float) -> Optional[TransportTask]:
        """Complete dropping off items."""
        completed = self.current_task
        
        self.carried_items.clear()
        self.current_task = None
        self.total_trips += 1
        self.total_items_moved += 1
        
        if self.task_queue:
            self.state = TransportState.MOVING_TO_PICKUP
        else:
            self.state = TransportState.IDLE
            self._update_time_tracking(current_time, "idle")
        
        return completed
    
    def set_blocked(self, current_time: float, blocked_by: str = None) -> None:
        """Set transport as blocked."""
        self.state = TransportState.BLOCKED
        self._update_time_tracking(current_time, "blocked")
        if blocked_by:
            self.blocked_locations.append(blocked_by)
    
    def clear_blocked(self, current_time: float) -> None:
        """Clear blocked state."""
        if self.current_task:
            self.state = TransportState.MOVING_TO_PICKUP if not self.is_loaded else TransportState.MOVING_TO_DROPOFF
        else:
            self.state = TransportState.IDLE
        self._update_time_tracking(current_time, "busy" if self.current_task else "idle")
    
    def _update_time_tracking(self, current_time: float, new_state: str) -> None:
        """Update time tracking statistics."""
        elapsed = current_time - self.last_state_change
        
        if self.state == TransportState.IDLE:
            self.idle_time += elapsed
        elif self.state == TransportState.BLOCKED:
            self.blocked_time += elapsed
        else:
            self.busy_time += elapsed
        
        self.last_state_change = current_time
    
    def charge_battery(self, amount: float = 1.0) -> None:
        """Charge battery (for AGVs)."""
        self.battery_level = min(1.0, self.battery_level + amount)
    
    def get_state_snapshot(self) -> Dict[str, Any]:
        """Get current state as dictionary."""
        return {
            "id": self.id,
            "type": self.transport_type.name,
            "state": self.state.name,
            "position": self.position,
            "target": self.target_position,
            "is_loaded": self.is_loaded,
            "carried_items": list(self.carried_items),
            "queue_length": len(self.task_queue),
            "battery_level": self.battery_level,
            "utilization": self.utilization,
            "total_trips": self.total_trips,
            "total_distance": self.total_distance,
            "is_available": self.is_available
        }
