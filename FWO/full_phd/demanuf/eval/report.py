"""Report generation — Markdown + CSV output for evaluation results.

Generates:
  - eval_summary.md  — fillable tables matching PAPER_5 §4
  - results.csv      — flat CSV of all EvalMetrics rows
  - results.json     — JSON array
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .metrics import (
    EvalMetrics,
    AggregatedMetric,
    aggregate,
    classify_envelope,
    EnvelopeThresholds,
    _METRIC_NAMES,
)


# ── CSV export ────────────────────────────────────────────────────────
def to_csv(results: Sequence[EvalMetrics]) -> str:
    """Return CSV string of all EvalMetrics rows."""
    if not results:
        return ""
    buf = io.StringIO()
    fieldnames = list(results[0].as_dict().keys())
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for r in results:
        writer.writerow(r.as_dict())
    return buf.getvalue()


# ── JSON export ───────────────────────────────────────────────────────
def to_json(results: Sequence[EvalMetrics], indent: int = 2) -> str:
    """Return JSON array of all EvalMetrics rows."""
    return json.dumps([r.as_dict() for r in results], indent=indent)


# ── Markdown tables ───────────────────────────────────────────────────
def _fmt(v: float, decimals: int = 4) -> str:
    return f"{v:.{decimals}f}"


def _agg_cell(agg: AggregatedMetric) -> str:
    """Format as mean [ci_lower, ci_upper]."""
    return f"{_fmt(agg.mean)} [{_fmt(agg.ci_lower)}, {_fmt(agg.ci_upper)}]"


def _build_safety_table(
    grouped: Dict[str, Dict[str, AggregatedMetric]],
) -> str:
    """Table 1: Safety outcomes by ablation."""
    lines = [
        "### Table 1 — Safety Outcomes",
        "",
        "| Ablation | CVR | IVR | DFR |",
        "|----------|-----|-----|-----|",
    ]
    for aid in sorted(grouped.keys()):
        agg = grouped[aid]
        lines.append(
            f"| {aid} | {_agg_cell(agg['cvr'])} | {_agg_cell(agg['ivr'])} | {_agg_cell(agg['dfr'])} |"
        )
    return "\n".join(lines)


def _build_operational_table(
    grouped: Dict[str, Dict[str, AggregatedMetric]],
) -> str:
    """Table 3: Operational KPIs by ablation."""
    lines = [
        "### Table 3 — Operational KPIs",
        "",
        "| Ablation | TP | CT | BT | RR | ERT |",
        "|----------|-----|-----|-----|-----|-----|",
    ]
    for aid in sorted(grouped.keys()):
        agg = grouped[aid]
        lines.append(
            f"| {aid} | {_agg_cell(agg['tp'])} | {_agg_cell(agg['ct'])} "
            f"| {_agg_cell(agg['bt'])} | {_agg_cell(agg['rr'])} "
            f"| {_agg_cell(agg['ert'])} |"
        )
    return "\n".join(lines)


def _build_uncertainty_table(
    grouped: Dict[str, Dict[str, AggregatedMetric]],
) -> str:
    """Table: Uncertainty management metrics."""
    lines = [
        "### Table — Uncertainty Management",
        "",
        "| Ablation | EF | IE | CQ | FPR |",
        "|----------|-----|-----|-----|-----|",
    ]
    for aid in sorted(grouped.keys()):
        agg = grouped[aid]
        lines.append(
            f"| {aid} | {_agg_cell(agg['ef'])} | {_agg_cell(agg['ie'])} "
            f"| {_agg_cell(agg['cq'])} | {_agg_cell(agg['fpr'])} |"
        )
    return "\n".join(lines)


def _build_overhead_table(
    grouped: Dict[str, Dict[str, AggregatedMetric]],
) -> str:
    """Table: Overhead metrics."""
    lines = [
        "### Table — Overhead / Deployability",
        "",
        "| Ablation | DL | SC | CL |",
        "|----------|-----|-----|-----|",
    ]
    for aid in sorted(grouped.keys()):
        agg = grouped[aid]
        lines.append(
            f"| {aid} | {_agg_cell(agg['dl'])} | {_agg_cell(agg['sc'])} "
            f"| {_agg_cell(agg['cl'])} |"
        )
    return "\n".join(lines)


# ── Full report ───────────────────────────────────────────────────────
def generate_report(
    results: List[EvalMetrics],
    thresholds: Optional[EnvelopeThresholds] = None,
    n_boot: int = 2000,
) -> str:
    """Generate eval_summary.md content from a list of EvalMetrics."""
    # Group by ablation_id
    by_aid: Dict[str, List[EvalMetrics]] = {}
    for r in results:
        by_aid.setdefault(r.ablation_id, []).append(r)

    grouped_agg: Dict[str, Dict[str, AggregatedMetric]] = {}
    for aid, runs in by_aid.items():
        grouped_agg[aid] = aggregate(runs, n_boot=n_boot)

    # Header
    sections: List[str] = [
        "# Evaluation Summary",
        "",
        f"Total runs: {len(results)}",
        f"Ablations: {', '.join(sorted(by_aid.keys()))}",
        f"Seeds per ablation: {min(len(v) for v in by_aid.values())} – {max(len(v) for v in by_aid.values())}",
        "",
        "---",
        "",
    ]

    # Tables
    sections.append(_build_safety_table(grouped_agg))
    sections.append("")
    sections.append(_build_operational_table(grouped_agg))
    sections.append("")
    sections.append(_build_uncertainty_table(grouped_agg))
    sections.append("")
    sections.append(_build_overhead_table(grouped_agg))
    sections.append("")

    # Envelope classification per ablation
    sections.append("### Envelope Classification")
    sections.append("")
    t = thresholds or EnvelopeThresholds()
    sections.append(f"Thresholds: τ_TP = {t.tau_tp}, τ_EF = {t.tau_ef}")
    sections.append("")
    sections.append("| Ablation | Inside Envelope |")
    sections.append("|----------|----------------|")
    for aid in sorted(grouped_agg.keys()):
        inside = classify_envelope(grouped_agg[aid], thresholds)
        sections.append(f"| {aid} | {'✓' if inside else '✗'} |")

    sections.append("")
    sections.append("---")
    sections.append("*Generated by demanuf eval harness.*")

    return "\n".join(sections)


# ── Write to disk ─────────────────────────────────────────────────────
def write_report(
    results: List[EvalMetrics],
    output_dir: str | Path,
    thresholds: Optional[EnvelopeThresholds] = None,
) -> Path:
    """Write eval_summary.md, results.csv, results.json to *output_dir*."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    (out / "eval_summary.md").write_text(
        generate_report(results, thresholds), encoding="utf-8"
    )
    (out / "results.csv").write_text(to_csv(results), encoding="utf-8")
    (out / "results.json").write_text(to_json(results), encoding="utf-8")

    return out
