---
name: troubleshoot-python
description: Workflow to diagnose and resolve Python bugs (runtime, import, I/O, dependencies) with root cause analysis. Tailored for DES simulation and research code.
argument-hint: "E.g.: 'SimPy resource deadlock in Daisy' or 'ImportError in SUDE/sim/model.py'"
compatibility: Python projects with runtime bugs or environment issues.
disable-model-invocation: false
user-invokable: true
license: MIT
metadata:
  stack: Python
  type: troubleshooting
  languages: [Python]
---

# Troubleshooter Python

Use this skill for Python runtime exceptions, import problems, environment mismatches, I/O errors, or logic regressions in the simulation and research codebase.

## Goal

- Reproduce the error in the same execution context.
- Distinguish code bugs from environment issues.
- Apply a minimal, verifiable fix.

## Workflow

1. Reproduce with full context
   - Gather command, Python version, active env, complete traceback.
   - If complete traceback is missing, request it before modifying code.

2. Classify the problem
   - `ImportError`/`ModuleNotFoundError` → dependencies or path issues.
   - `TypeError`/`AttributeError` → object contract violation.
   - I/O/config errors → paths, permissions, environment variables.
   - Numeric errors → NaN propagation, division by zero, overflow.
   - SimPy errors → resource deadlocks, process ordering, event scheduling.

3. Isolate root cause
   - Reduce to minimal reproducible case.
   - Verify hypothesis with a targeted test/command.

4. Apply fix
   - Fix the actual point of failure, not just symptoms.
   - Maintain compatibility with existing repository conventions.
   - Ensure fix does not break seed reproducibility.

5. Validate
   - Run targeted tests or the command that previously failed.
   - If appropriate, run a broader non-destructive check.

6. Final report
   - Root cause, updated files, validation commands, known limitations.

## Simulation-Specific Checks

- SimPy: Resource deadlocks, process generator issues, event ordering.
- Custom DES engines: Event queue correctness, timestamp ordering, event type handling.
- Pygame/Tkinter: Display initialization, event loop conflicts, rendering state sync.
- MQTT (digital twin): Connection handling, message ordering, topic matching.
- Config loading: YAML/JSON parsing, missing keys, schema mismatches.
- Event logging: CSV write errors, encoding issues, path handling on Windows.
- Seeded RNG: Verify fix doesn't introduce non-determinism.
- Distribution sampling: Parameter validation, edge cases (zero variance, negative values).

## Quick Checks

- Correct environment/venv active?
- Declared vs used dependencies match?
- Explicit error handling at I/O boundary points?
- Function types and contracts consistent?
- Windows path separators handled correctly?
