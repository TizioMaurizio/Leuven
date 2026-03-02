"""WP5 tests — evaluation harness: metrics, ablation, sweep, report.

Exercises:
  - EvalMetrics construction & serialisation
  - Bootstrap CI aggregation
  - Envelope classification
  - AblationConfig layer selection
  - run_one for each ablation level
  - Ablation runner (A0-A4 on paired seeds)
  - Factorial sweep (tiny 2-factor variant)
  - LHS sweep
  - Envelope mapping
  - Report generation (Markdown + CSV + JSON)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from demanuf.config import UncertaintyRegime, REGIME_LOW, REGIME_MEDIUM, REGIME_HIGH
from demanuf.eval.metrics import (
    EvalMetrics,
    AggregatedMetric,
    EnvelopeThresholds,
    aggregate,
    classify_envelope,
    _bootstrap_ci,
    _METRIC_NAMES,
)
from demanuf.eval.ablation import (
    AblationConfig,
    ABLATION_CONFIGS,
    ABLATION_IDS,
    AblationResult,
    run_one,
    run_ablation,
)
from demanuf.eval.sweep import (
    FACTOR_NAMES,
    factorial_sweep,
    lhs_sweep,
    envelope_map,
    EnvelopePoint,
    _regime_from_factors,
)
from demanuf.eval.report import (
    to_csv,
    to_json,
    generate_report,
    write_report,
)


# =====================================================================
# EvalMetrics
# =====================================================================
class TestEvalMetrics:
    def test_construction_defaults(self):
        em = EvalMetrics()
        assert em.ablation_id == "A0"
        assert em.cvr == 0.0
        assert em.tp == 0.0
        assert em.is_safe()

    def test_is_safe_true(self):
        em = EvalMetrics(cvr=0.0, ivr=0.0, dfr=0.0)
        assert em.is_safe()

    def test_is_safe_false(self):
        em = EvalMetrics(cvr=0.01)
        assert not em.is_safe()

    def test_as_dict_keys(self):
        d = EvalMetrics().as_dict()
        assert "ablation_id" in d
        assert "cvr" in d
        assert "tp" in d
        assert "dl" in d
        assert len(d) == 18  # 3 id + 15 metrics

    def test_as_dict_round_trip(self):
        em = EvalMetrics(ablation_id="A3", seed=7, tp=0.123456789)
        d = em.as_dict()
        assert d["ablation_id"] == "A3"
        assert d["seed"] == 7
        assert isinstance(d["tp"], float)


# =====================================================================
# Bootstrap CI
# =====================================================================
class TestBootstrapCI:
    def test_empty(self):
        agg = _bootstrap_ci([])
        assert agg.n == 0
        assert agg.mean == 0.0

    def test_single_value(self):
        agg = _bootstrap_ci([5.0])
        assert agg.mean == 5.0
        assert agg.ci_lower == 5.0
        assert agg.ci_upper == 5.0
        assert agg.n == 1

    def test_identical_values(self):
        agg = _bootstrap_ci([3.0, 3.0, 3.0, 3.0])
        assert agg.mean == 3.0
        assert agg.ci_lower == 3.0
        assert agg.ci_upper == 3.0

    def test_ci_contains_mean(self):
        vals = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        agg = _bootstrap_ci(vals, n_boot=5000, seed=42)
        assert agg.ci_lower <= agg.mean <= agg.ci_upper
        assert agg.n == 10

    def test_wide_spread(self):
        vals = [0.0, 100.0]
        agg = _bootstrap_ci(vals, seed=1)
        assert agg.ci_lower <= agg.mean <= agg.ci_upper


# =====================================================================
# Aggregation
# =====================================================================
class TestAggregate:
    def test_aggregate_single(self):
        em = EvalMetrics(tp=0.5, cvr=0.0, ef=0.1)
        agg = aggregate([em])
        assert agg["tp"].mean == 0.5
        assert agg["cvr"].mean == 0.0
        assert agg["ef"].mean == 0.1

    def test_aggregate_multiple(self):
        runs = [
            EvalMetrics(tp=0.4),
            EvalMetrics(tp=0.6),
            EvalMetrics(tp=0.5),
        ]
        agg = aggregate(runs, n_boot=1000, seed=0)
        assert abs(agg["tp"].mean - 0.5) < 0.01

    def test_all_metrics_present(self):
        agg = aggregate([EvalMetrics()])
        for name in _METRIC_NAMES:
            assert name in agg


# =====================================================================
# Envelope Classification
# =====================================================================
class TestEnvelope:
    def test_inside_envelope(self):
        """Safe, sufficient throughput, low escalation -> inside."""
        runs = [EvalMetrics(cvr=0.0, ivr=0.0, dfr=0.0, tp=0.1, ef=0.2)]
        agg = aggregate(runs)
        assert classify_envelope(agg)

    def test_outside_safety(self):
        """Any safety violation -> outside."""
        runs = [EvalMetrics(cvr=0.01, tp=0.1, ef=0.1)]
        agg = aggregate(runs)
        assert not classify_envelope(agg)

    def test_outside_throughput(self):
        """Below throughput threshold -> outside."""
        runs = [EvalMetrics(tp=0.01, cvr=0.0, ivr=0.0, dfr=0.0, ef=0.1)]
        agg = aggregate(runs)
        thresholds = EnvelopeThresholds(tau_tp=0.05)
        assert not classify_envelope(agg, thresholds)

    def test_outside_escalation(self):
        """High escalation -> outside."""
        runs = [EvalMetrics(cvr=0.0, ivr=0.0, dfr=0.0, tp=0.1, ef=0.9)]
        agg = aggregate(runs)
        thresholds = EnvelopeThresholds(tau_ef=0.5)
        assert not classify_envelope(agg, thresholds)


# =====================================================================
# AblationConfig
# =====================================================================
class TestAblationConfig:
    def test_a0_layers(self):
        c = AblationConfig.from_id("A0")
        assert c.layers == "L0"
        assert not c.use_holonic
        assert not c.use_twin

    def test_a1_layers(self):
        c = AblationConfig.from_id("A1")
        assert c.layers == "L0+L1"
        assert c.use_holonic

    def test_a2_layers(self):
        c = AblationConfig.from_id("A2")
        assert c.layers == "L0+L1+L2"
        assert c.use_twin

    def test_a3_layers(self):
        c = AblationConfig.from_id("A3")
        assert c.layers == "L0+L1+L2+L3"
        assert c.use_learning

    def test_a4_layers(self):
        c = AblationConfig.from_id("A4")
        assert c.layers == "L0+L1+L2+L3+L4"
        assert c.use_mediation

    def test_configs_dict(self):
        assert len(ABLATION_CONFIGS) == 5
        assert set(ABLATION_CONFIGS.keys()) == {"A0", "A1", "A2", "A3", "A4"}

    def test_progressive_inclusion(self):
        """Each level includes all layers of the level below."""
        prev_layers = set()
        for aid in ABLATION_IDS:
            c = AblationConfig.from_id(aid)
            current = set(c.layers.split("+"))
            assert prev_layers <= current, f"{aid}: {prev_layers} not subset of {current}"
            prev_layers = current


# =====================================================================
# run_one
# =====================================================================
class TestRunOne:
    @pytest.mark.parametrize("aid", ABLATION_IDS)
    def test_run_one_returns_eval_metrics(self, aid):
        config = AblationConfig.from_id(aid)
        em = run_one(config, seed=42, max_steps=30, max_products=5)
        assert isinstance(em, EvalMetrics)
        assert em.ablation_id == aid
        assert em.seed == 42

    def test_run_one_deterministic(self):
        config = AblationConfig.from_id("A0")
        em1 = run_one(config, seed=7, max_steps=30, max_products=5)
        em2 = run_one(config, seed=7, max_steps=30, max_products=5)
        assert em1.tp == em2.tp
        assert em1.cvr == em2.cvr
        assert em1.ct == em2.ct

    def test_all_metrics_populated(self):
        config = AblationConfig.from_id("A2")
        em = run_one(config, seed=1, max_steps=50, max_products=10)
        d = em.as_dict()
        # All numeric fields should be finite
        for key in _METRIC_NAMES:
            assert isinstance(d[key], (int, float))

    def test_a0_safety(self):
        """A0 (supervisor only) should have 0 safety violations."""
        config = AblationConfig.from_id("A0")
        em = run_one(config, seed=42, max_steps=50, max_products=10)
        assert em.cvr == 0.0  # supervisor guarantees safety


# =====================================================================
# run_ablation
# =====================================================================
class TestRunAblation:
    def test_run_ablation_small(self):
        results = run_ablation(
            ablation_ids=["A0", "A1"],
            seeds=[0, 1],
            max_steps=20,
            max_products=3,
        )
        assert "A0" in results
        assert "A1" in results
        assert results["A0"].n_runs == 2
        assert results["A1"].n_runs == 2

    def test_paired_seeds(self):
        """All ablation levels use the same DES seeds."""
        results = run_ablation(
            ablation_ids=["A0", "A2"],
            seeds=[42],
            max_steps=20,
            max_products=3,
        )
        assert results["A0"].runs[0].seed == results["A2"].runs[0].seed == 42


# =====================================================================
# Sweep
# =====================================================================
class TestSweep:
    def test_regime_from_factors(self):
        regime = _regime_from_factors({"p_d": 0.1, "eta": 0.05})
        assert regime.stripped_screw_prob == 0.1
        assert regime.sensor_false_negative == 0.05

    def test_factor_names(self):
        assert len(FACTOR_NAMES) == 6
        assert "p_d" in FACTOR_NAMES

    def test_lhs_sweep_small(self):
        results = lhs_sweep(
            ablation_id="A0",
            n_samples=3,
            seeds_per_point=1,
            max_steps=10,
            max_products=2,
        )
        assert len(results) == 3

    def test_lhs_deterministic(self):
        r1 = lhs_sweep("A0", n_samples=2, seeds_per_point=1, base_seed=0,
                        max_steps=10, max_products=2)
        r2 = lhs_sweep("A0", n_samples=2, seeds_per_point=1, base_seed=0,
                        max_steps=10, max_products=2)
        assert r1[0].tp == r2[0].tp

    def test_envelope_map(self):
        results = lhs_sweep("A0", n_samples=3, seeds_per_point=2,
                            max_steps=10, max_products=2)
        points = envelope_map(results, n_boot=100)
        assert len(points) > 0
        assert all(isinstance(p, EnvelopePoint) for p in points)
        for p in points:
            assert isinstance(p.inside, bool)


# =====================================================================
# Report
# =====================================================================
class TestReport:
    @pytest.fixture
    def sample_results(self):
        return [
            run_one(AblationConfig.from_id("A0"), seed=0, max_steps=20, max_products=3),
            run_one(AblationConfig.from_id("A0"), seed=1, max_steps=20, max_products=3),
            run_one(AblationConfig.from_id("A2"), seed=0, max_steps=20, max_products=3),
            run_one(AblationConfig.from_id("A2"), seed=1, max_steps=20, max_products=3),
        ]

    def test_to_csv(self, sample_results):
        csv_str = to_csv(sample_results)
        lines = csv_str.strip().split("\n")
        assert len(lines) == 5  # header + 4 data rows
        assert "ablation_id" in lines[0]
        assert "cvr" in lines[0]

    def test_to_json(self, sample_results):
        j = to_json(sample_results)
        data = json.loads(j)
        assert len(data) == 4
        assert data[0]["ablation_id"] in ("A0", "A2")

    def test_generate_report_markdown(self, sample_results):
        md = generate_report(sample_results, n_boot=100)
        assert "# Evaluation Summary" in md
        assert "Table 1" in md
        assert "Envelope Classification" in md
        assert "A0" in md

    def test_write_report_creates_files(self, sample_results):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = write_report(sample_results, tmpdir)
            assert (out / "eval_summary.md").exists()
            assert (out / "results.csv").exists()
            assert (out / "results.json").exists()

    def test_empty_results_csv(self):
        assert to_csv([]) == ""


# =====================================================================
# Integration: full pipeline
# =====================================================================
class TestIntegration:
    def test_full_pipeline_tiny(self):
        """End-to-end: ablation -> aggregate -> envelope -> report."""
        results_dict = run_ablation(
            ablation_ids=["A0", "A4"],
            seeds=[0, 1],
            max_steps=20,
            max_products=3,
        )
        all_results = []
        for aid, abl in results_dict.items():
            all_results.extend(abl.runs)

        # Aggregate per ablation
        for aid in ["A0", "A4"]:
            runs = [r for r in all_results if r.ablation_id == aid]
            agg = aggregate(runs, n_boot=100)
            # All metrics should be aggregated
            assert len(agg) == len(_METRIC_NAMES)

        # Report
        md = generate_report(all_results, n_boot=100)
        assert "A0" in md
        assert "A4" in md

    def test_safety_invariant_across_ablations(self):
        """Safety violations should be 0 across all ablation levels (supervisor guarantees)."""
        results_dict = run_ablation(
            ablation_ids=ABLATION_IDS,
            seeds=[42],
            max_steps=30,
            max_products=5,
        )
        for aid, abl in results_dict.items():
            for em in abl.runs:
                assert em.cvr == 0.0, f"{aid} seed={em.seed}: CVR={em.cvr}"
