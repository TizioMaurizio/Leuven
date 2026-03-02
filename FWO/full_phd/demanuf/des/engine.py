"""Minimal custom DES scheduler built on heapq.

Provides:
  - Event queue with deterministic tie-breaking
  - Simulation clock
  - Step / run interface
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# ── Scheduled event (priority-queue item) ────────────────────────────
@dataclass(order=True)
class ScheduledEvent:
    """Wrapper for the priority queue.  Ordering: (time, seq) for determinism."""

    time: float
    seq: int = field(compare=True)  # tie-breaker — insertion order
    callback: Callable[..., None] = field(compare=False)
    payload: Dict[str, Any] = field(default_factory=dict, compare=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"ScheduledEvent(t={self.time:.3f}, seq={self.seq}, payload={self.payload})"


# ── DES Engine ───────────────────────────────────────────────────────
class DESEngine:
    """Discrete-event simulation engine.

    * ``schedule(delay, callback, **payload)`` — add future event.
    * ``step()`` — pop next event, advance clock, invoke callback.
    * ``run(until=)`` — run until time limit or queue empty.
    """

    def __init__(self) -> None:
        self._queue: List[ScheduledEvent] = []
        self._seq: int = 0
        self.now: float = 0.0
        self._event_log: List[Dict[str, Any]] = []
        self._stopped: bool = False

    # ── scheduling ────────────────────────────────────────────
    def schedule(
        self,
        delay: float,
        callback: Callable[..., None],
        **payload: Any,
    ) -> ScheduledEvent:
        """Schedule *callback* to fire at ``now + delay``."""
        assert delay >= 0, f"Cannot schedule in the past (delay={delay})"
        evt = ScheduledEvent(
            time=self.now + delay,
            seq=self._seq,
            callback=callback,
            payload=payload,
        )
        self._seq += 1
        heapq.heappush(self._queue, evt)
        return evt

    # ── execution ─────────────────────────────────────────────
    def step(self) -> Optional[ScheduledEvent]:
        """Pop and execute the next event.  Returns it, or None if empty."""
        if not self._queue or self._stopped:
            return None
        evt = heapq.heappop(self._queue)
        self.now = evt.time
        evt.callback(self, evt)
        return evt

    def run(self, *, until: Optional[float] = None, max_steps: Optional[int] = None) -> int:
        """Run the simulation.

        Parameters
        ----------
        until : float, optional
            Stop when ``now >= until``.
        max_steps : int, optional
            Stop after this many events processed.

        Returns
        -------
        int
            Number of events processed.
        """
        count = 0
        while self._queue and not self._stopped:
            if until is not None and self._queue[0].time > until:
                break
            if max_steps is not None and count >= max_steps:
                break
            self.step()
            count += 1
        return count

    def stop(self) -> None:
        """Graceful stop — ``run`` will return at next iteration."""
        self._stopped = True

    @property
    def is_empty(self) -> bool:
        return len(self._queue) == 0

    def reset(self) -> None:
        """Reset engine to time-zero with an empty queue."""
        self._queue.clear()
        self._seq = 0
        self.now = 0.0
        self._event_log.clear()
        self._stopped = False

    def peek_time(self) -> Optional[float]:
        """Return the time of the next scheduled event, or None."""
        return self._queue[0].time if self._queue else None
