import type {
  SimulationSnapshot,
  CompletedProduct,
  DecisionRecord,
  Hypothesis,
  Observation,
  ProductTrace,
  StructuredDecision,
} from './types';
import type { PolicyConfig } from './config';
import type { RunMetrics, ConfusionMatrix } from './metrics';
import { computeRunMetrics } from './metrics';
import { computeBeliefDiagnostics } from './policy';

// ── Label maps ───────────────────────────────────────────────────────

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

// ── Formatting helpers ───────────────────────────────────────────────

function pct(v: number): string {
  return (v * 100).toFixed(1) + '%';
}

function humanLabel(key: string, map: Record<string, string>): string {
  return map[key] ?? key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function stationLabel(id: string): string {
  return id.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function fmtNum(v: number, decimals = 2): string {
  return v.toFixed(decimals);
}

// ── Confusion matrix → Markdown ──────────────────────────────────────

function renderConfusionMatrix(cm: ConfusionMatrix, title: string): string[] {
  const lines: string[] = [];
  lines.push(`### ${title}`);
  lines.push('');

  if (cm.labels.length === 0) {
    lines.push('_No data._');
    lines.push('');
    return lines;
  }

  const combinedLabels: Record<string, string> = { ...HYPOTHESIS_LABELS, ...BIN_LABELS };
  const header = '| True \\ Predicted | ' + cm.labels.map(l => humanLabel(l, combinedLabels)).join(' | ') + ' |';
  const sep = '|---' + '|---'.repeat(cm.labels.length) + '|';
  lines.push(header);
  lines.push(sep);

  for (let r = 0; r < cm.labels.length; r++) {
    const rowLabel = humanLabel(cm.labels[r], combinedLabels);
    const cells = cm.matrix[r].map(String).join(' | ');
    lines.push(`| ${rowLabel} | ${cells} |`);
  }
  lines.push('');
  return lines;
}

// ═══════════════════════════════════════════════════════════════════════
// 1. exportForLLM — rich Markdown export
// ═══════════════════════════════════════════════════════════════════════

export function exportForLLM(
  snapshot: SimulationSnapshot,
  scenarioName: string,
  seed: number,
  config?: PolicyConfig,
  maxEvents = 30,
): string {
  const lines: string[] = [];
  const ts = new Date().toISOString();

  lines.push('# Demanufacturing Cell Simulation — State Export');
  lines.push('');
  lines.push(`> Exported at ${ts}`);
  lines.push('');

  // ── 1. Configuration ───────────────────────────────────────────────
  lines.push('## Configuration');
  lines.push(`- **Scenario**: ${scenarioName}`);
  lines.push(`- **Seed**: ${seed}`);
  lines.push(`- **Current step**: ${snapshot.step}`);
  lines.push(`- **Phase**: ${snapshot.phase}`);
  const completed = snapshot.completedProducts?.length ?? 0;
  lines.push(`- **Products processed**: ${completed} (current: #${snapshot.productNumber ?? 1})`);
  if (config) {
    lines.push(`- **Policy**: ${config.name} — "${config.description}"`);
    lines.push(`- **Key thresholds**: minTopConf=${fmtNum(config.minTopConfidence)}, minMargin=${fmtNum(config.minTop2Margin)}, hazardGuard=${fmtNum(config.hazardGuardThreshold)}, abstention=${fmtNum(config.abstentionThreshold)}`);
  }
  lines.push('');

  // ── 2. Current Product ─────────────────────────────────────────────
  const p = snapshot.product;
  lines.push(`## Current Product (#${snapshot.productNumber ?? 1})`);
  lines.push(`- **ID**: ${p.id}`);
  lines.push(`- **Hidden condition**: ${humanLabel(p.condition, CONDITION_LABELS)} (NOT visible to the system)`);
  lines.push(`- **Properties**: screw_difficulty=${fmtNum(p.screwsDifficulty)}, adhesive=${fmtNum(p.adhesiveStrength)}, battery_risk=${fmtNum(p.batteryRisk)}, casing=${fmtNum(p.casingIntegrity)}, missing_parts=${p.missingParts ? 'yes' : 'no'}`);
  lines.push('');

  // ── 3. Current Belief State ────────────────────────────────────────
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

  const diag = computeBeliefDiagnostics(belief.beliefs, belief.uncertainty);
  if (diag.top2) {
    lines.push(`- **Top-2 hypothesis**: ${humanLabel(diag.top2.hypothesis, HYPOTHESIS_LABELS)} (${pct(diag.top2.probability)})`);
    lines.push(`- **Top-1 / Top-2 margin**: ${pct(diag.margin)}`);
  }
  lines.push(`- **Hazard guard**: ${diag.hazardPresent ? '🔴 ACTIVE (battery_hazard elevated)' : '🟢 Inactive'}`);

  const rec = belief.recommendedAction;
  lines.push(`- **Policy recommendation**: ${rec.action} — "${rec.reason}"`);
  lines.push('');

  // ── 4. Current Decision ────────────────────────────────────────────
  lines.push('## Current Decision');
  const cd = snapshot.currentDecision;
  if (cd) {
    lines.push(`- **Type**: ${cd.type}`);
    lines.push(`- **Confidence level**: ${cd.confidenceLevel}`);
    lines.push(`- **Selected route**: ${cd.selectedRoute ? stationLabel(cd.selectedRoute) : '(none — seeking evidence)'}`);
    lines.push(`- **Source**: ${cd.source}`);
    lines.push(`- **Reason**: ${cd.reason}`);
    lines.push(`- **Reason codes**: ${cd.reasonCodes.length > 0 ? cd.reasonCodes.join(', ') : '(none)'}`);
    lines.push(`- **Top hypothesis**: ${humanLabel(cd.topHypothesis.hypothesis, HYPOTHESIS_LABELS)} (${pct(cd.topHypothesis.probability)})`);
    if (cd.top2Hypothesis) {
      lines.push(`- **Top-2 hypothesis**: ${humanLabel(cd.top2Hypothesis.hypothesis, HYPOTHESIS_LABELS)} (${pct(cd.top2Hypothesis.probability)})`);
    }
    lines.push(`- **Top-2 margin**: ${pct(cd.top2Margin)}`);
    lines.push(`- **Uncertainty**: ${pct(cd.uncertainty)}`);
    lines.push(`- **Hazard present**: ${cd.hazardPresent ? 'yes' : 'no'}`);
    lines.push(`- **Enabled alternatives**: ${cd.enabledAlternatives.length > 0 ? cd.enabledAlternatives.map(stationLabel).join(', ') : '(none)'}`);
    lines.push(`- **Additional evidence available**: ${cd.additionalEvidenceAvailable ? 'yes' : 'no'}`);
    lines.push(`- **Evidence requests so far**: ${cd.evidenceRequestCount}`);
  } else {
    lines.push('_No structured decision recorded for this step._');
  }
  lines.push('');

  // ── 5. Current DES State ───────────────────────────────────────────
  const curStation = snapshot.stations[snapshot.currentStation];
  lines.push('## Current DES State');
  lines.push(`- **Item at**: ${stationLabel(snapshot.currentStation)} (${curStation?.status ?? 'unknown'}${curStation && curStation.processingTimeLeft > 0 ? `, ${curStation.processingTimeLeft} ticks left` : ''})`);
  if (snapshot.enabledTransitions.length > 0) {
    lines.push(`- **Enabled transitions**: ${snapshot.enabledTransitions.map(t => stationLabel(t)).join(', ')}`);
  } else {
    lines.push('- **Enabled transitions**: none');
  }
  lines.push('');

  // ── 6. Decision Trace (current product) ────────────────────────────
  const dh = snapshot.decisionHistory ?? [];
  lines.push('## Decision Trace (current product)');
  if (dh.length === 0) {
    lines.push('_No decisions recorded yet for this product._');
  } else {
    lines.push('| Step | Station | Decision Type | Selected | Reason Codes | Confidence |');
    lines.push('|---|---|---|---|---|---|');
    for (const dr of dh) {
      const d = dr.decision;
      lines.push(`| ${dr.step} | ${stationLabel(dr.station)} | ${d.type} | ${stationLabel(dr.selected)} | ${d.reasonCodes.join(', ') || '—'} | ${d.confidenceLevel} |`);
    }
  }
  lines.push('');

  // ── 7. Observations (current product) ──────────────────────────────
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

  // ── 8. Event Log (last N events) ──────────────────────────────────
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

  // ── 9. Completed Products History ──────────────────────────────────
  const cp = snapshot.completedProducts ?? [];
  lines.push('## Completed Products History');
  if (cp.length === 0) {
    lines.push('_No products completed yet._');
  } else {
    lines.push('| # | ID | True Condition | Output Bin | Steps | Belief Correct? | Dominant Belief | Escalated | Abstained | Ev.Reqs | Decisions |');
    lines.push('|---|---|---|---|---|---|---|---|---|---|---|');
    cp.forEach((c: CompletedProduct, i: number) => {
      const binLabel = humanLabel(c.outputBin, BIN_LABELS).replace(/^[^\w]*\s*/, '');
      lines.push(`| ${i + 1} | ${c.id} | ${humanLabel(c.condition, CONDITION_LABELS)} | ${binLabel} | ${c.totalSteps} | ${c.beliefCorrect ? '✓' : '✗'} | ${humanLabel(c.dominantBelief.hypothesis, HYPOTHESIS_LABELS)} (${pct(c.dominantBelief.confidence)}) | ${c.escalated ? '✓' : '—'} | ${c.abstained ? '✓' : '—'} | ${c.evidenceRequests} | ${c.decisionCount} |`);
    });
  }
  lines.push('');

  // ── 10. Run Metrics ────────────────────────────────────────────────
  lines.push('## Run Metrics');
  if (cp.length === 0) {
    lines.push('_No products completed yet — metrics unavailable._');
  } else {
    const m = computeRunMetrics(cp);

    lines.push('### Accuracy & Rates');
    lines.push(`- **Top-1 belief accuracy**: ${pct(m.beliefTop1Accuracy)}`);
    lines.push(`- **Abstention rate**: ${pct(m.abstentionRate)}`);
    lines.push(`- **Escalation rate**: ${pct(m.escalationRate)}`);
    lines.push(`- **Evidence-seeking rate**: ${pct(m.evidenceSeekingRate)}`);
    lines.push(`- **Unresolved rate**: ${pct(m.unresolvedRate)}`);
    lines.push('');

    lines.push('### Safety');
    lines.push(`- **Hazard recall**: ${pct(m.hazardRecall)}`);
    lines.push(`- **False-safe rate**: ${pct(m.falseSafeRate)}`);
    lines.push('');

    lines.push('### Efficiency');
    lines.push(`- **Avg steps/product**: ${fmtNum(m.avgStepsPerProduct)}`);
    lines.push(`- **Avg decisions/product**: ${fmtNum(m.avgDecisionsPerProduct)}`);
    lines.push(`- **Avg evidence requests/product**: ${fmtNum(m.avgEvidenceRequestsPerProduct)}`);
    lines.push('');

    lines.push('### Calibration');
    if (m.calibrationBuckets.length > 0) {
      lines.push('| Range | Count | Correct | Accuracy |');
      lines.push('|---|---|---|---|');
      for (const b of m.calibrationBuckets) {
        lines.push(`| ${b.range} | ${b.count} | ${b.correctCount} | ${pct(b.accuracy)} |`);
      }
    } else {
      lines.push('_No calibration data._');
    }
    lines.push('');

    // ── 11. Confusion Matrices ───────────────────────────────────────
    lines.push(...renderConfusionMatrix(m.beliefConfusion, 'Belief Confusion Matrix (True Condition → Dominant Belief)'));
    lines.push(...renderConfusionMatrix(m.binConfusion, 'Bin Confusion Matrix (True Condition → Output Bin)'));

    // ── 12. Per-Condition Breakdown ──────────────────────────────────
    lines.push('## Per-Condition Breakdown');
    const condEntries = Object.entries(m.conditionBreakdown);
    if (condEntries.length === 0) {
      lines.push('_No per-condition data._');
    } else {
      lines.push('| Condition | Count | Belief Acc. | Avg Steps | Avg Unc. | Escalation | Abstention |');
      lines.push('|---|---|---|---|---|---|---|');
      for (const [cond, data] of condEntries) {
        lines.push(`| ${humanLabel(cond, CONDITION_LABELS)} | ${data.count} | ${pct(data.beliefAccuracy)} | ${fmtNum(data.avgSteps)} | ${fmtNum(data.avgUncertainty)} | ${pct(data.escalationRate)} | ${pct(data.abstentionRate)} |`);
      }
    }
    lines.push('');
  }

  // ── 13. Bin Tallies ────────────────────────────────────────────────
  const bins = snapshot.binCounts ?? {};
  lines.push('## Bin Tallies');
  lines.push(`- ♻️ Reusable: ${bins['output_reusable'] ?? 0}`);
  lines.push(`- 🔄 Recoverable: ${bins['output_recoverable'] ?? 0}`);
  lines.push(`- ⚠️ Hazardous: ${bins['output_hazardous'] ?? 0}`);
  lines.push(`- ❓ Unresolved: ${bins['output_unresolved'] ?? 0}`);
  lines.push('');

  // ── 14. Policy Config ──────────────────────────────────────────────
  lines.push('## Policy Config');
  if (config) {
    lines.push('| Parameter | Value |');
    lines.push('|---|---|');
    lines.push(`| name | ${config.name} |`);
    lines.push(`| description | ${config.description} |`);
    lines.push(`| minTopConfidence | ${fmtNum(config.minTopConfidence)} |`);
    lines.push(`| minTop2Margin | ${fmtNum(config.minTop2Margin)} |`);
    lines.push(`| highUncertaintyThreshold | ${fmtNum(config.highUncertaintyThreshold)} |`);
    lines.push(`| hazardGuardThreshold | ${fmtNum(config.hazardGuardThreshold)} |`);
    lines.push(`| safeRouteThreshold | ${fmtNum(config.safeRouteThreshold)} |`);
    lines.push(`| abstentionThreshold | ${fmtNum(config.abstentionThreshold)} |`);
    lines.push(`| maxUnscrewAttempts | ${config.maxUnscrewAttempts} |`);
    lines.push(`| allowEvidenceSeeking | ${config.allowEvidenceSeeking} |`);
    lines.push(`| maxEvidenceRequests | ${config.maxEvidenceRequests} |`);
    lines.push(`| evidenceSeekingUncertaintyThreshold | ${fmtNum(config.evidenceSeekingUncertaintyThreshold)} |`);
  } else {
    lines.push('_No policy config provided._');
  }
  lines.push('');

  // ── 15. Context for Analysis ───────────────────────────────────────
  lines.push('## Context for Analysis');
  lines.push('This simulation models a single demanufacturing cell processing used laptops. Each product has a hidden structural condition that is NOT directly observable. The system uses Bayesian belief updates from noisy station observations to estimate the condition, and a threshold-based policy to route products through the cell.');
  lines.push('');
  lines.push('Key concepts:');
  lines.push('- **DES state** = operational flow (which station, what\'s processing, event sequence)');
  lines.push('- **Belief state** = epistemic uncertainty over the product\'s hidden condition');
  lines.push('- The DES controls execution; the belief layer informs routing decisions under partial observability.');
  lines.push('- The policy uses **configurable thresholds** (confidence, margin, hazard guard, abstention) to make routing decisions — different policy presets trade off accuracy vs. safety vs. throughput.');
  lines.push('');

  return lines.join('\n');
}

// ═══════════════════════════════════════════════════════════════════════
// 2. exportJSON — machine-readable structured export
// ═══════════════════════════════════════════════════════════════════════

export interface ExportJSONResult {
  meta: {
    scenario: string;
    seed: number;
    step: number;
    phase: string;
    timestamp: string;
    policyConfig: PolicyConfig | null;
  };
  currentProduct: {
    id: string;
    condition: string;
    screwsDifficulty: number;
    adhesiveStrength: number;
    batteryRisk: number;
    casingIntegrity: number;
    missingParts: boolean;
  };
  currentBelief: {
    beliefs: Record<Hypothesis, number>;
    uncertainty: number;
    diagnostics: {
      top1: { hypothesis: Hypothesis; probability: number };
      top2: { hypothesis: Hypothesis; probability: number } | null;
      margin: number;
      hazardPresent: boolean;
      safeSum: number;
    };
  };
  currentDecision: StructuredDecision | null;
  decisionTrace: DecisionRecord[];
  observations: Observation[];
  completedProducts: CompletedProduct[];
  productTraces: ProductTrace[];
  metrics: RunMetrics | null;
  binCounts: Record<string, number>;
}

export function exportJSON(
  snapshot: SimulationSnapshot,
  scenarioName: string,
  seed: number,
  config?: PolicyConfig,
): ExportJSONResult {
  const belief = snapshot.belief;
  const diag = computeBeliefDiagnostics(belief.beliefs, belief.uncertainty);
  const cp = snapshot.completedProducts ?? [];
  const metrics = cp.length > 0 ? computeRunMetrics(cp) : null;

  return {
    meta: {
      scenario: scenarioName,
      seed,
      step: snapshot.step,
      phase: snapshot.phase,
      timestamp: new Date().toISOString(),
      policyConfig: config ?? null,
    },
    currentProduct: {
      id: snapshot.product.id,
      condition: snapshot.product.condition,
      screwsDifficulty: snapshot.product.screwsDifficulty,
      adhesiveStrength: snapshot.product.adhesiveStrength,
      batteryRisk: snapshot.product.batteryRisk,
      casingIntegrity: snapshot.product.casingIntegrity,
      missingParts: snapshot.product.missingParts,
    },
    currentBelief: {
      beliefs: { ...belief.beliefs },
      uncertainty: belief.uncertainty,
      diagnostics: {
        top1: diag.top1,
        top2: diag.top2,
        margin: diag.margin,
        hazardPresent: diag.hazardPresent,
        safeSum: diag.safeSum,
      },
    },
    currentDecision: snapshot.currentDecision ?? null,
    decisionTrace: snapshot.decisionHistory ?? [],
    observations: belief.observations ?? [],
    completedProducts: cp,
    productTraces: snapshot.productTraces ?? [],
    metrics,
    binCounts: snapshot.binCounts ?? {},
  };
}
