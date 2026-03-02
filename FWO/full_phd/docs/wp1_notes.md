# WP1 Notes — Core DES Simulation + Baseline Holonic Coordination

## Source: PAPER_1.md

## Key Concepts Extracted

### Structural Uncertainty
- Uncertainty over the *structure* of the coordination problem (not just parameters)
- Exogenous variable ω ∈ Ω encodes hidden conditions: fastener state, adhesive strength, missing components, hazard class
- Evolving feasible action set: A(x,ω) = {σ ∈ Σ_c : F(x,σ,ω)=1}
- Three regimes: (1) static DES, (2) parametric disturbance, (3) structural evolution

### System Model
- Plant state x ∈ X: combines product state + resource state
- Events Σ = Σ_c ∪ Σ_uc (controllable / uncontrollable)
- Observable / unobservable partition
- Nominal plant G_0 = (X, Σ, δ_0, x_0)

### Entities
- **Products**: Phone-class and laptop-class devices with nominal disassembly graphs
- **Resources**: Human station, robot station, inspection station, hazard-handling station
- **Latent conditions (ω)**: stripped screws, adhesive strength, missing components, battery swelling

### Supervisor-Enabled Set
- Supervisor S computes Γ_S(x̂) ⊆ Σ_c (enabled controllable events)
- Decision gate: U_exec(x̂) = U(x̂) ∩ Γ_S(x̂)
- If empty → fallback (request sensing / reroute / escalate)

### Containment Properties
- **Proposition 1**: Safety invariant preserved under admissible control
- **Proposition 2**: No-new-behavior — L(π ∘ S / G_0) ⊆ L(S / G_0)

### HoDeSU-Bench Knobs
1. Variant mixture (product-model mismatch frequency)
2. Interference severity
3. Exception frequency (stripped screw, missing fastener, stuck adhesive probs)
4. Observation quality (noise, missed detections, delays)
5. Hazard strictness (battery-safe prerequisite gating)
6. Resource unreliability (robot/tool failures)
7. PLC budget (decision latency constraints)

### Metrics
- **Correctness**: safety violations, deadlocks, forbidden-event attempts
- **Adaptation**: plan invalidations, feasibility-set changes, recovery success, belief calibration
- **Performance**: throughput, cycle time, utilization, rework time
- **Deployability**: decision latency, policy footprint, communication load

### Failure Modes
- FM1: plan invalidation cascades
- FM2: deadlock from resource contention under unexpected precedence changes
- FM3: unsafe attempt under misestimated hazard state
- FM4: excessive escalation under strict hazard gating + low observability

## WP1 Implementation Requirements

1. DES engine: event queue (heapq), simulation clock, deterministic seed
2. Demanufacturing cell model:
   - Stations: intake, inspection, robot_disassembly, manual_disassembly, hazard_handling, output
   - Resources with availability/failure modes
   - Products with uncertain attributes (ω) revealed by inspection/disassembly
3. Supervisor abstraction computing enabled set Γ_S(x̂)
4. Baseline holonic policy: routing + exception handling (no AI)
5. Scenario generator for uncertainty regimes
6. Metrics logging: throughput, time-in-system, escalations, inspection count, blocked states
7. CLI: `simulate` command → data/runs/<run_id>/events.jsonl + metrics.json

## Assumptions
- Phone-class device as default product type
- 6 stations in the cell
- Processing times drawn from distributions (seed-controlled)
- Hidden conditions sampled at product creation time
- Supervisor uses hard-coded safety rules initially
