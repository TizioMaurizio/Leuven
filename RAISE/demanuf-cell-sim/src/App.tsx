import { useState } from 'react';
import { useSimulation } from './hooks/useSimulation';
import { exportForLLM } from './sim/export';
import Toolbar from './components/Toolbar';
import DESView from './components/DESView';
import BeliefView from './components/BeliefView';
import EventLog from './components/EventLog';

export default function App() {
  const sim = useSimulation();
  const [showTrueState, setShowTrueState] = useState(false);

  const handleExport = () => {
    const md = exportForLLM(
      sim.snapshot,
      sim.scenarios[sim.scenarioIndex].name,
      sim.seed,
    );
    navigator.clipboard.writeText(md).catch(() => {});

    const blob = new Blob([md], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sim-export-step${sim.snapshot.step}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="h-screen w-screen flex flex-col bg-surface text-white overflow-hidden">
      {/* Toolbar */}
      <Toolbar
        isPlaying={sim.isPlaying}
        speed={sim.speed}
        currentScenario={sim.scenarios[sim.scenarioIndex].name}
        scenarios={sim.scenarios}
        onPlay={sim.play}
        onPause={sim.pause}
        onStep={sim.step}
        onReset={sim.reset}
        onExport={handleExport}
        onSpeedChange={sim.setSpeed}
        onScenarioChange={sim.setScenarioIndex}
        onSeedChange={sim.setSeed}
        seed={sim.seed}
        step={sim.snapshot.step}
        phase={sim.snapshot.phase}
        productNumber={sim.snapshot.productNumber ?? 1}
        binCounts={sim.snapshot.binCounts ?? {}}
      />

      {/* Main content: two panels side by side */}
      <div className="flex-1 flex min-h-0">
        {/* Left: DES View */}
        <div className="flex-1 min-w-0 overflow-auto">
          <DESView snapshot={sim.snapshot} />
        </div>

        {/* Right: Belief View */}
        <div className="w-[480px] border-l border-gray-700 overflow-auto">
          <BeliefView
            snapshot={sim.snapshot}
            showTrueState={showTrueState}
            onToggleTrueState={() => setShowTrueState(v => !v)}
          />
        </div>
      </div>

      {/* Bottom: Event Log */}
      <div className="h-56 border-t border-gray-700">
        <EventLog events={sim.snapshot.events} />
      </div>
    </div>
  );
}
