#!/usr/bin/env python3
"""
Simulation test suite and report generator for demanuf-cell-sim.

Usage:
    python tests/test_simulation.py                    # run all tests + generate report
    python tests/test_simulation.py --report-only      # just generate report from cached traces
    python tests/test_simulation.py --seeds 10         # run with 10 seeds per scenario
    python -m pytest tests/test_simulation.py -v       # run as pytest suite
"""

import json
import math
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Any

# ── Trace acquisition ──────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRACE_CACHE = PROJECT_ROOT / "tests" / "trace_cache.json"
REPORT_OUTPUT = PROJECT_ROOT / "tests" / "report.txt"

CONDITION_TO_HYPOTHESIS = {
    "normal": "normal_path",
    "hidden_screws": "hidden_fastener",
    "strong_adhesive": "adhesive_issue",
    "swollen_battery": "battery_hazard",
    "missing_component": "missing_parts",
    "casing_damage": "structural_damage",
    "easy_disassembly": "easy_case",
}

OUTPUT_BINS = {
    "output_reusable",
    "output_recoverable",
    "output_hazardous",
    "output_unresolved",
}

VALID_STATIONS = {
    "input_buffer",
    "conveyor",
    "inspection",
    "unscrewing",
    "battery_check",
    "manual_escalation",
    "output_reusable",
    "output_recoverable",
    "output_hazardous",
    "output_unresolved",
}


def run_headless(seeds: int = 5) -> dict:
    """Invoke the Node.js headless runner and return parsed JSON."""
    cmd = ["npx", "tsx", "scripts/headless.ts", "--all", "--seeds", str(seeds)]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        shell=(os.name == "nt"),  # Windows needs shell=True for npx
    )
    if result.returncode != 0:
        raise RuntimeError(f"Headless runner failed:\n{result.stderr}")
    data = json.loads(result.stdout)
    # Cache for --report-only mode
    TRACE_CACHE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def load_traces(seeds: int = 5, use_cache: bool = False) -> dict:
    """Load traces from cache or run headless."""
    if use_cache and TRACE_CACHE.exists():
        return json.loads(TRACE_CACHE.read_text(encoding="utf-8"))
    return run_headless(seeds)


# ── Test result accumulator ────────────────────────────────────────────


class TestResults:
    """Accumulates test results for the report."""

    __test__ = False  # prevent pytest collection

    def __init__(self):
        self.passed: list[tuple[str, str]] = []
        self.failed: list[tuple[str, str]] = []
        self.warnings: list[str] = []
        self.stats: dict[str, Any] = {}

    def record(self, name: str, passed: bool, detail: str = ""):
        if passed:
            self.passed.append((name, detail))
        else:
            self.failed.append((name, detail))

    def warn(self, msg: str):
        self.warnings.append(msg)


# ── 1. Completion tests ────────────────────────────────────────────────


def check_all_runs_complete(traces: dict, results: TestResults):
    """Every run reaches completed=true."""
    runs = traces["runs"]
    incomplete = [
        f"{r['scenario']['name']}@seed={r['seed']}"
        for r in runs
        if not r["completed"]
    ]
    results.record(
        "all_runs_complete",
        len(incomplete) == 0,
        f"{len(incomplete)} incomplete: {', '.join(incomplete[:5])}"
        if incomplete
        else f"All {len(runs)} runs completed",
    )


def check_all_runs_reach_output_bin(traces: dict, results: TestResults):
    """Every completed run has a valid outputBin."""
    runs = [r for r in traces["runs"] if r["completed"]]
    bad = []
    for r in runs:
        ob = r.get("outputBin")
        if ob is None or ob not in OUTPUT_BINS:
            bad.append(
                f"{r['scenario']['name']}@seed={r['seed']} bin={ob}"
            )
    results.record(
        "all_runs_reach_output_bin",
        len(bad) == 0,
        f"{len(bad)} invalid bins: {', '.join(bad[:5])}"
        if bad
        else f"All {len(runs)} completed runs have valid output bins",
    )


def check_step_count_reasonable(traces: dict, results: TestResults):
    """No run exceeds 100 steps (runaway check)."""
    runs = traces["runs"]
    runaway = [
        f"{r['scenario']['name']}@seed={r['seed']} steps={r['totalSteps']}"
        for r in runs
        if r["totalSteps"] > 100
    ]
    results.record(
        "step_count_reasonable",
        len(runaway) == 0,
        f"{len(runaway)} runaways: {', '.join(runaway[:5])}"
        if runaway
        else f"All runs within 100 steps (max={max(r['totalSteps'] for r in runs)})",
    )


