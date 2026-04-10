---
name: critique-claims
description: Critically review claims in a paper draft for overclaiming, missing evidence, and code–claim alignment.
mode: agent
agent: Reviewer
---

Critically review the claims in the specified paper section or draft.

1. Read the draft text (PAPER_*.md, docs/wp*_notes.md, or provided text).
2. Use the `writing-review` skill checklist.
3. For each claim: verify evidence exists in the repo (run outputs, code behavior, formal arguments).
4. Check for overclaiming, missing baselines, unsupported generalization, and code–claim mismatches.
5. Rate each claim: SUPPORTED / PARTIALLY SUPPORTED / UNSUPPORTED / OVERCLAIMED.
6. Report issues with severity and suggested fixes.
