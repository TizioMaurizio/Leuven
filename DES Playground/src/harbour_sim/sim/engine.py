"""
Main simulation engine for HarbourSim.

Orchestrates all SimPy processes including ship arrivals, crane operations,
yard management, and truck pickups.
"""

import simpy
import random
import threading
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from queue import Queue
import logging

from harbour_sim.config import SimConfig
from harbour_sim.sim.entities import (
    Container, ContainerState, Ship, ShipState, Truck, TruckState
)
from harbour_sim.sim.resources import (
    QuayCraneManager, CraneState, Yard, YardMover, TruckGate, BerthManager
)
from harbour_sim.sim.policies import PolicyManager


@dataclass
class SimulationState:
    """
    Thread-safe snapshot of simulation state for visualization.
    
    Updated by the simulation and read by the renderer.
    """
    time: float = 0.0
    ships: List[Ship] = field(default_factory=list)
    ships_at_berth: Dict[int, Ship] = field(default_factory=dict)  # berth_id -> ship
    trucks: List[Truck] = field(default_factory=list)
    active_trucks: List[Truck] = field(default_factory=list)
    yard_state: List[List[List[Container]]] = field(default_factory=list)
    crane_states: List[Dict[str, Any]] = field(default_factory=list)
    berth_positions: List[Dict[str, float]] = field(default_factory=list)
    
    # Metrics snapshot
    containers_unloaded: int = 0
    containers_delivered: int = 0
    yard_occupancy: float = 0.0
    
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def update(self, **kwargs):
        """Thread-safe update of state."""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
    
    def copy(self) -> "SimulationState":
        """Create a copy for reading."""
        with self._lock:
            return SimulationState(
                time=self.time,
                ships=list(self.ships),
                ships_at_berth=dict(self.ships_at_berth),
                trucks=list(self.trucks),
                active_trucks=list(self.active_trucks),
                yard_state=self.yard_state,  # Already a snapshot
                crane_states=list(self.crane_states),
                berth_positions=list(self.berth_positions),
                containers_unloaded=self.containers_unloaded,
                containers_delivered=self.containers_delivered,
                yard_occupancy=self.yard_occupancy,
            )


@dataclass
class EventLog:
    """Simple event log for debugging."""
    entries: List[Dict[str, Any]] = field(default_factory=list)
    enabled: bool = True
    max_entries: int = 10000
    
    def log(self, time: float, entity_type: str, entity_id: int, action: str, details: str = ""):
        """Log an event."""
        if not self.enabled:
            return
        
        entry = {
            "time": time,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "details": details
        }
        
        self.entries.append(entry)
        
        # Trim if too large
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries // 2:]
    
    def get_recent(self, n: int = 20) -> List[Dict[str, Any]]:
        """Get the n most recent entries."""
        return self.entries[-n:]


