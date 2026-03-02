## Paper 3 — Conservative Learning-to-Update and Learning-to-Ask under DES-Constrained Structural Uncertainty

### Pre-writing

**1) Single strongest conceptual contribution**
A **belief-centric learning layer** that *only refines interpretations* of latent structural conditions (what is feasible / hazardous / unknown) and *never expands behavior*, because **all executable actions remain constrained by a verified DES supervisor**. Learning is treated as *uncertainty refinement + targeted evidence acquisition*, not policy synthesis.

**2) Exact safety property we can defend formally**
**Non-expansion / containment of executed behavior**: for every time step, the executed controllable event lies in the **supervisor-enabled set** (A_{\text{sup}}(s_t)). Consequently, the closed-loop language under the learned coordinator is contained in the supervisor’s closed-loop language (the Paper-1 “no-new-behavior” property), and safety invariants proven for the supervisor remain preserved.

**3) How this differs from safe RL**
Safe RL methods typically **learn or update a policy** (often requiring exploration) and then rely on penalties, constraints in expectation, or runtime shielding. Here, **learning never changes the admissible action set and never needs exploration**: it only updates a **belief / hypothesis set** over latent attributes and selects **inspection/escalation actions** that are themselves subject to the same DES constraints. In short: *safe RL learns what to do; this framework learns what is true (and when to ask) while the supervisor decides what may be done.*

---

# Conservative Learning-to-Update and Learning-to-Ask under DES-Constrained Structural Uncertainty

### A Safety-Preserving Uncertainty Refinement Framework for Demanufacturing Coordination

**(Manuscript draft — journal-ready structure)**

## Abstract

End-of-life (EoL) electronics demanufacturing exhibits *structural uncertainty*: inspection and partial disassembly reveal hidden conditions (e.g., stripped fasteners, adhesive failures, swollen batteries) that change the set of feasible actions and precedence relations online. Standard adaptive learning and reinforcement learning approaches are ill-suited for brownfield deployment because they can introduce new behaviors, require unsafe exploration, and are difficult to certify against PLC-level constraints. We propose a conservative learning framework embedded within a DES-constrained coordination architecture. The framework decomposes “learning” into (i) **conservative learning-to-update**: calibrated, abstaining updates that monotonically reduce a set-valued belief over latent structural attributes without expanding the admissible action set; and (ii) **learning-to-ask**: a cost-aware targeted sensing policy that acquires evidence when uncertainty blocks progress or intersects safety-critical decisions. A supervisory envelope enforces that all executed actions lie in a supervisor-enabled set, yielding a formal **non-expansion containment guarantee** independent of the learning module. We provide a problem formulation aligned with supervisory control theory (SCT), introduce conservative update and ask operators, state theoretical properties (monotonic belief refinement, escalation safety, and action-set non-expansion), and design an evaluation protocol for simulation benchmarks under partial observability and distribution shift. The result is a safety-preserving uncertainty refinement mechanism suitable for auditable industrial deployment.

**Keywords:** demanufacturing; structural uncertainty; supervisory control; selective prediction; conformal prediction; calibration; active information acquisition; safe learning; abstention.

---

## 1. Introduction

### 1.1 Motivation: uncertainty reduction is necessary—but must be bounded

EoL electronics demanufacturing operates on heterogeneous products with degraded and partially observable conditions. Unlike nominal manufacturing, feasibility is not fixed: a stripped screw can disable “unscrew” and enable “drill,” adhesive strength can invalidate non-destructive separation, and battery swelling can impose new hazard gating. These revelations change *what can be done next*, i.e., the feasible action set evolves online (Paper 1).

To achieve scalable coordination (routing, exception handling, targeted inspection), an intelligent layer must **reduce uncertainty** about latent device conditions and action feasibility. However, in brownfield facilities, PLC logic and certified safety interlocks constrain what is deployable at the actuation layer. Learning must therefore be *subordinate* to formally enforced constraints.

