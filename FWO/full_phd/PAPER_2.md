## Pre-writing

### Core architectural gap (5–6 lines)

Most manufacturing “digital twins” are either **state-overwrite dashboards** (monitoring shadows) or **offline replicas** (simulation models). They do not preserve *what was known when* and cannot deterministically replay the sequence of observations, inferences, and actions that produced a coordination decision. Under **partial observability** and **structural uncertainty** (feasible actions evolving during execution), this erases the evidentiary basis needed for safe exception handling and post-hoc accountability. The literature also rarely connects twin state to a **formal admissible action set** enforced by PLC/SCT-style supervision, leaving the twin’s recommendations weakly grounded in verified control constraints.

### Three strongest defensible claims

1. **Deterministic replay + bitemporal belief:** An event-sourced twin that logs *observations, inferences, and executed actions* can reproduce past twin state and “what we believed then” exactly, enabling reproducible debugging and audit-grade accountability. 
2. **Evidence-grounded state:** If every state attribute carries provenance pointers to evidence events plus confidence/freshness metadata, then any decision can be traced to a minimal supporting evidence set (or to an explicit “unknown” declaration). ([National Academies][1])
3. **DES-consistent decision interface:** If all twin-originating recommendations are compiled into DES events and intersected with the **supervisor-enabled set** before execution, then the twin cannot introduce behavior outside the verified supervisory envelope (a containment-by-construction interface). ([ScienceDirect][2])

### What this twin guarantees that conventional twins do not

* **Replayable coordination state**: reconstructs *exactly* the twin state, uncertainty, and evidence available at decision time (not just the latest overwritten state).
* **Decision-to-evidence traceability**: every recommended/approved action is linked to the evidence and inference steps that justified it.
* **Control-grounded admissibility**: recommendations are *constrained* to DES/SCT admissible events via a supervisor interface, rather than being “best effort” analytics. ([ScienceDirect][3])

---

# Event-Sourced, Evidence-Grounded Digital Twin for Demanufacturing under Partial Observability

## Abstract

End-of-life (EoL) electronics demanufacturing operates under partial observability and structural uncertainty: device configuration, damage, and hazards are only partially known at intake and are progressively revealed during inspection and disassembly, causing feasible actions to change online. Conventional digital twins—typically monitoring dashboards or simulation replicas—overwrite state and lose the evidentiary history needed for execution-time coordination, auditability, and root-cause analysis. This paper proposes an **event-sourced, evidence-grounded digital twin (EEDT)** architecture tailored to demanufacturing and other PLC-constrained cyber-physical production systems. The EEDT records immutable, time-stamped events capturing observations, inferred belief updates, action proposals, admissibility checks, and executed plant events. State is materialized by deterministic replay, while each state attribute carries provenance links, confidence, and freshness metadata. We formalize architectural requirements derived from structural uncertainty in discrete-event control, define key properties (deterministic replay, trace completeness, evidence-grounded decisions, and DES-consistent admissibility), and provide an experimental protocol and metrics for evaluating auditability and replay fidelity. The proposed architecture differentiates itself from monitoring-only and simulation-only twins by (i) preserving “what was believed when,” (ii) enabling trace-linked exception handling, and (iii) grounding decision support in a supervisor-enabled action set.

**Index Terms:** Digital twins, event sourcing, provenance, auditability, partial observability, demanufacturing, discrete-event systems, supervisory control, PLC integration.

---

## 1. Introduction

### 1.1 Coordination under partial observability and evolving feasibility

In EoL electronics demanufacturing, coordination decisions (routing, task selection, exception handling) are made while critical conditions—hidden fasteners, adhesive failures, missing components, swollen batteries—are unknown at intake and revealed only through inspection and partial disassembly. Structural uncertainty is not merely noisy parameters; it changes feasibility and constraints during execution. In discrete-event terms, the set of controllable events that are feasible at a state may evolve as evidence is acquired.

### 1.2 Why conventional digital twins fail here

Many industrial “digital twins” function as (i) monitoring shadows that maintain a current snapshot, or (ii) simulation replicas used offline. Systematic reviews note persistent confusion between simulation models and true twins, and that many implementations use only a subset of twin capabilities. ([CoLab][4])
For demanufacturing coordination, overwriting state is fatal: the system must answer questions like *“What evidence supported choosing drill instead of unscrew at 10:43:12?”* and *“What did we believe about battery risk at the time?”* This requires bitemporal traceability and deterministic replay—capabilities absent in most state-overwrite designs.

