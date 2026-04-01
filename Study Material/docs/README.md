# Study Materials — PhD Preparation

This repository contains structured, self-study learning packages for a PhD on **holonic demanufacturing under structural uncertainty**, with an evidence-grounded digital twin and bounded semantic mediation layer.

## Weekly learning packages

| Week | Topic | Status |
|------|-------|--------|
| [Week 1](week1/README.md) | Discrete Event Systems, Supervisory Control, Introductory Petri Nets | ✅ Available |
| Week 2 | Structural uncertainty, belief states, partial observability | 🔜 Planned |
| Week 3 | Event-sourced digital twins, process mining | 🔜 Planned |
| Week 4 | Conservative learning, calibration, conformal prediction | 🔜 Planned |
| Week 5 | Bounded semantic mediation, validation gates | 🔜 Planned |

## How to use

1. Start with the Week 1 [README](week1/README.md) for an overview and day-by-day reading path.
2. Follow the daily lesson pages in order (or jump to specific topics).
3. Run the [interactive demos](../interactive/week1/) locally for hands-on reinforcement.
4. Use the [exercises](week1/exercises.md) and [solutions](week1/exercise-solutions.md) for self-assessment.
5. Review the [PowerPoint overview](../slides/week1-overview.pptx) for a quick summary.

## Repository layout

```
docs/
  week1/          ← Week 1 learning package (Markdown-first)
interactive/
  week1/          ← Runnable Python demos for Week 1
slides/
  week1-overview.pptx     ← PowerPoint summary
  make_week1_overview.py  ← Script to regenerate the slides
```

## Conventions

- All material is **Markdown-first**, optimized for reading on GitHub.
- Diagrams use [Mermaid](https://mermaid.js.org/) syntax embedded directly in Markdown.
- Every major concept is grounded in at least one authoritative source (linked inline and in bibliography).
- Worked examples are drawn from a **demanufacturing cell** scenario aligned with the PhD proposal.
