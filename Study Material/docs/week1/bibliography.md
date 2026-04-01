# Bibliography — Week 1

[← Back to Week 1 overview](README.md)

All sources used in the Week 1 learning package, annotated with what each provides and where it is used.

---

## Essential sources

### Raisch, J. — *Discrete Event and Hybrid Systems* (course notes)

- **URL:** <https://www.hamilton.ie/ollie/Downloads/Hyb.pdf>
- **Type:** University lecture notes (Technische Universität Berlin)
- **Covers:** Petri nets (reachability, deadlock), finite automata with marked states, blocking vs nonblocking, SCT "manufacturing cell" worked example
- **Used in:** [Day 1](day-01-des-foundations.md), [Day 2](day-02-automata.md), [Day 5](day-05-safety-liveness-blocking.md), [Day 6](day-06-worked-example-automata-supervisor.md), [Day 7](day-07-intro-petri-nets.md)
- **Key sections:** Ch. 1 (DES intro, pp. 7–9), §4.5.1 (automata with marked states, pp. 73–74), §4.6 (manufacturing cell example, pp. 84–90), §2.2–2.4 (Petri nets, pp. 12–22)

### Cassandras, C. G. — *Discrete Event Systems* (EOLSS chapter)

- **URL:** <https://eolss.net/Sample-Chapters/C18/E6-43-27-00.pdf>
- **Type:** EOLSS encyclopaedia chapter
- **Covers:** DES definitions, contrast with time-driven systems, modelling overview including automata and Petri nets
- **Used in:** [Day 1](day-01-des-foundations.md), [Day 7](day-07-intro-petri-nets.md)

### Lafortune, S. — *Supervisory Control of Discrete Event Systems* (EOLSS chapter)

- **URL:** <https://www.eolss.net/sample-chapters/c18/E6-43-27-02.pdf>
- **Type:** EOLSS encyclopaedia chapter
- **Covers:** SCT introduction, controllable/uncontrollable events, observability, supremal controllable sublanguage, nonblocking
- **Used in:** [Day 3](day-03-supervisory-control.md), [Day 4](day-04-controllability-observability.md), [Day 5](day-05-safety-liveness-blocking.md)

### Cai, K. & Wonham, W. M. — *Supervisory Control of Discrete-Event Systems* (2020)

- **URL:** <https://www.caikai.org/publication/CaiWonham_20Encyclo.pdf>
- **Type:** Encyclopaedia chapter (2020, Springer)
- **Covers:** RW/SCT base model, nonblocking definition, controllability, partial-observation (observability, normality, relative observability)
- **Used in:** [Day 2](day-02-automata.md), [Day 3](day-03-supervisory-control.md), [Day 4](day-04-controllability-observability.md), [Day 5](day-05-safety-liveness-blocking.md), [Day 6](day-06-worked-example-automata-supervisor.md)
- **Key sections:** pp. 1–5 (base model, controllability), pp. 8–9 (observability, normality)

### Ramadge, P. J. & Wonham, W. M. — *The Control of Discrete Event Systems* (1989)

- **URL:** <https://www.labri.fr/perso/anca/Games/Bib/RamadgeWonham89.pdf>
- **Type:** Classic tutorial paper, Proceedings of the IEEE, Vol. 77, No. 1, 1989
- **Covers:** Foundational DES control perspective, controllability, observability, modular/hierarchical directions
- **Used in:** [Day 3](day-03-supervisory-control.md), [Day 4](day-04-controllability-observability.md)

### Sipser, M. — *MIT OCW 18.404J Theory of Computation, Lecture 1*

- **URL:** <https://ocw.mit.edu/courses/18-404j-theory-of-computation-fall-2020/b4d9bf1573dccea21bee82cfba4224d4_MIT18_404f20_lec1.pdf>
- **Type:** University lecture notes (MIT OpenCourseWare)
- **Covers:** DFA definition, regular languages
- **Used in:** [Day 2](day-02-automata.md)

### Sipser, M. — *MIT OCW 18.404J Theory of Computation, Lecture 2*

