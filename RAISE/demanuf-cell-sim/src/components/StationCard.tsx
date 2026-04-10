import { motion } from 'framer-motion';
import clsx from 'clsx';
import type { StationState, StationId, ResourceStatus } from '../sim/types';

interface StationCardProps {
  station: StationState;
  isActive: boolean;
  isEnabled: boolean;
  isOutput: boolean;
}

const STATION_ICONS: Record<StationId, string> = {
  input_buffer: '📥',
  conveyor: '➡️',
  inspection: '🔍',
  unscrewing: '🔧',
  battery_check: '🔋',
  manual_escalation: '👤',
  output_reusable: '♻️',
  output_recoverable: '🔄',
  output_hazardous: '⚠️',
  output_unresolved: '❓',
};

const STATUS_COLORS: Record<ResourceStatus, string> = {
  idle: 'bg-gray-500',
  busy: 'bg-accent-blue',
  blocked: 'bg-accent-red',
  waiting: 'bg-accent-amber',
  escalated: 'bg-accent-purple',
};

const STATUS_LABELS: Record<ResourceStatus, string> = {
  idle: 'Idle',
  busy: 'Busy',
  blocked: 'Blocked',
  waiting: 'Waiting',
  escalated: 'Escalated',
};

export default function StationCard({ station, isActive, isEnabled, isOutput }: StationCardProps) {
  const progress = station.processingTimeLeft > 0 && station.status === 'busy'
    ? Math.min(Math.max(1 - station.processingTimeLeft / 5, 0.1), 1)
    : 0;

  return (
    <motion.div
      layout
      animate={isActive ? { scale: 1.06 } : { scale: 1 }}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
      className={clsx(
        'rounded-xl bg-surface-light relative transition-all duration-200',
        isOutput ? 'p-3 min-w-[120px]' : 'p-3.5 min-w-[160px]',
        isActive && 'ring-2 ring-accent-blue shadow-lg shadow-accent-blue/40',
        isEnabled && !isActive && 'border border-dashed border-accent-green/50',
        !isActive && !isEnabled && 'border border-white/5',
      )}
    >
      {/* Icon + status dot */}
      <div className="flex items-center justify-between mb-2">
        <span className={clsx('leading-none', isOutput ? 'text-lg' : 'text-xl')}>
          {STATION_ICONS[station.id]}
        </span>
        <span className="relative flex h-2.5 w-2.5">
          {station.status === 'busy' && (
            <span className={clsx(
              'absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping',
              STATUS_COLORS[station.status],
            )} />
          )}
          <span className={clsx(
            'relative inline-flex rounded-full h-2.5 w-2.5',
            STATUS_COLORS[station.status],
          )} />
        </span>
      </div>

      {/* Label */}
      <p className={clsx(
        'font-semibold text-gray-200 leading-tight mb-1 truncate',
        isOutput ? 'text-[11px]' : 'text-xs',
      )}>
        {station.label}
      </p>

      {/* Status + ticks remaining */}
      <div className="flex items-center gap-1.5">
        <motion.span
          key={station.status}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className={clsx('text-[10px] font-medium leading-tight', {
            'text-gray-500': station.status === 'idle',
            'text-accent-blue': station.status === 'busy',
            'text-accent-red': station.status === 'blocked',
            'text-accent-amber': station.status === 'waiting',
            'text-accent-purple': station.status === 'escalated',
          })}
        >
          {STATUS_LABELS[station.status]}
        </motion.span>
        {station.status === 'busy' && station.processingTimeLeft > 0 && (
          <span className="text-[9px] text-gray-500 font-mono">
            {station.processingTimeLeft}tk left
          </span>
        )}
      </div>

      {/* Progress bar */}
      {station.status === 'busy' && station.processingTimeLeft > 0 && (
        <div className="mt-2 h-1 rounded-full bg-surface overflow-hidden">
          <motion.div
            className="h-full rounded-full bg-accent-blue"
            initial={{ width: 0 }}
            animate={{ width: `${Math.max(progress * 100, 10)}%` }}
            transition={{ duration: 0.3 }}
          />
        </div>
      )}

      {/* Item present indicator */}
      {station.itemPresent && (
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-accent-green flex items-center justify-center shadow-sm shadow-accent-green/30"
        >
          <span className="text-[9px] text-surface font-bold">●</span>
        </motion.div>
      )}
    </motion.div>
  );
}