### 1.2 Why unconstrained adaptive learning is unsafe in structurally uncertain systems

Standard adaptive control and RL assume either (i) a fixed action structure with parametric uncertainty, or (ii) the ability to explore and optimize a policy over time. Under structural uncertainty:

* exploration can induce unsafe sequences (e.g., attempting an action whose feasibility depends on an unobserved hazard),
* learned policies may propose actions outside PLC-approved sequences,
* distribution shift is endemic (new product variants, damage modes), undermining confidence estimates,
* learning may **expand** behavior (new action sequences) beyond verified envelopes.

Hence, learning must be reframed: not “learn a better controller,” but “**refine uncertainty** and **ask for evidence** without violating constraints.”

### 1.3 Literature gap

Existing strands—selective prediction/abstention, conformal prediction, calibration under shift, active learning/VoI, inspection planning, safe RL and shielding—offer building blocks. Yet none provide a unified **update-and-ask** mechanism that:

1. **preserves externally enforced admissible action sets** (DES supervisor-enabled actions),
2. supports **abstention/escalation** as a first-class decision,
3. enables **monotonic uncertainty reduction** (in a defensible sense), and
4. integrates with **event-sourced evidence** required for auditability (Paper 2).

### 1.4 Research questions

**RQ1.** How should conservative learning be formulated so that belief refinement reduces uncertainty without expanding admissible behavior under a DES supervisor?
**RQ2.** How can calibrated uncertainty and abstention be used to decide *when not to update* and *when not to act* under distribution shift?
**RQ3.** How can learning-to-ask be posed as a cost-aware inspection policy that remains within DES constraints and produces auditable evidence traces?

### 1.5 Contributions

**C1. Conservative learning formulation under DES constraints.** We define latent attributes (\theta), a set-valued belief (B_t), and DES-aligned update/ask operators (U(\cdot)), (Q(\cdot)).
**C2. Conservative update property.** We formalize *monotonic uncertainty reduction* as set contraction (B_{t+1}\subseteq B_t) under admissible evidence, explicitly separating uncertainty refinement from behavior change.
**C3. Non-expansion theorem (containment).** We prove that, with supervisory gating, learning cannot introduce new executed actions beyond (A_{\text{sup}}(s_t)), yielding “no-new-behavior” containment independent of the learning module.
**C4. Learning-to-ask under hard constraints.** We define a cost-aware VoI trigger that selects admissible inspection actions and escalates when information is insufficient, integrating with event-sourced evidence (Paper 2).
**C5. Evaluation protocol.** We specify uncertainty regimes, baselines, metrics, and ablations targeted to demanufacturing structural uncertainty and PLC-bounded deployment.

---

## 2. Analytical Positioning within the Literature

We position our approach as **uncertainty refinement + information acquisition under hard action constraints**, contrasting it with methods that implicitly expand behavior.

### Table 1 — Paradigm-level comparison (guarantees, constraints, escalation)

| Paradigm                             | Uncertainty addressed                            | Guarantee type                                                          | Abstention / escalation                                     | Compatibility with hard action constraints                     | Typical failure mode in demanufacturing                                  |
| ------------------------------------ | ------------------------------------------------ | ----------------------------------------------------------------------- | ----------------------------------------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Selective prediction / reject option | Predictive error / confidence (epistemic)        | Risk–coverage tradeoff; monotonic selective risk under rank assumptions | Explicit abstention based on confidence thresholds          | Indirect; must be integrated with an external action filter    | Miscalibration under shift → over-commit or over-abstain                 |
| Conformal prediction                 | Predictive set uncertainty (aleatoric+epistemic) | Finite-sample marginal coverage (i.i.d.); variants for shift robustness | “Ambiguity set” outputs enable deferral when sets are large | Compatible if used only for *interpretation*; not a controller | Coverage degrades under shift unless adapted                             |
| Calibration under shift              | Confidence misalignment                          | Improves probability reliability (no direct control guarantee)          | Enables thresholding for abstention                         | Orthogonal; helps safe decision layers                         | Calibration drift → unsafe confidence thresholds                         |
| Active learning / VoI                | Model uncertainty reduction                      | Mostly heuristic; some regret/sample bounds                             | Query action replaces decision                              | Can be made compatible by restricting query set                | Queries may be infeasible/unsafe without supervisor integration          |
| Inspection planning / sensing POMDP  | Latent state uncertainty                         | Optimality in small models; approximations in practice                  | Sensing as explicit action; escalate when unresolved        | Compatible if sensing actions are in admissible set            | Intractable if not abstracted; may assume controllability absent in PLCs |
| Constrained RL / safe RL             | Policy improvement under constraints             | Often in expectation; some monotonic update or shielding guarantees     | Shielding overrides unsafe actions; human-in-loop possible  | Shielding aligns well; learning itself may still explore       | Exploration unsafe; policy updates can introduce new sequences           |

