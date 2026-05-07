import { AnimatePresence, motion } from 'framer-motion';
import clsx from 'clsx';
import type { StructuredDecision, DecisionRecord, DecisionType, DecisionConfidenceLevel } from '../sim/types';

// ── Props ────────────────────────────────────────────────────────────

interface DecisionPanelProps {
  decision: StructuredDecision | null;
  decisionHistory: DecisionRecord[];
}

// ── Styling maps ─────────────────────────────────────────────────────

const DECISION_TYPE_STYLES: Record<DecisionType, string> = {
  route_confident:      'bg-accent-green/20 text-accent-green',
  route_moderate:       'bg-accent-blue/20 text-accent-blue',
  abstain_unresolved:   'bg-accent-amber/20 text-accent-amber',
  escalate_uncertainty: 'bg-accent-red/20 text-accent-red',
  escalate_hazard:      'bg-accent-red/20 text-accent-red',
  escalate_structural:  'bg-accent-red/20 text-accent-red',
  seek_evidence:        'bg-accent-purple/20 text-accent-purple',
  retry_operation:      'bg-accent-blue/20 text-accent-blue',
  complete:             'bg-gray-500/20 text-gray-400',
};

const CONFIDENCE_STYLES: Record<DecisionConfidenceLevel, string> = {
  confident:  'bg-accent-green/20 text-accent-green',
  moderate:   'bg-accent-blue/20 text-accent-blue',
  low:        'bg-accent-amber/20 text-accent-amber',
  abstaining: 'bg-accent-red/20 text-accent-red',
};

const SOURCE_STYLES: Record<string, string> = {
  standard_policy:   'bg-teal-500/15 text-teal-400',
  escalation:        'bg-accent-amber/15 text-accent-amber',
  mediation:         'bg-accent-purple/15 text-accent-purple',
  evidence_request:  'bg-accent-blue/15 text-accent-blue',
};

// ── Component ────────────────────────────────────────────────────────

export default function DecisionPanel({ decision, decisionHistory }: DecisionPanelProps) {
  if (!decision) {
    return (
      <div className="rounded-xl bg-surface-light p-3 border border-dashed border-gray-600 flex items-center justify-center">
        <span className="text-[10px] text-gray-500 italic">No decision yet</span>
      </div>
    );
  }

  const recentHistory = decisionHistory.slice(-5);

  return (
    <div className="space-y-2">
      {/* Current decision card */}
      <div className="rounded-xl bg-surface-lighter p-3 space-y-2 border-l-4 border-accent-blue">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-gray-300 uppercase tracking-wider">
            Structured Decision
          </span>
          <AnimatePresence mode="wait">
            <motion.span
              key={decision.type}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ duration: 0.15 }}
              className={clsx(
                'text-[9px] font-semibold px-2 py-0.5 rounded-full',
                DECISION_TYPE_STYLES[decision.type] ?? 'bg-gray-500/20 text-gray-400',
              )}
            >
              {decision.type.replace(/_/g, ' ')}
            </motion.span>
          </AnimatePresence>
        </div>

        {/* Confidence + Source badges */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span
            className={clsx(
              'text-[9px] px-1.5 py-0.5 rounded-full font-medium',
              CONFIDENCE_STYLES[decision.confidenceLevel],
            )}
          >
            {decision.confidenceLevel}
          </span>
          <span
            className={clsx(
              'text-[9px] px-1.5 py-0.5 rounded-full font-medium',
              SOURCE_STYLES[decision.source] ?? 'bg-gray-500/15 text-gray-400',
            )}
          >
            {decision.source.replace(/_/g, ' ')}
          </span>
          {decision.hazardPresent && (
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-accent-red/20 text-accent-red font-medium">
              ⚠ hazard
            </span>
          )}
          {decision.additionalEvidenceAvailable && (
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-accent-blue/15 text-accent-blue font-medium">
              ℹ evidence available
            </span>
          )}
        </div>

        {/* Selected route */}
        {decision.selectedRoute && (
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-gray-500">Route:</span>
            <span className="text-[10px] font-mono text-gray-200">
              {decision.selectedRoute.replace(/_/g, ' ')}
            </span>
          </div>
        )}

        {/* Reason codes */}
        {decision.reasonCodes.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {decision.reasonCodes.map((code) => (
              <span
                key={code}
                className="text-[8px] px-1.5 py-0.5 rounded-full bg-white/5 text-gray-400 font-mono"
              >
                {code}
              </span>
            ))}
          </div>
        )}

        {/* Alternatives */}
        {decision.enabledAlternatives.length > 0 && (
          <div className="flex items-center gap-1 flex-wrap">
            <span className="text-[10px] text-gray-500">Alts:</span>
            {decision.enabledAlternatives.map((alt) => (
              <span
                key={alt}
                className="text-[8px] px-1.5 py-0.5 rounded-full bg-gray-600/30 text-gray-500 font-mono"
              >
                {alt.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Decision timeline (last 5) */}
      {recentHistory.length > 0 && (
        <div className="rounded-xl bg-surface-light p-2 space-y-0.5">
          <h4 className="text-[10px] text-gray-500 font-semibold uppercase tracking-wider mb-1 px-1">
            Decision Timeline
          </h4>
          <div className="overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead>
                <tr className="text-gray-500">
                  <th className="text-left font-medium px-1 py-0.5">Step</th>
                  <th className="text-left font-medium px-1 py-0.5">Station</th>
                  <th className="text-left font-medium px-1 py-0.5">Type</th>
                  <th className="text-left font-medium px-1 py-0.5">Selected</th>
                  <th className="text-left font-medium px-1 py-0.5">Conf</th>
                </tr>
              </thead>
              <tbody>
                {recentHistory.map((rec, i) => (
                  <motion.tr
                    key={`${rec.step}-${i}`}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.12, delay: i * 0.03 }}
                    className="hover:bg-white/[0.03]"
                  >
                    <td className="font-mono text-gray-400 px-1 py-0.5">{rec.step}</td>
                    <td className="text-gray-300 px-1 py-0.5">{rec.station.replace(/_/g, ' ')}</td>
                    <td className="px-1 py-0.5">
                      <span
                        className={clsx(
                          'text-[8px] px-1 py-0.5 rounded-full',
                          DECISION_TYPE_STYLES[rec.decision.type] ?? 'bg-gray-500/20 text-gray-400',
                        )}
                      >
                        {rec.decision.type.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="font-mono text-gray-300 px-1 py-0.5">
                      {rec.selected.replace(/_/g, ' ')}
                    </td>
                    <td className="px-1 py-0.5">
                      <span
                        className={clsx(
                          'text-[8px] px-1 py-0.5 rounded-full',
                          CONFIDENCE_STYLES[rec.decision.confidenceLevel],
                        )}
                      >
                        {rec.decision.confidenceLevel}
                      </span>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
