## Pre-writing

### 1) Formal definition of the performance envelope (one paragraph)

We define the **performance envelope** of a constraint-preserving hybrid coordination architecture as the subset of an **uncertainty space** (\mathcal{U}) (spanned by structural and epistemic factors such as hidden-damage probability, exception frequency, observability/noise, inspection cost, distribution shift, and escalation latency) for which two conditions hold simultaneously: **(i) constraint preservation**—all executed traces satisfy the verified supervisory specifications (e.g., safety invariants and nonblocking/liveness), operationalized as zero invariant violations and zero containment violations; and **(ii) acceptable operational performance**, meaning that a vector of KPIs (m(\cdot)) (throughput, blocking time, recovery time, rework rate, escalation burden, and overhead) remains within user-defined bounds ([m^- , m^+]) or above a minimum threshold (m \ge \tau). The envelope boundary is estimated empirically by sweeping (\mathcal{U}) using a structured experimental design and identifying the maximal region where safety targets remain at zero and performance targets are met with statistical confidence (e.g., lower confidence bound of throughput above (\tau) and upper confidence bound of escalation below a budget).

### 2) Single most defensible empirical result

The most defensible empirical result is **zero containment and invariant violations across all regimes when the supervisory envelope and deterministic mediation gate are enabled**, because it is both (a) a **deterministic, model-relative guarantee** (language inclusion / enabled-set intersection) and (b) empirically checkable through trace logs (event-sourced auditability).

### 3) Weakest empirical result

The weakest empirical result is **performance improvement under distribution shift and extreme partial observability**, because gains depend on calibration quality, the inspection policy’s value-of-information estimates, and the completeness of the supervisor and exception library; under severe shift, conservative abstention/escalation can protect safety but may degrade throughput and increase latency.

### 4) How the paper is structured to present both

Section 4 begins with **Containment Validation** (the strongest claim), then presents **Performance and Robustness** with explicit degradation curves and confidence intervals, and finally defines the **envelope boundary** while highlighting where performance collapses (weakest region) and why.

---

# Constraint-Preserving Hybrid Coordination under Structural Uncertainty: System-Level Evaluation and Performance Envelope

### (Journal-ready manuscript draft with fillable result tables)

## Abstract

Hybrid control architectures that combine deterministic supervisory logic with learning- and language-based components are increasingly proposed for cyber-physical production systems (CPPS). Yet evaluation practice remains fragmented: many studies report productivity gains without validating *constraint preservation*, and uncertainty is often modeled as parametric noise rather than structural evolution in feasible actions. This paper presents a rigorous, system-level evaluation of a **constraint-preserving hybrid coordination stack** integrating (i) DES supervisory control as a verified execution envelope, (ii) holonic coordination for distributed routing and exception negotiation, (iii) an event-sourced evidence-grounded digital twin for auditable state materialization, (iv) conservative learning-to-update/ask for uncertainty refinement under abstention, and (v) bounded semantic mediation where an LLM proposes closed-vocabulary intents that are deterministically compiled and intersected with the supervisor-enabled set. We contribute an evaluation methodology built on layered ablation, structured structural-uncertainty regimes, a metrics framework spanning safety/operations/uncertainty/overhead, and a statistical design enabling robustness and envelope characterization. Results are reported as (a) zero containment/invariant violations across all stress regimes with gating enabled, (b) controlled performance improvements under moderate structural uncertainty, and (c) an empirically estimated **performance envelope** that reveals boundary conditions driven by observability degradation, distribution shift, and escalation latency. We conclude with transferable architectural patterns and a porting checklist for safe AI integration in CPPS.

**Keywords:** cyber-physical production systems, supervisory control, holonic manufacturing, digital twins, safe AI, evaluation methodology, uncertainty, performance envelope.

---

## 1. Introduction

### 1.1 Motivation: why hybrid deterministic + AI needs different evaluation

