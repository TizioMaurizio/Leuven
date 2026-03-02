"""WP3 tests — conservative learning-to-update & learning-to-ask.

Covers:
  - Full hypothesis space Θ and credible region computation
  - Monotonic belief contraction (B_{t+1} ⊆ B_t)
  - Abstention under shift, low info, and empty intersection
  - Feasibility oracle (robot blocked by stripped_screw, etc.)
  - Robust vs maybe feasibility classification
  - VoI computation and ask policy
  - Confidence gate: commit / ask / escalate
  - BeliefTracker orchestration with twin events
  - Non-expansion: learning never adds events outside Γ_S
"""

from __future__ import annotations

import math
import unittest

from demanuf.des.model import (
    CellState,
    EventType,
    LatentCondition,
    Product,
    ProductPhase,
    Station,
    StationStatus,
)
from demanuf.des.supervisor import Supervisor
from demanuf.twin.schema import (
    ActorType,
    TwinEvent,
    TwinEventType,
)
from demanuf.twin.store import EventStore
from demanuf.learning.belief import (
    THETA_FULL,
    BeliefSet,
    UpdateOutcome,
    credible_region,
    evidence_from_twin_event,
    create_belief_update_event,
)
from demanuf.learning.feasibility import (
    classify_actions,
    is_feasible,
    maybe_feasible,
    robust_feasible,
)
from demanuf.learning.ask import (
    AskDecision,
    AskPolicy,
    CommitmentDecision,
    QUERY_EVENTS,
    _expected_reduction,
    confidence_gate,
)
from demanuf.learning.tracker import BeliefTracker, TrackerMetrics


# ── Helpers ───────────────────────────────────────────────────────────
def _make_cell_state() -> CellState:
    """Build a cell state with all stations idle."""
    from demanuf.config import STATION_NAMES
    stations = {
        name: Station(name=name, status=StationStatus.IDLE)
        for name in STATION_NAMES
    }
    return CellState(stations=stations)


def _make_inspected_product(uid: int = 0, **observed) -> Product:
    """Create a product that has been inspected with given observations."""
    p = Product(uid=uid, phase=ProductPhase.WAITING, inspected=True)
    p.observed = observed
    return p


# ── Test classes ──────────────────────────────────────────────────────

class TestHypothesisSpace(unittest.TestCase):
    """Θ should have exactly 16 elements (2^4 booleans)."""

    def test_full_space_size(self):
        self.assertEqual(len(THETA_FULL), 16)

    def test_all_unique(self):
        as_tuples = {
            (t.stripped_screw, t.stuck_adhesive, t.missing_component, t.battery_risk)
            for t in THETA_FULL
        }
        self.assertEqual(len(as_tuples), 16)


class TestCredibleRegion(unittest.TestCase):

    def test_no_evidence_returns_full_theta(self):
        region = credible_region({})
        self.assertEqual(len(region), 16)

    def test_single_positive_halves(self):
        region = credible_region({"battery_risk": True})
        # 8 hypotheses where battery_risk=True
        self.assertEqual(len(region), 8)
        for theta in region:
            self.assertTrue(theta.battery_risk)

    def test_two_constraints_quarters(self):
        region = credible_region({"battery_risk": True, "stripped_screw": False})
        self.assertEqual(len(region), 4)
        for theta in region:
            self.assertTrue(theta.battery_risk)
            self.assertFalse(theta.stripped_screw)

    def test_full_constraint_singleton(self):
        region = credible_region({
            "stripped_screw": True,
            "stuck_adhesive": False,
            "missing_component": False,
            "battery_risk": True,
        })
        self.assertEqual(len(region), 1)


