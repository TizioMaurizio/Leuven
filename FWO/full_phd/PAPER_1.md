
## Title

**Structural Uncertainty in End-of-Life Electronics Demanufacturing Coordination: Formalization, Containment Guarantees, and a Benchmark for Evolving Feasible Action Sets**

## Abstract

End-of-life (EoL) electronics demanufacturing is dominated by *structural uncertainty*: during execution, inspection and partial disassembly reveal hidden fasteners, adhesive failures, missing components, or hazard-critical conditions (e.g., battery swelling) that can **change the set of feasible actions and precedence relations**. This breaks dominant automation paradigms that assume a fixed task graph with parametric noise. This paper makes three contributions. First, we formalize structural uncertainty as uncertainty over the *structure* of the coordination problem—encoded as an exogenous variable that induces an evolving feasible action set (A(x,\omega)) and, equivalently, an evolving transition structure of a discrete-event plant. Second, we propose a containment framework for brownfield settings: a high-level coordination layer may compute recommendations under uncertainty, but a supervisory envelope (implemented on PLC-executed event logic) filters decisions through a **supervisor-enabled set**, yielding a “no-new-behavior” containment property relative to the verified supervisor. Third, we introduce **HoDeSU-Bench**, a reusable benchmark specification for evaluating coordination architectures under evolving feasible action sets, with parameterized regimes (hidden damage probability, inspection noise, exception frequency, hazard gating strictness, resource unreliability, and PLC decision-budget constraints) and metrics that simultaneously capture throughput, blocking/nonblocking, invariant violations, and escalation/recovery behavior. The paper closes with an experimental protocol and reporting template to isolate structural uncertainty effects and support reproducible comparisons across holonic/multi-agent, DES/SCT-based, Petri-net, and POMDP/RL-inspired approaches.

## Index Terms

Demanufacturing, end-of-life electronics, structural uncertainty, discrete-event systems, supervisory control, holonic manufacturing systems, Petri nets, partial observability, benchmarks.

---

## I. Introduction

EoL electronics demanufacturing (selective or complete disassembly for reuse, remanufacture, recycling, and safe disposal) operates on heterogeneous product streams and degraded, non-nominal devices. At intake, the system often lacks reliable knowledge of device configuration, internal condition, and hazards; many conditions are only revealed through inspection and partial disassembly. Critically, these revelations can change **what can be done next**—for example, a stripped screw disables an “unscrew” operation and enables a “drill” fallback; adhesive strength can invalidate a non-destructive removal; a swollen battery can impose new safety gating actions and forbid operations that might puncture the cell. This phenomenon is *structural uncertainty*: uncertainty that changes the *structure* of feasible actions and constraints during execution, not merely the parameters of known actions (such as task durations). 

### A. Why existing automation paradigms fail

Much of manufacturing automation—and many disassembly planning approaches—assume a fixed product model (task graph, precedence constraints, and resource capabilities), then account for uncertainty mainly via parametric variation (e.g., stochastic task times, success probabilities). Under structural uncertainty, however, a plan can become invalid because the action set and precedence relations evolve online. Consequently, methods that optimize over a fixed structure (even robustly) may exhibit brittle execution-time behavior: frequent replanning, deadlock, unsafe attempts, or excessive human escalation. 

At the same time, brownfield demanufacturing facilities impose **PLC-bounded** constraints: safety interlocks, legacy sequencing logic, and certification requirements limit what may be deployed at the lowest control level. Thus, even if high-capacity planners (e.g., POMDP or deep RL) can reason about latent conditions, they must integrate with supervisory envelopes that preserve safety and nonblocking behavior and can execute at PLC cycle times. 

### B. Gap revealed by the literature

Your review synthesizes a fragmented landscape: (i) disassembly planning uses graphs, AND/OR representations, and Petri nets; (ii) DES/SCT provides strong safety/nonblocking guarantees but typically presumes a fixed plant structure; (iii) POMDP/RL naturally represent partial observability and action availability but rarely provide hard guarantees; and (iv) holonic/multi-agent architectures provide adaptation and reconfiguration but need a correctness envelope and deployability path. Across these threads, two hard gaps persist: 

