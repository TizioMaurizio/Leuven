// ── Station identifiers ──────────────────────────────────────────────
export type StationId =
  | 'input_buffer'
  | 'conveyor'
  | 'inspection'
  | 'unscrewing'
  | 'battery_check'
  | 'manual_escalation'
  | 'output_reusable'
  | 'output_recoverable'
  | 'output_hazardous'
  | 'output_unresolved';

// ── Hidden ground-truth conditions ───────────────────────────────────
export type HiddenCondition =
  | 'normal'
  | 'hidden_screws'
  | 'strong_adhesive'
  | 'swollen_battery'
  | 'missing_component'
  | 'casing_damage'
  | 'easy_disassembly';

// ── Resource status ──────────────────────────────────────────────────
export type ResourceStatus = 'idle' | 'busy' | 'blocked' | 'waiting' | 'escalated';

// ── Event types ──────────────────────────────────────────────────────
export type EventType =
  | 'item_arrived'
  | 'transfer_started'
  | 'transfer_completed'
  | 'inspection_started'
  | 'inspection_completed'
  | 'observation_received'
  | 'unscrewing_started'
  | 'unscrewing_attempted'
  | 'unscrewing_succeeded'
  | 'unscrewing_failed'
  | 'hidden_screw_detected'
  | 'adhesive_issue_detected'
  | 'battery_check_started'
  | 'battery_check_completed'
  | 'battery_risk_flagged'
  | 'battery_cleared'
  | 'reroute_to_operator'
  | 'reroute_to_battery_check'
  | 'reroute_to_output'
  | 'escalation_started'
  | 'escalation_completed'
  | 'escalation_resolved'
  | 'item_completed'
  | 'item_binned'
  | 'product_completed';

// ── Observation produced by a station ────────────────────────────────
export interface Observation {
  step: number;
  station: StationId;
  type: string;       // e.g. 'visual_inspection', 'screw_resistance'
  evidence: string;   // human-readable evidence string
  confidence: number; // 0–1
}

// ── Hypothesis labels for belief state ───────────────────────────────
export type Hypothesis =
  | 'normal_path'
  | 'hidden_fastener'
  | 'adhesive_issue'
  | 'battery_hazard'
  | 'missing_parts'
  | 'structural_damage'
  | 'easy_case';

// ── Belief state ─────────────────────────────────────────────────────
export interface BeliefState {
  beliefs: Record<Hypothesis, number>;
  uncertainty: number;               // entropy-based 0–1
  observations: Observation[];
  recommendedAction: PolicyRecommendation;
}

// ── Decision classification ──────────────────────────────────────────
export type DecisionConfidenceLevel = 'confident' | 'moderate' | 'low' | 'abstaining';

export type DecisionType =
  | 'route_confident'       // High confidence in destination
  | 'route_moderate'        // Moderate confidence, proceeding anyway
  | 'abstain_unresolved'    // Insufficient evidence → unresolved
  | 'escalate_uncertainty'  // Too uncertain → operator
  | 'escalate_hazard'       // Hazard guard triggered
  | 'escalate_structural'   // Structural issue suspected
  | 'seek_evidence'         // Requesting additional observation
  | 'retry_operation'       // Retrying a failed operation
  | 'complete';             // Product finished

// ── Structured decision object ───────────────────────────────────────
export interface StructuredDecision {
  type: DecisionType;
  selectedRoute: StationId | null;     // null if seeking evidence
  confidenceLevel: DecisionConfidenceLevel;

  // Numerical evidence summary
  topHypothesis: { hypothesis: Hypothesis; probability: number };
  top2Hypothesis: { hypothesis: Hypothesis; probability: number } | null;
  top2Margin: number;
  uncertainty: number;
  hazardPresent: boolean;

  // Reason codes (machine-readable)
  reasonCodes: string[];

  // Human-readable summary
  reason: string;

  // What alternatives were considered
  enabledAlternatives: StationId[];

  // Decision source
  source: 'standard_policy' | 'escalation' | 'mediation' | 'evidence_request';

  // Whether additional evidence was available but not requested
  additionalEvidenceAvailable: boolean;
  evidenceRequestCount: number;
}

// ── Decision record for containment logging ──────────────────────────
export interface DecisionRecord {
  step: number;
  station: StationId;
  decision: StructuredDecision;
  beliefSnapshot: Record<Hypothesis, number>;
  enabledTransitions: StationId[];
  selected: StationId;
  blocked: StationId[];
}

// ── Per-product trace ────────────────────────────────────────────────
export interface ProductTrace {
  productId: string;
  productNumber: number;
  trueCondition: HiddenCondition;
  startStep: number;
  endStep: number;
  outputBin: StationId;
  decisions: DecisionRecord[];
  beliefEvolution: Array<{ step: number; beliefs: Record<Hypothesis, number>; uncertainty: number }>;
  observations: Observation[];
  evidenceRequests: number;
  escalated: boolean;
  abstained: boolean;
}

// ── Policy recommendation ────────────────────────────────────────────
export interface PolicyRecommendation {
  action: 'continue' | 'inspect_more' | 'reroute_battery' | 'reroute_operator' | 'escalate' | 'abort' | 'complete' | 'seek_evidence' | 'abstain';
  reason: string;
  confidence: number;
  decision?: StructuredDecision;
}

// ── Station state ────────────────────────────────────────────────────
export interface StationState {
  id: StationId;
  label: string;
  status: ResourceStatus;
  processingTimeLeft: number;  // ticks remaining
  itemPresent: boolean;
}

// ── Simulation event (for event log) ─────────────────────────────────
export interface SimEvent {
  step: number;
  type: EventType;
  station: StationId;
  description: string;
  observation?: Observation;
  beliefDelta?: string;
}

// ── Product true state ───────────────────────────────────────────────
export interface ProductTrueState {
  id: string;
  condition: HiddenCondition;
  screwsDifficulty: number;   // 0–1
  adhesiveStrength: number;   // 0–1
  batteryRisk: number;        // 0–1
  missingParts: boolean;
  casingIntegrity: number;    // 0–1
}

// ── Completed product summary ────────────────────────────────────────
export interface CompletedProduct {
  id: string;
  condition: HiddenCondition;
  outputBin: StationId;
  totalSteps: number;
  finalUncertainty: number;
  dominantBelief: { hypothesis: Hypothesis; confidence: number };
  beliefCorrect: boolean;
  escalated: boolean;
  abstained: boolean;
  evidenceRequests: number;
  decisionCount: number;
  routePath: StationId[];
}

// ── Complete simulation snapshot ─────────────────────────────────────
export interface SimulationSnapshot {
  step: number;
  phase: 'idle' | 'running' | 'completed';
  product: ProductTrueState;
  productNumber: number;
  currentStation: StationId;
  stations: Record<StationId, StationState>;
  belief: BeliefState;
  events: SimEvent[];
  enabledTransitions: StationId[];
  lastEvent: SimEvent | null;
  outputBin: StationId | null;
  completedProducts: CompletedProduct[];
  binCounts: Record<string, number>;
  unscrewAttempts: number;
  unscrewSucceeded: boolean;
  currentDecision: StructuredDecision | null;
  decisionHistory: DecisionRecord[];
  productTraces: ProductTrace[];
  evidenceRequestCount: number;
}

// ── Scenario preset ──────────────────────────────────────────────────
export interface Scenario {
  name: string;
  description: string;
  condition: HiddenCondition | 'random';
  overrides?: Partial<ProductTrueState>;
}
