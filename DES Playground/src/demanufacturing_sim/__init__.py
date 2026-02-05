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

Extended with Holonic Multi-Agent Control (v2.0):
- ProductHolon → Autonomous product agent with uncertainty model
- ResourceHolon → Station agent with health/failure model
- TransportHolon → AGV/conveyor agent
- SystemHolon → System-wide state aggregator
- CognitiveOrchestrator → LLM-swappable meta-layer for policy modulation
"""

__version__ = "2.0.0"
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

# Holonic extensions (optional imports)
try:
    from demanufacturing_sim.sim.holonic_engine import (
        HolonicDemanufacturingSimulation,
        ControlMode,
        EnhancedSimulationState
    )
    from demanufacturing_sim.agents.product_holon import ProductHolon
    from demanufacturing_sim.agents.resource_holon import ResourceHolon
    from demanufacturing_sim.agents.transport_holon import TransportHolon
    from demanufacturing_sim.agents.system_holon import SystemHolon
    from demanufacturing_sim.agents.holon_manager import HolonManager
    from demanufacturing_sim.orchestrator.llm_orchestrator import CognitiveOrchestrator
    from demanufacturing_sim.sim.fault_injection import FaultInjector, FaultScenario
    from demanufacturing_sim.viz.holonic_renderer import HolonicFactoryRenderer
    from demanufacturing_sim.metrics_holonic import EnhancedMetricsCollector
    
    HOLONIC_AVAILABLE = True
except ImportError:
    HOLONIC_AVAILABLE = False

__all__ = [
    # Core
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
    # Holonic extensions
    "HolonicDemanufacturingSimulation",
    "ControlMode",
    "EnhancedSimulationState",
    "ProductHolon",
    "ResourceHolon", 
    "TransportHolon",
    "SystemHolon",
    "HolonManager",
    "CognitiveOrchestrator",
    "FaultInjector",
    "FaultScenario",
    "HolonicFactoryRenderer",
    "EnhancedMetricsCollector",
    "HOLONIC_AVAILABLE",
]
