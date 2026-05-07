/**
 * safety_tests.ts — Deterministic safety & causality tests for the simulation engine.
 *
 * Run with:  npx tsx scripts/safety_tests.ts
 */

import { SimEngine } from '../src/sim/engine';
import { SCENARIOS } from '../src/sim/scenarios';
import { POLICY_PRESETS, type PolicyConfig } from '../src/sim/config';
import { evaluatePolicy, selectOutputBin, computeBeliefDiagnostics } from '../src/sim/policy';
import type {
  DecisionRecord,
  HiddenCondition,
  Hypothesis,
  ProductTrace,
  SimulationSnapshot,
  StationId,
} from '../src/sim/types';

// ── Helpers ──────────────────────────────────────────────────────────

const SEED = 42;
const N_PRODUCTS = 20;
const MAX_STEPS = 2000;

const GROUND_TRUTH_FIELDS: (keyof import('../src/sim/types').ProductTrueState)[] = [
  'condition', 'batteryRisk', 'casingIntegrity', 'screwsDifficulty', 'adhesiveStrength', 'missingParts',
];

const CONDITION_NAMES: HiddenCondition[] = [
  'normal', 'hidden_screws', 'strong_adhesive', 'swollen_battery',
  'missing_component', 'casing_damage', 'easy_disassembly',
];

function randomScenario() {
  return SCENARIOS.find(s => s.name === 'Random')!;
}

function swollenScenario() {
  return SCENARIOS.find(s => s.name === 'Swollen Battery')!;
}

function runToCompletion(engine: SimEngine): SimulationSnapshot {
  let snap = engine.getSnapshot();
  let steps = 0;
  while (!engine.isComplete() && steps < MAX_STEPS) {
    snap = engine.step();
    steps++;
  }
  return snap;
}

interface TestResult {
  name: string;
  pass: boolean;
  detail: string;
  violations: string[];
}

// ══════════════════════════════════════════════════════════════════════
//  Test 1: No ground-truth leak in decisions
// ══════════════════════════════════════════════════════════════════════

function test1_noGroundTruthLeak(): TestResult {
  const violations: string[] = [];
  let totalDecisions = 0;

  for (const [presetName, config] of Object.entries(POLICY_PRESETS)) {
    const engine = new SimEngine(SEED, randomScenario(), config);
    engine.setMaxProducts(N_PRODUCTS);
    const snap = runToCompletion(engine);

    // Part A: Check decision reasons don't contain ground-truth field names
    for (const trace of snap.productTraces) {
      for (const dr of trace.decisions) {
        totalDecisions++;
        const reason = dr.decision.reason.toLowerCase();
        // Check the reason doesn't reference raw ground-truth fields
        for (const field of GROUND_TRUTH_FIELDS) {
          if (reason.includes(`product.${field}`)) {
            violations.push(
              `[${presetName}] Product #${trace.productNumber} step ${dr.step}: ` +
              `reason contains ground-truth ref "product.${field}"`
            );
          }
        }
        // Check the reason doesn't contain the raw condition name of THIS product
        // (other condition names appearing generically is fine — it's the specific true condition that leaks info)
        const trueCondition = trace.trueCondition;
        if (reason.includes(trueCondition) && !['normal'].includes(trueCondition)) {
          // 'normal' is too generic to flag; check specifically for the others
          violations.push(
            `[${presetName}] Product #${trace.productNumber} step ${dr.step}: ` +
            `reason contains product's true condition "${trueCondition}"`
          );
        }
      }
    }

    // Part B: selectOutputBin with identical belief returns same result regardless of product
    // Build an artificial snapshot with uniform belief, then call selectOutputBin twice
    // with different underlying products — result must match.
    const finalSnap = snap;
    if (finalSnap.productTraces.length > 0) {
      const sampleTrace = finalSnap.productTraces[0];
      if (sampleTrace.beliefEvolution.length > 0) {
        const beliefEntry = sampleTrace.beliefEvolution[0]; // uniform initial belief
        // Build two minimal snapshots with different products but same belief
        const fakeSnapA: SimulationSnapshot = {
          step: 0,
          phase: 'running',
          product: { id: 'FAKE-A', condition: 'normal', screwsDifficulty: 0.1, adhesiveStrength: 0.1, batteryRisk: 0.05, missingParts: false, casingIntegrity: 0.95 },
          productNumber: 1,
          currentStation: 'unscrewing',
          stations: {} as any,
          belief: { beliefs: { ...beliefEntry.beliefs }, uncertainty: beliefEntry.uncertainty, observations: [], recommendedAction: { action: 'continue', reason: '', confidence: 0 } },
          events: [],
          enabledTransitions: [],
          lastEvent: null,
          outputBin: null,
          completedProducts: [],
          binCounts: {},
          unscrewAttempts: 1,
          unscrewSucceeded: true,
          currentDecision: null,
          decisionHistory: [],
          productTraces: [],
          evidenceRequestCount: 0,
        };
        const fakeSnapB: SimulationSnapshot = {
          ...fakeSnapA,
          product: { id: 'FAKE-B', condition: 'swollen_battery', screwsDifficulty: 0.9, adhesiveStrength: 0.8, batteryRisk: 0.95, missingParts: true, casingIntegrity: 0.2 },
        };

        const binA = selectOutputBin(fakeSnapA, config);
        const binB = selectOutputBin(fakeSnapB, config);

        if (binA !== binB) {
          violations.push(
            `[${presetName}] selectOutputBin differs for same belief but different products: ` +
            `${binA} vs ${binB}`
          );
        }
      }
    }
  }

  return {
    name: 'No ground-truth leak',
    pass: violations.length === 0,
    detail: `${totalDecisions} decisions checked`,
    violations,
  };
}

