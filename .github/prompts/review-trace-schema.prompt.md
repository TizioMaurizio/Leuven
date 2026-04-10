---
name: review-trace-schema
description: Review event log schema and trace completeness for a simulation project.
mode: agent
agent: Twin
---

Review the event log schema and trace completeness.

1. Read the monitor/logging module for the target project.
2. Use the `trace-completeness-audit` skill procedure.
3. Check: all state transitions logged? Event types documented? Fields complete?
4. Check: metadata.json present with config, seed, code version, timestamp?
5. Check: replay from event log reproduces identical state?
6. Report trace coverage and any gaps in the event schema.
