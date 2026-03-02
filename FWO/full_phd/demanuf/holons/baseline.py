"""Baseline holonic coordination policy — routing + exception handling.

No AI; purely rule-based priority routing.  Serves as the WP1 baseline
and as the "no-adaptive" comparator in later ablation studies.
"""

from __future__ import annotations

from typing import Optional

from ..des.model import (
    CellState,
    EventType,
    Product,
    ProductPhase,
    StationStatus,
)
from .protocol import CoordinationPolicy


class BaselinePolicy(CoordinationPolicy):
    """Rule-based priority routing policy.

    Priority order after inspection:
      1. Hazard handling if battery risk observed and not cleared
      2. Robot disassembly if available and no blocking condition
      3. Manual disassembly fallback
      4. Escalate if nothing possible
    """

    def decide(
        self,
        product_uid: int,
        state: CellState,
        enabled_set: frozenset,
    ) -> Optional[EventType]:
        product = state.products.get(product_uid)
        if product is None:
            return None

        # Priority ordering over enabled set
        priority = [
            EventType.FINISH_INSPECTION,
            EventType.FINISH_ROBOT_DISASSEMBLY,
            EventType.FINISH_MANUAL_DISASSEMBLY,
            EventType.FINISH_HAZARD_HANDLING,
            EventType.START_HAZARD_HANDLING,
            EventType.START_INSPECTION,
            EventType.START_ROBOT_DISASSEMBLY,
            EventType.START_MANUAL_DISASSEMBLY,
            EventType.ROUTE_TO_OUTPUT,
            EventType.REQUEST_INSPECTION,
            EventType.ESCALATE,
        ]

        for evt in priority:
            if evt in enabled_set:
                return evt

        return None
