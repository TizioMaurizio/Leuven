"""Append-only event store backed by JSONL files (PAPER_2 §4.1.3, R2).

Events are appended once; corrections are new events.
Supports:
  - append(event) — write event
  - iter_events() — iterate in order
  - load from / write to JSONL
  - ingest WP1 DES logs
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import IO, Iterable, Iterator, List, Optional

from .schema import TwinEvent, des_event_to_twin


class EventStore:
    """In-memory + on-disk append-only event store.

    Events are kept in insertion order; ``seq_no`` is assigned at append time.
    """

    def __init__(self) -> None:
        self._events: List[TwinEvent] = []
        self._seq: int = 0
        self._last_hash: str = ""

    # ── append ────────────────────────────────────────────────
    def append(self, event: TwinEvent) -> TwinEvent:
        """Append a single event, assigning seq_no and hash_prev."""
        event.seq_no = self._seq
        event.hash_prev = self._last_hash
        self._seq += 1
        self._last_hash = event.content_hash()
        self._events.append(event)
        return event

    def append_raw(self, event_dict: dict) -> TwinEvent:
        """Append from a dict (e.g., deserialized JSON)."""
        evt = TwinEvent.from_dict(event_dict)
        return self.append(evt)

    # ── bulk ingest from WP1 log ──────────────────────────────
    def ingest_des_log(self, des_entries: Iterable[dict]) -> int:
        """Convert WP1 DES event dicts to TwinEvents and append.
        Returns count of ingested events.
        """
        count = 0
        for entry in des_entries:
            te = des_event_to_twin(entry, seq_no=0, prev_hash=self._last_hash)
            self.append(te)
            count += 1
        return count

    # ── iteration / queries ───────────────────────────────────
    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self) -> Iterator[TwinEvent]:
        return iter(self._events)

    def iter_events(
        self,
        start_seq: int = 0,
        end_seq: Optional[int] = None,
    ) -> Iterator[TwinEvent]:
        """Yield events in [start_seq, end_seq)."""
        for e in self._events:
            if e.seq_no < start_seq:
                continue
            if end_seq is not None and e.seq_no >= end_seq:
                break
            yield e

    def events_up_to(self, time: float) -> List[TwinEvent]:
        """Return events with event_time <= time."""
        return [e for e in self._events if e.event_time <= time]

    def get_by_id(self, event_id: str) -> Optional[TwinEvent]:
        """Retrieve event by event_id (linear scan)."""
        for e in self._events:
            if e.event_id == event_id:
                return e
        return None

    @property
    def all_events(self) -> List[TwinEvent]:
        return list(self._events)

    # ── persistence (JSONL) ───────────────────────────────────
    def write_jsonl(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            for evt in self._events:
                f.write(evt.to_json() + "\n")

    @classmethod
    def load_jsonl(cls, path: str | Path) -> "EventStore":
        """Load an EventStore from a JSONL file."""
        store = cls()
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                evt = TwinEvent.from_dict(d)
                store.append(evt)
        return store

    @classmethod
    def from_des_log_file(cls, path: str | Path) -> "EventStore":
        """Load a WP1 events.jsonl and convert to twin events."""
        store = cls()
        with open(path) as f:
            entries = [json.loads(line.strip()) for line in f if line.strip()]
        store.ingest_des_log(entries)
        return store
