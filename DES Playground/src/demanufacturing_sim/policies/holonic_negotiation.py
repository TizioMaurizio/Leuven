"""
Holonic Negotiation Policies for DIGITAU Demanufacturing Simulator.

Implements distributed decision-making protocols between holons:
- Contract Net Protocol for task allocation
- Priority-based negotiation
- Load balancing across resources
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from demanufacturing_sim.agents.product_holon import ProductHolon
    from demanufacturing_sim.agents.resource_holon import ResourceHolon, TaskRequest, TaskResponse


class NegotiationProtocol(ABC):
    """Base class for negotiation protocols between holons."""
    
    @abstractmethod
    def negotiate(self, requester: "ProductHolon", 
                 resources: List["ResourceHolon"],
                 task_type: str,
                 timestamp: float) -> Optional[str]:
        """
        Negotiate task assignment between product and resources.
        
        Args:
            requester: Product holon requesting service
            resources: Available resource holons
            task_type: Type of task to be performed
            timestamp: Current simulation time
        
        Returns:
            ID of assigned resource, or None if negotiation failed
        """
        pass


class ContractNetProtocol(NegotiationProtocol):
    """
    Contract Net Protocol implementation.
    
    Steps:
    1. Announcement: Product broadcasts task requirements
    2. Bidding: Resources submit bids based on availability/capability
    3. Awarding: Product selects best bid and awards contract
    """
    
    def __init__(self, 
                 prefer_shortest_queue: bool = True,
                 prefer_fastest: bool = True,
                 allow_queue_overflow: bool = False):
        self.prefer_shortest_queue = prefer_shortest_queue
        self.prefer_fastest = prefer_fastest
        self.allow_queue_overflow = allow_queue_overflow
    
    def negotiate(self, requester: "ProductHolon",
                 resources: List["ResourceHolon"],
                 task_type: str,
                 timestamp: float) -> Optional[str]:
        """Perform Contract Net negotiation."""
        from demanufacturing_sim.agents.resource_holon import TaskRequest
        
        # Phase 1: Create announcement
        request = TaskRequest(
            request_id=f"cnp_{requester.id}_{timestamp}",
            product_holon_id=requester.id,
            task_type=task_type,
            priority=requester.effective_priority,
            timestamp=timestamp
        )
        
        # Phase 2: Collect bids
        bids = []
        for resource in resources:
            if not resource.can_handle(task_type):
                continue
            
            response = resource.request_task(request)
            if response.accepted or (self.allow_queue_overflow and 
                                    response.rejection_reason == "low_priority_at_high_load"):
                bids.append({
                    "resource": resource,
                    "response": response,
                    "score": self._score_bid(resource, response)
                })
        
        if not bids:
            return None
        
        # Phase 3: Award to best bid
        bids.sort(key=lambda b: b["score"], reverse=True)
        winner = bids[0]["resource"]
        
        # If we collected bids but winner rejected, need to re-request
        if not bids[0]["response"].accepted:
            # Force accept for winner
            winner.current_queue.append(request)
        
        return winner.id
    
    def _score_bid(self, resource: "ResourceHolon", 
                   response: "TaskResponse") -> float:
        """Score a bid for ranking."""
        score = 100.0
        
        # Prefer resources that accepted
        if response.accepted:
            score += 50.0
        
        # Prefer shorter queues
        if self.prefer_shortest_queue:
            queue_penalty = resource.queue_length * 5.0
            score -= queue_penalty
        
        # Prefer faster resources
        if self.prefer_fastest:
            speed_bonus = resource.effective_rate * 10.0
            score += speed_bonus
        
        # Prefer healthier resources
        health_bonus = resource.health_percentage * 20.0
        score += health_bonus
        
        # Penalize estimated wait time
        if response.estimated_time:
            wait_penalty = response.estimated_time * 2.0
            score -= wait_penalty
        
        return score


class PriorityBasedNegotiation(NegotiationProtocol):
    """
    Simple priority-based assignment.
    
    High priority products get first choice of resources.
    Resources are sorted by availability and capability.
    """
    
    def __init__(self, 
                 priority_threshold: float = 1.0,
                 fast_track_high_value: bool = True):
        self.priority_threshold = priority_threshold
        self.fast_track_high_value = fast_track_high_value
    
    def negotiate(self, requester: "ProductHolon",
                 resources: List["ResourceHolon"],
                 task_type: str,
                 timestamp: float) -> Optional[str]:
        """Perform priority-based assignment."""
        from demanufacturing_sim.agents.resource_holon import TaskRequest
        
        # Check if this is a high-priority request
        is_high_priority = requester.effective_priority >= self.priority_threshold
        is_high_value = (self.fast_track_high_value and 
                        requester.predicted_value > 50.0)
        
        # Filter compatible resources
        compatible = [r for r in resources if r.can_handle(task_type)]
        if not compatible:
            return None
        
        # Sort by preference
        def sort_key(r):
            # Available resources first
            available = 1 if r.is_available else 0
            # Then by queue length
            queue = -r.queue_length
            # Then by speed
            speed = r.effective_rate
            return (available, queue, speed)
        
        compatible.sort(key=sort_key, reverse=True)
        
        # Create request
        request = TaskRequest(
            request_id=f"prio_{requester.id}_{timestamp}",
            product_holon_id=requester.id,
            task_type=task_type,
            priority=requester.effective_priority,
            timestamp=timestamp
        )
        
        # Try each resource
        for resource in compatible:
            # High priority can jump queues
            if is_high_priority or is_high_value:
                if resource.is_available or resource.queue_length < resource.queue_capacity * 0.5:
                    response = resource.request_task(request)
                    if response.accepted:
                        return resource.id
            else:
                # Normal priority must wait for availability
                if resource.is_available:
                    response = resource.request_task(request)
                    if response.accepted:
                        return resource.id
        
        # Fall back to any that accepts
        for resource in compatible:
            response = resource.request_task(request)
            if response.accepted:
                return resource.id
        
        return None


class LoadBalancingNegotiation(NegotiationProtocol):
    """
    Load balancing across resources.
    
    Distributes work evenly to prevent bottlenecks.
    """
    
    def __init__(self,
                 target_utilization: float = 0.8,
                 balance_window: int = 10):
        self.target_utilization = target_utilization
        self.balance_window = balance_window
        self._assignment_counts: Dict[str, int] = {}
    
    def negotiate(self, requester: "ProductHolon",
                 resources: List["ResourceHolon"],
                 task_type: str,
                 timestamp: float) -> Optional[str]:
        """Perform load-balanced assignment."""
        from demanufacturing_sim.agents.resource_holon import TaskRequest
        
        # Filter compatible and available
        compatible = [r for r in resources 
                     if r.can_handle(task_type) and r.is_available]
        
        if not compatible:
            # Fall back to any compatible with shortest queue
            compatible = [r for r in resources if r.can_handle(task_type)]
            if not compatible:
                return None
            compatible.sort(key=lambda r: r.queue_length)
        
        # Score by load balance
        def balance_score(r):
            # Current utilization distance from target
            util_distance = abs(r.utilization - self.target_utilization)
            # Recent assignments (prefer less assigned)
            recent = self._assignment_counts.get(r.id, 0)
            # Queue capacity remaining
            queue_space = r.queue_capacity - r.queue_length
            
            score = queue_space * 10 - util_distance * 20 - recent * 5
            return score
        
        compatible.sort(key=balance_score, reverse=True)
        
        # Create request
        request = TaskRequest(
            request_id=f"lb_{requester.id}_{timestamp}",
            product_holon_id=requester.id,
            task_type=task_type,
            priority=requester.effective_priority,
            timestamp=timestamp
        )
        
        # Try resources in order
        for resource in compatible:
            response = resource.request_task(request)
            if response.accepted:
                # Track assignment
                self._assignment_counts[resource.id] = \
                    self._assignment_counts.get(resource.id, 0) + 1
                
                # Decay old counts
                if sum(self._assignment_counts.values()) > self.balance_window * len(resources):
                    for key in self._assignment_counts:
                        self._assignment_counts[key] = max(0, self._assignment_counts[key] - 1)
                
                return resource.id
        
        return None


@dataclass
class NegotiationManager:
    """
    Manages negotiation protocols and policy switching.
    
    Can dynamically switch protocols based on system state
    or orchestrator guidance.
    """
    
    default_protocol: NegotiationProtocol = field(
        default_factory=lambda: ContractNetProtocol()
    )
    high_load_protocol: NegotiationProtocol = field(
        default_factory=lambda: PriorityBasedNegotiation()
    )
    balanced_protocol: NegotiationProtocol = field(
        default_factory=lambda: LoadBalancingNegotiation()
    )
    
    # Thresholds for protocol switching
    high_load_threshold: float = 0.8
    
    # Statistics
    negotiations_total: int = 0
    negotiations_successful: int = 0
    negotiations_failed: int = 0
    
    def get_protocol(self, system_load: float = 0.5,
                    guidance_mode: str = None) -> NegotiationProtocol:
        """
        Get appropriate protocol based on conditions.
        
        Args:
            system_load: Current system utilization (0-1)
            guidance_mode: Mode from orchestrator guidance
        
        Returns:
            Appropriate negotiation protocol
        """
        # Orchestrator guidance overrides
        if guidance_mode == "recovery":
            return self.high_load_protocol
        elif guidance_mode == "balanced":
            return self.balanced_protocol
        
        # Auto-select based on load
        if system_load >= self.high_load_threshold:
            return self.high_load_protocol
        
        return self.default_protocol
    
    def negotiate(self, requester: "ProductHolon",
                 resources: List["ResourceHolon"],
                 task_type: str,
                 timestamp: float,
                 system_load: float = 0.5,
                 guidance_mode: str = None) -> Optional[str]:
        """
        Perform negotiation using appropriate protocol.
        
        Args:
            requester: Product holon
            resources: Available resource holons
            task_type: Type of task
            timestamp: Current time
            system_load: Current system utilization
            guidance_mode: Mode from orchestrator
        
        Returns:
            Assigned resource ID or None
        """
        protocol = self.get_protocol(system_load, guidance_mode)
        
        self.negotiations_total += 1
        result = protocol.negotiate(requester, resources, task_type, timestamp)
        
        if result:
            self.negotiations_successful += 1
        else:
            self.negotiations_failed += 1
        
        return result
    
    @property
    def success_rate(self) -> float:
        """Get negotiation success rate."""
        if self.negotiations_total == 0:
            return 1.0
        return self.negotiations_successful / self.negotiations_total
