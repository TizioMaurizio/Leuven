import { useState, useRef, useEffect, useCallback } from 'react';
import { SimEngine } from '../sim/engine';
import { SCENARIOS } from '../sim/scenarios';
import type { SimulationSnapshot, Scenario } from '../sim/types';

export function useSimulation() {
  const [scenarioIndex, setScenarioIndex] = useState(0);
  const [seed, setSeed] = useState(42);
  const engineRef = useRef<SimEngine>(new SimEngine(42, SCENARIOS[0]));
  const [snapshot, setSnapshot] = useState<SimulationSnapshot>(
    () => engineRef.current.getSnapshot(),
  );
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(500);

  // Auto-play interval
  useEffect(() => {
    if (!isPlaying || snapshot.phase === 'completed') return;
    const interval = setInterval(() => {
      const next = engineRef.current.step();
      setSnapshot(next);
      if (next.phase === 'completed') setIsPlaying(false);
    }, speed);
    return () => clearInterval(interval);
  }, [isPlaying, speed, snapshot.phase]);

  const play = useCallback(() => {
    if (snapshot.phase !== 'completed') setIsPlaying(true);
  }, [snapshot.phase]);

  const pause = useCallback(() => setIsPlaying(false), []);

  const step = useCallback(() => {
    if (snapshot.phase === 'completed') return;
    setSnapshot(engineRef.current.step());
  }, [snapshot.phase]);

  const reset = useCallback(() => {
    setIsPlaying(false);
    engineRef.current.reset(seed, SCENARIOS[scenarioIndex]);
    setSnapshot(engineRef.current.getSnapshot());
  }, [seed, scenarioIndex]);

  const changeScenario = useCallback((index: number) => {
    setScenarioIndex(index);
    setIsPlaying(false);
    engineRef.current.reset(seed, SCENARIOS[index]);
    setSnapshot(engineRef.current.getSnapshot());
  }, [seed]);

  const changeSeed = useCallback((newSeed: number) => {
    setSeed(newSeed);
    setIsPlaying(false);
    engineRef.current.reset(newSeed, SCENARIOS[scenarioIndex]);
    setSnapshot(engineRef.current.getSnapshot());
  }, [scenarioIndex]);

  return {
    snapshot,
    isPlaying,
    speed,
    seed,
    scenarioIndex,
    scenarios: SCENARIOS as Scenario[],
    play,
    pause,
    step,
    reset,
    setSpeed,
    setScenarioIndex: changeScenario,
    setSeed: changeSeed,
  };
}
