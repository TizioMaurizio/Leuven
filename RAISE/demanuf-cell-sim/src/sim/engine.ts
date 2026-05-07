import { createRNG, pickWeighted } from './random';
import { createInitialBelief, updateBelief, conditionToHypothesis, getDominantHypothesis } from './belief';
import { evaluatePolicy, selectOutputBin } from './policy';
import { PolicyConfig, DEFAULT_POLICY_CONFIG } from './config';
import type {
  BeliefState,
  CompletedProduct,
  DecisionRecord,
  EventType,
  HiddenCondition,
  Hypothesis,
  Observation,
  PolicyRecommendation,
  ProductTrace,
  ProductTrueState,
  Scenario,
  SimEvent,
  SimulationSnapshot,
  StationId,
  StationState,
} from './types';

// ── Constants ────────────────────────────────────────────────────────

const STATION_LABELS: Record<StationId, string> = {
  input_buffer: 'Input Buffer',
  conveyor: 'Conveyor',
  inspection: 'Inspection',
  unscrewing: 'Unscrewing',
  battery_check: 'Battery Check',
  manual_escalation: 'Manual Escalation',
  output_reusable: 'Output – Reusable',
  output_recoverable: 'Output – Recoverable',
  output_hazardous: 'Output – Hazardous',
  output_unresolved: 'Output – Unresolved',
};

const PROCESSING_TICKS: Record<StationId, number> = {
  input_buffer: 1,
  conveyor: 2,
  inspection: 3,
  unscrewing: 4,
  battery_check: 3,
  manual_escalation: 5,
  output_reusable: 1,
  output_recoverable: 1,
  output_hazardous: 1,
  output_unresolved: 1,
};

const OUTPUT_BINS: StationId[] = [
  'output_reusable', 'output_recoverable', 'output_hazardous', 'output_unresolved',
];

const ALL_CONDITIONS: HiddenCondition[] = [
  'normal', 'hidden_screws', 'strong_adhesive', 'swollen_battery',
  'missing_component', 'casing_damage', 'easy_disassembly',
];

// ── Policy bridge ────────────────────────────────────────────────────
// The engine builds a lightweight snapshot for the policy module.

function selectPolicy(
  belief: BeliefState,
  currentStation: StationId,
  ctx: PolicyContext,
  config: PolicyConfig,
): PolicyRecommendation {
  // Build a minimal snapshot the policy can evaluate.
  // The engine calls this before a full snapshot is available,
  // so we synthesize the fields the policy inspects.
  const minSnap = {
    step: 0,
    phase: 'running' as const,
    product: { batteryRisk: 0, casingIntegrity: 0.9 } as any,
    currentStation,
    stations: {} as any,
    belief,
    events: ctx._events ?? [],
    enabledTransitions: [],
    lastEvent: null,
    outputBin: null,
    productNumber: 1,
    completedProducts: [],
    binCounts: {},
    unscrewAttempts: ctx.unscrewAttempts,
    unscrewSucceeded: ctx.unscrewSucceeded,
    currentDecision: null,
    decisionHistory: [],
    productTraces: [],
    evidenceRequestCount: ctx.evidenceRequestCount ?? 0,
  };
  return evaluatePolicy(minSnap, config);
}

interface PolicyContext {
  unscrewAttempts: number;
  unscrewSucceeded: boolean;
  evidenceRequestCount?: number;
  _events?: SimEvent[];
}

// ── Product generation ───────────────────────────────────────────────

function sampleCondition(rng: () => number): HiddenCondition {
  return pickWeighted(rng, ALL_CONDITIONS, [0.30, 0.15, 0.12, 0.13, 0.10, 0.10, 0.10]);
}

