---
name: simulation-causality-audit
description: Step-by-step procedure to audit simulation code for causal correctness — no lookahead, no retroactive state changes, deterministic event ordering. Use when reviewing any simulation model, process, or decision logic.
---

# Simulation Causality Audit

## Goal

Verify that simulation logic at time T uses **only** events and observations with timestamps ≤ T, and that no retroactive state modifications occur.

## Procedure

### 1. Identify the simulation entry point

Find the main simulation loop or process generator. In this repo, start with:
- `Daisy/sim/system.py` → SimPy process generators for the disassembly line.
- `SUDE/sim/model.py` → Custom DES `World` model.
- `FWO/full_phd/demanuf/des/engine.py` → DES engine step logic.
- `DES Playground/src/*/sim/engine.py` → Per-simulation engine.

### 2. Trace event ordering

For each process or event handler:
- Does it access only the current simulation time and past events?
- Are SimPy `yield` statements properly ordered (request → process → release)?
- Does the custom DES engine process events in non-decreasing timestamp order?

### 3. Check for dangerous patterns

| Pattern | Why It Leaks | Fix |
|---------|-------------|-----|
| Accessing future events in event list | Decision uses information not yet available | Filter to events with timestamp ≤ current |
| Retroactive state modification | Changes state at a past timestamp | Apply state changes only at current time |
| Non-deterministic event ordering | Ties broken by insertion order, dict order, or set iteration | Use stable tie-breaking (entity ID, event type priority) |
| Global state read before event processing | State reflects future events already processed | Process events one at a time, update state after each |
| `random.random()` without seed | Non-reproducible behavior | Use seeded RNG from config |
| `time.time()` or `datetime.now()` in sim logic | Real-world time leaks into simulation | Use only simulation clock |
| Observer/monitor altering simulation state | Logging affects outcomes | Ensure observer is read-only |

### 4. Resource constraint verification

- Are SimPy `Resource` / `Store` / `Container` capacities enforced?
- Can an entity bypass a full buffer or acquire a busy resource?
- Is queue discipline (FIFO, priority) deterministic and documented?

### 5. Reproducibility test

Run the simulation twice with identical seed + config:
- Same number of events?
- Same event timestamps?
- Same entity states at each timestamp?
- Same output metrics?

If any differ, there is a non-determinism bug.

### 6. Warm-up verification

- Is a warm-up period defined in config?
- Are metrics computed only from post-warm-up events?
- Does the monitor correctly exclude warm-up events?

## Report

For each check:
- PASS / FAIL with evidence.
- File and line reference.
- Severity: **CRITICAL** (changes simulation outcomes), **HIGH** (affects metrics), **LOW** (cosmetic).
- Suggested fix if FAIL.