1. **Formalizing and benchmarking execution-time coordination when feasibility itself evolves**, especially under PLC constraints.
2. **Standardizing exception libraries** that mutate feasible action sets (rather than only modeling probabilities on fixed transitions).

### C. Research questions

This paper addresses the following research questions (RQs):

* **RQ1 (Formalization):** How should structural uncertainty be defined for demanufacturing coordination so that it clearly distinguishes (i) static DES, (ii) DES under parametric disturbance, and (iii) DES under structural evolution?
* **RQ2 (Guarantees under integration):** Under what conditions can we integrate high-level coordination/planning with PLC-level supervisory control so that safety and nonblocking guarantees are preserved despite evolving feasible action sets?
* **RQ3 (Benchmarking):** What benchmark structure and experimental protocol enable reproducible comparison of coordination architectures under structural uncertainty, including deployability constraints?

### D. Contributions

**C1. Formal definition and modeling interface.** We formalize structural uncertainty for EoL demanufacturing as uncertainty over the *feasible action set and transition structure*, represented by (A(x,\omega)) and an induced family of DES plants (G_\omega). We explicitly separate static DES, parametric disturbance, and structural evolution.

**C2. Containment framework for PLC-bounded deployment.** We propose a layered architecture where a high-level coordination layer (holonic/multi-agent or optimizer) proposes actions, while a supervisory envelope enforces admissibility by intersecting recommendations with the **supervisor-enabled set** derived from a verified DES supervisor, yielding a “no-new-behavior” containment property relative to the supervisor.

**C3. HoDeSU-Bench benchmark specification.** We introduce a reusable benchmark definition for *Holonic Demanufacturing under Structural Uncertainty*, with parameterized regimes/knobs, scenario generation, metrics, baseline policy classes, and an experimental protocol designed to isolate the effect of evolving feasible action sets.

**C4. Reporting template and failure-mode taxonomy.** We define reporting artifacts (tables/plots) that expose causal failure modes—plan invalidation, blocking, unsafe attempts, and escalation patterns—rather than only aggregate throughput.

---

## II. Related Work (Analytical Synthesis)

We organize related work by modeling paradigm and emphasize how each treats: (i) structural vs. parametric uncertainty, (ii) partial observability, (iii) evolving constraints/action availability, and (iv) runtime guarantees. This synthesis is grounded in the review and its annotated bibliography. 

### A. Disassembly planning and graph/constraint models

Disassembly sequence planning frequently uses precedence graphs, AND/OR graphs, interference matrices, and hybrid representations. These excel at representing alternative paths and precedence, and many works incorporate parametric uncertainty via stochastic task times, success probabilities, or fuzzy parameters. However, most formulations implicitly assume that the underlying action set and constraints remain valid, or that replanning can be done without affecting correctness envelopes. Your review highlights the “online structure refinement” pattern (e.g., interference models updated online) as a bridge toward structural uncertainty. 

### B. Petri nets for sequencing and robustness analysis

Petri nets naturally model concurrency and asynchronous processes, can generate feasible sequences via reachability, and allow structural analysis (liveness, boundedness, reversibility under restrictions). Adaptive Petri-net planning is particularly relevant: uncertainty in product structure and conditions can change termination goals and require plan adaptation; some approaches update transition probabilities during execution. Petri nets also support robustness/fault tolerance analysis by embedding failures and studying tolerable failure modes. 

### C. DES and supervisory control (SCT) under partial observation and uncertainty

SCT provides a strong correctness framework: supervisors disable controllable events to satisfy specifications and are naturally aligned with safety (“nothing bad happens”) and nonblocking/liveness (“something good eventually happens”) requirements. Modern threads address partial observation, modular/distributed control, and uncertain/unknown plant models. Yet a core limitation remains: classical SCT assumes a fixed event structure and plant model; structural uncertainty implies that the plant structure may evolve or only be partially known, complicating guarantees unless robust or learning-based variants are used. 

### D. POMDPs, belief-state planning, and RL with changing action sets

