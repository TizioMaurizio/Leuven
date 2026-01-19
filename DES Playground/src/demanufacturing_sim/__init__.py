"""
DIGITAU - Digital Twin for Battery De/Remanufacturing

A discrete-event simulation and visualization system for modeling
battery and product lifecycle management in a circular economy context.

Adapted from HarbourSim with the following conceptual mapping:
- Container → Product/Battery with Digital Product Passport (DPP)
- Ship arrival → Incoming end-of-life product stream
- Quay crane → Processing station (inspection, dismantling, testing)
- Yard grid → Intermediate buffers / WIP areas
- Yard mover → Robot or human-robot collaborative operator
- Truck pickup → Exit decision (reuse, remanufacture, recycle)
- Truck departure → Product leaves system with assigned destination
"""

__version__ = "1.0.0"
__title__ = "DIGITAU Demanufacturing Simulator"

from demanufacturing_sim.config import SimConfig
from demanufacturing_sim.sim.entities import (
    Product, ProductState, DigitalProductPassport,
    ProductBatch, BatchState,
    ExitVehicle, ExitVehicleState, ExitDecision
)
from demanufacturing_sim.sim.engine import DemanufacturingSimulation
from demanufacturing_sim.sim.resources import (
    ProcessingStation, StationManager,
    Buffer, BufferSlot,
    Operator, OperatorPool,
    ExitGate
)
from demanufacturing_sim.sim.policies import (
    RoutingPolicy, QualityBasedRoutingPolicy,
    StationAssignmentPolicy, ProductSelectionPolicy
)
from demanufacturing_sim.metrics import MetricsCollector, SimulationMetrics
from demanufacturing_sim.viz.renderer import FactoryRenderer

__all__ = [
    "SimConfig",
    "Product", "ProductState", "DigitalProductPassport",
    "ProductBatch", "BatchState",
    "ExitVehicle", "ExitVehicleState", "ExitDecision",
    "DemanufacturingSimulation",
    "ProcessingStation", "StationManager",
    "Buffer", "BufferSlot",
    "Operator", "OperatorPool",
    "ExitGate",
    "RoutingPolicy", "QualityBasedRoutingPolicy",
    "StationAssignmentPolicy", "ProductSelectionPolicy",
    "MetricsCollector", "SimulationMetrics",
    "FactoryRenderer",
]