function generateProduct(rng: () => number, scenario: Scenario): ProductTrueState {
  const condition: HiddenCondition = scenario.condition === 'random'
    ? sampleCondition(rng)
    : scenario.condition;

  const base: ProductTrueState = {
    id: `PROD-${Math.floor(rng() * 90000) + 10000}`,
    condition,
    screwsDifficulty: 0.2,
    adhesiveStrength: 0.2,
    batteryRisk: 0.1,
    missingParts: false,
    casingIntegrity: 0.9,
  };

  // Set properties coherent with condition
  switch (condition) {
    case 'normal':
      base.screwsDifficulty = 0.15 + rng() * 0.15;
      base.adhesiveStrength = 0.1 + rng() * 0.15;
      base.batteryRisk = rng() * 0.15;
      base.casingIntegrity = 0.85 + rng() * 0.15;
      break;
    case 'hidden_screws':
      base.screwsDifficulty = 0.7 + rng() * 0.25;
      base.adhesiveStrength = 0.2 + rng() * 0.2;
      base.batteryRisk = rng() * 0.2;
      base.casingIntegrity = 0.7 + rng() * 0.2;
      break;
    case 'strong_adhesive':
      base.screwsDifficulty = 0.3 + rng() * 0.2;
      base.adhesiveStrength = 0.75 + rng() * 0.2;
      base.batteryRisk = rng() * 0.2;
      base.casingIntegrity = 0.6 + rng() * 0.25;
      break;
    case 'swollen_battery':
      base.screwsDifficulty = 0.2 + rng() * 0.2;
      base.adhesiveStrength = 0.15 + rng() * 0.15;
      base.batteryRisk = 0.7 + rng() * 0.25;
      base.casingIntegrity = 0.5 + rng() * 0.3;
      break;
    case 'missing_component':
      base.screwsDifficulty = 0.2 + rng() * 0.15;
      base.adhesiveStrength = 0.1 + rng() * 0.15;
      base.batteryRisk = rng() * 0.2;
      base.missingParts = true;
      base.casingIntegrity = 0.6 + rng() * 0.2;
      break;
    case 'casing_damage':
      base.screwsDifficulty = 0.3 + rng() * 0.3;
      base.adhesiveStrength = 0.3 + rng() * 0.3;
      base.batteryRisk = 0.1 + rng() * 0.2;
      base.casingIntegrity = 0.15 + rng() * 0.25;
      break;
    case 'easy_disassembly':
      base.screwsDifficulty = rng() * 0.1;
      base.adhesiveStrength = rng() * 0.1;
      base.batteryRisk = rng() * 0.1;
      base.casingIntegrity = 0.9 + rng() * 0.1;
      break;
  }

  // Apply scenario overrides
  if (scenario.overrides) {
    Object.assign(base, scenario.overrides);
  }
  return base;
}

// ── Station factory ──────────────────────────────────────────────────

function makeStations(): Record<StationId, StationState> {
  const ids: StationId[] = [
    'input_buffer', 'conveyor', 'inspection', 'unscrewing',
    'battery_check', 'manual_escalation',
    'output_reusable', 'output_recoverable', 'output_hazardous', 'output_unresolved',
  ];
  const result = {} as Record<StationId, StationState>;
  for (const id of ids) {
    result[id] = {
      id,
      label: STATION_LABELS[id],
      status: 'idle',
      processingTimeLeft: 0,
      itemPresent: false,
    };
  }
  return result;
}

// ── Observation generation ───────────────────────────────────────────

function generateInspectionObservations(
  rng: () => number,
  product: ProductTrueState,
  step: number,
): Observation[] {
  const obs: Observation[] = [];
  const c = product.condition;

  // Primary observation based on true condition
  const primaryConf = 0.5 + rng() * 0.3;

  switch (c) {
    case 'normal':
      obs.push({ step, station: 'inspection', type: 'visual_normal', evidence: 'Visual scan shows normal wear patterns, no anomalies detected', confidence: primaryConf });
      break;
    case 'hidden_screws':
      if (rng() < 0.70) {
        obs.push({ step, station: 'inspection', type: 'visual_screw_anomaly', evidence: 'Unusual screw pattern detected — possible concealed fasteners under label', confidence: primaryConf });
      } else {
        obs.push({ step, station: 'inspection', type: 'visual_normal', evidence: 'Visual scan shows standard screw layout', confidence: primaryConf * 0.7 });
      }
      break;
    case 'strong_adhesive':
      if (rng() < 0.55) {
        obs.push({ step, station: 'inspection', type: 'visual_adhesive', evidence: 'Adhesive residue visible on seam edges, may resist separation', confidence: primaryConf });
      } else {
        obs.push({ step, station: 'inspection', type: 'visual_normal', evidence: 'Case seam appears standard', confidence: primaryConf * 0.6 });
      }
      break;
    case 'swollen_battery':
      if (rng() < 0.60) {
        obs.push({ step, station: 'inspection', type: 'visual_battery_bulge', evidence: 'Battery casing shows slight deformation, potential swelling', confidence: primaryConf });
      } else {
        obs.push({ step, station: 'inspection', type: 'visual_normal', evidence: 'External casing within tolerance', confidence: primaryConf * 0.5 });
      }
      break;
    case 'missing_component':
      if (rng() < 0.65) {
        obs.push({ step, station: 'inspection', type: 'visual_missing', evidence: 'Weight check indicates lower-than-expected mass, possible missing internal module', confidence: primaryConf });
      } else {
        obs.push({ step, station: 'inspection', type: 'visual_normal', evidence: 'External dimensions nominal', confidence: primaryConf * 0.6 });
      }
      break;
    case 'casing_damage':
      if (rng() < 0.75) {
        obs.push({ step, station: 'inspection', type: 'visual_casing', evidence: 'Visible micro-cracks on casing corner, structural compromise likely', confidence: primaryConf });
      } else {
        obs.push({ step, station: 'inspection', type: 'visual_normal', evidence: 'Casing appears intact on cursory check', confidence: primaryConf * 0.5 });
      }
      break;
    case 'easy_disassembly':
      obs.push({ step, station: 'inspection', type: 'visual_normal', evidence: 'Product Design-for-Disassembly markers present, easy teardown expected', confidence: primaryConf + 0.15 });
      break;
  }

  // Secondary observation (generated ~50% of the time, noisier)
  if (rng() < 0.5) {
    const secondaryConf = 0.3 + rng() * 0.2;
    if (product.batteryRisk > 0.5 && rng() < 0.5) {
      obs.push({ step, station: 'inspection', type: 'visual_battery_bulge', evidence: 'Thermal camera shows slight hotspot near battery region', confidence: secondaryConf });
    } else if (product.casingIntegrity < 0.5 && rng() < 0.5) {
      obs.push({ step, station: 'inspection', type: 'visual_casing', evidence: 'UV scan reveals hairline fractures on back panel', confidence: secondaryConf });
    } else {
      obs.push({ step, station: 'inspection', type: 'visual_normal', evidence: 'Secondary scan nominal', confidence: secondaryConf });
    }
  }

  return obs;
}

