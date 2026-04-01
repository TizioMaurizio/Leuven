# Week 1 — Discrete Event Systems and Supervisory Control

## What this week covers

Week 1 builds the **formal modelling foundation** for a demanufacturing cell: how to represent real equipment behaviour as a discrete-event system (DES), how to specify safety constraints, and how to synthesise a supervisor that *guarantees* safety while keeping the system live and nonblocking.

By the end of the week you will understand:

- Why demanufacturing is naturally event-driven
- How finite automata and languages model DES plants
- What supervisory control theory (SCT) is and how it works
- The role of controllable vs uncontrollable events
- Observability and partial observation
- Safety vs liveness, blocking vs nonblocking
- How Petri nets model resource contention and concurrency
- How all these concepts connect to the PhD proposal architecture

## Why this matters for the PhD

Your proposal requires converting a real demanufacturing cell into **(i) a finite, auditable DES model** and **(ii) a supervisor that can guarantee safety while staying nonblocking**. The supervisor-enabled set produced by SCT is the formal foundation on which the digital twin, conservative learning layer, and bounded LLM mediation will rest. Without a sound DES/SCT base, higher-level components have no formal ground truth to operate on.

## Learning outcomes

After completing Week 1, you should be able to:

1. **Define** a DES formally (event alphabet, automaton, languages, marked states)
2. **Model** a simple demanufacturing cell as a plant automaton
3. **Specify** safety requirements as forbidden states or specification automata
4. **Explain** controllability and why uncontrollable events constrain supervisor design
5. **Distinguish** observable from unobservable events and explain partial-observation challenges
6. **Check** whether a supervised system is nonblocking (reachability + coreachability)
7. **Build** a supervisor rule table (enabling function) for a small plant
8. **Model** the same cell as a Petri net with resource places and token invariants
9. **Connect** each concept explicitly to the PhD proposal architecture

## Day-by-day reading path

| Day | Topic | Page |
|-----|-------|------|
| 1 | DES foundations — what is a DES, event alphabets, plant boundary | [day-01](day-01-des-foundations.md) |
| 2 | Automata for DES — DFA/NFA, marked states, languages | [day-02](day-02-automata.md) |
| 3 | Supervisory Control Theory — plant/supervisor split, synthesis | [day-03](day-03-supervisory-control.md) |
| 4 | Controllability & Observability — event partitions, partial observation | [day-04](day-04-controllability-observability.md) |
| 5 | Safety, Liveness & Blocking — nonblocking, deadlock, livelock | [day-05](day-05-safety-liveness-blocking.md) |
| 6 | Worked example — full automaton + supervisor for a demanufacturing cell | [day-06](day-06-worked-example-automata-supervisor.md) |
| 7 | Introductory Petri nets — places, transitions, resources, reachability | [day-07](day-07-intro-petri-nets.md) |

## Quick-start

1. Read **Day 1** to ground DES in the demanufacturing context.
2. Work through Days 2–5 for the theoretical core.
3. On Day 6, build (or trace through) the full worked example.
4. On Day 7, reinterpret the same example as a Petri net.
5. Test yourself with the [exercises](exercises.md) and check [solutions](exercise-solutions.md).
6. Review the [glossary](glossary.md) and [formal notation cheatsheet](formal-notation-cheatsheet.md) as references.

## Reference material

- [Glossary](glossary.md) — key terms defined in one place
- [Formal notation cheatsheet](formal-notation-cheatsheet.md) — symbols, conventions, key formulas
- [Exercises](exercises.md) — self-assessment problems
- [Exercise solutions](exercise-solutions.md) — worked answers
- [Bibliography](bibliography.md) — all sources with annotations
- [Interactive demos](../../interactive/week1/) — Python scripts for visual reinforcement
- [Slides](../../slides/week1-overview.pptx) — PowerPoint overview

## Running worked example

All daily pages build on a single **demanufacturing cell scenario**:

> A single unit (e.g., laptop) enters the cell → inspection → if battery suspected hazardous, route to quarantine; otherwise open, remove battery, route to recycling.

This scenario is modelled as:
- A **DES event alphabet** (Day 1)
- A **plant automaton** (Day 2, refined Day 6)
- A **supervised automaton** with safety specs (Days 3, 5, 6)
- A **Petri net** with resource places (Day 7)

## What you should be able to explain after Week 1

- "Why is my demanufacturing cell naturally modelled as a DES?"
- "What is the plant automaton and what are its marked states?"
- "How does a supervisor disable controllable events to enforce safety?"
- "Why can't the supervisor block uncontrollable events?"
- "What does nonblocking mean and how do I check it?"
- "How do Petri nets add resource-contention modelling that automata lack?"
- "How does this DES/SCT foundation support the rest of my proposal?"
