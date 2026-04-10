---
name: python-unit-test
description: Multi-step workflow to create Python unit tests (pytest/unittest) adhering to the repository setup. Tailored for DES simulation and research modules.
argument-hint: "E.g.: 'Add unit tests for Daisy/sim/stations.py' or 'Test coverage for the belief update module'"
compatibility: Python projects with existing test framework (pytest, unittest) or no tests.
disable-model-invocation: false
user-invokable: true
license: MIT
metadata:
  stack: Python
  type: unit testing
  frameworks: [pytest, unittest]
  languages: [Python]
---

## User Input

```text
$ARGUMENTS
```

## Goal

Create Python unit tests focused on logic, edge cases, and regressions for simulation and research modules.

## Bundled assets

- `templates/test_module_template.py`

## Workflow

1. Detect active framework (`pytest` or `unittest`) and folder conventions.
2. Map critical functions/classes and error paths in the target module.
3. Create parameterized tests and mock external dependencies (MQTT, file I/O).
4. Run target tests and verify failure output.
5. Report incremental coverage and uncovered cases.

## Simulation & Research Test Focus Areas

- **DES engine**: Verify event ordering, causal correctness, deterministic replay with same seed.
- **Station/process logic**: Test processing times, resource acquisition, exception paths (jams, failures).
- **Distribution sampling**: Test that seeded distributions produce reproducible outputs.
- **Entity lifecycle**: Test creation, state transitions, completion, and discard paths.
- **Resource constraints**: Test capacity enforcement, queue discipline, blocking behavior.
- **Belief updates**: Test monotonic refinement — feasible set never expands without new evidence.
- **Supervisor constraints**: Test that only supervisor-enabled actions are selected.
- **Config loading**: Test YAML/JSON config parsing, schema validation, default values.
- **Event logging**: Test that monitor produces correct CSV output without altering simulation state.
- **Metric computation**: Test metric aggregation, warm-up exclusion, per-seed reproducibility.

## Rules

- If `pytest` is present, prefer it.
- Do not depend on network or real filesystem except for dedicated fixtures.
- Use descriptive test names and single responsibility per test.
- Always test with reproducible seeds — never use unseeded randomness in tests.
- Mock MQTT connections — never connect to live brokers in tests.
- Test that identical seed + config produces identical event logs.
