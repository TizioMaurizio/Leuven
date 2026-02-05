"""
holons/product_holon.py

Product holon dataclass representing electronic devices in demanufacturing.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

from .uncertainty import UncertaintyMap


class ProductState(Enum):
    """States a product holon can be in during demanufacturing."""
    ARRIVED = "ARRIVED"
    IN_PROGRESS = "IN_PROGRESS"
    FAILED_ATTEMPT = "FAILED_ATTEMPT"
    REQUIRES_SPECIALIST = "REQUIRES_SPECIALIST"
    COMPLETED = "COMPLETED"
    SCRAPPED = "SCRAPPED"


@dataclass
class ProductHolon:
    """
    Represents an electronic device undergoing demanufacturing.
    
    Product holons are autonomous entities that carry their own state,
    uncertainty information, and disassembly progress.
    """
    
    holon_id: str
    """Unique identifier for this product holon."""
    
    device_type: str = "unknown"
    """Type of device (e.g., laptop_dell_xps, smartphone_iphone)."""
    
    disassembly_step: int = 0
    """Current step in the disassembly sequence."""
    
    total_steps: int = 8
    """Total number of disassembly steps for this device type."""
    
    state: ProductState = ProductState.ARRIVED
    """Current state of the product in the demanufacturing process."""
    
    confidence: float = 0.7
    """Confidence level in current state assessment (0.0 to 1.0)."""
    
    uncertainty_map: UncertaintyMap = field(default_factory=UncertaintyMap)
    """Uncertainty dimensions for this product."""
    
    last_operation: Optional[str] = None
    """Description of the last operation performed."""
    
    operated_by: Optional[str] = None
    """ID of the last resource (robot/operator) that worked on this product."""
    
    created_at: datetime = field(default_factory=datetime.now)
    """Timestamp when this holon was created."""
    
    updated_at: datetime = field(default_factory=datetime.now)
    """Timestamp of last state update."""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "holon_id": self.holon_id,
            "device_type": self.device_type,
            "disassembly_step": self.disassembly_step,
            "total_steps": self.total_steps,
            "state": self.state.value,
            "confidence": self.confidence,
            "uncertainty_map": self.uncertainty_map.to_dict(),
            "last_operation": self.last_operation,
            "operated_by": self.operated_by,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProductHolon":
        """Create from dictionary representation."""
        uncertainty_data = data.get("uncertainty_map", {})
        if isinstance(uncertainty_data, UncertaintyMap):
            uncertainty_map = uncertainty_data
        else:
            uncertainty_map = UncertaintyMap.from_dict(uncertainty_data)
        
        state_str = data.get("state", "ARRIVED")
        if isinstance(state_str, ProductState):
            state = state_str
        else:
            state = ProductState(state_str)
        
        return cls(
            holon_id=data["holon_id"],
            device_type=data.get("device_type", "unknown"),
            disassembly_step=int(data.get("disassembly_step", 0)),
            total_steps=int(data.get("total_steps", 8)),
            state=state,
            confidence=float(data.get("confidence", 0.7)),
            uncertainty_map=uncertainty_map,
            last_operation=data.get("last_operation"),
            operated_by=data.get("operated_by"),
        )

    def apply_patches(self, patches: Dict[str, Any]):
        """
        Apply a set of patches to this holon's state.
        
        Args:
            patches: Dictionary of dotted paths to values
        """
        self.updated_at = datetime.now()
        
        for path, value in patches.items():
            if path.startswith("uncertainty_map."):
                # Handle nested uncertainty patches
                uncertainty_field = path.split(".", 1)[1]
                self.uncertainty_map.apply_patch(uncertainty_field, value)
            elif path == "state":
                if isinstance(value, str):
                    self.state = ProductState(value)
                else:
                    self.state = value
            elif hasattr(self, path):
                setattr(self, path, value)

    @property
    def progress_percent(self) -> float:
        """Calculate completion percentage."""
        if self.total_steps == 0:
            return 100.0
        return (self.disassembly_step / self.total_steps) * 100.0
    
    @property
    def is_complete(self) -> bool:
        """Check if disassembly is complete."""
        return self.state == ProductState.COMPLETED
    
    @property
    def needs_intervention(self) -> bool:
        """Check if this product needs human intervention."""
        return (
            self.state in [ProductState.FAILED_ATTEMPT, ProductState.REQUIRES_SPECIALIST]
            or self.uncertainty_map.max_uncertainty() > 0.8
        )
