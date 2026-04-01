"""
automaton_visualizer.py — Week 1, Day 2

Educational purpose:
    Draws the demanufacturing cell plant automaton using Graphviz.
    - Initial state (Idle) is shown with an entry arrow.
    - Marked states (Recycle_Done, Quarantine_Done) are double-circled.
    - Uncontrollable events are shown in red; controllable events in blue.

Usage:
    python automaton_visualizer.py

Output:
    Saves 'demanufacturing_plant_automaton.svg' and
    'demanufacturing_plant_automaton.png' in the current directory.

What to observe:
    - The plant includes ALL physically possible transitions, even unsafe ones.
    - Red edges (uncontrollable events) cannot be disabled by a supervisor.
    - Blue edges (controllable events) are where the supervisor has authority.
"""

from graphviz import Digraph


def build_plant_automaton():
    """Build and return the Graphviz Digraph for the demanufacturing plant."""

    dot = Digraph(
        name="Demanufacturing Cell — Plant Automaton",
        format="svg",
        engine="dot",
    )
    dot.attr(rankdir="TB", fontname="Helvetica", fontsize="11")
    dot.attr("node", fontname="Helvetica", fontsize="10")
    dot.attr("edge", fontname="Helvetica", fontsize="9")

    # --- States ---
    normal_states = [
        "Idle", "Intake", "Inspected_OK", "Inspected_Suspect",
        "Opened", "Battery_Removed",
    ]
    marked_states = ["Recycle_Done", "Quarantine_Done"]

    for s in normal_states:
        dot.node(s, s, shape="ellipse")

    for s in marked_states:
        dot.node(s, s, shape="doublecircle", style="bold")

    # Invisible entry point for initial-state arrow
    dot.node("__start__", "", shape="point", width="0")
    dot.edge("__start__", "Idle")

    # --- Transitions ---
    # Format: (source, target, event, controllable?)
    transitions = [
        ("Idle", "Intake", "arrival", False),
        ("Intake", "Inspected_OK", "inspect_ok", False),
        ("Intake", "Inspected_Suspect", "inspect_sus", False),
        ("Inspected_OK", "Opened", "unscrew_cover", True),
        ("Inspected_OK", "Quarantine_Done", "route_quarantine", True),
        ("Inspected_OK", "Recycle_Done", "route_recycle", True),
        ("Inspected_Suspect", "Quarantine_Done", "route_quarantine", True),
        ("Inspected_Suspect", "Opened", "unscrew_cover", True),
        ("Inspected_Suspect", "Recycle_Done", "route_recycle", True),
        ("Opened", "Battery_Removed", "remove_battery", True),
        ("Opened", "Quarantine_Done", "route_quarantine", True),
        ("Opened", "Recycle_Done", "route_recycle", True),
        ("Battery_Removed", "Recycle_Done", "route_recycle", True),
        ("Battery_Removed", "Quarantine_Done", "route_quarantine", True),
    ]

    for src, dst, event, controllable in transitions:
        color = "blue" if controllable else "red"
        style = "solid" if controllable else "dashed"
        label = f"{event}"
        dot.edge(src, dst, label=label, color=color, style=style)

    return dot


def main():
    dot = build_plant_automaton()

    # Render SVG and PNG
    dot.render("demanufacturing_plant_automaton", cleanup=True)
    dot.format = "png"
    dot.render("demanufacturing_plant_automaton", cleanup=True)

    print("Saved: demanufacturing_plant_automaton.svg")
    print("Saved: demanufacturing_plant_automaton.png")
    print()
    print("Legend:")
    print("  Blue solid arrows  = controllable events (supervisor can disable)")
    print("  Red dashed arrows  = uncontrollable events (supervisor cannot prevent)")
    print("  Double circles     = marked states (safe completion)")
    print("  Entry arrow → Idle = initial state")


if __name__ == "__main__":
    main()
