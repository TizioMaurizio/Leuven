import type { SimulationSnapshot, CompletedProduct, Hypothesis, Observation } from './types';

const HYPOTHESIS_LABELS: Record<Hypothesis, string> = {
  normal_path: 'Normal Path',
  hidden_fastener: 'Hidden Fastener',
  adhesive_issue: 'Adhesive Issue',
  battery_hazard: 'Battery Hazard',
  missing_parts: 'Missing Parts',
  structural_damage: 'Structural Damage',
  easy_case: 'Easy Case',
};

const BIN_LABELS: Record<string, string> = {
  output_reusable: '♻️ Reusable',
  output_recoverable: '🔄 Recoverable',
  output_hazardous: '⚠️ Hazardous',
  output_unresolved: '❓ Unresolved',
};

const CONDITION_LABELS: Record<string, string> = {
  normal: 'Normal',
  hidden_screws: 'Hidden Screws',
  strong_adhesive: 'Strong Adhesive',
  swollen_battery: 'Swollen Battery',
  missing_component: 'Missing Component',
  casing_damage: 'Casing Damage',
  easy_disassembly: 'Easy Disassembly',
};

function pct(v: number): string {
  return (v * 100).toFixed(1) + '%';
}

function humanLabel(key: string, map: Record<string, string>): string {
  return map[key] ?? key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function stationLabel(id: string): string {
  return id.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export function exportForLLM(
  snapshot: SimulationSnapshot,
  scenarioName: string,
  seed: number,
  maxEvents = 30,
): string {
  const lines: string[] = [];
  const ts = new Date().toISOString();

  lines.push('# Demanufacturing Cell Simulation — State Export');
  lines.push('');
  lines.push(`> Exported at ${ts}`);
  lines.push('');

  // ── Configuration ──────────────────────────────────────────────────
  lines.push('## Configuration');
  lines.push(`- **Scenario**: ${scenarioName}`);
  lines.push(`- **Seed**: ${seed}`);
  lines.push(`- **Current step**: ${snapshot.step}`);
  const completed = snapshot.completedProducts?.length ?? 0;
  lines.push(`- **Products processed**: ${completed} (current: #${snapshot.productNumber ?? 1})`);
  lines.push(`- **Phase**: ${snapshot.phase}`);
  lines.push('');

  // ── Current Product ────────────────────────────────────────────────
  const p = snapshot.product;
  lines.push(`## Current Product (#${snapshot.productNumber ?? 1})`);
  lines.push(`- **ID**: ${p.id}`);
  lines.push(`- **Hidden condition**: ${humanLabel(p.condition, CONDITION_LABELS)} (NOT visible to the system)`);
  lines.push(`- **Properties**: screw_difficulty=${p.screwsDifficulty.toFixed(2)}, adhesive=${p.adhesiveStrength.toFixed(2)}, battery_risk=${p.batteryRisk.toFixed(2)}, casing=${p.casingIntegrity.toFixed(2)}, missing_parts=${p.missingParts ? 'yes' : 'no'}`);
  lines.push('');

  // ── Current Belief State ───────────────────────────────────────────
  const belief = snapshot.belief;
  const sorted = Object.entries(belief.beliefs)
    .map(([h, prob]) => ({ hypothesis: h as Hypothesis, prob }))
    .sort((a, b) => b.prob - a.prob);

  lines.push('## Current Belief State');
  lines.push('The system does NOT know the true condition. Its current estimate:');
  lines.push('');
  lines.push('| Hypothesis | Probability |');
  lines.push('|---|---|');
  for (const { hypothesis, prob } of sorted) {
    lines.push(`| ${humanLabel(hypothesis, HYPOTHESIS_LABELS)} | ${pct(prob)} |`);
  }
  lines.push('');

  const dominant = sorted[0];
  lines.push(`- **Uncertainty**: ${pct(belief.uncertainty)} (${belief.uncertainty > 0.6 ? 'high' : belief.uncertainty > 0.3 ? 'medium' : 'low'})`);
  if (dominant) {
    lines.push(`- **Dominant hypothesis**: ${humanLabel(dominant.hypothesis, HYPOTHESIS_LABELS)} (${pct(dominant.prob)})`);
  }
  const rec = belief.recommendedAction;
  lines.push(`- **Policy recommendation**: ${rec.action} — "${rec.reason}"`);
  lines.push('');

  // ── Current DES State ──────────────────────────────────────────────
  const curStation = snapshot.stations[snapshot.currentStation];
  lines.push('## Current DES State');
  lines.push(`- **Item at**: ${stationLabel(snapshot.currentStation)} (${curStation?.status ?? 'unknown'}${curStation && curStation.processingTimeLeft > 0 ? `, ${curStation.processingTimeLeft} ticks left` : ''})`);
  if (snapshot.enabledTransitions.length > 0) {
    lines.push(`- **Enabled transitions**: ${snapshot.enabledTransitions.map(t => stationLabel(t)).join(', ')}`);
  } else {
    lines.push('- **Enabled transitions**: none');
  }
  lines.push('');

  // ── Observations (current product) ─────────────────────────────────
  const obs = belief.observations ?? [];
  lines.push('## Observations (current product)');
  if (obs.length === 0) {
    lines.push('_No observations recorded yet._');
  } else {
    lines.push('| # | Step | Station | Evidence | Confidence |');
    lines.push('|---|---|---|---|---|');
    obs.forEach((o: Observation, i: number) => {
      lines.push(`| ${i + 1} | ${o.step} | ${stationLabel(o.station)} | ${o.evidence} | ${pct(o.confidence)} |`);
    });
  }
  lines.push('');

  // ── Event Log (last N events) ──────────────────────────────────────
  const events = snapshot.events ?? [];
  const tail = events.slice(-maxEvents);
  lines.push(`## Event Log (last ${maxEvents} events)`);
  if (tail.length === 0) {
    lines.push('_No events recorded yet._');
  } else {
    if (events.length > maxEvents) {
      lines.push(`_Showing last ${maxEvents} of ${events.length} total events._`);
      lines.push('');
    }
    lines.push('| Step | Type | Station | Description |');
    lines.push('|---|---|---|---|');
    for (const e of tail) {
      lines.push(`| ${e.step} | ${e.type} | ${stationLabel(e.station)} | ${e.description} |`);
    }
  }
  lines.push('');

  // ── Completed Products History ─────────────────────────────────────
  const cp = snapshot.completedProducts ?? [];
  lines.push('## Completed Products History');
  if (cp.length === 0) {
    lines.push('_No products completed yet._');
  } else {
    lines.push('| # | ID | True Condition | Output Bin | Steps | Belief Correct? | Dominant Belief |');
    lines.push('|---|---|---|---|---|---|---|');
    cp.forEach((c: CompletedProduct, i: number) => {
      const binLabel = humanLabel(c.outputBin, BIN_LABELS).replace(/^[^\w]*\s*/, '');
      lines.push(`| ${i + 1} | ${c.id} | ${humanLabel(c.condition, CONDITION_LABELS)} | ${binLabel} | ${c.totalSteps} | ${c.beliefCorrect ? '✓' : '✗'} | ${humanLabel(c.dominantBelief.hypothesis, HYPOTHESIS_LABELS)} (${pct(c.dominantBelief.confidence)}) |`);
    });
  }
  lines.push('');

  // ── Bin Tallies ────────────────────────────────────────────────────
  const bins = snapshot.binCounts ?? {};
  lines.push('## Bin Tallies');
  lines.push(`- ♻️ Reusable: ${bins['output_reusable'] ?? 0}`);
  lines.push(`- 🔄 Recoverable: ${bins['output_recoverable'] ?? 0}`);
  lines.push(`- ⚠️ Hazardous: ${bins['output_hazardous'] ?? 0}`);
  lines.push(`- ❓ Unresolved: ${bins['output_unresolved'] ?? 0}`);
  lines.push('');

  // ── Context for Analysis ───────────────────────────────────────────
  lines.push('## Context for Analysis');
  lines.push('This simulation models a single demanufacturing cell processing used laptops. Each product has a hidden structural condition that is NOT directly observable. The system uses Bayesian belief updates from noisy station observations to estimate the condition, and a threshold-based policy to route products through the cell.');
  lines.push('');
  lines.push('Key concepts:');
  lines.push('- **DES state** = operational flow (which station, what\'s processing, event sequence)');
  lines.push('- **Belief state** = epistemic uncertainty over the product\'s hidden condition');
  lines.push('- The DES controls execution; the belief layer informs routing decisions under partial observability.');
  lines.push('');

  return lines.join('\n');
}
