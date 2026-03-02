# WP5 Notes — System-Level Evaluation & Performance Envelope

Extracted from PAPER_5.md (489 lines).

## Core Idea

Rigorous system-level evaluation using:
- Layered ablation (A0→A4) of architectural components
- Structured uncertainty regimes
- Comprehensive metrics framework (safety, ops, uncertainty, overhead)
- Performance envelope estimation

## Ablation Structure

| ID | Layers     | Description                         |
|----|-----------|-------------------------------------|
| A0 | L0        | Supervisor-only baseline            |
| A1 | L0+L1     | + holonic coordination              |
| A2 | A1+L2     | + event-sourced twin                |
| A3 | A2+L3     | + conservative learning             |
| A4 | A3+L4     | + bounded semantic mediation        |

## Uncertainty Factors (6 axes)

- p_d: hidden damage probability
- η: sensor noise level
- p_e: exception frequency
- c_i: inspection cost
- Δ: distribution shift
- t_h: escalation latency

Each discretized to low/medium/high for factorial designs.

## Metrics Framework (4 categories)

### Safety/Correctness (target = 0)
- CVR: containment violation rate
- IVR: invariant violation rate
- DFR: deadlock/nonblocking failure rate

### Operational Performance
- TP: throughput (↑)
- CT: mean cycle time (↓)
- BT: blocking time (↓)
- RR: rework rate (↓)
- ERT: exception resolution time (↓)

### Uncertainty Management
- EF: escalation frequency
- IE: inspection efficiency (ΔH/c)
- CQ: calibration quality
- FPR: forbidden proposal rate

### Overhead/Deployability
- DL: decision latency
- SC: storage cost
- CL: communication load

## Experimental Design

- Fractional factorial (6 factors × 3 levels)
- ≥30 replications per condition (paired seeds)
- Latin hypercube for envelope mapping
- Bootstrap CI for all metrics
- Paired nonparametric tests (permutation/Wilcoxon)
- Effect sizes (Cliff's delta)

## Performance Envelope

Point is "inside" iff:
- CVR = 0 AND IVR = 0
- TP_LCB ≥ τ_TP
- EF_UCB ≤ τ_EF

## Implementation Requirements

### R1: EvalRunner
- Run one ablation config on one scenario
- Return structured metrics dict
- Support seed control

### R2: AblationRunner
- Run A0→A4 on identical scenario seeds
- Collect comparative metrics
- Output CSV/JSON results

### R3: SweepRunner
- Sweep uncertainty space (factorial or LHC)
- Collect metrics per point
- Identify envelope boundary

### R4: Metrics aggregation
- Compute mean/CI per metric
- Bootstrap confidence intervals
- Paired comparisons across ablations

### R5: Report generation
- Output eval_summary.md with tables
- CSV export for analysis
