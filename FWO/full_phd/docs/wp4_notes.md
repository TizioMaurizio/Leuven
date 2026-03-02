# WP4 Notes — Bounded Semantic Mediation

Extracted from PAPER_4.md (409 lines).

## Core Idea

LLM produces **intents** (not actuator commands) over a **closed
vocabulary**.  A **deterministic mediation gate** validates, compiles,
and intersects with the DES supervisor-enabled set before execution.

## Architecture Layers

1. Event-sourced twin (WP2) — provides grounded evidence
2. Semantic mediation module (LLM) — produces structured intents
3. Deterministic validation gate — schema + grounding + compilation + ∩ A_sup
4. PLC supervisor execution — verified supervisor policy

## Closed Intent Vocabulary

Finite, typed records:
- `RequestSensing(sensor_id, target, rationale_ref)`
- `ClassifyException(class_id, evidence_refs)`
- `ProposeRouting(route_id, justification_refs)`
- `EscalateToHuman(reason, evidence_refs)`

No free-form commands.

## Deterministic Validation Gate Steps

1. **Schema/type validation** — parse + typecheck
2. **Grounding validation** — evidence_refs exist; freshness predicates hold
3. **Intent compilation** — C(i, x̂) → set of candidate DES events (|∅ possible)
4. **Model-consistency check** — C(i, x̂) ∩ A_sup(x̂)
5. **Fallback** — if empty → RequestSensing (if admissible) or EscalateToHuman

## Containment Guarantee

A_exec(x̂) = C(i, x̂) ∩ A_sup(x̂) ⊆ A_sup(x̂) for all x̂

The LLM is NEVER in the actuator path.
Language inclusion: L(LLM ∘ S/G) ⊆ L(S/G)

## Assurance Case (CAE/GSN)

- C0: System preserves verified safety constraints under LLM mediation
  - C1: Outputs restricted to closed intent schema → E1: schema tests
  - C2: Evidence-grounded → E2: runtime logs + freshness tests
  - C3: A_exec ⊆ A_sup → E3: formal proof + trace replay
  - C4: Prompt injection cannot bypass → E4: adversarial prompt suite
  - C5: Control-plane attacks blocked → E5: constrained-decoding attack tests
  - C6: Reconstructible from logs → E6: replay determinism tests

## Evaluation Configs

1. **Unconstrained**: execute LLM suggestion directly (unsafe)
2. **Schema-only**: JSON schema validation, no supervisor intersection
3. **Model-consistent gate**: schema + grounding + compilation + ∩ A_sup

## Metrics

- Containment violation rate (target: 0)
- Invalid intent rejection rate
- Escalation frequency
- Throughput impact
- Gate overhead latency

## Implementation Requirements

### R1: Intent schema
- IntentType enum (REQUEST_SENSING, CLASSIFY_EXCEPTION, PROPOSE_ROUTING, ESCALATE)
- Intent dataclass with type, args, evidence_refs

### R2: Mock LLM provider
- Deterministic seed-based mock (no API key)
- Sometimes proposes unsafe/invalid intents (for testing gate)
- Pluggable interface for future real LLM providers (TODO)

### R3: Intent compiler
- C(i, x̂) → Set[EventType]
- Maps intents to DES event candidates

### R4: Validation gate
- Schema check → grounding check → compile → ∩ A_sup
- Returns GateResult with admitted/rejected/fallback

### R5: Adversarial test suite
- Prompt injection attempts
- Invalid action suggestions
- Schema violations
- Out-of-scope commands
- Must all be caught by the gate
