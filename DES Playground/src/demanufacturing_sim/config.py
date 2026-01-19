"""
Configuration module for DIGITAU Demanufacturing Simulator.

Provides centralized configuration with all simulation parameters
for the battery/product demanufacturing digital twin.
"""

from dataclasses import dataclass, field
from typing import Tuple, List, Dict
import yaml
from pathlib import Path


@dataclass
class SimConfig:
    """
    Complete configuration for the demanufacturing simulation.
    
    All time units are in minutes unless otherwise specified.
    
    CONCEPT MAPPING (from HarbourSim):
    - Ships → Product batches arriving for processing
    - Quay cranes → Processing stations (inspection, dismantling, testing)
    - Yard → Buffer/WIP storage areas
    - Yard movers → Operators (robots or human-robot collaborative)
    - Trucks → Exit vehicles carrying processed products to destinations
    - Truck gates → Exit gates for different destinations
    """
    
    # === Random seed for reproducibility ===
    seed: int = 42
    
    # === Simulation duration ===
    duration: float = 480.0  # 8 hours in minutes
    
    # === Incoming product stream parameters ===
    # (Mapped from: ship arrival)
    batch_interarrival_mean: float = 30.0  # Mean time between batch arrivals (exponential)
    products_per_batch_min: int = 5  # Min products per batch
    products_per_batch_max: int = 20  # Max products per batch
    num_receiving_docks: int = 2  # Number of receiving docks
    
    # === Processing station parameters ===
    # (Mapped from: quay cranes)
    # Multi-stage processing: INSPECTION → DISMANTLING → TESTING
    num_inspection_stations: int = 2
    num_dismantling_stations: int = 3
    num_testing_stations: int = 2
    
    # Processing times (triangular distribution)
    inspection_time_min: float = 2.0
    inspection_time_mode: float = 4.0
    inspection_time_max: float = 8.0
    
    dismantling_time_min: float = 5.0
    dismantling_time_mode: float = 10.0
    dismantling_time_max: float = 20.0
    
    testing_time_min: float = 3.0
    testing_time_mode: float = 6.0
    testing_time_max: float = 12.0
    
    # === Buffer/WIP parameters ===
    # (Mapped from: yard)
    buffer_width: int = 10  # Columns in buffer grid
    buffer_height: int = 6  # Rows in buffer grid
    buffer_max_stack: int = 3  # Max products stacked
    
    # === Operator parameters ===
    # (Mapped from: yard movers)
    num_operators: int = 4  # Robots/HRC operators
    operator_move_time_min: float = 0.5
    operator_move_time_mode: float = 1.0
    operator_move_time_max: float = 2.0
    
    # === Exit gate parameters ===
    # (Mapped from: truck gates)
    # Three exit paths: REUSE, REMANUFACTURE, RECYCLE
    num_reuse_gates: int = 1
    num_remanufacture_gates: int = 1
    num_recycle_gates: int = 1
    
    # Exit vehicle arrival rates
    reuse_vehicle_interarrival: float = 15.0
    remanufacture_vehicle_interarrival: float = 20.0
    recycle_vehicle_interarrival: float = 25.0
    
    # Loading times
    exit_load_time_min: float = 1.0
    exit_load_time_mode: float = 2.0
    exit_load_time_max: float = 4.0
    
    # === Product quality parameters ===
    # Quality score determines exit decision
    quality_reuse_threshold: float = 0.8  # Quality >= 0.8 → REUSE
    quality_remanufacture_threshold: float = 0.4  # 0.4 <= Quality < 0.8 → REMANUFACTURE
    # Quality < 0.4 → RECYCLE
    
    # Initial quality distribution (normal)
    initial_quality_mean: float = 0.5
    initial_quality_std: float = 0.2
    
    # Quality degradation during processing
    quality_degradation_per_stage: float = 0.02
    
    # === Predictive model parameters ===
    # Simple stochastic model for predicted vs actual quality
    prediction_accuracy: float = 0.85  # How accurate predictions are
    prediction_noise: float = 0.1  # Noise in predictions
    
    # === Value parameters (for KPIs) ===
    value_per_reuse: float = 100.0  # Value recovered per reused product
    value_per_remanufacture: float = 60.0
    value_per_recycle: float = 20.0
    cost_per_minute_processing: float = 0.5
    
    # === Visualization parameters ===
    render_enabled: bool = True
    render_fps: int = 30
    render_speed: float = 10.0  # Simulation speed multiplier
    window_width: int = 1400
    window_height: int = 900
    
    # === Colors (RGB tuples) ===
    color_background: Tuple[int, int, int] = (240, 240, 245)
    color_floor: Tuple[int, int, int] = (200, 200, 200)
    color_station_inspection: Tuple[int, int, int] = (100, 180, 100)
    color_station_dismantling: Tuple[int, int, int] = (180, 140, 80)
    color_station_testing: Tuple[int, int, int] = (100, 140, 200)
    color_buffer: Tuple[int, int, int] = (220, 220, 210)
    color_operator: Tuple[int, int, int] = (80, 80, 120)
    color_product_reuse: Tuple[int, int, int] = (50, 200, 50)  # Green
    color_product_remanufacture: Tuple[int, int, int] = (200, 180, 50)  # Yellow
    color_product_recycle: Tuple[int, int, int] = (200, 80, 80)  # Red
    color_product_unknown: Tuple[int, int, int] = (150, 150, 150)  # Gray
    color_exit_gate: Tuple[int, int, int] = (100, 100, 120)
    
    # === Logging ===
    log_events: bool = True
    log_file: str = "simulation.log"
    
    # === Output ===
    results_file: str = "results.csv"
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        assert self.num_receiving_docks > 0, "Must have at least 1 receiving dock"
        assert self.num_inspection_stations > 0, "Must have at least 1 inspection station"
        assert self.buffer_width > 0 and self.buffer_height > 0, "Buffer must have positive dimensions"
        assert self.duration > 0, "Duration must be positive"
        assert 0 <= self.quality_remanufacture_threshold < self.quality_reuse_threshold <= 1.0
    
    @property
    def total_stations(self) -> int:
        """Total number of processing stations."""
        return (self.num_inspection_stations + 
                self.num_dismantling_stations + 
                self.num_testing_stations)
    
    @property
    def total_exit_gates(self) -> int:
        """Total number of exit gates."""
        return self.num_reuse_gates + self.num_remanufacture_gates + self.num_recycle_gates
    
    @property
    def buffer_capacity(self) -> int:
        """Total buffer capacity in products."""
        return self.buffer_width * self.buffer_height * self.buffer_max_stack
    
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


# Default configuration instance
DEFAULT_CONFIG = SimConfig()
