"""
Entity definitions for the closed-loop manufacturing simulation.

Contains the Pallet class representing workpiece carriers that circulate
continuously through the two-station system.

CONCEPT MAPPING:
- Container (HarbourSim) / Product (DIGITAU) → Pallet
- Container lifecycle → Pallet cycle through S1 → C1 → S2 → C2 → S1 ...
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List, Dict, Any


class PalletState(Enum):
    """
    States for a pallet in the closed-loop system.
    
    Lifecycle: AT_S1 → IN_CONVEYOR_1 → AT_S2 → IN_CONVEYOR_2 → AT_S1 ...
    """
    # At stations
    WAITING_S1 = auto()      # Waiting in queue at S1
    PROCESSING_S1 = auto()   # Being processed at S1
    BLOCKED_S1 = auto()      # Finished at S1, waiting for buffer space
    
    WAITING_S2 = auto()      # Waiting in queue at S2
    PROCESSING_S2 = auto()   # Being processed at S2
    BLOCKED_S2 = auto()      # Finished at S2, waiting for buffer space
    
    # On conveyors
    IN_CONVEYOR_1 = auto()   # On conveyor from S1 to S2
    IN_CONVEYOR_2 = auto()   # On conveyor from S2 back to S1
    
    @property
    def is_at_station(self) -> bool:
        """Check if pallet is at a station (any state)."""
        return self in (
            PalletState.WAITING_S1, PalletState.PROCESSING_S1, PalletState.BLOCKED_S1,
            PalletState.WAITING_S2, PalletState.PROCESSING_S2, PalletState.BLOCKED_S2
        )
    
    @property
    def is_processing(self) -> bool:
        """Check if pallet is being processed."""
        return self in (PalletState.PROCESSING_S1, PalletState.PROCESSING_S2)
    
    @property
    def is_blocked(self) -> bool:
        """Check if pallet is blocked waiting for buffer space."""
        return self in (PalletState.BLOCKED_S1, PalletState.BLOCKED_S2)
    
    @property
    def is_on_conveyor(self) -> bool:
        """Check if pallet is on a conveyor."""
        return self in (PalletState.IN_CONVEYOR_1, PalletState.IN_CONVEYOR_2)
    
    @property
    def current_location(self) -> str:
        """Human-readable location description."""
        mapping = {
            PalletState.WAITING_S1: "S1 Queue",
            PalletState.PROCESSING_S1: "S1 Processing",
            PalletState.BLOCKED_S1: "S1 Blocked",
            PalletState.WAITING_S2: "S2 Queue",
            PalletState.PROCESSING_S2: "S2 Processing",
            PalletState.BLOCKED_S2: "S2 Blocked",
            PalletState.IN_CONVEYOR_1: "Conveyor S1→S2",
            PalletState.IN_CONVEYOR_2: "Conveyor S2→S1",
        }
        return mapping.get(self, "Unknown")


@dataclass
class PalletCycleRecord:
    """Record of a single cycle through the system."""
    cycle_number: int
    start_time: float
    end_time: Optional[float] = None
    s1_wait_time: float = 0.0
    s1_process_time: float = 0.0
    s1_block_time: float = 0.0
    conveyor_1_time: float = 0.0
    s2_wait_time: float = 0.0
    s2_process_time: float = 0.0
    s2_block_time: float = 0.0
    conveyor_2_time: float = 0.0
    
    @property
    def cycle_time(self) -> Optional[float]:
        """Total time for this cycle."""
        if self.end_time is not None:
            return self.end_time - self.start_time
        return None
    
    @property
    def total_block_time(self) -> float:
        """Total blocking time in this cycle."""
        return self.s1_block_time + self.s2_block_time


@dataclass
class Pallet:
    """
    A pallet (workpiece carrier) circulating in the closed-loop system.
    
    Mapped from: Container (HarbourSim) / Product (DIGITAU)
    
    Key difference: Pallets never leave the system - they circulate forever.
    Each pallet tracks its complete history of cycles through the system.
    """
    id: int
    state: PalletState = PalletState.WAITING_S1
    
    # Timing tracking
    creation_time: float = 0.0
    last_state_change: float = 0.0
    
    # Current cycle tracking
    current_cycle: int = 0
    current_cycle_start: float = 0.0
    
    # Accumulated times for current cycle
    _current_s1_wait_start: Optional[float] = None
    _current_s1_process_start: Optional[float] = None
    _current_s1_block_start: Optional[float] = None
    _current_c1_start: Optional[float] = None
    _current_s2_wait_start: Optional[float] = None
    _current_s2_process_start: Optional[float] = None
    _current_s2_block_start: Optional[float] = None
    _current_c2_start: Optional[float] = None
    
    # Cycle history
    completed_cycles: List[PalletCycleRecord] = field(default_factory=list)
    _current_cycle_record: Optional[PalletCycleRecord] = None
    
    # Position for visualization (normalized 0-1)
    visual_x: float = 0.0
    visual_y: float = 0.0
    
    # Statistics
    total_cycles: int = 0
    total_processing_time: float = 0.0
    total_blocking_time: float = 0.0
    total_waiting_time: float = 0.0
    total_conveyor_time: float = 0.0
    
    def __post_init__(self):
        """Initialize first cycle record."""
        self._start_new_cycle(self.creation_time)
    
    def _start_new_cycle(self, time: float):
        """Start a new cycle through the system."""
        self.current_cycle += 1
        self.current_cycle_start = time
        self._current_cycle_record = PalletCycleRecord(
            cycle_number=self.current_cycle,
            start_time=time
        )
    
    def _complete_cycle(self, time: float):
        """Complete the current cycle and archive it."""
        if self._current_cycle_record:
            self._current_cycle_record.end_time = time
            self.completed_cycles.append(self._current_cycle_record)
            self.total_cycles += 1
    
    def set_state(self, new_state: PalletState, time: float):
        """
        Update pallet state and track timing metrics.
        
        This is the main state transition method that properly accounts
        for time spent in each phase.
        """
        old_state = self.state
        elapsed = time - self.last_state_change
        
        # Accumulate time from previous state
        self._accumulate_time(old_state, elapsed)
        
        # Handle state-specific start tracking
        self._handle_state_entry(new_state, time)
        
        # Check for cycle completion (entering WAITING_S1 after being elsewhere)
        if new_state == PalletState.WAITING_S1 and old_state != PalletState.WAITING_S1:
            if old_state == PalletState.IN_CONVEYOR_2:
                # Completed a full cycle
                self._complete_cycle(time)
                self._start_new_cycle(time)
        
        self.state = new_state
        self.last_state_change = time
    
    def _accumulate_time(self, state: PalletState, elapsed: float):
        """Accumulate time for the given state."""
        if self._current_cycle_record is None:
            return
            
        if state == PalletState.WAITING_S1:
            self._current_cycle_record.s1_wait_time += elapsed
            self.total_waiting_time += elapsed
        elif state == PalletState.PROCESSING_S1:
            self._current_cycle_record.s1_process_time += elapsed
            self.total_processing_time += elapsed
        elif state == PalletState.BLOCKED_S1:
            self._current_cycle_record.s1_block_time += elapsed
            self.total_blocking_time += elapsed
        elif state == PalletState.IN_CONVEYOR_1:
            self._current_cycle_record.conveyor_1_time += elapsed
            self.total_conveyor_time += elapsed
        elif state == PalletState.WAITING_S2:
            self._current_cycle_record.s2_wait_time += elapsed
            self.total_waiting_time += elapsed
        elif state == PalletState.PROCESSING_S2:
            self._current_cycle_record.s2_process_time += elapsed
            self.total_processing_time += elapsed
        elif state == PalletState.BLOCKED_S2:
            self._current_cycle_record.s2_block_time += elapsed
            self.total_blocking_time += elapsed
        elif state == PalletState.IN_CONVEYOR_2:
            self._current_cycle_record.conveyor_2_time += elapsed
            self.total_conveyor_time += elapsed
    
    def _handle_state_entry(self, new_state: PalletState, time: float):
        """Handle specific state entry tracking."""
        # Reset tracking variables for the new state
        pass  # Time tracking is done via elapsed calculation
    
    @property
    def avg_cycle_time(self) -> Optional[float]:
        """Average cycle time across completed cycles."""
        if not self.completed_cycles:
            return None
        times = [c.cycle_time for c in self.completed_cycles if c.cycle_time]
        return sum(times) / len(times) if times else None
    
    @property
    def avg_block_time_per_cycle(self) -> Optional[float]:
        """Average blocking time per cycle."""
        if not self.completed_cycles:
            return None
        return sum(c.total_block_time for c in self.completed_cycles) / len(self.completed_cycles)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for state snapshots."""
        return {
            "id": self.id,
            "state": self.state.name,
            "location": self.state.current_location,
            "current_cycle": self.current_cycle,
            "total_cycles": self.total_cycles,
            "visual_x": self.visual_x,
            "visual_y": self.visual_y,
            "is_processing": self.state.is_processing,
            "is_blocked": self.state.is_blocked,
        }
    
    def __repr__(self) -> str:
        return f"Pallet(id={self.id}, state={self.state.name}, cycles={self.total_cycles})"
