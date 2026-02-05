# Holonic Electronics Demanufacturing Digital Twin Simulation

A fully runnable Python-based research simulation for holonic electronics demanufacturing with realistic uncertainty dynamics.

## Quick Start

### Prerequisites

1. **Python 3.11+** (tested with Python 3.12)
2. **Mosquitto MQTT Broker** (see installation below)

### Installation

1. **Install Mosquitto MQTT Broker:**

   **Windows:**
   - Download from: https://mosquitto.org/download/
   - Run installer (e.g., `mosquitto-2.0.18-install-windows-x64.exe`)
   - Add Mosquitto to PATH: `C:\Program Files\mosquitto`
   - Verify: `mosquitto -h` in terminal

   **macOS:**
   ```bash
   brew install mosquitto
   ```

   **Linux (Ubuntu/Debian):**
   ```bash
   sudo apt-get install mosquitto mosquitto-clients
   ```

2. **Install Python Dependencies:**
   ```powershell
   cd digital_twin
   python -m pip install --user -r requirements.txt
   ```

3. **Run the Simulation:**
   ```powershell
   python run_simulation.py
   ```

   Options:
   ```powershell
   python run_simulation.py --no-viz           # Disable visualization
   python run_simulation.py --spawn-interval 5 # Faster product arrival
   python run_simulation.py --api-port 8080    # Custom API port
   ```

## Architecture

```
Mock Hardware (simulated physical holons)
        │
        │  MQTT messages: holon/{holon_id}/delta
        ▼
MQTT Broker (Mosquitto, local subprocess)
        │
        ▼
Digital Twin Core
  ├─ TwinEngine (SimPy-based state evolution)
  ├─ MQTTObserver (state ingestion)
  ├─ MediatorAPI (what-if queries)
  └─ Visualization (Pygame schematic)
```

### Architectural Constraints (Hard Rules)

- **Mock hardware** publishes only (never imports from `core/`, `io_layer/`, `viz/`)
- **Digital twin** subscribes only (never imports from `mock_hardware/`)
- **No shared memory** — all coordination via MQTT topics
- **Unidirectional coupling:** mock hardware → MQTT → digital twin

## Project Structure

```
digital_twin/
├── holons/               # Holon dataclasses
│   ├── product_holon.py  # Product holons with uncertainty
│   ├── resource_holon.py # Robot/Operator holons
│   └── uncertainty.py    # Uncertainty modeling
├── core/                 # Digital twin engine
│   ├── twin_engine.py    # SimPy-based state evolution
│   └── state_store.py    # SQLite persistence
├── io_layer/             # I/O layer (renamed from 'io')
│   ├── mqtt_observer.py  # MQTT state ingestion
│   └── mediator_api.py   # Flask REST API
├── viz/                  # Visualization
│   └── schematic_view.py # Pygame schematic display
├── mock_hardware/        # Simulated physical layer
│   ├── mqtt_broker.py    # Mosquitto subprocess wrapper
│   ├── mock_factory.py   # Spawns electronic devices
│   ├── mock_robot.py     # Robot with uncertainty-driven success
│   └── mock_operator.py  # Operator with cognitive load
├── run_simulation.py     # One-command execution entry point
└── requirements.txt      # Python dependencies
```

## REST API Endpoints

Base URL: `http://localhost:5000`

### State Inspection

- `GET /health` - Health check
- `GET /api/products` - List all product holons
- `GET /api/products/<holon_id>` - Get specific product
- `GET /api/products/state/<state>` - Filter by state (ARRIVED, IN_PROGRESS, COMPLETED, etc.)
- `GET /api/products/interventions` - Products needing human intervention
- `GET /api/robots` - List all robot holons
- `GET /api/operators` - List all operator holons

### What-If Queries

- `POST /api/what-if/assign` - Simulate product-to-resource assignment
  ```json
  {
    "product_id": "dell_001",
    "resource_id": "arm_01"
  }
  ```

- `POST /api/what-if/batch-assign` - Evaluate multiple assignment options
  ```json
  {
    "product_id": "dell_001",
    "resource_ids": ["arm_01", "arm_02", "op_01"]
  }
  ```

### Statistics