### Table 2 — Where behavior expansion occurs (and how we avoid it)

| Method family                   | Where expansion can occur                            | Why problematic under PLC/SCT                | Our restriction                                                               |
| ------------------------------- | ---------------------------------------------------- | -------------------------------------------- | ----------------------------------------------------------------------------- |
| Adaptive control                | Updated control law changes reachable behaviors      | Hard to certify post-update                  | Learning does not alter control law; supervisor fixes admissible actions      |
| RL (even safe RL)               | Exploration + policy updates change action selection | New sequences may violate certified envelope | Learning refines belief; action execution always filtered by (A_{\text{sup}}) |
| Planner with online model edits | Model edits can enable new actions/routes            | Breaks verification assumptions              | Updates only reduce uncertainty about latent attributes; no new actions       |
| Pure ML decision systems        | Confidence-based choice may bypass safety logic      | Unverifiable decision boundary               | ML outputs are *interpreted* within a gate + evidence requirements            |

**Key distinction:** Many methods treat learning as a means to *do more*. We treat learning as a means to **safely do less until evidence justifies commitment**, while preserving a formally enforced admissible envelope.

---

## 3. Problem Formulation

### 3.1 DES under structural uncertainty

Let the demanufacturing cell be a DES plant:
[
G_\theta = (X, \Sigma, \delta_\theta, x_0),
]
where (X) is the system state (product progress + resource state), (\Sigma=\Sigma_c\cup\Sigma_{uc}) is the event set (controllable/uncontrollable), and (\theta\in\Theta) encodes latent structural attributes (fastener condition, adhesive class, hazard state, missing components, etc.) that determine feasibility.

Structural uncertainty means the feasibility predicate depends on (\theta):
[
F(x,\sigma,\theta)\in{0,1}, \quad A(x,\theta)={\sigma\in\Sigma_c: F(x,\sigma,\theta)=1}.
]
The key difficulty: (A(x,\theta)) is only partially known at runtime.

### 3.2 Observation and evidence

Let (e_t) denote evidence at time (t) (sensor readings, partial disassembly outcomes, operator reports), logged by an event-sourced twin (Paper 2). Observations can be noisy and delayed, and distribution shift is expected.

### 3.3 Supervisor-enabled action set

A verified supervisor (S) operates on observed strings (P(s_t)) and induces a supervisor estimate (\hat{x}*t). The supervisor-enabled set is:
[
A*{\text{sup}}(s_t) = \Gamma_S(\hat{x}_t)\subseteq \Sigma_c,
]
the set of controllable events permitted by the supervisor under its estimate. This set encodes PLC-level admissibility (safety interlocks, sequencing logic, certification constraints).

**Execution rule (gate):** any proposed controllable event must satisfy
[
\sigma_t \in A_{\text{sup}}(s_t).
]

### 3.4 Latent attribute set and belief state

