import { useMemo } from 'react';
import { motion } from 'framer-motion';
import clsx from 'clsx';
import type { CompletedProduct } from '../sim/types';
import { computeRunMetrics, type RunMetrics } from '../sim/metrics';

// ── Props ────────────────────────────────────────────────────────────

interface MetricsPanelProps {
  completedProducts: CompletedProduct[];
}

// ── Helpers ──────────────────────────────────────────────────────────

function pct(v: number): string {
  return `${(v * 100).toFixed(0)}%`;
}

function MetricCell({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="flex flex-col items-center">
      <span className={clsx('text-sm font-semibold font-mono', accent ?? 'text-gray-200')}>
        {value}
      </span>
      <span className="text-[9px] text-gray-500 leading-tight">{label}</span>
    </div>
  );
}

// ── Component ────────────────────────────────────────────────────────

export default function MetricsPanel({ completedProducts }: MetricsPanelProps) {
  const metrics: RunMetrics | null = useMemo(() => {
    if (completedProducts.length === 0) return null;
    return computeRunMetrics(completedProducts);
  }, [completedProducts]);

  if (!metrics) return null;

  const { calibrationBuckets, binConfusion } = metrics;

  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-wider">
        Run Metrics
        <span className="ml-2 text-[10px] font-normal normal-case text-gray-500">
          ({metrics.totalProducts} product{metrics.totalProducts !== 1 ? 's' : ''})
        </span>
      </h3>

      {/* Key metrics grid */}
      <div className="rounded-xl bg-surface-lighter p-3">
        <div className="grid grid-cols-3 gap-y-3 gap-x-2">
          <MetricCell label="Accuracy" value={pct(metrics.beliefTop1Accuracy)} accent="text-accent-green" />
          <MetricCell label="Abstain" value={pct(metrics.abstentionRate)} accent="text-accent-amber" />
          <MetricCell label="Escalate" value={pct(metrics.escalationRate)} accent="text-accent-red" />
          <MetricCell label="Hazard Recall" value={pct(metrics.hazardRecall)} accent="text-teal-400" />
          <MetricCell label="False-Safe" value={pct(metrics.falseSafeRate)} accent="text-rose-400" />
          <MetricCell label="Unresolved" value={pct(metrics.unresolvedRate)} />
        </div>

        <div className="mt-2 pt-2 border-t border-white/5 flex items-center justify-center gap-4">
          <MetricCell label="Avg Steps" value={metrics.avgStepsPerProduct.toFixed(1)} />
          <MetricCell label="Avg Decisions" value={metrics.avgDecisionsPerProduct.toFixed(1)} />
          <MetricCell label="Avg Evidence" value={metrics.avgEvidenceRequestsPerProduct.toFixed(1)} />
        </div>
      </div>

      {/* Calibration */}
      {calibrationBuckets.length > 0 && (
        <div className="rounded-xl bg-surface-light p-2 space-y-1.5">
          <h4 className="text-[10px] text-gray-500 font-semibold uppercase tracking-wider px-1">
            Calibration
          </h4>
          {calibrationBuckets.map((bucket, i) => (
            <motion.div
              key={bucket.range}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.12, delay: i * 0.04 }}
              className="flex items-center gap-2 px-1"
            >
              <span className="text-[9px] font-mono text-gray-500 w-12 shrink-0">
                {bucket.range}
              </span>
              <div className="flex-1 h-2 rounded-full bg-surface overflow-hidden">
                <div
                  className={clsx(
                    'h-full rounded-full transition-all',
                    bucket.count === 0
                      ? 'bg-gray-600'
                      : bucket.accuracy >= 0.7
                        ? 'bg-accent-green/70'
                        : bucket.accuracy >= 0.4
                          ? 'bg-accent-amber/70'
                          : 'bg-accent-red/70',
                  )}
                  style={{ width: `${bucket.count === 0 ? 0 : Math.max(bucket.accuracy * 100, 3)}%` }}
                />
              </div>
              <span className="text-[9px] font-mono text-gray-400 w-16 text-right shrink-0">
                {bucket.count === 0 ? '—' : `${bucket.correctCount}/${bucket.count} ${pct(bucket.accuracy)}`}
              </span>
            </motion.div>
          ))}
        </div>
      )}

      {/* Bin × Condition confusion mini-table */}
      {binConfusion.labels.length > 0 && metrics.totalProducts >= 3 && (
        <div className="rounded-xl bg-surface-light p-2 space-y-1.5">
          <h4 className="text-[10px] text-gray-500 font-semibold uppercase tracking-wider px-1">
            Bin × Condition
          </h4>
          <div className="overflow-x-auto">
            <table className="w-full text-[9px]">
              <thead>
                <tr>
                  <th className="text-left text-gray-500 font-medium px-1 py-0.5" />
                  {binConfusion.labels.map((l) => (
                    <th key={l} className="text-center text-gray-500 font-medium px-1 py-0.5 truncate max-w-[60px]">
                      {l.replace(/output_/g, '').replace(/_/g, ' ')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {binConfusion.labels.map((rowLabel, ri) => {
                  const rowSum = binConfusion.matrix[ri].reduce((a, b) => a + b, 0);
                  if (rowSum === 0) return null;
                  return (
                    <tr key={rowLabel} className="hover:bg-white/[0.03]">
                      <td className="text-gray-400 font-medium px-1 py-0.5 truncate max-w-[70px]">
                        {rowLabel.replace(/_/g, ' ')}
                      </td>
                      {binConfusion.matrix[ri].map((count, ci) => (
                        <td
                          key={ci}
                          className={clsx(
                            'text-center font-mono px-1 py-0.5',
                            count === 0
                              ? 'text-gray-600'
                              : ri === ci
                                ? 'text-accent-green font-semibold'
                                : 'text-gray-400',
                          )}
                        >
                          {count || '·'}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
