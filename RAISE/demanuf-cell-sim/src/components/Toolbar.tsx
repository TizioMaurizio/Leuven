import { useState } from 'react';
import { motion } from 'framer-motion';
import clsx from 'clsx';
import type { Scenario } from '../sim/types';

interface ToolbarProps {
  isPlaying: boolean;
  speed: number;
  currentScenario: string;
  scenarios: Scenario[];
  onPlay: () => void;
  onPause: () => void;
  onStep: () => void;
  onReset: () => void;
  onExport: () => void;
  onSpeedChange: (speed: number) => void;
  onScenarioChange: (index: number) => void;
  onSeedChange: (seed: number) => void;
  seed: number;
  step: number;
  phase: string;
  productNumber: number;
  binCounts: Record<string, number>;
  policyPreset: string;
  policyPresets: string[];
  onPolicyChange: (key: string) => void;
}

function phaseBadge(phase: string): string {
  switch (phase) {
    case 'idle': return 'bg-gray-600 text-gray-300';
    case 'running': return 'bg-accent-blue/20 text-accent-blue';
    case 'completed': return 'bg-accent-green/20 text-accent-green';
    default: return 'bg-gray-600 text-gray-400';
  }
}

const btnBase = 'rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-150 select-none flex items-center gap-1.5';
const btnPrimary = `${btnBase} bg-accent-blue/15 text-accent-blue hover:bg-accent-blue/25 active:scale-95`;
const btnSecondary = `${btnBase} bg-surface-lighter text-gray-300 hover:bg-white/10 active:scale-95`;

const BIN_ICONS: Record<string, string> = {
  output_reusable: '♻️',
  output_recoverable: '🔄',
  output_hazardous: '⚠️',
  output_unresolved: '❓',
};

export default function Toolbar({
  isPlaying, speed, currentScenario, scenarios,
  onPlay, onPause, onStep, onReset, onExport,
  onSpeedChange, onScenarioChange, onSeedChange,
  seed, step, phase, productNumber, binCounts,
  policyPreset, policyPresets, onPolicyChange,
}: ToolbarProps) {
  const [exportLabel, setExportLabel] = useState('Export');

  const handleExport = () => {
    onExport();
    setExportLabel('Copied!');
    setTimeout(() => setExportLabel('Export'), 1500);
  };
  return (
    <div className="flex items-center gap-3 px-4 py-2.5 bg-surface border-b border-white/5 flex-wrap">
      {/* ── Left: transport controls ───────────────────────────── */}
      <div className="flex items-center gap-1.5">
        {isPlaying ? (
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.92 }}
            onClick={onPause}
            className={btnPrimary}
          >
            <span className="text-sm">⏸</span> Pause
          </motion.button>
        ) : (
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.92 }}
            onClick={onPlay}
            className={clsx(btnPrimary, phase === 'completed' && 'opacity-40 pointer-events-none')}
          >
            <span className="text-sm">▶</span> Play
          </motion.button>
        )}

        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.92 }}
          onClick={onStep}
          disabled={phase === 'completed'}
          className={clsx(btnSecondary, phase === 'completed' && 'opacity-40 pointer-events-none')}
        >
          <span className="text-sm">⏭</span> Step
        </motion.button>

        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.92 }}
          onClick={onReset}
          className={btnSecondary}
        >
          <span className="text-sm">↺</span> Reset
        </motion.button>

        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.92 }}
          onClick={handleExport}
          className={btnSecondary}
          title="Copy simulation state to clipboard for LLM analysis"
        >
          <span className="text-sm">📋</span> {exportLabel}
        </motion.button>
      </div>

      {/* ── Divider ────────────────────────────────────────────── */}
      <div className="w-px h-6 bg-white/10" />

      {/* ── Center: speed / scenario / seed ─────────────────────── */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Speed */}
        <label className="flex items-center gap-2 text-xs text-gray-400">
          <span className="shrink-0">Speed</span>
          <input
            type="range"
            min={50}
            max={2000}
            step={50}
            value={speed}
            onChange={(e) => onSpeedChange(Number(e.target.value))}
            className="w-24 h-1 accent-accent-blue bg-surface-lighter rounded-full appearance-none cursor-pointer"
          />
          <span className="font-mono text-gray-500 text-[10px] w-12">{speed}ms</span>
        </label>

        {/* Scenario */}
        <select
          value={scenarios.findIndex((s) => s.name === currentScenario)}
          onChange={(e) => onScenarioChange(Number(e.target.value))}
          className="bg-surface-lighter text-gray-300 text-xs rounded-lg px-2 py-1.5 border border-white/5 focus:outline-none focus:ring-1 focus:ring-accent-blue/40"
        >
          {scenarios.map((s, i) => (
            <option key={s.name} value={i}>
              {s.name}
            </option>
          ))}
        </select>

        {/* Policy */}
        <div className="flex flex-col gap-0.5">
          <label className="text-xs text-gray-400">Policy</label>
          <select
            value={policyPreset}
            onChange={(e) => onPolicyChange(e.target.value)}
            className="bg-surface-lighter text-gray-300 text-xs rounded-lg px-2 py-1.5 border border-white/5 focus:outline-none focus:ring-1 focus:ring-accent-blue/40"
          >
            {policyPresets.map((key) => (
              <option key={key} value={key}>{key.replace(/_/g, ' ')}</option>
            ))}
          </select>
        </div>

        {/* Seed */}
        <label className="flex items-center gap-1.5 text-xs text-gray-400">
          <span>Seed</span>
          <input
            type="number"
            value={seed}
            onChange={(e) => {
              const v = parseInt(e.target.value, 10);
              if (!isNaN(v)) onSeedChange(v);
            }}
            className="w-16 bg-surface-lighter text-gray-300 text-xs rounded-lg px-2 py-1.5 border border-white/5 focus:outline-none focus:ring-1 focus:ring-accent-blue/40 font-mono text-center"
          />
        </label>
      </div>

      {/* ── Spacer ──────────────────────────────────────────────── */}
      <div className="flex-1" />

      {/* ── Right: status ───────────────────────────────────────── */}
      <div className="flex items-center gap-3 text-xs">
        <span className="px-2 py-0.5 rounded-full bg-teal-500/15 text-teal-400 text-[10px] font-semibold">
          Product #{productNumber ?? 1}
        </span>
        <div className="flex items-center gap-2 text-[10px] text-gray-400">
          {Object.entries(BIN_ICONS).map(([bin, icon]) => (
            <span key={bin} className="flex items-center gap-0.5">
              <span>{icon}</span>
              <span className="font-mono text-gray-300">{binCounts?.[bin] ?? 0}</span>
            </span>
          ))}
        </div>
        <span className="font-mono text-gray-500">Step <span className="text-gray-300">{step}</span></span>
        <span className={clsx('px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase', phaseBadge(phase))}>
          {phase}
        </span>
      </div>
    </div>
  );
}
