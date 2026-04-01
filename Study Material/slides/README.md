# Slides — Week 1 Overview

## Files

| File | Description |
|------|-------------|
| `week1-overview.pptx` | PowerPoint overview of Week 1 (generated) |
| `make_week1_overview.py` | Python script to regenerate the slides |

## Regenerating the slides

```bash
pip install python-pptx
python make_week1_overview.py
```

This produces `week1-overview.pptx` in the current directory.

## Slide outline

1. Title slide — Week 1: DES & Supervisory Control
2. Week overview & learning path
3. What is a DES?
4. Finite automata for DES
5. The plant/supervisor feedback loop
6. Controllable vs uncontrollable events
7. Observability & partial observation
8. Safety vs liveness
9. Blocking, nonblocking, deadlock, livelock
10. Worked example: demanufacturing cell automaton
11. Worked example: supervisor rule table
12. Introduction to Petri nets
13. Petri net worked example
14. Key Week 1 takeaways
15. Recommended next steps (Week 2)
