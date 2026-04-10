# Demanufacturing Cell Simulation

Interactive browser-based simulation of a demanufacturing cell with dual views:

- **DES View** — discrete-event simulation of the physical cell (stations, products, queues)
- **Belief View** — real-time visualization of belief states, feasibility estimates, and uncertainty

## Stack

- **React 18** + **TypeScript** — UI framework
- **Vite** — build tooling
- **Tailwind CSS** — utility-first styling with custom dark theme
- **Framer Motion** — animations and transitions

## Getting Started

```bash
npm install
npm run dev
```

## Structure

```
src/
  main.tsx              Entry point
  App.tsx               Root component
  index.css             Tailwind directives + global styles

  sim/                  Simulation engine (pure TypeScript, no React)
    types.ts            Core type definitions
    engine.ts           DES engine loop
    policy.ts           Action-selection policies
    scenarios.ts        Scenario configurations
    belief.ts           Belief-state representation and updates
    random.ts           Seeded RNG utilities

  components/           React UI components
    Toolbar.tsx         Simulation controls (play/pause/step/speed)
    DESView.tsx         Station layout and product flow
    BeliefView.tsx      Belief-state visualization panel
    EventLog.tsx        Scrolling event log
    StationCard.tsx     Individual station display
    BeliefBar.tsx       Belief probability bar
    ExplanationBox.tsx  Narrative explanation of decisions
    UncertaintyMeter.tsx  Visual uncertainty indicator

  hooks/
    useSimulation.ts    React hook wrapping the simulation engine
```
