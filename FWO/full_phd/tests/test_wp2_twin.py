"""WP2 Tests — Event store, replay determinism, evidence queries, WP1 ingestion."""

import hashlib
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from demanuf.twin.schema import (
    TwinEvent,
    TwinEventType,
    ActorType,
    EvidenceRef,
    AttributeMeta,
    des_event_to_twin,
)
from demanuf.twin.store import EventStore
from demanuf.twin.replay import replay, replay_events, snapshot_hash
from demanuf.twin.state import TwinState, reducer, ProductBelief
from demanuf.twin.queries import latest_evidence, decision_trace, evidence_grounded_check
from demanuf.des.simulation import SimulationRunner


class TestTwinEventSchema(unittest.TestCase):
    def test_serialization_roundtrip(self):
        evt = TwinEvent(
            event_time=1.5,
            event_type=TwinEventType.OBSERVATION,
            actor=ActorType.SENSOR,
            payload={"product": 0, "observed": {"battery_risk": True}},
        )
        d = evt.as_dict()
        restored = TwinEvent.from_dict(d)
        self.assertEqual(restored.event_time, 1.5)
        self.assertEqual(restored.event_type, TwinEventType.OBSERVATION)
        self.assertEqual(restored.payload["observed"]["battery_risk"], True)

    def test_content_hash_deterministic(self):
        evt = TwinEvent(event_id="test123", event_time=1.0, payload={"x": 1})
        h1 = evt.content_hash()
        h2 = evt.content_hash()
        self.assertEqual(h1, h2)


class TestAttributeMeta(unittest.TestCase):
    def test_freshness(self):
        meta = AttributeMeta(value=True, confidence=0.9, event_time=10.0, validity_window=5.0)
        self.assertFalse(meta.is_stale(14.0))
        self.assertTrue(meta.is_stale(16.0))


class TestEventStore(unittest.TestCase):
    def test_append_assigns_seq_no(self):
        store = EventStore()
        e1 = store.append(TwinEvent(event_time=1.0))
        e2 = store.append(TwinEvent(event_time=2.0))
        self.assertEqual(e1.seq_no, 0)
        self.assertEqual(e2.seq_no, 1)

    def test_hash_chain(self):
        store = EventStore()
        e1 = store.append(TwinEvent(event_time=1.0))
        e2 = store.append(TwinEvent(event_time=2.0))
        self.assertNotEqual(e2.hash_prev, "")
        self.assertEqual(e2.hash_prev, e1.content_hash())

    def test_jsonl_roundtrip(self):
        store = EventStore()
        store.append(TwinEvent(event_time=1.0, payload={"a": 1}))
        store.append(TwinEvent(event_time=2.0, payload={"b": 2}))
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
            path = f.name
        try:
            store.write_jsonl(path)
            loaded = EventStore.load_jsonl(path)
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded.all_events[0].payload["a"], 1)
        finally:
            os.unlink(path)

    def test_events_up_to(self):
        store = EventStore()
        store.append(TwinEvent(event_time=1.0))
        store.append(TwinEvent(event_time=5.0))
        store.append(TwinEvent(event_time=10.0))
        subset = store.events_up_to(6.0)
        self.assertEqual(len(subset), 2)


class TestReplayDeterminism(unittest.TestCase):
    """R5: same log → same materialised state."""

    def _make_store(self):
        store = EventStore()
        store.append(TwinEvent(
            event_time=1.0,
            event_type=TwinEventType.DES_EVENT,
            payload={"event": "product_arrive", "product": 0},
        ))
        store.append(TwinEvent(
            event_time=2.0,
            event_type=TwinEventType.OBSERVATION,
            payload={"event": "finish_inspection", "product": 0,
                     "observed": {"battery_risk": True, "stripped_screw": False}},
        ))
        store.append(TwinEvent(
            event_time=5.0,
            event_type=TwinEventType.EXCEPTION,
            payload={"event": "exception_stripped_screw", "product": 0},
        ))
        return store

    def test_replay_yields_same_state(self):
        store = self._make_store()
        s1 = replay(store)
        s2 = replay(store)
        self.assertEqual(snapshot_hash(s1), snapshot_hash(s2))

    def test_replay_up_to_time(self):
        store = self._make_store()
        s_partial = replay(store, up_to_time=3.0)
        s_full = replay(store)
        self.assertEqual(s_partial.events_applied, 2)
        self.assertEqual(s_full.events_applied, 3)
        # Partial should not have the exception-revealed attribute
        pb_partial = s_partial.products.get(0)
        self.assertIsNotNone(pb_partial)
        # After exception, stripped_screw should be True with confidence 1.0
        pb_full = s_full.products.get(0)
        self.assertEqual(pb_full.attributes["stripped_screw"].value, True)
        self.assertEqual(pb_full.attributes["stripped_screw"].confidence, 1.0)

    def test_replay_up_to_seq(self):
        store = self._make_store()
        s = replay(store, up_to_seq=1)
        self.assertEqual(s.events_applied, 1)


