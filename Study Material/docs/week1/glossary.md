# Glossary — Week 1

[← Back to Week 1 overview](README.md)

Key terms used throughout Week 1, in alphabetical order. Each definition includes the day where the concept is introduced and at least one authoritative source.

---

**Automaton (finite automaton)**
A 5-tuple $G = (Q, \Sigma, \delta, q_0, Q_m)$ modelling a DES plant. States represent system conditions, events label transitions. → [Day 2](day-02-automata.md).
*Source:* Raisch, [*DES and Hybrid Systems*](https://www.hamilton.ie/ollie/Downloads/Hyb.pdf), §4.5.1.

**Blocking**
A system is blocking if there exists a reachable state from which no marked state can be reached. Blocking can manifest as deadlock or livelock. → [Day 5](day-05-safety-liveness-blocking.md).
*Source:* Cai & Wonham (2020), [p. 2](https://www.caikai.org/publication/CaiWonham_20Encyclo.pdf).

**Controllable event**
An event $\sigma \in \Sigma_c$ that a supervisor can disable (prevent from occurring). Typically corresponds to actuator commands. → [Day 1](day-01-des-foundations.md), [Day 4](day-04-controllability-observability.md).
*Source:* Goorden et al., [*Modelling guidelines*](https://www.cs.vu.nl/~wanf/pubs/modeling-guidelines.pdf), §2.1.

**Controllability (of a language)**
A language $K \subseteq L(G)$ is controllable if $\overline{K}\,\Sigma_{uc} \cap L(G) \subseteq \overline{K}$. Necessary condition for a supervisor to enforce $K$. → [Day 4](day-04-controllability-observability.md).
*Source:* Cai & Wonham (2020), [Def. 2, p. 3](https://www.caikai.org/publication/CaiWonham_20Encyclo.pdf).

**Coreachable state**
A state $q$ from which some marked state $q_m \in Q_m$ can be reached via a finite event sequence. → [Day 5](day-05-safety-liveness-blocking.md).

**Deadlock**
A state with no enabled transitions that is not marked — the system is permanently stuck. → [Day 5](day-05-safety-liveness-blocking.md).
*Source:* Raisch, [*DES and Hybrid Systems*](https://www.hamilton.ie/ollie/Downloads/Hyb.pdf), p. 75.

**DES (discrete-event system)**
A dynamic system whose state changes occur at discrete instants, triggered by events rather than continuous time evolution. → [Day 1](day-01-des-foundations.md).
*Source:* Cassandras, [*Discrete Event Systems*](https://eolss.net/Sample-Chapters/C18/E6-43-27-00.pdf), EOLSS, §1–2.

**Enabling function**
A supervisor's policy: for each state (or observation), the set of controllable events that remain enabled. Events not in this set are disabled. → [Day 3](day-03-supervisory-control.md).

**Event**
An instantaneous occurrence that causes a state transition in a DES. → [Day 1](day-01-des-foundations.md).

**Event alphabet ($\Sigma$)**
The finite set of all events recognised by the DES model. Partitioned into $\Sigma_c$ (controllable) and $\Sigma_{uc}$ (uncontrollable). → [Day 1](day-01-des-foundations.md).

**Firing (Petri net)**
When a transition $t$ fires, it consumes tokens from input places and produces tokens in output places. → [Day 7](day-07-intro-petri-nets.md).
*Source:* Murata (1989), [§II](https://people.disim.univaq.it/adimarco/teaching/bioinfo15/paper.pdf).

**Generated language $L(G)$**
The set of all event strings producible by automaton $G$ starting from $q_0$. Represents everything the plant *can* do. → [Day 2](day-02-automata.md).

**Initial state ($q_0$)**
The starting state of an automaton. → [Day 2](day-02-automata.md).

**Livelock**
A condition where the system continues executing events but can never reach a marked state. → [Day 5](day-05-safety-liveness-blocking.md).
*Source:* Raisch, [*DES and Hybrid Systems*](https://www.hamilton.ie/ollie/Downloads/Hyb.pdf), p. 75.

**Liveness (DES property)**
"Something good eventually happens." The system can always make progress toward completion. Related to but distinct from nonblocking. → [Day 5](day-05-safety-liveness-blocking.md).

**Marked language $L_m(G)$**
The subset of $L(G)$ consisting of strings ending in marked states. → [Day 2](day-02-automata.md).

**Marked state**
A state in $Q_m$ representing task completion (e.g., unit successfully recycled or quarantined). → [Day 2](day-02-automata.md).

**Marking (Petri net)**
The distribution of tokens across places; represents the net's state. → [Day 7](day-07-intro-petri-nets.md).

**Maximally permissive**
A supervisor that disables only the minimum set of events necessary for safety and nonblocking. → [Day 3](day-03-supervisory-control.md), [Day 6](day-06-worked-example-automata-supervisor.md).

**Natural projection ($P$)**
A map $P: \Sigma^* \to \Sigma_o^*$ that erases unobservable events from strings. → [Day 4](day-04-controllability-observability.md).
*Source:* Cai & Wonham (2020), [p. 8](https://www.caikai.org/publication/CaiWonham_20Encyclo.pdf).

**Nonblocking**
A DES is nonblocking if $\overline{L_m(G)} = L(G)$, i.e., every reachable state can reach a marked state. → [Day 5](day-05-safety-liveness-blocking.md).
*Source:* Cai & Wonham (2020), [p. 2](https://www.caikai.org/publication/CaiWonham_20Encyclo.pdf).

**Normality**
A sufficient condition for observability that *is* closed under union. Stronger than standard observability. → [Day 4](day-04-controllability-observability.md).
*Source:* Cai & Wonham (2020), [p. 9](https://www.caikai.org/publication/CaiWonham_20Encyclo.pdf).

**Observable event**
An event $\sigma \in \Sigma_o$ that the supervisor can detect when it occurs. → [Day 4](day-04-controllability-observability.md).

**Observability (of a language)**
A language is observable if the supervisor can make consistent enable/disable decisions based solely on observed (projected) strings. → [Day 4](day-04-controllability-observability.md).

**Petri net**
A bipartite graph $(P, T, F, W)$ with places, transitions, and arcs, used to model discrete state, concurrency, and resource contention. → [Day 7](day-07-intro-petri-nets.md).
*Source:* Murata (1989), [§II](https://people.disim.univaq.it/adimarco/teaching/bioinfo15/paper.pdf).

**Place (Petri net)**
A node in a Petri net that holds tokens. Represents a condition, resource, or status. → [Day 7](day-07-intro-petri-nets.md).

**Place invariant**
A non-negative vector $y$ such that $y^T M$ is constant for all reachable markings. Used for structural safety arguments. → [Day 7](day-07-intro-petri-nets.md).
*Source:* Murata (1989), [§IV.B](https://people.disim.univaq.it/adimarco/teaching/bioinfo15/paper.pdf).

**Plant**
The uncontrolled system being modelled — everything the physical system can do, including unsafe behaviour. → [Day 3](day-03-supervisory-control.md).

**Prefix-closure ($\overline{K}$)**
The set of all prefixes of strings in $K$. A language $K$ is prefix-closed if $\overline{K} = K$. → [Day 4](day-04-controllability-observability.md).

**Reachability graph**
For automata: the set of states reachable from $q_0$. For Petri nets: the graph whose nodes are reachable markings and whose edges are transition firings. → [Day 5](day-05-safety-liveness-blocking.md), [Day 7](day-07-intro-petri-nets.md).

**Relative observability**
A weaker but more practical substitute for standard observability, useful when normality is too strong. → [Day 4](day-04-controllability-observability.md).
*Source:* Cai & Wonham (2020), [p. 9](https://www.caikai.org/publication/CaiWonham_20Encyclo.pdf).

**Safety (DES property)**
"Nothing bad ever happens." The system never enters a forbidden state or produces a forbidden string. → [Day 5](day-05-safety-liveness-blocking.md).

**Specification ($E$)**
A description of legal (allowed) behaviour, expressed as forbidden states, forbidden strings, or a specification automaton. → [Day 3](day-03-supervisory-control.md).

**Supervisor ($S$)**
A control agent that observes events and selectively disables controllable events to enforce a specification. → [Day 3](day-03-supervisory-control.md).
*Source:* Ramadge & Wonham (1989), [*The Control of DES*](https://www.labri.fr/perso/anca/Games/Bib/RamadgeWonham89.pdf).

**Supremal controllable sublanguage**
The largest subset of a specification language that is controllable, nonblocking, and realizable by a supervisor. → [Day 3](day-03-supervisory-control.md).
*Source:* Lafortune, [EOLSS §4](https://www.eolss.net/sample-chapters/c18/E6-43-27-02.pdf).

**Token (Petri net)**
A marker in a place, representing the presence of a condition or resource. → [Day 7](day-07-intro-petri-nets.md).

**Transition (Petri net)**
A node in a Petri net that consumes and produces tokens when it fires. Represents an event or action. → [Day 7](day-07-intro-petri-nets.md).

**Trim**
An automaton is trim if every state is both reachable and coreachable. Trimming removes states that violate this. → [Day 5](day-05-safety-liveness-blocking.md).

**Uncontrollable event**
An event $\sigma \in \Sigma_{uc}$ that a supervisor cannot prevent. Typically corresponds to sensor outcomes, faults, or external arrivals. → [Day 1](day-01-des-foundations.md), [Day 4](day-04-controllability-observability.md).

---

[← Back to Week 1 overview](README.md)
