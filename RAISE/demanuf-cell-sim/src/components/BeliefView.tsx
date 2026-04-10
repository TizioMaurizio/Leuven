import { useRef, useEffect, useMemo } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import clsx from 'clsx';
import type {
  SimulationSnapshot,
  Hypothesis,
  HiddenCondition,
  Observation,
} from '../sim/types';
import { conditionToHypothesis } from '../sim/belief';
import BeliefBar from './BeliefBar';
import UncertaintyMeter from './UncertaintyMeter';
import ExplanationBox from './ExplanationBox';

// ── Props ────────────────────────────────────────────────────────────

interface BeliefViewProps {
  snapshot: SimulationSnapshot;
  showTrueState: boolean;
  onToggleTrueState: () => void;
}

// ── Constants ────────────────────────────────────────────────────────

const HYPOTHESIS_ORDER: Hypothesis[] = [
  'normal_path',
  'hidden_fastener',
  'adhesive_issue',
  'battery_hazard',
  'missing_parts',
  'structural_damage',
  'easy_case',
];

const HYPOTHESIS_LABELS: Record<Hypothesis, string> = {
  normal_path:      'Normal Path',
  hidden_fastener:  'Hidden Fastener',
  adhesive_issue:   'Adhesive Issue',
  battery_hazard:   'Battery Hazard',
  missing_parts:    'Missing Parts',
  structural_damage:'Structural Damage',
  easy_case:        'Easy Case',
};

const HYPOTHESIS_COLORS: Record<Hypothesis, string> = {
  normal_path:       'bg-accent-blue',
  hidden_fastener:   'bg-accent-amber',
  adhesive_issue:    'bg-orange-500',
  battery_hazard:    'bg-accent-red',
  missing_parts:     'bg-accent-purple',
  structural_damage: 'bg-rose-500',
  easy_case:         'bg-accent-green',
};

const CONDITION_ICONS: Record<HiddenCondition, string> = {
  normal:            '💻',
  hidden_screws:     '🔩',
  strong_adhesive:   '🧴',
  swollen_battery:   '🔋',
  missing_component: '🚫',
  casing_damage:     '💥',
  easy_disassembly:  '✨',
};

const CONDITION_LABELS: Record<HiddenCondition, string> = {
  normal:            'Normal',
  hidden_screws:     'Hidden Screws',
  strong_adhesive:   'Strong Adhesive',
  swollen_battery:   'Swollen Battery',
  missing_component: 'Missing Component',
  casing_damage:     'Casing Damage',
  easy_disassembly:  'Easy Disassembly',
};

// ── Sub-components ───────────────────────────────────────────────────

function PropertyBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-gray-400 w-24 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-surface overflow-hidden">
        <div
          className="h-full rounded-full bg-accent-red/70"
          style={{ width: `${Math.max(value * 100, 1)}%` }}
        />
      </div>
      <span className="text-[10px] font-mono text-gray-500 w-8 text-right">
        {(value * 100).toFixed(0)}%
      </span>
    </div>
  );
}

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const cfg =
    confidence >= 0.7
      ? { text: 'high', cls: 'bg-accent-green/20 text-accent-green' }
      : confidence >= 0.4
        ? { text: 'med', cls: 'bg-accent-amber/20 text-accent-amber' }
        : { text: 'low', cls: 'bg-accent-red/20 text-accent-red' };

  return (
    <span className={clsx('text-[9px] px-1.5 py-0.5 rounded-full font-medium', cfg.cls)}>
      {cfg.text}
    </span>
  );
}

function ObservationRow({ obs, index }: { obs: Observation; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15 }}
      className="flex items-start gap-1.5 py-1.5 px-1.5 rounded hover:bg-white/[0.03]"
    >
      <span className="text-[10px] font-mono text-gray-500 w-4 text-right shrink-0 pt-0.5">
        {index + 1}.
      </span>
      <span className="text-[10px] font-mono text-gray-600 w-5 text-right shrink-0 pt-0.5">
        t{obs.step}
      </span>
      <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-accent-blue/15 text-accent-blue shrink-0">
        {obs.station.replace(/_/g, ' ')}
      </span>
      <span className="text-[10px] text-gray-300 flex-1 leading-tight">{obs.evidence}</span>
      <ConfidenceBadge confidence={obs.confidence} />
    </motion.div>
  );
}

// ── Main component ───────────────────────────────────────────────────

