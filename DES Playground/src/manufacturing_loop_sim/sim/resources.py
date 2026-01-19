"""
Resource definitions for the closed-loop manufacturing simulation.

Contains Station and Conveyor classes that manage processing and buffering
with proper blocking-after-service semantics.

CONCEPT MAPPING:
- ProcessingStation (DIGITAU) → Station (S1, S2)
- Buffer (DIGITAU) → Conveyor (finite FIFO buffer)

KEY SEMANTICS:
- Blocking-after-service: Station cannot release pallet until downstream
  conveyor has space available.
- Single-server stations: Each station processes one pallet at a time.
- FIFO conveyors: Pallets leave conveyor in the order they entered.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List, Dict, Any, Deque, TYPE_CHECKING
from collections import deque
import simpy

if TYPE_CHECKING:
    from manufacturing_loop_sim.sim.entities import Pallet


class StationState(Enum):
    """States for a processing station."""
    IDLE = auto()        # No pallet, ready to accept
    PROCESSING = auto()  # Currently processing a pallet
    BLOCKED = auto()     # Finished processing, waiting for downstream space
    DEGRADED = auto()    # Operating at reduced capacity (optional)
    DOWN = auto()        # Under repair (optional)


@dataclass
class Station:
    """
    A single-server processing station with blocking-after-service.
    
    Mapped from: ProcessingStation (DIGITAU) / QuayCrane (HarbourSim)
    
    Key difference: Implements blocking-after-service policy where the
    station holds the pallet after processing until downstream buffer
    has space available.
    
    Attributes:
        id: Station identifier (1 or 2)
        name: Human-readable name (S1 or S2)
        state: Current station state
        current_pallet: Pallet being processed/held
        processing_times: Triangular distribution parameters (min, mode, max)
    """
    id: int
    name: str
    env: simpy.Environment = field(repr=False)
    
    # Processing time distribution (triangular)
    time_min: float = 3.0
    time_mode: float = 5.0
    time_max: float = 8.0
    
    # State
    state: StationState = StationState.IDLE
    current_pallet: Optional["Pallet"] = None
    
    # SimPy resource for queue management
    _resource: simpy.Resource = field(init=False, repr=False)
    
    # Downstream conveyor reference (set after initialization)
    downstream_conveyor: Optional["Conveyor"] = None
    
    # Statistics
    pallets_processed: int = 0
    total_processing_time: float = 0.0
    total_blocked_time: float = 0.0
    total_idle_time: float = 0.0
    
    # Time tracking
    last_state_change: float = 0.0
    _blocked_start: Optional[float] = None
    
    # Degradation (optional)
    is_degraded: bool = False
    degradation_factor: float = 1.0
    
    # Position for visualization
    position_x: float = 0.0
    position_y: float = 0.0
    
    def __post_init__(self):
        """Initialize SimPy resource."""
        self._resource = simpy.Resource(self.env, capacity=1)
    
    @property
    def resource(self) -> simpy.Resource:
        """Get the SimPy resource for this station."""
        return self._resource
    
    @property
    def is_busy(self) -> bool:
        """Check if station has a pallet (processing or blocked)."""
        return self.current_pallet is not None
    
    @property
    def is_available(self) -> bool:
        """Check if station can accept a new pallet."""
        return self.state == StationState.IDLE and self.current_pallet is None
    
    @property
    def queue_length(self) -> int:
        """Number of pallets waiting for this station."""
        return len(self._resource.queue)
    
    def set_state(self, new_state: StationState, time: float):
        """Update state and track timing."""
        old_state = self.state
        elapsed = time - self.last_state_change
        
        # Accumulate time from previous state
        if old_state == StationState.PROCESSING:
            self.total_processing_time += elapsed
        elif old_state == StationState.BLOCKED:
            self.total_blocked_time += elapsed
        elif old_state == StationState.IDLE:
            self.total_idle_time += elapsed
        
        # Track blocking start/end
        if new_state == StationState.BLOCKED and old_state != StationState.BLOCKED:
            self._blocked_start = time
        elif old_state == StationState.BLOCKED and new_state != StationState.BLOCKED:
            self._blocked_start = None
        
        self.state = new_state
        self.last_state_change = time
    
    def get_processing_time(self, rng) -> float:
        """Generate a random processing time from triangular distribution."""
        base_time = rng.triangular(self.time_min, self.time_max, self.time_mode)
        if self.is_degraded:
            return base_time * self.degradation_factor
        return base_time
    
    @property
    def utilization(self) -> float:
        """Calculate station utilization (processing time / total time)."""
        total = self.total_processing_time + self.total_blocked_time + self.total_idle_time
        if total == 0:
            return 0.0
        return self.total_processing_time / total
    
    @property
    def blocking_ratio(self) -> float:
        """Ratio of time spent blocked vs processing."""
        if self.total_processing_time == 0:
            return 0.0
        return self.total_blocked_time / self.total_processing_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for state snapshots."""
        return {
            "id": self.id,
            "name": self.name,
            "state": self.state.name,
            "has_pallet": self.current_pallet is not None,
            "pallet_id": self.current_pallet.id if self.current_pallet else None,
            "queue_length": self.queue_length,
            "pallets_processed": self.pallets_processed,
            "utilization": self.utilization,
            "position_x": self.position_x,
            "position_y": self.position_y,
            "is_degraded": self.is_degraded,
        }