function generateUnscrewingObservation(
  rng: () => number,
  product: ProductTrueState,
  step: number,
  succeeded: boolean,
): Observation {
  const conf = 0.6 + rng() * 0.3;
  if (succeeded) {
    if (product.screwsDifficulty < 0.3) {
      return { step, station: 'unscrewing', type: 'screw_low_resistance', evidence: 'All fasteners removed with minimal torque', confidence: conf };
    }
    return { step, station: 'unscrewing', type: 'screw_low_resistance', evidence: 'Fasteners removed, moderate resistance encountered', confidence: conf * 0.8 };
  }
  if (product.condition === 'hidden_screws') {
    return { step, station: 'unscrewing', type: 'screw_high_resistance', evidence: 'Torque limit exceeded — hidden or non-standard fastener suspected', confidence: conf };
  }
  if (product.condition === 'strong_adhesive') {
    return { step, station: 'unscrewing', type: 'screw_failure', evidence: 'Fastener unseated but panel held by adhesive bond', confidence: conf };
  }
  return { step, station: 'unscrewing', type: 'screw_high_resistance', evidence: 'Unexpected resistance during unscrewing, cause unclear', confidence: conf * 0.7 };
}

function generateBatteryObservation(
  rng: () => number,
  product: ProductTrueState,
  step: number,
): Observation {
  const conf = 0.7 + rng() * 0.2;
  if (product.batteryRisk > 0.5) {
    return { step, station: 'battery_check', type: 'battery_high_voltage', evidence: 'Impedance test flagged — elevated internal resistance and voltage sag pattern', confidence: conf };
  }
  return { step, station: 'battery_check', type: 'battery_normal', evidence: 'Battery impedance and voltage within safe operating range', confidence: conf };
}

function generateEscalationObservation(
  _rng: () => number,
  product: ProductTrueState,
  step: number,
): Observation {
  const evidenceMap: Record<HiddenCondition, string> = {
    normal: 'Operator diagnosis: normal product, no defects found (normal path confirmed)',
    hidden_screws: 'Operator diagnosis: concealed fastener found under warranty sticker (hidden fastener confirmed)',
    strong_adhesive: 'Operator diagnosis: industrial adhesive bonding panel edges (adhesive issue confirmed)',
    swollen_battery: 'Operator diagnosis: battery pack swollen, safety protocol required (battery hazard confirmed)',
    missing_component: 'Operator diagnosis: internal RF module absent (missing parts confirmed)',
    casing_damage: 'Operator diagnosis: load-bearing frame cracked (structural damage confirmed)',
    easy_disassembly: 'Operator diagnosis: standard easy-release product (easy case confirmed)',
  };
  return {
    step,
    station: 'manual_escalation',
    type: 'operator_diagnosis',
    evidence: evidenceMap[product.condition],
    confidence: 0.92 + Math.random() * 0.05, // very high
  };
}

// ── Unscrewing success probability ───────────────────────────────────

function unscrewSuccessProbability(product: ProductTrueState): number {
  switch (product.condition) {
    case 'easy_disassembly': return 0.99;
    case 'normal':           return 0.95;
    case 'missing_component':return 0.90;
    case 'swollen_battery':  return 0.80;
    case 'casing_damage':    return 0.60;
    case 'hidden_screws':    return 0.40;
    case 'strong_adhesive':  return 0.30;
    default:                 return 0.50;
  }
}

// ── Routing logic ────────────────────────────────────────────────────

// ── Deep copy helper ─────────────────────────────────────────────────

function deepCopy<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj));
}

// ── Enabled transitions calculators ──────────────────────────────────

