"""Message types and negotiation interface for holonic coordination.

Defines the inter-holon message vocabulary used by coordination policies.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set

from ..des.model import EventType


class MessageType(str, enum.Enum):
    TASK_REQUEST = "task_request"
    TASK_OFFER = "task_offer"
    TASK_ACCEPT = "task_accept"
    TASK_REJECT = "task_reject"
    ROUTING_DECISION = "routing_decision"
    EXCEPTION_REPORT = "exception_report"
    ESCALATION = "escalation"
    STATUS_UPDATE = "status_update"


@dataclass
class HolonicMessage:
    """A message exchanged between holons."""

    msg_type: MessageType
    sender: str
    receiver: str
    product_uid: Optional[int] = None
    proposed_action: Optional[EventType] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


class CoordinationPolicy:
    """Abstract base for holonic coordination policies.

    Sub-classes must implement ``decide`` which, given the current state,
    returns the set of proposed controllable events for a product.
    """

    def decide(
        self,
        product_uid: int,
        state: Any,
        enabled_set: frozenset,
    ) -> Optional[EventType]:
        """Pick one event from *enabled_set* for *product_uid*, or None."""
        raise NotImplementedError
