"""Evidence queries against the twin event store (PAPER_2 §6).

Provides:
  - latest_evidence(attribute, product, freshness_constraint)
  - decision_trace(event_id) — provenance closure
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .schema import AttributeMeta, EvidenceRef, TwinEvent, TwinEventType
from .state import TwinState
from .store import EventStore


def latest_evidence(
    state: TwinState,
    product_uid: int,
    attribute: str,
    current_time: Optional[float] = None,
    max_stale: bool = False,
) -> Optional[AttributeMeta]:
    """Return the latest evidence for *attribute* on *product_uid*.

    Parameters
    ----------
    state : TwinState
        Materialised twin state.
    product_uid : int
    attribute : str
    current_time : float, optional
        If given, check freshness against this time.
    max_stale : bool
        If False (default), return None when evidence is stale.

    Returns
    -------
    AttributeMeta or None
    """
    pb = state.products.get(product_uid)
    if pb is None:
        return None

    meta = pb.attributes.get(attribute)
    if meta is None:
        return None

    if current_time is not None and not max_stale:
        if meta.is_stale(current_time):
            return None

    return meta


def decision_trace(
    store: EventStore,
    event_id: str,
    state: TwinState,
) -> List[TwinEvent]:
    """Return the provenance closure for a decision event.

    Walk backward from the event's provenance references.
    """
    target = store.get_by_id(event_id)
    if target is None:
        return []

    # Collect all referenced evidence event IDs
    visited = set()
    queue = [event_id]
    result = []

    while queue:
        eid = queue.pop(0)
        if eid in visited:
            continue
        visited.add(eid)
        evt = store.get_by_id(eid)
        if evt is None:
            continue
        result.append(evt)

        # If this event references a product, look up provenance
        uid = evt.payload.get("product")
        if uid is not None and uid in state.products:
            pb = state.products[uid]
            for meta in pb.attributes.values():
                for ref in meta.provenance:
                    if ref.event_id not in visited:
                        queue.append(ref.event_id)

    return result


def evidence_grounded_check(
    store: EventStore,
    state: TwinState,
    product_uid: int,
    required_attributes: List[str],
    current_time: float,
) -> Dict[str, Any]:
    """Check that all required attributes are evidence-grounded and fresh.

    Returns a dict with:
      - grounded: bool
      - missing: list of attributes without evidence
      - stale: list of attributes that are stale
    """
    missing = []
    stale = []

    pb = state.products.get(product_uid)
    if pb is None:
        return {"grounded": False, "missing": required_attributes, "stale": []}

    for attr in required_attributes:
        meta = pb.attributes.get(attr)
        if meta is None or not meta.provenance:
            missing.append(attr)
        elif meta.is_stale(current_time):
            stale.append(attr)

    grounded = len(missing) == 0 and len(stale) == 0
    return {"grounded": grounded, "missing": missing, "stale": stale}