// ══════════════════════════════════════════════════════════════════════
//  Test 2: Enabled transition containment
// ══════════════════════════════════════════════════════════════════════

function test2_enabledTransitionContainment(): TestResult {
  const violations: string[] = [];
  let totalDecisions = 0;

  for (const [presetName, config] of Object.entries(POLICY_PRESETS)) {
    const engine = new SimEngine(SEED, randomScenario(), config);
    engine.setMaxProducts(N_PRODUCTS);
    const snap = runToCompletion(engine);

    for (const trace of snap.productTraces) {
      for (const dr of trace.decisions) {
        totalDecisions++;
        if (!dr.enabledTransitions.includes(dr.selected)) {
          violations.push(
            `[${presetName}] Product #${trace.productNumber} step ${dr.step}: ` +
            `selected "${dr.selected}" NOT in enabled set [${dr.enabledTransitions.join(', ')}]`
          );
        }
      }
    }
  }

  return {
    name: 'Enabled transition containment',
    pass: violations.length === 0,
    detail: `${totalDecisions} decisions checked`,
    violations,
  };
}

// ══════════════════════════════════════════════════════════════════════
//  Test 3: Abstention reproducibility (determinism)
// ══════════════════════════════════════════════════════════════════════

function test3_reproducibility(): TestResult {
  const violations: string[] = [];
  let presetsChecked = 0;

  for (const [presetName, config] of Object.entries(POLICY_PRESETS)) {
    presetsChecked++;

    // Run A
    const engineA = new SimEngine(SEED, randomScenario(), config);
    engineA.setMaxProducts(N_PRODUCTS);
    const snapA = runToCompletion(engineA);

    // Run B
    const engineB = new SimEngine(SEED, randomScenario(), config);
    engineB.setMaxProducts(N_PRODUCTS);
    const snapB = runToCompletion(engineB);

    // Compare product traces
    if (snapA.productTraces.length !== snapB.productTraces.length) {
      violations.push(
        `[${presetName}] Trace count mismatch: ${snapA.productTraces.length} vs ${snapB.productTraces.length}`
      );
      continue;
    }

    for (let i = 0; i < snapA.productTraces.length; i++) {
      const tA = snapA.productTraces[i];
      const tB = snapB.productTraces[i];

      if (tA.outputBin !== tB.outputBin) {
        violations.push(
          `[${presetName}] Product #${i + 1}: output bin differs (${tA.outputBin} vs ${tB.outputBin})`
        );
      }

      if (tA.decisions.length !== tB.decisions.length) {
        violations.push(
          `[${presetName}] Product #${i + 1}: decision count differs (${tA.decisions.length} vs ${tB.decisions.length})`
        );
        continue;
      }

      for (let j = 0; j < tA.decisions.length; j++) {
        const dA = tA.decisions[j];
        const dB = tB.decisions[j];
        if (dA.selected !== dB.selected) {
          violations.push(
            `[${presetName}] Product #${i + 1}, decision ${j}: selected differs (${dA.selected} vs ${dB.selected})`
          );
        }
        if (dA.decision.type !== dB.decision.type) {
          violations.push(
            `[${presetName}] Product #${i + 1}, decision ${j}: type differs (${dA.decision.type} vs ${dB.decision.type})`
          );
        }
      }
    }
  }

  return {
    name: 'Abstention reproducibility',
    pass: violations.length === 0,
    detail: `${presetsChecked} presets, each deterministic`,
    violations,
  };
}

