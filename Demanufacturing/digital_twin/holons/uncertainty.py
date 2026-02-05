"""
holons/uncertainty.py

Uncertainty modeling for holonic demanufacturing.
"""

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class UncertaintyMap:
    """
    Represents uncertainty across different aspects of a holon.
    
    Uncertainty values range from 0.0 (certain) to 1.0 (completely uncertain).
    Higher uncertainty reduces the probability of successful operations.
    """
    
    fastener_type: float = 0.5
    """Uncertainty about fastener types (screws, clips, adhesive)."""
    
    battery_condition: float = 0.5
    """Uncertainty about battery state (swelling, damage risk)."""
    
    component_fragility: float = 0.3
    """Uncertainty about component fragility during handling."""
    
    material_composition: float = 0.4
    """Uncertainty about material types for recycling classification."""
    
    hidden_fasteners: float = 0.5
    """Uncertainty about concealed/hidden fasteners."""
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary representation."""
        return {
            "fastener_type": self.fastener_type,
            "battery_condition": self.battery_condition,
            "component_fragility": self.component_fragility,
            "material_composition": self.material_composition,
            "hidden_fasteners": self.hidden_fasteners,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UncertaintyMap":
        """Create from dictionary representation."""
        return cls(
            fastener_type=float(data.get("fastener_type", 0.5)),
            battery_condition=float(data.get("battery_condition", 0.5)),
            component_fragility=float(data.get("component_fragility", 0.3)),
            material_composition=float(data.get("material_composition", 0.4)),
            hidden_fasteners=float(data.get("hidden_fasteners", 0.5)),
        )

    def max_uncertainty(self) -> float:
        """Return the maximum uncertainty value across all dimensions."""
        return max(
            self.fastener_type,
            self.battery_condition,
            self.component_fragility,
            self.material_composition,
            self.hidden_fasteners,
        )
    
    def avg_uncertainty(self) -> float:
        """Return the average uncertainty across all dimensions."""
        values = [
            self.fastener_type,
            self.battery_condition,
            self.component_fragility,
            self.material_composition,
            self.hidden_fasteners,
        ]
        return sum(values) / len(values)

    def apply_patch(self, dotted_path: str, value: float):
        """
        Apply a patch to a specific uncertainty dimension.
        
        Args:
            dotted_path: Path like "fastener_type" or "battery_condition"
            value: New uncertainty value (0.0 to 1.0)
        """
        value = max(0.0, min(1.0, float(value)))
        if hasattr(self, dotted_path):
            setattr(self, dotted_path, value)
