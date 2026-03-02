"""BeliefTracker — per-product belief management and orchestration (PAPER_3).

Maintains a BeliefSet for each active product, processes evidence from
the twin event stream, and emits BELIEF_UPDATE events back to the store.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..des.model import CellState, EventType, Product
from ..des.supervisor import Supervisor
from ..twin.schema import TwinEvent, TwinEventType
from ..twin.store import EventStore
from .belief import (
    BeliefSet,
    UpdateResult,
    create_belief_update_event,
    evidence_from_twin_event,
)
from .ask import AskPolicy, CommitmentDecision, confidence_gate
from .feasibility import classify_actions


@dataclass
class TrackerMetrics:
    """Aggregate metrics for the learning layer."""
    updates: int = 0
    contractions: int = 0
    abstentions: int = 0
    asks: int = 0
    escalations: int = 0
    robust_commits: int = 0
    belief_size_trajectory: List[Dict[str, Any]] = field(default_factory=list)

    def record(self, product_uid: int, belief_size: int, event_time: float) -> None:
        self.belief_size_trajectory.append({
            "product": product_uid,
            "size": belief_size,
            "time": event_time,
        })

    def summary(self) -> Dict[str, Any]:
        return {
            "updates": self.updates,
            "contractions": self.contractions,
            "abstentions": self.abstentions,
            "asks": self.asks,
            "escalations": self.escalations,
            "robust_commits": self.robust_commits,
            "avg_final_belief": self._avg_final_belief(),
            "monotonic": self._is_monotonic(),
        }

    def _avg_final_belief(self) -> float:
        if not self.belief_size_trajectory:
            return 16.0
        # Last entry per product
        last: Dict[int, int] = {}
        for entry in self.belief_size_trajectory:
            last[entry["product"]] = entry["size"]
        return sum(last.values()) / max(len(last), 1)

    def _is_monotonic(self) -> bool:
        """Check that belief size never increased for any product."""
        prev: Dict[int, int] = {}
        for entry in self.belief_size_trajectory:
            pid = entry["product"]
            sz = entry["size"]
            if pid in prev and sz > prev[pid]:
                return False
            prev[pid] = sz
        return True


@dataclass
class BeliefTracker:
    """Orchestrates per-product belief sets and the ask policy.

    Parameters
    ----------
    supervisor : the DES supervisor providing enabled sets
    store : optional twin EventStore for emitting belief events
    ask_policy : VoI-based query policy
    """

    supervisor: Supervisor = field(default_factory=Supervisor)
    store: Optional[EventStore] = None
    ask_policy: AskPolicy = field(default_factory=AskPolicy)

    _beliefs: Dict[int, BeliefSet] = field(default_factory=dict)
    metrics: TrackerMetrics = field(default_factory=TrackerMetrics)

    def get_belief(self, product_uid: int) -> BeliefSet:
        if product_uid not in self._beliefs:
            self._beliefs[product_uid] = BeliefSet(product_uid=product_uid)
        return self._beliefs[product_uid]

    def process_event(self, event: TwinEvent) -> Optional[UpdateResult]:
        """Process a twin event — extract evidence, update belief, emit events.

        Returns the UpdateResult if an update was attempted, else None.
        """
        evidence = evidence_from_twin_event(event)
        if evidence is None:
            return None

        product_uid = event.payload.get("product")
        if product_uid is None:
            return None

        belief = self.get_belief(product_uid)
        result = belief.update(evidence)

        self.metrics.updates += 1
        if result.abstained:
            self.metrics.abstentions += 1
        elif result.outcome.value == "contracted":
            self.metrics.contractions += 1

        self.metrics.record(product_uid, belief.size, event.event_time)

        # Emit belief update to twin store
        if self.store is not None:
            twin_evt = create_belief_update_event(
                product_uid=product_uid,
                result=result,
                event_time=event.event_time,
                belief_set_size=belief.size,
            )
            self.store.append(twin_evt)

        return result

    def decide(
        self,
        product: Product,
        state: CellState,
        preferred_action: Optional[EventType] = None,
    ) -> CommitmentDecision:
        """Apply confidence-gate logic for a product.

        Returns a CommitmentDecision (robust commit / ask / escalate).
        """
        belief = self.get_belief(product.uid)
        decision = confidence_gate(
            belief=belief,
            product=product,
            state=state,
            supervisor=self.supervisor,
            ask_policy=self.ask_policy,
            preferred_action=preferred_action,
        )

        if decision.kind == "robust":
            self.metrics.robust_commits += 1
        elif decision.kind == "ask":
            self.metrics.asks += 1
        elif decision.kind == "escalate":
            self.metrics.escalations += 1

        return decision

    def remove_product(self, product_uid: int) -> None:
        """Clean up belief state for a completed/escalated product."""
        self._beliefs.pop(product_uid, None)

    def summary(self) -> Dict[str, Any]:
        return {
            "active_products": len(self._beliefs),
            "metrics": self.metrics.summary(),
        }
