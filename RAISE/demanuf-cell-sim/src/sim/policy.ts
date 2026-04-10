import type {
  PolicyRecommendation,
  SimulationSnapshot,
  StationId,
} from './types';
import { getDominantHypothesis } from './belief';

// ── Constants ────────────────────────────────────────────────────────

const OUTPUT_BINS: StationId[] = [
  'output_reusable', 'output_recoverable', 'output_hazardous', 'output_unresolved',
];

// ── Exported API ─────────────────────────────────────────────────────

/**
 * Evaluate the current snapshot and produce a policy recommendation.
 * Rules are threshold-based and intentionally interpretable.
 */
export function evaluatePolicy(snapshot: SimulationSnapshot): PolicyRecommendation {
  const b = snapshot.belief.beliefs;
  const unc = snapshot.belief.uncertainty;
  const station = snapshot.currentStation;
  const nObs = snapshot.belief.observations.length;
  const unscrewAttempts = countUnscrewAttempts(snapshot);

  // At output bins → already complete
  if (OUTPUT_BINS.includes(station)) {
    return { action: 'complete', reason: 'Item has reached output bin.', confidence: 1 };
  }

  // 1. Battery hazard check
  if (b.battery_hazard > 0.4 && station !== 'battery_check') {
    return {
      action: 'reroute_battery',
      reason: `Battery hazard belief at ${pct(b.battery_hazard)} exceeds safety threshold (40%). Routing to battery check station for verification.`,
      confidence: b.battery_hazard,
    };
  }

  // 2. High uncertainty early in process → gather more evidence
  if (unc > 0.7 && nObs < 4 && (station === 'inspection' || station === 'conveyor')) {
    return {
      action: 'inspect_more',
      reason: `Uncertainty at ${pct(unc)} with only ${nObs} observation(s). More evidence needed before committing to a path.`,
      confidence: 1 - unc,
    };
  }

  // 3. Structural issues after unscrewing failure → escalate
  if ((b.hidden_fastener > 0.5 || b.adhesive_issue > 0.5) && unscrewAttempts >= 1) {
    const dominant = b.hidden_fastener > b.adhesive_issue ? 'hidden_fastener' : 'adhesive_issue';
    const val = Math.max(b.hidden_fastener, b.adhesive_issue);
    return {
      action: 'escalate',
      reason: `${dominant} belief at ${pct(val)} after ${unscrewAttempts} unscrewing attempt(s). Escalating to operator.`,
      confidence: val,
    };
  }

  // 4. Missing parts → escalate
  if (b.missing_parts > 0.5) {
    return {
      action: 'escalate',
      reason: `Missing parts belief at ${pct(b.missing_parts)} — manual verification required.`,
      confidence: b.missing_parts,
    };
  }

  // 5. Safe to continue
  const safeSum = b.normal_path + b.easy_case;
  if (safeSum > 0.6 && unc < 0.4) {
    return {
      action: 'continue',
      reason: `Combined normal/easy belief at ${pct(safeSum)} with low uncertainty (${pct(unc)}). Safe to proceed.`,
      confidence: safeSum,
    };
  }

  // 6. Unscrewing failed twice → operator
  if (unscrewAttempts >= 2) {
    return {
      action: 'reroute_operator',
      reason: `Unscrewing failed ${unscrewAttempts} times. Routing to manual escalation.`,
      confidence: 0.9,
    };
  }

  // 7. Default: base recommendation on highest-risk hypothesis
  const { hypothesis, confidence } = getDominantHypothesis(b);
  if (hypothesis === 'battery_hazard') {
    return {
      action: 'reroute_battery',
      reason: `Dominant hypothesis is battery_hazard (${pct(confidence)}). Verifying at battery check.`,
      confidence,
    };
  }
  if (hypothesis === 'hidden_fastener' || hypothesis === 'adhesive_issue' || hypothesis === 'structural_damage') {
    return {
      action: 'escalate',
      reason: `Dominant hypothesis is ${hypothesis} (${pct(confidence)}). Escalating for manual resolution.`,
      confidence,
    };
  }
  return {
    action: 'continue',
    reason: `Dominant hypothesis is ${hypothesis} (${pct(confidence)}). Proceeding normally.`,
    confidence: Math.max(0, 1 - unc),
  };
}

/**
 * Choose the next station to transition to, given the full snapshot.
 * Maps policy recommendations to concrete station transitions
 * based on the current station context.
 */
export function chooseTransition(snapshot: SimulationSnapshot): StationId {
  const rec = evaluatePolicy(snapshot);
  const station = snapshot.currentStation;
  const b = snapshot.belief;
  const unscrewAttempts = countUnscrewAttempts(snapshot);
  const unscrewSucceeded = snapshot.unscrewSucceeded;

  switch (station) {
    case 'input_buffer':
      return 'conveyor';

    case 'conveyor':
      return 'inspection';

    case 'inspection': {
      if (rec.action === 'reroute_battery') return 'battery_check';
      if (rec.action === 'escalate' || rec.action === 'reroute_operator') return 'manual_escalation';
      if (rec.action === 'inspect_more' && b.uncertainty > 0.8) return 'manual_escalation';
      return 'unscrewing';
    }

    case 'unscrewing': {
      if (unscrewSucceeded) {
        return chooseOutputBin(snapshot);
      }
      // Failure path
      if (unscrewAttempts >= 2) return 'manual_escalation';
      if (rec.action === 'reroute_operator' || rec.action === 'escalate') return 'manual_escalation';
      if (unscrewAttempts === 1 && b.uncertainty > 0.6) return 'manual_escalation';
      return 'unscrewing'; // retry
    }

    case 'battery_check': {
      if (b.beliefs.battery_hazard > 0.5) {
        return 'output_hazardous';
      }
      return 'unscrewing';
    }

    case 'manual_escalation':
      return chooseEscalationOutput(snapshot);

    default:
      return station;
  }
}

// ── Internal helpers ─────────────────────────────────────────────────

function pct(v: number): string {
  return `${(v * 100).toFixed(0)}%`;
}

function countUnscrewAttempts(snapshot: SimulationSnapshot): number {
  return snapshot.unscrewAttempts;
}

function chooseOutputBin(snapshot: SimulationSnapshot): StationId {
  const b = snapshot.belief;
  if (b.beliefs.battery_hazard > 0.5) return 'output_hazardous';
  if (b.beliefs.structural_damage > 0.4 || b.beliefs.missing_parts > 0.4) return 'output_recoverable';
  if (b.beliefs.hidden_fastener > 0.4 || b.beliefs.adhesive_issue > 0.4) return 'output_recoverable';
  if (b.beliefs.normal_path > 0.3 || b.beliefs.easy_case > 0.3) return 'output_reusable';
  return 'output_unresolved';
}

function chooseEscalationOutput(snapshot: SimulationSnapshot): StationId {
  const b = snapshot.belief;
  if (b.beliefs.battery_hazard > 0.5) return 'output_hazardous';
  if (b.beliefs.structural_damage > 0.4 || b.beliefs.missing_parts > 0.4) return 'output_recoverable';
  if (b.beliefs.hidden_fastener > 0.4 || b.beliefs.adhesive_issue > 0.4) return 'output_recoverable';
  if (b.beliefs.normal_path > 0.3 || b.beliefs.easy_case > 0.3) return 'output_reusable';
  return 'output_unresolved';
}
