# SUDE Laptop Pilot – Discrete Event Simulation

A Python discrete-event simulation (DES) of the SUDE laptop pilot control flow
(S0–S8) with real-time Pygame visualization.

## Process flow

```
S0 Arrival
 → S1 Imaging (Camera)
 → S2 Retrieval (RetrievalEngine)
 → [recognized?]
    YES → S3 Lookup → S4 Automation (RobotCell)
           → [success?]
              YES → S5 Handover (Operator)
              NO  → S7 Manual fallback (Operator)
    NO  → S6 Manual + onboarding (Operator)
 → S8 Logging → Departure
```

## Quick start

```bash
pip install -r requirements.txt

# Visual mode (Pygame window)
python main.py

# Headless mode (fast, exports files)
python main.py --headless

# Custom seed / duration
python main.py --headless --seed 123 --end 14400
```

## Controls (visual mode)

| Key         | Action                  |
|-------------|-------------------------|
| Space       | Pause / resume          |
| `+` / `-`   | Increase / decrease speed |
| `S`         | Step one event (paused) |
| `R`         | Reset (same seed)       |
| `Shift+R`   | Reset (new random seed) |
| `Esc`       | Quit                    |

## Project structure

```
├── main.py                 # Entry point (visual + headless)
├── config/
│   └── default.json        # All parameters (distributions, capacities, etc.)
├── sim/
│   ├── core.py             # Event, EventQueue, Simulator
│   ├── model.py            # Laptop, InstructionDB, Resource, World
│   ├── process.py          # S0–S8 state machine (ProcessLogic)
│   └── distributions.py    # Sampling utilities
├── viz/
│   ├── pygame_view.py      # Pygame rendering + sim/wall coupling
│   └── anim.py             # Token animation interpolation
├── outputs/
│   ├── metrics.py          # MetricsCollector, export
│   └── results/            # Generated output files
│       ├── run_summary.json
│       ├── laptop_traces.csv
│       └── time_series.csv
└── requirements.txt
```

## Configuration

Edit `config/default.json` to change:

- **Arrival rate**: `arrival_rate_per_min`
- **Processing times**: all distributions (lognormal, triangular, constant)
- **Probabilities**: recognition, automation success
- **Capacities**: operators, robot cells, cameras
- **Mode**: `"waterjet"` or `"unscrew"`
- **Learning**: initial DB size, target unique models, Zipf parameter

## Outputs

After a run, three files are exported:

- **`run_summary.json`** – throughput, ratios, cycle times, config, seed
- **`laptop_traces.csv`** – per-laptop state history and flags
- **`time_series.csv`** – periodic snapshots of WIP, queue lengths, DB size

## Key metrics

- **Throughput** (laptops/hour)
- **Retrieval ratio** (recognised / total) – improves as DB grows
- **Automation success ratio**
- **Cycle time** (average, p50, p95)
- **Resource utilization** (operator, robot cell, camera)
- **DB size** and onboarding count over time