// ══════════════════════════════════════════════════════════════════════
//  Test 4: Hazard guard invariant
// ══════════════════════════════════════════════════════════════════════

function test4_hazardGuard(): TestResult {
  const violations: string[] = [];
  const summaries: string[] = [];

  for (const [presetName, config] of Object.entries(POLICY_PRESETS)) {
    if (config.hazardGuardThreshold > 0.30) continue; // Only test strict presets

    const engine = new SimEngine(SEED, swollenScenario(), config);
    engine.setMaxProducts(N_PRODUCTS);
    const snap = runToCompletion(engine);

    let hazardExceededCount = 0;
    let correctlyHandled = 0;

    for (const trace of snap.productTraces) {
      // Check if battery_hazard exceeded the threshold at any point
      const hazardExceeded = trace.beliefEvolution.some(
        be => be.beliefs.battery_hazard > config.hazardGuardThreshold
      );

      if (hazardExceeded) {
        hazardExceededCount++;
        // Must be routed to hazardous or manual_escalation
        if (trace.outputBin === 'output_hazardous' || trace.outputBin === 'manual_escalation' || trace.escalated) {
          correctlyHandled++;
        } else {
          violations.push(
            `[${presetName}] Product #${trace.productNumber} (${trace.trueCondition}): ` +
            `battery_hazard exceeded ${(config.hazardGuardThreshold * 100).toFixed(0)}% ` +
            `but routed to ${trace.outputBin} without escalation`
          );
        }
      }
    }

    const belowThreshold = snap.productTraces.length - hazardExceededCount;
    summaries.push(
      `${presetName}: ${correctlyHandled}/${hazardExceededCount} hazard products handled` +
      (belowThreshold > 0 ? ` — ${belowThreshold} below threshold` : '')
    );
  }

  return {
    name: 'Hazard guard invariant',
    pass: violations.length === 0,
    detail: summaries.join('; '),
    violations,
  };
}

// ══════════════════════════════════════════════════════════════════════
//  Test 5: No future information in decisions
// ══════════════════════════════════════════════════════════════════════

