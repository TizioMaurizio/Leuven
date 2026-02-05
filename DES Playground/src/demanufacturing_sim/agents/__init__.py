"""
Holonic Multi-Agent Layer for DIGITAU Demanufacturing Simulator.

This module implements a holonic control architecture with four types of agents:
- ProductHolon: Represents individual EoL products with state, goals, and routing
- ResourceHolon: Represents physical stations with capabilities and health
- TransportHolon: Represents AGVs/conveyors for material movement
- SystemHolon: Aggregates system state and resolves deadlocks

Each holon communicates via an event bus abstraction (pub/sub pattern).
"""

from demanufacturing_sim.agents.event_bus import EventBus, Event, EventType
from demanufacturing_sim.agents.product_holon import ProductHolon
from demanufacturing_sim.agents.resource_holon import ResourceHolon
from demanufacturing_sim.agents.transport_holon import TransportHolon
from demanufacturing_sim.agents.system_holon import SystemHolon
from demanufacturing_sim.agents.holon_manager import HolonManager

__all__ = [
    'EventBus',
    'Event', 
    'EventType',
    'ProductHolon',
    'ResourceHolon',
    'TransportHolon',
    'SystemHolon',
    'HolonManager'
]
