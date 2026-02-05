"""
SystemHolon: High-level coordinator for the holonic system.

Aggregates system state and provides:
- Workload monitoring and balancing
- Bottleneck detection
- Deadlock resolution
- Global state publishing
- Fallback decisions when local negotiation fails
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set, Callable, Tuple
from enum import Enum, auto
import statistics


class SystemAlertLevel(Enum):
    """Alert levels for system issues."""
    NORMAL = auto()
    WARNING = auto()
    CRITICAL = auto()
    EMERGENCY = auto()


class BottleneckType(Enum):
    """Types of detected bottlenecks."""
    QUEUE_OVERFLOW = auto()
    RESOURCE_FAILURE = auto()
    TRANSPORT_CONGESTION = auto()
    BUFFER_FULL = auto()
    STARVATION = auto()
    THROUGHPUT_DROP = auto()


@dataclass
class BottleneckAlert:
    """Alert about a detected bottleneck."""
    bottleneck_type: BottleneckType
    location_id: str
    severity: SystemAlertLevel
    timestamp: float
    details: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolution_time: Optional[float] = None


@dataclass
class SystemSnapshot:
    """
    Complete snapshot of system state for orchestrator.
    
    Aggregated metrics and status from all holons.
    """
    timestamp: float = 0.0
    
    # Product state
    total_products_in_system: int = 0
    products_by_stage: Dict[str, int] = field(default_factory=dict)
    products_by_route: Dict[str, int] = field(default_factory=dict)
    avg_uncertainty: float = 0.0
    high_value_products: int = 0
    
    # Resource state
    total_resources: int = 0
    available_resources: int = 0
    failed_resources: int = 0
    resource_utilization: Dict[str, float] = field(default_factory=dict)
    queue_lengths: Dict[str, int] = field(default_factory=dict)
    
    # Transport state
    active_transports: int = 0
    blocked_transports: int = 0
    transport_utilization: float = 0.0
    
    # Flow metrics
    throughput_rate: float = 0.0  # Items per hour
    avg_cycle_time: float = 0.0
    wip_level: int = 0
    
    # Health
    system_health: float = 1.0
    bottlenecks: List[BottleneckAlert] = field(default_factory=list)
    alert_level: SystemAlertLevel = SystemAlertLevel.NORMAL
    
    # Value metrics
    total_value_recovered: float = 0.0
    value_recovery_rate: float = 0.0


@dataclass
class SystemHolon:
    """
    System-level holon for coordination and monitoring.
    
    Responsibilities:
    - Aggregate state from all holons
    - Detect bottlenecks and anomalies
    - Publish system state for orchestrator
    - Resolve deadlocks and stuck situations
    - Provide fallback decisions
    """
    id: str = "system_holon"
    
    # Connected holons
    product_holons: Dict[str, Any] = field(default_factory=dict)
    resource_holons: Dict[str, Any] = field(default_factory=dict)
    transport_holons: Dict[str, Any] = field(default_factory=dict)
    
    # State tracking
    current_snapshot: SystemSnapshot = field(default_factory=SystemSnapshot)
    snapshot_history: List[SystemSnapshot] = field(default_factory=list)
    max_history: int = 100
    
    # Alerts
    active_alerts: List[BottleneckAlert] = field(default_factory=list)
    alert_history: List[BottleneckAlert] = field(default_factory=list)
    
    # Metrics tracking for trend analysis
    throughput_history: List[Tuple[float, float]] = field(default_factory=list)
    utilization_history: List[Tuple[float, Dict[str, float]]] = field(default_factory=list)
    
    # Thresholds for bottleneck detection
    queue_warning_threshold: float = 0.7
    queue_critical_threshold: float = 0.9
    utilization_warning_threshold: float = 0.85
    throughput_drop_threshold: float = 0.3  # 30% drop triggers alert
    
    # Deadlock detection
    stuck_products: Dict[str, float] = field(default_factory=dict)  # product_id -> stuck_since
    stuck_threshold: float = 30.0  # Minutes without progress
    
    # Callbacks
    _on_alert: Optional[Callable] = None
    _on_snapshot: Optional[Callable] = None
    
    def register_product_holon(self, holon_id: str, holon: Any) -> None:
        """Register a product holon for monitoring."""
        self.product_holons[holon_id] = holon
    
    def unregister_product_holon(self, holon_id: str) -> None:
        """Unregister a product holon."""
        if holon_id in self.product_holons:
            del self.product_holons[holon_id]
        if holon_id in self.stuck_products:
            del self.stuck_products[holon_id]
    
    def register_resource_holon(self, holon_id: str, holon: Any) -> None:
        """Register a resource holon for monitoring."""
        self.resource_holons[holon_id] = holon
    
    def register_transport_holon(self, holon_id: str, holon: Any) -> None:
        """Register a transport holon for monitoring."""
        self.transport_holons[holon_id] = holon
    
    def update_snapshot(self, current_time: float) -> SystemSnapshot:
        """
        Create a new system snapshot by aggregating all holon states.
        
        Args:
            current_time: Current simulation time
        
        Returns:
            SystemSnapshot with aggregated state
        """
        snapshot = SystemSnapshot(timestamp=current_time)
        
        # Aggregate product states
        products_by_stage = {}
        products_by_route = {}
        uncertainties = []
        high_value_count = 0
        
        for holon_id, holon in self.product_holons.items():
            state = holon.get_state_snapshot()
            
            stage = state.get("stage", "unknown")
            products_by_stage[stage] = products_by_stage.get(stage, 0) + 1
            
            route = state.get("route", "undecided")
            products_by_route[route] = products_by_route.get(route, 0) + 1
            
            uncertainties.append(holon.uncertainty_factor)
            
            if state.get("predicted_value", 0) > 50:
                high_value_count += 1
            
            # Check for stuck products
            self._check_stuck_product(holon_id, state, current_time)
        
        snapshot.total_products_in_system = len(self.product_holons)
        snapshot.products_by_stage = products_by_stage
        snapshot.products_by_route = products_by_route
        snapshot.avg_uncertainty = statistics.mean(uncertainties) if uncertainties else 0.0
        snapshot.high_value_products = high_value_count
        snapshot.wip_level = snapshot.total_products_in_system
        
        # Aggregate resource states
        available = 0
        failed = 0
        utilizations = {}
        queue_lengths = {}
        
        for holon_id, holon in self.resource_holons.items():
            state = holon.get_state_snapshot()
            
            if state.get("is_available", False):
                available += 1
            if state.get("health_state") == "FAILED":
                failed += 1
            
            utilizations[holon_id] = state.get("utilization", 0.0)
            queue_lengths[holon_id] = state.get("queue_length", 0)
            
            # Check for bottlenecks
            self._check_resource_bottleneck(holon_id, state, current_time)
        
        snapshot.total_resources = len(self.resource_holons)
        snapshot.available_resources = available
        snapshot.failed_resources = failed
        snapshot.resource_utilization = utilizations
        snapshot.queue_lengths = queue_lengths
        
        # Aggregate transport states
        active = 0
        blocked = 0
        transport_utils = []
        
        for holon_id, holon in self.transport_holons.items():
            state = holon.get_state_snapshot()
            
            if state.get("state") != "IDLE":
                active += 1
            if state.get("state") == "BLOCKED":
                blocked += 1
            
            transport_utils.append(state.get("utilization", 0.0))
        
        snapshot.active_transports = active
        snapshot.blocked_transports = blocked
        snapshot.transport_utilization = (
            statistics.mean(transport_utils) if transport_utils else 0.0
        )
        
        # Calculate throughput
        snapshot.throughput_rate = self._calculate_throughput(current_time)
        
        # Calculate system health
        snapshot.system_health = self._calculate_system_health(snapshot)
        
        # Determine alert level
        snapshot.alert_level = self._determine_alert_level(snapshot)
        snapshot.bottlenecks = list(self.active_alerts)
        
        # Store snapshot
        self.current_snapshot = snapshot
        self.snapshot_history.append(snapshot)
        if len(self.snapshot_history) > self.max_history:
            self.snapshot_history = self.snapshot_history[-self.max_history // 2:]
        
        # Record metrics history
        self.throughput_history.append((current_time, snapshot.throughput_rate))
        self.utilization_history.append((current_time, dict(utilizations)))
        
        # Trigger callback
        if self._on_snapshot:
            self._on_snapshot(snapshot)
        
        return snapshot
    
    def _check_stuck_product(self, product_id: str, state: Dict, 
                            current_time: float) -> None:
        """Check if a product is stuck and hasn't progressed."""
        stage = state.get("stage", "")
        
        # Products should progress; if same stage for too long, flag as stuck
        if product_id in self.stuck_products:
            stuck_duration = current_time - self.stuck_products[product_id]
            if stuck_duration > self.stuck_threshold:
                self._raise_alert(
                    BottleneckType.STARVATION,
                    product_id,
                    SystemAlertLevel.WARNING,
                    current_time,
                    {"stage": stage, "stuck_duration": stuck_duration}
                )
        else:
            self.stuck_products[product_id] = current_time
    
    def mark_product_progress(self, product_id: str, current_time: float) -> None:
        """Mark that a product has made progress."""
        self.stuck_products[product_id] = current_time
    
    def _check_resource_bottleneck(self, resource_id: str, state: Dict,
                                   current_time: float) -> None:
        """Check for bottlenecks at a resource."""
        queue_length = state.get("queue_length", 0)
        queue_capacity = state.get("queue_capacity", 10)
        utilization = state.get("utilization", 0.0)
        health_state = state.get("health_state", "")
        
        queue_ratio = queue_length / queue_capacity if queue_capacity > 0 else 0
        
        # Check queue overflow
        if queue_ratio >= self.queue_critical_threshold:
            self._raise_alert(
                BottleneckType.QUEUE_OVERFLOW,
                resource_id,
                SystemAlertLevel.CRITICAL,
                current_time,
                {"queue_ratio": queue_ratio, "queue_length": queue_length}
            )
        elif queue_ratio >= self.queue_warning_threshold:
            self._raise_alert(
                BottleneckType.QUEUE_OVERFLOW,
                resource_id,
                SystemAlertLevel.WARNING,
                current_time,
                {"queue_ratio": queue_ratio, "queue_length": queue_length}
            )
        
        # Check resource failure
        if health_state == "FAILED":
            self._raise_alert(
                BottleneckType.RESOURCE_FAILURE,
                resource_id,
                SystemAlertLevel.CRITICAL,
                current_time,
                {"health_state": health_state}
            )
    
    def _raise_alert(self, bottleneck_type: BottleneckType, location_id: str,
                    severity: SystemAlertLevel, timestamp: float,
                    details: Dict = None) -> BottleneckAlert:
        """Raise a new bottleneck alert."""
        # Check if similar alert already active
        for alert in self.active_alerts:
            if (alert.bottleneck_type == bottleneck_type and 
                alert.location_id == location_id and
                not alert.resolved):
                # Update existing alert
                alert.severity = max(alert.severity, severity, key=lambda x: x.value)
                alert.details.update(details or {})
                return alert
        
        alert = BottleneckAlert(
            bottleneck_type=bottleneck_type,
            location_id=location_id,
            severity=severity,
            timestamp=timestamp,
            details=details or {}
        )
        
        self.active_alerts.append(alert)
        self.alert_history.append(alert)
        
        if self._on_alert:
            self._on_alert(alert)
        
        return alert
    
    def resolve_alert(self, alert: BottleneckAlert, current_time: float) -> None:
        """Mark an alert as resolved."""
        alert.resolved = True
        alert.resolution_time = current_time
        self.active_alerts = [a for a in self.active_alerts if not a.resolved]
    
    def _calculate_throughput(self, current_time: float) -> float:
        """Calculate current throughput rate."""
        # Use recent history
        if len(self.throughput_history) < 2:
            return 0.0
        
        # Count products that exited in recent window
        window = 60.0  # 1 hour
        exited = sum(
            1 for ph in self.product_holons.values()
            if ph.current_stage == "exited"
        )
        
        # Items per hour
        return exited  # Simplified; in practice track exit events
    
    def _calculate_system_health(self, snapshot: SystemSnapshot) -> float:
        """Calculate overall system health score (0-1)."""
        health = 1.0
        
        # Penalize failed resources
        if snapshot.total_resources > 0:
            failure_penalty = snapshot.failed_resources / snapshot.total_resources
            health -= failure_penalty * 0.3
        
        # Penalize blocked transports
        if len(self.transport_holons) > 0:
            blocked_penalty = snapshot.blocked_transports / len(self.transport_holons)
            health -= blocked_penalty * 0.2
        
        # Penalize active alerts
        critical_count = sum(
            1 for a in self.active_alerts 
            if a.severity == SystemAlertLevel.CRITICAL
        )
        health -= critical_count * 0.1
        
        # Penalize high WIP (indicates congestion)
        if snapshot.total_resources > 0:
            wip_ratio = snapshot.wip_level / (snapshot.total_resources * 10)
            if wip_ratio > 1.5:
                health -= 0.1
        
        return max(0.0, min(1.0, health))
    
    def _determine_alert_level(self, snapshot: SystemSnapshot) -> SystemAlertLevel:
        """Determine overall system alert level."""
        if not self.active_alerts:
            return SystemAlertLevel.NORMAL
        
        # Use highest severity among active alerts
        severities = [a.severity for a in self.active_alerts]
        return max(severities, key=lambda x: x.value)
    
    def detect_deadlock(self, current_time: float) -> List[str]:
        """
        Detect potential deadlock situations.
        
        Returns:
            List of product IDs that appear to be in a deadlock
        """
        deadlocked = []
        
        for product_id, stuck_since in self.stuck_products.items():
            if current_time - stuck_since > self.stuck_threshold * 2:
                # Long stuck = likely deadlock
                deadlocked.append(product_id)
        
        return deadlocked
    
    def suggest_resolution(self, deadlocked_products: List[str]) -> Dict[str, str]:
        """
        Suggest resolutions for deadlocked products.
        
        Returns:
            Dict mapping product_id -> suggested_action
        """
        suggestions = {}
        
        for product_id in deadlocked_products:
            if product_id not in self.product_holons:
                continue
            
            holon = self.product_holons[product_id]
            stage = holon.current_stage
            
            # Suggest based on stage
            if stage in ("awaiting_inspection", "awaiting_disassembly"):
                # Try alternative resource
                suggestions[product_id] = "reroute_to_alternative"
            elif stage == "in_buffer":
                # Force exit via recycle
                suggestions[product_id] = "force_recycle_exit"
            else:
                # Generic: increase priority
                suggestions[product_id] = "increase_priority"
        
        return suggestions
    
    def get_orchestrator_context(self) -> Dict[str, Any]:
        """
        Get context summary for the cognitive orchestrator.
        
        Returns comprehensive state for high-level decision making.
        """
        snapshot = self.current_snapshot
        
        # Identify top bottlenecks
        top_bottlenecks = sorted(
            self.active_alerts,
            key=lambda a: a.severity.value,
            reverse=True
        )[:3]
        
        # Calculate trend indicators
        throughput_trend = self._calculate_trend(
            [t[1] for t in self.throughput_history[-10:]]
        )
        
        return {
            "timestamp": snapshot.timestamp,
            "system_health": snapshot.system_health,
            "alert_level": snapshot.alert_level.name,
            
            # Product flow
            "wip_level": snapshot.wip_level,
            "products_by_stage": snapshot.products_by_stage,
            "products_by_route": snapshot.products_by_route,
            "avg_uncertainty": snapshot.avg_uncertainty,
            "high_value_products": snapshot.high_value_products,
            
            # Resources
            "available_resources": snapshot.available_resources,
            "failed_resources": snapshot.failed_resources,
            "avg_utilization": (
                statistics.mean(snapshot.resource_utilization.values())
                if snapshot.resource_utilization else 0.0
            ),
            "max_queue_length": max(snapshot.queue_lengths.values(), default=0),
            
            # Transport
            "blocked_transports": snapshot.blocked_transports,
            
            # Flow metrics
            "throughput_rate": snapshot.throughput_rate,
            "throughput_trend": throughput_trend,
            
            # Issues
            "bottlenecks": [
                {
                    "type": b.bottleneck_type.name,
                    "location": b.location_id,
                    "severity": b.severity.name
                }
                for b in top_bottlenecks
            ],
            
            # Deadlocks
            "stuck_products_count": sum(
                1 for _, since in self.stuck_products.items()
                if snapshot.timestamp - since > self.stuck_threshold
            )
        }
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from recent values."""
        if len(values) < 3:
            return "stable"
        
        first_half = statistics.mean(values[:len(values)//2])
        second_half = statistics.mean(values[len(values)//2:])
        
        if first_half == 0:
            return "stable"
        
        change = (second_half - first_half) / first_half
        
        if change > 0.1:
            return "increasing"
        elif change < -0.1:
            return "decreasing"
        return "stable"


# Type hint fix for dataclass field
from typing import Tuple