# ── 2. Event ordering / DES integrity ─────────────────────────────────


def check_events_monotonically_ordered(traces: dict, results: TestResults):
    """Event step numbers are non-decreasing within each run."""
    violations = []
    for r in traces["runs"]:
        events = r["events"]
        for i in range(1, len(events)):
            if events[i]["step"] < events[i - 1]["step"]:
                violations.append(
                    f"{r['scenario']['name']}@seed={r['seed']} "
                    f"step {events[i-1]['step']}→{events[i]['step']}"
                )
                break
    results.record(
        "events_monotonically_ordered",
        len(violations) == 0,
        f"{len(violations)} violations: {', '.join(violations[:5])}"
        if violations
        else "All event sequences monotonically ordered",
    )


def check_first_event_is_arrival(traces: dict, results: TestResults):
    """Every run starts with 'item_arrived'."""
    bad = []
    for r in traces["runs"]:
        if not r["events"]:
            bad.append(f"{r['scenario']['name']}@seed={r['seed']} (no events)")
        elif r["events"][0]["type"] != "item_arrived":
            bad.append(
                f"{r['scenario']['name']}@seed={r['seed']} "
                f"first={r['events'][0]['type']}"
            )
    results.record(
        "first_event_is_arrival",
        len(bad) == 0,
        f"{len(bad)} bad starts: {', '.join(bad[:5])}"
        if bad
        else "All runs start with item_arrived",
    )


def check_last_events_are_completion(traces: dict, results: TestResults):
    """Completed runs end with 'item_binned' and 'item_completed'."""
    bad = []
    for r in traces["runs"]:
        if not r["completed"]:
            continue
        events = r["events"]
        if len(events) < 2:
            bad.append(f"{r['scenario']['name']}@seed={r['seed']} (too few events)")
            continue
        last_types = [e["type"] for e in events[-2:]]
        # Expect item_binned then item_completed as the last two events
        if "item_binned" not in last_types or "item_completed" not in last_types:
            bad.append(
                f"{r['scenario']['name']}@seed={r['seed']} "
                f"last2={last_types}"
            )
    results.record(
        "last_events_are_completion",
        len(bad) == 0,
        f"{len(bad)} bad endings: {', '.join(str(b) for b in bad[:5])}"
        if bad
        else "All completed runs end with item_binned + item_completed",
    )


def check_stations_are_valid(traces: dict, results: TestResults):
    """All station IDs in events and visits are from the valid set."""
    invalid = set()
    for r in traces["runs"]:
        for e in r["events"]:
            st = e.get("station")
            if st and st not in VALID_STATIONS:
                invalid.add(st)
        for v in r["stationVisits"]:
            st = v.get("station")
            if st and st not in VALID_STATIONS:
                invalid.add(st)
    results.record(
        "stations_are_valid",
        len(invalid) == 0,
        f"Unknown stations: {invalid}" if invalid else "All station IDs valid",
    )


# ── 3. Station flow integrity ─────────────────────────────────────────


def check_station_visits_cover_path(traces: dict, results: TestResults):
    """Every run visits input_buffer, conveyor, inspection, and ≥1 output bin."""
    required = {"input_buffer", "conveyor", "inspection"}
    bad = []
    for r in traces["runs"]:
        visited = {v["station"] for v in r["stationVisits"]}
        missing_required = required - visited
        has_output = bool(visited & OUTPUT_BINS)
        if missing_required or (r["completed"] and not has_output):
            detail_parts = []
            if missing_required:
                detail_parts.append(f"missing={missing_required}")
            if r["completed"] and not has_output:
                detail_parts.append("no output bin visited")
            bad.append(
                f"{r['scenario']['name']}@seed={r['seed']} {'; '.join(detail_parts)}"
            )
    results.record(
        "station_visits_cover_path",
        len(bad) == 0,
        f"{len(bad)} path gaps: {', '.join(bad[:5])}"
        if bad
        else "All runs cover required station path",
    )


def check_no_duplicate_consecutive_visits(traces: dict, results: TestResults):
    """No station appears twice consecutively (except unscrewing retry)."""
    bad = []
    for r in traces["runs"]:
        visits = r["stationVisits"]
        for i in range(1, len(visits)):
            if (
                visits[i]["station"] == visits[i - 1]["station"]
                and visits[i]["station"] != "unscrewing"
            ):
                bad.append(
                    f"{r['scenario']['name']}@seed={r['seed']} "
                    f"dup={visits[i]['station']}"
                )
                break
    results.record(
        "no_duplicate_consecutive_visits",
        len(bad) == 0,
        f"{len(bad)} duplicates: {', '.join(bad[:5])}"
        if bad
        else "No invalid consecutive duplicate station visits",
    )


