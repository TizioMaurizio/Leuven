"""
Fault Injection System for DIGITAU Demanufacturing Simulator.

Provides mechanisms for injecting various types of faults/disturbances:
- Resource failures (MTBF/MTTR based)
- Degradation events
- Arrival surges
- Inspection noise
- Transport congestion

Supports predefined fault scenarios for experimental comparison.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from enum import Enum, auto
import random


class FaultType(Enum):
    """Types of faults that can be injected."""
    RESOURCE_FAILURE = auto()      # Complete resource failure
    RESOURCE_DEGRADATION = auto()  # Partial capacity reduction
    INSPECTION_NOISE = auto()      # Increased observation noise
    ARRIVAL_SURGE = auto()         # Spike in arrivals
    TRANSPORT_BLOCK = auto()       # Transport congestion
    QUALITY_DROP = auto()          # Products have worse quality
    PROCESSING_SLOWDOWN = auto()   # Increased processing times


@dataclass
class FaultEvent:
    """A fault event to be injected."""
    fault_type: FaultType
    target: str  # Resource ID or "all"
    start_time: float
    duration: float
    severity: float = 1.0  # 0-1, where 1 is full severity
    parameters: Dict[str, Any] = field(default_factory=dict)
    triggered: bool = False
    resolved: bool = False


@dataclass
class FaultScenario:
    """
    A predefined fault scenario for experimental comparison.
    
    Scenarios define a sequence of fault events that test
    system resilience and recovery capabilities.
    """
    name: str
    description: str
    events: List[FaultEvent] = field(default_factory=list)
    
    @classmethod
    def none(cls) -> "FaultScenario":
        """No faults scenario (baseline)."""
        return cls(
            name="none",
            description="Baseline scenario with no faults"
        )
    
    @classmethod
    def robot_down(cls) -> "FaultScenario":
        """
        Robot failure scenario.
        
        One disassembly robot fails at t=60, repairs after 45 minutes.
        """
        return cls(
            name="robot_down",
            description="Disassembly robot failure at t=60min for 45min",
            events=[
                FaultEvent(
                    fault_type=FaultType.RESOURCE_FAILURE,
                    target="resource_dismantling_0",
                    start_time=60.0,
                    duration=45.0,
                    severity=1.0,
                    parameters={"failure_type": "mechanical"}
                )
            ]
        )
    
    @classmethod
    def inspection_noise_high(cls) -> "FaultScenario":
        """
        High inspection noise scenario.
        
        Inspection sensors degrade, causing high observation noise.
        """
        return cls(
            name="inspection_noise_high",
            description="High inspection noise from t=30 to t=150",
            events=[
                FaultEvent(
                    fault_type=FaultType.INSPECTION_NOISE,
                    target="all",
                    start_time=30.0,
                    duration=120.0,
                    severity=0.8,
                    parameters={"noise_multiplier": 3.0}
                )
            ]
        )
    
    @classmethod
    def surge_arrivals(cls) -> "FaultScenario":
        """
        Arrival surge scenario.
        
        Sudden influx of products at t=45.
        """
        return cls(
            name="surge_arrivals",
            description="3x arrival rate from t=45 to t=90",
            events=[
                FaultEvent(
                    fault_type=FaultType.ARRIVAL_SURGE,
                    target="arrivals",
                    start_time=45.0,
                    duration=45.0,
                    severity=1.0,
                    parameters={"rate_multiplier": 3.0}
                )
            ]
        )
    
    @classmethod
    def cascading_failures(cls) -> "FaultScenario":
        """
        Cascading failures scenario.
        
        Multiple resources fail in sequence, testing resilience.
        """
        return cls(
            name="cascading_failures",
            description="Multiple sequential failures testing cascade resilience",
            events=[
                FaultEvent(
                    fault_type=FaultType.RESOURCE_FAILURE,
                    target="resource_dismantling_0",
                    start_time=30.0,
                    duration=30.0,
                    severity=1.0
                ),
                FaultEvent(
                    fault_type=FaultType.RESOURCE_DEGRADATION,
                    target="resource_dismantling_1",
                    start_time=40.0,
                    duration=50.0,
                    severity=0.5,
                    parameters={"capacity_reduction": 0.5}
                ),
                FaultEvent(
                    fault_type=FaultType.TRANSPORT_BLOCK,
                    target="transport_agv_0",
                    start_time=50.0,
                    duration=20.0,
                    severity=1.0
                )
            ]
        )
    
    @classmethod
    def quality_crisis(cls) -> "FaultScenario":
        """
        Quality crisis scenario.
        
        Incoming products have significantly degraded quality.
        """
        return cls(
            name="quality_crisis",
            description="Low quality incoming products from t=20 to t=120",
            events=[
                FaultEvent(
                    fault_type=FaultType.QUALITY_DROP,
                    target="arrivals",
                    start_time=20.0,
                    duration=100.0,
                    severity=0.7,
                    parameters={"quality_reduction": 0.3}
                )
            ]
        )
    
    @classmethod
    def stress_test(cls) -> "FaultScenario":
        """
        Stress test scenario combining multiple fault types.
        """
        return cls(
            name="stress_test",
            description="Combined faults for stress testing",
            events=[
                FaultEvent(
                    fault_type=FaultType.ARRIVAL_SURGE,
                    target="arrivals",
                    start_time=30.0,
                    duration=60.0,
                    severity=0.7,
                    parameters={"rate_multiplier": 2.0}
                ),
                FaultEvent(
                    fault_type=FaultType.RESOURCE_DEGRADATION,
                    target="resource_inspection_0",
                    start_time=60.0,
                    duration=90.0,
                    severity=0.4,
                    parameters={"capacity_reduction": 0.4}
                ),
                FaultEvent(
                    fault_type=FaultType.PROCESSING_SLOWDOWN,
                    target="resource_dismantling_1",
                    start_time=90.0,
                    duration=60.0,
                    severity=0.5,
                    parameters={"slowdown_factor": 1.5}
                )
            ]
        )


class FaultInjector:
    """
    Manages fault injection during simulation.
    
    Integrates with the simulation to trigger and resolve faults
    according to predefined scenarios or random injection.
    """
    
    def __init__(self, seed: int = None):
        self.rng = random.Random(seed)
        self.scenario: Optional[FaultScenario] = None
        self.active_faults: List[FaultEvent] = []
        self.fault_history: List[FaultEvent] = []
        
        # Random fault injection settings
        self.random_injection_enabled = False
        self.random_mtbf: float = 240.0  # Mean time between random faults
        self.next_random_fault_time: Optional[float] = None
        
        # Callbacks
        self._on_fault_start: Optional[Callable] = None
        self._on_fault_end: Optional[Callable] = None
        
        # State modifiers (applied during active faults)
        self.arrival_rate_multiplier: float = 1.0
        self.observation_noise_multiplier: float = 1.0
        self.quality_modifier: float = 0.0
        self.processing_time_multiplier: float = 1.0
        
        # Statistics
        self.total_faults_triggered = 0
        self.total_fault_duration = 0.0
    
    def set_scenario(self, scenario: FaultScenario) -> None:
        """Set the fault scenario to use."""
        self.scenario = scenario
        self.active_faults.clear()
        self.reset_modifiers()
    
    @classmethod
    def get_available_scenarios(cls) -> List[str]:
        """Get list of available scenario names."""
        return [
            "none",
            "robot_down",
            "inspection_noise_high",
            "surge_arrivals",
            "cascading_failures",
            "quality_crisis",
            "stress_test"
        ]
    
    @classmethod
    def create_scenario(cls, name: str) -> FaultScenario:
        """Create a scenario by name."""
        scenarios = {
            "none": FaultScenario.none,
            "robot_down": FaultScenario.robot_down,
            "inspection_noise_high": FaultScenario.inspection_noise_high,
            "surge_arrivals": FaultScenario.surge_arrivals,
            "cascading_failures": FaultScenario.cascading_failures,
            "quality_crisis": FaultScenario.quality_crisis,
            "stress_test": FaultScenario.stress_test
        }
        factory = scenarios.get(name)
        if factory:
            return factory()
        return FaultScenario.none()
    
    def enable_random_faults(self, mtbf: float = 240.0) -> None:
        """Enable random fault injection."""
        self.random_injection_enabled = True
        self.random_mtbf = mtbf
        self.next_random_fault_time = None
    
    def disable_random_faults(self) -> None:
        """Disable random fault injection."""
        self.random_injection_enabled = False
        self.next_random_fault_time = None
    
    def reset_modifiers(self) -> None:
        """Reset all state modifiers to defaults."""
        self.arrival_rate_multiplier = 1.0
        self.observation_noise_multiplier = 1.0
        self.quality_modifier = 0.0
        self.processing_time_multiplier = 1.0
    
    def update(self, current_time: float) -> List[Dict[str, Any]]:
        """
        Update fault state and return any new fault actions.
        
        Args:
            current_time: Current simulation time
        
        Returns:
            List of fault action dicts to apply
        """
        actions = []
        
        # Check scenario events
        if self.scenario:
            for event in self.scenario.events:
                # Start event
                if (not event.triggered and 
                    current_time >= event.start_time):
                    action = self._trigger_fault(event, current_time)
                    if action:
                        actions.append(action)
                
                # End event
                if (event.triggered and not event.resolved and
                    current_time >= event.start_time + event.duration):
                    action = self._resolve_fault(event, current_time)
                    if action:
                        actions.append(action)
        
        # Check for random faults
        if self.random_injection_enabled:
            action = self._check_random_fault(current_time)
            if action:
                actions.append(action)
        
        # Update modifiers based on active faults
        self._update_modifiers()
        
        return actions
    
    def _trigger_fault(self, event: FaultEvent, 
                       current_time: float) -> Optional[Dict[str, Any]]:
        """Trigger a fault event."""
        event.triggered = True
        self.active_faults.append(event)
        self.fault_history.append(event)
        self.total_faults_triggered += 1
        
        action = {
            "action": "start_fault",
            "fault_type": event.fault_type.name,
            "target": event.target,
            "severity": event.severity,
            "parameters": event.parameters,
            "timestamp": current_time,
            "duration": event.duration
        }
        
        if self._on_fault_start:
            self._on_fault_start(event)
        
        return action
    
    def _resolve_fault(self, event: FaultEvent,
                       current_time: float) -> Optional[Dict[str, Any]]:
        """Resolve a fault event."""
        event.resolved = True
        self.active_faults = [f for f in self.active_faults if f != event]
        self.total_fault_duration += event.duration
        
        action = {
            "action": "end_fault",
            "fault_type": event.fault_type.name,
            "target": event.target,
            "timestamp": current_time
        }
        
        if self._on_fault_end:
            self._on_fault_end(event)
        
        return action
    
    def _check_random_fault(self, current_time: float) -> Optional[Dict[str, Any]]:
        """Check and possibly trigger a random fault."""
        if self.next_random_fault_time is None:
            # Schedule first random fault
            delay = self.rng.expovariate(1.0 / self.random_mtbf)
            self.next_random_fault_time = current_time + delay
            return None
        
        if current_time >= self.next_random_fault_time:
            # Trigger random fault
            event = self._generate_random_fault(current_time)
            action = self._trigger_fault(event, current_time)
            
            # Schedule next random fault
            delay = self.rng.expovariate(1.0 / self.random_mtbf)
            self.next_random_fault_time = current_time + delay
            
            return action
        
        return None
    
    def _generate_random_fault(self, current_time: float) -> FaultEvent:
        """Generate a random fault event."""
        fault_types = [
            (FaultType.RESOURCE_DEGRADATION, 0.4),
            (FaultType.PROCESSING_SLOWDOWN, 0.3),
            (FaultType.TRANSPORT_BLOCK, 0.15),
            (FaultType.RESOURCE_FAILURE, 0.1),
            (FaultType.INSPECTION_NOISE, 0.05)
        ]
        
        # Weighted random selection
        r = self.rng.random()
        cumulative = 0.0
        fault_type = FaultType.RESOURCE_DEGRADATION
        for ft, prob in fault_types:
            cumulative += prob
            if r <= cumulative:
                fault_type = ft
                break
        
        # Random target
        targets = [
            "resource_inspection_0",
            "resource_dismantling_0",
            "resource_dismantling_1",
            "resource_testing_0",
            "transport_agv_0"
        ]
        target = self.rng.choice(targets)
        
        # Random duration and severity
        duration = self.rng.triangular(10.0, 30.0, 60.0)
        severity = self.rng.uniform(0.3, 0.8)
        
        return FaultEvent(
            fault_type=fault_type,
            target=target,
            start_time=current_time,
            duration=duration,
            severity=severity,
            parameters={"source": "random"}
        )
    
    def _update_modifiers(self) -> None:
        """Update state modifiers based on active faults."""
        self.reset_modifiers()
        
        for fault in self.active_faults:
            if fault.fault_type == FaultType.ARRIVAL_SURGE:
                mult = fault.parameters.get("rate_multiplier", 2.0)
                self.arrival_rate_multiplier *= mult * fault.severity
            
            elif fault.fault_type == FaultType.INSPECTION_NOISE:
                mult = fault.parameters.get("noise_multiplier", 2.0)
                self.observation_noise_multiplier *= mult * fault.severity
            
            elif fault.fault_type == FaultType.QUALITY_DROP:
                reduction = fault.parameters.get("quality_reduction", 0.2)
                self.quality_modifier -= reduction * fault.severity
            
            elif fault.fault_type == FaultType.PROCESSING_SLOWDOWN:
                factor = fault.parameters.get("slowdown_factor", 1.5)
                self.processing_time_multiplier *= factor
    
    def get_active_faults(self) -> List[Dict[str, Any]]:
        """Get list of currently active faults."""
        return [
            {
                "type": f.fault_type.name,
                "target": f.target,
                "severity": f.severity,
                "time_remaining": f.start_time + f.duration - f.start_time
            }
            for f in self.active_faults
        ]
    
    def is_resource_failed(self, resource_id: str) -> bool:
        """Check if a resource is currently failed."""
        for fault in self.active_faults:
            if (fault.fault_type == FaultType.RESOURCE_FAILURE and
                (fault.target == resource_id or fault.target == "all")):
                return True
        return False
    
    def get_resource_degradation(self, resource_id: str) -> float:
        """Get degradation factor for a resource (1.0 = normal, 0.0 = failed)."""
        factor = 1.0
        for fault in self.active_faults:
            if fault.fault_type == FaultType.RESOURCE_DEGRADATION:
                if fault.target == resource_id or fault.target == "all":
                    reduction = fault.parameters.get("capacity_reduction", 0.5)
                    factor *= (1.0 - reduction * fault.severity)
        return factor
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get fault injection statistics."""
        return {
            "scenario": self.scenario.name if self.scenario else "none",
            "total_faults_triggered": self.total_faults_triggered,
            "total_fault_duration": self.total_fault_duration,
            "active_faults_count": len(self.active_faults),
            "random_injection_enabled": self.random_injection_enabled,
            "current_modifiers": {
                "arrival_rate": self.arrival_rate_multiplier,
                "observation_noise": self.observation_noise_multiplier,
                "quality": self.quality_modifier,
                "processing_time": self.processing_time_multiplier
            }
        }
