"""WP1 Tests — DES engine, model, supervisor, simulation determinism."""

import hashlib
import json
import os
import sys
import tempfile
import unittest

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from demanuf.des.engine import DESEngine, ScheduledEvent
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
from demanuf.des.simulation import SimulationRunner
from demanuf.des.scenarios import Scenario, generate_product_stream, NAMED_REGIMES
from demanuf.des.metrics import RunMetrics
from demanuf.config import UncertaintyRegime, REGIME_LOW, REGIME_HIGH
from demanuf.holons.baseline import BaselinePolicy


class TestDESEngine(unittest.TestCase):
    """Core engine tests."""

    def test_empty_step_returns_none(self):
        e = DESEngine()
        self.assertIsNone(e.step())

    def test_events_in_order(self):
        e = DESEngine()
        order = []
        e.schedule(3.0, lambda eng, ev: order.append(3))
        e.schedule(1.0, lambda eng, ev: order.append(1))
        e.schedule(2.0, lambda eng, ev: order.append(2))
        e.run()
        self.assertEqual(order, [1, 2, 3])

    def test_clock_advances(self):
        e = DESEngine()
        e.schedule(5.0, lambda eng, ev: None)
        e.run()
        self.assertAlmostEqual(e.now, 5.0)

    def test_run_until(self):
        e = DESEngine()
        e.schedule(1.0, lambda eng, ev: None)
        e.schedule(5.0, lambda eng, ev: None)
        e.schedule(10.0, lambda eng, ev: None)
        count = e.run(until=6.0)
        self.assertEqual(count, 2)
        self.assertAlmostEqual(e.now, 5.0)

    def test_run_max_steps(self):
        e = DESEngine()
        for i in range(100):
            e.schedule(float(i), lambda eng, ev: None)
        count = e.run(max_steps=10)
        self.assertEqual(count, 10)

    def test_deterministic_tie_breaking(self):
        """Events at same time should fire in insertion order."""
        e = DESEngine()
        order = []
        e.schedule(1.0, lambda eng, ev: order.append("a"))
        e.schedule(1.0, lambda eng, ev: order.append("b"))
        e.schedule(1.0, lambda eng, ev: order.append("c"))
        e.run()
        self.assertEqual(order, ["a", "b", "c"])


class TestModel(unittest.TestCase):
    """Product / Station / CellState tests."""

    def test_product_creation(self):
        import random
        state = CellState()
        rng = random.Random(42)
        regime = UncertaintyRegime()
        p = state.create_product(rng, regime, 0.0)
        self.assertEqual(p.uid, 0)
        self.assertFalse(p.inspected)
        self.assertEqual(p.phase, ProductPhase.WAITING)

    def test_station_availability(self):
        s = Station(name="test")
        self.assertTrue(s.is_available())
        s.status = StationStatus.BUSY
        self.assertFalse(s.is_available())

    def test_event_type_partitions(self):
        ctrl = EventType.controllable()
        unctrl = EventType.uncontrollable()
        self.assertEqual(len(ctrl & unctrl), 0, "Partitions must not overlap")
        self.assertEqual(len(ctrl) + len(unctrl), len(EventType))


class TestSupervisor(unittest.TestCase):
    """Supervisor enabled-set and gate tests."""

    def _make_state_with_product(self, **latent_kwargs):
        state = CellState()
        for name in ["intake", "inspection", "robot_disassembly",
                      "manual_disassembly", "hazard_handling", "output"]:
            state.stations[name] = Station(name=name)
        p = Product(uid=0, latent=LatentCondition(**latent_kwargs))
        state.products[0] = p
        return state, p

    def test_waiting_product_can_inspect(self):
        state, p = self._make_state_with_product()
        sup = Supervisor()
        enabled = sup.enabled_set(p, state)
        self.assertIn(EventType.START_INSPECTION, enabled)

    def test_battery_risk_forces_hazard_handling(self):
        """Product with observed battery risk must go to hazard handling."""
        state, p = self._make_state_with_product(battery_risk=True)
        p.inspected = True
        p.observed = {"battery_risk": True}
        p.phase = ProductPhase.WAITING
        sup = Supervisor()
        enabled = sup.enabled_set(p, state)
        self.assertIn(EventType.START_HAZARD_HANDLING, enabled)
        self.assertNotIn(EventType.START_ROBOT_DISASSEMBLY, enabled)
        self.assertNotIn(EventType.START_MANUAL_DISASSEMBLY, enabled)

    def test_stripped_screw_blocks_robot(self):
        """Robot disassembly blocked when stripped screw observed."""
        state, p = self._make_state_with_product(stripped_screw=True)
        p.inspected = True
        p.observed = {"stripped_screw": True, "battery_risk": False}
        p.phase = ProductPhase.WAITING
        sup = Supervisor()
        enabled = sup.enabled_set(p, state)
        self.assertNotIn(EventType.START_ROBOT_DISASSEMBLY, enabled)
        self.assertIn(EventType.START_MANUAL_DISASSEMBLY, enabled)

    def test_gate_intersection(self):
        state, p = self._make_state_with_product()
        sup = Supervisor()
        proposed = {EventType.START_INSPECTION, EventType.START_ROBOT_DISASSEMBLY}
        result = sup.gate(proposed, p, state)
        # Waiting product can only inspect
        self.assertIn(EventType.START_INSPECTION, result)

    def test_supervisor_never_allows_forbidden(self):
        """Supervisor must never include uncontrollable events."""
        state, p = self._make_state_with_product()
        sup = Supervisor()
        for phase in ProductPhase:
            p.phase = phase
            enabled = sup.enabled_set(p, state)
            for ev in enabled:
                self.assertIn(ev, EventType.controllable(),
                              f"Supervisor enabled uncontrollable event {ev} in phase {phase}")