def check_item_arrives_before_processing(traces: dict, results: TestResults):
    """item_arrived occurs before any processing event."""
    bad = []
    for r in traces["runs"]:
        arrival_step = None
        for e in r["events"]:
            if e["type"] == "item_arrived":
                arrival_step = e["step"]
                break
        if arrival_step is None:
            bad.append(f"{r['scenario']['name']}@seed={r['seed']} no arrival event")
            continue
        # Check that no processing event precedes arrival
        processing_types = {
            "processing_started",
            "processing_completed",
            "observation",
            "transfer_started",
            "transfer_completed",
        }
        for e in r["events"]:
            if e["type"] in processing_types and e["step"] < arrival_step:
                bad.append(
                    f"{r['scenario']['name']}@seed={r['seed']} "
                    f"{e['type']}@step={e['step']} before arrival@step={arrival_step}"
                )
                break
    results.record(
        "item_arrives_before_processing",
        len(bad) == 0,
        f"{len(bad)} violations: {', '.join(bad[:5])}"
        if bad
        else "All processing events occur after item arrival",
    )


# ── 4. Belief model tests ─────────────────────────────────────────────


def check_beliefs_are_normalized(traces: dict, results: TestResults):
    """In every belief snapshot, beliefs sum to ~1.0 (±0.01)."""
    violations = []
    for r in traces["runs"]:
        for bh in r["beliefHistory"]:
            total = sum(bh["beliefs"].values())
            if abs(total - 1.0) > 0.01:
                violations.append(
                    f"{r['scenario']['name']}@seed={r['seed']} "
                    f"step={bh['step']} sum={total:.4f}"
                )
                break  # one per run is enough
        # Also check finalBelief
        total = sum(r["finalBelief"]["beliefs"].values())
        if abs(total - 1.0) > 0.01:
            violations.append(
                f"{r['scenario']['name']}@seed={r['seed']} "
                f"final sum={total:.4f}"
            )
    results.record(
        "beliefs_are_normalized",
        len(violations) == 0,
        f"{len(violations)} unnormalized: {', '.join(violations[:5])}"
        if violations
        else "All belief snapshots sum to ~1.0",
    )


def check_beliefs_never_zero(traces: dict, results: TestResults):
    """No belief goes to exactly 0.0 (floor enforcement)."""
    violations = []
    for r in traces["runs"]:
        for bh in r["beliefHistory"]:
            zeros = [k for k, v in bh["beliefs"].items() if v == 0.0]
            if zeros:
                violations.append(
                    f"{r['scenario']['name']}@seed={r['seed']} "
                    f"step={bh['step']} zeros={zeros}"
                )
                break
        # Check final
        zeros = [k for k, v in r["finalBelief"]["beliefs"].items() if v == 0.0]
        if zeros:
            violations.append(
                f"{r['scenario']['name']}@seed={r['seed']} "
                f"final zeros={zeros}"
            )
    results.record(
        "beliefs_never_zero",
        len(violations) == 0,
        f"{len(violations)} zero-belief violations: {', '.join(violations[:5])}"
        if violations
        else "No belief ever reaches exactly 0.0",
    )


def check_uncertainty_decreases_on_average(traces: dict, results: TestResults):
    """Across all runs, average final uncertainty < average initial uncertainty."""
    initials = []
    finals = []
    for r in traces["runs"]:
        if r["beliefHistory"]:
            initials.append(r["beliefHistory"][0]["uncertainty"])
        finals.append(r["finalBelief"]["uncertainty"])
    if not initials:
        results.record(
            "uncertainty_decreases_on_average",
            False,
            "No belief history available",
        )
        return
    avg_init = sum(initials) / len(initials)
    avg_final = sum(finals) / len(finals)
    passed = avg_final < avg_init
    results.record(
        "uncertainty_decreases_on_average",
        passed,
        f"avg initial={avg_init:.3f} → avg final={avg_final:.3f} "
        f"({'decreased' if passed else 'NOT decreased'})",
    )


