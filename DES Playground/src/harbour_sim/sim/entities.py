"""
Entity definitions for the harbour simulation.

Contains dataclasses for Container, Ship, and Truck entities with their
state tracking and lifecycle management.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Tuple, List
import random


class ContainerState(Enum):
    """Lifecycle states for a container."""
    CREATED = auto()      # On ship, not yet unloaded
    UNLOADING = auto()    # Being unloaded by crane
    IN_YARD = auto()      # Stored in yard
    READY_FOR_PICKUP = auto()  # Assigned to truck, waiting
    LOADING_TRUCK = auto()  # Being loaded onto truck
    ON_TRUCK = auto()     # Loaded on truck
    EXITED = auto()       # Left the system


@dataclass
class Container:
    """
    A shipping container entity.
    
    Attributes:
        id: Unique container identifier
        ship_id: ID of the ship this container came from
        state: Current lifecycle state
        created_time: Simulation time when container was created
        unload_start_time: When unloading started
        yard_arrival_time: When container arrived in yard
        pickup_request_time: When truck requested this container
        exit_time: When container left the system
        yard_position: (x, y, z) position in yard grid
        color: RGB color for visualization
    """
    id: int
    ship_id: int
    state: ContainerState = ContainerState.CREATED
    created_time: float = 0.0
    unload_start_time: Optional[float] = None
    yard_arrival_time: Optional[float] = None
    pickup_request_time: Optional[float] = None
    exit_time: Optional[float] = None
    yard_position: Optional[Tuple[int, int, int]] = None  # (x, y, stack_level)
    color: Tuple[int, int, int] = field(default_factory=lambda: (
        random.randint(50, 200),
        random.randint(50, 200),
        random.randint(50, 200)
    ))
    
    @property
    def dwell_time(self) -> Optional[float]:
        """Time container spent in yard (if exited)."""
        if self.yard_arrival_time is not None and self.exit_time is not None:
            return self.exit_time - self.yard_arrival_time
        return None
    
    @property
    def total_time(self) -> Optional[float]:
        """Total time from creation to exit."""
        if self.exit_time is not None:
            return self.exit_time - self.created_time
        return None
    
    def transition_to(self, new_state: ContainerState, time: float) -> None:
        """
        Transition container to a new state with timestamp recording.
        
        Args:
            new_state: The target state
            time: Current simulation time
        """
        self.state = new_state
        
        if new_state == ContainerState.UNLOADING:
            self.unload_start_time = time
        elif new_state == ContainerState.IN_YARD:
            self.yard_arrival_time = time
        elif new_state == ContainerState.READY_FOR_PICKUP:
            self.pickup_request_time = time
        elif new_state == ContainerState.EXITED:
            self.exit_time = time


class ShipState(Enum):
    """States for a ship in the harbour."""
    ARRIVING = auto()      # Approaching harbour
    WAITING_BERTH = auto() # Waiting for berth
    BERTHED = auto()       # At berth
    UNLOADING = auto()     # Being unloaded
    DEPARTING = auto()     # Leaving harbour
    DEPARTED = auto()      # Left the system


@dataclass
class Ship:
    """
    A cargo ship entity carrying containers.
    
    Attributes:
        id: Unique ship identifier
        num_containers: Total containers on this ship
        containers: List of Container objects on this ship
        state: Current ship state
        arrival_time: When ship arrived at harbour
        berth_time: When ship berthed
        unload_complete_time: When unloading completed
        departure_time: When ship departed
        berth_id: Which berth the ship is at (if any)
    """
    id: int
    num_containers: int
    containers: List[Container] = field(default_factory=list)
    state: ShipState = ShipState.ARRIVING
    arrival_time: float = 0.0
    berth_time: Optional[float] = None
    unload_complete_time: Optional[float] = None
    departure_time: Optional[float] = None
    berth_id: Optional[int] = None
    
    # Visualization position
    visual_x: float = 0.0
    visual_y: float = 0.0
    
    def __post_init__(self):
        """Initialize containers if not provided."""
        if not self.containers:
            self.containers = [
                Container(
                    id=self.id * 10000 + i,
                    ship_id=self.id,
                    created_time=self.arrival_time
                )
                for i in range(self.num_containers)
            ]
    
    @property
    def turnaround_time(self) -> Optional[float]:
        """Total time from arrival to departure."""
        if self.departure_time is not None:
            return self.departure_time - self.arrival_time
        return None
    
    @property
    def containers_remaining(self) -> int:
        """Number of containers still on ship."""
        return sum(
            1 for c in self.containers 
            if c.state in (ContainerState.CREATED, ContainerState.UNLOADING)
        )
    
    @property
    def is_empty(self) -> bool:
        """Check if all containers have been unloaded."""
        return self.containers_remaining == 0


class TruckState(Enum):
    """States for a truck."""
    ARRIVING = auto()      # Approaching gate
    WAITING_GATE = auto()  # Waiting at gate
    AT_GATE = auto()       # At gate, processing
    WAITING_CONTAINER = auto()  # Waiting for container
    LOADING = auto()       # Container being loaded
    DEPARTING = auto()     # Leaving
    DEPARTED = auto()      # Left the system


@dataclass
class Truck:
    """
    A truck entity for container pickup.
    
    Attributes:
        id: Unique truck identifier
        state: Current truck state
        arrival_time: When truck arrived
        gate_time: When truck reached gate
        load_start_time: When loading started
        departure_time: When truck departed
        container: The container being picked up (if any)
        gate_id: Which gate the truck is at
    """
    id: int
    state: TruckState = TruckState.ARRIVING
    arrival_time: float = 0.0
    gate_time: Optional[float] = None
    load_start_time: Optional[float] = None
    departure_time: Optional[float] = None
    container: Optional[Container] = None
    gate_id: Optional[int] = None
    
    # Visualization position
    visual_x: float = 0.0
    visual_y: float = 0.0
    
    @property
    def wait_time(self) -> Optional[float]:
        """Time spent waiting (arrival to load start)."""
        if self.load_start_time is not None:
            return self.load_start_time - self.arrival_time
        return None
    
    @property
    def total_time(self) -> Optional[float]:
        """Total time in system."""
        if self.departure_time is not None:
            return self.departure_time - self.arrival_time
        return None