export default function BeliefView({ snapshot, showTrueState, onToggleTrueState }: BeliefViewProps) {
  const { product, belief, lastEvent } = snapshot;
  const prevBeliefsRef = useRef<Record<Hypothesis, number> | null>(null);
  const timelineRef = useRef<HTMLDivElement>(null);

  // Store previous beliefs each time they change
  const prevBeliefs = prevBeliefsRef.current;
  useEffect(() => {
    prevBeliefsRef.current = { ...belief.beliefs };
  }, [belief.beliefs]);

  // Auto-scroll evidence timeline
  useEffect(() => {
    if (timelineRef.current) {
      timelineRef.current.scrollTop = timelineRef.current.scrollHeight;
    }
  }, [belief.observations.length]);

  const trueHypothesis = conditionToHypothesis(product.condition);

  // Last event's beliefDelta string
  const beliefDelta = lastEvent?.beliefDelta;

  // Sorted hypotheses by probability (highest first)
  const sortedHypotheses = useMemo(() => {
    return [...HYPOTHESIS_ORDER].sort(
      (a, b) => (belief.beliefs[b] ?? 0) - (belief.beliefs[a] ?? 0),
    );
  }, [belief.beliefs]);

  // Dominant hypothesis
  const dominantHypothesis = sortedHypotheses[0];
  const dominantProb = belief.beliefs[dominantHypothesis] ?? 0;

  return (
    <div className="flex flex-col h-full">
      {/* Panel header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-white/5">
        <h2 className="text-sm font-semibold tracking-wide text-gray-200">
          Belief &amp; Hidden State
        </h2>
        <button
          onClick={onToggleTrueState}
          className={clsx(
            'text-[10px] px-2.5 py-1 rounded-full font-medium transition-colors',
            showTrueState
              ? 'bg-accent-red/20 text-accent-red hover:bg-accent-red/30'
              : 'bg-gray-600/40 text-gray-400 hover:bg-gray-600/60',
          )}
        >
          {showTrueState ? 'Hide True State' : 'Reveal True State'}
        </button>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4 scrollbar-thin">
        {/* Section A: Hidden Ground Truth */}
        <section>
          <AnimatePresence mode="wait">
            {showTrueState ? (
              <motion.div
                key="truth-revealed"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.25 }}
                className="rounded-xl bg-surface-light p-3 ring-1 ring-accent-red/40 space-y-2.5 overflow-hidden"
              >
                <div className="flex items-center gap-2">
                  <span className="text-lg leading-none">
                    {CONDITION_ICONS[product.condition]}
                  </span>
                  <div>
                    <p className="text-sm font-medium text-gray-100">
                      {CONDITION_LABELS[product.condition]}
                    </p>
                    <p className="text-[10px] text-gray-500">
                      Ground truth — product {product.id}
                    </p>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <PropertyBar label="Screw difficulty" value={product.screwsDifficulty} />
                  <PropertyBar label="Adhesive strength" value={product.adhesiveStrength} />
                  <PropertyBar label="Battery risk" value={product.batteryRisk} />
                  <PropertyBar label="Casing integrity" value={product.casingIntegrity} />
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-gray-400 w-24 shrink-0">Missing parts</span>
                    <span
                      className={clsx(
                        'text-[10px] px-1.5 py-0.5 rounded-full font-medium',
                        product.missingParts
                          ? 'bg-accent-red/20 text-accent-red'
                          : 'bg-accent-green/20 text-accent-green',
                      )}
                    >
                      {product.missingParts ? 'Yes' : 'No'}
                    </span>
                  </div>
                </div>
              </motion.div>
            ) : (
              <motion.div
                key="truth-hidden"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="rounded-xl bg-surface-light p-3 border border-dashed border-gray-600 flex items-center justify-center gap-2"
              >
                <span className="text-2xl leading-none text-gray-600">?</span>
                <span className="text-xs text-gray-500">Hidden — click to reveal</span>
              </motion.div>
            )}
          </AnimatePresence>
        </section>

        {/* Quick Status Summary */}
        <section>
          <div className="rounded-lg bg-surface-lighter/60 px-3 py-2 flex items-center gap-3 text-xs flex-wrap">
            <span className="text-gray-400">
              Product: <span className="font-mono text-teal-400">#{snapshot.productNumber ?? 1}</span>
            </span>
            <span className="text-gray-600">|</span>
            <span className="text-gray-400">
              Step: <span className="font-mono text-gray-200">{snapshot.step}</span>
            </span>
            <span className="text-gray-600">|</span>
            <span className="text-gray-400">
              Observations: <span className="font-mono text-gray-200">{belief.observations.length}</span>
            </span>
            <span className="text-gray-600">|</span>
            <span className="text-gray-400">
              Uncertainty: <span className="font-mono text-gray-200">{(belief.uncertainty * 100).toFixed(0)}%</span>
            </span>
            <span className="text-gray-600">|</span>
            <span className="text-gray-400">
              Best guess: <span className="font-medium text-gray-200">{HYPOTHESIS_LABELS[dominantHypothesis]}</span>
            </span>
          </div>
        </section>

        {/* Section B: Belief Distribution */}
        <section>
          <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1">
            Belief Distribution
          </h3>
          <p className="text-[10px] text-gray-500 mb-2">
            System's estimate of the product's hidden condition
          </p>

          {/* Dominant hypothesis callout */}
          <div className="mb-2">
            <motion.span
              key={dominantHypothesis}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.2 }}
              className={clsx(
                'inline-flex items-center gap-1.5 text-sm font-semibold px-3 py-1 rounded-full',
                HYPOTHESIS_COLORS[dominantHypothesis]?.replace('bg-', 'bg-') + '/20',
                'text-gray-100',
              )}
              style={{ backgroundColor: `color-mix(in srgb, currentColor 12%, transparent)` }}
            >
              <span className={clsx('w-2.5 h-2.5 rounded-full', HYPOTHESIS_COLORS[dominantHypothesis])} />
              Best guess: {HYPOTHESIS_LABELS[dominantHypothesis]} ({(dominantProb * 100).toFixed(0)}%)
            </motion.span>
          </div>

          <div className="space-y-1.5">
            {sortedHypotheses.map((h) => (
              <BeliefBar
                key={h}
                hypothesis={HYPOTHESIS_LABELS[h]}
                probability={belief.beliefs[h]}
                previousProbability={prevBeliefs ? prevBeliefs[h] : undefined}
                color={HYPOTHESIS_COLORS[h]}
                isTrue={showTrueState && h === trueHypothesis}
              />
            ))}
          </div>
        </section>

        {/* Section C: Uncertainty Meter */}
        <section>
          <UncertaintyMeter uncertainty={belief.uncertainty} />
        </section>

        {/* Section D: Evidence Timeline */}
        <section>
          <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-wider mb-2">
            Evidence Timeline
            <span className="ml-2 text-[10px] font-normal normal-case text-gray-500">
              ({belief.observations.length} observation{belief.observations.length !== 1 ? 's' : ''})
            </span>
          </h3>
          <div
            ref={timelineRef}
            className="rounded-xl bg-surface-light p-2 max-h-48 overflow-y-auto scrollbar-thin space-y-0.5"
          >
            {belief.observations.length === 0 ? (
              <p className="text-[10px] text-gray-600 italic text-center py-2">
                No observations yet
              </p>
            ) : (
              <AnimatePresence initial={false}>
                {belief.observations.map((obs, i) => (
                  <ObservationRow
                    key={`${obs.step}-${obs.type}-${i}`}
                    obs={obs}
                    index={i}
                  />
                ))}
              </AnimatePresence>
            )}
          </div>
        </section>

        {/* Section E: Policy Recommendation */}
        <section>
          <ExplanationBox
            recommendation={belief.recommendedAction}
            lastEvent={lastEvent}
            beliefDelta={beliefDelta}
          />
        </section>

        {/* Section F: Completed Products */}
        {(snapshot.completedProducts ?? []).length > 0 && (
          <section>
            <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-wider mb-2">
              Completed ({snapshot.completedProducts.length} product{snapshot.completedProducts.length !== 1 ? 's' : ''})
            </h3>
            <div className="space-y-1">
              {snapshot.completedProducts.slice(-5).map((cp, i) => {
                const globalIndex = snapshot.completedProducts.length - 5 + i;
                const displayIndex = Math.max(globalIndex, i) + 1;
                return (
                  <div key={cp.id} className="rounded-lg bg-surface-light px-3 py-2 flex items-center justify-between">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-[10px] text-gray-500 font-mono">#{displayIndex}</span>
                      <span className="text-xs text-gray-300 truncate">{cp.id}</span>
                      <span
                        className={clsx(
                          'text-[9px] px-1.5 py-0.5 rounded-full font-medium',
                          cp.beliefCorrect ? 'bg-accent-green/20 text-accent-green' : 'bg-accent-red/20 text-accent-red',
                        )}
                      >
                        {cp.beliefCorrect ? '✓ correct' : '✗ wrong'}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-[10px] text-gray-500">{cp.totalSteps}tk</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-teal-500/15 text-teal-400">
                        {cp.outputBin.replace('output_', '')}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
