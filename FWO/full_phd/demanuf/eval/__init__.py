"""Eval sub-package — ablations, sweeps, reporting (WP5)."""

from .metrics import EvalMetrics, aggregate, classify_envelope, EnvelopeThresholds
from .ablation import (
    AblationConfig,
    ABLATION_CONFIGS,
    ABLATION_IDS,
    run_one,
    run_ablation,
)
from .sweep import factorial_sweep, lhs_sweep, envelope_map
from .report import generate_report, write_report, to_csv, to_json

__all__ = [
    "EvalMetrics",
    "aggregate",
    "classify_envelope",
    "EnvelopeThresholds",
    "AblationConfig",
    "ABLATION_CONFIGS",
    "ABLATION_IDS",
    "run_one",
    "run_ablation",
    "factorial_sweep",
    "lhs_sweep",
    "envelope_map",
    "generate_report",
    "write_report",
    "to_csv",
    "to_json",
]
