---
name: check-invariants
description: Check formal invariants, supervisor constraints, and containment guarantees after a code change.
mode: agent
agent: Control
---

Check formal invariants and containment guarantees.

1. Read the supervisor module (`FWO/full_phd/demanuf/des/supervisor.py`) and any changed simulation or learning files.
2. Use the `invariant-review` skill procedure.
3. Verify: every executed action is in the supervisor-enabled set.
4. Verify: no-new-behavior containment holds (executed language ⊆ supervisor's closed-loop language).
5. Verify: belief updates are monotonically refining (if learning modules changed).
6. Report containment violation count (target: zero) with evidence for any violations.
