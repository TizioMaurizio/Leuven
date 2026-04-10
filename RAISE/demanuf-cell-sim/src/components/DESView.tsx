import { motion } from 'framer-motion';
import clsx from 'clsx';
import type { SimulationSnapshot, StationId } from '../sim/types';
import StationCard from './StationCard';

interface DESViewProps {
  snapshot: SimulationSnapshot;
}

// ── Station groups by stage ──────────────────────────────────────────
const INTAKE: StationId[] = ['input_buffer', 'conveyor', 'inspection'];
const PROCESSING: StationId[] = ['battery_check', 'unscrewing', 'manual_escalation'];
const OUTPUT: StationId[] = [
  'output_reusable',
  'output_recoverable',
  'output_hazardous',
  'output_unresolved',
];
const OUTPUT_SET = new Set<StationId>(OUTPUT);

// ── Inter-stage connection descriptors ───────────────────────────────
const INTAKE_TO_PROCESSING: { target: StationId; label: string; icon: string }[] = [
  { target: 'battery_check', label: 'battery risk', icon: '⚡' },
  { target: 'unscrewing', label: 'proceed', icon: '🔧' },
  { target: 'manual_escalation', label: 'escalate', icon: '👤' },
];

const PROCESSING_TO_OUTPUT: { target: StationId; label: string }[] = [
  { target: 'output_reusable', label: 'reusable' },
  { target: 'output_recoverable', label: 'recoverable' },
  { target: 'output_hazardous', label: 'hazardous' },
  { target: 'output_unresolved', label: 'unresolved' },
];

// ── Badge color helpers ──────────────────────────────────────────────
function eventBadgeColor(type: string): string {
  if (type.startsWith('item_arrived') || type.startsWith('transfer'))
    return 'bg-accent-blue/20 text-accent-blue';
  if (type.startsWith('inspection') || type.startsWith('observation'))
    return 'bg-accent-green/20 text-accent-green';
  if (type.startsWith('unscrewing') || type.includes('screw') || type.includes('adhesive'))
    return 'bg-accent-amber/20 text-accent-amber';
  if (type.startsWith('battery') || type.includes('battery'))
    return 'bg-accent-red/20 text-accent-red';
  if (type.startsWith('escalation') || type.includes('reroute_to_operator'))
    return 'bg-accent-purple/20 text-accent-purple';
  if (type.includes('binned') || type.includes('completed') || type.includes('output'))
    return 'bg-teal-500/20 text-teal-400';
  return 'bg-gray-500/20 text-gray-400';
}

function phaseBadgeColor(phase: string): string {
  switch (phase) {
    case 'idle':
      return 'bg-gray-600 text-gray-300';
    case 'running':
      return 'bg-accent-blue/20 text-accent-blue';
    case 'completed':
      return 'bg-accent-green/20 text-accent-green';
    default:
      return 'bg-gray-600 text-gray-400';
  }
}

// ── Step Explanation ─────────────────────────────────────────────────
function StepExplanation({ snapshot }: { snapshot: SimulationSnapshot }) {
  const { lastEvent, belief, currentStation, stations } = snapshot;

  return (
    <div className="mx-4 mt-2 mb-1 rounded-lg bg-surface-lighter/50 px-4 py-3 border-l-4 border-accent-blue">
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-100 leading-snug">
            <span className="text-teal-400 font-semibold">Product #{snapshot.productNumber ?? 1}</span>
            {' — '}
            {lastEvent
              ? lastEvent.description
              : 'Simulation ready — press Play or Step to begin.'}
          </p>
          {belief.recommendedAction.reason && (
            <p className="text-xs text-gray-400 mt-1">
              → Next: {belief.recommendedAction.reason}
            </p>
          )}
        </div>
        <span className="shrink-0 text-[10px] px-2 py-0.5 rounded bg-accent-blue/15 text-accent-blue font-medium">
          {stations[currentStation].label}
        </span>
      </div>
    </div>
  );
}

// ── Stage label ─────────────────────────────────────────────────────
function StageLabel({ label, number }: { label: string; number: number }) {
  return (
    <div className="flex items-center gap-2 w-full max-w-2xl px-1 mt-2 mb-1">
      <span className="text-[9px] font-bold uppercase tracking-widest text-gray-500">
        {number}
      </span>
      <span className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold">
        {label}
      </span>
      <div className="flex-1 h-px bg-white/5" />
    </div>
  );
}

// ── Horizontal arrow between inline stations ────────────────────────
function HArrow({ active, dimmed }: { active: boolean; dimmed?: boolean }) {
  return (
    <div
      className={clsx(
        'flex items-center px-1 select-none transition-colors duration-200',
        active ? 'text-accent-blue' : dimmed ? 'text-gray-700' : 'text-gray-600',
      )}
    >
      <span className="text-base leading-none">→</span>
    </div>
  );
}

// ── Vertical connector between stage rows ───────────────────────────
function VConnector({
  label,
  icon,
  active,
  enabled,
}: {
  label: string;
  icon?: string;
  active: boolean;
  enabled: boolean;
}) {
  return (
    <div
      className={clsx(
        'flex flex-col items-center gap-0.5 min-w-[80px] transition-colors duration-200',
        active
          ? 'text-accent-blue'
          : enabled
            ? 'text-accent-green/70'
            : 'text-gray-700',
      )}
    >
      <span className={clsx('text-lg leading-none', active && 'animate-pulse')}>↓</span>
      <span className="text-[9px] font-medium whitespace-nowrap flex items-center gap-0.5">
        {icon && <span className="text-[10px]">{icon}</span>}
        {label}
      </span>
    </div>
  );
}

