# WP2 Notes — Event-Sourced Evidence-Grounded Digital Twin

## Source: PAPER_2.md

## Key Concepts

### EEDT Architecture
- Event-sourced: all state derived by replaying immutable events
- Evidence-grounded: every attribute carries provenance + confidence + freshness
- Bitemporal: preserves "what was believed when" (event_time vs ingest_time)
- DES-consistent: recommendations constrained by supervisor enabled-set

### Canonical Event Schema (§4.1.1)
Fields per event:
- `event_id` (UUID), `seq_no` (monotone), `event_time`, `ingest_time`
- `type`: Observation, ActionProposed, ActionAdmitted, ActionExecuted, Exception, HumanDecision, ModelRevision, BeliefUpdate
- `actor`: Sensor, PLC, Operator, Coordinator, TwinInference
- `payload` (typed by type)
- `hash_prev` (optional hash chain)

### Evidence Model (§4.2)
- EvidenceRef = pointer to observation/inspection/inference event
- Each derived attribute: provenance={EvidenceRef...}, source, method, version
- Confidence c ∈ [0,1], valid_until = event_time + window, stale flag

### Requirements (§3)
- R1: Time-stamped state transitions with total order
- R2: Immutable append-only event store
- R3: Uncertainty metadata per attribute (value, confidence, freshness, window)
- R4: Evidence linkage / provenance pointers
- R5: Deterministic replay: same log → same state
- R6: Supervisor compatibility: recommendations ∈ Γ_S

### Properties
- Deterministic replay (Proposition 1)
- Trace completeness ratio (TCR)
- Evidence-grounded decision (Definition 3)
- DES admissibility consistency (Definition 4)

### Metrics
- TCR: |L|/|T| (trace completeness)
- RDR: replay determinism rate
- EGDP: evidence-grounded decision percentage
- Overhead: ingestion latency, storage rate, materialization time

## WP2 Implementation Requirements

1. Canonical event schema (dataclass with all fields)
2. Append-only event store (JSONL, write-once with seq_no)
3. Deterministic replay: fold(f, s0, events) materialises state
4. Query API:
   - Latest evidence for attribute X with freshness constraint
   - Trace for decision Y (provenance closure)
5. Convert WP1 DES events into canonical twin events
6. BeliefUpdate and ModelRevision as explicit event types
7. State materialisation with confidence/freshness tracking

## Assumptions
- Single-stream event log (one cell)
- seq_no assigned at ingestion time
- Stale threshold configurable per attribute type
- Hash chain optional for prototype
