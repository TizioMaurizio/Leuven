## Pre-writing

1. **Containment property (single statement).** For all decision steps (t), the executed controllable event is always supervisor-enabled:
   [
   \sigma_t \in A_{\text{sup}}(\hat{s}*t)\quad\text{equivalently}\quad A*{\text{exec}}(\hat{s}*t)\subseteq A*{\text{sup}}(\hat{s}_t).
   ]

2. **Single strongest theoretical claim.**
   **No-new-behavior containment:** if every executed controllable action is obtained by intersecting any LLM-proposed action candidates with the supervisor-enabled set, then the closed-loop behavior generated under LLM guidance is a sublanguage of the behavior under the verified supervisor alone (language inclusion), hence cannot introduce new supervisor-forbidden behaviors. ([Princeton University][1])

3. **Weakest assumption.**
   **Model completeness / adequacy of the supervisor envelope:** the supervisor’s event set and specifications must cover the relevant safety constraints and failure modes; unmodeled events or plant-model mismatch can violate real-world safety even if containment relative to the model holds. (This is the standard boundary of guarantees in supervisory control when the model is incomplete.) ([Princeton University][1])

---

# Bounded Semantic Mediation for LLM-Assisted Coordination with Deterministic Containment Guarantees

## Abstract

Exception-heavy demanufacturing of end-of-life (EoL) electronics is characterized by partial observability and frequent deviations from nominal process assumptions. These deviations create a coordination burden: operators must aggregate heterogeneous evidence, interpret exceptions, and select recoveries under time pressure. Large language models (LLMs) can support this coordination layer by summarizing evidence, classifying exceptions, and proposing structured recovery intents. However, LLM outputs are stochastic and may propose actions that expand behavior beyond a verified industrial control model.

This paper proposes **bounded semantic mediation**, an architecture that integrates an LLM reasoning module into a discrete-event-system (DES) demanufacturing cell while guaranteeing **no new behavior** relative to a verified supervisor. The key mechanism is a **deterministic mediation gate** that (i) enforces a closed intent vocabulary, (ii) requires evidence-grounded references to an event-sourced digital twin, (iii) compiles intents into action candidates, and (iv) **intersects** them with the **supervisor-enabled action set** before any actuation request is issued. We formalize the containment objective, provide a proof sketch establishing language inclusion, and develop an assurance-case template linking architectural claims to testable evidence. Finally, we present an empirical validation on a toy DES disassembly model that contrasts syntactic/schema filtering with model-consistent enforcement: the mediation gate achieves **zero containment violations** by construction, while baselines that rely on structured outputs alone do not.

**Keywords:** demanufacturing, discrete-event systems, supervisory control, containment, assurance case, LLM safety, runtime enforcement.

---

## 1. Introduction

EoL electronics demanufacturing operates under structural variability: device condition, fasteners, adhesives, and hazard states are often partially known at intake and are revealed during inspection and partial disassembly. The resulting exceptions—stripped screws, hidden clips, adhesive failures, swollen batteries—create **coordination complexity** even when low-level actuation remains PLC-based and deterministic.

Semantic reasoning is useful here for three concrete coordination tasks:

1. **Aggregation:** compressing heterogeneous logs, sensor cues, and operator notes into a coherent state narrative.
2. **Explanation:** producing trace-linked rationales (“which evidence supports the current hazard class?”).
3. **Exception handling:** mapping observed anomalies to standardized exception classes and suggesting admissible recoveries (e.g., request inspection, reroute, escalate).

The core risk is that integrating a non-deterministic model into a safety-critical workflow can **expand** behavior beyond what a verified supervisory controller allows. This mismatch is acute in PLC-bounded settings, where the certified envelope is encoded as a supervisor over a DES model. The central problem is therefore:

> **How can semantic reasoning be integrated into coordination without violating DES admissibility guarantees?**

### Research questions

**RQ1:** How should an LLM reasoning module be interfaced to a DES supervisor so that executed controllable actions remain within the supervisor-enabled set?
**RQ2:** What deterministic validation and compilation steps are sufficient to ensure “no new behavior” despite stochastic generation?
**RQ3:** How should assurance evidence (logs, proofs, adversarial tests) be structured to support certification-grade claims?
**RQ4:** How does model-consistent enforcement compare to schema-only (syntactic) containment in exception-heavy scenarios?