- `GET /api/stats` - Runtime statistics
- `GET /api/snapshot` - Complete state snapshot
- `GET /api/history/<holon_id>?limit=100` - State change history

## Example API Usage

```powershell
# List all products
curl http://localhost:5000/api/products

# Get statistics
curl http://localhost:5000/api/stats

# What-if query: assign product to robot
curl -X POST http://localhost:5000/api/what-if/assign `
  -H "Content-Type: application/json" `
  -d '{\"product_id\": \"dell_001\", \"resource_id\": \"arm_01\"}'

# Batch assignment evaluation
curl -X POST http://localhost:5000/api/what-if/batch-assign `
  -H "Content-Type: application/json" `
  -d '{\"product_id\": \"dell_001\", \"resource_ids\": [\"arm_01\", \"arm_02\", \"op_01\"]}'
```

## Behavioral Models

### Speed Controls

The visualization includes interactive speed controls:
- **<< Button:** Decrease simulation speed (0.25x, 0.5x, 1.0x, 2.0x, 4.0x, 8.0x)
- **>> Button:** Increase simulation speed
- Click the buttons in the top-right corner to adjust speed in real-time
- Default speed: 1.0x (real-time)

Speed multiplier affects:
- SimPy time advancement rate
- Wall-clock sleep intervals between simulation steps
- Overall simulation execution speed (8x = 8 times faster)

### Mock Factory
- Spawns heterogeneous electronic devices (laptops, smartphones, tablets)
- Each device has initial uncertainty metrics
- Configurable spawn interval (default: 8 seconds)

### Mock Robots
- **Profiles:** standard, precision, fast
- **Success probability:** Inversely proportional to product uncertainty
- **Fatigue accumulation:** Reduces performance over time
- **Autonomous claiming:** Robots claim unassigned products

### Mock Operators
- **Cognitive load dynamics:** Bounded random walk
- **State transitions:** AVAILABLE → BUSY → OVERLOADED
- **Intervention:** Handle high-uncertainty cases that robots fail
- **Profiles:** novice, experienced, expert

### Uncertainty Model
Product holons carry explicit uncertainty across multiple dimensions:
- `fastener_type`: Uncertainty about fastener types
- `battery_condition`: Battery damage/swelling risk
- `component_fragility`: Fragility during handling
- `material_composition`: Material classification uncertainty
- `hidden_fasteners`: Concealed fastener discovery

Higher uncertainty → Lower robot success probability → More likely to need human intervention

## Timing Model

- **Mock hardware:** Runs in real wall-clock time
- **TwinEngine:** Uses SimPy simulation time
- **Main loop:** Advances SimPy in small increments to keep pace with MQTT events

## Troubleshooting

### "ModuleNotFoundError: No module named 'X'"
Install missing dependency for your specific Python executable:
```powershell
C:/Users/YOUR_USER/AppData/Local/Microsoft/WindowsApps/python3.12.exe -m pip install --user X
```

### "Mosquitto not found on system PATH"
- Ensure Mosquitto is installed
- Add Mosquitto to PATH or specify full path in `mqtt_broker.py`
- Windows: Add `C:\Program Files\mosquitto` to system PATH

### "Port already in use" (5000 or 1883)
```powershell
python run_simulation.py --api-port 8080 --mqtt-port 1884
```

### Visualization window not opening
Run without visualization:
```powershell
python run_simulation.py --no-viz
```

## Research Notes

### Cognitive Mediation
The `MediatorAPI` provides what-if query capabilities for decision support:
- Predict success probability for product-resource assignments
- Evaluate multiple assignment options simultaneously
- Consider uncertainty, resource fatigue, and cognitive load

### State History
All state changes are logged to SQLite for post-analysis:
```python
from core.state_store import StateStore
store = StateStore("simulation.db")
history = store.get_history("dell_001", limit=100)
```

### Extending the Simulation
1. Add device types in `mock_factory.py::DEVICE_PROFILES`
2. Customize robot behaviors in `mock_robot.py`
3. Implement cognitive mediation strategies in `core/twin_engine.py::what_if_*`

## License

Research simulation for holonic electronics demanufacturing.

## Citation

If you use this simulation in research, please cite:
```
[Your paper citation here]
```

## Contact

[Your contact information]
