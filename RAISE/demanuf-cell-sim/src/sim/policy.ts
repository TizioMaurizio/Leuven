import type {
  DecisionConfidenceLevel,
  Hypothesis,
  PolicyRecommendation,
  SimulationSnapshot,
  StationId,
  StructuredDecision,
} from './types';
import type { PolicyConfig } from './config';
import { DEFAULT_POLICY_CONFIG } from './config';

// ── Constants ────────────────────────────────────────────────────────

const OUTPUT_BINS: StationId[] = [
  'output_reusable', 'output_recoverable', 'output_hazardous', 'output_unresolved',
];

// ── Belief diagnostics ───────────────────────────────────────────────

export interface BeliefDiagnostics {
  top1: { hypothesis: Hypothesis; probability: number };
  top2: { hypothesis: Hypothesis; probability: number } | null;
  margin: number;
  uncertainty: number;
  hazardPresent: boolean;
  safeSum: number;
}

export function computeBeliefDiagnostics(
  beliefs: Record<Hypothesis, number>,
  uncertainty: number,
): BeliefDiagnostics {
  const sorted = (Object.entries(beliefs) as [Hypothesis, number][])
    .sort((a, b) => b[1] - a[1]);

  const top1 = { hypothesis: sorted[0][0], probability: sorted[0][1] };
  const top2 = sorted.length > 1
    ? { hypothesis: sorted[1][0], probability: sorted[1][1] }
    : null;
  const margin = top2 ? top1.probability - top2.probability : top1.probability;
  const hazardPresent = beliefs.battery_hazard > 0.2;
  const safeSum = beliefs.normal_path + beliefs.easy_case;

  return { top1, top2, margin, uncertainty, hazardPresent, safeSum };
}

// ── Exported API ─────────────────────────────────────────────────────

/**
 * Evaluate the current snapshot and produce a policy recommendation.
 * Uses config-driven guarded decisions with StructuredDecision output.
 */
