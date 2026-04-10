---
name: draft-methodology
description: Draft a methodology section for a paper, grounded in the actual simulation code and configs.
mode: agent
agent: Writing
---

Draft the methodology section for the specified paper.

1. Read the relevant PAPER_*.md file to understand the paper's scope and contributions.
2. Read the simulation code, config files, and any relevant module implementations.
3. Draft the methodology section covering: simulation model, architecture, formal properties, and evaluation setup.
4. Ground every claim in a specific file or config parameter — use `[SOURCE: file/path]` annotations.
5. Use `[RESULT: metric, scenario]` placeholders for any results not yet computed.
6. Flag the draft to the Reviewer agent for critique.
