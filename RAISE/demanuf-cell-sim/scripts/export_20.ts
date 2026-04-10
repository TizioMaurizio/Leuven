import { SimEngine } from '../src/sim/engine';
import { SCENARIOS } from '../src/sim/scenarios';
import { exportForLLM } from '../src/sim/export';

function runWithIntermediates(scenarioIndex: number, seed: number, scenarioName: string): void {
  const scenario = SCENARIOS[scenarioIndex];
  const engine = new SimEngine(seed, scenario);
  engine.setMaxProducts(20);

  const exports: { label: string; text: string }[] = [];
  let prevCompleted = 0;
  let steps = 0;

  while (!engine.isComplete() && steps < 2000) {
    const snap = engine.step();
    steps++;

    const currentCompleted = snap.completedProducts?.length ?? 0;
    if (currentCompleted > prevCompleted) {
      // A new product was just completed
      exports.push({
        label: `=== EXPORT AFTER PRODUCT ${currentCompleted} ===`,
        text: exportForLLM(snap, scenarioName, seed),
      });
      prevCompleted = currentCompleted;
    }
  }

  // Final export
  const finalSnap = engine.getSnapshot();
  exports.push({
    label: `=== FINAL EXPORT (${scenarioName}, seed=${seed}) ===`,
    text: exportForLLM(finalSnap, scenarioName, seed),
  });

  for (const e of exports) {
    console.log('\n' + e.label);
    console.log(e.text);
  }
}

function runFinalOnly(scenarioIndex: number, seed: number, scenarioName: string): void {
  const scenario = SCENARIOS[scenarioIndex];
  const engine = new SimEngine(seed, scenario);
  engine.setMaxProducts(20);

  let steps = 0;
  while (!engine.isComplete() && steps < 2000) {
    engine.step();
    steps++;
  }

  const finalSnap = engine.getSnapshot();
  console.log(`\n=== FINAL EXPORT (${scenarioName}, seed=${seed}) ===`);
  console.log(exportForLLM(finalSnap, scenarioName, seed));
}

// Run Nominal with intermediates
console.log('############################################################');
console.log('# NOMINAL LAPTOP — seed 42 — with intermediate exports');
console.log('############################################################');
runWithIntermediates(0, 42, 'Nominal Laptop');

// Run Swollen Battery (index 2) final only
console.log('\n\n############################################################');
console.log('# SWOLLEN BATTERY — seed 42 — final export only');
console.log('############################################################');
runFinalOnly(2, 42, 'Swollen Battery');

// Run Random (index 7) final only
console.log('\n\n############################################################');
console.log('# RANDOM — seed 42 — final export only');
console.log('############################################################');
runFinalOnly(7, 42, 'Random');
