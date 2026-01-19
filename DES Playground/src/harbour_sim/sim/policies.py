"""
Policy definitions for the harbour simulation.

Contains dispatch and placement policies for crane assignment,
yard slot selection, and truck-container matching.
"""

from typing import List, Optional, Protocol, TYPE_CHECKING
from abc import ABC, abstractmethod
import random

if TYPE_CHECKING:
    from harbour_sim.sim.entities import Container, Ship, Truck
    from harbour_sim.sim.resources import (
        QuayCrane, QuayCraneManager, Yard, YardSlot, Berth, BerthManager
    )


class CraneAssignmentPolicy(ABC):
    """Abstract base for crane assignment policies."""
    
    @abstractmethod
    def assign_crane(
        self,
        cranes: "QuayCraneManager",
        ship: "Ship",
        berth: "Berth"
    ) -> Optional["QuayCrane"]:
        """
        Assign a crane to unload a ship.
        
        Args:
            cranes: Crane manager
            ship: Ship to unload
            berth: Berth where ship is docked
        
        Returns:
            Assigned crane, or None if none available.
        """
        pass


class NearestCranePolicy(CraneAssignmentPolicy):
    """Assign the crane nearest to the ship's berth."""
    
    def assign_crane(
        self,
        cranes: "QuayCraneManager",
        ship: "Ship",
        berth: "Berth"
    ) -> Optional["QuayCrane"]:
        available = [c for c in cranes.cranes if c.berth_id is None]
        
        if not available:
            return None
        
        # Find nearest crane to berth
        berth_x = berth.position_x
        available.sort(key=lambda c: abs(c.position_x - berth_x))
        
        crane = available[0]
        cranes.assign_crane_to_berth(crane, berth.id)
        return crane


class FirstAvailableCranePolicy(CraneAssignmentPolicy):
    """Assign the first available crane by ID."""
    
    def assign_crane(
        self,
        cranes: "QuayCraneManager",
        ship: "Ship",
        berth: "Berth"
    ) -> Optional["QuayCrane"]:
        crane = cranes.get_available_crane()
        if crane:
            cranes.assign_crane_to_berth(crane, berth.id)
        return crane


class YardPlacementPolicy(ABC):
    """Abstract base for yard placement policies."""
    
    @abstractmethod
    def select_slot(
        self,
        yard: "Yard",
        container: "Container"
    ) -> Optional["YardSlot"]:
        """
        Select a yard slot for a container.
        
        Args:
            yard: The yard
            container: Container to place
        
        Returns:
            Selected slot, or None if yard is full.
        """
        pass


class NearestToPickupPolicy(YardPlacementPolicy):
    """
    Place containers nearest to the pickup point (high x values).
    
    This policy prefers slots with higher x coordinates,
    assuming trucks pick up from the far end of the yard.
    """
    
    def select_slot(
        self,
        yard: "Yard",
        container: "Container"
    ) -> Optional["YardSlot"]:
        # Search from highest x (pickup end) to lowest
        for x in range(yard.width - 1, -1, -1):
            for y in range(yard.height):
                slot = yard.grid[x][y]
                if not slot.is_full:
                    return slot
        return None


class LowestStackPolicy(YardPlacementPolicy):
    """Place containers in the slot with lowest stack height."""
    
    def select_slot(
        self,
        yard: "Yard",
        container: "Container"
    ) -> Optional["YardSlot"]:
        best_slot = None
        min_height = float('inf')
        
        for x in range(yard.width):
            for y in range(yard.height):
                slot = yard.grid[x][y]
                if not slot.is_full and slot.height < min_height:
                    min_height = slot.height
                    best_slot = slot
        
        return best_slot


class RandomSlotPolicy(YardPlacementPolicy):
    """Place containers in a random available slot."""
    
    def __init__(self, rng: random.Random = None):
        self.rng = rng or random.Random()
    
    def select_slot(
        self,
        yard: "Yard",
        container: "Container"
    ) -> Optional["YardSlot"]:
        available = []
        for x in range(yard.width):
            for y in range(yard.height):
                slot = yard.grid[x][y]
                if not slot.is_full:
                    available.append(slot)
        
        if not available:
            return None
        
        return self.rng.choice(available)


class BalancedRowPolicy(YardPlacementPolicy):
    """
    Balance containers across rows, preferring lower stacks.
    
    This helps maintain even distribution and reduces reshuffling.
    """
    
    def select_slot(
        self,
        yard: "Yard",
        container: "Container"
    ) -> Optional["YardSlot"]:
        # Calculate total height per row
        row_heights = []
        for y in range(yard.height):
            total = sum(yard.grid[x][y].height for x in range(yard.width))
            row_heights.append((y, total))
        
        # Sort by total height (ascending)
        row_heights.sort(key=lambda x: x[1])
        
        # Try to place in the least loaded row
        for y, _ in row_heights:
            for x in range(yard.width):
                slot = yard.grid[x][y]
                if not slot.is_full:
                    return slot
        
        return None


class ContainerSelectionPolicy(ABC):
    """Abstract base for selecting containers for truck pickup."""
    
    @abstractmethod
    def select_container(
        self,
        yard: "Yard",
        truck: "Truck"
    ) -> Optional["Container"]:
        """
        Select a container for a truck to pick up.
        
        Args:
            yard: The yard
            truck: Truck requesting pickup
        
        Returns:
            Selected container, or None if none available.
        """
        pass


class FIFOContainerPolicy(ContainerSelectionPolicy):
    """
    First-In-First-Out: select the container that arrived earliest.
    
    Only considers accessible containers (top of stacks).
    """
    
    def select_container(
        self,
        yard: "Yard",
        truck: "Truck"
    ) -> Optional["Container"]:
        return yard.get_accessible_container()


class NearestContainerPolicy(ContainerSelectionPolicy):
    """
    Select the nearest accessible container to the pickup point.
    
    Pickup point is assumed to be at high x values.
    """
    
    def select_container(
        self,
        yard: "Yard",
        truck: "Truck"
    ) -> Optional["Container"]:
        # Search from highest x (nearest to pickup)
        for x in range(yard.width - 1, -1, -1):
            for y in range(yard.height):
                slot = yard.grid[x][y]
                top = slot.peek_top()
                if top is not None and top.state.name == 'IN_YARD':
                    return top
        return None


class PolicyManager:
    """
    Manages all policies for the simulation.
    
    Provides a centralized way to configure and access policies.
    """
    
    def __init__(
        self,
        crane_policy: CraneAssignmentPolicy = None,
        yard_policy: YardPlacementPolicy = None,
        container_policy: ContainerSelectionPolicy = None
    ):
        self.crane_policy = crane_policy or NearestCranePolicy()
        self.yard_policy = yard_policy or BalancedRowPolicy()
        self.container_policy = container_policy or FIFOContainerPolicy()
    
    @classmethod
    def default(cls) -> "PolicyManager":
        """Create a policy manager with default policies."""
        return cls(
            crane_policy=NearestCranePolicy(),
            yard_policy=NearestToPickupPolicy(),
            container_policy=FIFOContainerPolicy()
        )


# Export default yard placement policy for convenience
DefaultYardPlacementPolicy = NearestToPickupPolicy