POMDP formulations explicitly represent latent EoL deviations and allow policies contingent on observations, naturally capturing evolving feasibility as beliefs update. However, exact POMDP planning is rarely compatible with PLC-cycle constraints without heavy abstraction. RL literature on stochastic/changing action sets formalizes the phenomenon that not all actions are available at all times; naïve RL can diverge unless availability is modeled. Yet RL typically lacks hard safety and nonblocking guarantees without an external envelope. 

### E. Holonic/multi-agent architectures (PROSA/ADACOR and beyond)

Holonic architectures support distributed decision making, reconfiguration, and disturbance responsiveness. They are attractive for demanufacturing because adaptation is a first-class requirement. However, flexibility can conflict with formal correctness unless holonic decisions are constrained by a verified envelope (e.g., supervisory constraints), and deployability depends on integration with PLC logic and limited sensing. 

### F. Where guarantees break under evolving feasible action sets

Table I summarizes the main breakpoints.

**Table I — Paradigm comparison under structural uncertainty (summary)**

| Paradigm                  | Structural vs parametric                      | Partial observability                    | Evolving feasible action sets                                   | Typical guarantees                                    | Breakpoint under structural evolution                                          |
| ------------------------- | --------------------------------------------- | ---------------------------------------- | --------------------------------------------------------------- | ----------------------------------------------------- | ------------------------------------------------------------------------------ |
| Graph/AND-OR/constraints  | Mostly parametric; some online refinement     | Limited unless coupled to online updates | Often handled by replanning; rarely formalized                  | Optimality (w.r.t. model), feasibility (offline)      | Plans become invalid; no system-level safety/nonblocking guarantee             |
| Petri nets                | Can encode structure and adaptation           | Possible via observers/augmented nets    | Can model changing success/termination; still needs integration | Structural properties; reachability-based feasibility | Runtime adaptation may violate plant-wide safety envelopes without supervision |
| DES/SCT                   | Strong correctness on fixed plant             | Mature partial-observation theory        | Structural evolution not native                                 | Safety/nonblocking/language constraints               | Plant/model mismatch; uncertain enabled events break assumptions               |
| POMDP                     | Natural structural deviations via latent vars | Native belief representation             | Native via beliefs and action availability                      | Expected reward; sometimes bounded safety             | Computational/deployability limits; no hard nonblocking without envelope       |
| RL (changing action sets) | Models availability                           | Can handle via POMDP-RL                  | Native to SAS-MDP formulations                                  | Empirical performance                                 | Safety and liveness not guaranteed without external constraint layer           |
| Holonic/MAS               | High adaptation                               | Depends on sensing and shared state      | Can reconfigure & negotiate                                     | Architectural agility                                 | Correctness/deployability depend on integration with verified supervisor       |

---

## III. Problem Formulation

### A. System model (DES with product–resource coupling)

We model a demanufacturing cell/line as a discrete-event system with:

* **Plant state:** (x \in X), combining product state (disassembly progress, latent condition flags) and resource state (station availability, tool readiness).
* **Event set:** (\Sigma = \Sigma_c \cup \Sigma_{uc}) partitioned into controllable and uncontrollable events (e.g., “start unscrew” controllable; “tool jam” uncontrollable).
* **Observation:** (\Sigma = \Sigma_o \cup \Sigma_{uo}) partitioned into observable/unobservable events.
* **Nominal plant:** (G_0 = (X, \Sigma, \delta_0, x_0)) where (\delta_0: X \times \Sigma \to X) is a partial transition function.

A **specification** is given by safety invariants and progress requirements. For instance:

* Safety invariant (I(x) = 1) indicates hazard-safe conditions (e.g., “no cutting before battery-safe state”).
* Nonblocking/progress requirement: from any reachable state, the system can reach a marked set (X_m) (e.g., “battery removed and device routed to correct stream”) without deadlock.

### B. Structural uncertainty: evolving feasibility and evolving transitions

