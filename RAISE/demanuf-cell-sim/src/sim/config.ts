// ── Policy configuration ─────────────────────────────────────────────

export interface PolicyConfig {
  name: string;
  description: string;

  // Minimum top-1 confidence to be considered "confident"
  minTopConfidence: number;

  // Minimum margin between top-1 and top-2 to be considered "decisive"
  minTop2Margin: number;

  // Entropy threshold above which we flag "high uncertainty"
  highUncertaintyThreshold: number;

  // Battery hazard guard: if battery_hazard exceeds this, always escalate/reroute
  hazardGuardThreshold: number;

  // Threshold for "safe to route as normal" (combined normal_path + easy_case)
  safeRouteThreshold: number;

  // Low-confidence routing: below this, route to unresolved rather than guessing
  abstentionThreshold: number;

  // Max unscrewing attempts before mandatory escalation
  maxUnscrewAttempts: number;

  // Whether the policy can request extra evidence (secondary inspection etc.)
  allowEvidenceSeeking: boolean;

  // Max additional evidence requests per product
  maxEvidenceRequests: number;

  // Minimum uncertainty to trigger evidence-seeking
  evidenceSeekingUncertaintyThreshold: number;
}

// ── Presets ───────────────────────────────────────────────────────────

export const POLICY_PRESETS: Record<string, PolicyConfig> = {
  baseline: {
    name: 'baseline',
    description: 'Approximate original hardcoded thresholds — permissive routing.',
    minTopConfidence: 0.30,
    minTop2Margin: 0.05,
    highUncertaintyThreshold: 0.70,
    hazardGuardThreshold: 0.40,
    safeRouteThreshold: 0.60,
    abstentionThreshold: 0.15,
    maxUnscrewAttempts: 2,
    allowEvidenceSeeking: false,
    maxEvidenceRequests: 0,
    evidenceSeekingUncertaintyThreshold: 0.70,
  },

  cautious: {
    name: 'cautious',
    description: 'Stricter thresholds — more escalation, less guessing.',
    minTopConfidence: 0.45,
    minTop2Margin: 0.15,
    highUncertaintyThreshold: 0.55,
    hazardGuardThreshold: 0.25,
    safeRouteThreshold: 0.65,
    abstentionThreshold: 0.35,
    maxUnscrewAttempts: 2,
    allowEvidenceSeeking: false,
    maxEvidenceRequests: 0,
    evidenceSeekingUncertaintyThreshold: 0.50,
  },

  abstention_aware: {
    name: 'abstention_aware',
    description: 'Routes to unresolved rather than guessing under low confidence.',
    minTopConfidence: 0.40,
    minTop2Margin: 0.10,
    highUncertaintyThreshold: 0.65,
    hazardGuardThreshold: 0.30,
    safeRouteThreshold: 0.55,
    abstentionThreshold: 0.30,
    maxUnscrewAttempts: 2,
    allowEvidenceSeeking: false,
    maxEvidenceRequests: 0,
    evidenceSeekingUncertaintyThreshold: 0.55,
  },

  evidence_seeking: {
    name: 'evidence_seeking',
    description: 'Actively requests more observations when uncertain.',
    minTopConfidence: 0.40,
    minTop2Margin: 0.10,
    highUncertaintyThreshold: 0.60,
    hazardGuardThreshold: 0.30,
    safeRouteThreshold: 0.55,
    abstentionThreshold: 0.30,
    maxUnscrewAttempts: 2,
    allowEvidenceSeeking: true,
    maxEvidenceRequests: 2,
    evidenceSeekingUncertaintyThreshold: 0.50,
  },
};

export const DEFAULT_POLICY_CONFIG: PolicyConfig = POLICY_PRESETS.abstention_aware;
