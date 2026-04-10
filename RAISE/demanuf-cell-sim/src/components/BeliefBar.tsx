import { motion } from 'framer-motion';
import clsx from 'clsx';

interface BeliefBarProps {
  hypothesis: string;
  probability: number;
  previousProbability?: number;
  color: string;
  isTrue?: boolean;
}

export default function BeliefBar({
  hypothesis,
  probability,
  previousProbability,
  color,
  isTrue,
}: BeliefBarProps) {
  const pct = probability * 100;
  const delta = previousProbability != null ? probability - previousProbability : null;

  return (
    <div
      className={clsx(
        'rounded-lg px-3 py-2 transition-colors duration-200',
        isTrue
          ? 'bg-surface-lighter ring-1 ring-accent-green/60'
          : 'bg-surface-light',
      )}
    >
      {/* Label row */}
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-1.5 min-w-0">
          {isTrue && <span className="text-xs leading-none">✓</span>}
          <span className="text-sm font-semibold text-gray-200 truncate">{hypothesis}</span>
        </div>

        <div className="flex items-center gap-2 shrink-0 ml-2">
          {/* Delta indicator */}
          {delta != null && Math.abs(delta) > 0.005 && (
            <motion.span
              key={delta.toFixed(3)}
              initial={{ opacity: 0, x: 4 }}
              animate={{ opacity: 1, x: 0 }}
              className={clsx(
                'text-xs font-mono font-semibold leading-none px-1.5 py-0.5 rounded',
                delta > 0 ? 'text-accent-green bg-accent-green/10' : 'text-accent-red bg-accent-red/10',
              )}
            >
              {delta > 0 ? '▲' : '▼'} {delta > 0 ? '+' : ''}
              {(delta * 100).toFixed(1)}
            </motion.span>
          )}
          <span className="text-sm font-mono text-gray-300 w-[3.5rem] text-right font-medium">
            {pct.toFixed(1)}%
          </span>
        </div>
      </div>

      {/* Bar */}
      <div className="h-3 rounded-full bg-surface overflow-hidden">
        <motion.div
          className={clsx('h-full rounded-full', color)}
          initial={false}
          animate={{ width: `${Math.max(pct, 2)}%` }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        />
      </div>
    </div>
  );
}