Let (\omega \in \Omega) denote an exogenous uncertainty variable capturing hidden structure and condition (fastener state, adhesive strength class, missing component, hazard class, etc.). Structural uncertainty is represented via a **feasibility predicate**
[
F(x,\sigma,\omega) \in {0,1}
]
that determines whether event (\sigma) is feasible at state (x) under realization (\omega).

Define the **evolving feasible action set**
[
A(x,\omega) \triangleq {\sigma \in \Sigma_c : F(x,\sigma,\omega)=1}.
]
Structural uncertainty implies that (A(x,\omega)) may be unknown a priori and may change as (\omega) is revealed or evolves (e.g., due to failures). 

Equivalently, structural uncertainty induces a **family of plants**
[
G_\omega = (X,\Sigma,\delta_\omega,x_0),
]
where (\delta_\omega(x,\sigma)) is defined iff (F(x,\sigma,\omega)=1) and the event outcome is feasible (including stochastic outcomes if desired). The key distinction is that uncertainty affects the **domain** of feasible transitions (structure), not only their costs or probabilities.

### C. Parametric disturbance vs structural evolution

We distinguish three cases:

1. **Static DES (no uncertainty):** (\delta_\omega \equiv \delta_0), feasibility fixed.
2. **Parametric disturbance:** structure fixed, but transition attributes (time/cost/probability) are uncertain. Feasible action set (A(x)) is fixed.
3. **Structural evolution:** feasibility predicate (F(x,\sigma,\omega)) changes the domain of feasible events, so (A(x,\omega)) evolves.

This paper focuses on (3).

### D. Supervisor-enabled set under partial observation

A supervisor observes (P(s)), the projection of an event string (s \in \Sigma^*) onto observable events. Let (x = \delta_\omega(x_0,s)) be the (possibly unobserved) plant state.

Let (\hat{x}) denote an **estimate** (observer state or belief-support) computed from observations. A supervisor (S) induces an **enabled set** of controllable events:
[
\Gamma_S(\hat{x}) \subseteq \Sigma_c.
]
Intuitively, (\Gamma_S(\hat{x})) are actions permitted by the verified supervisor given what is known (or estimated) about the state.

### E. Definition (Structural uncertainty)

**Definition 1 (Structural uncertainty).** A demanufacturing coordination problem exhibits structural uncertainty if there exists a nontrivial (\Omega) and feasibility predicate (F) such that, for some reachable states (x), the feasible controllable event set (A(x,\omega)) depends on (\omega) and is not known with certainty at planning time, and may change during execution as evidence about (\omega) is acquired or as failure events modify feasibility.

This definition matches the operational characterization in your review and makes the modeling boundary explicit: uncertainty changes *what is feasible*, not only *how long it takes* or *how likely it succeeds*. 

---

## IV. Containment Framework and Theoretical Guarantees

### A. Architecture: coordination under a supervisory envelope

We consider a two-layer architecture consistent with PLC-bounded constraints:

* **Coordination layer (high level):** selects tasks, routes products, and proposes next controllable action(s) using a holonic/MAS policy, optimization, heuristic, or learning-based policy operating on estimated state (\hat{x}) and evidence.
* **Supervisory envelope (PLC level):** executes verified event logic and enforces admissibility by filtering proposed actions through (\Gamma_S(\hat{x})) and safety constraints.

**Decision gate (admissibility filter).** Let the coordinator propose a set (U(\hat{x}) \subseteq \Sigma_c) (possibly singleton). The gate outputs:
[
U_{\text{exec}}(\hat{x}) = U(\hat{x}) \cap \Gamma_S(\hat{x}).
]
If (U_{\text{exec}}(\hat{x}) = \emptyset), the system triggers a structured fallback: request sensing, reroute, or escalate to human supervisor, depending on the benchmark policy. 

### B. Containment properties

We formalize two properties: (i) invariant preservation and (ii) no-new-behavior containment relative to the supervisor.

#### Proposition 1 (Safety invariant preservation under admissible control)

Assume:

* (A1) The supervisory controller (S) is verified (for the nominal model) to enforce a safety invariant (I(x)=1) for all reachable states under enabled events (\Gamma_S(\hat{x})).
* (A2) The PLC execution layer only executes controllable events selected from (U_{\text{exec}}(\hat{x}) \subseteq \Gamma_S(\hat{x})), and uncontrollable events evolve according to the plant.

