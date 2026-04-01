# Exercise Solutions — Week 1

[← Back to exercises](exercises.md) · [Back to Week 1 overview](README.md)

---

## Solution 1 — Event taxonomy

Sample event alphabet for a smartphone demanufacturing cell:

| Event | Meaning | Ctrl? | Obs? | Source | Safety-critical? |
|-------|---------|:---:|:---:|--------|:---:|
| `phone_arrive` | Phone arrives on conveyor | No | Yes | Sensor | No |
| `xray_start` | Command to start X-ray scan | Yes | Yes | PLC | No |
| `xray_ok` | X-ray: no hazard detected | No | Yes | Sensor | Yes — false negative is dangerous |
| `xray_hazard` | X-ray: hazard detected | No | Yes | Sensor | Yes — must trigger quarantine |
| `grip_phone` | Robot grips the phone | Yes | Yes | PLC | No |
| `grip_fail` | Grip fails (dropped phone) | No | Partially | Sensor | Yes — phone in unknown state |
| `remove_screen` | Robot removes screen assembly | Yes | Yes | PLC | No |
| `remove_battery` | Robot extracts battery | Yes | Yes | PLC | Yes — battery manipulation |
| `neutralise_batt` | Battery placed in chemical bath | Yes | Yes | PLC | Yes — chemical process |
| `route_recycle` | Phone to recycling bin | Yes | Yes | PLC | No |
| `route_hazwaste` | Phone to hazardous waste bin | Yes | Yes | PLC | No |
| `e_stop` | Emergency stop by operator | No | Yes | Human | Yes — interrupts everything |

Safety-critical events (3+):
1. `xray_ok` — a false negative means a hazardous phone enters the disassembly stream
2. `xray_hazard` — must lead to safe quarantine, never to recycling
3. `remove_battery` — battery manipulation carries fire/explosion risk
4. `neutralise_batt` — chemical process must complete before further handling

---

## Solution 2 — Plant automaton

### Formal tuple

$G = (Q, \Sigma, \delta, q_0, Q_m)$ where:
- $Q = \{$`Idle`, `Intake`, `Inspected_OK`, `Inspected_Suspect`, `Opened`, `Battery_Removed`, `Recycle_Done`, `Quarantine_Done`, `Faulted`$\}$
- $\Sigma = \{$`arrival`, `inspect_ok`, `inspect_sus`, `unscrew_cover`, `remove_battery`, `route_recycle`, `route_quarantine`, `fault`$\}$
- $q_0 =$ `Idle`
- $Q_m = \{$`Recycle_Done`, `Quarantine_Done`$\}$

The `fault` transition: `Opened` → `Faulted` via `fault` (uncontrollable).

`Faulted` is **not** a marked state because a fault is not a successful completion. This creates a potential blocking issue (see Exercise 5 reasoning) — the `Faulted` state needs a recovery path to maintain nonblocking.

### Example traces

| # | Trace | $\in L(G)$? | $\in L_m(G)$? | Safe? |
|---|-------|:---:|:---:|:---:|
| 1 | `arrival, inspect_ok, unscrew_cover, remove_battery, route_recycle` | ✅ | ✅ | ✅ |
| 2 | `arrival, inspect_sus, route_quarantine` | ✅ | ✅ | ✅ |
| 3 | `arrival, inspect_sus, route_recycle` | ✅ | ✅ | ❌ |
| 4 | `arrival, inspect_ok, unscrew_cover, fault` | ✅ | ❌ | Depends on handling |
| 5 | `arrival, inspect_ok, route_recycle` | ✅ | ✅ | ❌ (battery not removed) |

---

## Solution 3 — Safety specifications

### Three safety rules

**S1 (hazard rule):**
- Informal: "Suspect units must not be opened or recycled."
- Formal: Transitions `(Inspected_Suspect, unscrew_cover)` and `(Inspected_Suspect, route_recycle)` are forbidden.

**S2 (battery rule):**
- Informal: "Units must not be recycled unless the battery has been removed."
- Formal: `route_recycle` is forbidden from all states except `Battery_Removed`.

