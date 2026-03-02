"""Sweep runner — factorial & LHS uncertainty-space exploration (PAPER_5 §3).

Provides:
  - factorial_sweep:  full grid over discretised uncertainty factors
  - lhs_sweep:        Latin-hypercube sample for envelope estimation
  - envelope_map:     classify each swept point as inside/outside envelope
"""

from __future__ import annotations

import itertools
import math
import random as _random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..config import UncertaintyRegime
from .ablation import AblationConfig, run_one, ABLATION_IDS
from .metrics import (
    EvalMetrics,
    EnvelopeThresholds,
    aggregate,
    classify_envelope,
)


# ── Uncertainty factor space ──────────────────────────────────────────

# Six factors from PAPER_5 §2.3, each with low/medium/high presets
_FACTOR_LEVELS: Dict[str, Dict[str, float]] = {
    "p_d": {"low": 0.03, "medium": 0.10, "high": 0.25},       # hidden damage (stripped_screw)
    "eta": {"low": 0.02, "medium": 0.05, "high": 0.15},       # sensor noise (false neg)
    "p_e": {"low": 0.01, "medium": 0.05, "high": 0.15},       # exception frequency (missing)
    "c_i": {"low": 3.0, "medium": 5.0, "high": 8.0},          # inspection cost (time)
    "delta": {"low": 0.02, "medium": 0.08, "high": 0.20},     # distribution shift (adhesive)
    "t_h": {"low": 0.01, "medium": 0.03, "high": 0.10},       # escalation latency (station_failure)
}

FACTOR_NAMES = list(_FACTOR_LEVELS.keys())


def _regime_from_factors(factors: Dict[str, float]) -> UncertaintyRegime:
    """Build an UncertaintyRegime from the 6-factor parameterisation."""
    return UncertaintyRegime(
        stripped_screw_prob=factors.get("p_d", 0.10),
        stuck_adhesive_prob=factors.get("delta", 0.08),
        missing_component_prob=factors.get("p_e", 0.05),
        battery_risk_prob=0.12,  # held constant
        sensor_false_negative=factors.get("eta", 0.05),
        station_failure_prob=factors.get("t_h", 0.03),
        arrival_interval=12.0,  # held constant
    )


def _factor_label(factors: Dict[str, float]) -> str:
    """Short label for a factor combination."""
    parts = []
    for name in FACTOR_NAMES:
        val = factors.get(name, 0)
        for level_name, level_val in _FACTOR_LEVELS[name].items():
            if abs(val - level_val) < 1e-9:
                parts.append(f"{name}={level_name}")
                break
        else:
            parts.append(f"{name}={val:.3f}")
    return "|".join(parts)


# ── Factorial sweep ───────────────────────────────────────────────────
def factorial_sweep(
    ablation_id: str = "A4",
    seeds: Sequence[int] = (42,),
    levels: Sequence[str] = ("low", "medium", "high"),
    max_steps: int = 200,
    max_products: int = 30,
) -> List[EvalMetrics]:
    """Run a full factorial over the 6 uncertainty factors.

    With 3 levels per factor this produces 3^6 = 729 conditions.
    Each condition is run for each seed.
    """
    config = AblationConfig.from_id(ablation_id)
    factor_combos = list(
        itertools.product(*[levels for _ in FACTOR_NAMES])
    )

    results: List[EvalMetrics] = []
    for combo in factor_combos:
        factors = {
            name: _FACTOR_LEVELS[name][level]
            for name, level in zip(FACTOR_NAMES, combo)
        }
        regime = _regime_from_factors(factors)
        regime_name = _factor_label(factors)

        for s in seeds:
            em = run_one(
                config=config,
                seed=s,
                regime=regime,
                regime_name=regime_name,
                max_steps=max_steps,
                max_products=max_products,
            )
            results.append(em)

    return results


# ── Latin-hypercube sample ────────────────────────────────────────────
def lhs_sweep(
    ablation_id: str = "A4",
    n_samples: int = 50,
    seeds_per_point: int = 5,
    base_seed: int = 0,
    max_steps: int = 200,
    max_products: int = 30,
) -> List[EvalMetrics]:
    """Latin-hypercube sample over the continuous uncertainty space.

    Each factor is sampled uniformly within its [low, high] range.
    """
    config = AblationConfig.from_id(ablation_id)
    rng = _random.Random(base_seed)
    k = len(FACTOR_NAMES)

    # Generate LHS grid
    perm: List[List[int]] = [list(range(n_samples)) for _ in range(k)]
    for p in perm:
        rng.shuffle(p)

    results: List[EvalMetrics] = []
    for i in range(n_samples):
        factors: Dict[str, float] = {}
        for j, name in enumerate(FACTOR_NAMES):
            levels = _FACTOR_LEVELS[name]
            lo = levels["low"]
            hi = levels["high"]
            # bin centre
            u = (perm[j][i] + rng.random()) / n_samples
            factors[name] = lo + u * (hi - lo)

        regime = _regime_from_factors(factors)
        regime_name = _factor_label(factors)

        for s_idx in range(seeds_per_point):
            seed = base_seed + i * seeds_per_point + s_idx
            em = run_one(
                config=config,
                seed=seed,
                regime=regime,
                regime_name=regime_name,
                max_steps=max_steps,
                max_products=max_products,
            )
            results.append(em)

    return results


# ── Envelope estimation ───────────────────────────────────────────────
@dataclass
class EnvelopePoint:
    """One point in the envelope map."""

    factors: Dict[str, float]
    regime_name: str
    inside: bool
    aggregated: Dict[str, Any] = field(default_factory=dict)


def envelope_map(
    sweep_results: List[EvalMetrics],
    thresholds: Optional[EnvelopeThresholds] = None,
    n_boot: int = 1000,
) -> List[EnvelopePoint]:
    """Classify each swept regime-point as inside/outside the envelope.

    Groups results by regime_name, aggregates, classifies.
    """
    # Group by regime_name
    groups: Dict[str, List[EvalMetrics]] = {}
    for em in sweep_results:
        groups.setdefault(em.regime_name, []).append(em)

    points: List[EnvelopePoint] = []
    for regime_name, runs in groups.items():
        agg = aggregate(runs, n_boot=n_boot)
        inside = classify_envelope(agg, thresholds)

        # Parse factors from regime_name (best-effort)
        factors: Dict[str, float] = {}
        for part in regime_name.split("|"):
            if "=" in part:
                k, v = part.split("=", 1)
                try:
                    factors[k] = float(v)
                except ValueError:
                    factors[k] = _FACTOR_LEVELS.get(k, {}).get(v, 0.0)

        points.append(EnvelopePoint(
            factors=factors,
            regime_name=regime_name,
            inside=inside,
            aggregated={k: v.as_dict() for k, v in agg.items()},
        ))

    return points