@dataclass  
class Conveyor:
    """
    A finite-capacity FIFO conveyor buffer between stations.
    
    Mapped from: Buffer (DIGITAU) / Yard (HarbourSim)
    
    Key differences:
    - Simple FIFO queue (no spatial grid)
    - Finite capacity triggers blocking at upstream station
    - No stacking - single layer of pallets
    
    Attributes:
        id: Conveyor identifier
        name: Human-readable name (e.g., "S1→S2")
        capacity: Maximum number of pallets
        transfer_time: Time to move pallet onto conveyor
    """
    id: int
    name: str
    env: simpy.Environment = field(repr=False)
    capacity: int = 8
    transfer_time: float = 1.0
    
    # FIFO queue of pallets
    _queue: Deque["Pallet"] = field(default_factory=deque)
    
    # SimPy store for blocking semantics
    _store: simpy.Store = field(init=False, repr=False)
    
    # Statistics
    pallets_transferred: int = 0
    total_wait_time: float = 0.0
    
    # Occupancy tracking
    occupancy_history: List[tuple] = field(default_factory=list)
    _last_occupancy_time: float = 0.0
    
    # Position for visualization
    start_x: float = 0.0
    start_y: float = 0.0
    end_x: float = 0.0
    end_y: float = 0.0
    
    def __post_init__(self):
        """Initialize SimPy store."""
        self._store = simpy.Store(self.env, capacity=self.capacity)
    
    @property
    def count(self) -> int:
        """Number of pallets currently on conveyor."""
        return len(self._store.items)
    
    @property
    def is_full(self) -> bool:
        """Check if conveyor is at capacity."""
        return self.count >= self.capacity
    
    @property
    def is_empty(self) -> bool:
        """Check if conveyor has no pallets."""
        return self.count == 0
    
    @property
    def has_space(self) -> bool:
        """Check if conveyor can accept another pallet."""
        return self.count < self.capacity
    
    @property
    def occupancy(self) -> float:
        """Current occupancy ratio (0-1)."""
        return self.count / self.capacity if self.capacity > 0 else 0.0
    
    @property
    def pallets(self) -> List["Pallet"]:
        """List of pallets currently on conveyor (for visualization)."""
        return list(self._store.items)
    
    def can_accept(self) -> bool:
        """Check if conveyor can accept a pallet (non-blocking check)."""
        return self.has_space
    
    def put(self, pallet: "Pallet"):
        """
        Put a pallet onto the conveyor.
        
        This is a SimPy generator that yields until space is available.
        Should only be called when space is confirmed available.
        """
        self._record_occupancy()
        self.pallets_transferred += 1
        return self._store.put(pallet)
    
    def get(self):
        """
        Get a pallet from the conveyor (FIFO).
        
        This is a SimPy generator that yields until a pallet is available.
        """
        self._record_occupancy()
        return self._store.get()
    
    def peek(self) -> Optional["Pallet"]:
        """Look at the next pallet without removing it."""
        if self._store.items:
            return self._store.items[0]
        return None
    
    def _record_occupancy(self):
        """Record occupancy for statistics."""
        current_time = self.env.now
        self.occupancy_history.append((current_time, self.count))
        self._last_occupancy_time = current_time
    
    @property
    def avg_occupancy(self) -> float:
        """Calculate average occupancy over time."""
        if not self.occupancy_history or len(self.occupancy_history) < 2:
            return self.occupancy
        
        total_weighted = 0.0
        total_time = 0.0
        
        for i in range(1, len(self.occupancy_history)):
            prev_time, prev_count = self.occupancy_history[i-1]
            curr_time, _ = self.occupancy_history[i]
            duration = curr_time - prev_time
            total_weighted += prev_count * duration
            total_time += duration
        
        if total_time == 0:
            return 0.0
        return (total_weighted / total_time) / self.capacity
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for state snapshots."""
        return {
            "id": self.id,
            "name": self.name,
            "count": self.count,
            "capacity": self.capacity,
            "occupancy": self.occupancy,
            "is_full": self.is_full,
            "pallet_ids": [p.id for p in self.pallets],
            "start_x": self.start_x,
            "start_y": self.start_y,
            "end_x": self.end_x,
            "end_y": self.end_y,
        }
