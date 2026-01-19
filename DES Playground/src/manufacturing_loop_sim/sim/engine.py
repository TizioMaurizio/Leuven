"""
Main simulation engine for the closed-loop manufacturing system.

Orchestrates SimPy processes for a two-station system with:
- Blocking-after-service semantics
- Finite conveyor buffers
- Continuous pallet circulation

CONCEPT MAPPING:
- DemanufacturingSimulation → ClosedLoopSimulation
- batch_arrival_process → (removed - closed loop)
- product_process → pallet_process
- exit_vehicle_process → (removed - pallets loop back)

KEY DIFFERENCE: No arrivals or departures - pallets circulate forever.
"""

import simpy
import random
import threading
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, field

from manufacturing_loop_sim.config import SimConfig
from manufacturing_loop_sim.sim.entities import Pallet, PalletState
from manufacturing_loop_sim.sim.resources import Station, StationState, Conveyor


@dataclass
class SimulationState:
    """
    Thread-safe snapshot of simulation state for visualization.
    """
    time: float = 0.0
    
    # Pallets
    pallets: List[Dict[str, Any]] = field(default_factory=list)
    
    # Stations
    station_1: Dict[str, Any] = field(default_factory=dict)
    station_2: Dict[str, Any] = field(default_factory=dict)
    
    # Conveyors
    conveyor_1: Dict[str, Any] = field(default_factory=dict)  # S1 → S2
    conveyor_2: Dict[str, Any] = field(default_factory=dict)  # S2 → S1
    
    # Aggregate metrics
    total_cycles: int = 0
    wip_s1_queue: int = 0
    wip_s2_queue: int = 0
    wip_conveyor_1: int = 0
    wip_conveyor_2: int = 0
    
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
                pallets=list(self.pallets),
                station_1=dict(self.station_1),
                station_2=dict(self.station_2),
                conveyor_1=dict(self.conveyor_1),
                conveyor_2=dict(self.conveyor_2),
                total_cycles=self.total_cycles,
                wip_s1_queue=self.wip_s1_queue,
                wip_s2_queue=self.wip_s2_queue,
                wip_conveyor_1=self.wip_conveyor_1,
                wip_conveyor_2=self.wip_conveyor_2,
            )


