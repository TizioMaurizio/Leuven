# Interactive Demos — Week 1

## Purpose

These Python scripts provide visual, interactive reinforcement of Week 1 concepts. Each script is self-contained with a clear educational goal.

## Scripts

| Script | Concept | What it shows |
|--------|---------|--------------|
| `automaton_visualizer.py` | Day 2 — Automata | Draws the demanufacturing cell plant automaton, highlights initial and marked states |
| `supervisor_demo.py` | Day 6 — Supervisory control | Shows enabled/disabled controllable events at each state; traces through the supervised system |
| `petri_net_demo.py` | Day 7 — Petri nets | Visualizes places, transitions, tokens; simulates token flow for the demanufacturing net |

## Requirements

Install dependencies:

```bash
pip install -r requirements.txt
```

Dependencies: `graphviz` (Python bindings + Graphviz system install), `matplotlib`, `networkx`.

**Graphviz system install:**
- Windows: `choco install graphviz` or download from <https://graphviz.org/download/>
- macOS: `brew install graphviz`
- Linux: `sudo apt install graphviz`

## Running

```bash
# From the interactive/week1/ directory:
python automaton_visualizer.py    # Opens/saves automaton diagram
python supervisor_demo.py         # Interactive supervisor walkthrough in terminal
python petri_net_demo.py          # Opens/saves Petri net diagram + marking evolution
```

Each script saves output images to the current directory and may also display them if a GUI is available.

## What to observe

### automaton_visualizer.py
- Initial state (`Idle`) has a special arrow
- Marked states (`Recycle_Done`, `Quarantine_Done`) are double-circled
- All physically possible transitions are shown (including unsafe ones the supervisor will disable)

### supervisor_demo.py
- For each state, see which controllable events are **enabled** vs **disabled**
- Trace event sequences interactively and see the supervisor's decision at each step
- Try entering an unsafe event to see it get blocked

### petri_net_demo.py
- Places are circles with token counts
- Transitions are rectangles
- Watch tokens flow as transitions fire
- Observe resource conservation (ROBOT_FREE, INSPECTOR_FREE stay at 1 total)
