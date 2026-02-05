import json
from pathlib import Path

import pandas as pd
import plotly.express as px


# Path to your JSON plan file
PLAN_PATH = Path("plan.json")


def load_plan(path: Path = PLAN_PATH) -> dict:
    """Load the structured PhD plan from a JSON file."""
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def build_dataframe(data: dict) -> tuple[pd.DataFrame, str]:
    """
    Convert the JSON plan into a DataFrame with concrete start/end dates.

    JSON schema expected:

    {
      "project": {
        "name": "My PhD Project",
        "start_date": "2026-10-01"   # YYYY-MM-DD
      },
      "tasks": [
        {
          "id": "WP1-1",
          "name": "Literature review",
          "work_package": "WP1 – Background and state of the art",
          "phase": "Year 1",
          "start_offset_months": 0,
          "duration_months": 6,
          "depends_on": []
        },
        ...
      ]
    }
    """
    project_name = data["project"]["name"]
    project_start = pd.to_datetime(data["project"]["start_date"])

    # Flatten tasks into a DataFrame
    df = pd.json_normalize(data["tasks"])

    # Ensure numeric types for offsets and durations
    df["start_offset_months"] = df["start_offset_months"].astype(int)
    df["duration_months"] = df["duration_months"].astype(int)

    # Compute concrete start and end dates from month offsets
    df["start"] = df["start_offset_months"].apply(
        lambda m: project_start + pd.DateOffset(months=int(m))
    )
    df["end"] = df.apply(
        lambda row: row["start"] + pd.DateOffset(months=int(row["duration_months"])) - pd.Timedelta(days=1),
        axis=1,
    )

    # Label to display on Y axis
    df["label"] = df["id"] + " – " + df["name"]

    # If depends_on is missing for any task, fill with empty list / string for safety
    if "depends_on" not in df.columns:
        df["depends_on"] = [[] for _ in range(len(df))]

    return df, project_name


def make_gantt(
    df: pd.DataFrame,
    project_name: str,
    output_html: str = "phd_gantt.html",
) -> None:
    """
    Build and show an interactive Gantt chart.
    Also writes an HTML file you can open in a browser.
    """
    fig = px.timeline(
        df,
        x_start="start",
        x_end="end",
        y="label",
        color="work_package",
        hover_data=["phase", "depends_on"],
    )

    # Gantt-style ordering (earliest at top)
    fig.update_yaxes(autorange="reversed")

    fig.update_layout(
        title=f"Gantt chart – {project_name}",
        xaxis_title="Time",
        yaxis_title="Tasks",
    )

    # Save to HTML and show
    fig.write_html(output_html)
    fig.show()


def main():
    data = load_plan()
    df, project_name = build_dataframe(data)
    make_gantt(df, project_name)


if __name__ == "__main__":
    main()