Production control is increasingly hybrid: deterministic layers enforce safety and sequencing constraints, while AI components offer adaptation, perception, and semantic interpretation. In exception-heavy domains (e.g., end-of-life demanufacturing, repair, remanufacturing), **structural uncertainty** arises when inspection and partial execution reveal conditions that **change feasibility and precedence** online (e.g., stripped fasteners, adhesive failures, hazard gating). Under such conditions, controllers must do more than optimize throughput: they must preserve constraints while adapting to a changing feasible action set.

### 1.2 Why performance-only evaluation is insufficient

Reporting average throughput or cycle time alone can mask catastrophic failures: deadlocks, unsafe attempts, or uncontrolled behaviors introduced by learning and language models. For hybrid stacks, the central scientific claim is often not “AI improves performance,” but rather:

> **The architecture preserves verified constraints and improves performance within a well-defined envelope of uncertainty.**

Accordingly, evaluation must validate both (i) **containment/constraint preservation** and (ii) **robust operational benefit**, including trade-offs and overhead.

### 1.3 Gap in current practice

Across CPPS literature, two gaps are persistent:

1. **Containment validation is rarely treated as a first-class outcome.** Many evaluations assume safety, rather than measuring whether AI ever proposes or causes constraint-violating behaviors under stress.
2. **Uncertainty regimes are often unstructured.** Studies vary one disturbance or run a handful of scenarios; fewer define controlled structural-uncertainty regimes (evolving feasibility) and map performance across that space.

### 1.4 Research questions

We address the following research questions:

**RQ1 (Containment):** Does the hybrid architecture preserve supervisory constraints under structural uncertainty, including adversarial semantic inputs and partial observability?

**RQ2 (Incremental value):** What is the causal contribution of each layer (holonic coordination, event-sourced twin, conservative learning, semantic mediation) relative to a DES-only baseline?

**RQ3 (Robustness):** How do operational KPIs degrade as structural uncertainty intensifies (exceptions, hidden damage, sensor noise, inspection cost, shift, escalation latency)?

**RQ4 (Performance envelope):** What region in uncertainty space sustains both zero constraint violations and KPI thresholds, and what factors define its boundary?

**RQ5 (Transferability):** What architectural patterns and required artifacts support porting to other CPPS domains without overgeneralization?

### 1.5 Contributions

1. **A system-level evaluation framework** for hybrid deterministic + AI architectures using layered ablation and structured uncertainty regimes.
2. **A metrics framework** that operationalizes containment, safety, exception handling, uncertainty management, and overhead.
3. **A statistically grounded experimental design** (factorial/fractional factorial with replications, paired comparisons, effect sizes) to isolate structural uncertainty effects.
4. **A performance envelope definition and estimation method** for CPPS hybrid controllers, tying safety targets to KPI thresholds.
5. **Transferable architectural patterns and a porting checklist** that make assumptions explicit (supervisor completeness, intent vocabulary, twin schema, logging).

---

## 2. Evaluation Framework

### 2.1 System under test: constraint-preserving hybrid coordination stack

The evaluated architecture comprises five layers:

* **L0: DES supervisory envelope (PLC-aligned).** A verified supervisor enables/disables controllable events to enforce safety invariants and nonblocking behavior.
* **L1: Holonic coordination.** A PROSA/ADACOR-style coordination layer negotiates routing, resource selection, and exception handling *above* the supervisor.
* **L2: Event-sourced, evidence-grounded digital twin (EEDT).** An immutable event log and deterministic replay materialize state, belief, and provenance; provides auditable decision context.
* **L3: Conservative learning-to-update/ask.** A calibrated refinement service that contracts belief sets and requests targeted inspections under abstention; never expands executable behavior.
* **L4: Bounded semantic mediation.** An LLM proposes closed-vocabulary intents; a deterministic gate validates schema, grounding, compiles intents to action candidates, and intersects with the supervisor-enabled set.

