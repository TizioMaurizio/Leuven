"""
sim/process.py – Control-flow logic implementing S0–S8.

``ProcessLogic`` is the state-machine that the ``Simulator`` dispatches
events to.  Each handler acquires / releases resources and schedules
the next event in the chain.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sim.core import EventType, Event
from sim.model import InstructionPackage

if TYPE_CHECKING:
    from sim.core import Simulator


class ProcessLogic:
    """Event-driven state machine for the SUDE laptop pilot."""

    # ── dispatcher ───────────────────────────────────────────────────────

    def on_event(self, sim: "Simulator", ev: Event) -> None:
        handler = _DISPATCH.get(ev.event_type)
        if handler is not None:
            handler(self, sim, ev)

    # ── S0 Arrival ───────────────────────────────────────────────────────

    def handle_arrival(self, sim: "Simulator", ev: Event) -> None:
        world = sim.world
        laptop = world.create_laptop(sim.now, sim.rng)

        # collect metric
        if sim.metrics:
            sim.metrics.record_arrival(sim.now)

        # schedule next arrival
        dt = world.dist["inter_arrival"](sim.rng)
        sim.schedule_in(dt, EventType.ARRIVAL, laptop_id=-1)

        # request camera for imaging (S1)
        self._request_imaging(sim, laptop.id)

    # ── S1 Imaging ───────────────────────────────────────────────────────

    def _request_imaging(self, sim: "Simulator", laptop_id: int) -> None:
        world = sim.world
        laptop = world.laptops[laptop_id]
        laptop.enter_state("S1_IMAGING_WAIT", sim.now)

        def on_camera_granted(lid: int) -> None:
            lp = world.laptops[lid]
            lp.enter_state("S1_IMAGING", sim.now)
            dt = world.dist["imaging_time"](sim.rng)
            sim.schedule_in(dt, EventType.IMAGING_DONE, lid)

        granted = world.resources["camera"].request(
            laptop_id, sim.now, on_camera_granted)
        # if not granted, callback fires later via release chain

    def handle_imaging_done(self, sim: "Simulator", ev: Event) -> None:
        world = sim.world
        laptop = world.laptops[ev.laptop_id]
        laptop.finish_state(sim.now)
        world.resources["camera"].release(ev.laptop_id, sim.now)
        self._serve_pending(sim, "camera")

        # proceed to S2 retrieval
        self._request_retrieval(sim, ev.laptop_id)

    # ── S2 Retrieval ─────────────────────────────────────────────────────

    def _request_retrieval(self, sim: "Simulator", laptop_id: int) -> None:
        world = sim.world
        laptop = world.laptops[laptop_id]
        laptop.enter_state("S2_RETRIEVAL_WAIT", sim.now)

        def on_retrieval_granted(lid: int) -> None:
            lp = world.laptops[lid]
            lp.enter_state("S2_RETRIEVAL", sim.now)
            dt = world.dist["retrieval_time"](sim.rng)
            sim.schedule_in(dt, EventType.RETRIEVAL_DONE, lid)

        world.resources["retrieval"].request(
            laptop_id, sim.now, on_retrieval_granted)

    def handle_retrieval_done(self, sim: "Simulator", ev: Event) -> None:
        world = sim.world
        laptop = world.laptops[ev.laptop_id]
        laptop.finish_state(sim.now)
        world.resources["retrieval"].release(ev.laptop_id, sim.now)
        self._serve_pending(sim, "retrieval")

        # Guard G1: recognised?
        recognized = world.recognizer.match(
            laptop.true_model_id, world.db, sim.rng)
        laptop.flags["recognized"] = recognized

        if sim.metrics:
            sim.metrics.record_retrieval(sim.now, recognized)

        if recognized:
            # S3 lookup
            self._start_lookup(sim, ev.laptop_id)
        else:
            # S6 path: manual + onboarding
            laptop.flags["new_model"] = True
            self._request_manual(sim, ev.laptop_id, new_model=True)

    # ── S3 Instruction lookup ────────────────────────────────────────────

    def _start_lookup(self, sim: "Simulator", laptop_id: int) -> None:
        world = sim.world
        laptop = world.laptops[laptop_id]
        laptop.enter_state("S3_LOOKUP", sim.now)
        dt = world.dist["lookup_time"](sim.rng)
        sim.schedule_in(dt, EventType.LOOKUP_DONE, laptop_id)

    def handle_lookup_done(self, sim: "Simulator", ev: Event) -> None:
        world = sim.world
        laptop = world.laptops[ev.laptop_id]
        laptop.finish_state(sim.now)

        # proceed to S4 automation
        self._request_automation(sim, ev.laptop_id)

    # ── S4 Automated fastener removal ────────────────────────────────────

    def _request_automation(self, sim: "Simulator", laptop_id: int) -> None:
        world = sim.world
        laptop = world.laptops[laptop_id]
        laptop.enter_state("S4_AUTOMATION_WAIT", sim.now)

        def on_robot_granted(lid: int) -> None:
            lp = world.laptops[lid]
            lp.enter_state("S4_AUTOMATION", sim.now)
            dist_key = (
                "automation_time_waterjet"
                if world.mode == "waterjet"
                else "automation_time_unscrew"
            )
            dt = world.dist[dist_key](sim.rng)
            sim.schedule_in(dt, EventType.AUTOMATION_DONE, lid)

        world.resources["robot"].request(
            laptop_id, sim.now, on_robot_granted)

    def handle_automation_done(self, sim: "Simulator", ev: Event) -> None:
        world = sim.world
        laptop = world.laptops[ev.laptop_id]
        laptop.finish_state(sim.now)
        world.resources["robot"].release(ev.laptop_id, sim.now)
        self._serve_pending(sim, "robot")

        # Guard G2: automation success?
        probs = world.cfg.get("probabilities", {})
        p_success = (
            probs.get("p_auto_success_waterjet", 0.85)
            if world.mode == "waterjet"
            else probs.get("p_auto_success_unscrew", 0.70)
        )
        success = sim.rng.random() < p_success
        laptop.flags["auto_success"] = success

        if sim.metrics:
            sim.metrics.record_automation(sim.now, success)

        if success:
            # S5 handover
            self._request_handover(sim, ev.laptop_id)
        else:
            # S7 manual fallback
            self._request_manual(sim, ev.laptop_id, new_model=False)

    # ── S5 Handover ──────────────────────────────────────────────────────

    def _request_handover(self, sim: "Simulator", laptop_id: int) -> None:
        world = sim.world
        laptop = world.laptops[laptop_id]
        laptop.enter_state("S5_HANDOVER_WAIT", sim.now)

        def on_operator_granted(lid: int) -> None:
            lp = world.laptops[lid]
            lp.enter_state("S5_HANDOVER", sim.now)
            dt = world.dist["handover_time"](sim.rng)
            sim.schedule_in(dt, EventType.HANDOVER_DONE, lid)

        world.resources["operator"].request(
            laptop_id, sim.now, on_operator_granted)

    def handle_handover_done(self, sim: "Simulator", ev: Event) -> None:
        world = sim.world
        laptop = world.laptops[ev.laptop_id]
        laptop.finish_state(sim.now)
        world.resources["operator"].release(ev.laptop_id, sim.now)
        self._serve_pending(sim, "operator")

        # S8 logging
        self._start_logging(sim, ev.laptop_id)

    # ── S6/S7 Manual path ────────────────────────────────────────────────

    def _request_manual(self, sim: "Simulator", laptop_id: int,
                        new_model: bool) -> None:
        world = sim.world
        laptop = world.laptops[laptop_id]
        state_label = "S6_MANUAL_NEW" if new_model else "S7_MANUAL_FALLBACK"
        laptop.enter_state(f"{state_label}_WAIT", sim.now)

        def on_operator_granted(lid: int) -> None:
            lp = world.laptops[lid]
            lp.enter_state(state_label, sim.now)
            dist_key = (
                "manual_new_model_time" if new_model
                else "manual_fallback_time"
            )
            dt = world.dist[dist_key](sim.rng)
            sim.schedule_in(dt, EventType.MANUAL_DONE, lid,
                            payload={"new_model": new_model})

        world.resources["operator"].request(
            laptop_id, sim.now, on_operator_granted)

    def handle_manual_done(self, sim: "Simulator", ev: Event) -> None:
        world = sim.world
        laptop = world.laptops[ev.laptop_id]
        laptop.finish_state(sim.now)
        world.resources["operator"].release(ev.laptop_id, sim.now)
        self._serve_pending(sim, "operator")

        new_model = ev.payload.get("new_model", False)
        if new_model:
            # S6 onboarding: register model in DB
            if not world.db.is_known(laptop.true_model_id):
                world.db.register(laptop.true_model_id, t=sim.now)
                laptop.flags["new_model_registered"] = True
                if sim.metrics:
                    sim.metrics.record_onboarding(sim.now, world.db.size())

        # S8 logging
        self._start_logging(sim, ev.laptop_id)

    # ── S8 Logging / learning ────────────────────────────────────────────

    def _start_logging(self, sim: "Simulator", laptop_id: int) -> None:
        world = sim.world
        laptop = world.laptops[laptop_id]
        laptop.enter_state("S8_LOGGING", sim.now)
        dt = world.dist["logging_time"](sim.rng)
        sim.schedule_in(dt, EventType.LOGGING_DONE, laptop_id)

    def handle_logging_done(self, sim: "Simulator", ev: Event) -> None:
        world = sim.world
        laptop = world.laptops[ev.laptop_id]
        laptop.finish_state(sim.now)
        laptop.t_departure = sim.now
        laptop.enter_state("DEPARTED", sim.now)
        laptop.finish_state(sim.now)

        if sim.metrics:
            sim.metrics.record_departure(sim.now, laptop)

    # ── Helpers ──────────────────────────────────────────────────────────

    def _serve_pending(self, sim: "Simulator", resource_name: str) -> None:
        """After releasing a resource, grant to next in queue."""
        res = sim.world.resources[resource_name]
        nxt = res.release(-1, sim.now)  # dummy release to check queue
        # Actually the release was already done; we use a lighter approach:
        # The release method already popped and granted the next request.
        # But the granted callback needs the sim context, so we handle
        # it properly by re-checking.
        # This is already handled inside Resource.release() above –
        # the on_granted callback fires synchronously.  Nothing extra needed
        # if the callback schedules the correct event.  However, the current
        # implementation only stores the callback – it doesn't call it
        # automatically on release.  Let's fix that here.
        pass  # callbacks are invoked inside Resource.release → handled above

    def _serve_pending_real(self, sim: "Simulator", resource_name: str) -> None:
        """Check if the resource has a pending request after a release."""
        # Not needed — Resource.release already pops the next request.
        # But the on_granted callback only receives laptop_id, not sim.
        # We need to trigger the callback.
        pass


# Ensure Resource.release triggers queued callbacks properly.
# We patch the release flow: after the main handler calls release(),
# if a ResourceRequest was returned, call its on_granted(laptop_id).
# This is done in each handle_*_done above — Resource.release returns
# the next request and we call its on_granted.  Let's refactor the
# handlers to do this properly.

# Actually, looking at the code flow:
# 1. Handler calls resource.release(laptop_id, now) → returns next_req
# 2. If next_req is not None, call next_req.on_granted(next_req.laptop_id)
# The on_granted callback schedules the next event.
# Let's update the handlers.

class _PatchedProcessLogic(ProcessLogic):
    """Patch release flow so queued requests are served."""

    def _release_and_serve(self, sim: "Simulator", resource_name: str,
                           laptop_id: int) -> None:
        res = sim.world.resources[resource_name]
        nxt = res.release(laptop_id, sim.now)
        if nxt is not None:
            nxt.on_granted(nxt.laptop_id)

    def handle_imaging_done(self, sim, ev):
        world = sim.world
        laptop = world.laptops[ev.laptop_id]
        laptop.finish_state(sim.now)
        self._release_and_serve(sim, "camera", ev.laptop_id)
        self._request_retrieval(sim, ev.laptop_id)

    def handle_retrieval_done(self, sim, ev):
        world = sim.world
        laptop = world.laptops[ev.laptop_id]
        laptop.finish_state(sim.now)
        self._release_and_serve(sim, "retrieval", ev.laptop_id)

        recognized = world.recognizer.match(
            laptop.true_model_id, world.db, sim.rng)
        laptop.flags["recognized"] = recognized
        if sim.metrics:
            sim.metrics.record_retrieval(sim.now, recognized)

        if recognized:
            self._start_lookup(sim, ev.laptop_id)
        else:
            laptop.flags["new_model"] = True
            self._request_manual(sim, ev.laptop_id, new_model=True)

    def handle_automation_done(self, sim, ev):
        world = sim.world
        laptop = world.laptops[ev.laptop_id]
        laptop.finish_state(sim.now)
        self._release_and_serve(sim, "robot", ev.laptop_id)

        probs = world.cfg.get("probabilities", {})
        p_success = (
            probs.get("p_auto_success_waterjet", 0.85)
            if world.mode == "waterjet"
            else probs.get("p_auto_success_unscrew", 0.70)
        )
        success = sim.rng.random() < p_success
        laptop.flags["auto_success"] = success
        if sim.metrics:
            sim.metrics.record_automation(sim.now, success)

        if success:
            self._request_handover(sim, ev.laptop_id)
        else:
            self._request_manual(sim, ev.laptop_id, new_model=False)

    def handle_handover_done(self, sim, ev):
        world = sim.world
        laptop = world.laptops[ev.laptop_id]
        laptop.finish_state(sim.now)
        self._release_and_serve(sim, "operator", ev.laptop_id)
        self._start_logging(sim, ev.laptop_id)

    def handle_manual_done(self, sim, ev):
        world = sim.world
        laptop = world.laptops[ev.laptop_id]
        laptop.finish_state(sim.now)
        self._release_and_serve(sim, "operator", ev.laptop_id)

        new_model = ev.payload.get("new_model", False)
        if new_model:
            if not world.db.is_known(laptop.true_model_id):
                world.db.register(laptop.true_model_id, t=sim.now)
                laptop.flags["new_model_registered"] = True
                if sim.metrics:
                    sim.metrics.record_onboarding(sim.now, world.db.size())
        self._start_logging(sim, ev.laptop_id)


# ── dispatch table ───────────────────────────────────────────────────────

_DISPATCH = {
    EventType.ARRIVAL:         ProcessLogic.handle_arrival,
    EventType.IMAGING_DONE:    _PatchedProcessLogic.handle_imaging_done,
    EventType.RETRIEVAL_DONE:  _PatchedProcessLogic.handle_retrieval_done,
    EventType.LOOKUP_DONE:     ProcessLogic.handle_lookup_done,
    EventType.AUTOMATION_DONE: _PatchedProcessLogic.handle_automation_done,
    EventType.HANDOVER_DONE:   _PatchedProcessLogic.handle_handover_done,
    EventType.MANUAL_DONE:     _PatchedProcessLogic.handle_manual_done,
    EventType.LOGGING_DONE:    ProcessLogic.handle_logging_done,
}


def create_process_logic() -> _PatchedProcessLogic:
    return _PatchedProcessLogic()
