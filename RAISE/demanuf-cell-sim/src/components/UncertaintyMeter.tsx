import { motion } from 'framer-motion';
import clsx from 'clsx';

interface UncertaintyMeterProps {
  uncertainty: number;
  label?: string;
}

function getInterpretation(u: number): { text: string; colorClass: string } {
  if (u < 0.3) return { text: 'Low — confident', colorClass: 'text-accent-green' };
  if (u < 0.6) return { text: 'Moderate', colorClass: 'text-accent-amber' };
  if (u < 0.8) return { text: 'High — uncertain', colorClass: 'text-accent-red' };
  return { text: 'Very high — insufficient evidence', colorClass: 'text-accent-red' };
}

function getFillColor(u: number): string {
  if (u < 0.3) return 'from-accent-green to-accent-green';
  if (u < 0.6) return 'from-accent-green via-accent-amber to-accent-amber';
  if (u < 0.8) return 'from-accent-green via-accent-amber to-accent-red';
  return 'from-accent-green via-accent-amber to-accent-red';
}

export default function UncertaintyMeter({ uncertainty, label }: UncertaintyMeterProps) {
  const pct = Math.min(Math.max(uncertainty, 0), 1) * 100;
  const interp = getInterpretation(uncertainty);

  return (
    <div className="rounded-xl bg-surface-light p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-gray-300 uppercase tracking-wider">
          {label ?? 'Uncertainty'}
        </span>
        <motion.span
          key={uncertainty.toFixed(3)}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-sm font-mono text-gray-200"
        >
          {(uncertainty * 100).toFixed(1)}%
        </motion.span>
      </div>

      {/* Horizontal gauge */}
      <div className="h-3 rounded-full bg-surface overflow-hidden">
        <motion.div
          className={clsx('h-full rounded-full bg-gradient-to-r', getFillColor(uncertainty))}
          initial={false}
          animate={{ width: `${Math.max(pct, 1)}%` }}
          transition={{ type: 'spring', stiffness: 250, damping: 28 }}
        />
      </div>

      {/* Interpretation label */}
      <motion.p
        key={interp.text}
        initial={{ opacity: 0, y: 2 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className={clsx('text-[10px] mt-1.5 font-medium', interp.colorClass)}
      >
        {interp.text}
      </motion.p>
    </div>
  );
}
