import { useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import clsx from 'clsx';
import type { SimEvent } from '../sim/types';

interface EventLogProps {
  events: SimEvent[];
  maxVisible?: number;
}

function categoryColor(type: string): string {
  if (type.startsWith('item_arrived') || type.startsWith('transfer')) return 'bg-accent-blue/20 text-accent-blue';
  if (type.startsWith('inspection') || type.startsWith('observation')) return 'bg-accent-green/20 text-accent-green';
  if (type.startsWith('unscrewing') || type.includes('screw') || type.includes('adhesive')) return 'bg-accent-amber/20 text-accent-amber';
  if (type.startsWith('battery') || type.includes('battery')) return 'bg-accent-red/20 text-accent-red';
  if (type.startsWith('escalation') || type.includes('reroute_to_operator')) return 'bg-accent-purple/20 text-accent-purple';
  if (type.includes('binned') || type.includes('completed')) return 'bg-teal-500/20 text-teal-400';
  if (type.includes('reroute')) return 'bg-accent-amber/20 text-accent-amber';
  return 'bg-gray-500/20 text-gray-400';
}

function eventIcon(type: string): string {
  if (type.includes('completed') || type.includes('succeeded') || type.includes('cleared')) return '✓';
  if (type.includes('failed') || type.includes('flagged') || type.includes('detected')) return '✗';
  if (type.startsWith('observation') || type.startsWith('inspection')) return '👁';
  if (type.startsWith('transfer') || type.includes('reroute')) return '→';
  if (type.includes('battery') || type.includes('escalation')) return '⚠';
  if (type.includes('binned') || type.includes('item_completed')) return '🏁';
  return '·';
}

export default function EventLog({ events, maxVisible = 50 }: EventLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const visibleEvents = events.slice(-maxVisible);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events.length]);

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-1.5 border-b border-white/5 flex items-center justify-between">
        <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-wider">Event Log</h3>
        <span className="text-[10px] text-gray-500 font-mono">{events.length} events</span>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5 scrollbar-thin">
        <AnimatePresence initial={false}>
          {visibleEvents.map((evt, i) => (
            <motion.div
              key={`${evt.step}-${evt.type}-${i}`}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.15 }}
              className="flex items-start gap-2 py-1 px-1.5 rounded hover:bg-white/[0.03] group"
              title={evt.description}
            >
              {/* Step number */}
              <span className="text-[10px] font-mono text-gray-600 w-6 text-right shrink-0 pt-0.5">
                {evt.step}
              </span>

              {/* Event icon */}
              <span className="text-xs w-4 text-center shrink-0 pt-px">
                {eventIcon(evt.type)}
              </span>

              {/* Event type badge */}
              <span className={clsx(
                'text-[9px] px-1.5 py-0.5 rounded font-medium shrink-0 uppercase tracking-wider',
                categoryColor(evt.type),
              )}>
                {evt.type.replace(/_/g, ' ').slice(0, 18)}
              </span>

              {/* Description */}
              <span className="text-xs text-gray-400 leading-tight flex-1 min-w-0 truncate group-hover:whitespace-normal group-hover:text-gray-300">
                {evt.description}
              </span>

              {/* Observation chip */}
              {evt.observation && (
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-accent-purple/10 text-accent-purple shrink-0">
                  obs: {(evt.observation.confidence * 100).toFixed(0)}%
                </span>
              )}

              {/* Belief delta */}
              {evt.beliefDelta && (
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-accent-amber/10 text-accent-amber shrink-0">
                  Δ
                </span>
              )}
            </motion.div>
          ))}
        </AnimatePresence>

        {events.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <p className="text-xs text-gray-600 italic">No events yet</p>
          </div>
        )}
      </div>
    </div>
  );
}
