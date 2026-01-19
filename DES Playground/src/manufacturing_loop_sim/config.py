"""
Configuration module for Manufacturing Loop Simulator.

Provides centralized configuration for the two-station closed-loop
production system with blocking-after-service semantics.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class SimConfig:
    """
    Configuration for the closed-loop manufacturing simulation.
    
    All time units are in seconds (typical for lab-scale systems).
    
    SYSTEM DESCRIPTION:
    - Two stations (S1, S2) processing pallets in sequence
    - Conveyors between stations act as finite buffers
    - Pallets circulate continuously in a closed loop
    - Blocking-after-service: station waits for buffer space before releasing
    
    CONCEPTUAL MAPPING:
    - Container/Product → Pallet
    - Processing Station → Station (S1, S2)
    - Yard/Buffer → Conveyor buffer
    - No arrivals → Closed loop initialization
    - No departures → Loop back to start
    """
    
    # === Random seed for reproducibility ===
    seed: int = 42
    
    # === Simulation duration ===
    duration: float = 600.0  # 10 minutes in seconds
    
    # === Pallet parameters ===
    num_pallets: int = 12  # Fixed number of pallets in the system
    
    # === Station parameters ===
    # Station S1: First processing station
    s1_time_min: float = 3.0   # Triangular distribution minimum
    s1_time_mode: float = 5.0  # Triangular distribution mode
    s1_time_max: float = 8.0   # Triangular distribution maximum
    
    # Station S2: Second processing station
    s2_time_min: float = 2.0   # Triangular distribution minimum
    s2_time_mode: float = 3.0  # Triangular distribution mode
    s2_time_max: float = 5.0   # Triangular distribution maximum
    
    # === Conveyor/Buffer parameters ===
    # Conveyor C1: From S1 to S2
    conveyor_s1_to_s2_capacity: int = 8
    conveyor_s1_to_s2_transfer_time: float = 5.0  # Time to move pallet onto conveyor (increased for visibility)
    
    # Conveyor C2: From S2 back to S1 (closing the loop)
    conveyor_s2_to_s1_capacity: int = 8
    conveyor_s2_to_s1_transfer_time: float = 5.0
    
    # === Station degradation (optional extension) ===
    enable_degradation: bool = False
    degradation_factor: float = 1.5  # Multiplier for processing time when degraded
    degradation_probability: float = 0.01  # Probability of degradation per cycle
    repair_time_mean: float = 30.0  # Mean repair time
    
    # === Visualization parameters ===
    render_fps: int = 30
    render_speed: float = 10.0  # Simulation speed multiplier for rendering
    window_width: int = 1200
    window_height: int = 700
    
    # === Colors (RGB tuples) ===
    color_background: Tuple[int, int, int] = (240, 245, 250)
    color_station_idle: Tuple[int, int, int] = (100, 180, 100)  # Green
    color_station_busy: Tuple[int, int, int] = (200, 140, 80)   # Orange
    color_station_blocked: Tuple[int, int, int] = (200, 80, 80) # Red
    color_station_degraded: Tuple[int, int, int] = (180, 80, 180)  # Purple
    color_conveyor: Tuple[int, int, int] = (180, 180, 190)
    color_conveyor_full: Tuple[int, int, int] = (220, 180, 180)
    color_pallet: Tuple[int, int, int] = (60, 100, 180)  # Blue
    color_pallet_processing: Tuple[int, int, int] = (180, 140, 60)  # Gold
    color_text: Tuple[int, int, int] = (40, 40, 50)
    color_grid: Tuple[int, int, int] = (200, 200, 210)
    
    # === Logging ===
    log_events: bool = True
    monitor_interval: float = 5.0  # Interval for status logging
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        assert self.num_pallets > 0, "Must have at least 1 pallet"
        assert self.conveyor_s1_to_s2_capacity > 0, "Conveyor capacity must be positive"
        assert self.conveyor_s2_to_s1_capacity > 0, "Conveyor capacity must be positive"
        assert self.duration > 0, "Duration must be positive"
        assert self.s1_time_min <= self.s1_time_mode <= self.s1_time_max, "Invalid S1 triangular params"
        assert self.s2_time_min <= self.s2_time_mode <= self.s2_time_max, "Invalid S2 triangular params"
    
    @property
    def total_buffer_capacity(self) -> int:
        """Total buffer capacity in the system."""
        return self.conveyor_s1_to_s2_capacity + self.conveyor_s2_to_s1_capacity
    
    @property
    def system_capacity(self) -> int:
        """Maximum pallets the system can hold (stations + buffers)."""
        return 2 + self.total_buffer_capacity  # 2 stations + conveyors