def check_uncertainty_in_range(traces: dict, results: TestResults):
    """All uncertainty values are in [0, 1]."""
    violations = []
    for r in traces["runs"]:
        for bh in r["beliefHistory"]:
            u = bh["uncertainty"]
            if u < 0.0 or u > 1.0:
                violations.append(
                    f"{r['scenario']['name']}@seed={r['seed']} "
                    f"step={bh['step']} uncertainty={u}"
                )
                break
        u = r["finalBelief"]["uncertainty"]
        if u < 0.0 or u > 1.0:
            violations.append(
                f"{r['scenario']['name']}@seed={r['seed']} "
                f"final uncertainty={u}"
            )
    results.record(
        "uncertainty_in_range",
        len(violations) == 0,
        f"{len(violations)} out-of-range: {', '.join(violations[:5])}"
        if violations
        else "All uncertainty values in [0, 1]",
    )


# ── 5. Belief accuracy tests ──────────────────────────────────────────


def check_dominant_belief_matches_truth(traces: dict, results: TestResults):
    """For completed runs, dominant final hypothesis matches true condition ≥50%."""
    completed = [r for r in traces["runs"] if r["completed"]]
    if not completed:
        results.record("dominant_belief_matches_truth", False, "No completed runs")
        return
    correct = 0
    for r in completed:
        true_hyp = CONDITION_TO_HYPOTHESIS.get(r["product"]["condition"])
        if not true_hyp:
            continue
        best = max(r["finalBelief"]["beliefs"], key=r["finalBelief"]["beliefs"].get)
        if best == true_hyp:
            correct += 1
    rate = correct / len(completed)
    passed = rate >= 0.50
    detail = f"{correct}/{len(completed)} ({100*rate:.1f}%) dominant beliefs match truth"
    if not passed:
        results.warn(
            f"Belief accuracy below 50%: {detail}"
        )
    results.record("dominant_belief_matches_truth", passed, detail)


def check_hazard_detection(traces: dict, results: TestResults):
    """For swollen_battery products, battery_hazard belief > 0.3 in ≥60% of runs."""
    hazard_runs = [
        r
        for r in traces["runs"]
        if r["product"]["condition"] == "swollen_battery" and r["completed"]
    ]
    if not hazard_runs:
        results.warn("No swollen_battery runs to test hazard detection")
        results.record("hazard_detection", True, "Skipped: no swollen_battery runs")
        return
    detected = sum(
        1
        for r in hazard_runs
        if r["finalBelief"]["beliefs"].get("battery_hazard", 0) > 0.3
    )
    rate = detected / len(hazard_runs)
    passed = rate >= 0.60
    detail = (
        f"{detected}/{len(hazard_runs)} ({100*rate:.1f}%) "
        f"swollen_battery runs have battery_hazard > 0.3"
    )
    if not passed:
        results.warn(f"Hazard detection below 60%: {detail}")
    results.record("hazard_detection", passed, detail)


def check_easy_detection(traces: dict, results: TestResults):
    """For easy_disassembly products, easy_case or normal_path dominate ≥50%."""
    easy_runs = [
        r
        for r in traces["runs"]
        if r["product"]["condition"] == "easy_disassembly" and r["completed"]
    ]
    if not easy_runs:
        results.warn("No easy_disassembly runs to test easy detection")
        results.record("easy_detection", True, "Skipped: no easy_disassembly runs")
        return
    detected = 0
    for r in easy_runs:
        best = max(r["finalBelief"]["beliefs"], key=r["finalBelief"]["beliefs"].get)
        if best in ("easy_case", "normal_path"):
            detected += 1
    rate = detected / len(easy_runs)
    passed = rate >= 0.50
    detail = (
        f"{detected}/{len(easy_runs)} ({100*rate:.1f}%) "
        f"easy_disassembly runs have easy_case or normal_path dominant"
    )
    if not passed:
        results.warn(f"Easy detection below 50%: {detail}")
    results.record("easy_detection", passed, detail)


# ── 6. Policy / routing tests ─────────────────────────────────────────


def check_hazardous_products_routed_correctly(traces: dict, results: TestResults):
    """Swollen battery products mostly go to output_hazardous (≥60%)."""
    hazard_runs = [
        r
        for r in traces["runs"]
        if r["product"]["condition"] == "swollen_battery" and r["completed"]
    ]
    if not hazard_runs:
        results.warn("No swollen_battery runs to test routing")
        results.record(
            "hazardous_products_routed_correctly",
            True,
            "Skipped: no swollen_battery runs",
        )
        return
    correct_bin = sum(
        1 for r in hazard_runs if r["outputBin"] == "output_hazardous"
    )
    rate = correct_bin / len(hazard_runs)
    passed = rate >= 0.60
    detail = (
        f"{correct_bin}/{len(hazard_runs)} ({100*rate:.1f}%) "
        f"swollen_battery → output_hazardous"
    )
    if not passed:
        results.warn(f"Hazardous routing below 60%: {detail}")
    results.record("hazardous_products_routed_correctly", passed, detail)