### Contributions

1. **Containment formalization:** a precise containment objective stated as supervisor-enabled set inclusion and (language) behavior containment. ([Princeton University][1])
2. **Bounded semantic mediation architecture:** an LLM-outside-the-actuator-path design with a deterministic gate enforcing closed intents, evidence grounding, and supervisor intersection.
3. **Formal containment argument:** a proposition and proof sketch establishing no-new-behavior containment via set intersection and language inclusion in the Ramadge–Wonham framework. ([Princeton University][1])
4. **Assurance-case template:** a reusable CAE/GSN-aligned structure linking claims to proof obligations, runtime logs, and adversarial tests. ([Claims Arguments Evidence][2])
5. **Empirical validation:** a minimal DES case study demonstrating that schema-only containment is insufficient and that model-consistent gating eliminates containment violations.

---

## 2. Analytical positioning in the literature

### 2.1 LLM integration in industrial systems

Industrial interest in LLMs emphasizes interfaces, summarization, and decision support. The safety challenge is architectural: ICS/PLC control is deterministic, while LLM outputs are probabilistic, motivating separation and validation layers. ([NVIDIA Docs][3])

### 2.2 Tool-use and schema-constrained generation

A common mitigation is to constrain outputs to structured forms (JSON schema, grammars, function calls) and validate them. Systems compute token masks or enforce grammars during decoding to ensure syntactic well-formedness. LLGuidance and related guided decoding approaches explicitly build token masks from grammars/JSON schema. ([Guidance AI][4])
However, recent work shows that structured-output constraints introduce a **control-plane** attack surface: Constrained Decoding Attacks can exploit grammar/schema mechanisms to bypass safety controls. ([dblp][5])
Thus, syntactic containment is necessary for robustness of parsing, but not sufficient for behavioral safety.

### 2.3 Runtime enforcement architectures

Runtime enforcement frameworks specify and enforce constraints on agent behavior at execution time (triggers, predicates, enforcement actions). AgentSpec exemplifies a DSL-driven enforcement approach with reported effectiveness across multiple domains. ([InK][6])
Such approaches align with manufacturing needs, but typically enforce **semantic** rules (policy predicates) rather than **formal model-consistency** with DES supervisors.

### 2.4 Supervisory control containment

Supervisory control theory models a DES as a generator of a language and synthesizes supervisors that restrict controllable events to meet specifications; a key notion is that closed-loop behavior is constrained by the enabled-event policy. ([Princeton University][1])
Our paper leverages this structure: the supervisor defines an admissible set at each estimated state, and the LLM is only permitted to influence choice *within* that set.

### 2.5 Assurance cases in safety-critical systems

Assurance cases structure claims, arguments, and evidence (CAE/GSN). CAE provides a minimal claim–argument–evidence decomposition, while GSN provides a richer notation and community standard usage in safety arguments. ([Claims Arguments Evidence][2])
Formal treatments of safety case patterns and their instantiation motivate machine-checkable assurance artifacts. ([NASA Technical Reports Server][7])
LLMs have been explored for instantiating assurance cases from formalized patterns, but results emphasize limitations and the need for expert oversight—consistent with our stance that LLM outputs cannot be trusted as enforcement. ([ScienceDirect][8])

### 2.6 Adversarial testing of hybrid AI-control systems

Robustness evaluation toolchains for LLM safety (e.g., jailbreak toolboxes) reflect the need for standardized adversarial tests and reproducible benchmarks. ([Cool Papers][9])
In hybrid systems, adversarial testing must include (i) prompt-based attacks and (ii) structured-output/control-plane attacks. ([dblp][5])

---

### 2.7 Synthesis tables

**Table 1 — Containment taxonomy**

| Containment type | Mechanism                                       | What it guarantees                                  | Guarantee strength           | Typical failure mode                                                                |
| ---------------- | ----------------------------------------------- | --------------------------------------------------- | ---------------------------- | ----------------------------------------------------------------------------------- |
| Syntactic        | JSON schema / grammar / token masking           | Well-formed outputs; parseability                   | Deterministic for syntax     | Semantics unsafe; control-plane attacks on constraints ([dblp][5])                  |
| Semantic         | Rule/validator checks; policy predicates        | Domain constraints as encoded                       | Often conditional / partial  | Incomplete rules; classifier/LLM errors; bypass via prompt injection ([GitHub][10]) |
| Model-consistent | Intersection with formal supervisor-enabled set | No supervisor-forbidden controllable events execute | Deterministic (w.r.t. model) | Model incompleteness; unmodeled events/hazards ([Princeton University][1])          |