class TestBeliefSet(unittest.TestCase):

    def test_initial_size(self):
        bs = BeliefSet(product_uid=1)
        self.assertEqual(bs.size, 16)
        self.assertAlmostEqual(bs.uncertainty, 4.0)  # log2(16) = 4

    def test_contraction(self):
        bs = BeliefSet(product_uid=1)
        result = bs.update({"battery_risk": True})
        self.assertEqual(result.outcome, UpdateOutcome.CONTRACTED)
        self.assertEqual(bs.size, 8)
        self.assertTrue(result.belief_before == 16)
        self.assertTrue(result.belief_after == 8)

    def test_monotonic_contraction(self):
        """B_{t+1} ⊆ B_t — Proposition 1."""
        bs = BeliefSet(product_uid=1)
        prev = bs.size
        for attr in ["battery_risk", "stripped_screw", "stuck_adhesive"]:
            bs.update({attr: True})
            self.assertLessEqual(bs.size, prev)
            prev = bs.size

    def test_uncertainty_non_increasing(self):
        """U(B_t) non-increasing — monotone property."""
        bs = BeliefSet(product_uid=1)
        prev_u = bs.uncertainty
        for attr, val in [("battery_risk", True), ("stripped_screw", False)]:
            bs.update({attr: val})
            self.assertLessEqual(bs.uncertainty, prev_u)
            prev_u = bs.uncertainty

    def test_abstain_empty_intersection(self):
        """If B_t ∩ C(e) = ∅ → abstain."""
        bs = BeliefSet(product_uid=1)
        # First constrain to battery_risk=True
        bs.update({"battery_risk": True})
        # Now try contradictory evidence
        result = bs.update({"battery_risk": False})
        self.assertEqual(result.outcome, UpdateOutcome.ABSTAINED_EMPTY)
        self.assertTrue(result.abstained)
        # Size should not change
        self.assertEqual(bs.size, 8)

    def test_abstain_shift_detected(self):
        bs = BeliefSet(product_uid=1)
        bs.shift_detected = True
        result = bs.update({"battery_risk": True})
        self.assertEqual(result.outcome, UpdateOutcome.ABSTAINED_SHIFT)
        self.assertTrue(result.abstained)
        self.assertEqual(bs.size, 16)  # no change

    def test_abstain_low_informativeness(self):
        """If C(e) ⊇ B_t (no elimination), abstain."""
        bs = BeliefSet(product_uid=1)
        # Empty evidence → C(e) = Θ → no elimination
        result = bs.update({})
        self.assertEqual(result.outcome, UpdateOutcome.ABSTAINED_LOW_INFO)
        self.assertEqual(bs.size, 16)

    def test_reset(self):
        bs = BeliefSet(product_uid=1)
        bs.update({"battery_risk": True})
        bs.reset()
        self.assertEqual(bs.size, 16)


class TestFeasibility(unittest.TestCase):

    def test_robot_blocked_by_stripped_screw(self):
        latent = LatentCondition(stripped_screw=True)
        self.assertFalse(is_feasible(EventType.START_ROBOT_DISASSEMBLY, latent))

    def test_robot_blocked_by_adhesive(self):
        latent = LatentCondition(stuck_adhesive=True)
        self.assertFalse(is_feasible(EventType.START_ROBOT_DISASSEMBLY, latent))

    def test_robot_ok_clean(self):
        latent = LatentCondition()
        self.assertTrue(is_feasible(EventType.START_ROBOT_DISASSEMBLY, latent))

    def test_manual_handles_stripped_screw(self):
        latent = LatentCondition(stripped_screw=True)
        self.assertTrue(is_feasible(EventType.START_MANUAL_DISASSEMBLY, latent))

    def test_manual_blocked_by_missing(self):
        latent = LatentCondition(missing_component=True)
        self.assertFalse(is_feasible(EventType.START_MANUAL_DISASSEMBLY, latent))

    def test_hazard_always_feasible(self):
        for ss in (False, True):
            for sa in (False, True):
                latent = LatentCondition(stripped_screw=ss, stuck_adhesive=sa, battery_risk=True)
                self.assertTrue(is_feasible(EventType.START_HAZARD_HANDLING, latent))

    def test_robust_feasible_full_belief(self):
        """With full Θ, robot is NOT robust-feasible (some θ block it)."""
        self.assertFalse(robust_feasible(EventType.START_ROBOT_DISASSEMBLY, set(THETA_FULL)))

    def test_robust_feasible_clean_subset(self):
        """If belief contains only clean θ, robot IS robust-feasible."""
        clean = {LatentCondition()}
        self.assertTrue(robust_feasible(EventType.START_ROBOT_DISASSEMBLY, clean))

    def test_maybe_feasible_full(self):
        """Some θ in Θ allow robot → maybe-feasible."""
        self.assertTrue(maybe_feasible(EventType.START_ROBOT_DISASSEMBLY, set(THETA_FULL)))

    def test_classify(self):
        clean = {LatentCondition()}
        actions = [EventType.START_ROBOT_DISASSEMBLY, EventType.START_MANUAL_DISASSEMBLY]
        result = classify_actions(actions, clean)
        self.assertIn(EventType.START_ROBOT_DISASSEMBLY, result["robust"])
        self.assertIn(EventType.START_MANUAL_DISASSEMBLY, result["robust"])


