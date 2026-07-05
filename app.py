from pathlib import Path
from io import BytesIO

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# =========================
# Page config
# =========================
st.set_page_config(
    page_title="Aircraft Cleaning Optimization Dashboard",
    page_icon="✈️",
    layout="wide",
)


# =========================
# Path setting
# =========================
BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_RESULT_FILE = BASE_DIR / "output" / "python_optimization_result.xlsx"


# =========================
# Helper functions
# =========================
@st.cache_data
def load_result_file(file):
    """Load scenario_summary and output_schedule from Excel result file."""
    summary_df = pd.read_excel(file, sheet_name="scenario_summary")
    schedule_df = pd.read_excel(file, sheet_name="output_schedule")

    return summary_df, schedule_df


def create_gantt_chart(schedule_df: pd.DataFrame, scenario_id: str):
    """Create Gantt Chart using Plotly Bar Chart with start_time as base."""
    df = schedule_df[schedule_df["scenario_id"] == scenario_id].copy()

    if df.empty:
        return None

    df = df.sort_values(by=["start_time", "finish_time", "task_id"]).reset_index(drop=True)

    df["task_label"] = (
        df["task_id"].astype(str)
        + " | "
        + df["task_name_th"].astype(str)
        + " | "
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
                name=str(row["worker_id"]),
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
        height=520,
        showlegend=False,
        barmode="overlay",
        xaxis=dict(range=[0, max(30, max_finish + 2)]),
        margin=dict(l=20, r=20, t=60, b=40),
    )

    fig.update_yaxes(autorange="reversed")

    return fig


def create_scenario_comparison_chart(summary_df: pd.DataFrame):
    """Create chart comparing Cmax, Actual Completion Time, and Buffer Time."""
    df = summary_df.copy()
    df = df[df["feasible"] == "Yes"].copy()

    if df.empty:
        return None

    df = df.sort_values(by=["num_workers"])

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
        title="Scenario Comparison",
        xaxis_title="Number of Workers",
        yaxis_title="Time (minutes)",
        height=500,
        legend_title="Metric",
        margin=dict(l=20, r=20, t=60, b=40),
    )

    return fig


def create_cmax_reduction_chart(summary_df: pd.DataFrame):
    """Create Cmax reduction percentage chart compared with base case."""
    df = summary_df.copy()
    df = df[df["feasible"] == "Yes"].copy()

    if df.empty:
        return None

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
            name="Cmax Reduction",
        )
    )

    fig.update_layout(
        title="Cmax Reduction Compared with Base Case",
        xaxis_title="Number of Workers",
        yaxis_title="Cmax Reduction (%)",
        height=450,
        margin=dict(l=20, r=20, t=60, b=40),
    )

    return fig


def dataframe_to_excel_download(summary_df: pd.DataFrame, schedule_df: pd.DataFrame):
    """Convert result dataframes to Excel file for download."""
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="scenario_summary", index=False)
        schedule_df.to_excel(writer, sheet_name="output_schedule", index=False)

    output.seek(0)

    return output


# =========================
# App title
# =========================
st.title("✈️ Aircraft Cleaning Optimization Dashboard")
st.caption("Dashboard สำหรับแสดงผลการจัดตารางงานทำความสะอาดเครื่องบินจาก Python OR-Tools CP-SAT")


# =========================
# Sidebar
# =========================
st.sidebar.header("Control Panel")

uploaded_file = st.sidebar.file_uploader(
    "Upload result file (.xlsx)",
    type=["xlsx"],
)

if uploaded_file is not None:
    result_file = uploaded_file
    st.sidebar.success("ใช้ไฟล์ที่ Upload แล้ว")
else:
    result_file = DEFAULT_RESULT_FILE
    st.sidebar.info("ใช้ไฟล์ Default จากโฟลเดอร์ output")


# =========================
# Load data
# =========================
try:
    summary_df, schedule_df = load_result_file(result_file)
except FileNotFoundError:
    st.error(
        "ไม่พบไฟล์ผลลัพธ์ กรุณารัน solve_aircraft_cleaning.py ก่อน "
        "หรือ Upload ไฟล์ python_optimization_result.xlsx"
    )
    st.stop()
except Exception as e:
    st.error(f"อ่านไฟล์ไม่ได้: {e}")
    st.stop()


# =========================
# Scenario selection
# =========================
scenario_list = summary_df["scenario_id"].dropna().astype(str).tolist()

selected_scenario = st.sidebar.selectbox(
    "Select Scenario",
    scenario_list,
)

selected_summary = summary_df[
    summary_df["scenario_id"].astype(str) == selected_scenario
].iloc[0]

selected_schedule = schedule_df[
    schedule_df["scenario_id"].astype(str) == selected_scenario
].copy()