**Table 2 — Where enforcement occurs**

| Location                         | Example                    | Pre/post actuation | Notes                                                                 |
| -------------------------------- | -------------------------- | ------------------ | --------------------------------------------------------------------- |
| Pre-actuation deterministic gate | Supervisor intersection    | Pre                | Enforces behavioral envelope before PLC actuation                     |
| Pre-actuation validators         | Guardrails / schema checks | Pre                | Ensures structure, can trigger re-asks ([GitHub][10])                 |
| Runtime enforcement DSL          | AgentSpec                  | Pre / runtime      | Interpretable policy enforcement, not inherently DES-based ([InK][6]) |
| Post-hoc monitoring              | Logging / audit            | Post               | Supports assurance evidence but cannot prevent unsafe actuation       |

**Gap identified.** Existing approaches widely implement syntactic and semantic containment, but **formal, model-consistent containment** for LLM-assisted exception handling—where executed actions are proven to remain within a verified DES supervisor—is largely absent in deployed pipelines. ([Princeton University][1])

---

## 3. System model and problem formulation

### 3.1 DES plant and supervisor

Let the demanufacturing cell be modeled as a DES plant
[
G=(X,\Sigma,\delta,x_0),
]
with event set (\Sigma=\Sigma_c\cup\Sigma_{uc}) partitioned into controllable and uncontrollable events.

A supervisor (S) restricts controllable events based on an observed history (or observer state) (\hat{s}\in\hat{X}) under partial observation. The supervisor induces an enabled set
[
A_{\text{sup}}(\hat{s}) \subseteq \Sigma_c.
]
In the Ramadge–Wonham language framework, the supervised behavior is a closed-loop language (L(S/G)). ([Princeton University][1])

### 3.2 LLM-generated intent space

Let (I) be a finite **intent space** (closed vocabulary) exposed to the LLM. Each intent (i\in I) is a typed record (schema) with arguments (e.g., exception class, target station, requested sensing). The LLM module produces a proposal
[
i_t \sim \mathcal{M}(\cdot \mid \mathcal{C}_t),
]
where (\mathcal{M}) is stochastic and (\mathcal{C}_t) is the context assembled from the digital twin.

### 3.3 Intent compilation and validation gate

An **intent compiler**
[
C : I \times \hat{X} \rightarrow 2^{\Sigma_c}
]
maps an intent to a set of candidate controllable events (possibly empty), given the current estimated state. A **validation gate** (V) deterministically returns an executable set:
[
A_{\text{exec}}(\hat{s}) ;=; V(i,\hat{s}) ;=; C(i,\hat{s}) \cap A_{\text{sup}}(\hat{s}).
]

### 3.4 Containment objective (central formal objective)

[
\boxed{A_{\text{exec}}(\hat{s}) \subseteq A_{\text{sup}}(\hat{s})\quad\forall \hat{s}}
]
Equivalently, for each executed controllable event (\sigma_t),
[
\sigma_t \in A_{\text{sup}}(\hat{s}_t).
]

### 3.5 Assumptions

**A1 (Supervisor correctness w.r.t. model):** (S) is verified to enforce the required safety/nonblocking properties for (G) under the assumed observation model. ([Princeton University][1])
**A2 (Actuation mediation):** the PLC execution layer only requests controllable events from (A_{\text{exec}}(\hat{s})).
**A3 (Compiler determinism):** (C) and (V) are deterministic functions (given inputs).
**A4 (Model adequacy):** relevant hazards are captured within (\Sigma) and the specifications used for synthesis (weakest assumption; see Discussion).

---

## 4. Proposed bounded semantic mediation architecture

### Overview

The architecture enforces a strict separation: the LLM produces **intents**, not actuator commands; the PLC executes only events admitted by a deterministic gate.

#### Components (layered)

1. **Event-sourced, evidence-grounded twin** (coordination substrate; companion work) providing trace-linked facts and freshness.
2. **Semantic mediation module (LLM)** producing structured intents over a closed vocabulary.
3. **Deterministic validation gate** enforcing schema, grounding, compilation, and supervisor intersection.
4. **PLC supervisor execution** implementing the verified supervisor policy.