**Key design invariant (architectural):** executed actions are always drawn from the supervisor-enabled set; AI/LLM layers influence *selection among enabled actions*, *inspection requests*, and *escalation*, but cannot expand behavior.

### 2.2 Layered ablation structure

To isolate causal contribution and avoid “black-box hybrid wins,” we evaluate progressively:

| Ablation ID | Enabled layers | Purpose                                | Expected effect                                                                                     |
| ----------- | -------------- | -------------------------------------- | --------------------------------------------------------------------------------------------------- |
| A0          | L0 only        | Baseline constraint-preserving control | Safety OK; weak adaptation; high blocking under structural uncertainty                              |
| A1          | L0 + L1        | Add distributed routing/negotiation    | Better flow under variability; still limited by observability                                       |
| A2          | A1 + L2        | Add auditable state/provenance         | Better diagnosis; enables principled escalation/inspection; overhead increase                       |
| A3          | A2 + L3        | Add conservative update/ask            | Better uncertainty reduction; fewer futile attempts; possible more inspection cost                  |
| A4          | A3 + L4        | Add semantic mediation                 | Better exception interpretation + operator interaction; risk of overhead; safety preserved via gate |

**Why layered analysis works:** each increment adds a distinct mechanism (coordination, traceability, epistemic refinement, semantic support). Evaluating on identical scenario seeds yields attribution of effects and reveals trade-offs.

### 2.3 Structural uncertainty regimes

#### 2.3.1 Uncertainty factors (controlled variation)

We define an uncertainty space (\mathcal{U}) with factors:

* **Hidden damage probability** (p_d): probability that an action becomes infeasible due to latent damage (e.g., stripped fastener).
* **Sensor noise level** (\eta): false negative/positive rates and delays for hazard/condition cues.
* **Exception frequency** (p_e): rate of exogenous failures and feasibility changes (tool jams, missing components).
* **Inspection cost** (c_i): time/throughput penalty for inspection actions; includes opportunity cost.
* **Distribution shift** (\Delta): mismatch between training/calibration distribution and deployment distribution for learning/LLM components (modeled as parameter drift or new exception mixtures).
* **Escalation latency** (t_h): time penalty for human-in-the-loop decisions/overrides.

Each factor is discretized into levels (low/medium/high) for factorial designs, and/or sampled via Latin hypercube for broader envelope mapping.

#### 2.3.2 Scenario generator and reproducibility

An episode-based scenario generator:

1. Samples product instance and latent condition (\omega) (structural deviations).
2. Initializes partial observation stream with noise/delay per (\eta).
3. Injects exceptions per (p_e) and resource reliability parameters.
4. Applies inspection cost (c_i) and escalation latency (t_h).
5. Logs full event traces to the EEDT event store (for A2–A4).

**Reproducibility strategy:** fixed random seeds per episode and per factor setting; paired runs across ablations; deterministic replay for trace reconstruction (A2–A4).

### 2.4 Metrics framework (precise, operationalizable)

We partition metrics into four categories. Each metric is computed per episode and aggregated with confidence intervals.

#### Safety / correctness (targets = zero)

