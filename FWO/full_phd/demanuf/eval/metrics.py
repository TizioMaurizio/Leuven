"""Evaluation metrics — 4-category framework from PAPER_5 §2.4.

Categories:
  1. Safety / Correctness  (CVR, IVR, DFR)
  2. Operational Performance (TP, CT, BT, RR, ERT)
  3. Uncertainty Management (EF, IE, CQ, FPR)
  4. Overhead / Deployability (DL, SC, CL)
"""

from __future__ import annotations

import math
import random as _random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


# ── Single-run evaluation metrics ─────────────────────────────────────
@dataclass
class EvalMetrics:
    """Structured metrics from one evaluation episode."""

    # -- identifiers --
    ablation_id: str = "A0"
    seed: int = 0
    regime_name: str = "medium"

    # -- Safety / Correctness (lower = better, target = 0) --
    cvr: float = 0.0          # containment violation rate
    ivr: float = 0.0          # invariant violation rate
    dfr: float = 0.0          # deadlock/nonblocking failure rate

    # -- Operational Performance --
    tp: float = 0.0           # throughput (products / time-unit)   ↑
    ct: float = 0.0           # mean cycle time                    ↓
    bt: float = 0.0           # blocking time                      ↓
    rr: float = 0.0           # rework/reroute rate                ↓
    ert: float = 0.0          # exception resolution time          ↓

    # -- Uncertainty Management --
    ef: float = 0.0           # escalation frequency               ↓
    ie: float = 0.0           # inspection efficiency (ΔH / c)     ↑
    cq: float = 0.0           # calibration quality                ↑
    fpr: float = 0.0          # forbidden proposal rate            ↓

    # -- Overhead / Deployability --
    dl: float = 0.0           # decision latency (s)               ↓
    sc: float = 0.0           # storage cost (events)              ↓
    cl: float = 0.0           # communication load (messages)      ↓

    def is_safe(self) -> bool:
        """Point is safe iff CVR = IVR = DFR = 0."""
        return self.cvr == 0.0 and self.ivr == 0.0 and self.dfr == 0.0

    def as_dict(self) -> Dict[str, Any]:
        """Flat dictionary for CSV / JSON export."""
        return {
            "ablation_id": self.ablation_id,
            "seed": self.seed,
            "regime": self.regime_name,
            "cvr": self.cvr,
            "ivr": self.ivr,
            "dfr": self.dfr,
            "tp": round(self.tp, 6),
            "ct": round(self.ct, 4),
            "bt": round(self.bt, 4),
            "rr": round(self.rr, 4),
            "ert": round(self.ert, 4),
            "ef": round(self.ef, 4),
            "ie": round(self.ie, 4),
            "cq": round(self.cq, 4),
            "fpr": round(self.fpr, 4),
            "dl": round(self.dl, 6),
            "sc": round(self.sc, 2),
            "cl": round(self.cl, 2),
        }


# ── Aggregation with bootstrap CI ────────────────────────────────────
@dataclass
class AggregatedMetric:
    """Mean + 95% bootstrap confidence interval for a single metric."""

    mean: float = 0.0
    ci_lower: float = 0.0
    ci_upper: float = 0.0
    n: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "mean": round(self.mean, 6),
            "ci_lower": round(self.ci_lower, 6),
            "ci_upper": round(self.ci_upper, 6),
            "n": self.n,
        }


_METRIC_NAMES = [
    "cvr", "ivr", "dfr",
    "tp", "ct", "bt", "rr", "ert",
    "ef", "ie", "cq", "fpr",
    "dl", "sc", "cl",
]


def _bootstrap_ci(
    values: Sequence[float],
    n_boot: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
) -> AggregatedMetric:
    """Compute mean + percentile bootstrap CI."""
    n = len(values)
    if n == 0:
        return AggregatedMetric()
    if n == 1:
        v = values[0]
        return AggregatedMetric(mean=v, ci_lower=v, ci_upper=v, n=1)

    rng = _random.Random(seed)
    overall_mean = sum(values) / n
    boot_means: List[float] = []
    for _ in range(n_boot):
        sample = [rng.choice(values) for _ in range(n)]
        boot_means.append(sum(sample) / n)
    boot_means.sort()

    lo_idx = max(0, int(math.floor(alpha / 2 * n_boot)) - 1)
    hi_idx = min(n_boot - 1, int(math.ceil((1 - alpha / 2) * n_boot)) - 1)

    return AggregatedMetric(
        mean=overall_mean,
        ci_lower=boot_means[lo_idx],
        ci_upper=boot_means[hi_idx],
        n=n,
    )


def aggregate(
    runs: Sequence[EvalMetrics],
    n_boot: int = 2000,
    seed: int = 0,
) -> Dict[str, AggregatedMetric]:
    """Aggregate multiple runs into mean + CI per metric."""
    result: Dict[str, AggregatedMetric] = {}
    for name in _METRIC_NAMES:
        values = [getattr(r, name) for r in runs]
        result[name] = _bootstrap_ci(values, n_boot=n_boot, seed=seed)
    return result


# ── Envelope classification (PAPER_5 §4.1) ───────────────────────────
@dataclass
class EnvelopeThresholds:
    """Thresholds for envelope boundary classification."""

    tau_tp: float = 0.05      # minimum throughput LCB
    tau_ef: float = 0.50      # maximum escalation frequency UCB


def classify_envelope(
    agg: Dict[str, AggregatedMetric],
    thresholds: Optional[EnvelopeThresholds] = None,
) -> bool:
    """Return True if the operating point is inside the performance envelope.

    Inside iff:
      - CVR_UCB = 0  AND  IVR_UCB = 0
      - TP_LCB ≥ τ_TP
      - EF_UCB ≤ τ_EF
    """
    t = thresholds or EnvelopeThresholds()
    cvr_ucb = agg["cvr"].ci_upper
    ivr_ucb = agg["ivr"].ci_upper
    tp_lcb = agg["tp"].ci_lower
    ef_ucb = agg["ef"].ci_upper

    return (
        cvr_ucb == 0.0
        and ivr_ucb == 0.0
        and tp_lcb >= t.tau_tp
        and ef_ucb <= t.tau_ef
    )
