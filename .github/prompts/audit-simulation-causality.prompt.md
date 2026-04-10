---
name: audit-simulation-causality
description: Audit simulation code for causal correctness — no lookahead, no retroactive state changes, proper event ordering.
mode: agent
agent: Control
---

Audit the simulation code for causal correctness.

1. Read the simulation engine and model files for the target project (Daisy/sim/, SUDE/sim/, FWO/full_phd/demanuf/des/, or DES Playground/src/*/sim/).
2. Use the `simulation-causality-audit` skill procedure.
3. Check that at time T, only events and observations with timestamps ≤ T are used.
4. Check for retroactive state modifications, future-data access, or non-deterministic event ordering.
5. Run `pytest tests/ -q` in the relevant project to verify existing tests pass.
6. Report pass/fail for each check with file/line evidence.
