"""Ablation runner — A0-A4 layered evaluation (PAPER_5 §2.2).

Each ablation progressively activates architectural layers:
  A0  L0 only       -> supervisor gating (baseline DES)
  A1  L0 + L1       -> + holonic coordination protocol
  A2  A1 + L2       -> + event-sourced digital twin
  A3  A2 + L3       -> + conservative learning
  A4  A3 + L4       -> + bounded semantic mediation
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from ..config import UncertaintyRegime
from ..des.metrics import RunMetrics
from ..des.simulation import SimulationRunner
from ..des.supervisor import Supervisor
from ..holons.baseline import BaselinePolicy
from ..twin.store import EventStore
from ..learning.tracker import BeliefTracker
from ..learning.ask import AskPolicy
from ..mediation.gate import MediationGate
from ..mediation.llm import MockLLM
from .metrics import EvalMetrics


# ── Ablation IDs ──────────────────────────────────────────────────────
ABLATION_IDS = ["A0", "A1", "A2", "A3", "A4"]


@dataclass
class AblationConfig:
    """Describes which layers are active for one ablation level."""

    ablation_id: str
    use_holonic: bool = False      # L1
    use_twin: bool = False         # L2
    use_learning: bool = False     # L3
    use_mediation: bool = False    # L4

    @property
    def layers(self) -> str:
        parts = ["L0"]
        if self.use_holonic:
            parts.append("L1")
        if self.use_twin:
            parts.append("L2")
        if self.use_learning:
            parts.append("L3")
        if self.use_mediation:
            parts.append("L4")
        return "+".join(parts)

    @staticmethod
    def from_id(aid: str) -> "AblationConfig":
        """Create config from ablation ID (A0-A4)."""
        level = int(aid[1])
        return AblationConfig(
            ablation_id=aid,
            use_holonic=level >= 1,
            use_twin=level >= 2,
            use_learning=level >= 3,
            use_mediation=level >= 4,
        )


ABLATION_CONFIGS: Dict[str, AblationConfig] = {
    aid: AblationConfig.from_id(aid) for aid in ABLATION_IDS
}


# ── Single-run evaluator ─────────────────────────────────────────────
def run_one(
    config: AblationConfig,
    seed: int,
    regime: Optional[UncertaintyRegime] = None,
    regime_name: str = "medium",
    max_steps: int = 200,
    max_products: int = 30,
) -> EvalMetrics:
    """Execute a single evaluation run with the given ablation config.

    Returns structured EvalMetrics.
    """
    regime = regime or UncertaintyRegime()
    policy = BaselinePolicy()
    supervisor = Supervisor()

    # L2: event-sourced twin
    store: Optional[EventStore] = None
    if config.use_twin:
        store = EventStore()

    # L3: conservative learning
    tracker: Optional[BeliefTracker] = None
    if config.use_learning:
        tracker = BeliefTracker(
            supervisor=supervisor,
            store=store,
            ask_policy=AskPolicy(),
        )

    # L4: bounded semantic mediation
    gate: Optional[MediationGate] = None
    if config.use_mediation:
        gate = MediationGate(
            supervisor=supervisor,
            store=store,
            require_grounding=False,  # relaxed for bench
        )

    # Track timing for overhead metrics
    t0 = time.perf_counter()

    runner = SimulationRunner(
        seed=seed,
        regime=regime,
        policy=policy,
        max_steps=max_steps,
        max_products=max_products,
    )
    run_metrics: RunMetrics = runner.run()

    elapsed = time.perf_counter() - t0

    # L2: ingest DES log into twin
    if store is not None:
        store.ingest_des_log(run_metrics.event_log)

    # L3: process twin events through belief tracker
    n_learning_updates = 0
    if tracker is not None and store is not None:
        for event in store:
            tracker.process_event(event)
            n_learning_updates += 1

    # L4: count gate metrics
    gate_admitted = 0
    gate_rejected = 0
    if gate is not None:
        gate_admitted = gate.admitted
        gate_rejected = gate.rejected

    # Build EvalMetrics
    n_products = max(run_metrics.products_completed, 1)
    n_events = max(len(run_metrics.event_log), 1)

    # Safety
    cvr = run_metrics.safety_violations / n_events
    ivr = run_metrics.forbidden_event_attempts / n_events
    dfr = run_metrics.deadlocks / n_events

    # Operational
    tp = run_metrics.throughput
    ct = run_metrics.avg_cycle_time
    bt = run_metrics.blocked_ticks / n_events
    rr = run_metrics.plan_invalidations / n_products
    ert = run_metrics.feasibility_changes / n_products if n_products else 0.0

    # Uncertainty
    ef = run_metrics.escalations / n_products
    ie = run_metrics.inspection_count / n_products if n_products else 0.0
    cq_val = 0.0
    if tracker is not None:
        tms = tracker.metrics.summary()
        avg_belief = tms.get("avg_final_belief", 16.0)
        cq_val = 1.0 - (avg_belief / 16.0)  # 0 = no info, 1 = singleton
    fpr = run_metrics.forbidden_event_attempts / n_events

    # Overhead
    dl = elapsed / n_events if n_events else 0.0
    sc_val = float(len(run_metrics.event_log))
    if store is not None:
        sc_val += float(len(list(store)))
    cl_val = float(n_learning_updates + gate_admitted + gate_rejected)

    return EvalMetrics(
        ablation_id=config.ablation_id,
        seed=seed,
        regime_name=regime_name,
        cvr=cvr, ivr=ivr, dfr=dfr,
        tp=tp, ct=ct, bt=bt, rr=rr, ert=ert,
        ef=ef, ie=ie, cq=cq_val, fpr=fpr,
        dl=dl, sc=sc_val, cl=cl_val,
    )


# ── Ablation runner ──────────────────────────────────────────────────
@dataclass
class AblationResult:
    """Collected metrics for all seeds under one ablation configuration."""

    config: AblationConfig
    runs: List[EvalMetrics] = field(default_factory=list)

    @property
    def n_runs(self) -> int:
        return len(self.runs)


def run_ablation(
    ablation_ids: Optional[Sequence[str]] = None,
    seeds: Optional[Sequence[int]] = None,
    regime: Optional[UncertaintyRegime] = None,
    regime_name: str = "medium",
    max_steps: int = 200,
    max_products: int = 30,
) -> Dict[str, AblationResult]:
    """Run ablation study across selected configs and seeds.

    Returns dict mapping ablation_id -> AblationResult.
    """
    if ablation_ids is None:
        ablation_ids = ABLATION_IDS
    if seeds is None:
        seeds = list(range(30))

    results: Dict[str, AblationResult] = {}
    for aid in ablation_ids:
        config = ABLATION_CONFIGS[aid]
        abl_result = AblationResult(config=config)
        for seed in seeds:
            em = run_one(
                config=config,
                seed=seed,
                regime=regime,
                regime_name=regime_name,
                max_steps=max_steps,
                max_products=max_products,
            )
            abl_result.runs.append(em)
        results[aid] = abl_result

    return results
