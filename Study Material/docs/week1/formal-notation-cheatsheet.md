# Formal Notation Cheatsheet — Week 1

[← Back to Week 1 overview](README.md)

A quick-reference sheet for all symbols and formal notation used in Week 1.

---

## Automata

| Symbol | Meaning | Introduced |
|--------|---------|-----------|
| $G = (Q, \Sigma, \delta, q_0, Q_m)$ | Plant automaton | [Day 2](day-02-automata.md) |
| $Q$ | Finite set of states | [Day 2](day-02-automata.md) |
| $\Sigma$ | Event alphabet (finite) | [Day 1](day-01-des-foundations.md) |
| $\Sigma_c$ | Controllable events | [Day 1](day-01-des-foundations.md) |
| $\Sigma_{uc}$ | Uncontrollable events | [Day 1](day-01-des-foundations.md) |
| $\Sigma_o$ | Observable events | [Day 4](day-04-controllability-observability.md) |
| $\delta: Q \times \Sigma \to Q$ | Transition function (partial) | [Day 2](day-02-automata.md) |
| $\delta^*: Q \times \Sigma^* \to Q$ | Extended transition function (over strings) | [Day 2](day-02-automata.md) |
| $q_0$ | Initial state | [Day 2](day-02-automata.md) |
| $Q_m$ | Marked states (task completion) | [Day 2](day-02-automata.md) |

## Languages

| Symbol | Meaning | Introduced |
|--------|---------|-----------|
| $\Sigma^*$ | Set of all finite strings over $\Sigma$ (including empty string $\varepsilon$) | [Day 2](day-02-automata.md) |
| $\varepsilon$ | Empty string | [Day 2](day-02-automata.md) |
| $L(G)$ | Generated language: all strings producible by $G$ from $q_0$ | [Day 2](day-02-automata.md) |
| $L_m(G)$ | Marked language: strings in $L(G)$ ending in $Q_m$ | [Day 2](day-02-automata.md) |
| $\overline{K}$ | Prefix-closure of language $K$ | [Day 4](day-04-controllability-observability.md) |
| $K \subseteq L(G)$ | Legal (desired) language | [Day 4](day-04-controllability-observability.md) |

## Supervisory control

| Symbol | Meaning | Introduced |
|--------|---------|-----------|
| $S$ | Supervisor (control agent) | [Day 3](day-03-supervisory-control.md) |
| $E$ | Specification (legal behaviour) | [Day 3](day-03-supervisory-control.md) |
| $S/G$ | Closed-loop system (supervisor controlling plant) | [Day 3](day-03-supervisory-control.md) |

## Key formulas

### Controllability condition

$$\overline{K}\,\Sigma_{uc} \cap L(G) \subseteq \overline{K}$$

*Reading:* If a string is a legal prefix and the plant allows an uncontrollable continuation, that continuation must still be legal.

→ [Day 4](day-04-controllability-observability.md)

### Nonblocking condition

$$\overline{L_m(G)} = L(G)$$

*Reading:* Every string producible by the plant can be extended to a string in the marked language. Equivalently, every reachable state can reach a marked state.

→ [Day 5](day-05-safety-liveness-blocking.md)

### Natural projection

$$P: \Sigma^* \to \Sigma_o^*$$

$$P(\varepsilon) = \varepsilon, \quad P(\sigma) = \begin{cases} \sigma & \text{if } \sigma \in \Sigma_o \\ \varepsilon & \text{if } \sigma \notin \Sigma_o \end{cases}, \quad P(s\sigma) = P(s) \cdot P(\sigma)$$

→ [Day 4](day-04-controllability-observability.md)

## Petri nets

| Symbol | Meaning | Introduced |
|--------|---------|-----------|
| $N = (P, T, F, W)$ | Petri net structure | [Day 7](day-07-intro-petri-nets.md) |
| $P$ | Set of places | [Day 7](day-07-intro-petri-nets.md) |
| $T$ | Set of transitions | [Day 7](day-07-intro-petri-nets.md) |
| $F$ | Flow relation (arcs) | [Day 7](day-07-intro-petri-nets.md) |
| $W$ | Arc weight function | [Day 7](day-07-intro-petri-nets.md) |
| $M: P \to \mathbb{N}_0$ | Marking (token distribution) | [Day 7](day-07-intro-petri-nets.md) |
| $M_0$ | Initial marking | [Day 7](day-07-intro-petri-nets.md) |
| ${}^{\bullet}t$ | Input places of transition $t$ | [Day 7](day-07-intro-petri-nets.md) |
| $t^{\bullet}$ | Output places of transition $t$ | [Day 7](day-07-intro-petri-nets.md) |
| $C$ | Incidence matrix | [Day 7](day-07-intro-petri-nets.md) |

### Firing rule

Transition $t$ is enabled at $M$ if:

$$\forall p \in {}^{\bullet}t:\; M(p) \geq W(p, t)$$

After firing:

$$M'(p) = M(p) - W(p, t) + W(t, p)$$

### Place invariant

$$y^T \cdot C = 0 \implies y^T \cdot M = y^T \cdot M_0 \quad \forall \text{ reachable } M$$

## Running example notation

| Symbol | Value in the demanufacturing example |
|--------|--------------------------------------|
| $Q$ | `{Idle, Intake, Inspected_OK, Inspected_Suspect, Opened, Battery_Removed, Recycle_Done, Quarantine_Done}` |
| $\Sigma_c$ | `{unscrew_cover, remove_battery, route_recycle, route_quarantine}` |
| $\Sigma_{uc}$ | `{arrival, inspect_ok, inspect_sus}` |
| $q_0$ | `Idle` |
| $Q_m$ | `{Recycle_Done, Quarantine_Done}` |

---

[← Back to Week 1 overview](README.md)