class HarbourSimulation:
    """
    Main simulation class orchestrating all harbour operations.
    
    Uses SimPy as the core event engine and maintains state snapshots
    for visualization.
    """
    
    def __init__(
        self,
        config: SimConfig = None,
        policies: PolicyManager = None,
        seed: int = None
    ):
        """
        Initialize the simulation.
        
        Args:
            config: Simulation configuration
            policies: Policy manager (uses defaults if None)
            seed: Random seed (overrides config if provided)
        """
        self.config = config or SimConfig()
        self.policies = policies or PolicyManager.default()
        
        # Set up random number generator
        self._seed = seed if seed is not None else self.config.seed
        self.rng = random.Random(self._seed)
        
        # Set up logging
        self.logger = logging.getLogger("harbour_sim")
        
        # SimPy environment
        self.env = simpy.Environment()
        
        # Resources
        self.berths = BerthManager(self.env, self.config.num_berths)
        self.cranes = QuayCraneManager(self.env, self.config.num_quay_cranes)
        self.yard = Yard(
            self.env,
            self.config.yard_width,
            self.config.yard_height,
            self.config.yard_max_stack_height
        )
        self.yard_movers = YardMover(self.env, self.config.num_yard_movers)
        self.truck_gates = TruckGate(self.env, self.config.num_truck_gates)
        
        # Entity tracking
        self.ships: List[Ship] = []
        self.trucks: List[Truck] = []
        self.all_containers: List[Container] = []
        
        # Counters
        self._ship_counter = 0
        self._truck_counter = 0
        self._container_counter = 0
        
        # State for visualization
        self.state = SimulationState()
        self._update_state_callback: Optional[Callable] = None
        
        # Event logging
        self.event_log = EventLog(enabled=self.config.log_events)
        
        # Running flag
        self._running = False
        self._stop_requested = False
    
    def _random_exponential(self, mean: float) -> float:
        """Generate exponentially distributed random value."""
        return self.rng.expovariate(1.0 / mean)
    
    def _random_triangular(self, low: float, mode: float, high: float) -> float:
        """Generate triangular distributed random value."""
        return self.rng.triangular(low, high, mode)
    
    def _random_int_range(self, low: int, high: int) -> int:
        """Generate random integer in range [low, high]."""
        return self.rng.randint(low, high)
    
    def _update_state(self):
        """Update the shared state snapshot for visualization."""
        # Update crane states
        crane_states = []
        for crane in self.cranes.cranes:
            crane_states.append({
                "id": crane.id,
                "state": crane.state.name,
                "position_x": crane.position_x,
                "position_y": crane.position_y,
                "berth_id": crane.berth_id,
                "has_container": crane.current_container is not None,
                "container_color": crane.current_container.color if crane.current_container else None
            })
        
        # Update berth positions
        berth_positions = []
        for berth in self.berths.berths:
            berth_positions.append({
                "id": berth.id,
                "position_x": berth.position_x,
                "position_y": berth.position_y,
                "is_occupied": berth.is_occupied
            })
        
        # Create ships at berth mapping
        ships_at_berth = {}
        for ship in self.ships:
            if ship.berth_id is not None and ship.state in (ShipState.BERTHED, ShipState.UNLOADING):
                ships_at_berth[ship.berth_id] = ship
        
        # Active trucks (not departed)
        active_trucks = [t for t in self.trucks if t.state != TruckState.DEPARTED]
        
        self.state.update(
            time=self.env.now,
            ships=list(self.ships),
            ships_at_berth=ships_at_berth,
            trucks=list(self.trucks),
            active_trucks=active_trucks,
            yard_state=self.yard.get_state_snapshot(),
            crane_states=crane_states,
            berth_positions=berth_positions,
            containers_unloaded=sum(1 for c in self.all_containers 
                                    if c.state not in (ContainerState.CREATED, ContainerState.UNLOADING)),
            containers_delivered=sum(1 for c in self.all_containers 
                                     if c.state == ContainerState.EXITED),
            yard_occupancy=self.yard.occupancy
        )
        
        if self._update_state_callback:
            self._update_state_callback(self.state)

    def monitor_process(self, interval: float = 5.0):
        """
        Periodic monitoring process to log high-level statistics for bottleneck analysis.
        """
        while not self._stop_requested:
            yield self.env.timeout(interval)

            now = self.env.now
            try:
                yard_total = self.yard.total_containers()
            except Exception:
                yard_total = self.yard.container_count

            try:
                crane_busy = self.cranes.busy_count()
            except Exception:
                crane_busy = 0

            try:
                mover_busy = self.yard_movers.busy_count()
            except Exception:
                mover_busy = 0

            try:
                gate_queue = self.truck_gates.queue_length()
                gate_busy = self.truck_gates.busy_count()
            except Exception:
                gate_queue = 0
                gate_busy = 0

            trucks_waiting = sum(1 for t in self.trucks if t.state in (TruckState.WAITING_GATE, TruckState.WAITING_CONTAINER))

            if self.config.log_events:
                print(f"[{now:6.1f}] YARD={yard_total}/{self.yard.capacity} | CRANES_BUSY={crane_busy}/{len(self.cranes.cranes)} | "
                      f"MOVERS_BUSY={mover_busy}/{getattr(self.yard_movers, 'num_movers', 0)} | GATE_BUSY={gate_busy}/{getattr(self.truck_gates, 'num_gates', 0)} | "
                      f"GATE_QUEUE={gate_queue} | TRUCKS_WAITING={trucks_waiting}")
    
    def set_state_callback(self, callback: Callable):
        """Set callback for state updates."""
        self._update_state_callback = callback
    
    # === SHIP PROCESSES ===
    
    def ship_arrival_process(self):
        """Process that generates ship arrivals."""
        while not self._stop_requested:
            # Wait for next ship arrival
            interarrival = self._random_exponential(self.config.ship_interarrival_mean)
            yield self.env.timeout(interarrival)
            
            if self._stop_requested:
                break
            
            # Create new ship
            self._ship_counter += 1
            num_containers = self._random_int_range(
                self.config.ship_containers_min,
                self.config.ship_containers_max
            )
            
            ship = Ship(
                id=self._ship_counter,
                num_containers=num_containers,
                arrival_time=self.env.now
            )
            
            # Track containers
            self.all_containers.extend(ship.containers)
            
            self.ships.append(ship)
            self.event_log.log(
                self.env.now, "Ship", ship.id, "ARRIVED",
                f"containers={num_containers}"
            )
            
            # Start ship process
            self.env.process(self.ship_process(ship))
            self._update_state()
    
    def ship_process(self, ship: Ship):
        """
        Process for a single ship from arrival to departure.
        
        Args:
            ship: The ship entity
        """
        ship.state = ShipState.WAITING_BERTH
        
        # Request berth
        with self.berths.resource.request() as berth_req:
            yield berth_req
            
            if self._stop_requested:
                return
            
            # Get available berth
            berth = self.berths.get_available_berth()
            if berth is None:
                # This shouldn't happen with proper resource management
                self.logger.warning(f"No berth available for ship {ship.id}")
                return
            
            # Dock ship
            berth.dock_ship(ship)
            ship.berth_id = berth.id
            ship.berth_time = self.env.now
            ship.state = ShipState.BERTHED
            
            # Set visual position
            ship.visual_x = berth.position_x
            ship.visual_y = berth.position_y
            
            self.event_log.log(
                self.env.now, "Ship", ship.id, "BERTHED",
                f"berth={berth.id}"
            )
            self._update_state()
            
            # Start unloading
            ship.state = ShipState.UNLOADING
            yield self.env.process(self.unload_ship_process(ship, berth))
            
            if self._stop_requested:
                return
            
            # Unloading complete
            ship.unload_complete_time = self.env.now
            ship.state = ShipState.DEPARTING
            
            self.event_log.log(
                self.env.now, "Ship", ship.id, "UNLOAD_COMPLETE",
                f"duration={ship.unload_complete_time - ship.berth_time:.1f}"
            )
            
            # Undock and depart
            berth.undock_ship()
            ship.berth_id = None
            
            # Brief departure delay
            yield self.env.timeout(1.0)
            
            ship.state = ShipState.DEPARTED
            ship.departure_time = self.env.now
            
            self.event_log.log(
                self.env.now, "Ship", ship.id, "DEPARTED",
                f"turnaround={ship.turnaround_time:.1f}"
            )
            self._update_state()
    
    def unload_ship_process(self, ship: Ship, berth):
        """
        Unload all containers from a ship using parallel crane operations.
        
        Args:
            ship: Ship to unload
            berth: Berth where ship is docked
        """
        # Launch parallel unloading processes for multiple cranes
        unload_processes = []
        containers_to_unload = [c for c in ship.containers if c.state == ContainerState.CREATED]
        container_queue = list(containers_to_unload)
        
        # Determine how many cranes can work on this ship (up to 2 per berth typically)
        cranes_per_ship = min(2, self.config.num_quay_cranes)
        
        # Start parallel unload processes
        for _ in range(cranes_per_ship):
            proc = self.env.process(self._crane_unload_process(ship, berth, container_queue))
            unload_processes.append(proc)
        
        # Wait for all unloading to complete
        yield self.env.all_of(unload_processes)
    
    def _crane_unload_process(self, ship: Ship, berth, container_queue: list):
        """
        Single crane unloading process - takes containers from queue.
        
        Args:
            ship: Ship being unloaded
            berth: Berth where ship is docked
            container_queue: Shared queue of containers to unload
        """
        while container_queue and not self._stop_requested:
            # Request crane
            with self.cranes.resource.request() as crane_req:
                yield crane_req
                
                if self._stop_requested or not container_queue:
                    break
                
                # Get next container from queue
                try:
                    container = container_queue.pop(0)
                except IndexError:
                    break  # Queue empty
                
                # Get an available crane
                crane = None
                for c in self.cranes.cranes:
                    if c.state == CraneState.IDLE:
                        crane = c
                        break
                
                if crane is None:
                    # Put container back and retry
                    container_queue.insert(0, container)
                    yield self.env.timeout(0.1)
                    continue
                
                # Assign crane to berth
                crane.berth_id = berth.id
                
                # Move crane to ship position
                crane.set_state(CraneState.MOVING, self.env.now)
                crane.target_x = berth.position_x
                crane.target_y = berth.position_y
                
                # Calculate move time
                distance = abs(crane.position_x - berth.position_x)
                move_time = distance / self.config.crane_move_speed if self.config.crane_move_speed > 0 else 0
                
                if move_time > 0:
                    yield self.env.timeout(move_time)
                
                crane.position_x = berth.position_x
                crane.position_y = berth.position_y
                
                # Pick container from ship
                crane.set_state(CraneState.PICKING, self.env.now)
                container.transition_to(ContainerState.UNLOADING, self.env.now)
                crane.current_container = container
                
                pick_time = self._random_triangular(
                    self.config.crane_unload_time_min,
                    self.config.crane_unload_time_mode,
                    self.config.crane_unload_time_max
                )
                
                self._update_state()
                yield self.env.timeout(pick_time)
                
                if self._stop_requested:
                    break
                
                # Find yard slot
                slot = self.policies.yard_policy.select_slot(self.yard, container)
                
                if slot is None:
                    self.event_log.log(
                        self.env.now, "Container", container.id, "YARD_FULL",
                        "No available slot"
                    )
                    # Put back container - in real sim would handle this
                    container.state = ContainerState.CREATED
                    crane.current_container = None
                    crane.set_state(CraneState.IDLE, self.env.now)
                    continue
                
                # Move crane to yard position
                crane.set_state(CraneState.MOVING, self.env.now)
                yard_x = slot.x * 5 + 10  # Scale for visualization
                crane.target_x = yard_x
                
                distance = abs(crane.position_x - yard_x)
                move_time = distance / self.config.crane_move_speed if self.config.crane_move_speed > 0 else 0
                
                self._update_state()
                
                if move_time > 0:
                    yield self.env.timeout(move_time / 2)  # Simplified: half time to yard
                
                crane.position_x = yard_x
                
                # Drop container in yard
                crane.set_state(CraneState.DROPPING, self.env.now)
                
                drop_time = self._random_triangular(
                    self.config.crane_unload_time_min * 0.5,
                    self.config.crane_unload_time_mode * 0.5,
                    self.config.crane_unload_time_max * 0.5
                )
                
                self._update_state()
                yield self.env.timeout(drop_time)
                
                # Place in yard
                self.yard.place_container(container, slot)
                crane.current_container = None
                crane.containers_unloaded += 1
                
                self.event_log.log(
                    self.env.now, "Container", container.id, "IN_YARD",
                    f"slot=({slot.x},{slot.y},{slot.height-1})"
                )
                
                # Return crane to idle
                crane.set_state(CraneState.IDLE, self.env.now)
                crane.berth_id = None
                
                self._update_state()
    
    # === TRUCK PROCESSES ===
    
    def truck_arrival_process(self):
        """Process that generates truck arrivals."""
        while not self._stop_requested:
            # Wait for next truck arrival
            interarrival = self._random_exponential(self.config.truck_interarrival_mean)
            yield self.env.timeout(interarrival)
            
            if self._stop_requested:
                break
            
            # Create new truck
            self._truck_counter += 1
            truck = Truck(
                id=self._truck_counter,
                arrival_time=self.env.now
            )
            
            self.trucks.append(truck)
            self.event_log.log(
                self.env.now, "Truck", truck.id, "ARRIVED", ""
            )
            
            # Start truck process
            self.env.process(self.truck_process(truck))
            self._update_state()
    
    def truck_process(self, truck: Truck):
        """
        Process for a single truck from arrival to departure.
        
        Args:
            truck: The truck entity
        """
        truck.state = TruckState.WAITING_GATE
        
        # Request gate
        with self.truck_gates.resource.request() as gate_req:
            yield gate_req
            
            if self._stop_requested:
                return
            
            truck.state = TruckState.AT_GATE
            truck.gate_time = self.env.now
            
            self._update_state()
            
            # Wait for available container
            truck.state = TruckState.WAITING_CONTAINER
            container = None
            
            # Poll for container (with timeout to prevent infinite wait)
            max_wait = 60.0  # Maximum wait time
            wait_start = self.env.now
            
            while container is None and not self._stop_requested:
                container = self.policies.container_policy.select_container(self.yard, truck)
                
                if container is None:
                    if self.env.now - wait_start > max_wait:
                        # Give up waiting
                        self.event_log.log(
                            self.env.now, "Truck", truck.id, "GAVE_UP",
                            "No container available"
                        )
                        truck.state = TruckState.DEPARTING
                        yield self.env.timeout(0.5)
                        truck.state = TruckState.DEPARTED
                        truck.departure_time = self.env.now
                        self._update_state()
                        return
                    
                    # Wait a bit and try again
                    yield self.env.timeout(1.0)
                    self._update_state()
            
            if container is None or self._stop_requested:
                return
            
            # Mark container for pickup
            container.transition_to(ContainerState.READY_FOR_PICKUP, self.env.now)
            truck.container = container
            
            self.event_log.log(
                self.env.now, "Truck", truck.id, "CONTAINER_ASSIGNED",
                f"container={container.id}"
            )
            
            # Load container onto truck
            truck.state = TruckState.LOADING
            truck.load_start_time = self.env.now
            container.transition_to(ContainerState.LOADING_TRUCK, self.env.now)
            
            # Request yard mover for loading
            with self.yard_movers.resource.request() as mover_req:
                yield mover_req
                
                if self._stop_requested:
                    return
                
                # Remove from yard
                self.yard.remove_container(container)
                
                # Loading time
                load_time = self._random_triangular(
                    self.config.truck_load_time_min,
                    self.config.truck_load_time_mode,
                    self.config.truck_load_time_max
                )
                
                self._update_state()
                yield self.env.timeout(load_time)
            
            if self._stop_requested:
                return
            
            # Container loaded
            container.transition_to(ContainerState.ON_TRUCK, self.env.now)
            
            # Depart
            truck.state = TruckState.DEPARTING
            self.truck_gates.trucks_processed += 1
            
            yield self.env.timeout(0.5)  # Brief departure time
            
            truck.state = TruckState.DEPARTED
            truck.departure_time = self.env.now
            container.transition_to(ContainerState.EXITED, self.env.now)
            
            self.event_log.log(
                self.env.now, "Truck", truck.id, "DEPARTED",
                f"container={container.id}, wait_time={truck.wait_time:.1f}"
            )
            
            self._update_state()
    
    # === SIMULATION CONTROL ===
    
    def run(self, duration: float = None, step_callback: Callable = None):
        """
        Run the simulation.
        
        Args:
            duration: Simulation duration (uses config if None)
            step_callback: Optional callback called each step
        """
        duration = duration or self.config.duration
        
        self._running = True
        self._stop_requested = False
        
        # Start main processes
        self.env.process(self.ship_arrival_process())
        self.env.process(self.truck_arrival_process())
        # Start monitor process
        self.env.process(self.monitor_process(interval=5.0))
        
        # Run with step updates
        step_size = 0.1  # Update every 0.1 time units
        
        while self.env.now < duration and not self._stop_requested:
            try:
                self.env.run(until=min(self.env.now + step_size, duration))
                self._update_state()
                
                if step_callback:
                    step_callback(self.env.now, self.state)
                    
            except simpy.core.EmptySchedule:
                break
        
        self._running = False
        self._update_state()
    
    def run_until(self, time: float):
        """Run simulation until specified time."""
        if time > self.env.now:
            self.env.run(until=time)
            self._update_state()
    
    def step(self, delta: float = 1.0):
        """Advance simulation by delta time units."""
        target = self.env.now + delta
        self.env.run(until=target)
        self._update_state()
    
    def stop(self):
        """Request simulation stop."""
        self._stop_requested = True
    
    @property
    def is_running(self) -> bool:
        """Check if simulation is running."""
        return self._running
    
    @property
    def current_time(self) -> float:
        """Get current simulation time."""
        return self.env.now