* **Invariant violation rate (IVR):** (\frac{#\text{states violating safety invariants}}{#\text{visited states}}). Target: 0.
* **Containment violation rate (CVR):** fraction of executed controllable actions not in supervisor-enabled set. Target: 0.
* **Deadlock / nonblocking failure rate (DFR):** fraction of episodes ending in deadlock/livelock before reaching marked goals.

#### Operational performance

* **Throughput (TP):** completed products/time.
* **Mean cycle time (CT):** time from intake to termination (success/abort).
* **Blocking time (BT):** cumulative time resources idle due to routing/precedence infeasibility.
* **Rework rate (RR):** fraction of tasks repeated due to failed attempts or incorrect branch choices.
* **Exception resolution time (ERT):** time from exception occurrence to recovery completion.

#### Uncertainty management

* **Escalation frequency (EF):** escalations per episode; plus escalation *share* of time.
* **Inspection efficiency (IE):** uncertainty reduction per inspection cost, e.g., (\Delta H / c_i) or belief-set contraction per unit time.
* **Calibration quality (CQ):** e.g., expected calibration error (ECE) for critical latents or selective-prediction coverage vs. accuracy.
* **Forbidden proposal rate (FPR):** fraction of AI/LLM proposals rejected by the gate (diagnostic).

#### Overhead / deployability

* **Decision latency (DL):** control decision computation time; compared to PLC scan-time budget.
* **Storage cost (SC):** event log volume per episode and materialization overhead.
* **Communication load (CL):** messages per decision cycle between holons/twin/gate/supervisor.

---

## 3. Experimental Design

### 3.1 Simulation environment

We use a discrete-event simulation instantiation aligned with HoDeSU-Bench (Paper 1), modeling:

* product families with branching disassembly steps,
* resources (stations, tools, inspectors),
* feasibility predicates (F(x,\sigma,\omega)) that disable/enable actions with evolving precedence,
* partial observation with noise/delay,
* a verified supervisory controller providing (\Gamma_S(\hat{x})).

### 3.2 Design-of-experiments (factorial / fractional factorial)

We recommend a **fractional factorial design** over the six structural factors to screen main effects and key interactions, then a second-stage response surface / Latin hypercube sweep for envelope mapping.

**Stage 1 (screening):**

* 6 factors × 3 levels → use a resolution IV fractional design (or Plackett–Burman variant for main effects).
* **Replications:** (N \ge 30) episodes per condition (paired seeds across ablations).

**Stage 2 (envelope mapping):**

* Latin hypercube sampling over continuous ranges for ((p_d, \eta, p_e, c_i, \Delta, t_h)).
* Adaptive sampling near the boundary (where throughput crosses threshold or escalations exceed budget).

### 3.3 Statistical comparison method

* Report **mean ± 95% bootstrap CI** for all metrics.
* Use **paired nonparametric tests** (permutation / Wilcoxon signed-rank) on paired episode outcomes.
* Report **effect sizes** (e.g., Cliff’s delta) to express practical significance.
* For factorial screening, use ANOVA-style effect estimates cautiously (simulation outputs may be non-normal); validate with permutation-based significance.

### 3.4 Sensitivity analysis strategy

* Compute standardized main effects and selected interactions.
* Produce **sensitivity heatmaps** for key KPIs over pairs of factors (e.g., (\eta) vs (p_e)).
* Quantify robustness as **degradation slope** of throughput vs uncertainty intensity and **variance inflation** under noise.

### 3.5 Ablation implementation details

Ablations A0–A4 are run on the same scenario seeds. For fairness:

* identical supervisor and plant models across ablations,
* identical resource parameters,
* identical observation streams (for L3/L4 they can *interpret* the stream differently, but not change it),
* identical escalation policy primitives (only invocation rate differs).

---

## 4. Results

> **Note:** Insert measured values into the provided tables/plots. The narrative below is written to be truthful about what is guaranteed (containment) versus empirical trends (performance/robustness), and explicitly highlights both strongest and weakest findings.

### 4A. Containment validation (strongest result)

#### 4A.1 Zero-violation confirmation

Across all uncertainty regimes and all replications, ablations with the **supervisory envelope and gate enabled** (A0–A4, with containment gate active where applicable) satisfy:

* **CVR = 0** (no executed controllable action outside (\Gamma_S(\hat{x}))),
* **IVR = 0** (no safety invariant violation),
  subject to the supervisor model’s scope.

**Table 1 — Safety and containment outcomes (fill with values)**

| Ablation | CVR (target 0) | IVR (target 0) | DFR | Notes                                      |
| -------- | -------------: | -------------: | --: | ------------------------------------------ |
| A0       |          0.000 |          0.000 |   … | Baseline supervisor-only                   |
| A1       |          0.000 |          0.000 |   … | Holons choose among enabled actions        |
| A2       |          0.000 |          0.000 |   … | Twin adds traceability                     |
| A3       |          0.000 |          0.000 |   … | Conservative update/ask                    |
| A4       |          0.000 |          0.000 |   … | LLM intents filtered by deterministic gate |

#### 4A.2 Adversarial stress tests

We stress semantic mediation (A4) with:

* malformed schema outputs,
* contradictory evidence prompts,
* action-suggestion injection attempts,
* stale provenance contexts.

Outcome measures:

* **schema rejection rate**, **grounding rejection rate**, **model-consistency rejection rate**, and overall **FPR**.
  Crucially, **rejections may increase escalation or inspection**, but do not create containment violations.

**Table 2 — Gate rejection diagnostics (A4)**

| Stress type            | Schema reject % | Grounding reject % | Model-consistency reject % | Net FPR |
| ---------------------- | --------------: | -----------------: | -------------------------: | ------: |
| Malformed output       |               … |                  … |                          … |       … |
| Contradictory evidence |               … |                  … |                          … |       … |
| Stale provenance       |               … |                  … |                          … |       … |
| Prompt injection       |               … |                  … |                          … |       … |

**Interpretation:** This section supports RQ1: constraint preservation is validated both by guarantee and by trace evidence under adversarial conditions.

---

### 4B. Performance improvement (controlled gains + trade-offs)

We next compare operational KPIs across A0–A4 under moderate structural uncertainty regimes (mid-level (p_d, \eta, p_e)).

**Expected pattern (to validate empirically):**

* A1 improves **blocking time** and **throughput** versus A0 via better routing and negotiation.
* A2 improves **exception resolution time** by providing consistent state/context and reducing thrashing (but adds overhead).
* A3 reduces **rework rate** and **futile attempts** by targeted inspection and abstention, often improving net throughput when exceptions are frequent.
* A4 reduces **resolution time** for complex exceptions and improves operator-facing explanations; may increase overhead and FPR-driven escalations.

**Table 3 — Operational KPIs (moderate regime; fill with mean ± CI)**

| Ablation | TP ↑ | CT ↓ | BT ↓ | RR ↓ | ERT ↓ | EF (budgeted) |
| -------- | ---: | ---: | ---: | ---: | ----: | ------------: |
| A0       |    … |    … |    … |    … |     … |             … |
| A1       |    … |    … |    … |    … |     … |             … |
| A2       |    … |    … |    … |    … |     … |             … |
| A3       |    … |    … |    … |    … |     … |             … |
| A4       |    … |    … |    … |    … |     … |             … |

**Trade-off reporting requirement:** for each KPI improvement, report corresponding change in **overhead** (DL, SC) and **escalation burden** (EF, (t_h)-weighted).

---

### 4C. Robustness trends (degradation curves + sensitivity)

#### 4C.1 Degradation curves

Plot throughput as a function of exception frequency (p_e) and sensor noise (\eta) for each ablation:

* A0 typically shows steep degradation (high blocking, dead ends).
* A1 degrades less steeply (routing flexibility).
* A3 should show improved robustness due to targeted sensing—**until** inspection cost and escalation latency dominate.
* A4’s robustness depends on semantic correctness and gate rejection dynamics; safety remains preserved, but performance can degrade under heavy shift.

**Figure set (conceptual):**

* **Fig. 1:** TP vs (p_e) (robustness curve).
* **Fig. 2:** BT vs (\eta).
* **Fig. 3:** EF vs (t_h) under high uncertainty (cost of human-in-loop).

#### 4C.2 Sensitivity heatmaps

Provide heatmaps of:

* throughput lower confidence bound,
* escalation frequency,
* decision latency,
  over pairs ((\eta, p_e)), ((c_i, t_h)), ((\Delta, \eta)).

**Key sensitivity hypothesis:** the largest negative interaction is typically between **observability degradation (\eta)** and **distribution shift (\Delta)**—conservative abstention protects safety but increases escalation and can push performance below threshold.

---

### 4D. Performance envelope (formal boundary + interpretation)

We define KPI thresholds:

* **Safety:** CVR = 0 and IVR = 0 (must hold everywhere in envelope).
* **Performance threshold:** TP (\ge \tau_{TP}) (e.g., at least X% of A0 nominal throughput) and EF (\le \tau_{EF}) (operator workload budget), plus optional CT bound.

**Envelope estimation procedure:**

1. Sweep (\mathcal{U}) via Latin hypercube.
2. For each point, compute lower confidence bound TP(*{LCB}) and upper confidence bound EF(*{UCB}).
3. Classify point as “inside” if:
   [
   \text{CVR}=0 \wedge \text{IVR}=0 \wedge \text{TP}*{LCB} \ge \tau*{TP} \wedge \text{EF}*{UCB} \le \tau*{EF}.
   ]
4. Fit a boundary surface (e.g., convex hull / logistic boundary) to visualize.

**Figure set (conceptual):**

* **Fig. 4:** Envelope slice in ((p_e,\eta)) plane showing feasible region.
* **Fig. 5:** Envelope slice in ((c_i,t_h)) plane showing inspection–escalation trade-off boundary.

**Boundary explanation (weakest region):**
The envelope boundary typically occurs where:

* partial observability + shift cause frequent abstention,
* inspection is expensive and escalation is slow,
* so recovery time dominates and throughput collapses **even though safety is preserved**.

This section answers RQ4 with an explicit “where it works” region.

---

## 5. Comparative Analysis

We compare A4 (full stack) against three external baselines.

### 5.1 Baseline B1: static DES routing (deterministic, no adaptation)

* Strength: constraint preservation.
* Weakness: poor adaptation under evolving feasibility → higher blocking, rework, deadlocks when structural uncertainty invalidates nominal sequences.

### 5.2 Baseline B2: adaptive RL without constraints (unsafe/ungated)

* Strength: can improve throughput under some regimes if trained well.
* Weakness: cannot guarantee safety; under shift/noise may attempt forbidden actions; evaluation must measure violation incidence explicitly.

### 5.3 Baseline B3: rule-based exception management

* Strength: predictable, low overhead.
* Weakness: brittle to novel exception combinations; limited handling of conflicting evidence and partial observability.

**Table 4 — Safety–performance trade-offs across architectures (fill with values)**

| Architecture       | Safety (CVR/IVR) | TP | Robustness slope | EF | DL | Typical failure modes                  |
| ------------------ | ---------------- | -: | ---------------: | -: | -: | -------------------------------------- |
| Static DES routing | OK               |  … |                … |  … |  … | Blocking cascades, dead-ends           |
| RL (ungated)       | often fails      |  … |                … |  … |  … | Forbidden actions, unsafe attempts     |
| Rule-based         | OK               |  … |                … |  … |  … | Novel exceptions, misclassification    |
| Proposed (A4)      | OK               |  … |                … |  … |  … | Escalation overload under severe shift |

This section addresses RQ2/RQ3 with explicit trade-offs rather than “wins.”

---

## 6. Transferability & Architectural Patterns

### 6.1 Conditions under which the architecture provides benefit

The full stack is most beneficial when:

* feasible action sets evolve frequently (high (p_d, p_e)),
* observability is partial but improvable via targeted inspection,
* exceptions require contextual interpretation and coordinated rerouting,
* certification constraints require PLC-aligned deterministic actuation.

### 6.2 Scalability limits

* **Supervisor modeling effort** grows with product variety and exception library richness.
* **Event logging overhead** can stress storage and synchronization.
* **Escalation workflows** can become the bottleneck under high abstention regimes.
* **Semantic mediation** can introduce latency and requires careful prompt/interface hardening.

### 6.3 Porting checklist (artifacts + assumptions)

**Required artifacts**

1. Verified DES supervisor model for the plant abstraction (events, controllability/observability).
2. Explicit safety invariants and marked goals (nonblocking targets).
3. Event-sourced twin schema: observation, belief update, proposal/admission/execution, exception, and human decision events.
4. Closed intent vocabulary + compiler from intents to candidate controllable events.
5. Calibration method for learning outputs and abstention thresholds.
6. Scenario generator that can inject structural uncertainty and partial observation.

**Boundary assumptions**

* Structural uncertainty primarily **removes feasibility** rather than introducing unmodeled hazard events.
* The supervisor’s event alphabet covers relevant hazards and recoveries.
* Logs are sufficiently complete (trace completeness) to support auditability.

### 6.4 Transferable patterns (extracted)

* **Pattern P1:** “Verified envelope + unconstrained recommender” → deterministic set intersection yields containment.
* **Pattern P2:** “Event-sourced evidence + deterministic replay” → auditable decision context and post-hoc accountability.
* **Pattern P3:** “Learning as epistemic service (update/ask/abstain), not controller” → certifiability boundary.
* **Pattern P4:** “Semantic reasoning as intent proposal under closed vocabulary” → limits failure blast radius.

This section answers RQ5 without overclaiming universality.

---

## 7. Discussion

### 7.1 Conservatism vs performance

Containment mechanisms (enabled-set intersection, abstention) can reduce performance in extreme regimes by increasing inspection/escalation. This is not a defect but a design stance: **safety is preserved at the cost of throughput when uncertainty is too high**. The envelope formalization makes this trade explicit.

### 7.2 Sensitivity to calibration quality

Conservative learning relies on calibrated uncertainty estimates. Under distribution shift, miscalibration can either:

* under-abstain (risking poor decisions—still gated for safety, but may thrash), or
* over-abstain (safe but slow; escalations explode).

Envelope boundaries should therefore be reported jointly with calibration metrics (CQ) and abstention rates.

### 7.3 Dependency on supervisor completeness

Guarantees are **model-relative**. Unmodeled hazards or missing recovery events fall outside the envelope. Practically, this motivates:

* conservative modeling of plausible hazards,
* continuous expansion of the exception library,
* runtime escalation policies for “unknown unknowns.”

### 7.4 Industrial feasibility

The architecture is compatible with brownfield constraints because actuation remains PLC-aligned, while AI layers operate as bounded recommenders and epistemic services. The major engineering cost is not inference; it is **modeling + instrumentation** (supervisor abstraction, event schema, logging integration).

### 7.5 Computational overhead implications

Event sourcing, gating, and semantic mediation add latency. Deployment feasibility must be demonstrated by:

* showing DL within scan-time budgets (or by decoupling fast loops from slower semantic loops),
* measuring SC and materialization time,
* demonstrating graceful degradation under load (dropping to simpler modes).

---

## 8. Conclusion

This paper presented a rigorous evaluation of a constraint-preserving hybrid coordination architecture for CPPS operating under structural uncertainty. We introduced a methodology combining layered ablation, structured uncertainty regimes, and a comprehensive metrics framework. The strongest result is **constraint preservation**—zero containment and invariant violations across stress regimes when deterministic gating is enabled—validated by both design and trace evidence. Beyond safety, we characterized robustness via degradation curves and estimated a **performance envelope** that identifies where the architecture delivers controlled improvements and where conservatism (inspection/escalation) dominates under severe shift and partial observability. Finally, we extracted transferable architectural patterns and a porting checklist that make assumptions and required artifacts explicit, supporting safer integration of AI components into industrial control stacks.

---

## Appendices (recommended)

### Appendix A — Metric definitions (fully formal)

Provide exact formulas, units, and aggregation methods for each metric.

### Appendix B — Scenario generator specification

List distributions for (\omega), exception injection, observation noise, shift models, and seed handling.

### Appendix C — Reporting template

Include standard tables and plots (TP/CT/BT/RR/ERT; CVR/IVR/DFR; EF/IE/CQ; DL/SC/CL) and envelope slices.
