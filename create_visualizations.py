from pathlib import Path
import pandas as pd
import plotly.graph_objects as go


BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "output"
CHART_DIR = OUTPUT_DIR / "charts"
CHART_DIR.mkdir(exist_ok=True)

RESULT_FILE = OUTPUT_DIR / "python_optimization_result.xlsx"


def load_results():
    """Load scenario summary and output schedule from Python optimization result."""
    summary_df = pd.read_excel(RESULT_FILE, sheet_name="scenario_summary")
    schedule_df = pd.read_excel(RESULT_FILE, sheet_name="output_schedule")

    return summary_df, schedule_df


def create_gantt_chart(schedule_df: pd.DataFrame, scenario_id: str):
    """Create Gantt chart for one scenario."""

    df = schedule_df[schedule_df["scenario_id"] == scenario_id].copy()

    if df.empty:
        print(f"No schedule data for {scenario_id}")
        return

    df = df.sort_values(by=["start_time", "finish_time", "task_id"]).reset_index(drop=True)

    # Label shown on y-axis
    df["task_label"] = (
        df["task_id"].astype(str)
        + " - "
        + df["task_name_th"].astype(str)
        + " / "
        + df["worker_id"].astype(str)
    )

    fig = go.Figure()

    for _, row in df.iterrows():
        fig.add_trace(
            go.Bar(
                y=[row["task_label"]],
                x=[row["duration"]],
                base=[row["start_time"]],
                orientation="h",
                name=row["worker_id"],
                text=f"{row['start_time']}–{row['finish_time']} min",
                textposition="inside",
                hovertemplate=(
                    f"Task: {row['task_id']}<br>"
                    f"งาน: {row['task_name_th']}<br>"
                    f"Worker: {row['worker_id']}<br>"
                    f"Start: {row['start_time']} min<br>"
                    f"Finish: {row['finish_time']} min<br>"
                    f"Duration: {row['duration']} min"
                    "<extra></extra>"
                ),
            )
        )

    max_finish = int(df["finish_time"].max())

    fig.update_layout(
        title=f"Gantt Chart: Aircraft Cleaning Schedule ({scenario_id})",
        xaxis_title="Time (minutes)",
        yaxis_title="Task / Worker",
        barmode="stack",
        showlegend=False,
        height=500,
        width=1000,
        xaxis=dict(range=[0, max(30, max_finish + 2)]),
    )

    # Reverse y-axis so first task appears at top
    fig.update_yaxes(autorange="reversed")

    html_path = CHART_DIR / f"gantt_{scenario_id}.html"
    png_path = CHART_DIR / f"gantt_{scenario_id}.png"

    fig.write_html(html_path)

    try:
        fig.write_image(png_path, scale=2)
    except Exception as e:
        print(f"Could not export PNG for {scenario_id}. HTML is still created.")
        print(e)

    print(f"Saved Gantt chart for {scenario_id}: {html_path}")


def create_all_gantt_charts(schedule_df: pd.DataFrame):
    """Create Gantt chart for every scenario."""
    scenario_ids = schedule_df["scenario_id"].dropna().unique()

    for scenario_id in scenario_ids:
        create_gantt_chart(schedule_df, scenario_id)


def create_scenario_comparison_chart(summary_df: pd.DataFrame):
    """Create comparison chart for workers, Cmax, actual completion time, and buffer time."""

    df = summary_df.copy()
    df = df[df["feasible"] == "Yes"].copy()

    if df.empty:
        print("No feasible scenario found for comparison chart.")
        return

    df = df.sort_values(by=["num_workers"]).reset_index(drop=True)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=df["num_workers"],
            y=df["cmax"],
            name="Cmax",
            text=df["cmax"],
            textposition="auto",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["num_workers"],
            y=df["actual_completion_time"],
            mode="lines+markers+text",
            name="Actual Completion Time",
            text=df["actual_completion_time"],
            textposition="top center",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["num_workers"],
            y=df["buffer_time"],
            mode="lines+markers+text",
            name="Buffer Time",
            text=df["buffer_time"],
            textposition="bottom center",
        )
    )

    fig.update_layout(
        title="Scenario Comparison: Workers vs Cmax / Actual Time / Buffer",
        xaxis_title="Number of Workers",
        yaxis_title="Time (minutes)",
        width=1000,
        height=550,
        legend_title="Metric",
    )

    html_path = CHART_DIR / "scenario_comparison.html"
    png_path = CHART_DIR / "scenario_comparison.png"

    fig.write_html(html_path)

    try:
        fig.write_image(png_path, scale=2)
    except Exception as e:
        print("Could not export PNG for scenario comparison. HTML is still created.")
        print(e)

    print(f"Saved scenario comparison chart: {html_path}")


def create_cmax_improvement_chart(summary_df: pd.DataFrame):
    """Create chart showing percentage improvement in Cmax compared with base case."""

    df = summary_df.copy()
    df = df[df["feasible"] == "Yes"].copy()

    if df.empty:
        print("No feasible scenario found for improvement chart.")
        return

    df = df.sort_values(by=["num_workers"]).reset_index(drop=True)

    base_cmax = df.loc[0, "cmax"]
    df["cmax_reduction_percent"] = ((base_cmax - df["cmax"]) / base_cmax) * 100

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=df["num_workers"],
            y=df["cmax_reduction_percent"],
            text=df["cmax_reduction_percent"].round(1).astype(str) + "%",
            textposition="auto",
            name="Cmax Reduction (%)",
        )
    )

    fig.update_layout(
        title="Cmax Reduction Compared with Base Case",
        xaxis_title="Number of Workers",
        yaxis_title="Cmax Reduction (%)",
        width=900,
        height=500,
    )

    html_path = CHART_DIR / "cmax_reduction.html"
    png_path = CHART_DIR / "cmax_reduction.png"

    fig.write_html(html_path)

    try:
        fig.write_image(png_path, scale=2)
    except Exception as e:
        print("Could not export PNG for Cmax reduction chart. HTML is still created.")
        print(e)

    print(f"Saved Cmax reduction chart: {html_path}")


def main():
    summary_df, schedule_df = load_results()

    create_all_gantt_charts(schedule_df)
    create_scenario_comparison_chart(summary_df)
    create_cmax_improvement_chart(summary_df)

    print("\nAll charts created successfully.")
    print(f"Charts folder: {CHART_DIR}")


if __name__ == "__main__":
    main()
    