class ClosedLoopSimulation:
    """
    Simulation engine for a two-station closed-loop manufacturing system.
    
    Implements blocking-after-service semantics where a station holds
    a pallet after processing until the downstream conveyor has space.
    
    System topology:
        S1 → Conveyor1 → S2 → Conveyor2 → S1 (loop)
    """
    
    def __init__(self, config: SimConfig = None, seed: int = None):
        """Initialize the simulation."""
        self.config = config or SimConfig()
        
        # Random number generator
        self._seed = seed if seed is not None else self.config.seed
        self.rng = random.Random(self._seed)
        
        # SimPy environment
        self.env = simpy.Environment()
        
        # Create stations
        self.station_1 = Station(
            id=1,
            name="S1",
            env=self.env,
            time_min=self.config.s1_time_min,
            time_mode=self.config.s1_time_mode,
            time_max=self.config.s1_time_max,
            position_x=0.2,
            position_y=0.5,
        )
        
        self.station_2 = Station(
            id=2,
            name="S2", 
            env=self.env,
            time_min=self.config.s2_time_min,
            time_mode=self.config.s2_time_mode,
            time_max=self.config.s2_time_max,
            position_x=0.8,
            position_y=0.5,
        )
        
        # Create conveyors
        self.conveyor_1 = Conveyor(
            id=1,
            name="S1→S2",
            env=self.env,
            capacity=self.config.conveyor_s1_to_s2_capacity,
            transfer_time=self.config.conveyor_s1_to_s2_transfer_time,
            start_x=0.25,
            start_y=0.35,
            end_x=0.75,
            end_y=0.35,
        )
        
        self.conveyor_2 = Conveyor(
            id=2,
            name="S2→S1",
            env=self.env,
            capacity=self.config.conveyor_s2_to_s1_capacity,
            transfer_time=self.config.conveyor_s2_to_s1_transfer_time,
            start_x=0.75,
            start_y=0.65,
            end_x=0.25,
            end_y=0.65,
        )
        
        # Link stations to downstream conveyors
        self.station_1.downstream_conveyor = self.conveyor_1
        self.station_2.downstream_conveyor = self.conveyor_2
        
        # Create pallets
        self.pallets: List[Pallet] = []
        for i in range(self.config.num_pallets):
            pallet = Pallet(
                id=i + 1,
                creation_time=0.0,
                state=PalletState.WAITING_S1,
            )
            self.pallets.append(pallet)
        
        # State for visualization
        self.state = SimulationState()
        
        # Running flags
        self._running = False
        self._stop_requested = False
        self._initialized = False
    
    def _update_state(self):
        """Update the shared state snapshot for visualization."""
        # Update pallet visual positions
        self._update_pallet_positions()
        
        self.state.update(
            time=self.env.now,
            pallets=[p.to_dict() for p in self.pallets],
            station_1=self.station_1.to_dict(),
            station_2=self.station_2.to_dict(),
            conveyor_1=self.conveyor_1.to_dict(),
            conveyor_2=self.conveyor_2.to_dict(),
            total_cycles=sum(p.total_cycles for p in self.pallets),
            wip_s1_queue=self.station_1.queue_length,
            wip_s2_queue=self.station_2.queue_length,
            wip_conveyor_1=self.conveyor_1.count,
            wip_conveyor_2=self.conveyor_2.count,
        )
    
    def _update_pallet_positions(self):
        """Update visual positions of all pallets based on their state."""
        # Count pallets in each location for positioning
        s1_queue_count = 0
        s2_queue_count = 0
        c1_count = 0
        c2_count = 0
        
        for pallet in self.pallets:
            if pallet.state in (PalletState.WAITING_S1,):
                pallet.visual_x = 0.08
                pallet.visual_y = 0.4 + s1_queue_count * 0.06
                s1_queue_count += 1
            elif pallet.state in (PalletState.PROCESSING_S1, PalletState.BLOCKED_S1):
                pallet.visual_x = 0.2
                pallet.visual_y = 0.5
            elif pallet.state == PalletState.IN_CONVEYOR_1:
                # Position along conveyor
                c1_pallets = self.conveyor_1.pallets
                if pallet in c1_pallets:
                    idx = c1_pallets.index(pallet)
                    progress = (idx + 1) / (len(c1_pallets) + 1)
                    pallet.visual_x = 0.28 + progress * 0.44
                    pallet.visual_y = 0.35
                c1_count += 1
            elif pallet.state in (PalletState.WAITING_S2,):
                pallet.visual_x = 0.92
                pallet.visual_y = 0.4 + s2_queue_count * 0.06
                s2_queue_count += 1
            elif pallet.state in (PalletState.PROCESSING_S2, PalletState.BLOCKED_S2):
                pallet.visual_x = 0.8
                pallet.visual_y = 0.5
            elif pallet.state == PalletState.IN_CONVEYOR_2:
                # Position along conveyor (reverse direction)
                c2_pallets = self.conveyor_2.pallets
                if pallet in c2_pallets:
                    idx = c2_pallets.index(pallet)
                    progress = (idx + 1) / (len(c2_pallets) + 1)
                    pallet.visual_x = 0.72 - progress * 0.44
                    pallet.visual_y = 0.65
                c2_count += 1
    
    def get_state(self) -> SimulationState:
        """Get current simulation state for visualization."""
        self._update_state()
        return self.state.copy()
    
    # === MAIN PALLET PROCESS ===
    
    def pallet_process(self, pallet: Pallet):
        """
        Main process for a single pallet circulating through the system.
        
        This implements the closed-loop behavior with blocking-after-service.
        
        Flow: S1 → C1 → S2 → C2 → (loop back to S1)
        """
        while not self._stop_requested:
            # === STAGE 1: Process at S1 ===
            yield from self._process_at_station(pallet, self.station_1, 
                                                 PalletState.WAITING_S1,
                                                 PalletState.PROCESSING_S1,
                                                 PalletState.BLOCKED_S1)
            
            # === STAGE 2: Transfer to Conveyor 1 (S1 → S2) ===
            yield from self._transfer_to_conveyor(pallet, self.station_1, 
                                                   self.conveyor_1,
                                                   PalletState.IN_CONVEYOR_1)
            
            # === STAGE 3: Arrive at S2 (get from conveyor 1) ===
            # Note: conveyor.get() blocks until there's a pallet
            # But we know we just put this pallet on it, so it should be there
            _ = yield self.conveyor_1.get()  # Remove ourselves from conveyor
            pallet.set_state(PalletState.WAITING_S2, self.env.now)
            self._update_state()
            
            # === STAGE 4: Process at S2 ===
            yield from self._process_at_station(pallet, self.station_2,
                                                 PalletState.WAITING_S2,
                                                 PalletState.PROCESSING_S2,
                                                 PalletState.BLOCKED_S2)
            
            # === STAGE 5: Transfer to Conveyor 2 (back to S1) ===
            yield from self._transfer_to_conveyor(pallet, self.station_2,
                                                   self.conveyor_2,
                                                   PalletState.IN_CONVEYOR_2)
            
            # === STAGE 6: Arrive back at S1 queue ===
            # Get pallet from conveyor 2
            _ = yield self.conveyor_2.get()
            pallet.set_state(PalletState.WAITING_S1, self.env.now)
            
            # Increment cycle count
            pallet._complete_cycle(self.env.now)
            
            self._update_state()
    
    def _process_at_station(self, pallet: Pallet, station: Station,
                            waiting_state: PalletState,
                            processing_state: PalletState,
                            blocked_state: PalletState):
        """
        Process a pallet at a station with blocking-after-service.
        """
        # Wait for station to be available
        with station.resource.request() as req:
            yield req
            
            # Now at station
            pallet.set_state(processing_state, self.env.now)
            station.current_pallet = pallet
            station.set_state(StationState.PROCESSING, self.env.now)
            self._update_state()
            
            # Process
            process_time = station.get_processing_time(self.rng)
            yield self.env.timeout(process_time)
            
            station.pallets_processed += 1
            
            # === BLOCKING-AFTER-SERVICE ===
            # Check if downstream conveyor has space
            if not station.downstream_conveyor.can_accept():
                # Enter blocked state
                pallet.set_state(blocked_state, self.env.now)
                station.set_state(StationState.BLOCKED, self.env.now)
                self._update_state()
                
                # Wait until space is available
                while not station.downstream_conveyor.can_accept():
                    yield self.env.timeout(0.1)  # Check periodically
                    if self._stop_requested:
                        return
            
            # Space available, ready to release
            station.current_pallet = None
            station.set_state(StationState.IDLE, self.env.now)
    
    def _transfer_to_conveyor(self, pallet: Pallet, station: Station,
                               conveyor: Conveyor, conveyor_state: PalletState):
        """
        Transfer pallet from station to conveyor.
        """
        # Put pallet on conveyor
        pallet.set_state(conveyor_state, self.env.now)
        yield conveyor.put(pallet)
        
        # Transfer time
        yield self.env.timeout(conveyor.transfer_time)
        
        self._update_state()
    
    def _feeder_process(self, conveyor: Conveyor, destination_station: Station,
                        source_state: PalletState, dest_waiting_state: PalletState):
        """
        Process that moves pallets from conveyor to station queue.
        """
        while not self._stop_requested:
            # Wait for pallet on conveyor
            if conveyor.is_empty:
                yield self.env.timeout(0.1)
                continue
            
            # Check if station can accept (has queue space)
            # For simplicity, we assume infinite queue at station entrance
            # The pallet_process will request the station resource
            
            yield self.env.timeout(0.1)
    
    # === MONITORING ===
    
    def monitor_process(self, interval: float = 5.0):
        """Periodic monitoring process for status logging."""
        while not self._stop_requested:
            yield self.env.timeout(interval)
            
            if self.config.log_events:
                now = self.env.now
                s1_state = "PROC" if self.station_1.state == StationState.PROCESSING else \
                          "BLOCK" if self.station_1.state == StationState.BLOCKED else "IDLE"
                s2_state = "PROC" if self.station_2.state == StationState.PROCESSING else \
                          "BLOCK" if self.station_2.state == StationState.BLOCKED else "IDLE"
                
                total_cycles = sum(p.total_cycles for p in self.pallets)
                
                print(f"[{now:6.1f}] S1={s1_state:5} Q={self.station_1.queue_length} | "
                      f"C1={self.conveyor_1.count}/{self.conveyor_1.capacity} | "
                      f"S2={s2_state:5} Q={self.station_2.queue_length} | "
                      f"C2={self.conveyor_2.count}/{self.conveyor_2.capacity} | "
                      f"Cycles={total_cycles}")
    
    # === SIMULATION CONTROL ===
    
    def initialize(self):
        """Initialize simulation processes without running."""
        if self._initialized:
            return
        
        self._running = True
        self._stop_requested = False
        self._initialized = True
        
        # Initially, place all pallets in the S1 queue (conveyor 2)
        # Actually, let's distribute them: some at S1 queue, some on conveyors
        # For simplicity, all start at S1 waiting
        
        # Start pallet processes
        for pallet in self.pallets:
            self.env.process(self.pallet_process(pallet))
        
        # Start monitor
        self.env.process(self.monitor_process(self.config.monitor_interval))
    
    def run(self, duration: float = None):
        """Run the simulation."""
        duration = duration or self.config.duration
        
        if not self._initialized:
            self.initialize()
        
        step_size = 0.1
        
        while self.env.now < duration and not self._stop_requested:
            try:
                self.env.run(until=min(self.env.now + step_size, duration))
                self._update_state()
            except simpy.core.EmptySchedule:
                break
        
        self._running = False
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
        return self._running
    
    @property
    def current_time(self) -> float:
        return self.env.now
    
    @property
    def throughput(self) -> float:
        """Cycles completed per time unit."""
        if self.env.now == 0:
            return 0.0
        total_cycles = sum(p.total_cycles for p in self.pallets)
        return total_cycles / self.env.now
    
    @property 
    def total_wip(self) -> int:
        """Total work-in-progress (pallets in system)."""
        return len(self.pallets)
