"""
Policy definitions for the DIGITAU demanufacturing simulation.

Contains routing policies for station assignment, buffer placement,
product selection, and exit decision making.

CONCEPT MAPPING (from HarbourSim):
- CraneAssignmentPolicy → StationAssignmentPolicy
- YardPlacementPolicy → BufferPlacementPolicy
- ContainerSelectionPolicy → ProductSelectionPolicy

NEW ADDITIONS:
- RoutingPolicy: Determines next processing stage and station
- ExitDecisionPolicy: Determines REUSE/REMANUFACTURE/RECYCLE decision
"""

from typing import List, Optional, Protocol, TYPE_CHECKING
from abc import ABC, abstractmethod
import random

from demanufacturing_sim.sim.entities import ExitDecision, ProductState

if TYPE_CHECKING:
    from demanufacturing_sim.sim.entities import Product, ProductBatch, ExitVehicle
    from demanufacturing_sim.sim.resources import (
        ProcessingStation, StationManager, Buffer, BufferSlot
    )


class StationAssignmentPolicy(ABC):
    """Abstract base for station assignment policies."""
    
    @abstractmethod
    def assign_station(
        self,
        stations: "StationManager",
        product: "Product"
    ) -> Optional["ProcessingStation"]:
        """
        Assign a station to process a product.
        
        Args:
            stations: Station manager
            product: Product to process
        
        Returns:
            Assigned station, or None if none available.
        """
        pass


class NearestStationPolicy(StationAssignmentPolicy):
    """Assign the nearest available station."""
    
    def assign_station(
        self,
        stations: "StationManager",
        product: "Product"
    ) -> Optional["ProcessingStation"]:
        return stations.get_available_station()


class LeastBusyStationPolicy(StationAssignmentPolicy):
    """Assign the station with lowest utilization."""
    
    def assign_station(
        self,
        stations: "StationManager",
        product: "Product"
    ) -> Optional["ProcessingStation"]:
        available = [s for s in stations.stations if not s.is_busy]
        if not available:
            return None
        
        # Sort by products processed (prefer less loaded)
        available.sort(key=lambda s: s.products_processed)
        return available[0]


class BufferPlacementPolicy(ABC):
    """Abstract base for buffer placement policies."""
    
    @abstractmethod
    def select_slot(
        self,
        buffer: "Buffer",
        product: "Product"
    ) -> Optional["BufferSlot"]:
        """
        Select a buffer slot for a product.
        
        Args:
            buffer: The buffer
            product: Product to place
        
        Returns:
            Selected slot, or None if buffer is full.
        """
        pass


class LowestStackPlacementPolicy(BufferPlacementPolicy):
    """Place products in the slot with lowest stack height."""
    
    def select_slot(
        self,
        buffer: "Buffer",
        product: "Product"
    ) -> Optional["BufferSlot"]:
        return buffer.find_available_slot()


class GroupByDecisionPolicy(BufferPlacementPolicy):
    """
    Group products by their exit decision in the buffer.
    
    Helps organize products for efficient exit vehicle loading.
    """
    
    def select_slot(
        self,
        buffer: "Buffer",
        product: "Product"
    ) -> Optional["BufferSlot"]:
        decision = product.exit_decision
        
        # Define regions for each decision
        # REUSE: left third, REMANUFACTURE: middle, RECYCLE: right third
        if decision == ExitDecision.REUSE:
            x_start, x_end = 0, buffer.width // 3
        elif decision == ExitDecision.REMANUFACTURE:
            x_start, x_end = buffer.width // 3, 2 * buffer.width // 3
        else:
            x_start, x_end = 2 * buffer.width // 3, buffer.width
        
        # Find lowest stack in region
        best_slot = None
        min_height = float('inf')
        
        for x in range(x_start, x_end):
            for y in range(buffer.height):
                slot = buffer.grid[x][y]
                if not slot.is_full and slot.height < min_height:
                    min_height = slot.height
                    best_slot = slot
        
        # Fallback to any available slot
        if best_slot is None:
            best_slot = buffer.find_available_slot()
        
        return best_slot


