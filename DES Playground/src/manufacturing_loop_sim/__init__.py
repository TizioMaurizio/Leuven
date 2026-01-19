"""
Manufacturing Loop Simulator - Two-Station Closed-Loop Production System

A discrete-event simulation of a lab-scale closed-loop manufacturing system
with blocking-after-service semantics, based on the WSC case study.

Adapted from HarbourSim/DIGITAU with the following conceptual mapping:
- Container/Product → Pallet (circulating workpiece carrier)
- Processing Station → Station (S1, S2)
- Buffer/Yard → Conveyor (finite buffer between stations)
- No arrivals/departures → Closed loop (pallets circulate forever)
- Exit decision → Loop-back to first station

SYSTEM CHARACTERISTICS:
- Two processing stations (S1, S2) in series
- Conveyors as finite buffers between stations
- Fixed number of pallets circulating (no entry/exit)
- Blocking-after-service: station holds pallet until downstream buffer has space
- Stochastic processing times (triangular distribution)
"""

__version__ = "1.0.0"
__title__ = "Manufacturing Loop Simulator"

from manufacturing_loop_sim.config import SimConfig
from manufacturing_loop_sim.sim.entities import Pallet, PalletState
from manufacturing_loop_sim.sim.resources import Station, StationState, Conveyor
from manufacturing_loop_sim.sim.engine import ClosedLoopSimulation, SimulationState
from manufacturing_loop_sim.metrics import MetricsCollector, SimulationMetrics

__all__ = [
    "SimConfig",
    "Pallet", "PalletState",
    "Station", "StationState", "Conveyor",
    "ClosedLoopSimulation", "SimulationState",
    "MetricsCollector", "SimulationMetrics",
]
