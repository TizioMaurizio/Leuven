"""
supervisor_demo.py — Week 1, Day 6

Educational purpose:
    Interactive demonstration of supervisory control for the demanufacturing cell.
    - Shows the current state and which controllable events are enabled/disabled.
    - Lets you trace through event sequences and see the supervisor's decisions.
    - Blocks unsafe events with an explanation of which safety rule prevents them.

Usage:
    python supervisor_demo.py

What to observe:
    - Uncontrollable events (arrival, inspect_ok, inspect_sus) are always allowed.
    - The supervisor disables specific controllable events based on safety rules.
    - Try typing an unsafe event to see the supervisor block it.
    - Every reachable state has at least one path to a marked state (nonblocking).
"""


# --- Plant definition ---

STATES = {
    "Idle", "Intake", "Inspected_OK", "Inspected_Suspect",
    "Opened", "Battery_Removed", "Recycle_Done", "Quarantine_Done",
}

INITIAL_STATE = "Idle"
MARKED_STATES = {"Recycle_Done", "Quarantine_Done"}

CONTROLLABLE = {"unscrew_cover", "remove_battery", "route_recycle", "route_quarantine"}
UNCONTROLLABLE = {"arrival", "inspect_ok", "inspect_sus"}

# Plant transitions: (state, event) -> next_state
PLANT_TRANSITIONS = {
    ("Idle", "arrival"): "Intake",
    ("Intake", "inspect_ok"): "Inspected_OK",
    ("Intake", "inspect_sus"): "Inspected_Suspect",
    ("Inspected_OK", "unscrew_cover"): "Opened",
    ("Inspected_OK", "route_quarantine"): "Quarantine_Done",
    ("Inspected_OK", "route_recycle"): "Recycle_Done",
    ("Inspected_Suspect", "route_quarantine"): "Quarantine_Done",
    ("Inspected_Suspect", "unscrew_cover"): "Opened",
    ("Inspected_Suspect", "route_recycle"): "Recycle_Done",
    ("Opened", "remove_battery"): "Battery_Removed",
    ("Opened", "route_quarantine"): "Quarantine_Done",
    ("Opened", "route_recycle"): "Recycle_Done",
    ("Battery_Removed", "route_recycle"): "Recycle_Done",
    ("Battery_Removed", "route_quarantine"): "Quarantine_Done",
}

# --- Supervisor specification ---
# Disabled events per state with the safety rule that justifies each.

SUPERVISOR_DISABLED = {
    "Idle": {},
    "Intake": {},
    "Inspected_OK": {
        "route_recycle": "S2 -- battery not removed yet",
    },
    "Inspected_Suspect": {
        "unscrew_cover": "S1 -- must not open a suspect unit",
        "route_recycle": "S1 -- must not recycle a suspect unit",
    },
    "Opened": {
        "route_recycle": "S2 -- battery not removed yet",
    },
    "Battery_Removed": {},
    "Recycle_Done": {},
    "Quarantine_Done": {},
}


def get_enabled_events(state):
    """Return (enabled, disabled_with_reasons) for the given state."""
    plant_events = [
        ev for (s, ev), _ in PLANT_TRANSITIONS.items() if s == state
    ]
    disabled = SUPERVISOR_DISABLED.get(state, {})

    enabled = []
    disabled_info = []
    for ev in plant_events:
        if ev in disabled:
            disabled_info.append((ev, disabled[ev]))
        else:
            enabled.append(ev)
    return enabled, disabled_info


def print_state_info(state, trace):
    """Print the current state, trace history, and supervisor decision."""
    print()
    print("=" * 60)
    is_marked = state in MARKED_STATES
    marker = " [MARKED] (task complete)" if is_marked else ""
    print(f"  Current state: {state}{marker}")
    print(f"  Trace so far:  {' -> '.join(trace) if trace else '(start)'}")
    print("-" * 60)

    if is_marked:
        print("  The unit has been safely processed. Done!")
        return

    enabled, disabled = get_enabled_events(state)

    if enabled:
        print("  ENABLED events:")
        for ev in enabled:
            ev_type = "controllable" if ev in CONTROLLABLE else "uncontrollable"
            next_state = PLANT_TRANSITIONS.get((state, ev), "?")
            print(f"    [+] {ev} ({ev_type}) -> {next_state}")

    if disabled:
        print("  DISABLED events (supervisor blocks):")
        for ev, reason in disabled:
            print(f"    [-] {ev} -- {reason}")

    if not enabled:
        print("  No events available (terminal state).")


def interactive_mode():
    """Run the interactive supervisor demo."""
    print()
    print("+" + "=" * 58 + "+")
    print("|  Supervisor Demo -- Demanufacturing Cell                |")
    print("|  Type an event name to execute it.                      |")
    print("|  Type 'reset' to restart, 'quit' to exit.              |")
    print("+" + "=" * 58 + "+")

    state = INITIAL_STATE
    trace = []

    while True:
        print_state_info(state, trace)

        if state in MARKED_STATES:
            choice = input("\n  Type 'reset' to restart or 'quit' to exit: ").strip().lower()
            if choice == "quit":
                break
            state = INITIAL_STATE
            trace = []
            continue

        enabled, disabled = get_enabled_events(state)
        choice = input("\n  Enter event: ").strip().lower()

        if choice == "quit":
            break
        if choice == "reset":
            state = INITIAL_STATE
            trace = []
            continue

        # Check if the event is disabled by supervisor
        disabled_dict = SUPERVISOR_DISABLED.get(state, {})
        if choice in disabled_dict:
            print(f"\n  [BLOCKED] by supervisor: {disabled_dict[choice]}")
            print(f"     The event '{choice}' is controllable and disabled in state '{state}'.")
            continue

        # Check if the event is a valid plant transition
        next_state = PLANT_TRANSITIONS.get((state, choice))
        if next_state is None:
            print(f"\n  [!] '{choice}' is not a valid event from state '{state}'.")
            print(f"    Valid events: {', '.join(enabled)}")
            continue

        trace.append(choice)
        state = next_state


def demo_all_states():
    """Print supervisor decisions for all states (non-interactive overview)."""
    print()
    print("Supervisor rule table -- all states:")
    print("=" * 60)

    for state in [
        "Idle", "Intake", "Inspected_OK", "Inspected_Suspect",
        "Opened", "Battery_Removed", "Recycle_Done", "Quarantine_Done",
    ]:
        enabled, disabled = get_enabled_events(state)
        print(f"\n  [{state}]")
        if enabled:
            print(f"    Enabled:  {', '.join(enabled)}")
        if disabled:
            for ev, reason in disabled:
                print(f"    Disabled: {ev} -- {reason}")
        if not enabled and not disabled:
            print("    (no controllable events apply)")


def main():
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--table":
        demo_all_states()
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