class ProductSelectionPolicy(ABC):
    """Abstract base for selecting products for exit vehicle pickup."""
    
    @abstractmethod
    def select_product(
        self,
        buffer: "Buffer",
        vehicle: "ExitVehicle"
    ) -> Optional["Product"]:
        """
        Select a product for an exit vehicle to pick up.
        
        Args:
            buffer: The buffer
            vehicle: Exit vehicle requesting pickup
        
        Returns:
            Selected product, or None if none available.
        """
        pass


class FIFOProductPolicy(ProductSelectionPolicy):
    """
    First-In-First-Out: select the product that arrived earliest.
    
    Only considers accessible products (top of stacks) matching
    the vehicle's destination.
    """
    
    def select_product(
        self,
        buffer: "Buffer",
        vehicle: "ExitVehicle"
    ) -> Optional["Product"]:
        return buffer.get_product_by_decision(vehicle.destination)


class HighestValueFirstPolicy(ProductSelectionPolicy):
    """Select the highest estimated value product first."""
    
    def select_product(
        self,
        buffer: "Buffer",
        vehicle: "ExitVehicle"
    ) -> Optional["Product"]:
        accessible: List["Product"] = []
        
        for x in range(buffer.width):
            for y in range(buffer.height):
                slot = buffer.grid[x][y]
                top = slot.peek_top()
                if top is not None and top.state == ProductState.IN_BUFFER:
                    if top.exit_decision == vehicle.destination:
                        accessible.append(top)
        
        if not accessible:
            return None
        
        # Sort by estimated value (highest first)
        accessible.sort(
            key=lambda p: p.dpp.estimated_value if p.dpp else 0,
            reverse=True
        )
        return accessible[0]


class RoutingPolicy(ABC):
    """
    Abstract base for routing products through processing stages.
    
    Determines the next processing step based on product state,
    predictions, and system conditions.
    """
    
    @abstractmethod
    def get_next_stage(self, product: "Product") -> Optional[str]:
        """
        Determine the next processing stage for a product.
        
        Args:
            product: The product to route
        
        Returns:
            Next stage name ("inspection", "dismantling", "testing", "buffer", "exit")
            or None if product should wait.
        """
        pass


class SequentialRoutingPolicy(RoutingPolicy):
    """
    Standard sequential routing through all stages.
    
    ARRIVAL → INSPECTION → DISMANTLING → TESTING → BUFFER → EXIT
    """
    
    def get_next_stage(self, product: "Product") -> Optional[str]:
        state = product.state
        
        if state == ProductState.CREATED:
            return "inspection"
        elif state == ProductState.AWAITING_DISMANTLING:
            return "dismantling"
        elif state == ProductState.AWAITING_TESTING:
            return "testing"
        elif state == ProductState.IN_BUFFER:
            if product.exit_decision != ExitDecision.UNDECIDED:
                return "exit"
            return None  # Wait for decision
        
        return None


class QualityBasedRoutingPolicy(RoutingPolicy):
    """
    Routing that can skip stages based on quality predictions.
    
    - Very high quality products may skip dismantling (direct reuse)
    - Very low quality products may skip testing (direct recycle)
    """
    
    def __init__(self, skip_dismantling_threshold: float = 0.9,
                 skip_testing_threshold: float = 0.2):
        self.skip_dismantling_threshold = skip_dismantling_threshold
        self.skip_testing_threshold = skip_testing_threshold
    
    def get_next_stage(self, product: "Product") -> Optional[str]:
        state = product.state
        predicted_quality = product.predicted_quality
        
        if state == ProductState.CREATED:
            return "inspection"
        
        elif state == ProductState.AWAITING_DISMANTLING:
            # Very high quality: skip dismantling, go to testing
            if predicted_quality >= self.skip_dismantling_threshold:
                return "testing"
            return "dismantling"
        
        elif state == ProductState.AWAITING_TESTING:
            # Very low quality: skip testing, go to buffer (recycle)
            if predicted_quality <= self.skip_testing_threshold:
                return "buffer"
            return "testing"
        
        elif state == ProductState.IN_BUFFER:
            if product.exit_decision != ExitDecision.UNDECIDED:
                return "exit"
            return None
        
        return None


