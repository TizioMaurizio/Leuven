"""
holons/resource_holon.py

Resource holon dataclasses representing robots and operators.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
from abc import ABC


class ResourceState(Enum):
    """States a resource holon can be in."""
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    OVERLOADED = "OVERLOADED"
    ON_BREAK = "ON_BREAK"
    MAINTENANCE = "MAINTENANCE"
    OFFLINE = "OFFLINE"


@dataclass
class ResourceHolon(ABC):
    """
    Base class for resource holons (robots, operators).
    
    Resource holons represent the agents that perform disassembly operations.
    """
    
    holon_id: str
    """Unique identifier for this resource holon."""
    
    state: ResourceState = ResourceState.AVAILABLE
    """Current state of the resource."""
    
    created_at: datetime = field(default_factory=datetime.now)
    """Timestamp when this holon was created."""
    
    updated_at: datetime = field(default_factory=datetime.now)
    """Timestamp of last state update."""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "holon_id": self.holon_id,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def apply_patches(self, patches: Dict[str, Any]):
        """Apply patches to this holon's state."""
        self.updated_at = datetime.now()
        
        for path, value in patches.items():
            if path == "state":
                if isinstance(value, str):
                    self.state = ResourceState(value)
                else:
                    self.state = value
            elif hasattr(self, path):
                setattr(self, path, value)


@dataclass
class RobotHolon(ResourceHolon):
    """
    Represents a robotic disassembly arm.
    """
    
    robot_type: str = "standard"
    """Type of robot (standard, precision, fast)."""
    
    fatigue: float = 0.0
    """Accumulated fatigue level (0.0 to 1.0)."""
    
    operations_count: int = 0
    """Total number of operations performed."""
    
    success_rate: float = 1.0
    """Rolling success rate for recent operations."""
    
    assigned_product: Optional[str] = None
    """ID of currently assigned product, if any."""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = super().to_dict()
        data.update({
            "robot_type": self.robot_type,
            "fatigue": self.fatigue,
            "operations_count": self.operations_count,
            "success_rate": self.success_rate,
            "assigned_product": self.assigned_product,
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RobotHolon":
        """Create from dictionary representation."""
        state_str = data.get("state", "AVAILABLE")
        if isinstance(state_str, ResourceState):
            state = state_str
        else:
            state = ResourceState(state_str)
            
        return cls(
            holon_id=data["holon_id"],
            state=state,
            robot_type=data.get("robot_type", "standard"),
            fatigue=float(data.get("fatigue", 0.0)),
            operations_count=int(data.get("operations_count", 0)),
            success_rate=float(data.get("success_rate", 1.0)),
            assigned_product=data.get("assigned_product"),
        )


@dataclass
class OperatorHolon(ResourceHolon):
    """
    Represents a human operator.
    """
    
    cognitive_load: float = 0.3
    """Current cognitive load (0.0 to 1.0)."""
    
    time_on_task_minutes: float = 0.0
    """Minutes spent on current shift."""
    
    tasks_completed: int = 0
    """Total tasks completed this shift."""
    
    queue_depth: int = 0
    """Number of products waiting for this operator."""
    
    skill_level: str = "experienced"
    """Operator skill level (novice, experienced, expert)."""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = super().to_dict()
        data.update({
            "cognitive_load": self.cognitive_load,
            "time_on_task_minutes": self.time_on_task_minutes,
            "tasks_completed": self.tasks_completed,
            "queue_depth": self.queue_depth,
            "skill_level": self.skill_level,
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OperatorHolon":
        """Create from dictionary representation."""
        state_str = data.get("state", "AVAILABLE")
        if isinstance(state_str, ResourceState):
            state = state_str
        else:
            state = ResourceState(state_str)
            
        return cls(
            holon_id=data["holon_id"],
            state=state,
            cognitive_load=float(data.get("cognitive_load", 0.3)),
            time_on_task_minutes=float(data.get("time_on_task_minutes", 0.0)),
            tasks_completed=int(data.get("tasks_completed", 0)),
            queue_depth=int(data.get("queue_depth", 0)),
            skill_level=data.get("skill_level", "experienced"),
        )

    @property
    def is_overloaded(self) -> bool:
        """Check if operator is cognitively overloaded."""
        return self.cognitive_load > 0.75 or self.state == ResourceState.OVERLOADED
