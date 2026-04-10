/**
 * Headless simulation runner.
 * Usage: npx tsx scripts/headless.ts [--scenario <name|index>] [--seed <n>] [--seeds <n>] [--all]
 *
 * --all           Run all scenarios with all seeds (default)
 * --scenario <s>  Run a specific scenario by name or index
 * --seed <n>      Single seed (default: 42)
 * --seeds <n>     Run with seeds 1..n for each scenario
 * --max-steps <n> Safety limit per run (default: 200)
 *
 * Output: JSON to stdout with structure:
 * {
 *   "runs": [
 *     {
 *       "scenario": { name, description, condition },
 *       "seed": number,
 *       "totalSteps": number,
 *       "completed": boolean,
 *       "outputBin": string | null,
 *       "product": { id, condition, screwsDifficulty, ... },
 *       "finalBelief": { beliefs: {...}, uncertainty: number },
 *       "events": [ { step, type, station, description, observation?, beliefDelta? }, ... ],
 *       "observations": [ { step, station, type, evidence, confidence }, ... ],
 *       "beliefHistory": [ { step, beliefs: {...}, uncertainty } ],
 *       "stationVisits": [ { station, entryStep, exitStep } ],
 *       "policyDecisions": [ { step, action, reason, confidence } ],
 *     }
 *   ],
 *   "meta": {
 *     "timestamp": ISO string,
 *     "version": "0.1.0",
 *     "totalRuns": number,
 *     "scenariosUsed": string[],
 *     "seedsUsed": number[]
 *   }
 * }
 */

import { SimEngine } from '../src/sim/engine';
import { SCENARIOS } from '../src/sim/scenarios';
import type { Scenario, SimEvent, StationId } from '../src/sim/types';

// ── CLI arg parsing ──────────────────────────────────────────────────

const args = process.argv.slice(2);

function getArg(name: string): string | undefined {
  const idx = args.indexOf(`--${name}`);
  return idx >= 0 && idx + 1 < args.length ? args[idx + 1] : undefined;
}

const hasFlag = (name: string) => args.includes(`--${name}`);

const maxSteps = parseInt(getArg('max-steps') ?? '200', 10);
const singleSeed = parseInt(getArg('seed') ?? '42', 10);
const seedCount = parseInt(getArg('seeds') ?? '1', 10);
const scenarioFilter = getArg('scenario');
const runAll = hasFlag('all') || !scenarioFilter;

// ── Determine scenarios to run ───────────────────────────────────────

let selectedScenarios: { scenario: Scenario; index: number }[] = [];

if (runAll) {
  selectedScenarios = SCENARIOS.map((s, i) => ({ scenario: s, index: i }));
} else {
  const idx = parseInt(scenarioFilter!, 10);
  if (!isNaN(idx) && idx >= 0 && idx < SCENARIOS.length) {
    selectedScenarios = [{ scenario: SCENARIOS[idx], index: idx }];
  } else {
    const found = SCENARIOS.findIndex(
      (s) => s.name.toLowerCase().includes(scenarioFilter!.toLowerCase()),
    );
    if (found >= 0) {
      selectedScenarios = [{ scenario: SCENARIOS[found], index: found }];
    } else {
      console.error(`Scenario not found: ${scenarioFilter}`);
      process.exit(1);
    }
  }
}

// ── Determine seeds ──────────────────────────────────────────────────

const seeds =
  seedCount > 1
    ? Array.from({ length: seedCount }, (_, i) => i + 1)
    : [singleSeed];

// ── Run trace type ───────────────────────────────────────────────────

interface RunTrace {
  scenario: { name: string; description: string; condition: string };
  seed: number;
  totalSteps: number;
  completed: boolean;
  outputBin: string | null;
  product: Record<string, unknown>;
  finalBelief: { beliefs: Record<string, number>; uncertainty: number };
  events: SimEvent[];
  observations: { step: number; station: string; type: string; evidence: string; confidence: number }[];
  beliefHistory: { step: number; beliefs: Record<string, number>; uncertainty: number }[];
  stationVisits: { station: string; entryStep: number; exitStep: number | null }[];
  policyDecisions: { step: number; action: string; reason: string; confidence: number }[];
}

// ── Run simulations ──────────────────────────────────────────────────

const runs: RunTrace[] = [];

for (const { scenario } of selectedScenarios) {
  for (const seed of seeds) {
    const engine = new SimEngine(seed, scenario);
    engine.setMaxProducts(1);
    let snap = engine.getSnapshot();

    const beliefHistory: RunTrace['beliefHistory'] = [];
    const stationVisits: RunTrace['stationVisits'] = [];
    const policyDecisions: RunTrace['policyDecisions'] = [];

    // Track initial state
    let currentStation: StationId = snap.currentStation;
    let entryStep = snap.step;

    beliefHistory.push({
      step: snap.step,
      beliefs: { ...snap.belief.beliefs },
      uncertainty: snap.belief.uncertainty,
    });

    let steps = 0;
    while (!engine.isComplete() && steps < maxSteps) {
      snap = engine.step();
      steps++;

      // Track station changes
      if (snap.currentStation !== currentStation) {
        stationVisits.push({
          station: currentStation,
          entryStep,
          exitStep: snap.step,
        });
        currentStation = snap.currentStation;
        entryStep = snap.step;
      }

      // Track observations (belief changes)
      if (snap.lastEvent?.observation) {
        beliefHistory.push({
          step: snap.step,
          beliefs: { ...snap.belief.beliefs },
          uncertainty: snap.belief.uncertainty,
        });
      }

      // Track policy decisions (on recommendation changes)
      if (snap.belief.recommendedAction) {
        const last = policyDecisions[policyDecisions.length - 1];
        if (
          !last ||
          last.action !== snap.belief.recommendedAction.action ||
          last.reason !== snap.belief.recommendedAction.reason
        ) {
          policyDecisions.push({
            step: snap.step,
            action: snap.belief.recommendedAction.action,
            reason: snap.belief.recommendedAction.reason,
            confidence: snap.belief.recommendedAction.confidence,
          });
        }
      }
    }

    // Close last station visit
    stationVisits.push({
      station: currentStation,
      entryStep,
      exitStep: snap.step,
    });

    // Extract observations from events
    const observations = snap.events
      .filter((e: SimEvent) => e.observation != null)
      .map((e: SimEvent) => e.observation!);

    runs.push({
      scenario: {
        name: scenario.name,
        description: scenario.description,
        condition: scenario.condition,
      },
      seed,
      totalSteps: snap.step,
      completed: snap.phase === 'completed',
      outputBin: snap.outputBin,
      product: snap.product as unknown as Record<string, unknown>,
      finalBelief: {
        beliefs: snap.belief.beliefs,
        uncertainty: snap.belief.uncertainty,
      },
      events: snap.events,
      observations,
      beliefHistory,
      stationVisits,
      policyDecisions,
    });
  }
}

// ── Output ───────────────────────────────────────────────────────────

const output = {
  runs,
  meta: {
    timestamp: new Date().toISOString(),
    version: '0.1.0',
    totalRuns: runs.length,
    scenariosUsed: [...new Set(runs.map((r) => r.scenario.name))],
    seedsUsed: [...new Set(runs.map((r) => r.seed))],
  },
};

console.log(JSON.stringify(output, null, 2));
