"""Conservative belief-set update module (PAPER_3 §4).

Maintains a set-valued belief B_t ⊆ Θ (all plausible latent conditions)
and performs monotonic set-contraction updates via:

    B_{t+1} = B_t ∩ C(e_t)

With abstention when evidence is uninformative, shift is detected, or
the intersection would be empty.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from ..des.model import EventType, LatentCondition
from ..twin.schema import TwinEvent, TwinEventType, ActorType


# ── Enumerate Θ (all 2^4 = 16 latent-condition hypotheses) ───────────
def _all_latent_conditions() -> FrozenSet[LatentCondition]:
    """Generate the full hypothesis space Θ."""
    conditions: Set[LatentCondition] = set()
    for ss in (False, True):
        for sa in (False, True):
            for mc in (False, True):
                for br in (False, True):
                    conditions.add(LatentCondition(
                        stripped_screw=ss,
                        stuck_adhesive=sa,
                        missing_component=mc,
                        battery_risk=br,
                    ))
    return frozenset(conditions)


THETA_FULL: FrozenSet[LatentCondition] = _all_latent_conditions()
assert len(THETA_FULL) == 16


# ── Update result ─────────────────────────────────────────────────────
class UpdateOutcome(str, enum.Enum):
    CONTRACTED = "contracted"       # B shrank
    NO_CHANGE = "no_change"         # C(e) superset of B already
    ABSTAINED_LOW_INFO = "abstained_low_info"
    ABSTAINED_SHIFT = "abstained_shift"
    ABSTAINED_EMPTY = "abstained_empty"


@dataclass
class UpdateResult:
    """Result of a single belief update step."""
    outcome: UpdateOutcome
    belief_before: int      # |B_t|
    belief_after: int       # |B_{t+1}|
    evidence_set_size: int  # |C(e)|
    abstained: bool = False


# ── Credibility region builder C(e) ──────────────────────────────────
def credible_region(evidence: Dict[str, Any]) -> Set[LatentCondition]:
    """Compute C(e_t) — the set of latent conditions consistent with evidence.

    Evidence is a dict mapping attribute names to observed values
    (e.g., {"battery_risk": True, "stripped_screw": False}).
    Only constrain on *positive observations*; absent keys are unconstrained.
    """
    region: Set[LatentCondition] = set()
    for theta in THETA_FULL:
        consistent = True
        for attr, val in evidence.items():
            theta_val = getattr(theta, attr, None)
            if theta_val is not None and theta_val != val:
                consistent = False
                break
        if consistent:
            region.add(theta)
    return region


# ── Belief Set tracker ────────────────────────────────────────────────
@dataclass
class BeliefSet:
    """Set-valued belief B_t ⊆ Θ for a single product.

    Starts as Θ (full ignorance) and can only shrink.
    """

    product_uid: int = 0
    beliefs: Set[LatentCondition] = field(default_factory=lambda: set(THETA_FULL))
    history: List[Dict[str, Any]] = field(default_factory=list)

    # Tuneable thresholds
    min_informativeness: float = 0.5   # C(e) must eliminate ≥ this fraction of B
    shift_detected: bool = False        # external flag for distribution shift

    @property
    def size(self) -> int:
        return len(self.beliefs)

    @property
    def uncertainty(self) -> float:
        """U(B_t) = log₂|B_t|  (0 when |B|=1)."""
        if self.size <= 1:
            return 0.0
        return math.log2(self.size)

    def update(self, evidence: Dict[str, Any]) -> UpdateResult:
        """Conservative update: B_{t+1} = B_t ∩ C(e_t) with abstention checks.

        Returns an UpdateResult describing the outcome.
        """
        before = self.size
        c_e = credible_region(evidence)

        # Guard 1: intersection would be empty → abstain
        intersection = self.beliefs & c_e
        if not intersection:
            result = UpdateResult(
                outcome=UpdateOutcome.ABSTAINED_EMPTY,
                belief_before=before,
                belief_after=before,
                evidence_set_size=len(c_e),
                abstained=True,
            )
            self.history.append({"outcome": result.outcome.value, "size": before})
            return result

        # Guard 2: shift detected — don't commit
        if self.shift_detected:
            result = UpdateResult(
                outcome=UpdateOutcome.ABSTAINED_SHIFT,
                belief_before=before,
                belief_after=before,
                evidence_set_size=len(c_e),
                abstained=True,
            )
            self.history.append({"outcome": result.outcome.value, "size": before})
            return result

        # Guard 3: low informativeness — C(e) doesn't eliminate enough
        eliminated_fraction = 1.0 - len(intersection) / max(before, 1)
        if eliminated_fraction < self.min_informativeness and len(intersection) == before:
            result = UpdateResult(
                outcome=UpdateOutcome.ABSTAINED_LOW_INFO,
                belief_before=before,
                belief_after=before,
                evidence_set_size=len(c_e),
                abstained=True,
            )
            self.history.append({"outcome": result.outcome.value, "size": before})
            return result

        # Commit: contract
        self.beliefs = intersection
        after = self.size
        outcome = UpdateOutcome.CONTRACTED if after < before else UpdateOutcome.NO_CHANGE

        result = UpdateResult(
            outcome=outcome,
            belief_before=before,
            belief_after=after,
            evidence_set_size=len(c_e),
        )
        self.history.append({"outcome": result.outcome.value, "size": after})
        return result

    def reset(self) -> None:
        """Reset to full ignorance."""
        self.beliefs = set(THETA_FULL)
        self.history.clear()
        self.shift_detected = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "product_uid": self.product_uid,
            "size": self.size,
            "uncertainty": round(self.uncertainty, 4),
            "history": list(self.history),
        }


# ── Twin-event integration ───────────────────────────────────────────
def evidence_from_twin_event(event: TwinEvent) -> Optional[Dict[str, Any]]:
    """Extract an evidence dict from a twin event, if applicable.

    Returns None if the event carries no constraint on latent conditions.
    """
    payload = event.payload

    # Observation events carry 'observed' dict
    if event.event_type == TwinEventType.OBSERVATION:
        obs = payload.get("observed", {})
        # Filter to latent-condition attributes only
        latent_attrs = {"stripped_screw", "stuck_adhesive",
                        "missing_component", "battery_risk"}
        evidence = {k: v for k, v in obs.items() if k in latent_attrs}
        return evidence if evidence else None

    # Exception events reveal specific conditions
    if event.event_type == TwinEventType.EXCEPTION:
        exc = payload.get("event", "")
        if "stripped_screw" in exc:
            return {"stripped_screw": True}
        if "stuck_adhesive" in exc:
            return {"stuck_adhesive": True}
        if "battery_risk" in exc:
            return {"battery_risk": True}
        if "missing_component" in exc:
            return {"missing_component": True}

    return None


def create_belief_update_event(
    product_uid: int,
    result: UpdateResult,
    event_time: float,
    belief_set_size: int,
) -> TwinEvent:
    """Create a BELIEF_UPDATE twin event recording a learning step."""
    return TwinEvent(
        event_time=event_time,
        event_type=TwinEventType.BELIEF_UPDATE,
        actor=ActorType.TWIN_INFERENCE,
        payload={
            "product": product_uid,
            "outcome": result.outcome.value,
            "belief_before": result.belief_before,
            "belief_after": result.belief_after,
            "evidence_set_size": result.evidence_set_size,
            "abstained": result.abstained,
            "updates": {
                "belief_size": {
                    "value": belief_set_size,
                    "confidence": 1.0 - (belief_set_size / 16.0),
                },
            },
        },
    )