// ── Main Component ──────────────────────────────────────────────────
export default function DESView({ snapshot }: DESViewProps) {
  const { currentStation, stations, enabledTransitions, lastEvent, step, phase } = snapshot;
  const productNumber = snapshot.productNumber ?? 1;
  const binCounts = snapshot.binCounts ?? {};
  const enabledSet = new Set(enabledTransitions);

  const justTransferred = !!(
    lastEvent &&
    (lastEvent.type.includes('transfer') ||
      lastEvent.type === 'item_arrived' ||
      lastEvent.type.includes('reroute'))
  );

  const isEdgeActive = (target: StationId) => justTransferred && currentStation === target;

  return (
    <div className="flex flex-col h-full">
      {/* ─── Header ─── */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-white/5">
        <h2 className="text-sm font-semibold tracking-wide text-gray-200">
          Demanufacturing Cell
          <span className="ml-2 text-[10px] font-medium text-teal-400 bg-teal-500/15 px-1.5 py-0.5 rounded-full">
            Product #{productNumber}
          </span>
        </h2>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-gray-500 font-mono">Step {step}</span>
          <span
            className={clsx(
              'px-2 py-0.5 rounded-full text-[10px] font-medium',
              phaseBadgeColor(phase),
            )}
          >
            {phase}
          </span>
          {lastEvent && (
            <span
              className={clsx(
                'px-2 py-0.5 rounded-full text-[10px] font-medium',
                eventBadgeColor(lastEvent.type),
              )}
            >
              {lastEvent.type.replace(/_/g, ' ')}
            </span>
          )}
        </div>
      </div>

      {/* ─── Step Explanation ─── */}
      <StepExplanation snapshot={snapshot} />

      {/* ─── Cell Diagram ─── */}
      <div className="flex-1 flex flex-col items-center justify-start px-4 pt-2 pb-3 overflow-y-auto">
        {/* ── Stage 1: INTAKE ── */}
        <StageLabel label="Intake" number={1} />
        <div className="flex items-center justify-center gap-1">
          {INTAKE.flatMap((id, i) => {
            const els: React.ReactNode[] = [];
            if (i > 0) {
              els.push(<HArrow key={`ha-${id}`} active={isEdgeActive(id)} />);
            }
            els.push(
              <motion.div key={id} layout>
                <StationCard
                  station={stations[id]}
                  isActive={currentStation === id}
                  isEnabled={enabledSet.has(id)}
                  isOutput={false}
                />
              </motion.div>,
            );
            return els;
          })}
        </div>

        {/* ── Connector: Intake → Processing ── */}
        <div className="flex items-center justify-center gap-3 py-2">
          {INTAKE_TO_PROCESSING.map(({ target, label, icon }) => (
            <VConnector
              key={target}
              label={label}
              icon={icon}
              active={isEdgeActive(target)}
              enabled={enabledSet.has(target)}
            />
          ))}
        </div>

        {/* ── Stage 2: PROCESSING ── */}
        <StageLabel label="Processing" number={2} />
        <div className="flex items-center justify-center gap-1">
          {PROCESSING.flatMap((id, i) => {
            const els: React.ReactNode[] = [];
            if (i > 0) {
              els.push(<HArrow key={`ha-${id}`} active={isEdgeActive(id)} dimmed />);
            }
            els.push(
              <motion.div key={id} layout>
                <StationCard
                  station={stations[id]}
                  isActive={currentStation === id}
                  isEnabled={enabledSet.has(id)}
                  isOutput={false}
                />
              </motion.div>,
            );
            return els;
          })}
        </div>

        {/* ── Connector: Processing → Output ── */}
        <div className="flex items-center justify-center gap-3 py-2">
          {PROCESSING_TO_OUTPUT.map(({ target, label }) => (
            <VConnector
              key={target}
              label={label}
              active={isEdgeActive(target)}
              enabled={enabledSet.has(target)}
            />
          ))}
        </div>

        {/* ── Stage 3: OUTPUT ── */}
        <StageLabel label="Output" number={3} />
        <div className="flex items-center justify-center gap-3">
          {OUTPUT.map((id) => (
            <div key={id} className="relative">
              <motion.div layout>
                <StationCard
                  station={stations[id]}
                  isActive={currentStation === id}
                  isEnabled={enabledSet.has(id)}
                  isOutput={true}
                />
              </motion.div>
              {(binCounts[id] ?? 0) > 0 && (
                <span className="absolute -top-2 -left-2 bg-teal-500 text-white text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center shadow">
                  {binCounts[id]}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ─── Enabled Transitions Footer ─── */}
      <div className="px-4 py-2 border-t border-white/5 flex items-center gap-2 flex-wrap">
        <span className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">
          Enabled →
        </span>
        {enabledTransitions.length === 0 ? (
          <span className="text-[10px] text-gray-600 italic">none</span>
        ) : (
          enabledTransitions.map((id) => (
            <span
              key={id}
              className={clsx(
                'text-[10px] px-2 py-0.5 rounded-full font-medium',
                OUTPUT_SET.has(id)
                  ? 'bg-teal-500/15 text-teal-400'
                  : 'bg-accent-green/15 text-accent-green',
              )}
            >
              {stations[id].label}
            </span>
          ))
        )}
      </div>
    </div>
  );
}