class ExitDecisionPolicy(ABC):
    """Abstract base for determining exit decisions."""
    
    @abstractmethod
    def make_decision(self, product: "Product", config) -> ExitDecision:
        """
        Make an exit decision for a product.
        
        Args:
            product: The product
            config: Simulation configuration with thresholds
        
        Returns:
            ExitDecision (REUSE, REMANUFACTURE, or RECYCLE)
        """
        pass


class QualityThresholdDecisionPolicy(ExitDecisionPolicy):
    """
    Make exit decisions based on quality thresholds.
    
    - Quality >= reuse_threshold → REUSE
    - Quality >= remanufacture_threshold → REMANUFACTURE
    - Otherwise → RECYCLE
    """
    
    def make_decision(self, product: "Product", config) -> ExitDecision:
        quality = product.quality
        
        if quality >= config.quality_reuse_threshold:
            return ExitDecision.REUSE
        elif quality >= config.quality_remanufacture_threshold:
            return ExitDecision.REMANUFACTURE
        else:
            return ExitDecision.RECYCLE


class PredictiveDecisionPolicy(ExitDecisionPolicy):
    """
    Make exit decisions using predicted quality.
    
    Uses the DPP's predicted quality with confidence weighting.
    """
    
    def make_decision(self, product: "Product", config) -> ExitDecision:
        if product.dpp is None:
            return ExitDecision.RECYCLE
        
        # Weighted average of actual and predicted quality
        confidence = product.dpp.prediction_confidence
        actual = product.dpp.current_quality
        predicted = product.dpp.predicted_quality
        
        # Blend based on confidence
        effective_quality = confidence * predicted + (1 - confidence) * actual
        
        if effective_quality >= config.quality_reuse_threshold:
            return ExitDecision.REUSE
        elif effective_quality >= config.quality_remanufacture_threshold:
            return ExitDecision.REMANUFACTURE
        else:
            return ExitDecision.RECYCLE


class PolicyManager:
    """
    Manages all policies for the simulation.
    
    Provides a centralized way to configure and access policies.
    """
    
    def __init__(
        self,
        station_policy: StationAssignmentPolicy = None,
        buffer_policy: BufferPlacementPolicy = None,
        product_policy: ProductSelectionPolicy = None,
        routing_policy: RoutingPolicy = None,
        exit_decision_policy: ExitDecisionPolicy = None
    ):
        self.station_policy = station_policy or NearestStationPolicy()
        self.buffer_policy = buffer_policy or GroupByDecisionPolicy()
        self.product_policy = product_policy or FIFOProductPolicy()
        self.routing_policy = routing_policy or SequentialRoutingPolicy()
        self.exit_decision_policy = exit_decision_policy or QualityThresholdDecisionPolicy()
    
    @classmethod
    def default(cls) -> "PolicyManager":
        """Create a policy manager with default policies."""
        return cls(
            station_policy=NearestStationPolicy(),
            buffer_policy=GroupByDecisionPolicy(),
            product_policy=FIFOProductPolicy(),
            routing_policy=SequentialRoutingPolicy(),
            exit_decision_policy=QualityThresholdDecisionPolicy()
        )
    
    @classmethod
    def predictive(cls) -> "PolicyManager":
        """Create a policy manager with predictive/quality-based policies."""
        return cls(
            station_policy=LeastBusyStationPolicy(),
            buffer_policy=GroupByDecisionPolicy(),
            product_policy=HighestValueFirstPolicy(),
            routing_policy=QualityBasedRoutingPolicy(),
            exit_decision_policy=PredictiveDecisionPolicy()
        )
