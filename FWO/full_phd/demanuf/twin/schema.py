"""Canonical event and evidence schema for the EEDT (PAPER_2 §4.1).

Defines:
  - TwinEventType enum
  - ActorType enum
  - EvidenceRef
  - AttributeMeta (value + confidence + freshness + provenance)
  - TwinEvent dataclass — the canonical record
"""

from __future__ import annotations

import enum
import hashlib
import json
import time as _time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set


# ── Enums ─────────────────────────────────────────────────────────────
class TwinEventType(str, enum.Enum):
    OBSERVATION = "observation"
    ACTION_PROPOSED = "action_proposed"
    ACTION_ADMITTED = "action_admitted"
    ACTION_REJECTED = "action_rejected"
    ACTION_EXECUTED = "action_executed"
    EXCEPTION = "exception"
    HUMAN_DECISION = "human_decision"
    MODEL_REVISION = "model_revision"
    BELIEF_UPDATE = "belief_update"
    # WP1-originated DES events mapped to twin events
    DES_EVENT = "des_event"


class ActorType(str, enum.Enum):
    SENSOR = "sensor"
    PLC = "plc"
    OPERATOR = "operator"
    COORDINATOR = "coordinator"
    TWIN_INFERENCE = "twin_inference"
    DES_ENGINE = "des_engine"


# ── Evidence reference ────────────────────────────────────────────────
@dataclass(frozen=True)
class EvidenceRef:
    """Pointer to an event that serves as evidence for an attribute."""
    event_id: str
    source: str = ""
    method: str = ""

    def as_dict(self) -> Dict[str, str]:
        return {"event_id": self.event_id, "source": self.source, "method": self.method}


# ── Attribute metadata (R3 + R4) ──────────────────────────────────────
@dataclass
class AttributeMeta:
    """Metadata for a single state attribute: value + confidence + freshness + provenance."""

    value: Any = None
    confidence: float = 0.0           # c ∈ [0, 1]
    event_time: float = 0.0           # τ — last validation time
    validity_window: float = 60.0     # w — seconds of validity
    provenance: List[EvidenceRef] = field(default_factory=list)

    @property
    def valid_until(self) -> float:
        return self.event_time + self.validity_window

    def is_stale(self, current_time: float) -> bool:
        return current_time > self.valid_until

    def as_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "confidence": self.confidence,
            "event_time": self.event_time,
            "valid_until": self.valid_until,
            "provenance": [r.as_dict() for r in self.provenance],
        }


# ── Canonical twin event (R1, R2) ────────────────────────────────────
@dataclass
class TwinEvent:
    """Immutable canonical event record.

    All state changes in the EEDT are represented as TwinEvent instances.
    """

    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    seq_no: int = 0
    event_time: float = 0.0
    ingest_time: float = field(default_factory=_time.monotonic)
    event_type: TwinEventType = TwinEventType.DES_EVENT
    actor: ActorType = ActorType.DES_ENGINE
    payload: Dict[str, Any] = field(default_factory=dict)
    hash_prev: str = ""

    # ── Serialisation ─────────────────────────────────────────
    def as_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "seq_no": self.seq_no,
            "event_time": self.event_time,
            "ingest_time": self.ingest_time,
            "event_type": self.event_type.value,
            "actor": self.actor.value,
            "payload": self.payload,
            "hash_prev": self.hash_prev,
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), default=str)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TwinEvent":
        return cls(
            event_id=d.get("event_id", uuid.uuid4().hex[:16]),
            seq_no=d.get("seq_no", 0),
            event_time=d.get("event_time", 0.0),
            ingest_time=d.get("ingest_time", 0.0),
            event_type=TwinEventType(d.get("event_type", "des_event")),
            actor=ActorType(d.get("actor", "des_engine")),
            payload=d.get("payload", {}),
            hash_prev=d.get("hash_prev", ""),
        )

    def content_hash(self) -> str:
        """SHA-256 over deterministic serialisation (for chain)."""
        raw = json.dumps(self.as_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ── Helpers ───────────────────────────────────────────────────────────
def des_event_to_twin(
    des_entry: Dict[str, Any], seq_no: int, prev_hash: str = ""
) -> TwinEvent:
    """Convert a WP1 DES log entry to a canonical TwinEvent."""
    etype_str = des_entry.get("event", "des_event")
    # Map some DES events to twin types
    twin_type = TwinEventType.DES_EVENT
    actor = ActorType.DES_ENGINE

    if "inspection" in etype_str:
        twin_type = TwinEventType.OBSERVATION
        actor = ActorType.SENSOR
    elif "exception" in etype_str:
        twin_type = TwinEventType.EXCEPTION
    elif "escalate" in etype_str:
        twin_type = TwinEventType.HUMAN_DECISION
        actor = ActorType.OPERATOR

    return TwinEvent(
        seq_no=seq_no,
        event_time=des_entry.get("time", 0.0),
        event_type=twin_type,
        actor=actor,
        payload=des_entry,
        hash_prev=prev_hash,
    )
