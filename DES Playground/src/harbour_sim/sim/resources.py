"""
Resource definitions for the harbour simulation.

Contains classes for QuayCrane, Yard, YardMover, and TruckGate resources
that manage capacity and provide SimPy resource semantics.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict, Set
from enum import Enum, auto
import simpy
from harbour_sim.sim.entities import Container, ContainerState


class CraneState(Enum):
    """States for a quay crane."""
    IDLE = auto()
    MOVING = auto()
    PICKING = auto()
    DROPPING = auto()


@dataclass
class QuayCrane:
    """
    A quay crane for unloading containers from ships.
    
    Attributes:
        id: Unique crane identifier
        berth_id: Which berth this crane is assigned to (if any)
        state: Current crane state
        position_x: Current x position (along quay)
        position_y: Current y position
        target_x: Target x position
        target_y: Target y position
        current_container: Container being moved (if any)
        containers_unloaded: Count of containers unloaded
        busy_time: Total time spent busy
    """
    id: int
    berth_id: Optional[int] = None
    state: CraneState = CraneState.IDLE
    position_x: float = 0.0
    position_y: float = 0.0
    target_x: float = 0.0
    target_y: float = 0.0
    current_container: Optional[Container] = None
    containers_unloaded: int = 0
    busy_time: float = 0.0
    last_state_change: float = 0.0
    
    def update_busy_time(self, current_time: float) -> None:
        """Update accumulated busy time."""
        if self.state != CraneState.IDLE:
            self.busy_time += current_time - self.last_state_change
        self.last_state_change = current_time
    
    def set_state(self, state: CraneState, time: float) -> None:
        """Change state and update busy time tracking."""
        self.update_busy_time(time)
        self.state = state

    @property
    def is_busy(self) -> bool:
        """Return True if crane is currently busy."""
        return self.state != CraneState.IDLE


class QuayCraneManager:
    """
    Manages multiple quay cranes as SimPy resources.
    
    Attributes:
        env: SimPy environment
        cranes: List of QuayCrane objects
        resource: SimPy Resource for crane allocation
    """
    
    def __init__(self, env: simpy.Environment, num_cranes: int):
        """
        Initialize crane manager.
        
        Args:
            env: SimPy environment
            num_cranes: Number of cranes to create
        """
        self.env = env
        self.cranes = [QuayCrane(id=i) for i in range(num_cranes)]
        self.resource = simpy.Resource(env, capacity=num_cranes)
        self._crane_assignments: Dict[int, QuayCrane] = {}  # request_id -> crane
        self._next_request_id = 0
    
    def get_available_crane(self) -> Optional[QuayCrane]:
        """Get an available (idle) crane if any."""
        for crane in self.cranes:
            if crane.state == CraneState.IDLE and crane.berth_id is None:
                return crane
        return None

    def busy_count(self) -> int:
        """Return number of cranes currently busy."""
        return sum(1 for c in self.cranes if c.is_busy)
    
    def assign_crane_to_berth(self, crane: QuayCrane, berth_id: int) -> None:
        """Assign a crane to a specific berth."""
        crane.berth_id = berth_id
    
    def release_crane(self, crane: QuayCrane) -> None:
        """Release a crane from its current assignment."""
        crane.berth_id = None
        crane.state = CraneState.IDLE
        crane.current_container = None
    
    @property
    def utilization(self) -> float:
        """Calculate average crane utilization."""
        if not self.cranes or self.env.now == 0:
            return 0.0
        total_busy = sum(c.busy_time for c in self.cranes)
        return total_busy / (len(self.cranes) * self.env.now)


@dataclass
class YardSlot:
    """
    A single slot in the yard grid.
    
    Attributes:
        x: X coordinate (bay)
        y: Y coordinate (row)
        max_height: Maximum stack height
        containers: Stack of containers (bottom to top)
    """
    x: int
    y: int
    max_height: int = 4
    containers: List[Container] = field(default_factory=list)
    
    @property
    def height(self) -> int:
        """Current stack height."""
        return len(self.containers)
    
    @property
    def is_full(self) -> bool:
        """Check if slot is at max capacity."""
        return self.height >= self.max_height
    
    @property
    def is_empty(self) -> bool:
        """Check if slot has no containers."""
        return self.height == 0
    
    def add_container(self, container: Container) -> bool:
        """
        Add a container to the top of the stack.
        
        Returns:
            True if successful, False if full.
        """
        if self.is_full:
            return False
        container.yard_position = (self.x, self.y, self.height)
        self.containers.append(container)
        return True
    
    def remove_top_container(self) -> Optional[Container]:
        """
        Remove and return the top container.
        
        Returns:
            The container, or None if empty.
        """
        if self.is_empty:
            return None
        container = self.containers.pop()
        container.yard_position = None
        return container
    
    def peek_top(self) -> Optional[Container]:
        """Get the top container without removing it."""
        if self.is_empty:
            return None
        return self.containers[-1]


class Yard:
    """
    The container yard with grid-based storage.
    
    Attributes:
        env: SimPy environment
        width: Number of bays (x)
        height: Number of rows (y)
        max_stack_height: Maximum containers per slot
        grid: 2D array of YardSlots
    """
    
    def __init__(
        self,
        env: simpy.Environment,
        width: int,
        height: int,
        max_stack_height: int = 4
    ):
        """
        Initialize the yard.
        
        Args:
            env: SimPy environment
            width: Number of bays
            height: Number of rows
            max_stack_height: Max stack height per slot
        """
        self.env = env
        self.width = width
        self.height = height
        self.max_stack_height = max_stack_height
        
        # Create grid of slots
        self.grid: List[List[YardSlot]] = [
            [YardSlot(x=x, y=y, max_height=max_stack_height) 
             for y in range(height)]
            for x in range(width)
        ]
        
        # Track all containers in yard
        self._containers_in_yard: Set[int] = set()
        
        # Occupancy history for metrics
        self.occupancy_history: List[Tuple[float, int]] = []
    
    @property
    def capacity(self) -> int:
        """Total yard capacity."""
        return self.width * self.height * self.max_stack_height
    
    @property
    def container_count(self) -> int:
        """Current number of containers in yard."""
        return len(self._containers_in_yard)
    
    @property
    def occupancy(self) -> float:
        """Current occupancy ratio."""
        return self.container_count / self.capacity if self.capacity > 0 else 0.0
    
    def record_occupancy(self) -> None:
        """Record current occupancy for metrics."""
        self.occupancy_history.append((self.env.now, self.container_count))

    # Monitoring helpers
    def total_containers(self) -> int:
        """Return total containers currently in yard."""
        return self.container_count

    def stack_heights(self):
        """Return a 2D list of stack heights by slot."""
        return [[slot.height for slot in col] for col in self.grid]
    
    def get_slot(self, x: int, y: int) -> Optional[YardSlot]:
        """Get slot at coordinates."""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.grid[x][y]
        return None
    
    def find_available_slot(self, prefer_x: Optional[int] = None) -> Optional[YardSlot]:
        """
        Find an available slot for a container.
        
        Args:
            prefer_x: Preferred x coordinate (for nearest-to-pickup policy)
        
        Returns:
            An available YardSlot, or None if yard is full.
        """
        # If preference given, search from that x outward
        if prefer_x is not None:
            for dx in range(self.width):
                for direction in [1, -1]:
                    x = prefer_x + dx * direction
                    if 0 <= x < self.width:
                        for y in range(self.height):
                            slot = self.grid[x][y]
                            if not slot.is_full:
                                return slot
        else:
            # Default: search from bottom-left
            for x in range(self.width):
                for y in range(self.height):
                    slot = self.grid[x][y]
                    if not slot.is_full:
                        return slot
        return None
    
    def place_container(self, container: Container, slot: Optional[YardSlot] = None) -> bool:
        """
        Place a container in the yard.
        
        Args:
            container: Container to place
            slot: Specific slot (if None, finds available)
        
        Returns:
            True if successful.
        """
        if slot is None:
            slot = self.find_available_slot()
        
        if slot is None or slot.is_full:
            return False
        
        if slot.add_container(container):
            self._containers_in_yard.add(container.id)
            container.transition_to(ContainerState.IN_YARD, self.env.now)
            self.record_occupancy()
            return True
        return False
    
    def find_container(self, container_id: int) -> Optional[Tuple[YardSlot, int]]:
        """
        Find a container by ID.
        
        Returns:
            Tuple of (slot, stack_index) or None.
        """
        for x in range(self.width):
            for y in range(self.height):
                slot = self.grid[x][y]
                for i, c in enumerate(slot.containers):
                    if c.id == container_id:
                        return (slot, i)
        return None
    
    def get_accessible_container(self) -> Optional[Container]:
        """
        Get an accessible container (top of any stack) for truck pickup.
        
        Prefers containers that have been in yard longest (FIFO).
        
        Returns:
            An accessible Container, or None.
        """
        accessible: List[Container] = []
        
        for x in range(self.width):
            for y in range(self.height):
                slot = self.grid[x][y]
                top = slot.peek_top()
                if top is not None and top.state == ContainerState.IN_YARD:
                    accessible.append(top)
        
        if not accessible:
            return None
        
        # Sort by yard arrival time (FIFO)
        accessible.sort(key=lambda c: c.yard_arrival_time or float('inf'))
        return accessible[0]
    
    def remove_container(self, container: Container) -> bool:
        """
        Remove a container from the yard.
        
        Note: Only top containers can be removed directly.
        
        Args:
            container: Container to remove
        
        Returns:
            True if successful.
        """
        if container.yard_position is None:
            return False
        
        x, y, z = container.yard_position
        slot = self.get_slot(x, y)
        
        if slot is None:
            return False
        
        # Check if container is on top
        if slot.peek_top() == container:
            slot.remove_top_container()
            self._containers_in_yard.discard(container.id)
            self.record_occupancy()
            return True
        
        return False
    
    def get_state_snapshot(self) -> List[List[List[Container]]]:
        """Get a snapshot of all containers in yard for visualization."""
        return [
            [list(slot.containers) for slot in row]
            for row in self.grid
        ]


class YardMover:
    """
    Yard movers (straddle carriers / reach stackers) for internal moves.
    
    Attributes:
        env: SimPy environment
        resource: SimPy Resource for mover allocation
        num_movers: Number of movers
        moves_completed: Total moves completed
    """
    
    def __init__(self, env: simpy.Environment, num_movers: int):
        """
        Initialize yard mover manager.
        
        Args:
            env: SimPy environment
            num_movers: Number of yard movers
        """
        self.env = env
        self.resource = simpy.Resource(env, capacity=num_movers)
        self.num_movers = num_movers
        self.moves_completed = 0
        self.busy_time = 0.0

    def busy_count(self) -> int:
        """Return number of movers currently busy (resource users)."""
        try:
            return self.resource.count
        except Exception:
            return 0


class TruckGate:
    """
    Truck gates for entry/exit and container pickup.
    
    Attributes:
        env: SimPy environment
        resource: SimPy Resource for gate allocation
        num_gates: Number of gates
        trucks_processed: Total trucks processed
    """
    
    def __init__(self, env: simpy.Environment, num_gates: int):
        """
        Initialize truck gate manager.
        
        Args:
            env: SimPy environment
            num_gates: Number of truck gates
        """
        self.env = env
        self.resource = simpy.Resource(env, capacity=num_gates)
        self.num_gates = num_gates
        self.trucks_processed = 0
        self.busy_time = 0.0

    def queue_length(self) -> int:
        """Return current queue length at the gate."""
        try:
            return len(self.resource.queue)
        except Exception:
            return 0

    def busy_count(self) -> int:
        """Return number of gates currently occupied."""
        try:
            return self.resource.count
        except Exception:
            return 0


class Berth:
    """
    A berth where ships can dock.
    
    Attributes:
        id: Berth identifier
        ship: Currently docked ship (if any)
        position_x: X position for visualization
        position_y: Y position for visualization
    """
    
    def __init__(self, berth_id: int, position_x: float = 0.0, position_y: float = 0.0):
        self.id = berth_id
        self.ship = None
        self.position_x = position_x
        self.position_y = position_y
    
    @property
    def is_occupied(self) -> bool:
        """Check if berth has a ship."""
        return self.ship is not None
    
    def dock_ship(self, ship) -> bool:
        """Dock a ship at this berth."""
        if self.is_occupied:
            return False
        self.ship = ship
        return True
    
    def undock_ship(self):
        """Remove the ship from this berth."""
        ship = self.ship
        self.ship = None
        return ship


class BerthManager:
    """
    Manages multiple berths as SimPy resources.
    
    Attributes:
        env: SimPy environment
        berths: List of Berth objects
        resource: SimPy Resource for berth allocation
    """
    
    def __init__(self, env: simpy.Environment, num_berths: int, quay_length: float = 100.0):
        """
        Initialize berth manager.
        
        Args:
            env: SimPy environment
            num_berths: Number of berths
            quay_length: Length of quay for positioning
        """
        self.env = env
        self.num_berths = num_berths
        
        # Space berths evenly along quay
        spacing = quay_length / (num_berths + 1)
        self.berths = [
            Berth(berth_id=i, position_x=spacing * (i + 1), position_y=0)
            for i in range(num_berths)
        ]
        
        self.resource = simpy.Resource(env, capacity=num_berths)
    
    def get_available_berth(self) -> Optional[Berth]:
        """Get an available berth."""
        for berth in self.berths:
            if not berth.is_occupied:
                return berth
        return None
    
    def get_berth_by_id(self, berth_id: int) -> Optional[Berth]:
        """Get berth by ID."""
        for berth in self.berths:
            if berth.id == berth_id:
                return berth
        return None
