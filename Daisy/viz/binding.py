"""
viz/binding.py – Consume simulation EventBus events and update VisualState.

The binding translates logical sim events (Q_PUT, M1_START, DISPATCHED …)
into visual state mutations (token position, status, queue lengths, etc.).
"""

from __future__ import annotations

from typing import Any

from viz.state import VisualState, Token


# ---------------------------------------------------------------------------
# Location → position mapping (filled in from config at init time)
# ---------------------------------------------------------------------------

_positions: dict[str, tuple[float, float]] = {}


def init_positions(cfg: Any) -> None:
    """Read station/queue positions from the viz config and cache them."""
    layout = cfg.viz.layout
    for name, pos in layout.station_positions.__dict__.items():
        _positions[name] = (float(pos[0]), float(pos[1]))
    for name, pos in layout.queue_positions.__dict__.items():
        _positions[name] = (float(pos[0]), float(pos[1]))
    # Also add S0 (arrival) position – left of Q0
    if "Q0" in _positions:
        _positions["S0"] = (_positions["Q0"][0] - 60, _positions["Q0"][1])


def _pos(location: str) -> tuple[float, float]:
    return _positions.get(location, (0.0, 0.0))


# ---------------------------------------------------------------------------
# Event consumer
# ---------------------------------------------------------------------------

def consume_event(event: dict[str, Any], vs: VisualState,
                  move_duration_ms: float = 200.0) -> None:
    """Process one sim event dict and mutate *vs* accordingly."""
    import time as _time

    etype = event.get("event", "")
    device_id = event.get("device_id")
    station = event.get("station", "")
    t = event.get("t", 0.0)

    vs.sim_time = t

    if device_id is None:
        return

    tok = vs.get_or_create_token(device_id)

    now_ms = _time.monotonic() * 1000  # wall-clock for animation

    # -- Queue events -------------------------------------------------------
    if etype == "Q_PUT":
        vs.queue_lengths[station] = vs.queue_lengths.get(station, 0) + 1
        _move_token(tok, station, now_ms, move_duration_ms)

    elif etype == "Q_GET":
        vs.queue_lengths[station] = max(0, vs.queue_lengths.get(station, 0) - 1)

    # -- Arrival ------------------------------------------------------------
    elif etype == "ARRIVAL_BIN":
        vs.total_arrived += 1
        tok.status = "normal"
        px, py = _pos("S0")
        tok.x = tok.target_x = px
        tok.y = tok.target_y = py
        tok.location = "S0"

    # -- Station start / end ------------------------------------------------
    elif etype.endswith("_START"):
        vs.station_devices.setdefault(station, set()).add(device_id)
        _move_token(tok, station, now_ms, move_duration_ms)

    elif etype.endswith("_END"):
        vs.station_devices.get(station, set()).discard(device_id)

    # -- Exceptions ---------------------------------------------------------
    elif etype == "UNKNOWN_MODEL":
        tok.status = "unknown"
        tok.exception_type = "unknown_model"
        vs.rejected_count += 1
        # Move off-screen or to reject area
        tok.target_x = _pos("S1")[0]
        tok.target_y = _pos("S1")[1] + 120
        tok.move_start = now_ms
        tok.move_duration = move_duration_ms

    elif etype == "BATTERY_ISSUE":
        tok.status = "exception"
        tok.exception_type = "battery_issue"
        _move_token(tok, "E2", now_ms, move_duration_ms)

    elif etype == "JAM":
        tok.status = "exception"
        tok.exception_type = "jam"
        _move_token(tok, "E3", now_ms, move_duration_ms)

    elif etype in ("MANUAL_BATT_START", "MANUAL_BATT_END"):
        _move_token(tok, "E2", now_ms, move_duration_ms)
        if etype == "MANUAL_BATT_END":
            tok.status = "normal"
            tok.exception_type = None

    elif etype in ("JAM_CLEAR_START", "JAM_CLEAR_END"):
        _move_token(tok, "E3", now_ms, move_duration_ms)
        if etype == "JAM_CLEAR_END":
            tok.status = "normal"
            tok.exception_type = None

    # -- Dispatch -----------------------------------------------------------
    elif etype == "DISPATCHED":
        tok.status = "dispatched"
        vs.completed_count += 1
        vs.throughput_history.append((t, vs.completed_count))
        vs.wip_history.append((t, vs.total_wip()))

        # Update output totals from extra
        extra = event.get("extra", {})
        outputs = extra.get("outputs", {})
        for frac, val in outputs.items():
            vs.output_totals[frac] = vs.output_totals.get(frac, 0.0) + val

        # Move past S6
        px, py = _pos("S6")
        tok.target_x = px + 80
        tok.target_y = py
        tok.move_start = now_ms
        tok.move_duration = move_duration_ms


def _move_token(tok: Token, location: str,
                now_ms: float, duration_ms: float) -> None:
    tok.location = location
    px, py = _pos(location)
    tok.target_x = px
    tok.target_y = py
    tok.move_start = now_ms
    tok.move_duration = duration_ms


# ---------------------------------------------------------------------------
# Batch consume (drain the deque up to N events per frame)
# ---------------------------------------------------------------------------

def consume_pending(vs: VisualState, bus_queue, *,
                    max_per_frame: int = 500,
                    move_duration_ms: float = 200.0) -> int:
    """Drain up to *max_per_frame* events from the bus deque."""
    consumed = 0
    while bus_queue and consumed < max_per_frame:
        evt = bus_queue.popleft()
        consume_event(evt, vs, move_duration_ms)
        consumed += 1
    return consumed