**S3 (fault recovery):**
- Informal: "A faulted unit must be quarantined, not recycled or further processed."
- Formal: From `Faulted`, only `route_quarantine` is allowed (controllable); any other controllable event is disabled.

### Why forbidden transitions must involve controllable events

If a forbidden transition involves an **uncontrollable** event, no supervisor can prevent it. For example, if `inspect_sus` (uncontrollable) directly led to an unsafe state, the supervisor could not help — the plant design itself would need to change. The controllability condition requires that $\overline{K}\,\Sigma_{uc} \cap L(G) \subseteq \overline{K}$: the legal language must already accommodate all uncontrollable continuations.

---

## Solution 4 — Controllable vs uncontrollable classification

| Event | Classification | Justification |
|-------|:---:|-------------|
| `start_drill` | Controllable | Actuator command — supervisor can choose not to issue it |
| `drill_done` | Uncontrollable | Sensor report — supervisor cannot prevent completion |
| `part_arrive` | Uncontrollable | External event — parts arrive from upstream |
| `clamp_part` | Controllable | Actuator command |
| `clamp_fail` | Uncontrollable | Sensor/fault — cannot prevent mechanical failure |
| `release_part` | Controllable | Actuator command |
| `move_to_output` | Controllable | Actuator command |
| `operator_override` | Uncontrollable | Human action — cannot be prevented by supervisor |

### Controllability verification sketch

Safety rule: "Do not start drilling unless part is clamped."

Legal prefixes include states where the part is clamped. If `clamp_fail` (uncontrollable) occurs after clamping, the controllability condition requires that the resulting state is still in the legal language. This means the legal language must include a "clamp failed" path — the specification must account for this outcome.

---

## Solution 5 — Blocking / nonblocking check

### Reachable states

Starting from $S0$: $\{S0, S1, S2, S3, S4\}$ — all states are reachable.

### Coreachable states

Marked states: $\{S0, S3\}$.
- $S3$ is marked → coreachable ✅
- $S2 \xrightarrow{c} S3$ → coreachable ✅
- $S1 \xrightarrow{b} S2 \xrightarrow{c} S3$ → coreachable ✅
- $S0$ is marked → coreachable ✅
- $S4$: no outgoing transitions → **not coreachable** ❌ (and not marked)

### Analysis

The automaton is **not nonblocking** because $S4$ is reachable but not coreachable.

$S4$ is a **deadlock**: it has no outgoing transitions and is not a marked state. The system gets permanently stuck.

### Minimal fix

Add a transition from $S4$ to a marked state, e.g., $S4 \xrightarrow{f} S0$. This makes $S4$ coreachable, restoring nonblocking.

---

## Solution 6 — Supervisor design with S3

### Updated supervisor rule table

S3 adds: once a unit is opened (`Opened` state), it must not be quarantined directly — battery must be removed first.

| State | Enabled $\Sigma_c$ | Disabled $\Sigma_c$ | Rules |
|-------|-------------------|---------------------|-------|
| `Idle` | — | — | — |
| `Intake` | — | — | — |
| `Inspected_OK` | `unscrew_cover`, `route_quarantine` | `route_recycle` | S2 |
| `Inspected_Suspect` | `route_quarantine` | `unscrew_cover`, `route_recycle` | S1 |
| `Opened` | `remove_battery` | `route_recycle`, `route_quarantine` | S2, **S3** |
| `Battery_Removed` | `route_recycle`, `route_quarantine` | — | — |

### Controllability check

Uncontrollable events (`arrival`, `inspect_ok`, `inspect_sus`) are never disabled → ✅.

### Nonblocking check

- `Opened` → `remove_battery` → `Battery_Removed` → `route_recycle` or `route_quarantine` ✅
- All other states: unchanged from before ✅

### Safe traces

