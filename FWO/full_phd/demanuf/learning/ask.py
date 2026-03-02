"""Learning-to-Ask — VoI-based targeted sensing policy (PAPER_3 §5).

Selects cost-effective inspection actions from within the supervisor-enabled
set to maximise information gain per unit cost:

    Q(B_t, x̂_t) = argmax_{σ^q ∈ A_sup ∩ Σ_q}  Δ(σ^q; B_t) / c(σ^q)

Escalates when no useful query exists or when safety-critical ambiguity
persists beyond a budget.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from ..des.model import EventType, CellState, Product
from ..des.supervisor import Supervisor
from .belief import BeliefSet, credible_region, THETA_FULL
from .feasibility import classify_actions


# ── Inspection / query event types ───────────────────────────────────
QUERY_EVENTS: FrozenSet[EventType] = frozenset({
    EventType.START_INSPECTION,
    EventType.REQUEST_INSPECTION,
})

# ── Inspection costs (time-units) ────────────────────────────────────
DEFAULT_INSPECTION_COSTS: Dict[EventType, float] = {
    EventType.START_INSPECTION: 5.0,     # full visual + sensor
    EventType.REQUEST_INSPECTION: 3.0,   # quick re-inspect / targeted probe
}

# Attribute-specific inspection: which attributes each inspection can reveal
INSPECTION_REVEALS: Dict[EventType, List[str]] = {
    EventType.START_INSPECTION: [
        "stripped_screw", "stuck_adhesive", "missing_component", "battery_risk",
    ],
    EventType.REQUEST_INSPECTION: [
        "stripped_screw", "stuck_adhesive", "missing_component", "battery_risk",
    ],
}


# ── Ask result ────────────────────────────────────────────────────────
class AskDecision:
    """Result of the ask policy."""

    def __init__(
        self,
        action: Optional[EventType] = None,
        voi: float = 0.0,
        cost: float = 0.0,
        escalate: bool = False,
        reason: str = "",
    ):
        self.action = action
        self.voi = voi
        self.cost = cost
        self.escalate = escalate
        self.reason = reason

    @property
    def voi_per_cost(self) -> float:
        if self.cost <= 0:
            return 0.0
        return self.voi / self.cost

    def as_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value if self.action else None,
            "voi": round(self.voi, 4),
            "cost": round(self.cost, 4),
            "voi_per_cost": round(self.voi_per_cost, 4),
            "escalate": self.escalate,
            "reason": self.reason,
        }


# ── Expected uncertainty reduction ────────────────────────────────────
def _expected_reduction(
    query: EventType,
    belief: BeliefSet,
) -> float:
    """Estimate Δ(σ^q; B_t) = E[U(B_t) - U(B_t ∩ C(E(σ^q)))].

    We enumerate possible outcomes for the attributes the query can reveal.
    Each outcome yields a credible region; we weight by the fraction of
    current hypotheses consistent with that outcome.
    """
    attrs = INSPECTION_REVEALS.get(query, [])
    if not attrs or belief.size <= 1:
        return 0.0

    u_before = belief.uncertainty
    # Enumerate distinct attribute signatures within current belief set
    outcomes: Dict[tuple, int] = {}
    for theta in belief.beliefs:
        sig = tuple(getattr(theta, a, None) for a in attrs)
        outcomes[sig] = outcomes.get(sig, 0) + 1

    total = belief.size
    expected_u_after = 0.0
    for sig, count in outcomes.items():
        prob = count / total
        # Posterior belief size = count (those θ matching this observation)
        u_after = math.log2(count) if count > 1 else 0.0
        expected_u_after += prob * u_after

    return u_before - expected_u_after


# ── Ask policy ────────────────────────────────────────────────────────
@dataclass
class AskPolicy:
    """VoI-based targeted sensing policy.

    Parameters
    ----------
    costs : dict mapping EventType → float (time-unit cost)
    min_voi_per_cost : threshold below which we escalate
    max_inspections : hard cap on repeated inspections
    """

    costs: Dict[EventType, float] = field(
        default_factory=lambda: dict(DEFAULT_INSPECTION_COSTS)
    )
    min_voi_per_cost: float = 0.1
    max_inspections: int = 3

    def ask(
        self,
        belief: BeliefSet,
        product: Product,
        state: CellState,
        supervisor: Supervisor,
    ) -> AskDecision:
        """Select the best admissible query or escalate.

        Steps:
        1. Get supervisor-enabled set for product
        2. Intersect with QUERY_EVENTS → admissible queries
        3. Evaluate VoI / cost for each
        4. Select best, or escalate
        """
        # Already resolved
        if belief.size <= 1:
            return AskDecision(
                escalate=False,
                reason="belief_resolved",
            )

        # Inspection cap
        if product.inspection_count >= self.max_inspections:
            return AskDecision(
                escalate=True,
                reason="max_inspections_reached",
            )

        # Admissible queries
        enabled = supervisor.enabled_set(product, state)
        admissible_queries = enabled & QUERY_EVENTS
        if not admissible_queries:
            return AskDecision(
                escalate=True,
                reason="no_admissible_query",
            )

        # Evaluate each
        best: Optional[AskDecision] = None
        for q in admissible_queries:
            delta = _expected_reduction(q, belief)
            cost = self.costs.get(q, 1.0)
            candidate = AskDecision(
                action=q,
                voi=delta,
                cost=cost,
            )
            if best is None or candidate.voi_per_cost > best.voi_per_cost:
                best = candidate

        # Threshold gate
        if best is None or best.voi_per_cost < self.min_voi_per_cost:
            return AskDecision(
                escalate=True,
                reason="voi_below_threshold",
            )

        best.reason = "selected"
        return best


# ── Commitment logic (§4.3) ──────────────────────────────────────────
@dataclass
class CommitmentDecision:
    """Outcome of the confidence threshold logic."""
    action: Optional[EventType] = None
    kind: str = ""  # "robust", "ask", "escalate"
    ask_decision: Optional[AskDecision] = None
    reason: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value if self.action else None,
            "kind": self.kind,
            "reason": self.reason,
            "ask": self.ask_decision.as_dict() if self.ask_decision else None,
        }


# Actions whose physical feasibility depends on latent conditions.
# Only these are tested against the belief set; others (escalate, finish,
# inspection, etc.) are not subject to feasibility constraints.
_WORK_ACTIONS: FrozenSet[EventType] = frozenset({
    EventType.START_ROBOT_DISASSEMBLY,
    EventType.FINISH_ROBOT_DISASSEMBLY,
    EventType.START_MANUAL_DISASSEMBLY,
    EventType.FINISH_MANUAL_DISASSEMBLY,
    EventType.START_HAZARD_HANDLING,
    EventType.FINISH_HAZARD_HANDLING,
})


def confidence_gate(
    belief: BeliefSet,
    product: Product,
    state: CellState,
    supervisor: Supervisor,
    ask_policy: AskPolicy,
    preferred_action: Optional[EventType] = None,
) -> CommitmentDecision:
    """Apply the confidence threshold logic (PAPER_3 §4.3).

    1. If preferred_action is robust-feasible under B_t → commit.
    2. Else check all enabled *work* actions for robust-feasible → pick best.
    3. If only maybe-feasible work actions → ask.
    4. If no feasible work action → escalate.

    Only "work" actions (disassembly, hazard handling) are subject to
    feasibility analysis.  Queries, escalations, and finish events are
    handled separately.
    """
    from .feasibility import robust_feasible, maybe_feasible

    enabled = supervisor.enabled_set(product, state)
    work_enabled = enabled & _WORK_ACTIONS

    # 1. Check preferred action (if it's a work action)
    if preferred_action and preferred_action in work_enabled:
        if robust_feasible(preferred_action, belief.beliefs):
            return CommitmentDecision(
                action=preferred_action,
                kind="robust",
                reason="preferred_robust_feasible",
            )

    # 2. Find any robust-feasible work action
    for a in sorted(work_enabled, key=lambda e: e.value):  # deterministic order
        if robust_feasible(a, belief.beliefs):
            return CommitmentDecision(
                action=a,
                kind="robust",
                reason="robust_feasible",
            )

    # 3. Maybe-feasible work action → trigger ask
    has_maybe = any(maybe_feasible(a, belief.beliefs) for a in work_enabled)

    if has_maybe:
        ask_dec = ask_policy.ask(belief, product, state, supervisor)
        return CommitmentDecision(
            kind="ask",
            ask_decision=ask_dec,
            reason="maybe_feasible_ask_triggered",
        )

    # 4. Escalate — no feasible work action
    return CommitmentDecision(
        kind="escalate",
        action=EventType.ESCALATE if EventType.ESCALATE in enabled else None,
        reason="no_feasible_action",
    )