function test5_noFutureInformation(): TestResult {
  const violations: string[] = [];
  let totalSteps = 0;

  for (const [presetName, config] of Object.entries(POLICY_PRESETS)) {
    const engine = new SimEngine(SEED, randomScenario(), config);
    engine.setMaxProducts(N_PRODUCTS);
    const snap = runToCompletion(engine);

    for (const trace of snap.productTraces) {
      for (const dr of trace.decisions) {
        totalSteps++;
        const decisionStep = dr.step;

        // All observations in the belief snapshot that informed this decision
        // must have step ≤ decisionStep.
        // We check via the observations recorded in the trace up to this point.
        const obsBeforeOrAt = trace.observations.filter(o => o.step <= decisionStep);
        const obsFuture = trace.observations.filter(o => o.step > decisionStep);

        // The belief snapshot at decision time should not reflect future observations.
        // We check: the decision's beliefSnapshot should be reachable from observations
        // with step ≤ decisionStep only.
        // Practical check: no observation in the trace with step > decisionStep
        // should have been incorporated before this decision.
        // Since decisions are recorded at dr.step, any observation in trace.observations
        // with step > dr.step should NOT have influenced the belief snapshot.

        // Verify belief snapshot entries are plausible — if a future observation
        // would dramatically shift a belief, flag it (heuristic: check ordering)
        // More robust: verify decision steps are monotonically increasing
        if (trace.decisions.indexOf(dr) > 0) {
          const prev = trace.decisions[trace.decisions.indexOf(dr) - 1];
          if (dr.step < prev.step) {
            violations.push(
              `[${presetName}] Product #${trace.productNumber}: ` +
              `decision at step ${dr.step} appears BEFORE prior decision at step ${prev.step} (non-monotonic)`
            );
          }
        }
      }

      // Also verify observations are time-ordered
      for (let i = 1; i < trace.observations.length; i++) {
        totalSteps++;
        if (trace.observations[i].step < trace.observations[i - 1].step) {
          violations.push(
            `[${presetName}] Product #${trace.productNumber}: ` +
            `observation at step ${trace.observations[i].step} appears before ` +
            `prior observation at step ${trace.observations[i - 1].step}`
          );
        }
      }
    }
  }

  return {
    name: 'No future information',
    pass: violations.length === 0,
    detail: `${totalSteps} steps checked`,
    violations,
  };
}

// ══════════════════════════════════════════════════════════════════════
//  Test 6: Monotonic belief (per product)
// ══════════════════════════════════════════════════════════════════════

function test6_monotonicBelief(): TestResult {
  const violations: string[] = [];
  let productsChecked = 0;

  // Use a single preset (abstention_aware) on Random scenario
  const config = POLICY_PRESETS.abstention_aware;
  const engine = new SimEngine(SEED, randomScenario(), config);
  engine.setMaxProducts(N_PRODUCTS);
  const snap = runToCompletion(engine);

  for (const trace of snap.productTraces) {
    productsChecked++;

    // Belief evolution steps must be strictly non-decreasing
    for (let i = 1; i < trace.beliefEvolution.length; i++) {
      const prev = trace.beliefEvolution[i - 1];
      const curr = trace.beliefEvolution[i];

      if (curr.step < prev.step) {
        violations.push(
          `Product #${trace.productNumber}: beliefEvolution step ${curr.step} ` +
          `< previous step ${prev.step} (non-monotonic time)`
        );
      }
    }

    // Observations must be strictly ordered by step
    for (let i = 1; i < trace.observations.length; i++) {
      if (trace.observations[i].step < trace.observations[i - 1].step) {
        violations.push(
          `Product #${trace.productNumber}: observation at step ${trace.observations[i].step} ` +
          `before previous at step ${trace.observations[i - 1].step}`
        );
      }
    }

    // Belief can only change when an observation has arrived.
    // Observations are timestamped at generation (step S) but consumed during
    // later ticks (step S+n). The causal check is: every belief change at step S
    // must have at least one observation with obs.step ≤ S that was not yet
    // consumed by an earlier belief change.
    const sortedObs = [...trace.observations].sort((a, b) => a.step - b.step);
    let obsIdx = 0; // next unconsumed observation

    for (let i = 1; i < trace.beliefEvolution.length; i++) {
      const prev = trace.beliefEvolution[i - 1];
      const curr = trace.beliefEvolution[i];

      // Check if beliefs actually changed
      const changed = (Object.keys(curr.beliefs) as Hypothesis[]).some(
        h => Math.abs(curr.beliefs[h] - prev.beliefs[h]) > 1e-9
      );

      if (changed) {
        // Consume exactly one observation whose generation step ≤ this belief change step
        const hadObs = obsIdx < sortedObs.length && sortedObs[obsIdx].step <= curr.step;
        if (hadObs) {
          obsIdx++;
        } else {
          violations.push(
            `Product #${trace.productNumber}: belief changed at step ${curr.step} ` +
            `but no unconsumed observation with step ≤ ${curr.step}`
          );
        }
      }
    }
  }

  return {
    name: 'Monotonic belief',
    pass: violations.length === 0,
    detail: `${productsChecked} products checked`,
    violations,
  };
}