| # | Trace | End state |
|---|-------|-----------|
| 1 | `arrival, inspect_ok, unscrew_cover, remove_battery, route_recycle` | `Recycle_Done` |
| 2 | `arrival, inspect_ok, unscrew_cover, remove_battery, route_quarantine` | `Quarantine_Done` |
| 3 | `arrival, inspect_ok, route_quarantine` | `Quarantine_Done` |
| 4 | `arrival, inspect_sus, route_quarantine` | `Quarantine_Done` |

Note: trace 3 from the original (Day 6) list — `arrival, inspect_ok, unscrew_cover, route_quarantine` — is now **forbidden** by S3. The unit must have its battery removed before any terminal action from `Opened`.

---

## Solution 7 — Basic Petri net

### Structure

**Places:** `Wait_A`, `In_A`, `Done_A`, `In_B`, `Done_B`, `In_C`, `Done_C`, `DONE`, `DRILL_FREE`, `ROBOT_FREE`

**Transitions:**
- `start_A`: `Wait_A` + `DRILL_FREE` → `In_A`
- `end_A`: `In_A` → `Done_A` + `DRILL_FREE`
- `start_B`: `Done_A` → `In_B`
- `end_B`: `In_B` → `Done_B`
- `start_C`: `Done_B` + `ROBOT_FREE` → `In_C`
- `end_C`: `In_C` → `DONE` + `ROBOT_FREE`

### Initial marking

$M_0$: `Wait_A` = 1, `DRILL_FREE` = 1, `ROBOT_FREE` = 1, all others = 0.

### Place invariants

1. **Drill conservation:** `In_A + DRILL_FREE = 1` — drill is either in use or free
2. **Robot conservation:** `In_C + ROBOT_FREE = 1` — packing robot is either in use or free
3. **Part conservation:** `Wait_A + In_A + Done_A + In_B + Done_B + In_C + DONE = 1` — part is in exactly one stage

### Execution trace

| Step | Transition fired | Marking change |
|------|-----------------|---------------|
| 0 | — | `Wait_A=1, DRILL_FREE=1, ROBOT_FREE=1` |
| 1 | `start_A` | `In_A=1, ROBOT_FREE=1` |
| 2 | `end_A` | `Done_A=1, DRILL_FREE=1, ROBOT_FREE=1` |
| 3 | `start_B` | `In_B=1, DRILL_FREE=1, ROBOT_FREE=1` |
| 4 | `end_B` | `Done_B=1, DRILL_FREE=1, ROBOT_FREE=1` |
| 5 | `start_C` | `In_C=1, DRILL_FREE=1` |
| 6 | `end_C` | `DONE=1, DRILL_FREE=1, ROBOT_FREE=1` |

With 2 initial tokens in `Wait_A`, contention occurs at `DRILL_FREE` (Station A) and `ROBOT_FREE` (Station C). The invariants guarantee that at most one part uses each resource at a time.

---

## Solution 8 — Integrative modelling exercise

*(Abbreviated — this is an open-ended modelling exercise. A reference solution outline is provided.)*

### Event alphabet

| Event | Ctrl? | Obs? |
|-------|:---:|:---:|
| `arrive` | No | Yes |
| `weigh_heavy` | No | Yes |
| `weigh_light` | No | Yes |
| `sort_start` | Yes | Yes |
| `sort_done` | No | Yes |
| `sort_reject` | No | Yes |
| `shred_start` | Yes | Yes |
| `shred_done` | No | Yes |
| `route_recycle` | Yes | Yes |
| `route_reject` | Yes | Yes |

### Key safety rules

- **R1:** `shred_start` is forbidden while `sort_start` has occurred without `sort_done`
- **R2:** `shred_start` is forbidden after `sort_reject`
- **R3:** Heavy units ($>5$ kg) must pass through `sort_start` → `sort_done` before `shred_start`

### Nonblocking

Verify that:
- Light units always have a path to `route_recycle`
- Heavy non-rejected units have a path through sorting to shredding to `route_recycle`
- Rejected units have a path to `route_reject`

The supervisor is nonblocking if every reachable state maintains at least one of these paths.

---

[← Back to exercises](exercises.md) · [Back to Week 1 overview](README.md)
