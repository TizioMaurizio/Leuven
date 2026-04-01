"""
petri_net_demo.py — Week 1, Day 7

Educational purpose:
    Visualizes the demanufacturing cell Petri net and simulates token flow.
    - Shows places (circles) with token counts.
    - Shows transitions (rectangles).
    - Simulates a sequence of transition firings and prints marking after each.
    - Checks place invariants at each step.

Usage:
    python petri_net_demo.py              # Run simulation and print markings
    python petri_net_demo.py --draw       # Also generate a Graphviz diagram

Output:
    Prints marking evolution to the terminal.
    With --draw: saves 'demanufacturing_petri_net.svg' and .png.

What to observe:
    - Token counts change as transitions fire.
    - Resource places (INSPECTOR_FREE, ROBOT_FREE) always sum to 1 (conserved).
    - SAFE_FLAG + HAZARD_FLAG = 1 (hazard boolean invariant).
    - BATT_IN + BATT_OUT = 1 (battery boolean invariant).
    - Unsafe transitions (unscrew_hazard, recycle_direct) are never fired.
"""

from collections import OrderedDict
from copy import deepcopy


# --- Petri Net Definition ---

# Places with initial marking
INITIAL_MARKING = OrderedDict([
    # Flow places
    ("Unit_In", 1),
    ("Wait_Inspect", 0),
    ("OK", 0),
    ("SUS", 0),
    ("OPEN", 0),
    ("BATT_REMOVED", 0),
    ("DONE_RECYCLE", 0),
    ("DONE_QUAR", 0),
    # Resource places
    ("INSPECTOR_FREE", 1),
    ("ROBOT_FREE", 1),
    # Status places
    ("SAFE_FLAG", 1),
    ("HAZARD_FLAG", 0),
    ("BATT_IN", 1),
    ("BATT_OUT", 0),
])

# Transitions: name -> (input_places, output_places, controllable, safe)
# input_places / output_places are dicts: {place: weight}
TRANSITIONS = OrderedDict([
    ("arrival", {
        "inputs": {"Unit_In": 1},
        "outputs": {"Wait_Inspect": 1},
        "controllable": False,
        "safe": True,
    }),
    ("inspect_ok", {
        "inputs": {"Wait_Inspect": 1, "INSPECTOR_FREE": 1},
        "outputs": {"OK": 1, "INSPECTOR_FREE": 1},
        "controllable": False,
        "safe": True,
    }),
    ("inspect_sus", {
        "inputs": {"Wait_Inspect": 1, "INSPECTOR_FREE": 1, "SAFE_FLAG": 1},
        "outputs": {"SUS": 1, "INSPECTOR_FREE": 1, "HAZARD_FLAG": 1},
        "controllable": False,
        "safe": True,
    }),
    ("unscrew_cover", {
        "inputs": {"OK": 1, "ROBOT_FREE": 1, "SAFE_FLAG": 1},
        "outputs": {"OPEN": 1, "ROBOT_FREE": 1, "SAFE_FLAG": 1},
        "controllable": True,
        "safe": True,
    }),
    ("remove_battery", {
        "inputs": {"OPEN": 1, "ROBOT_FREE": 1, "BATT_IN": 1},
        "outputs": {"BATT_REMOVED": 1, "ROBOT_FREE": 1, "BATT_OUT": 1},
        "controllable": True,
        "safe": True,
    }),
    ("route_recycle", {
        "inputs": {"BATT_REMOVED": 1},
        "outputs": {"DONE_RECYCLE": 1},
        "controllable": True,
        "safe": True,
    }),
    ("route_quarantine_ok", {
        "inputs": {"OK": 1},
        "outputs": {"DONE_QUAR": 1},
        "controllable": True,
        "safe": True,
    }),
    ("route_quarantine_sus", {
        "inputs": {"SUS": 1},
        "outputs": {"DONE_QUAR": 1},
        "controllable": True,
        "safe": True,
    }),
    ("route_quarantine_open", {
        "inputs": {"OPEN": 1},
        "outputs": {"DONE_QUAR": 1},
        "controllable": True,
        "safe": True,
    }),
    ("route_quarantine_br", {
        "inputs": {"BATT_REMOVED": 1},
        "outputs": {"DONE_QUAR": 1},
        "controllable": True,
        "safe": True,
    }),
    # Unsafe transitions (disabled by supervisor)
    ("unscrew_hazard", {
        "inputs": {"SUS": 1, "ROBOT_FREE": 1, "HAZARD_FLAG": 1},
        "outputs": {"OPEN": 1, "ROBOT_FREE": 1, "HAZARD_FLAG": 1},
        "controllable": True,
        "safe": False,  # DISABLED by supervisor (S1)
    }),
    ("recycle_direct", {
        "inputs": {"OK": 1},
        "outputs": {"DONE_RECYCLE": 1},
        "controllable": True,
        "safe": False,  # DISABLED by supervisor (S2)
    }),
])

# Place invariants to check: list of (name, {place: weight}, expected_sum)
INVARIANTS = [
    ("Inspector conservation", {"INSPECTOR_FREE": 1}, 1),
    ("Robot conservation", {"ROBOT_FREE": 1}, 1),
    ("Hazard boolean", {"SAFE_FLAG": 1, "HAZARD_FLAG": 1}, 1),
    ("Battery boolean", {"BATT_IN": 1, "BATT_OUT": 1}, 1),
]


