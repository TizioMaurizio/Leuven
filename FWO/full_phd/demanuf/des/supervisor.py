"""Supervisor — computes the enabled set Γ_S(x̂) of controllable events.

Implements the admissibility filter from PAPER_1 §IV:
  - Safety invariant: no cutting/disassembly before battery-safe state
  - Nonblocking: avoid known-deadlock actions
  - Decision gate: U_exec = U ∩ Γ_S
"""

from __future__ import annotations

from typing import Dict, FrozenSet, List, Optional, Set

from .model import CellState, EventType, Product, ProductPhase, StationStatus


class Supervisor:
    """Hard-coded supervisory controller.

    Returns the set of enabled controllable events for a given product,
    enforcing safety invariants and feasibility constraints.
    """

    def enabled_set(
        self, product: Product, state: CellState
    ) -> FrozenSet[EventType]:
        """Compute Γ_S(x̂) for *product* in *state*.

        Returns the frozenset of controllable events currently admissible.
        """
        enabled: Set[EventType] = set()

        phase = product.phase

        # ── Inspection in progress ────────────────────────────────
        if phase == ProductPhase.INSPECTION:
            # Can finish inspection (handled by sim clock)
            enabled.add(EventType.FINISH_INSPECTION)

        # ── After inspection — routing decisions ──────────────────
        elif phase == ProductPhase.WAITING and product.inspected:

            # Safety: if battery_risk observed and NOT cleared → must go to hazard handling
            if product.observed.get("battery_risk") and not product.hazard_cleared:
                if state.stations["hazard_handling"].is_available():
                    enabled.add(EventType.START_HAZARD_HANDLING)
                # Cannot proceed to disassembly until hazard cleared
            else:
                # Robot disassembly if station available + no blocking condition
                if state.stations["robot_disassembly"].is_available():
                    # Robot cannot handle stripped screw
                    if not product.observed.get("stripped_screw"):
                        enabled.add(EventType.START_ROBOT_DISASSEMBLY)
                # Manual disassembly always available if station idle
                if state.stations["manual_disassembly"].is_available():
                    enabled.add(EventType.START_MANUAL_DISASSEMBLY)
                # Re-inspect allowed
                enabled.add(EventType.REQUEST_INSPECTION)

            # Escalate always possible
            enabled.add(EventType.ESCALATE)

        # ── Robot disassembly ─────────────────────────────────────
        elif phase == ProductPhase.ROBOT_DISASSEMBLY:
            enabled.add(EventType.FINISH_ROBOT_DISASSEMBLY)

        # ── Manual disassembly ────────────────────────────────────
        elif phase == ProductPhase.MANUAL_DISASSEMBLY:
            enabled.add(EventType.FINISH_MANUAL_DISASSEMBLY)

        # ── Hazard handling ───────────────────────────────────────
        elif phase == ProductPhase.HAZARD_HANDLING:
            enabled.add(EventType.FINISH_HAZARD_HANDLING)

        # ── Pre-inspection waiting (intake) ───────────────────────
        elif phase == ProductPhase.WAITING and not product.inspected:
            if state.stations["inspection"].is_available():
                enabled.add(EventType.START_INSPECTION)
            enabled.add(EventType.REQUEST_INSPECTION)

        return frozenset(enabled)

    def is_safe(self, event: EventType, product: Product, state: CellState) -> bool:
        """Check whether *event* is in the enabled set for *product*."""
        return event in self.enabled_set(product, state)

    def gate(
        self, proposed: Set[EventType], product: Product, state: CellState
    ) -> FrozenSet[EventType]:
        """Admissibility gate: U_exec = proposed ∩ Γ_S."""
        return frozenset(proposed & self.enabled_set(product, state))