function computeEnabled(station: StationId, belief: BeliefState, ctx: PolicyContext): StationId[] {
  switch (station) {
    case 'input_buffer':    return ['conveyor'];
    case 'conveyor':        return ['inspection'];
    case 'inspection': {
      const targets: StationId[] = ['unscrewing'];
      if (belief.beliefs.battery_hazard > 0.3) targets.push('battery_check');
      if (belief.uncertainty > 0.8) targets.push('manual_escalation');
      targets.push('inspection'); // re-inspection for evidence seeking
      targets.push('output_unresolved'); // abstention routing
      return targets;
    }
    case 'unscrewing': {
      if (ctx.unscrewAttempts >= 2) return ['manual_escalation'];
      const targets: StationId[] = ['output_reusable', 'output_recoverable', 'output_hazardous', 'output_unresolved'];
      targets.push('unscrewing');     // retry on failure
      targets.push('inspection');      // evidence seeking on failure
      if (ctx.unscrewAttempts >= 1) targets.push('manual_escalation');
      return targets;
    }
    case 'battery_check':   return ['unscrewing', 'output_hazardous'];
    case 'manual_escalation': return ['output_reusable', 'output_recoverable', 'output_hazardous', 'output_unresolved'];
    default:                return [];
  }
}

// ══════════════════════════════════════════════════════════════════════
//  SimEngine
// ══════════════════════════════════════════════════════════════════════

export class SimEngine {
  private snapshot: SimulationSnapshot;
  private rng: () => number;
  private config: PolicyConfig;
  private unscrewAttempts = 0;
  private unscrewSucceeded = false;
  private inspectionDone = false;
  private pendingObservations: Observation[] = [];
  private awaitingNextProduct = false;
  private maxProducts = Infinity;
  private scenario: Scenario;
  private productStartStep = 0;

  // Per-product tracking
  private routePath: StationId[] = [];
  private escalated = false;
  private evidenceRequestCount = 0;
  private beliefHistory: Array<{ step: number; beliefs: Record<Hypothesis, number>; uncertainty: number }> = [];

  constructor(seed: number, scenario: Scenario, config?: PolicyConfig) {
    this.rng = createRNG(seed);
    this.scenario = scenario;
    this.config = config ?? DEFAULT_POLICY_CONFIG;
    this.snapshot = this.buildInitialSnapshot(scenario);
  }

  setMaxProducts(n: number): void {
    this.maxProducts = n;
  }

  setConfig(config: PolicyConfig): void {
    this.config = config;
  }

  // ── Public API ────────────────────────────────────────────────────

  getSnapshot(): SimulationSnapshot {
    return deepCopy(this.snapshot);
  }

  isComplete(): boolean {
    return this.snapshot.phase === 'completed';
  }

  reset(seed: number, scenario: Scenario, config?: PolicyConfig): void {
    this.rng = createRNG(seed);
    this.scenario = scenario;
    if (config) this.config = config;
    this.unscrewAttempts = 0;
    this.unscrewSucceeded = false;
    this.inspectionDone = false;
    this.pendingObservations = [];
    this.awaitingNextProduct = false;
    this.maxProducts = Infinity;
    this.productStartStep = 0;
    this.routePath = [];
    this.escalated = false;
    this.evidenceRequestCount = 0;
    this.beliefHistory = [];
    this.snapshot = this.buildInitialSnapshot(scenario);
  }

  step(): SimulationSnapshot {
    if (this.snapshot.phase === 'completed') return this.getSnapshot();

    if (this.awaitingNextProduct) {
      this.awaitingNextProduct = false;
      return this.spawnNextProduct();
    }

    const s = this.snapshot;
    s.step += 1;

    const cur = s.stations[s.currentStation];

    // ── Phase 1: If station is still processing, tick down ────────
    if (cur.status === 'busy' && cur.processingTimeLeft > 1) {
      cur.processingTimeLeft -= 1;
      // Emit mid-processing events like observations
      if (this.pendingObservations.length > 0) {
        const obs = this.pendingObservations.shift()!;
        s.belief = updateBelief(s.belief, obs);
        this.recordBeliefSnapshot(s);
        const evt = this.makeEvent(s.step, 'observation_received', s.currentStation,
          `Observation at ${STATION_LABELS[s.currentStation]}: ${obs.evidence}`, obs);
        s.events.push(evt);
        s.lastEvent = evt;
        s.belief.recommendedAction = selectPolicy(s.belief, s.currentStation, this.policyCtx(), this.config);
        s.enabledTransitions = computeEnabled(s.currentStation, s.belief, this.policyCtx());
        return this.getSnapshot();
      }
      // No observation to emit — just a processing tick
      const evt = this.makeEvent(s.step, this.processingEventType(s.currentStation), s.currentStation,
        `${STATION_LABELS[s.currentStation]} processing… (${cur.processingTimeLeft} ticks left)`);
      s.events.push(evt);
      s.lastEvent = evt;
      return this.getSnapshot();
    }

    // ── Phase 2: Processing complete — resolve station logic ──────
    if (cur.status === 'busy' && cur.processingTimeLeft <= 1) {
      cur.processingTimeLeft = 0;
      cur.status = 'idle';
      cur.itemPresent = false;

      // Drain any remaining pending observations
      if (this.pendingObservations.length > 0) {
        const obs = this.pendingObservations.shift()!;
        s.belief = updateBelief(s.belief, obs);
        this.recordBeliefSnapshot(s);
      }

      // Station-specific completion logic
      const next = this.resolveStationCompletion(s);
      return this.transitionTo(next);
    }

    // ── Phase 3: Station is idle / item just arrived — start ──────
    if (cur.status === 'idle' && s.phase === 'running') {
      return this.beginStationProcessing();
    }

    return this.getSnapshot();
  }

