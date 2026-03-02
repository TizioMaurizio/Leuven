"""Closed intent vocabulary and schema (PAPER_4 §4.1).

A finite, typed set of structured intents that the LLM may produce.
No free-form commands are accepted.
"""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class IntentType(str, enum.Enum):
    """Closed intent vocabulary."""
    REQUEST_SENSING = "request_sensing"
    CLASSIFY_EXCEPTION = "classify_exception"
    PROPOSE_ROUTING = "propose_routing"
    ESCALATE_TO_HUMAN = "escalate_to_human"


# Valid exception class IDs
EXCEPTION_CLASSES = frozenset({
    "stripped_screw",
    "stuck_adhesive",
    "missing_component",
    "battery_risk",
    "unknown_exception",
})

# Valid route IDs
ROUTE_IDS = frozenset({
    "robot_disassembly",
    "manual_disassembly",
    "hazard_handling",
    "re_inspect",
    "output",
})

# Valid sensor IDs
SENSOR_IDS = frozenset({
    "visual_inspection",
    "torque_probe",
    "battery_scan",
    "adhesive_test",
})


@dataclass
class Intent:
    """A structured intent produced by the LLM.

    All fields are typed and validated against the closed vocabulary.
    """
    intent_type: IntentType
    target_product: Optional[int] = None
    target_station: Optional[str] = None

    # Type-specific arguments
    sensor_id: Optional[str] = None        # REQUEST_SENSING
    class_id: Optional[str] = None         # CLASSIFY_EXCEPTION
    route_id: Optional[str] = None         # PROPOSE_ROUTING
    reason: str = ""                       # ESCALATE_TO_HUMAN

    # Evidence grounding
    evidence_refs: List[str] = field(default_factory=list)  # event IDs
    rationale: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "intent_type": self.intent_type.value,
            "target_product": self.target_product,
            "target_station": self.target_station,
            "sensor_id": self.sensor_id,
            "class_id": self.class_id,
            "route_id": self.route_id,
            "reason": self.reason,
            "evidence_refs": self.evidence_refs,
            "rationale": self.rationale,
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict())

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Intent":
        return cls(
            intent_type=IntentType(d["intent_type"]),
            target_product=d.get("target_product"),
            target_station=d.get("target_station"),
            sensor_id=d.get("sensor_id"),
            class_id=d.get("class_id"),
            route_id=d.get("route_id"),
            reason=d.get("reason", ""),
            evidence_refs=d.get("evidence_refs", []),
            rationale=d.get("rationale", ""),
        )


# ── Schema validation ─────────────────────────────────────────────────

class SchemaError(Exception):
    """Raised when an intent fails schema validation."""
    pass


def validate_schema(intent: Intent) -> List[str]:
    """Validate intent against the closed vocabulary schema.

    Returns a list of error messages (empty if valid).
    """
    errors: List[str] = []

    if intent.intent_type == IntentType.REQUEST_SENSING:
        if intent.sensor_id is None:
            errors.append("REQUEST_SENSING requires sensor_id")
        elif intent.sensor_id not in SENSOR_IDS:
            errors.append(f"Unknown sensor_id: {intent.sensor_id}")

    elif intent.intent_type == IntentType.CLASSIFY_EXCEPTION:
        if intent.class_id is None:
            errors.append("CLASSIFY_EXCEPTION requires class_id")
        elif intent.class_id not in EXCEPTION_CLASSES:
            errors.append(f"Unknown class_id: {intent.class_id}")

    elif intent.intent_type == IntentType.PROPOSE_ROUTING:
        if intent.route_id is None:
            errors.append("PROPOSE_ROUTING requires route_id")
        elif intent.route_id not in ROUTE_IDS:
            errors.append(f"Unknown route_id: {intent.route_id}")

    elif intent.intent_type == IntentType.ESCALATE_TO_HUMAN:
        if not intent.reason:
            errors.append("ESCALATE_TO_HUMAN requires reason")

    if intent.target_product is None:
        errors.append("target_product is required")

    return errors