### 1.3 Gap: trace-linked, uncertainty-aware, replayable twins connected to DES supervision

Three gaps recur in the literature:

1. **Trace gaps:** typical historian/SCADA logs are incomplete and do not encode semantic causality between observations, inferred states, and decisions.
2. **Uncertainty gaps:** trustworthy twins must report confidence and continuously manage VVUQ; yet many twins do not propagate uncertainty into operational decisions. ([National Academies][1])
3. **Control grounding gaps:** PLC reality shapes architectures, but is under-treated; moreover, most twins are not formally coupled to admissible action sets enforced by supervisory control. ([ScienceDirect][2])

### 1.4 Research questions

* **RQ1:** What architectural requirements must a digital twin satisfy to support coordination under partial observability and structural uncertainty in PLC-constrained demanufacturing?
* **RQ2:** How can a twin provide deterministic replay and audit-grade evidence lineage while representing uncertainty explicitly?
* **RQ3:** How can the twin be interfaced with a DES supervisor so that runtime recommendations remain within the supervisor-enabled action set?

### 1.5 Contributions

**C1.** A precise, layered **event-sourced, evidence-grounded digital twin (EEDT)** architecture for demanufacturing, differentiating monitoring-only and simulation-only twins. ([ScienceDirect][3])
**C2.** A formal event/evidence/uncertainty model with **bitemporal belief versioning** and attribute-level provenance. ([National Academies][1])
**C3.** A **DES-consistent supervisor interface** that constrains recommendations via intersection with a supervisor-enabled set, enabling containment-by-construction. ([ScienceDirect][3])
**C4.** Testable properties and an evaluation protocol with metrics for replay determinism, trace completeness, evidence-grounded decisions, and overhead.

---

## 2. Analytical Review of Digital Twin Architectures

We synthesize four families, emphasizing state representation, traceability, provenance, replay, and control integration.

### 2.1 Monitoring twins (Digital Shadows)

Monitoring twins ingest telemetry and present a current state. Kritzinger et al. distinguish **Digital Model (DM)**, **Digital Shadow (DS)** (automatic one-way data flow), and **Digital Twin (DT)** (bidirectional link), and observe that true DTs are comparatively scarce in manufacturing literature. ([ScienceDirect][3])
Monitoring twins typically store *latest values*; historical reconstruction depends on separate logging systems and is rarely semantically linked to decisions.

### 2.2 Simulation twins (replicas)

Simulation replicas are high-fidelity models used for what-if analysis, planning, and offline optimization. A systematic review on “when a simulation is a digital twin” reports that many implementations are essentially simulation models and that DT concepts and practice remain disconnected. ([CoLab][4])
Replicas can explore futures but usually cannot reproduce *the operational decision context* (what was known then, with which uncertainty).

### 2.3 Control-integrated twins

Some authors frame DTs as macro closed-loop control constructs; however, this often blurs responsibilities between the twin and certified control logic. ([isa.org][5])
Industrial practice typically retains PLCs as final arbiters, and recent work highlights that PLC capabilities strongly determine DT architecture, while PLC-in-the-loop synchronization is rarely handled rigorously. ([ScienceDirect][2])

### 2.4 Event-driven / architecture-driven twins

Architecture work on DT engineering emphasizes domain-driven design and patterns such as hexagonal architecture. The ICSA’23 paper explicitly distinguishes DM/DS/DT and motivates general DT architecture guidance. 
Yet, event-driven proposals often stop at software architecture patterns and do not define an evidence/uncertainty model nor a formal coupling to DES admissibility.

### 2.5 Synthesis table

| Family                        | State representation                  | Traceability               | Provenance                 | Replay                          | Control grounding                |
| ----------------------------- | ------------------------------------- | -------------------------- | -------------------------- | ------------------------------- | -------------------------------- |
| Monitoring/DS                 | latest snapshot                       | partial (logs external)    | weak                       | low                             | none/implicit                    |
| Simulation replica            | model trajectories                    | limited to simulation runs | model-level                | stochastic / non-operational    | weak                             |
| Control-integrated            | mixed, often ad hoc                   | variable                   | variable                   | variable                        | sometimes, but often informal    |
| **Event-sourced (this work)** | replayable fold over immutable events | high by construction       | explicit attribute lineage | deterministic under assumptions | explicit interface to supervisor |

Limitations for structural uncertainty: none of the first three families reliably preserve *bitemporal belief* (what happened vs what was believed), nor do they enforce that recommendations are constrained by a supervisor-enabled set.