# =========================
# KPI section
# =========================
st.subheader(f"Selected Scenario: {selected_scenario}")

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("Aircraft Type", selected_summary["aircraft_type"])
col2.metric("Workers", int(selected_summary["num_workers"]))
col3.metric("Actual Time", f"{selected_summary['actual_completion_time']} min")
col4.metric("Cmax", f"{selected_summary['cmax']} min")
col5.metric("Buffer", f"{selected_summary['buffer_time']} min")

feasible = selected_summary["feasible"]

if feasible == "Yes":
    st.success("Feasible: ตารางงานนี้สามารถทำเสร็จภายใน Turnaround Time")
else:
    st.error("Not Feasible: ตารางงานนี้ยังไม่สามารถใช้ได้ ต้องปรับจำนวนพนักงานหรือเวลางาน")


# =========================
# Tabs
# =========================
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "📊 Dashboard",
        "📅 Gantt Chart",
        "📋 Output Schedule",
        "📈 Scenario Summary",
        "🧠 Model Explanation",
    ]
)


with tab1:
    st.subheader("Scenario Comparison")

    fig_compare = create_scenario_comparison_chart(summary_df)
    if fig_compare is not None:
        st.plotly_chart(fig_compare, use_container_width=True)
    else:
        st.warning("ไม่มี Scenario ที่ Feasible สำหรับสร้างกราฟเปรียบเทียบ")

    fig_reduction = create_cmax_reduction_chart(summary_df)
    if fig_reduction is not None:
        st.plotly_chart(fig_reduction, use_container_width=True)

    st.markdown(
        """
        **การอ่านผลเบื้องต้น**

        - Cmax ใช้บอกภาระงานสูงสุดของพนักงานคนใดคนหนึ่ง  
        - Actual Completion Time ใช้บอกเวลาที่กระบวนการทำความสะอาดเสร็จจริง  
        - Buffer Time คือเวลาที่เหลือก่อนถึง Turnaround Time  
        """
    )


with tab2:
    st.subheader("Gantt Chart")

    fig_gantt = create_gantt_chart(schedule_df, selected_scenario)

    if fig_gantt is not None:
        st.plotly_chart(fig_gantt, use_container_width=True)
    else:
        st.warning("ไม่มีข้อมูลตารางงานของ Scenario นี้")

    st.markdown(
        """
        **คำอธิบาย Gantt Chart**

        กราฟนี้แสดงว่าแต่ละงานเริ่มเวลาใด เสร็จเวลาใด และพนักงานคนใดเป็นผู้รับผิดชอบ  
        ถ้าแท่งงานของพนักงานคนเดียวกันไม่ซ้อนกัน แสดงว่าแผนงานไม่มีปัญหาการทำงานชนกัน
        """
    )


with tab3:
    st.subheader("Output Schedule")

    if selected_schedule.empty:
        st.warning("ไม่มีข้อมูล Output Schedule")
    else:
        st.dataframe(selected_schedule, use_container_width=True)

        csv_data = selected_schedule.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            label="Download Selected Schedule as CSV",
            data=csv_data,
            file_name=f"schedule_{selected_scenario}.csv",
            mime="text/csv",
        )


with tab4:
    st.subheader("Scenario Summary")

    st.dataframe(summary_df, use_container_width=True)

    excel_data = dataframe_to_excel_download(summary_df, schedule_df)

    st.download_button(
        label="Download Result as Excel",
        data=excel_data,
        file_name="streamlit_dashboard_result.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


with tab5:
    st.subheader("Model Explanation")

    st.markdown(
        """
        ### แนวคิดของโมเดล

        โมเดลนี้ใช้ผลลัพธ์จาก Python OR-Tools CP-SAT เพื่อแสดงผลการจัดตารางงานทำความสะอาดเครื่องบิน  
        โดยพิจารณาองค์ประกอบหลัก ได้แก่

        1. งานทำความสะอาดแต่ละงาน  
        2. เวลาที่ใช้ของแต่ละงาน  
        3. จำนวนพนักงาน  
        4. ลำดับก่อน–หลังของงาน  
        5. ข้อจำกัดว่าพนักงานคนเดียวกันไม่สามารถทำงานซ้อนกันได้  

        ### ตัวชี้วัดหลัก

        | KPI | ความหมาย |
        |---|---|
        | Actual Completion Time | เวลาที่กระบวนการทำความสะอาดเสร็จจริง |
        | Cmax | ภาระงานสูงสุดของพนักงาน |
        | Buffer Time | เวลาที่เหลือก่อนถึง Turnaround Time |
        | Feasible | แผนงานสามารถทำเสร็จภายในเวลาที่กำหนดหรือไม่ |

        ### การใช้งาน

        ผู้ใช้สามารถเลือก Scenario จากด้านซ้ายของหน้าจอ แล้ว Dashboard จะแสดงผลลัพธ์ของ Scenario นั้นโดยอัตโนมัติ
        """
    )
    