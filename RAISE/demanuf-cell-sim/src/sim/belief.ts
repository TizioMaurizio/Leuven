import type {
  BeliefState,
  HiddenCondition,
  Hypothesis,
  Observation,
} from './types';

// ── Constants ────────────────────────────────────────────────────────

const ALL_HYPOTHESES: Hypothesis[] = [
  'normal_path', 'hidden_fastener', 'adhesive_issue',
  'battery_hazard', 'missing_parts', 'structural_damage', 'easy_case',
];

const BELIEF_FLOOR = 0.001;

// ── Likelihood model ─────────────────────────────────────────────────
// P(observation_type | hypothesis).
// Keys are observation type strings; values map each hypothesis to its
// likelihood.  Any hypothesis not listed gets the baseline of 0.15.

type LikelihoodEntry = Partial<Record<Hypothesis, number>>;

const LIKELIHOOD_TABLE: Record<string, LikelihoodEntry> = {
  // ── Inspection / visual observations ─────────────────────────────
  visual_normal: {
    normal_path: 0.75,
    easy_case: 0.70,
    hidden_fastener: 0.15,
    adhesive_issue: 0.15,
    battery_hazard: 0.10,
    missing_parts: 0.12,
    structural_damage: 0.08,
  },
  visual_screw_anomaly: {
    hidden_fastener: 0.80,
    structural_damage: 0.35,
    normal_path: 0.08,
    easy_case: 0.05,
    adhesive_issue: 0.15,
    battery_hazard: 0.10,
    missing_parts: 0.10,
  },
  visual_adhesive: {
    adhesive_issue: 0.82,
    hidden_fastener: 0.20,
    structural_damage: 0.18,
    normal_path: 0.06,
    easy_case: 0.04,
    battery_hazard: 0.08,
    missing_parts: 0.08,
  },
  visual_battery_bulge: {
    battery_hazard: 0.85,
    structural_damage: 0.15,
    normal_path: 0.05,
    easy_case: 0.03,
    hidden_fastener: 0.08,
    adhesive_issue: 0.08,
    missing_parts: 0.06,
  },
  visual_missing: {
    missing_parts: 0.82,
    structural_damage: 0.20,
    normal_path: 0.05,
    easy_case: 0.04,
    hidden_fastener: 0.08,
    adhesive_issue: 0.06,
    battery_hazard: 0.06,
  },
  visual_casing: {
    structural_damage: 0.80,
    missing_parts: 0.18,
    hidden_fastener: 0.15,
    adhesive_issue: 0.12,
    battery_hazard: 0.10,
    normal_path: 0.05,
    easy_case: 0.04,
  },

  // ── Unscrewing observations ──────────────────────────────────────
  screw_high_resistance: {
    hidden_fastener: 0.78,
    adhesive_issue: 0.50,
    structural_damage: 0.25,
    normal_path: 0.08,
    easy_case: 0.04,
    battery_hazard: 0.12,
    missing_parts: 0.10,
  },
  screw_low_resistance: {
    normal_path: 0.72,
    easy_case: 0.80,
    hidden_fastener: 0.06,
    adhesive_issue: 0.08,
    battery_hazard: 0.15,
    missing_parts: 0.15,
    structural_damage: 0.10,
  },
  screw_failure: {
    hidden_fastener: 0.70,
    adhesive_issue: 0.65,
    structural_damage: 0.40,
    normal_path: 0.04,
    easy_case: 0.02,
    battery_hazard: 0.10,
    missing_parts: 0.10,
  },
  screw_stripped: {
    hidden_fastener: 0.72,
    structural_damage: 0.55,
    adhesive_issue: 0.30,
    normal_path: 0.05,
    easy_case: 0.03,
    battery_hazard: 0.10,
    missing_parts: 0.08,
  },
  adhesive_detected: {
    adhesive_issue: 0.92,
    hidden_fastener: 0.20,
    structural_damage: 0.15,
    normal_path: 0.03,
    easy_case: 0.02,
    battery_hazard: 0.06,
    missing_parts: 0.06,
  },

  // ── Battery check observations ───────────────────────────────────
  battery_high_voltage: {
    battery_hazard: 0.88,
    structural_damage: 0.12,
    normal_path: 0.05,
    easy_case: 0.04,
    hidden_fastener: 0.08,
    adhesive_issue: 0.06,
    missing_parts: 0.06,
  },
  battery_normal: {
    normal_path: 0.65,
    easy_case: 0.60,
    battery_hazard: 0.05,
    hidden_fastener: 0.15,
    adhesive_issue: 0.15,
    missing_parts: 0.15,
    structural_damage: 0.12,
  },
  voltage_anomaly: {
    battery_hazard: 0.85,
    structural_damage: 0.15,
    normal_path: 0.05,
    easy_case: 0.04,
    hidden_fastener: 0.08,
    adhesive_issue: 0.06,
    missing_parts: 0.06,
  },
  impedance_normal: {
    normal_path: 0.62,
    easy_case: 0.58,
    battery_hazard: 0.06,
    hidden_fastener: 0.15,
    adhesive_issue: 0.15,
    missing_parts: 0.15,
    structural_damage: 0.12,
  },
  swelling_detected: {
    battery_hazard: 0.95,
    structural_damage: 0.10,
    normal_path: 0.02,
    easy_case: 0.02,
    hidden_fastener: 0.05,
    adhesive_issue: 0.05,
    missing_parts: 0.04,
  },
};

// ── Internal helpers ─────────────────────────────────────────────────