---

## 3. Architectural Requirements (derived from structural uncertainty + DES supervision)

We formalize requirements as testable properties. Let the plant be a DES with event alphabet (\Sigma=\Sigma_c \cup \Sigma_{uc}). Let (\hat{x}_t) be the twin’s state estimate/belief at time (t).

**R1 — Time-stamped state transitions.** Every logged event (e) carries event-time (t_e) and a monotone sequence id (k), defining a total order (\prec) for replay.

**R2 — Immutable event store.** Events are append-only; corrections are new events (no in-place edits).

**R3 — Uncertainty metadata.** Each state attribute includes ((v, c, \tau, w)): value (v), confidence (c\in[0,1]), last validation time (\tau), and validity window (w) (freshness). ([National Academies][1])

**R4 — Evidence linkage (provenance).** Every attribute instance stores pointers to an evidence set (E^+\subseteq \text{Events}) supporting it (observations, inspections, model inferences), including source attribution.

**R5 — Deterministic replay.** Replaying the same ordered event log from the same initial state yields the same materialized state (including belief versions).

**R6 — Supervisor compatibility.** The twin exports recommendations only as candidates in (\Sigma_c) and supports an admissibility check: executed controllable events must satisfy
[
\sigma_t \in \Gamma_S(\hat{x}_t),
]
where (\Gamma_S(\hat{x})) is the supervisor-enabled set computed from the DES supervisor given the current estimate.

---

## 4. Proposed Architecture

**Figure 1 (textual):** A layered architecture with (i) **Plant/PLC layer** producing events and executing allowed actions, (ii) **Event ingestion + canonicalization** mapping PLC signals/commands to canonical events, (iii) **Immutable event store**, (iv) **Replay/materialization service** producing twin state and belief versions, (v) **Decision support services** (routing, sensing suggestion, exception handling), and (vi) **Supervisor interface/gate** intersecting any proposed action with (\Gamma_S) before execution.

### 4.1 Event model

#### 4.1.1 Canonical event schema

Each event (e) is a record:

* `event_id` (UUID), `seq_no` (monotone), `event_time`, `ingest_time`
* `type` ∈ {Observation, ActionProposed, ActionAdmitted, ActionExecuted, Exception, HumanDecision, ModelRevision, BeliefUpdate}
* `actor` ∈ {Sensor, PLC, Operator, Coordinator, TwinInference}
* `payload` (typed by `type`)
* `hash_prev` (optional hash-chain for tamper evidence)
* `signature` (optional; for regulated contexts)

#### 4.1.2 State transition function

Let (S) be the twin state space and (f:S \times \mathcal{E} \to S) be a deterministic reducer. Materialized state after (n) events:
[
s_n = \text{fold}(f, s_0, [e_1,\dots,e_n]).
]
Queries “state at time (t)” replay to the prefix with (t_{e_i}\le t).

#### 4.1.3 Immutable event store

Events are appended once. Any correction is an event (e.g., `ObservationCorrected`, `CalibrationUpdated`). This supports bitemporal reasoning: “what we believed then” is preserved as of that prefix.

### 4.2 Evidence model

#### 4.2.1 Evidence typing and provenance tagging

We define evidence objects as first-class:

* `EvidenceRef` = pointer to an event that is an observation, inspection result, operator annotation, or validated inference output.
* Each derived attribute stores `provenance = {EvidenceRef...}` plus `source`, `method`, and `version`.

This follows DT trustworthiness needs emphasizing uncertainty and traceability for decision support. ([National Academies][1])

#### 4.2.2 Confidence and freshness

Each attribute instance (a) carries:

* `confidence` (c) (sensor quality grade mapped to numeric, or inference posterior mass),
* `valid_until = event_time + window`,
* `stale` flag if current time exceeds `valid_until`.

### 4.3 Uncertainty representation

We use a **hybrid** representation suitable for PLC-constrained settings:

1. **Attribute-level confidence** for most variables (fast, compositional).
2. **Belief state versioning** for a small set of hazard/structure-critical latent variables (battery risk class, fastener integrity class, adhesive regime), stored as `BeliefState(version_id, support/probabilities)`.

Belief updates are explicit events (`BeliefUpdate`) so that replay reproduces the evolution of uncertainty.

### 4.4 Interface with DES supervisor

#### 4.4.1 Twin → supervisor alignment

