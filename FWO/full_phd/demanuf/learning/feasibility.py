"""Feasibility oracle — F(cell_state, action, latent_condition) → bool.

Encodes which controllable actions are physically feasible given
a specific latent-condition hypothesis θ (PAPER_3 §4.3).

The feasibility function is deliberately *separate* from the supervisor's
enabled set Γ_S, which encodes safety / nonblocking constraints.
Feasibility captures *whether the physical world allows the action to succeed*.
"""

from __future__ import annotations

from typing import Dict

from ..des.model import EventType, LatentCondition, Product


def is_feasible(action: EventType, latent: LatentCondition) -> bool:
    """Return True iff *action* can physically succeed under *latent*.

    Domain rules (from PAPER_3 §4.3 & PAPER_1 §III-B):
    - Robot disassembly infeasible if stripped_screw (tool cannot grip)
    - Robot disassembly infeasible if stuck_adhesive (non-destructive removal impossible)
    - Start/finish disassembly infeasible if missing_component (nothing to remove)
    - Hazard handling required (and always feasible) if battery_risk
    - Manual disassembly can handle stripped_screw / adhesive (human adaptive)
    - Manual disassembly still infeasible if component is missing
    """

    if action in (EventType.START_ROBOT_DISASSEMBLY,
                  EventType.FINISH_ROBOT_DISASSEMBLY):
        if latent.stripped_screw:
            return False
        if latent.stuck_adhesive:
            return False
        if latent.missing_component:
            return False
        return True

    if action in (EventType.START_MANUAL_DISASSEMBLY,
                  EventType.FINISH_MANUAL_DISASSEMBLY):
        if latent.missing_component:
            return False
        return True

    if action in (EventType.START_HAZARD_HANDLING,
                  EventType.FINISH_HAZARD_HANDLING):
        # Always physically feasible (handler trained for battery risk)
        return True

    # All other events are not feasibility-constrained at the physical layer
    return True


def robust_feasible(action: EventType, belief_set: set) -> bool:
    """∀θ ∈ B_t : F(x, σ, θ) = 1  →  guaranteed success.

    *belief_set* is a set of LatentCondition instances.
    """
    if not belief_set:
        return False
    return all(is_feasible(action, theta) for theta in belief_set)


def maybe_feasible(action: EventType, belief_set: set) -> bool:
    """∃θ ∈ B_t : F(x, σ, θ) = 1  →  possible success."""
    if not belief_set:
        return False
    return any(is_feasible(action, theta) for theta in belief_set)


def classify_actions(
    actions, belief_set: set
) -> Dict[str, list]:
    """Classify a set of actions into robust / maybe / infeasible.

    Returns dict with keys "robust", "maybe", "infeasible".
    """
    result: Dict[str, list] = {"robust": [], "maybe": [], "infeasible": []}
    for a in actions:
        if robust_feasible(a, belief_set):
            result["robust"].append(a)
        elif maybe_feasible(a, belief_set):
            result["maybe"].append(a)
        else:
            result["infeasible"].append(a)
    return result