/** Build likelihood vector P(obs | h) for every hypothesis. */
function getObservationLikelihood(obs: Observation): Record<Hypothesis, number> {
  const lk = {} as Record<Hypothesis, number>;
  for (const h of ALL_HYPOTHESES) lk[h] = 0.15;

  // Operator diagnosis: very high-confidence, encodes the true hyp in evidence
  if (obs.type === 'operator_diagnosis') {
    for (const h of ALL_HYPOTHESES) lk[h] = 0.05;
    if (obs.evidence.includes('normal'))     lk.normal_path       = 0.90;
    if (obs.evidence.includes('fastener'))   lk.hidden_fastener   = 0.90;
    if (obs.evidence.includes('adhesive'))   lk.adhesive_issue    = 0.90;
    if (obs.evidence.includes('battery'))    lk.battery_hazard    = 0.90;
    if (obs.evidence.includes('missing'))    lk.missing_parts     = 0.90;
    if (obs.evidence.includes('structural')) lk.structural_damage = 0.90;
    if (obs.evidence.includes('easy'))       lk.easy_case         = 0.90;
    return lk;
  }

  // Standard table lookup, scaled by observation confidence
  const entry = LIKELIHOOD_TABLE[obs.type];
  if (entry) {
    for (const h of ALL_HYPOTHESES) {
      if (h in entry) {
        const tableVal = entry[h]!;
        lk[h] = 0.15 + (tableVal - 0.15) * obs.confidence;
      }
    }
  }

  return lk;
}

/** Normalize beliefs to sum-to-1 with floor enforcement. */
function normalizeBelief(beliefs: Record<Hypothesis, number>): Record<Hypothesis, number> {
  for (const h of ALL_HYPOTHESES) {
    if (beliefs[h] < BELIEF_FLOOR) beliefs[h] = BELIEF_FLOOR;
  }
  let total = 0;
  for (const h of ALL_HYPOTHESES) total += beliefs[h];
  for (const h of ALL_HYPOTHESES) beliefs[h] /= total;
  return beliefs;
}

// ── Exported API ─────────────────────────────────────────────────────

/** Create initial belief state — uniform with a slight bias toward normal. */
export function createInitialBelief(): BeliefState {
  const n = ALL_HYPOTHESES.length;
  const beliefs = {} as Record<Hypothesis, number>;
  for (const h of ALL_HYPOTHESES) beliefs[h] = 1 / n;
  beliefs.normal_path += 0.04;
  beliefs.easy_case   += 0.02;
  normalizeBelief(beliefs);

  return {
    beliefs,
    uncertainty: computeUncertainty(beliefs),
    observations: [],
    recommendedAction: { action: 'continue', reason: 'Starting — no observations yet', confidence: 0 },
  };
}

/**
 * Bayesian belief update: P(h | obs) ∝ P(obs | h) · P(h).
 *
 * 1. Compute likelihood of the observation under each hypothesis.
 * 2. Multiply prior by likelihood.
 * 3. Normalize (with floor).
 * 4. Recompute entropy-based uncertainty.
 */
export function updateBelief(prior: BeliefState, obs: Observation): BeliefState {
  const lk = getObservationLikelihood(obs);
  const posterior = {} as Record<Hypothesis, number>;

  for (const h of ALL_HYPOTHESES) {
    posterior[h] = prior.beliefs[h] * lk[h];
  }
  normalizeBelief(posterior);

  return {
    beliefs: posterior,
    uncertainty: computeUncertainty(posterior),
    observations: [...prior.observations, obs],
    recommendedAction: prior.recommendedAction, // overwritten by policy later
  };
}

/** Shannon entropy normalized to [0, 1].  0 = certain, 1 = uniform. */
export function computeUncertainty(beliefs: Record<Hypothesis, number>): number {
  let h = 0;
  for (const p of Object.values(beliefs)) {
    if (p > 0) h -= p * Math.log2(p);
  }
  const maxH = Math.log2(ALL_HYPOTHESES.length);
  return maxH > 0 ? h / maxH : 0;
}

/** Map a ground-truth HiddenCondition to the corresponding Hypothesis. */
export function conditionToHypothesis(condition: HiddenCondition): Hypothesis {
  const map: Record<HiddenCondition, Hypothesis> = {
    normal:            'normal_path',
    hidden_screws:     'hidden_fastener',
    strong_adhesive:   'adhesive_issue',
    swollen_battery:   'battery_hazard',
    missing_component: 'missing_parts',
    casing_damage:     'structural_damage',
    easy_disassembly:  'easy_case',
  };
  return map[condition];
}

/** Return the hypothesis with the highest belief and its value. */
export function getDominantHypothesis(
  beliefs: Record<Hypothesis, number>,
): { hypothesis: Hypothesis; confidence: number } {
  let best: Hypothesis = 'normal_path';
  let bestVal = -1;
  for (const h of ALL_HYPOTHESES) {
    if (beliefs[h] > bestVal) {
      bestVal = beliefs[h];
      best = h;
    }
  }
  return { hypothesis: best, confidence: bestVal };
}

/** Human-readable summary of belief changes (only deltas > 1%). */
export function summarizeBeliefDelta(
  before: Record<Hypothesis, number>,
  after: Record<Hypothesis, number>,
): string {
  const changes: string[] = [];
  for (const h of ALL_HYPOTHESES) {
    const delta = after[h] - before[h];
    if (Math.abs(delta) > 0.01) {
      const sign = delta > 0 ? '+' : '';
      changes.push(`${h}: ${sign}${(delta * 100).toFixed(1)}%`);
    }
  }
  return changes.length === 0 ? 'Beliefs unchanged' : changes.join(', ');
}