class TestSimulationDeterminism(unittest.TestCase):
    """Same seed → identical event log."""

    def _run_and_hash(self, seed: int, steps: int = 50) -> str:
        runner = SimulationRunner(seed=seed, max_steps=steps, max_products=10)
        runner.run()
        log_str = json.dumps(runner.metrics.event_log, sort_keys=True)
        return hashlib.sha256(log_str.encode()).hexdigest()

    def test_deterministic_same_seed(self):
        h1 = self._run_and_hash(seed=1)
        h2 = self._run_and_hash(seed=1)
        self.assertEqual(h1, h2, "Same seed must produce identical event logs")

    def test_different_seeds_differ(self):
        h1 = self._run_and_hash(seed=1)
        h2 = self._run_and_hash(seed=2)
        self.assertNotEqual(h1, h2, "Different seeds should produce different logs")


class TestSimulationRuns(unittest.TestCase):
    """Simulation runs without crashing under various regimes."""

    def test_low_regime(self):
        runner = SimulationRunner(seed=10, regime=REGIME_LOW, max_steps=100, max_products=10)
        m = runner.run()
        self.assertGreater(len(m.event_log), 0)

    def test_medium_regime(self):
        runner = SimulationRunner(seed=10, max_steps=100, max_products=10)
        m = runner.run()
        self.assertGreater(len(m.event_log), 0)

    def test_high_regime(self):
        runner = SimulationRunner(seed=10, regime=REGIME_HIGH, max_steps=100, max_products=10)
        m = runner.run()
        self.assertGreater(len(m.event_log), 0)

    def test_write_results(self):
        runner = SimulationRunner(seed=42, max_steps=50, max_products=5)
        runner.run()
        with tempfile.TemporaryDirectory() as td:
            runner.write_results(td)
            self.assertTrue(os.path.exists(os.path.join(td, "events.jsonl")))
            self.assertTrue(os.path.exists(os.path.join(td, "metrics.json")))
            # Verify JSON parsability
            with open(os.path.join(td, "metrics.json")) as f:
                data = json.load(f)
            self.assertIn("products_completed", data)

    def test_zero_safety_violations_under_supervisor(self):
        """With supervisor active, there should be no safety violations."""
        runner = SimulationRunner(seed=42, max_steps=200, max_products=20)
        m = runner.run()
        self.assertEqual(m.safety_violations, 0)


class TestBaselinePolicy(unittest.TestCase):
    def test_policy_returns_from_enabled(self):
        policy = BaselinePolicy()
        state = CellState()
        p = Product(uid=0)
        state.products[0] = p
        enabled = frozenset({EventType.START_INSPECTION, EventType.ESCALATE})
        result = policy.decide(0, state, enabled)
        self.assertIn(result, enabled)


class TestGUIImport(unittest.TestCase):
    """Smoke test: GUI module imports without error."""

    def test_import_gui(self):
        # Just import — don't create a Tk window (would fail in headless CI)
        import demanuf.gui as gui_mod
        self.assertTrue(hasattr(gui_mod, "DemanufGUI"))
        self.assertTrue(hasattr(gui_mod, "main"))


if __name__ == "__main__":
    unittest.main()