The EEDT maintains a mapping from canonical events to DES events in (\Sigma), ensuring that PLC-executed actions and relevant uncontrollable events are represented in the same alphabet used by the supervisor.

#### 4.4.2 Admissibility gate

Any `ActionProposed(σ)` event triggers:

1. **Grounding check:** all preconditions used to justify σ must be supported by evidence pointers with non-stale freshness (or explicitly marked unknown).
2. **Supervisor check:** compile σ to a DES controllable event and compute
   [
   \sigma \in \Gamma_S(\hat{x}).
   ]
   If true, record `ActionAdmitted(σ)`; else record `ActionRejected(σ, reason)` and trigger fallback (`request_sensing`, `reroute`, `escalate`).

#### 4.4.3 Synchronization mechanism

**Figure 2 (textual):** A timeline with PLC scan cycles producing command + telemetry events; ingestion assigns `seq_no` and reconciles out-of-order arrivals using bitemporal fields (`event_time`, `ingest_time`). The replay service materializes (s_t) using ordered events by (`seq_no`) while allowing forensic queries by `event_time`.

PLC constraints matter: PLCs are essential to DT implementations and shape achievable architectures. ([ScienceDirect][2])

---

## 5. Formal Properties

We state properties with explicit assumptions.

### Assumption A1 (Total order)

The stored events admit a total order (\prec) consistent with causality (implemented via `seq_no` assigned at ingestion for each plant stream; ties broken deterministically).

### Assumption A2 (Deterministic reducer)

The reducer (f) is deterministic and pure w.r.t. inputs (s,e). Any stochastic inference must be logged as outcomes (or use fixed seeds stored as event payload).

### Definition 1 (Deterministic replay)

Given the same initial state (s_0) and ordered event log (L=[e_1,\dots,e_n]), replay yields a unique state (s_n).

**Proposition 1.** Under A1–A2, replay is deterministic: ( \text{fold}(f,s_0,L)) is unique.
*Proof sketch:* fold over a fixed sequence with a deterministic reducer is deterministic by induction on (n).

### Definition 2 (Trace completeness)

Let (T) be the true plant event trace over a logged alphabet (\Sigma_{\log}\subseteq \Sigma). Let (L) be the stored event log projected to (\Sigma_{\log}). Trace completeness ratio:
[
\text{TCR} = \frac{|L|}{|T|}.
]
TCR=1 indicates completeness over the instrumented alphabet; missing unobservable events are outside scope unless inferred and logged as such.

### Definition 3 (Evidence-grounded decision)

A proposed action (σ) at time (t) is evidence-grounded if every predicate used in its justification depends only on attributes whose provenance sets are non-empty and non-stale at (t), or are explicitly labeled unknown with an associated escalation/sensing policy.

### Definition 4 (DES admissibility consistency)

An executed controllable event (σ_t) is consistent if (σ_t \in \Gamma_S(\hat{x}_t)).

**Proposition 2 (Containment interface).** If the execution layer only executes events that have an `ActionAdmitted(σ)` record produced by the gate, then every executed controllable event satisfies DES admissibility consistency.
*Proof sketch:* The gate emits `ActionAdmitted(σ)` iff (σ\in\Gamma_S(\hat{x})); executed controllable events are a subset of admitted events.

---

## 6. Experimental Validation

We design validation around falsifiable tests and metrics, using a demanufacturing DES testbed (e.g., the structural uncertainty benchmark from Paper 1).

### A. Auditability tests

**A1 Decision trace reconstruction.** Randomly sample (N) executed actions; for each, reconstruct:

* evidence set (E^+) (minimal provenance closure),
* belief version used,
* admissibility result.
  **Pass criterion:** ≥(1−ε) actions have complete decision-to-evidence linkage (no missing provenance pointers).

**A2 Replay forensic repeatability.** Inject post-hoc corrections (e.g., sensor calibration fixes) as new events. Compare:

* “what we believed then” (prefix replay),
* “what we believe now” (full replay).
  **Metric:** belief divergence across versions; ability to reproduce original decision context.

### B. Debugging scenarios

**B1 Exception root-cause analysis.** Inject faults (stripped screw, hidden adhesive, hazard flag false negative). Compare time-to-diagnosis and correctness of root cause between:

* event-sourced EEDT
* state-overwrite twin + external logs
  **Metric:** root-cause attribution accuracy; steps required; reproducibility.

**B2 Replay fidelity under noise.** Perturb event arrival ordering and drop non-critical telemetry.
**Metric:** replay determinism rate (RDR) = fraction of runs where replayed state hashes match reference.

