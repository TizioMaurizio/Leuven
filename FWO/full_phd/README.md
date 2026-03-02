# Demanuf — Holonic Demanufacturing Coordination Architecture

Research prototype implementing a holonic demanufacturing coordination system
with structural uncertainty, event-sourced digital twin, conservative learning,
and bounded semantic mediation.

## Quick Start

```bash
# No external dependencies required for core functionality
# Python 3.10+ with standard library is sufficient

# Run a headless simulation
python -m demanuf.cli simulate --seed 1 --steps 200

# Launch the graphical interface
python -m demanuf.gui

# Run tests
python -m pytest -q
# or without pytest:
python -m unittest discover -s tests -q
```

## Project Structure

```
demanuf/
  cli.py          # Command-line interface
  gui.py          # Tkinter graphical interface
  config.py       # Configuration and uncertainty regimes
  des/            # Discrete Event Simulation engine
  holons/         # Holonic coordination protocol and policies
  twin/           # Event-sourced digital twin (WP2)
  learning/       # Conservative learning components (WP3)
  mediation/      # Bounded semantic mediation (WP4)
  eval/           # Evaluation harness (WP5)
docs/             # Documentation and WP notes
tests/            # Test suite
data/             # Generated run data
```

## CLI Commands

```bash
# Basic simulation
python -m demanuf.cli simulate --seed 1 --steps 50

# High-uncertainty regime
python -m demanuf.cli simulate --seed 1 --steps 200 --regime high

# Custom output directory
python -m demanuf.cli simulate --seed 42 --steps 100 --output data/my_runs

# Ablation evaluation (A0-A4, 5 seeds, medium regime)
python -m demanuf.cli eval --seeds 5 --steps 100

# Evaluate specific ablations
python -m demanuf.cli eval --ablations A0 A4 --seeds 10 --regime high
```

## GUI

Launch with `python -m demanuf.gui`. Controls:
- **Start**: Begin auto-stepping the simulation
- **Pause**: Pause auto-stepping
- **Step**: Execute one DES event
- **Reset**: Reset simulation (respects seed spinbox)
- **Load Run**: Replay a past `events.jsonl` file

## Dependencies

- **Core**: Python 3.10+ standard library only (tkinter, heapq, json, dataclasses, etc.)
- **Tests**: `pytest` (optional; `unittest` works too)
- **Plots**: `matplotlib` (optional; only for WP5 evaluation reports)
