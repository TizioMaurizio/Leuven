"""
ResourceHolon: Autonomous agent representing a physical station.

Represents processing stations (inspection, disassembly robots, shredder, 
sorter, test bench, storage buffers) with:
- Availability and health tracking
- Capability advertisement
- Task acceptance/rejection based on state
- Failure and degradation handling
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set, Callable
from enum import Enum, auto
import random


class ResourceType(Enum):
    """Types of resources in the demanufacturing system."""
    INSPECTION = auto()
    DISASSEMBLY_ROBOT = auto()
    SHREDDER = auto()
    SORTER = auto()
    TEST_BENCH = auto()
    STORAGE_BUFFER = auto()
    AGV = auto()


class HealthState(Enum):
    """Health state of a resource."""
    OPTIMAL = auto()       # 100% capacity
    GOOD = auto()          # 90% capacity
    DEGRADED = auto()      # 70% capacity
    IMPAIRED = auto()      # 50% capacity
    FAILED = auto()        # 0% - not operational


class TaskState(Enum):
    """State of task processing."""
    IDLE = auto()
    PROCESSING = auto()
    WAITING_INPUT = auto()
    WAITING_OUTPUT = auto()
    MAINTENANCE = auto()


@dataclass
class ResourceCapability:
    """A capability that a resource can offer."""
    name: str
    processing_rate: float = 1.0  # items per time unit at full health
    quality_impact: float = 0.0   # impact on product quality (-ve = degradation)
    compatible_stages: List[str] = field(default_factory=list)
    requires_components: List[str] = field(default_factory=list)


@dataclass
class TaskRequest:
    """A request to process a task."""
    request_id: str
    product_holon_id: str
    task_type: str
    priority: float = 1.0
    deadline: Optional[float] = None
    timestamp: float = 0.0
    
    # Parameters
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResponse:
    """Response to a task request."""
    request_id: str
    accepted: bool
    resource_id: str
    estimated_time: Optional[float] = None
    rejection_reason: Optional[str] = None


@dataclass
class FailureEvent:
    """Record of a failure event."""
    timestamp: float
    duration: float
    severity: str  # minor, major, critical
    cause: str
    repaired: bool = False
    repair_time: Optional[float] = None


@dataclass
class ResourceHolon:
    """
    Holon representing an autonomous resource/station in the system.
    
    Attributes:
        id: Unique resource identifier
        resource_type: Type of resource
        health_state: Current health condition
        task_state: Current task processing state
        capabilities: List of capabilities this resource offers
        queue_capacity: Maximum queue size
        current_load: Current number of items in queue
    """
    id: str
    resource_type: ResourceType
    
    # Health and availability
    health_state: HealthState = HealthState.OPTIMAL
    health_percentage: float = 1.0
    task_state: TaskState = TaskState.IDLE
    
    # Capabilities
    capabilities: List[ResourceCapability] = field(default_factory=list)
    base_processing_time: float = 5.0  # minutes
    
    # Queue management
    queue_capacity: int = 10
    current_queue: List[TaskRequest] = field(default_factory=list)
    current_task: Optional[TaskRequest] = None
    
    # Statistics
    total_processed: int = 0
    total_failures: int = 0
    busy_time: float = 0.0
    idle_time: float = 0.0
    last_state_change: float = 0.0
    
    # Failure model (MTBF = Mean Time Between Failures, MTTR = Mean Time To Repair)
    mtbf: float = 480.0  # 8 hours between failures on average
    mttr: float = 30.0   # 30 minutes to repair on average
    failure_history: List[FailureEvent] = field(default_factory=list)
    next_failure_time: Optional[float] = None
    
    # Degradation
    degradation_rate: float = 0.001  # Per processed item
    maintenance_threshold: float = 0.7
    
    # Configuration
    accepts_tasks: bool = True
    max_reject_rate: float = 0.3  # Can reject up to 30% of requests when overloaded
    
    # Callbacks for SimPy integration
    _on_task_complete: Optional[Callable] = None
    _on_failure: Optional[Callable] = None
    
    def __post_init__(self):
        """Initialize capabilities based on resource type."""
        if not self.capabilities:
            self.capabilities = self._default_capabilities()
    
    def _default_capabilities(self) -> List[ResourceCapability]:
        """Get default capabilities for resource type."""
        caps = {
            ResourceType.INSPECTION: [
                ResourceCapability(
                    name="visual_inspection",
                    processing_rate=1.0,
                    compatible_stages=["inspection"]
                ),
                ResourceCapability(
                    name="functional_test",
                    processing_rate=0.5,
                    compatible_stages=["inspection", "testing"]
                )
            ],
            ResourceType.DISASSEMBLY_ROBOT: [
                ResourceCapability(
                    name="partial_disassembly",
                    processing_rate=0.8,
                    compatible_stages=["disassembly"]
                ),
                ResourceCapability(
                    name="full_disassembly",
                    processing_rate=0.4,
                    compatible_stages=["disassembly"]
                )
            ],
            ResourceType.SHREDDER: [
                ResourceCapability(
                    name="shredding",
                    processing_rate=2.0,
                    quality_impact=-0.5,
                    compatible_stages=["recycling"]
                )
            ],
            ResourceType.SORTER: [
                ResourceCapability(
                    name="material_sorting",
                    processing_rate=1.5,
                    compatible_stages=["classification"]
                )
            ],
            ResourceType.TEST_BENCH: [
                ResourceCapability(
                    name="component_testing",
                    processing_rate=0.7,
                    compatible_stages=["testing"]
                )
            ],
            ResourceType.STORAGE_BUFFER: [
                ResourceCapability(
                    name="storage",
                    processing_rate=10.0,
                    compatible_stages=["buffer"]
                )
            ],
            ResourceType.AGV: [
                ResourceCapability(
                    name="transport",
                    processing_rate=1.0,
                    compatible_stages=["transport"]
                )
            ]
        }
        return caps.get(self.resource_type, [])
    
    @property
    def is_available(self) -> bool:
        """Check if resource can accept new tasks."""
        return (
            self.accepts_tasks and
            self.health_state != HealthState.FAILED and
            self.task_state not in (TaskState.MAINTENANCE,) and
            len(self.current_queue) < self.queue_capacity
        )
    
    @property
    def effective_rate(self) -> float:
        """Get effective processing rate considering health."""
        health_multiplier = {
            HealthState.OPTIMAL: 1.0,
            HealthState.GOOD: 0.9,
            HealthState.DEGRADED: 0.7,
            HealthState.IMPAIRED: 0.5,
            HealthState.FAILED: 0.0
        }
        return health_multiplier.get(self.health_state, 1.0) * self.health_percentage
    
    @property
    def queue_length(self) -> int:
        """Current queue length."""
        return len(self.current_queue)
    
    @property
    def estimated_wait_time(self) -> float:
        """Estimate wait time for new task."""
        if self.task_state == TaskState.IDLE and not self.current_queue:
            return 0.0
        
        # Estimate based on queue and current task
        queue_time = len(self.current_queue) * self.base_processing_time / self.effective_rate
        current_time = self.base_processing_time / 2 if self.current_task else 0
        return queue_time + current_time
    
    @property
    def utilization(self) -> float:
        """Calculate utilization rate."""
        total_time = self.busy_time + self.idle_time
        return self.busy_time / total_time if total_time > 0 else 0.0
    
    def can_handle(self, task_type: str) -> bool:
        """Check if resource can handle a task type."""
        for cap in self.capabilities:
            if task_type in cap.compatible_stages or cap.name == task_type:
                return True
        return False
    
    def request_task(self, request: TaskRequest) -> TaskResponse:
        """
        Handle a task request.
        
        Args:
            request: Task request to evaluate
        
        Returns:
            TaskResponse indicating acceptance or rejection
        """
        # Check if we can handle this task type
        if not self.can_handle(request.task_type):
            return TaskResponse(
                request_id=request.request_id,
                accepted=False,
                resource_id=self.id,
                rejection_reason="incompatible_task_type"
            )
        
        # Check availability
        if not self.is_available:
            reason = "failed" if self.health_state == HealthState.FAILED else "overloaded"
            return TaskResponse(
                request_id=request.request_id,
                accepted=False,
                resource_id=self.id,
                rejection_reason=reason
            )
        
        # Check if we should reject due to load balancing
        if self.queue_length >= self.queue_capacity * 0.8:
            # High load - might reject low priority tasks
            if request.priority < 0.5:
                return TaskResponse(
                    request_id=request.request_id,
                    accepted=False,
                    resource_id=self.id,
                    rejection_reason="low_priority_at_high_load",
                    estimated_time=self.estimated_wait_time
                )
        
        # Accept the task
        self.current_queue.append(request)
        
        return TaskResponse(
            request_id=request.request_id,
            accepted=True,
            resource_id=self.id,
            estimated_time=self.estimated_wait_time
        )
    
    def start_next_task(self, current_time: float) -> Optional[TaskRequest]:
        """Start processing the next task in queue."""
        if self.current_task or not self.current_queue:
            return None
        
        if self.health_state == HealthState.FAILED:
            return None
        
        self.current_task = self.current_queue.pop(0)
        self.task_state = TaskState.PROCESSING
        self._update_time_tracking(current_time, is_busy=True)
        
        return self.current_task
    
    def complete_current_task(self, current_time: float) -> Optional[TaskRequest]:
        """Mark current task as complete."""
        completed = self.current_task
        self.current_task = None
        
        if completed:
            self.total_processed += 1
            self._apply_degradation()
        
        if self.current_queue:
            self.task_state = TaskState.PROCESSING
        else:
            self.task_state = TaskState.IDLE
            self._update_time_tracking(current_time, is_busy=False)
        
        if self._on_task_complete:
            self._on_task_complete(completed)
        
        return completed
    
    def get_processing_time(self, task_type: str = None, 
                           rng: random.Random = None) -> float:
        """Get processing time for a task type."""
        rng = rng or random.Random()
        
        # Base time with health adjustment
        base = self.base_processing_time / self.effective_rate
        
        # Add variability (triangular distribution)
        time = rng.triangular(base * 0.7, base, base * 1.5)
        
        return max(0.5, time)
    
    def _apply_degradation(self) -> None:
        """Apply gradual degradation after processing."""
        self.health_percentage -= self.degradation_rate
        self.health_percentage = max(0.0, self.health_percentage)
        
        # Update health state based on percentage
        if self.health_percentage >= 0.95:
            self.health_state = HealthState.OPTIMAL
        elif self.health_percentage >= 0.85:
            self.health_state = HealthState.GOOD
        elif self.health_percentage >= 0.7:
            self.health_state = HealthState.DEGRADED
        elif self.health_percentage >= 0.5:
            self.health_state = HealthState.IMPAIRED
        else:
            # Trigger failure below 50%
            pass  # Don't auto-fail, let random failures handle this
    
    def _update_time_tracking(self, current_time: float, is_busy: bool) -> None:
        """Update time tracking statistics."""
        elapsed = current_time - self.last_state_change
        if is_busy:
            self.idle_time += elapsed
        else:
            self.busy_time += elapsed
        self.last_state_change = current_time
    
    def trigger_failure(self, current_time: float, severity: str = "major",
                       cause: str = "random", rng: random.Random = None) -> FailureEvent:
        """
        Trigger a failure event.
        
        Args:
            current_time: Current simulation time
            severity: minor, major, or critical
            cause: Cause of failure
            rng: Random number generator
        
        Returns:
            FailureEvent describing the failure
        """
        rng = rng or random.Random()
        
        # Determine duration based on severity
        duration_multipliers = {"minor": 0.3, "major": 1.0, "critical": 2.5}
        mult = duration_multipliers.get(severity, 1.0)
        duration = rng.expovariate(1.0 / (self.mttr * mult))
        
        failure = FailureEvent(
            timestamp=current_time,
            duration=duration,
            severity=severity,
            cause=cause
        )
        
        self.failure_history.append(failure)
        self.total_failures += 1
        self.health_state = HealthState.FAILED
        self.task_state = TaskState.MAINTENANCE
        self.accepts_tasks = False
        
        if self._on_failure:
            self._on_failure(failure)
        
        return failure
    
    def repair(self, current_time: float) -> None:
        """Complete repair and restore resource."""
        if self.failure_history:
            self.failure_history[-1].repaired = True
            self.failure_history[-1].repair_time = current_time
        
        self.health_state = HealthState.GOOD
        self.health_percentage = 0.9  # Not quite optimal after repair
        self.task_state = TaskState.IDLE
        self.accepts_tasks = True
    
    def schedule_next_failure(self, current_time: float, 
                             rng: random.Random = None) -> float:
        """Schedule the next random failure time."""
        rng = rng or random.Random()
        
        # Time to next failure follows exponential distribution
        time_to_failure = rng.expovariate(1.0 / self.mtbf)
        
        # Adjust based on health - degraded resources fail sooner
        health_factor = 2.0 - self.health_percentage  # 1.0 at optimal, 2.0 at 0%
        time_to_failure /= health_factor
        
        self.next_failure_time = current_time + time_to_failure
        return self.next_failure_time
    
    def apply_slowdown(self, factor: float) -> None:
        """Apply temporary slowdown (e.g., from orchestrator guidance)."""
        self.health_percentage = min(self.health_percentage, factor)
    
    def get_state_snapshot(self) -> Dict[str, Any]:
        """Get current state as dictionary for monitoring."""
        return {
            "id": self.id,
            "type": self.resource_type.name,
            "health_state": self.health_state.name,
            "health_percentage": self.health_percentage,
            "task_state": self.task_state.name,
            "queue_length": self.queue_length,
            "queue_capacity": self.queue_capacity,
            "effective_rate": self.effective_rate,
            "utilization": self.utilization,
            "total_processed": self.total_processed,
            "total_failures": self.total_failures,
            "is_available": self.is_available,
            "estimated_wait": self.estimated_wait_time
        }
    
    def advertise_services(self) -> Dict[str, Any]:
        """Advertise available services/capabilities."""
        if not self.is_available:
            return {"available": False, "reason": self.health_state.name}
        
        return {
            "available": True,
            "resource_id": self.id,
            "resource_type": self.resource_type.name,
            "capabilities": [cap.name for cap in self.capabilities],
            "compatible_stages": list(set(
                stage for cap in self.capabilities 
                for stage in cap.compatible_stages
            )),
            "queue_space": self.queue_capacity - self.queue_length,
            "estimated_wait": self.estimated_wait_time,
            "effective_rate": self.effective_rate
        }
