# src/solve_aircraft_cleaning.py

from pathlib import Path
import pandas as pd
from ortools.sat.python import cp_model


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = BASE_DIR / "data" / "python_input_data.xlsx"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

OUTPUT_XLSX = OUTPUT_DIR / "python_optimization_result.xlsx"


def load_input_data(file_path: Path) -> dict:
    """Read all input sheets from Excel."""
    data = {
        "aircraft_master": pd.read_excel(file_path, sheet_name="aircraft_master"),
        "task_master": pd.read_excel(file_path, sheet_name="task_master"),
        "precedence": pd.read_excel(file_path, sheet_name="precedence"),
        "worker_master": pd.read_excel(file_path, sheet_name="worker_master"),
        "scenarios": pd.read_excel(file_path, sheet_name="scenarios"),
    }

    # Clean column names
    for key, df in data.items():
        df.columns = [str(col).strip() for col in df.columns]

    return data


def solve_one_scenario(data: dict, scenario: pd.Series) -> tuple[dict, pd.DataFrame]:
    """Solve one aircraft cleaning scheduling scenario using OR-Tools CP-SAT."""

    scenario_id = scenario["scenario_id"]
    aircraft_type = scenario["aircraft_type"]
    cleaning_type = scenario["cleaning_type"]
    num_workers = int(scenario["num_workers"])
    turnaround_time = int(scenario["turnaround_time"])

    task_df = data["task_master"].copy()
    worker_df = data["worker_master"].copy()
    precedence_df = data["precedence"].copy()

    # Filter tasks for aircraft and cleaning type
    task_df = task_df[
        (task_df["aircraft_type"] == aircraft_type)
        & (task_df["cleaning_type"] == cleaning_type)
    ].reset_index(drop=True)

    if task_df.empty:
        summary = {
            "scenario_id": scenario_id,
            "aircraft_type": aircraft_type,
            "cleaning_type": cleaning_type,
            "num_workers": num_workers,
            "turnaround_time": turnaround_time,
            "status": "No task data",
            "actual_completion_time": None,
            "cmax": None,
            "buffer_time": None,
            "feasible": "No",
        }
        return summary, pd.DataFrame()

    # Select available workers
    worker_df = worker_df[worker_df["available"] == 1].reset_index(drop=True)

    if len(worker_df) < num_workers:
        summary = {
            "scenario_id": scenario_id,
            "aircraft_type": aircraft_type,
            "cleaning_type": cleaning_type,
            "num_workers": num_workers,
            "turnaround_time": turnaround_time,
            "status": "Not enough workers",
            "actual_completion_time": None,
            "cmax": None,
            "buffer_time": None,
            "feasible": "No",
        }
        return summary, pd.DataFrame()

    worker_df = worker_df.head(num_workers)

    tasks = task_df["task_id"].tolist()
    workers = worker_df["worker_id"].tolist()

    duration = {
        row["task_id"]: int(row["duration_min"])
        for _, row in task_df.iterrows()
    }

    task_name_th = {
        row["task_id"]: row["task_name_th"]
        for _, row in task_df.iterrows()
    }

    # Filter precedence
    precedence_df = precedence_df[
        (precedence_df["aircraft_type"] == aircraft_type)
        & (precedence_df["cleaning_type"] == cleaning_type)
    ].reset_index(drop=True)

    precedence_pairs = []
    for _, row in precedence_df.iterrows():
        before = row["before_task"]
        after = row["after_task"]
        if before in tasks and after in tasks:
            precedence_pairs.append((before, after))

    horizon = sum(duration[t] for t in tasks)
    model = cp_model.CpModel()

    # -----------------------------
    # Decision variables
    # -----------------------------
    start = {}
    end = {}
    assign = {}
    optional_intervals = {w: [] for w in workers}

    for t in tasks:
        start[t] = model.NewIntVar(0, horizon, f"start_{t}")
        end[t] = model.NewIntVar(0, horizon, f"end_{t}")

        # End = Start + Duration
        model.Add(end[t] == start[t] + duration[t])

        for w in workers:
            assign[(t, w)] = model.NewBoolVar(f"assign_{t}_{w}")

            interval = model.NewOptionalIntervalVar(
                start[t],
                duration[t],
                end[t],
                assign[(t, w)],
                f"interval_{t}_{w}",
            )

            optional_intervals[w].append(interval)

    # -----------------------------
    # Constraints
    # -----------------------------

    # 1) Each task must be assigned to exactly one worker
    for t in tasks:
        model.AddExactlyOne(assign[(t, w)] for w in workers)

    # 2) Same worker cannot do overlapping tasks
    for w in workers:
        model.AddNoOverlap(optional_intervals[w])

    # 3) Precedence constraints
    for before, after in precedence_pairs:
        model.Add(start[after] >= end[before])

    # 4) Actual completion time / makespan
    actual_completion_time = model.NewIntVar(0, horizon, "actual_completion_time")
    model.AddMaxEquality(actual_completion_time, [end[t] for t in tasks])

    # 5) Must finish within turnaround time
    model.Add(actual_completion_time <= turnaround_time)

    # 6) Workload and Cmax
    cmax = model.NewIntVar(0, horizon, "cmax")

    for w in workers:
        workload_w = sum(duration[t] * assign[(t, w)] for t in tasks)
        model.Add(workload_w <= cmax)

    # -----------------------------
    # Objective
    # -----------------------------
    # Prioritize minimizing actual completion time first,
    # then minimize workload balance.
    model.Minimize(1000 * actual_completion_time + cmax)

    # -----------------------------
    # Solve
    # -----------------------------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
    solver.parameters.num_search_workers = 8

    status = solver.Solve(model)

    status_name = solver.StatusName(status)

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        summary = {
            "scenario_id": scenario_id,
            "aircraft_type": aircraft_type,
            "cleaning_type": cleaning_type,
            "num_workers": num_workers,
            "turnaround_time": turnaround_time,
            "status": status_name,
            "actual_completion_time": None,
            "cmax": None,
            "buffer_time": None,
            "feasible": "No",
        }
        return summary, pd.DataFrame()

    # -----------------------------
    # Extract solution
    # -----------------------------
    schedule_rows = []

    worker_workload = {w: 0 for w in workers}

    for t in tasks:
        assigned_worker = None

        for w in workers:
            if solver.Value(assign[(t, w)]) == 1:
                assigned_worker = w
                worker_workload[w] += duration[t]
                break

        schedule_rows.append(
            {
                "scenario_id": scenario_id,
                "aircraft_type": aircraft_type,
                "cleaning_type": cleaning_type,
                "task_id": t,
                "task_name_th": task_name_th[t],
                "worker_id": assigned_worker,
                "start_time": solver.Value(start[t]),
                "finish_time": solver.Value(end[t]),
                "duration": duration[t],
            }
        )

    schedule_df = pd.DataFrame(schedule_rows)
    schedule_df = schedule_df.sort_values(
        by=["start_time", "finish_time", "task_id"]
    ).reset_index(drop=True)

    actual_time = solver.Value(actual_completion_time)
    cmax_value = solver.Value(cmax)
    buffer_time = turnaround_time - actual_time

    summary = {
        "scenario_id": scenario_id,
        "aircraft_type": aircraft_type,
        "cleaning_type": cleaning_type,
        "num_workers": num_workers,
        "turnaround_time": turnaround_time,
        "status": status_name,
        "actual_completion_time": actual_time,
        "cmax": cmax_value,
        "buffer_time": buffer_time,
        "feasible": "Yes" if buffer_time >= 0 else "No",
    }

    return summary, schedule_df


def main():
    data = load_input_data(DATA_PATH)

    all_summary = []
    all_schedule = []

    scenarios = data["scenarios"]

    for _, scenario in scenarios.iterrows():
        summary, schedule_df = solve_one_scenario(data, scenario)

        all_summary.append(summary)

        if not schedule_df.empty:
            all_schedule.append(schedule_df)

        print(
            f"Scenario {summary['scenario_id']}: "
            f"status={summary['status']}, "
            f"actual_time={summary['actual_completion_time']}, "
            f"cmax={summary['cmax']}"
        )

    summary_df = pd.DataFrame(all_summary)

    if all_schedule:
        output_schedule_df = pd.concat(all_schedule, ignore_index=True)
    else:
        output_schedule_df = pd.DataFrame()

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="scenario_summary", index=False)
        output_schedule_df.to_excel(writer, sheet_name="output_schedule", index=False)

    print(f"\nResult saved to: {OUTPUT_XLSX}")


if __name__ == "__main__":
    main()
    