"""
Resource definitions for the DIGITAU demanufacturing simulation.

Contains classes for ProcessingStation, Buffer, Operator, and ExitGate
resources that manage capacity and provide SimPy resource semantics.

CONCEPT MAPPING (from HarbourSim):
- QuayCrane → ProcessingStation (inspection, dismantling, testing)
- Yard → Buffer (intermediate storage / WIP areas)
- YardMover → Operator (robot or human-robot collaborative)
- TruckGate → ExitGate (gates for different exit paths)
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict, Set
from enum import Enum, auto
import simpy
from demanufacturing_sim.sim.entities import Product, ProductState, ExitDecision


class StationType(Enum):
    """Types of processing stations."""
    INSPECTION = auto()
    DISMANTLING = auto()
    TESTING = auto()


class StationState(Enum):
    """States for a processing station."""
    IDLE = auto()
    PROCESSING = auto()
    MAINTENANCE = auto()


@dataclass
class ProcessingStation:
    """
    A processing station for product inspection, dismantling, or testing.
    
    Mapped from: QuayCrane in HarbourSim
    
    Attributes:
        id: Unique station identifier
        station_type: Type of processing (INSPECTION, DISMANTLING, TESTING)
        state: Current station state
        current_product: Product being processed (if any)
        products_processed: Count of products processed
        busy_time: Total time spent processing
    """
    id: int
    station_type: StationType
    state: StationState = StationState.IDLE
    current_product: Optional[Product] = None
    products_processed: int = 0
    busy_time: float = 0.0
    last_state_change: float = 0.0
    
    # Position for visualization
    position_x: float = 0.0
    position_y: float = 0.0
    
    def update_busy_time(self, current_time: float) -> None:
        """Update accumulated busy time."""
        if self.state == StationState.PROCESSING:
            self.busy_time += current_time - self.last_state_change
        self.last_state_change = current_time
    
    def set_state(self, state: StationState, time: float) -> None:
        """Change state and update busy time tracking."""
        self.update_busy_time(time)
        self.state = state
    
    @property
    def is_busy(self) -> bool:
        """Return True if station is currently busy."""
        return self.state == StationState.PROCESSING
    
    @property
    def type_name(self) -> str:
        """Human-readable station type name."""
        return self.station_type.name.capitalize()


class StationManager:
    """
    Manages multiple processing stations of a specific type.
    
    Mapped from: QuayCraneManager in HarbourSim
    """
    
    def __init__(self, env: simpy.Environment, station_type: StationType, num_stations: int):
        """
        Initialize station manager.
        
        Args:
            env: SimPy environment
            station_type: Type of stations to manage
            num_stations: Number of stations to create
        """
        self.env = env
        self.station_type = station_type
        self.stations = [
            ProcessingStation(id=i, station_type=station_type)
            for i in range(num_stations)
        ]
        self.resource = simpy.Resource(env, capacity=num_stations)
    
    def get_available_station(self) -> Optional[ProcessingStation]:
        """Get an available (idle) station if any."""
        for station in self.stations:
            if station.state == StationState.IDLE:
                return station
        return None
    
    def busy_count(self) -> int:
        """Return number of stations currently busy."""
        return sum(1 for s in self.stations if s.is_busy)
    
    @property
    def utilization(self) -> float:
        """Calculate average station utilization."""
        if not self.stations or self.env.now == 0:
            return 0.0
        total_busy = sum(s.busy_time for s in self.stations)
        return total_busy / (len(self.stations) * self.env.now)


@dataclass
class BufferSlot:
    """
    A single slot in the buffer grid.
    
    Mapped from: YardSlot in HarbourSim
    
    Attributes:
        x: X coordinate
        y: Y coordinate
        max_height: Maximum stack height
        products: Stack of products (bottom to top)
    """
    x: int
    y: int
    max_height: int = 3
    products: List[Product] = field(default_factory=list)
    
    @property
    def height(self) -> int:
        """Current stack height."""
        return len(self.products)
    
    @property
    def is_full(self) -> bool:
        """Check if slot is at max capacity."""
        return self.height >= self.max_height
    
    @property
    def is_empty(self) -> bool:
        """Check if slot has no products."""
        return self.height == 0
    
    def add_product(self, product: Product) -> bool:
        """Add a product to the top of the stack."""
        if self.is_full:
            return False
        product.buffer_position = (self.x, self.y, self.height)
        self.products.append(product)
        return True
    
    def remove_top_product(self) -> Optional[Product]:
        """Remove and return the top product."""
        if self.is_empty:
            return None
        product = self.products.pop()
        product.buffer_position = None
        return product
    
    def peek_top(self) -> Optional[Product]:
        """Get the top product without removing it."""
        if self.is_empty:
            return None
        return self.products[-1]


class Buffer:
    """
    The product buffer/WIP storage with grid-based storage.
    
    Mapped from: Yard in HarbourSim
    
    Attributes:
        env: SimPy environment
        width: Number of columns
        height: Number of rows
        max_stack_height: Maximum products per slot
        grid: 2D array of BufferSlots
    """
    
    def __init__(
        self,
        env: simpy.Environment,
        width: int,
        height: int,
        max_stack_height: int = 3
    ):
        """Initialize the buffer."""
        self.env = env
        self.width = width
        self.height = height
        self.max_stack_height = max_stack_height
        
        # Create grid of slots
        self.grid: List[List[BufferSlot]] = [
            [BufferSlot(x=x, y=y, max_height=max_stack_height)
             for y in range(height)]
            for x in range(width)
        ]
        
        # Track all products in buffer
        self._products_in_buffer: Set[int] = set()
        
        # Occupancy history for metrics
        self.occupancy_history: List[Tuple[float, int]] = []
    
    @property
    def capacity(self) -> int:
        """Total buffer capacity."""
        return self.width * self.height * self.max_stack_height
    
    @property
    def product_count(self) -> int:
        """Current number of products in buffer."""
        return len(self._products_in_buffer)
    
    def total_products(self) -> int:
        """Return total products in buffer (for monitoring)."""
        return self.product_count
    
    @property
    def occupancy(self) -> float:
        """Current occupancy ratio."""
        return self.product_count / self.capacity if self.capacity > 0 else 0.0
    
    def record_occupancy(self) -> None:
        """Record current occupancy for metrics."""
        self.occupancy_history.append((self.env.now, self.product_count))
    
    def get_slot(self, x: int, y: int) -> Optional[BufferSlot]:
        """Get slot at coordinates."""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.grid[x][y]
        return None
    
    def find_available_slot(self) -> Optional[BufferSlot]:
        """Find an available slot for a product."""
        # Prefer slots with lowest stack height
        best_slot = None
        min_height = float('inf')
        
        for x in range(self.width):
            for y in range(self.height):
                slot = self.grid[x][y]
                if not slot.is_full and slot.height < min_height:
                    min_height = slot.height
                    best_slot = slot
        
        return best_slot
    
    def place_product(self, product: Product, slot: Optional[BufferSlot] = None) -> bool:
        """Place a product in the buffer."""
        if slot is None:
            slot = self.find_available_slot()
        
        if slot is None or slot.is_full:
            return False
        
        if slot.add_product(product):
            self._products_in_buffer.add(product.id)
            product.transition_to(ProductState.IN_BUFFER, self.env.now)
            self.record_occupancy()
            return True
        return False
    
    def get_product_by_decision(self, decision: ExitDecision) -> Optional[Product]:
        """
        Get an accessible product with the specified exit decision.
        
        Args:
            decision: The exit decision to match
        
        Returns:
            An accessible Product matching the decision, or None.
        """
        accessible: List[Product] = []
        
        for x in range(self.width):
            for y in range(self.height):
                slot = self.grid[x][y]
                top = slot.peek_top()
                if top is not None and top.state == ProductState.IN_BUFFER:
                    if top.exit_decision == decision:
                        accessible.append(top)
        
        if not accessible:
            return None
        
        # Sort by buffer arrival time (FIFO)
        accessible.sort(key=lambda p: p.buffer_arrival_time or float('inf'))
        return accessible[0]
    
    def get_any_accessible_product(self) -> Optional[Product]:
        """Get any accessible product (top of any stack) with a decision made."""
        accessible: List[Product] = []
        
        for x in range(self.width):
            for y in range(self.height):
                slot = self.grid[x][y]
                top = slot.peek_top()
                if top is not None and top.state == ProductState.IN_BUFFER:
                    if top.exit_decision != ExitDecision.UNDECIDED:
                        accessible.append(top)
        
        if not accessible:
            return None
        
        accessible.sort(key=lambda p: p.buffer_arrival_time or float('inf'))
        return accessible[0]
    
    def remove_product(self, product: Product) -> bool:
        """Remove a product from the buffer."""
        if product.buffer_position is None:
            return False
        
        x, y, z = product.buffer_position
        slot = self.get_slot(x, y)
        
        if slot is None:
            return False
        
        # Check if product is on top
        if slot.peek_top() == product:
            slot.remove_top_product()
            self._products_in_buffer.discard(product.id)
            self.record_occupancy()
            return True
        
        return False
    
    def get_state_snapshot(self) -> List[List[List[Product]]]:
        """Get a snapshot of all products in buffer for visualization."""
        return [
            [list(slot.products) for slot in row]
            for row in self.grid
        ]
    
    def stack_heights(self):
        """Return a 2D list of stack heights by slot."""
        return [[slot.height for slot in col] for col in self.grid]


class Operator:
    """
    Operators (robots or human-robot collaborative) for moving products.
    
    Mapped from: YardMover in HarbourSim
    """
    
    def __init__(self, env: simpy.Environment, num_operators: int):
        """Initialize operator pool."""
        self.env = env
        self.resource = simpy.Resource(env, capacity=num_operators)
        self.num_operators = num_operators
        self.moves_completed = 0
        self.busy_time = 0.0
    
    def busy_count(self) -> int:
        """Return number of operators currently busy."""
        try:
            return self.resource.count
        except Exception:
            return 0


# Alias for compatibility
OperatorPool = Operator


@dataclass
class ExitGate:
    """
    An exit gate for a specific destination category.
    
    Mapped from: TruckGate in HarbourSim
    """
    id: int
    destination: ExitDecision
    position_x: float = 0.0
    position_y: float = 0.0
    vehicles_processed: int = 0


class ExitGateManager:
    """
    Manages exit gates for different destinations.
    
    Mapped from: TruckGate in HarbourSim (but split by destination)
    """
    
    def __init__(
        self,
        env: simpy.Environment,
        num_reuse: int,
        num_remanufacture: int,
        num_recycle: int
    ):
        """Initialize exit gate managers for each destination."""
        self.env = env
        
        # Create gates for each destination
        gate_id = 0
        
        self.reuse_gates = [
            ExitGate(id=gate_id + i, destination=ExitDecision.REUSE)
            for i in range(num_reuse)
        ]
        gate_id += num_reuse
        
        self.remanufacture_gates = [
            ExitGate(id=gate_id + i, destination=ExitDecision.REMANUFACTURE)
            for i in range(num_remanufacture)
        ]
        gate_id += num_remanufacture
        
        self.recycle_gates = [
            ExitGate(id=gate_id + i, destination=ExitDecision.RECYCLE)
            for i in range(num_recycle)
        ]
        
        # SimPy resources for each destination
        self.reuse_resource = simpy.Resource(env, capacity=max(1, num_reuse))
        self.remanufacture_resource = simpy.Resource(env, capacity=max(1, num_remanufacture))
        self.recycle_resource = simpy.Resource(env, capacity=max(1, num_recycle))
        
        self.total_processed = 0
    
    @property
    def all_gates(self) -> List[ExitGate]:
        """Get all gates."""
        return self.reuse_gates + self.remanufacture_gates + self.recycle_gates
    
    def get_resource(self, destination: ExitDecision) -> simpy.Resource:
        """Get the SimPy resource for a destination."""
        if destination == ExitDecision.REUSE:
            return self.reuse_resource
        elif destination == ExitDecision.REMANUFACTURE:
            return self.remanufacture_resource
        else:
            return self.recycle_resource
    
    def get_gates(self, destination: ExitDecision) -> List[ExitGate]:
        """Get gates for a destination."""
        if destination == ExitDecision.REUSE:
            return self.reuse_gates
        elif destination == ExitDecision.REMANUFACTURE:
            return self.remanufacture_gates
        else:
            return self.recycle_gates
    
    def queue_length(self, destination: ExitDecision = None) -> int:
        """Return queue length for a destination or total."""
        if destination is None:
            return (len(self.reuse_resource.queue) + 
                    len(self.remanufacture_resource.queue) +
                    len(self.recycle_resource.queue))
        return len(self.get_resource(destination).queue)
    
    def busy_count(self, destination: ExitDecision = None) -> int:
        """Return number of gates currently occupied."""
        if destination is None:
            return (self.reuse_resource.count + 
                    self.remanufacture_resource.count +
                    self.recycle_resource.count)
        return self.get_resource(destination).count


@dataclass
class ReceivingDock:
    """
    A receiving dock where product batches arrive.
    
    Mapped from: Berth in HarbourSim
    """
    id: int
    batch: Optional["ProductBatch"] = None
    position_x: float = 0.0
    position_y: float = 0.0
    
    @property
    def is_occupied(self) -> bool:
        """Check if dock has a batch."""
        return self.batch is not None
    
    def receive_batch(self, batch) -> bool:
        """Receive a batch at this dock."""
        if self.is_occupied:
            return False
        self.batch = batch
        return True
    
    def release_batch(self):
        """Release the batch from this dock."""
        batch = self.batch
        self.batch = None
        return batch


class DockManager:
    """
    Manages receiving docks.
    
    Mapped from: BerthManager in HarbourSim
    """
    
    def __init__(self, env: simpy.Environment, num_docks: int):
        """Initialize dock manager."""
        self.env = env
        self.num_docks = num_docks
        
        self.docks = [
            ReceivingDock(id=i)
            for i in range(num_docks)
        ]
        
        self.resource = simpy.Resource(env, capacity=num_docks)
    
    def get_available_dock(self) -> Optional[ReceivingDock]:
        """Get an available dock."""
        for dock in self.docks:
            if not dock.is_occupied:
                return dock
        return None
    
    def get_dock_by_id(self, dock_id: int) -> Optional[ReceivingDock]:
        """Get dock by ID."""
        for dock in self.docks:
            if dock.id == dock_id:
                return dock
        return None