We model latent attributes as (\theta\in\Theta). We use a **set-valued belief** (credal/hypothesis set) for conservative monotonicity:
[
B_t \subseteq \Theta,
]
interpreted as “(\theta) values still consistent with admissible evidence so far.”

(Optionally, one may maintain a distribution (p_t(\theta)) *inside* (B_t) for ranking, while (B_t) provides the conservative safety/monotonicity interface.)

### 3.5 Update and ask operators

**Update operator:**
[
B_{t+1} = U(B_t, e_t).
]

**Ask operator:**
[
q_t = Q(B_t, \hat{x}*t),
]
where (q_t) is either (i) an admissible inspection action (\sigma^q_t \in A*{\text{sup}}(s_t)\cap\Sigma_q), or (ii) an escalation request to a human supervisor, or (iii) “no query.”

### 3.6 Conservative update property

We say (U) is **conservative** if it satisfies:

**(P1) Monotonic uncertainty reduction (set contraction):**
[
U(B_t,e_t)\subseteq B_t.
]

**(P2) No behavior expansion:** updates do not enlarge the admissible action set (they may restrict choices, never add):
[
\forall \hat{x}*t:\ \text{Decisions remain gated by }A*{\text{sup}}(s_t)\text{ regardless of }B_t.
]

This distinguishes:

* **Learning that changes behavior:** modifies (S), modifies event logic, or introduces new controllable events.
* **Learning that refines admissible interpretations:** shrinks (B_t), triggers sensing/escalation, and ranks choices *within* the admissible envelope.

---

## 4. Conservative Learning-to-Update

### 4.1 Uncertainty quantification and calibration interface

We assume predictors provide calibrated uncertainty about latent attributes or feasibility-relevant predicates, e.g. classifiers for fastener state or hazard signals. Since calibration can degrade under shift, we avoid “single probability → hard action” mapping. Instead we use **set-valued predictions** plus abstention.

Let (g(e_t)) be a nonconformity score (or confidence score) for a predicate about (\theta). Construct an acceptance region (e.g., via conformal or selective mechanisms) that yields a subset of plausible latent values consistent with evidence:
[
C(e_t)\subseteq \Theta.
]
Then define the conservative update:
[
B_{t+1} = U(B_t,e_t) := B_t \cap C(e_t).
]
This guarantees (B_{t+1}\subseteq B_t) by construction.

### 4.2 Abstention rule for updates

Even with calibrated sets, some evidence is too weak (noisy, shifted) to justify elimination. We therefore define an *update abstention* rule: only apply elimination when confidence/coverage conditions hold; otherwise keep (B_{t+1}=B_t) and trigger (Q).

Operationally:

* If (C(e_t)) is overly broad (low informativeness), do not “pretend we learned.”
* If (C(e_t)) would eliminate almost all hypotheses but under questionable calibration (shift detected), abstain and ask.

### 4.3 Confidence threshold logic (commit vs ask vs reroute)

Given a candidate admissible action (\sigma\in A_{\text{sup}}(s_t)), define a feasibility-support test over the belief set:
[
\text{Feasible}*{B_t}(x_t,\sigma) := \mathbf{1}\left[\exists\theta\in B_t: F(x_t,\sigma,\theta)=1\right].
]
and a robust-feasibility test:
[
\text{RobustFeasible}*{B_t}(x_t,\sigma) := \mathbf{1}\left[\forall\theta\in B_t: F(x_t,\sigma,\theta)=1\right].
]

We propose the following conservative decision logic within the admissible envelope:

1. Prefer (\sigma) with (\text{RobustFeasible}=1) (guaranteed feasible given remaining hypotheses).
2. If none exist but there are (\sigma) with (\text{Feasible}=1), trigger inspection (Q) to reduce (B_t).
3. If no feasible admissible action exists, escalate or reroute using supervisor-safe recovery actions (still within (A_{\text{sup}})).

This is **not** a new controller: it is a *ranking and deferral policy* over actions already permitted by (S).

### 4.4 Proof sketch: non-expansion of feasible action set

