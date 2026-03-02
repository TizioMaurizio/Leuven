import datetime as dt
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ==== CONFIGURATION ====

# Project start date (change to your actual expected start)
project_start = dt.date(2027, 1, 1)

# Helper: convert "years from start" (e.g. 1.5 = mid-Y2) to a date
def years_to_date(years_from_start: float) -> dt.date:
    # Simple approximation: 1 year = 365 days
    days = int(years_from_start * 365)
    return project_start + dt.timedelta(days=days)

# Work packages: (label, start_in_years, end_in_years)
wp_schedule = [
    ("WP1 — Brownfield benchmark, structural uncertainty models, and evaluation platform",
     0.0, 2.0),   # Y1–Y2

    ("WP2 — Uncertainty-aware digital twin state, evidence, and trace layer",
     0.5, 3.0),   # mid-Y1–end-Y3

    ("WP3 — Learning-to-update and learning-to-ask for twin maintenance",
     1.5, 4.0),   # mid-Y2–end-Y4

    ("WP4 — Bounded semantic mediation: contract, gate, and formal assurance",
     1.0, 3.0),   # start-Y2–end-Y3

    ("WP5 — System-level safety/performance envelope, baselines, and transferable patterns",
     2.0, 4.0),   # start-Y3–end-Y4
]

# Milestones: (label, years_from_start)
milestones = [
    ("M1 (end Y1)", 1.0),
    ("M2 (mid Y2)", 1.5),
    ("M3 (end Y2)", 2.0),
    ("M4 (mid Y3)", 2.5),
    ("M5 (end Y3)", 3.0),
    ("M6 (end Y4)", 4.0),
]

# ==== BUILD DATA ====

wp_labels = []
wp_starts = []
wp_durations = []

for label, start_years, end_years in wp_schedule:
    start_date = years_to_date(start_years)
    end_date = years_to_date(end_years)
    duration = (end_date - start_date).days

    wp_labels.append(label)
    wp_starts.append(start_date)
    wp_durations.append(duration)

# Milestone dates
ms_dates = [years_to_date(y) for (_, y) in milestones]

# ==== PLOT GANTT ====

fig, ax = plt.subplots(figsize=(12, 6))

y_positions = range(len(wp_labels))

# Horizontal bars for WPs
for i, (start, duration) in enumerate(zip(wp_starts, wp_durations)):
    ax.barh(
        y=i,
        width=duration,
        left=start,
        align='center'
    )

# Y-axis labels
ax.set_yticks(list(y_positions))
ax.set_yticklabels(wp_labels)

# X-axis: time formatting
ax.xaxis_date()
ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
fig.autofmt_xdate()

# Milestones as vertical lines + labels at top
y_top = len(wp_labels) + 0.3  # slightly above the last bar
for (label, _), date in zip(milestones, ms_dates):
    ax.axvline(x=date, linestyle='--', linewidth=1)
    ax.text(date, y_top, label, rotation=90, va='bottom', ha='center')

ax.set_title("Project Gantt Chart: WPs and Milestones")
ax.set_xlabel("Time")
ax.set_ylabel("Work Packages")

plt.tight_layout()
plt.show()