class TestExpectedReduction(unittest.TestCase):

    def test_full_belief_high_reduction(self):
        bs = BeliefSet(product_uid=1)
        delta = _expected_reduction(EventType.START_INSPECTION, bs)
        self.assertGreater(delta, 0.0)

    def test_singleton_no_reduction(self):
        bs = BeliefSet(product_uid=1)
        bs.beliefs = {LatentCondition()}
        delta = _expected_reduction(EventType.START_INSPECTION, bs)
        self.assertEqual(delta, 0.0)


class TestAskPolicy(unittest.TestCase):

    def setUp(self):
        self.supervisor = Supervisor()
        self.policy = AskPolicy()
        self.state = _make_cell_state()

    def test_ask_pre_inspection(self):
        """Product waiting before inspection → ask selects START_INSPECTION."""
        product = Product(uid=0, phase=ProductPhase.WAITING, inspected=False)
        self.state.products[0] = product
        belief = BeliefSet(product_uid=0)
        decision = self.policy.ask(belief, product, self.state, self.supervisor)
        self.assertFalse(decision.escalate)
        self.assertIn(decision.action, QUERY_EVENTS)

    def test_ask_resolved_no_action(self):
        """Belief already singleton → no ask needed."""
        product = Product(uid=0, phase=ProductPhase.WAITING, inspected=False)
        self.state.products[0] = product
        belief = BeliefSet(product_uid=0)
        belief.beliefs = {LatentCondition()}
        decision = self.policy.ask(belief, product, self.state, self.supervisor)
        self.assertFalse(decision.escalate)
        self.assertEqual(decision.reason, "belief_resolved")

    def test_ask_max_inspections_escalate(self):
        """Hit inspection cap → escalate."""
        product = Product(uid=0, phase=ProductPhase.WAITING, inspected=False)
        product.inspection_count = 5
        self.state.products[0] = product
        belief = BeliefSet(product_uid=0)
        decision = self.policy.ask(belief, product, self.state, self.supervisor)
        self.assertTrue(decision.escalate)


class TestConfidenceGate(unittest.TestCase):

    def setUp(self):
        self.supervisor = Supervisor()
        self.ask_policy = AskPolicy()
        self.state = _make_cell_state()

    def test_robust_commit(self):
        """Clean belief → robot robust-feasible → commit."""
        product = _make_inspected_product(uid=0)
        self.state.products[0] = product
        belief = BeliefSet(product_uid=0)
        belief.beliefs = {LatentCondition()}  # only clean
        decision = confidence_gate(
            belief, product, self.state, self.supervisor, self.ask_policy,
        )
        self.assertEqual(decision.kind, "robust")
        self.assertIsNotNone(decision.action)

    def test_ambiguous_triggers_ask(self):
        """Full belief → no robust-feasible → ask."""
        product = _make_inspected_product(uid=0)
        self.state.products[0] = product
        belief = BeliefSet(product_uid=0)  # full Θ
        decision = confidence_gate(
            belief, product, self.state, self.supervisor, self.ask_policy,
        )
        # Should trigger ask or escalate (depends on enabled set)
        self.assertIn(decision.kind, ("ask", "escalate"))

    def test_no_feasible_escalates(self):
        """All belief hypotheses block everything → escalate."""
        product = _make_inspected_product(uid=0)
        self.state.products[0] = product
        # Belief: only missing_component=True hypotheses
        belief = BeliefSet(product_uid=0)
        belief.beliefs = {
            LatentCondition(missing_component=True),
        }
        decision = confidence_gate(
            belief, product, self.state, self.supervisor, self.ask_policy,
        )
        self.assertEqual(decision.kind, "escalate")