The learning module can only:

* shrink (B_t),
* request admissible inspection events,
* select among supervisor-enabled actions.

It cannot introduce new controllable events, nor enable events disabled by the supervisor.

---

## 5. Learning-to-Ask (Targeted Sensing Policy)

### 5.1 Admissible query actions and escalation

Let (\Sigma_q \subseteq \Sigma_c) denote sensing/inspection events (visual inspection, torque probe, battery risk scan, adhesive test). Queries are subject to the same supervisor-enabled constraints:
[
\sigma^q_t \in A_{\text{sup}}(s_t)\cap \Sigma_q.
]
If no admissible query exists, the ask operator returns an escalation request to the human supervisor.

### 5.2 Value-of-information under hard constraints

Define an uncertainty measure over the belief set, e.g.:
[
\mathcal{U}(B_t)=\log |B_t| \quad \text{(or a weighted version if (\Theta) structured)}.
]
For a query action (\sigma^q), let (E(\sigma^q)) denote the random evidence generated. Define expected uncertainty reduction:
[
\Delta(\sigma^q;B_t) = \mathbb{E}\big[\mathcal{U}(B_t)-\mathcal{U}(U(B_t,E(\sigma^q)))\big].
]
Let (c(\sigma^q)) denote inspection cost (time, labor, sensor wear, opportunity cost). The ask policy selects:
[
Q(B_t,\hat{x}*t) = \arg\max*{\sigma^q \in A_{\text{sup}}(s_t)\cap \Sigma_q} \frac{\Delta(\sigma^q;B_t)}{c(\sigma^q)}
]
subject to an escalation trigger:

* if (\max \Delta/c) is below a minimum usefulness threshold, or
* if shift indicators invalidate calibration assumptions, or
* if safety-critical ambiguity persists beyond a time/cost budget,
  then **escalate** rather than guess.

### 5.3 Integration with the event-sourced twin (Paper 2)

The twin provides:

* a time-stamped evidence ledger (e_t) (what was observed, when, and how),
* replayable traces for audit and post-incident analysis,
* a schema for “ask” events (inspection request, operator query, escalation decision).

Crucially, the ask decision is itself logged with justification: (B_t), candidate queries, expected (\Delta/c), and the reason for escalation. This supports industrial auditability.

---

## 6. Theoretical Properties

We state properties at two layers: **(i) behavioral safety via DES containment**, and **(ii) epistemic safety via conservative belief updates and escalation.**

### Assumptions

**A1 (Supervisor correctness).** The supervisor (S) is verified to satisfy safety invariants and nonblocking requirements for the modeled event structure.
**A2 (Execution gating).** The PLC layer executes only controllable events in (A_{\text{sup}}(s_t)).
**A3 (Structural uncertainty as feasibility removal).** Uncertainty may disable modeled actions (feasibility loss) but does not introduce unmodeled unsafe events at the actuation layer; otherwise escalation is required.
**A4 (Conservative update).** (U(B_t,e_t)=B_t\cap C(e_t)).

### Theorem 1 — Non-expansion containment (executed actions)

For any coordinator policy (\pi) (including learning-to-update and learning-to-ask modules), if execution is gated by (A_{\text{sup}}(s_t)), then every executed controllable event satisfies:
[
\sigma_t \in A_{\text{sup}}(s_t).
]
Consequently, the closed-loop language under (\pi) is contained in the supervisor’s closed-loop language (no-new-behavior), and supervisor-proven invariants remain preserved.

*Proof sketch.* The only way (\pi) influences the plant is by proposing controllable events. The gate enforces membership in (A_{\text{sup}}(s_t)). Therefore the sequence of executed controllable events is a subsequence of events permitted by (S) under the same observation history. □

### Proposition 1 — Monotonic uncertainty reduction (belief contraction)

If (U(B_t,e_t)=B_t\cap C(e_t)), then:
[
B_{t+1}\subseteq B_t
]
for all (t). Thus (\mathcal{U}(B_t)) is non-increasing for any monotone set-size-based uncertainty measure.