Then, for any coordination policy that proposes (U(\hat{x})), the executed closed-loop behavior preserves the safety invariant (I) (relative to the supervisor’s state estimate and plant assumptions).

**Proof sketch.** The coordinator can only influence the plant via controllable events. Because the gate enforces that any executed controllable event belongs to (\Gamma_S(\hat{x})), the set of controllable events applied is a subset of those allowed by the verified supervisor. Therefore, the closed-loop reachable set under the coordinator is a subset of the closed-loop reachable set under (S) alone. By (A1), all states in the latter satisfy (I); thus all states in the former satisfy (I). ∎

#### Proposition 2 (No-new-behavior containment)

Let (L(S/G_0)) be the closed-loop language of supervisor (S) controlling nominal plant (G_0). Let (L(\pi \circ S / G_0)) be the closed-loop language when an additional coordination policy (\pi) chooses among enabled events but is filtered by (\Gamma_S) as above. Then:
[
L(\pi \circ S / G_0) \subseteq L(S/G_0).
]

**Proof sketch.** The only difference is the selection rule among controllable events; the set of enabled controllable events at any supervisor estimate (\hat{x}) is unchanged and remains (\Gamma_S(\hat{x})). Therefore any event string producible under (\pi) is also producible under (S) with some choice function. ∎

### C. What this does and does not guarantee under structural uncertainty

The propositions above are **containment results relative to the supervisor model and admissibility constraints**. Under structural uncertainty, the physical plant is (G_\omega), not (G_0). If structural uncertainty only **removes feasibility** (disables some events) but does not introduce unmodeled events, then the envelope remains meaningful: the supervisor continues to forbid unsafe actions, and the coordinator’s proposals remain bounded. However, if structural uncertainty introduces **unmodeled behaviors** (e.g., a hazardous failure mode absent from (\Sigma) or (\delta_0)), then guarantees require either (i) robust/learning-based supervisory methods, (ii) conservative modeling that includes plausible recovery actions and hazards, or (iii) runtime escalation. This motivates why the benchmark must explicitly model exception libraries and observation regimes. 

---

## V. HoDeSU-Bench: Benchmark Design

### A. Benchmark objective

HoDeSU-Bench evaluates execution-time coordination and control policies for EoL electronics demanufacturing when **feasible action sets and precedence constraints evolve** due to hidden structure, failures, and hazard constraints, under **PLC-bounded deployment constraints**. 

### B. Entities and environment

**Products.** Phone-class and laptop-class devices (and optionally PCB modules), each with a nominal disassembly graph annotated with tools/skills.

**Resources.** Human station(s), robot station(s), inspection station(s), hazard-handling station(s) (e.g., battery-safe removal), with availability and failure modes.

**Control layers.** PLC-level supervisor (S) and high-level coordinator (\pi) (central dispatcher or holonic/MAS).

### C. State, observation, and feasibility

**Latent condition (\omega).** Encodes fastener conditions, adhesive strength class, missing components, deformation/corrosion, hazard class.

**Observations.** Limited sensors: visibility/accessibility, torque/force signatures, “battery risk” signal with false negatives, delayed signals; mapped to estimator (\hat{x}).

**Feasible actions.** State- and (\omega)-dependent:

* “unscrew” unavailable if stripped;
* “cut” available only after battery-safe state;
* “pry” forbidden if hazard risk high.

Formally: (A(x,\omega)) as in Section III.

### D. Uncertainty regimes and knobs

HoDeSU-Bench exposes knobs to separate parametric and structural effects:

* **Variant mixture:** product-model mismatch frequency.
* **Interference severity:** controls distributions in online interference models.
* **Exception frequency:** probabilities of stripped screw, missing fastener, stuck adhesive.
* **Observation quality:** noise, missed detections, delays.
* **Hazard strictness:** gating severity (battery-safe prerequisite).
* **Resource unreliability:** robot/tool failures.
* **PLC budget:** decision latency and policy-size constraints.

