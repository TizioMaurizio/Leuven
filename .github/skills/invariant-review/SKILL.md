---
name: invariant-review
description: Procedure to verify formal invariants, supervisor constraints, and containment guarantees in simulation and coordination code.
---

# Invariant Review

## Goal

Verify that formal properties — supervisor-enabled sets, containment, monotonic refinement, and structural invariants — hold across the codebase.

## Procedure

### 1. Supervisor-Enabled Set

- Locate the supervisor module (`FWO/full_phd/demanuf/des/supervisor.py` or equivalent).
- For each state, list the supervisor-enabled actions.
- Trace the action selection logic: does it query the supervisor-enabled set before executing?
- Check: is there any code path where an action is executed without checking admissibility?
- Check: exception handlers — do they also respect the supervisor-enabled set?

### 2. No-New-Behavior Containment

- Define the supervisor's closed-loop language L(S/G) for the relevant automaton.
- Trace the executed event sequences from simulation logs or code paths.
- Verify: every executed sequence is a prefix of some word in L(S/G).
- Check: does any learning, mediation, or coordination module introduce actions outside L(S/G)?

### 3. Monotonic Belief Refinement

- Locate belief update logic (`FWO/full_phd/demanuf/learning/belief.py` or equivalent).
- Verify: after an update, the feasible set is a subset of (or equal to) the pre-update feasible set.
- Exception: expansion is allowed only with explicit new evidence that contradicts prior narrowing.
- Check: is there a code path where the feasible set grows without new evidence?

### 4. Mediation Gate (if applicable)

- Locate the mediation gate (`FWO/full_phd/demanuf/mediation/gate.py`).
- Verify: LLM-proposed intents are intersected with the supervisor-enabled set.
- Verify: only the intersection is executed — the LLM cannot bypass the gate.
- Check: does the gate handle empty intersections (proposed intent fully blocked)?

### 5. Resource Invariants

- For each resource type: is the capacity constraint enforced at all times?
- Can the simulation enter a state where more entities hold a resource than its capacity?
- Is deadlock possible? If so, is it detected and handled?
- Are buffer overflow / underflow conditions handled?

### 6. State Machine Properties

- For entity state machines: are all transitions valid according to the defined FSM?
- Can an entity skip a state or enter an undefined state?
- Are terminal states (completion, discard) absorbing?

## Report

For each property:
- HOLDS / VIOLATED / UNVERIFIABLE with evidence.
- If VIOLATED: exact code path, violating action, and affected state.
- Containment violation count (target: zero).
- Severity: **CRITICAL** (breaks formal guarantee), **HIGH** (weakens guarantee), **INFORMATIONAL** (potential concern).
- Recommended fix or further investigation needed.
