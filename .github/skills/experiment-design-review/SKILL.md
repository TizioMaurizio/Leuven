---
name: experiment-design-review
description: Procedure to review experiment design for scientific rigor — baselines, ablations, seeds, metrics, regimes, and reproducibility. Use when planning or validating an evaluation study.
---

# Experiment Design Review

## Goal

Verify that an experiment design is scientifically rigorous, reproducible, and sufficient to support the intended claims.

## Checklist

### Baselines
- [ ] At least one no-intervention baseline (e.g., A0: greedy/random without the proposed component).
- [ ] Baselines are fair — they use the same information available to the proposed approach (minus the specific contribution).
- [ ] Baseline implementations exist in the repo (not just described in text).

### Ablations
- [ ] Ablations are additive: A0 → A1 → A2 → ... → A_n, each adding one component.
- [ ] Each ablation isolates exactly one contribution (e.g., A1 adds only the twin, A2 adds only the learning).
- [ ] The full system (A_n) equals the composition of all individual components.
- [ ] No ablation accidentally includes components from a later stage.

### Seeds and Statistical Validity
- [ ] Minimum 10 seeds per scenario for statistical claims.
- [ ] Seeds are documented in config and reproducible.
- [ ] Results report mean ± confidence interval (not just mean).
- [ ] Seed range is consistent across all ablations and scenarios.

### Uncertainty Regimes
- [ ] At least low, medium, high structural uncertainty tested.
- [ ] Regimes are clearly defined in config (e.g., fraction of unknown product types).
- [ ] Results are reported per-regime, not just aggregated.

### Metrics
- [ ] Every paper claim maps to at least one computed metric.
- [ ] Metrics cover both performance (throughput, cycle time, utilization) and correctness (containment violations, belief accuracy).
- [ ] Metric computation excludes warm-up period.
- [ ] Metrics are computed from event logs, not from in-simulation state (observer pattern).

### Scenario Coverage
- [ ] Scenarios cover the range of conditions described in the paper.
- [ ] Edge cases tested: maximum uncertainty, resource saturation, all-unknown products.
- [ ] Fault/exception scenarios included if the paper claims robustness.

### Reproducibility
- [ ] Each run is reproducible from: seed + config file + code version.
- [ ] Run outputs include metadata.json with config, seed, code version, timestamp.
- [ ] Event logs are preserved and immutable.

### Output Structure
- [ ] Results are organized in run directories (e.g., `runs/{scenario}_rep{N}/`).
- [ ] Batch summary CSV aggregates across runs.
- [ ] Output format is suitable for figure generation (CSV, JSON, or structured data).

## Report

For each checklist item:
- PRESENT / MISSING / PARTIAL with evidence.
- If MISSING: what needs to be added, with a suggested implementation location.
- Overall assessment: ready for evaluation / needs design work / major gaps.
