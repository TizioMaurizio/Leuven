# HarbourSim

A discrete-event simulation of a commercial container harbour with real-time 2D visualization.

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![SimPy](https://img.shields.io/badge/SimPy-4.0+-green.svg)
![Pygame](https://img.shields.io/badge/Pygame-2.5+-red.svg)

## Overview

HarbourSim simulates the complete container flow in a harbour terminal:

1. **Ships arrive** at the harbour with batches of containers
2. **Quay cranes** unload containers from ships to the yard
3. **Containers** are stored in a grid-based yard with stacking
4. **Trucks arrive** to pick up containers and depart

The simulation tracks key performance indicators (KPIs) and provides a real-time visualization of all operations.

## Features

- **Discrete-event simulation** powered by SimPy
- **2D visualization** using Pygame showing ships, cranes, yard, and trucks
- **Configurable parameters** for all aspects of the simulation
- **Multiple policies** for crane assignment, yard placement, and container selection
- **Comprehensive metrics** including throughput, utilization, and wait times
- **Deterministic runs** via random seed for reproducibility
- **Headless mode** for fast batch runs and parameter sweeps

## Installation

### Prerequisites

- Python 3.10 or higher
- pip package manager

### Install from source

```bash
# Clone or navigate to the project directory
cd HarbourSim

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install the package
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

### Dependencies

- `simpy>=4.0.0` - Discrete event simulation
- `salabim>=23.0.0` - Auxiliary simulation library
- `pygame>=2.5.0` - 2D visualization
- `pyyaml>=6.0` - Configuration files
- `numpy>=1.24.0` - Numerical operations

```bash
python -m harbour_sim --render
# or
python run.py --render
```

### Quick Visual Demo (recommended for first-time viewers)

Run the manufacturing loop demonstrator to immediately see a compact closed-loop system in action. This is useful if you want a quick visual introduction to the kinds of simulations included in this repository.

```bash
# Run the two-station closed-loop manufacturing demo with rendering
python -m manufacturing_loop_sim --render --duration 200 --pallets 12 --speed 10
```
The command above launches a small factory layout (S1 → Conveyor → S2 → Conveyor → S1) with 12 pallets circulating. Use the window controls (ESC to quit) to explore the visualization.

### Run headless (fast, no graphics)

```bash
python -m harbour_sim --no-render
python -m harbour_sim --render --duration 240 --seed 12345 --cranes 6 --berths 4
```

## Command Line Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--render` | `-r` | True | Enable 2D visualization |
| `--no-render` | `-n` | False | Run headless without graphics |
| `--duration` | `-d` | 480 | Simulation duration (minutes) |
| `--seed` | `-s` | 42 | Random seed for reproducibility |
| `--speed` | | 10.0 | Visualization speed multiplier |
| `--yard-height` | | 10 | Yard height (rows) |
| `--max-stack` | | 4 | Maximum container stack height |
| `--ship-arrival` | | 60.0 | Mean ship interarrival time (min) |
| `--truck-arrival` | | 5.0 | Mean truck interarrival time (min) |
| `--output` | `-o` | results.csv | Output CSV file |
| `--config` | | | Load configuration from YAML |
| `--save-config` | | | Save configuration to YAML |

## Project Structure

```
HarbourSim/
├── src/harbour_sim/
│   ├── __init__.py          # Package exports
│   ├── __main__.py          # CLI entry point
│   ├── config.py            # Configuration management
│   ├── metrics.py           # KPI collection and reporting
│   ├── sim/
│   │   ├── __init__.py
│   │   ├── engine.py        # Main simulation orchestration
│   │   ├── entities.py      # Ship, Truck, Container classes
│   │   ├── resources.py     # Crane, Yard, Gate resources
│   │   └── policies.py      # Dispatch and placement policies
│   └── viz/
│       ├── __init__.py
│       └── renderer.py      # Pygame 2D visualization
├── tests/
│   ├── test_entities.py
│   ├── test_resources.py
│   └── test_simulation.py
├── pyproject.toml           # Project configuration
├── run.py                   # Alternative entry point
└── README.md
```

## Simulation Model

### Entities

- **Container**: The unit of cargo with lifecycle states (CREATED → UNLOADING → IN_YARD → ON_TRUCK → EXITED)
- **Ship**: Arrives with batch of containers, docks at berth, waits for unloading
- **Truck**: Arrives to pick up a container, waits if needed, departs with cargo

### Resources

- **Berths**: Limited docking positions for ships
- **Quay Cranes**: Unload containers from ships to yard (one container at a time)
- **Yard**: Grid-based storage area with stacking (W × H × max_height)
- **Yard Movers**: Internal transport equipment
- **Truck Gates**: Entry/exit points for trucks

### Distributions

| Parameter | Distribution | Default |
|-----------|-------------|---------|
| Ship interarrival | Exponential | μ = 60 min |
| Containers per ship | Uniform | [20, 80] |
| Crane unload time | Triangular | (2, 3, 5) min |
| Truck interarrival | Exponential | μ = 5 min |
| Truck load time | Triangular | (2, 3, 5) min |

### Policies

**Crane Assignment:**
- `NearestCranePolicy`: Assign crane nearest to berth
- `FirstAvailableCranePolicy`: Assign first idle crane

**Yard Placement:**
- `BalancedRowPolicy`: Balance containers across rows (default)
- `LowestStackPolicy`: Prefer lowest stacks
- `NearestToPickupPolicy`: Place near truck pickup point
- `RandomSlotPolicy`: Random placement

**Container Selection:**
- `FIFOContainerPolicy`: First-in-first-out (default)
- `NearestContainerPolicy`: Nearest to pickup point

## KPIs Tracked

- **Throughput**: Containers/hour, Trucks/hour
- **Ship turnaround time**: Average, min, max
- **Container dwell time**: Time in yard
- **Crane utilization**: Percentage of time busy
- **Yard occupancy**: Average and peak
- **Truck wait time**: Time from arrival to loading

## Visualization

The 2D visualization shows:

- **Water area** with animated waves
- **Quay** with berth markers (green = available, red = occupied)
- **Ships** at berths showing remaining containers
- **Quay cranes** with state indicators and container loads
- **Container yard** as a grid with stacked containers (colors vary)
- **Truck road** with gates and queuing trucks
- **Info panel** with real-time metrics

### Controls

- **ESC**: Exit simulation

## Configuration File

Save/load configuration via YAML:

```yaml
# example_config.yaml
seed: 42
duration: 480.0
num_berths: 3
num_quay_cranes: 4
yard_width: 20
yard_height: 10
yard_max_stack_height: 4
ship_interarrival_mean: 60.0
truck_interarrival_mean: 5.0
```

Usage:
```bash
# Load config
python -m harbour_sim --config example_config.yaml

# Save current config
python -m harbour_sim --save-config my_config.yaml
```

## Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=harbour_sim
```

## Example Output

```
============================================================
HARBOUR SIMULATION RESULTS
============================================================

Simulation Duration: 480.0 minutes
Random Seed: 42

--- SHIP METRICS ---
Total Ships Arrived: 8
Ships Completed: 7
Avg Turnaround Time: 45.3 min
Min/Max Turnaround: 28.1 / 72.4 min

--- CONTAINER METRICS ---
Total Containers: 392
Containers Unloaded: 358
Containers Delivered: 312
Avg Dwell Time: 24.7 min

--- CRANE METRICS ---
Total Unload Operations: 358
Crane Utilization: 67.2%

--- YARD METRICS ---
Avg Yard Occupancy: 18.3%
Max Yard Occupancy: 34.5%
Peak Container Count: 276

--- TRUCK METRICS ---
Total Trucks Arrived: 96
Trucks Served: 89
Avg Wait Time: 8.4 min

--- THROUGHPUT ---
Containers/Hour: 39.0
Trucks/Hour: 11.1
============================================================
```

## Screenshots

*Run the simulation with `--render` to see the visualization.*

The visualization displays:
- Ships docking at berths (top)
- Cranes moving along the quay
- Colorful containers in the yard grid
- Trucks arriving, loading, and departing (bottom)
- Real-time statistics panel

## License

MIT License

---

# DIGITAU Demanufacturing Simulator

This repository also includes **DIGITAU**, a battery demanufacturing digital twin refactored from HarbourSim.

## Quick Start

```bash
# Run with visualization
python -m demanufacturing_sim --render

# Run headless
python -m demanufacturing_sim --no-render --duration 480
```

## Conceptual Mapping

| HarbourSim | DIGITAU | Description |
|------------|---------|-------------|
| Container | Product/Battery | Physical item with lifecycle data |
| Ship | ProductBatch | Incoming end-of-life products |
| Quay Crane | ProcessingStation | Inspection/Dismantling/Testing |
| Yard Grid | Buffer/WIP Area | Intermediate storage |
| Yard Mover | Operator | Robot or human-robot worker |
| Truck | ExitVehicle | Transport to final destination |

## Process Flow

1. **ProductBatch arrives** → Receiving docks
2. **Inspection** → Initial quality assessment, create Digital Product Passport
3. **Dismantling** → Component separation
4. **Testing** → Final quality validation
5. **Exit Decision** → Route to REUSE (≥0.8), REMANUFACTURE (0.4-0.8), or RECYCLE (<0.4)

## Key Features

- **Multi-stage Processing Pipeline**: ARRIVAL → INSPECTION → DISMANTLING → TESTING → EXIT
- **Digital Product Passport (DPP)**: Object-centric lifecycle tracking
- **Quality-based Routing**: Products routed based on quality thresholds
- **Comprehensive KPIs**: Throughput, value recovered, station utilization

## Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--render` | False | Enable visualization |
| `--duration` | 240 | Simulation duration (minutes) |
| `--seed` | 42 | Random seed |
| `--inspection-stations` | 2 | Number of inspection stations |
| `--dismantling-stations` | 3 | Number of dismantling stations |
| `--testing-stations` | 2 | Number of testing stations |
| `--export FILE` | None | Export metrics to CSV |

For full documentation, see [README_DIGITAU.md](README_DIGITAU.md).

---

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## Acknowledgments

- [SimPy](https://simpy.readthedocs.io/) - Discrete event simulation
- [Pygame](https://www.pygame.org/) - 2D graphics
- [Salabim](https://www.salabim.org/) - Simulation components