*Proof.* Immediate from set intersection. □

### Proposition 2 — Escalation safety

If the system abstains (does not commit to an uncertain interpretive update) when calibration/shift conditions are violated, and queries are limited to admissible inspection actions, then the learning layer cannot cause unsafe actions; in worst case it increases escalation or delays, but does not violate invariants.

*Reasoning.* Abstention prevents unjustified elimination that could mis-rank actions into dead-ends. Query actions are supervisor-admissible. Safety remains governed by Theorem 1. □

---

## 7. Experimental Evaluation

We propose evaluation in a controlled discrete-event simulation consistent with Paper-1 benchmark logic (evolving feasible action sets, PLC decision budgets) and Paper-2 event-sourced evidence logging.

### A. Uncertainty regimes

1. **Hidden structural damage probability**: frequency of stripped screws, adhesive failures, missing components.
2. **Sensor noise and delay**: false negatives on hazard signals, noisy torque signatures.
3. **Distribution shift**: new product variants, changed damage distribution, new adhesive types.
4. **Inspection cost variation**: time and resource penalties for different inspections.

### B. Baselines

* **B0 No learning**: fixed nominal routing/heuristics; no belief refinement; escalate on failure.
* **B1 Standard probabilistic update**: Bayesian-style updates without abstention/calibration safeguards.
* **B2 RL-based adaptive strategy**: policy learning to choose actions and inspections; optionally with shielding (to separate “learning vs safety filter”).
* **B3 Conservative update only**: our (U) without (Q).
* **B4 Ask only**: heuristic query policy without calibrated conservative update.
* **B5 Full method**: conservative update + learning-to-ask + supervisor gating.

### C. Metrics

**Uncertainty & reliability**

* Coverage (fraction of decisions made without abstention).
* Calibration error (ECE or reliability diagrams on attribute predictions; plus conformal set size).
* Belief-set size (|B_t|) trajectory (monotonicity check).

**Escalation and cost**

* Escalation frequency and time-to-resolution.
* Inspection count and total inspection cost.
* Information efficiency: (\Delta\mathcal{U}/c) aggregated.

**Operational**

* Throughput / cycle time / utilization.
* Blocking/deadlock incidence (should remain zero if supervisor is nonblocking; otherwise report “progress failures” as escalations).

**Safety**

* Invariant violations (should remain zero with gating).
* Forbidden-event attempts (proposed by coordinator but rejected by gate)—useful to show why unconstrained methods fail even if the gate saves safety.

### D. Ablations

* Remove abstention (force updates): show overconfident mis-updates under shift.
* Remove calibration robustness (use raw confidences): show mis-thresholding.
* Remove ask policy (no targeted sensing): show throughput loss due to unresolved ambiguity.
* Remove constraint enforcement (no gate): demonstrate invariant violations / new behaviors (only in simulation; never in real deployment).

---

## 8. Results (reporting template and expected causal patterns)

*(No fabricated numbers; this section is written in “ready-to-fill” journal style.)*

### 8.1 Conservative mechanisms reduce uncertainty without inducing unsafe behavior

We report that the belief-set uncertainty (|B_t|) decreases monotonically under the conservative update operator (U), while standard probabilistic updates can oscillate under noisy evidence or shift (e.g., entropy may increase, and miscalibration can drive incorrect commitments). The full method maintains stable calibration-aware abstention, resulting in fewer incorrect feasibility commitments.

**Table 3 — Uncertainty and abstention**
| Regime | Method | Coverage ↑ | Avg conformal set size ↓ | Calibration error ↓ | Monotonic (|B_t|) (%) ↑ |
|---|---|---:|---:|---:|---:|
| Shift off/on | B1 / B5 |  |  |  |  |

### 8.2 Learning-to-ask improves throughput under structural uncertainty at bounded inspection cost

