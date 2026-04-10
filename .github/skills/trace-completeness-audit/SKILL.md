---
name: trace-completeness-audit
description: Procedure to verify that event logs capture all significant state transitions, that schemas are complete, and that replay produces identical state.
---

# Trace Completeness Audit

## Goal

Verify that simulation event logs are complete, well-structured, and sufficient for deterministic replay and evidence provenance.

## Procedure

### 1. Schema Review

- Read the event schema definition (e.g., `FWO/full_phd/demanuf/twin/schema.py`, `Daisy/sim/monitor.py`).
- List all defined event types.
- For each event type, verify required fields: timestamp, event_type, entity_id, location/station, details.
- Check for optional fields: evidence_id, confidence, source, duration.

### 2. Coverage Analysis

For each significant state transition in the simulation:

| Transition | Should Log | Actually Logged? |
|------------|-----------|-----------------|
| Entity creation / arrival | Yes | ? |
| Station entry (start processing) | Yes | ? |
| Station exit (end processing) | Yes | ? |
| Buffer enqueue / dequeue | Yes | ? |
| Resource request / acquire / release | Yes | ? |
| Exception triggered (jam, failure, unknown) | Yes | ? |
| Exception resolved | Yes | ? |
| Belief update | Yes (if uncertainty module active) | ? |
| Decision made (action selected) | Yes | ? |
| Entity completion / departure | Yes | ? |

### 3. Ordering Verification

- Confirm events are written in non-decreasing timestamp order.
- Check tie-breaking policy: is it stable and deterministic?
- Verify that interleaved processes don't produce out-of-order events.

### 4. Metadata Completeness

Check metadata.json (or equivalent) for:
- [ ] Config file used (name or embedded content).
- [ ] Seed value.
- [ ] Code version (git commit hash or manual version).
- [ ] Timestamp of run.
- [ ] Runtime duration.
- [ ] Simulation parameters summary.

### 5. Replay Test

If a replay module exists:
- Load an event log.
- Replay through the event sequence.
- Compare final state against the original simulation's final state.
- Verify intermediate states at sampled checkpoints.
- Report any divergence.

### 6. Evidence Provenance (if applicable)

For systems with belief/uncertainty modules:
- [ ] Each belief update event references the evidence event(s) that triggered it.
- [ ] Evidence events have confidence/freshness metadata.
- [ ] The chain from observation → evidence → belief update → action is traceable in the log.

## Report

For each check:
- COMPLETE / PARTIAL / MISSING with evidence.
- List of unlogged state transitions.
- Schema gaps (missing fields, undocumented event types).
- Replay divergence details if any.
