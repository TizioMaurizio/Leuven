---
name: review-experiment-design
description: Review an experiment design for scientific rigor — baselines, ablations, seeds, metrics, and reproducibility.
mode: agent
agent: Evaluation
---

Review the experiment design for the specified study.

1. Read the scenario definitions and batch configuration files.
2. Use the `experiment-design-review` skill checklist.
3. Check: baseline present? Ablations isolate components? Sufficient seeds (≥10)? Metrics cover all claims?
4. Check: warm-up documented and excluded? Uncertainty regimes tested? Results reproducible from seed+config?
5. Report checklist results with recommendations for missing elements.