export function evaluatePolicy(
  snapshot: SimulationSnapshot,
  config: PolicyConfig = DEFAULT_POLICY_CONFIG,
): PolicyRecommendation {
  const b = snapshot.belief.beliefs;
  const unc = snapshot.belief.uncertainty;
  const station = snapshot.currentStation;
  const unscrewAttempts = snapshot.unscrewAttempts;

  const diag = computeBeliefDiagnostics(b, unc);
  const enabledAlts = snapshot.enabledTransitions ?? [];
  const evidenceCount = snapshot.evidenceRequestCount ?? 0;

  // ── a. Output bin reached → complete ───────────────────────────────
  if (OUTPUT_BINS.includes(station)) {
    return pack('complete', station, 'confident', diag, enabledAlts, evidenceCount,
      ['COMPLETED'], 'Item has reached output bin.', 'standard_policy', 'complete');
  }

  // ── b. Hazard guard ────────────────────────────────────────────────
  if (b.battery_hazard > config.hazardGuardThreshold && station !== 'battery_check') {
    return pack('escalate_hazard', 'battery_check', 'confident', diag, enabledAlts, evidenceCount,
      ['HAZARD_GUARD'],
      `Battery hazard belief at ${pct(b.battery_hazard)} exceeds safety threshold (${pct(config.hazardGuardThreshold)}). Routing to battery check.`,
      'escalation', 'reroute_battery');
  }

  // ── c. Evidence seeking ────────────────────────────────────────────
  if (
    config.allowEvidenceSeeking &&
    unc > config.evidenceSeekingUncertaintyThreshold &&
    evidenceCount < config.maxEvidenceRequests
  ) {
    const codes: string[] = ['HIGH_UNCERTAINTY'];
    if (diag.margin < config.minTop2Margin) codes.push('LOW_MARGIN');
    return pack('seek_evidence', null, 'low', diag, enabledAlts, evidenceCount,
      codes,
      `Uncertainty at ${pct(unc)} with margin ${pct(diag.margin)}. Requesting additional evidence (${evidenceCount + 1}/${config.maxEvidenceRequests}).`,
      'evidence_request', 'seek_evidence');
  }

  // ── d. Structural issues after unscrewing failure ──────────────────
  if ((b.hidden_fastener > 0.5 || b.adhesive_issue > 0.5) && unscrewAttempts >= 1) {
    const dominant = b.hidden_fastener > b.adhesive_issue ? 'hidden_fastener' : 'adhesive_issue';
    const val = Math.max(b.hidden_fastener, b.adhesive_issue);
    return pack('escalate_structural', 'manual_escalation', 'confident', diag, enabledAlts, evidenceCount,
      ['STRUCTURAL_ISSUE', 'UNSCREW_FAILURE'],
      `${dominant} belief at ${pct(val)} after ${unscrewAttempts} unscrewing attempt(s). Escalating to operator.`,
      'escalation', 'escalate');
  }

  // ── e. Missing parts → escalate ───────────────────────────────────
  if (b.missing_parts > 0.5) {
    return pack('escalate_uncertainty', 'manual_escalation', 'moderate', diag, enabledAlts, evidenceCount,
      ['MISSING_PARTS'],
      `Missing parts belief at ${pct(b.missing_parts)} — manual verification required.`,
      'escalation', 'escalate');
  }

  // ── f. Confident safe route ────────────────────────────────────────
  if (
    diag.safeSum > config.safeRouteThreshold &&
    diag.top1.probability > config.minTopConfidence &&
    diag.margin > config.minTop2Margin &&
    unc < config.highUncertaintyThreshold
  ) {
    return pack('route_confident', null, 'confident', diag, enabledAlts, evidenceCount,
      ['HIGH_CONFIDENCE', 'SAFE_ROUTE'],
      `Combined normal/easy at ${pct(diag.safeSum)}, top-1 ${pct(diag.top1.probability)}, margin ${pct(diag.margin)}, uncertainty ${pct(unc)}. Confident safe route.`,
      'standard_policy', 'continue');
  }

  // ── g. Moderate safe route ─────────────────────────────────────────
  if (diag.safeSum > config.safeRouteThreshold) {
    const codes: string[] = ['MODERATE_CONFIDENCE', 'SAFE_ROUTE'];
    if (diag.margin <= config.minTop2Margin) codes.push('LOW_MARGIN');
    if (unc >= config.highUncertaintyThreshold) codes.push('HIGH_UNCERTAINTY');
    return pack('route_moderate', null, 'moderate', diag, enabledAlts, evidenceCount,
      codes,
      `Combined normal/easy at ${pct(diag.safeSum)} above safe threshold. Moderate confidence — proceeding.`,
      'standard_policy', 'continue');
  }

  // ── h. Unscrewing failed ≥ maxUnscrewAttempts → escalate ──────────
  if (unscrewAttempts >= config.maxUnscrewAttempts) {
    return pack('escalate_structural', 'manual_escalation', 'moderate', diag, enabledAlts, evidenceCount,
      ['MAX_UNSCREW_ATTEMPTS'],
      `Unscrewing failed ${unscrewAttempts} time(s) (max ${config.maxUnscrewAttempts}). Routing to manual escalation.`,
      'escalation', 'escalate');
  }

  // ── i. Top-1 below abstention threshold → abstain ─────────────────
  if (diag.top1.probability < config.abstentionThreshold) {
    const codes: string[] = ['ABSTENTION'];
    if (unc >= config.highUncertaintyThreshold) codes.push('HIGH_UNCERTAINTY');
    if (diag.margin < config.minTop2Margin) codes.push('LOW_MARGIN');
    return pack('abstain_unresolved', 'output_unresolved', 'abstaining', diag, enabledAlts, evidenceCount,
      codes,
      `Top-1 ${diag.top1.hypothesis} at ${pct(diag.top1.probability)} below abstention threshold (${pct(config.abstentionThreshold)}). Insufficient evidence to route.`,
      'standard_policy', 'abstain');
  }

  // ── j. Default → abstain (never route with low evidence) ──────────
  return pack('abstain_unresolved', 'output_unresolved', 'abstaining', diag, enabledAlts, evidenceCount,
    ['ABSTENTION', 'NO_MATCHING_GUARD'],
    `No decision guard matched. Top-1 ${diag.top1.hypothesis} at ${pct(diag.top1.probability)}, uncertainty ${pct(unc)}. Abstaining.`,
    'standard_policy', 'abstain');
}

