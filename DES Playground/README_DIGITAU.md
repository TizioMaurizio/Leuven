# DIGITAU Demanufacturing Simulator

A discrete-event simulation and visualization system for modeling battery and product lifecycle management in a circular economy context.

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![SimPy](https://img.shields.io/badge/SimPy-4.0+-green.svg)
![Pygame](https://img.shields.io/badge/Pygame-2.5+-red.svg)

## Overview

**DIGITAU** simulates a battery demanufacturing facility where end-of-life products undergo inspection, dismantling, and testing before being routed to their optimal circular economy destination.

### Process Flow

1. **Product Batches arrive** (incoming end-of-life products)
2. **Inspection Stations** assess initial quality and create Digital Product Passports
3. **Dismantling Stations** separate components for further processing
4. **Testing Stations** perform final quality assessment
5. **Exit Decision** routes products to: **Reuse**, **Remanufacture**, or **Recycle**

## Conceptual Mapping from HarbourSim

This simulator was refactored from the HarbourSim harbour terminal simulation. The following mapping preserves the original architecture while adapting it to the demanufacturing domain:

| HarbourSim Concept | DIGITAU Concept | Description |
|-------------------|-----------------|-------------|
| Container | Product/Battery | Physical item with lifecycle data |
| Ship | ProductBatch | Incoming stream of end-of-life products |
| Quay Crane | Processing Station | Inspection, Dismantling, Testing stations |
| Yard Grid | Buffer / WIP Area | Intermediate storage between stages |
| Yard Mover | Operator | Robot or human-robot collaborative worker |
| Truck | Exit Vehicle | Transport to reuse/remanufacture/recycle |
| Container Metadata | Digital Product Passport (DPP) | Tracks quality, processing history, predictions |

## Key Features

- **Multi-stage Processing Pipeline**: ARRIVAL → INSPECTION → DISMANTLING → TESTING → DECISION → EXIT
- **Digital Product Passport (DPP)**: Object-centric lifecycle tracking for each product
- **Quality-based Routing**: Products routed based on assessed quality thresholds
- **Predictive Models**: Rule-based quality predictions with configurable accuracy
- **Exit Decisions**: Three paths - Reuse (quality ≥ 0.8), Remanufacture (0.4-0.8), Recycle (< 0.4)
- **Real-time Visualization**: Factory layout with color-coded product states
- **Comprehensive KPIs**: Throughput, value recovered, station utilization, dwell times

## Installation

```bash
# Navigate to project directory
cd HarbourSim

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install the package
pip install -e .
```

## Quick Start

### Run with Visualization

```bash
python -m demanufacturing_sim --render
```

### Run Headless (Fast)

```bash
python -m demanufacturing_sim --no-render
```

### Custom Parameters

```bash
python -m demanufacturing_sim --render --duration 480 --seed 123 \
    --inspection-stations 3 --dismantling-stations 4 --testing-stations 2
```

## Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--render` / `-r` | False | Enable pygame visualization |
| `--no-render` | True | Run headless without graphics |
| `--duration` / `-d` | 240 | Simulation duration (minutes) |
| `--seed` / `-s` | 42 | Random seed for reproducibility |
| `--speed` | 60.0 | Visualization speed multiplier |
| `--inspection-stations` | 2 | Number of inspection stations |
| `--dismantling-stations` | 3 | Number of dismantling stations |
| `--testing-stations` | 2 | Number of testing stations |
| `--operators` | 6 | Number of operators |
| `--exit-gates` | 2 | Number of exit gates per category |
| `--buffer-capacity` | 100 | Buffer capacity (products) |
| `--export` / `-e` | None | Export metrics to CSV file |
| `--quiet` / `-q` | False | Suppress summary output |
| `--verbose` / `-v` | False | Enable verbose logging |

## Output Metrics

The simulation tracks and reports:

### Product Metrics
- Total products processed
- Average dwell time (time in system)
- Processing time per stage

### Exit Decision Breakdown
- Reuse count and percentage
- Remanufacture count and percentage  
- Recycle count and percentage

### Station Utilization
- Inspection station utilization
- Dismantling station utilization
- Testing station utilization

### Value Metrics
- Total value recovered ($)
- Value per product
- Value recovery rate (%)

### Throughput
- Products per hour
- Breakdown by exit category

## Project Structure

```
src/demanufacturing_sim/
├── __init__.py          # Package exports
├── __main__.py          # CLI entry point
├── config.py            # Simulation configuration
├── metrics.py           # KPI collection and reporting
├── sim/
│   ├── __init__.py      # Simulation module exports
│   ├── entities.py      # Product, Batch, DPP, ExitVehicle
│   ├── resources.py     # Stations, Buffer, Operators, Gates
│   ├── policies.py      # Routing and assignment policies
│   └── engine.py        # Main simulation orchestration
└── viz/
    ├── __init__.py      # Visualization exports
    └── renderer.py      # Pygame factory visualization
```

## Digital Product Passport (DPP)

Each product carries a Digital Product Passport containing:

```python
@dataclass
class DigitalProductPassport:
    product_type: str           # e.g., "LI_ION_BATTERY"
    manufacturer: str           # Original manufacturer
    production_date: datetime   # When product was made
    initial_quality: float      # Quality at arrival (0-1)
    current_quality: float      # Updated during processing
    processing_history: List    # Record of all processing steps
    predicted_decision: ExitDecision  # ML/rule-based prediction
    actual_decision: ExitDecision     # Final routing decision
```

## Configuration

The simulation is fully configurable via `SimConfig`:

```python
config = SimConfig(
    # Timing
    duration=480,              # 8 hours
    random_seed=42,
    
    # Batch arrivals
    batch_interarrival_mean=30.0,
    products_per_batch_mean=15,
    
    # Stations
    num_inspection_stations=2,
    num_dismantling_stations=3,
    num_testing_stations=2,
    
    # Processing times (minutes)
    inspection_time_mean=5.0,
    dismantling_time_mean=15.0,
    testing_time_mean=8.0,
    
    # Quality thresholds
    reuse_threshold=0.8,
    remanufacture_threshold=0.4,
    
    # Value recovered ($)
    value_per_reuse=500.0,
    value_per_remanufacture=200.0,
    value_per_recycle=50.0,
)
```

## Architecture Notes

### SimPy Integration
The simulation uses SimPy for discrete-event modeling:
- Resources for stations, operators, gates
- Processes for product lifecycle stages
- Environment for time management

### Pygame Visualization
The factory renderer displays:
- Receiving docks (left side)
- Processing stations (inspection → dismantling → testing)
- Buffer/WIP area (center)
- Exit gates (right side)
- Info panel with real-time KPIs

### Preserved from HarbourSim
- SimPy-based discrete-event engine
- Pygame rendering infrastructure
- Policy-based decision making
- Metrics collection framework
- CLI argument parsing pattern

## License

MIT License

## Original Project

This simulator is refactored from [HarbourSim](./README_HARBOUR.md), a discrete-event harbour terminal simulation.
