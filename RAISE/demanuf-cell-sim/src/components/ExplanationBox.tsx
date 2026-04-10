import { AnimatePresence, motion } from 'framer-motion';
import clsx from 'clsx';
import type { PolicyRecommendation, SimEvent } from '../sim/types';

interface ExplanationBoxProps {
  recommendation: PolicyRecommendation;
  lastEvent?: SimEvent | null;
  beliefDelta?: string;
}

const ACTION_STYLES: Record<string, string> = {
  continue:        'bg-accent-green/20 text-accent-green',
  inspect_more:    'bg-accent-blue/20 text-accent-blue',
  reroute_battery: 'bg-accent-red/20 text-accent-red',
  reroute_operator:'bg-accent-purple/20 text-accent-purple',
  escalate:        'bg-accent-amber/20 text-accent-amber',
  abort:           'bg-red-500/25 text-red-400',
  complete:        'bg-teal-500/20 text-teal-400',
};

const ACTION_LABELS: Record<string, string> = {
  continue:        'Continue',
  inspect_more:    'Inspect More',
  reroute_battery: 'Reroute → Battery',
  reroute_operator:'Reroute → Operator',
  escalate:        'Escalate',
  abort:           'Abort',
  complete:        'Complete',
};

export default function ExplanationBox({ recommendation, lastEvent, beliefDelta }: ExplanationBoxProps) {
  const actionStyle = ACTION_STYLES[recommendation.action] ?? 'bg-gray-500/20 text-gray-400';
  const actionLabel = ACTION_LABELS[recommendation.action] ?? recommendation.action;

  return (
    <div className="rounded-xl bg-surface-lighter p-3 space-y-2 border-l-4 border-accent-amber">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-gray-300 uppercase tracking-wider">
          Policy Recommendation
        </span>
        <AnimatePresence mode="wait">
          <motion.span
            key={recommendation.action}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ duration: 0.15 }}
            className={clsx('text-xs font-semibold px-2.5 py-1 rounded-full', actionStyle)}
          >
            {actionLabel}
          </motion.span>
        </AnimatePresence>
      </div>

      {/* Trigger */}
      {lastEvent && (
        <p className="text-[10px] text-gray-500">
          Triggered by:{' '}
          <span className="text-gray-400 font-medium">{lastEvent.type.replace(/_/g, ' ')}</span>
        </p>
      )}

      {/* Reason */}
      <AnimatePresence mode="wait">
        <motion.p
          key={recommendation.reason}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.2 }}
          className="text-sm text-gray-200 leading-relaxed"
        >
          {recommendation.reason}
        </motion.p>
      </AnimatePresence>

      {/* Confidence bar */}
      <div className="flex items-center gap-2">
        <span className="text-[10px] text-gray-500">Confidence</span>
        <div className="flex-1 h-1.5 rounded-full bg-surface overflow-hidden">
          <motion.div
            className="h-full rounded-full bg-accent-blue"
            initial={false}
            animate={{ width: `${Math.max(recommendation.confidence * 100, 2)}%` }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          />
        </div>
        <span className="text-[10px] font-mono text-gray-400">
          {(recommendation.confidence * 100).toFixed(0)}%
        </span>
      </div>

      {/* Belief delta note */}
      {beliefDelta && (
        <p className="text-[10px] text-gray-500 italic">{beliefDelta}</p>
      )}
    </div>
  );
}
