// ── Run-level metrics (pure computation, no side effects) ────────────
import type {
  CompletedProduct,
  HiddenCondition,
  Hypothesis,
  StationId,
} from './types';
import { conditionToHypothesis } from './belief';

// ── Types ────────────────────────────────────────────────────────────

export interface ConfusionMatrix {
  labels: string[];
  matrix: number[][]; // matrix[trueIdx][predictedIdx] = count
}

export interface RunMetrics {
  totalProducts: number;
  totalSteps: number;

  // Accuracy
  beliefTop1Accuracy: number;

  // Calibration buckets
  calibrationBuckets: Array<{
    range: string;
    count: number;
    correctCount: number;
    accuracy: number;
  }>;

  // Rates
  abstentionRate: number;
  escalationRate: number;
  evidenceSeekingRate: number;
  unresolvedRate: number;

  // Safety
  hazardRecall: number;
  falseSafeRate: number;

  // Efficiency
  avgStepsPerProduct: number;
  avgDecisionsPerProduct: number;
  avgEvidenceRequestsPerProduct: number;

  // Bin distribution
  binDistribution: Record<string, number>;

  // Confusion matrices
  beliefConfusion: ConfusionMatrix;
  binConfusion: ConfusionMatrix;

  // Per-condition breakdown
  conditionBreakdown: Record<
    string,
    {
      count: number;
      beliefAccuracy: number;
      avgSteps: number;
      avgUncertainty: number;
      binDistribution: Record<string, number>;
      escalationRate: number;
      abstentionRate: number;
    }
  >;
}

// ── Helpers ──────────────────────────────────────────────────────────

function safeDivide(num: number, den: number, fallback = 0): number {
  return den === 0 ? fallback : num / den;
}

/** Collect the unique sorted union of string values. */
function uniqueSorted(values: string[]): string[] {
  return [...new Set(values)].sort();
}

// ── Confusion matrix builders ────────────────────────────────────────

/**
 * Build a confusion matrix between true conditions (mapped to hypothesis
 * labels) and dominant beliefs.
 */
export function buildBeliefConfusion(
  products: CompletedProduct[],
): ConfusionMatrix {
  const trueLabels = products.map((p) =>
    conditionToHypothesis(p.condition),
  );
  const predLabels = products.map((p) => p.dominantBelief.hypothesis);
  const labels = uniqueSorted([...trueLabels, ...predLabels]);

  const idx = new Map<string, number>();
  labels.forEach((l, i) => idx.set(l, i));

  const n = labels.length;
  const matrix: number[][] = Array.from({ length: n }, () =>
    Array(n).fill(0),
  );
  for (let i = 0; i < products.length; i++) {
    const ti = idx.get(trueLabels[i])!;
    const pi = idx.get(predLabels[i])!;
    matrix[ti][pi]++;
  }
  return { labels, matrix };
}

/**
 * Build a confusion matrix between true conditions (hypothesis labels)
 * and the output bin each product was routed to.
 */
export function buildBinConfusion(
  products: CompletedProduct[],
): ConfusionMatrix {
  const trueLabels = products.map((p) =>
    conditionToHypothesis(p.condition),
  );
  const predLabels = products.map((p) => p.outputBin as string);
  const labels = uniqueSorted([...trueLabels, ...predLabels]);

  const idx = new Map<string, number>();
  labels.forEach((l, i) => idx.set(l, i));

  const n = labels.length;
  const matrix: number[][] = Array.from({ length: n }, () =>
    Array(n).fill(0),
  );
  for (let i = 0; i < products.length; i++) {
    const ti = idx.get(trueLabels[i])!;
    const pi = idx.get(predLabels[i])!;
    matrix[ti][pi]++;
  }
  return { labels, matrix };
}

// ── Calibration ──────────────────────────────────────────────────────

/**
 * Bin products by dominant-belief confidence into equal-width buckets
 * and compute per-bucket accuracy.
 */
export function computeCalibration(
  products: CompletedProduct[],
  bucketCount: number = 5,
): RunMetrics['calibrationBuckets'] {
  const buckets: RunMetrics['calibrationBuckets'] = [];
  const width = 1 / bucketCount;

  for (let b = 0; b < bucketCount; b++) {
    const lo = b * width;
    const hi = (b + 1) * width;
    const range = `${lo.toFixed(1)}\u2013${hi.toFixed(1)}`;

    const inBucket = products.filter((p) => {
      const c = p.dominantBelief.confidence;
      return b < bucketCount - 1 ? c >= lo && c < hi : c >= lo && c <= hi;
    });
    const correctCount = inBucket.filter((p) => p.beliefCorrect).length;

    buckets.push({
      range,
      count: inBucket.length,
      correctCount,
      accuracy: safeDivide(correctCount, inBucket.length),
    });
  }
  return buckets;
}