(These knobs and their intended metric impacts are defined in your review and are adopted verbatim as the benchmark specification core.) 

### E. Scenario generator and evaluation loop

Each episode:

1. Sample product instance (nominal + latent deviations (\omega)).
2. Initialize (\hat{x}) via inspection.
3. Coordinator allocates tasks/resources.
4. PLC supervisor executes admissible events; gate filters coordinator proposals.
5. Environment returns outcomes and observations; feasibility changes may occur.
6. Terminate when target components extracted, hazard-safe terminal state reached, or abort.
7. Log traces for post-analysis.

### F. Metrics

Metrics must reflect both performance and correctness:

**Correctness & safety**

* Safety invariant violations (count, severity).
* Near-miss hazard events.
* Deadlock/livelock occurrences (nonblocking violations).
* Forbidden-event attempts (blocked by gate).

**Adaptation under structural uncertainty**

* Plan invalidations.
* Number of feasibility-set changes.
* Recovery success after exceptions.
* Belief calibration error (if belief models used).

**Operational performance**

* Throughput, cycle time, utilization.
* Rework time, delay cost.

**Deployability**

* Decision latency vs PLC scan constraints.
* Policy footprint (e.g., number of branches, macro-actions).
* Communication load between coordinator and PLC.

### G. Baseline policy classes

HoDeSU-Bench includes paired baselines: (A) decision policy and (B) architecture.

**Decision policy baselines**

* Fixed nominal deterministic plan (no online updates).
* Adaptive Petri-net planner with updated success probabilities.
* Online interference-updating planner.
* POMDP-lite receding-horizon policy.
* SAS-aware RL vs naïve RL (action availability).
* Safe RL hybrid: RL proposes; supervisor filters.

**Architecture baselines**

* Central dispatcher (fixed priorities).
* PROSA-style holonic control.
* ADACOR-style holonic control.
* Holonic planning with evolving roles/actions stress test.

All are drawn from your synthesis and are included to directly test “coordination under evolving feasible action sets with PLC-bounded execution.” 

---

## VI. Experimental Protocol (Reproducible and Causal)

### A. Simulation environment

HoDeSU-Bench is intended to be instantiated in a discrete-event simulation where:

* Events correspond to skill primitives (unscrew, cut, pry, inspect) and resource transitions.
* Observation models generate sensor outputs with controlled noise/delay.
* Latent deviations (\omega) affect feasibility predicate (F) and possibly outcome distributions.

### B. Controlled variation factors

To isolate structural uncertainty effects:

* Vary **structural knobs** (exception frequency, hazard strictness, variant mixture) while holding parametric noise fixed.
* Then vary parametric noise (task time variance) while holding structural knobs fixed.
* Use mixed regimes to measure interaction terms.

Recommended design:

* Fractional factorial or Latin hypercube over knob ranges.
* (N) random seeds per condition (e.g., (N \ge 30)) for stable CIs.

### C. Statistical comparison

Report:

* Mean ± 95% bootstrap CI for each metric.
* Nonparametric tests (e.g., paired permutation tests) for policy comparisons under identical seeds.
* Effect sizes (Cliff’s delta) for robustness.

### D. Sensitivity and ablation

Ablate:

* Gate on/off (to demonstrate containment and trade-offs).
* Observation quality (to quantify partial observability burden).
* PLC budget constraints (to quantify deployability-performance frontier).
* Exception library richness (to quantify structural uncertainty difficulty).

### E. Reporting template

At minimum, report:

* **Table A:** throughput/cycle time/utilization across regimes.
* **Table B:** safety & nonblocking metrics across regimes.
* **Table C:** escalation/recovery metrics across regimes.
* **Figure 1:** performance vs exception frequency (robustness curve).
* **Figure 2:** violations vs hazard strictness.
* **Figure 3:** deployability frontier (latency/footprint vs performance).

---

## VII. Results (Placeholders and Expected Structure)

> **Note:** This section is structured as it should appear in a submission, but values are placeholders until experiments are run.

### A. Overall performance