class TestBeliefTracker(unittest.TestCase):

    def test_process_observation_event(self):
        """Tracker extracts evidence from OBSERVATION event and contracts belief."""
        store = EventStore()
        tracker = BeliefTracker(store=store)
        event = TwinEvent(
            event_type=TwinEventType.OBSERVATION,
            actor=ActorType.SENSOR,
            event_time=10.0,
            payload={
                "product": 1,
                "event": "finish_inspection",
                "observed": {"battery_risk": True, "stripped_screw": False},
            },
        )
        result = tracker.process_event(event)
        self.assertIsNotNone(result)
        belief = tracker.get_belief(1)
        self.assertLess(belief.size, 16)
        # All remaining θ must have battery_risk=True, stripped_screw=False
        for theta in belief.beliefs:
            self.assertTrue(theta.battery_risk)
            self.assertFalse(theta.stripped_screw)

    def test_process_exception_event(self):
        """Exception reveals a condition."""
        tracker = BeliefTracker()
        event = TwinEvent(
            event_type=TwinEventType.EXCEPTION,
            event_time=20.0,
            payload={"product": 2, "event": "exception_stripped_screw"},
        )
        result = tracker.process_event(event)
        self.assertIsNotNone(result)
        belief = tracker.get_belief(2)
        for theta in belief.beliefs:
            self.assertTrue(theta.stripped_screw)

    def test_metrics_monotonic(self):
        """Belief size trajectory must be monotonically non-increasing."""
        tracker = BeliefTracker()
        events = [
            TwinEvent(
                event_type=TwinEventType.OBSERVATION,
                event_time=1.0,
                payload={"product": 0, "observed": {"battery_risk": True}},
            ),
            TwinEvent(
                event_type=TwinEventType.OBSERVATION,
                event_time=2.0,
                payload={"product": 0, "observed": {"stripped_screw": False}},
            ),
        ]
        for e in events:
            tracker.process_event(e)
        self.assertTrue(tracker.metrics._is_monotonic())

    def test_decide_integration(self):
        """Tracker.decide routes through confidence gate."""
        state = _make_cell_state()
        product = _make_inspected_product(uid=5)
        state.products[5] = product
        tracker = BeliefTracker()
        decision = tracker.decide(product, state)
        self.assertIn(decision.kind, ("robust", "ask", "escalate"))

    def test_remove_product(self):
        tracker = BeliefTracker()
        tracker.get_belief(10)
        self.assertIn(10, tracker._beliefs)
        tracker.remove_product(10)
        self.assertNotIn(10, tracker._beliefs)


class TestNonExpansion(unittest.TestCase):
    """Theorem 1: learning never proposes events outside Γ_S."""

    def test_ask_within_enabled(self):
        """Ask policy only returns events from supervisor enabled set."""
        supervisor = Supervisor()
        state = _make_cell_state()
        product = Product(uid=0, phase=ProductPhase.WAITING, inspected=False)
        state.products[0] = product
        belief = BeliefSet(product_uid=0)
        policy = AskPolicy()
        decision = policy.ask(belief, product, state, supervisor)
        if decision.action is not None:
            enabled = supervisor.enabled_set(product, state)
            self.assertIn(decision.action, enabled)

    def test_confidence_gate_within_enabled(self):
        """Confidence gate only returns actions from supervisor."""
        supervisor = Supervisor()
        state = _make_cell_state()
        product = _make_inspected_product(uid=0)
        state.products[0] = product
        belief = BeliefSet(product_uid=0)
        belief.beliefs = {LatentCondition()}
        decision = confidence_gate(
            belief, product, state, supervisor, AskPolicy(),
        )
        if decision.action is not None:
            enabled = supervisor.enabled_set(product, state)
            self.assertIn(decision.action, enabled)


class TestEvidenceExtraction(unittest.TestCase):

    def test_observation_extracts(self):
        event = TwinEvent(
            event_type=TwinEventType.OBSERVATION,
            payload={"product": 1, "observed": {"battery_risk": True, "foo": "bar"}},
        )
        ev = evidence_from_twin_event(event)
        self.assertEqual(ev, {"battery_risk": True})

    def test_exception_extracts(self):
        event = TwinEvent(
            event_type=TwinEventType.EXCEPTION,
            payload={"product": 1, "event": "exception_stuck_adhesive"},
        )
        ev = evidence_from_twin_event(event)
        self.assertEqual(ev, {"stuck_adhesive": True})

    def test_des_event_returns_none(self):
        event = TwinEvent(
            event_type=TwinEventType.DES_EVENT,
            payload={"product": 1, "event": "product_arrive"},
        )
        ev = evidence_from_twin_event(event)
        self.assertIsNone(ev)


if __name__ == "__main__":
    unittest.main()