def check_normal_products_not_hazardous(traces: dict, results: TestResults):
    """Normal and easy products never go to output_hazardous."""
    safe_conditions = {"normal", "easy_disassembly"}
    bad = []
    for r in traces["runs"]:
        if (
            r["product"]["condition"] in safe_conditions
            and r["completed"]
            and r["outputBin"] == "output_hazardous"
        ):
            bad.append(
                f"{r['scenario']['name']}@seed={r['seed']} "
                f"condition={r['product']['condition']}"
            )
    results.record(
        "normal_products_not_hazardous",
        len(bad) == 0,
        f"{len(bad)} misrouted to hazardous: {', '.join(bad[:5])}"
        if bad
        else "No normal/easy products routed to output_hazardous",
    )


def check_policy_decisions_have_reasons(traces: dict, results: TestResults):
    """Every policy decision has a non-empty reason string."""
    bad = []
    total = 0
    for r in traces["runs"]:
        for pd in r["policyDecisions"]:
            total += 1
            reason = pd.get("reason", "")
            if not reason or not reason.strip():
                bad.append(
                    f"{r['scenario']['name']}@seed={r['seed']} "
                    f"step={pd['step']} action={pd['action']}"
                )
    results.record(
        "policy_decisions_have_reasons",
        len(bad) == 0,
        f"{len(bad)}/{total} decisions lack reasons: {', '.join(bad[:5])}"
        if bad
        else f"All {total} policy decisions have reasons",
    )


# ── 7. Observation generation tests ───────────────────────────────────


def check_observations_generated(traces: dict, results: TestResults):
    """Every run produces at least 1 observation."""
    bad = []
    for r in traces["runs"]:
        if len(r["observations"]) == 0:
            bad.append(f"{r['scenario']['name']}@seed={r['seed']}")
    results.record(
        "observations_generated",
        len(bad) == 0,
        f"{len(bad)} runs with no observations: {', '.join(bad[:5])}"
        if bad
        else f"All runs produced observations (min={min(len(r['observations']) for r in traces['runs'])})",
    )


def check_observation_confidence_in_range(traces: dict, results: TestResults):
    """All observation confidences are in (0, 1]."""
    bad = []
    for r in traces["runs"]:
        for obs in r["observations"]:
            c = obs["confidence"]
            if c <= 0.0 or c > 1.0:
                bad.append(
                    f"{r['scenario']['name']}@seed={r['seed']} "
                    f"step={obs['step']} confidence={c}"
                )
    results.record(
        "observation_confidence_in_range",
        len(bad) == 0,
        f"{len(bad)} out-of-range confidences: {', '.join(bad[:5])}"
        if bad
        else "All observation confidences in (0, 1]",
    )


def check_inspection_generates_observations(traces: dict, results: TestResults):
    """If inspection is visited, at least one observation comes from inspection."""
    bad = []
    for r in traces["runs"]:
        visited_inspection = any(
            v["station"] == "inspection" for v in r["stationVisits"]
        )
        if not visited_inspection:
            continue
        has_inspection_obs = any(
            obs["station"] == "inspection" for obs in r["observations"]
        )
        if not has_inspection_obs:
            bad.append(f"{r['scenario']['name']}@seed={r['seed']}")
    results.record(
        "inspection_generates_observations",
        len(bad) == 0,
        f"{len(bad)} runs visited inspection without observations: {', '.join(bad[:5])}"
        if bad
        else "All inspection visits produced observations",
    )


# ── 8. Reproducibility tests ──────────────────────────────────────────


def check_same_seed_same_result(traces: dict, results: TestResults):
    """Warning: if same scenario+seed appears twice, outputs should be identical."""
    seen: dict[str, dict] = {}
    mismatches = []
    for r in traces["runs"]:
        key = f"{r['scenario']['name']}|seed={r['seed']}"
        if key in seen:
            prev = seen[key]
            if (
                prev["totalSteps"] != r["totalSteps"]
                or prev["outputBin"] != r["outputBin"]
                or prev["completed"] != r["completed"]
            ):
                mismatches.append(key)
        else:
            seen[key] = r
    if mismatches:
        results.warn(
            f"Reproducibility: {len(mismatches)} scenario+seed combos produced "
            f"different results: {', '.join(mismatches[:5])}"
        )
    results.record(
        "same_seed_same_result",
        len(mismatches) == 0,
        f"{len(mismatches)} mismatches"
        if mismatches
        else f"No duplicate scenario+seed combos found (or all matched)",
    )