### C. Performance metrics

* **Trace completeness ratio (TCR)** as defined above.
* **Replay determinism rate (RDR)**: % of replay queries yielding identical state hash for same log.
* **Evidence-grounded decision percentage (EGDP)**: % proposed actions passing grounding check.
* **Overhead:** event ingestion latency, storage rate (events/s), and materialization time for “state now” query.

Protocol: run matched scenarios with identical random seeds; report mean ± CI over ≥30 episodes per condition.

---

## 7. Comparative Evaluation

We compare architectural capabilities (not hype) against three baselines:

1. **State-overwrite twin (SOT).** Maintains current state in a database; logs are separate (if any).
2. **Monitoring dashboard (MD).** Telemetry visualization + alarms; no causal model.
3. **Simulation replica (SR).** Offline DES/physics simulation; no guaranteed synchronization.

### Capability comparison (representative)

| Capability                                  | MD |                  SR |                 SOT |        **EEDT (this work)** |
| ------------------------------------------- | -: | ------------------: | ------------------: | --------------------------: |
| Deterministic replay of *operational* state |  ✗ | △ (simulation-only) | △ (if logs perfect) |                           ✓ |
| “What we believed then” (bitemporal belief) |  ✗ |                   ✗ |                 ✗/△ |                           ✓ |
| Decision-to-evidence traceability           |  ✗ |                   △ |                   △ |                           ✓ |
| Explicit uncertainty + freshness            |  △ |                   △ |                   △ | ✓ ([National Academies][1]) |
| Supervisor-grounded admissibility           |  ✗ |                 ✗/△ |                   △ |      ✓ ([ScienceDirect][3]) |
| PLC-shaped synchronization considered       |  △ |                   ✗ |                   △ |      ✓ ([ScienceDirect][2]) |

(△ indicates achievable only with substantial custom engineering and without formal guarantees.)

---

## 8. Discussion

### 8.1 Trade-offs

* **Storage and throughput:** event sourcing increases write volume; mitigation requires compaction strategies (snapshots + retention tiers) without breaking replay semantics.
* **Latency:** materialization can be optimized via incremental projections; the critical constraint is keeping PLC scan-cycle control separate (twin is decision-support + coordination, not inner-loop control). ([ScienceDirect][2])
* **Complexity:** evidence typing and provenance closure require disciplined schema governance; however, this complexity is the cost of audit-grade coordination.

### 8.2 Scalability limits

High-resolution logging across many stations can overwhelm central stores. A practical path is hierarchical logging: local event buffers at cell level with periodic consolidation, while preserving total order per resource/product stream.

### 8.3 Portability to other CPS domains

Any domain where feasibility evolves with evidence (maintenance/repair, remanufacturing, field robotics with changing affordances) benefits from replayable belief + evidence lineage. The DES-coupled interface is especially relevant for systems where certified controllers must remain authoritative.

### 8.4 Interaction with conservative learning (Paper 3)

Conservative learning can be implemented as producing **BeliefUpdate** and **ModelRevision** events only when confidence improves beyond a threshold, ensuring learning never silently overwrites operational state. The admissibility gate remains unchanged; learning affects *estimates*, not the supervisor’s constraints.

### 8.5 Interaction with semantic mediation (Paper 4)

LLM-based mediation can be inserted as a recommender that emits `ActionProposed` or `SensingRequested` intents. The EEDT provides the grounding substrate (evidence pointers + freshness). The deterministic gate enforces schema validity, grounding, and DES admissibility; all mediation outputs become auditable events.

---

## 9. Conclusion

We presented an **event-sourced, evidence-grounded digital twin (EEDT)** for demanufacturing under partial observability and structural uncertainty. The architecture differs from monitoring-only twins and simulation replicas by preserving immutable event histories, bitemporal belief evolution, and attribute-level provenance with confidence/freshness metadata. We defined testable requirements and formal properties—deterministic replay, trace completeness, evidence-grounded decision making, and DES admissibility consistency—and provided an evaluation protocol and metrics focused on auditability and replay fidelity. Practically, the EEDT enables trace-linked exception handling and forensic accountability while remaining compatible with PLC-constrained supervisory envelopes.

**Extensions:** (i) formal methods for detecting and bounding missing events (trace gaps), (ii) scalable distributed event sourcing with causal consistency across multiple twins, and (iii) tighter integration of uncertainty-aware supervisors that explicitly account for evolving feasible action sets.
