--- 
name: academic-materials-repo
applyTo: "**"
description: Repository-wide guidance for building academically rigorous, proposal-aligned study materials and interactive learning assets with GitHub Copilot custom agents.
---

# Academic Materials Repository Instructions

This repository is used to prepare study and teaching materials for a PhD on holonic demanufacturing under structural uncertainty, with an evidence-grounded digital twin and bounded semantic mediation layer.

## Default priorities

1. Formal DES and supervisory control first.
2. Petri nets and holonic coordination second.
3. Structural uncertainty and partial observability next.
4. Event-sourced digital twins and traceability after that.
5. Conservative learning for update/ask decisions after the state layer is clear.
6. LLM mediation only as a bounded, validated exception-handling layer.

## Material quality rules

- Be academically precise.
- Prefer primary or authoritative sources.
- Use the web to verify any claim that depends on current information.
- Distinguish clearly between fact, interpretation, and design suggestion.
- Do not fabricate references, definitions, formal guarantees, or equations.
- Keep examples grounded in the demanufacturing context whenever possible.

## Output conventions

Prefer this folder structure for new content:

```text
study-materials/
  00_overview/
  01_des-supervisory-control/
  02_petri-nets-holonic-control/
  03_structural-uncertainty-belief-states/
  04_digital-twins-event-sourcing/
  05_conservative-learning/
  06_bounded-semantic-mediation/
  references/
  interactive/
  assessments/
  flashcards/
```

## File conventions

- Use Markdown for notes, reading packs, glossaries, and assessments.
- Use self-contained HTML/CSS/JS for simple interactive demos unless a heavier stack is explicitly requested.
- Use Python notebooks or scripts only when they materially improve explanation.
- Add a brief usage note to each executable artifact.

## Pedagogy conventions

Every substantive module should explain:
- why the topic matters for the PhD
- prerequisites
- core concepts
- one domain-grounded worked example
- common confusions
- next recommended reading or exercise

## Language

Default to English unless the user explicitly asks for Italian.

## Tooling note

The custom agents in this repository assume use in GitHub Copilot Chat / agent workflows with access to read/search/edit tools and, in IDE environments, the built-in `web` tool. If the current environment does not support `web`, fall back to repository sources and clearly state the limitation.