def is_enabled(transition, marking):
    """Check if a transition is enabled at the given marking."""
    for place, weight in transition["inputs"].items():
        if marking.get(place, 0) < weight:
            return False
    return True


def fire(transition, marking):
    """Fire a transition, returning the new marking. Does not check enabling."""
    new_marking = deepcopy(marking)
    for place, weight in transition["inputs"].items():
        new_marking[place] -= weight
    for place, weight in transition["outputs"].items():
        new_marking[place] += weight
    return new_marking


def check_invariants(marking, step_label=""):
    """Check and print all place invariants."""
    all_ok = True
    for name, places, expected in INVARIANTS:
        actual = sum(marking.get(p, 0) * w for p, w in places.items())
        status = "OK" if actual == expected else "VIOLATED"
        if actual != expected:
            all_ok = False
            print(f"    {status} {name}: {actual} (expected {expected})")
    return all_ok


def print_marking(marking, step, transition_name=""):
    """Print the current marking in a readable format."""
    nonzero = {p: v for p, v in marking.items() if v > 0}
    label = f"  Step {step}"
    if transition_name:
        label += f" (fired: {transition_name})"
    print(label)
    print(f"    Tokens: {dict(nonzero)}")


def simulate(trace):
    """Simulate a sequence of transition firings."""
    marking = deepcopy(INITIAL_MARKING)

    print("\n" + "=" * 60)
    print("  Petri Net Simulation - Demanufacturing Cell")
    print("=" * 60)
    print_marking(marking, 0, "(initial)")
    check_invariants(marking)

    for i, t_name in enumerate(trace, 1):
        if t_name not in TRANSITIONS:
            print(f"\n  [!] Unknown transition: '{t_name}'")
            continue

        t = TRANSITIONS[t_name]

        if not t["safe"]:
            print(f"\n  [BLOCKED] Transition '{t_name}' is DISABLED by supervisor -- skipping.")
            continue

        if not is_enabled(t, marking):
            print(f"\n  [!] Transition '{t_name}' is NOT ENABLED at current marking -- skipping.")
            continue

        marking = fire(t, marking)
        print()
        print_marking(marking, i, t_name)
        ok = check_invariants(marking)
        if not ok:
            print("    [!] Invariant violation detected!")

    print("\n" + "-" * 60)
    print("  Simulation complete.")
    final_nonzero = {p: v for p, v in marking.items() if v > 0}
    print(f"  Final marking: {dict(final_nonzero)}")

    # Check terminal state
    if marking.get("DONE_RECYCLE", 0) > 0:
        print("  [*] Unit safely recycled.")
    elif marking.get("DONE_QUAR", 0) > 0:
        print("  [*] Unit safely quarantined.")
    else:
        print("  [!] Unit not yet in a terminal state.")


def draw_net():
    """Generate a Graphviz diagram of the Petri net."""
    try:
        from graphviz import Digraph
    except ImportError:
        print("  graphviz package not installed. Skipping diagram generation.")
        print("  Install with: pip install graphviz")
        return

    dot = Digraph(name="Demanufacturing Petri Net", format="svg", engine="dot")
    dot.attr(rankdir="LR", fontname="Helvetica", fontsize="10")

    # Places
    for place, tokens in INITIAL_MARKING.items():
        label = f"{place}\n[{tokens}]" if tokens > 0 else place
        shape = "circle"
        style = "filled" if tokens > 0 else ""
        fillcolor = "lightyellow" if tokens > 0 else "white"
        dot.node(f"p_{place}", label, shape=shape, style=style,
                 fillcolor=fillcolor, fontname="Helvetica", fontsize="8")

    # Transitions
    for t_name, t_def in TRANSITIONS.items():
        color = "black" if t_def["safe"] else "red"
        style = "filled" if t_def["safe"] else "filled"
        fillcolor = "lightblue" if t_def["safe"] else "lightcoral"
        label = t_name
        if not t_def["safe"]:
            label += "\n(DISABLED)"
        dot.node(f"t_{t_name}", label, shape="box", style=style,
                 fillcolor=fillcolor, fontname="Helvetica", fontsize="7")

        for place in t_def["inputs"]:
            dot.edge(f"p_{place}", f"t_{t_name}")
        for place in t_def["outputs"]:
            dot.edge(f"t_{t_name}", f"p_{place}")

    dot.render("demanufacturing_petri_net", cleanup=True)
    dot.format = "png"
    dot.render("demanufacturing_petri_net", cleanup=True)
    print("\nSaved: demanufacturing_petri_net.svg")
    print("Saved: demanufacturing_petri_net.png")


def main():
    import sys

    # Trace 1: Safe path -- inspect OK, open, remove battery, recycle
    print("\n--- Trace 1: OK -> open -> remove battery -> recycle ---")
    simulate([
        "arrival", "inspect_ok", "unscrew_cover", "remove_battery", "route_recycle"
    ])

    # Trace 2: Suspect path -- quarantine
    print("\n\n--- Trace 2: Suspect -> quarantine ---")
    simulate([
        "arrival", "inspect_sus", "route_quarantine_sus"
    ])

    # Trace 3: Attempt unsafe transition
    print("\n\n--- Trace 3: Attempt unsafe recycle_direct (should be blocked) ---")
    simulate([
        "arrival", "inspect_ok", "recycle_direct"
    ])

    if "--draw" in sys.argv:
        draw_net()


if __name__ == "__main__":
    main()
