"""Demanufacturing cell model — stations, products, events, resources.

Implements the plant model from PAPER_1 §III:
  - Product with latent conditions (ω)
  - Station / resource with availability
  - EventType enum for the event alphabet Σ
"""

from __future__ import annotations

import enum
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


# ── EventType — the event alphabet Σ ─────────────────────────────────
class EventType(str, enum.Enum):
    """Controllable and uncontrollable events in the demanufacturing cell."""

    # Controllable (Σ_c)
    PRODUCT_ARRIVE = "product_arrive"
    START_INSPECTION = "start_inspection"
    FINISH_INSPECTION = "finish_inspection"
    START_ROBOT_DISASSEMBLY = "start_robot_disassembly"
    FINISH_ROBOT_DISASSEMBLY = "finish_robot_disassembly"
    START_MANUAL_DISASSEMBLY = "start_manual_disassembly"
    FINISH_MANUAL_DISASSEMBLY = "finish_manual_disassembly"
    START_HAZARD_HANDLING = "start_hazard_handling"
    FINISH_HAZARD_HANDLING = "finish_hazard_handling"
    ROUTE_TO_OUTPUT = "route_to_output"
    PRODUCT_COMPLETE = "product_complete"
    ESCALATE = "escalate"
    REQUEST_INSPECTION = "request_inspection"

    # Uncontrollable (Σ_uc)
    STATION_FAILURE = "station_failure"
    STATION_REPAIR = "station_repair"
    EXCEPTION_STRIPPED_SCREW = "exception_stripped_screw"
    EXCEPTION_STUCK_ADHESIVE = "exception_stuck_adhesive"
    EXCEPTION_MISSING_COMPONENT = "exception_missing_component"
    EXCEPTION_BATTERY_RISK = "exception_battery_risk"

    @classmethod
    def controllable(cls) -> Set["EventType"]:
        return {
            cls.PRODUCT_ARRIVE,
            cls.START_INSPECTION,
            cls.FINISH_INSPECTION,
            cls.START_ROBOT_DISASSEMBLY,
            cls.FINISH_ROBOT_DISASSEMBLY,
            cls.START_MANUAL_DISASSEMBLY,
            cls.FINISH_MANUAL_DISASSEMBLY,
            cls.START_HAZARD_HANDLING,
            cls.FINISH_HAZARD_HANDLING,
            cls.ROUTE_TO_OUTPUT,
            cls.PRODUCT_COMPLETE,
            cls.ESCALATE,
            cls.REQUEST_INSPECTION,
        }

    @classmethod
    def uncontrollable(cls) -> Set["EventType"]:
        return {
            cls.STATION_FAILURE,
            cls.STATION_REPAIR,
            cls.EXCEPTION_STRIPPED_SCREW,
            cls.EXCEPTION_STUCK_ADHESIVE,
            cls.EXCEPTION_MISSING_COMPONENT,
            cls.EXCEPTION_BATTERY_RISK,
        }


# ── Product ──────────────────────────────────────────────────────────
class ProductPhase(str, enum.Enum):
    WAITING = "waiting"
    INSPECTION = "inspection"
    ROBOT_DISASSEMBLY = "robot_disassembly"
    MANUAL_DISASSEMBLY = "manual_disassembly"
    HAZARD_HANDLING = "hazard_handling"
    COMPLETE = "complete"
    ESCALATED = "escalated"


@dataclass(unsafe_hash=True)
class LatentCondition:
    """Hidden structural state ω for a product, sampled at creation."""

    stripped_screw: bool = False
    stuck_adhesive: bool = False
    missing_component: bool = False
    battery_risk: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "stripped_screw": self.stripped_screw,
            "stuck_adhesive": self.stuck_adhesive,
            "missing_component": self.missing_component,
            "battery_risk": self.battery_risk,
        }


@dataclass
class Product:
    """A product (device) being demanufactured."""

    uid: int
    product_type: str = "phone"
    phase: ProductPhase = ProductPhase.WAITING
    latent: LatentCondition = field(default_factory=LatentCondition)
    observed: Dict[str, Any] = field(default_factory=dict)  # revealed info
    arrival_time: float = 0.0
    completion_time: Optional[float] = None
    inspected: bool = False
    inspection_count: int = 0
    hazard_cleared: bool = False
    escalated: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "uid": self.uid,
            "product_type": self.product_type,
            "phase": self.phase.value,
            "inspected": self.inspected,
            "inspection_count": self.inspection_count,
            "hazard_cleared": self.hazard_cleared,
            "escalated": self.escalated,
            "latent": self.latent.as_dict(),
            "observed": self.observed,
        }


# ── Station / Resource ───────────────────────────────────────────────
class StationStatus(str, enum.Enum):
    IDLE = "idle"
    BUSY = "busy"
    FAILED = "failed"


@dataclass
class Station:
    """A resource / workstation in the cell."""

    name: str
    status: StationStatus = StationStatus.IDLE
    current_product: Optional[int] = None  # product uid
    queue: List[int] = field(default_factory=list)

    def is_available(self) -> bool:
        return self.status == StationStatus.IDLE

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "current_product": self.current_product,
            "queue_length": len(self.queue),
        }


# ── CellState — combined plant state x ──────────────────────────────
@dataclass
class CellState:
    """Materialised plant state x ∈ X."""

    stations: Dict[str, Station] = field(default_factory=dict)
    products: Dict[int, Product] = field(default_factory=dict)
    completed_products: List[int] = field(default_factory=list)
    escalated_products: List[int] = field(default_factory=list)
    next_product_id: int = 0

    def create_product(self, rng: random.Random, regime, arrival_time: float) -> Product:
        """Sample a new product with latent conditions drawn from *regime*."""
        uid = self.next_product_id
        self.next_product_id += 1
        latent = LatentCondition(
            stripped_screw=rng.random() < regime.stripped_screw_prob,
            stuck_adhesive=rng.random() < regime.stuck_adhesive_prob,
            missing_component=rng.random() < regime.missing_component_prob,
            battery_risk=rng.random() < regime.battery_risk_prob,
        )
        p = Product(uid=uid, latent=latent, arrival_time=arrival_time)
        self.products[uid] = p
        return p

    def as_dict(self) -> Dict[str, Any]:
        return {
            "stations": {k: v.as_dict() for k, v in self.stations.items()},
            "num_products": len(self.products),
            "completed": len(self.completed_products),
            "escalated": len(self.escalated_products),
        }
