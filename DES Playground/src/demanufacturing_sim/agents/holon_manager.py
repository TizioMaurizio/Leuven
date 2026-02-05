"""
HolonManager: Coordinates all holons and integrates with SimPy simulation.

This manager bridges the holonic agent layer with the underlying SimPy
simulation engine, creating and managing holons for each entity.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, TYPE_CHECKING
import random

from demanufacturing_sim.agents.event_bus import EventBus, Event, EventType
from demanufacturing_sim.agents.product_holon import (
    ProductHolon, ProductBOM, ProductUncertaintyLevel, DisassemblyIntent
)
from demanufacturing_sim.agents.resource_holon import (
    ResourceHolon, ResourceType, HealthState, TaskRequest
)
from demanufacturing_sim.agents.transport_holon import (
    TransportHolon, TransportType, TransportTask, Location
)
from demanufacturing_sim.agents.system_holon import SystemHolon

if TYPE_CHECKING:
    from demanufacturing_sim.sim.entities import Product
    from demanufacturing_sim.sim.resources import ProcessingStation


@dataclass
class HolonManagerConfig:
    """Configuration for the holon manager."""
    num_agvs: int = 4
    observation_noise: float = 0.15
    mtbf_base: float = 480.0  # Mean time between failures (minutes)
    mttr_base: float = 30.0   # Mean time to repair (minutes)
    degradation_rate: float = 0.001


class HolonManager:
    """
    Manages all holons in the system and coordinates their interactions.
    
    Responsibilities:
    - Create holons for products, resources, and transports
    - Route events between holons via event bus
    - Integrate with SimPy simulation
    - Provide aggregated state for orchestrator
    """
    
    def __init__(self, config: HolonManagerConfig = None, seed: int = None):
        self.config = config or HolonManagerConfig()
        self.rng = random.Random(seed)
        
        # Event bus for communication
        self.event_bus = EventBus()
        
        # Holon registries
        self.product_holons: Dict[str, ProductHolon] = {}
        self.resource_holons: Dict[str, ResourceHolon] = {}
        self.transport_holons: Dict[str, TransportHolon] = {}
        
        # System holon
        self.system_holon = SystemHolon()
        
        # Factory layout (locations for transport)
        self.locations: Dict[str, Location] = {}
        
        # Statistics
        self.total_products_created = 0
        self.total_products_completed = 0
    
    def initialize_factory_layout(self, config: Any) -> None:
        """
        Initialize factory locations for transport routing.
        
        Creates locations for all stations, buffers, and exit gates.
        """
        # Receiving docks
        for i in range(config.num_receiving_docks):
            self.locations[f"dock_{i}"] = Location(
                id=f"dock_{i}",
                name=f"Receiving Dock {i+1}",
                x=100 + i * 150,
                y=50,
                location_type="dock"
            )
        
        # Inspection stations
        for i in range(config.num_inspection_stations):
            self.locations[f"inspection_{i}"] = Location(
                id=f"inspection_{i}",
                name=f"Inspection {i+1}",
                x=100 + i * 100,
                y=200,
                location_type="station"
            )
        
        # Dismantling stations
        for i in range(config.num_dismantling_stations):
            self.locations[f"dismantling_{i}"] = Location(
                id=f"dismantling_{i}",
                name=f"Dismantling {i+1}",
                x=100 + i * 100,
                y=350,
                location_type="station"
            )
        
        # Testing stations
        for i in range(config.num_testing_stations):
            self.locations[f"testing_{i}"] = Location(
                id=f"testing_{i}",
                name=f"Testing {i+1}",
                x=100 + i * 100,
                y=500,
                location_type="station"
            )
        
        # Buffer area
        self.locations["buffer_main"] = Location(
            id="buffer_main",
            name="Main Buffer",
            x=400,
            y=400,
            location_type="buffer"
        )
        
        # Exit gates
        exit_x = 600
        self.locations["gate_reuse"] = Location(
            id="gate_reuse",
            name="Reuse Exit",
            x=exit_x,
            y=150,
            location_type="gate"
        )
        self.locations["gate_remanufacture"] = Location(
            id="gate_remanufacture",
            name="Remanufacture Exit",
            x=exit_x,
            y=300,
            location_type="gate"
        )
        self.locations["gate_recycle"] = Location(
            id="gate_recycle",
            name="Recycle Exit",
            x=exit_x,
            y=450,
            location_type="gate"
        )
        self.locations["gate_disposal"] = Location(
            id="gate_disposal",
            name="Disposal Exit",
            x=exit_x,
            y=550,
            location_type="gate"
        )
    
    def create_resource_holons(self, 
                               inspection_stations: List,
                               dismantling_stations: List,
                               testing_stations: List) -> None:
        """
        Create resource holons for all processing stations.
        
        Args:
            inspection_stations: List of inspection ProcessingStation objects
            dismantling_stations: List of dismantling ProcessingStation objects
            testing_stations: List of testing ProcessingStation objects
        """
        # Inspection holons
        for station in inspection_stations:
            holon_id = f"resource_inspection_{station.id}"
            holon = ResourceHolon(
                id=holon_id,
                resource_type=ResourceType.INSPECTION,
                mtbf=self.config.mtbf_base * 1.2,  # Inspection more reliable
                mttr=self.config.mttr_base * 0.5,
                degradation_rate=self.config.degradation_rate * 0.5,
                base_processing_time=4.0
            )
            self.resource_holons[holon_id] = holon
            self.system_holon.register_resource_holon(holon_id, holon)
            self.event_bus.register_holon(holon_id, self._handle_resource_event)
        
        # Dismantling holons (robots - more prone to failure)
        for station in dismantling_stations:
            holon_id = f"resource_dismantling_{station.id}"
            holon = ResourceHolon(
                id=holon_id,
                resource_type=ResourceType.DISASSEMBLY_ROBOT,
                mtbf=self.config.mtbf_base * 0.8,  # Robots less reliable
                mttr=self.config.mttr_base * 1.5,
                degradation_rate=self.config.degradation_rate * 1.5,
                base_processing_time=10.0
            )
            self.resource_holons[holon_id] = holon
            self.system_holon.register_resource_holon(holon_id, holon)
            self.event_bus.register_holon(holon_id, self._handle_resource_event)
        
        # Testing holons
        for station in testing_stations:
            holon_id = f"resource_testing_{station.id}"
            holon = ResourceHolon(
                id=holon_id,
                resource_type=ResourceType.TEST_BENCH,
                mtbf=self.config.mtbf_base,
                mttr=self.config.mttr_base,
                degradation_rate=self.config.degradation_rate,
                base_processing_time=6.0
            )
            self.resource_holons[holon_id] = holon
            self.system_holon.register_resource_holon(holon_id, holon)
            self.event_bus.register_holon(holon_id, self._handle_resource_event)
        
        # Additional resources: Shredder and Sorter for recycle path
        for i in range(2):  # 2 shredders
            holon_id = f"resource_shredder_{i}"
            holon = ResourceHolon(
                id=holon_id,
                resource_type=ResourceType.SHREDDER,
                mtbf=self.config.mtbf_base * 0.6,  # High wear
                mttr=self.config.mttr_base * 2.0,
                degradation_rate=self.config.degradation_rate * 2.0,
                base_processing_time=3.0
            )
            self.resource_holons[holon_id] = holon
            self.system_holon.register_resource_holon(holon_id, holon)
        
        for i in range(2):  # 2 sorters
            holon_id = f"resource_sorter_{i}"
            holon = ResourceHolon(
                id=holon_id,
                resource_type=ResourceType.SORTER,
                mtbf=self.config.mtbf_base,
                mttr=self.config.mttr_base,
                degradation_rate=self.config.degradation_rate,
                base_processing_time=2.0
            )
            self.resource_holons[holon_id] = holon
            self.system_holon.register_resource_holon(holon_id, holon)
    
    def create_transport_holons(self) -> None:
        """Create transport holons (AGVs) for material movement."""
        for i in range(self.config.num_agvs):
            holon_id = f"transport_agv_{i}"
            holon = TransportHolon(
                id=holon_id,
                transport_type=TransportType.AGV,
                speed=15.0,  # Distance units per minute
                capacity=1,
                home_position=(300.0, 400.0)
            )
            holon.set_locations(self.locations)
            holon.position = (300.0 + i * 50, 400.0)
            
            self.transport_holons[holon_id] = holon
            self.system_holon.register_transport_holon(holon_id, holon)
            self.event_bus.register_holon(holon_id, self._handle_transport_event)
    
    def create_product_holon(self, product: "Product", 
                            arrival_time: float) -> ProductHolon:
        """
        Create a product holon for a new product.
        
        Args:
            product: The underlying Product entity
            arrival_time: Simulation time of arrival
        
        Returns:
            New ProductHolon
        """
        self.total_products_created += 1
        holon_id = f"product_{product.id}"
        
        # Generate random BOM with hidden structure
        bom = ProductBOM.generate_random(
            self.rng,
            min_components=3,
            max_components=8
        )
        bom._observation_noise = self.config.observation_noise
        
        # Determine initial value estimate based on product quality
        initial_value = 20.0 + self.rng.gauss(30, 15)
        
        holon = ProductHolon(
            id=holon_id,
            product=product,
            bom=bom,
            uncertainty_level=ProductUncertaintyLevel.HIGH,
            predicted_value=initial_value,
            current_stage="arrived"
        )
        
        # Set base priority (can be random or based on product type)
        holon.base_priority = self.rng.uniform(0.5, 1.5)
        
        holon.record_event("created", arrival_time, {
            "batch_id": product.batch_id,
            "initial_value": initial_value,
            "components_count": len(bom.true_components)
        })
        
        self.product_holons[holon_id] = holon
        self.system_holon.register_product_holon(holon_id, holon)
        self.event_bus.register_holon(holon_id, self._handle_product_event)
        
        # Publish arrival event
        self.event_bus.publish(Event(
            event_type=EventType.PRODUCT_ARRIVED,
            source_id=holon_id,
            timestamp=arrival_time,
            payload={"product_id": product.id, "holon_id": holon_id}
        ))
        
        return holon
    
    def remove_product_holon(self, product_id: int, exit_time: float) -> None:
        """Remove a product holon when it exits the system."""
        holon_id = f"product_{product_id}"
        
        if holon_id in self.product_holons:
            holon = self.product_holons[holon_id]
            holon.current_stage = "exited"
            holon.record_event("exited", exit_time, {"route": holon.chosen_route})
            
            self.system_holon.unregister_product_holon(holon_id)
            self.event_bus.unregister_holon(holon_id)
            del self.product_holons[holon_id]
            
            self.total_products_completed += 1
            
            # Publish exit event
            self.event_bus.publish(Event(
                event_type=EventType.PRODUCT_EXITED,
                source_id=holon_id,
                timestamp=exit_time,
                payload={"product_id": product_id, "route": holon.chosen_route}
            ))
    
    def get_product_holon(self, product_id: int) -> Optional[ProductHolon]:
        """Get product holon by product ID."""
        holon_id = f"product_{product_id}"
        return self.product_holons.get(holon_id)
    
    def get_resource_holon(self, station_type: str, 
                          station_id: int) -> Optional[ResourceHolon]:
        """Get resource holon for a station."""
        holon_id = f"resource_{station_type}_{station_id}"
        return self.resource_holons.get(holon_id)
    
    def get_available_transport(self) -> Optional[TransportHolon]:
        """Get an available transport holon."""
        for holon in self.transport_holons.values():
            if holon.is_available:
                return holon
        return None
    
    def update_product_stage(self, product_id: int, stage: str,
                            timestamp: float) -> None:
        """Update a product's current stage."""
        holon = self.get_product_holon(product_id)
        if holon:
            holon.current_stage = stage
            holon.record_event(f"stage_{stage}", timestamp)
            self.system_holon.mark_product_progress(f"product_{product_id}", timestamp)
    
    def process_inspection_result(self, product_id: int, 
                                  timestamp: float) -> Dict[str, Any]:
        """
        Process inspection result for a product.
        
        Returns inspection findings and updated predictions.
        """
        holon = self.get_product_holon(product_id)
        if not holon:
            return {}
        
        # Update holon state after inspection
        holon.update_after_inspection(timestamp, self.rng)
        
        # Make routing prediction
        quality_thresholds = {"reuse": 0.8, "remanufacture": 0.4}
        suggested_route = holon.determine_route(quality_thresholds)
        
        # Check if deep disassembly is recommended
        deep_disassembly = holon.should_request_deep_disassembly()
        if deep_disassembly:
            holon.disassembly_intent = DisassemblyIntent.DEEP
        
        # Publish event
        self.event_bus.publish(Event(
            event_type=EventType.PRODUCT_INSPECTION_COMPLETE,
            source_id=f"product_{product_id}",
            timestamp=timestamp,
            payload={
                "product_id": product_id,
                "predicted_value": holon.predicted_value,
                "uncertainty": holon.uncertainty_level.name,
                "suggested_route": suggested_route,
                "deep_disassembly": deep_disassembly
            }
        ))
        
        return {
            "predicted_value": holon.predicted_value,
            "uncertainty": holon.uncertainty_level,
            "suggested_route": suggested_route,
            "disassembly_intent": holon.disassembly_intent
        }
    
    def process_disassembly_result(self, product_id: int,
                                   timestamp: float) -> Dict[str, Any]:
        """Process disassembly result for a product."""
        holon = self.get_product_holon(product_id)
        if not holon:
            return {}
        
        holon.update_after_disassembly(timestamp, rng=self.rng)
        
        # Publish event
        self.event_bus.publish(Event(
            event_type=EventType.PRODUCT_DISASSEMBLY_COMPLETE,
            source_id=f"product_{product_id}",
            timestamp=timestamp,
            payload={
                "product_id": product_id,
                "components_revealed": len(holon.bom.revealed_components),
                "predicted_value": holon.predicted_value
            }
        ))
        
        return {
            "predicted_value": holon.predicted_value,
            "uncertainty": holon.uncertainty_level,
            "components_revealed": len(holon.bom.revealed_components)
        }
    
    def request_resource(self, product_id: int, resource_type: str,
                        timestamp: float) -> Optional[str]:
        """
        Request a resource for a product using holonic negotiation.
        
        Returns the assigned resource holon ID, or None if rejected.
        """
        holon = self.get_product_holon(product_id)
        if not holon:
            return None
        
        # Find compatible resources
        compatible = [
            r for r in self.resource_holons.values()
            if r.resource_type.name.lower() in resource_type.lower() or
               r.can_handle(resource_type)
        ]
        
        if not compatible:
            return None
        
        # Create task request
        request = TaskRequest(
            request_id=f"req_{product_id}_{timestamp}",
            product_holon_id=f"product_{product_id}",
            task_type=resource_type,
            priority=holon.effective_priority,
            timestamp=timestamp
        )
        
        # Try each compatible resource (prefer available ones with shorter queues)
        compatible.sort(key=lambda r: (
            0 if r.is_available else 1,
            r.queue_length,
            -r.effective_rate
        ))
        
        for resource in compatible:
            response = resource.request_task(request)
            if response.accepted:
                holon.current_station_id = resource.id
                holon.pending_requests.append(request.request_id)
                return resource.id
        
        # All rejected
        holon.rejection_count += 1
        holon.last_rejection_time = timestamp
        return None
    
    def update_system_state(self, timestamp: float) -> Dict[str, Any]:
        """Update and return system state snapshot."""
        snapshot = self.system_holon.update_snapshot(timestamp)
        return self.system_holon.get_orchestrator_context()
    
    def apply_orchestrator_guidance(self, guidance: Dict[str, Any],
                                   timestamp: float) -> None:
        """
        Apply guidance from the cognitive orchestrator.
        
        Args:
            guidance: Guidance signals from orchestrator
            timestamp: Current simulation time
        """
        # Apply priority multipliers
        if "priority_adjustments" in guidance:
            for product_id, multiplier in guidance["priority_adjustments"].items():
                holon = self.product_holons.get(product_id)
                if holon:
                    holon.priority_multiplier = multiplier
        
        # Apply disassembly depth guidance
        if "disassembly_depth" in guidance:
            depth = guidance["disassembly_depth"]
            depth_enum = {
                "none": DisassemblyIntent.NONE,
                "shallow": DisassemblyIntent.SHALLOW,
                "standard": DisassemblyIntent.STANDARD,
                "deep": DisassemblyIntent.DEEP
            }.get(depth, DisassemblyIntent.STANDARD)
            
            # Apply to products not yet in disassembly
            for holon in self.product_holons.values():
                if holon.current_stage in ("arrived", "inspection", "awaiting_disassembly"):
                    holon.disassembly_intent = depth_enum
        
        # Apply resource slowdowns/speedups
        if "resource_rates" in guidance:
            for resource_id, rate in guidance["resource_rates"].items():
                holon = self.resource_holons.get(resource_id)
                if holon:
                    holon.health_percentage = min(holon.health_percentage, rate)
        
        # Publish guidance event
        self.event_bus.publish(Event(
            event_type=EventType.GUIDANCE_POLICY_MODULATION,
            source_id="orchestrator",
            timestamp=timestamp,
            payload=guidance
        ))
    
    def _handle_product_event(self, event: Event) -> None:
        """Handle events targeted at product holons."""
        pass  # Placeholder for future event-driven behavior
    
    def _handle_resource_event(self, event: Event) -> None:
        """Handle events targeted at resource holons."""
        pass
    
    def _handle_transport_event(self, event: Event) -> None:
        """Handle events targeted at transport holons."""
        pass
    
    def get_state_summary(self) -> Dict[str, Any]:
        """Get summary of holon manager state."""
        return {
            "total_products_created": self.total_products_created,
            "total_products_completed": self.total_products_completed,
            "active_products": len(self.product_holons),
            "resource_count": len(self.resource_holons),
            "transport_count": len(self.transport_holons),
            "event_bus_stats": self.event_bus.get_statistics()
        }