# ── Report generation ─────────────────────────────────────────────────


def generate_report(traces: dict, results: TestResults) -> str:
    """Generate a comprehensive text report."""
    lines = []
    lines.append("=" * 72)
    lines.append("DEMANUFACTURING CELL SIMULATION — TEST & ANALYSIS REPORT")
    lines.append("=" * 72)
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append(f"Engine version: {traces['meta']['version']}")
    lines.append(f"Total runs: {traces['meta']['totalRuns']}")
    lines.append(f"Scenarios: {', '.join(traces['meta']['scenariosUsed'])}")
    lines.append(f"Seeds: {traces['meta']['seedsUsed']}")
    lines.append("")

    # ── Test summary ──
    lines.append("-" * 72)
    lines.append("TEST SUMMARY")
    lines.append("-" * 72)
    total = len(results.passed) + len(results.failed)
    lines.append(f"Passed: {len(results.passed)}/{total}")
    lines.append(f"Failed: {len(results.failed)}/{total}")
    lines.append(f"Warnings: {len(results.warnings)}")
    lines.append("")

    if results.failed:
        lines.append("FAILURES:")
        for name, detail in results.failed:
            lines.append(f"  \u2717 {name}")
            if detail:
                lines.append(f"    {detail}")
        lines.append("")

    if results.warnings:
        lines.append("WARNINGS:")
        for w in results.warnings:
            lines.append(f"  \u26a0 {w}")
        lines.append("")

    lines.append("PASSED:")
    for name, detail in results.passed:
        lines.append(f"  \u2713 {name}")
        if detail:
            lines.append(f"    {detail}")
    lines.append("")

    # ── Per-scenario statistics ──
    lines.append("-" * 72)
    lines.append("PER-SCENARIO STATISTICS")
    lines.append("-" * 72)

    by_scenario: dict[str, list[dict]] = {}
    for run in traces["runs"]:
        name = run["scenario"]["name"]
        by_scenario.setdefault(name, []).append(run)

    for name, runs in sorted(by_scenario.items()):
        lines.append(f"\n  {name} ({len(runs)} runs)")
        lines.append(f"  Condition: {runs[0]['scenario']['condition']}")

        steps = [r["totalSteps"] for r in runs]
        lines.append(
            f"  Steps: avg={sum(steps)/len(steps):.1f}, "
            f"min={min(steps)}, max={max(steps)}"
        )

        completed = sum(1 for r in runs if r["completed"])
        lines.append(f"  Completed: {completed}/{len(runs)}")

        bins: dict[str, int] = {}
        for r in runs:
            b = r["outputBin"] or "none"
            bins[b] = bins.get(b, 0) + 1
        lines.append(f"  Output bins: {bins}")

        # Belief accuracy
        correct = 0
        testable = 0
        for r in runs:
            true_hyp = CONDITION_TO_HYPOTHESIS.get(r["product"]["condition"])
            if true_hyp:
                testable += 1
                best_hyp = max(
                    r["finalBelief"]["beliefs"],
                    key=r["finalBelief"]["beliefs"].get,
                )
                if best_hyp == true_hyp:
                    correct += 1
        lines.append(
            f"  Belief accuracy (dominant matches truth): {correct}/{testable}"
        )

        uncertainties = [r["finalBelief"]["uncertainty"] for r in runs]
        lines.append(
            f"  Final uncertainty: avg={sum(uncertainties)/len(uncertainties):.3f}"
        )

        obs_counts = [len(r["observations"]) for r in runs]
        lines.append(
            f"  Observations: avg={sum(obs_counts)/len(obs_counts):.1f}"
        )

    # ── Global statistics ──
    lines.append("")
    lines.append("-" * 72)
    lines.append("GLOBAL STATISTICS")
    lines.append("-" * 72)

    all_runs = traces["runs"]
    all_steps = [r["totalSteps"] for r in all_runs]
    all_unc_initial = [
        r["beliefHistory"][0]["uncertainty"]
        for r in all_runs
        if r["beliefHistory"]
    ]
    all_unc_final = [r["finalBelief"]["uncertainty"] for r in all_runs]
    all_obs = [len(r["observations"]) for r in all_runs]

    lines.append(f"Total runs: {len(all_runs)}")
    lines.append(
        f"Completion rate: "
        f"{sum(1 for r in all_runs if r['completed'])}/{len(all_runs)}"
    )
    lines.append(f"Avg steps: {sum(all_steps)/len(all_steps):.1f}")
    lines.append(f"Avg observations per run: {sum(all_obs)/len(all_obs):.1f}")
    if all_unc_initial:
        lines.append(
            f"Avg initial uncertainty: "
            f"{sum(all_unc_initial)/len(all_unc_initial):.3f}"
        )
    lines.append(
        f"Avg final uncertainty: "
        f"{sum(all_unc_final)/len(all_unc_final):.3f}"
    )

    # Output bin distribution
    bin_counts: dict[str, int] = {}
    for r in all_runs:
        b = r["outputBin"] or "none"
        bin_counts[b] = bin_counts.get(b, 0) + 1
    lines.append(f"Output bin distribution: {bin_counts}")

    # Overall belief accuracy
    correct = 0
    testable = 0
    for r in all_runs:
        true_hyp = CONDITION_TO_HYPOTHESIS.get(r["product"]["condition"])
        if true_hyp:
            testable += 1
            best_hyp = max(
                r["finalBelief"]["beliefs"],
                key=r["finalBelief"]["beliefs"].get,
            )
            if best_hyp == true_hyp:
                correct += 1
    if testable:
        lines.append(
            f"Overall belief accuracy: "
            f"{correct}/{testable} ({100*correct/testable:.1f}%)"
        )
    else:
        lines.append("Overall belief accuracy: N/A (no testable runs)")

    # Event type frequency
    evt_freq: dict[str, int] = {}
    for r in all_runs:
        for e in r["events"]:
            evt_freq[e["type"]] = evt_freq.get(e["type"], 0) + 1
    lines.append("\nEvent type frequencies (across all runs):")
    for t, c in sorted(evt_freq.items(), key=lambda x: -x[1]):
        lines.append(f"  {t}: {c}")

    # Observation type frequency
    obs_freq: dict[str, int] = {}
    for r in all_runs:
        for obs in r["observations"]:
            obs_freq[obs["type"]] = obs_freq.get(obs["type"], 0) + 1
    if obs_freq:
        lines.append("\nObservation type frequencies (across all runs):")
        for t, c in sorted(obs_freq.items(), key=lambda x: -x[1]):
            lines.append(f"  {t}: {c}")

    # Station visit frequency
    station_freq: dict[str, int] = {}
    for r in all_runs:
        for v in r["stationVisits"]:
            station_freq[v["station"]] = station_freq.get(v["station"], 0) + 1
    lines.append("\nStation visit frequencies (across all runs):")
    for st, c in sorted(station_freq.items(), key=lambda x: -x[1]):
        lines.append(f"  {st}: {c}")

    # Policy action frequency
    action_freq: dict[str, int] = {}
    for r in all_runs:
        for pd in r["policyDecisions"]:
            action_freq[pd["action"]] = action_freq.get(pd["action"], 0) + 1
    if action_freq:
        lines.append("\nPolicy action frequencies (across all runs):")
        for a, c in sorted(action_freq.items(), key=lambda x: -x[1]):
            lines.append(f"  {a}: {c}")

    lines.append("")
    lines.append("=" * 72)
    lines.append("END OF REPORT")
    lines.append("=" * 72)

    return "\n".join(lines)


