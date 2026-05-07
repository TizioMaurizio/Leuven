import type { StationId, Hypothesis, BeliefState, StructuredDecision } from './types';
import type { PolicyConfig } from './config';

// ── Intent types ─────────────────────────────────────────────────────

export interface MediationContext {
  currentStation: StationId;
  belief: BeliefState;
  enabledTransitions: StationId[];
  currentDecision: StructuredDecision | null;
  unscrewAttempts: number;
  evidenceRequestCount: number;
  config: PolicyConfig;
}

export interface MediationIntent {
  proposedAction: StationId;
  confidence: number;          // mediator's confidence in the proposal
  rationale: string;           // natural language reason
  source: 'llm' | 'rule' | 'stub';
}

export interface MediationResult {
  accepted: boolean;
  finalAction: StationId;
  intent: MediationIntent | null;
  validationReason: string;    // why accepted or rejected
  constraintViolation: string | null;  // which constraint was violated, if any
}

// ── Mediator interface ───────────────────────────────────────────────

export interface Mediator {
  proposeIntent(context: MediationContext): MediationIntent | null;
  validateIntent(intent: MediationIntent, enabledActions: StationId[]): { valid: boolean; reason: string };
  resolveAction(context: MediationContext, intent: MediationIntent | null, policyDefault: StationId): MediationResult;
}

// ── Stub implementation (deterministic, no LLM) ─────────────────────

export class StubMediator implements Mediator {
  // Always defers to policy — produces no proposals
  proposeIntent(_context: MediationContext): MediationIntent | null {
    return null;
  }

  validateIntent(intent: MediationIntent, enabledActions: StationId[]): { valid: boolean; reason: string } {
    if (!enabledActions.includes(intent.proposedAction)) {
      return { valid: false, reason: `Action '${intent.proposedAction}' not in enabled set: [${enabledActions.join(', ')}]` };
    }
    return { valid: true, reason: 'Action is within enabled set' };
  }

  resolveAction(
    _context: MediationContext,
    intent: MediationIntent | null,
    policyDefault: StationId,
  ): MediationResult {
    // Stub: always use the policy default, log that no mediation occurred
    return {
      accepted: false,
      finalAction: policyDefault,
      intent,
      validationReason: intent ? 'Stub mediator — deferring to policy' : 'No intent proposed',
      constraintViolation: null,
    };
  }
}

// ── Default instance ─────────────────────────────────────────────────

export const defaultMediator: Mediator = new StubMediator();