- **URL:** <https://ocw.mit.edu/courses/18-404j-theory-of-computation-fall-2020/d741901d23b4522588e267177c77d10d_MIT18_404f20_lec2.pdf>
- **Type:** University lecture notes (MIT OpenCourseWare)
- **Covers:** NFA, NFA→DFA construction, equivalence
- **Used in:** [Day 2](day-02-automata.md)

### Murata, T. — *Petri Nets: Properties, Analysis and Applications* (1989)

- **URL:** <https://people.disim.univaq.it/adimarco/teaching/bioinfo15/paper.pdf>
- **Type:** Tutorial paper, Proceedings of the IEEE, Vol. 77, No. 4, 1989
- **Covers:** Petri net primitives, behavioural/structural properties, analysis methods, reachability, place invariants
- **Used in:** [Day 7](day-07-intro-petri-nets.md)

---

## Recommended sources

### Goorden, M. et al. — *Modelling guidelines for component-based supervisory control synthesis*

- **URL:** <https://www.cs.vu.nl/~wanf/pubs/modeling-guidelines.pdf>
- **Type:** Research paper / practical modelling guide
- **Covers:** Event classification (actuators vs sensors), marked states, nonblocking, maximally permissive synthesis
- **Used in:** [Day 1](day-01-des-foundations.md), [Day 3](day-03-supervisory-control.md), [Day 4](day-04-controllability-observability.md), [Day 6](day-06-worked-example-automata-supervisor.md)

### Reniers, M. — *Model-based Engineering of Supervisory Controllers* (lecture slides)

- **URL:** <https://ipa.win.tue.nl/wp-content/uploads/2018/05/LectureIPA-final.pdf>
- **Type:** University lecture slides (TU Eindhoven / IPA)
- **Covers:** Synthesis-based engineering process, nonblocking/controllable/maximally permissive conditions
- **Used in:** [Day 6](day-06-worked-example-automata-supervisor.md)

---

## Fallback / supplementary sources

### Esparza, J. — *Petri Net Lecture Notes*

- **URL:** <https://www.cse.iitb.ac.in/~akshayss/courses/cs735/Esparza-lecture-notes.pdf>
- **Type:** University lecture notes
- **Covers:** Reachability graph algorithm, liveness theorem
- **Used in:** [Day 7](day-07-intro-petri-nets.md) (supplementary)

### Geeraerts, G. — *Petri Net Tutorial*

- **URL:** <https://verif.ulb.be/ggeeraer/Tutorial-Perti-Nets-Geeraerts.pdf>
- **Type:** Tutorial notes (Université Libre de Bruxelles)
- **Covers:** Reachability trees, place invariants, coverability
- **Used in:** [Day 7](day-07-intro-petri-nets.md) (supplementary)

---

## Tool references

| Tool | URL | Purpose |
|------|-----|---------|
| JFLAP | <https://www.jflap.org/getjflap.html> | Finite automata editor and simulator |
| JFLAP Tutorial | <https://www.jflap.org/tutorial/fa/createfa/fa.html> | Step-by-step FA construction |
| TCT | <https://www.caikai.org/teaching/des-course/TCT.pdf> | Supervisor synthesis (`supcon`, `condat`, `trim`) |
| libFAUDES | <https://fgdes.tf.fau.de/faudes/faudes_about.html> | Open-source DES analysis/synthesis library |
| IEEE CSS DES Resources | <https://ieeecss.org/tc/discrete-event-systems/resources> | Directory of DES tools |
| PIPE2 | <https://pipe2.sourceforge.net/> | Petri net editor with reachability graph |
| TINA | <https://projects.laas.fr/tina/download.php> | Time Petri Net Analyser |
| Snoopy | <https://github.com/PetriNuts/snoopy> | Hierarchical Petri nets |
| WoPeD | <https://woped.dhbw-karlsruhe.de/> | Workflow Petri nets, PNML |
| CPN IDE | <https://cpnide.org/> | Coloured Petri nets |

---

[← Back to Week 1 overview](README.md)
