import type { Scenario } from './types';

export const SCENARIOS: Scenario[] = [
  {
    name: 'Nominal Laptop',
    description: 'A standard laptop in normal condition — straightforward disassembly expected.',
    condition: 'normal',
  },
  {
    name: 'Hidden Screws',
    description: "Laptop has concealed fasteners that aren't visible during initial inspection.",
    condition: 'hidden_screws',
    overrides: { screwsDifficulty: 0.85 },
  },
  {
    name: 'Swollen Battery',
    description: 'Battery may be swollen — potential safety hazard during removal.',
    condition: 'swollen_battery',
    overrides: { batteryRisk: 0.9 },
  },
  {
    name: 'Strong Adhesive',
    description: 'Manufacturer used unusually strong adhesive — mechanical removal difficult.',
    condition: 'strong_adhesive',
    overrides: { adhesiveStrength: 0.9 },
  },
  {
    name: 'Conflicting Signals',
    description: 'Observations will be noisy and contradictory — tests belief resilience.',
    condition: 'normal',
    overrides: { screwsDifficulty: 0.5, batteryRisk: 0.4, adhesiveStrength: 0.4 },
  },
  {
    name: 'Repeated Failure',
    description: 'Laptop with hidden screws AND adhesive — unscrewing will likely fail multiple times.',
    condition: 'hidden_screws',
    overrides: { screwsDifficulty: 0.95, adhesiveStrength: 0.7 },
  },
  {
    name: 'Easy Disassembly',
    description: 'Well-designed laptop — quick and clean disassembly.',
    condition: 'easy_disassembly',
    overrides: { screwsDifficulty: 0.05, adhesiveStrength: 0.05, batteryRisk: 0.02 },
  },
  {
    name: 'Random',
    description: 'Random hidden condition — discover what happens.',
    condition: 'random',
  },
];
