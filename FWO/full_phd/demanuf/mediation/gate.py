"""Deterministic mediation gate — schema + grounding + compile + ∩ A_sup.

Implements the validation gate from PAPER_4 §4.3:
  1. Schema/type validation
  2. Grounding validation (evidence refs exist + fresh)
  3. Intent compilation C(i, x̂) → Set[EventType]
  4. Model-consistency check: C(i, x̂) ∩ A_sup(x̂)
  5. Fallback: RequestSensing (if admissible) or EscalateToHuman
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set

from ..des.model import CellState, EventType, Product
from ..des.supervisor import Supervisor
from ..twin.schema import TwinEvent, TwinEventType, ActorType
from ..twin.store import EventStore
from .intents import Intent, IntentType, validate_schema


# ── Gate result ───────────────────────────────────────────────────────
class GateOutcome(str, enum.Enum):
    ADMITTED = "admitted"
    REJECTED_SCHEMA = "rejected_schema"
    REJECTED_GROUNDING = "rejected_grounding"
    REJECTED_EMPTY = "rejected_empty"       # compilation produced ∅
    REJECTED_SUPERVISOR = "rejected_supervisor"  # ∩ A_sup = ∅
    FALLBACK_SENSING = "fallback_sensing"
    FALLBACK_ESCALATE = "fallback_escalate"
    REJECTED_PARSE = "rejected_parse"       # malformed LLM output


@dataclass
class GateResult:
    """Result of the mediation gate."""
    outcome: GateOutcome
    admitted_events: FrozenSet[EventType] = field(default_factory=frozenset)
    rejected_reasons: List[str] = field(default_factory=list)
    intent: Optional[Intent] = None
    fallback_event: Optional[EventType] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "admitted_events": [e.value for e in self.admitted_events],
            "rejected_reasons": self.rejected_reasons,
            "fallback_event": self.fallback_event.value if self.fallback_event else None,
        }


# ── Intent compiler C(i, x̂) → Set[EventType] ────────────────────────
def compile_intent(intent: Intent, product: Product, state: CellState) -> Set[EventType]:
    """Map a validated intent to a set of candidate DES controllable events.

    This is the deterministic compiler C(i, x̂).
    """
    candidates: Set[EventType] = set()

    if intent.intent_type == IntentType.REQUEST_SENSING:
        # Map to inspection events
        if not product.inspected:
            candidates.add(EventType.START_INSPECTION)
        candidates.add(EventType.REQUEST_INSPECTION)

    elif intent.intent_type == IntentType.CLASSIFY_EXCEPTION:
        # Classification intents don't directly map to actions;
        # they inform the belief update layer.  Emit no candidate events.
        pass

    elif intent.intent_type == IntentType.PROPOSE_ROUTING:
        route = intent.route_id
        if route == "robot_disassembly":
            candidates.add(EventType.START_ROBOT_DISASSEMBLY)
        elif route == "manual_disassembly":
            candidates.add(EventType.START_MANUAL_DISASSEMBLY)
        elif route == "hazard_handling":
            candidates.add(EventType.START_HAZARD_HANDLING)
        elif route == "re_inspect":
            candidates.add(EventType.REQUEST_INSPECTION)
        elif route == "output":
            candidates.add(EventType.ROUTE_TO_OUTPUT)

    elif intent.intent_type == IntentType.ESCALATE_TO_HUMAN:
        candidates.add(EventType.ESCALATE)

    return candidates


# ── Grounding validator ───────────────────────────────────────────────
def validate_grounding(
    intent: Intent,
    store: Optional[EventStore] = None,
    max_stale_seconds: float = 120.0,
    current_time: float = 0.0,
) -> List[str]:
    """Validate that all evidence_refs exist and are fresh.

    Returns list of error strings (empty if valid).
    """
    errors: List[str] = []

    if not intent.evidence_refs:
        # Escalation intents may lack evidence; others need it
        if intent.intent_type not in (IntentType.ESCALATE_TO_HUMAN,):
            errors.append("No evidence references provided")
        return errors

    if store is None:
        return errors  # can't validate without store

    for ref_id in intent.evidence_refs:
        event = store.get_by_id(ref_id)
        if event is None:
            errors.append(f"Evidence ref not found: {ref_id}")
        else:
            age = current_time - event.event_time
            if age > max_stale_seconds:
                errors.append(f"Evidence ref stale: {ref_id} (age={age:.1f}s)")

    return errors


# ── Mediation gate ────────────────────────────────────────────────────
class MediationGate:
    """Deterministic validation gate (PAPER_4 §4.3).

    Enforces: schema → grounding → compile → ∩ A_sup → fallback.
    """

    def __init__(
        self,
        supervisor: Supervisor,
        store: Optional[EventStore] = None,
        max_stale: float = 120.0,
        require_grounding: bool = True,
    ):
        self.supervisor = supervisor
        self.store = store
        self.max_stale = max_stale
        self.require_grounding = require_grounding

        # Metrics
        self.total_proposals: int = 0
        self.admitted: int = 0
        self.rejected: int = 0
        self.fallbacks: int = 0

    def evaluate(
        self,
        intent: Optional[Intent],
        product: Product,
        state: CellState,
        current_time: float = 0.0,
        parse_error: Optional[str] = None,
    ) -> GateResult:
        """Run the full gate pipeline on an intent.

        Parameters
        ----------
        intent : the parsed intent (None if parse failed)
        product : the target product
        state : current cell state
        current_time : simulation time (for freshness checks)
        parse_error : error from LLM output parsing (if any)
        """
        self.total_proposals += 1

        # Step 0: Parse failure
        if intent is None or parse_error:
            self.rejected += 1
            return GateResult(
                outcome=GateOutcome.REJECTED_PARSE,
                rejected_reasons=[parse_error or "No intent parsed"],
            )

        # Step 1: Schema validation
        schema_errors = validate_schema(intent)
        if schema_errors:
            self.rejected += 1
            return GateResult(
                outcome=GateOutcome.REJECTED_SCHEMA,
                rejected_reasons=schema_errors,
                intent=intent,
            )

        # Step 2: Grounding validation
        if self.require_grounding:
            grounding_errors = validate_grounding(
                intent, self.store, self.max_stale, current_time,
            )
            if grounding_errors:
                self.rejected += 1
                return GateResult(
                    outcome=GateOutcome.REJECTED_GROUNDING,
                    rejected_reasons=grounding_errors,
                    intent=intent,
                )

        # Step 3: Intent compilation
        candidates = compile_intent(intent, product, state)
        if not candidates:
            self.rejected += 1
            return GateResult(
                outcome=GateOutcome.REJECTED_EMPTY,
                rejected_reasons=["Intent compiled to empty event set"],
                intent=intent,
            )

        # Step 4: Model-consistency — ∩ A_sup
        enabled = self.supervisor.enabled_set(product, state)
        admitted = frozenset(candidates & enabled)

        if admitted:
            self.admitted += 1
            return GateResult(
                outcome=GateOutcome.ADMITTED,
                admitted_events=admitted,
                intent=intent,
            )

        # Step 5: Fallback — nothing admitted
        self.fallbacks += 1

        # Try sensing as fallback
        sensing_events = {EventType.START_INSPECTION, EventType.REQUEST_INSPECTION}
        sensing_enabled = enabled & sensing_events
        if sensing_enabled:
            fb = sorted(sensing_enabled, key=lambda e: e.value)[0]
            return GateResult(
                outcome=GateOutcome.FALLBACK_SENSING,
                rejected_reasons=["Proposed events not supervisor-enabled; falling back to sensing"],
                intent=intent,
                fallback_event=fb,
            )

        # Last resort: escalate
        if EventType.ESCALATE in enabled:
            return GateResult(
                outcome=GateOutcome.FALLBACK_ESCALATE,
                rejected_reasons=["No admissible action; escalating"],
                intent=intent,
                fallback_event=EventType.ESCALATE,
            )

        return GateResult(
            outcome=GateOutcome.REJECTED_SUPERVISOR,
            rejected_reasons=["No supervisor-enabled events match; no fallback available"],
            intent=intent,
        )

    def summary(self) -> Dict[str, Any]:
        return {
            "total_proposals": self.total_proposals,
            "admitted": self.admitted,
            "rejected": self.rejected,
            "fallbacks": self.fallbacks,
            "admission_rate": self.admitted / max(self.total_proposals, 1),
        }


# ── Twin event creation for audit ────────────────────────────────────
def create_gate_event(
    gate_result: GateResult,
    product_uid: int,
    event_time: float,
) -> TwinEvent:
    """Create a twin event recording a gate decision for audit."""
    if gate_result.outcome == GateOutcome.ADMITTED:
        event_type = TwinEventType.ACTION_ADMITTED
    elif gate_result.outcome in (GateOutcome.FALLBACK_SENSING, GateOutcome.FALLBACK_ESCALATE):
        event_type = TwinEventType.ACTION_PROPOSED
    else:
        event_type = TwinEventType.ACTION_REJECTED

    return TwinEvent(
        event_time=event_time,
        event_type=event_type,
        actor=ActorType.COORDINATOR,
        payload={
            "product": product_uid,
            "gate_outcome": gate_result.outcome.value,
            "admitted_events": [e.value for e in gate_result.admitted_events],
            "rejected_reasons": gate_result.rejected_reasons,
            "fallback": gate_result.fallback_event.value if gate_result.fallback_event else None,
        },
    )