  // ── Internal ──────────────────────────────────────────────────────

  private policyCtx(): PolicyContext {
    return {
      unscrewAttempts: this.unscrewAttempts,
      unscrewSucceeded: this.unscrewSucceeded,
      evidenceRequestCount: this.evidenceRequestCount,
      _events: this.snapshot?.events ?? [],
    };
  }

  private recordBeliefSnapshot(s: SimulationSnapshot): void {
    this.beliefHistory.push({
      step: s.step,
      beliefs: { ...s.belief.beliefs },
      uncertainty: s.belief.uncertainty,
    });
  }

  private buildMinimalSnapshot(s: SimulationSnapshot): SimulationSnapshot {
    return {
      step: s.step,
      phase: s.phase,
      product: s.product,
      currentStation: s.currentStation,
      stations: s.stations,
      belief: s.belief,
      events: s.events,
      enabledTransitions: s.enabledTransitions,
      lastEvent: s.lastEvent,
      outputBin: s.outputBin,
      productNumber: s.productNumber,
      completedProducts: s.completedProducts,
      binCounts: s.binCounts,
      unscrewAttempts: s.unscrewAttempts,
      unscrewSucceeded: s.unscrewSucceeded,
      currentDecision: s.currentDecision,
      decisionHistory: s.decisionHistory,
      productTraces: s.productTraces,
      evidenceRequestCount: s.evidenceRequestCount,
    };
  }

  private recordDecision(
    s: SimulationSnapshot,
    station: StationId,
    rec: PolicyRecommendation,
    nextStation: StationId,
  ): void {
    const enabled = computeEnabled(station, s.belief, this.policyCtx());
    const blocked = enabled.filter(t => t !== nextStation);
    const dominant = getDominantHypothesis(s.belief.beliefs);
    const decision = rec.decision ?? {
      type: 'route_moderate' as const,
      selectedRoute: nextStation,
      confidenceLevel: 'moderate' as const,
      topHypothesis: { hypothesis: dominant.hypothesis, probability: dominant.confidence },
      top2Hypothesis: null,
      top2Margin: 0,
      uncertainty: s.belief.uncertainty,
      hazardPresent: s.belief.beliefs.battery_hazard > 0.2,
      reasonCodes: [],
      reason: rec.reason,
      enabledAlternatives: enabled,
      source: 'standard_policy' as const,
      additionalEvidenceAvailable: false,
      evidenceRequestCount: this.evidenceRequestCount,
    };
    const decisionRecord: DecisionRecord = {
      step: s.step,
      station,
      decision,
      beliefSnapshot: { ...s.belief.beliefs },
      enabledTransitions: enabled,
      selected: nextStation,
      blocked,
    };
    s.decisionHistory.push(decisionRecord);
    s.currentDecision = decision;
  }

  private archiveCurrentProduct(outputBin: StationId): void {
    const s = this.snapshot;
    const dominant = getDominantHypothesis(s.belief.beliefs);
    const trueHyp = conditionToHypothesis(s.product.condition);
    const completed: CompletedProduct = {
      id: s.product.id,
      condition: s.product.condition,
      outputBin,
      totalSteps: s.step - this.productStartStep,
      finalUncertainty: s.belief.uncertainty,
      dominantBelief: dominant,
      beliefCorrect: dominant.hypothesis === trueHyp,
      escalated: this.escalated,
      abstained: s.currentDecision?.type === 'abstain_unresolved',
      evidenceRequests: this.evidenceRequestCount,
      decisionCount: s.decisionHistory.length,
      routePath: [...this.routePath],
    };
    s.completedProducts.push(completed);
    s.binCounts[outputBin] = (s.binCounts[outputBin] ?? 0) + 1;
  }

  private buildProductTrace(s: SimulationSnapshot): ProductTrace {
    return {
      productId: s.product.id,
      productNumber: s.productNumber,
      trueCondition: s.product.condition,
      startStep: this.productStartStep,
      endStep: s.step,
      outputBin: s.outputBin!,
      decisions: [...s.decisionHistory],
      beliefEvolution: [...this.beliefHistory],
      observations: [...s.belief.observations],
      evidenceRequests: this.evidenceRequestCount,
      escalated: this.escalated,
      abstained: s.currentDecision?.type === 'abstain_unresolved',
    };
  }