class TestWP1Ingestion(unittest.TestCase):
    """WP1 event logs can be ingested into the twin store."""

    def test_ingest_des_log(self):
        runner = SimulationRunner(seed=42, max_steps=50, max_products=5)
        runner.run()
        des_log = runner.metrics.event_log

        store = EventStore()
        count = store.ingest_des_log(des_log)
        self.assertEqual(count, len(des_log))
        self.assertGreater(len(store), 0)

        # Replay should work
        state = replay(store)
        self.assertGreater(state.events_applied, 0)

    def test_ingest_from_file(self):
        runner = SimulationRunner(seed=42, max_steps=30, max_products=3)
        runner.run()
        with tempfile.TemporaryDirectory() as td:
            runner.write_results(td)
            events_path = os.path.join(td, "events.jsonl")
            store = EventStore.from_des_log_file(events_path)
            self.assertGreater(len(store), 0)

    def test_replay_determinism_on_wp1_log(self):
        """Same WP1 run → same twin state after ingestion + replay."""
        runner = SimulationRunner(seed=7, max_steps=80, max_products=10)
        runner.run()

        store1 = EventStore()
        store1.ingest_des_log(runner.metrics.event_log)
        s1 = replay(store1)

        store2 = EventStore()
        store2.ingest_des_log(runner.metrics.event_log)
        s2 = replay(store2)

        self.assertEqual(snapshot_hash(s1), snapshot_hash(s2))


class TestEvidenceQueries(unittest.TestCase):
    def _build_state(self):
        store = EventStore()
        store.append(TwinEvent(
            event_time=1.0,
            event_type=TwinEventType.DES_EVENT,
            payload={"event": "product_arrive", "product": 0},
        ))
        store.append(TwinEvent(
            event_time=2.0,
            event_type=TwinEventType.OBSERVATION,
            payload={"event": "finish_inspection", "product": 0,
                     "observed": {"battery_risk": True, "stripped_screw": False}},
        ))
        state = replay(store)
        return store, state

    def test_latest_evidence_fresh(self):
        store, state = self._build_state()
        meta = latest_evidence(state, 0, "battery_risk", current_time=3.0)
        self.assertIsNotNone(meta)
        self.assertEqual(meta.value, True)
        self.assertGreater(meta.confidence, 0.0)

    def test_latest_evidence_stale(self):
        store, state = self._build_state()
        # Default validity window is 60; so at time 100 it should be stale
        meta = latest_evidence(state, 0, "battery_risk", current_time=100.0)
        self.assertIsNone(meta)

    def test_latest_evidence_allow_stale(self):
        store, state = self._build_state()
        meta = latest_evidence(state, 0, "battery_risk", current_time=100.0, max_stale=True)
        self.assertIsNotNone(meta)

    def test_evidence_grounded_check(self):
        store, state = self._build_state()
        result = evidence_grounded_check(store, state, 0,
                                          ["battery_risk", "stripped_screw"], 3.0)
        self.assertTrue(result["grounded"])
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["stale"], [])

    def test_evidence_grounded_missing(self):
        store, state = self._build_state()
        result = evidence_grounded_check(store, state, 0,
                                          ["nonexistent_attr"], 3.0)
        self.assertFalse(result["grounded"])
        self.assertIn("nonexistent_attr", result["missing"])

    def test_decision_trace(self):
        store, state = self._build_state()
        # Trace from the observation event
        obs_event = store.all_events[1]
        trace = decision_trace(store, obs_event.event_id, state)
        self.assertGreater(len(trace), 0)


if __name__ == "__main__":
    unittest.main()