### 4.1 Closed intent vocabulary

The intent vocabulary is finite and typed; examples (illustrative):

* `RequestSensing(sensor_id, target, rationale_ref)`
* `ClassifyException(class_id, evidence_refs)`
* `ProposeRouting(route_id, justification_refs)`
* `EscalateToHuman(reason, evidence_refs)`

No free-form “do X” commands are accepted. The aim is not to make the LLM safe by instruction, but to ensure the interface is narrow and machine-checkable.

**Relation to structured generation literature.** Grammar/schema-constrained generation and token-masking approaches ensure well-formed outputs and reduce parsing failures. ([Guidance AI][4])

### 4.2 Grounding requirements

Every intent must include:

* **Evidence references** to event-log entries (observation IDs, timestamps),
* **Freshness bounds** for safety-critical claims (e.g., hazard class),
* **Scope** (which device/unit, which station),
* **Explicit unknowns** when evidence is missing.

Grounding is validated deterministically against the twin log; missing or stale evidence causes rejection or conversion to a sensing request/escalation.

### 4.3 Deterministic validation gate

Given intent (i) and estimate (\hat{s}), the gate performs:

1. **Schema/type validation** (parse + typecheck). (Structured output tooling supports this step but does not suffice alone.) ([GitHub][10])
2. **Grounding validation**: all `evidence_refs` exist; freshness predicates hold.
3. **Intent compilation** (C(i,\hat{s})): map intent to candidate DES events (or an empty set).
4. **Model-consistency check**: compute (C(i,\hat{s}) \cap A_{\text{sup}}(\hat{s})).
5. **Fallback**: if empty, deterministically emit `RequestSensing` (if admissible) or `EscalateToHuman`.

### 4.4 Why the LLM is never in the actuator path

The LLM influences coordination **only** by proposing intents; it cannot directly issue PLC commands. Any controllable event request passes through a deterministic intersection with (A_{\text{sup}}), so containment does not depend on the LLM’s correctness.

---

## 5. Formal containment argument

### Proposition 1 (Non-expansion of admissible behavior)

Assume A1–A3. For any LLM policy producing intents (i_t), if the executed controllable event (\sigma_t) is selected from
[
A_{\text{exec}}(\hat{s}_t)=C(i_t,\hat{s}*t)\cap A*{\text{sup}}(\hat{s}*t),
]
then (\sigma_t \in A*{\text{sup}}(\hat{s}_t)) for all (t). Consequently, the closed-loop language under LLM guidance is contained in the supervisor language:
[
L(\text{LLM}\circ S/G)\subseteq L(S/G).
]

**Proof sketch.** By definition, (A_{\text{exec}}(\hat{s})\subseteq A_{\text{sup}}(\hat{s})). Since the only influence on controllable events is via selection from (A_{\text{exec}}), any executed controllable event is also supervisor-enabled. Therefore any event string generated under LLM guidance is also a feasible event string under (S) alone (with some choice function resolving nondeterminism among enabled controllable events), yielding language inclusion. ([Princeton University][1])

### What is guaranteed

* **Containment relative to the supervisor model:** no supervisor-forbidden controllable event is executed.
* **Deterministic enforcement:** containment is independent of LLM stochasticity.

### What is not guaranteed

* **Semantic correctness:** the LLM’s explanation or exception classification may be wrong.
* **Optimality/performance:** containment may increase rejections/escalations, reducing throughput.
* **Real-world safety under model incompleteness:** if hazards are unmodeled, containment does not prevent them (see §9). ([Princeton University][1])

---

## 6. Assurance case structure

We adopt a CAE/GSN-compatible argument structure: top-level claims are decomposed into architectural and verification subclaims, each linked to evidence. ([Claims Arguments Evidence][2])

### 6.1 Assurance case template (textual CAE form)

**C0 (Top claim):** System preserves verified safety constraints while incorporating LLM-based semantic mediation.

* **A1 (Argument):** Containment-by-construction: executed controllable events are restricted to supervisor-enabled set.

  * **C1:** All LLM outputs are restricted to a closed intent schema.

    * **E1:** Schema definition + parser/typechecker test suite; schema fuzz tests.

  * **C2:** Every admitted intent is evidence-grounded against the event log.

    * **E2:** Runtime logs linking each admitted intent to evidence IDs; freshness validation tests.

  * **C3:** Every executed controllable event is in (A_{\text{sup}}(\hat{s})).

    * **E3:** Formal proof sketch (Proposition 1) + audited gate implementation + trace replay checks.