/**
 * Choose the next station to transition to, given the full snapshot.
 * Maps policy recommendations to concrete station transitions.
 */
export function chooseTransition(
  snapshot: SimulationSnapshot,
  config: PolicyConfig = DEFAULT_POLICY_CONFIG,
): StationId {
  const rec = evaluatePolicy(snapshot, config);
  const station = snapshot.currentStation;
  const b = snapshot.belief;
  const unscrewAttempts = snapshot.unscrewAttempts;
  const unscrewSucceeded = snapshot.unscrewSucceeded;

  switch (station) {
    case 'input_buffer':
      return 'conveyor';

    case 'conveyor':
      return 'inspection';

    case 'inspection': {
      if (rec.action === 'reroute_battery') return 'battery_check';
      if (rec.action === 'escalate' || rec.action === 'reroute_operator') return 'manual_escalation';
      if (rec.action === 'seek_evidence') return 'inspection';
      if (rec.action === 'abstain') return 'output_unresolved';
      if (rec.action === 'inspect_more' && b.uncertainty > 0.8) return 'manual_escalation';
      return 'unscrewing';
    }

    case 'unscrewing': {
      if (unscrewSucceeded) {
        return selectOutputBin(snapshot, config);
      }
      if (unscrewAttempts >= config.maxUnscrewAttempts) return 'manual_escalation';
      if (rec.action === 'reroute_operator' || rec.action === 'escalate') return 'manual_escalation';
      if (rec.action === 'abstain') return 'manual_escalation';
      if (rec.action === 'seek_evidence') return 'inspection';
      if (unscrewAttempts >= 1 && b.uncertainty > config.highUncertaintyThreshold) return 'manual_escalation';
      return 'unscrewing';
    }

    case 'battery_check': {
      if (b.beliefs.battery_hazard > 0.5) return 'output_hazardous';
      return 'unscrewing';
    }

    case 'manual_escalation':
      return selectOutputBin(snapshot, config);

    default:
      return station;
  }
}

/**
 * Belief-only, config-driven output bin selection.
 */
export function selectOutputBin(
  snapshot: SimulationSnapshot,
  config: PolicyConfig = DEFAULT_POLICY_CONFIG,
): StationId {
  const b = snapshot.belief.beliefs;
  const diag = computeBeliefDiagnostics(b, snapshot.belief.uncertainty);

  if (diag.top1.probability < config.abstentionThreshold) return 'output_unresolved';
  if (b.battery_hazard > 0.5) return 'output_hazardous';
  if (
    b.structural_damage > 0.4 ||
    b.missing_parts > 0.4 ||
    b.hidden_fastener > 0.4 ||
    b.adhesive_issue > 0.4
  ) return 'output_recoverable';
  if (diag.safeSum > config.safeRouteThreshold) return 'output_reusable';
  return 'output_unresolved';
}

// ── Internal helpers ─────────────────────────────────────────────────

function pct(v: number): string {
  return `${(v * 100).toFixed(0)}%`;
}

type LegacyAction = PolicyRecommendation['action'];

function pack(
  decisionType: StructuredDecision['type'],
  selectedRoute: StationId | null,
  confidenceLevel: DecisionConfidenceLevel,
  diag: BeliefDiagnostics,
  enabledAlts: StationId[],
  evidenceCount: number,
  reasonCodes: string[],
  reason: string,
  source: StructuredDecision['source'],
  legacyAction: LegacyAction,
): PolicyRecommendation {
  const decision: StructuredDecision = {
    type: decisionType,
    selectedRoute,
    confidenceLevel,
    topHypothesis: diag.top1,
    top2Hypothesis: diag.top2,
    top2Margin: diag.margin,
    uncertainty: diag.uncertainty,
    hazardPresent: diag.hazardPresent,
    reasonCodes,
    reason,
    enabledAlternatives: enabledAlts,
    source,
    additionalEvidenceAvailable: evidenceCount < 2,
    evidenceRequestCount: evidenceCount,
  };

  return {
    action: legacyAction,
    reason,
    confidence: diag.top1.probability,
    decision,
  };
}
