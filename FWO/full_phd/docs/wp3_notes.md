# WP3 Notes — Conservative Learning-to-Update & Learning-to-Ask

Extracted from PAPER_3.md (446 lines).

## Core Idea

Learning module sits **between** the event-sourced twin (WP2) and the
supervisor gate (WP1).  Two sub-modules:

1. **Learning-to-Update (U)** — refine a *set-valued* belief B_t over latent
   parameters θ using incoming evidence, via conservative set contraction
   (B_{t+1} ⊆ B_t).
2. **Learning-to-Ask (Q)** — select cost-effective admissible inspection
   actions to maximise information gain within the supervisor-enabled envelope.

## Key Concepts

### Set-valued Belief

- `B_t ⊆ Θ` — set of plausible latent-condition hypotheses.
- Each θ ∈ Θ is a LatentCondition dict (4 booleans → 16 possible combos).
- Initial `B_0 = Θ` (full ignorance).

### Conservative Update Operator

```
U(B_t, e_t) = B_t ∩ C(e_t)
```

Where `C(e_t)` is the conformal-credible region consistent with evidence e_t.

**Properties:**
- B_{t+1} ⊆ B_t (monotonic contraction)
- Non-expansion of executable actions
- Abstention when: (i) C(e_t) too broad (low info), (ii) calibration
  suspect (shift detected), (iii) evidence would eliminate *all* hypotheses.

### Confidence Threshold Logic

For admissible action σ ∈ A_sup(s_t):
- **RobustFeasible**: ∀θ ∈ B_t : F(x_t,σ,θ) = 1 → commit to σ
- **Feasible**: ∃θ ∈ B_t : F(x_t,σ,θ) = 1 → trigger ask (Q) to shrink B
- **No feasible** → escalate/reroute (still within A_sup)

### Feasibility Model F(x, σ, θ)

Maps (cell_state, action, latent) → bool. Encodes which actions actually
work under a given latent condition:
- Robot disassembly infeasible if stripped_screw = True
- Disassembly infeasible if missing_component = True (nothing to remove)
- Hazard handling required if battery_risk = True
- Adhesive issues may slow/fail robot disassembly

### Learning-to-Ask (VoI Policy)

- Query set: inspection events Σ_q ⊆ Σ_c (admissible)
- Uncertainty measure: U(B_t) = log |B_t|
- Expected reduction: Δ(σ^q; B_t) = E[U(B_t) - U(U(B_t, E(σ^q)))]
- Cost c(σ^q) for each query type
- Select: argmax (Δ/c) over admissible queries
- Escalate if max Δ/c < threshold or safety-critical ambiguity persists

### Integration Points

- **WP1**: Supervisor provides A_sup(s_t); gate enforces containment
- **WP2**: Twin provides evidence ledger; ask events logged as BELIEF_UPDATE
- Theorem 1: π including learning never escapes A_sup (gate enforces)
- Proposition 1: |B_t| non-increasing under U
- Proposition 2: Abstention + admissible queries → escalation safe

## Requirements for Implementation

### R1: BeliefSet
- Maintain B_t as set of LatentCondition dicts (≤16 elements)
- Support intersection (contraction) and size tracking

### R2: Update module
- Accept TwinEvent evidence → compute C(e_t) → contract B_t
- Abstention checks: informativeness, shift detection, empty-set guard
- Emit BELIEF_UPDATE events to twin store

### R3: Ask module
- Compute VoI for each admissible query action
- Cost dict for inspections
- Select max Δ/c or escalate
- Only propose actions within supervisor enabled set

### R4: Feasibility oracle
- F(cell_state, action, latent_condition) → bool
- Encodes domain constraints

### R5: BeliefTracker — orchestrator
- Holds current B_t
- On new evidence: call update → get commitment or ask/escalate
- On ask result: apply new evidence
- Track BeliefSet size trajectory for metrics

## Evaluation Baselines (from §7)

- B0: No learning
- B1: Standard probabilistic (no abstention)
- B2: RL-based (optionally shielded)
- B3: Conservative update only (our U, no Q)
- B4: Ask only (no calibrated update)
- B5: Full method (U + Q + supervisor gating)

## Metrics (from §7C)

- Coverage, calibration error, belief-set size trajectory
- Escalation frequency, inspection cost, Δ U/c efficiency
- Throughput, cycle time, utilisation
- Invariant violations (should be 0), forbidden-event proposals