# ── Test runner ────────────────────────────────────────────────────────

ALL_TEST_FUNCTIONS = [
    check_all_runs_complete,
    check_all_runs_reach_output_bin,
    check_step_count_reasonable,
    check_events_monotonically_ordered,
    check_first_event_is_arrival,
    check_last_events_are_completion,
    check_stations_are_valid,
    check_station_visits_cover_path,
    check_no_duplicate_consecutive_visits,
    check_item_arrives_before_processing,
    check_beliefs_are_normalized,
    check_beliefs_never_zero,
    check_uncertainty_decreases_on_average,
    check_uncertainty_in_range,
    check_dominant_belief_matches_truth,
    check_hazard_detection,
    check_easy_detection,
    check_hazardous_products_routed_correctly,
    check_normal_products_not_hazardous,
    check_policy_decisions_have_reasons,
    check_observations_generated,
    check_observation_confidence_in_range,
    check_inspection_generates_observations,
    check_same_seed_same_result,
]


def run_all_tests(traces: dict) -> TestResults:
    """Run all tests and return results."""
    results = TestResults()
    for fn in ALL_TEST_FUNCTIONS:
        fn(traces, results)
    return results


# ── pytest integration ─────────────────────────────────────────────────

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def _traces():
    """Load traces once for the entire pytest session."""
    return load_traces(seeds=3, use_cache=TRACE_CACHE.exists())