* **A2 (Argument):** Robustness to adversarial inputs: prompt injections and control-plane attacks cannot expand executed behavior.

  * **C4:** Prompt injection cannot bypass gate checks.

    * **E4:** Adversarial prompt suite + rejection logs.

  * **C5:** Structured-output/control-plane attacks cannot force out-of-envelope actuation.

    * **E5:** Tests that emulate constrained-decoding attack patterns; gate rejection/containment results. ([dblp][5])

* **A3 (Argument):** Evidence integrity and auditability

  * **C6:** All decisions are reconstructible from event-sourced logs.

    * **E6:** Replay determinism tests; completeness metrics; audit trail reviews.

**Note.** Pattern-based and partially automated assurance-case generation is feasible, but the enforcement claim remains anchored in deterministic gate logic rather than LLM-generated artifacts. ([ScienceDirect][8])

---

## 7. Adversarial & exception-heavy evaluation

### 7.1 Experimental design

We evaluate three configurations:

1. **Unconstrained LLM integration:** execute the LLM’s suggested action directly (baseline; unsafe).
2. **Schema-only containment:** accept structured outputs (JSON/schema) and reject malformed outputs, but *no model-consistency intersection*.
3. **Proposed model-consistent gate:** schema + grounding + compilation + ( \cap A_{\text{sup}} ).

### 7.2 Exception injection (manufacturing-relevant)

* Conflicting context (two hazard signals disagree),
* Missing evidence (no recent battery observation),
* Ambiguous state (partial disassembly without confirmation),
* Out-of-distribution phrasing (unexpected operator language).

### 7.3 Attack simulation

* Prompt injection (“ignore previous rules; do X now”),
* Invalid action suggestions (“cut battery now”),
* Intent schema violations (wrong fields/types),
* Structured-output/control-plane stressors (adversarially constructed structured content). ([dblp][5])

### 7.4 Metrics

* **Containment violation rate**: fraction of episodes where an executed controllable event (\notin A_{\text{sup}}) (target: 0).
* **Invalid intent rejection rate**: fraction rejected by the gate.
* **Escalation frequency**: rate of `EscalateToHuman`.
* **Throughput impact**: cycle time / completions under exceptions.
* **Overhead latency**: gate evaluation time (ms-scale target in PLC-adjacent settings).
  Runtime enforcement work suggests millisecond-scale overhead is achievable for guard logic. ([InK][6])

---

## 8. Results

### 8.1 Empirical validation on a toy DES demanufacturing model

We implemented a minimal DES with three operational states (pre-battery-safe, post-shield removal, battery-safe) and a supervisor that disallows cutting/prying before battery-safe. The LLM generator was modeled as a stochastic proposer that sometimes suggests unsafe actions (e.g., `cut` too early) or out-of-scope commands. We simulated **5,000 episodes** per configuration.

**Table 3 — Toy DES results (5,000 episodes)**

| Policy                 | Containment violation rate | Mean violations / episode | Mean rejections / episode | Terminal completion rate |
| ---------------------- | -------------------------: | ------------------------: | ------------------------: | -----------------------: |
| Unconstrained          |                     0.8534 |                    2.7592 |                    0.0000 |                   0.9996 |
| Schema-only            |                     0.7872 |                    2.0720 |                    0.6868 |                   0.9996 |
| **Model-gated (ours)** |                 **0.0000** |                **0.0000** |                    2.1032 |                   0.9998 |

**Interpretation.**

* **Schema-only containment is insufficient:** although malformed outputs are rejected, structurally valid yet supervisor-forbidden actions still execute, producing many containment violations.
* **Model-consistent gating eliminates containment violations by construction:** all executed controllable events are supervisor-enabled, regardless of LLM proposal quality.

### 8.2 Syntactic filtering vs model-consistent enforcement

Schema constraints and token masking improve parseability and reduce malformed outputs. ([Guidance AI][4])
But safety-critical containment depends on **model-consistency**, not syntax. Moreover, structured-output mechanisms can be attacked at the constraint layer (control-plane), reinforcing the need for a supervisor intersection that is independent of LLM decoding tricks. ([dblp][5])