// ── Main entry point ─────────────────────────────────────────────────

export function computeRunMetrics(
  products: CompletedProduct[],
): RunMetrics {
  const n = products.length;

  // Total steps across all products
  const totalSteps = products.reduce((s, p) => s + p.totalSteps, 0);

  // ── Accuracy ───────────────────────────────────────────────────────
  const correctCount = products.filter((p) => p.beliefCorrect).length;
  const beliefTop1Accuracy = safeDivide(correctCount, n);

  // ── Calibration ────────────────────────────────────────────────────
  const calibrationBuckets = computeCalibration(products);

  // ── Rates ──────────────────────────────────────────────────────────
  const abstentionRate = safeDivide(
    products.filter((p) => p.abstained).length,
    n,
  );
  const escalationRate = safeDivide(
    products.filter((p) => p.escalated).length,
    n,
  );
  const evidenceSeekingRate = safeDivide(
    products.filter((p) => p.evidenceRequests > 0).length,
    n,
  );
  const unresolvedRate = safeDivide(
    products.filter((p) => p.outputBin === 'output_unresolved').length,
    n,
  );

  // ── Safety (hazard = swollen_battery) ──────────────────────────────
  const hazardous = products.filter(
    (p) => p.condition === 'swollen_battery',
  );
  const hazardRecall = safeDivide(
    hazardous.filter((p) => p.outputBin === 'output_hazardous').length,
    hazardous.length,
  );
  const falseSafeRate = safeDivide(
    hazardous.filter((p) => p.outputBin === 'output_reusable').length,
    hazardous.length,
  );

  // ── Efficiency ─────────────────────────────────────────────────────
  const avgStepsPerProduct = safeDivide(totalSteps, n);
  const avgDecisionsPerProduct = safeDivide(
    products.reduce((s, p) => s + p.decisionCount, 0),
    n,
  );
  const avgEvidenceRequestsPerProduct = safeDivide(
    products.reduce((s, p) => s + p.evidenceRequests, 0),
    n,
  );

  // ── Bin distribution ───────────────────────────────────────────────
  const binDistribution: Record<string, number> = {};
  for (const p of products) {
    binDistribution[p.outputBin] = (binDistribution[p.outputBin] ?? 0) + 1;
  }

  // ── Confusion matrices ─────────────────────────────────────────────
  const beliefConfusion = buildBeliefConfusion(products);
  const binConfusion = buildBinConfusion(products);

  // ── Per-condition breakdown ────────────────────────────────────────
  const conditionBreakdown: RunMetrics['conditionBreakdown'] = {};

  const grouped = new Map<HiddenCondition, CompletedProduct[]>();
  for (const p of products) {
    const arr = grouped.get(p.condition);
    if (arr) arr.push(p);
    else grouped.set(p.condition, [p]);
  }

  for (const [cond, group] of grouped) {
    const gc = group.length;
    const bd: Record<string, number> = {};
    for (const p of group) {
      bd[p.outputBin] = (bd[p.outputBin] ?? 0) + 1;
    }
    conditionBreakdown[cond] = {
      count: gc,
      beliefAccuracy: safeDivide(
        group.filter((p) => p.beliefCorrect).length,
        gc,
      ),
      avgSteps: safeDivide(
        group.reduce((s, p) => s + p.totalSteps, 0),
        gc,
      ),
      avgUncertainty: safeDivide(
        group.reduce((s, p) => s + p.finalUncertainty, 0),
        gc,
      ),
      binDistribution: bd,
      escalationRate: safeDivide(
        group.filter((p) => p.escalated).length,
        gc,
      ),
      abstentionRate: safeDivide(
        group.filter((p) => p.abstained).length,
        gc,
      ),
    };
  }

  return {
    totalProducts: n,
    totalSteps,
    beliefTop1Accuracy,
    calibrationBuckets,
    abstentionRate,
    escalationRate,
    evidenceSeekingRate,
    unresolvedRate,
    hazardRecall,
    falseSafeRate,
    avgStepsPerProduct,
    avgDecisionsPerProduct,
    avgEvidenceRequestsPerProduct,
    binDistribution,
    beliefConfusion,
    binConfusion,
    conditionBreakdown,
  };
}
