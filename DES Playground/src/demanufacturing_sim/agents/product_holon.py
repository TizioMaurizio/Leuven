"""
ProductHolon: Autonomous agent representing an End-of-Life product.

Holds per-instance state including:
- Observed structure (partially revealed BOM)
- Detected components
- Predicted value and uncertainty level
- Chosen route and history

Goal: Maximize recovered value and material quality under time/queue constraints.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum, auto
import random


class ProductUncertaintyLevel(Enum):
    """Level of uncertainty about product state."""
    HIGH = auto()      # Just arrived, unknown structure
    MEDIUM = auto()    # After inspection, partial info
    LOW = auto()       # After disassembly, most info known
    KNOWN = auto()     # Fully characterized


class DisassemblyIntent(Enum):
    """Intended disassembly depth."""
    NONE = auto()          # Skip disassembly (direct reuse)
    SHALLOW = auto()       # Minimal disassembly
    STANDARD = auto()      # Normal depth
    DEEP = auto()          # Full disassembly for max recovery


@dataclass
class Component:
    """A component within a product."""
    id: str
    name: str
    is_revealed: bool = False
    condition: float = 0.5  # 0-1, actual condition
    observed_condition: Optional[float] = None  # Noisy observation
    value: float = 10.0
    material_type: str = "mixed"
    recyclable: bool = True
    
    def reveal(self, observation_noise: float = 0.1, rng: random.Random = None) -> float:
        """Reveal this component and return noisy observation."""
        self.is_revealed = True
        rng = rng or random.Random()
        noise = rng.gauss(0, observation_noise)
        self.observed_condition = max(0.0, min(1.0, self.condition + noise))
        return self.observed_condition


@dataclass
class ProductBOM:
    """Bill of Materials for a product - true vs observed structure."""
    true_components: List[Component] = field(default_factory=list)
    _observation_noise: float = 0.1
    
    @classmethod
    def generate_random(cls, rng: random.Random = None, 
                       min_components: int = 3,
                       max_components: int = 10) -> "ProductBOM":
        """Generate a random BOM with hidden components."""
        rng = rng or random.Random()
        num = rng.randint(min_components, max_components)
        
        component_types = [
            ("battery_cell", "lithium", 50.0),
            ("motor", "copper", 30.0),
            ("controller", "electronic", 25.0),
            ("housing", "plastic", 5.0),
            ("wiring", "copper", 8.0),
            ("sensor", "electronic", 15.0),
            ("connector", "metal", 3.0),
            ("seal", "rubber", 1.0),
        ]
        
        components = []
        for i in range(num):
            ctype = rng.choice(component_types)
            comp = Component(
                id=f"comp_{i}",
                name=f"{ctype[0]}_{i}",
                condition=rng.gauss(0.6, 0.2),
                value=ctype[2] * rng.uniform(0.8, 1.2),
                material_type=ctype[1],
                is_revealed=False
            )
            comp.condition = max(0.0, min(1.0, comp.condition))
            components.append(comp)
        
        return cls(true_components=components)
    
    @property
    def revealed_components(self) -> List[Component]:
        """Get list of revealed components."""
        return [c for c in self.true_components if c.is_revealed]
    
    @property
    def hidden_count(self) -> int:
        """Number of still-hidden components."""
        return sum(1 for c in self.true_components if not c.is_revealed)
    
    @property
    def total_true_value(self) -> float:
        """True total value of all components."""
        return sum(c.value * c.condition for c in self.true_components)
    
    @property
    def observed_value(self) -> float:
        """Observed value from revealed components only."""
        revealed = self.revealed_components
        if not revealed:
            return 0.0
        return sum(c.value * (c.observed_condition or c.condition) for c in revealed)
    
    def reveal_some(self, fraction: float, rng: random.Random = None) -> List[Component]:
        """Reveal a fraction of hidden components."""
        rng = rng or random.Random()
        hidden = [c for c in self.true_components if not c.is_revealed]
        num_to_reveal = max(1, int(len(hidden) * fraction))
        to_reveal = rng.sample(hidden, min(num_to_reveal, len(hidden)))
        for comp in to_reveal:
            comp.reveal(self._observation_noise, rng)
        return to_reveal


@dataclass 
class ProductHolon:
    """
    Holon representing an autonomous EoL product in the system.
    
    Attributes:
        id: Unique product identifier
        product: Reference to the underlying Product entity
        bom: Bill of materials (true and observed)
        uncertainty_level: Current uncertainty about product state
        predicted_value: Estimated recoverable value
        chosen_route: Current routing decision intent
        priority: Priority score (can be modulated by orchestrator)
        history: Processing history events
    """
    id: str
    product: Any  # Reference to Product entity
    
    # State
    bom: ProductBOM = field(default_factory=ProductBOM)
    uncertainty_level: ProductUncertaintyLevel = ProductUncertaintyLevel.HIGH
    disassembly_intent: DisassemblyIntent = DisassemblyIntent.STANDARD
    
    # Value predictions
    predicted_value: float = 0.0
    value_confidence: float = 0.0
    time_in_system: float = 0.0
    
    # Routing
    current_station_id: Optional[str] = None
    current_stage: str = "arrived"
    chosen_route: str = "undecided"  # reuse, remanufacture, recycle, disposal
    
    # Priority (can be modulated by orchestrator)
    base_priority: float = 1.0
    priority_multiplier: float = 1.0
    
    # History
    history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Negotiation state
    pending_requests: List[str] = field(default_factory=list)
    last_rejection_time: Optional[float] = None
    rejection_count: int = 0
    
    @property
    def effective_priority(self) -> float:
        """Get effective priority after multipliers."""
        return self.base_priority * self.priority_multiplier
    
    @property
    def uncertainty_factor(self) -> float:
        """Numeric uncertainty factor (0=known, 1=unknown)."""
        mapping = {
            ProductUncertaintyLevel.KNOWN: 0.0,
            ProductUncertaintyLevel.LOW: 0.25,
            ProductUncertaintyLevel.MEDIUM: 0.5,
            ProductUncertaintyLevel.HIGH: 1.0
        }
        return mapping.get(self.uncertainty_level, 1.0)
    
    def record_event(self, event_type: str, timestamp: float, 
                    details: Dict[str, Any] = None) -> None:
        """Record an event in history."""
        self.history.append({
            "event": event_type,
            "timestamp": timestamp,
            "details": details or {}
        })
    
    def update_after_inspection(self, timestamp: float, 
                               rng: random.Random = None) -> None:
        """Update state after inspection stage."""
        # Reveal some components during inspection
        revealed = self.bom.reveal_some(0.3, rng)
        
        # Update uncertainty
        self.uncertainty_level = ProductUncertaintyLevel.MEDIUM
        
        # Update value prediction
        self._update_value_prediction()
        
        self.record_event("inspection_complete", timestamp, {
            "components_revealed": len(revealed),
            "predicted_value": self.predicted_value,
            "uncertainty": self.uncertainty_level.name
        })
    
    def update_after_disassembly(self, timestamp: float,
                                 depth: DisassemblyIntent = None,
                                 rng: random.Random = None) -> None:
        """Update state after disassembly stage."""
        depth = depth or self.disassembly_intent
        
        # Reveal components based on disassembly depth
        reveal_fraction = {
            DisassemblyIntent.NONE: 0.0,
            DisassemblyIntent.SHALLOW: 0.3,
            DisassemblyIntent.STANDARD: 0.6,
            DisassemblyIntent.DEEP: 1.0
        }.get(depth, 0.6)
        
        revealed = self.bom.reveal_some(reveal_fraction, rng)
        
        # Update uncertainty
        if self.bom.hidden_count == 0:
            self.uncertainty_level = ProductUncertaintyLevel.KNOWN
        else:
            self.uncertainty_level = ProductUncertaintyLevel.LOW
        
        self._update_value_prediction()
        
        self.record_event("disassembly_complete", timestamp, {
            "depth": depth.name,
            "components_revealed": len(revealed),
            "total_revealed": len(self.bom.revealed_components),
            "predicted_value": self.predicted_value
        })
    
    def _update_value_prediction(self) -> None:
        """Update value prediction based on observed information."""
        observed = self.bom.observed_value
        hidden_count = self.bom.hidden_count
        total_count = len(self.bom.true_components)
        
        if total_count == 0:
            self.predicted_value = 0.0
            self.value_confidence = 0.0
            return
        
        # Extrapolate value for hidden components
        if hidden_count > 0 and len(self.bom.revealed_components) > 0:
            avg_revealed_value = observed / len(self.bom.revealed_components)
            estimated_hidden = avg_revealed_value * hidden_count * 0.8  # Conservative
            self.predicted_value = observed + estimated_hidden
        else:
            self.predicted_value = observed
        
        # Confidence based on how much is revealed
        self.value_confidence = 1.0 - (hidden_count / total_count) * 0.7
    
    def determine_route(self, quality_thresholds: Dict[str, float],
                       time_pressure: float = 0.0) -> str:
        """
        Determine routing decision based on current state.
        
        Args:
            quality_thresholds: Dict with reuse/remanufacture thresholds
            time_pressure: Time pressure factor (0-1)
        
        Returns:
            Route string: reuse, remanufacture, recycle, disposal
        """
        # Get observed quality
        quality = self._estimate_quality()
        
        # Adjust thresholds based on uncertainty (be conservative when uncertain)
        uncertainty_penalty = self.uncertainty_factor * 0.1
        
        reuse_threshold = quality_thresholds.get("reuse", 0.8) + uncertainty_penalty
        reman_threshold = quality_thresholds.get("remanufacture", 0.4) + uncertainty_penalty * 0.5
        
        # Time pressure can push towards faster routes (recycle)
        if time_pressure > 0.7:
            reuse_threshold += 0.1
            reman_threshold += 0.1
        
        if quality >= reuse_threshold:
            self.chosen_route = "reuse"
        elif quality >= reman_threshold:
            self.chosen_route = "remanufacture"
        elif quality >= 0.1:
            self.chosen_route = "recycle"
        else:
            self.chosen_route = "disposal"
        
        return self.chosen_route
    
    def _estimate_quality(self) -> float:
        """Estimate overall product quality from observations."""
        revealed = self.bom.revealed_components
        if not revealed:
            # No observations yet - use prior
            return 0.5
        
        # Weighted average of observed conditions
        total_value = sum(c.value for c in revealed)
        if total_value == 0:
            return 0.5
        
        weighted_quality = sum(
            c.value * (c.observed_condition or c.condition) 
            for c in revealed
        ) / total_value
        
        return weighted_quality
    
    def should_request_deep_disassembly(self) -> bool:
        """Decide if deep disassembly is warranted."""
        # High value potential and high uncertainty -> worth exploring
        if self.predicted_value > 50.0 and self.uncertainty_level == ProductUncertaintyLevel.MEDIUM:
            return True
        
        # Many hidden components with good observed quality
        if self.bom.hidden_count > 3 and self._estimate_quality() > 0.6:
            return True
        
        return False
    
    def get_state_snapshot(self) -> Dict[str, Any]:
        """Get current state as dictionary for monitoring."""
        return {
            "id": self.id,
            "stage": self.current_stage,
            "route": self.chosen_route,
            "uncertainty": self.uncertainty_level.name,
            "predicted_value": self.predicted_value,
            "value_confidence": self.value_confidence,
            "priority": self.effective_priority,
            "components_revealed": len(self.bom.revealed_components),
            "components_hidden": self.bom.hidden_count,
            "time_in_system": self.time_in_system
        }
