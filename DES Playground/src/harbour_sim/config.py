"""
Configuration module for HarbourSim.

Provides a centralized configuration with all simulation parameters.
"""

from dataclasses import dataclass, field
from typing import Tuple
import yaml
from pathlib import Path


@dataclass
class SimConfig:
    """
    Complete configuration for the harbour simulation.
    
    All time units are in minutes unless otherwise specified.
    """
    
    # === Random seed for reproducibility ===
    seed: int = 42
    
    # === Simulation duration ===
    duration: float = 480.0  # 8 hours in minutes
    
    # === Ship arrival parameters ===
    ship_interarrival_mean: float = 60.0  # Mean time between ship arrivals (exponential)
    ship_containers_min: int = 20  # Min containers per ship
    ship_containers_max: int = 80  # Max containers per ship
    num_berths: int = 3  # Number of berths for ships
    
    # === Quay crane parameters ===
    num_quay_cranes: int = 4  # Total quay cranes
    crane_unload_time_min: float = 1.5  # Min unload time per container (triangular)
    crane_unload_time_mode: float = 2.5  # Mode unload time per container (slightly faster)
    crane_unload_time_max: float = 4.5  # Max unload time per container
    crane_move_speed: float = 10.0  # Crane movement speed (units per minute)
    
    # === Yard parameters ===
    yard_width: int = 20  # Number of columns (bays)
    yard_height: int = 10  # Number of rows
    yard_max_stack_height: int = 4  # Max containers stacked
    
    # === Yard mover parameters ===
    num_yard_movers: int = 6  # Straddle carriers / reach stackers (increased)
    yard_mover_time_min: float = 1.0  # Min yard move time
    yard_mover_time_mode: float = 2.0  # Mode yard move time
    yard_mover_time_max: float = 3.0  # Max yard move time
    
    # === Truck parameters ===
    truck_interarrival_mean: float = 2.0  # Mean time between truck arrivals (increased arrival rate)
    truck_load_time_min: float = 2.0  # Min loading time
    truck_load_time_mode: float = 3.0  # Mode loading time
    truck_load_time_max: float = 5.0  # Max loading time
    num_truck_gates: int = 6  # Number of truck gates (increased)
    
    # === Visualization parameters ===
    render_enabled: bool = True
    render_fps: int = 30
    render_speed: float = 10.0  # Simulation speed multiplier
    window_width: int = 1400
    window_height: int = 900
    
    # === Colors (RGB tuples) ===
    color_water: Tuple[int, int, int] = (64, 164, 223)
    color_quay: Tuple[int, int, int] = (128, 128, 128)
    color_yard: Tuple[int, int, int] = (200, 200, 180)
    color_road: Tuple[int, int, int] = (80, 80, 80)
    color_ship: Tuple[int, int, int] = (100, 60, 40)
    color_crane: Tuple[int, int, int] = (255, 200, 0)
    color_container_default: Tuple[int, int, int] = (0, 100, 200)
    color_truck: Tuple[int, int, int] = (50, 50, 50)
    
    # === Logging ===
    log_events: bool = True
    log_file: str = "simulation.log"
    
    # === Output ===
    results_file: str = "results.csv"
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        assert self.num_berths > 0, "Must have at least 1 berth"
        assert self.num_quay_cranes > 0, "Must have at least 1 crane"
        assert self.yard_width > 0 and self.yard_height > 0, "Yard must have positive dimensions"
        assert self.yard_max_stack_height > 0, "Stack height must be positive"
        assert self.duration > 0, "Duration must be positive"
    
    @classmethod
    def from_yaml(cls, path: str) -> "SimConfig":
        """Load configuration from a YAML file."""
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(**data)
    
    def to_yaml(self, path: str) -> None:
        """Save configuration to a YAML file."""
        data = {
            k: v for k, v in self.__dict__.items()
            if not k.startswith('_')
        }
        # Convert tuples to lists for YAML
        for key, value in data.items():
            if isinstance(value, tuple):
                data[key] = list(value)
        
        with open(path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    @property
    def yard_capacity(self) -> int:
        """Total yard capacity in containers."""
        return self.yard_width * self.yard_height * self.yard_max_stack_height


# Default configuration instance
DEFAULT_CONFIG = SimConfig()
