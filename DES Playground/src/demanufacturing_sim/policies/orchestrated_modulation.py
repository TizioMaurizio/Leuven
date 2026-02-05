"""
Orchestrated Policy Modulation for DIGITAU Demanufacturing Simulator.

Implements policy adjustments based on orchestrator guidance:
- Priority modulation for products
- Disassembly depth adjustment
- Routing threshold modification
- Resource allocation tuning
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum, auto


class ModulationType(Enum):
    """Types of policy modulation."""
    PRIORITY = auto()
    DISASSEMBLY_DEPTH = auto()
    ROUTING_THRESHOLD = auto()
    PROCESSING_SPEED = auto()
    QUEUE_PRIORITY = auto()


@dataclass
class PolicyModulation:
    """
    A policy modulation directive from orchestrator.
    
    Represents an adjustment to default policy behavior.
    """
    modulation_type: ModulationType
    parameters: Dict[str, Any] = field(default_factory=dict)
    duration: Optional[float] = None  # None = until changed
    start_time: float = 0.0
    reason: str = ""
    
    def is_expired(self, current_time: float) -> bool:
        """Check if modulation has expired."""
        if self.duration is None:
            return False
        return current_time > self.start_time + self.duration


@dataclass
class OrchestratedPolicyManager:
    """
    Manages policy modulations from the cognitive orchestrator.
    
    Acts as an intermediary between orchestrator guidance and
    actual policy execution.
    """
    
    # Active modulations
    active_modulations: Dict[ModulationType, PolicyModulation] = field(
        default_factory=dict
    )
    
    # Default parameters (baselines)
    default_priority_multiplier: float = 1.0
    default_disassembly_depth: str = "standard"
    default_reuse_threshold: float = 0.8
    default_remanufacture_threshold: float = 0.4
    default_processing_speed: float = 1.0
    
    # Current effective parameters
    current_priority_multiplier: float = 1.0
    current_disassembly_depth: str = "standard"
    current_reuse_threshold: float = 0.8
    current_remanufacture_threshold: float = 0.4
    current_processing_speed: float = 1.0
    
    # Per-product priority overrides
    product_priorities: Dict[str, float] = field(default_factory=dict)
    
    # Per-resource speed overrides
    resource_speeds: Dict[str, float] = field(default_factory=dict)
    
    # History
    modulation_history: List[PolicyModulation] = field(default_factory=list)
    
    def apply_guidance(self, guidance: Dict[str, Any], 
                      current_time: float) -> None:
        """
        Apply guidance from orchestrator.
        
        Args:
            guidance: Guidance dict from orchestrator update
            current_time: Current simulation time
        """
        # Handle priority adjustments
        if "priority_adjustments" in guidance:
            adj = guidance["priority_adjustments"]
            if "route_multipliers" in adj:
                # Apply route-based multipliers (for future use)
                pass
            if "boost_factor" in adj:
                mod = PolicyModulation(
                    modulation_type=ModulationType.PRIORITY,
                    parameters={
                        "multiplier": adj.get("boost_factor", 1.5),
                        "value_threshold": adj.get("value_threshold", 50.0)
                    },
                    start_time=current_time,
                    reason=guidance.get("reason", "orchestrator guidance")
                )
                self._apply_modulation(mod, current_time)
        
        # Handle disassembly depth
        if "disassembly_depth" in guidance:
            depth = guidance["disassembly_depth"]
            mod = PolicyModulation(
                modulation_type=ModulationType.DISASSEMBLY_DEPTH,
                parameters={"depth": depth},
                start_time=current_time,
                reason=guidance.get("reason", "orchestrator guidance")
            )
            self._apply_modulation(mod, current_time)
        
        # Handle routing bias
        if "routing_bias" in guidance:
            bias = guidance["routing_bias"]
            threshold_adjust = bias.get("threshold_adjust", 0.0)
            mod = PolicyModulation(
                modulation_type=ModulationType.ROUTING_THRESHOLD,
                parameters={
                    "reuse_adjust": threshold_adjust,
                    "remanufacture_adjust": threshold_adjust * 0.5
                },
                start_time=current_time,
                reason=guidance.get("reason", "orchestrator guidance")
            )
            self._apply_modulation(mod, current_time)
        
        # Handle flow control / speed adjustments
        if "flow_control" in guidance:
            flow = guidance["flow_control"]
            if "reduce_inflow" in flow:
                mod = PolicyModulation(
                    modulation_type=ModulationType.PROCESSING_SPEED,
                    parameters={"speed_factor": flow["reduce_inflow"]},
                    start_time=current_time,
                    reason="Flow control adjustment"
                )
                self._apply_modulation(mod, current_time)
        
        # Update effective parameters
        self._update_effective_parameters(current_time)
    
    def _apply_modulation(self, mod: PolicyModulation, 
                         current_time: float) -> None:
        """Apply a single modulation."""
        self.active_modulations[mod.modulation_type] = mod
        self.modulation_history.append(mod)
    
    def _update_effective_parameters(self, current_time: float) -> None:
        """Update effective parameters from active modulations."""
        # Start from defaults
        self.current_priority_multiplier = self.default_priority_multiplier
        self.current_disassembly_depth = self.default_disassembly_depth
        self.current_reuse_threshold = self.default_reuse_threshold
        self.current_remanufacture_threshold = self.default_remanufacture_threshold
        self.current_processing_speed = self.default_processing_speed
        
        # Remove expired modulations
        expired = []
        for mod_type, mod in self.active_modulations.items():
            if mod.is_expired(current_time):
                expired.append(mod_type)
        for mod_type in expired:
            del self.active_modulations[mod_type]
        
        # Apply active modulations
        for mod_type, mod in self.active_modulations.items():
            if mod_type == ModulationType.PRIORITY:
                self.current_priority_multiplier = mod.parameters.get(
                    "multiplier", 1.0
                )
            
            elif mod_type == ModulationType.DISASSEMBLY_DEPTH:
                self.current_disassembly_depth = mod.parameters.get(
                    "depth", "standard"
                )
            
            elif mod_type == ModulationType.ROUTING_THRESHOLD:
                self.current_reuse_threshold = max(0.0, min(1.0,
                    self.default_reuse_threshold + 
                    mod.parameters.get("reuse_adjust", 0.0)
                ))
                self.current_remanufacture_threshold = max(0.0, min(1.0,
                    self.default_remanufacture_threshold + 
                    mod.parameters.get("remanufacture_adjust", 0.0)
                ))
            
            elif mod_type == ModulationType.PROCESSING_SPEED:
                self.current_processing_speed = mod.parameters.get(
                    "speed_factor", 1.0
                )
    
    def get_product_priority(self, product_id: str, 
                            base_priority: float,
                            value: float = 0.0) -> float:
        """
        Get effective priority for a product.
        
        Args:
            product_id: Product identifier
            base_priority: Product's base priority
            value: Product's predicted value
        
        Returns:
            Effective priority after modulations
        """
        # Check for direct override
        if product_id in self.product_priorities:
            return self.product_priorities[product_id]
        
        # Apply global multiplier
        effective = base_priority * self.current_priority_multiplier
        
        # Check value-based boost
        if ModulationType.PRIORITY in self.active_modulations:
            mod = self.active_modulations[ModulationType.PRIORITY]
            threshold = mod.parameters.get("value_threshold", 50.0)
            boost = mod.parameters.get("multiplier", 1.5)
            if value >= threshold:
                effective *= boost
        
        return effective
    
    def get_disassembly_depth(self, product_value: float = 0.0,
                             uncertainty: float = 0.5) -> str:
        """
        Get recommended disassembly depth.
        
        Args:
            product_value: Product's predicted value
            uncertainty: Product's uncertainty level
        
        Returns:
            Disassembly depth: "none", "shallow", "standard", "deep"
        """
        base_depth = self.current_disassembly_depth
        
        # Adjust based on value and uncertainty
        if base_depth == "deep" and uncertainty < 0.2:
            # Already low uncertainty, standard is enough
            return "standard"
        
        if base_depth == "shallow" and product_value > 80.0:
            # High value item deserves more attention
            return "standard"
        
        return base_depth
    
    def get_routing_thresholds(self) -> Dict[str, float]:
        """Get current routing thresholds."""
        return {
            "reuse": self.current_reuse_threshold,
            "remanufacture": self.current_remanufacture_threshold
        }
    
    def get_processing_speed_factor(self, resource_id: str = None) -> float:
        """
        Get processing speed factor.
        
        Args:
            resource_id: Optional specific resource
        
        Returns:
            Speed factor (1.0 = normal, >1 = faster, <1 = slower)
        """
        # Check resource-specific override
        if resource_id and resource_id in self.resource_speeds:
            return self.resource_speeds[resource_id]
        
        return self.current_processing_speed
    
    def set_product_priority_override(self, product_id: str, 
                                      priority: float) -> None:
        """Set a direct priority override for a product."""
        self.product_priorities[product_id] = priority
    
    def clear_product_priority_override(self, product_id: str) -> None:
        """Clear priority override for a product."""
        if product_id in self.product_priorities:
            del self.product_priorities[product_id]
    
    def reset_to_defaults(self) -> None:
        """Reset all parameters to defaults."""
        self.active_modulations.clear()
        self.product_priorities.clear()
        self.resource_speeds.clear()
        self.current_priority_multiplier = self.default_priority_multiplier
        self.current_disassembly_depth = self.default_disassembly_depth
        self.current_reuse_threshold = self.default_reuse_threshold
        self.current_remanufacture_threshold = self.default_remanufacture_threshold
        self.current_processing_speed = self.default_processing_speed
    
    def get_state_summary(self) -> Dict[str, Any]:
        """Get summary of current policy state."""
        return {
            "active_modulations": len(self.active_modulations),
            "priority_multiplier": self.current_priority_multiplier,
            "disassembly_depth": self.current_disassembly_depth,
            "reuse_threshold": self.current_reuse_threshold,
            "remanufacture_threshold": self.current_remanufacture_threshold,
            "processing_speed": self.current_processing_speed,
            "product_overrides": len(self.product_priorities),
            "modulations": [
                {
                    "type": mt.name,
                    "params": mod.parameters,
                    "reason": mod.reason
                }
                for mt, mod in self.active_modulations.items()
            ]
        }