**Table II** compares throughput and cycle time across baseline architectures under low/medium/high exception rates.

### B. Correctness and safety envelope effectiveness

**Table III** reports invariant violations and blocking incidents. We expect:

* Policies without supervisory filtering exhibit occasional forbidden attempts and higher violation risk under noisy observations.
* The gate eliminates forbidden-event executions and reduces safety violations, but may increase escalation rate when feasibility collapses.

### C. Robustness under structural uncertainty

**Figure 1** plots throughput vs exception frequency, showing:

* Steeper degradation for fixed-plan baselines.
* Smoother degradation for adaptive Petri-net/IPM baselines.
* Potentially competitive performance for SAS-aware RL, but only when filtered by the supervisory envelope for correctness.

### D. Failure modes

We report a qualitative failure taxonomy:

* **FM1:** plan invalidation cascades (replanning thrash).
* **FM2:** deadlock due to resource contention under unexpected precedence changes.
* **FM3:** unsafe attempt under misestimated hazard state (mitigated by envelope).
* **FM4:** excessive escalation under strict hazard gating and low observability.

---

## VIII. Discussion

### A. Implications for DES/SCT

Structural uncertainty stresses the classical SCT assumption of a fixed plant structure. The containment approach reframes the integration problem: rather than requiring the coordinator to be formally verified, one can verify the supervisory envelope and constrain all high-level decisions to remain within it. This shifts formal effort toward: (i) adequate modeling of plausible events/recovery actions, and (ii) state estimation under partial observation.

### B. Implications for holonic/multi-agent control

Holonic control’s strength is adaptation and distributed coordination, but without a correctness envelope it risks unpredictable behavior. HoDeSU-Bench and the admissibility filter provide a way to quantify: (i) how much adaptation matters under structural uncertainty, and (ii) how adaptation interacts with deployability and PLC constraints.

### C. Practical implications for demanufacturing

The benchmark explicitly includes PLC budget constraints and limited sensing—conditions common in brownfield facilities. The key practical takeaway is that structural uncertainty should be treated as “feasibility evolution,” requiring (i) targeted sensing policies, (ii) standardized exception libraries, and (iii) supervisory containment to prevent unsafe/unverifiable behavior.

### D. Boundary conditions and transferability

The proposed formalization and benchmark structure transfer to other CPS domains where feasible actions evolve online: maintenance and repair lines, remanufacturing, field robotics with changing affordances, and safety-critical reconfiguration. Boundary conditions include unmodeled hazards/events and extreme partial observability, which require either more conservative envelopes or higher escalation.

---

## IX. Conclusion

This paper formalized structural uncertainty in EoL electronics demanufacturing as uncertainty over the structure of feasibility and transitions, captured by an evolving feasible action set (A(x,\omega)). We proposed a PLC-compatible containment framework in which high-level coordination decisions are filtered through a supervisor-enabled set, yielding a no-new-behavior property relative to a verified supervisory envelope. Finally, we introduced HoDeSU-Bench, a benchmark specification with parameterized regimes, metrics, baselines, and experimental protocol designed to isolate structural uncertainty effects and support reproducible comparisons across coordination paradigms. Future work will implement the benchmark, instantiate representative phone/laptop scenarios, and report comparative results and statistically grounded robustness trends.

---

## References (draft placeholders)

> **Instruction:** Convert the URLs/titles already listed in your review into BibTeX (or IEEE references) and replace these placeholders.

* [R1] Foundational SCT reference (Ramadge & Wonham, 1987) — supervisory control of DES.
* [R2] PROSA reference architecture (1998).
* [R3] ADACOR holonic architecture (2006).
* [R4] Adaptive disassembly planning with uncertain structure (1999).
* [R5] Petri net disassembly planning from CAD + structural properties (2001).
* [R6] Interference probability matrix with online update (2021).
* [R7] CAD→POMDP disassembly formulation (2025).
* [R8] RAISE phone disassembly testbed (2025).
* [R9] PLC/DES implementation and IEC 61131-3 code generation (2002, 2005).
  (All of these are already enumerated in your review document.) 
