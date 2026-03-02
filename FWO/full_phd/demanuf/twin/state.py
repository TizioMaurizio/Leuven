"""Materialised twin state with belief objects (PAPER_2 §4.2, §4.3).

State is produced by replaying events through a deterministic reducer.
Each attribute tracks confidence, freshness, and provenance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .schema import AttributeMeta, EvidenceRef, TwinEvent, TwinEventType


@dataclass
class ProductBelief:
    """Belief state for a single product, derived from evidence."""

    uid: int = 0
    attributes: Dict[str, AttributeMeta] = field(default_factory=dict)
    phase: str = "unknown"
    last_updated: float = 0.0

    def get(self, attr_name: str) -> Optional[AttributeMeta]:
        return self.attributes.get(attr_name)

    def set_attribute(
        self,
        name: str,
        value: Any,
        confidence: float,
        event_time: float,
        evidence: Optional[EvidenceRef] = None,
        validity_window: float = 60.0,
    ) -> None:
        meta = self.attributes.get(name)
        if meta is None:
            meta = AttributeMeta(validity_window=validity_window)
            self.attributes[name] = meta
        meta.value = value
        meta.confidence = confidence
        meta.event_time = event_time
        if evidence:
            meta.provenance.append(evidence)
        self.last_updated = event_time


@dataclass
class TwinState:
    """Materialised twin state for the entire cell.

    Built by fold(reducer, initial, events).
    """

    products: Dict[int, ProductBelief] = field(default_factory=dict)
    station_status: Dict[str, str] = field(default_factory=dict)
    current_time: float = 0.0
    events_applied: int = 0

    # History of belief update events for tracing
    belief_history: List[Dict[str, Any]] = field(default_factory=list)

    def get_product(self, uid: int) -> ProductBelief:
        if uid not in self.products:
            self.products[uid] = ProductBelief(uid=uid)
        return self.products[uid]

    def summary(self) -> Dict[str, Any]:
        return {
            "current_time": self.current_time,
            "events_applied": self.events_applied,
            "num_products": len(self.products),
            "stations": dict(self.station_status),
        }


def reducer(state: TwinState, event: TwinEvent) -> TwinState:
    """Deterministic state-transition function f(s, e) → s'.

    This is the core fold function for replay.
    """
    state.current_time = max(state.current_time, event.event_time)
    state.events_applied += 1

    payload = event.payload
    product_uid = payload.get("product")
    evidence_ref = EvidenceRef(event_id=event.event_id, source=event.actor.value)

    # ── Observation events (inspection results) ───────────────
    if event.event_type == TwinEventType.OBSERVATION:
        if product_uid is not None:
            pb = state.get_product(product_uid)
            observed = payload.get("observed", {})
            for attr_name, attr_val in observed.items():
                pb.set_attribute(
                    attr_name,
                    value=attr_val,
                    confidence=0.9,  # sensor observation confidence
                    event_time=event.event_time,
                    evidence=evidence_ref,
                )
            pb.phase = payload.get("event", pb.phase)

    # ── DES events (routing, start/finish, etc.) ──────────────
    elif event.event_type == TwinEventType.DES_EVENT:
        if product_uid is not None:
            pb = state.get_product(product_uid)
            evt_name = payload.get("event", "")
            if "complete" in evt_name:
                pb.phase = "complete"
            elif "start_" in evt_name or "finish_" in evt_name:
                pb.phase = evt_name
        station = payload.get("station")
        if station:
            evt_name = payload.get("event", "")
            if "start" in evt_name:
                state.station_status[station] = "busy"
            elif "finish" in evt_name or "repair" in evt_name:
                state.station_status[station] = "idle"
            elif "failure" in evt_name:
                state.station_status[station] = "failed"

    # ── Belief update ─────────────────────────────────────────
    elif event.event_type == TwinEventType.BELIEF_UPDATE:
        if product_uid is not None:
            pb = state.get_product(product_uid)
            for attr_name, attr_data in payload.get("updates", {}).items():
                pb.set_attribute(
                    attr_name,
                    value=attr_data.get("value"),
                    confidence=attr_data.get("confidence", 0.5),
                    event_time=event.event_time,
                    evidence=evidence_ref,
                )
        state.belief_history.append(event.as_dict())

    # ── Exception ─────────────────────────────────────────────
    elif event.event_type == TwinEventType.EXCEPTION:
        if product_uid is not None:
            pb = state.get_product(product_uid)
            exception_type = payload.get("event", "unknown_exception")
            # Mark the discovered condition
            if "stripped_screw" in exception_type:
                pb.set_attribute("stripped_screw", True, 1.0, event.event_time, evidence_ref)
            elif "stuck_adhesive" in exception_type:
                pb.set_attribute("stuck_adhesive", True, 1.0, event.event_time, evidence_ref)
            elif "battery_risk" in exception_type:
                pb.set_attribute("battery_risk", True, 1.0, event.event_time, evidence_ref)

    # ── Action proposed/admitted/rejected ──────────────────────
    elif event.event_type in (
        TwinEventType.ACTION_PROPOSED,
        TwinEventType.ACTION_ADMITTED,
        TwinEventType.ACTION_REJECTED,
    ):
        # Record in belief history for tracing
        state.belief_history.append(event.as_dict())

    # ── Human decision (escalations) ──────────────────────────
    elif event.event_type == TwinEventType.HUMAN_DECISION:
        if product_uid is not None:
            pb = state.get_product(product_uid)
            pb.phase = "escalated"

    return state