Under medium/high exception rates, policies without targeted sensing either escalate excessively or thrash among admissible actions that are feasible only under subsets of (B_t). Learning-to-ask selects inspections with higher (\Delta/c), reducing time spent in ambiguous states and lowering escalation.

**Table 4 — Cost-aware inspection performance**

| Regime                      | Method       | Escalation rate ↓ | Inspection cost ↓ | Throughput impact (Δ) ↑ |
| --------------------------- | ------------ | ----------------: | ----------------: | ----------------------: |
| High damage + noisy sensors | B0 / B3 / B5 |                   |                   |                         |

### 8.3 Unconstrained learning violates containment unless gated (and still wastes effort)

When constraint enforcement is removed (simulation-only), RL-based strategies can execute sequences that violate safety invariants under partial observability. With gating restored, invariants remain preserved, but RL may exhibit high rates of **forbidden-event proposals**, indicating mismatch with PLC-admissible structure and wasted decision budget.

**Figure concept:** forbidden proposals vs. shift severity, showing advantage of “interpretation refinement” over “policy learning.”

---

## 9. Discussion

### 9.1 Conservatism vs performance

Conservatism trades throughput for certainty: robust-feasible actions may be fewer, leading to more inspections or escalations. The key engineering lever is **where to be conservative**:

* invariants remain hard-constrained by (S),
* feasibility and throughput are optimized by (Q) and ranking, not by expanding behavior.

### 9.2 Scalability limits

Set-valued beliefs can be large if (\Theta) is combinatorial. Practical deployment requires structured factorization of (\theta) (attributes with local influence on feasibility) and incremental elimination based on evidence. Event-sourced traces (Paper 2) help debug and compact (\Theta) via empirical exception libraries.

### 9.3 Dependence on calibration quality and shift detection

Our framework is intentionally *robust to imperfect calibration* by supporting abstention and escalation rather than forced commitment. However, aggressive elimination relies on trustworthy coverage guarantees; under severe shift, the framework should default to “ask” or safe fallbacks.

### 9.4 Interaction with semantic mediation (Paper 4)

A bounded semantic module can propose high-level intents (request sensing, reroute, escalate), but should not directly choose actions. Our conservative update-and-ask layer provides a **typed, auditable interface**: the LLM may suggest *which uncertainty to resolve*, while (Q) enforces admissible inspection actions and (S) enforces execution constraints.

### 9.5 Generalization beyond demanufacturing

Any CPS where feasible actions evolve with hidden structure (repair, maintenance, remanufacturing, field robotics with changing affordances) can use the same pattern:
**verified envelope + conservative belief refinement + admissible information acquisition.**

---

## 10. Conclusion

We proposed a conservative learning framework for demanufacturing under structural uncertainty, embedded within a DES-constrained coordination architecture. The central principle is **safety-preserving uncertainty refinement**: learning updates only shrink a set-valued belief over latent attributes and triggers targeted sensing or escalation when evidence is insufficient. A verified DES supervisor enforces admissible action sets at runtime, yielding a formal **non-expansion containment guarantee** independent of the learning module. This reframes “AI integration” for brownfield industrial systems: not as adding new behaviors, but as making uncertainty explicit, auditable, and resolvable—without compromising certified constraints.

---

## References (indicative; replace with your BibTeX/IEEE entries)

* Supervisory control of DES (foundational SCT).
* Selective prediction / reject-option learning and risk–coverage theory.
* Conformal prediction (classical split conformal; Mondrian/weighted variants).
* Coverage under distribution shift / pseudo-calibrated conformal methods.
* Calibration methods and calibration-under-shift analyses.
* Active learning with safety constraints (constrained bandits).
* Cost-aware feature/label acquisition (e.g., (\mu)POCA / cost-aware AL).
* Shielding under partial observability; safe RL surveys; Lyapunov/constrained policy optimization.
* Self-querying / structured “ask” planning (SQ-BCP-style targeted queries).