  private spawnNextProduct(): SimulationSnapshot {
    const s = this.snapshot;

    // Archive the current product
    this.archiveCurrentProduct(s.outputBin!);

    // Build and store the product trace
    s.productTraces.push(this.buildProductTrace(s));

    // Emit product_completed summary event
    const summaryEvt = this.makeEvent(s.step, 'product_completed', s.outputBin!,
      `Product #${s.productNumber} (${s.product.id}) completed \u2014 ${s.completedProducts.length} products processed so far`);
    s.events.push(summaryEvt);

    // Reset per-product state
    this.unscrewAttempts = 0;
    this.unscrewSucceeded = false;
    this.inspectionDone = false;
    this.pendingObservations = [];
    this.routePath = [];
    this.escalated = false;
    this.evidenceRequestCount = 0;
    this.beliefHistory = [];
    s.unscrewAttempts = 0;
    s.unscrewSucceeded = false;
    s.evidenceRequestCount = 0;
    s.decisionHistory = [];
    s.currentDecision = null;

    // Generate new product (RNG continues, no reseed)
    const newProduct = generateProduct(this.rng, this.scenario);
    s.product = newProduct;
    s.productNumber += 1;
    this.productStartStep = s.step;

    // Reset belief
    const belief = createInitialBelief();
    const initCtx: PolicyContext = { unscrewAttempts: 0, unscrewSucceeded: false, evidenceRequestCount: 0, _events: s.events };
    belief.recommendedAction = selectPolicy(belief, 'input_buffer', initCtx, this.config);
    s.belief = belief;

    // Record initial belief snapshot
    this.recordBeliefSnapshot(s);

    // Reset station states (all idle, no items)
    const stations = makeStations();
    stations.input_buffer.itemPresent = true;
    stations.input_buffer.status = 'idle';
    s.stations = stations;

    // Place product at input buffer
    s.currentStation = 'input_buffer';
    s.outputBin = null;
    s.phase = 'running';
    s.enabledTransitions = ['conveyor'];

    // Emit arrival event for new product
    const arrivalEvt = this.makeEvent(s.step, 'item_arrived', 'input_buffer',
      `Product ${newProduct.id} (#${s.productNumber}) arrived at Input Buffer`);
    s.events.push(arrivalEvt);
    s.lastEvent = arrivalEvt;

    return this.getSnapshot();
  }

  private buildInitialSnapshot(scenario: Scenario): SimulationSnapshot {
    const product = generateProduct(this.rng, scenario);
    const stations = makeStations();
    stations.input_buffer.itemPresent = true;
    stations.input_buffer.status = 'idle';

    const belief = createInitialBelief();
    const initCtx: PolicyContext = { unscrewAttempts: 0, unscrewSucceeded: false, evidenceRequestCount: 0, _events: [] };
    belief.recommendedAction = selectPolicy(belief, 'input_buffer', initCtx, this.config);

    const arrivalEvent: SimEvent = {
      step: 0,
      type: 'item_arrived',
      station: 'input_buffer',
      description: `Product ${product.id} arrived at Input Buffer`,
    };

    // Record initial belief
    this.beliefHistory = [{
      step: 0,
      beliefs: { ...belief.beliefs },
      uncertainty: belief.uncertainty,
    }];

    return {
      step: 0,
      phase: 'running',
      product,
      productNumber: 1,
      currentStation: 'input_buffer',
      stations,
      belief,
      events: [arrivalEvent],
      enabledTransitions: ['conveyor'],
      lastEvent: arrivalEvent,
      outputBin: null,
      completedProducts: [],
      binCounts: {},
      unscrewAttempts: 0,
      unscrewSucceeded: false,
      currentDecision: null,
      decisionHistory: [],
      productTraces: [],
      evidenceRequestCount: 0,
    };
  }

  private beginStationProcessing(): SimulationSnapshot {
    const s = this.snapshot;
    const station = s.currentStation;
    const st = s.stations[station];

    st.status = 'busy';
    st.itemPresent = true;
    st.processingTimeLeft = PROCESSING_TICKS[station];

    // Track route path
    this.routePath.push(station);

    // Queue observations for certain stations
    if (station === 'inspection' && !this.inspectionDone) {
      this.pendingObservations = generateInspectionObservations(this.rng, s.product, s.step);
      this.inspectionDone = true;
    } else if (station === 'inspection' && this.inspectionDone) {
      // Re-inspection generates one more observation
      const conf = 0.4 + this.rng() * 0.3;
      this.pendingObservations = [{
        step: s.step,
        station: 'inspection',
        type: 'visual_normal',
        evidence: 'Re-inspection scan: features consistent with prior observations',
        confidence: conf,
      }];
    }

    if (station === 'battery_check') {
      this.pendingObservations = [generateBatteryObservation(this.rng, s.product, s.step)];
    }

    if (station === 'manual_escalation') {
      this.pendingObservations = [generateEscalationObservation(this.rng, s.product, s.step)];
    }

    const evtType = this.startedEventType(station);
    const evt = this.makeEvent(s.step, evtType, station,
      `${STATION_LABELS[station]} started processing product ${s.product.id}`);
    s.events.push(evt);
    s.lastEvent = evt;

    s.belief.recommendedAction = selectPolicy(s.belief, station, this.policyCtx(), this.config);
    s.enabledTransitions = computeEnabled(station, s.belief, this.policyCtx());

    return this.getSnapshot();
  }

