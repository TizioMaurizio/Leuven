"""Deterministic replay / materialisation service (PAPER_2 §4.1.2, R5).

Replays an ordered event log through the reducer to produce twin state
at any point in time.
"""

from __future__ import annotations

from typing import List, Optional

from .schema import TwinEvent
from .state import TwinState, reducer
from .store import EventStore


def replay(
    store: EventStore,
    *,
    up_to_time: Optional[float] = None,
    up_to_seq: Optional[int] = None,
    initial_state: Optional[TwinState] = None,
) -> TwinState:
    """Materialise twin state by replaying events from *store*.

    Parameters
    ----------
    store : EventStore
    up_to_time : float, optional
        Replay events with event_time <= this value.
    up_to_seq : int, optional
        Replay events with seq_no < this value.
    initial_state : TwinState, optional
        Starting state (default: fresh empty state).

    Returns
    -------
    TwinState
        The materialised state after applying matching events.
    """
    state = initial_state if initial_state is not None else TwinState()

    for event in store:
        if up_to_time is not None and event.event_time > up_to_time:
            break
        if up_to_seq is not None and event.seq_no >= up_to_seq:
            break
        state = reducer(state, event)

    return state


def replay_events(
    events: List[TwinEvent],
    initial_state: Optional[TwinState] = None,
) -> TwinState:
    """Replay a list of events (useful for testing without a store)."""
    state = initial_state if initial_state is not None else TwinState()
    for event in events:
        state = reducer(state, event)
    return state


def snapshot_hash(state: TwinState) -> str:
    """Produce a deterministic hash of the materialised state for comparison."""
    import hashlib
    import json

    # Build a deterministic representation
    data: dict = {
        "current_time": state.current_time,
        "events_applied": state.events_applied,
        "products": {},
        "stations": dict(sorted(state.station_status.items())),
    }
    for uid in sorted(state.products.keys()):
        pb = state.products[uid]
        attrs = {}
        for k in sorted(pb.attributes.keys()):
            a = pb.attributes[k]
            attrs[k] = {
                "value": a.value,
                "confidence": a.confidence,
                "event_time": a.event_time,
            }
        data["products"][uid] = {"phase": pb.phase, "attributes": attrs}

    raw = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()
