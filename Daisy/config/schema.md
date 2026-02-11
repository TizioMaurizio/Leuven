# Configuration Schema – Daisy DES

## Top-level keys

| Key       | Type   | Required | Description                           |
|-----------|--------|----------|---------------------------------------|
| `sim`     | object | yes      | Simulation control parameters         |
| `arrival` | object | yes      | Bin arrival distribution parameters   |
| `buffers` | object | yes      | Finite buffer capacities  (Q0–Q5)     |
| `resources`| object| yes      | Resource capacities (machines/workers) |
| `S1`–`S6` | object | yes      | Station-specific processing params    |
| `E2`, `E3`| object | yes      | Exception-handler parameters          |
| `outputs` | object | yes      | Per-device output fraction model      |
| `monitor` | object | yes      | Logging / sampling configuration      |
| `viz`     | object | no       | Pygame visualisation settings         |

## Distribution specification

Any parameter that represents a **random duration** uses the form:

```yaml
some_time:
  dist: triangular | triangular_int | exponential | bernoulli | constant
  # additional fields depend on dist:
  min: <float>       # triangular
  mode: <float>      # triangular
  max: <float>       # triangular
  rate: <float>      # exponential (1/mean)
  p: <float>         # bernoulli
  value: <float>     # constant
  to_calibrate: true # marks the parameter for calibration sweeps
  range: [lo, hi]    # sensitivity analysis bounds
```

## Probability parameters

```yaml
p_something:
  value: <float 0..1>
  range: [lo, hi]      # for sensitivity sweeps
  to_calibrate: true
```

## Buffer entry

```yaml
Qk:
  capacity: <int>    # max items; blocking when full
```

## Resource entry

```yaml
resource_name:
  capacity: <int>    # number of parallel servers
```

## Override merging

Scenario overrides are **deep-merged** over defaults:

```yaml
# scenario file
S3:
  p_battery_issue:
    value: 0.15
```

Only the specified leaf values change; everything else keeps its default.