def _make_pytest_test(fn):
    """Create a pytest-compatible test wrapper from a test function."""

    def wrapper(_traces):
        r = TestResults()
        fn(_traces, r)
        if r.failed:
            details = "; ".join(d for _, d in r.failed if d)
            pytest.fail(f"{fn.__name__}: {details}")

    wrapper.__name__ = f"test_pytest_{fn.__name__.removeprefix('check_')}"
    wrapper.__qualname__ = wrapper.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


# Generate a pytest test function for each test in the battery
test_pytest_all_runs_complete = _make_pytest_test(check_all_runs_complete)
test_pytest_all_runs_reach_output_bin = _make_pytest_test(check_all_runs_reach_output_bin)
test_pytest_step_count_reasonable = _make_pytest_test(check_step_count_reasonable)
test_pytest_events_monotonically_ordered = _make_pytest_test(check_events_monotonically_ordered)
test_pytest_first_event_is_arrival = _make_pytest_test(check_first_event_is_arrival)
test_pytest_last_events_are_completion = _make_pytest_test(check_last_events_are_completion)
test_pytest_stations_are_valid = _make_pytest_test(check_stations_are_valid)
test_pytest_station_visits_cover_path = _make_pytest_test(check_station_visits_cover_path)
test_pytest_no_duplicate_consecutive_visits = _make_pytest_test(check_no_duplicate_consecutive_visits)
test_pytest_item_arrives_before_processing = _make_pytest_test(check_item_arrives_before_processing)
test_pytest_beliefs_are_normalized = _make_pytest_test(check_beliefs_are_normalized)
test_pytest_beliefs_never_zero = _make_pytest_test(check_beliefs_never_zero)
test_pytest_uncertainty_decreases_on_average = _make_pytest_test(check_uncertainty_decreases_on_average)
test_pytest_uncertainty_in_range = _make_pytest_test(check_uncertainty_in_range)
test_pytest_dominant_belief_matches_truth = _make_pytest_test(check_dominant_belief_matches_truth)
test_pytest_hazard_detection = _make_pytest_test(check_hazard_detection)
test_pytest_easy_detection = _make_pytest_test(check_easy_detection)
test_pytest_hazardous_products_routed_correctly = _make_pytest_test(check_hazardous_products_routed_correctly)
test_pytest_normal_products_not_hazardous = _make_pytest_test(check_normal_products_not_hazardous)
test_pytest_policy_decisions_have_reasons = _make_pytest_test(check_policy_decisions_have_reasons)
test_pytest_observations_generated = _make_pytest_test(check_observations_generated)
test_pytest_observation_confidence_in_range = _make_pytest_test(check_observation_confidence_in_range)
test_pytest_inspection_generates_observations = _make_pytest_test(check_inspection_generates_observations)
test_pytest_same_seed_same_result = _make_pytest_test(check_same_seed_same_result)


# ── CLI entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Simulation test suite and report generator"
    )
    parser.add_argument(
        "--report-only", action="store_true", help="Use cached traces"
    )
    parser.add_argument(
        "--seeds", type=int, default=5, help="Seeds per scenario"
    )
    parser.add_argument(
        "--output", type=str, default=None, help="Report output path"
    )
    args = parser.parse_args()

    print("Loading simulation traces...")
    traces = load_traces(seeds=args.seeds, use_cache=args.report_only)
    print(f"Loaded {traces['meta']['totalRuns']} runs")

    print("Running tests...")
    results = run_all_tests(traces)

    report = generate_report(traces, results)

    output_path = Path(args.output) if args.output else REPORT_OUTPUT
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"\nReport written to: {output_path}")

    # Print summary to console
    total = len(results.passed) + len(results.failed)
    print(f"\n{'=' * 50}")
    print(
        f"Tests: {len(results.passed)}/{total} passed, "
        f"{len(results.failed)} failed, "
        f"{len(results.warnings)} warnings"
    )
    if results.failed:
        print("\nFailed tests:")
        for name, detail in results.failed:
            print(f"  \u2717 {name}: {detail}")
    print(f"{'=' * 50}")

    sys.exit(1 if results.failed else 0)