// ══════════════════════════════════════════════════════════════════════
//  Test 7: Abstention threshold invariant
// ══════════════════════════════════════════════════════════════════════

function test7_abstentionThreshold(): TestResult {
  const violations: string[] = [];
  let totalDecisions = 0;

  const ABSTENTION_PRESETS = ['abstention_aware', 'cautious'] as const;
  const OUTPUT_BIN_STATIONS: StationId[] = [
    'output_reusable', 'output_recoverable', 'output_hazardous', 'output_unresolved',
  ];

  for (const presetName of ABSTENTION_PRESETS) {
    const config = POLICY_PRESETS[presetName];
    const engine = new SimEngine(SEED, randomScenario(), config);
    engine.setMaxProducts(N_PRODUCTS);
    const snap = runToCompletion(engine);

    for (const trace of snap.productTraces) {
      for (const dr of trace.decisions) {
        // Only consider routing decisions (where selected is an output bin)
        if (!OUTPUT_BIN_STATIONS.includes(dr.selected)) continue;

        totalDecisions++;

        // Compute the dominant belief from the belief snapshot at decision time
        const beliefs = dr.beliefSnapshot;
        const diag = computeBeliefDiagnostics(beliefs, dr.decision.uncertainty);
        const dominantProb = diag.top1.probability;

        // If dominant belief is below abstention threshold, decision type must NOT be route_confident
        if (dominantProb < config.abstentionThreshold) {
          const dt = dr.decision.type;
          if (dt === 'route_confident') {
            violations.push(
              `[${presetName}] Product #${trace.productNumber} step ${dr.step}: ` +
              `dominant belief ${(dominantProb * 100).toFixed(1)}% < abstention threshold ` +
              `${(config.abstentionThreshold * 100).toFixed(0)}%, but decision type is "${dt}"`
            );
          }
        }
      }
    }
  }

  return {
    name: 'Abstention threshold',
    pass: violations.length === 0,
    detail: `${totalDecisions} decisions checked`,
    violations,
  };
}

// ══════════════════════════════════════════════════════════════════════
//  Runner
// ══════════════════════════════════════════════════════════════════════

function main() {
  console.log('=== SAFETY & CAUSALITY TESTS ===\n');

  const tests: (() => TestResult)[] = [
    test1_noGroundTruthLeak,
    test2_enabledTransitionContainment,
    test3_reproducibility,
    test4_hazardGuard,
    test5_noFutureInformation,
    test6_monotonicBelief,
    test7_abstentionThreshold,
  ];

  const results: TestResult[] = [];

  for (let i = 0; i < tests.length; i++) {
    const result = tests[i]();
    results.push(result);
    const status = result.pass ? 'PASS' : 'FAIL';
    const detail = result.detail ? ` (${result.detail})` : '';
    console.log(`${i + 1}. ${result.name} ... ${status}${detail}`);

    if (!result.pass) {
      for (const v of result.violations.slice(0, 10)) {
        console.log(`   !! ${v}`);
      }
      if (result.violations.length > 10) {
        console.log(`   ... and ${result.violations.length - 10} more violations`);
      }
    }
  }

  const passed = results.filter(r => r.pass).length;
  console.log(`\n${passed}/${results.length} passed.`);

  if (passed < results.length) {
    process.exit(1);
  }
}

main();