  private resolveStationCompletion(s: SimulationSnapshot): StationId {
    const station = s.currentStation;

    switch (station) {
      case 'input_buffer':
        return 'conveyor';

      case 'conveyor':
        return 'inspection';

      case 'inspection': {
        const rec = selectPolicy(s.belief, station, this.policyCtx(), this.config);
        s.belief.recommendedAction = rec;

        // Handle seek_evidence: re-route to inspection for additional observation
        if (
          rec.action === 'seek_evidence' &&
          this.evidenceRequestCount < this.config.maxEvidenceRequests
        ) {
          this.evidenceRequestCount += 1;
          s.evidenceRequestCount = this.evidenceRequestCount;
          this.recordDecision(s, station, rec, 'inspection');
          return 'inspection';
        }

        let nextInsp: StationId;
        if (rec.action === 'reroute_battery') {
          nextInsp = 'battery_check';
        } else if (rec.action === 'escalate' || rec.action === 'reroute_operator') {
          nextInsp = 'manual_escalation';
          this.escalated = true;
        } else if (rec.action === 'abstain') {
          nextInsp = 'output_unresolved';
        } else {
          nextInsp = 'unscrewing';
        }
        this.recordDecision(s, station, rec, nextInsp);
        return nextInsp;
      }

      case 'unscrewing': {
        const prob = unscrewSuccessProbability(s.product);
        const succeeded = this.rng() < prob;
        this.unscrewAttempts += 1;
        s.unscrewAttempts = this.unscrewAttempts;

        const obs = generateUnscrewingObservation(this.rng, s.product, s.step, succeeded);
        s.belief = updateBelief(s.belief, obs);
        this.recordBeliefSnapshot(s);

        if (succeeded) {
          this.unscrewSucceeded = true;
          s.unscrewSucceeded = true;
          const compEvt: EventType = 'unscrewing_succeeded';
          const evt = this.makeEvent(s.step, compEvt, station,
            `Unscrewing succeeded on attempt ${this.unscrewAttempts}`, obs,
            `Belief updated: unscrewing success observed`);
          s.events.push(evt);
          s.lastEvent = evt;

          // Enforce supervisor containment: if at max attempts, must escalate
          if (this.unscrewAttempts >= this.config.maxUnscrewAttempts) {
            this.escalated = true;
            const bin = 'manual_escalation' as StationId;
            const binRec = selectPolicy(s.belief, station, this.policyCtx(), this.config);
            this.recordDecision(s, station, binRec, bin);
            return bin;
          }

          const binSnap = this.buildMinimalSnapshot(s);
          const bin = selectOutputBin(binSnap, this.config);
          const binRec = selectPolicy(s.belief, station, this.policyCtx(), this.config);
          this.recordDecision(s, station, binRec, bin);
          return bin;
        }

        // Failure
        const failEvt: EventType = 'unscrewing_failed';
        const evt = this.makeEvent(s.step, failEvt, station,
          `Unscrewing failed on attempt ${this.unscrewAttempts} \u2014 ${obs.evidence}`, obs,
          `Belief updated: unscrewing failure observed`);
        s.events.push(evt);
        s.lastEvent = evt;

        const rec = selectPolicy(s.belief, station, this.policyCtx(), this.config);
        s.belief.recommendedAction = rec;

        let nextUnscrew: StationId;
        if (rec.action === 'reroute_operator' || rec.action === 'escalate') {
          nextUnscrew = 'manual_escalation';
          this.escalated = true;
        } else if (rec.action === 'seek_evidence' && this.evidenceRequestCount < this.config.maxEvidenceRequests) {
          this.evidenceRequestCount += 1;
          s.evidenceRequestCount = this.evidenceRequestCount;
          nextUnscrew = 'inspection';
        } else {
          // Retry unscrewing
          nextUnscrew = 'unscrewing';
        }
        this.recordDecision(s, station, rec, nextUnscrew);
        return nextUnscrew;
      }

      case 'battery_check': {
        const recBat = selectPolicy(s.belief, station, this.policyCtx(), this.config);
        s.belief.recommendedAction = recBat;

        let nextBat: StationId;
        if (s.belief.beliefs.battery_hazard > 0.5) {
          const evt = this.makeEvent(s.step, 'battery_risk_flagged', station,
            `Battery deemed hazardous (belief=${(s.belief.beliefs.battery_hazard * 100).toFixed(0)}%) \u2014 routing to hazardous output`);
          s.events.push(evt);
          s.lastEvent = evt;
          nextBat = 'output_hazardous';
        } else {
          const evt = this.makeEvent(s.step, 'battery_cleared', station,
            'Battery cleared \u2014 proceeding to unscrewing');
          s.events.push(evt);
          s.lastEvent = evt;
          nextBat = 'unscrewing';
        }
        this.recordDecision(s, station, recBat, nextBat);
        return nextBat;
      }

      case 'manual_escalation': {
        const evt = this.makeEvent(s.step, 'escalation_resolved', station,
          `Operator resolved diagnosis for product ${s.product.id}`);
        s.events.push(evt);
        s.lastEvent = evt;
        const escSnap = this.buildMinimalSnapshot(s);
        const bin = selectOutputBin(escSnap, this.config);
        const recEsc = selectPolicy(s.belief, station, this.policyCtx(), this.config);
        this.recordDecision(s, station, recEsc, bin);
        return bin;
      }

      // Output bins
      default:
        return station;
    }
  }