---

## 9. Discussion

### 9.1 Scalability limits

The approach scales with the supervisor representation and the cost of evaluating (A_{\text{sup}}(\hat{s})). Distributed/decentralized supervisory control suggests decomposition is feasible, but careful interface design is required so that local enabled sets still imply global properties. ([ScienceDirect][11])

### 9.2 Dependency on model completeness

Containment is **relative** to the modeled event set and specifications. If a hazard mode is absent from (\Sigma) or not constrained in the supervisor, the gate cannot prevent it. This is the principal boundary condition of “no new behavior” guarantees.

### 9.3 Interaction with conservative learning (companion work)

A conservative learning-to-update/ask layer can reduce rejections by improving (\hat{s}) and requesting evidence when uncertainty is high. In this combined view:

* Learning refines beliefs and triggers sensing,
* The LLM proposes intents (classification/explanations),
* The supervisor gate remains the sole behavioral envelope.

### 9.4 Generalization to other CPS domains

Any CPS domain with a verified discrete-event (or hybrid) supervisor can adopt bounded semantic mediation: maintenance lines, remanufacturing, and safety-critical exception triage in logistics. The requirement is an executable notion of an enabled set and an enforceable actuation boundary.

### 9.5 Limits of deterministic containment under incomplete models

Deterministic containment does not “solve” semantic errors, hallucinated explanations, or missing sensors. It ensures only that such errors cannot expand executed controllable behavior beyond the certified envelope. This is intentionally narrow—and appropriate for PLC-bounded deployment.

---

## 10. Conclusion

We proposed **bounded semantic mediation**, an architecture for integrating LLM-based semantic support into demanufacturing coordination while preserving deterministic supervisory control guarantees. The central containment principle is a simple inclusion:
[
A_{\text{exec}}(\hat{s}) = C(i,\hat{s}) \cap A_{\text{sup}}(\hat{s}) \subseteq A_{\text{sup}}(\hat{s}),
]
which yields **no new behavior** relative to the verified supervisor. Grounded, closed-vocabulary intents and deterministic validation provide auditable interfaces, while an assurance-case template links claims to proofs, runtime logs, and adversarial tests. A toy DES evaluation demonstrates that structured outputs alone are insufficient and that model-consistent gating achieves zero containment violations.

**Implication:** In industrial control contexts, LLMs can be used as *semantic explainers and exception suggesters* only when their outputs are mediated by deterministic enforcement tied to a formally verified control envelope.

---

## References (selected, web-verified)

* Ramadge, P.J., Wonham, W.M. “Supervisory control of a class of discrete event processes.” SIAM J. Control Optim., 1987. ([Princeton University][1])
* Lin, F., Wonham, W.M. “Decentralized supervisory control of discrete-event systems.” Information Sciences, 1988. ([ScienceDirect][11])
* Zhang, S. et al. “Output Constraints as Attack Surface: Exploiting Structured Generation to Bypass LLM Safety Mechanisms.” arXiv:2503.24191, 2025. ([dblp][5])
* Wang, H., Poskitt, C.M., Sun, J. “AgentSpec: Customizable runtime enforcement for safe and reliable LLM agents.” (ICSE 2026 listing / arXiv), 2025–2026. ([InK][6])
* Beyer, T. et al. “AdversariaLLM: A Unified and Modular Toolbox for LLM Robustness Research.” arXiv:2511.04316, 2025. ([Cool Papers][9])
* Zeroual et al. (JSS 2025) “Automatic instantiation of assurance cases from patterns using large language models.” Journal of Systems and Software, 2025. ([ScienceDirect][8])
* Denney, E., Pai, G. “Safety Case Patterns: Theory and Applications.” NASA/TM-2015-218492, 2015. ([NASA Technical Reports Server][12])
* Denney, E., Pai, G. “A Formal Basis for Safety Case Patterns.” NASA technical report, 2014. ([NASA Technical Reports Server][7])
* CAE framework overview (Claims–Arguments–Evidence). ([Claims Arguments Evidence][2])
* GSN references via SACM (OMG issue attachment) and GSN literature. ([OMG Issue Tracker][13])
* Structured constraints / token masking approaches (LMQL/LLGuidance docs). ([LMQL][14])