  private transitionTo(target: StationId): SimulationSnapshot {
    const s = this.snapshot;
    const from = s.currentStation;

    // Mark escalated when routing to manual_escalation
    if (target === 'manual_escalation') {
      this.escalated = true;
    }

    // Leave old station
    s.stations[from].status = 'idle';
    s.stations[from].itemPresent = false;

    // Check if target is an output bin
    const isOutput = OUTPUT_BINS.includes(target);

    if (isOutput) {
      // Move to output bin
      s.currentStation = target;
      s.stations[target].itemPresent = true;
      s.stations[target].status = 'idle';
      s.outputBin = target;

      // Track the output bin in route path
      this.routePath.push(target);

      const evtType: EventType = 'item_binned';
      const evt = this.makeEvent(s.step, evtType, target,
        `Product ${s.product.id} binned at ${STATION_LABELS[target]}`);
      s.events.push(evt);

      const compEvt = this.makeEvent(s.step, 'item_completed', target,
        `Disassembly complete \u2014 product ${s.product.id} classified as ${STATION_LABELS[target].replace('Output \u2013 ', '').toLowerCase()}`);
      s.events.push(compEvt);
      s.lastEvent = compEvt;

      // Check if we've reached the product limit
      if (s.completedProducts.length + 1 >= this.maxProducts) {
        // Archive this product before completing
        this.archiveCurrentProduct(target);
        // Build and store the product trace
        s.productTraces.push(this.buildProductTrace(s));
        s.phase = 'completed';
        s.enabledTransitions = [];
        s.belief.recommendedAction = { action: 'complete', reason: 'Product limit reached \u2014 simulation complete', confidence: 1 };
        return this.getSnapshot();
      }

      // Continuous mode: flag for next product spawn
      s.enabledTransitions = [];
      s.belief.recommendedAction = { action: 'complete', reason: 'Item has been classified and binned', confidence: 1 };
      this.awaitingNextProduct = true;
      return this.getSnapshot();
    }

    // Transfer event
    const transferType: EventType = from !== target ? 'transfer_started' : 'transfer_completed';
    const evt = this.makeEvent(s.step, transferType, target,
      `Transferring product from ${STATION_LABELS[from]} \u2192 ${STATION_LABELS[target]}`);
    s.events.push(evt);
    s.lastEvent = evt;

    s.currentStation = target;
    s.stations[target].itemPresent = true;
    s.stations[target].status = 'idle';
    s.belief.recommendedAction = selectPolicy(s.belief, target, this.policyCtx(), this.config);
    s.enabledTransitions = computeEnabled(target, s.belief, this.policyCtx());

    // Start processing at new station immediately
    return this.beginStationProcessing();
  }

  private makeEvent(
    step: number,
    type: EventType,
    station: StationId,
    description: string,
    observation?: Observation,
    beliefDelta?: string,
  ): SimEvent {
    const evt: SimEvent = { step, type, station, description };
    if (observation) evt.observation = observation;
    if (beliefDelta) evt.beliefDelta = beliefDelta;
    return evt;
  }

  private startedEventType(station: StationId): EventType {
    switch (station) {
      case 'inspection':        return 'inspection_started';
      case 'unscrewing':        return 'unscrewing_started';
      case 'battery_check':     return 'battery_check_started';
      case 'manual_escalation': return 'escalation_started';
      default:                  return 'transfer_started';
    }
  }

  private processingEventType(station: StationId): EventType {
    switch (station) {
      case 'inspection':        return 'inspection_started';
      case 'unscrewing':        return 'unscrewing_attempted';
      case 'battery_check':     return 'battery_check_started';
      case 'manual_escalation': return 'escalation_started';
      default:                  return 'transfer_started';
    }
  }
}
